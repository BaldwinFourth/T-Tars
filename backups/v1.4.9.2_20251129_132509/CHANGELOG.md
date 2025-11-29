# T-TARS CHANGELOG

## v1.4.9.2 (2025-11-29)

### ✨ Telegram UI Düzeltmeleri
- **/scan mesajı:** Coinler alt alta emoji ile listeleniyor
- **/help mesajı:** "(BTC + SOL)" kaldırıldı
- **CHANGELOG parse:** "Label: desc" formatı desteği

### 🔧 Düzeltilen Formatlar
- ✅ /scan: 7 coin alt alta gösteriliyor
- ✅ /help: Temiz görünüm
- ✅ Yenilikler: Doğru parse ediliyor

---

## v1.4.9.1 (2025-11-29)

### 🐛 Fixed
- **Sorun:** Volume spike anlık değişiyordu
- **Çözüm:** OB/FVG volume_confirmed kullanılıyor

---

## v1.4.9 (2025-11-28)

### 🔧 Refactored
- ✅ ob_detector.py ayrıldı
- ✅ fvg_detector.py ayrıldı
- ✅ volume_analyzer.py ayrıldı

---

## v1.4.8 (2025-11-28)

### ✨ Added
- ✅ Yeni coinler: ETH, LTC, BNB, SHIB, DOGE
- ✅ /reset_score komutu

---

## v1.4.7 (2025-11-28)

### 🐛 Fixed
- ✅ FVG dual TP sistemi
- ✅ Entry price mid-point

---

## v1.4.0 - v1.4.6

- Tracking, multi-chat, refactoring
