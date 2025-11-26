from flask import Flask, request, jsonify
from app.services.claude_service import ClaudeService
from app.services.telegram_service import TelegramService
from app.services.storage_service import StorageService
from app.services.okx_service import OKXService
from app.config import Config
from datetime import datetime
import logging
import sys
import json

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Config validation ve services init
try:
    Config.validate()
    claude = ClaudeService()
    telegram = TelegramService()
    storage = StorageService()
    okx = OKXService()
    logger.info("✅ All services initialized")
except Exception as e:
    logger.error(f"❌ Service initialization failed: {e}")
    sys.exit(1)

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        "service": "T-TARS Trading Bot v1.2",
        "version": "1.2.1",
        "status": "running",
        "model": Config.CLAUDE_MODEL,
        "features": ["telegram_commands", "cloud_storage", "tradingview_webhook", "okx_realtime_data", "smart_money_detection", "volume_analysis", "auto_scan", "manual_scan"]
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model": Config.CLAUDE_MODEL,
        "bucket": Config.BUCKET_NAME
    })

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Telegram Webhook - Bot komutları"""
    try:
        data = request.json
        
        if not data or 'message' not in data:
            return jsonify({"status": "ignored"}), 200
        
        message = data['message']
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        logger.info(f"📱 Telegram command: {text} from {chat_id}")
        
        # Sadece authorized chat_id'den komut kabul et
        if str(chat_id) != Config.TELEGRAM_CHAT_ID:
            logger.warning(f"Unauthorized chat_id: {chat_id}")
            return jsonify({"status": "unauthorized"}), 403
        
        # Komutları işle
        if text.startswith('/plan'):
            handle_plan_command(text)
        elif text.startswith('/execute'):
            handle_execute_command(text)
        elif text.startswith('/log'):
            handle_log_command(text)
        elif text.startswith('/check') or text.startswith('/status'):
            handle_check_command()
        elif text.startswith('/scan'):
            handle_scan_command()
        elif text.startswith('/help'):
            handle_help_command()
        else:
            telegram.send("❓ Bilinmeyen komut. `/help` yazın.")
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"❌ Telegram webhook error: {e}")
        return jsonify({"error": str(e)}), 500

def handle_plan_command(text):
    """
    /plan [parite] - İşlem öncesi plan oluştur
    Örnek: /plan BTCUSDT
    """
    try:
        # Parite parse et
        parts = text.split()
        ticker = parts[1] if len(parts) > 1 else "BTCUSDT"
        ticker = ticker.upper()  # Büyük harfe çevir
        
        # OKX Futures formatına çevir (BTCUSDT → BTC/USDT:USDT)
        if '/' not in ticker:
            base = ticker[:-4]  # BTC
            quote = ticker[-4:]  # USDT
            ticker = f"{base}/{quote}:{quote}"  # BTC/USDT:USDT (Perpetual Futures)
        
        # Feedback mesajı
        telegram.send(f"🔄 **{ticker.replace('/', '')} analizi bekleniyor...**\n\n⏳ Market data çekiliyor...")
        
        # Gerçek market data çek (FULL ANALYSIS)
        market_data = okx.get_complete_analysis_data(ticker)
        
        # Şablonu oku
        template = storage.get_plan_template()
        
        # Bias belirleme (PDC'ye göre)
        pdc = market_data['previous_day']
        bias_emoji = "🟢" if pdc['candle_type'] == 'green' else "🔴"
        bias_text = "**LONG**" if pdc['candle_type'] == 'green' else "**SHORT**"
        
        # Volume summary
        volume_4h = market_data['volume']['4h']
        volume_1h = market_data['volume']['1h']
        volume_15m = market_data['volume']['15m']
        volume_3m = market_data['volume']['3m']
        
        # Bias'a göre kuralları hazırla
        if pdc['candle_type'] == 'red':
            bias_rules = f"""
### 🔴 SHORT BİAS KURALLARI:

1. **STOP:** Entry üstünde (sweep koruması)
2. **TP:** Entry altında (fiyat düşecek)
3. **FİBO ENTRY:** %61.8 - %100 arası (PDC LOW yakın)
4. **FİBO TP:** Extension 1.272 - 1.618 (PDC LOW altı)
5. **YORUMLAMA:** 
   - %100 (PDC LOW) = Güçlü destek (buradan yükseliş)
   - %0 (PDC HIGH) = Güçlü direnç (buradan düşüş)
   - Entry ideal: %70.5 - %78.6 civarı
