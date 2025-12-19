# -*- coding: utf-8 -*-
"""
T-TARS FVG Detector v2.3.10
===========================
Fair Value Gap setup detection (Scanning + Validation)

v2.3.10:
- FIX: Return dict'e volume_spike_ratio ve fvg_strength eklendi
- Bu sayede main.py'de python_score doğru hesaplanacak

v2.3.8:
- CHANGED: VOLUME_THRESHOLD kaldırıldı → calculators.VOLUME_TRADEABLE_MIN (DRY)
- CHANGED: Volume log format .2f → .4f (hassas okuma)

v2.2.7:
- ADD: Log mesajlarına [timeframe] eklendi (debug için)
- FIX: Confidence artık dinamik hesaplanıyor (calculate_setup_strength)
- FIX: Hardcoded 'MEDIUM' kaldırıldı

v2.2.6:
- FIX: R:R floating point karşılaştırma hatası düzeltildi

v2.2.5:
- NEW: Entry distance filter - Entry, current price'tan max %3 uzakta olabilir

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
    VOLUME_TRADEABLE_MIN  # v2.3.8: DRY - tek yerden yönetim
)
from app.strategies.volume_analyzer import analyze_volume

logger = logging.getLogger(__name__)

# v2.2.5: Entry distance filter - max %3 uzaklık
MAX_ENTRY_DISTANCE_PERCENT = 3.0


# --- SCANNING LOGIC (GÖZLER) ---
def scan_fair_value_gaps(ohlcv, timeframe_str):
    """
    Mum verilerini tarayarak potansiyel FVG'leri bulur.
    """
    fvgs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"FVG Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        # Son 50 muma bakmak yeterli
        lookback_data = ohlcv[-50:]
        
        # Mum yapısı: [timestamp, open, high, low, close, volume]
        for i in range(1, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            # Bullish FVG: 1. mumun high'ı ile 3. mumun low'u arasında boşluk
            if next_candle[3] > prev[2]:  # 3. mum low > 1. mum high
                gap_low = prev[2]    # 1. mumun high'ı
                gap_high = next_candle[3]  # 3. mumun low'u
                gap_size = gap_high - gap_low
                
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bullish',
                        'high': gap_high,
                        'low': gap_low,
                        'gap_size': gap_size,
                        'strength': 'high' if gap_size > (curr[2] - curr[3]) * 0.5 else 'medium'
                    })
            
            # Bearish FVG: 1. mumun low'u ile 3. mumun high'ı arasında boşluk
            if next_candle[2] < prev[3]:  # 3. mum high < 1. mum low
                gap_high = prev[3]   # 1. mumun low'u
                gap_low = next_candle[2]  # 3. mumun high'ı
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
        
        return fvgs[-5:]  # Son 5 FVG'yi döndür
        
    except Exception as e:
        logger.error(f"❌ FVG Scan Error [{timeframe_str}]: {e}")
        return []


def _get_confidence_label(strength_score):
    """
    v2.2.7: Strength score'dan confidence label üret
    """
    if strength_score >= 0.8:
        return 'HIGH'
    elif strength_score >= 0.5:
        return 'MEDIUM'
    else:
        return 'LOW'


# --- VALIDATION LOGIC (BEYİN) ---
def detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair=""):
    """Bullish FVG setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        # v2.3.8: Volume kontrolü - VOLUME_TRADEABLE_MIN calculators'tan (DRY)
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        gap_low = fvg['low']
        gap_high = fvg['high']
        
        # Entry = Gap mid-point
        entry_price = (gap_low + gap_high) / 2
        
        # v2.2.5: Entry distance kontrolü
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        # Stop = Entry - ATR (1R risk)
        stop_price = entry_price - atr
        stop_loss = format_price(stop_price)
        
        # TP1 = Entry + 2*ATR (2R), TP2 = Entry + 4*ATR (4R)
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        
        # R:R hesabı
        risk = abs(entry_price - stop_price)  # = ATR
        reward = abs(tp1_price - entry_price)  # = 2*ATR
        rr_ratio = reward / risk if risk > 0 else 0  # = 2.0
        
        # v2.2.6 FIX: R:R kontrolü - floating point toleransı
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.2.7: Dinamik confidence hesapla
        fvg_strength = fvg.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, fvg_strength, rr_ratio, 'MEDIUM')
        confidence = _get_confidence_label(strength_score)
        
        # v2.3.8: Volume format .4f
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
        
        # v2.3.8: Volume kontrolü - VOLUME_TRADEABLE_MIN calculators'tan (DRY)
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        gap_low = fvg['low']
        gap_high = fvg['high']
        
        # Entry = Gap mid-point
        entry_price = (gap_low + gap_high) / 2
        
        # v2.2.5: Entry distance kontrolü
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        # Stop = Entry + ATR (1R risk)
        stop_price = entry_price + atr
        stop_loss = format_price(stop_price)
        
        # TP1 = Entry - 2*ATR (2R), TP2 = Entry - 4*ATR (4R)
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        
        # R:R hesabı
        risk = abs(stop_price - entry_price)  # = ATR
        reward = abs(entry_price - tp1_price)  # = 2*ATR
        rr_ratio = reward / risk if risk > 0 else 0  # = 2.0
        
        # v2.2.6 FIX: R:R kontrolü - floating point toleransı
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.2.7: Dinamik confidence hesapla
        fvg_strength = fvg.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, fvg_strength, rr_ratio, 'MEDIUM')
        confidence = _get_confidence_label(strength_score)
        
        # v2.3.8: Volume format .4f
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
