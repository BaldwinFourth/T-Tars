# T-TARS Trading Bot - CHANGELOG

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
