from pathlib import Path
import joblib
import pandas as pd
import streamlit as st
import folium
from branca.element import Element
from streamlit_folium import st_folium

from src.prediction import predict_risk, apply_realtime_safety_layer
from src.data_analysis import load_data, feature_importance, create_feature_importance_chart
from src.weather_api import PROVINCES, fetch_province_data, fetch_rain_map, fetch_weather_forecast_7days
from src.usage_analytics import register_session, record_province, get_usage_stats
import uuid

st.set_page_config(page_title="KKU Smart Flood AI V3", page_icon="🌊", layout="wide")
st.title("🌊 KKU Smart Flood AI")
st.subheader("ระบบ AI สำหรับประเมินความเสี่ยงน้ำท่วมจากข้อมูลฝน ระดับน้ำ และสถานีตรวจวัดจริง")
st.info("V3 เชื่อมข้อมูล ThaiWater + Open-Meteo และแสดง Weather Forecast 7 วันตามจังหวัดที่เลือก พร้อม Real-time Water Safety Layer")

# สถิติการใช้งานแบบไม่เก็บ IP หรือข้อมูลระบุตัวบุคคล
if "usage_session_id" not in st.session_state:
    st.session_state.usage_session_id = str(uuid.uuid4())
    register_session(st.session_state.usage_session_id)
if st.session_state.get("last_recorded_province") != st.session_state.get("province_data_province"):
    # บันทึกเมื่อมีข้อมูลจังหวัดที่โหลดสำเร็จแล้วเท่านั้น (ดูบล็อกบันทึกด้านล่าง)
    pass


if not Path("models/flood_model.pkl").exists(): st.error("ไม่พบโมเดล กรุณารัน generate_data.py และ train_model.py"); st.stop()
bundle=joblib.load("models/flood_model.pkl"); df=load_data()
if "history" not in st.session_state: st.session_state.history=[]

st.header("1. เลือกจังหวัดและอัปเดตข้อมูล API")
province=st.selectbox("จังหวัดของพื้นที่ที่ต้องการวิเคราะห์ (77 จังหวัด)",list(PROVINCES.keys()),index=list(PROVINCES.keys()).index("ฉะเชิงเทรา"))
# ดึงข้อมูลใหม่โดยอัตโนมัติเมื่อเลือกจังหวัดที่ต่างจากข้อมูลใน session
# ปุ่มอัปเดตยังใช้สำหรับบังคับดึงข้อมูลล่าสุดของจังหวัดเดิมได้
province_changed = st.session_state.get("province_data_province") != province
manual_refresh = st.button("🔄 อัปเดตข้อมูล ThaiWater + สภาพอากาศ", use_container_width=True)
if province_changed or manual_refresh:
    try:
        with st.spinner(f"กำลังดึงข้อมูลล่าสุดของ {province}..."):
            fresh_data = fetch_province_data(province)
            fresh_forecast = fetch_weather_forecast_7days(province)
            st.session_state.province_data = fresh_data
            st.session_state.weather_forecast = fresh_forecast
            st.session_state.province_data_province = province
            st.session_state.weather_forecast_province = province
            if st.session_state.get("last_recorded_province") != province:
                record_province(st.session_state.usage_session_id, province)
                st.session_state.last_recorded_province = province
            st.session_state.api_error = None
            # ล้างผลเดิม เพื่อไม่ให้ผลของจังหวัดก่อนหน้าค้างอยู่
            for key in ("prediction", "model_prediction", "probabilities", "reasons", "prediction_province", "prediction_data_updated_at"):
                st.session_state.pop(key, None)
    except Exception as e:
        st.session_state.api_error = str(e)
        # ป้องกันการนำข้อมูลของจังหวัดก่อนหน้ามาใช้วิเคราะห์
        if st.session_state.get("province_data_province") != province:
            st.session_state.pop("province_data", None)
            st.session_state.pop("weather_forecast", None)
            st.session_state.pop("province_data_province", None)
            st.session_state.pop("weather_forecast_province", None)
