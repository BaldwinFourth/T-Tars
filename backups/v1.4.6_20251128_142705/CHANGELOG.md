# T-TARS CHANGELOG

## v1.4.6 (2025-11-26)

### 🔧 Refactored
- **telegram_handlers.py modülü oluşturuldu** - Tüm Telegram komut handler'ları ayrı dosyaya taşındı
- main.py **~650 satır** küçüldü (1060 → ~410 satır)
- Handler'lar dependency injection ile service'lere erişiyor

### 📁 Güncel Dosya Yapısı
```
app/
├── handlers/                 ← YENİ KLASÖR
│   ├── __init__.py
│   └── telegram_handlers.py  ← Tüm handle_* fonksiyonları
├── strategies/
│   ├── __init__.py
│   ├── calculators.py
│   └── setup_detector.py
├── main.py                   ← Sadece routes (~410 satır)
└── services/
```

### 🎯 telegram_handlers.py İçeriği
- `init_handlers(telegram, okx, claude, storage, tracking)` - Service injection
- `handle_plan_command(text, chat_id)` - /plan komutu
- `handle_scan_command(chat_id)` - /scan komutu
- `handle_status_command(chat_id)` - /status komutu
- `handle_score_command(chat_id)` - /score komutu
- `handle_help_command(chat_id)` - /help komutu

### ✅ Avantajlar
- main.py sadece routing, çok okunabilir
- Handler logic'i merkezi yönetim
- Test ve debug kolaylığı
- Modüler yapı tamamlandı

---

## v1.4.5 (2025-11-26)

### 🔧 Refactored
- **setup_detector.py modülü oluşturuldu**
- `detect_trading_setup()`, `check_timeframe_for_setups()`, `detect_all_trading_setups()` taşındı
- main.py ~600 satır küçüldü
- **storage_service.py** CHANGELOG parse düzeltmesi

### 🐛 Fixed
- CHANGELOG parse formatı düzeltildi (v1.4.5 format desteği)
- Telegram Markdown karakter temizleme iyileştirildi
- /help mesajından /execute ve /log kaldırıldı

---

## v1.4.4 (2025-11-26)

### 🔧 Refactored
- **calculators.py modülü oluşturuldu**
- `calculate_setup_strength()` fonksiyonu taşındı
- `MIN_RR_RATIO` constant olarak tanımlandı

---

## v1.4.3 (2025-11-26)

### Added
- **Multi-Timeframe Scan:** 4h → 1h → 15m → 5m → 3m
- **Time Tracking:** duration_minutes
- **Movement Tracking:** movement_captured_dollars
- **Enhanced Emojis:** TP1 🎯, TP2 🎉🏆, STOP ⛔❌

### Fixed
- Balance hesabı: TP1=breakeven, TP2=profit, STOP=loss
- Win Rate: TP1 artık WIN sayılmıyor

---

## v1.4.2 (2025-11-25)

### Fixed
- Traffic routing fix (--to-latest)
- Tracking service id/setup_type fix

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
