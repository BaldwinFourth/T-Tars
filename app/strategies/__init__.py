# -*- coding: utf-8 -*-
"""
T-TARS Trading Strategies
=========================
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

__all__ = [
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
    'is_valid_setup'
]
