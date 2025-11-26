# T-TARS CHANGELOG

## v1.4.4 (2025-11-26)

### 🔧 Refactored
- **calculators.py modülü oluşturuldu** - Tüm katsayılar ve hesaplama fonksiyonları ayrı dosyaya taşındı
- `calculate_setup_strength()` fonksiyonu `app/strategies/calculators.py`'ye taşındı
- `MIN_RR_RATIO` constant olarak tanımlandı (hardcoded 2.0 yerine)
- main.py'den import ile kullanılıyor

### 📁 Yeni Dosya Yapısı
```
app/
├── strategies/           ← YENİ KLASÖR
│   ├── __init__.py
│   └── calculators.py    ← Katsayılar burada
├── main.py              ← Import eklendi
└── services/
```

### 🎯 calculators.py İçeriği
- `STOP_MULTIPLIER = 1.5`
- `TP1_MULTIPLIER = 2.0`
- `TP2_MULTIPLIER = 3.5`
- `MIN_RR_RATIO = 2.0`
- `VOLUME_EXCELLENT/GOOD/MEDIUM/LOW`
- `calculate_setup_strength()`
- `calculate_rr()`
- `get_volume_score()`
- `get_rr_score()`
- `is_valid_setup()`

### ✅ Avantajlar
- Fine-tuning için tek dosya düzenle
- main.py küçüldü (~33 satır azaldı)
- Katsayılar merkezi yönetim
- Kolay test ve debug

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
