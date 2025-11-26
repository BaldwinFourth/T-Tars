# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from app.services.claude_service import ClaudeService
from app.services.telegram_service import TelegramService
from app.services.storage_service import StorageService
from app.services.okx_service import OKXService
from app.services.tracking_service import TrackingService
from app.config import Config
from app.strategies.calculators import calculate_setup_strength, MIN_RR_RATIO  # v1.4.4
from app.strategies.setup_detector import detect_trading_setup, detect_all_trading_setups  # v1.4.5
from datetime import datetime, timezone, timedelta
import logging
import sys
import json

# Turkey timezone (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))

def get_turkey_time():
    """Get current time in Turkey timezone"""
    return datetime.now(TURKEY_TZ)

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
    tracking = TrackingService()
    logger.info("✅ All services initialized")
except Exception as e:
    logger.error(f"❌ Service initialization failed: {e}")
    sys.exit(1)

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        "service": f"T-TARS Trading Bot v{Config.VERSION}",
        "version": Config.VERSION,
        "status": "running",
        "model": Config.CLAUDE_MODEL,
        "features": ["telegram_commands", "cloud_storage", "tradingview_webhook", "okx_realtime_data", "smart_money_detection", "volume_analysis", "auto_scan", "manual_scan", "setup_tracking"]
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": get_turkey_time().isoformat(),
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
        
        # Sadece komutlara cevap ver (/ ile başlayanlar)
        if not text or not text.startswith('/'):
            return jsonify({"status": "ignored - not a command"}), 200
        
        logger.info(f"📱 Telegram command: {text} from {chat_id}")
        
        # Multi-chat authorization
        allowed_chats = Config.get_allowed_chats()
        if str(chat_id) not in allowed_chats:
            logger.warning(f"Unauthorized chat_id: {chat_id} (Allowed: {allowed_chats})")
            return jsonify({"status": "unauthorized"}), 403
        
        # Komutları işle - CHAT_ID EKLE
        if text.startswith('/plan'):
            handle_plan_command(text, chat_id)
        elif text.startswith('/execute'):
            handle_execute_command(text, chat_id)
        elif text.startswith('/log'):
            handle_log_command(text, chat_id)
        elif text.startswith('/status'):
            handle_status_command(chat_id)
        elif text.startswith('/scan'):
            handle_scan_command(chat_id)
        elif text.startswith('/score'):
            handle_score_command(chat_id)
        elif text.startswith('/help'):
            handle_help_command(chat_id)
        else:
            telegram.send("❌ Bilinmeyen komut. `/help` yazın.", chat_id=chat_id)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"❌ Telegram webhook error: {e}")
        return jsonify({"error": str(e)}), 500

