# -*- coding: utf-8 -*-
"""
T-TARS Trading Calculators v2.3.11
===================================
v2.3.11:
- CHANGED: calculate_setup_strength() 4 parametre → 3 parametre
- REMOVED: confidence parametresi (circular logic fix)
- NEW: Volume VETO - düşük volume = max LOW confidence garantisi
- CHANGED: Weight'ler: Volume %40, OB/FVG %40, R:R %20

v2.3.8:
- DRY prensibi: Score'lar constant olarak tanımlandı
- VOLUME_TRADEABLE_MIN eklendi (volume_analyzer ve claude_service import edecek)

Kullanım:
    from app.strategies.calculators import (
        calculate_setup_strength,
        calculate_rr,
        format_price,
        MIN_RR_RATIO,
        STOP_MULTIPLIER,
        TP1_MULTIPLIER,
        TP2_MULTIPLIER,
        VOLUME_TRADEABLE_MIN,
        VOLUME_LOW,
        VOLUME_GOOD,
        VOLUME_EXCELLENT
    )
"""

# ============================================
# ATR MULTIPLIERS - STOP & TP (FINE TUNING)
# ============================================
STOP_MULTIPLIER = 1.0      # Stop seviyesi: 1.0 ATR
TP1_MULTIPLIER = 2.0       # TP1: 2.0 ATR (R:R 2.0)
TP2_MULTIPLIER = 4.0       # TP2: 4.0 ATR (Ana hedef)

# ============================================
# R:R THRESHOLDS (Fine tuning buradan)
# ============================================
MIN_RR_RATIO = 2.0         # Minimum kabul edilebilir R:R
RR_EXCELLENT = 4.0         # Mükemmel
RR_GOOD = 3.5              # İyi
RR_MEDIUM = 3.0            # Orta
RR_MINIMUM = 2.0           # Minimum

# ============================================
# R:R SCORES (Fine tuning buradan)
# ============================================
SCORE_RR_EXCELLENT = 1.05  # Bonus
SCORE_RR_GOOD = 0.85
SCORE_RR_MEDIUM = 0.65
SCORE_RR_MINIMUM = 0.35
SCORE_RR_ELSE = 0.20

# ============================================
# VOLUME THRESHOLDS (Fine tuning buradan)
# ============================================
VOLUME_TRADEABLE_MIN = 0.5 # Minimum tradeable (bu altı = reject)
VOLUME_LOW = 0.8           # Düşük ama kabul edilebilir
VOLUME_MEDIUM = 1.2        # Orta
VOLUME_GOOD = 1.6          # İyi
VOLUME_EXCELLENT = 2.0     # Mükemmel volume spike

# Volume Spike Flag (boolean için) - bitget_service kullanıyor
VOLUME_SPIKE_FLAG = 1.5    # spike_ratio >= bu değer → spike=True

# Volume Strength Labels - bitget_service kullanıyor
VOLUME_STRENGTH_HIGH = 3.0   # >= 3.0 → 'high'
VOLUME_STRENGTH_MEDIUM = 2.0 # >= 2.0 → 'medium'
# else → 'low'

# ============================================
# VOLUME SCORES (Fine tuning buradan)
# ============================================
SCORE_VOLUME_EXCELLENT = 1.20  # Bonus
SCORE_VOLUME_GOOD = 0.90
SCORE_VOLUME_MEDIUM = 0.70
SCORE_VOLUME_LOW = 0.40
SCORE_VOLUME_ELSE = 0.25

# ============================================
# OB/FVG STRENGTH MAPPING (Fine tuning buradan)
# ============================================
STRENGTH_MAP = {
    'high': 1.15,    # Bonus
    'medium': 0.75,
    'low': 0.35
}

# ============================================
# FALLBACK DEFAULTS (Bilinmeyen değer gelirse)
# ============================================
DEFAULT_STRENGTH_SCORE = 0.25   # Bilinmeyen strength için

