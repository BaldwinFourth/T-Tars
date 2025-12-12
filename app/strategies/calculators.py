# -*- coding: utf-8 -*-
"""
T-TARS Trading Calculators v2.0.9
===================================
Kullanım:
    from app.strategies.calculators import (
        calculate_setup_strength,
        calculate_rr,
        format_price,
        MIN_RR_RATIO,
        STOP_MULTIPLIER,
        TP1_MULTIPLIER,
        TP2_MULTIPLIER
    )
"""

# ============================================
# ATR MULTIPLIERS - STOP & TP (FINE TUNING)
# ============================================
# Stop seviyesi: 1.0 ATR (Daha dar stop)
STOP_MULTIPLIER = 1.0      

# Hedefler: R:R 2.0 tutturmak için TP1 en az 2.0 ATR olmalı
# 2.0 / 1.0 = 2.0 R:R
TP1_MULTIPLIER = 2.0       

# TP2: Ana hedef
TP2_MULTIPLIER = 4.0       

# ============================================
# R:R THRESHOLDS
# ============================================
# Minimum Risk:Reward oranı (Reward / Risk)
# Kesin kural: En az 2 birim kazanç hedeflenmeli
MIN_RR_RATIO = 2.0         

RR_EXCELLENT = 4.0         # R:R >= 3.0 → Score 1.0
RR_GOOD = 3.5              # R:R >= 2.5 → Score 0.8
RR_MEDIUM = 3            # R:R >= 2.2 → Score 0.6
RR_MINIMUM = 2.0           # R:R >= 2.0 → Score 0.4

# ============================================
# VOLUME THRESHOLDS
# ============================================
VOLUME_EXCELLENT = 3.0     # Volume >= 3.0x → Score 1.0
VOLUME_GOOD = 2.5          # Volume >= 2.5x → Score 0.8
VOLUME_MEDIUM = 2.0        # Volume >= 2.0x → Score 0.6
VOLUME_LOW = 1.5           # Volume >= 1.5x → Score 0.4

# ============================================
# OB/FVG STRENGTH MAPPING
# ============================================
STRENGTH_MAP = {
    'high': 1.05,
    'medium': 0.65,
    'low': 0.25
}

# ============================================
# CONFIDENCE MAPPING
# ============================================
CONFIDENCE_MAP = {
    'HIGH': 1.05,
    'MEDIUM': 0.65,
    'LOW': 0.25
}

# ============================================
# WEIGHT DISTRIBUTION
# ============================================
WEIGHT_VOLUME = 0.25
WEIGHT_STRENGTH = 0.25
WEIGHT_RR = 0.25
WEIGHT_CONFIDENCE = 0.25


# ============================================
# FUNCTIONS
# ============================================

def format_price(price):
    """
    Fiyatı dinamik formatta string'e çevir.
    SHIB/DOGE gibi düşük fiyatlı coinler için 8 ondalık,
    BTC gibi yüksek fiyatlılar için 2 ondalık kullanır.
    """
    if price is None or price == 0:
        return "$0.00"
    
    abs_price = abs(price)
    
    if abs_price < 0.0001:
        return f"${price:.8f}"
    elif abs_price < 0.01:
        return f"${price:.6f}"
    elif abs_price < 1:
        return f"${price:.4f}"
    elif abs_price < 100:
        return f"${price:,.4f}"
    else:
        return f"${price:,.2f}"


def format_price_raw(price):
    """
    Fiyatı $ olmadan formatla (log için)
    """
    formatted = format_price(price)
    return formatted.replace("$", "")


def calculate_rr(entry_price, stop_price, tp_price):
    """
    Risk:Reward oranını hesapla.
    """
    risk = abs(entry_price - stop_price)
    reward = abs(tp_price - entry_price)
    
    if risk == 0:
        return 0
    
    return reward / risk


def calculate_setup_strength(volume_spike_ratio, ob_or_fvg_strength, rr_ratio, confidence):
    """
    Setup gücünü hesapla (0-1 arası).
    """
    # Volume Score
    if volume_spike_ratio >= VOLUME_EXCELLENT:
        volume_score = 1.05
    elif volume_spike_ratio >= VOLUME_GOOD:
        volume_score = 0.85
    elif volume_spike_ratio >= VOLUME_MEDIUM:
        volume_score = 0.65
    elif volume_spike_ratio >= VOLUME_LOW:
        volume_score = 0.35
    else:
        volume_score = 0.2
    
    # OB/FVG Strength Score
    strength_score = STRENGTH_MAP.get(ob_or_fvg_strength.lower(), 0.5)
    
    # R:R Score
    if rr_ratio >= RR_EXCELLENT:
        rr_score = 1.05
    elif rr_ratio >= RR_GOOD:
        rr_score = 0.85
    elif rr_ratio >= RR_MEDIUM:
        rr_score = 0.65
    elif rr_ratio >= RR_MINIMUM:
        rr_score = 0.35
    else:
        rr_score = 0.2
    
    # Confidence Score
    confidence_score = CONFIDENCE_MAP.get(confidence, 0.55)
    
    # Weighted Average
    overall_strength = (
        volume_score * WEIGHT_VOLUME +
        strength_score * WEIGHT_STRENGTH +
        rr_score * WEIGHT_RR +
        confidence_score * WEIGHT_CONFIDENCE
    )
    
    return overall_strength


def get_volume_score(volume_ratio):
    if volume_ratio >= VOLUME_EXCELLENT: return 1.05
    elif volume_ratio >= VOLUME_GOOD: return 0.85
    elif volume_ratio >= VOLUME_MEDIUM: return 0.65
    elif volume_ratio >= VOLUME_LOW: return 0.35
    else: return 0.2


def get_rr_score(rr_ratio):
    if rr_ratio >= RR_EXCELLENT: return 1.05
    elif rr_ratio >= RR_GOOD: return 0.85
    elif rr_ratio >= RR_MEDIUM: return 0.65
    elif rr_ratio >= RR_MINIMUM: return 0.35
    else: return 0.2


def is_valid_setup(rr_ratio):
    return rr_ratio >= MIN_RR_RATIO