def handle_plan_command(text, chat_id):
    """
    /plan [parite] - İşlem öncesi plan oluştur
    """
    try:
        parts = text.split()
        user_input = parts[1] if len(parts) > 1 else "BTCUSDT"
        
        ticker = Config.get_pair_symbol(user_input)
        
        if ticker not in Config.MANUAL_PAIRS:
            supported = ', '.join([p.split('/')[0] for p in Config.MANUAL_PAIRS[:10]])
            telegram.send(f"❌ **{user_input}** desteklenmiyor.\n\n✅ Desteklenen: {supported}... ve daha fazlası.\n\n`/help` yazarak tüm listeyi görebilirsin.", chat_id=chat_id)
            return
        
        telegram.send(f"🔄 **{ticker.replace('/', '').replace(':USDT', '')} analizi bekleniyor...**\n\n⏳ Market data çekiliyor...", chat_id=chat_id)
        
        market_data = okx.get_complete_analysis_data(ticker)
        template = storage.get_plan_template()
        
        pdc = market_data['previous_day']
        bias_emoji = "🟢" if pdc['candle_type'] == 'green' else "🔴"
        bias_text = "**LONG**" if pdc['candle_type'] == 'green' else "**SHORT**"
        
        volume_4h = market_data['volume']['4h']
        volume_1h = market_data['volume']['1h']
        volume_15m = market_data['volume']['15m']
        volume_5m = market_data['volume']['5m']
        volume_3m = market_data['volume']['3m']
        
        prompt = f"""
Sen T-TARS trading asistanısın. Aşağıdaki KOMPAKT FORMAT'ta plan oluşturacaksın.

══════════════════════════════════════════
📊 GERÇEK MARKET DATA
══════════════════════════════════════════

**Tarih:** {market_data['current_date']}
**Saat:** {market_data['current_time']}
**Anlık Fiyat:** ${market_data['current_price']:,.2f}

**Önceki Gün Mumu (PDC) - {pdc['date']}:**
- Tip: {pdc['candle_type'].upper()}
- High: ${pdc['high']:,.2f}
- Low: ${pdc['low']:,.2f}
- Volume: {pdc['volume']:,.0f}

**Bias (PDC'ye göre):** {bias_emoji} {bias_text}

**KRİTİK: BIAS'A GÖRE FİBO ENTRY MANTIK:**

🔴 SHORT BIAS (Ters Fibo):
- 0% = PDC HIGH (Direnç) → Entry buraya yakın olmalı
- 100% = PDC LOW (Destek) → TP buraya doğru
- **ENTRY SWEET ZONE:** 23.6% - 38.2% arası (Direnç yakını)
- AI karar ver: Volume, OB, FVG'ye göre en ideal entry noktasını 23.6-38.2 arasından seç
- TP: Extensions 1.272, 1.618 (Destek altı)

🟢 LONG BIAS (Normal Fibo):
- 0% = PDC LOW (Destek) → Entry buraya yakın olmalı
- 100% = PDC HIGH (Direnç) → TP buraya doğru
- **ENTRY SWEET ZONE:** 61.8% - 78.6% arası (Destek yakını)
- AI karar ver: Volume, OB, FVG'ye göre en ideal entry noktasını 61.8-78.6 arasından seç
- TP: 38.2%, 23.6%, 0% (Direnç'e doğru)

══════════════════════════════════════════
📈 ATR(14) - MULTI TIMEFRAME
══════════════════════════════════════════
- 1G: ${market_data['atr']['1d']:,.2f}
- 4S: ${market_data['atr']['4h']:,.2f}
- 1S: ${market_data['atr']['1h']:,.2f}
- 15D: ${market_data['atr']['15m']:,.2f}
- 5D: ${market_data['atr']['5m']:,.2f}
- 3D: ${market_data['atr']['3m']:,.2f}

**Kadircan Stop (Sabit):** ${market_data['stop_loss']['stop_price']:,.2f}

══════════════════════════════════════════
🎯 FIBONACCI SEVİYELERİ
══════════════════════════════════════════
- 0%: ${market_data['fibonacci']['levels']['0.0']:,.2f}
- 23.6%: ${market_data['fibonacci']['levels']['23.6']:,.2f}
- 38.2%: ${market_data['fibonacci']['levels']['38.2']:,.2f}
- 50%: ${market_data['fibonacci']['levels']['50.0']:,.2f}
- 61.8%: ${market_data['fibonacci']['levels']['61.8']:,.2f}
- 78.6%: ${market_data['fibonacci']['levels']['78.6']:,.2f}
- 100%: ${market_data['fibonacci']['levels']['100.0']:,.2f}
- Ext 1.272: ${market_data['fibonacci']['levels']['1.272']:,.2f}
- Ext 1.618: ${market_data['fibonacci']['levels']['1.618']:,.2f}

══════════════════════════════════════════
📊 VOLUME ANALİZİ
══════════════════════════════════════════
**4S:** {volume_4h['spike_ratio']}x, {volume_4h['trend']}, {volume_4h['strength']}
**1S:** {volume_1h['spike_ratio']}x, {volume_1h['trend']}, {volume_1h['strength']}
**15D:** {volume_15m['spike_ratio']}x, {volume_15m['trend']}, {volume_15m['strength']}
**5D:** {volume_5m['spike_ratio']}x, {volume_5m['trend']}, {volume_5m['strength']}
**3D:** {volume_3m['spike_ratio']}x, {volume_3m['trend']}, {volume_3m['strength']}

══════════════════════════════════════════
🧠 SMART MONEY
══════════════════════════════════════════
**OB (4S):** {json.dumps(market_data['smart_money']['order_blocks']['4h'][:3], indent=2)}
**OB (1S):** {json.dumps(market_data['smart_money']['order_blocks']['1h'][:3], indent=2)}
**FVG (4S):** {json.dumps(market_data['smart_money']['fair_value_gaps']['4h'][:2], indent=2)}
**FVG (1S):** {json.dumps(market_data['smart_money']['fair_value_gaps']['1h'][:2], indent=2)}

══════════════════════════════════════════
🎯 GÖREV - KOMPAKT FORMAT
══════════════════════════════════════════

Aşağıdaki **KOMPAKT FORMAT**ta plan oluştur:

```
📊 T-TARS PLAN - {ticker.replace('/', '')}
{market_data['current_date']} {market_data['current_time']}
---
## 📝 GENEL BİLGİ

Parite: {ticker.replace('/', '')}
Anlık Fiyat: ${market_data['current_price']:,.2f}
Bias: {bias_emoji} {bias_text}

---
## 📍 PDC + FİBO ({"Ters - Kırmızı Mum" if pdc['candle_type'] == 'red' else "Normal - Yeşil Mum"})

PDC: {bias_emoji} {pdc['candle_type'].upper()}
High: ${pdc['high']:,.2f}
Low: ${pdc['low']:,.2f}

KRİTİK SEVİYELER:
- 0%: $XXX ({"Direnç" if pdc['candle_type'] == 'red' else "Destek"})
- {"23.6-38.2" if pdc['candle_type'] == 'red' else "61.8-78.6"}%: $XXX (İdeal entry zone) ✅
- 100%: $XXX ({"Destek" if pdc['candle_type'] == 'red' else "Direnç"})
- Ext 1.272: $XXX (TP1)
- Ext 1.618: $XXX (TP2)

{"Mantık: SHORT → Entry direnç yakını, TP destek altı" if pdc['candle_type'] == 'red' else "Mantık: LONG → Entry destek yakını, TP direnç üstü"}

---
## 📊 ATR(14)

- 15D: $XXX ← Entry TF
- (Diğer TF'ler opsiyonel)

---
## 🛡️ STOP

Tars Stop: $XXX
- Hesaplama: 15D ATR ($XXX) × X.X
- Neden: (Volume/volatilite/sweep riski açıkla)

Kadircan Stop: ${market_data['stop_loss']['stop_price']:,.2f}

Tavsiye: Tars (AI güvenli)

---
## 📊 VOLUME

4S: X.Xx TREND 🔴/🟡/🟢 Seviye
1S: X.Xx TREND 🔴/🟡/🟢 Seviye
15D: X.Xx TREND 🔴/🟡/🟢 Seviye

Özet: (Genel durum - spike var mı, beklemeli mi?)

---
## 🧠 SMART MONEY

Order Blocks:
- $XXX (XS Bearish/Bullish, vol ✅/❌) - Açıklama
- En kritik 2-3 OB

Fair Value Gaps:
- $XXX-$XXX (XS, $XXX gap, vol ✅/❌) - Açıklama
- En kritik 1-2 FVG

Kritik: (Önemli uyarı varsa)

---
## 🎯 15D ENTRY

Fiyat: $XXX (Fibo hangi zone'da)
Volume: 🔴/🟡/🟢 (Durum)
OB Risk: (Varsa yakın OB uyarısı)

ENTRY OPTIONS:
A) Conservative: $XXX-$XXX (Fibo seviyesi)
   → (Ne beklemeli)
   
B) Aggressive: $XXX-$XXX
   → (Risk)

Tavsiye: A/B - (Sebep)

---
## 🎁 TP

TP1: $XXX (Ext X.XXX, R:R 1:X.X)
└─ XX% pozisyon kapat
└─ (Destek durumu)

TP2: $XXX (Ext X.XXX, R:R 1:X.X)
└─ XX% trailing
└─ (Volume desteği)

TP3: $XXX (BE sonrası XX%)

---
## ⚠️ KRİTİK UYARILAR

🔴 (En önemli 2-3 risk faktörü)
✅ (Olumlu faktörler)

---
## ✅ KARAR: 🟡/🟢/🔴 (DURUMU)

YAPILACAK:
1-5. (Adımlar)

YAPILMAYACAK:
❌ (3 yasak)

---
📊 T-TARS AI | Real-Time Data
```

**KRİTİK KURALLAR:**

1. **SHORT Entry:** 23.6-38.2% arası sweet zone belirle (direnç yakını)
2. **LONG Entry:** 61.8-78.6% arası sweet zone belirle (destek yakını)
3. **Tars Stop:** AI karar ver (TF, ATR, multiplier, sebep)
4. **Volume:** Her analiz volume ile değerlendir
5. **Kompakt:** Max 120 satır, 1 Telegram mesajı
6. **Emoji:** 🔴🟢🟡 kullan
7. **Gerçek fiyat:** İcat etme!

Sadece yukarıdaki formatı doldur, ekstra açıklama yapma!
"""
        
        result = claude.analyze(prompt)
        
        message = f"📊 *T-TARS PLAN - {ticker.replace('/', '')}*\n\n{result['text']}"
        
        if len(message) > 4000:
            telegram.send(message[:4000] + "...", chat_id=chat_id)
            telegram.send("...(devam)\n" + message[4000:8000], chat_id=chat_id)
            if len(message) > 8000:
                telegram.send("...(devam)\n" + message[8000:], chat_id=chat_id)
        else:
            telegram.send(message, chat_id=chat_id)
        
        logger.info(f"✅ Plan sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Plan command error: {e}")
        
        error_msg = str(e).lower()
        if 'rate' in error_msg or 'limit' in error_msg:
            telegram.send(f"❌ **Rate Limit:** Çok fazla istek. 1 dakika bekle ve tekrar dene.", chat_id=chat_id)
        elif 'network' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
            telegram.send(f"❌ **Network Hatası:** Bağlantı sorunu. Tekrar dene.", chat_id=chat_id)
        elif 'token' in error_msg or 'api' in error_msg:
            telegram.send(f"❌ **API Hatası:** Claude veya OKX servisi yanıt vermiyor. Daha sonra tekrar dene.", chat_id=chat_id)
        else:
            telegram.send(f"❌ **Bilinmeyen Hata:** {str(e)[:100]}\n\nTekrar dene veya destek için bildir.", chat_id=chat_id)

