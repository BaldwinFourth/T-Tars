# -*- coding: utf-8 -*-
"""
T-TARS FVG Detector v1.4.9.1
============================
Fair Value Gap setup detection (LONG + SHORT)
volume_confirmed field kullanılıyor
"""

import logging
from app.config import Config
from app.strategies.calculators import (
    calculate_setup_strength,
    MIN_RR_RATIO,
    STOP_MULTIPLIER,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER
)

logger = logging.getLogger(__name__)


def detect_fvg_long(fvg, volume, atr, timeframe, current_price):
    """
    Bullish FVG setup tespiti
    
    Returns:
        dict: Setup bilgileri veya None
    """
    try:
        # Volume confirmed kontrolü (FVG bulunduğu andaki volume)
        if not fvg.get('volume_confirmed', False):
            logger.info(f"FVG LONG rejected: volume_confirmed=False")
            return None
        
        entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
        entry_price = (fvg['gap_low'] + fvg['gap_high']) / 2  # FVG mid-point
        
        stop_distance = atr * STOP_MULTIPLIER
        stop_price = fvg['gap_low'] - stop_distance
        stop_loss = f"${stop_price:,.2f}"
        
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        tp1 = f"${tp1_price:,.2f}"
        tp2 = f"${tp2_price:,.2f}"
        
        risk = abs(entry_price - stop_price)
        reward = abs(tp1_price - entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        logger.info(f"📊 FVG LONG R:R: {rr_ratio:.2f} (entry=${entry_price:.2f})")
        
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"FVG LONG rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
            return None
        
        # Risk hesabı
        fvg_strength = fvg.get('volume_strength', 'medium')
        balance = Config.DEFAULT_BALANCE
        volume_spike_ratio = volume.get('spike_ratio', 1.0)
        setup_strength = calculate_setup_strength(
            volume_spike_ratio=volume_spike_ratio,
            ob_or_fvg_strength=fvg_strength,
            rr_ratio=rr_ratio,
            confidence='MEDIUM'
        )
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100
        
        detailed_explanation = f"""
📊 **FVG Analizi:**
• Bullish FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}
• Gap size: ${fvg['gap_size']:,.2f}
• Volume confirmed: ✅
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📈 **TP/Stop:**
• ATR: ${atr:,.2f} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
        
        return {
            'type': 'FVG + Volume Spike (LONG)',
            'confidence': 'MEDIUM',
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
            'fvg_strength': fvg_strength,
            'rr_ratio': rr_ratio,
            'detailed_explanation': detailed_explanation,
            'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume confirmed"
        }
        
    except Exception as e:
        logger.error(f"FVG LONG detection error: {e}")
        return None


def detect_fvg_short(fvg, volume, atr, timeframe, current_price):
    """
    Bearish FVG setup tespiti
    
    Returns:
        dict: Setup bilgileri veya None
    """
    try:
        # Volume confirmed kontrolü (FVG bulunduğu andaki volume)
        if not fvg.get('volume_confirmed', False):
            logger.info(f"FVG SHORT rejected: volume_confirmed=False")
            return None
        
        entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
        entry_price = (fvg['gap_low'] + fvg['gap_high']) / 2  # FVG mid-point
        
        stop_distance = atr * STOP_MULTIPLIER
        stop_price = fvg['gap_high'] + stop_distance
        stop_loss = f"${stop_price:,.2f}"
        
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        tp1 = f"${tp1_price:,.2f}"
        tp2 = f"${tp2_price:,.2f}"
        
        risk = abs(stop_price - entry_price)
        reward = abs(entry_price - tp1_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        logger.info(f"📊 FVG SHORT R:R: {rr_ratio:.2f} (entry=${entry_price:.2f})")
        
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"FVG SHORT rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
            return None
        
        # Risk hesabı
        fvg_strength = fvg.get('volume_strength', 'medium')
        balance = Config.DEFAULT_BALANCE
        volume_spike_ratio = volume.get('spike_ratio', 1.0)
        setup_strength = calculate_setup_strength(
            volume_spike_ratio=volume_spike_ratio,
            ob_or_fvg_strength=fvg_strength,
            rr_ratio=rr_ratio,
            confidence='MEDIUM'
        )
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100
        
        detailed_explanation = f"""
📊 **FVG Analizi:**
• Bearish FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}
• Gap size: ${fvg['gap_size']:,.2f}
• Volume confirmed: ✅
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📉 **TP/Stop:**
• ATR: ${atr:,.2f} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
        
        return {
            'type': 'FVG + Volume Spike (SHORT)',
            'confidence': 'MEDIUM',
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
            'fvg_strength': fvg_strength,
            'rr_ratio': rr_ratio,
            'detailed_explanation': detailed_explanation,
            'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume confirmed"
        }
        
    except Exception as e:
        logger.error(f"FVG SHORT detection error: {e}")
        return None
