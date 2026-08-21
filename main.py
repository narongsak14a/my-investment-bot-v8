import pandas as pd
import requests

# ==========================================
# 1. ตั้งค่า URL สำหรับดึงข้อมูล CSV จาก Google Sheets
# ==========================================
ASSET_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyU-ww2M22WZq781y1pEwbXihk0iOar0xyx2ZIo776WgbdQOkXAK-9S6ckGgHk3F7NlBGsaqDv4zwR/pub?gid=0&single=true&output=csv"
INVESTMENT_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSyU-ww2M22WZq781y1pEwbXihk0iOar0xyx2ZIo776WgbdQOkXAK-9S6ckGgHk3F7NlBGsaqDv4zwR/pub?gid=1298818179&single=true&output=csv"
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
# 3. ฟังก์ชันดึงคำสั่งพิเศษจากชีท NEED (อ่านค่า detail)
# ==========================================
def fetch_user_needs():
    print("⏳ กำลังดึงคำสั่งพิเศษจากชีท NEED...")
    try:
        df_need = pd.read_csv(NEED_SHEET_CSV_URL)
        df_need = df_need.dropna(how='all')  # ลบบรรทัดว่าง
        
        if df_need.empty:
            print("ℹ️ ไม่พบคำสั่งพิเศษในชีท NEED (ใช้วิเคราะห์ตามปกติ)")
            return "• ไม่มีคำสั่งพิเศษเพิ่มเติม ให้วิเคราะห์ตามมาตรฐาน"
            
        needs_summary = []
        for index, row in df_need.iterrows():
            topic = row.get('topic', '-')
            detail = row.get('detail', '-')
            
            if pd.notna(topic) or pd.notna(detail):
                needs_summary.append(f"• หัวข้อคำสั่ง: {topic}\n  เป้าหมายการวิเคราะห์ (detail): {detail}")
                
        if not needs_summary:
            return "• ไม่มีคำสั่งพิเศษเพิ่มเติม ให้วิเคราะห์ตามมาตรฐาน"

        need_text = "=== [คำสั่งและเป้าหมายวิเคราะห์พิเศษจากผู้ใช้ (ชีท NEED)] ===\n" + "\n".join(needs_summary)
        print("✅ ดึงข้อมูล topic และ detail จากชีท NEED สำเร็จ!")
        return need_text
        
    except Exception as e:
        print(f"⚠️ ไม่สามารถดึงข้อมูลจากชีท NEED ได้ ({e})")
        return "• ไม่สามารถดึงคำสั่งพิเศษจากชีท NEED ได้"

# ==========================================
# 4. ฟังก์ชันสร้าง Prompt คงโครงสร้างการรายงานเดิม
# ==========================================
def run_investment_ai_pipeline():
    portfolio_data = fetch_portfolio_data()
    user_needs_data = fetch_user_needs()
    
    macro_tech_prompt = f"""
คุณเป็นที่ปรึกษาการลงทุนระดับมืออาชีพ ให้สรุปสภาวะตลาด จัดทำรายงานวิเคราะห์ประจำวัน และให้คำแนะนำตามโครงสร้างรายงานเดิมอย่างเคร่งครัด

[คำสั่งและเป้าหมายวิเคราะห์พิเศษเฉพาะกิจจากผู้ใช้ (ชีท NEED)]
{user_needs_data}

[แนวทางการนำข้อมูลพิเศษไปประมวลผล]:
1. นำข้อความในช่อง 'detail' จากชีท NEED เป็นโจทย์หลักสูงสุดในการปรับเน้นเนื้อหาบทวิเคราะห์
2. นำคอลัมน์ 'comment' จากชีท asset และ investment ไปประเมินเรื่องสภาพคล่อง (Liquidity), กระแสเงินสดรับ (Cash Flow) และเงื่อนไขการ Switching/Rebalancing ของพอร์ต

[ข้อมูลพอร์ตการลงทุนปัจจุบันของผู้ใช้]
{portfolio_data}

---
### 📋 รูปแบบโครงสร้างการรายงานผล (คงรูปแบบเดิมอย่างเคร่งครัด)

โปรดตอบกลับโดยใช้โครงสร้างรายงานตามลำดับดังต่อไปนี้:

**1. สรุปภาพรวมสภาวะตลาดและปัจจัยมหภาค (Macro Overview)**
- สรุปแนวโน้มตลาดหลัก ตลาดหุ้น ดอกเบี้ย และราคาสินค้าโภคภัณฑ์

**2. สรุปการวิเคราะห์พอร์ตการลงทุนปัจจุบัน (Portfolio Analysis)**
- วิเคราะห์สัดส่วนสินทรัพย์ โดยนำข้อมูล 'comment' (เช่น เงื่อนไขการถอนเงิน รอบดอกเบี้ย และข้อจำกัด RMF) มาประเมินสภาพคล่องและข้อจำกัดการลงทุนร่วมด้วย
- ประเมินความสอดคล้องกับวัตถุประสงค์ในคอลัมน์ 'detail' (จากชีท NEED)

**3. ตารางสรุปสัญญาณทางเทคนิคและคำแนะนำ (Technical Summary Table)**
สร้างตาราง Markdown สรุปรายการสินทรัพย์/กองทุน โดยมีคอลัมน์ดังนี้:
| สินทรัพย์/กองทุน | แนวโน้ม (Trend) | สัญญาณเทคนิค | หมายเหตุ/เงื่อนไข (Comment) | คำแนะนำ (Action) |

**4. แผนการดำเนินการและคำแนะนำการปรับพอร์ต (Action Plan)**
- ให้คำแนะนำเชิงรุก เช่น การ Rebalancing, การ Switching กองทุน หรือการบริหารสภาพคล่อง ที่ตอบโจทย์ 'detail' ในชีท NEED อย่างเป็นรูปธรรม
"""
    
    print("🚀 พร้อมส่ง Prompt วิเคราะห์ตามโครงสร้างเดิมเรียบร้อย!")
    return macro_tech_prompt

if __name__ == "__main__":
    prompt_result = run_investment_ai_pipeline()