def handle_execute_command(text, chat_id):
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
            telegram.send(message[:4000] + "...", chat_id=chat_id)
            telegram.send("...(devam)\n" + message[4000:], chat_id=chat_id)
        else:
            telegram.send(message, chat_id=chat_id)
        
        logger.info(f"✅ Execute sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Execute command error: {e}")
        telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)

def handle_log_command(text, chat_id):
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
            telegram.send(message[:4000] + "...", chat_id=chat_id)
            telegram.send("...(devam)\n" + message[4000:], chat_id=chat_id)
        else:
            telegram.send(message, chat_id=chat_id)
        
        logger.info(f"✅ Log sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Log command error: {e}")
        telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)

def handle_status_command(chat_id):
    """Bot durum kontrolü"""
    try:
        from datetime import datetime
        import time
        
        check_start = time.time()
        
        services_status = {
            'telegram': '⏳',
            'okx': '⏳',
            'claude': '⏳',
            'storage': '⏳'
        }
        
        try:
            telegram.send("🔄 Kontrol yapılıyor...", chat_id=chat_id)
            services_status['telegram'] = '✅'
        except:
            services_status['telegram'] = '❌'
        
        try:
            test_price = okx.get_current_price('BTC/USDT:USDT')
            services_status['okx'] = f'✅ (${test_price:,.2f})'
        except Exception as e:
            services_status['okx'] = f'❌ ({str(e)[:20]})'
        
        try:
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
        
        try:
            test_template = storage.get_plan_template()
            services_status['storage'] = '✅'
        except Exception as e:
            services_status['storage'] = f'❌ ({str(e)[:20]})'
        
        check_time = (time.time() - check_start) * 1000
        
        status_message = f"""
🤖 **T-TARS BOT DURUM KONTROLÜ**

⏰ **Zaman:** {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
⚡ **Response Time:** {check_time:.0f}ms

---

📡 **SERVİSLER:**

• Telegram: {services_status['telegram']}
• OKX Market: {services_status['okx']}
• Claude AI: {services_status['claude']}
• Cloud Storage: {services_status['storage']}

---

📊 **SİSTEM BİLGİLERİ:**

• Bot Version: v{Config.VERSION}
• Model: {Config.CLAUDE_MODEL}
• Environment: Google Cloud Run
• Region: us-central1

---

✅ **BOT AKTİF VE HAZIR!**

Komutlar için: /help
"""
        
        telegram.send(status_message, chat_id=chat_id)
        logger.info(f"✅ Check command completed in {check_time:.0f}ms")
        
    except Exception as e:
        logger.error(f"❌ Check command error: {e}")
        telegram.send(f"❌ Kontrol hatası: {str(e)}", chat_id=chat_id)

