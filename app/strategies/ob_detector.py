# -*- coding: utf-8 -*-
"""
T-TARS OB Detector v2.3.8
=========================
Order Block setup detection (Scanning + Validation)

v2.3.8:
- CHANGED: VOLUME_THRESHOLD kaldırıldı → calculators.VOLUME_TRADEABLE_MIN (DRY)
- CHANGED: Volume log format .2f → .4f (hassas okuma)

v2.2.7:
- ADD: Log mesajlarına [timeframe] eklendi (debug için)
- FIX: Confidence artık dinamik hesaplanıyor (calculate_setup_strength)
- FIX: Hardcoded 'HIGH' kaldırıldı

v2.2.6:
- FIX: R:R floating point karşılaştırma hatası düzeltildi

v2.2.5:
- NEW: Entry distance filter - Entry, current price'tan max %3 uzakta olabilir

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
    VOLUME_TRADEABLE_MIN  # v2.3.8: DRY - tek yerden yönetim
)
from app.strategies.volume_analyzer import analyze_volume

logger = logging.getLogger(__name__)

# v2.2.5: Entry distance filter - max %3 uzaklık
MAX_ENTRY_DISTANCE_PERCENT = 3.0


# --- SCANNING LOGIC (GÖZLER) ---
def scan_order_blocks(ohlcv, timeframe_str):
    """
    Mum verilerini tarayarak potansiyel Order Block'ları bulur.
    """
    obs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"OB Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        # Son 50 muma bakmak yeterli
        lookback_data = ohlcv[-50:]
        
        # Mum yapısı: [timestamp, open, high, low, close, volume]
        for i in range(2, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            # Bullish OB: Kırmızı mum, ardından gelen yeşil mum önceki kırmızının High'ını kırarsa
            if curr[4] < curr[1]:  # Kırmızı (Düşüş)
                if next_candle[4] > curr[2]:  # Sonraki mum, kırmızının tepesini geçti
                    obs.append({
                        'type': 'bullish',
                        'high': curr[2],   # OB High (mumun high'ı)
                        'low': curr[3],    # OB Low (mumun low'u)
                        'strength': 'high',
                        'volume_confirmed': True
                    })

            # Bearish OB: Yeşil mum, ardından gelen kırmızı mum önceki yeşilin Low'unu kırarsa
            elif curr[4] > curr[1]:  # Yeşil (Yükseliş)
                if next_candle[4] < curr[3]:  # Sonraki mum, yeşilin dibini kırdı
                    obs.append({
                        'type': 'bearish',
                        'high': curr[2],   # OB High (mumun high'ı)
                        'low': curr[3],    # OB Low (mumun low'u)
                        'strength': 'high',
                        'volume_confirmed': True
                    })
        
        if obs:
            logger.debug(f"📦 OB Scan [{timeframe_str}]: {len(obs)} OB bulundu")
        
        return obs[-5:]  # Son 5 OB'yi döndür
        
    except Exception as e:
        logger.error(f"❌ OB Scan Error [{timeframe_str}]: {e}")
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
def detect_ob_long(ob, volume, atr, timeframe, current_price, pair=""):
    """Bullish Order Block setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        # v2.3.8: Volume kontrolü - VOLUME_TRADEABLE_MIN calculators'tan (DRY)
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} OB LONG [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        # Entry = OB mid-point
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        # v2.2.5: Entry distance kontrolü
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} OB LONG [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
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
            logger.info(f"{coin} OB LONG [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.2.7: Dinamik confidence hesapla
        ob_strength = ob.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, ob_strength, rr_ratio, 'MEDIUM')
        confidence = _get_confidence_label(strength_score)
        
        # v2.3.8: Volume format .4f
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
        
        # v2.3.8: Volume kontrolü - VOLUME_TRADEABLE_MIN calculators'tan (DRY)
        if not volume.get('spike', False) and vol_ratio < VOLUME_TRADEABLE_MIN:
            logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Low Volume ({vol_ratio:.4f}x < {VOLUME_TRADEABLE_MIN}x)")
            return None
        
        # Entry = OB mid-point
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        # v2.2.5: Entry distance kontrolü
        if current_price > 0:
            distance_percent = abs(entry_price - current_price) / current_price * 100
            if distance_percent > MAX_ENTRY_DISTANCE_PERCENT:
                logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Entry too far ({distance_percent:.1f}% > {MAX_ENTRY_DISTANCE_PERCENT}%)")
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
            logger.info(f"{coin} OB SHORT [{timeframe}] rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # v2.2.7: Dinamik confidence hesapla
        ob_strength = ob.get('strength', 'medium')
        strength_score = calculate_setup_strength(vol_ratio, ob_strength, rr_ratio, 'MEDIUM')
        confidence = _get_confidence_label(strength_score)
        
        # v2.3.8: Volume format .4f
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
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB SHORT error ({pair}): {e}")
        return None
