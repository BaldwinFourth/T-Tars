# T-TARS CHANGELOG

## v2.0.2 - 2024-12-04

### 🔧 OKX Order Execution Fix

**Problem:** Bot setup buluyordu ama OKX'te işlem açamıyordu.

**Kök Nedenler:**
1. Leverage ayarlanmıyordu
2. `posSide` parametresi eksikti (one-way mode için `net` gerekli)
3. Amount hesabı yanlıştı (USD vs kontrat)
4. Setup'larda `direction` field'ı yoktu

**Düzeltmeler:**

- **okx_service.py:**
  - `set_leverage()` fonksiyonu eklendi
  - `posSide: 'net'` eklendi (one-way mode)
  - `calculate_contracts()` fonksiyonu eklendi (USD → kontrat çevirme)
  - `get_contract_size()` fonksiyonu eklendi
  - `place_order_with_tp_sl()` düzeltildi: entry_price parametresi, leverage set

- **ob_detector.py & fvg_detector.py:**
  - `direction` field eklendi: `'LONG'` veya `'SHORT'`

- **telegram_handlers.py:**
  - `execute_trade_for_setup()` düzeltildi
  - Direction artık setup'tan alınıyor
  - entry_price OKX'e geçiriliyor

### Technical Details
- Leverage: 10x (default, isolated margin)
- Position mode: One-way (posSide: 'net')
- Order type: Market with TP/SL
- Amount: Otomatik USD → kontrat çevirme

---

## v2.0.1 - 2024-12-04

### 🔇 Silent Mode

- `/analyze` endpoint sessiz çalışır (Telegram mesajı göndermez)
- SETUP DETECTED mesajları kaldırıldı
- `/scan` OKX gerçek pozisyonlarını gösterir

---

## v2.0.0 - 2024-12-04

### 🚀 OKX Trade Execution

- **YENİ:** OKX API entegrasyonu
- **YENİ:** `/balance` - Hesap bakiyesi
- **YENİ:** `/positions` - Açık pozisyonlar
- **YENİ:** `/stopokx` - Trading durdur
- **YENİ:** `/startokx` - Trading başlat
- Auto-scan: 13 coin desteği
- Risk management: Max $100/position, Max $50/day loss
