# T-TARS Trading Bot - CHANGELOG

## v2.4.5 (2025-12-25)

### Removed
- **30m Timeframe**: Auto analyze ve global scanning işlemlerinden `30m` timeframe kaldırıldı. Sadece `1h` ve `15m` için çalışıyor.
- `config.py` updated to reflect `TIMEFRAMES = ['1h', '15m']`.

### Fixed
- **CRITICAL: status PENDING bug**: Order açıldığında status FILLED olarak kaydedilmiyordu, monitor bu yüzden kapanan pozisyonları görmüyordu

---

## v2.4.4 (2025-12-24)

### New
- **Pozisyon Kapanış Bildirimi**: Pozisyon kapandığında Telegram mesajı
- **WIN/LOSS Otomatik Belirleme**: Bitget API'den PnL çekilerek sonuç belirleniyor
- **PnL Takibi**: `get_closed_position_pnl()` fonksiyonu eklendi

### Improved
- **REPLACE mesaj formatı**: Emir güncellendiğinde farklı Telegram mesajı
  - YENİ EMİR → `🟢 YENİ EMİR AÇILDI`
  - REPLACE → `🔄 EMİR GÜNCELLENDİ`
- **Detaylı bilgi**: Eski Order ID ve güncelleme sebebi mesajda gösteriliyor
- **/help kısaltıldı**: Sadece güncel versiyon changelog gösteriliyor