if st.session_state.get("api_error"):
    st.error("ดึงข้อมูล API ไม่สำเร็จ: " + st.session_state.api_error)

data=st.session_state.get("province_data")
if data and st.session_state.get("province_data_province")==province:
    c=st.columns(4)
    c[0].metric("ฝน 1 ชม.",f"{data['rainfall_1h']:.1f} mm")
    c[1].metric("ฝน 24 ชม.",f"{data['rainfall_24h']:.1f} mm")
    c[2].metric("ฝนสะสม 3 วัน",f"{data['rainfall_3d']:.1f} mm" if data['rainfall_3d'] is not None else "ไม่มีข้อมูล")
    c[3].metric("ฝนสะสม 7 วัน",f"{data['rainfall_7d']:.1f} mm" if data['rainfall_7d'] is not None else "ไม่มีข้อมูล")

    c=st.columns(4)
    c[0].metric("ระดับน้ำสูงสุด",f"{data['water_level_m']:.2f} m" if data['water_level_m'] is not None else "ไม่มีข้อมูล")
    c[1].metric("แนวโน้มระดับน้ำ",f"{data['water_trend_m']:+.2f} m")
    c[2].metric("สถานีล้นตลิ่ง",str(data['overbank_count']))
    c[3].metric("สถานีเตือน/วิกฤต",str(data['warning_station_count']))
    st.caption(f"ThaiWater: {data['water_station_count']} สถานีระดับน้ำ | อัปเดตข้อมูลเมื่อ {data['updated_at']}")
    if data['overbank_count']>0: st.error(f"⚠️ พบสถานีน้ำล้นตลิ่ง {data['overbank_count']} สถานีในจังหวัด {province}")
    elif data['critical_station_count']>0: st.warning(f"⚠️ พบสถานีระดับวิกฤต {data['critical_station_count']} สถานี")
    if data['water_stations']:
        st.subheader("สถานีระดับน้ำล่าสุด")
        st.caption("ลิงก์อ้างอิงรายสถานี: กด “เปิดสถานี ↗” เพื่อดูรายละเอียดของสถานีนั้นบน THData")
        station_df = pd.DataFrame(data['water_stations']).rename(columns={
            "station": "ชื่อสถานี", "level_msl": "ระดับน้ำล่าสุด (ม. MSL)",
            "trend_m": "แนวโน้ม (ม.)", "situation_level": "ระดับสถานการณ์",
            "bank_status": "สถานะเทียบตลิ่ง", "source_url": "อ้างอิงระดับน้ำ"
        })
        if "อ้างอิงระดับน้ำ" not in station_df.columns:
            station_df["อ้างอิงระดับน้ำ"] = "https://water.thdata.co/"
        st.dataframe(
            station_df, use_container_width=True, hide_index=True,
            column_config={
                "อ้างอิงระดับน้ำ": st.column_config.LinkColumn(
                    "อ้างอิงระดับน้ำ", display_text="เปิดสถานี ↗",
                    help="เปิดหน้ารายละเอียดของสถานีนี้บน THData"
                ),
                "ระดับน้ำล่าสุด (ม. MSL)": st.column_config.NumberColumn(format="%.2f"),
                "แนวโน้ม (ม.)": st.column_config.NumberColumn(format="%+.2f")
            }
        )

    forecast=st.session_state.get("weather_forecast")
    if forecast and st.session_state.get("weather_forecast_province")==province:
        st.subheader("🌤️ Weather Forecast 7 วัน")
        st.caption(f"เริ่มจากวันนี้ • จังหวัด {province} • ข้อมูลพยากรณ์จาก Open-Meteo")
        cards=[]
        for day in forecast["forecast"]:
            tmax="-" if day["temp_max"] is None else f"{day['temp_max']:.0f}°"
            tmin="-" if day["temp_min"] is None else f"{day['temp_min']:.0f}°"
            p="-" if day["rain_probability"] is None else f"{day['rain_probability']:.0f}%"
            cards.append(f"""<div style='flex:1;min-width:135px;background:#fff;border:1px solid #d9e2ec;border-radius:12px;padding:12px 10px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06)'>
<div style='font-size:15px;font-weight:700;color:#17324d'>{day['label']}</div>
<div style='font-size:12px;color:#64748b'>{day['date']}</div>
<div style='font-size:34px;margin:6px 0'>{day['icon']}</div>
<div style='font-size:12px;min-height:36px;color:#334155'>{day['description']}</div>
<div style='font-size:17px;font-weight:700;margin-top:6px'>{tmax} / {tmin}C</div>
<div style='font-size:12px;color:#2563eb;margin-top:5px'>🌧️ ฝน {day['rain_mm']:.1f} mm</div>
<div style='font-size:12px;color:#475569'>โอกาสฝน {p}</div>
</div>""")
        st.markdown("<div style='display:flex;gap:10px;overflow-x:auto;padding:4px 0 12px'>"+"".join(cards)+"</div>",unsafe_allow_html=True)
