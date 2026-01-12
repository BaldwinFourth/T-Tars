# -*- coding: utf-8 -*-
"""
T-TARS Trading Calculators v2.8.0
===================================
v2.8.0:
- NEW: TIMEFRAME_HIERARCHY constant (1D > 1h > 15m)
- NEW: check_pdc_breakout() - PDC High/Low kırılma tespiti
- NEW: is_higher_tf_aligned() - Üst TF bias uyumu kontrolü
- NEW: get_intraday_bias() - Güncel fiyata göre intraday bias

v2.6.1:
- FIX: Momentum body_sizes artık body_ratio kullanıyor (universal, fiyattan bağımsız)
- FIX: Küçük fiyatlı coinlerde (PEPE, DOGE) 0.0 sorunu çözüldü

v2.6.0:
- NEW: Kapsamlı Candle Pattern Detection sistemi
- NEW: detect_candle_patterns() - Ana pattern tespit fonksiyonu
- NEW: Doji ailesi (Standard, Gravestone, Dragonfly, Long-legged)
- NEW: Hammer/Star ailesi (Hammer, Inverted Hammer, Shooting Star, Hanging Man)
- NEW: Engulfing patterns (Bullish/Bearish Engulfing)
- NEW: Piercing Line / Dark Cloud Cover
- NEW: Morning Star / Evening Star (3 mum)
- NEW: Three White Soldiers / Three Black Crows
- NEW: Momentum analizi (Shrinking/Growing bodies)
- NEW: Liquidity Sweep detection
- NEW: Trend context analizi (Son 5 mum)
- CHANGED: calculate_pdc_bias() artık detect_candle_patterns() kullanıyor

v2.5.1:
- CHANGED: FVG_ZONE_MIN = 0.50, FVG_ZONE_MAX = 1.50 (PDC içi + dışı)
- CHANGED: calculate_fibo_zones() - Bias-aware fibo hesabı

v2.5.0:
- OPTİMİZASYON: Volume, FVG, OB, RR threshold güncellendi. 

v2.4.10:
- CHANGED: MIN_RR_RATIO = 3.0 (eskiden 2.0)
- CHANGED: TP_MULTIPLIER = 3.0 (tek TP, eskiden TP1=2.0/TP2=4.0)
"""

import logging

logger = logging.getLogger(__name__)

# ============================================
# v2.7.0: TIMEFRAME HIERARCHY
# ============================================
# 1D (PDC) > 1h > 15m
# Üst timeframe bias'ı alt timeframe'i yönetir
TIMEFRAME_HIERARCHY = {
    '1D': 0,   # En yüksek öncelik (PDC)
    '4h': 1,
    '1h': 2,
    '15m': 3,
    '5m': 4,
    '3m': 5    # En düşük öncelik
}

# TF Grupları - aynı grup içindeki TF'ler aynı bias'ta olmalı
TF_GROUP_HTF = ['1D', '4h', '1h']  # Higher Timeframes
TF_GROUP_LTF = ['15m', '5m', '3m']  # Lower Timeframes

# ============================================
# ATR MULTIPLIERS - STOP & TP (v2.4.10)
# ============================================
STOP_MULTIPLIER = 1.0      # Stop seviyesi: 1.0 ATR
TP_MULTIPLIER = 3.0        # v2.4.10: Tek TP = 3.0 ATR (R:R 3.0)

# ============================================
# R:R THRESHOLDS (v2.4.10)
# ============================================
MIN_RR_RATIO = 3.0         # v2.4.10: Minimum R:R = 3.0 (eskiden 2.0)
RR_EXCELLENT = 5.0         # Mükemmel
RR_GOOD = 4.0              # İyi
RR_MEDIUM = 3.5            # Orta
RR_MINIMUM = 3.0           # Minimum

# ============================================
# R:R SCORES (Fine tuning buradan)
# ============================================
SCORE_RR_EXCELLENT = 1.50  # Bonus
SCORE_RR_GOOD = 1.00
SCORE_RR_MEDIUM = 0.65
SCORE_RR_MINIMUM = 0.50
SCORE_RR_ELSE = 0.10

# ============================================
# VOLUME THRESHOLDS (Fine tuning buradan)
# ============================================
VOLUME_TRADEABLE_MIN = 0.65 # Minimum tradeable (bu altı = reject)
VOLUME_LOW = 0.75           # Düşük ama kabul edilebilir
VOLUME_MEDIUM = 1.5        # Orta
VOLUME_GOOD = 2.0          # İyi
VOLUME_EXCELLENT = 2.5     # Mükemmel volume spike

# Volume Spike Flag (boolean için) - bitget_service kullanıyor
VOLUME_SPIKE_FLAG = 1.5    # spike_ratio >= bu değer → spike=True

# Volume Strength Labels - bitget_service kullanıyor
VOLUME_STRENGTH_HIGH = 2.0   # >= 2.0 → 'high'
VOLUME_STRENGTH_MEDIUM = 1.5 # >= 1.5 → 'medium'
# else → 'low'

# ============================================
# VOLUME SCORES (Fine tuning buradan)
# ============================================
SCORE_VOLUME_EXCELLENT = 1.50  # Bonus
SCORE_VOLUME_GOOD = 1.20
SCORE_VOLUME_MEDIUM = 0.80
SCORE_VOLUME_LOW = 0.50
SCORE_VOLUME_ELSE = 0.4

# ============================================
# OB/FVG STRENGTH MAPPING (Fine tuning buradan)
# ============================================
STRENGTH_MAP = {
    'high': 1.25,    # Bonus
    'medium': 0.75,
    'low': 0.30
}

# ============================================
# FALLBACK DEFAULTS (Bilinmeyen değer gelirse)
# ============================================
DEFAULT_STRENGTH_SCORE = 0.10   # Bilinmeyen strength için

# ============================================
# WEIGHT DISTRIBUTION (Fine tuning buradan)
# ============================================
WEIGHT_VOLUME = 0.45       # Volume ağırlığı - EN KRİTİK
WEIGHT_STRENGTH = 0.45     # OB/FVG gücü ağırlığı
WEIGHT_RR = 0.10           # Risk:Reward ağırlığı
# Toplam = 1.0

# Volume Veto Threshold
VOLUME_VETO_MAX_SCORE = 0.65  # Volume < VOLUME_LOW ise max bu score

# ============================================
# v2.4.0: OB/FVG MİNİMUM BOYUT (ATR bazlı)
# ============================================
MIN_OB_SIZE_ATR = 1.2      # OB en az 1.1 ATR olmalı
MIN_FVG_SIZE_ATR = 1.2     # FVG en az 1.1 ATR olmalı

# ============================================
# v2.5.1: LOOKBACK & ENTRY DISTANCE
# ============================================
OB_LOOKBACK = 200                  # OB arama: 15m ~3 gün, 1h ~12 gün
FVG_LOOKBACK = 200                 # FVG arama: 15m ~3 gün, 1h ~12 gün
MAX_ENTRY_DISTANCE_PERCENT = 2.0   # Entry max %2 uzaklıkta olmalı

# ============================================
# v2.5.1: MAX ZONE COUNTS
# ============================================
MAX_OB_COUNT = 3                   # En fazla 3 OB döndür
MAX_FVG_COUNT = 3                  # En fazla 3 FVG döndür

# ============================================
# v2.5.1: FİBO ZONE TANIMLARI (UPDATED!)
# ============================================
# OB Zone: PDC içi retracement (%70-90)
OB_ZONE_MIN = 0.60         # OB arama: %50-150
OB_ZONE_MAX = 1.50  