"""
        else:
            bias_rules = f"""
### 🟢 LONG BİAS KURALLARI:

1. **STOP:** Entry altında
2. **TP:** Entry üstünde (fiyat yükselecek)
3. **FİBO ENTRY:** %61.8 - %100 arası (PDC HIGH yakın)
4. **FİBO TP:** %23.6 - %0 arası (PDC HIGH üstü)
5. **YORUMLAMA:**
   - %0 (PDC LOW) = Güçlü destek
   - %100 (PDC HIGH) = Önceki zirve (buradan düşüş riski)
   - Entry ideal: %70.5 - %78.6 civarı
"""
        
        # Bias detaylarını hazırla
        if pdc['candle_type'] == 'red':
            bias_details = f"""
🔴 SHORT BIAS - DÜŞÜŞ BEKLENTİSİ:

- Current Price: ${market_data['current_price']:,.2f}
- STOP: Current üstünde (örnek: $112,500+)
- TP: Current altında (örnek: $110,000, $109,500)
- Entry Zone: Fibo %61.8 - %100 arası (${market_data['fibonacci']['levels']['61.8']:,.2f} - ${market_data['fibonacci']['levels']['100.0']:,.2f})
- TP Zone: Extension 1.272, 1.618 (${market_data['fibonacci']['levels']['1.272']:,.2f}, ${market_data['fibonacci']['levels']['1.618']:,.2f})

FİBO YORUMLAMA (Kırmızı mum - Ters fibo):
- %100 (${market_data['fibonacci']['levels']['100.0']:,.2f}) = PDC LOW = Güçlü DESTEK
- %78.6 (${market_data['fibonacci']['levels']['78.6']:,.2f}) = İdeal ENTRY (destek yakını)
- %61.8 (${market_data['fibonacci']['levels']['61.8']:,.2f}) = Entry üst sınır
- %0 (${market_data['fibonacci']['levels']['0.0']:,.2f}) = PDC HIGH = Güçlü DİRENÇ
- Extension 1.272/1.618 = Aggressive SHORT TP (daha aşağı)
"""
        else:
            bias_details = f"""
🟢 LONG BIAS - YÜKSELIŞ BEKLENTİSİ:

- Current Price: ${market_data['current_price']:,.2f}
- STOP: Current altında
- TP: Current üstünde
- Entry Zone: Fibo %61.8 - %100 arası
- TP Zone: %23.6 - %0 arası

FİBO YORUMLAMA (Yeşil mum - Normal fibo):
- %0 (${market_data['fibonacci']['levels']['0.0']:,.2f}) = PDC LOW = Güçlü DESTEK
- %61.8 (${market_data['fibonacci']['levels']['61.8']:,.2f}) = İdeal ENTRY
- %78.6 (${market_data['fibonacci']['levels']['78.6']:,.2f}) = Entry üst sınır
- %100 (${market_data['fibonacci']['levels']['100.0']:,.2f}) = PDC HIGH = Önceki zirve
"""
        
        # TP kurallarını hazırla
        if pdc['candle_type'] == 'red':
            tp_rules = f"""
🔴 SHORT BIAS → TP'LER AŞAĞIDA:

- Tars TP (Conservative): Extension 1.272 (${market_data['fibonacci']['levels']['1.272']:,.2f})
- Kadircan TP (Aggressive): Extension 1.618 (${market_data['fibonacci']['levels']['1.618']:,.2f})
- KRİTİK: TP'ler mevcut fiyattan (${market_data['current_price']:,.2f}) AŞAĞIDA olmalı!
- Volume güçlü ise daha aşağı seviyeleri hedefle
- STOP: Mevcut fiyattan YUKARDA (örnek: $112,500+)
"""
        else:
            tp_rules = f"""
🟢 LONG BIAS → TP'LER YUKARDA:

