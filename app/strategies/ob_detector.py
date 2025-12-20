# -*- coding: utf-8 -*-
"""
T-TARS OB Detector v2.3.11
==========================
Order Block setup detection (Scanning + Validation)

v2.3.11:
- CHANGED: calculate_setup_strength() 3 parametre (confidence kaldırıldı)
- Bu sayede circular logic sorunu çözüldü

v2.3.10:
- FIX: Return dict'e volume_spike_ratio ve ob_strength eklendi

v2.3.8:
- CHANGED: VOLUME_THRESHOLD kaldırıldı → calculators.VOLUME_TRADEABLE_MIN (DRY)

Formül (Kadircan):
LONG:  Entry = (OB_H + OB_L) / 2, Stop = Entry - ATR, TP1 = Entry + 2*ATR, TP2 = Entry + 4*ATR
SHORT: Entry = (OB_H + OB_L) / 2, Stop = Entry + ATR, TP1 = Entry - 2*ATR, TP2 = Entry - 4*ATR
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


def scan_order_blocks(ohlcv, timeframe_str):
    """Mum verilerini tarayarak potansiyel Order Block'ları bulur."""
    obs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"OB Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        lookback_data = ohlcv[-50:]
        
        for i in range(2, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            if curr[4] < curr[1]:  # Kırmızı
                if next_candle[4] > curr[2]:
                    obs.append({
                        'type': 'bullish',
                        'high': curr[2],
                        'low': curr[3],
                        'strength': 'high',
                        'volume_confirmed': True
                    })

            elif curr[4] > curr[1]:  # Yeşil
                if next_candle[4] < curr[3]:
                    obs.append({
                        'type': 'bearish',
                        'high': curr[2],
                        'low': curr[3],
                        'strength': 'high',
                        'volume_confirmed': True
                    })
        
        if obs:
            logger.debug(f"📦 OB Scan [{timeframe_str}]: {len(obs)} OB bulundu")
        
        return obs[-5:]
        
    except Exception as e:
        logger.error(f"❌ OB Scan Error [{timeframe_str}]: {e}")
        return []


def _get_confidence_label(strength_score):
    """Strength score'dan confidence label üret"""
    if strength_score >= 0.8:
        return 'HIGH'
    elif strength_score >= 0.5:
        return 'MEDIUM'
    else:
        return 'LOW'


def detect_ob_long(ob, volume, atr, timeframe, current_price, pair=""):
    """Bullish Order Block setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} OB LONG [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} OB LONG [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price - atr
        stop_loss = format_price(stop_price)
        
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        
        risk = abs(entry_price - stop_price)
        reward = abs(tp1_price - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} OB LONG [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.3.11: 3 parametre (confidence kaldırıldı - circular logic fix)
        ob_strength = ob.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, ob_strength, rr_ratio)
        confidence = _get_confidence_label(strength_score)
        
        detailed_explanation = f"""
📊 **OB Analizi (LONG):**
• Zone: {entry_zone}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.4f}x | Score: {strength_score:.2f}

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {stop_loss}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} OB LONG [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'OB + Volume (LONG)',
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
            'ob_strength': ob_strength,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB LONG error ({pair}): {e}")
        return None


def detect_ob_short(ob, volume, atr, timeframe, current_price, pair=""):
    """Bearish Order Block setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price + atr
        stop_loss = format_price(stop_price)
        
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        
        risk = abs(stop_price - entry_price)
        reward = abs(entry_price - tp1_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.3.11: 3 parametre (confidence kaldırıldı - circular logic fix)
        ob_strength = ob.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, ob_strength, rr_ratio)
        confidence = _get_confidence_label(strength_score)
        
        detailed_explanation = f"""
📊 **OB Analizi (SHORT):**
• Zone: {entry_zone}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.4f}x | Score: {strength_score:.2f}

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {stop_loss}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} OB SHORT [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'OB + Volume (SHORT)',
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
            'ob_strength': ob_strength,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB SHORT error ({pair}): {e}")
        return None
