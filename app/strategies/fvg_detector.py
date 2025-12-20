# -*- coding: utf-8 -*-
"""
T-TARS FVG Detector v2.3.11
===========================
Fair Value Gap setup detection (Scanning + Validation)

v2.3.11:
- CHANGED: calculate_setup_strength() 3 parametre (confidence kaldırıldı)
- Bu sayede circular logic sorunu çözüldü

v2.3.10:
- FIX: Return dict'e volume_spike_ratio ve fvg_strength eklendi

v2.3.8:
- CHANGED: VOLUME_THRESHOLD kaldırıldı → calculators.VOLUME_TRADEABLE_MIN (DRY)

Formül (Kadircan):
Gap Size = Gap High - Gap Low
Entry = Gap içinde (genelde mid-point)
LONG:  Stop = Entry - ATR, TP1 = Entry + 2*ATR, TP2 = Entry + 4*ATR
SHORT: Stop = Entry + ATR, TP1 = Entry - 2*ATR, TP2 = Entry - 4*ATR
"""

import logging
from app.strategies.calculators import (
    calculate_setup_strength,
    format_price,
    MIN_RR_RATIO,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER,
    VOLUME_TRADEABLE_MIN
)
from app.strategies.volume_analyzer import analyze_volume

logger = logging.getLogger(__name__)

MAX_ENTRY_DISTANCE_PERCENT = 3.0


def scan_fair_value_gaps(ohlcv, timeframe_str):
    """Mum verilerini tarayarak potansiyel FVG'leri bulur."""
    fvgs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"FVG Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        lookback_data = ohlcv[-50:]
        
        for i in range(1, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            if next_candle[3] > prev[2]:
                gap_low = prev[2]
                gap_high = next_candle[3]
                gap_size = gap_high - gap_low
                
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bullish',
                        'high': gap_high,
                        'low': gap_low,
                        'gap_size': gap_size,
                        'strength': 'high' if gap_size > (curr[2] - curr[3]) * 0.5 else 'medium'
                    })
            
            if next_candle[2] < prev[3]:
                gap_high = prev[3]
                gap_low = next_candle[2]
                gap_size = gap_high - gap_low
                
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bearish',
                        'high': gap_high,
                        'low': gap_low,
                        'gap_size': gap_size,
                        'strength': 'high' if gap_size > (curr[2] - curr[3]) * 0.5 else 'medium'
                    })
        
        if fvgs:
            logger.debug(f"📊 FVG Scan [{timeframe_str}]: {len(fvgs)} FVG bulundu")
        
        return fvgs[-5:]
        
    except Exception as e:
        logger.error(f"❌ FVG Scan Error [{timeframe_str}]: {e}")
        return []


def _get_confidence_label(strength_score):
    """Strength score'dan confidence label üret"""
    if strength_score >= 0.8:
        return 'HIGH'
    elif strength_score >= 0.5:
        return 'MEDIUM'
    else:
        return 'LOW'


def detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair=""):
    """Bullish FVG setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        gap_low = fvg['low']
        gap_high = fvg['high']
        
        entry_price = (gap_low + gap_high) / 2
        
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price - atr
        stop_loss = format_price(stop_price)
        
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        
        risk = abs(entry_price - stop_price)
        reward = abs(tp1_price - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.3.11: 3 parametre (confidence kaldırıldı - circular logic fix)
        fvg_strength = fvg.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, fvg_strength, rr_ratio)
        confidence = _get_confidence_label(strength_score)
        
        detailed_explanation = f"""
📊 **FVG Analizi (LONG):**
• Gap: {format_price(gap_low)} - {format_price(gap_high)}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.4f}x | Score: {strength_score:.2f}

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {stop_loss}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} FVG LONG [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'FVG + Volume (LONG)',
            'direction': 'LONG',
            'timeframe': timeframe,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'strength_score': strength_score,
            'volume_spike_ratio': vol_ratio,
            'fvg_strength': fvg_strength,
            'entry_zone': f"{format_price(gap_low)} - {format_price(gap_high)}",
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ FVG LONG error ({pair}): {e}")
        return None


def detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair=""):
    """Bearish FVG setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        gap_low = fvg['low']
        gap_high = fvg['high']
        
        entry_price = (gap_low + gap_high) / 2
        
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price + atr
        stop_loss = format_price(stop_price)
        
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        
        risk = abs(stop_price - entry_price)
        reward = abs(entry_price - tp1_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.3.11: 3 parametre (confidence kaldırıldı - circular logic fix)
        fvg_strength = fvg.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, fvg_strength, rr_ratio)
        confidence = _get_confidence_label(strength_score)
        
        detailed_explanation = f"""
📊 **FVG Analizi (SHORT):**
• Gap: {format_price(gap_low)} - {format_price(gap_high)}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.4f}x | Score: {strength_score:.2f}

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {stop_loss}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} FVG SHORT [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'FVG + Volume (SHORT)',
            'direction': 'SHORT',
            'timeframe': timeframe,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'strength_score': strength_score,
            'volume_spike_ratio': vol_ratio,
            'fvg_strength': fvg_strength,
            'entry_zone': f"{format_price(gap_low)} - {format_price(gap_high)}",
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ FVG SHORT error ({pair}): {e}")
        return None