# FVG Zone: PDC içi + dışı (%50-150)
FVG_ZONE_MIN = 0.60        # v2.5.1: %50 (PDC orta noktası)
FVG_ZONE_MAX = 1.50        # v2.5.1: %150 (PDC dışı extension)

# ============================================
# v2.6.0: CANDLE PATTERN THRESHOLDS
# ============================================

# === DOJI THRESHOLDS ===
DOJI_BODY_THRESHOLD = 0.10        # Body < %10 = Doji
DOJI_SHADOW_RATIO = 2.0           # Gölge/body oranı (Gravestone/Dragonfly için)
DOJI_LONGLEG_MULTIPLIER = 3.0     # Long-legged doji: gölge > body×3

# === HAMMER/STAR THRESHOLDS ===
HAMMER_SHADOW_RATIO = 2.0         # Alt gölge ≥ 2x body
HAMMER_OPPOSITE_MAX = 0.3         # Karşı gölge < %30 body

# === ENGULFING THRESHOLDS ===
ENGULF_MIN_RATIO = 1.0            # 2. body ≥ 1. body
ENGULF_PARTIAL_RATIO = 0.7        # Partial engulf için min %70

# === PIERCING/DARK CLOUD THRESHOLDS ===
PIERCING_MIN_RATIO = 0.5          # En az %50 penetrasyon

# === MOMENTUM THRESHOLDS ===
MOMENTUM_SHRINK_RATIO = 0.7       # Body < öncekinin %70'i = shrinking
MOMENTUM_GROW_RATIO = 1.3         # Body > öncekinin %130'u = growing
MOMENTUM_MIN_COUNT = 2            # En az 2 ardışık değişim

# === TREND CONTEXT ===
TREND_MIN_CANDLES = 3             # Min 3 aynı yönlü mum = trend
TREND_LOOKBACK = 5                # Son 5 muma bak

# === LIQUIDITY SWEEP THRESHOLDS ===
SWEEP_WICK_RATIO = 0.6            # Wick > range'in %60'ı
SWEEP_LOOKBACK = 5                # Swing high/low için geriye bak

# === CONFIDENCE WEIGHTS ===
CONFIDENCE_3_CANDLE = 0.95        # 3 mum pattern (Star)
CONFIDENCE_2_CANDLE = 0.85        # 2 mum pattern (Engulfing)
CONFIDENCE_1_CANDLE = 0.70        # 1 mum pattern (Doji/Hammer)
CONFIDENCE_MOMENTUM = 0.60        # Momentum analizi

# === CONTEXT MULTIPLIERS ===
CONTEXT_REVERSAL_BONUS = 1.2      # Doğru konumda bonus
CONTEXT_WRONG_PENALTY = 0.5       # Yanlış konumda ceza


# ============================================
# HELPER FUNCTIONS
# ============================================

def format_price(price):
    """Fiyatı dinamik formatta string'e çevir."""
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
    """Fiyatı $ olmadan formatla (log için)"""
    formatted = format_price(price)
    return formatted.replace("$", "")


def calculate_rr(entry_price, stop_price, tp_price):
    """Risk:Reward oranını hesapla."""
    risk = abs(entry_price - stop_price)
    reward = abs(tp_price - entry_price)
    
    if risk == 0:
        return 0
    
    return reward / risk


def get_volume_score(volume_ratio):
    """Volume spike oranına göre score döndür."""
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
    """Risk:Reward oranına göre score döndür."""
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
    """Setup gücünü hesapla (0-1 arası, bonus ile 1.0'ı aşabilir)."""
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
    
    # Volume VETO
    if volume_spike_ratio < VOLUME_LOW:
        overall_strength = min(overall_strength, VOLUME_VETO_MAX_SCORE)
    
    return overall_strength


def is_valid_setup(rr_ratio):
    """R:R minimum gerekliliği karşılıyor mu?"""
    return rr_ratio >= MIN_RR_RATIO


# ============================================
# v2.7.0: PDC BREAKOUT & INTRADAY BIAS
# ============================================

def check_pdc_breakout(current_price, pdc, previous_bias):
    """
    PDC High/Low kırılma kontrolü.
    
    Kural:
    - Fiyat PDC High'ı kırarsa → Bias LONG'a döner
    - Fiyat PDC Low'u kırarsa → Bias SHORT'a döner
    
    Args:
        current_price: Şu anki fiyat
        pdc: {'high', 'low', 'open', 'close', 'type'}
        previous_bias: Önceki bias ('LONG' veya 'SHORT')
    
    Returns:
        {
            'breakout_detected': bool,
            'breakout_type': 'HIGH' | 'LOW' | None,
            'new_bias': 'LONG' | 'SHORT',
            'bias_changed': bool,
            'message': str
        }
    """
    if not pdc or current_price <= 0:
        return {
            'breakout_detected': False,
            'breakout_type': None,
            'new_bias': previous_bias,
            'bias_changed': False,
            'message': 'Yetersiz veri'
        }
    
    pdc_high = pdc.get('high', 0)
    pdc_low = pdc.get('low', 0)
    
    # PDC High kırıldı mı?
    if current_price > pdc_high:
        new_bias = 'LONG'
        bias_changed = previous_bias != 'LONG'
        
        return {
            'breakout_detected': True,
            'breakout_type': 'HIGH',
            'new_bias': new_bias,
            'bias_changed': bias_changed,
            'message': f'PDC High ({format_price(pdc_high)}) kırıldı → Intraday bias: LONG'
        }
    
    # PDC Low kırıldı mı?
    if current_price < pdc_low:
        new_bias = 'SHORT'
        bias_changed = previous_bias != 'SHORT'
        
        return {
            'breakout_detected': True,
            'breakout_type': 'LOW',
            'new_bias': new_bias,
            'bias_changed': bias_changed,
            'message': f'PDC Low ({format_price(pdc_low)}) kırıldı → Intraday bias: SHORT'
        }
    
    # Fiyat PDC içinde
    return {
        'breakout_detected': False,
        'breakout_type': None,
        'new_bias': previous_bias,
        'bias_changed': False,
        'message': f'Fiyat PDC içinde ({format_price(pdc_low)} - {format_price(pdc_high)})'
    }


def get_intraday_bias(current_price, pdc, pdc_bias):
    """
    Güncel fiyata göre intraday bias belirle.
    
    Mantık:
    1. PDC rengine göre base bias belirlenir
    2. Fiyat PDC High'ı kırarsa → LONG (bullish breakout)
    3. Fiyat PDC Low'u kırarsa → SHORT (bearish breakout)
    4. Fiyat PDC içindeyse → PDC bias'ı geçerli
    
    Args:
        current_price: Şu anki fiyat
        pdc: {'high', 'low', 'open', 'close', 'type'}
        pdc_bias: PDC'den gelen bias ('LONG' veya 'SHORT')
    
    Returns:
        {
            'bias': 'LONG' | 'SHORT',
            'source': 'PDC' | 'BREAKOUT_HIGH' | 'BREAKOUT_LOW',
            'in_pdc_range': bool
        }
    """
    if not pdc or current_price <= 0:
        return {
            'bias': pdc_bias,
            'source': 'PDC',
            'in_pdc_range': True
        }
    
    pdc_high = pdc.get('high', 0)
    pdc_low = pdc.get('low', 0)
    
    # PDC High kırıldı
    if current_price > pdc_high:
        return {
            'bias': 'LONG',
            'source': 'BREAKOUT_HIGH',
            'in_pdc_range': False
        }
    
    # PDC Low kırıldı
    if current_price < pdc_low:
        return {
            'bias': 'SHORT',
            'source': 'BREAKOUT_LOW',
            'in_pdc_range': False
        }
    
    # PDC içinde - PDC bias'ı kullan
    return {
        'bias': pdc_bias,
        'source': 'PDC',
        'in_pdc_range': True
    }


