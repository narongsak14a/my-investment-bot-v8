import os
import json
import pandas as pd
import requests

# ==========================================
# 0. ตั้งค่า URL สื่อสาร
# ==========================================
CLOUDFLARE_WORKER_URL = os.environ.get("CLOUDFLARE_WORKER_URL") or "https://dry-voice-2e82.narongsak14.workers.dev/"

# ==========================================
# 1. ตั้งค่า URL สำหรับดึงข้อมูล CSV จาก Google Sheets
# ==========================================
ASSET_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyU-ww2M22WZq781y1pEwbXihk0iOar0xyx2ZIo776WgbdQOkXAK-9S6ckGgHk3F7NlBGsaqDv4zwR/pub?gid=0&single=true&output=csv"
INVESTMENT_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyU-ww2M22WZq781y1pEwbXihk0iOar0xyx2ZIo776WgbdQOkXAK-9S6ckGgHk3F7NlBGsaqDv4zwR/pub?gid=1067250335&single=true&output=csv"
NEED_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyU-ww2M22WZq781y1pEwbXihk0iOar0xyx2ZIo776WgbdQOkXAK-9S6ckGgHk3F7NlBGsaqDv4zwR/pub?gid=267763866&single=true&output=csv"

PORTFOLIO_URL = "https://example.com/fallback_portfolio.txt"

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลพอร์ต ( asset + investment + comments )
# ==========================================
def fetch_portfolio_data():
    print("⏳ กำลังดึงข้อมูลพอร์ตจาก Google Sheet (asset & investment)...")
    try:
        df_asset = pd.read_csv(ASSET_SHEET_CSV_URL)
        df_investment = pd.read_csv(INVESTMENT_SHEET_CSV_URL)
        
        # จัดการคอลัมน์ comment (หากไม่มีข้อมูลใส่ '-' เพื่อความสะอาดของตาราง)
        if 'comment' in df_asset.columns:
            df_asset['comment'] = df_asset['comment'].fillna('-')
        if 'comment' in df_investment.columns:
            df_investment['comment'] = df_investment['comment'].fillna('-')
        
        portfolio_text = "=== [ข้อมูลพอร์ตการลงทุนจาก Google Sheet] ===\n\n"
        portfolio_text += "📌 รายการสินทรัพย์อื่นๆ พร้อมเงื่อนไข/หมายเหตุ (ชีท asset):\n"
        portfolio_text += df_asset.to_string(index=False) + "\n\n"
        
        portfolio_text += "📌 รายการกองทุน/เงินลงทุน พร้อมเงื่อนไข/หมายเหตุ (ชีท investment):\n"
        portfolio_text += df_investment.to_string(index=False)
        
        print("✅ ดึงข้อมูลพอร์ตและ comment สำเร็จ!")
        return portfolio_text

    except Exception as e:
        print(f"⚠️ ไม่สามารถดึงข้อมูลจาก Google Sheet ได้ ({e}) สลับไปใช้ข้อมูลสำรอง")
        try:
            response = requests.get(PORTFOLIO_URL, timeout=10)
            if response.status_code == 200:
                return response.text[:2500]
            else:
                return "• ไม่สามารถดึงข้อมูลพอร์ตได้ในขณะนี้"
        except Exception:
            return "• ไม่พบข้อมูลพอร์ตการลงทุน"

# ==========================================
# 3. ฟังก์ชันดึงคำสั่งพิเศษจากชีท NEED (รองรับข้อความไร้ Header)
# ==========================================
def fetch_user_needs():
    print("⏳ กำลังดึงคำสั่งพิเศษจากชีท NEED...")
    try:
        # ใช้ header=None เพื่ออ่านข้อความตั้งแต่บรรทัดแรก โดยไม่ข้ามข้อความไปเป็นชื่อคอลัมน์
        df_need = pd.read_csv(NEED_SHEET_CSV_URL, header=None)
        
        all_text_list = []
        for row in df_need.itertuples(index=False):
            for cell in row:
                if pd.notna(cell) and str(cell).strip() != "":
                    all_text_list.append(str(cell).strip())
        
        if not all_text_list:
            print("ℹ️ ไม่พบคำสั่งพิเศษในชีท NEED (ใช้วิเคราะห์ตามปกติ)")
            return "• ไม่มีคำสั่งพิเศษเพิ่มเติม ให้วิเคราะห์ตามมาตรฐาน"
            
        need_text = "=== [คำสั่งและเป้าหมายวิเคราะห์พิเศษจากผู้ใช้ (ชีท NEED)] ===\n"
        need_text += "\n".join([f"• {text}" for text in all_text_list])
        
        print("✅ ดึงข้อความจากชีท NEED สำเร็จ!")
        return need_text
        
    except Exception as e:
        print(f"⚠️ ไม่สามารถดึงข้อมูลจากชีท NEED ได้ ({e})")
        return "• ไม่สามารถดึงคำสั่งพิเศษจากชีท NEED ได้"

