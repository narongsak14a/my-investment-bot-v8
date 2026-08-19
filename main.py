import os
import time
import requests
import feedparser
from google import genai
from google.genai.errors import APIError
from tradingview_ta import TA_Handler, Interval
from youtube_transcript_api import YouTubeTranscriptApi

# ==========================================
# 1. ตั้งค่า API Key, Endpoints & Variables
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CLOUDFLARE_WORKER_URL = os.environ.get("CLOUDFLARE_WORKER_URL")
CLOUDFLARE_AUTH_TOKEN = os.environ.get("CLOUDFLARE_AUTH_TOKEN")
PORTFOLIO_URL = "https://broad-disk-2905.narongsak14.workers.dev/"

# รายชื่อ Video ID จาก YouTube (หากไม่มีให้ปล่อยเป็น [""])
YOUTUBE_VIDEO_IDS = [""]

# รายชื่อสินทรัพย์ ดัชนีอ้างอิง และกองทุนเป้าหมาย
ASSETS = [
    {"name": "ทองคำโลก (Gold)", "symbol": "XAUUSD", "exchange": "OANDA", "screener": "cfd"},
    {"name": "ทองคำไทย (Gold TH)", "symbol": "GOLD", "exchange": "TVC", "screener": "cfd"},
    {"name": "Tesla (TSLA)", "symbol": "TSLA", "exchange": "NASDAQ", "screener": "america"},
    {"name": "Nvidia (NVDA)", "symbol": "NVDA", "exchange": "NASDAQ", "screener": "america"},
    {"name": "ดัชนีหุ้นไทย (SET Index)", "symbol": "SET", "exchange": "SET", "screener": "thailand"},
    {"name": "หุ้น DEMCO (DEMCO)", "symbol": "DEMCO", "exchange": "SET", "screener": "thailand"},
    {"name": "หุ้น ASP (ASP)", "symbol": "ASP", "exchange": "SET", "screener": "thailand"},
    {"name": "หุ้น KGI (KGI)", "symbol": "KGI", "exchange": "SET", "screener": "thailand"},
    {"name": "หุ้น TISCO (TISCO)", "symbol": "TISCO", "exchange": "SET", "screener": "thailand"},
    {"name": "หุ้น KTB (KTB)", "symbol": "KTB", "exchange": "SET", "screener": "thailand"},
    {"name": "หุ้น SCB (SCB)", "symbol": "SCB", "exchange": "SET", "screener": "thailand"},
    {"name": "KTB RMF4 (อ้างอิงดัชนี SET)", "symbol": "SET", "exchange": "SET", "screener": "thailand"},
    {"name": "KTB RMF1 Benchmark (Bond Yield 10Y)", "symbol": "US10Y", "exchange": "TVC", "screener": "bond"},
    {"name": "Bitcoin (BTC/USD)", "symbol": "BTCUSD", "exchange": "BINANCE", "screener": "crypto"}
]

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลพอร์ต, RSS & TradingView
# ==========================================
def fetch_portfolio_data():
    print("⏳ กำลังเชื่อมต่อดึงข้อมูลพอร์ตการลงทุนจริง...")
    try:
        response = requests.get(PORTFOLIO_URL, timeout=10)
        if response.status_code == 200:
            print("✅ ดึงข้อมูลพอร์ตการลงทุนสำเร็จ!")
            return response.text[:2500]
        else:
            print(f"⚠️ ไม่สามารถดึงข้อมูลพอร์ตได้ (HTTP {response.status_code})")
            return "• ไม่สามารถดึงข้อมูลพอร์ตได้ในขณะนี้"
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการดึงข้อมูลพอร์ต: {e}")
        return "• ไม่พบข้อมูลพอร์ตการลงทุน"

