# T-TARS CHANGELOG

## v1.4.7 (2025-11-28)

### 🐛 Fixed - Setup Detection
- **FVG dual TP sistemi eklendi** - tp1, tp2, tp1_price, tp2_price artık FVG'lerde de var
- **Entry price hesabı düzeltildi** - OB/FVG mid-point kullanılıyor
- **R:R hesabı düzeltildi** - current_price yerine entry_price bazlı
- **Tüm tracking field'ları FVG'ye eklendi** - current_price, stop_price, entry_price

### 📊 Değişiklik Detayları
```
# Önceki (yanlış):
entry_zone = FVG zone
risk = |current_price - stop|  ← YANLIŞ
R:R = 38.7  ← Absürt

# Sonraki (doğru):
entry_price = (gap_low + gap_high) / 2  ← Mid-point
risk = |entry_price - stop|  ← DOĞRU
R:R = 1.3 - 2.5  ← Gerçekçi
```

### ✅ Düzeltilen Sorunlar
- SHORT setup'larda stop mevcut fiyatın altında çıkıyordu
- TP1/TP2 N/A görünüyordu (FVG'lerde)
- R:R oranları 30-40 gibi absürt değerler alıyordu

---

## v1.4.6 (2025-11-26)

### 🔧 Refactored
- **telegram_handlers.py modülü oluşturuldu**
- main.py ~650 satır küçüldü (~410 satıra)
- Handler'lar dependency injection ile service'lere erişiyor

---

## v1.4.5 (2025-11-26)

### 🔧 Refactored
- **setup_detector.py modülü oluşturuldu**
- main.py ~600 satır küçüldü
- **storage_service.py** CHANGELOG parse düzeltmesi

---

## v1.4.4 (2025-11-26)

### 🔧 Refactored
- **calculators.py modülü oluşturuldu**
- `calculate_setup_strength()` fonksiyonu taşındı

---

## v1.4.3 (2025-11-26)

### Added
- Multi-Timeframe Scan
- Time & Movement Tracking
- Enhanced Emojis

### Fixed
- Balance hesabı
- Win Rate

---

## v1.4.2 (2025-11-25)

### Fixed
- Traffic routing fix

---

## v1.4.1 (2025-11-24)

### Added
- Setup tracking system
- /score command

---

## v1.4.0 (2025-11-23)

### Added
- Multi-chat Telegram support
- Cloud Scheduler integration