else:
    st.warning("กดปุ่มอัปเดตเพื่อดึงข้อมูลล่าสุดจาก ThaiWater และ Open-Meteo")

st.header("🗺️ แผนที่ฝน 24 ชั่วโมงย้อนหลัง")

# Load automatically on the first page visit; keep the manual refresh button.
if "rain_map" not in st.session_state and "rain_map_error" not in st.session_state:
    try:
        with st.spinner("กำลังโหลดข้อมูลสถานีฝน 24 ชั่วโมงย้อนหลัง..."):
            st.session_state.rain_map=fetch_rain_map()
            st.session_state.rain_map_error=None
    except Exception as e:
        st.session_state.rain_map=[]
        st.session_state.rain_map_error=str(e)

if st.button("📍 โหลด/รีเฟรชแผนที่ฝน",use_container_width=True):
    try:
        with st.spinner("กำลังอัปเดตแผนที่ฝน 24 ชั่วโมงย้อนหลัง..."):
            st.session_state.rain_map=fetch_rain_map()
            st.session_state.rain_map_error=None
    except Exception as e:
        st.session_state.rain_map=[]
        st.session_state.rain_map_error=str(e)

if st.session_state.get("rain_map_error"):
    st.error("โหลดแผนที่ไม่สำเร็จ: "+st.session_state.rain_map_error)

