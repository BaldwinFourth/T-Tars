# T-TARS CHANGELOG

## v1.4.9.1 (2025-11-29)

### 🐛 Fixed - Volume Spike Kontrolü
- **Sorun:** Genel volume spike kontrolü anlık değişen market koşullarını kullanıyordu
- **Çözüm:** OB/FVG'nin kendi `volume_confirmed` field'ı kullanılıyor

### 🔧 Changed
- `ob_detector.py`: `ob['volume_confirmed']` kontrolü eklendi
- `fvg_detector.py`: `fvg['volume_confirmed']` kontrolü eklendi  
- `setup_detector.py`: Genel `has_volume_spike()` kontrolü kaldırıldı

### 📊 Mantık Değişikliği
```
ÖNCE:
1. Market'tan güncel volume spike al
2. Spike yoksa setup arama (❌ yanlış - market değişmiş olabilir)

SONRA:
1. OB/FVG bulunduğu andaki volume_confirmed kullan (✅ doğru)
2. Her OB/FVG kendi volume bilgisini taşıyor
```

---

## v1.4.9 (2025-11-28)

### 🔧 Refactored
- ob_detector.py, fvg_detector.py, volume_analyzer.py ayrıldı
- setup_detector.py sadeleştirildi

---

## v1.4.8 (2025-11-28)

### ✨ Added
- Yeni Coinler: ETH, LTC, BNB, SHIB, DOGE
- /reset_score komutu

---

## v1.4.7 (2025-11-28)

### 🐛 Fixed
- FVG dual TP sistemi
- Entry price, R:R düzeltmeleri

---

## v1.4.0 - v1.4.6

- Tracking, multi-chat, refactoring