- Tars TP (Conservative): %38.2 - %50 (${market_data['fibonacci']['levels']['38.2']:,.2f} - ${market_data['fibonacci']['levels']['50.0']:,.2f})
- Kadircan TP (Aggressive): %61.8 - %78.6 (${market_data['fibonacci']['levels']['61.8']:,.2f} - ${market_data['fibonacci']['levels']['78.6']:,.2f})
- KRİTİK: TP'ler mevcut fiyattan (${market_data['current_price']:,.2f}) YUKARDA olmalı!
- Volume güçlü ise extension (1.272, 1.618) hedefle
- STOP: Mevcut fiyattan AŞAĞIDA
"""
        
        # Claude'a gönder - VOLUME-AWARE PROMPT
        prompt = f"""
Sen T-TARS trading asistanısın. **T-Tars Plan** şablonunu GERÇEK MARKET DATA ile dolduracaksın.

**KRITIK: VOLUME HER ANALİZDE KULLANILMALI!**

═══════════════════════════════════════════════
📊 GERÇEK MARKET DATA
═══════════════════════════════════════════════

**Tarih:** {market_data['current_date']}
**Saat:** {market_data['current_time']}
**Anlık Fiyat:** ${market_data['current_price']:,.2f}

**Önceki Gün Mumu (PDC) - {pdc['date']}:**
- Tip: {pdc['candle_type'].upper()}
- Open: ${pdc['open']:,.2f}
- High: ${pdc['high']:,.2f}
- Low: ${pdc['low']:,.2f}
- Close: ${pdc['close']:,.2f}
- Volume: {pdc['volume']:,.0f}

