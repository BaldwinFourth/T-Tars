# -*- coding: utf-8 -*-
"""
T-TARS OB Detector v2.0.2
=========================
Order Block setup detection (LONG + SHORT)

v2.0.2:
- direction field eklendi (OKX order için ZORUNLU)

v1.4.9.5:
- pair parametresi eklendi
- STOP_MULTIPLIER artık 1.0
"""

import logging
from app.config import Config
from app.strategies.calculators import (
    calculate_setup_strength,
    format_price,
    MIN_RR_RATIO,
    STOP_MULTIPLIER,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER
)

logger = logging.getLogger(__name__)


def detect_ob_long(ob, volume, atr, timeframe, current_price, pair=""):
    """
    Bullish Order Block setup tespiti
    
    Returns:
        dict: Setup bilgileri veya None
    """
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        
        if not ob.get('volume_confirmed', False):
            logger.info(f"{coin} OB LONG rejected: volume_confirmed=False")
            return None
        
        entry_price = (ob['low'] + ob['price']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['price'])}"
        
        stop_distance = atr * STOP_MULTIPLIER
        stop_price = ob['low'] - stop_distance
        stop_loss = format_price(stop_price)
        
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        tp1 = format_price(tp1_price)
        tp2 = format_price(tp2_price)
        
        risk = abs(entry_price - stop_price)
        reward = abs(tp1_price - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        logger.info(f"📊 {coin} OB LONG R:R: {rr_ratio:.2f}")
        
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"{coin} OB LONG rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
            return None
        
        balance = Config.DEFAULT_BALANCE
        volume_spike_ratio = volume.get('spike_ratio', 1.0)
        setup_strength = calculate_setup_strength(
            volume_spike_ratio=volume_spike_ratio,
            ob_or_fvg_strength=ob['strength'],
            rr_ratio=rr_ratio,
            confidence='HIGH'
        )
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100
        
        detailed_explanation = f"""
📊 **OB Analizi:**
• Bullish OB @ {format_price(ob['low'])} - {format_price(ob['price'])}
• Volume confirmed: ✅
• OB strength: {ob['strength'].upper()}
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📈 **TP/Stop:**
• ATR: {format_price(atr)} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
        
        logger.info(f"✅ {coin} OB LONG ACCEPTED: R:R {rr_ratio:.2f}")
        
        return {
            'type': 'OB + Volume Spike (LONG)',
            'direction': 'LONG',  # v2.0.2: OKX order için ZORUNLU
            'confidence': 'HIGH',
            'timeframe': timeframe,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
            'current_price': current_price,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'volume_spike_ratio': volume_spike_ratio,
            'ob_strength': ob['strength'],
            'rr_ratio': rr_ratio,
            'detailed_explanation': detailed_explanation,
            'details': f"Bullish OB @ {format_price(ob['low'])}\nVolume confirmed"
        }
        
    except Exception as e:
        logger.error(f"OB LONG detection error: {e}")
        return None


def detect_ob_short(ob, volume, atr, timeframe, current_price, pair=""):
    """
    Bearish Order Block setup tespiti
    
    Returns:
        dict: Setup bilgileri veya None
    """
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        
        if not ob.get('volume_confirmed', False):
            logger.info(f"{coin} OB SHORT rejected: volume_confirmed=False")
            return None
        
        entry_price = (ob['price'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['price'])} - {format_price(ob['high'])}"
        
        stop_distance = atr * STOP_MULTIPLIER
        stop_price = ob['high'] + stop_distance
        stop_loss = format_price(stop_price)
        
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        tp1 = format_price(tp1_price)
        tp2 = format_price(tp2_price)
        
        risk = abs(stop_price - entry_price)
        reward = abs(entry_price - tp1_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        logger.info(f"📊 {coin} OB SHORT R:R: {rr_ratio:.2f}")
        
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"{coin} OB SHORT rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
            return None
        
        balance = Config.DEFAULT_BALANCE
        volume_spike_ratio = volume.get('spike_ratio', 1.0)
        setup_strength = calculate_setup_strength(
            volume_spike_ratio=volume_spike_ratio,
            ob_or_fvg_strength=ob['strength'],
            rr_ratio=rr_ratio,
            confidence='HIGH'
        )
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100
        
        detailed_explanation = f"""
📊 **OB Analizi:**
• Bearish OB @ {format_price(ob['price'])} - {format_price(ob['high'])}
• Volume confirmed: ✅
• OB strength: {ob['strength'].upper()}
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📉 **TP/Stop:**
• ATR: {format_price(atr)} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
        
        logger.info(f"✅ {coin} OB SHORT ACCEPTED: R:R {rr_ratio:.2f}")
        
        return {
            'type': 'OB + Volume Spike (SHORT)',
            'direction': 'SHORT',  # v2.0.2: OKX order için ZORUNLU
            'confidence': 'HIGH',
            'timeframe': timeframe,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
            'current_price': current_price,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'volume_spike_ratio': volume_spike_ratio,
            'ob_strength': ob['strength'],
            'rr_ratio': rr_ratio,
            'detailed_explanation': detailed_explanation,
            'details': f"Bearish OB @ {format_price(ob['high'])}\nVolume confirmed"
        }
        
    except Exception as e:
        logger.error(f"OB SHORT detection error: {e}")
        return None
