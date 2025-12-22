# -*- coding: utf-8 -*-
"""
T-TARS Strategies v2.4.0
=========================
Trading strategy modülleri.

v2.4.0:
- NEW: calculate_pdc_bias - PDC bazlı bias belirleme
- NEW: calculate_fibo_zones - Fibo zone hesaplama
- NEW: is_in_ob_zone - OB %70-90 zone kontrolü
- NEW: is_in_fvg_zone - FVG %60-90 zone kontrolü
- NEW: check_doji - Doji kontrolü
- NEW: MIN_OB_SIZE_ATR, MIN_FVG_SIZE_ATR constants
- NEW: OB_ZONE_MIN/MAX, FVG_ZONE_MIN/MAX, DOJI_BODY_THRESHOLD constants

v2.3.11:
- calculators: Yeni constant'lar eklendi
- volume_analyzer: Webhook storage fonksiyonları eklendi
"""

from .calculators import (
    # Functions
    calculate_setup_strength,
    calculate_rr,
    format_price,
    get_volume_score,
    get_rr_score,
    is_valid_setup,
    # v2.4.0: PDC/Fibo/Doji Functions
    calculate_pdc_bias,
    calculate_fibo_zones,
    is_in_ob_zone,
    is_in_fvg_zone,
    check_doji,
    # R:R Constants
    MIN_RR_RATIO,
    STOP_MULTIPLIER,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER,
    # Volume thresholds
    VOLUME_TRADEABLE_MIN,
    VOLUME_LOW,
    VOLUME_MEDIUM,
    VOLUME_GOOD,
    VOLUME_EXCELLENT,
    VOLUME_SPIKE_FLAG,
    VOLUME_STRENGTH_HIGH,
    VOLUME_STRENGTH_MEDIUM,
    VOLUME_VETO_MAX_SCORE,
    # v2.4.0: OB/FVG Size constants
    MIN_OB_SIZE_ATR,
    MIN_FVG_SIZE_ATR,
    # v2.4.0: Fibo Zone constants
    OB_ZONE_MIN,
    OB_ZONE_MAX,
    FVG_ZONE_MIN,
    FVG_ZONE_MAX,
    DOJI_BODY_THRESHOLD,
)

from .ob_detector import (
    scan_order_blocks,
    detect_ob_long,
    detect_ob_short
)

from .fvg_detector import (
    scan_fair_value_gaps,
    detect_fvg_long,
    detect_fvg_short
)

from .volume_analyzer import (
    # Webhook storage (v2.3.7+)
    store_volume,
    get_volume,
    get_all_volumes,
    cleanup_expired_volumes,
    get_volume_store_stats,
    # Analysis functions
    has_volume_spike,
    get_spike_ratio,
    get_volume_strength,
    get_volume_trend,
    select_best_volume,
    analyze_volume
)

from .setup_detector import (
    detect_trading_setup,
    check_timeframe,
    scan_setups,
    detect_all_trading_setups,
    check_timeframe_for_setups
)

__all__ = [
    # Calculators - Functions
    'calculate_setup_strength',
    'calculate_rr',
    'format_price',
    'get_volume_score',
    'get_rr_score',
    'is_valid_setup',
    # Calculators - PDC/Fibo/Doji Functions (v2.4.0)
    'calculate_pdc_bias',
    'calculate_fibo_zones',
    'is_in_ob_zone',
    'is_in_fvg_zone',
    'check_doji',
    # Calculators - R:R Constants
    'MIN_RR_RATIO',
    'STOP_MULTIPLIER',
    'TP1_MULTIPLIER',
    'TP2_MULTIPLIER',
    # Calculators - Volume Constants
    'VOLUME_TRADEABLE_MIN',
    'VOLUME_LOW',
    'VOLUME_MEDIUM',
    'VOLUME_GOOD',
    'VOLUME_EXCELLENT',
    'VOLUME_SPIKE_FLAG',
    'VOLUME_STRENGTH_HIGH',
    'VOLUME_STRENGTH_MEDIUM',
    'VOLUME_VETO_MAX_SCORE',
    # Calculators - OB/FVG Size Constants (v2.4.0)
    'MIN_OB_SIZE_ATR',
    'MIN_FVG_SIZE_ATR',
    # Calculators - Fibo Zone Constants (v2.4.0)
    'OB_ZONE_MIN',
    'OB_ZONE_MAX',
    'FVG_ZONE_MIN',
    'FVG_ZONE_MAX',
    'DOJI_BODY_THRESHOLD',
    # OB Detector
    'scan_order_blocks',
    'detect_ob_long',
    'detect_ob_short',
    # FVG Detector
    'scan_fair_value_gaps',
    'detect_fvg_long',
    'detect_fvg_short',
    # Volume Analyzer - Storage
    'store_volume',
    'get_volume',
    'get_all_volumes',
    'cleanup_expired_volumes',
    'get_volume_store_stats',
    # Volume Analyzer - Analysis
    'has_volume_spike',
    'get_spike_ratio',
    'get_volume_strength',
    'get_volume_trend',
    'select_best_volume',
    'analyze_volume',
    # Setup Detector
    'detect_trading_setup',
    'check_timeframe',
    'scan_setups',
    'detect_all_trading_setups',
    'check_timeframe_for_setups'
]
