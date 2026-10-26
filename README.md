# KKU Smart Flood AI — V3.1

โปรเจกต์ต้นแบบสำหรับ Portfolio: ระบบ AI ประเมินความเสี่ยงน้ำท่วมจากข้อมูลฝน ระดับน้ำ และสถานีตรวจวัดจริง

## V3.1 มีอะไรใหม่
- เชื่อม ThaiWater public API: ฝน 24 ชม. + ระดับน้ำล่าสุด
- ดึงฝนสะสม 3 วัน/7 วันจาก endpoint ของ ThaiWater เมื่อมีข้อมูล
- วิเคราะห์สถานีล้นตลิ่ง / เตือนภัย / วิกฤต และแนวโน้มระดับน้ำ
- แผนที่ฝน 24 ชั่วโมงแบบ Interactive ด้วย Folium
- Open-Meteo สำหรับอุณหภูมิ ความชื้น และลม
- Random Forest รุ่นใหม่ที่ใช้ feature ด้านฝนและระดับน้ำมากขึ้น
- Real-time Water Safety Layer: ถ้าข้อมูล ThaiWater ระบุว่าน้ำล้นตลิ่ง/ระดับวิกฤต ระบบจะไม่ปล่อยให้ผลสุดท้ายเป็น LOW โดยไม่แสดงเหตุผล
- เปลี่ยนหัวข้อเป็น `AI Flood Risk Analysis` และ `AI Model Performance`

## สำคัญ
โมเดล ML ยังเป็น **Synthetic Prototype Dataset** ไม่ใช่โมเดลที่ผ่านการ validate ด้วยข้อมูลน้ำท่วมจริง ดังนั้นค่า Accuracy ใช้เพื่อแสดงประสิทธิภาพของต้นแบบเท่านั้น ส่วนข้อมูล ThaiWater เป็นข้อมูลภาคสนามล่าสุดที่ระบบดึงมาใช้ร่วมกับ safety layer

## วิธีรัน
```bash
pip install -r requirements.txt
python generate_data.py
python train_model.py
streamlit run app.py
```

## Deploy Streamlit
ตั้ง Main file เป็น `app.py` และติดตั้ง dependencies จาก `requirements.txt`

## แหล่งข้อมูล
- ThaiWater public API: https://api-v3.thaiwater.net/api/v1/thaiwater30/
- ThaiWater: https://www.thaiwater.net/
- Open-Meteo: https://open-meteo.com/

## ข้อจำกัด
API ของ ThaiWater เป็นบริการสาธารณะที่อาจมีช่วงข้อมูลว่างหรือเปลี่ยนแปลงได้ หากฝนสะสม 3/7 วันคืนค่าว่าง ระบบจะแสดงว่าไม่มีข้อมูลแทนการตีความว่าไม่มีฝน
\n\n## V3.1 Map Fix\n- Fixed ThaiWater rainfall-map coordinate parsing to support both `lat/long` and `latitude/longitude` station fields.\n- The rainfall map now loads automatically on first visit and can be refreshed manually.\n

## V3.2 - Rain Map API Fallback
- แผนที่ฝน 24 ชั่วโมงย้อนหลังใช้ RID SWOC/HII เป็นแหล่งข้อมูลหลัก (`rainfall-hii-24hr`) และสำรองด้วย ThaiWater `/public/rain_24h`
- ระบบแสดงแหล่งข้อมูลที่ใช้งานจริงบนหน้าแผนที่
- หาก API หลักล้มเหลว ระบบจะลองแหล่งสำรองอัตโนมัติ


## การปรับปรุง THData และแผนที่จังหวัด

- ตารางสถานีระดับน้ำแสดงรายการสถานีทั้งหมดที่ API เดิมส่งกลับสำหรับจังหวัดที่เลือก และเพิ่มคอลัมน์ลิงก์ `เปิด THData ↗` ไปยัง https://water.thdata.co/
- แผนที่ฝนย้อนหลัง 24 ชั่วโมงจะเลื่อนไปยังพิกัดตัวแทนของจังหวัดที่เลือก (ซูมระดับจังหวัด) ปักหมุดจังหวัด และไฮไลต์จุดสถานีที่ชื่อจังหวัดตรงกัน
- **ข้อจำกัดแหล่งข้อมูล:** โค้ดนี้ยังดึงค่าตัวเลขระดับน้ำ/ฝนจาก API สาธารณะเดิมของ ThaiWater/RID ที่มีอยู่ในโปรเจกต์ เพราะยังไม่มี endpoint API สาธารณะ موثّق (documented) ของ water.thdata.co ที่ยืนยันได้ในงานนี้ ลิงก์ THData ใช้สำหรับตรวจสอบข้อมูลต้นทางผ่านเว็บไซต์ และไม่ได้หมายความว่าค่าตัวเลขในแอปดึงจาก THData โดยตรง
- พิกัดหมุดจังหวัดเป็นพิกัดตัวแทนจาก `PROVINCES` ไม่ใช่ตำแหน่งสถานีวัดฝน


## ผู้พัฒนา
- ชื่อ: นาย วชิรวิทย์ ดอนซุยแป
- โรงเรียน: พุทธิรังสีพิบูล
- จังหวัด: ฉะเชิงเทรา

## สถิติการใช้งาน
แอปมีสถิติการใช้งานพื้นฐานจาก SQLite ได้แก่จำนวนเซสชันที่บันทึก การเลือกจังหวัด และจังหวัดที่ถูกเลือกบ่อย โดยไม่เก็บ IP หรือชื่อผู้ใช้ ฐานข้อมูลอยู่ใน `data/usage_analytics.db` การเก็บข้อมูลนี้เป็นแบบ local และอาจหายเมื่อโฮสต์รีสตาร์ต/ลบไฟล์ โดยเฉพาะบนบริการโฮสต์ที่ใช้พื้นที่ชั่วคราว หากต้องการสถิติผู้เข้าชมสะสมที่คงอยู่จริง ควรเชื่อมฐานข้อมูลภายนอกหรือบริการวิเคราะห์เว็บ
