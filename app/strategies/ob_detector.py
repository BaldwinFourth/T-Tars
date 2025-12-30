# -*- coding: utf-8 -*-
"""
T-TARS OB Detector v2.5.1
===========================
Order Block setup detection (Scanning + Validation)

v2.5.1:
- CHANGED: OB_LOOKBACK, MAX_OB_COUNT, MAX_ENTRY_DISTANCE_PERCENT calculators'dan import
- REMOVED: Hardcoded sabitler kaldırıldı (DRY prensibi)

v2.4.10:
- CHANGED: Tek TP sistemi (tp1_price/tp2_price → tp_price)
- CHANGED: TP_MULTIPLIER = 3.0 kullanılıyor (R:R 3.0)
- CHANGED: MIN_RR_RATIO = 3.0

v2.4.0:
- NEW: Minimum boyut filtresi (≥1.0 ATR)
- NEW: En yakın 4 OB döndür (noise reduction)
- NEW: current_price parametresi scan_order_blocks'a eklendi

Formül (v2.4.10):
LONG:  Entry = (OB_H + OB_L) / 2, Stop = Entry - ATR, TP = Entry + 3*ATR
SHORT: Entry = (OB_H + OB_L) / 2, Stop = Entry + ATR, TP = Entry - 3*ATR
"""

import logging
from app.strategies.calculators import (
    calculate_setup_strength,
    format_price,
    MIN_RR_RATIO,
    TP_MULTIPLIER,
    VOLUME_TRADEABLE_MIN,
    MIN_OB_SIZE_ATR,
    # v2.5.1: Yeni import'lar
    OB_LOOKBACK,
    MAX_OB_COUNT,
    MAX_ENTRY_DISTANCE_PERCENT
)
from app.strategies.volume_analyzer import analyze_volume

logger = logging.getLogger(__name__)


def scan_order_blocks(ohlcv, timeframe_str, atr=0, current_price=0):
    """
    Mum verilerini tarayarak potansiyel Order Block'ları bulur.
    
    v2.5.1:
    - OB_LOOKBACK calculators'dan import (300 bar)
    - MAX_OB_COUNT calculators'dan import (4)
    
    v2.4.0:
    - Boyut filtresi: OB boyutu >= 1.0 ATR olmalı
    - En yakın 4: Fiyata en yakın 4 OB döndürülür
    
    Args:
        ohlcv: Mum verileri [[ts, o, h, l, c, v], ...]
        timeframe_str: Timeframe string (örn: '1h')
        atr: ATR değeri (boyut filtresi için)
        current_price: Güncel fiyat (sıralama için)
    
    Returns:
        list: En yakın MAX_OB_COUNT OB (boyut filtresinden geçenler)
    """
    obs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"OB Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        # v2.5.1: calculators'dan import edilen OB_LOOKBACK kullan
        lookback_data = ohlcv[-OB_LOOKBACK:]
        
        for i in range(2, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            # Bullish OB: Kırmızı mum + sonraki mum yukarı kırılım
            if curr[4] < curr[1]:  # Kırmızı
                if next_candle[4] > curr[2]:
                    ob_high = curr[2]
                    ob_low = curr[3]
                    ob_size = ob_high - ob_low
                    ob_mid = (ob_high + ob_low) / 2
                    
                    # Boyut filtresi
                    if atr > 0 and ob_size < (atr * MIN_OB_SIZE_ATR):
                        logger.debug(f"OB Scan [{timeframe_str}]: Bullish OB rejected (size={ob_size:.4f} < {atr * MIN_OB_SIZE_ATR:.4f})")
                        continue
                    
                    obs.append({
                        'type': 'bullish',
                        'high': ob_high,
                        'low': ob_low,
                        'mid': ob_mid,
                        'size': ob_size,
                        'strength': 'high',
                        'volume_confirmed': True
                    })

            # Bearish OB: Yeşil mum + sonraki mum aşağı kırılım
            elif curr[4] > curr[1]:  # Yeşil
                if next_candle[4] < curr[3]:
                    ob_high = curr[2]
                    ob_low = curr[3]
                    ob_size = ob_high - ob_low
                    ob_mid = (ob_high + ob_low) / 2
                    
                    # Boyut filtresi
                    if atr > 0 and ob_size < (atr * MIN_OB_SIZE_ATR):
                        logger.debug(f"OB Scan [{timeframe_str}]: Bearish OB rejected (size={ob_size:.4f} < {atr * MIN_OB_SIZE_ATR:.4f})")
                        continue
                    
                    obs.append({
                        'type': 'bearish',
                        'high': ob_high,
                        'low': ob_low,
                        'mid': ob_mid,
                        'size': ob_size,
                        'strength': 'high',
                        'volume_confirmed': True
                    })
        
        # Fiyata en yakın MAX_OB_COUNT OB'yi seç
        if current_price > 0 and len(obs) > MAX_OB_COUNT:
            obs = sorted(obs, key=lambda x: abs(x['mid'] - current_price))[:MAX_OB_COUNT]
            logger.debug(f"📦 OB Scan [{timeframe_str}]: {len(obs)} OB (filtered to closest {MAX_OB_COUNT})")
        elif obs:
            obs = obs[-MAX_OB_COUNT:]
            logger.debug(f"📦 OB Scan [{timeframe_str}]: {len(obs)} OB bulundu")
        
        return obs
        
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
    """Bullish Order Block setup onayı - v2.4.10: Tek TP"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} OB LONG [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        # v2.5.1: calculators'dan import edilen MAX_ENTRY_DISTANCE_PERCENT kullan
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} OB LONG [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price - atr
        stop_loss = format_price(stop_price)
        
        # v2.4.10: Tek TP = 3.0 ATR
        tp_price = entry_price + (atr * TP_MULTIPLIER)
        
        risk = abs(entry_price - stop_price)
        reward = abs(tp_price - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} OB LONG [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
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
• TP: {format_price(tp_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} OB LONG [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'OB + Volume (LONG)',
            'direction': 'LONG',
            'timeframe': timeframe,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp_price': tp_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'strength_score': strength_score,
            'volume_spike_ratio': vol_ratio,
            'ob_strength': ob_strength,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp': format_price(tp_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB LONG error ({pair}): {e}")
        return None


def detect_ob_short(ob, volume, atr, timeframe, current_price, pair=""):
    """Bearish Order Block setup onayı - v2.4.10: Tek TP"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        # v2.5.1: calculators'dan import edilen MAX_ENTRY_DISTANCE_PERCENT kullan
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
                return None
        
        stop_price = entry_price + atr
        stop_loss = format_price(stop_price)
        
        # v2.4.10: Tek TP = 3.0 ATR
        tp_price = entry_price - (atr * TP_MULTIPLIER)
        
        risk = abs(stop_price - entry_price)
        reward = abs(entry_price - tp_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if round(rr_ratio, 2) < MIN_RR_RATIO:
            logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
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
• TP: {format_price(tp_price)}
• R:R: {rr_ratio:.2f} | Confidence: {confidence}
"""
        
        logger.info(f"✅ {coin} OB SHORT [{timeframe}] VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.4f}x, Conf={confidence}")
        
        return {
            'type': 'OB + Volume (SHORT)',
            'direction': 'SHORT',
            'timeframe': timeframe,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp_price': tp_price,
            'rr_ratio': rr_ratio,
            'confidence': confidence,
            'strength_score': strength_score,
            'volume_spike_ratio': vol_ratio,
            'ob_strength': ob_strength,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp': format_price(tp_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB SHORT error ({pair}): {e}")
        return None
