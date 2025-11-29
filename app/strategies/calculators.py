# -*- coding: utf-8 -*-
"""
T-TARS Trading Calculators v1.4.9.3
===================================
Tüm katsayılar ve hesaplama fonksiyonları.
Fine-tuning için sadece bu dosyayı düzenle.

v1.4.9.3:
- format_price() eklendi - SHIB/DOGE gibi düşük fiyatlı coinler için dinamik format

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
# ATR MULTIPLIERS - STOP & TP
# ============================================
STOP_MULTIPLIER = 1.5      # Stop = OB edge - (ATR × 1.5)
TP1_MULTIPLIER = 2.0       # TP1 = Entry + (ATR × 2.0)
TP2_MULTIPLIER = 3.5       # TP2 = Entry + (ATR × 3.5)

# ============================================
# R:R THRESHOLDS
# ============================================
MIN_RR_RATIO = 2.0         # Minimum kabul edilen R:R

RR_EXCELLENT = 3.0         # R:R >= 3.0 → Score 1.0
RR_GOOD = 2.5              # R:R >= 2.5 → Score 0.8
RR_MEDIUM = 2.2            # R:R >= 2.2 → Score 0.6
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
    'high': 1.0,
    'medium': 0.6,
    'low': 0.3
}

# ============================================
# CONFIDENCE MAPPING
# ============================================
CONFIDENCE_MAP = {
    'HIGH': 1.0,
    'MEDIUM': 0.6,
    'LOW': 0.3
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
    
    Args:
        price: float fiyat değeri
    
    Returns:
        str: Formatlanmış fiyat ($ ile birlikte)
    
    Examples:
        format_price(95000.50) → "$95,000.50"
        format_price(0.00002345) → "$0.00002345"
        format_price(235.5678) → "$235.57"
    """
    if price is None or price == 0:
        return "$0.00"
    
    abs_price = abs(price)
    
    if abs_price < 0.0001:
        # SHIB gibi çok düşük: 8 ondalık
        return f"${price:.8f}"
    elif abs_price < 0.01:
        # Düşük fiyatlı: 6 ondalık
        return f"${price:.6f}"
    elif abs_price < 1:
        # Orta-düşük: 4 ondalık
        return f"${price:.4f}"
    elif abs_price < 100:
        # Normal: 4 ondalık (SOL, LTC gibi)
        return f"${price:,.4f}"
    else:
        # Yüksek fiyatlı (BTC, ETH, BNB): 2 ondalık
        return f"${price:,.2f}"


def format_price_raw(price):
    """
    Fiyatı $ olmadan formatla (log için)
    
    Returns:
        str: Formatlanmış fiyat ($ olmadan)
    """
    formatted = format_price(price)
    return formatted.replace("$", "")


def calculate_rr(entry_price, stop_price, tp_price):
    """
    Risk:Reward oranını hesapla.
    
    Args:
        entry_price: Giriş fiyatı
        stop_price: Stop loss fiyatı
        tp_price: Take profit fiyatı
    
    Returns:
        float: R:R oranı (0 eğer risk sıfırsa)
    """
    risk = abs(entry_price - stop_price)
    reward = abs(tp_price - entry_price)
    
    if risk == 0:
        return 0
    
    return reward / risk


def calculate_setup_strength(volume_spike_ratio, ob_or_fvg_strength, rr_ratio, confidence):
    """
    Setup gücünü hesapla (0-1 arası).
    
    Args:
        volume_spike_ratio: Volume spike oranı (örn: 2.5x)
        ob_or_fvg_strength: OB/FVG gücü ('high', 'medium', 'low')
        rr_ratio: Risk:Reward oranı
        confidence: Güven seviyesi ('HIGH', 'MEDIUM', 'LOW')
    
    Returns:
        float: Overall strength (0.0 - 1.0)
    """
    # Volume Score
    if volume_spike_ratio >= VOLUME_EXCELLENT:
        volume_score = 1.0
    elif volume_spike_ratio >= VOLUME_GOOD:
        volume_score = 0.8
    elif volume_spike_ratio >= VOLUME_MEDIUM:
        volume_score = 0.6
    elif volume_spike_ratio >= VOLUME_LOW:
        volume_score = 0.4
    else:
        volume_score = 0.2
    
    # OB/FVG Strength Score
    strength_score = STRENGTH_MAP.get(ob_or_fvg_strength.lower(), 0.5)
    
    # R:R Score
    if rr_ratio >= RR_EXCELLENT:
        rr_score = 1.0
    elif rr_ratio >= RR_GOOD:
        rr_score = 0.8
    elif rr_ratio >= RR_MEDIUM:
        rr_score = 0.6
    elif rr_ratio >= RR_MINIMUM:
        rr_score = 0.4
    else:
        rr_score = 0.2
    
    # Confidence Score
    confidence_score = CONFIDENCE_MAP.get(confidence, 0.5)
    
    # Weighted Average
    overall_strength = (
        volume_score * WEIGHT_VOLUME +
        strength_score * WEIGHT_STRENGTH +
        rr_score * WEIGHT_RR +
        confidence_score * WEIGHT_CONFIDENCE
    )
    
    return overall_strength


def get_volume_score(volume_ratio):
    """Volume ratio'dan score hesapla"""
    if volume_ratio >= VOLUME_EXCELLENT:
        return 1.0
    elif volume_ratio >= VOLUME_GOOD:
        return 0.8
    elif volume_ratio >= VOLUME_MEDIUM:
        return 0.6
    elif volume_ratio >= VOLUME_LOW:
        return 0.4
    else:
        return 0.2


def get_rr_score(rr_ratio):
    """R:R ratio'dan score hesapla"""
    if rr_ratio >= RR_EXCELLENT:
        return 1.0
    elif rr_ratio >= RR_GOOD:
        return 0.8
    elif rr_ratio >= RR_MEDIUM:
        return 0.6
    elif rr_ratio >= RR_MINIMUM:
        return 0.4
    else:
        return 0.2


def is_valid_setup(rr_ratio):
    """Setup R:R minimum kriteri karşılıyor mu?"""
    return rr_ratio >= MIN_RR_RATIO