def is_higher_tf_aligned(setup_tf, setup_direction, htf_bias):
    """
    Setup timeframe'inin üst TF bias'ıyla uyumlu olup olmadığını kontrol et.
    
    Kural: 1D (PDC) > 1h > 15m
    - 15m setup yalnızca 1h ve 1D aynı yönde ise geçerli
    - 1h setup yalnızca 1D ile aynı yönde ise geçerli
    
    Args:
        setup_tf: Setup timeframe'i ('15m', '1h', vb.)
        setup_direction: Setup yönü ('LONG' veya 'SHORT')
        htf_bias: Üst TF bias bilgisi {'1D': 'LONG', '1h': 'LONG', ...}
    
    Returns:
        {
            'aligned': bool,
            'conflicts': list,  # Uyumsuz TF'ler
            'message': str
        }
    """
    if not htf_bias:
        return {
            'aligned': True,
            'conflicts': [],
            'message': 'HTF verisi yok, kontrol atlandı'
        }
    
    setup_priority = TIMEFRAME_HIERARCHY.get(setup_tf, 99)
    conflicts = []
    
    # Daha yüksek öncelikli (daha küçük numara) TF'leri kontrol et
    for tf, priority in TIMEFRAME_HIERARCHY.items():
        if priority < setup_priority:  # Daha yüksek TF
            tf_bias = htf_bias.get(tf)
            if tf_bias and tf_bias != setup_direction:
                conflicts.append(f"{tf}={tf_bias}")
    
    if conflicts:
        return {
            'aligned': False,
            'conflicts': conflicts,
            'message': f'{setup_tf} {setup_direction} HTF ile uyumsuz: {", ".join(conflicts)}'
        }
    
    return {
        'aligned': True,
        'conflicts': [],
        'message': f'{setup_tf} {setup_direction} HTF ile uyumlu'
    }


def get_tf_priority(timeframe):
    """Timeframe öncelik sırasını döndür (düşük = yüksek öncelik)."""
    return TIMEFRAME_HIERARCHY.get(timeframe, 99)


def is_tf_higher(tf1, tf2):
    """tf1, tf2'den daha yüksek TF mi?"""
    return get_tf_priority(tf1) < get_tf_priority(tf2)


# ============================================
# v2.6.0: CANDLE PATTERN DETECTION SYSTEM
# ============================================

def _get_candle_metrics(candle):
    """
    Tek mum için metrik hesapla.
    
    Args:
        candle: [timestamp, open, high, low, close, volume]
    
    Returns:
        dict: {open, high, low, close, body, range, upper_shadow, lower_shadow, 
               body_ratio, is_green, ...}
    """
    if len(candle) < 5:
        return None
    
    o, h, l, c = float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4])
    
    body = abs(c - o)
    range_ = h - l
    
    # Gölge hesaplamaları
    if c >= o:  # Yeşil mum
        upper_shadow = h - c
        lower_shadow = o - l
        is_green = True
    else:  # Kırmızı mum
        upper_shadow = h - o
        lower_shadow = c - l
        is_green = False
    
    # Oranlar (sıfıra bölme koruması)
    body_ratio = body / range_ if range_ > 0 else 0
    upper_ratio = upper_shadow / range_ if range_ > 0 else 0
    lower_ratio = lower_shadow / range_ if range_ > 0 else 0
    
    return {
        'open': o,
        'high': h,
        'low': l,
        'close': c,
        'body': body,
        'range': range_,
        'upper_shadow': upper_shadow,
        'lower_shadow': lower_shadow,
        'body_ratio': body_ratio,
        'upper_ratio': upper_ratio,
        'lower_ratio': lower_ratio,
        'is_green': is_green,
        'is_red': not is_green
    }


def _determine_trend_context(candles):
    """
    Son 5 mumdan trend belirle.
    
    Args:
        candles: Son 5+ mum listesi
    
    Returns:
        dict: {trend, green_count, red_count, close_trend, ...}
    """
    if not candles or len(candles) < TREND_LOOKBACK:
        return {
            'trend': 'RANGE',
            'green_count': 0,
            'red_count': 0,
            'close_trend': 'FLAT',
            'is_downtrend': False,
            'is_uptrend': False
        }
    
    last_5 = candles[-TREND_LOOKBACK:]
    
    green_count = 0
    red_count = 0
    closes = []
    
    for c in last_5:
        metrics = _get_candle_metrics(c)
        if metrics:
            if metrics['is_green']:
                green_count += 1
            else:
                red_count += 1
            closes.append(metrics['close'])
    
    # Close trend belirleme
    if len(closes) >= 3:
        rising = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        falling = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])
        
        if rising >= 3:
            close_trend = 'RISING'
        elif falling >= 3:
            close_trend = 'FALLING'
        else:
            close_trend = 'MIXED'
    else:
        close_trend = 'UNKNOWN'
    
    # Trend belirleme
    if green_count >= TREND_MIN_CANDLES or close_trend == 'RISING':
        trend = 'UPTREND'
        is_uptrend = True
        is_downtrend = False
    elif red_count >= TREND_MIN_CANDLES or close_trend == 'FALLING':
        trend = 'DOWNTREND'
        is_uptrend = False
        is_downtrend = True
    else:
        trend = 'RANGE'
        is_uptrend = False
        is_downtrend = False
    
    return {
        'trend': trend,
        'green_count': green_count,
        'red_count': red_count,
        'close_trend': close_trend,
        'is_downtrend': is_downtrend,
        'is_uptrend': is_uptrend
    }


def _detect_doji_type(candle):
    """
    Doji tipini tespit et.
    
    Returns:
        dict: {is_doji, doji_type, signal, ...} veya None
    """
    metrics = _get_candle_metrics(candle)
    if not metrics:
        return None
    
    # Doji kontrolü: body < range'in %10'u
    if metrics['body_ratio'] >= DOJI_BODY_THRESHOLD:
        return None
    
    # Doji tipi belirleme
    upper = metrics['upper_shadow']
    lower = metrics['lower_shadow']
    body = metrics['body']
    
    # Sıfıra bölme koruması
    if body == 0:
        body = 0.0001
    
    upper_body_ratio = upper / body if body > 0 else 0
    lower_body_ratio = lower / body if body > 0 else 0
    
    # Gravestone Doji: Üst gölge dominant
    if upper > lower * DOJI_SHADOW_RATIO and metrics['upper_ratio'] > 0.6:
        doji_type = 'GRAVESTONE'
        signal = 'BEARISH'
        description = 'Gravestone Doji - Üst gölge dominant, bearish sinyal'
    
    # Dragonfly Doji: Alt gölge dominant
    elif lower > upper * DOJI_SHADOW_RATIO and metrics['lower_ratio'] > 0.6:
        doji_type = 'DRAGONFLY'
        signal = 'BULLISH'
        description = 'Dragonfly Doji - Alt gölge dominant, bullish sinyal'
    
    # Long-legged Doji: Her iki gölge uzun
    elif upper_body_ratio >= DOJI_LONGLEG_MULTIPLIER and lower_body_ratio >= DOJI_LONGLEG_MULTIPLIER:
        doji_type = 'LONG_LEGGED'
        signal = 'NEUTRAL'
        description = 'Long-legged Doji - Extreme kararsızlık'
    
    # Standard Doji
    else:
        doji_type = 'STANDARD'
        signal = 'NEUTRAL'
        description = 'Standard Doji - Kararsızlık'
    
    return {
        'is_doji': True,
        'doji_type': doji_type,
        'signal': signal,
        'description': description,
        'body_ratio': round(metrics['body_ratio'] * 100, 2),
        'upper_ratio': round(metrics['upper_ratio'] * 100, 2),
        'lower_ratio': round(metrics['lower_ratio'] * 100, 2)
    }


