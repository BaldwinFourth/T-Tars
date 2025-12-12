# -*- coding: utf-8 -*-
"""
T-TARS Volume Analyzer v2.0.9
=============================
Volume spike detection ve analiz

v2.0.9:
- FIX: 10m timeframe kaldırıldı (OKX desteklemiyor)
- FIX: tradeable threshold 1.2 -> 0.5 (daha az katı)
- ADD: Detaylı logging eklendi
"""

import logging

logger = logging.getLogger(__name__)

# Volume threshold - 0.5x ve üzeri tradeable
TRADEABLE_THRESHOLD = 0.5


def has_volume_spike(volume_data):
    """
    Volume spike var mı kontrol et
    Args: volume_data (dict)
    Returns: bool
    """
    if not volume_data:
        return False
    return volume_data.get('spike', False)


def get_spike_ratio(volume_data):
    """
    Volume spike oranını al
    Returns: float
    """
    if not volume_data:
        return 0.0
    return volume_data.get('spike_ratio', 0.0)


def get_volume_strength(volume_data):
    """Volume gücünü al"""
    if not volume_data:
        return 'low'
    return volume_data.get('strength', 'medium')


def get_volume_trend(volume_data):
    """Volume trendini al"""
    if not volume_data:
        return 'stable'
    return volume_data.get('trend', 'stable')


def select_best_volume(volume_data_dict):
    """
    Tüm timeframe'lerin volume verileri arasından en iyisini seçer.
    
    Args:
        volume_data_dict: dict, keys=['4h', '2h', ...], values=volume_data dict
        
    Returns:
        tuple: (best_volume_data, best_timeframe_str)
    """
    if not volume_data_dict:
        logger.debug("📊 Volume: Veri yok, default 3m")
        return {'spike': False, 'spike_ratio': 0.0}, '3m'
    
    # Öncelik Sıralaması (Büyük TF > Küçük TF) - 10m kaldırıldı
    priority_order = ['4h', '2h', '1h', '30m', '15m', '5m', '3m']
    
    # 1. ADIM: Spike Kontrolü (Hiyerarşik)
    for tf in priority_order:
        data = volume_data_dict.get(tf)
        if data and has_volume_spike(data):
            logger.info(f"📊 Volume SPIKE bulundu: {tf} ({data.get('spike_ratio', 0):.2f}x)")
            return data, tf
    
    # 2. ADIM: Ratio Karşılaştırması (En Yüksek Oran)
    best_tf = '3m'
    best_vol = volume_data_dict.get('3m')
    max_ratio = -1.0
    
    for tf in priority_order:
        data = volume_data_dict.get(tf)
        if data:
            ratio = get_spike_ratio(data)
            if ratio > max_ratio:
                max_ratio = ratio
                best_vol = data
                best_tf = tf
    
    if best_vol is None:
        logger.debug("📊 Volume: Hiç veri bulunamadı")
        return {'spike': False, 'spike_ratio': 0.0}, '3m'
    
    logger.debug(f"📊 Volume seçildi: {best_tf} ({max_ratio:.2f}x)")
    return best_vol, best_tf


def analyze_volume(market_data, timeframe):
    """
    Belirli timeframe için volume analizi yapar.
    
    Args:
        market_data: Tam market data
        timeframe: '4h', '2h', '1h', '30m', '15m', '5m', '3m'
    
    Returns:
        dict: Volume analiz sonucu
    """
    try:
        volume = market_data['volume'].get(timeframe, {})
        
        if not volume:
            logger.debug(f"📊 Volume [{timeframe}]: Veri yok")
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
        
        # Tradeable: Spike var veya ratio threshold üstünde (0.5x)
        tradeable = has_spike or spike_ratio >= TRADEABLE_THRESHOLD
        
        logger.debug(f"📊 Volume [{timeframe}]: Ratio={spike_ratio:.2f}x, Spike={has_spike}, Tradeable={tradeable}")
        
        return {
            'has_spike': has_spike,
            'spike_ratio': spike_ratio,
            'strength': strength,
            'trend': trend,
            'tradeable': tradeable
        }
        
    except Exception as e:
        logger.error(f"❌ Volume analysis error [{timeframe}]: {e}")
        return {
            'has_spike': False,
            'spike_ratio': 0.0,
            'strength': 'low',
            'trend': 'stable',
            'tradeable': False
        }
