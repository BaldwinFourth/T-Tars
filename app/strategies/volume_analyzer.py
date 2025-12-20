# -*- coding: utf-8 -*-
"""
T-TARS Volume Analyzer v2.3.11
==============================
Volume spike detection ve analiz

v2.3.11:
- FIX: get_volume_strength() default 'medium' → 'low' (güvenli varsayılan)
- ADD: Key eksikse debug log

v2.3.8:
- CHANGED: TRADEABLE_THRESHOLD kaldırıldı, calculators.VOLUME_TRADEABLE_MIN kullanılıyor (DRY)
"""

import logging
import time

from app.strategies.calculators import VOLUME_TRADEABLE_MIN

logger = logging.getLogger(__name__)

VOLUME_EXPIRY_SECONDS = 2 * 60 * 60

_VOLUME_STORE = {}


def store_volume(pair: str, tf: str, spike: float, atr: float) -> None:
    """Webhook'tan gelen volume verisini sakla."""
    key = f"{pair}_{tf}"
    _VOLUME_STORE[key] = {
        'spike': spike,
        'atr': atr,
        'timestamp': time.time()
    }
    logger.debug(f"📊 Volume stored: {key} = {spike:.2f}x, ATR={atr:.6g}")


def get_volume(pair: str, tf: str) -> dict:
    """Belirli pair ve timeframe için volume verisi döndür."""
    key = f"{pair}_{tf}"
    data = _VOLUME_STORE.get(key)
    
    if not data:
        return {'spike': 0.0, 'atr': 0.0}
    
    age = time.time() - data.get('timestamp', 0)
    if age > VOLUME_EXPIRY_SECONDS:
        logger.debug(f"📊 Volume expired: {key} (age={age/60:.1f}m)")
        del _VOLUME_STORE[key]
        return {'spike': 0.0, 'atr': 0.0}
    
    return data


def get_all_volumes(pair: str) -> dict:
    """Bir pair'in tüm timeframe'leri için volume verisi döndür."""
    result = {}
    for tf in ['5m', '15m', '30m', '1h']:
        result[tf] = get_volume(pair, tf)
    return result


def cleanup_expired_volumes() -> int:
    """Süresi dolmuş volume verilerini temizle."""
    now = time.time()
    expired_keys = []
    
    for key, data in _VOLUME_STORE.items():
        age = now - data.get('timestamp', 0)
        if age > VOLUME_EXPIRY_SECONDS:
            expired_keys.append(key)
    
    for key in expired_keys:
        del _VOLUME_STORE[key]
    
    if expired_keys:
        logger.info(f"🧹 Volume cleanup: {len(expired_keys)} expired entries removed")
    
    return len(expired_keys)


def get_volume_store_stats() -> dict:
    """Volume store istatistiklerini döndür (debug için)."""
    pairs = set()
    for key in _VOLUME_STORE.keys():
        pair = key.rsplit('_', 1)[0]
        pairs.add(pair)
    
    return {
        'total': len(_VOLUME_STORE),
        'pairs': list(pairs)
    }


def has_volume_spike(volume_data):
    """Volume spike var mı kontrol et"""
    if not volume_data:
        return False
    return volume_data.get('spike', False)


def get_spike_ratio(volume_data):
    """Volume spike oranını al"""
    if not volume_data:
        return 0.0
    return volume_data.get('spike_ratio', 0.0)


def get_volume_strength(volume_data):
    """
    Volume gücünü al
    
    v2.3.11 FIX: Default 'medium' → 'low' (güvenli varsayılan)
    """
    if not volume_data:
        return 'low'
    
    # v2.3.11: Key eksikse log + güvenli default
    if 'strength' not in volume_data:
        logger.debug(f"⚠️ volume_data has no 'strength' key, defaulting to 'low'")
        return 'low'
    
    return volume_data.get('strength', 'low')


def get_volume_trend(volume_data):
    """Volume trendini al"""
    if not volume_data:
        return 'stable'
    return volume_data.get('trend', 'stable')


def select_best_volume(volume_data_dict):
    """Tüm timeframe'lerin volume verileri arasından en iyisini seçer."""
    if not volume_data_dict:
        logger.debug("📊 Volume: Veri yok, default 3m")
        return {'spike': False, 'spike_ratio': 0.0}, '3m'
    
    priority_order = ['4h', '2h', '1h', '30m', '15m', '5m', '3m']
    
    for tf in priority_order:
        data = volume_data_dict.get(tf)
        if data and has_volume_spike(data):
            logger.info(f"📊 Volume SPIKE bulundu: {tf} ({data.get('spike_ratio', 0):.2f}x)")
            return data, tf
    
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
    """Belirli timeframe için volume analizi yapar."""
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
        
        tradeable = has_spike or spike_ratio >= VOLUME_TRADEABLE_MIN
        
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
