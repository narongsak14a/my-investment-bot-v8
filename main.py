import os
import time
import requests
import feedparser
import pandas as pd
import pandas_ta as ta
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

YOUTUBE_VIDEO_IDS = [""]

# ใส่ URL ที่ได้จากการ Publish Google Sheet เป็น CSV ตรงนี้
GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-xxxxxxx/pub?output=csv"

# ==========================================
# ฟังก์ชันดึง ASSETS จาก Google Sheet
# ==========================================
def fetch_assets_from_google_sheet():
    print("⏳ กำลังดึงรายการ ASSETS จาก Google Sheet...")
    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        # แปลงข้อมูลใน Sheet ให้เป็น List of Dicts
        assets_list = df.to_dict(orient='records')
        print(f"✅ ดึงรายการสินทรัพย์สำเร็จ ทั้งหมด {len(assets_list)} รายการ")
        return assets_list
    except Exception as e:
        print(f"⚠️ ไม่สามารถดึงข้อมูลจาก Google Sheet ได้ ({e}) นำเข้าค่าสำรองแทน")
        # รายการสำรอง (Fallback) หากดึง Sheet ไม่สำเร็จ
        return [
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
            {"name": "KTB RMF1 Benchmark (Bond Yield 10Y)", "symbol": "US10Y", "exchange": "TVC", "screener": "bond"}
        ]
# เรียกใช้งานฟังก์ชันดึง ASSETS
ASSETS = fetch_assets_from_google_sheet()

# ==========================================
# Helper Function: ป้องกัน HTTP 429 (Rate Limit)
# ==========================================
def get_analysis_safe(handler, retries=3, delay=3.0):
    """เรียกใช้ get_analysis() พร้อมระบบชะลอเวลาและลองใหม่เมื่อติด Rate Limit (429)"""
    for i in range(retries):
        try:
            return handler.get_analysis()
        except Exception as e:
            if "429" in str(e) and i < retries - 1:
                print(f"⚠️ ติด Rate Limit (429) ชั่วคราว รอ {delay:.1f} วินาที แล้วลองใหม่ (พยายามครั้งที่ {i+1}/{retries})...")
                time.sleep(delay)
                delay *= 2  # เพิ่มเวลาหน่วงแบบ Exponential Backoff
            else:
                raise e

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลดิบ (Data Acquisition)
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

def fetch_rss_news():
    print("⏳ กำลังเชื่อมต่อดึงข้อมูลข่าวสารและบทวิเคราะห์...")
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
    return news_compiled if news_compiled else "• ไม่สามารถดึงข้อมูลข่าวสารได้ในขณะนี้\n"

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
            analysis = get_analysis_safe(handler)
            rec = analysis.summary.get('RECOMMENDATION', 'N/A')
            buy = analysis.summary.get('BUY', 0)
            sell = analysis.summary.get('SELL', 0)
            neutral = analysis.summary.get('NEUTRAL', 0)
            tv_summary_report += f"- {asset['name']}: สัญญาณสรุป [{rec}] (แรงซื้อ: {buy}, แรงขาย: {sell}, ถือครอง: {neutral})\n"
            
            time.sleep(1.5)
        except Exception as e:
            tv_summary_report += f"- {asset['name']}: ดึงข้อมูลไม่สำเร็จ ({e})\n"
    return tv_summary_report

def calculate_cdc_and_stoch(handler_analysis):
    indicators = handler_analysis.indicators
    close_price = indicators.get("close", 0)
    ema12 = indicators.get("EMA12", indicators.get("EMA10", 0))
    ema26 = indicators.get("EMA26", indicators.get("EMA20", 0))
    summary_rec = handler_analysis.summary.get('RECOMMENDATION', 'N/A')

    if ema12 > 0 and ema26 > 0:
        cdc_status = "🟢 BULLISH (โซนสีเขียว / ซื้อ-ถือครอง)" if ema12 > ema26 else "🔴 BEARISH (โซนสีแดง / ขาย-พักเงิน)"
    else:
        cdc_status = "🟢 BULLISH (โซนสีเขียว / ซื้อ-ถือครอง)" if "BUY" in summary_rec else "🔴 BEARISH (โซนสีแดง / ขาย-พักเงิน)"

    stoch_k = indicators.get("Stoch.K", 0)
    stoch_d = indicators.get("Stoch.D", 0)
    stoch_status = "Neutral"
    if stoch_k < 20:
        stoch_status = "🔵 Oversold (ขายมากเกินไป - ลุ้นดีดกลับ/จังหวะตั้งรับ)"
    elif stoch_k > 80:
        stoch_status = "🟠 Overbought (ซื้อมากเกินไป - ระวังการย่อตัว)"

    return close_price, ema12, ema26, cdc_status, stoch_k, stoch_d, stoch_status, summary_rec

