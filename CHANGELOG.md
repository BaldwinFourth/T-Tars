# T-TARS Trading Bot - CHANGELOG

## [2.1.2] - 2025-12-11

### Changed
- **Market Order -> Limit Order**: Artik limit emir kullaniliyor
  - Daha dusuk komisyon (Maker fee < Taker fee)
  - Slippage yok (tam istenen fiyattan giris)
  - Setup entry fiyati korunuyor

### Fixed
- **OKX TP/SL Error 51000**: Parameter ordType hatasi duzeltildi
  - Flat parametreler yerine `attachAlgoOrds` array kullaniliyor
  - OKX API v5 standardi uyguland
  - `tpTriggerPxType` ve `slTriggerPxType` eklendi ('last')

### Technical Details
```python
# ESKI (v2.1.1 - Market)
order = exchange.create_order(
    type='market',
    ...
)

# YENI (v2.1.2 - Limit)
order = exchange.create_order(
    type='limit',
    price=entry_price,
    params={
        'attachAlgoOrds': [{
            'tpTriggerPx': str(tp),
            'tpOrdPx': '-1',
            'tpTriggerPxType': 'last',
            'slTriggerPx': str(sl),
            'slOrdPx': '-1',
            'slTriggerPxType': 'last'
        }]
    }
)
```

### Changed Files
- `app/services/okx_service.py`

---

## [2.1.1] - 2025-12-10

### Fixed
- tdMode 'isolated' -> 'cross' (Cross Margin)
- 'hedged' parametresi kaldirildi
- close_position'da da cross mode

---

## [2.1.0] - 2025-12-10

### Added
- Real balance integration
- Detailed /score reporting
- Monitor emoji mapping
