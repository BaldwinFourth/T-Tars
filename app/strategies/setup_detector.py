# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v2.0.9
============================
Trading setup orchestrator.

v2.0.9:
- FIX: TIMEFRAMES listesinde virgül hatası düzeltildi ('1d' '4h' -> '1d', '4h')
- FIX: 10m kaldırıldı (OKX desteklemiyor)
- ADD: Tüm fonksiyonlara detaylı logging eklendi
- ADD: Exception handling iyileştirildi
"""

import logging
from app.strategies.ob_detector import detect_ob_long, detect_ob_short
from app.strategies.fvg_detector import detect_fvg_long, detect_fvg_short
from app.strategies.volume_analyzer import select_best_volume

logger = logging.getLogger(__name__)

# v2.0.9: Düzeltilmiş Timeframe listesi (10m kaldırıldı, virgül düzeltildi)
TIMEFRAMES = ['4h', '2h', '1h', '30m', '15m', '5m', '3m']


def detect_trading_setup(pair, market_data):
    """Otomatik tarama için - Tek setup döndürür"""
    try:
        if not market_data:
            logger.warning(f"⚠️ {pair}: Market data boş!")
            return False
        
        pdc = market_data.get('previous_day', {})
        bias = pdc.get('candle_type', 'red')
        bias_str = 'bullish' if bias == 'green' else 'bearish'
        current_price = market_data.get('current_price', 0)
        
        # Volume verisini sözlük olarak gönder
        volume_data, timeframe = select_best_volume(market_data.get('volume', {}))
        
        # Seçilen TF'ye göre OB/FVG al
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        atr = market_data['atr'].get(timeframe, 0)
        
        logger.info(f"🔍 {pair}: TF={timeframe}, OB={len(obs)}, FVG={len(fvgs)}, Bias={bias_str}, ATR={atr:.2f}")
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            logger.debug(f"📦 {pair}: OB kontrol - Type={ob['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and ob['type'] == 'bullish':
                result = detect_ob_long(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    logger.info(f"✅ {pair}: OB LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                result = detect_ob_short(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    logger.info(f"✅ {pair}: OB SHORT setup bulundu!")
                return result
        
        # FVG Kontrol
        if len(fvgs) > 0:
            fvg = fvgs[0]
            logger.debug(f"📊 {pair}: FVG kontrol - Type={fvg['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and fvg['type'] == 'bullish':
                result = detect_fvg_long(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    logger.info(f"✅ {pair}: FVG LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                result = detect_fvg_short(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    logger.info(f"✅ {pair}: FVG SHORT setup bulundu!")
                return result
        
        logger.debug(f"ℹ️ {pair}: Setup bulunamadı (Bias uyumsuz veya OB/FVG yok)")
        return False
        
    except Exception as e:
        logger.error(f"❌ {pair} Setup detection error: {e}")
        return False


def check_timeframe(pair, market_data, timeframe, bias, current_price):
    """Belirli bir timeframe için setup kontrol et"""
    setups = []
    try:
        volume = market_data['volume'].get(timeframe, {})
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        atr = market_data['atr'].get(timeframe, 0)
        
        logger.debug(f"🕐 {pair} [{timeframe}]: OB={len(obs)}, FVG={len(fvgs)}, Vol={volume.get('spike_ratio', 0):.2f}x")
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            if bias == 'bullish' and ob['type'] == 'bullish':
                s = detect_ob_long(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: OB LONG found!")
                    setups.append(s)
            elif bias == 'bearish' and ob['type'] == 'bearish':
                s = detect_ob_short(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: OB SHORT found!")
                    setups.append(s)
        
        # FVG Kontrol
        if len(fvgs) > 0:
            fvg = fvgs[0]
            if bias == 'bullish' and fvg['type'] == 'bullish':
                s = detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: FVG LONG found!")
                    setups.append(s)
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                s = detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    logger.info(f"✅ {pair} [{timeframe}]: FVG SHORT found!")
                    setups.append(s)
        
        return setups
        
    except KeyError as e:
        logger.error(f"❌ {pair} [{timeframe}]: Missing data key: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ {pair} [{timeframe}]: Check error: {e}")
        return []


def scan_setups(pair, market_data):
    """Tüm timeframe'leri tarayarak setup bul"""
    try:
        if not market_data:
            logger.warning(f"⚠️ {pair}: scan_setups - Market data boş!")
            return []
        
        pdc = market_data.get('previous_day', {})
        bias = 'bullish' if pdc.get('candle_type') == 'green' else 'bearish'
        current_price = market_data.get('current_price', 0)
        
        logger.info(f"🔎 {pair}: Scan başladı - Bias={bias}, Price=${current_price:.2f}, TFs={len(TIMEFRAMES)}")
        
        all_setups = []
        
        for tf in TIMEFRAMES:
            s = check_timeframe(pair, market_data, tf, bias, current_price)
            if s:
                all_setups.extend(s)
        
        if all_setups:
            logger.info(f"🎯 {pair}: Toplam {len(all_setups)} setup bulundu!")
        else:
            logger.debug(f"ℹ️ {pair}: Setup bulunamadı")
        
        return all_setups
        
    except Exception as e:
        logger.error(f"❌ {pair}: Scan error: {e}")
        return []


# Alias'lar (geriye uyumluluk)
detect_all_trading_setups = scan_setups
check_timeframe_for_setups = check_timeframe
