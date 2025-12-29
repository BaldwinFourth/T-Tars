# -*- coding: utf-8 -*-
"""
T-TARS Trading Calculators v2.4.11
===================================
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
SCORE_RR_ELSE = 0.20

# ============================================
# VOLUME THRESHOLDS (Fine tuning buradan)
# ============================================
VOLUME_TRADEABLE_MIN = 0.70 # Minimum tradeable (bu altı = reject)
VOLUME_LOW = 0.8           # Düşük ama kabul edilebilir
VOLUME_MEDIUM = 1.5        # Orta
VOLUME_GOOD = 2.0          # İyi
VOLUME_EXCELLENT = 2.5     # Mükemmel volume spike

# Volume Spike Flag (boolean için) - bitget_service kullanıyor
VOLUME_SPIKE_FLAG = 1.5    # spike_ratio >= bu değer → spike=True

# Volume Strength Labels - bitget_service kullanıyor
VOLUME_STRENGTH_HIGH = 3.0   # >= 3.0 → 'high'
VOLUME_STRENGTH_MEDIUM = 2.0 # >= 2.0 → 'medium'
# else → 'low'

# ============================================
# VOLUME SCORES (Fine tuning buradan)
# ============================================
SCORE_VOLUME_EXCELLENT = 1.50  # Bonus
SCORE_VOLUME_GOOD = 1.20
SCORE_VOLUME_MEDIUM = 0.80
SCORE_VOLUME_LOW = 0.60
SCORE_VOLUME_ELSE = 0.3

# ============================================
# OB/FVG STRENGTH MAPPING (Fine tuning buradan)
# ============================================
STRENGTH_MAP = {
    'high': 1.25,    # Bonus
    'medium': 0.65,
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
MIN_OB_SIZE_ATR = 1.5      # OB en az 1.2 ATR olmalı
MIN_FVG_SIZE_ATR = 2.0     # FVG en az 1.2 ATR olmalı

# ============================================
# v2.4.0: FİBO ZONE TANIMLARI
# ============================================
OB_ZONE_MIN = 0.70         # OB arama: %70-90
OB_ZONE_MAX = 0.90
FVG_ZONE_MIN = 0.70        # FVG arama: %70-90
FVG_ZONE_MAX = 0.90

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
# v2.4.0: FİBO ZONE FONKSİYONLARI
# ============================================

def calculate_fibo_zones(pdc, bias):
    """
    PDC ve bias'a göre Fibo zone'larını hesapla.
    
    Args:
        pdc: {'open', 'high', 'low', 'close', 'type'}
        bias: 'LONG' | 'SHORT'
    
    Returns:
        {
            'fib_0': float,      # 0% seviyesi
            'fib_100': float,    # 100% seviyesi
            'ob_zone': (low, high),   # OB arama bölgesi (%70-90)
            'fvg_zone': (low, high),  # FVG arama bölgesi (%70-90)
            'fib_levels': {...}  # Tüm fibo seviyeleri
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
            'fvg_zone': (low, high),
            'fib_levels': {},
            'pdc_high': high,
            'pdc_low': low
        }
    
    # Fibo yönü bias'a göre
    if bias == 'LONG':
        # Yeşil PDC: 0 altta, 100 üstte
        fib_0 = low
        fib_100 = high
    else:
        # Kırmızı PDC: 0 üstte, 100 altta (ters çevrilmiş)
        fib_0 = high
        fib_100 = low
    
    # Fibo seviyeleri hesapla
    def calc_level(pct):
        if bias == 'LONG':
            return low + (diff * pct)
        else:
            return high - (diff * pct)
    
    fib_levels = {
        '0': calc_level(0),
        '23.6': calc_level(0.236),
        '38.2': calc_level(0.382),
        '50': calc_level(0.5),
        '60': calc_level(0.6),
        '61.8': calc_level(0.618),
        '70': calc_level(0.7),
        '78.6': calc_level(0.786),
        '90': calc_level(0.9),
        '100': calc_level(1.0)
    }
    
    # OB Zone: %70-90
    ob_low = min(fib_levels['70'], fib_levels['90'])
    ob_high = max(fib_levels['70'], fib_levels['90'])
    
    # FVG Zone: %70-90
    fvg_low = min(fib_levels['70'], fib_levels['90'])
    fvg_high = max(fib_levels['70'], fib_levels['90'])
    
    return {
        'fib_0': fib_0,
        'fib_100': fib_100,
        'ob_zone': (ob_low, ob_high),
        'fvg_zone': (fvg_low, fvg_high),
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


def is_in_fvg_zone(price, fibo_data):
    """
    Fiyatın FVG zone'unda (%70-90) olup olmadığını kontrol et.
    
    Args:
        price: Kontrol edilecek fiyat (FVG mid-point)
        fibo_data: calculate_fibo_zones() çıktısı
    
    Returns:
        bool
    """
    if not fibo_data or 'fvg_zone' not in fibo_data:
        return True  # Fibo yoksa filtre uygulama
    
    zone_low, zone_high = fibo_data['fvg_zone']
    return zone_low <= price <= zone_high
