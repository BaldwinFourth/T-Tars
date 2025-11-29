# T-TARS CHANGELOG

Automated Trading Bot - TradingView + Claude AI + OKX + Telegram
Google Cloud Run Deployment

---

## v1.4.9.4 (2025-11-29)

### ATR Precision Fix - Dusuk Fiyatli Coinler

**Sorun Tespiti:**
- DOGE fiyati $0.15, ATR degeri ~0.003
- SHIB fiyati $0.00002, ATR degeri ~0.0000002
- round(atr, 2) fonksiyonu bu degerleri 0.00 yapiyordu
- R:R hesaplamasinda division by zero veya 0.0 sonuc

**Log Ornegi:**
```
OB SHORT R:R: 0.00 (entry=$0.1493)
OB SHORT rejected: R:R 0.0 < 2.0
```

**Cozum:**
- okx_service.py: calculate_atr() fonksiyonunda round(atr, 2) yerine round(atr, 8)
- Fibonacci levels: round(v, 8) ile 8 ondalik hassasiyet
- calculate_stop_loss: round(price, 8)

**Etkilenen Dosyalar:**
- app/services/okx_service.py

---

### R:R Multiplier Fix

**Sorun Tespiti:**
- STOP_MULTIPLIER = 1.5 (Stop = Entry - ATR x 1.5)
- TP1_MULTIPLIER = 2.0 (TP1 = Entry + ATR x 2.0)
- R:R = TP1 / STOP = 2.0 / 1.5 = 1.33
- MIN_RR_RATIO = 2.0
- 1.33 < 2.0 oldugundan TUM SETUPLAR REJECT ediliyordu!

**Cozum:**
- TP1_MULTIPLIER: 2.0 -> 3.0 (R:R = 3.0/1.5 = 2.0)
- TP2_MULTIPLIER: 3.5 -> 4.5 (R:R = 4.5/1.5 = 3.0)

**Yeni Degerler:**
| Multiplier | Eski | Yeni | R:R |
|------------|------|------|-----|
| STOP | 1.5 | 1.5 | - |
| TP1 | 2.0 | 3.0 | 2.0 |
| TP2 | 3.5 | 4.5 | 3.0 |

**Etkilenen Dosyalar:**
- app/strategies/calculators.py

---

## v1.4.9.3 (2025-11-29)

### format_price() Dinamik Fiyat Formatlama

**Sorun:**
- SHIB fiyati $0.00002345
- Python f-string ${price:,.2f} ile $0.00 gosteriliyordu
- Telegram mesajlarinda fiyatlar okunamiyor

**Cozum - format_price() fonksiyonu:**
```python
def format_price(price):
    if price < 0.0001:
        return f"${price:.8f}"   # SHIB: $0.00002345
    elif price < 0.01:
        return f"${price:.6f}"   # $0.004567
    elif price < 1:
        return f"${price:.4f}"   # DOGE: $0.4000
    elif price < 100:
        return f"${price:,.4f}"  # SOL: $235.0000
    else:
        return f"${price:,.2f}"  # BTC: $95,000.50
```

**Etkilenen Dosyalar:**
- app/strategies/calculators.py (fonksiyon eklendi)
- app/strategies/ob_detector.py (format_price kullanimi)
- app/strategies/fvg_detector.py (format_price kullanimi)

---

### Telegram /help Fix

**Sorun:**
- /help komutu 400 Bad Request hatasi veriyordu
- /status komutu calisiyordu

**Neden:**
- storage_service.parse_version_features() CHANGELOG.md den veri cekiyordu
- CHANGELOG icindeki ozel karakterler (**, ->, $, <) Telegram Markdown bozuyordu

**Cozum:**
- CHANGELOG parse tamamen kaldirildi
- Statik help mesaji kullaniliyor

**Etkilenen Dosyalar:**
- app/handlers/telegram_handlers.py

---

## v1.4.9.2 (2025-11-29)

### Telegram UI Iyilestirmeleri