def fetch_gold_analysis_detail():
    print("⏳ กำลังดึงสัญญาณเทคนิคอลเจาะลึกทองคำ (XAUUSD)...")
    timeframes = {"1D (ภาพรวมวัน)": Interval.INTERVAL_1_DAY, "4H (จังหวะระยะสั้น)": Interval.INTERVAL_4_HOURS}
    gold_report = "=== [การวิเคราะห์เจาะลึกทองคำ XAUUSD (CDC ActionZone + Stochastic 14, 3, 3)] ===\n"
    for tf_name, tf_interval in timeframes.items():
        try:
            handler = TA_Handler(symbol="XAUUSD", exchange="OANDA", screener="cfd", interval=tf_interval)
            analysis = get_analysis_safe(handler)
            close_price, ema12, ema26, cdc_status, stoch_k, stoch_d, stoch_status, summary_rec = calculate_cdc_and_stoch(analysis)
            gold_report += (
                f"\n📌 Timeframe: {tf_name}\n"
                f"  - ราคาปัจจุบัน: {close_price:.2f}\n"
                f"  - สัญญาณสรุป TradingView: [{summary_rec}]\n"
                f"  - CDC ActionZone (EMA12/EMA26): {cdc_status} (EMA12: {ema12:.2f}, EMA26: {ema26:.2f})\n"
                f"  - Stochastic (14, 3, 3): %K = {stoch_k:.2f}, %D = {stoch_d:.2f} [{stoch_status}]\n"
            )
            time.sleep(1.5)
        except Exception as e:
            gold_report += f"\n⚠️ ไม่สามารถดึงข้อมูล XAUUSD ({tf_name}) ได้: {e}\n"
    return gold_report

def fetch_btc_analysis_detail():
    print("⏳ กำลังดึงสัญญาณเทคนิคอลเจาะลึกบิทคอยน์ (BTCUSD)...")
    timeframes = {"1D (ภาพรวมวัน)": Interval.INTERVAL_1_DAY, "4H (จังหวะระยะสั้น)": Interval.INTERVAL_4_HOURS}
    btc_report = "=== [การวิเคราะห์เจาะลึกบิทคอยน์ BTCUSD (CDC ActionZone + Stochastic 14, 3, 3)] ===\n"
    for tf_name, tf_interval in timeframes.items():
        try:
            handler = TA_Handler(symbol="BTCUSD", exchange="BINANCE", screener="crypto", interval=tf_interval)
            analysis = get_analysis_safe(handler)
            close_price, ema12, ema26, cdc_status, stoch_k, stoch_d, stoch_status, summary_rec = calculate_cdc_and_stoch(analysis)
            btc_report += (
                f"\n📌 Timeframe: {tf_name}\n"
                f"  - ราคาปัจจุบัน: {close_price:.2f}\n"
                f"  - สัญญาณสรุป TradingView: [{summary_rec}]\n"
                f"  - CDC ActionZone (EMA12/EMA26): {cdc_status} (EMA12: {ema12:.2f}, EMA26: {ema26:.2f})\n"
                f"  - Stochastic (14, 3, 3): %K = {stoch_k:.2f}, %D = {stoch_d:.2f} [{stoch_status}]\n"
            )
            time.sleep(1.5)
        except Exception as e:
            btc_report += f"\n⚠️ ไม่สามารถดึงข้อมูล BTCUSD ({tf_name}) ได้: {e}\n"
    return btc_report

# ==========================================
# 3. ส่วนคำนวณเทคนิครวม KTB RMF1 & RMF4
# ==========================================
def calculate_rmf1_technical_signals(df_nav):
    """คำนวณ WMA, MACD, RSI และ Stochastic สำหรับ KTB RMF1"""
    if df_nav is None or len(df_nav) < 26:
        print("⚠️ ข้อมูลราคา RMF1 ไม่เพียงพอสำหรับประมวลผล")
        return None

    df = df_nav.copy()
    df["WMA12"] = ta.wma(df["close"], length=12)
    df["WMA26"] = ta.wma(df["close"], length=26)

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        df["MACD"] = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]
    else:
        df["MACD"] = 0.0
        df["MACD_Signal"] = 0.0

    df["RSI14"] = ta.rsi(df["close"], length=14)

    if "high" not in df.columns:
        df["high"] = df["close"]
    if "low" not in df.columns:
        df["low"] = df["close"]

    stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
    if stoch is not None and not stoch.empty:
        df["STOCHk"] = stoch["STOCHk_14_3_3"]
        df["STOCHd"] = stoch["STOCHd_14_3_3"]
    else:
        df["STOCHk"] = 0.0
        df["STOCHd"] = 0.0

    latest = df.iloc[-1]
    wma_status = "🟢 BULLISH (Golden Cross)" if latest["WMA12"] > latest["WMA26"] else "🔴 BEARISH (Death Cross)"

    return {
        "close_nav": latest["close"],
        "wma12": latest["WMA12"],
        "wma26": latest["WMA26"],
        "wma_status": wma_status,
        "macd": latest["MACD"],
        "macd_signal": latest["MACD_Signal"],
        "rsi": latest["RSI14"],
        "stoch_k": latest["STOCHk"],
        "stoch_d": latest["STOCHd"]
    }