def handle_scan_command(chat_id):
    """
    /scan - Manuel market taraması (v1.4.3: multi-timeframe + aktif setup listesi)
    """
    try:
        pair_names = ' + '.join([p.split('/')[0] + 'USDT' for p in Config.AUTO_SCAN_PAIRS])
        telegram.send(f"🔍 **Market taraması başlatılıyor...**\n\n⏳ {pair_names} tüm timeframe'lerde analiz ediliyor...", chat_id=chat_id)
        
        pairs = Config.AUTO_SCAN_PAIRS
        results = []
        total_new_setups = 0
        
        for pair in pairs:
            try:
                market_data = okx.get_complete_analysis_data(pair)
                setups = detect_all_trading_setups(pair, market_data)  # v1.4.5: from setup_detector
                
                if setups:
                    # HER SETUP İÇİN AYRI MESAJ GÖNDER
                    for setup in setups:
                        setup_type = setup['type']
                        confidence = setup['confidence']
                        entry_zone = setup.get('entry_zone', 'N/A')
                        stop_loss = setup.get('stop_loss', 'N/A')
                        tp1 = setup.get('tp1', 'N/A')
                        tp2 = setup.get('tp2', 'N/A')
                        detailed_explanation = setup.get('detailed_explanation', setup.get('details', ''))
                        timeframe = setup.get('timeframe', '5m')
                        
                        # TRACKING KAYDI EKLE
                        try:
                            setup_id = tracking.log_setup({
                                'pair': pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT'),
                                'timestamp': f"{market_data['current_date']} {market_data['current_time']}",
                                'setup_type': setup_type,
                                'confidence': confidence,
                                'entry_zone': entry_zone,
                                'stop_loss': stop_loss,
                                'tp1': tp1,
                                'tp2': tp2,
                                'current_price': setup.get('current_price', market_data['current_price']),
                                'stop_price': setup.get('stop_price', 0),
                                'tp1_price': setup.get('tp1_price', 0),
                                'tp2_price': setup.get('tp2_price', 0),
                                'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                'ob_strength': setup.get('ob_strength', 'medium'),
                                'rr_ratio': setup.get('rr_ratio', 0),
                                'balance_before': 1000.00,
                                'risk_percent': 2.0
                            })
                            logger.info(f"✅ Setup #{setup_id} logged and tracked")
                        except Exception as track_error:
                            logger.error(f"❌ Tracking failed: {track_error}")
                        
                        message = f"""```
🚨 SETUP DETECTED!

📊 Parite: {pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')}
🎯 Setup: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
{"🔴 Bias: SHORT" if 'SHORT' in setup_type else "🟢 Bias: LONG"}
⚡ Confidence: {confidence}

💰 Mevcut Fiyat: ${market_data['current_price']:,.2f}
🎯 Entry Zone: {entry_zone}
🛡️ Stop Loss: {stop_loss}
🎁 TP1 (Tars TP): {tp1}
🎁 TP2 (Kadircan TP): {tp2}
📅 Time: {market_data['current_time']}
```

---
**📊 Detaylar:**

{detailed_explanation}

---
🤖 **AI Genel Düşünceler:**

_"Bu setup, güçlü OB reaction + volume spike kombinasyonuna dayanıyor. Stop tight ama realistic, TP mantıklı seviyede. Entry zone'da patience kritik - aggressive giriş riskli. R:R oranı solid setup sunuyor."_
"""
                        telegram.send_signal(message)
                        total_new_setups += 1
                    
                    results.append(f"✅ {pair.replace('/USDT:USDT', 'USDT')}: {len(setups)} setup(s) found")
                else:
                    results.append(f"ℹ️ {pair.replace('/USDT:USDT', 'USDT')}: No setup")
                    
            except Exception as e:
                logger.error(f"Error scanning {pair}: {e}")
                results.append(f"❌ {pair.replace('/USDT:USDT', 'USDT')}: Error")
        
        # TARAMA SONUÇLARI + AKTİF SETUP LİSTESİ (v1.4.3)
        try:
            pending_setups = tracking.get_all_pending_setups()
            
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "📊 **Yeni Setup'lar:**\n"
            summary += "\n".join(results)
            summary += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup bulundu"
            
            if pending_setups and len(pending_setups) > 0:
                summary += f"\n\n---\n📊 **AKTİF SETUP'LAR:** {len(pending_setups)} adet\n"
                for setup in pending_setups[:10]:  # Max 10 göster
                    setup_id = setup['id'][:8].upper()
                    pair = setup['pair']
                    setup_type = setup['setup_type']
                    status = setup['status']
                    status_emoji = '🎯' if status == 'TP1' else '⏳'
                    summary += f"\n{status_emoji} #{setup_id} - {pair} - {setup_type} ({status})"
                
                if len(pending_setups) > 10:
                    summary += f"\n... ve {len(pending_setups) - 10} setup daha"
            else:
                summary += "\n\nℹ️ Aktif setup yok"
            
            summary += f"\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}"
            telegram.send(summary, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"❌ Error fetching active setups: {e}")
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "\n".join(results)
            summary += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup bulundu"
            summary += f"\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}"
            telegram.send(summary, chat_id=chat_id)
        
        logger.info(f"✅ Manual scan completed: {len(pairs)} pairs, {total_new_setups} new setups")
        
    except Exception as e:
        logger.error(f"❌ Scan command error: {e}")
        
        error_msg = str(e).lower()
        if 'rate' in error_msg or 'limit' in error_msg:
            telegram.send(f"❌ **Rate Limit:** Çok fazla tarama. 1 dakika bekle.", chat_id=chat_id)
        elif 'network' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
            telegram.send(f"❌ **Network Hatası:** OKX bağlantı sorunu. Tekrar dene.", chat_id=chat_id)
        else:
            telegram.send(f"❌ **Tarama Hatası:** {str(e)[:100]}", chat_id=chat_id)