**/scan Mesaji:**
- Onceki: "BTC + ETH + SOL + LTC + BNB + SHIB + DOGE analiz ediliyor..."
- Yeni: Her coin alt alta emoji ile listeleniyor
```
🧪 BTC
🧪 ETH
🧪 SOL
...
```

**/help Mesaji:**
- "(BTC + SOL)" ifadesi kaldirildi
- Daha temiz gorunum

**CHANGELOG Parse:**
- "Label: description" formati destegi eklendi

**Etkilenen Dosyalar:**
- app/handlers/telegram_handlers.py

---

## v1.4.9.1 (2025-11-29)

### Volume Confirmed Field Kullanimi

**Onceki Davranis:**
- Anlik volume spike kontrol ediliyordu
- OB/FVG bulunduktan sonra volume degisebiliyordu

**Yeni Davranis:**
- volume_confirmed field OB/FVG olusumu sirasindaki volume
- Daha tutarli setup tespiti

**Etkilenen Dosyalar:**
- app/strategies/ob_detector.py
- app/strategies/fvg_detector.py

---

## v1.4.9 (2025-11-28)

### Moduler Setup Detector Mimarisi

**Onceki:**
- setup_detector.py: 689 satir, tek dosyada hersey

**Yeni Yapi:**
```
app/strategies/
├── calculators.py      # Tum katsayilar
├── setup_detector.py   # Main coordinator
├── ob_detector.py      # Order Block detection
├── fvg_detector.py     # Fair Value Gap detection
└── volume_analyzer.py  # Volume analysis
```

**Avantajlar:**
- Her modul bagimsiz test edilebilir
- Katsayilar tek dosyada (fine-tuning kolayligi)
- Kod bakimi kolaylasti

**Etkilenen Dosyalar:**
- Yeni: ob_detector.py, fvg_detector.py, volume_analyzer.py
- Guncellenen: setup_detector.py, calculators.py

---

## v1.4.8 (2025-11-28)

### Yeni Coin Destegi

**Onceki AUTO_SCAN_PAIRS:**
- BTC/USDT:USDT
- SOL/USDT:USDT

**Yeni AUTO_SCAN_PAIRS (7 coin):**
- BTC/USDT:USDT
- ETH/USDT:USDT
- SOL/USDT:USDT
- LTC/USDT:USDT
- BNB/USDT:USDT
- SHIB/USDT:USDT
- DOGE/USDT:USDT

**Etkilenen Dosyalar:**
- app/config.py

---

### /reset_score Komutu

**Yeni Gizli Komut:**
- /help mesajinda gorunmuyor
- Tum tracking verilerini sifirliyor
- Balance $1000 a donuyor
- Test amacli kullanim

**Etkilenen Dosyalar:**
- app/handlers/telegram_handlers.py
- app/services/tracking_service.py

---

## v1.4.7 (2025-11-28)

### Entry Price Hesaplama Fix

**Sorun:**
- Entry price yanlis hesaplaniyordu
- R:R ratio yanlis cikiyordu

**Cozum:**
- OB: mid-point = (ob_low + ob_high) / 2
- FVG: mid-point = (gap_low + gap_high) / 2

**Etkilenen Dosyalar:**
- app/strategies/ob_detector.py
- app/strategies/fvg_detector.py

---

## v1.4.6 (2025-11-28)

### FVG Dual TP Sistemi

**Onceki:**
- FVG setuplar icin tek TP

**Yeni:**
- TP1 (Tars TP): Conservative hedef
- TP2 (Kadircan TP): Aggressive hedef
- Her setup icin iki hedef ZORUNLU

**Etkilenen Dosyalar:**
- app/strategies/fvg_detector.py

---

## v1.4.5 (2025-11-26)

### Multi-Timeframe Scan

**Taranan Timeframeler:**
- 4H (4 saat)
- 1H (1 saat)
- 15M (15 dakika)
- 5M (5 dakika)
- 3M (3 dakika)

**Her Timeframe Icin:**
- Ayri OB detection
- Ayri FVG detection
- Ayri volume analysis
- Ayri ATR hesaplama

