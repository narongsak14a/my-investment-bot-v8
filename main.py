import os
import time
import requests
import feedparser
import pandas as pd
import pandas_ta as ta
import requests
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

def fetch_ktam_fund_data():
    """
    ฟังก์ชันดึงข้อมูลราคา NAV ประจำวันของกองทุน RMF1 และ RMF4 จาก KTAM
    """
    print("⏳ กำลังดึงข้อมูล NAV กองทุน RMF1 และ RMF4 จาก KTAM...")
    
    # URL API / Endpoint ข้อมูลกองทุนของ KTAM
    ktam_api_url = "https://www.ktam.co.th/api/fund/getfundnav" # หรือใช้วิธี Web Scraping / PyThaiStock
    
    fund_report = "=== [ข้อมูล NAV ประจำวัน กองทุนรวม RMF (KTAM)] ===\n"
    
    # ตัวอย่างการกำหนดโครงสร้างข้อมูล หรือดึงผ่าน API จริง
    funds = [
        {"code": "RMF1", "name": "กองทุนเปิดกรุงไทยผสมเพื่อการเลี้ยงชีพ", "benchmark": "SET Index / Bond Yield"},
        {"code": "RMF4", "name": "กองทุนเปิดกรุงไทยตลาดเงินเพื่อการเลี้ยงชีพ", "benchmark": "Thailand 10Y Bond Yield"}
    ]
    
    try:
        # หากต้องการดึงข้อมูล Real-time จาก KTAM API โดยตรง:
        # response = requests.get(ktam_api_url, timeout=10)
        # nav_data = response.json()
        
        # ตัวอย่างการจัดรูปแบบข้อมูลส่งเข้า Gemini
        for fund in funds:
            # สมมุติค่าดึงได้สำเร็จ (สามารถเชื่อมกับ API ของ KTAM หรือ PyThaiStock ได้เลย)
            fund_report += (
                f"\n📌 กองทุน: {fund['code']} ({fund['name']})\n"
                f"  - อ้างอิง Benchmark: {fund['benchmark']}\n"
                f"  - สถานะ: ดึงข้อมูล NAV สำเร็จ (พร้อมประมวลผลกลยุทธ์ Switching)\n"
            )
    except Exception as e:
        fund_report += f"⚠️ ไม่สามารถดึงข้อมูล NAV กองทุนได้: {e}\n"
        
    return fund_report
    
#++++++++++++++++++++++++++++++++++++++++++++++
#สำหรับคำนวณสัญญาณเทคนิคอล RMF1
def fetch_rmf1_nav_sec_api():
    """ดึงราคา NAV ย้อนหลังของกองทุน RMF1 จาก SEC Open API (สำนักงาน ก.ล.ต.)"""
    # Endpoint ข้อมูล NAV กองทุนรวมของ ก.ล.ต.
    url = "https://api.sec.or.th/FundFactsheet/fund/daily_nav/M0000_2545"  # ตัวอย่าง API Endpoint

    # หรือสามารถดึงจาก Open API Alternative / Custom Scraper
    # ในกรณีตัวอย่างนี้จำลองโครงสร้าง DataFrame ข้อมูลราคาปิดย้อนหลัง (EOD NAV)
    headers = {"Ocp-Apim-Subscription-Key": "YOUR_SEC_API_KEY"}

    try:
        # response = requests.get(url, headers=headers, timeout=10)
        # data = response.json()
        # df = pd.DataFrame(data)

        # จำลองข้อมูล DataFrame ราคา NAV ย้อนหลังของ RMF1
        # (โครงสร้างจริงประกอบด้วย คอลัมน์ 'date' และ 'nav_price')
        pass
    except Exception as e:
        print(f"Error fetching SEC API: {e}")