def fetch_rmf1_analysis_detail():
    """ประมวลผลบทวิเคราะห์และ Logic การสลับพอร์ต KTB RMF1"""
    dummy_data = {
        "close": [62.10, 62.15, 62.20, 62.30, 62.25, 62.40, 62.55, 62.60, 62.80, 63.00,
                  63.10, 63.25, 63.50, 63.80, 64.10, 64.50, 65.00, 65.20, 65.80, 66.10,
                  66.50, 66.80, 67.00, 67.15, 67.20, 67.30, 67.25, 67.28, 67.32, 67.49]
    }
    df_sample = pd.DataFrame(dummy_data)
    result = calculate_rmf1_technical_signals(df_sample)

    if not result:
        return {
            "action": "🟡 [HOLD] ไม่พบข้อมูล",
            "weight": "0%",
            "report_text": "⚠️ ไม่พบข้อมูลสำหรับประมวลผล RMF1"
        }

    wma12 = result['wma12']
    wma26 = result['wma26']
    rsi = result['rsi']
    wma_gap_pct = ((wma12 - wma26) / wma26) * 100

    if wma12 < wma26:
        action_recommendation = "🔴 [REDUCE PORTFOLIO] ลดพอร์ต RMF1 ทันที และ Switching ไปยัง KTB RMF4 เพื่อปกป้องเงินต้น (เกิด Death Cross)"
        suggested_weight = "0% - 10%"
    elif wma_gap_pct < 0.5 and rsi > 80:
        action_recommendation = "⚠️ [TAKE PROFIT / REDUCE] WMA12 ชะลอตัวใกล้ตัด WMA26 ลง + RSI/Stoch Overbought แนะนำทยอยลดพอร์ต RMF1 ล็อกกำไร แล้วย้ายเข้า KTB RMF4"
        suggested_weight = "10% - 20%"
    elif wma12 > wma26:
        if rsi > 80:
            action_recommendation = "🟢 [BUY ON DIP] WMA12 ตัดขึ้นเหนือ WMA26 (Golden Cross) ปรับพอร์ต RMF1 สูงขึ้น แต่เนื่องจาก RSI Overbought ให้เน้นทยอย DCA/ตั้งรับเมื่อย่อตัว"
        else:
            action_recommendation = "🟢 [STRONG BUY] WMA12 ตัดขึ้นเหนือ WMA26 (Golden Cross) สัญญาณขาขึ้นชัดเจน แนะนำปรับพอร์ต RMF1 สูงขึ้น"
        suggested_weight = "30% - 40%"
    else:
        action_recommendation = "🟡 [HOLD] รอดูทิศทางสัญญาณ"
        suggested_weight = "20%"

    rmf1_report = (
        "=== [การวิเคราะห์เทคนิคอล KTB RMF1 (WMA + MACD + RSI + Stoch)] ===\n"
        f"  - ราคา NAV ล่าสุด: {result['close_nav']:.4f}\n"
        f"  - สัญญาณ WMA (12/26): {result['wma_status']} (WMA12: {wma12:.2f}, WMA26: {wma26:.2f})\n"
        f"  - MACD: {result['macd']:.4f} | Signal: {result['macd_signal']:.4f}\n"
        f"  - RSI (14): {rsi:.2f} | Stoch %K: {result['stoch_k']:.2f}, %D: {result['stoch_d']:.2f}\n"
        f"  - คำแนะนำปรับพอร์ต: {action_recommendation} (สัดส่วนแนะนำ: {suggested_weight})\n"
    )

    return {
        "action": action_recommendation,
        "weight": suggested_weight,
        "report_text": rmf1_report,
        "raw_result": result
    }