# ============================================
# WEIGHT DISTRIBUTION (Fine tuning buradan)
# v2.3.11: Confidence kaldırıldı (circular logic fix)
# ============================================
WEIGHT_VOLUME = 0.40       # Volume ağırlığı - EN KRİTİK
WEIGHT_STRENGTH = 0.40     # OB/FVG gücü ağırlığı
WEIGHT_RR = 0.20           # Risk:Reward ağırlığı (genelde sabit 2.0)
# Toplam = 1.0

# Volume Veto Threshold
VOLUME_VETO_MAX_SCORE = 0.45  # Volume < VOLUME_LOW ise max bu score


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


def get_volume_score(volume_ratio):
    """
    Volume spike oranına göre score döndür.
    Fine tuning: Dosya başındaki SCORE_VOLUME_* constant'larını değiştir.
    """
    if volume_ratio >= VOLUME_EXCELLENT:
        return SCORE_VOLUME_EXCELLENT
    elif volume_ratio >= VOLUME_GOOD:
        return SCORE_VOLUME_GOOD
    elif volume_ratio >= VOLUME_MEDIUM:
        return SCORE_VOLUME_MEDIUM
    elif volume_ratio >= VOLUME_LOW:
        return SCORE_VOLUME_LOW
    else:
        return SCORE_VOLUME_ELSE


def get_rr_score(rr_ratio):
    """
    Risk:Reward oranına göre score döndür.
    Fine tuning: Dosya başındaki SCORE_RR_* constant'larını değiştir.
    """
    if rr_ratio >= RR_EXCELLENT:
        return SCORE_RR_EXCELLENT
    elif rr_ratio >= RR_GOOD:
        return SCORE_RR_GOOD
    elif rr_ratio >= RR_MEDIUM:
        return SCORE_RR_MEDIUM
    elif rr_ratio >= RR_MINIMUM:
        return SCORE_RR_MINIMUM
    else:
        return SCORE_RR_ELSE


def calculate_setup_strength(volume_spike_ratio, ob_or_fvg_strength, rr_ratio):
    """
    Setup gücünü hesapla (0-1 arası, bonus ile 1.0'ı aşabilir).
    
    v2.3.11 DEĞİŞİKLİKLER:
    - confidence parametresi KALDIRILDI (circular logic fix)
    - Volume VETO eklendi: Volume < 0.8 → max 0.45 score (LOW garantisi)
    - Weight'ler: Volume %40, OB/FVG %40, R:R %20
    
    Args:
        volume_spike_ratio: Volume spike oranı (0.0 - 5.0+)
        ob_or_fvg_strength: 'high', 'medium', 'low'
        rr_ratio: Risk:Reward oranı (2.0+)
    
    Returns:
        float: Setup strength score (0.0 - 1.2)
    """
    # Volume Score
    volume_score = get_volume_score(volume_spike_ratio)
    
    # OB/FVG Strength Score
    strength_score = STRENGTH_MAP.get(ob_or_fvg_strength.lower(), DEFAULT_STRENGTH_SCORE)
    
    # R:R Score
    rr_score = get_rr_score(rr_ratio)
    
    # Weighted Average
    overall_strength = (
        volume_score * WEIGHT_VOLUME +
        strength_score * WEIGHT_STRENGTH +
        rr_score * WEIGHT_RR
    )
    
    # 🚨 VOLUME VETO: Düşük volume = maximum LOW confidence
    # Volume < 0.8 ise, diğer faktörler ne kadar iyi olursa olsun
    # score max 0.45'te kalır → _get_confidence_label() = LOW
    if volume_spike_ratio < VOLUME_LOW:
        overall_strength = min(overall_strength, VOLUME_VETO_MAX_SCORE)
    
    return overall_strength


def is_valid_setup(rr_ratio):
    """
    R:R minimum gerekliliği karşılıyor mu?
    """
    return rr_ratio >= MIN_RR_RATIO