points=st.session_state.get("rain_map",[])
if points:
    selected_lat, selected_lon = PROVINCES.get(province, (13.5, 101.0))
    province_points = [p for p in points if str(p.get("province", "")).strip() == province]
    st.caption(
        f"พบจุดข้อมูลฝน {len(points):,} จุด | จังหวัดที่เลือก: {province} "
        f"(จุดสถานีที่จับคู่ชื่อจังหวัดได้ {len(province_points):,} จุด) | "
        f"แหล่งข้อมูล: {points[0].get('source', 'ไม่ระบุ')}"
    )
    # Focus the map on the selected province and pin its representative province coordinate.
    m=folium.Map(location=[selected_lat,selected_lon],zoom_start=8,tiles="OpenStreetMap")
    folium.Marker(
        [selected_lat,selected_lon],
        tooltip=f"จังหวัดที่เลือก: {province}",
        popup=folium.Popup(
            f"<b>จังหวัดที่เลือก: {province}</b><br>หมุดนี้เป็นพิกัดตัวแทนจังหวัด ไม่ใช่พิกัดสถานีวัดฝน",
            max_width=320
        ),
        icon=folium.Icon(color="purple",icon="map-marker",prefix="fa")
    ).add_to(m)
    folium.Circle([selected_lat,selected_lon],radius=18000,color="purple",fill=False,weight=2).add_to(m)
    def rain_color(v):
        if v<=10:return "blue"
        if v<=20:return "lightblue"
        if v<=35:return "green"
        if v<=50:return "yellow"
        if v<=70:return "orange"
        if v<=90:return "darkorange"
        return "red"
    for p in points:
        is_selected_province = str(p.get("province", "")).strip() == province
        popup=f"<b>{p['station']}</b><br>จังหวัด: {p['province']}<br>ฝน 24 ชม.: {p['rain_24h']:.1f} mm<br>เวลา: {p['time']}"
        folium.CircleMarker(
            [p['lat'],p['lon']], radius=7 if is_selected_province else 4,
            color="magenta" if is_selected_province else rain_color(p['rain_24h']),
            fill=True, fill_color="magenta" if is_selected_province else rain_color(p['rain_24h']),
            fill_opacity=.9 if is_selected_province else .7,
            weight=3 if is_selected_province else 1,
            tooltip=f"{p['station']} — {p['province']}" + (" (จังหวัดที่เลือก)" if is_selected_province else ""),
            popup=folium.Popup(popup,max_width=300)
        ).add_to(m)
    legend = """<div style='position: fixed; bottom: 20px; left: 20px; z-index: 9999; background: white; padding: 10px 12px; border: 1px solid #999; border-radius: 6px; font-size: 12px; box-shadow: 0 1px 5px rgba(0,0,0,.25)'>
    <b>เกณฑ์ฝน 24 ชม. (mm)</b><br>
    <span style='color:blue'>●</span> ≤10 &nbsp; <span style='color:lightblue'>●</span> &gt;10–20 &nbsp; <span style='color:green'>●</span> &gt;20–35 &nbsp; <span style='color:#d6b400'>●</span> &gt;35–50 &nbsp; <span style='color:orange'>●</span> &gt;50–70 &nbsp; <span style='color:darkorange'>●</span> &gt;70–90 &nbsp; <span style='color:red'>●</span> &gt;90
    </div>"""
    m.get_root().html.add_child(Element(legend))
    st_folium(m,use_container_width=True,height=620,returned_objects=[])
    sources=sorted({p.get("source", "API") for p in points})
    st.caption(f"แสดงสถานีฝน {len(points):,} สถานี | แหล่งข้อมูล: {", ".join(sources)} | จุดสีแดง/ส้มเข้มแสดงสถานีที่มีฝนสะสม 24 ชั่วโมงสูง")
else:
    st.warning("ยังไม่สามารถโหลดข้อมูลสถานีฝน 24 ชั่วโมงย้อนหลังได้")
    st.caption("แหล่งข้อมูลแผนที่: RID SWOC/HII → ThaiWater → Open-Meteo (สำรองอัตโนมัติ)")

st.header("2. AI Flood Risk Analysis")
# ผลวิเคราะห์ต้องผูกกับจังหวัดและ timestamp ของข้อมูลที่กำลังแสดงในข้อ 1
if data and st.session_state.get("province_data_province") == province:
    data_updated_at = str(data.get("updated_at", "ไม่ระบุเวลา"))
    prediction_is_current = (
        st.session_state.get("prediction_province") == province
        and st.session_state.get("prediction_data_updated_at") == data_updated_at
    )
    if data.get("water_level_m") is None:
        st.warning(f"จังหวัด{province} ยังไม่มีข้อมูลระดับน้ำเพียงพอ จึงไม่แสดงผลวิเคราะห์ใหม่")
        for key in ("prediction", "model_prediction", "probabilities", "reasons", "prediction_province", "prediction_data_updated_at"):
            st.session_state.pop(key, None)
    else:
        if not prediction_is_current:
            try:
                model_pred, model_probs = predict_risk(data)
                final, final_probs, reasons = apply_realtime_safety_layer(model_pred, model_probs, data)
                st.session_state.prediction = final
                st.session_state.model_prediction = model_pred
                st.session_state.probabilities = final_probs
                st.session_state.reasons = reasons
                st.session_state.prediction_province = province
                st.session_state.prediction_data_updated_at = data_updated_at
                st.session_state.history.insert(0, {
                    "จังหวัด": province,
                    "ฝน1ชม.(mm)": data.get("rainfall_1h"),
                    "ฝน24ชม.(mm)": data.get("rainfall_24h"),
                    "ฝน3วัน(mm)": data.get("rainfall_3d"),
                    "ระดับน้ำ(m)": data.get("water_level_m"),
                    "ล้นตลิ่ง": data.get("overbank_count"),
                    "AI Model": model_pred,
                    "Final Risk": final,
                    "อัปเดตข้อมูล": data_updated_at,
                })
            except Exception as e:
                st.error(f"ไม่สามารถวิเคราะห์ข้อมูลของจังหวัด{province} ได้: {e}")
        st.caption(f"จังหวัดที่วิเคราะห์: {province} | อ้างอิงข้อมูลล่าสุด: {data_updated_at}")
        if st.button("🔎 วิเคราะห์ซ้ำจากข้อมูลจังหวัดนี้", type="primary", use_container_width=True):
            try:
                model_pred, model_probs = predict_risk(data)
                final, final_probs, reasons = apply_realtime_safety_layer(model_pred, model_probs, data)
                st.session_state.prediction = final
                st.session_state.model_prediction = model_pred
                st.session_state.probabilities = final_probs
                st.session_state.reasons = reasons
                st.session_state.prediction_province = province
                st.session_state.prediction_data_updated_at = data_updated_at
                st.session_state.history.insert(0, {
                    "จังหวัด": province,
                    "ฝน1ชม.(mm)": data.get("rainfall_1h"),
                    "ฝน24ชม.(mm)": data.get("rainfall_24h"),
                    "ฝน3วัน(mm)": data.get("rainfall_3d"),
                    "ระดับน้ำ(m)": data.get("water_level_m"),
                    "ล้นตลิ่ง": data.get("overbank_count"),
                    "AI Model": model_pred,
                    "Final Risk": final,
                    "อัปเดตข้อมูล": data_updated_at,
                })
                st.rerun()
            except Exception as e:
                st.error(f"ไม่สามารถวิเคราะห์ข้อมูลของจังหวัด{province} ได้: {e}")
