# -*- coding: utf-8 -*-
"""
T-TARS FVG Detector v2.1.0
==========================
Fair Value Gap setup detection (Scanning + Validation)

v2.1.0:
- FIX: Entry hesabı düzeltildi → Kadircan formülü (21.46% oran)
- FIX: Stop hesabı düzeltildi → Entry ± ATR
- FIX: timestamp field eklendi (tracking_service uyumu)
- REMOVE: STOP_MULTIPLIER kullanımı kaldırıldı

Formül (Kadircan):
LONG:  Entry = gap_high - (((gap_high + gap_low)/100) * 21.46), Stop = Entry - ATR
SHORT: Entry = gap_low + (((gap_high + gap_low)/100) * 21.46), Stop = Entry + ATR
"""

import logging
import datetime
from app.config import Config
from app.strategies.calculators import (
    calculate_setup_strength,
    format_price,
    MIN_RR_RATIO,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER
)

logger = logging.getLogger(__name__)

# Volume threshold - 0.5x ve üzeri kabul edilir
VOLUME_THRESHOLD = 0.5

# FVG Entry oranı (Kadircan formülü)
FVG_ENTRY_RATIO = 21.46


# --- SCANNING LOGIC ---
def scan_fair_value_gaps(ohlcv, timeframe_str):
    """Mum verilerini tarayarak FVG'leri bulur."""
    fvgs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"FVG Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        # Son 50 mum
        data = ohlcv[-50:]
        
        for i in range(1, len(data)-1):
            prev = data[i-1]  # Mum 1
            curr = data[i]    # Mum 2 (Gap olan)
            next_candle = data[i+1]  # Mum 3
            
            # Bullish FVG: Mum 1 High < Mum 3 Low
            if next_candle[3] > prev[2] and curr[4] > curr[1]:  # Yeşil mum
                gap_size = next_candle[3] - prev[2]
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bullish',
                        'gap_low': prev[2],
                        'gap_high': next_candle[3],
                        'gap_size': gap_size,
                        'volume_confirmed': True
                    })
            
            # Bearish FVG: Mum 1 Low > Mum 3 High
            elif next_candle[2] < prev[3] and curr[4] < curr[1]:  # Kırmızı mum
                gap_size = prev[3] - next_candle[2]
                if gap_size > 0:
                    fvgs.append({
                        'type': 'bearish',
                        'gap_low': next_candle[2],
                        'gap_high': prev[3],
                        'gap_size': gap_size,
                        'volume_confirmed': True
                    })
        
        if fvgs:
            logger.debug(f"📊 FVG Scan [{timeframe_str}]: {len(fvgs)} FVG bulundu")
        
        return fvgs[-5:]
        
    except Exception as e:
        logger.error(f"❌ FVG Scan Error [{timeframe_str}]: {e}")
        return []


# --- VALIDATION LOGIC ---
def detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair=""):
    """Bullish FVG setup validasyonu"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        # Volume kontrolü (threshold: 0.5x)
        if not volume.get('spike', False) and vol_ratio < VOLUME_THRESHOLD:
            logger.info(f"{coin} FVG LONG rejected: Low Volume ({vol_ratio}x < {VOLUME_THRESHOLD}x)")
            return None
        
        gap_high = fvg['gap_high']
        gap_low = fvg['gap_low']
        
        # v2.1.0 FIX: Doğru FVG formülü
        # Entry = gap_high - (((gap_high + gap_low) / 100) * 21.46)
        entry_price = gap_high - (((gap_high + gap_low) / 100) * FVG_ENTRY_RATIO)
        
        # Stop = Entry - ATR (1R risk)
        stop_price = entry_price - atr
        
        # TP1 = Entry + 2*ATR (2R), TP2 = Entry + 4*ATR (4R)
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        
        # R:R hesabı
        risk = abs(entry_price - stop_price)  # = ATR
        reward = abs(tp1_price - entry_price)  # = 2*ATR
        rr_ratio = reward / risk if risk > 0 else 0  # = 2.0
        
        # R:R kontrolü
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"{coin} FVG LONG rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # Setup strength hesapla
        setup_strength = calculate_setup_strength(vol_ratio, 'medium', rr_ratio, 'MEDIUM')
        balance = Config.DEFAULT_BALANCE
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100

        detailed_explanation = f"""
📊 **FVG Analizi (LONG):**
• Gap: {format_price(gap_low)} - {format_price(gap_high)}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.2f}x

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {format_price(stop_price)}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Risk: ${risk_usd:.1f}
"""
        
        logger.info(f"✅ {coin} FVG LONG VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.2f}x")
        
        return {
            'type': 'FVG + Volume (LONG)',
            'direction': 'LONG',
            'timeframe': timeframe,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'rr_ratio': rr_ratio,
            'confidence': 'MEDIUM',
            'entry_zone': f"{format_price(gap_low)} - {format_price(gap_high)}",
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ FVG LONG error ({pair}): {e}")
        return None


def detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair=""):
    """Bearish FVG setup validasyonu"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        # Volume kontrolü (threshold: 0.5x)
        if not volume.get('spike', False) and vol_ratio < VOLUME_THRESHOLD:
            logger.info(f"{coin} FVG SHORT rejected: Low Volume ({vol_ratio}x < {VOLUME_THRESHOLD}x)")
            return None
        
        gap_high = fvg['gap_high']
        gap_low = fvg['gap_low']
        
        # v2.1.0 FIX: Doğru FVG formülü
        # Entry = gap_low + (((gap_high + gap_low) / 100) * 21.46)
        entry_price = gap_low + (((gap_high + gap_low) / 100) * FVG_ENTRY_RATIO)
        
        # Stop = Entry + ATR (1R risk)
        stop_price = entry_price + atr
        
        # TP1 = Entry - 2*ATR (2R), TP2 = Entry - 4*ATR (4R)
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        
        # R:R hesabı
        risk = abs(stop_price - entry_price)  # = ATR
        reward = abs(entry_price - tp1_price)  # = 2*ATR
        rr_ratio = reward / risk if risk > 0 else 0  # = 2.0
        
        # R:R kontrolü
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"{coin} FVG SHORT rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # Setup strength hesapla
        setup_strength = calculate_setup_strength(vol_ratio, 'medium', rr_ratio, 'MEDIUM')
        balance = Config.DEFAULT_BALANCE
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100

        detailed_explanation = f"""
📊 **FVG Analizi (SHORT):**
• Gap: {format_price(gap_low)} - {format_price(gap_high)}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.2f}x

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {format_price(stop_price)}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Risk: ${risk_usd:.1f}
"""
        
        logger.info(f"✅ {coin} FVG SHORT VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.2f}x")
        
        return {
            'type': 'FVG + Volume (SHORT)',
            'direction': 'SHORT',
            'timeframe': timeframe,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'rr_ratio': rr_ratio,
            'confidence': 'MEDIUM',
            'entry_zone': f"{format_price(gap_low)} - {format_price(gap_high)}",
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ FVG SHORT error ({pair}): {e}")
        return None