def _detect_hammer_star(candle, trend_context):
    """
    Hammer/Star ailesi tespit et (konum önemli!).
    
    Args:
        candle: Mum verisi
        trend_context: Trend bilgisi (_determine_trend_context çıktısı)
    
    Returns:
        dict veya None
    """
    metrics = _get_candle_metrics(candle)
    if not metrics:
        return None
    
    body = metrics['body']
    upper = metrics['upper_shadow']
    lower = metrics['lower_shadow']
    
    # Sıfıra bölme koruması
    if body == 0:
        body = 0.0001
    
    # Hammer/Hanging Man: Alt gölge uzun
    if lower >= body * HAMMER_SHADOW_RATIO and upper < body * HAMMER_OPPOSITE_MAX:
        if trend_context['is_downtrend']:
            # Düşüş sonrası = Hammer (Bullish)
            return {
                'pattern_type': 'HAMMER',
                'pattern_name': 'Hammer',
                'signal': 'BULLISH',
                'signal_strength': 'STRONG',
                'description': 'Düşüş sonrası Hammer - Güçlü bullish reversal',
                'is_reversal_position': True
            }
        elif trend_context['is_uptrend']:
            # Yükseliş sonrası = Hanging Man (Bearish)
            return {
                'pattern_type': 'HANGING_MAN',
                'pattern_name': 'Hanging Man',
                'signal': 'BEARISH',
                'signal_strength': 'MEDIUM',
                'description': 'Yükseliş sonrası Hanging Man - Bearish uyarı',
                'is_reversal_position': True
            }
    
    # Shooting Star/Inverted Hammer: Üst gölge uzun
    if upper >= body * HAMMER_SHADOW_RATIO and lower < body * HAMMER_OPPOSITE_MAX:
        if trend_context['is_uptrend']:
            # Yükseliş sonrası = Shooting Star (Bearish)
            return {
                'pattern_type': 'SHOOTING_STAR',
                'pattern_name': 'Shooting Star',
                'signal': 'BEARISH',
                'signal_strength': 'STRONG',
                'description': 'Yükseliş sonrası Shooting Star - Güçlü bearish reversal',
                'is_reversal_position': True
            }
        elif trend_context['is_downtrend']:
            # Düşüş sonrası = Inverted Hammer (Bullish, zayıf)
            return {
                'pattern_type': 'INVERTED_HAMMER',
                'pattern_name': 'Inverted Hammer',
                'signal': 'BULLISH',
                'signal_strength': 'WEAK',
                'description': 'Düşüş sonrası Inverted Hammer - Zayıf bullish sinyal',
                'is_reversal_position': True
            }
    
    return None


def _detect_engulfing(candle1, candle2):
    """
    Engulfing pattern tespit et.
    
    Args:
        candle1: Önceki mum
        candle2: Son mum (engulf eden)
    
    Returns:
        dict veya None
    """
    m1 = _get_candle_metrics(candle1)
    m2 = _get_candle_metrics(candle2)
    
    if not m1 or not m2:
        return None
    
    # Bullish Engulfing: Kırmızı → Yeşil, 2. body > 1. body
    if m1['is_red'] and m2['is_green']:
        if m2['body'] >= m1['body'] * ENGULF_MIN_RATIO and m2['close'] > m1['open']:
            # Perfect engulf kontrolü
            is_perfect = m2['high'] >= m1['high'] and m2['low'] <= m1['low']
            
            engulf_ratio = m2['body'] / m1['body'] if m1['body'] > 0 else 1.0
            
            return {
                'pattern_type': 'ENGULFING',
                'pattern_name': 'Bullish Engulfing',
                'signal': 'BULLISH',
                'signal_strength': 'VERY_STRONG' if is_perfect else 'STRONG',
                'description': f'Bullish Engulfing ({"Perfect" if is_perfect else "Body"}) - Güçlü reversal',
                'is_perfect': is_perfect,
                'engulf_ratio': round(engulf_ratio, 2)
            }
    
    # Bearish Engulfing: Yeşil → Kırmızı, 2. body > 1. body
    if m1['is_green'] and m2['is_red']:
        if m2['body'] >= m1['body'] * ENGULF_MIN_RATIO and m2['close'] < m1['open']:
            # Perfect engulf kontrolü
            is_perfect = m2['high'] >= m1['high'] and m2['low'] <= m1['low']
            
            engulf_ratio = m2['body'] / m1['body'] if m1['body'] > 0 else 1.0
            
            return {
                'pattern_type': 'ENGULFING',
                'pattern_name': 'Bearish Engulfing',
                'signal': 'BEARISH',
                'signal_strength': 'VERY_STRONG' if is_perfect else 'STRONG',
                'description': f'Bearish Engulfing ({"Perfect" if is_perfect else "Body"}) - Güçlü reversal',
                'is_perfect': is_perfect,
                'engulf_ratio': round(engulf_ratio, 2)
            }
    
    return None


def _detect_piercing_darkcloud(candle1, candle2):
    """
    Piercing Line / Dark Cloud Cover tespit et.
    
    Returns:
        dict veya None
    """
    m1 = _get_candle_metrics(candle1)
    m2 = _get_candle_metrics(candle2)
    
    if not m1 or not m2:
        return None
    
    # Piercing Line: Kırmızı → Yeşil, %50+ penetrasyon
    if m1['is_red'] and m2['is_green']:
        # 2. mum 1. mumun altından açılıp, body'nin %50'sinden fazlasını kapatmalı
        if m2['open'] < m1['close']:
            penetration = (m2['close'] - m1['close']) / m1['body'] if m1['body'] > 0 else 0
            
            if penetration >= PIERCING_MIN_RATIO:
                return {
                    'pattern_type': 'PIERCING',
                    'pattern_name': 'Piercing Line',
                    'signal': 'BULLISH',
                    'signal_strength': 'MEDIUM',
                    'description': f'Piercing Line - %{penetration*100:.0f} penetrasyon',
                    'penetration': round(penetration * 100, 1)
                }
    
    # Dark Cloud Cover: Yeşil → Kırmızı, %50+ penetrasyon
    if m1['is_green'] and m2['is_red']:
        # 2. mum 1. mumun üstünden açılıp, body'nin %50'sinden fazlasını kapatmalı
        if m2['open'] > m1['close']:
            penetration = (m1['close'] - m2['close']) / m1['body'] if m1['body'] > 0 else 0
            
            if penetration >= PIERCING_MIN_RATIO:
                return {
                    'pattern_type': 'DARK_CLOUD',
                    'pattern_name': 'Dark Cloud Cover',
                    'signal': 'BEARISH',
                    'signal_strength': 'MEDIUM',
                    'description': f'Dark Cloud Cover - %{penetration*100:.0f} penetrasyon',
                    'penetration': round(penetration * 100, 1)
                }
    
    return None


