# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v2.4.0
=============================
Trading setup orchestrator with PDC bias + Fibo zone filtering.

v2.4.0:
- NEW: PDC bias belirleme (yeşil=LONG, kırmızı=SHORT)
- NEW: Fibo zone filtreleme (OB: %70-90, FVG: %60-90)
- NEW: Doji reversal kontrolü
- NEW: scan_order_blocks ve scan_fair_value_gaps'a atr/current_price geçiliyor
- CHANGED: Import'lara calculate_pdc_bias, calculate_fibo_zones, is_in_ob_zone, is_in_fvg_zone eklendi

v2.1.0:
- TIMEFRAMES Config'den alınıyor
"""

import logging
from app.config import Config
from app.strategies.ob_detector import detect_ob_long, detect_ob_short, scan_order_blocks
from app.strategies.fvg_detector import detect_fvg_long, detect_fvg_short, scan_fair_value_gaps
from app.strategies.volume_analyzer import select_best_volume
from app.strategies.calculators import (
    calculate_pdc_bias,
    calculate_fibo_zones,
    is_in_ob_zone,
    is_in_fvg_zone
)

logger = logging.getLogger(__name__)

# Config'den al - bitget_service ile tutarlı
TIMEFRAMES = Config.TIMEFRAMES  # ['4h', '1h', '30m', '15m', '5m']


def detect_trading_setup(pair, market_data):
    """
    Otomatik tarama için - Tek setup döndürür.
    
    v2.4.0: PDC bias + Fibo zone + Doji kontrolü
    """
    try:
        if not market_data:
            logger.warning(f"⚠️ {pair}: Market data boş!")
            return False
        
        # v2.4.0: PDC bazlı bias belirleme
        daily_ohlcv = market_data.get('daily_ohlcv', [])
        if daily_ohlcv and len(daily_ohlcv) >= 5:
            pdc_result = calculate_pdc_bias(daily_ohlcv)
            bias = pdc_result['bias']
            bias_str = 'bullish' if bias == 'LONG' else 'bearish'
            pdc = pdc_result['pdc']
            doji_warning = pdc_result['doji_warning']
            reversal_mode = pdc_result['reversal_mode']
            
            # Fibo zone hesapla
            fibo_data = calculate_fibo_zones(pdc, bias)
            
            if doji_warning:
                logger.info(f"⚠️ {pair}: Doji uyarısı! Reversal mode: {reversal_mode}")
        else:
            # Fallback: Eski yöntem
            pdc = market_data.get('previous_day', {})
            bias = 'LONG' if pdc.get('candle_type') == 'green' else 'SHORT'
            bias_str = 'bullish' if bias == 'LONG' else 'bearish'
            fibo_data = None
            doji_warning = False
            reversal_mode = False
        
        current_price = market_data.get('current_price', 0)
        
        # Volume verisini sözlük olarak gönder
        volume_data, timeframe = select_best_volume(market_data.get('volume', {}))
        
        # Seçilen TF'ye göre OB/FVG al
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        atr = market_data['atr'].get(timeframe, 0)
        
        # v2.4.0: Fibo zone filtresi
        if fibo_data:
            obs = [ob for ob in obs if is_in_ob_zone(ob.get('mid', (ob['high']+ob['low'])/2), fibo_data)]
            fvgs = [fvg for fvg in fvgs if is_in_fvg_zone(fvg.get('mid', (fvg['high']+fvg['low'])/2), fibo_data)]
            logger.debug(f"📐 {pair}: Fibo filtre sonrası OB={len(obs)}, FVG={len(fvgs)}")
        
        logger.info(f"🔍 {pair}: TF={timeframe}, OB={len(obs)}, FVG={len(fvgs)}, Bias={bias}, Doji={doji_warning}")
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            logger.debug(f"📦 {pair}: OB kontrol - Type={ob['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and ob['type'] == 'bullish':
                result = detect_ob_long(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    logger.info(f"✅ {pair}: OB LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                result = detect_ob_short(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    logger.info(f"✅ {pair}: OB SHORT setup bulundu!")
                return result
        
        # FVG Kontrol
        if len(fvgs) > 0:
            fvg = fvgs[0]
            logger.debug(f"📊 {pair}: FVG kontrol - Type={fvg['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and fvg['type'] == 'bullish':
                result = detect_fvg_long(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    logger.info(f"✅ {pair}: FVG LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                result = detect_fvg_short(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    logger.info(f"✅ {pair}: FVG SHORT setup bulundu!")
                return result
        
        logger.debug(f"ℹ️ {pair}: Setup bulunamadı (Bias uyumsuz veya OB/FVG yok)")
        return False
        
    except Exception as e:
        logger.error(f"❌ {pair} Setup detection error: {e}")
        return False


def check_timeframe(pair, market_data, timeframe, bias, current_price, fibo_data=None):
    """
    Belirli bir timeframe için setup kontrol et.
    
    v2.4.0: Fibo zone filtresi eklendi
    """
    setups = []
    try:
        volume = market_data['volume'].get(timeframe, {})
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        atr = market_data['atr'].get(timeframe, 0)
        
        # v2.4.0: Fibo zone filtresi
        if fibo_data:
            obs = [ob for ob in obs if is_in_ob_zone(ob.get('mid', (ob['high']+ob['low'])/2), fibo_data)]
            fvgs = [fvg for fvg in fvgs if is_in_fvg_zone(fvg.get('mid', (fvg['high']+fvg['low'])/2), fibo_data)]
        
        logger.debug(f"🕐 {pair} [{timeframe}]: OB={len(obs)}, FVG={len(fvgs)}, Vol={volume.get('spike_ratio', 0):.2f}x")
        
        bias_str = 'bullish' if bias == 'LONG' else 'bearish'
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            if bias_str == 'bullish' and ob['type'] == 'bullish':
                s = detect_ob_long(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: OB LONG found!")
                    setups.append(s)
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                s = detect_ob_short(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: OB SHORT found!")
                    setups.append(s)
        
        # FVG Kontrol
        if len(fvgs) > 0:
            fvg = fvgs[0]
            if bias_str == 'bullish' and fvg['type'] == 'bullish':
                s = detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: FVG LONG found!")
                    setups.append(s)
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                s = detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: FVG SHORT found!")
                    setups.append(s)
        
        return setups
        
    except KeyError as e:
        logger.error(f"❌ {pair} [{timeframe}]: Missing data key: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ {pair} [{timeframe}]: Check error: {e}")
        return []


def scan_setups(pair, market_data):
    """
    Tüm timeframe'leri tarayarak setup bul.
    
    v2.4.0: PDC bias + Fibo zone + Doji kontrolü
    """
    try:
        if not market_data:
            logger.warning(f"⚠️ {pair}: scan_setups - Market data boş!")
            return []
        
        # v2.4.0: PDC bazlı bias belirleme
        daily_ohlcv = market_data.get('daily_ohlcv', [])
        if daily_ohlcv and len(daily_ohlcv) >= 5:
            pdc_result = calculate_pdc_bias(daily_ohlcv)
            bias = pdc_result['bias']
            pdc = pdc_result['pdc']
            doji_warning = pdc_result['doji_warning']
            reversal_mode = pdc_result['reversal_mode']
            
            # Fibo zone hesapla
            fibo_data = calculate_fibo_zones(pdc, bias)
            
            if doji_warning:
                logger.info(f"⚠️ {pair}: Doji uyarısı! Count={pdc_result['doji_count']}, Reversal={reversal_mode}")
        else:
            # Fallback: Eski yöntem
            pdc = market_data.get('previous_day', {})
            bias = 'LONG' if pdc.get('candle_type') == 'green' else 'SHORT'
            fibo_data = None
            doji_warning = False
            reversal_mode = False
        
        current_price = market_data.get('current_price', 0)
        
        logger.info(f"🔎 {pair}: Scan başladı - Bias={bias}, Price=${current_price:.2f}, TFs={len(TIMEFRAMES)}, Doji={doji_warning}")
        
        all_setups = []
        
        for tf in TIMEFRAMES:
            s = check_timeframe(pair, market_data, tf, bias, current_price, fibo_data)
            if s:
                # Doji bilgisini ekle
                for setup in s:
                    setup['doji_warning'] = doji_warning
                    setup['reversal_mode'] = reversal_mode
                all_setups.extend(s)
        
        if all_setups:
            logger.info(f"🎯 {pair}: Toplam {len(all_setups)} setup bulundu!")
        else:
            logger.debug(f"ℹ️ {pair}: Setup bulunamadı")
        
        return all_setups
        
    except Exception as e:
        logger.error(f"❌ {pair}: Scan error: {e}")
        return []


# Alias'lar (geriye uyumluluk)
detect_all_trading_setups = scan_setups
check_timeframe_for_setups = check_timeframe
