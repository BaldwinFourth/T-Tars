# -*- coding: utf-8 -*-
"""
T-TARS Volume Analyzer v1.4.9
=============================
Volume spike detection ve analiz
"""

import logging

logger = logging.getLogger(__name__)


def has_volume_spike(volume_data):
    """
    Volume spike var mı kontrol et
    
    Args:
        volume_data: Volume dict {'spike': bool, 'spike_ratio': float, ...}
    
    Returns:
        bool: Spike var mı
    """
    if not volume_data:
        return False
    return volume_data.get('spike', False)


def get_spike_ratio(volume_data):
    """
    Volume spike oranını al
    
    Returns:
        float: Spike ratio (örn: 1.5x)
    """
    if not volume_data:
        return 0.0
    return volume_data.get('spike_ratio', 0.0)


def get_volume_strength(volume_data):
    """
    Volume gücünü al
    
    Returns:
        str: 'low', 'medium', 'high'
    """
    if not volume_data:
        return 'low'
    return volume_data.get('strength', 'medium')


def get_volume_trend(volume_data):
    """
    Volume trendini al
    
    Returns:
        str: 'increasing', 'decreasing', 'stable'
    """
    if not volume_data:
        return 'stable'
    return volume_data.get('trend', 'stable')


def select_best_volume(volume_5m, volume_3m):
    """
    5m ve 3m volume'dan en iyisini seç
    
    Returns:
        tuple: (volume_data, timeframe)
    """
    if has_volume_spike(volume_5m):
        return volume_5m, '5m'
    elif has_volume_spike(volume_3m):
        return volume_3m, '3m'
    else:
        # Spike yoksa, ratio'su yüksek olanı seç
        ratio_5m = get_spike_ratio(volume_5m)
        ratio_3m = get_spike_ratio(volume_3m)
        if ratio_5m >= ratio_3m:
            return volume_5m, '5m'
        return volume_3m, '3m'


def analyze_volume(market_data, timeframe):
    """
    Belirli timeframe için volume analizi
    
    Args:
        market_data: Tam market data
        timeframe: '4h', '1h', '15m', '5m', '3m'
    
    Returns:
        dict: Volume analiz sonucu
    """
    try:
        volume = market_data['volume'].get(timeframe, {})
        
        if not volume:
            return {
                'has_spike': False,
                'spike_ratio': 0.0,
                'strength': 'low',
                'trend': 'stable',
                'tradeable': False
            }
        
        has_spike = has_volume_spike(volume)
        spike_ratio = get_spike_ratio(volume)
        strength = get_volume_strength(volume)
        trend = get_volume_trend(volume)
        
        # Tradeable: Spike var veya ratio 1.2x üstünde
        tradeable = has_spike or spike_ratio >= 1.2
        
        return {
            'has_spike': has_spike,
            'spike_ratio': spike_ratio,
            'strength': strength,
            'trend': trend,
            'tradeable': tradeable
        }
        
    except Exception as e:
        logger.error(f"Volume analysis error for {timeframe}: {e}")
        return {
            'has_spike': False,
            'spike_ratio': 0.0,
            'strength': 'low',
            'trend': 'stable',
            'tradeable': False
        }