def handle_score_command(chat_id):
    """
    /score - Performance raporu (v1.4.3: avg duration eklendi)
    """
    try:
        telegram.send("📊 İstatistikler hesaplanıyor...", chat_id=chat_id)
        
        # Aggregate stats
        stats = tracking.get_aggregate_stats()
        
        # Duration formatı (v1.4.3)
        avg_duration = stats.get('avg_duration_minutes', 0)
        if avg_duration > 0:
            duration_text = f"⏱️ Avg Duration: {avg_duration:.1f} minutes\n"
        else:
            duration_text = ""
        
        score_message = f"""
📊 **T-TARS PERFORMANCE REPORT**

🎯 **Setup İstatistikleri:**
• Total Setups: {stats['total_setups']}
• Winning Trades: {stats['winning_trades']} ({stats['win_rate']:.1f}%)
• Losing Trades: {stats['losing_trades']}

💰 **Balance Tracking:**
• Starting: ${stats['starting_balance']:,.2f}
• Current: ${stats['current_balance']:,.2f}
• Profit: {'+ ' if stats['profit'] >= 0 else ''}{stats['profit_percent']:.1f}% (${stats['profit']:,.2f})

{duration_text}📈 **Best Performer:**
{stats['best_setup_type']}

---
⏱️ Last Updated: {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        telegram.send(score_message, chat_id=chat_id)
        logger.info(f"✅ Score command sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Score command error: {e}")
        telegram.send(f"❌ İstatistik hatası: {str(e)}", chat_id=chat_id)

def handle_help_command(chat_id):
    """Yardım mesajı"""
    
    try:
        version_features = storage.parse_version_features(Config.VERSION)
        if version_features:
            features_text = "\n".join(version_features)
        else:
            features_text = """✅ Balance hesabı düzeltmesi