def _detect_morning_evening_star(candle1, candle2, candle3, trend_context):
    """
    Morning Star / Evening Star tespit et (3 mum pattern).
    
    Args:
        candle1: İlk mum (büyük)
        candle2: Orta mum (küçük/doji)
        candle3: Son mum (büyük)
        trend_context: Trend bilgisi
    
    Returns:
        dict veya None
    """
    m1 = _get_candle_metrics(candle1)
    m2 = _get_candle_metrics(candle2)
    m3 = _get_candle_metrics(candle3)
    
    if not m1 or not m2 or not m3:
        return None
    
    # Orta mum küçük olmalı (doji veya small body)
    is_middle_small = m2['body_ratio'] < 0.3 or m2['body'] < min(m1['body'], m3['body']) * 0.5
    
    if not is_middle_small:
        return None
    
    # Morning Star: Kırmızı → Küçük → Yeşil (Downtrend sonunda)
    if m1['is_red'] and m3['is_green'] and m3['close'] > (m1['open'] + m1['close']) / 2:
        is_doji_star = m2['body_ratio'] < DOJI_BODY_THRESHOLD
        
        return {
            'pattern_type': 'MORNING_STAR',
            'pattern_name': 'Morning Star' + (' (Doji)' if is_doji_star else ''),
            'signal': 'BULLISH',
            'signal_strength': 'VERY_STRONG',
            'description': 'Morning Star - Çok güçlü bullish reversal',
            'is_doji_star': is_doji_star,
            'is_reversal_position': trend_context['is_downtrend']
        }
    
    # Evening Star: Yeşil → Küçük → Kırmızı (Uptrend sonunda)
    if m1['is_green'] and m3['is_red'] and m3['close'] < (m1['open'] + m1['close']) / 2:
        is_doji_star = m2['body_ratio'] < DOJI_BODY_THRESHOLD
        
        return {
            'pattern_type': 'EVENING_STAR',
            'pattern_name': 'Evening Star' + (' (Doji)' if is_doji_star else ''),
            'signal': 'BEARISH',
            'signal_strength': 'VERY_STRONG',
            'description': 'Evening Star - Çok güçlü bearish reversal',
            'is_doji_star': is_doji_star,
            'is_reversal_position': trend_context['is_uptrend']
        }
    
    return None


def _detect_three_soldiers_crows(candle1, candle2, candle3):
    """
    Three White Soldiers / Three Black Crows tespit et.
    
    Returns:
        dict veya None
    """
    m1 = _get_candle_metrics(candle1)
    m2 = _get_candle_metrics(candle2)
    m3 = _get_candle_metrics(candle3)
    
    if not m1 or not m2 or not m3:
        return None
    
    # Three White Soldiers: 3 ardışık yeşil, her biri öncekinin üstünde kapanır
    if m1['is_green'] and m2['is_green'] and m3['is_green']:
        if m2['close'] > m1['close'] and m3['close'] > m2['close']:
            if m2['open'] > m1['open'] and m3['open'] > m2['open']:
                return {
                    'pattern_type': 'THREE_SOLDIERS',
                    'pattern_name': 'Three White Soldiers',
                    'signal': 'BULLISH',
                    'signal_strength': 'STRONG',
                    'description': 'Three White Soldiers - Güçlü bullish trend başlangıcı'
                }
    
    # Three Black Crows: 3 ardışık kırmızı, her biri öncekinin altında kapanır
    if m1['is_red'] and m2['is_red'] and m3['is_red']:
        if m2['close'] < m1['close'] and m3['close'] < m2['close']:
            if m2['open'] < m1['open'] and m3['open'] < m2['open']:
                return {
                    'pattern_type': 'THREE_CROWS',
                    'pattern_name': 'Three Black Crows',
                    'signal': 'BEARISH',
                    'signal_strength': 'STRONG',
                    'description': 'Three Black Crows - Güçlü bearish trend başlangıcı'
                }
    
    return None


def _analyze_momentum(candles):
    """
    Body size trend analizi (momentum).
    
    Args:
        candles: Son 5+ mum
    
    Returns:
        dict: {trend, body_sizes, pressure, ...}
    """
    if not candles or len(candles) < 4:
        return {
            'trend': 'UNKNOWN',
            'body_sizes': [],
            'pressure': 'NONE',
            'shrinking_count': 0,
            'growing_count': 0
        }
    
    # Son 4 mum için body size
    body_sizes = []
    upper_shadows = []
    lower_shadows = []
    
    for c in candles[-4:]:
        metrics = _get_candle_metrics(c)
        if metrics:
            body_sizes.append(round(metrics['body_ratio'] * 100, 1))  # % olarak
            upper_shadows.append(metrics['upper_shadow'])
            lower_shadows.append(metrics['lower_shadow'])
    
    if len(body_sizes) < 3:
        return {
            'trend': 'UNKNOWN',
            'body_sizes': body_sizes,
            'pressure': 'NONE',
            'shrinking_count': 0,
            'growing_count': 0
        }
    
    # Shrinking/Growing analizi
    shrinking_count = 0
    growing_count = 0
    
    for i in range(1, len(body_sizes)):
        prev_body = body_sizes[i-1] if body_sizes[i-1] > 0 else 0.0001
        
        if body_sizes[i] < prev_body * MOMENTUM_SHRINK_RATIO:
            shrinking_count += 1
        elif body_sizes[i] > prev_body * MOMENTUM_GROW_RATIO:
            growing_count += 1
    
    # Trend belirleme
    if shrinking_count >= MOMENTUM_MIN_COUNT:
        trend = 'SHRINKING'
    elif growing_count >= MOMENTUM_MIN_COUNT:
        trend = 'GROWING'
    else:
        trend = 'STABLE'
    
    # Gölge baskısı analizi
    avg_upper = sum(upper_shadows) / len(upper_shadows) if upper_shadows else 0
    avg_lower = sum(lower_shadows) / len(lower_shadows) if lower_shadows else 0
    avg_body = sum(body_sizes) / len(body_sizes) if body_sizes else 1
    
    if avg_upper > avg_body and avg_upper > avg_lower * 1.5:
        pressure = 'UPPER_SHADOW'  # Satış baskısı
    elif avg_lower > avg_body and avg_lower > avg_upper * 1.5:
        pressure = 'LOWER_SHADOW'  # Alım baskısı
    else:
        pressure = 'NONE'
    
    return {
        'trend': trend,
        'body_sizes': body_sizes,
        'pressure': pressure,
        'shrinking_count': shrinking_count,
        'growing_count': growing_count
    }


def _detect_liquidity_sweep(candles):
    """
    Liquidity sweep tespiti.
    
    Sweep = Fiyat önceki swing high/low'u kırıp geri dönüyor.
    
    Returns:
        dict veya None
    """
    if not candles or len(candles) < SWEEP_LOOKBACK:
        return None
    
    last_candles = candles[-SWEEP_LOOKBACK:]
    current = _get_candle_metrics(last_candles[-1])
    
    if not current:
        return None
    
    # Önceki mumların high/low'larını bul
    prev_highs = []
    prev_lows = []
    
    for c in last_candles[:-1]:  # Son mum hariç
        m = _get_candle_metrics(c)
        if m:
            prev_highs.append(m['high'])
            prev_lows.append(m['low'])
    
    if not prev_highs or not prev_lows:
        return None
    
    max_prev_high = max(prev_highs)
    min_prev_low = min(prev_lows)
    
    # Sweep up sonra aşağı kapanış (Bearish Sweep)
    if current['high'] > max_prev_high:
        # Wick yukarı uzanmış ama aşağı kapanmış
        upper_wick_ratio = current['upper_shadow'] / current['range'] if current['range'] > 0 else 0
        
        if upper_wick_ratio >= SWEEP_WICK_RATIO and current['is_red']:
            return {
                'pattern_type': 'LIQUIDITY_SWEEP',
                'pattern_name': 'Bearish Liquidity Sweep',
                'signal': 'BEARISH',
                'signal_strength': 'STRONG',
                'description': f'High sweep: Önceki high ({format_price(max_prev_high)}) kırılıp geri dönüldü',
                'swept_level': max_prev_high,
                'sweep_direction': 'UP'
            }
    
    # Sweep down sonra yukarı kapanış (Bullish Sweep)
    if current['low'] < min_prev_low:
        # Wick aşağı uzanmış ama yukarı kapanmış
        lower_wick_ratio = current['lower_shadow'] / current['range'] if current['range'] > 0 else 0
        
        if lower_wick_ratio >= SWEEP_WICK_RATIO and current['is_green']:
            return {
                'pattern_type': 'LIQUIDITY_SWEEP',
                'pattern_name': 'Bullish Liquidity Sweep',
                'signal': 'BULLISH',
                'signal_strength': 'STRONG',
                'description': f'Low sweep: Önceki low ({format_price(min_prev_low)}) kırılıp geri dönüldü',
                'swept_level': min_prev_low,
                'sweep_direction': 'DOWN'
            }
    
    return None