# ==========================================
# 4. ฟังก์ชันสร้าง Prompt
# ==========================================
def run_investment_ai_pipeline():
    portfolio_data = fetch_portfolio_data()
    user_needs_data = fetch_user_needs()
    
    macro_tech_prompt = f"""
คุณเป็นที่ปรึกษาการลงทุนระดับมืออาชีพ ให้สรุปสภาวะตลาด จัดทำรายงานวิเคราะห์ประจำวัน และให้คำแนะนำตามโครงสร้างรายงานเดิมอย่างเคร่งครัด

[คำสั่งและเป้าหมายวิเคราะห์พิเศษเฉพาะกิจจากผู้ใช้ (ชีท NEED)]
{user_needs_data}

[แนวทางการนำข้อมูลพิเศษไปประมวลผล]:
1. นำข้อความคำสั่งจากชีท NEED มาเป็นโจทย์หลักสูงสุดในการกำหนดทิศทางบทวิเคราะห์และ Action Plan
2. **นำคอลัมน์ comment ทั้งหมดมาวิเคราะห์เจาะลึก:**
   - **ด้านสภาพคล่อง (Liquidity):** แยกแยะสินทรัพย์ที่ถอนไม่ได้ (เช่น หุ้นสหกรณ์) ออกจากสินทรัพย์ที่ถอนได้ (เช่น เงินฝากสุขเกษียณ) เพื่อวางแผนเงินสำรองฉุกเฉิน
   - **ด้านกระแสเงินสด (Cash Flow):** นำรอบจ่ายดอกเบี้ย/ปันผล (เช่น ปีละครั้งใน ก.พ. VS ทุกเดือน) มาประเมิน Liquidity Management
   - **ด้านข้อจำกัดการลงทุน:** นำเป้าหมายและเงื่อนไขของกองทุน RMF มาใช้กำหนดกลยุทธ์ Switching และ Rebalancing

[ข้อมูลพอร์ตการลงทุนปัจจุบันของผู้ใช้]
{portfolio_data}

---
### 📋 รูปแบบโครงสร้างการรายงานผล (คงรูปแบบเดิมอย่างเคร่งครัด)

โปรดตอบกลับโดยใช้โครงสร้างรายงานตามลำดับดังต่อไปนี้:

**1. สรุปภาพรวมสภาวะตลาดและปัจจัยมหภาค (Macro Overview)**
- สรุปแนวโน้มตลาดหลัก ตลาดหุ้น ดอกเบี้ย และราคาสินค้าโภคภัณฑ์

**2. สรุปการวิเคราะห์พอร์ตการลงทุนปัจจุบัน (Portfolio Analysis)**
- วิเคราะห์สัดส่วนสินทรัพย์ โดยนำข้อมูล 'comment' (เงื่อนไขการถอนเงิน รอบดอกเบี้ยรับ และข้อจำกัด RMF) มาวิเคราะห์เจาะลึกด้านสภาพคล่องและกระแสเงินสด
- ประเมินความสอดคล้องกับวัตถุประสงค์ที่ระบุจากชีท NEED

**3. ตารางสรุปสัญญาณทางเทคนิคและคำแนะนำ (Technical Summary Table)**
สร้างตาราง Markdown สรุปรายการสินทรัพย์/กองทุน โดยมีคอลัมน์ดังนี้:
| สินทรัพย์/กองทุน | แนวโน้ม (Trend) | สัญญาณเทคนิค | หมายเหตุ/เงื่อนไข (Comment) | คำแนะนำ (Action) |

**4. แผนการดำเนินการและคำแนะนำการปรับพอร์ต (Action Plan)**
- ให้คำแนะนำเชิงรุก เช่น การ Rebalancing, การ Switching กองทุน หรือการวางแผนเงินสำรองสภาพคล่อง ที่ตอบโจทย์ความต้องการในชีท NEED และสอดคล้องกับ comment ในพอร์ตอย่างเป็นรูปธรรม
"""
    return macro_tech_prompt

# ==========================================
# 5. ฟังก์ชันส่งข้อมูลไปยัง Cloudflare Worker (รองรับ ภาษาไทย utf-8)
# ==========================================
def send_to_cloudflare(payload_data):
    print(f"🤖 กำลังส่งรายงานไปยัง Cloudflare ({CLOUDFLARE_WORKER_URL})...")
    
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "prompt": payload_data,
        "source": "Python Investment Pipeline"
    }
    
    # แปลง payload เป็น JSON โดยตั้งค่า ensure_ascii=False เพื่อให้ส่งภาษาไทยตรงๆ ไม่แปลงเป็น \uXXXX
    json_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    
    try:
        response = requests.post(
            CLOUDFLARE_WORKER_URL, 
            data=json_bytes, 
            headers=headers, 
            timeout=30
        )
        if response.status_code == 200:
            print("🎉 ส่งข้อมูลไปยัง Cloudflare Worker สำเร็จ!")
            return response.text
        else:
            print(f"❌ การส่งข้อมูลล้มเหลว (Status Code: {response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"💥 เกิดข้อผิดพลาดในการเชื่อมต่อกับ Cloudflare: {e}")
        return None

if __name__ == "__main__":
    prompt_result = run_investment_ai_pipeline()
    print("🚀 พร้อมส่ง Prompt วิเคราะห์ตามโครงสร้างเดิมเรียบร้อย!")
    
    # ส่งข้อมูลไปยัง Cloudflare Worker
    send_to_cloudflare(prompt_result)