def fetch_gold_analysis_detail():
    print("⏳ กำลังดึงสัญญาณเทคนิคอลเจาะลึกทองคำ (XAUUSD) บน Timeframe 1D และ 4H...")
    timeframes = {
        "1D (ภาพรวมวัน)": Interval.INTERVAL_1_DAY,
        "4H (จังหวะระยะสั้น)": Interval.INTERVAL_4_HOURS
    }
    gold_report = "=== [การวิเคราะห์เจาะลึกทองคำ XAUUSD (CDC ActionZone + Stochastic 14, 3, 3)] ===\n"
    for tf_name, tf_interval in timeframes.items():
        try:
            handler = TA_Handler(
                symbol="XAUUSD",
                exchange="OANDA",
                screener="cfd",
                interval=tf_interval
            )
            analysis = handler.get_analysis()
            indicators = analysis.indicators
            close_price = indicators.get("close", 0)
            ema12 = indicators.get("EMA12", 0)
            ema26 = indicators.get("EMA26", 0)
            
            if ema12 > ema26:
                cdc_status = "🟢 BULLISH (โซนสีเขียว / ซื้อ-ถือครอง)"
            else:
                cdc_status = "🔴 BEARISH (โซนสีแดง / ขาย-พักเงิน)"
                
            stoch_k = indicators.get("Stoch.K", 0)
            stoch_d = indicators.get("Stoch.D", 0)
            stoch_status = "Neutral"
            if stoch_k < 20:
                stoch_status = "🔵 Oversold (ขายมากเกินไป - ลุ้นดีดกลับ/จังหวะตั้งรับ)"
            elif stoch_k > 80:
                stoch_status = "🟠 Overbought (ซื้อมากเกินไป - ระวังการย่อตัว)"
                
            summary_rec = analysis.summary.get('RECOMMENDATION', 'N/A')
            gold_report += (
                f"\n📌 Timeframe: {tf_name}\n"
                f"  - ราคาปัจจุบัน: {close_price:.2f}\n"
                f"  - สัญญาณสรุป TradingView: [{summary_rec}]\n"
                f"  - CDC ActionZone (EMA12/EMA26): {cdc_status} (EMA12: {ema12:.2f}, EMA26: {ema26:.2f})\n"
                f"  - Stochastic (14, 3, 3): %K = {stoch_k:.2f}, %D = {stoch_d:.2f} [{stoch_status}]\n"
            )
        except Exception as e:
            gold_report += f"\n⚠️ ไม่สามารถดึงข้อมูล XAUUSD ({tf_name}) ได้: {e}\n"
    return gold_report

def fetch_btc_analysis_detail():
    print("⏳ กำลังดึงสัญญาณเทคนิคอลเจาะบิทคอยน์ (BTCUSD) บน Timeframe 1D และ 4H...")
    timeframes = {
        "1D (ภาพรวมวัน)": Interval.INTERVAL_1_DAY,
        "4H (จังหวะระยะสั้น)": Interval.INTERVAL_4_HOURS
    }
    # 🛠️ แก้ไขข้อความ Header ให้เป็น บิทคอยน์ BTCUSD
    btc_report = "=== [การวิเคราะห์เจาะลึกบิทคอยน์ BTCUSD (CDC ActionZone + Stochastic 14, 3, 3)] ===\n"
    for tf_name, tf_interval in timeframes.items():
        try:
            handler = TA_Handler(
                symbol="BTCUSD",
                exchange="BINANCE",
                screener="crypto",
                interval=tf_interval
            )
            analysis = handler.get_analysis()
            indicators = analysis.indicators
            close_price = indicators.get("close", 0)
            ema12 = indicators.get("EMA12", 0)
            ema26 = indicators.get("EMA26", 0)
            
            if ema12 > ema26:
                cdc_status = "🟢 BULLISH (โซนสีเขียว / ซื้อ-ถือครอง)"
            else:
                cdc_status = "🔴 BEARISH (โซนสีแดง / ขาย-พักเงิน)"
                
            stoch_k = indicators.get("Stoch.K", 0)
            stoch_d = indicators.get("Stoch.D", 0)
            stoch_status = "Neutral"
            if stoch_k < 20:
                stoch_status = "🔵 Oversold (ขายมากเกินไป - ลุ้นดีดกลับ/จังหวะตั้งรับ)"
            elif stoch_k > 80:
                stoch_status = "🟠 Overbought (ซื้อมากเกินไป - ระวังการย่อตัว)"
                
            summary_rec = analysis.summary.get('RECOMMENDATION', 'N/A')
            btc_report += (
                f"\n📌 Timeframe: {tf_name}\n"
                f"  - ราคาปัจจุบัน: {close_price:.2f}\n"
                f"  - สัญญาณสรุป TradingView: [{summary_rec}]\n"
                f"  - CDC ActionZone (EMA12/EMA26): {cdc_status} (EMA12: {ema12:.2f}, EMA26: {ema26:.2f})\n"
                f"  - Stochastic (14, 3, 3): %K = {stoch_k:.2f}, %D = {stoch_d:.2f} [{stoch_status}]\n"
            )
        except Exception as e:
            # 🛠️ แก้ไขกรณี Error ให้ระบุ BTCUSD
            btc_report += f"\n⚠️ ไม่สามารถดึงข้อมูล BTCUSD ({tf_name}) ได้: {e}\n"
    return btc_report