def detect_candle_patterns(daily_ohlcv):
    """
    ANA FONKSİYON: Tüm candle pattern'ları tespit et.
    
    Args:
        daily_ohlcv: Son 5+ daily mum [[ts, o, h, l, c, v], ...]
    
    Returns:
        dict: Kapsamlı pattern analizi
    """
    logger.debug(f"🕯️ detect_candle_patterns() ENTRY | candles: {len(daily_ohlcv) if daily_ohlcv else 0}")
    
    # Default result
    default_result = {
        'pattern_detected': False,
        'pattern_type': None,
        'pattern_name': None,
        'candles_used': 0,
        'signal': 'NEUTRAL',
        'signal_strength': 'NONE',
        'confidence': 0.0,
        'trend_context': 'UNKNOWN',
        'is_reversal_position': False,
        'momentum': {
            'trend': 'UNKNOWN',
            'body_sizes': [],
            'pressure': 'NONE'
        },
        'all_patterns': [],
        'bias_suggestion': None,
        'skip_recommended': False,
        'description': 'Pattern tespit edilemedi'
    }
    
    if not daily_ohlcv or len(daily_ohlcv) < 5:
        logger.warning(f"⚠️ detect_candle_patterns: Yetersiz veri ({len(daily_ohlcv) if daily_ohlcv else 0} mum)")
        return default_result
    
    all_patterns = []
    
    # Trend context belirle
    trend_context = _determine_trend_context(daily_ohlcv)
    logger.debug(f"📈 Trend context: {trend_context['trend']} (G:{trend_context['green_count']}/R:{trend_context['red_count']})")
    
    # Son mumları al
    last_5 = daily_ohlcv[-5:]
    c1 = last_5[-3] if len(last_5) >= 3 else None  # 3. son mum
    c2 = last_5[-2] if len(last_5) >= 2 else None  # 2. son mum (PDC)
    c3 = last_5[-1] if len(last_5) >= 1 else None  # Son mum (bugün - açık)
    
    # ============================================
    # 1. ÜÇ MUM PATTERNLERİ (En güvenilir)
    # ============================================
    
    # Morning/Evening Star
    if c1 and c2 and c3:
        star = _detect_morning_evening_star(c1, c2, c3, trend_context)
        if star:
            star['confidence'] = CONFIDENCE_3_CANDLE
            star['candles_used'] = 3
            all_patterns.append(star)
            logger.info(f"⭐ 3-Candle Pattern: {star['pattern_name']} | Signal: {star['signal']} | Strength: {star['signal_strength']}")
        
        # Three Soldiers/Crows
        soldiers_crows = _detect_three_soldiers_crows(c1, c2, c3)
        if soldiers_crows:
            soldiers_crows['confidence'] = CONFIDENCE_3_CANDLE
            soldiers_crows['candles_used'] = 3
            all_patterns.append(soldiers_crows)
            logger.info(f"🎖️ 3-Candle Pattern: {soldiers_crows['pattern_name']} | Signal: {soldiers_crows['signal']}")
    
    # ============================================
    # 2. İKİ MUM PATTERNLERİ
    # ============================================
    
    if c2 and c3:
        # Engulfing
        engulfing = _detect_engulfing(c2, c3)
        if engulfing:
            engulfing['confidence'] = CONFIDENCE_2_CANDLE
            engulfing['candles_used'] = 2
            all_patterns.append(engulfing)
            logger.info(f"🔄 2-Candle Pattern: {engulfing['pattern_name']} | Signal: {engulfing['signal']} | Ratio: {engulfing.get('engulf_ratio', 'N/A')}")
        
        # Piercing/Dark Cloud
        piercing = _detect_piercing_darkcloud(c2, c3)
        if piercing:
            piercing['confidence'] = CONFIDENCE_2_CANDLE * 0.9  # Biraz daha düşük
            piercing['candles_used'] = 2
            all_patterns.append(piercing)
            logger.info(f"☁️ 2-Candle Pattern: {piercing['pattern_name']} | Signal: {piercing['signal']}")
    
    # ============================================
    # 3. LİKİDİTE SWEEP
    # ============================================
    
    sweep = _detect_liquidity_sweep(daily_ohlcv)
    if sweep:
        sweep['confidence'] = CONFIDENCE_2_CANDLE
        sweep['candles_used'] = SWEEP_LOOKBACK
        all_patterns.append(sweep)
        logger.info(f"💧 Liquidity Sweep: {sweep['pattern_name']} | Swept: {format_price(sweep.get('swept_level', 0))}")
    
    # ============================================
    # 4. TEK MUM PATTERNLERİ (PDC - c2)
    # ============================================
    
    if c2:
        # Hammer/Star ailesi
        hammer_star = _detect_hammer_star(c2, trend_context)
        if hammer_star:
            hammer_star['confidence'] = CONFIDENCE_1_CANDLE
            hammer_star['candles_used'] = 1
            all_patterns.append(hammer_star)
            logger.info(f"🔨 1-Candle Pattern: {hammer_star['pattern_name']} | Signal: {hammer_star['signal']} | Strength: {hammer_star['signal_strength']}")
        
        # Doji tipleri
        doji = _detect_doji_type(c2)
        if doji:
            doji['confidence'] = CONFIDENCE_1_CANDLE
            doji['candles_used'] = 1
            doji['pattern_type'] = 'DOJI'
            doji['pattern_name'] = f"{doji['doji_type'].replace('_', ' ').title()} Doji"
            doji['signal_strength'] = 'WEAK' if doji['signal'] == 'NEUTRAL' else 'MEDIUM'
            all_patterns.append(doji)
            logger.info(f"⚪ Doji: {doji['pattern_name']} | Body: %{doji['body_ratio']} | Signal: {doji['signal']}")
    
    # ============================================
    # 5. MOMENTUM ANALİZİ
    # ============================================
    
    momentum = _analyze_momentum(daily_ohlcv)
    
    if momentum['trend'] != 'STABLE' and momentum['trend'] != 'UNKNOWN':
        momentum_pattern = {
            'pattern_type': 'MOMENTUM',
            'pattern_name': f"Momentum {momentum['trend']}",
            'signal': 'BEARISH' if (momentum['trend'] == 'SHRINKING' and trend_context['is_uptrend']) else
                      'BULLISH' if (momentum['trend'] == 'SHRINKING' and trend_context['is_downtrend']) else
                      'NEUTRAL',
            'signal_strength': 'WEAK',
            'confidence': CONFIDENCE_MOMENTUM,
            'candles_used': 4,
            'description': f"Body sizes: {momentum['body_sizes']} - {momentum['trend']}"
        }
        all_patterns.append(momentum_pattern)
        logger.info(f"📊 Momentum: {momentum['trend']} | Bodies: {momentum['body_sizes']} | Pressure: {momentum['pressure']}")
    
    # ============================================
    # SONUÇ BELİRLEME
    # ============================================
    
    if not all_patterns:
        logger.info(f"ℹ️ detect_candle_patterns: Pattern bulunamadı")
        default_result['trend_context'] = trend_context['trend']
        default_result['momentum'] = momentum
        return default_result
    
    # En güçlü pattern'ı seç (confidence'a göre sırala)
    all_patterns.sort(key=lambda x: (x.get('confidence', 0), 
                                      1 if x.get('signal_strength') == 'VERY_STRONG' else
                                      0.8 if x.get('signal_strength') == 'STRONG' else
                                      0.5 if x.get('signal_strength') == 'MEDIUM' else 0.3), 
                      reverse=True)
    
    best_pattern = all_patterns[0]
    
    # Konum bonusu/cezası uygula
    confidence = best_pattern.get('confidence', CONFIDENCE_1_CANDLE)
    is_reversal_position = best_pattern.get('is_reversal_position', False)
    
    # Reversal pattern doğru konumda mı?
    if best_pattern.get('signal') == 'BULLISH' and trend_context['is_downtrend']:
        confidence *= CONTEXT_REVERSAL_BONUS
        is_reversal_position = True
    elif best_pattern.get('signal') == 'BEARISH' and trend_context['is_uptrend']:
        confidence *= CONTEXT_REVERSAL_BONUS
        is_reversal_position = True
    elif best_pattern.get('signal') == 'BULLISH' and trend_context['is_uptrend']:
        confidence *= CONTEXT_WRONG_PENALTY  # Zaten trend yönünde, reversal değil
        is_reversal_position = False
    elif best_pattern.get('signal') == 'BEARISH' and trend_context['is_downtrend']:
        confidence *= CONTEXT_WRONG_PENALTY
        is_reversal_position = False
    
    confidence = min(confidence, 1.0)  # Max 1.0
    
    # Bias suggestion
    bias_suggestion = None
    if confidence >= 0.7:
        if best_pattern.get('signal') == 'BULLISH':
            bias_suggestion = 'LONG'
        elif best_pattern.get('signal') == 'BEARISH':
            bias_suggestion = 'SHORT'
    
    # Skip önerisi
    skip_recommended = False
    if best_pattern.get('signal') == 'NEUTRAL' and confidence < 0.5:
        skip_recommended = True
    
    # Description oluştur
    description = f"{best_pattern.get('pattern_name', 'Unknown')}"
    if is_reversal_position:
        description += f" ({trend_context['trend']} sonunda - Reversal anlamlı)"
    else:
        description += f" ({trend_context['trend']} içinde)"
    
    result = {
        'pattern_detected': True,
        'pattern_type': best_pattern.get('pattern_type'),
        'pattern_name': best_pattern.get('pattern_name'),
        'candles_used': best_pattern.get('candles_used', 1),
        'signal': best_pattern.get('signal', 'NEUTRAL'),
        'signal_strength': best_pattern.get('signal_strength', 'WEAK'),
        'confidence': round(confidence, 2),
        'trend_context': trend_context['trend'],
        'is_reversal_position': is_reversal_position,
        'momentum': momentum,
        'all_patterns': [{'name': p.get('pattern_name'), 
                         'signal': p.get('signal'), 
                         'strength': p.get('signal_strength'),
                         'confidence': round(p.get('confidence', 0), 2)} 
                        for p in all_patterns],
        'bias_suggestion': bias_suggestion,
        'skip_recommended': skip_recommended,
        'description': description
    }
    
    logger.info(f"🕯️ detect_candle_patterns() EXIT | Best: {result['pattern_name']} | "
                f"Signal: {result['signal']} ({result['signal_strength']}) | "
                f"Confidence: {result['confidence']} | Bias: {result['bias_suggestion']}")
    
    return result