**Etkilenen Dosyalar:**
- app/strategies/setup_detector.py
- app/services/okx_service.py

---

## v1.4.4 (2025-11-26)

### Calculators Modulu

**Amac:**
- Tum katsayilar tek dosyada
- Fine-tuning icin tek yer
- Kolay deney yapma

**Icerik:**
```python
# ATR Multipliers
STOP_MULTIPLIER = 1.5
TP1_MULTIPLIER = 2.0  # v1.4.9.4 de 3.0 oldu
TP2_MULTIPLIER = 3.5  # v1.4.9.4 de 4.5 oldu

# R:R Thresholds
MIN_RR_RATIO = 2.0

# Volume Thresholds
VOLUME_EXCELLENT = 3.0
VOLUME_GOOD = 2.5
VOLUME_MEDIUM = 2.0
VOLUME_LOW = 1.5
```

**Etkilenen Dosyalar:**
- Yeni: app/strategies/calculators.py

---

## v1.4.3 (2025-11-25)

### Score ve Performance Tracking

**/score Komutu:**
```
📊 T-TARS PERFORMANCE REPORT

🎯 Setup Istatistikleri:
• Total Setups: 15
• Winning Trades: 10 (66.7%)
• Losing Trades: 5

💰 Balance Tracking:
• Starting: $1,000.00
• Current: $1,150.00
• Profit: +15.0% ($150.00)

📈 Best Performer:
OB + Volume Spike (LONG)
```

**Avg Duration:**
- Setup ne kadar surede sonuclandi
- TP1, TP2, STOP hit suresi

**Etkilenen Dosyalar:**
- app/handlers/telegram_handlers.py
- app/services/tracking_service.py

---

## v1.4.2 (2025-11-24)

### Cloud Run Traffic Routing Fix

**Sorun:**
- Deploy sonrasi yeni revision traffic almiyordu
- Eski kod calismaya devam ediyordu

**Neden:**
- gcloud run deploy --to-latest olmadan calisiyordu

**Cozum:**
- deploy.sh ye --to-latest eklendi
- Her deploy otomatik traffic yonlendirme

**Etkilenen Dosyalar:**
- deploy.sh

---

## v1.4.1 (2025-11-23)

### ATR Timeframe Consistency Fix

**v1.4.0 daki Sorun (v4 stable da tespit edildi):**
```python
# YANLIS kod:
stop_distance = atr_5m * 1.5   # 5m ATR
tp = current_price - (atr_15m * 2.5)  # 15m ATR ← TUTARSIZ!
```

**v1.4.1 Cozumu:**
```python
# DOGRU kod:
# Hangi timeframe'de analiz yapiliyorsa O ATR kullan
atr = atr_5m if timeframe == '5m' else atr_3m

stop_distance = atr * 1.5
tp1 = current_price + (atr * 2.0)
tp2 = current_price + (atr * 3.5)
```

**Etki:**
- Stop ve TP mesafeleri tutarli
- R:R hesaplamasi dogru
- ~40% daha tight stop seviyeleri

**Etkilenen Dosyalar:**
- app/main.py (detect_trading_setup fonksiyonu)

---

### Dual TP Sistemi

**Onceki (v1.4.0):**
```python
'take_profit': take_profit  # Tek TP
```

**Yeni (v1.4.1):**
```python
'tp1': tp1,                 # Tars TP (Conservative)
'tp2': tp2,                 # Kadircan TP (Extended)
'tp1_price': tp1_price,     # Tracking icin
'tp2_price': tp2_price
```

**TP Stratejisi:**
- TP1: +2.0 ATR (Quick profit + Breakeven)
- TP2: +3.5 ATR (Extended target)
- R:R hesaplama TP1 e gore

---

### Tracking Entegrasyonu Fix

**v1.4.0 daki Sorun:**
- Setup bulunuyordu ama tracking e kaydedilmiyordu
- /score komutu bos donuyordu

**Log Ornegi (sorunlu):**
```
🚨 SETUP DETECTED!
# Ama tracking e kayit YOK!
```