def fetch_all_tradingview_signals():
    print("⏳ กำลังดึงสัญญาณเทคนิคอลเชิงลึกจาก TradingView...")
    tv_summary_report = ""
    for asset in ASSETS:
        try:
            handler = TA_Handler(
                symbol=asset["symbol"],
                exchange=asset["exchange"],
                screener=asset["screener"],
                interval=Interval.INTERVAL_1_DAY
            )
            analysis = handler.get_analysis()
            rec = analysis.summary.get('RECOMMENDATION', 'N/A')
            buy = analysis.summary.get('BUY', 0)
            sell = analysis.summary.get('SELL', 0)
            neutral = analysis.summary.get('NEUTRAL', 0)
            tv_summary_report += f"- {asset['name']}: สัญญาณสรุป [{rec}] (แรงซื้อ: {buy}, แรงขาย: {sell}, ถือครอง: {neutral})\n"
        except Exception as e:
            tv_summary_report += f"- {asset['name']}: ดึงข้อมูลไม่สำเร็จ ({e})\n"
    return tv_summary_report

def fetch_rss_news():
    print("⏳ กำลังเชื่อมต่อดึงข้อมูลข่าวสารและบทวิเคราะห์จาก Investing.com & Yahoo Finance...")
    feed_urls = [
        "https://th.investing.com/rss/news.rss",
        "https://th.investing.com/rss/market_overview.rss",
        "https://finance.yahoo.com/news/rssindex"
    ]
    news_compiled = ""
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:2]:
                    summary = getattr(entry, 'summary', '')
                    clean_summary = summary.split('<')[0][:180] if summary else 'ไม่มีรายละเอียดสรุป'
                    news_compiled += f"• ข่าวสาร/บทวิเคราะห์: {entry.title}\n  รายละเอียด: {clean_summary}...\n"
        except Exception as e:
            print(f"⚠️ ไม่สามารถดึง feed จาก {url}: {e}")
            continue
    if not news_compiled:
        news_compiled = "• ไม่สามารถดึงข้อมูลข่าวสารได้ในขณะนี้\n"
    return news_compiled

def fetch_youtube_insights():
    print("⏳ กำลังดึงบทสัมภาษณ์และมุมมองเชิงลึกจาก YouTube...")
    yt_summary = ""
    for video_id in YOUTUBE_VIDEO_IDS:
        if not video_id:
            continue
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.fetch(video_id, languages=['th', 'en'])
            text = " ".join([item['text'] for item in transcript_list])[:1800]
            yt_summary += f"• สรุปบทสัมภาษณ์ YouTube (ID: {video_id}): {text}\n\n"
        except Exception as e:
            print(f"⚠️ ข้ามการดึง Transcript จาก YouTube ({e})")
    return yt_summary if yt_summary else "• ไม่มีข้อมูลบทสัมภาษณ์ YouTube ในรอบนี้\n"