# ============================================
# v2.4.0: PDC & BIAS FONKSİYONLARI (GÜNCELLEME)
# ============================================

def check_doji(candle):
    """
    Tek mumun doji olup olmadığını kontrol et.
    (Backward compatibility için korunuyor)
    
    Args:
        candle: [timestamp, open, high, low, close, volume]
    
    Returns:
        bool: Doji ise True
    """
    if len(candle) < 5:
        return False
    
    o, h, l, c = candle[1], candle[2], candle[3], candle[4]
    body = abs(c - o)
    range_ = h - l
    
    if range_ == 0:
        return True  # Hiç hareket yok = doji
    
    return body < (range_ * DOJI_BODY_THRESHOLD)


def calculate_pdc_bias(daily_ohlcv):
    """
    PDC'ye göre bias belirle + Pattern Detection.
    
    v2.6.0 GÜNCELLEME:
    - detect_candle_patterns() entegrasyonu
    - Pattern bazlı bias override
    
    Args:
        daily_ohlcv: Son 5+ daily mum [[ts, o, h, l, c, v], ...]
    
    Returns:
        {
            'bias': 'LONG' | 'SHORT',
            'pdc': {'open', 'high', 'low', 'close', 'type'},
            'doji_warning': bool,
            'doji_count': int,
            'pdc_is_doji': bool,
            'reversal_mode': bool,
            'pattern': dict  # v2.6.0: Pattern detection sonucu
        }
    """
    logger.debug(f"📊 calculate_pdc_bias() ENTRY | candles: {len(daily_ohlcv) if daily_ohlcv else 0}")
    
    if not daily_ohlcv or len(daily_ohlcv) < 5:
        logger.warning(f"⚠️ calculate_pdc_bias: Yetersiz veri")
        return {
            'bias': 'LONG',
            'pdc': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'type': 'green'},
            'doji_warning': False,
            'doji_count': 0,
            'pdc_is_doji': False,
            'reversal_mode': False,
            'pattern': None
        }
    
    # Son 5 mum al
    last_5 = daily_ohlcv[-5:]
    
    # PDC = dünkü kapanmış mum (bugün hariç)
    pdc = last_5[-2]
    pdc_open, pdc_high, pdc_low, pdc_close = pdc[1], pdc[2], pdc[3], pdc[4]
    pdc_type = 'green' if pdc_close > pdc_open else 'red'
    
    # ============================================
    # v2.6.0: Pattern Detection
    # ============================================
    pattern_result = detect_candle_patterns(daily_ohlcv)
    
    # Doji kontrolü - son 4 KAPANMIŞ mum (bugün hariç)
    closed_candles = last_5[:-1]  # [-5, -4, -3, -2] indisleri
    doji_count = 0
    pdc_is_doji = False
    
    for candle in closed_candles:
        if check_doji(candle):
            doji_count += 1
            if candle == pdc:
                pdc_is_doji = True
    
    # ============================================
    # BİAS BELİRLEME (Pattern öncelikli)
    # ============================================
    
    # Pattern confidence yüksekse, pattern'ın önerisini kullan
    if pattern_result.get('confidence', 0) >= 0.75 and pattern_result.get('bias_suggestion'):
        bias = pattern_result['bias_suggestion']
        reversal_mode = pattern_result.get('is_reversal_position', False)
        logger.info(f"🎯 Bias override by pattern: {pattern_result['pattern_name']} → {bias} (conf: {pattern_result['confidence']})")
    
    # Yoksa eski mantık
    elif pdc_is_doji:
        # PDC doji ise, ondan önceki muma bak ve TERSİNİ al
        prev_candle = last_5[-3]
        prev_type = 'green' if prev_candle[4] > prev_candle[1] else 'red'
        bias = 'SHORT' if prev_type == 'green' else 'LONG'
        reversal_mode = True
        logger.info(f"🎯 Bias by Doji reversal: PDC is doji, prev={prev_type} → {bias}")
    
    elif doji_count >= 2:
        # 2+ doji varsa reversal modu
        bias = 'SHORT' if pdc_type == 'green' else 'LONG'
        reversal_mode = True
        logger.info(f"🎯 Bias by multiple dojis ({doji_count}): PDC={pdc_type} → {bias}")
    
    else:
        # Normal mod
        bias = 'LONG' if pdc_type == 'green' else 'SHORT'
        reversal_mode = False
        logger.debug(f"🎯 Bias by PDC color: {pdc_type} → {bias}")
    
    result = {
        'bias': bias,
        'pdc': {
            'open': pdc_open,
            'high': pdc_high,
            'low': pdc_low,
            'close': pdc_close,
            'type': pdc_type
        },
        'doji_warning': doji_count > 0 or (pattern_result.get('pattern_type') == 'DOJI'),
        'doji_count': doji_count,
        'pdc_is_doji': pdc_is_doji,
        'reversal_mode': reversal_mode,
        'pattern': pattern_result  # v2.6.0: Yeni field
    }
    
    logger.info(f"📊 calculate_pdc_bias() EXIT | Bias: {bias} | PDC: {pdc_type} | "
                f"Doji: {doji_count} | Reversal: {reversal_mode} | "
                f"Pattern: {pattern_result.get('pattern_name', 'None')}")
    
    return result


