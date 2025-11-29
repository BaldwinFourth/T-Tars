# T-TARS CHANGELOG

## v1.4.9.3 (2025-11-29)

### ✨ SHIB/DOGE Düşük Fiyat Desteği
- **format_price():** Dinamik fiyat formatlama fonksiyonu
- **Sorun:** SHIB $0.00002 → $0.00 gösteriliyordu
- **Çözüm:** Fiyata göre otomatik ondalık basamak seçimi

### 🔧 Format Kuralları
- ✅ Fiyat < $0.0001 → 8 ondalık ($0.00002345)
- ✅ Fiyat < $0.01 → 6 ondalık
- ✅ Fiyat < $1 → 4 ondalık
- ✅ Fiyat >= $100 → 2 ondalık ($95,000.50)

---

## v1.4.9.2 (2025-11-29)

### ✨ Telegram UI Düzeltmeleri
- **/scan mesajı:** Coinler alt alta 🧪 emoji ile
- **/help mesajı:** "(BTC + SOL)" kaldırıldı
- **CHANGELOG parse:** "Label: desc" formatı desteği

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

## v1.4.0 - v1.4.7

- Tracking, multi-chat, refactoring, FVG dual TP
