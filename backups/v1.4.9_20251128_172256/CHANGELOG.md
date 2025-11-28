# T-TARS CHANGELOG

## v1.4.9 (2025-11-28)

### 🔧 Refactored - Kod Organizasyonu
- **ob_detector.py** oluşturuldu - OB LONG/SHORT detection (~150 satır)
- **fvg_detector.py** oluşturuldu - FVG LONG/SHORT detection (~150 satır)
- **volume_analyzer.py** oluşturuldu - Volume spike analizi (~100 satır)
- **setup_detector.py** sadeleştirildi - Orchestrator (~150 satır)

### 📁 Yeni Yapı
```
app/strategies/
├── __init__.py          # Export'lar
├── calculators.py       # Katsayılar (v1.4.4)
├── ob_detector.py       # 🆕 OB LONG + SHORT
├── fvg_detector.py      # 🆕 FVG LONG + SHORT
├── volume_analyzer.py   # 🆕 Volume spike
└── setup_detector.py    # Orchestrator (küçüldü)
```

### 🔄 Fonksiyon İsimleri
- `detect_all_trading_setups()` → `scan_setups()` (eski isim de çalışır)
- `check_timeframe_for_setups()` → `check_timeframe()` (eski isim de çalışır)
- `detect_trading_setup()` → değişmedi (otomatik 3dk tarama)

### ✅ Avantajlar
- Kod tekrarı kaldırıldı
- Her dosya tek sorumluluğa sahip
- Kolay debug ve test
- Gelecek genişlemeler için hazır

---

## v1.4.8 (2025-11-28)

### ✨ Added
- Yeni Coinler (AUTO_SCAN): ETH, LTC, BNB, SHIB, DOGE
- /reset_score komutu (gizli)

### 🔧 Fixed
- TP1/TP2 emoji düzeltmesi
- Timeframe gösterimi
- Entry price düzeltmesi

---

## v1.4.7 (2025-11-28)

### 🐛 Fixed
- FVG dual TP sistemi
- Entry price = mid-point
- R:R formülü düzeltmesi

---

## v1.4.6 (2025-11-26)

### 🔧 Refactored
- telegram_handlers.py modülü

---

## v1.4.5 (2025-11-26)

### 🔧 Refactored
- setup_detector.py modülü

---

## v1.4.4 (2025-11-26)

### 🔧 Refactored
- calculators.py modülü

---

## v1.4.0 - v1.4.3

- Multi-chat, tracking, balance fix
