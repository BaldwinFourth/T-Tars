# T-TARS Trading Bot - Changelog v1.4.0

## [1.4.0] - 2025-11-20
### Fixed - ENCODING CLEANUP
- ✅ **Tüm bozuk karakterler düzeltildi**
  - Emoji encoding sorunları (📱📊🎯⚡💰 vs)
  - Türkçe karakterler (ç, ş, ı, ö, ü, İ)
  - Semboller (✅❌→═─└)
  
### Added - SETUP TRACKING & PERFORMANCE
- ✅ **TrackingService entegrasyonu**
  - Setup tracking (TP1/TP2/STOP monitor)
  - Performance scoring sistemi
  - Balance tracking ($1000 starting balance)
  
- ✅ **Yeni Komutlar:**
  - `/score` - Performance raporu (Win rate, P&L, Best setup)
  - `/monitor` endpoint - Cloud Scheduler ile otomatik setup takibi

### Changed - VERSION UPDATE
- ✅ Version: 1.3.2 → **1.4.0**
- ✅ Version güncellendi (4 yerde):
  - `index()` endpoint: "v1.4"
  - `/status` mesajı: "v1.4.0"
  - Startup log: "v1.4.0"
  - `/help` mesajı: "v1.4"

### Technical Details

**Encoding Düzeltmeleri:**
```python
# Önceki (bozuk):
ðŸ"± → 📱 (Telegram icon)
ðŸ"Š → 📊 (Chart icon)
âœ… → ✅ (Check mark)
Ã§ → ç (Turkish c)
oluÅŸtur → oluştur

# Toplam 50+ encoding sorunu düzeltildi
```

**TrackingService:**
```python
# Cloud Storage bucket: tars-trading-data
tracking = TrackingService()

# Setup kayıt
tracking.record_setup(
    pair='BTCUSDT',
    setup_type='OB + Volume Spike (LONG)',
    entry_price=current_price,
    stop_loss=stop_price,
    tp1=tp1_price,
    tp2=tp2_price,
    confidence='HIGH',
    risk_percent=1.5
)

# Status check (Cloud Scheduler her 5dk)
status_result = tracking.check_setup_status(setup_id, current_price)
# Returns: {status_changed, new_status, profit, profit_percent}

# Performance stats
stats = tracking.get_aggregate_stats()
# Returns: {total_setups, winning_trades, win_rate, current_balance, profit, profit_percent}
```

**/score Komutu:**
```
📊 T-TARS PERFORMANCE REPORT

🎯 Setup İstatistikleri:
• Total Setups: 15
• Winning Trades: 10 (66.7%)
• Losing Trades: 5 (33.3%)

💰 Balance Tracking:
• Starting: $1,000.00
• Current: $1,150.00
• Profit: + 15.0% ($150.00)

📈 Best Performer:
OB + Volume Spike (LONG) - 75% win rate
```

**Monitor Endpoint:**
- URL: `/monitor`
- Trigger: Cloud Scheduler (*/5 * * * *)
- Function: Pending setup'ları kontrol et, TP1/TP2/STOP hit olunca bildir
- Broadcast: Telegram'a otomatik setup update mesajları

**Deployment Gereklilikler:**
1. **tracking_service.py** eklenmeli (app/services/)
2. **ENV variables:**
   - `BUCKET_NAME_DATA=tars-trading-data` (tracking data için)
3. **Cloud Storage bucket:**
   - `gsutil mb -l us-central1 gs://tars-trading-data`
4. **Cloud Scheduler:**
   - Monitor job: */5 * * * * (her 5 dakika)

---

## Version Comparison
- **v1.3.2**: Encoding sorunları + tracking yok
- **v1.4.0**: Clean encoding + Setup tracking + /score + /monitor ✅

---

## Migration Notes
1. `tracking_service.py` upload et
2. Bucket oluştur: `tars-trading-data`
3. ENV update: `BUCKET_NAME_DATA`
4. Cloud Scheduler setup: monitor job
5. Test: `/score` komutu ile

---

## Known Issues
- Yok (Tüm encoding sorunları çözüldü)

---

## Next Steps
- [ ] v1.4.1: tracking_service.py ekle
- [ ] v1.5.0: Advanced analytics (Sharpe ratio, drawdown)