✅ Win rate fix (TP1 ≠ WIN)
✅ Time tracking (duration)
✅ Movement tracking ($)
✅ Emoji sistem (TP1/TP2/STOP)"""
    except Exception as e:
        logger.warning(f"⚠️ Could not load changelog features: {e}")
        features_text = """✅ Balance & Win Rate Fix
✅ Time & Movement Tracking
✅ Enhanced Emojis"""
    
    help_text = f"""
🤖 *T-TARS Trading Bot v{Config.VERSION}*

📊 `/plan` - BTCUSDT için tam analiz
   • Gerçek OKX data
   • Volume analizi
   • OB/FVG/Sweep detection
   • Multi-timeframe ATR (3m + 5m)
   • Dinamik Fibonacci

📊 `/plan ETHUSDT` - Farklı parite

🔍 `/scan` - Manuel market taraması (BTC + SOL)
📊 `/score` - Performance raporu

⚡ `/execute` - Aktif durum
📋 `/log` - İşlem özeti
📡 `/status` - Bot durum kontrolü
❓ `/help` - Bu mesaj

🆕 *v{Config.VERSION} Yenilikler:*
{features_text}
"""
    telegram.send(help_text, chat_id=chat_id)

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

⏰ {get_turkey_time().strftime('%H:%M:%S')}
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
        telegram.send(f"🧪 *T-TARS v{Config.VERSION} Test*\n\n✅ Sistem çalışıyor!\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# ROUTES - MONITORING & AUTO-ANALYZE
# ============================================
# v1.4.5: detect_trading_setup ve detect_all_trading_setups
# artık app.strategies.setup_detector'dan import ediliyor

@app.route('/monitor', methods=['POST', 'GET'])
def monitor_setups():
    """
    Cloud Scheduler tarafından her 5 dakikada tetiklenen otomatik setup monitoring
    v1.4.3: Enhanced emojis, duration, movement tracking
    """
    try:
        logger.info("🔍 Monitor: Checking pending setups...")
        
        pending_setups = tracking.get_all_pending_setups()
        
        if not pending_setups or len(pending_setups) == 0:
            logger.info("ℹ️ No pending setups to monitor")
            return jsonify({
                "status": "success",
                "timestamp": get_turkey_time().isoformat(),
                "pending_setups": 0,
                "updates": []
            })
        
        logger.info(f"📊 Found {len(pending_setups)} pending setup(s)")
        updates = []
        
        for setup in pending_setups:
            try:
                setup_id = setup['id']
                pair = setup['pair']
                setup_type = setup['setup_type']
                
                if '/' not in pair:
                    okx_pair = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}"
                else:
                    okx_pair = pair
                
                current_price = okx.get_current_price(okx_pair)
                logger.info(f"💰 {pair}: Current price ${current_price:,.2f}")
                
                status_result = tracking.check_setup_status(setup_id, current_price)
                
                if status_result and status_result.get('status_changed'):
                    new_status = status_result['new_status']
                    old_status = status_result['old_status']
                    setup_data = status_result.get('setup', {})
                    
                    # v1.4.3: Enhanced data
                    profit = setup_data.get('profit_loss', 0)
                    balance_before = setup_data.get('balance_before', 1000)
                    balance_after = setup_data.get('balance_after', balance_before)
                    profit_percent = (profit / balance_before * 100) if balance_before > 0 else 0
                    duration = setup_data.get('duration_minutes', 0)
                    movement = setup_data.get('movement_captured_dollars', 0)
                    
                    stats = tracking.get_aggregate_stats()
                    
                    # v1.4.3: Emoji mapping
                    if new_status == 'TP1':
                        emoji = '🎯'
                        status_text = 'TP1 HIT!'
                        status_emoji = '✅'
                        next_action = '📊 Status: Breakeven, TP2 bekliyor'
                    elif new_status == 'COMPLETED':
                        emoji = '🎉'
                        status_text = 'TP2 HIT - FULL WIN!'
                        status_emoji = '🏆'
                        next_action = '✅ Setup tamamlandı!'
                    elif new_status == 'STOPPED':
                        emoji = '⛔'
                        status_text = 'STOP HIT'
                        status_emoji = '❌'
                        next_action = '❌ Setup kapatıldı'
                    else:
                        emoji = '📊'
                        status_text = 'Status Updated'
                        status_emoji = 'ℹ️'
                        next_action = ''
                    
                    # Duration text (v1.4.3)
                    if duration > 0:
                        duration_text = f"⏱️ Duration: {duration:.1f} minutes\n"
                    else:
                        duration_text = ""
                    
                    # Movement text (v1.4.3)
                    if movement > 0:
                        movement_text = f"📊 Movement: ${movement:.2f} captured\n"
                    else:
                        movement_text = ""
                    
                    broadcast_message = f"""
{emoji} **SETUP #{setup_id[:8].upper()} → {status_text}**

