# -*- coding: utf-8 -*-
"""
T-TARS Trading Strategies v1.4.5
================================
Setup detection ve calculation modülleri.
"""

from .calculators import (
    # Constants
    STOP_MULTIPLIER,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER,
    MIN_RR_RATIO,
    VOLUME_EXCELLENT,
    VOLUME_GOOD,
    VOLUME_MEDIUM,
    VOLUME_LOW,
    # Functions
    calculate_setup_strength,
    calculate_rr,
    get_volume_score,
    get_rr_score,
    is_valid_setup
)

from .setup_detector import (
    detect_trading_setup,
    detect_all_trading_setups,
    check_timeframe_for_setups
)

__all__ = [
    # Calculators
    'STOP_MULTIPLIER',
    'TP1_MULTIPLIER', 
    'TP2_MULTIPLIER',
    'MIN_RR_RATIO',
    'VOLUME_EXCELLENT',
    'VOLUME_GOOD',
    'VOLUME_MEDIUM',
    'VOLUME_LOW',
    'calculate_setup_strength',
    'calculate_rr',
    'get_volume_score',
    'get_rr_score',
    'is_valid_setup',
    # Setup Detector
    'detect_trading_setup',
    'detect_all_trading_setups',
    'check_timeframe_for_setups'
]
