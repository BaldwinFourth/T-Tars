# -*- coding: utf-8 -*-
"""
T-TARS Strategies v2.3.11
=========================
Trading strategy modülleri.

v2.3.11:
- calculators: Yeni constant'lar eklendi
- volume_analyzer: Webhook storage fonksiyonları eklendi
"""

from .calculators import (
    calculate_setup_strength,
    calculate_rr,
    format_price,
    get_volume_score,
    get_rr_score,
    is_valid_setup,
    # Constants
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
    # Calculators - Constants
    'MIN_RR_RATIO',
    'STOP_MULTIPLIER',
    'TP1_MULTIPLIER',
    'TP2_MULTIPLIER',
    'VOLUME_TRADEABLE_MIN',
    'VOLUME_LOW',
    'VOLUME_MEDIUM',
    'VOLUME_GOOD',
    'VOLUME_EXCELLENT',
    'VOLUME_SPIKE_FLAG',
    'VOLUME_STRENGTH_HIGH',
    'VOLUME_STRENGTH_MEDIUM',
    'VOLUME_VETO_MAX_SCORE',
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