### Fixed
- **/scan market_cache**: `/scan` komutu artık TradingView volume verisini kullanıyor
- **/plan market_cache**: `/plan` komutu da cache'den volume alıyor
- **/status cache info**: Cache entry sayısı gösteriliyor
- **/score WIN/LOSS**: Artık doğru hesaplanıyor (PnL'den)

### Technical
- `bitget_service.py`: `get_order_history_track()`, `get_closed_position_pnl()` eklendi
- `main.py` monitor: PnL çekme + WIN/LOSS + Telegram mesajı
- `telegram_handlers.py`: market_cache + /help kısaltma

---

## v2.4.3 (2025-12-22)

### FIXED
- **Duplicate Order Sorunu Cozuldu:** REPLACE handling duzeltildi
  - Eski order cancel ediliyor
  - Eski setup EXPIRED olarak isaretleniyor
  - Yeni order aciliyor
- **TP/SL Preset Fix:** Bitget API doc'a gore parametreler duzeltildi
  - `stopSurplus/stopLoss` → `presetStopSurplusPrice/presetStopLossPrice`
  - Artik TP ve SL order'a ekleniyor

### CHANGED
- `UPDATE_NEEDED` → `REPLACE` (daha net isimlendirme)
- Mantik: Ayni coin+direction icin farkli fiyatli order varsa → eski cancel + yeni ac

### FILES CHANGED
- `main.py` - REPLACE handling eklendi
- `bitget_service.py` - TP/SL preset format duzeltildi
- `tracking_service.py` - UPDATE_NEEDED → REPLACE

---

## v2.4.2 (2025-12-22)

### FIXED
- **Hedge Mode Order Fix:** Bitget API dokümantasyonuna göre params düzeltildi
- `holdSide` kaldırıldı (native API'de yok)
- `tradeSide='open'` eklendi (pozisyon açmak için)
- `tradeSide='close'` (pozisyon kapatmak için)
- **40774 Hatası Çözüldü:** "unilateral position" hatası

### CHANGED
- Hedge mode parametreleri: side=buy/sell (yön), tradeSide=open/close (işlem tipi)

### FILES CHANGED
- `bitget_service.py` - Order params düzeltildi

---

## v2.4.1 (2025-12-22)

### ADDED
- **Detayli Log'lar:** Fibo zone reject, Bias mismatch, PDC is_doji
- **Fibo Zone Reject:** Her reject'te fibo % gosteriliyor
- **Bias Mismatch:** OB/FVG type ile bias uyumsuzlugu loglanıyor
- **PDC Doji:** Doji uyarısında PDC_is_Doji bilgisi eklendi

### CHANGED
- setup_detector.py: Fibo filtreleme detaylı log ile

### FILES CHANGED
- `setup_detector.py` - Detaylı log'lar eklendi

---

## v2.4.0 (2024-12-22)

### 🚀 MAJOR: Strateji Yeniden Yapılandırma

#### PDC + Bias Belirleme (YENİ)
- PDC (Previous Day Candle) bazlı bias: Yeşil = LONG, Kırmızı = SHORT
- Doji kontrolü: Son 4 daily mumda doji varsa reversal mode aktif
- PDC kendisi doji ise: Önceki mumun tersi yönde işlem

#### Fibonacci Zone Filtreleme (YENİ)
- OB arama bölgesi: %70-90 arası (PDC'ye göre)
- FVG arama bölgesi: %60-90 arası (PDC'ye göre)
- Zone dışındaki OB/FVG'ler filtreleniyor

#### OB/FVG Noise Reduction (YENİ)
- Minimum boyut filtresi: OB ≥ 1.0 ATR, FVG ≥ 1.0 ATR
- En yakın 4: Fiyata en yakın 4 OB/FVG döndürülüyor (eskiden 5)

### 🔧 API FIX
- **Copy Trade API düzeltildi**: Yanlış endpoint (`order-open-position`) yerine normal CCXT `create_order` kullanılıyor
- **trackingNo**: Order sonrası `find_tracking_no_by_symbol` ile alınıyor

### 📁 DEĞİŞEN DOSYALAR
- `calculators.py`: PDC, Fibo, Doji fonksiyonları + MIN_SIZE constant'ları
- `ob_detector.py`: Boyut filtresi + en yakın 4
- `fvg_detector.py`: Boyut filtresi + en yakın 4
- `setup_detector.py`: Bias + Fibo zone filtresi
- `bitget_service.py`: API fix (CCXT create_order)
- `strategies/__init__.py`: Yeni export'lar

---

## v2.3.14 - Copy Trade API + Duplicate Kontrolü
**Tarih:** 2024-12-22

### main.py
- **NEW:** Duplicate order kontrolü (ENTER öncesi)
- `tracking.check_duplicate_setup()` ile kontrol
- DUPLICATE → skip, UPDATE_NEEDED → yeni order aç

### bitget_service.py
- **NEW:** `place_copy_trade_order()` - Copy Trade API endpoint
- **CHANGED:** `place_order_with_tp_sl()` → Copy Trade API kullanıyor
- **FIXED:** trackingNo:None sorunu çözüldü

### tracking_service.py
- **NEW:** `check_duplicate_setup(coin, direction, entry, tp, sl)`
- Returns: `NEW` | `DUPLICATE` | `UPDATE_NEEDED`

---

# T-TARS v2.3.13 - Limit emir kapatma
**Tarih:** 2024-12-22

### Değişiklikler
- **bitget_service.py**: `close_position()` - Market → Limit close
  - Yeni parametreler: `order_type`, `slippage_pct`
  - LONG kapatma: `price * (1 - slippage)` 
  - SHORT kapatma: `price * (1 + slippage)`
  - Fiyat alınamazsa market'e fallback

- **config.py**: Limit close parametreleri
  - `CLOSE_ORDER_TYPE = 'limit'`
  - `CLOSE_SLIPPAGE_PCT = 0.002` (%0.2)

---

# T-TARS v2.3.12 - Api Key + Parite güncelleme
**Tarih:** 2024-12-22

## 🔧 Değişiklikler

### Config - Pair ve Timeframe Güncellemesi
- **REMOVED:** 5m timeframe (PineScript pasife alındı)
- **REMOVED:** BGB/USDT (AUTO_SCAN_PAIRS ve MANUAL_PAIRS'den çıkarıldı)
- **ADDED:** XRP/USDT, TRX/USDT (AUTO_SCAN_PAIRS'e eklendi)

### API Key
- **UPDATED:** Bitget API key güncellendi (ENV)

### 📁 Değişen Dosyalar (1 dosya)
- `config.py` - Timeframe ve pair güncellemesi

---
**Deploy:** 1 dosya değişti

---

# T-TARS v2.3.11 - (2025-12-20)

## 🔧 Değişiklikler

### Calculators - Confidence Circular Logic Fix
- **CHANGED:** `calculate_setup_strength()` 4 parametre → 3 parametre
- **REMOVED:** confidence parametresi (circular logic fix)
- **NEW:** Volume VETO - düşük volume (<0.8) = max LOW confidence garantisi
- **CHANGED:** Weight'ler: Volume %40, OB/FVG %40, R:R %20

### Tracking Service - TF Bazlı Order Expiry
- **NEW:** `check_and_expire_orders(exchange)` - TF bazlı otomatik expiry
- **NEW:** `get_expiry_hours(timeframe)` - TF'ye göre expiry süresi
  - 5m/3m setup → 2 saat sonra cancel
  - 15m/30m/1h/4h setup → 4 saat sonra cancel

### OB/FVG Detectors
- **CHANGED:** `calculate_setup_strength()` 3 parametre ile çağrılıyor
- **FIX:** Vol=0.63x artık LOW confidence döner (eskiden MEDIUM)

### Telegram Handlers - Score Fix
- **FIX:** f-string format hatası düzeltildi (`available_balance` ternary)

### Main.py - Sadeleştirme
- **REMOVED:** `ORDER_EXPIRY_HOURS` sabit (artık TF bazlı)
- **CHANGED:** `calculate_setup_strength()` 3 parametre

### 📁 Değişen Dosyalar (6 dosya)
- `calculators.py` - Confidence fix + volume veto
- `ob_detector.py` - 3 parametre
- `fvg_detector.py` - 3 parametre
- `tracking_service.py` - TF bazlı expiry
- `telegram_handlers.py` - Score f-string fix
- `main.py` - Expiry logic kaldırıldı + 3 parametre
- `app/__init__.py` - Versiyon güncelleme
- `app/handlers/__init__.py` - Versiyon güncelleme
- `app/services/__init__.py` - BitgetService eklendi
- `app/strategies/__init__.py` - Yeni export'lar

---
**Deploy:** 11 dosya değişti

---
# T-TARS v2.3.10 - (2025-12-19)

## 🔧 Değişiklikler

### OB/FVG Detector - Return Dict Fix
- **FIX:** `volume_spike_ratio` return dict'e eklendi
- **FIX:** `ob_strength` / `fvg_strength` return dict'e eklendi
- Artık main.py'de doğru değerler okunuyor

### Main.py - Setup Strength Fix
- **FIX:** `setup_strength` hem `ob_strength` hem `fvg_strength`'den okunuyor
- OB setup → ob_strength kullanır
- FVG setup → fvg_strength kullanır

### Sonuç
- Python Score artık doğru hesaplanacak (0.46 yerine ~0.70+)
- Daha fazla setup ENTER alacak

### 📁 Değişen Dosyalar
- `main.py`
- `ob_detector.py`
- `fvg_detector.py`

---
**Deploy:** 3 dosya değişti

---
# T-TARS v2.3.9 - (2025-12-19)

## 🔧 Değişiklikler

### Claude Service - EXPAND Algı Düzeltmesi
- **FIX:** Stop EXPAND artık risk olarak algılanmıyor
- **CHANGED:** `⚠️ STOP ADJUSTMENT YAPILDI` → `ℹ️ STOP/TP OPTİMİZASYONU (EXPAND)`
- **ADDED:** EXPAND için pozitif açıklama: "R:R korundu, trade kalitesi değişmedi"

### Mantık
- Stop genişlerse TP de orantılı genişler
- R:R 2.0 → 2.0 kalır (değişmez)
- Bu bir risk DEĞİL, güvenlik optimizasyonu

### 📁 Değişen Dosyalar
- `claude_service.py` - Prompt adjustment bilgisi güncellendi

**Deploy:** Sadece `claude_service.py` değişti

---

## v2.3.8 (2025-12-19)

### 🔧 DRY Refactoring - Tek Yerden Yönetim
- **calculators.py**: Tüm threshold'lar ve score'lar merkezi olarak tanımlandı
- `VOLUME_TRADEABLE_MIN = 0.5` eklendi (minimum tradeable volume)
- `DEFAULT_STRENGTH_SCORE` ve `DEFAULT_CONFIDENCE_SCORE` eklendi (fallback değerler)
- `get_volume_score()` ve `get_rr_score()` fonksiyonları `calculate_setup_strength()` tarafından çağrılıyor

### 🔄 Import Güncellemeleri
- **volume_analyzer.py**: `TRADEABLE_THRESHOLD` kaldırıldı → `VOLUME_TRADEABLE_MIN` import
- **claude_service.py**: Prompt'taki hardcoded değerler → `VOLUME_LOW`, `VOLUME_GOOD`, `VOLUME_EXCELLENT`, `MIN_RR_RATIO` import
- **ob_detector.py**: `VOLUME_THRESHOLD` kaldırıldı → `VOLUME_TRADEABLE_MIN` import
- **fvg_detector.py**: `VOLUME_THRESHOLD` kaldırıldı → `VOLUME_TRADEABLE_MIN` import

### 🐛 Bug Fixes
- **main.py**: `MARKET_CACHE_TTL` 300→1200 saniye (20 dakika)
  - HTF verileri (15m, 30m, 1h) artık expire olmadan yeni veri gelir
  - "Low Volume (0.00x)" false rejection sorunu çözüldü

### 📊 Log Format İyileştirmeleri
- Volume log format `.2f` → `.4f` (0.0000x hassasiyeti)
- HTF cache durumu loglarına TTL bilgisi eklendi

### ⚙️ Config Değişiklikleri
- **config.py**: `MARKET_CACHE_TTL = 1200` eklendi (20 dakika)
- **config.py**: `STOP_DISTANCE_MAX` %1.5 → %2.5 (Claude prompt ile tutarlı)

### 📁 Değişen Dosyalar
- `config.py` - MARKET_CACHE_TTL, STOP_DISTANCE_MAX
- `calculators.py` - Merkezi threshold/score yönetimi + VOLUME_SPIKE_FLAG, VOLUME_STRENGTH_*
- `volume_analyzer.py` - DRY import
- `claude_service.py` - DRY import + prompt güncelleme
- `ob_detector.py` - DRY import + log format
- `fvg_detector.py` - DRY import + log format
- `main.py` - Config.MARKET_CACHE_TTL kullanımı
- `bitget_service.py` - Config.MARKET_CACHE_TTL + DRY volume thresholds

---

## v2.3.7 (2025-12-18)

### Yeni Özellikler
- **Volume Analyzer Entegrasyonu**: Webhook'tan gelen volume verisi artık `volume_analyzer` modülüne yazılıyor
- `store_volume()`: Webhook'tan volume/ATR saklar
- `get_volume()`: Detector'lar için volume döndürür
- `get_all_volumes()`: Tüm TF'ler için volume döndürür
- 2 saat sonra otomatik expire
- **Bar Kapanışı Timing**: Analyze sadece 5m bar kapandıktan 1 dk sonra çalışır (xx:01, xx:06, xx:11...)

### Değişiklikler
- Webhook hem `MARKET_CACHE` hem `volume_analyzer`'a yazıyor (backward compatibility)
- `/volume` komutu artık volume store istatistiklerini de gösteriyor
- Auto analyze'da `cleanup_expired_volumes()` çağrılıyor
- Cloud Scheduler her 3 dk çağırır ama sadece uygun dakikalarda gerçek analiz yapar

### ATR Format Düzeltmesi
- **PineScript**: ATR formatı `#.######` (6 decimal) olarak güncellendi
- **Python**: ATR log formatı `.6g` (dinamik precision, trailing zeros yok)
- **Örnek Çıktı**: `JUPUSDT_5m = 0.53x, ATR=0.0005` ✅

### Timing Kontrolü (Config'e Bağlı)
- `Config.MONITOR_INTERVAL_MINUTES = 5` (default)
- main.py artık Config'den okur (hardcoded değil)
- Cloud Scheduler: `1,6,11,16,21,26,31,36,41,46,51,56 * * * *`

### Mimari
- Detector'lar artık `volume_analyzer.get_volume()` ile okuyabilir
- Cache problemi çözüldü - merkezi volume storage
- Timing uyumsuzluğu çözüldü - bar kapanışı + 1dk bekleme

---

## v2.3.6 (2025-12-17)

### 🐛 Bug Fixes
- **FIX: POST 400 hatası düzeltildi** - `spike=0` artık kabul ediliyor
  - Eski: `spike <= 0` ise 400 dönüyordu (düşük volume'u reddediyordu)
  - Yeni: Sadece `spike` field eksikse 400 döner, 0 değeri kabul edilir
  - Bu düzeltme sayesinde tüm volume değerleri cache'e yazılacak

### 📝 Technical Details
- `/webhook/volume` endpoint'inde validation mantığı değişti
- `spike=0` = düşük volume demek, bu geçerli bir piyasa verisi
- Cache miss sorunu çözülecek (0.00x görünmeyecek)

--- 

## v2.3.5 (2025-12-17)

### 🔥 Major Change: Fallback Kaldırıldı
- **REMOVED:** Bitget fallback volume/ATR hesaplama tamamen kaldırıldı
- **CHANGED:** Cache'de TradingView verisi yoksa `spike_ratio = 0` döner
- **RESULT:** Setup'lar "Low Volume (0.00x < 0.5x)" ile reject edilir
- **BENEFIT:** Daha temiz ve öngörülebilir davranış

### 📊 Davranış Değişikliği
- Önceki: Cache miss → Bitget'ten hesapla (yavaş, tutarsız)
- Yeni: Cache miss → spike_ratio=0 → Setup reject

### ⚠️ Önemli Not
- TradingView alert'lerinin düzgün çalışması kritik
- XAU ve BGB için TradingView alert yoksa setup bulunamaz
- Alert webhook URL: `/webhook/volume`
# T-TARS CHANGELOG

## v2.3.4 (2025-12-17)

## 🚀 Yeni Özellikler

### TradingView ATR Entegrasyonu
- **ATR artık TradingView'dan alınıyor** (Binance kaynaklı)
- Pine Script v4 ile hem Volume hem ATR webhook'la gönderiliyor
- ATR cache'de yoksa veya eskiyse → Bitget fallback hesaplama

### Cache Sistemi Genişletildi
- `VOLUME_CACHE` → `MARKET_CACHE` olarak yeniden adlandırıldı
- Cache artık hem Volume hem ATR içeriyor
- Format: `{"BTCUSDT_15m": {"spike": 2.34, "atr": 125.5, "ts": ...}}`

## 🐛 Bug Fixes

### Claude Service TP2 Fix
- **FIX:** `adjust_stop_and_tp()` artık TP2'yi de hesaplıyor
- **FIX:** ATR=0 durumu için sanity check eklendi
- **FIX:** LONG için TP2 > Entry, SHORT için TP2 < Entry kontrolü
- Eski problem: TP1 güncelleniyor ama TP2 orijinal kalıyordu

## 📝 Değişiklikler

### main.py
- `/webhook/volume` endpoint artık `atr` parametresi de kabul ediyor
- `MARKET_CACHE` hem volume hem ATR depoluyor
- `/volume` komutu ATR cache durumunu da gösteriyor

### bitget_service.py
- `volume_cache` → `market_cache` parametresi
- ATR değeri önce cache'den aranıyor
- Log: "Vol: X TV, Y fallback | ATR: X TV, Y fallback"

### claude_service.py
- `adjust_stop_and_tp()` artık `tp2_price` parametresi alıyor
- TP2 de adjustment'a dahil (TP2/TP1 oranı korunuyor)
- ATR=0 kontrolü: TP2 ≤ Entry (LONG) veya TP2 ≥ Entry (SHORT) → SKIP

## 📦 Dosyalar

| Dosya | Değişiklik |
|-------|------------|
| `main.py` | ATR webhook, MARKET_CACHE |
| `bitget_service.py` | ATR cache okuma |
| `claude_service.py` | TP2 adjustment, ATR=0 kontrolü |
| `VERSION` | 2.3.4 |

---

## v2.3.3 (2025-12-17)

### Added
- **main.py**: TradingView Volume Webhook entegrasyonu
  * `VOLUME_CACHE` global dict - TF bazlı volume cache
  * `/webhook/volume` endpoint - Binance volume spike alır
  * `/webhook/volume/status` endpoint - Cache durumu gösterir
  * `/volume` Telegram komutu - Cache stats
- **bitget_service.py**: `get_complete_analysis_data(volume_cache=None)` parametresi
  * TradingView cache varsa ve taze (<5dk) → Binance volume kullanır
  * Cache yoksa veya eskiyse → Bitget fallback hesaplama

### Changed
- **main.py**: auto_analyze() volume_cache'i bitget'e geçirir
- **main.py**: Eski cache entry'leri otomatik temizlenir (TTL: 5dk)
- **bitget_service.py**: Volume source loglama eklendi (Binance vs fallback)
- **bitget_service.py**: analyze_volume_for_tf() 'source' field eklendi

### Technical Details
- TradingView Pine Script → POST /webhook/volume → VOLUME_CACHE
- Cache key format: "BTCUSDT_15m"
- Payload: {"pair": "BTCUSDT", "tf": "15", "spike": 2.34}
- Volume öncelik: TradingView Binance > Bitget fallback
- Auto-cleanup: 5 dakikadan eski entry'ler analyze başında silinir

---

## v2.3.2 (2025-12-17)

### Added
- **claude_service.py**: Otomatik Stop Adjustment sistemi
  * Stop < 0.8% → %0.8'e çek, TP orantılı uzat (EXPAND)
  * Stop 1.5-2% → %1.5'e çek, TP orantılı kısalt (SHRINK)
  * Stop 2-2.5% → %1.8'e çek, TP 3R yap (AGGRESSIVE)
  * Stop >= 2.5% → SKIP (çok riskli)
- **claude_service.py**: `adjust_stop_and_tp()` fonksiyonu
- **claude_service.py**: Adjustment bilgisi Claude prompt'una eklendi
- **claude_service.py**: Adjustment logları ve debug bilgisi

### Changed
- **claude_service.py**: Sabit %0.8 min ve %1.5 max stop kontrolleri kaldırıldı
- **claude_service.py**: Stop/TP adjustment sonrası Claude'a gönderiliyor
- **claude_service.py**: Response'a `adjustments` dict eklendi

### Technical Details
- Stop adjustment sabitleri class değişkeni olarak tanımlandı
- EXPAND: R:R korunur, stop/tp orantılı genişler
- SHRINK: R:R korunur, stop/tp orantılı daralır
- AGGRESSIVE: Stop %1.8, TP 3R sabit
- Adjustment result None ise → SKIP (stop >= 2.5%)

---
## v2.3.1 (2025-12-17)

### Fixed
- **main.py**: `setup['pair'] = pair` eklendi - Setup'a pair bilgisi eklenmiyordu, Claude hep SKIP ediyordu
- **claude_service.py**: `round(rr_ratio, 2) < 2.0` - R:R 2.00 floating point hatası düzeltildi, artık 2.0 dahil
- **claude_service.py**: Hardcoded default değerler kaldırıldı - "neyse o" modeli: veri yoksa LOG + SKIP
- **telegram_handlers.py**: `/score` komutu - Available yerine TOTAL bakiye gösteriliyor
- **telegram_handlers.py**: Best/Worst coin ve TF - Min 3 trade zorunluluğu kaldırıldı, tüm veriler gösteriliyor

### Added
- **claude_service.py**: Debug logları - Eksik veri anında görünür
- **main.py**: Timeframe bilgisi log mesajlarına eklendi
- **telegram_handlers.py**: Completed trade sayısı, expired count gösterimi

### Technical Details
- claude_service.py: Tüm kritik veriler (pair, direction, timeframe, entry, stop, tp, rr) kontrol ediliyor
- Eksik kritik veri varsa → ERROR log + SKIP (yanlış default ile işlem yok)
- Opsiyonel veriler (confidence, strength_score, pdc, atr, volume) → WARNING log

---

## v2.3.0 (2025-12-16) - Claude AI Decision Engine

### 🚀 Major Features
- **Claude AI Karar Mekanizması**: Setup'lar artık Claude Haiku 4.5 tarafından değerlendiriliyor
- **Akıllı Filtre**: Claude onay vermeden HİÇBİR emir açılmıyor
- **Likidite + Reversal Kontrolü**: PDC sweep ve reversal sinyalleri analiz ediliyor

### 🔄 Changes
- `claude_service.py`: `evaluate_setup()` fonksiyonu eklendi
- `bitget_service.py`: `execute_trade_for_setup()` taşındı (telegram_handlers'dan)
- `main.py`: auto_analyze() Claude entegrasyonu
- `telegram_handlers.py`: execute_trade_for_setup() kaldırıldı

### 📊 Claude Kontrol Listesi
1. Likidite temizlenmiş mi? (PDC High/Low sweep)
2. Reversal sinyali var mı?
3. OB/FVG confluence güçlü mü?
4. Direction PDC bias ile uyumlu mu?
5. Stop mesafesi %0.8-1.5 arası mı?
6. RR oranı minimum 2.0 mı?

### ⚙️ Technical
- Pre-filter: RR < 2.0 veya Stop %0.8-1.5 dışı → Otomatik SKIP
- Claude karar: ENTER / SKIP / WAIT
- Telegram bildirimi: Claude reasoning dahil

---

## v2.2.9 (2025-12-16) - SL Clamp Fix

### Fixed
- `place_order_with_tp_sl()` içinde SL minimum mesafe kontrolü
- Stop çok yakınsa minimum %0.8 mesafeye çekiliyor
- "Anında stop vurma" sorunu çözüldü

---
# T-TARS Trading Bot CHANGELOG

## v2.2.8 (2025-12-16)

### Added
- **4 Saat Order Expiry**: Dolmayan limit emirler 4 saat sonra otomatik iptal
  - Monitor her 3 dk'da PENDING emirlerin yaşını kontrol eder
  - 4 saat geçmiş emirler → Bitget'ten iptal + tracking'de EXPIRED
  - Marjin esir alınmasını önler, yeni işlemlere yer açar

- **Kademeli Marjin Sistemi**: TOTAL balance'a göre dinamik marjin
  - Total >= $2000 → %1-2 dinamik ($20-40)
  - $1000 <= Total < $2000 → Sabit $20
  - Total < $1000 → Sabit $10
  - Available balance değil, TOTAL balance kullanılıyor

### Changed
- `bitget_service.py`: `calculate_position_size()` artık `total` balance kullanıyor
- `main.py`: Monitor'a order expiry logic eklendi
- `tracking_service.py`: `mark_setup_expired()` fonksiyonu eklendi, EXPIRED status

### Technical Details
- `ORDER_EXPIRY_HOURS = 4` (main.py)
- Monitor response: `{"status": "success", "updates": X, "expired": Y}`
- Tracking status: PENDING → EXPIRED (iptal edilen emirler için)
- Stats'ta expired_setups gösteriliyor

---

## 2.2.7 - 2024-12-16

### Fixed
- **Monitor TP/SL Kaldırıldı**: Monitor artık `modify_tracking_tpsl()` çağırmıyor
  - TP/SL order sırasında preset ediliyor (v2.2.6)
  - "batch TP/SL" hatası çözüldü
  - Tekrarlayan TP/SL ekleme girişimleri engellendi

### Changed
- **Marjin Log'ları Netleştirildi**:
  - Marjin vs Notional ayrımı açıkça gösteriliyor
  - `💰 Pozisyon Hesabı:` detaylı log eklendi
  - Bakiye, Marjin Limiti, Hesaplanan Marjin, Notional ayrı ayrı loglanıyor
  
### Technical Details
- `main.py`: Monitor'dan `modify_tracking_tpsl()` kaldırıldı (satır 167-180)
- `bitget_service.py`: `calculate_position_size()` log'ları iyileştirildi
- `place_order_with_tp_sl()`: `margin_usd` return değeri eklendi

### Log Örneği (v2.2.7)
```
💰 Pozisyon Hesabı:
   Bakiye: $2000.00
   Marjin Limiti: $20.00 - $40.00 (%1-%2)
   Hesaplanan Marjin: $25.00 → Final: $25.00
   Notional (Kaldıraçlı): $500.00 (20x)
```


## v2.2.6 (2025-12-16)

### 🚀 Major Fixes
- **TP/SL at Order Time**: Artık limit emir açılırken TP/SL aynı anda set ediliyor
  - `presetStopSurplusPrice` → Take Profit
  - `presetStopLossPrice` → Stop Loss
  - Sonradan trackingNo arama ve modify işlemi KALDIRILDI
  - TP/SL validation hataları ÇÖZÜLDÜí

### 📱 Telegram Bildirimleri
- **HER ZAMAN bildirim**: Execute sonrası mutlaka Telegram bildirimi gönderiliyor
- `chat_id` olmasa bile `Config.TELEGRAM_CHAT_ID`'ye gönderim
- Detaylı başarı/hata mesajları

### ⚙️ Coin Listesi
- AUTO_SCAN_PAIRS 9 coine düşürüldü (log kirliliği azaltma):
  - BTC, ETH, SOL, BNB, DOGE, SHIB, XAU, JUP, BGB

### 🔧 Technical
- `bitget_service.py`: place_order_with_tp_sl() yeniden yazıldı
- `telegram_handlers.py`: execute_trade_for_setup() güncellendi
- `config.py`: AUTO_SCAN_PAIRS güncellendi

---

## 2.2.5 - 2025-12-16

### Added
- **Entry Distance Filter**: Setup'lar artık current price'tan max %3 uzaklıkta olabilir
  - `ob_detector.py`: MAX_ENTRY_DISTANCE_PERCENT = 3.0
  - `fvg_detector.py`: MAX_ENTRY_DISTANCE_PERCENT = 3.0
  - Uzak zone'lara emir verilmesi engellendi
  - TP/SL Bitget validation hataları önlendi

### Fixed
- BCH $542 → $760 entry gibi uzak emirler artık reddedilecek
- "Take profit price needs to be < current price" hatası çözüldü
- "Stop loss price needs to be > current price" hatası çözüldü

### Technical Details
```python
# Her detect fonksiyonuna eklendi:
MAX_ENTRY_DISTANCE_PERCENT = 3.0

if current_price > 0:
    distance_percent = abs(entry_price - current_price) / current_price * 100
    if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
        logger.info(f"{coin} rejected: Entry too far ({distance_percent:.1f}%)")
        return None
```

### Changed Files
- `app/strategies/ob_detector.py` → v2.2.5
- `app/strategies/fvg_detector.py` → v2.2.5

## v2.2.4 (2024-12-16)

### 🔥 Major Changes - Bitget Bazlı Takip Sistemi

**Ezbere Takip KALDIRILDI - Artık Tamamen Bitget Verisi Kullanılıyor**

### Added
- `bitget_service.py`:
  - `_sign_request()` - Bitget API HMAC-SHA256 imzalama
  - `_get_headers()` - Signed headers oluşturma  
  - `_copy_trade_request()` - Direct HTTP request helper
  - Copy Trade API artık `requests` kütüphanesi ile doğrudan HTTP kullanıyor (CCXT bypass)
  - `TF_LOOKBACK_BARS` - Her TF için farklı geriye bakış süresi:
    - 5m: 288 bar (24 saat)
    - 15m: 96 bar (24 saat)
    - 30m: 48 bar (24 saat)
    - 1h: 36 bar (36 saat)
    - 4h: 9 bar (36 saat)

- `tracking_service.py`:
  - `update_setup_from_bitget()` - Bitget'ten gelen gerçek P/L ile güncelleme
  - `mark_setup_filled()` - Emir dolduğunda çağrılır
  - `get_setup_by_tracking_no()` - trackingNo ile setup bulma
  - `get_setup_by_order_id()` - order_id ile setup bulma
  - `get_pending_setups()` - Sadece PENDING/FILLED olanları getir

- `main.py`:
  - `/monitor` artık Bitget bazlı çalışıyor:
    1. Bekleyen limit emirleri kontrol et (doldu mu?)
    2. Emir dolmuşsa → trackingNo al, TP/SL ekle
    3. Copy Trade pozisyonlarını kontrol et (kapanmış mı?)
    4. Kapanmışsa → Bitget P/L ile tracking güncelle

### Changed
- `bitget_service.py`:
  - `get_tracking_orders()` - CCXT → Direct HTTP
  - `modify_tracking_tpsl()` - CCXT → Direct HTTP
  - `close_tracking_order()` - CCXT → Direct HTTP

- `tracking_service.py`:
  - `log_setup()` artık Bitget order bilgilerini de kaydediyor:
    - `order_id`, `tracking_no`, `contracts`, `position_usd`
    - `bitget_entry_price`, `bitget_close_price`, `bitget_pnl`, `bitget_fee`

### Removed
- `tracking_service.py`:
  - ❌ `check_setup_status()` - Ezbere fiyat karşılaştırması KALDIRILDI
  - ❌ `get_all_pending_setups()` → `get_pending_setups()` ile değiştirildi

### Fixed
- CCXT'nin Copy Trade API endpoint'lerini tanımaması sorunu (`'bitget' object has no attribute 'privateGetApiV2CopyMixTraderOrderCurrentTrack'`)

### Technical Details
- Bitget API Signing: `timestamp + method + requestPath + body` → HMAC-SHA256 → Base64
- Copy Trade Endpoints:
  - GET `/api/v2/copy/mix-trader/order-current-track`
  - POST `/api/v2/copy/mix-trader/order-modify-tpsl`
  - POST `/api/v2/copy/mix-trader/order-close-positions`

---
## v2.2.3 (2025-12-15)

### NEW - Copy Trade API Entegrasyonu
- **get_tracking_orders():** Copy Trade açık pozisyonlarını çek
  - GET /api/v2/copy/mix-trader/order-current-track
  - trackingNo, symbol, posSide, TP/SL bilgileri döner
  
- **modify_tracking_tpsl():** Copy Trade TP/SL ekle/güncelle
  - POST /api/v2/copy/mix-trader/order-modify-tpsl
  - trackingNo ile TP ve SL fiyatlarını set eder
  
- **close_tracking_order():** Copy Trade pozisyon kapat
  - POST /api/v2/copy/mix-trader/order-close-positions
  - trackingNo veya symbol ile pozisyon kapatır
  
- **find_tracking_no_by_symbol():** Symbol'e göre trackingNo bul

### Changed
- **place_order_with_tp_sl():** Yeni 4 adımlı akış:
  1. Normal API ile limit emir aç
  2. 2 saniye bekle (emir işlensin)
  3. trackingNo'yu bul (Copy Trade API)
  4. TP/SL ekle (Copy Trade API - order-modify-tpsl)

### Removed
- **add_tp_sl_to_position():** Kaldırıldı (place-pos-tpsl çalışmıyordu)

### Technical
- Copy Trade pozisyon kapatınca personal hesapta da kapanıyor
- Elite Trader olarak T-TARS artık Copy Trade API kullanıyor

---
## v2.2.2 (2025-12-15)

### Fixed
- **Bitget Hedge Mode (40774):** `tradeSide: 'open'` parametresi eklendi - GitHub #20729 çözümü
- **OHLCV 2h Bug:** 2h timeframe kaldırıldı - CCXT Bitget bug (GitHub #27281)
- **Tracking KeyError:** log_setup fonksiyonunda `entry_zone` KeyError hatası düzeltildi

### Changed
- **Config:** TIMEFRAMES listesinden 2h kaldırıldı: `['4h', '1h', '30m', '15m', '5m']`
- **BitgetService:** close_position için `tradeSide: 'close'` eklendi
- **TrackingService:** Tüm setup_data erişimleri .get() ile güvenli hale getirildi

### Technical
- bitget_service.py: SKIP_TIMEFRAMES listesi eklendi
- tracking_service.py: entry_zone fallback olarak entry_price kullanılıyor

---

## v2.2.1 (2024-12-13)

### 🔧 Fixed
- **TP/SL Hatası Çözüldü**: Bitget `createOrder()` artık 2 adımda çalışıyor
  - ADIM 1: Limit order (TP/SL olmadan)
  - ADIM 2: `place-pos-tpsl` API ile TP/SL ekleme
- **Bildirim Sorunu Çözüldü**: Execute başarısız olan trade'ler artık log'lanmıyor
  - Eski: Setup detect → Log → Execute (başarısız olsa bile bildirim)
  - Yeni: Setup detect → Execute → Başarılıysa Log (başarısız = atla)

### ✨ Changed
- **bitget_service.py**: 2 adımlı order sistemi (`add_tp_sl_to_position` fonksiyonu eklendi)
- **main.py**: Execute-first akışı (`/analyze` route güncellendi)
- **tracking_service.py**: `check_duplicate_setup()` kaldırıldı (copy trade desteği)

### 📁 Değişen Dosyalar
- `app/services/bitget_service.py` (v2.2.0 → v2.2.1)
- `app/main.py` (v2.2.0 → v2.2.1)
- `app/services/tracking_service.py` (v2.1.4 → v2.2.1)

---
## v2.2.0 (2025-12-13)

### 🔄 MAJOR: Bitget Fork
- **CHANGED:** `okx_service.py` → `bitget_service.py`
- **CHANGED:** ccxt.okx() → ccxt.bitget()
- **CHANGED:** OKX ENV değişkenleri → Bitget ENV değişkenleri:
  - `OKX_API_KEY` → `BITGET_API_KEY`
  - `OKX_SECRET_KEY` → `BITGET_SECRET_KEY`
  - `OKX_PASSPHRASE` → `BITGET_PASSPHRASE`
  - `OKX_TRADING_ENABLED` → `BITGET_TRADING_ENABLED`
- **CHANGED:** Hedge mode parametreleri:
  - `tdMode: 'cross'` → `marginMode: 'cross'`
  - `posSide` → `holdSide`
- **CHANGED:** TP/SL parametreleri:
  - `attachAlgoOrds` → `stopLossPrice`, `takeProfitPrice`

### ✨ NEW: Çoklu Emir Desteği
- **REMOVED:** `has_pending_orders()` kontrolü kaldırıldı
- **REMOVED:** `has_open_position()` kontrolü kaldırıldı
- Copy trade altında aynı yönde birden fazla emir açılabiliyor

### ⏱️ Timeframe Değişiklikleri
- **ADDED:** 5m timeframe geri eklendi
- **KEPT:** 3m hala kaldırılmış durumda (düşük ATR sorunu)
- TIMEFRAMES: `['4h', '2h', '1h', '30m', '15m', '5m']`

### 💹 Yeni Pariteler
- **ADDED:** XAU/USDT:USDT (Gold)
- **ADDED:** FLOKI/USDT:USDT
- **ADDED:** BGB/USDT:USDT (Bitget Token)
- **ADDED:** BCH/USDT:USDT (Bitcoin Cash)
- AUTO_SCAN_PAIRS: 14 → 18 coin

### 🤖 Telegram Komutları
- **CHANGED:** `/stopokx` → `/stopbitget`
- **CHANGED:** `/startokx` → `/startbitget`
- **ADDED:** Backward compatibility (eski komutlar da çalışıyor)
- **FIX:** Trading kapalıyken tracking bildirimleri gitmiyor
- **CHANGED:** `/status` - Bitget market/API durumu gösteriyor
- **CHANGED:** `/help` - Güncel komut listesi

### 📊 Score & Tracking
- **FIX:** Trade count gösterimi (Top/Worst listelerinde)
- **FIX:** Ağırlıklı sıralama (win_rate × trade_weight)
- **NOTE:** 3m istatistikleri eski verilerden kalma, reset_score ile temizlenir

### 📁 Dosya Değişiklikleri
- `okx_service.py` → `bitget_service.py` (yeniden yazıldı)
- `config.py` (ENV isimleri, pariteler, timeframes)
- `main.py` (import değişiklikleri)
- `telegram_handlers.py` (komut değişiklikleri)

### 🔧 Teknik Detaylar
- Bitget USDT-M Futures (linear) desteği
- Hedge mode (double_hold) aktif
- Cross margin kullanılıyor
- Leverage: 20x (default)

---
## [v2.1.4] (2024-12-12)

### 🎯 Ana Değişiklikler
- **3m ve 5m timeframe devreden çıkarıldı** - Düşük ATR nedeniyle çok dar stop mesafesi sorunu
- **Stop mesafesi limitleri** - Min %0.8, Max %1.5 (Config'den ayarlanabilir)
- **Dinamik marjin limitleri** - Bakiyenin %1-2'si (Config'den ayarlanabilir)
- **Trade count gösterimi** - Top/Worst listelerinde kaç işlem yapıldığı görünüyor
- **Ağırlıklı sıralama** - 1 trade %100 win artık en üstte değil

### 📁 Değişen Dosyalar

#### config.py
- **ADDED:** `TIMEFRAMES = ['4h', '2h', '1h', '30m', '15m']` (3m, 5m kaldırıldı)
- **ADDED:** `STOP_DISTANCE_MIN = 0.008` (%0.8)
- **ADDED:** `STOP_DISTANCE_MAX = 0.015` (%1.5)
- **ADDED:** `MARGIN_MIN_PERCENT = 1.0` (Bakiyenin %1'i)
- **ADDED:** `MARGIN_MAX_PERCENT = 2.0` (Bakiyenin %2'si)

#### okx_service.py
- **CHANGED:** `ANALYSIS_TIMEFRAMES` kaldırıldı → `Config.TIMEFRAMES` kullanılıyor
- **ADDED:** `format_price_display()` - PEPE/PUMP $0.00 sorunu düzeltildi
- **CHANGED:** `calculate_position_size()` - Stop ve marjin limitleri uygulanıyor
- **ADDED:** Stop mesafesi clamp log: `📏 Stop mesafesi clamp: 0.32% → 0.80%`
- **ADDED:** Marjin clamp log: `💰 Marjin clamp: $312.50 → $42.00`

#### telegram_handlers.py
- **CHANGED:** `/score` formatı güncellendi
- **ADDED:** Trade count gösterimi: `PEPE - W:100% L:0% (3)`
- **ADDED:** "(min 3 trade)" başlık notu

#### tracking_service.py
- **ADDED:** `MIN_TRADES_FOR_RANKING = 3` (2'den yükseltildi)
- **ADDED:** `calculate_ranking_score()` - Ağırlıklı sıralama fonksiyonu
- **ADDED:** `completed` field - Trade count stats'ta
- **CHANGED:** Top/Worst sıralaması artık `win_rate × trade_weight` kullanıyor
- **ADDED:** $500 fallback uyarı logu

### 📊 Örnek Çıktılar

#### Stop & Marjin Clamp ($2100 bakiye, 20x kaldıraç):
```
📏 Stop mesafesi clamp: 0.32% → 0.80%
💰 Marjin clamp: $312.50 → $42.00 (min:$21.00, max:$42.00)
📐 Risk Hesabi: Bakiye=$2100.00 | Risk%=1.0 | Risk$=21.00 | Stop=0.80% | Marjin=$42.00 | Pozisyon=$840.00
```

#### /score Formatı:
```
🏆 Top 5 Coin (min 3 trade)
  1. AVAX - W:88.9% L:11.1% (9)
  2. JUP - W:83.3% L:16.7% (6)
  3. TRUMP - W:71.4% L:28.6% (7)
```

### 🔢 Ağırlıklı Sıralama Formülü
```
score = win_rate × (1 - 1/(trade_count + 1))

Örnekler:
- 3 trade, %100 win → 100 × 0.75 = 75
- 10 trade, %70 win → 70 × 0.91 = 63.7
- 20 trade, %60 win → 60 × 0.95 = 57
```

### 📋 Marjin Hesaplama Tablosu

| Bakiye | Min Marjin (%1) | Max Marjin (%2) | Min Pozisyon (20x) | Max Pozisyon (20x) |
|--------|-----------------|-----------------|--------------------|--------------------|
| $1500 | $15 | $30 | $300 | $600 |
| $2100 | $21 | $42 | $420 | $840 |
| $3000 | $30 | $60 | $600 | $1200 |

---

## [v2.1.3] (2025-12-12)

### 🎯 BÜYÜK DEĞİŞİKLİK: Risk Bazlı Pozisyon Hesaplama

#### config.py
- **REMOVED:** `MAX_POSITION_SIZE` (risk hesabı artık okx_service'te)
- **REMOVED:** `RISK_PER_TRADE_MIN` / `RISK_PER_TRADE_MAX` → tek `RISK_PER_TRADE`
- **REMOVED:** `DEFAULT_BALANCE` (gerçek bakiye OKX'ten alınacak)
- **ADDED:** `RISK_PER_TRADE = 1.0` (varsayılan %1 risk)

#### telegram_handlers.py
- **REMOVED:** `execute_trade_for_setup` içindeki tüm risk hesaplama kodu
- **REMOVED:** `Config.MAX_POSITION_SIZE` referansı
- **CHANGED:** Sadece setup bilgilerini okx_service'e geçiriyor

#### okx_service.py
- **NEW:** `calculate_position_size(entry_price, stop_price)` - Risk bazlı pozisyon hesaplama
- **NEW:** `has_pending_orders(symbol)` - Bekleyen emir kontrolü
- **NEW:** `has_open_position(symbol)` - Açık pozisyon kontrolü
- **NEW:** `format_price_string(price)` - Scientific notation fix
- **CHANGED:** `place_order_with_tp_sl` artık `amount_usd` almıyor, risk otomatik

#### ob_detector.py
- **REMOVED:** `Config.DEFAULT_BALANCE` referansı
- **REMOVED:** `Config.RISK_PER_TRADE_MIN/MAX` referansı
- **REMOVED:** `detailed_explanation`'dan `risk_usd` bilgisi
- **CLEAN:** Sadece setup detection, risk hesabı yok

#### fvg_detector.py
- **REMOVED:** `Config.DEFAULT_BALANCE` referansı
- **REMOVED:** `Config.RISK_PER_TRADE_MIN/MAX` referansı
- **REMOVED:** `detailed_explanation`'dan `risk_usd` bilgisi
- **CLEAN:** Sadece setup detection, risk hesabı yok

### 📐 Yeni Risk Hesaplama Mantığı

```
Bakiye: $2000 (OKX'ten gerçek)
Risk: %1 = $20 (Config.RISK_PER_TRADE)
Entry: $100, Stop: $99 (mesafe: %1)

Position Size = $20 / 0.01 = $2000

Sonuç:
- 1R kaybı = $20
- 2R karı = $40 (TP1)
- 4R karı = $80 (TP2)
```

### 🔒 Güvenlik Kontrolleri

```python
# Emir açmadan ÖNCE kontrol:
if has_pending_orders(symbol):
    return 'pending_order_exists'

if has_open_position(symbol):
    return 'position_exists'
```

### 🔢 Scientific Notation Fix

```python
# Eski: "1.1745893714285715e-05" ❌
# Yeni: "0.0000117459" ✅
```

# T-TARS Changelog

## [v2.1.2] - 2025-12-11

### Fixed
- **OKX TP/SL Error 51000**: Parameter ordType hatasi duzeltildi
  - Flat parametreler (tpTriggerPx, slTriggerPx) yerine `attachAlgoOrds` array kullaniliyor
  - OKX API v5 standardi: TP/SL attached algo order olarak gonderiliyor
  - `tpTriggerPxType` ve `slTriggerPxType` eklendi ('last' = son fiyat)
  - `tpOrdPx` ve `slOrdPx` '-1' olarak ayarlandi (market price)

### Technical Details
- **Root Cause**: OKX API v5, market order ile birlikte TP/SL gonderirken flat parametre yerine `attachAlgoOrds` array bekliyor
- **Solution**: params dict icinde `attachAlgoOrds: [{tpTriggerPx, tpOrdPx, tpTriggerPxType, slTriggerPx, slOrdPx, slTriggerPxType}]` kullaniliyor
- **Reference**: OKX API docs - "attachAlgoOrds array parameters"

### Changed Files
- `app/services/okx_service.py` - place_order_with_tp_sl() fonksiyonu guncellendi

---

## [v2.1.1] (2025-12-11)

### Added - Gerçek Balance & Detaylı Rapor

**main.py:**
- NEW: `auto_analyze()` başında OKX balance 1 kez çekiliyor
- NEW: `tracking.log_setup(balance_before=real_balance)` gerçek balance geçiriliyor
- FIX: Monitor endpoint'te emoji mapping eklendi (TP1, TP2, STOPPED, EXPIRED)

**tracking_service.py:**
- NEW: `get_aggregate_stats(real_balance)` parametresi eklendi
- NEW: Top 5 / Worst 5 coin (win rate bazlı, min 2 trade)
- NEW: Top 5 / Worst 5 timeframe (win rate bazlı, min 2 trade)
- FIX: Hardcoded 1000$ kaldırıldı, OKX balance kullanılıyor

**telegram_handlers.py:**
- NEW: `/score` detaylı rapor formatı:
  - Genel durum (Total, Win, Loss, Win Rate)
  - P/L durumu (gerçek balance ile)
  - Top 5 Coin & TimeFrame
  - Worst 5 Coin & TimeFrame
- FIX: `execute_trade_for_setup()` parametre düzeltmesi (amount → amount_usd)

### Technical Details

**Balance Akışı:**
```
auto_analyze() başı:
    balance = okx.get_balance()['free']  ← 1 API call / 3dk
    
    for setup in setups:
        tracking.log_setup(balance_before=balance)  ← Hepsi aynı balance
```

**Rapor Formatı (/score):**
```
📊 T-TARS İSTATİSTİK RAPORU

🎯 Genel Durum
• Total: X | Win: X | Loss: X
• Win Rate: %X | Loss Rate: %X

📈 P/L Durumu
• Bakiye: $500.00
• Kar/Zarar: +$XX.XX (+%X.X)

🏆 Top 5 Coin
  1. BTC - W:80% L:20%
  ...

⏱️ Top 5 TimeFrame
  1. 4h - W:75% L:25%
  ...

💀 Worst 5 Coin
  ...

⚠️ Worst 5 TimeFrame
  ...
```

---
## [v2.1.0] (2025-12-11)

### Fixed - Kritik Formül Düzeltmeleri

**telegram_handlers.py:**
- FIX: `execute_trade_for_setup()` parametre hatası düzeltildi
  - `amount=size_usd` → `amount_usd=size_usd`
  - Bu hata yüzünden OKX'e emir gitmiyordu

**main.py:**
- FIX: `tracking.log_setup()` eksik field'lar tamamlandı
  - timestamp, entry_price, entry_zone, stop_loss, stop_price
  - tp1, tp2, tp1_price, tp2_price, rr_ratio
- FIX: Detector'dan gelen tüm veriler doğru mapping ile tracking'e geçiriliyor
- FIX: `stop_loss` artık format_price() ile string'e çevriliyor

**ob_detector.py:**
- FIX: Entry hesabı düzeltildi → `(OB_Low + OB_High) / 2`
- FIX: Stop hesabı düzeltildi → `Entry ± ATR` (OB'den değil, Entry'den)
- FIX: scan_order_blocks key'leri tutarlı hale getirildi (`high`/`low`)
- REMOVE: STOP_MULTIPLIER kullanımı kaldırıldı (direkt ATR)

**fvg_detector.py:**
- FIX: Entry hesabı düzeltildi → Kadircan formülü (21.46% oran)
  - LONG: `gap_high - (((gap_high + gap_low) / 100) * 21.46)`
  - SHORT: `gap_low + (((gap_high + gap_low) / 100) * 21.46)`
- FIX: Stop hesabı düzeltildi → `Entry ± ATR`
- REMOVE: STOP_MULTIPLIER kullanımı kaldırıldı
- ADD: `FVG_ENTRY_RATIO = 21.46` sabiti eklendi

### Technical Details

**Yeni Formüller:**

| Setup | Entry | Stop | TP1 | TP2 |
|-------|-------|------|-----|-----|
| OB LONG | (OB_H + OB_L) / 2 | Entry - ATR | Entry + 2*ATR | Entry + 4*ATR |
| OB SHORT | (OB_H + OB_L) / 2 | Entry + ATR | Entry - 2*ATR | Entry - 4*ATR |
| FVG LONG | gap_high - (sum * 0.2146) | Entry - ATR | Entry + 2*ATR | Entry + 4*ATR |
| FVG SHORT | gap_low + (sum * 0.2146) | Entry + ATR | Entry - 2*ATR | Entry - 4*ATR |

**R:R Sonucu:**
- Risk = 1 ATR (sabit)
- TP1 R:R = 2.0
- TP2 R:R = 4.0

## [v2.0.9] - 2025-12-10

### 🔴 Critical Fixes
- **10m Timeframe:** OKX desteklemiyor, tüm dosyalardan kaldırıldı.
- **TIMEFRAMES Virgül Hatası:** `'1d' '4h'` -> `'1d', '4h'` düzeltildi (string concat bug).
- **Volume Threshold:** 1.1x -> 0.5x düşürüldü (daha fazla setup geçecek).

### Added
- **Detaylı Logging:** setup_detector, ob_detector, fvg_detector, volume_analyzer'a loglar eklendi.
- **Reject Logları:** Volume ve R:R reject sebepleri artık loglanıyor.

### Changed
- **5 Dosya Güncellendi:**
  - `okx_service.py` - 10m kaldırıldı
  - `setup_detector.py` - Logging + virgül fix
  - `ob_detector.py` - Threshold 0.5x + logging
  - `fvg_detector.py` - Threshold 0.5x + logging
  - `volume_analyzer.py` - 10m kaldırıldı + logging

## [v2.0.8] - 2025-12-10

### 🔴 Critical Fix
- **get_complete_analysis_data():** Fonksiyon BOŞ dict yerine TÜM verileri döndürüyor.

### Added
- Multi-TF OHLCV: 4h, 2h, 1h, 30m, 15m, 5m, 3m için veri çekimi.
- Volume Analysis: Her TF için spike detection.
- OB/FVG Scanning: scan_order_blocks() ve scan_fair_value_gaps() entegrasyonu.

## [v2.0.7] - 2025-12-09

### Fixed
- **OKX Kontrat Hesabı:** `sz` parametresinin USD yerine kontrat adedi beklemesi sorunu çözüldü. `calculate_contracts` fonksiyonu `USD / (Kontrat Değeri * Fiyat)` formülüyle yenilendi.
- **Service Responsibility:** `okx_service.py` içindeki analiz yükü temizlendi, görev strateji modüllerine devredildi.

### Added
- **Scanner:** `ob_detector.py` ve `fvg_detector.py` dosyalarına grafik tarama yeteneği eklendi.
- **Market Load:** `okx_service.py` başlatılırken tüm coinlerin kontrat büyüklüklerini hafızaya alma özelliği eklendi.

### Changed
- **Setup Dedektörü:** `setup_detector.py` ve `telegram_handlers.py` artık 6 farklı zaman dilimini tarayıp en mantıklı setup'ı seçiyor.

## [v2.0.6] - 2025-12-09

### Changed
- **Hacim Filtresi:** İşlem reddini önlemek için `okx_service.py` içindeki katı hacim şartları esnetildi (Spike 1.5x, Güç 1.1x).
- **Hacim Seçimi:** `volume_analyzer.py` artık 4h-3m arası tüm zaman dilimlerini hiyerarşik olarak tarar (Spike > Ratio).

### Fixed
- **Timeframe:** `15D` anahtar çakışması `10D` (10dk) olarak düzeltildi.
- **Status:** `/status` komutu için `check_connection` metodu eklendi

## [v2.0.5] - 2025-12-09

### Fixed
- **TP/SL:** OKX uyumlu `tpTriggerPx`/`tpOrdPx` (-1) parametreleri uygulandı.
- **Sembol:** Çift slash hatası `_normalize_symbol` ile giderildi.
- **Hedge:** Emirlerde `hedged: True` zorunlu kılındı.

### Added
- **Oto Konfigürasyon:** Açılışta hesap otomatik `Hedge` moduna alınır.
- **Veri:** 2h, 30m, 10m, 5m zaman dilimi desteği eklendi.

## [v2.0.4] - 2025-12-08

### Fixed
- **Execution:** `float` dönüşüm hataları giderildi, loglama artırıldı.
- **Raporlama:** `/scan` işlem açmaz, sadece raporlar.
- **Import:** `is_trading_enabled` modül hatası çözüldü

### Changed
- **Strateji:** Agresif mod (R:R 2.0, Stop 1.0 ATR) aktif edildi.

## [v2.0.3] - 2025-12-05

### Fixed
- **Telegram Loop:** Botun kendi mesajlarını görmezden gelmesi sağlandı.
- **Scan Timeout:** `/scan` arka plana (threading) alındı.
- **OKX Hedge Mode:** `posSide='long'/'short'` uyumu sağlandı.

### Added
- **Leverage:** Config'e `DEFAULT_LEVERAGE = 3` eklendi.
- **Analiz:** `/score` komutuna en kötü 3 performans analizi eklendi.

## [v2.0.2] - 2024-12-04

### 🔧 OKX Order Execution Fix

**Sorun:** Setup var, işlem yok. **Çözüm:** Leverage, posSide ve Kontrat hesabı eksikleri giderildi.

**Düzeltmeler:**
- **okx_service.py:** `set_leverage`, `posSide: 'net'` ve USD->Kontrat çevirici eklendi.
- **Dedektörler:** Setup'lara `direction` alanı eklendi.
- **Handlers:** `execute_trade_for_setup` güncellendi.
### Technical Detail
- Leverage: 10x isolated.
- Mode: One-way.
- Order: Market with TP/SL.

## [v2.0.1] - 2024-12-04

### Changed
- **Sessiz Mod:** `/analyze` ve `/scan` bildirimleri kapatıldı.

## [v2.0.0] - 2024-12-04

## FORK
	[v1.5] ile forklandı. Real markete geçildi

### Added
- **OKX Entegrasyonu:** API, Bakiye, Pozisyon ve Trade komutları (`/stopokx`, `/startokx`).
- **Risk:** Max $100/pozisyon, $50/gün zarar limiti.