**Bias (PDC'ye göre):** {bias_emoji} {bias_text}

**KRİTİK: BIAS'A GÖRE TP/STOP MANTIK:**

{bias_rules}

═══════════════════════════════════════════════
📈 ATR(14) - MULTI TIMEFRAME
═══════════════════════════════════════════════
- 1G (Daily): ${market_data['atr']['1d']:,.2f}
- 4S (4H): ${market_data['atr']['4h']:,.2f}
- 1S (1H): ${market_data['atr']['1h']:,.2f}
- 15D (15Min): ${market_data['atr']['15m']:,.2f}
- 5D (5Min): ${market_data['atr']['5m']:,.2f}

**Stop Hesaplaması:**
- Kadircan Stop (Sabit): ${market_data['stop_loss']['stop_price']:,.2f}

**Tars Stop için AI Karar Vermelisin:**
1. Entry hangi timeframe'de olacak? (15D, 1H, 4H?)
2. O timeframe'in ATR'si nedir?
3. Volume ve volatilite nasıl?
4. Dinamik multiplier belirle (1.0 - 2.5 arası)
5. Hesapla: Current Price - (Seçilen ATR × Multiplier)
6. Açıkla: "15D ATR × 1.5 kullandım çünkü..."

═══════════════════════════════════════════════
🎯 FIBONACCI SEVİYELERİ (PDC)
═══════════════════════════════════════════════
PDC Tipi: {market_data['fibonacci']['candle_type'].upper()}
{"[Kırmızı mum - Ters Fibo]" if market_data['fibonacci']['candle_type'] == 'red' else "[Yeşil mum - Normal Fibo]"}

- 100.0%: ${market_data['fibonacci']['levels']['100.0']:,.2f}
- 78.6%: ${market_data['fibonacci']['levels']['78.6']:,.2f}
- 70.5%: ${market_data['fibonacci']['levels']['70.5']:,.2f}
- 61.8%: ${market_data['fibonacci']['levels']['61.8']:,.2f}
- 50.0%: ${market_data['fibonacci']['levels']['50.0']:,.2f}
- 38.2%: ${market_data['fibonacci']['levels']['38.2']:,.2f}
- 23.6%: ${market_data['fibonacci']['levels']['23.6']:,.2f}
- 0.0%: ${market_data['fibonacci']['levels']['0.0']:,.2f}
- Extension 1.272: ${market_data['fibonacci']['levels']['1.272']:,.2f}
- Extension 1.618: ${market_data['fibonacci']['levels']['1.618']:,.2f}

═══════════════════════════════════════════════
📊 VOLUME ANALİZİ - MULTI TIMEFRAME
═══════════════════════════════════════════════

**4 Saatlik (4S):**
- Mevcut: {volume_4h['current']:,.0f}
- Ortalama: {volume_4h['average']:,.0f}
- Spike: {"✅ EVET" if volume_4h['spike'] else "❌ YOK"} ({volume_4h['spike_ratio']}x)
- Trend: {volume_4h['trend'].upper()}
- Güç: {volume_4h['strength'].upper()}

**1 Saatlik (1S):**
- Mevcut: {volume_1h['current']:,.0f}
- Ortalama: {volume_1h['average']:,.0f}
- Spike: {"✅ EVET" if volume_1h['spike'] else "❌ YOK"} ({volume_1h['spike_ratio']}x)
- Trend: {volume_1h['trend'].upper()}
- Güç: {volume_1h['strength'].upper()}

**15 Dakikalık (15D):**
- Mevcut: {volume_15m['current']:,.0f}
- Ortalama: {volume_15m['average']:,.0f}
- Spike: {"✅ EVET" if volume_15m['spike'] else "❌ YOK"} ({volume_15m['spike_ratio']}x)
- Trend: {volume_15m['trend'].upper()}
- Güç: {volume_15m['strength'].upper()}

**3 Dakikalık (3D):**
- Mevcut: {volume_3m['current']:,.0f}
- Ortalama: {volume_3m['average']:,.0f}
- Spike: {"✅ EVET" if volume_3m['spike'] else "❌ YOK"} ({volume_3m['spike_ratio']}x)
- Trend: {volume_3m['trend'].upper()}
- Güç: {volume_3m['strength'].upper()}

═══════════════════════════════════════════════
🧠 SMART MONEY DETECTION
═══════════════════════════════════════════════

**Order Blocks (4S):**
{json.dumps(market_data['smart_money']['order_blocks']['4h'], indent=2)}

**Order Blocks (1S):**
{json.dumps(market_data['smart_money']['order_blocks']['1h'], indent=2)}

**Order Blocks (15D):**
{json.dumps(market_data['smart_money']['order_blocks']['15m'], indent=2)}

**Order Blocks (5D):**
{json.dumps(market_data['smart_money']['order_blocks']['5m'], indent=2)}

**Fair Value Gaps (4S):**
{json.dumps(market_data['smart_money']['fair_value_gaps']['4h'], indent=2)}

**Fair Value Gaps (1S):**
{json.dumps(market_data['smart_money']['fair_value_gaps']['1h'], indent=2)}

**Fair Value Gaps (15D):**
{json.dumps(market_data['smart_money']['fair_value_gaps']['15m'], indent=2)}

**Fair Value Gaps (5D):**
{json.dumps(market_data['smart_money']['fair_value_gaps']['5m'], indent=2)}

**Liquidity Sweep (1S):**
{json.dumps(market_data['smart_money']['liquidity_sweep'], indent=2)}

═══════════════════════════════════════════════
🎯 GÖREV
═══════════════════════════════════════════════

**T-Tars Plan şablonunu doldururken MUTLAKA şunları yap:**

0. **BIAS'A GÖRE DOĞRU MANTIK KULLAN (ÇOK KRİTİK!):**

{bias_details}

1. **VOLUME HER ANALİZDE KULLAN:**
   - OB tespit ettin? → Volume destekliyor mu kontrol et!
   - FVG var? → Volume spike var mı bak!
   - Sweep tespit? → Volume spike yoksa FAKE sweep!
   - Entry önerisi? → Volume trend'e bak!
   - TP belirleme? → Volume güçlü mü zayıf mı?

2. **Format:**
   - **Anlık Fiyat:** KALIN YAZ
   - **Bias:** {bias_emoji} {bias_text} (Emoji + Kalın)
   - Tarih: {market_data['current_date']}
   - Parite: {ticker.replace('/', '')}

3. **Fibonacci Tablosu:**
   - Yukarıdaki GERÇEK seviyeleri kullan
   - PDC tipi belirt (yeşil/kırmızı)

4. **Stop Seviyeleri Tablosu:**
   - ATR(14) her timeframe için göster
   - **TARS STOP - AI KARAR (ÖNEMLİ):**
     a) Entry timeframe'i belirle (15D, 1H, 4H?)
     b) O timeframe'in ATR'sini seç
     c) Volume + volatilite değerlendir
     d) Multiplier belirle (1.0-2.5 arası)
     e) Hesapla ve AÇIKLA:
        "Örnek: 15D ATR (250 USDT) × 1.5 = 110,225
        Sebep: Entry 15D'de, volume yüksek, volatilite normal"
   - Kadircan Stop = ${market_data['stop_loss']['stop_price']:,.2f} (sabit)

