# T-TARS Trading Bot - CHANGELOG

## v1.4.10.2 (2025-12-03)

### Fixed
- **TP1 P/L = $0 SORUNU**: TP1 HIT'te artık partial profit hesaplanıyor
  - TP1: 1R kar ($20 @ 2% risk)
  - TP2: Full profit (TP1 + kalan pozisyondan)
  - Mesajda doğru P/L gösterilecek
- **AUTO-ANALYZE SESSİZ**: `/analyze` endpoint artık SETUP DETECTED mesajı GÖNDERMİYOR
  - Sadece tracking'e kaydeder
  - Telegram'da spam yok
  - `/scan` komutu hala mesaj gönderir (manuel tetikleme)
- **DUPLICATE DETECTION**: Aynı pair + timeframe + direction için aktif (PENDING/TP1) setup varsa yeni oluşturulmaz
- **404 ERROR HANDLING**: Silinmiş dosyalar skip edilir

### Technical Details
- `check_setup_status()`: TP1'de `profit_loss = risk_dollars * 1.0` (partial profit)
- `check_setup_status()`: TP2'de `profit = tp1_profit + tp2_additional` (full profit)
- `/analyze`: `telegram.send_signal()` kaldırıldı, sadece `log_setup()` çağrılır
- `tracking_service.py`: `check_duplicate_setup()` fonksiyonu eklendi
- `log_setup()`: Duplicate varsa `None` döndürür
- Stats artık doğru hesaplanacak (duplicate yok = tutarlı ID'ler)

---

## v1.4.10.1 (2025-12-02)

### Fixed
- Grup komut parsing düzeltildi (`/score@BotName` → `/score`)
- Komutlar `startswith` yerine `==` ile karşılaştırılıyor

---

## v1.4.10.0 (2025-12-02)

### Fixed
- `/reset_score` komut sıralaması düzeltildi
- `entry_price` parametresi `log_setup`'a eklendi
- SETUP DETECTED mesajı kısa formata dönüştürüldü

---

## v1.4.9.9 (2025-12-02)

### Fixed
- SHORT pozisyonlarda TP1 hesaplaması düzeltildi
- `entry_price` ve `current_price` ayrımı yapıldı
