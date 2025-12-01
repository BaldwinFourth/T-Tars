# T-TARS CHANGELOG

## v1.4.9.6 (2025-12-01)

### Added
- /scan: Timeframe dagilimi gosteriliyor (4H: 5 | 1H: 3 | 5M: 10)
- /score: Timeframe analizi eklendi (her TF icin win rate)
- /score: Aktif setup sayisi ve yuzdesi
- /score: Loss rate yuzdesi

### Fixed
- STOP_MULTIPLIER: 1.5 → 1.0 (R:R 3.0)
- /help: CHANGELOG parse (list → string fix)
- Tracking: Movement dogru hesaplaniyor
- Tracking: format_price() ile dusuk fiyatli coinler
- Tracking: Mesaj formatlari (++0.00% → +0.00%)

### Changed
- /scan: Setup listesinde TF gosteriliyor
- tracking_service: get_aggregate_stats timeframe breakdown
- tracking_service: get_all_pending_setups timeframe breakdown

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