def fetch_rmf4_analysis_detail():
    """ประมวลผลข้อมูล KTB RMF4 (Safe Zone/ตลาดเงิน)"""
    rmf4_nav = 10.1254
    rmf4_report = (
        "=== [การวิเคราะห์ KTB RMF4 (กองทุนตลาดเงิน / พักเงิน)] ===\n"
        f"  - ราคา NAV ล่าสุด: {rmf4_nav:.4f}\n"
        "  - สถานะ: Safe Zone ความเสี่ยงต่ำ (เงินต้นปลอดภัย)\n"
        "  - คำแนะนำ: ใช้เป็นกองทุนพักเงินเมื่อ RMF1 มีสัญญาณลดพอร์ต\n"
    )
    return {
        "action": "🛡️ [SAFE ZONE] พักเงิน / ปกป้องเงินต้น",
        "weight": "50% - 60%",
        "report_text": rmf4_report,
        "close_nav": rmf4_nav
    }

def send_to_cloudflare(message_text):
    print("⏳ กำลังส่งข้อมูลไปยัง Cloudflare...")
    if not CLOUDFLARE_WORKER_URL:
        print("❌ ไม่พบ CLOUDFLARE_WORKER_URL ใน Secrets")
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
# 4. Pipeline หลักการรันระบบ AI
# ==========================================
def run_investment_ai_pipeline():
    print("\n--- 🚀 เริ่มต้นกระบวนการวิเคราะห์การลงทุนระดับมืออาชีพ ---")

    portfolio_data = fetch_portfolio_data()
    gold_detailed_signals = fetch_gold_analysis_detail()
    btc_detailed_signals = fetch_btc_analysis_detail()
    raw_news_data = fetch_rss_news()
    youtube_insights = fetch_youtube_insights()
    tradingview_signals = fetch_all_tradingview_signals()

    rmf1_analysis = fetch_rmf1_analysis_detail()
    rmf4_analysis = fetch_rmf4_analysis_detail()

    macro_tech_prompt = f"""
    คุณเป็นที่ปรึกษาการลงทุนระดับมืออาชีพ ให้สรุปสภาวะตลาดและจัดทำรายงานวิเคราะห์ประจำวัน

    [ข้อมูลพอร์ตการลงทุนปัจจุบันของผู้ใช้]
    {portfolio_data}

    [ข้อมูลวิเคราะห์ KTB RMF1]
    {rmf1_analysis['report_text']}

    [ข้อมูลวิเคราะห์ KTB RMF4]
    {rmf4_analysis['report_text']}

    [ข้อมูลทองคำ XAUUSD]
    {gold_detailed_signals}

    [ข้อมูลบิทคอยน์ BTCUSD]
    {btc_detailed_signals}

    [ข้อมูลสัญญาณจาก TradingView]
    {tradingview_signals}

    [ข่าวสารล่าสุด]
    {raw_news_data}

    [YouTube Insights]
    {youtube_insights}

    [คำสั่งพิเศษสำหรับการแสดงผลตาราง Markdown]
    ให้จัดทำตาราง Markdown สรุปสัญญาณเทคนิคและกลยุทธ์การลงทุนแยกออกเป็น 2 ตารางอย่างชัดเจน ดังนี้:

    1. **ตารางสรุปภาวะกองทุน KTB RMF:**
    | สินทรัพย์ / กองทุน | ราคา NAV ล่าสุด | สัญญาณ MA (12/26) | Stochastic / RSI (14) | สัญญาณ MACD | สัดส่วนแนะนำ (%) | กลยุทธ์การปรับพอร์ต (Portfolio Strategy) |
    - KTB RMF1: แสดงค่า NAV, สัญญาณ WMA, ค่า RSI และ Stochastic (%K, %D) คำแนะนำเป็น "{rmf1_analysis['action']}" ด้วยสัดส่วน {rmf1_analysis['weight']}
    - KTB RMF4: แสดงค่า NAV และคำแนะนำเป็น "{rmf4_analysis['action']}" ด้วยสัดส่วน {rmf4_analysis['weight']}

    2. **ตารางสรุปสัญญาณเทคนิคอลสินทรัพย์ทางเลือก (XAUUSD & BTCUSD):**
    | สินทรัพย์ | Timeframe | ราคาล่าสุด | CDC ActionZone (EMA12/26) | Stochastic (14,3,3) | สัญญาณสรุป TV | สัดส่วนแนะนำ (%) | กลยุทธ์การลงทุน (Trading Strategy) |
    - XAUUSD: ดึงข้อมูลสรุปทั้ง 1D และ 4H ลงในตาราง พร้อมใส่กลยุทธ์และสัดส่วนน้ำหนักแนะนำ
    - BTCUSD: ดึงข้อมูลสรุปทั้ง 1D และ 4H ลงในตาราง พร้อมใส่กลยุทธ์และสัดส่วนน้ำหนักแนะนำ
    """

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=macro_tech_prompt
    )

    report_text = response.text
    print("\n=== [ผลลัพธ์รายงาน AI] ===")
    print(report_text[:1000])

    send_to_cloudflare(report_text)

if __name__ == "__main__":
    run_investment_ai_pipeline()