# ============================================
# v2.5.1: FİBO ZONE FONKSİYONLARI (DEĞİŞMEDİ)
# ============================================

def calculate_fibo_zones(pdc, bias):
    """
    PDC ve bias'a göre Fibo zone'larını hesapla.
    
    v2.5.1 GÜNCELLEME:
    - OB Zone: %70-90 (PDC içi retracement) - DEĞİŞMEDİ
    - FVG Zone: %50-150 (PDC içi + dışı extension)
    
    Fibo Yönü (Bias'a göre):
    - LONG (Yeşil PDC): 0 = PDC Low, 100 = PDC High, extension yukarı
    - SHORT (Kırmızı PDC): 0 = PDC High, 100 = PDC Low, extension aşağı
    
    Args:
        pdc: {'open', 'high', 'low', 'close', 'type'}
        bias: 'LONG' | 'SHORT'
    
    Returns:
        {
            'fib_0': float,
            'fib_100': float,
            'ob_zone': (low, high),       # OB: %70-90 (PDC içi)
            'fvg_zone_long': (low, high), # FVG LONG: %50-150 yukarı
            'fvg_zone_short': (low, high),# FVG SHORT: %50-150 aşağı
            'fib_levels': {...},
            'pdc_high': float,
            'pdc_low': float
        }
    """
    high = pdc['high']
    low = pdc['low']
    diff = high - low
    
    if diff == 0:
        return {
            'fib_0': low,
            'fib_100': high,
            'ob_zone': (low, high),
            'fvg_zone_long': (high, high),
            'fvg_zone_short': (low, low),
            'fib_levels': {},
            'pdc_high': high,
            'pdc_low': low
        }
    
    # ============================================
    # OB Zone: %70-90 (PDC içi, sabit hesaplama)
    # Her zaman PDC low'dan yukarı hesaplanır
    # ============================================
    ob_70 = low + (diff * OB_ZONE_MIN)  # %70
    ob_90 = low + (diff * OB_ZONE_MAX)  # %90
    ob_zone = (min(ob_70, ob_90), max(ob_70, ob_90))
    
    # ============================================
    # FVG Zone: %50-150 (Bias'a göre yön değişir)
    # ============================================
    
    # LONG/Bullish FVG Zone (Yeşil PDC mantığı):
    # Fibo 0 = PDC Low, Fibo 100 = PDC High
    # %50 = PDC orta, %150 = PDC High + %50 range (yukarı extension)
    fvg_long_50 = low + (diff * FVG_ZONE_MIN)   # %50
    fvg_long_150 = low + (diff * FVG_ZONE_MAX)  # %150 (yukarı extension)
    fvg_zone_long = (min(fvg_long_50, fvg_long_150), max(fvg_long_50, fvg_long_150))
    
    # SHORT/Bearish FVG Zone (Kırmızı PDC mantığı):
    # Fibo 0 = PDC High, Fibo 100 = PDC Low
    # %50 = PDC orta, %150 = PDC Low - %50 range (aşağı extension)
    fvg_short_50 = high - (diff * FVG_ZONE_MIN)   # %50 (high'dan aşağı)
    fvg_short_150 = high - (diff * FVG_ZONE_MAX)  # %150 (aşağı extension)
    fvg_zone_short = (min(fvg_short_50, fvg_short_150), max(fvg_short_50, fvg_short_150))
    
    # Fibo seviyeleri (referans için - LONG yönünde)
    fib_levels = {
        '0': low,
        '23.6': low + (diff * 0.236),
        '38.2': low + (diff * 0.382),
        '50': low + (diff * 0.5),
        '61.8': low + (diff * 0.618),
        '70': low + (diff * 0.7),
        '78.6': low + (diff * 0.786),
        '90': low + (diff * 0.9),
        '100': high,
        '150': low + (diff * 1.5)  # Extension
    }
    
    return {
        'fib_0': low,
        'fib_100': high,
        'ob_zone': ob_zone,
        'fvg_zone_long': fvg_zone_long,
        'fvg_zone_short': fvg_zone_short,
        'fib_levels': fib_levels,
        'pdc_high': high,
        'pdc_low': low
    }


def is_in_ob_zone(price, fibo_data):
    """
    Fiyatın OB zone'unda (%70-90) olup olmadığını kontrol et.
    
    Args:
        price: Kontrol edilecek fiyat (OB mid-point)
        fibo_data: calculate_fibo_zones() çıktısı
    
    Returns:
        bool
    """
    if not fibo_data or 'ob_zone' not in fibo_data:
        return True  # Fibo yoksa filtre uygulama
    
    zone_low, zone_high = fibo_data['ob_zone']
    return zone_low <= price <= zone_high


def is_in_fvg_zone(price, fibo_data, direction='LONG'):
    """
    Fiyatın FVG zone'unda (%100-150 extension) olup olmadığını kontrol et.
    
    v2.5.1 GÜNCELLEME:
    - FVG zone artık PDC DIŞINDA (extension)
    - LONG: PDC high'dan yukarı (%100-150)
    - SHORT: PDC low'dan aşağı (%100-150, negatif yönde)
    
    Args:
        price: Kontrol edilecek fiyat (FVG mid-point)
        fibo_data: calculate_fibo_zones() çıktısı
        direction: 'LONG' veya 'SHORT' (FVG yönü)
    
    Returns:
        bool
    """
    if not fibo_data:
        return True  # Fibo yoksa filtre uygulama
    
    if direction == 'LONG':
        if 'fvg_zone_long' not in fibo_data:
            return True
        zone_low, zone_high = fibo_data['fvg_zone_long']
    else:  # SHORT
        if 'fvg_zone_short' not in fibo_data:
            return True
        zone_low, zone_high = fibo_data['fvg_zone_short']
    
    return zone_low <= price <= zone_high
