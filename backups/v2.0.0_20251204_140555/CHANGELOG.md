# T-TARS Changelog

## v2.0.0 (2025-12-04)

### 🚀 MAJOR: OKX API Entegrasyonu

**Yeni Komutlar:**
- `/balance` - OKX hesap bakiyesi
- `/positions` - Açık pozisyonları listele
- `/stopokx` - Trading durdur (yeni pozisyon açmaz)
- `/startokx` - Trading başlat

**Yeni Coinler (13 toplam):**
- XRP, AVAX, TRUMP, JUP, PEPE, TRX eklendi
- Mevcut: BTC, ETH, SOL, BNB, LTC, SHIB, DOGE

**Score Geliştirmeleri:**
- Top 3 Timeframe (win rate'e göre) 🥇🥈🥉
- Top 3 Coin (win rate'e göre) 🥇🥈🥉

**Status Geliştirmeleri:**
- OKX API durumu (bağlantı + bakiye)
- Trading durumu (AKTİF/DURDURULDU)

**Kaldırılanlar:**
- Beta group desteği (T-Tars Watcher)
- `broadcast()` - sadece tek chat'e gönderim

### Dosya Değişiklikleri:
- `main.py` - Yeni komut routing
- `telegram_handlers.py` - 4 yeni komut handler
- `telegram_service.py` - broadcast kaldırıldı
- `tracking_service.py` - coin_breakdown eklendi
- `config.py` - OKX ENV, AUTO_SCAN_PAIRS genişletildi
- `okx_service.py` - Trade execution, account management

### ENV Variables (Yeni):
```
OKX_API_KEY=xxx
OKX_SECRET_KEY=xxx
OKX_PASSPHRASE=xxx
OKX_DEMO_MODE=false
```

---

## v1.4.10.3 (2025-12-04)

### Fixed
- TP1 stats: PARTIAL_WIN artık winning olarak sayılıyor
- /score: TP1 hit olan işlemler Win'e dahil

---

## v1.4.10.2 (2025-12-03)

### Fixed
- Duplicate setup detection
- /analyze sessiz mod (mesaj göndermez)
- 404 error handling

---

## v1.4.10.1 (2025-12-03)

### Fixed
- Grup chatlerinde komut parsing (@BotName)