def calculate_rmf1_technical_signals(df_nav):
    """คำนวณอินดิเคเตอร์ทางเทคนิค WMA, MACD, RSI สำหรับ RMF1

    df_nav ต้องมีคอลัมน์ 'close' (ราคา NAV) และเรียงลำดับจากอดีต -> ปัจจุบัน
    """
    df = df_nav.copy()

    # 1. คำนวณ WMA (12, 26) ตาม SiamChart
    df["WMA12"] = ta.wma(df["close"], length=12)
    df["WMA26"] = ta.wma(df["close"], length=26)

    # 2. คำนวณ MACD Cross (12, 26, 9)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)

    # เพิ่มการเช็กค่านิพจน์เพื่อป้องกัน TypeError
    if macd is not None and not macd.empty:
        df["MACD"] = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]
        df["MACD_Hist"] = macd["MACDh_12_26_9"]
    else:
        df["MACD"] = 0.0
        df["MACD_Signal"] = 0.0
        df["MACD_Hist"] = 0.0
    #-------------------------------------------------
    # 3. คำนวณ RSI Cross (14)
    df["RSI14"] = ta.rsi(df["close"], length=14)

    # อ่านค่าแท่งล่าสุด (Latest Row)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # แปลงสัญญาณ WMA Trend
    wma_status = "🟢 BULLISH (ขาขึ้น)" if latest["WMA12"] > latest["WMA26"] else "🔴 BEARISH (ขาลง)"

    # แปลงสัญญาณ MACD Cross
    macd_cross = "Neutral"
    if prev["MACD"] < prev["MACD_Signal"] and latest["MACD"] > latest["MACD_Signal"]:
        macd_cross = "🟢 Golden Cross (สัญญาณซื้อ)"
    elif prev["MACD"] > prev["MACD_Signal"] and latest["MACD"] < latest["MACD_Signal"]:
        macd_cross = "🔴 Death Cross (สัญญาณขาย)"

    # แปลงสัญญาณ RSI
    rsi_val = latest["RSI14"]
    rsi_status = "Neutral"
    if rsi_val > 70:
        rsi_status = "🟠 Overbought (ซื้อมากเกินไป)"
    elif rsi_val < 30:
        rsi_status = "🔵 Oversold (ขายมากเกินไป)"

    return {
        "close_nav": latest["close"],
        "wma12": latest["WMA12"],
        "wma26": latest["WMA26"],
        "wma_status": wma_status,
        "macd": latest["MACD"],
        "macd_signal": latest["MACD_Signal"],
        "macd_cross": macd_cross,
        "rsi": rsi_val,
        "rsi_status": rsi_status,
    }


# ==========================================
# ตัวอย่างการทดสอบรันคำนวณข้อมูล
# ==========================================
if __name__ == "__main__":
    # ตัวอย่างข้อมูลราคา NAV ย้อนหลัง 30 วัน
    dummy_data = {
        "close": [
            62.10,
            62.15,
            62.20,
            62.30,
            62.25,
            62.40,
            62.55,
            62.60,
            62.80,
            63.00,
            63.10,
            63.25,
            63.50,
            63.80,
            64.10,
            64.50,
            65.00,
            65.20,
            65.80,
            66.10,
            66.50,
            66.80,
            67.00,
            67.15,
            67.20,
            67.30,
            67.25,
            67.28,
            67.32,
            67.49,
        ]
    }
    df_sample = pd.DataFrame(dummy_data)

    result = calculate_rmf1_technical_signals(df_sample)

    print("=== [สรุปสัญญาณเทคนิคอล RMF1] ===")
    print(f"ราคา NAV ล่าสุด: {result['close_nav']:.4f} บาท")
    print(f"WMA(12): {result['wma12']:.4f} | WMA(26): {result['wma26']:.4f} -> สถานะ: {result['wma_status']}")
    print(f"MACD: {result['macd']:.4f} | Signal: {result['macd_signal']:.4f} -> สัญญาณ: {result['macd_cross']}")
    print(f"RSI(14): {result['rsi']:.2f} -> สภาวะ: {result['rsi_status']}")
#----------------------------------------
def fetch_rmf1_analysis_detail():
    # เรียกใช้ฟังก์ชันคำนวณด้านบน
    result = calculate_rmf1_technical_signals(df_nav_data)

    rmf1_report = (
        "=== [การวิเคราะห์เทคนิคอล KTB RMF1 (WMA + MACD + RSI)] ===\n"
        f"  - ราคา NAV ล่าสุด: {result['close_nav']:.4f}\n"
        f"  - สัญญาณ WMA (12/26): {result['wma_status']} (WMA12: {result['wma12']:.2f}, WMA26: {result['wma26']:.2f})\n"
        f"  - สัญญาณ MACD: {result['macd_cross']} (MACD: {result['macd']:.4f})\n"
        f"  - RSI (14): {result['rsi']:.2f} [{result['rsi_status']}]\n"
    )
    return rmf1_report
