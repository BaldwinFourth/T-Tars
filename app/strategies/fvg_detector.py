# -*- coding: utf-8 -*-
"""
T-TARS FVG Detector v2.5.1
============================
Fair Value Gap setup detection (Scanning + Validation)

v2.5.1:
- CHANGED: FVG_LOOKBACK, MAX_FVG_COUNT, MAX_ENTRY_DISTANCE_PERCENT calculators'dan import
- REMOVED: Hardcoded sabitler kaldırıldı (DRY prensibi)

v2.4.10:
- CHANGED: TP1/TP2 kaldırıldı → Tek TP (3.0 ATR)
- CHANGED: MIN_RR_RATIO = 3.0 (eskiden 2.0)
- UPDATED: Return dict'ten tp1, tp2, tp1_price, tp2_price kaldırıldı → tp, tp_price

v2.4.0:
- NEW: Minimum boyut filtresi (≥1.0 ATR)
- NEW: En yakın 4 FVG döndür (noise reduction)

Formül (Kadircan) v2.4.10:
Gap Size = Gap High - Gap Low
Entry = Gap mid-point
LONG:  Stop = Entry - ATR, TP = Entry + 3*ATR
SHORT: Stop = Entry + ATR, TP = Entry - 3*ATR
"""

import logging
from app.strategies.calculators import (
    calculate_setup_strength,
    format_price,
    MIN_RR_RATIO,
    TP_MULTIPLIER,
    VOLUME_TRADEABLE_MIN,
    MIN_FVG_SIZE_ATR,
    # v2.5.1: Yeni import'lar
    FVG_LOOKBACK,
    MAX_FVG_COUNT,
    MAX_ENTRY_DISTANCE_PERCENT
)
from app.strategies.volume_analyzer import analyze_volume

logger = logging.getLogger(__name__)


def scan_fair_value_gaps(ohlcv, timeframe_str, atr=0, current_price=0):
    """
    Mum verilerini tarayarak potansiyel FVG'leri bulur.
    
    v2.5.1:
    - FVG_LOOKBACK calculators'dan import (300 bar)
    - MAX_FVG_COUNT calculators'dan import (4)
    
    v2.4.0:
    - Boyut filtresi: FVG gap boyutu >= 1.0 ATR olmalı
    - En yakın 4: Fiyata en yakın 4 FVG döndürülür
    
    Args:
        ohlcv: Mum verileri [[ts, o, h, l, c, v], ...]
        timeframe_str: Timeframe string (örn: '1h')
        atr: ATR değeri (boyut filtresi için)
        current_price: Güncel fiyat (sıralama için)
    
    Returns:
        list: En yakın MAX_FVG_COUNT FVG (boyut filtresinden geçenler)
    """
    fvgs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"FVG Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        # v2.5.1: calculators'dan import edilen FVG_LOOKBACK kullan
        lookback_data = ohlcv[-FVG_LOOKBACK:]
        
        for i in range(1, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            # Bullish FVG: Sonraki mumun low'u > önceki mumun high'ı
            if next_candle[3] > prev[2]:
                gap_low = prev[2]
                gap_high = next_candle[3]
                gap_size = gap_high - gap_low
                gap_mid = (gap_high + gap_low) / 2
                
                # v2.4.0: Boyut filtresi
                if atr > 0 and gap_size < (atr * MIN_FVG_SIZE_ATR):
                    logger.debug(f"FVG Scan [{timeframe_str}]: Bullish FVG rejected (size={gap_size:.4f} < {atr * MIN_FVG_SIZE_ATR:.4f})")
                    continue
                
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bullish',
                        'high': gap_high,
                        'low': gap_low,
                        'mid': gap_mid,
                        'gap_size': gap_size,
                        'strength': 'high' if gap_size > (curr[2] - curr[3]) * 0.5 else 'medium'
                    })
            
            # Bearish FVG: Sonraki mumun high'ı < önceki mumun low'u
            if next_candle[2] < prev[3]:
                gap_high = prev[3]
                gap_low = next_candle[2]
                gap_size = gap_high - gap_low
                gap_mid = (gap_high + gap_low) / 2
                
                # v2.4.0: Boyut filtresi
                if atr > 0 and gap_size < (atr * MIN_FVG_SIZE_ATR):
                    logger.debug(f"FVG Scan [{timeframe_str}]: Bearish FVG rejected (size={gap_size:.4f} < {atr * MIN_FVG_SIZE_ATR:.4f})")
                    continue
                
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bearish',
                        'high': gap_high,
                        'low': gap_low,
                        'mid': gap_mid,
                        'gap_size': gap_size,
                        'strength': 'high' if gap_size > (curr[2] - curr[3]) * 0.5 else 'medium'
                    })
        
        # v2.5.1: Fiyata en yakın MAX_FVG_COUNT FVG'yi seç
        if current_price > 0 and len(fvgs) > MAX_FVG_COUNT:
            fvgs = sorted(fvgs, key=lambda x: abs(x['mid'] - current_price))[:MAX_FVG_COUNT]
            logger.debug(f"📊 FVG Scan [{timeframe_str}]: {len(fvgs)} FVG (filtered to closest {MAX_FVG_COUNT})")
        elif fvgs:
            fvgs = fvgs[-MAX_FVG_COUNT:]  # Son MAX_FVG_COUNT'u al
            logger.debug(f"📊 FVG Scan [{timeframe_str}]: {len(fvgs)} FVG bulundu")
        
        return fvgs
        
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
        
        # v2.5.1: calculators'dan import edilen MAX_ENTRY_DISTANCE_PERCENT kullan
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} FVG LONG [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price - atr
        stop_loss = format_price(stop_price)
        
        # v2.4.10: Tek TP (3.0 ATR)
        tp_price = entry_price + (atr * TP_MULTIPLIER)
        
        risk = abs(entry_price - stop_price)
        reward = abs(tp_price - entry_price)
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
• TP: {format_price(tp_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} FVG LONG [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'FVG + Volume (LONG)',
            'direction': 'LONG',
            'timeframe': timeframe,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp_price': tp_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'strength_score': strength_score,
            'volume_spike_ratio': vol_ratio,
            'fvg_strength': fvg_strength,
            'entry_zone': f"{format_price(gap_low)} - {format_price(gap_high)}",
            'tp': format_price(tp_price),
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
        
        # v2.5.1: calculators'dan import edilen MAX_ENTRY_DISTANCE_PERCENT kullan
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} FVG SHORT [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price + atr
        stop_loss = format_price(stop_price)
        
        # v2.4.10: Tek TP (3.0 ATR)
        tp_price = entry_price - (atr * TP_MULTIPLIER)
        
        risk = abs(stop_price - entry_price)
        reward = abs(entry_price - tp_price)
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
• TP: {format_price(tp_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} FVG SHORT [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'FVG + Volume (SHORT)',
            'direction': 'SHORT',
            'timeframe': timeframe,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp_price': tp_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'strength_score': strength_score,
            'volume_spike_ratio': vol_ratio,
            'fvg_strength': fvg_strength,
            'entry_zone': f"{format_price(gap_low)} - {format_price(gap_high)}",
            'tp': format_price(tp_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ FVG SHORT error ({pair}): {e}")
        return None
