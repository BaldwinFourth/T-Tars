# T-TARS Trading Bot - Changelog

## [1.4.2] - 2025-11-24

### Fixed - MONITOR KEY MISMATCH
- ✅ **get_all_pending_setups() Field Fix**
  - Önce: `setup_id` dönüyordu, main.py `id` bekliyordu
  - Şimdi: Hem `id` hem `setup_id` dönüyor
  - Monitor artık setup'ları doğru takip ediyor

- ✅ **setup_type Field Eklendi**
  - Önce: `setup_type` dönmüyordu
  - Şimdi: Her pending setup'ta `setup_type` mevcut
  - Telegram bildirimleri tam bilgi içeriyor

### Added - RESET FUNCTIONALITY
- ✅ **reset_all_tracking() Fonksiyonu**
  - Tüm tracking verilerini sıfırlama
  - Cloud Storage'daki setup'ları temizleme
  - `/reset_score` komutu için altyapı hazır

### Technical Details

**Değiştirilen Dosya:** `tracking_service.py`

**get_all_pending_setups() - Önce:**
```python
pending_setups.append({
    'setup_id': setup['setup_id'],
    'pair': setup['pair'],
    # ❌ 'id' eksik
    # ❌ 'setup_type' eksik
})
```

**get_all_pending_setups() - Şimdi:**
```python
pending_setups.append({
    'id': setup['setup_id'],           # ✅ Eklendi
    'setup_id': setup['setup_id'],
    'pair': setup['pair'],
    'setup_type': setup['setup_type'], # ✅ Eklendi
    'current_price': setup['current_price'],
    'tp1_price': setup['tp1_price'],
    'tp2_price': setup['tp2_price'],
    'stop_price': setup['stop_price'],
    'status': setup['status']
})
```

### Impact
- Monitor endpoint artık çalışıyor
- TP1/TP2/STOP hit'leri Telegram'a bildirilecek
- Win/Loss tracking aktif

---

## [1.4.1] - 2025-11-22

### Fixed
- ✅ ATR Timeframe Fix (15m → 5m/3m)
- ✅ Dual TP System (TP1 + TP2)
- ✅ Tracking Integration
- ✅ UTF-8 Encoding (Turkish chars)

---

## [1.4.0] - 2025-11-21

### Added
- ✅ TrackingService entegrasyonu
- ✅ /score komutu
- ✅ Performance tracking

---

📊 **T-TARS v1.4.2** | Monitor Fix + Reset Function ✅