5. **OB/FVG Analizi:**
   - Her OB için: "Volume confirmed: YES/NO" yaz
   - Her FVG için: "Volume spike: YES/NO" yaz
   - Sweep için: "Volume spike: YES/NO" - fake olup olmadığını belirt

6. **15 Dakika (15D) Entry Analizi:**
   - Son mumları kontrol et
   - Volume trend bak
   - Entry zone öner

7. **TP Hedefleri (BIAS'A GÖRE HESAPLA!):**

{tp_rules}


**ÖNEMLİ:**
- GERÇEK fiyatları kullan, icat etme!
- Volume her zaman değerlendir!
- **TELEGRAM FORMAT:** Markdown tablolar yerine basit liste kullan (tablolar bozuluyor)
  ```
  ❌ YANLIŞ: | Seviye | Fiyat |
  ✅ DOĞRU: 
  • 78.6%: $112,976
  • 61.8%: $113,634
  ```
- Emoji kullan
- Kısa ve net ol
- "ZONADAHI" değil "Zone içinde" yaz

Sadece doldurulmuş şablonu döndür.
"""
        
        result = claude.analyze(prompt)
        
        # Telegram'a gönder (uzunsa böl)
        message = f"📊 *T-TARS PLAN - {ticker.replace('/', '')}*\n\n{result['text']}"
        
        if len(message) > 4000:
            # Uzun mesajı böl
            telegram.send(message[:4000] + "...")
            telegram.send("...(devam)\n" + message[4000:8000])
            if len(message) > 8000:
                telegram.send("...(devam)\n" + message[8000:])
        else:
            telegram.send(message)
        
        logger.info(f"✅ Plan sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Plan command error: {e}")
        telegram.send(f"❌ Hata: {str(e)}")

def handle_execute_command(text):
    """
    /execute [parite] - Aktif işlem durumu
    """
    try:
        parts = text.split()
        ticker = parts[1] if len(parts) > 1 else "BTCUSDT"
        
        template = storage.get_execute_template()
        
        prompt = f"""
Sen T-TARS trading asistanısın. **T-Tars Execute** şablonunu doldur.

**ŞABLON:**
{template}

**GÖREV:**
1. {ticker} için aktif işlem durumunu raporla
2. Entry scout varsa listele
3. Gerçekleşen işlemleri kaydet
4. Senaryo analizi yap

Sadece doldurulmuş şablonu döndür.
"""
        
        result = claude.analyze(prompt)
        message = f"⚡ *T-TARS EXECUTE - {ticker}*\n\n{result['text']}"
        
        if len(message) > 4000:
            telegram.send(message[:4000] + "...")
            telegram.send("...(devam)\n" + message[4000:])
        else:
            telegram.send(message)
        
        logger.info(f"✅ Execute sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Execute command error: {e}")
        telegram.send(f"❌ Hata: {str(e)}")

def handle_log_command(text):
    """
    /log - Tüm işlemlerin özet tablosu
    """
    try:
        template = storage.get_log_template()
        
        prompt = f"""
Sen T-TARS trading asistanısın. **T-Tars Trade Log** şablonunu doldur.

**ŞABLON:**
{template}

**GÖREV:**
1. Son işlemlerin özet tablosunu oluştur
2. HTF ve LTF setup'ları özetle
3. P&L hesapla

Sadece doldurulmuş şablonu döndür.
"""
        
        result = claude.analyze(prompt)
        message = f"📋 *T-TARS TRADE LOG*\n\n{result['text']}"
        
        if len(message) > 4000:
            telegram.send(message[:4000] + "...")
            telegram.send("...(devam)\n" + message[4000:])
        else:
            telegram.send(message)
        
        logger.info(f"✅ Log sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Log command error: {e}")
        telegram.send(f"❌ Hata: {str(e)}")

def handle_check_command():
    """Bot durum kontrolü"""
    try:
        from datetime import datetime
        import time
        
        check_start = time.time()
        
        # Servis durumları test et
        services_status = {
            'telegram': '❓',
            'okx': '❓',
            'claude': '❓',
            'storage': '❓'
        }
        
        # 1. Telegram Test
        try:
            telegram.send("🔄 Kontrol yapılıyor...")
            services_status['telegram'] = '✅'
        except:
            services_status['telegram'] = '❌'
        
        # 2. OKX Test
        try:
            test_price = okx.get_current_price('BTC/USDT:USDT')
            services_status['okx'] = f'✅ (${test_price:,.2f})'
        except Exception as e:
            services_status['okx'] = f'❌ ({str(e)[:20]})'
        
        # 3. Claude Test (Simple ping)
        try:
            # Basit test mesajı - sadece servis aktif mi kontrol et
            from anthropic import Anthropic
            client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            services_status['claude'] = '✅'
        except Exception as e:
            services_status['claude'] = f'❌ ({str(e)[:20]})'
        
        # 4. Storage Test
        try:
            test_template = storage.get_plan_template()
            services_status['storage'] = '✅'
        except Exception as e:
            services_status['storage'] = f'❌ ({str(e)[:20]})'
        
        check_time = (time.time() - check_start) * 1000  # ms
        
        # Durum mesajı
        status_message = f"""
🤖 **T-TARS BOT DURUM KONTROLÜ**

⏰ **Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⚡ **Response Time:** {check_time:.0f}ms

---

📡 **SERVİSLER:**

• Telegram: {services_status['telegram']}
• OKX Market: {services_status['okx']}
• Claude AI: {services_status['claude']}
• Cloud Storage: {services_status['storage']}

---

📊 **SİSTEM BİLGİLERİ:**

• Bot Version: v1.2.1
• Model: {Config.CLAUDE_MODEL}
• Environment: Google Cloud Run
• Region: us-central1

---

✅ **BOT AKTİF VE HAZIR!**

Komutlar için: /help
"""
        
        telegram.send(status_message)
        logger.info(f"✅ Check command completed in {check_time:.0f}ms")
        
    except Exception as e:
        logger.error(f"❌ Check command error: {e}")
        telegram.send(f"❌ Kontrol hatası: {str(e)}")

def handle_scan_command():
    """
    /scan - Manuel market taraması
    """
    try:
        telegram.send("🔍 **Market taraması başlatılıyor...**\n\n⏳ BTCUSDT + SOLUSDT analiz ediliyor...")
        
        pairs = ['BTC/USDT:USDT', 'SOL/USDT:USDT']
        results = []
        setup_found = False
        
        for pair in pairs:
            try:
                market_data = okx.get_complete_analysis_data(pair)
                setup_detected = detect_trading_setup(pair, market_data)
                
                if setup_detected:
                    setup_found = True
                    setup_type = setup_detected['type']
                    confidence = setup_detected['confidence']
                    
                    message = f"""
🚨 **SETUP DETECTED!**

📊 **Parite:** {pair.replace('/USDT:USDT', 'USDT')}
🎯 **Setup:** {setup_type}
⚡ **Confidence:** {confidence}

💰 **Price:** ${market_data['current_price']:,.2f}
📅 **Time:** {market_data['current_time']}

---
**Detaylar:**
{setup_detected['details']}
"""
                    telegram.send(message)
                    results.append(f"✅ {pair.replace('/USDT:USDT', 'USDT')}: Setup found")
                else:
                    results.append(f"ℹ️ {pair.replace('/USDT:USDT', 'USDT')}: No setup")
                    
            except Exception as e:
                logger.error(f"Error scanning {pair}: {e}")
                results.append(f"❌ {pair.replace('/USDT:USDT', 'USDT')}: Error")
        
        if not setup_found:
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "\n".join(results)
            summary += f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            telegram.send(summary)
        
        logger.info(f"✅ Manual scan completed: {len(pairs)} pairs")
        
    except Exception as e:
        logger.error(f"❌ Scan command error: {e}")
        telegram.send(f"❌ Tarama hatası: {str(e)}")

def handle_help_command():
    """Yardım mesajı"""
    help_text = """
🤖 *T-TARS Trading Bot v1.2*

📊 `/plan` - BTCUSDT için tam analiz
   • Gerçek OKX data
   • Volume analizi
   • OB/FVG/Sweep detection
   • Multi-timeframe ATR
   • Dinamik Fibonacci

📊 `/plan ETHUSDT` - Farklı parite

🔍 `/scan` - Manuel market taraması (BTC + SOL)

⚡ `/execute` - Aktif durum
📋 `/log` - İşlem özeti
🔍 `/check` - Bot durum kontrolü
❓ `/help` - Bu mesaj

---
🔗 *Webhook:*
`https://tars-api-609075413784.us-central1.run.app/webhook/tradingview`

🆕 *v1.2 Yenilikler:*
✅ Auto-scan (3 dakikada bir)
✅ /scan komutu (manuel tarama)
✅ Volume-aware analiz
✅ Order Block detection
✅ Fair Value Gap detection
✅ Liquidity Sweep detection
✅ Multi-timeframe ATR (3m)
✅ Dinamik Fibonacci (PDC)
"""
    telegram.send(help_text)

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """TradingView Webhook Endpoint"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400
        
        logger.info(f"📊 TradingView Alert: {data}")
        
        ticker = data.get('ticker', 'UNKNOWN')
        interval = data.get('interval', 'N/A')
        close = data.get('close', 'N/A')
        
        message = f"""
🚨 *TRADINGVIEW ALERT*

📊 {ticker} | {interval}
💰 ${close}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        telegram.send(message)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"❌ TradingView webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test/telegram', methods=['GET'])
def test_telegram():
    """Telegram test endpoint"""
    try:
        telegram.send(f"🧪 *T-TARS v3.0 Test*\n\n✅ Sistem çalışıyor!\n\n⏰ {datetime.now().strftime('%H:%M:%S')}")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def detect_trading_setup(pair, market_data):
    """Trading setup tespit et"""
    try:
        pdc = market_data['previous_day']
        bias = 'bullish' if pdc['candle_type'] == 'green' else 'bearish'
        
        volume_3m = market_data['volume']['3m']
        obs_3m = market_data['smart_money']['order_blocks']['3m']
        fvgs_3m = market_data['smart_money']['fair_value_gaps']['3m']
        
        has_volume_spike = volume_3m['spike']
        has_order_block = len(obs_3m) > 0
        has_fvg = len(fvgs_3m) > 0
        
        if has_order_block and has_volume_spike:
            ob = obs_3m[0]
            if bias == 'bullish' and ob['type'] == 'bullish':
                return {'type': 'OB + Volume Spike (LONG)', 'confidence': 'HIGH', 'details': f"Bullish OB @ ${ob['low']:,.2f}\nVolume: {volume_3m['spike_ratio']}x spike"}
            elif bias == 'bearish' and ob['type'] == 'bearish':
                return {'type': 'OB + Volume Spike (SHORT)', 'confidence': 'HIGH', 'details': f"Bearish OB @ ${ob['high']:,.2f}\nVolume: {volume_3m['spike_ratio']}x spike"}
        
        if has_fvg and has_volume_spike:
            fvg = fvgs_3m[0]
            return {'type': f'FVG + Volume Spike ({bias.upper()})', 'confidence': 'MEDIUM', 'details': f"FVG: ${fvg['low']:,.2f} - ${fvg['high']:,.2f}\nVolume: {volume_3m['spike_ratio']}x"}
        
        return False
    except Exception as e:
        logger.error(f"Setup detection error: {e}")
        return False

@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """Cloud Scheduler tarafından her 3 dakikada tetiklenen otomatik analiz"""
    try:
        pairs = ['BTC/USDT:USDT', 'SOL/USDT:USDT']
        results = []
        
        for pair in pairs:
            try:
                market_data = okx.get_complete_analysis_data(pair)
                setup_detected = detect_trading_setup(pair, market_data)
                
                if setup_detected:
                    message = f"""🚨 **SETUP DETECTED!**\n\n📊 **Parite:** {pair.replace('/USDT:USDT', 'USDT')}\n🎯 **Setup:** {setup_detected['type']}\n⚡ **Confidence:** {setup_detected['confidence']}\n\n💰 **Price:** ${market_data['current_price']:,.2f}\n📅 **Time:** {market_data['current_time']}\n\n---\n**Detaylar:**\n{setup_detected['details']}"""
                    telegram.send(message)
                    results.append(f"{pair}: Setup found")
                else:
                    results.append(f"{pair}: No setup")
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
                results.append(f"{pair}: Error")
        
        return jsonify({"status": "success", "timestamp": datetime.now().isoformat(), "results": results})
    except Exception as e:
        logger.error(f"Auto analyze error: {e}")
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS Trading Bot v1.2.1 on port {Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)