**v1.4.1 Cozumu:**
```python
if setup_detected:
    # Setup bulunca OTOMATIK tracking kaydi
    try:
        setup_id = tracking.log_setup({
            'pair': pair,
            'timestamp': timestamp,
            'setup_type': setup_type,
            'tp1': tp1,
            'tp2': tp2,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            ...
        })
        logger.info(f"✅ Setup #{setup_id} logged and tracked")
    except Exception as track_error:
        logger.error(f"❌ Tracking failed: {track_error}")
    
    telegram.send_signal(message)
```

**Etkilenen Fonksiyonlar:**
- handle_scan_command()
- auto_analyze()

---

### Debug Logging

**Yeni Log Satiri:**
```python
logger.info(f"📊 LONG R:R: entry=${current_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1:.2f}, tp2=${tp2:.2f}, risk=${risk:.2f}, reward=${reward:.2f}, ratio={rr_ratio:.2f}")
```

**Ornek Log:**
```
📊 LONG R:R: entry=$95000.00, stop=$94500.00, tp1=$96000.00, tp2=$96750.00, risk=$500.00, reward=$1000.00, ratio=2.00
```

---

### Version System Fix

**v1.4.0 Hatasi:**
- Version 7 yerde hard-coded yazilmisti

**v1.4.1 Cozumu:**
- Config.VERSION kullaniliyor
- Tek yerden version kontrolu

**4 Yerde Config.VERSION Kullanimi:**
1. `/` endpoint response
2. `/status` mesaji
3. Startup log
4. `/help` mesaji

---

## v1.4.0 (2025-11-22)

### Major Restructure - Moduler Mimari

**Onceki Yapi:**
```
main.py (1200+ satir, hersey icinde)
```

**Yeni Yapi:**
```
app/
├── __init__.py
├── main.py (Flask routes)
├── config.py (Merkezi konfigurasyon)
├── services/
│   ├── claude_service.py
│   ├── okx_service.py
│   ├── telegram_service.py
│   ├── storage_service.py
│   └── tracking_service.py
└── handlers/
    └── telegram_handlers.py
```

**Dockerfile Degisikligi:**
```dockerfile
CMD ["gunicorn", "app.main:app", ...]
```

---

### Setup Tracking Sistemi

**Yeni Ozellikler:**
- tracking_service.py ile setup kaydi
- Google Cloud Storage da JSON data
- TP1/TP2/STOP monitoring
- Broadcast alerts (hedef vurulunca)

**Setup Durumlari:**
- PENDING: Aktif, izleniyor
- TP1: Ilk hedef vuruldu
- TP2: Ikinci hedef vuruldu
- STOPPED: Stop vuruldu

---

### UTF-8 Encoding Fix (v4 stable)

**Sorun Tespiti:**
- telegram_service.py ve storage_service.py UTF-8 encoding yoktu
- Emoji ve Turkce karakterler bozuluyordu
- Telegram mesajlarinda "ðŸ¤–" yerine "🤖" gosteriliyordu

**Cozum:**
- Tum dosyalara `# -*- coding: utf-8 -*-` eklendi
- telegram_service.py: Content-Type header UTF-8
- storage_service.py: blob.download_as_text(encoding='utf-8')
- okx_service.py: Turkey timezone (UTC+3)

**Etkilenen 8 Dosya:**
1. main_v1.4.0.py - UTF-8 header
2. config_v1.4.0.py - UTF-8 header
3. tracking_service_v1.4.0.py - UTF-8 header
4. okx_service_v1.4.0.py - UTF-8 + Turkey TZ
5. telegram_service_v1.4.0.py - UTF-8 + Content-Type header
6. storage_service_v1.4.0.py - UTF-8 encoding tum blob download
7. VERSION
8. CHANGELOG_v1.4.0.md

---

### R:R Hesaplama Sorunu (v4 stable debug)

**Tespit Edilen Sorun:**
```python
# YANLIS:
stop_distance = atr_5m * 1.5   # 5m ATR
tp = current_price - (atr_15m * 2.5)  # 15m ATR ← FARKLI!
```