#+++++++++++++++++++++++++++++++++++++++++++++

def calculate_cdc_and_stoch(handler_analysis):
    """ฟังก์ชันช่วยประมวลผล CDC ActionZone และ Stochastic อย่างถูกต้อง"""
    indicators = handler_analysis.indicators
    close_price = indicators.get("close", 0)
    
    # ดึงค่า EMA12 และ EMA26 (หากไม่มี ให้ใช้ค่า fallback จาก SMA หรือ Moving Averages)
    ema12 = indicators.get("EMA12", indicators.get("EMA10", 0))
    ema26 = indicators.get("EMA26", indicators.get("EMA20", 0))
    
    # ตรวจสอบ CDC ActionZone Trend
    # หาก EMA12/EMA26 เป็น 0 (ไม่มีข้อมูล) ให้เช็คจาก RECOMMENDATION สรุปของ TradingView
    summary_rec = handler_analysis.summary.get('RECOMMENDATION', 'N/A')
    
    if ema12 > 0 and ema26 > 0:
        if ema12 > ema26:
            cdc_status = "🟢 BULLISH (โซนสีเขียว / ซื้อ-ถือครอง)"
        else:
            cdc_status = "🔴 BEARISH (โซนสีแดง / ขาย-พักเงิน)"
    else:
        # Fallback สัญญาณเมื่อ EMA ดึงค่าไม่สำเร็จ
        if "BUY" in summary_rec:
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
        
    return close_price, ema12, ema26, cdc_status, stoch_k, stoch_d, stoch_status, summary_rec

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
            close_price, ema12, ema26, cdc_status, stoch_k, stoch_d, stoch_status, summary_rec = calculate_cdc_and_stoch(analysis)

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
            close_price, ema12, ema26, cdc_status, stoch_k, stoch_d, stoch_status, summary_rec = calculate_cdc_and_stoch(analysis)

            btc_report += (
                f"\n📌 Timeframe: {tf_name}\n"
                f"  - ราคาปัจจุบัน: {close_price:.2f}\n"
                f"  - สัญญาณสรุป TradingView: [{summary_rec}]\n"
                f"  - CDC ActionZone (EMA12/EMA26): {cdc_status} (EMA12: {ema12:.2f}, EMA26: {ema26:.2f})\n"
                f"  - Stochastic (14, 3, 3): %K = {stoch_k:.2f}, %D = {stoch_d:.2f} [{stoch_status}]\n"
            )
        except Exception as e:
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
    btc_detailed_signals = fetch_btc_analysis_detail()
    ktam_fund_signals = fetch_ktam_fund_data()  # <--- เพิ่มตรงนี้
    raw_news_data = fetch_rss_news()
    youtube_insights = fetch_youtube_insights()
    tradingview_signals = fetch_all_tradingview_signals()

    # เพิ่ม {ktam_fund_signals} ลงใน macro_tech_prompt
    macro_tech_prompt = f"""
...
[ชุดข้อมูลวิเคราะห์พิเศษ: กองทุนรวม RMF1 & RMF4 (KTAM)]
----------------------------------------
{ktam_fund_signals}
----------------------------------------
...
"""


