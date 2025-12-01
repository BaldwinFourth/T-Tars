# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v1.4.9.5
==============================
Trading setup orchestrator.
OB, FVG, Volume modüllerini import eder.

v1.4.9.5:
- pair parametresi OB/FVG detector'lara geçiriliyor (log'da coin ismi görünsün)

v1.4.9.1:
- Genel volume spike kontrolü kaldırıldı
- OB/FVG'nin kendi volume_confirmed field'ı kullanılıyor
"""

import logging
from app.strategies.ob_detector import detect_ob_long, detect_ob_short
from app.strategies.fvg_detector import detect_fvg_long, detect_fvg_short
from app.strategies.volume_analyzer import select_best_volume

logger = logging.getLogger(__name__)

# Timeframe listesi
TIMEFRAMES = ['4h', '1h', '15m', '5m', '3m']


def detect_trading_setup(pair, market_data):
    """
    Otomatik 3dk tarama için - Tek setup döndürür
    5m/3m timeframe'leri kontrol eder
    
    Returns:
        dict veya False
    """
    try:
        pdc = market_data['previous_day']
        bias = 'bullish' if pdc['candle_type'] == 'green' else 'bearish'
        current_price = market_data['current_price']
        
        # Volume seç (info için)
        volume_5m = market_data['volume']['5m']
        volume_3m = market_data['volume']['3m']
        volume, timeframe = select_best_volume(volume_5m, volume_3m)
        
        # OB ve FVG data
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        
        # ATR
        atr = market_data['atr'].get(timeframe, market_data['atr']['15m'])
        
        logger.info(f"🔍 {pair}: OB={len(obs)}, FVG={len(fvgs)}, bias={bias}, TF={timeframe}")
        
        # OB Setup kontrol (volume_confirmed OB içinde kontrol edilecek)
        if len(obs) > 0:
            ob = obs[0]
            if bias == 'bullish' and ob['type'] == 'bullish':
                setup = detect_ob_long(ob, volume, atr, timeframe, current_price, pair)
                if setup:
                    return setup
            elif bias == 'bearish' and ob['type'] == 'bearish':
                setup = detect_ob_short(ob, volume, atr, timeframe, current_price, pair)
                if setup:
                    return setup
        
        # FVG Setup kontrol (volume_confirmed FVG içinde kontrol edilecek)
        if len(fvgs) > 0:
            fvg = fvgs[0]
            if bias == 'bullish' and fvg['type'] == 'bullish':
                setup = detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair)
                if setup:
                    return setup
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                setup = detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair)
                if setup:
                    return setup
        
        return False
        
    except Exception as e:
        logger.error(f"Setup detection error: {e}")
        return False


def check_timeframe(pair, market_data, timeframe, bias, current_price):
    """
    Belirli timeframe'de setup kontrol et
    
    Returns:
        list: Setup listesi (boş olabilir)
    """
    setups = []
    
    try:
        volume = market_data['volume'].get(timeframe, {})
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        
        # ATR mapping
        atr = market_data['atr'].get(timeframe, market_data['atr'].get('15m', 0))
        
        # Debug log
        logger.info(f"📊 {pair} {timeframe.upper()}: OB={len(obs)}, FVG={len(fvgs)}, bias={bias}")
        
        # OB Setup kontrol (volume_confirmed OB içinde)
        if len(obs) > 0:
            ob = obs[0]
            if bias == 'bullish' and ob['type'] == 'bullish':
                setup = detect_ob_long(ob, volume, atr, timeframe, current_price, pair)
                if setup:
                    logger.info(f"✅ {pair} {timeframe.upper()} LONG OB R:R: {setup['rr_ratio']:.2f}")
                    setups.append(setup)
            elif bias == 'bearish' and ob['type'] == 'bearish':
                setup = detect_ob_short(ob, volume, atr, timeframe, current_price, pair)
                if setup:
                    logger.info(f"✅ {pair} {timeframe.upper()} SHORT OB R:R: {setup['rr_ratio']:.2f}")
                    setups.append(setup)
        
        # FVG Setup kontrol (volume_confirmed FVG içinde)
        if len(fvgs) > 0:
            fvg = fvgs[0]
            if bias == 'bullish' and fvg['type'] == 'bullish':
                setup = detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair)
                if setup:
                    logger.info(f"✅ {pair} {timeframe.upper()} LONG FVG R:R: {setup['rr_ratio']:.2f}")
                    setups.append(setup)
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                setup = detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair)
                if setup:
                    logger.info(f"✅ {pair} {timeframe.upper()} SHORT FVG R:R: {setup['rr_ratio']:.2f}")
                    setups.append(setup)
        
        return setups
        
    except Exception as e:
        logger.error(f"Error checking {timeframe} setups: {e}")
        return []


def scan_setups(pair, market_data):
    """
    TÜM timeframe'leri tara - /scan için
    
    Returns:
        list: Tüm setup'lar
    """
    try:
        pdc = market_data['previous_day']
        bias = 'bullish' if pdc['candle_type'] == 'green' else 'bearish'
        current_price = market_data['current_price']
        
        all_setups = []
        
        logger.info(f"🔍 {pair}: Scanning {len(TIMEFRAMES)} timeframes (bias: {bias})")
        
        for timeframe in TIMEFRAMES:
            setups_in_tf = check_timeframe(pair, market_data, timeframe, bias, current_price)
            if setups_in_tf:
                logger.info(f"✅ {pair} {timeframe.upper()}: {len(setups_in_tf)} setup(s) found")
                all_setups.extend(setups_in_tf)
            else:
                logger.info(f"ℹ️ {pair} {timeframe.upper()}: No setup")
        
        logger.info(f"📊 {pair}: Total {len(all_setups)} setup(s) found across all timeframes")
        return all_setups
        
    except Exception as e:
        logger.error(f"❌ Multi-timeframe scan error for {pair}: {e}")
        return []


# Backward compatibility - eski isimler de çalışsın
detect_all_trading_setups = scan_setups
check_timeframe_for_setups = check_timeframe
