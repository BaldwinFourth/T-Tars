# -*- coding: utf-8 -*-
"""
T-TARS Strategies v1.4.9
========================
Trading strategy modülleri.
"""

from .calculators import (
    calculate_setup_strength,
    MIN_RR_RATIO,
    STOP_MULTIPLIER,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER
)

from .ob_detector import (
    detect_ob_long,
    detect_ob_short
)

from .fvg_detector import (
    detect_fvg_long,
    detect_fvg_short
)

from .volume_analyzer import (
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
    # Backward compatibility
    detect_all_trading_setups,
    check_timeframe_for_setups
)

__all__ = [
    # Calculators
    'calculate_setup_strength',
    'MIN_RR_RATIO',
    'STOP_MULTIPLIER',
    'TP1_MULTIPLIER',
    'TP2_MULTIPLIER',
    # OB Detector
    'detect_ob_long',
    'detect_ob_short',
    # FVG Detector
    'detect_fvg_long',
    'detect_fvg_short',
    # Volume Analyzer
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