else:
    st.warning("กรุณารอให้ข้อ 1 ดึงข้อมูลของจังหวัดที่เลือกสำเร็จก่อน ระบบจึงจะวิเคราะห์ความเสี่ยงจากข้อมูลชุดเดียวกันได้")

if ("prediction" in st.session_state
        and st.session_state.get("prediction_province") == province
        and st.session_state.get("province_data_province") == province):
    labels = {"LOW": "🟢 ความเสี่ยงต่ำ", "MEDIUM": "🟡 ความเสี่ยงปานกลาง", "HIGH": "🔴 ความเสี่ยงสูง"}
    st.success(f"ผลการประเมินจังหวัด{province}: {labels[st.session_state.prediction]}")
    if st.session_state.get("model_prediction") != st.session_state.prediction:
        st.warning(f"AI Model เดิมประเมิน {st.session_state.model_prediction} แต่ Real-time Water Safety Layer ปรับเป็น {st.session_state.prediction} จากข้อมูลสถานีจริง")
    if st.session_state.get("reasons"):
        st.write("**เหตุผลจากข้อมูลปัจจุบัน:**")
        for r in st.session_state.reasons:
            st.write("• " + r)
    p = st.session_state.probabilities
    a, b, c = st.columns(3)
    a.metric("LOW", f"{p.get('LOW', 0)*100:.2f}%")
    b.metric("MEDIUM", f"{p.get('MEDIUM', 0)*100:.2f}%")
    c.metric("HIGH", f"{p.get('HIGH', 0)*100:.2f}%")

st.header("3. AI Model Performance")
a,b,c=st.columns(3); a.metric("Model Accuracy",f"{bundle['accuracy']*100:.2f}%"); b.metric("Decision Trees",bundle['model'].n_estimators); c.metric("Training Dataset",len(df))
st.caption("Accuracy มาจาก Synthetic Prototype Dataset ไม่ใช่ความแม่นยำที่ผ่านการรับรองจากข้อมูลน้ำท่วมจริง")

st.header("4. AI Feature Importance")
imp=feature_importance(); st.dataframe(imp.style.format({"Importance":"{:.4f}"}),use_container_width=True,hide_index=True)
if not Path("images/feature_importance.png").exists(): create_feature_importance_chart()
st.image("images/feature_importance.png",use_container_width=True)