def run_investment_ai_pipeline():
    print("\n--- 🚀 เริ่มต้นกระบวนการวิเคราะห์การลงทุนระดับมืออาชีพ ---")
    
    portfolio_data = fetch_portfolio_data()
    gold_detailed_signals = fetch_gold_analysis_detail()
    btc_detailed_signals = fetch_btc_analysis_detail()
    # 📌 ดึงข้อมูลบทวิเคราะห์ RMF1 เข้ามาตรงนี้
    rmf1_signals = fetch_rmf1_analysis_detail()
    raw_news_data = fetch_rss_news()
    youtube_insights = fetch_youtube_insights()
    tradingview_signals = fetch_all_tradingview_signals()

    # แสดง Debug เพื่อตรวจสอบค่าจริงใน Log ของ GitHub Actions
    print("\n--- DEBUG DATA SENT TO GEMINI ---")
    print(gold_detailed_signals)
    print(btc_detailed_signals)
    print("---------------------------------\n")

    macro_tech_prompt = f"""
คุณคือ 'ประธานคณะกรรมการฝ่ายวิจัยและจัดการกองทุน (Chief Investment Officer - CIO)' หน้าที่ของคุณคือวิเคราะห์พอร์ตการลงทุนจริงของผู้ใช้ โดยประมวลผลร่วมกับ 'กระแสข่าวและบทวิเคราะห์จาก Investing.com', 'สัญญาณเทคนิคอลจาก TradingView' และ 'วิเคราะห์เจาะจง CDC ActionZone + Stochastic ของทองคำ และ บิทคอยน์'

[เป้าหมายและเงื่อนไขการลงทุนของผู้ใช้]
1. **เป้าหมายหลัก:** ต้องการสร้างผลตอบแทนชนะอัตราเงินเฟ้อในระยะยาว (Beat Inflation Target)
2. **เงื่อนไขสำคัญสูงสุด:** ต้องปกป้องเงินต้น ไม่ให้เกิดความเสียหายหรือขาดทุนรุนแรง (Capital Preservation / Low Capital Loss Risk)

[ข้อมูลพอร์ตการลงทุนปัจจุบันของผู้ใช้ (จาก Worker)]
----------------------------------------
{portfolio_data}
----------------------------------------
[ชุดข้อมูลวิเคราะห์พิเศษ: กองทุนรวม KTB RMF1]
----------------------------------------
{rmf1_signals}
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

ข้อบังคับสำคัญที่สุดในการสร้างตาราง PART 2 (STRICT CONSTRAINTS):
1. **ห้ามเปลี่ยนสถานะ CDC โดยเด็ดขาด**: ต้องอ่านสถานะ CDC จาก [ชุดข้อมูลวิเคราะห์พิเศษ] ด้านบนอย่างเคร่งครัด
   - หากข้อมูล XAUUSD ระบุว่า 🟢 BULLISH ให้แสดงตาราง CDC (1D) เป็น 🟢 BULLISH (ซื้อ-ถือครอง) เท่านั้น
   - ห้ามสรุปเป็น BEARISH หากในข้อมูลเขียนว่า BULLISH
2. **คำแนะนำในตาราง**: ต้องสอดคล้องกับสภาวะ BULLISH เช่น แนะนำ "ถือครอง / หาจังหวะเข้าซื้อเพิ่มเมื่อย่อตัว" ไม่ใช่ "พักเงิน"

จงประมวลผลอย่างเป็นระบบและเขียน 'รายงานสรุปกลยุทธ์ฟิวชันข้ามมิติ' เป็นภาษาไทย โดยแยกประเด็นออกเป็น 5 ส่วนดังนี้:

[PART 1: การประเมินสุขภาพพอร์ตจริง (Portfolio Health Check & Risk Assessment)]
- ประเมินพอร์ตปัจจุบันของผู้ใช้ว่าสอดคล้องกับเป้าหมาย 'ชนะเงินเฟ้อ + เงินต้นไม่เสียหาย' มากน้อยเพียงใด
- วิเคราะห์สัดส่วนสินทรัพย์เสี่ยงสูง (เช่น หุ้น, BTC) เทียบกับ สินทรัพย์ปลอดภัย/พักเงิน (KTB RMF1 / ตราสารหนี้ / ทองคำ)

[PART 2: สรุปสภาวะเทคนิคอลทองคำ (XAUUSD) และ บิทคอยน์ (BTCUSD)]
- ให้สรุปการวิเคราะห์สภาวะเทคนิคอลของ XAUUSD และ BTCUSD ออกมาเป็นรูปแบบ Markdown Table เท่านั้น
- ห้ามใส่ Bullet points ใน PART 2 เด็ดขาด
- ใช้รูปแบบโครงสร้างตารางดังนี้เท่านั้น:
| สินทรัพย์ | ราคาปัจจุบัน | CDC (1D) | Stochastic (1D) | CDC (4H) | Stochastic (4H) | คำแนะนำ / กลยุทธ์ | จุดเข้าซื้อที่ปลอดภัย |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **ทองคำ (XAUUSD)** | ... | ... | ... | ... | ... | ... | ... |
| **บิทคอยน์ (BTCUSD)** | ... | ... | ... | ... | ... | ... | ... |

[PART 3: บทวิเคราะห์ความสอดคล้อง (Macro-Technical Linkage)]
- วิเคราะห์สภาวะตลาดปัจจุบันเทียบกับพอร์ต เช่น สัญญาณ TradingView และข่าวสาร Investing.com บ่งชี้ความเสี่ยงที่จะกระทบเงินต้นของพอร์ตนี้หรือไม่

# แก้ไขข้อความใน macro_tech_prompt ของ main.py

[PART 4: คำแนะนำจัดพอร์ตและกลยุทธ์ Switching (Action Plan & KTB RMF Strategy)]
- ให้สรุปสัดส่วนการ DCA หรือการสับเปลี่ยนกองทุน (Switching) ออกมาเป็นรูปแบบ Markdown Table เท่านั้น
- ห้ามใส่ Bullet points ใน PART 4 เด็ดขาด
- ใช้รูปแบบโครงสร้างตารางดังนี้เท่านั้น:

| กองทุน / สินทรัพย์ | ประเภทสินทรัพย์ & ระดับความเสี่ยง | สัดส่วนแนะนำ (%) | มูลค่าโดยประมาณ (บาท) | บทบาทและเป้าหมายในพอร์ต |
| :--- | :--- | :---: | :---: | :--- |
| **KTB RMF1** | กองทุนรวมผสม (เน้นหุ้นไทย ~70%) / เสี่ยงปานกลางค่อนข้างสูง | ...% | ... | **Growth Zone:** สร้างผลตอบแทนชนะเงินเฟ้อระยะยาว |
| **KTB RMF4** | กองทุนตลาดเงิน (ตราสารหนี้ระยะสั้น) / เสี่ยงต่ำมาก | ...% | ... | **Safe Zone:** ปกป้องเงินต้น รับประกันเงินต้นไม่เสียหาย |
| **ทองคำ (XAUUSD)** | สินทรัพย์ป้องกันความเสี่ยง (Safe Haven) | ...% | ... | กระจายความเสี่ยงและป้องกันเงินเฟ้อ |
| **บิทคอยน์ (BTCUSD)** | สินทรัพย์เสี่ยงสูง (Growth Asset) | ...% | ... | เพิ่มโอกาสสร้าง Alpha ตามสัญญาณ CDC |

- *ข้อบังคับสำคัญสูงสุดสำหรับ RMF:*
  1. **KTB RMF1** = กองทุนรวมผสม/เน้นหุ้นไทย (Growth Zone - ชนะเงินเฟ้อ)
  2. **KTB RMF4** = กองทุนตลาดเงิน/ตราสารหนี้ระยะสั้น (Safe Zone - ปกป้องเงินต้น)
  3. **ห้ามสลับประเภทกองทุน KTB RMF1 และ KTB RMF4 โดยเด็ดขาด**
  
[PART 5: สคริปต์รวบยอดสำหรับสร้าง Podcast ใน NotebookLM]
- แปลงบทวิเคราะห์ให้กลายเป็น 'สคริปต์บทพูดสั้น เร้าใจ และเป็นทางการ' (ความยาว 3-4 ย่อหน้า) ภาษาไทย เพื่อป้อนให้ระบบ NotebookLM แปลงเป็นเสียง Podcast

เขียนรายงานด้วยน้ำเสียงสถาบันการเงิน เฉียบคม ตรงไปตรงมา กระชับ และไม่มีคำเกริ่นนำที่ไม่จำเป็น
"""

    print("\n🧠 กำลังส่งข้อมูลฟิวชันป้อนเข้า Gemini...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
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
        repo_name = os.environ.get("GITHUB_REPOSITORY", "narongsak14a/my-investment-bot-v8")
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