**Log Ornegi:**
```
SHORT setup rejected: R:R 0.4 < 2.0
```

**Analiz:**
- Entry: $124 (current price)
- Stop: $140.97 (OB high + 1.5 ATR)
- TP: $121 (current - 2.5 ATR)
- Risk: $16.97
- Reward: $3
- R:R = 0.18 (cok kotu!)

**Sorun Nedeni:**
- Stop icin 5m ATR kullaniliyor (kucuk)
- TP icin 15m ATR kullaniliyor (buyuk)
- Bu tutarsizlik R:R yi bozuyor

**Cozum v1.4.1 de uygulanacak**

---

## v1.3.2 (2025-11-20)

### Cleanup ve Iyilestirmeler

- Webhook URL kaldirildi (guvenlik)
- /check komutu kaldirildi (sadece /status)
- Default balance: $2000 -> $1000
- Risk: AI-based calculation (%1-2 arasi)
- Error handling iyilestirildi

---

## v1.3.1 (2025-11-20)

### Help Komutu Markdown Fix

- Telegram markdown parse hatalari duzeltildi

---

## v1.3.0 (2025-11-19)

### Yeni Pariteler ve Sinyal Formati

- 20+ yeni parite destegi
- Yeni sinyal formati

---

## v1.2.9 (2025-11-18)

### CHANGELOG Entegrasyonu

- /help komutu Cloud Storage dan feature listesi cekiyor
- Manuel guncelleme gerekmiyor

---

## v1.2.8 (2025-11-18)

### Multi-Chat Support

- Kisisel chat: 844960218
- Grup chat: -1003414684807 (T-Tars Watcher)
- Command-only mode (grupta sadece / komutlarina cevap)

---

## v1.2.7 (2025-11-18)

### Turkey Timezone

- UTC+3 timezone destegi
- Tum timestamp lar Turkiye saati

---

## v1.2.6 (2025-11-18)

### Compact Format

- /plan mesaji 356 satirdan ~120 satira dusuruldu
- Tek Telegram mesajinda tum bilgi

---

## v1.2.5 (2025-11-18)

### SHORT Bias Fibonacci Fix

**Sorun:**
- SHORT icin 61.8-78.6% kullaniliyordu (LONG logic)

**Cozum:**
- SHORT: 23.6-38.2% (direnc yakini)
- LONG: 61.8-78.6% (destek yakini)

---

## v1.2.4 (2025-11-18)

### R:R Filter

- Minimum R:R 1:2 zorunlu
- Dusuk R:R setuplar reject

---

## v1.2.0 - v1.2.3 (2025-11-17)

### Volume-Aware Analiz

- Volume spike detection
- Order Block + Volume confirmation
- FVG + Volume confirmation

---

## v1.1.x (2025-11-16)

### Smart Money Detection

- Order Block detection (Bullish/Bearish)
- Fair Value Gap detection
- Liquidity Sweep detection

---

## v1.0.0 (2025-11-15)

### Initial Release

- TradingView webhook entegrasyonu
- Claude AI analiz (Haiku + Extended Thinking)
- OKX Perpetual Futures data
- Telegram bot komutlari: /plan, /execute, /log, /status, /help
- PDC (Previous Day Candle) bazli Fibonacci
- ATR(14) hesaplama
- Google Cloud Run deployment

---

## Teknik Stack

- **Backend:** Python Flask
- **AI:** Claude Haiku 4.5 (Extended Thinking 20K)
- **Exchange:** OKX Perpetual Futures (USDT-M)
- **Messaging:** Telegram Bot API
- **Storage:** Google Cloud Storage
- **Hosting:** Google Cloud Run
- **Scheduler:** Google Cloud Scheduler

---

## ENV Variables

```
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xx
TELEGRAM_BETA_GROUP_ID=-xx
ANTHROPIC_API_KEY=sk-ant-xxx
CLAUDE_MODEL=claude-haiku-4-5-20251001
BUCKET_NAME=tars-trading-templates
BUCKET_NAME_DATA=tars-trading-data
```

---