st.header("5. วิเคราะห์ข้อมูล")
x,y=st.columns(2)
with x: st.subheader("จำนวนข้อมูลแต่ละระดับ"); st.bar_chart(df["Risk"].value_counts())
with y: st.subheader("ตัวอย่าง Training Dataset"); st.dataframe(df.head(10),use_container_width=True)

st.header("6. ประวัติการวิเคราะห์")
if st.session_state.history:
    st.dataframe(pd.DataFrame(st.session_state.history),use_container_width=True,hide_index=True)
    if st.button("ล้างประวัติ"): st.session_state.history=[]; st.rerun()
else: st.write("ยังไม่มีประวัติ")

st.header("7. แหล่งข้อมูลและข้อจำกัด")
st.markdown("""**ThaiWater** — ข้อมูลฝนและระดับน้ำจากสถานีตรวจวัดของคลังข้อมูลน้ำแห่งชาติ

**Open-Meteo** — อุณหภูมิ ความชื้น สภาพอากาศปัจจุบัน และ Weather Forecast 7 วันของพิกัดตัวแทนจังหวัด

**AI Model** — Random Forest ที่ฝึกด้วย Synthetic Prototype Dataset ที่ออกแบบให้เรียนรู้หลายตัวแปรด้านฝนและน้ำ

**Real-time Water Safety Layer** — ชั้นตรวจสอบข้อมูลสถานีจริง เช่น น้ำล้นตลิ่ง ระดับวิกฤต และแนวโน้มระดับน้ำ เพื่อไม่ให้โมเดลต้นแบบให้ LOW ทั้งที่ข้อมูลภาคสนามอยู่ในภาวะอันตราย

**ข้อจำกัด:** โปรเจกต์นี้ยังไม่ใช่ระบบเตือนภัยอย่างเป็นทางการ และโมเดลยังไม่ได้รับการ validate ด้วยชุดข้อมูลน้ำท่วมจริงในระยะยาว จึงไม่ควรใช้แทนประกาศเตือนภัยจากหน่วยงานรัฐ""")
st.warning("⚠️ ใช้เพื่อการศึกษาและพัฒนา Portfolio ไม่ใช่ระบบตัดสินใจด้านความปลอดภัยในสถานการณ์จริง")


st.divider()
with st.expander("📊 สถิติการใช้งานเว็บไซต์", expanded=False):
    try:
        usage = get_usage_stats()
        st.caption("สถิติจากฐานข้อมูล SQLite ของแอปนี้ นับจำนวนเซสชันและการเลือกจังหวัด โดยไม่เก็บ IP หรือชื่อผู้ใช้")
        a, b = st.columns(2)
        a.metric("เซสชันที่บันทึกไว้", f"{usage['sessions']:,}")
        b.metric("การเปิดดูจังหวัด", f"{usage['province_views']:,}")
        if usage["top_provinces"]:
            st.markdown("**จังหวัดที่ถูกเลือกบ่อย (5 อันดับแรก)**")
            st.dataframe(
                pd.DataFrame(usage["top_provinces"], columns=["จังหวัด", "จำนวนครั้งที่บันทึก"]),
                use_container_width=True, hide_index=True
            )
        st.caption("หมายเหตุ: เป็นสถิติจากไฟล์ฐานข้อมูลของแอป ไม่ใช่จำนวนคนจริงแบบไม่ซ้ำกัน และอาจเริ่มนับใหม่เมื่อแพลตฟอร์มลบไฟล์หรือรีสตาร์ตระบบ")
    except Exception:
        st.info("ขณะนี้ยังไม่สามารถอ่านสถิติการใช้งานได้")

st.divider()
st.markdown(
    """
    <div style="text-align:center; padding: 12px 0 6px 0; color: #6b7280; font-size: 0.9rem;">
      <strong>ผู้พัฒนา: นาย วชิรวิทย์ ดอนซุยแป</strong><br>
      โรงเรียนพุทธิรังสีพิบูล · จังหวัดฉะเชิงเทรา<br>
      KKU Smart Flood AI V3.3
    </div>
    """,
    unsafe_allow_html=True,
)
