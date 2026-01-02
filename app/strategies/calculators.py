# -*- coding: utf-8 -*-
"""
T-TARS Trading Calculators v2.5.1
===================================
v2.5.1:
- CHANGED: FVG_ZONE_MIN = 0.50, FVG_ZONE_MAX = 1.50 (PDC içi + dışı)
- CHANGED: calculate_fibo_zones() - Bias-aware fibo hesabı
  - LONG: Fibo 0=Low, 100=High, extension yukarı
  - SHORT: Fibo 0=High, 100=Low, extension aşağı
- CHANGED: is_in_fvg_zone() - Bias'a göre zone kontrolü

v2.5.0:
- OPTİMİZASYON: Volume, FVG, OB, RR threshold güncellendi. 

v2.4.11:
- FIX: Yorum düzeltmeleri (FVG zone %70-90)

v2.4.10:
- CHANGED: MIN_RR_RATIO = 3.0 (eskiden 2.0)
- CHANGED: TP_MULTIPLIER = 3.0 (tek TP, eskiden TP1=2.0/TP2=4.0)
- REMOVED: TP1_MULTIPLIER, TP2_MULTIPLIER (tek TP sistemine geçildi)

v2.4.0:
- NEW: calculate_pdc_bias() - PDC bazlı bias + Doji kontrolü
- NEW: calculate_fibo_zones() - Fibo %70-90 zone hesabı
- NEW: is_in_ob_zone() - OB için %70-90 kontrolü
- NEW: is_in_fvg_zone() - FVG için %70-90 kontrolü
- NEW: check_doji() - Tek mum doji kontrolü
- NEW: MIN_OB_SIZE_ATR = 1.2, MIN_FVG_SIZE_ATR = 1.2
"""

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
# v2.4.0: DOJİ THRESHOLD
# ============================================
DOJI_BODY_THRESHOLD = 0.10  # Body < range'in %10'u ise doji


# ============================================
# FUNCTIONS
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
# v2.4.0: PDC & BIAS FONKSİYONLARI
# ============================================

def check_doji(candle):
    """
    Tek mumun doji olup olmadığını kontrol et.
    
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
    PDC'ye göre bias belirle + Doji kontrolü.
    
    Args:
        daily_ohlcv: Son 5+ daily mum [[ts, o, h, l, c, v], ...]
    
    Returns:
        {
            'bias': 'LONG' | 'SHORT',
            'pdc': {'open', 'high', 'low', 'close', 'type'},
            'doji_warning': bool,
            'doji_count': int,
            'pdc_is_doji': bool,
            'reversal_mode': bool
        }
    """
    if not daily_ohlcv or len(daily_ohlcv) < 5:
        return {
            'bias': 'LONG',
            'pdc': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'type': 'green'},
            'doji_warning': False,
            'doji_count': 0,
            'pdc_is_doji': False,
            'reversal_mode': False
        }
    
    # Son 5 mum al
    last_5 = daily_ohlcv[-5:]
    
    # PDC = dünkü kapanmış mum (bugün hariç)
    pdc = last_5[-2]
    pdc_open, pdc_high, pdc_low, pdc_close = pdc[1], pdc[2], pdc[3], pdc[4]
    pdc_type = 'green' if pdc_close > pdc_open else 'red'
    
    # Doji kontrolü - son 4 KAPANMIŞ mum (bugün hariç)
    closed_candles = last_5[:-1]  # [-5, -4, -3, -2] indisleri
    doji_count = 0
    pdc_is_doji = False
    
    for candle in closed_candles:
        if check_doji(candle):
            doji_count += 1
            if candle == pdc:
                pdc_is_doji = True
    
    # Bias belirleme
    if pdc_is_doji:
        # PDC doji ise, ondan önceki muma bak ve TERSİNİ al
        prev_candle = last_5[-3]
        prev_type = 'green' if prev_candle[4] > prev_candle[1] else 'red'
        bias = 'SHORT' if prev_type == 'green' else 'LONG'
        reversal_mode = True
    elif doji_count >= 2:
        # 2+ doji varsa reversal modu
        bias = 'SHORT' if pdc_type == 'green' else 'LONG'
        reversal_mode = True
    else:
        # Normal mod
        bias = 'LONG' if pdc_type == 'green' else 'SHORT'
        reversal_mode = False
    
    return {
        'bias': bias,
        'pdc': {
            'open': pdc_open,
            'high': pdc_high,
            'low': pdc_low,
            'close': pdc_close,
            'type': pdc_type
        },
        'doji_warning': doji_count > 0,
        'doji_count': doji_count,
        'pdc_is_doji': pdc_is_doji,
        'reversal_mode': reversal_mode
    }


# ============================================
# v2.5.1: FİBO ZONE FONKSİYONLARI (UPDATED!)
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
