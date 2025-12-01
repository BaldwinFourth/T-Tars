# T-TARS CHANGELOG

## v1.4.9.5 (2025-12-01)

### Fixed
- STOP_MULTIPLIER: 1.5 → 1.0 (ATR zaten volatilite olcuyor, ekstra carpan gereksiz)
- R:R hesabi duzeltildi: Artik 3.0/1.0 = 3.0 (eskiden 3.0/1.5 = 2.0)
- /help: CHANGELOG parse fonksiyonu geri eklendi

### Added
- Log'da coin ismi gorunuyor (BTC OB LONG R:R: 2.5 gibi)

### Changed
- ob_detector.py: pair parametresi eklendi
- fvg_detector.py: pair parametresi eklendi

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
