# T-TARS CHANGELOG

## v1.4.5 (2025-11-26)

### 🔧 Refactored
- **setup_detector.py modülü oluşturuldu** - Tüm setup detection fonksiyonları ayrı dosyaya taşındı
- `detect_trading_setup()` fonksiyonu `app/strategies/setup_detector.py`'ye taşındı
- `check_timeframe_for_setups()` fonksiyonu taşındı
- `detect_all_trading_setups()` fonksiyonu taşındı
- main.py **~600 satır** küçüldü (1662 → ~1060 satır)

### 📁 Güncel Dosya Yapısı
```
app/
├── strategies/
│   ├── __init__.py          ← Updated
│   ├── calculators.py       ← v1.4.4
│   └── setup_detector.py    ← YENİ (v1.4.5)
├── main.py                  ← Küçüldü (~1060 satır)
└── services/
```

### 🎯 setup_detector.py İçeriği
- `detect_trading_setup(pair, market_data)` - Tek TF setup tespiti
- `check_timeframe_for_setups(pair, market_data, timeframe, bias, current_price)` - TF bazlı kontrol
- `detect_all_trading_setups(pair, market_data)` - Multi-TF tarama

### ✅ Avantajlar
- Setup logic'i merkezi yönetim
- main.py daha okunabilir
- OB/FVG detection kolay düzenlenebilir
- Test ve debug kolaylığı

---

## v1.4.4 (2025-11-26)

### 🔧 Refactored
- **calculators.py modülü oluşturuldu** - Tüm katsayılar ve hesaplama fonksiyonları ayrı dosyaya taşındı
- `calculate_setup_strength()` fonksiyonu `app/strategies/calculators.py`'ye taşındı
- `MIN_RR_RATIO` constant olarak tanımlandı

### 📁 Yeni Dosya Yapısı
```
app/
├── strategies/
│   ├── __init__.py
│   └── calculators.py
├── main.py
└── services/
```

---

## v1.4.3 (2025-11-26)

### Added
- **Multi-Timeframe Scan:** 4h → 1h → 15m → 5m → 3m
- **Time Tracking:** created_at, duration_minutes
- **Movement Tracking:** movement_captured_dollars
- **Enhanced Emojis:** TP1 🎯, TP2 🎉🏆, STOP ⛔❌
- **/scan aktif setup listesi:** Tarama sonunda aktif setup'lar gösterilir

### Fixed
- **Balance hesabı:** TP1=breakeven, TP2=profit, STOP=loss
- **Win Rate:** TP1 artık WIN sayılmıyor
- **Dynamic Timeframe:** Hardcoded değil, gerçek TF gösteriliyor

---

## v1.4.2 (2025-11-25)

### Fixed
- Traffic routing fix (--to-latest)
- Tracking service get_all_pending_setups() id/setup_type fix
- deploy.sh traffic yönlendirme eklendi

---

## v1.4.1 (2025-11-24)

### Added
- Setup tracking system
- /score command
- Balance tracking

---

## v1.4.0 (2025-11-23)

### Added
- Multi-chat Telegram support
- Cloud Scheduler integration
- Automatic setup monitoring
