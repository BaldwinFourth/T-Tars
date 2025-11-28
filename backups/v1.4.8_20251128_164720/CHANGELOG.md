# T-TARS CHANGELOG

## v1.4.8 (2025-11-28)

### ✨ Added
- **Yeni Coinler (AUTO_SCAN):** ETH, LTC, BNB, SHIB, DOGE eklendi (toplam 7 coin)
- **/reset_score komutu:** Tüm istatistikleri sıfırla (gizli komut - /help'te yok)

### 🔧 Fixed - Mesaj Formatları
- **TP1 emoji:** `🎯 TP1 HIT! 💰💰💰`
- **TP2 emoji:** `🎉 TP2 HIT - FULL WIN! 🎉🎉🎉`
- **Timeframe gösterimi:** Her TP/STOP mesajında timeframe bilgisi
- **Entry price:** `setup['current_price']` → `entry_price` (doğru değer)
- **Movement text:** "captured" kelimesi kaldırıldı

### 📊 AUTO_SCAN_PAIRS (v1.4.8)
```python
AUTO_SCAN_PAIRS = [
    'BTC/USDT:USDT',
    'ETH/USDT:USDT',
    'SOL/USDT:USDT',
    'LTC/USDT:USDT',
    'BNB/USDT:USDT',
    'SHIB/USDT:USDT',
    'DOGE/USDT:USDT'
]
```

---

## v1.4.7 (2025-11-28)

### 🐛 Fixed - Setup Detection
- FVG dual TP sistemi eklendi
- Entry price = mid-point hesabı
- R:R formülü düzeltmesi
- Constants import (STOP_MULTIPLIER, TP1_MULTIPLIER, TP2_MULTIPLIER)

---

## v1.4.6 (2025-11-26)

### 🔧 Refactored
- telegram_handlers.py modülü oluşturuldu
- main.py ~650 satır küçüldü

---

## v1.4.5 (2025-11-26)

### 🔧 Refactored
- setup_detector.py modülü oluşturuldu

---

## v1.4.4 (2025-11-26)

### 🔧 Refactored
- calculators.py modülü oluşturuldu

---

## v1.4.3 (2025-11-26)

### Added
- Multi-Timeframe Scan
- Time & Movement Tracking

---

## v1.4.2 - v1.4.0

- Traffic routing, tracking system, multi-chat support