def send_to_cloudflare(message_text):
    print("⏳ กำลังส่งข้อมูลไปยัง Cloudflare...")
    if not CLOUDFLARE_WORKER_URL:
        print("❌ ไม่พบ CLOUDFLARE_WORKER_URL ใน GitHub Secrets")
        return
    headers = {"Content-Type": "application/json"}
    if CLOUDFLARE_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {CLOUDFLARE_AUTH_TOKEN.strip()}"
    payload = {
        "email": "narongsak14@gmail.com",
        "report_type": "CIO_DAILY_REPORT",
        "content": message_text
    }
    try:
        response = requests.post(CLOUDFLARE_WORKER_URL, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print("✅ ส่งรายงานไปยัง Cloudflare เรียบร้อยแล้ว!")
        else:
            print(f"❌ ส่งเข้า Cloudflare ไม่สำเร็จ (HTTP {response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการส่งไปยัง Cloudflare: {e}")

# ==========================================
# 3. ฟังก์ชันประมวลผล Gemini AI และสั่งรัน
# ==========================================
def generate_content_with_retry(client, model, prompt, max_retries=3, delay=10):
    """ฟังก์ชันช่วย Retry การเรียกใช้ Gemini API เมื่อเจอ Error 503 หรือ Rate Limit"""
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return response
        except APIError as e:
            if "503" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "UNAVAILABLE" in str(e):
                print(f"⚠️ พบปัญหา Gemini API High Demand (Error 503) - พยายามครั้งที่ {attempt}/{max_retries} รอ {delay} วินาที...")
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise e
            else:
                raise e

def run_investment_ai_pipeline():
    print("\n--- 🚀 เริ่มต้นกระบวนการวิเคราะห์การลงทุนระดับมืออาชีพ ---")
    portfolio_data = fetch_portfolio_data()
    gold_detailed_signals = fetch_gold_analysis_detail()
    # 🛠️ ดึงสัญญาณวิเคราะห์เจาะลึก บิทคอยน์ (BTCUSD)
    btc_detailed_signals = fetch_btc_analysis_detail()
    raw_news_data = fetch_rss_news()
    youtube_insights = fetch_youtube_insights()
    tradingview_signals = fetch_all_tradingview_signals()

    macro_tech_prompt = f"""
คุณคือ 'ประธานคณะกรรมการฝ่ายวิจัยและจัดการกองทุน (Chief Investment Officer - CIO)' หน้าที่ของคุณคือวิเคราะห์พอร์ตการลงทุนจริงของผู้ใช้ โดยประมวลผลร่วมกับ 'กระแสข่าวและบทวิเคราะห์จาก Investing.com', 'สัญญาณเทคนิคอลจาก TradingView' และ 'วิเคราะห์เจาะจง CDC ActionZone + Stochastic ของทองคำ และ บิทคอยน์'

[เป้าหมายและเงื่อนไขการลงทุนของผู้ใช้]
1. **เป้าหมายหลัก:** ต้องการสร้างผลตอบแทนชนะอัตราเงินเฟ้อในระยะยาว (Beat Inflation Target)
2. **เงื่อนไขสำคัญสูงสุด:** ต้องปกป้องเงินต้น ไม่ให้เกิดความเสียหายหรือขาดทุนรุนแรง (Capital Preservation / Low Capital Loss Risk)

[ข้อมูลพอร์ตการลงทุนปัจจุบันของผู้ใช้ (จาก Worker)]
----------------------------------------
{portfolio_data}
----------------------------------------

[ชุดข้อมูลวิเคราะห์พิเศษ: ทองคำโลก XAUUSD (1D & 4H)]
----------------------------------------
{gold_detailed_signals}
----------------------------------------

[ชุดข้อมูลวิเคราะห์พิเศษ: บิทคอยน์ BTCUSD (1D & 4H)]
----------------------------------------
{btc_detailed_signals}
----------------------------------------

[ชุดข้อมูลประกอบการวิเคราะห์อื่นๆ]
- สัญญาณเทคนิคอลภาพรวม (TradingView): {tradingview_signals}
- ข่าวสารการเงินและบทวิเคราะห์ Investing.com: {raw_news_data}
- ข้อมูลสัมภาษณ์ YouTube: {youtube_insights}
----------------------------------------

จงประมวลผลอย่างเป็นระบบและเขียน 'รายงานสรุปกลยุทธ์ฟิวชันข้ามมิติ' เป็นภาษาไทย โดยแยกประเด็นออกเป็น 5 ส่วนดังนี้:

[PART 1: การประเมินสุขภาพพอร์ตจริง (Portfolio Health Check & Risk Assessment)]
- ประเมินพอร์ตปัจจุบันของผู้ใช้ว่าสอดคล้องกับเป้าหมาย 'ชนะเงินเฟ้อ + เงินต้นไม่เสียหาย' มากน้อยเพียงใด
- วิเคราะห์สัดส่วนสินทรัพย์เสี่ยงสูง (เช่น หุ้น, BTC) เทียบกับ สินทรัพย์ปลอดภัย/พักเงิน (KTB RMF1 / ตราสารหนี้ / ทองคำ)

[PART 2: วิเคราะห์จังหวะเข้าลงทุนทองคำ (XAUUSD) และ บิทคอยน์ (BTCUSD)]
- สรุปสถานะ CDC ActionZone (1D และ 4H) และ Stochastic (14, 3, 3) ของทั้งทองคำและบิทคอยน์
- ฟันธงจังหวะและช่วงเวลาการลงทุนที่เหมาะสม เช่น "ควรรอย่อตัวแถวโซน Oversold ใน 4H", "โซนเขียว 1D สนับสนุนการสะสม" หรือ "อยู่ในภาวะ Overbought ให้ชะลอการซื้อ"

[PART 3: บทวิเคราะห์ความสอดคล้อง (Macro-Technical Linkage)]
- วิเคราะห์สภาวะตลาดปัจจุบันเทียบกับพอร์ต เช่น สัญญาณ TradingView และข่าวสาร Investing.com บ่งชี้ความเสี่ยงที่จะกระทบเงินต้นของพอร์ตนี้หรือไม่

[PART 4: คำแนะนำจัดพอร์ตและกลยุทธ์ Switching (Action Plan & KTB RMF Strategy)]
- ฟันธงสัดส่วนการปรับพอร์ตประจำวัน โดยเน้นคุมความเสี่ยงเงินต้นเป็นหลัก
- ระบุสัดส่วนการ DCA หรือการสับเปลี่ยนกองทุน (Switching) ระหว่าง **KTB RMF4 (หุ้นไทย - เพื่อชนะเงินเฟ้อ)** และ **KTB RMF1 (ตราสารหนี้ - เพื่อปกป้องเงินต้น)** รวมถึงจังหวะการจัดสรรเข้า ทองคำ/BTC อย่างชัดเจน

[PART 5: สคริปต์รวบยอดสำหรับสร้าง Podcast ใน NotebookLM]
- แปลงบทวิเคราะห์ให้กลายเป็น 'สคริปต์บทพูดสั้น เร้าใจ และเป็นทางการ' (ความยาว 3-4 ย่อหน้า) ภาษาไทย เพื่อป้อนให้ระบบ NotebookLM แปลงเป็นเสียง Podcast

เขียนรายงานด้วยน้ำเสียงสถาบันการเงิน เฉียบคม ตรงไปตรงมา กระชับ และไม่มีคำเกริ่นนำที่ไม่จำเป็น
"""

    print("\n🧠 กำลังส่งข้อมูลฟิวชันป้อนเข้า Gemini...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        # 🛠️ ใช้ Retry mechanism เมื่อเจอ Error 503
        response = generate_content_with_retry(
            client=client,
            model="gemini-3.6-flash",
            prompt=macro_tech_prompt,
            max_retries=3,
            delay=10
        )
        report_text = response.text

        print("\n--- ✨ รายงานจาก Gemini ---")
        print(report_text)

        print("\n📤 กำลังส่งรายงานไปยัง Cloudflare...")
        repo_name = os.environ.get("GITHUB_REPOSITORY", "narongsak14a/my-investment-bot-v7")
        header = (
            f"📦 Repository: {repo_name}\n"
            f"📊 [รายงานสรุปกลยุทธ์การลงทุน CIO Report (พอร์ตจริง + CDC ActionZone Gold/BTC + ชนะเงินเฟ้อ)]\n"
            f"--------------------------------------------------\n\n"
        )
        send_to_cloudflare(header + report_text)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในระบบ AI: {e}")

if __name__ == "__main__":
    run_investment_ai_pipeline()
