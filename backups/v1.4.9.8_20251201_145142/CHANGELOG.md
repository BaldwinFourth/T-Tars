# T-TARS CHANGELOG

## v1.4.9.8 (2025-12-01)

### Added
- SETUP DETECTED mesajinda setup_id gosteriliyor (#ABC123)
- TP/STOP mesajlarinda dogru hedef fiyat (entry → tp1/tp2/stop)
- /score: Son reset zamani gosteriliyor
- tracking_service: get_last_reset_time() fonksiyonu

### Fixed
- Timeframe kucuk harf (3M → 3m, 5M → 5m)
- Entry = Stop ayni fiyat sorunu cozuldu (target_price kullaniliyor)

### Changed
- Mesaj formati daha kompakt
- /scan TF dagilimi kucuk harf
- /score TF analizi kucuk harf
- reset_all_tracking: timestamp kaydediyor

## v1.4.9.7 (2025-12-01)

### Changed
- SETUP DETECTED mesaji kompakt (detaylar ve AI dusunceler kaldirildi)
- TP HIT mesaji kompakt (tek satir stats)
- format_price() ile detayli fiyatlar (DOGE $0.1431 gibi)
- Duration: "5.1 minutes" → "5.1m"
- Movement: "$0.01" → "$0.0100"

---

## v1.4.9.4 (2025-11-30)

### Changed
- TP1_MULTIPLIER: 2.0 → 3.0

---

## v1.4.9.3 (2025-11-30)

### Fixed
- format_price(): SHIB/DOGE gibi dusuk fiyatli coinler icin dinamik format
- Telegram markdown fix
- storage_service tab hatasi duzeltildi

### Changed
- /scan mesaji: coinler alt alta emoji ile
- /help: "(BTC + SOL)" kaldirildi

---

## v1.4.9.2 (2025-11-29)

### Changed
- /scan mesaji: coinler alt alta 🧪 emoji ile
- CHANGELOG parse "Label: desc" formati destegi

---

## v1.4.9.1 (2025-11-28)

### Added
- volume_confirmed field: OB/FVG bulundugu andaki volume spike kontrolu

---

## v1.4.9 (2025-11-27)

### Changed
- setup_detector.py (689 satir) → 4 module ayrildi:
  - ob_detector.py
  - fvg_detector.py
  - volume_analyzer.py
  - setup_detector.py (orchestrator)

---

## v1.4.8 (2025-11-26)

### Added
- ETH, LTC, BNB, SHIB, DOGE eklendi (7 coin AUTO_SCAN)
- /reset_score komutu

### Fixed
- Entry price/R:R duzeltmeleri