📊 **Parite:** {pair}
🎯 **Setup Type:** {setup_type}
{status_emoji} **Entry:** ${setup['current_price']:,.2f} → **{new_status}:** ${current_price:,.2f}
💰 **Profit:** {'+' if profit >= 0 else ''}{profit_percent:+.2f}% (${profit:+,.2f})
{movement_text}{duration_text}{next_action}

---
📈 **Current Stats:**
• Total Setups: {stats['total_setups']}
• Win Rate: {stats['win_rate']:.1f}%
• Current Balance: ${stats['current_balance']:,.2f} ({stats['profit_percent']:+.1f}%)

⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
                    
                    telegram.send_signal(broadcast_message)
                    
                    updates.append({
                        'setup_id': setup_id,
                        'pair': pair,
                        'old_status': old_status,
                        'new_status': new_status,
                        'profit': profit,
                        'profit_percent': profit_percent,
                        'duration_minutes': duration,
                        'movement_dollars': movement
                    })
                    
                    logger.info(f"✅ {pair} #{setup_id[:8]}: {old_status} → {new_status} (Profit: {profit_percent:+.2f}%, Duration: {duration:.1f}m)")
                
            except Exception as e:
                logger.error(f"❌ Error monitoring setup {setup.get('id', 'unknown')}: {e}")
                updates.append({
                    'setup_id': setup.get('id', 'unknown'),
                    'error': str(e)
                })
        
        logger.info(f"✅ Monitor completed: {len(updates)} update(s)")
        
        return jsonify({
            "status": "success",
            "timestamp": get_turkey_time().isoformat(),
            "pending_setups": len(pending_setups),
            "updates": updates
        })
        
    except Exception as e:
        logger.error(f"❌ Monitor error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """Cloud Scheduler tarafından her 3 dakikada tetiklenen otomatik analiz (v1.4.3: multi-timeframe)"""
    try:
        pairs = ['BTC/USDT:USDT', 'SOL/USDT:USDT']
        results = []
        total_setups = 0
        
        for pair in pairs:
            try:
                market_data = okx.get_complete_analysis_data(pair)
                setups = detect_all_trading_setups(pair, market_data)  # v1.4.5: from setup_detector
                
                if setups:
                    # HER SETUP İÇİN AYRI MESAJ
                    for setup in setups:
                        entry_zone = setup.get('entry_zone', 'N/A')
                        stop_loss = setup.get('stop_loss', 'N/A')
                        tp1 = setup.get('tp1', 'N/A')
                        tp2 = setup.get('tp2', 'N/A')
                        detailed_explanation = setup.get('detailed_explanation', setup.get('details', ''))
                        timeframe = setup.get('timeframe', '5m')
                        
                        # TRACKING KAYDI EKLE
                        try:
                            setup_id = tracking.log_setup({
                                'pair': pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT'),
                                'timestamp': f"{market_data['current_date']} {market_data['current_time']}",
                                'setup_type': setup['type'],
                                'confidence': setup['confidence'],
                                'entry_zone': entry_zone,
                                'stop_loss': stop_loss,
                                'tp1': tp1,
                                'tp2': tp2,
                                'current_price': setup.get('current_price', market_data['current_price']),
                                'stop_price': setup.get('stop_price', 0),
                                'tp1_price': setup.get('tp1_price', 0),
                                'tp2_price': setup.get('tp2_price', 0),
                                'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                'ob_strength': setup.get('ob_strength', 'medium'),
                                'rr_ratio': setup.get('rr_ratio', 0),
                                'balance_before': 1000.00,
                                'risk_percent': 2.0
                            })
                            logger.info(f"✅ Setup #{setup_id} logged and tracked")
                        except Exception as track_error:
                            logger.error(f"❌ Tracking failed: {track_error}")
                        
                        message = f"""```
🚨 SETUP DETECTED!

📊 Parite: {pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')}
🎯 Setup: {setup['type']}
⏱️ Timeframe: {timeframe.upper()}
{"🔴 Bias: SHORT" if 'SHORT' in setup['type'] else "🟢 Bias: LONG"}
⚡ Confidence: {setup['confidence']}

💰 Mevcut Fiyat: ${market_data['current_price']:,.2f}
🎯 Entry Zone: {entry_zone}
🛡️ Stop Loss: {stop_loss}
🎁 TP1 (Tars TP): {tp1}
🎁 TP2 (Kadircan TP): {tp2}
📅 Time: {market_data['current_time']}
```

---
**📊 Detaylar:**

{detailed_explanation}

---
🤖 **AI Genel Düşünceler:**

_"Bu setup, güçlü OB reaction + volume spike kombinasyonuna dayanıyor. Stop tight ama realistic, TP mantıklı seviyede. Entry zone'da patience kritik - aggressive giriş riskli. R:R oranı solid setup sunuyor."_
"""
                        telegram.send_signal(message)
                        total_setups += 1
                    
                    results.append(f"{pair}: {len(setups)} setup(s) found")
                else:
                    results.append(f"{pair}: No setup")
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
                results.append(f"{pair}: Error")
        
        logger.info(f"✅ Auto analyze completed: {total_setups} total setups found")
        return jsonify({"status": "success", "timestamp": get_turkey_time().isoformat(), "results": results, "total_setups": total_setups})
    except Exception as e:
        logger.error(f"Auto analyze error: {e}")
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS Trading Bot v{Config.VERSION} on port {Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)
