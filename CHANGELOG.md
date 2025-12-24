# T-TARS Trading Bot - CHANGELOG

## v2.4.4 (2025-12-24)

### New
- **Pozisyon Kapanış Bildirimi**: Pozisyon kapandığında Telegram mesajı
- **WIN/LOSS Otomatik Belirleme**: Bitget API'den PnL çekilerek sonuç belirleniyor
- **PnL Takibi**: `get_closed_position_pnl()` fonksiyonu eklendi

### Improved
- **REPLACE mesaj formatı**: Emir güncellendiğinde farklı Telegram mesajı
  - YENİ EMİR → `🟢 YENİ EMİR AÇILDI`
  - REPLACE → `🔄 EMİR GÜNCELLENDİ`
- **Detaylı bilgi**: Eski Order ID ve güncelleme sebebi mesajda gösteriliyor
- **/help kısaltıldı**: Sadece güncel versiyon changelog gösteriliyor

### Fixed
- **/scan market_cache**: `/scan` komutu artık TradingView volume verisini kullanıyor
- **/plan market_cache**: `/plan` komutu da cache'den volume alıyor
- **/status cache info**: Cache entry sayısı gösteriliyor
- **/score WIN/LOSS**: Artık doğru hesaplanıyor (PnL'den)

### Technical
- `bitget_service.py`: `get_order_history_track()`, `get_closed_position_pnl()` eklendi
- `main.py` monitor: PnL çekme + WIN/LOSS + Telegram mesajı
- `telegram_handlers.py`: market_cache + /help kısaltma

---

## v2.4.3 (2025-12-22)

### Fixed
- REPLACE handling düzeltildi (eski order cancel + yeni order)
- Duplicate order sorunu çözüldü

### Changed
- UPDATE_NEEDED → REPLACE (daha net isimlendirme)

---

## v2.4.2 (2025-12-22)

### Fixed
- TP/SL preset format düzeltildi (`presetStopSurplusPrice`, `presetStopLossPrice`)

---

## v2.4.1 (2025-12-21)

### Changed
- Log mesajı versiyonu güncellendi

---

## v2.4.0 (2025-12-21)

### Major Upgrade - Strateji Yeniden Yapılandırması
- **PDC Bias**: Previous Day Candle yönüne göre trade filtresi
- **Fibonacci Zone**: Fiyatın Fibo seviyelerine göre değerlendirme
- **Doji Filter**: Belirsizlik mumu tespiti ve uyarısı
- **OB/FVG Noise Filter**: Düşük kaliteli setup'ları eleme

---

## v2.3.14 (2025-12-20)

### New
- Duplicate order kontrolü (`tracking.check_duplicate_setup`)
- Order açmadan önce aynı coin+direction kontrolü
- Copy Trade API trackingNo desteği

---

## v2.3.11 (2025-12-19)

### Changed
- Expiry logic `tracking_service`'e taşındı
- TF bazlı expiry (5m→2h, diğerleri→4h)

### Removed
- `ORDER_EXPIRY_HOURS` sabit - artık `tracking_service.get_expiry_hours()`

---

## v2.3.8 (2025-12-18)

### Fixed
- `MARKET_CACHE_TTL` 300→1200 (20 dakika) - HTF verisi expire olmuyordu

### Changed
- DRY: Tüm threshold'lar `calculators.py`'den yönetiliyor
