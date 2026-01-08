# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v2.6.0
=============================
Trading setup orchestrator with PDC bias + Fibo zone filtering.

v2.6.0:
- NEW: Pattern detection bilgisi setup'a ekleniyor
- NEW: pattern_info field'ı (Grok için detaylı pattern bilgisi)
- CHANGED: calculate_pdc_bias() artık pattern döndürüyor
- Detaylı pattern loglama

v2.5.1:
- CHANGED: FVG zone %50-150 (PDC içi + dışı)
- CHANGED: is_in_fvg_zone() artık direction parametresi alıyor
- CHANGED: Bias-aware fibo hesaplama
  - LONG: 0=Low, 100=High, extension yukarı
  - SHORT: 0=High, 100=Low, extension aşağı

v2.4.1:
- ADDED: Detaylı log'lar (Fibo zone reject, Bias mismatch, PDC is_doji)
- ADDED: Fibo zone reject log'unda fibo % gösteriliyor
- ADDED: Bias mismatch durumunda log

v2.4.0:
- NEW: PDC bias belirleme (yeşil=LONG, kırmızı=SHORT)
- NEW: Fibo zone filtreleme (OB: %70-90, FVG: %100-150)
- NEW: Doji reversal kontrolü

v2.1.0:
- TIMEFRAMES Config'den alınıyor
"""

import logging
from app.config import Config
from app.strategies.ob_detector import detect_ob_long, detect_ob_short, scan_order_blocks
from app.strategies.fvg_detector import detect_fvg_long, detect_fvg_short, scan_fair_value_gaps
from app.strategies.volume_analyzer import select_best_volume
from app.strategies.calculators import (
    calculate_pdc_bias,
    calculate_fibo_zones,
    is_in_ob_zone,
    is_in_fvg_zone,
    FVG_ZONE_MIN,
    FVG_ZONE_MAX
)

logger = logging.getLogger(__name__)

# Config'den al - bitget_service ile tutarlı
TIMEFRAMES = Config.TIMEFRAMES  # ['4h', '1h', '30m', '15m', '5m']


def _format_pattern_for_grok(pattern_result):
    """
    Pattern sonucunu Grok için okunabilir formata çevir.
    
    Args:
        pattern_result: detect_candle_patterns() çıktısı
    
    Returns:
        str: Grok prompt'una eklenecek pattern özeti
    """
    if not pattern_result or not pattern_result.get('pattern_detected'):
        return "Pattern tespit edilemedi"
    
    lines = []
    
    # Ana pattern
    lines.append(f"Pattern: {pattern_result.get('pattern_name', 'Unknown')}")
    lines.append(f"Sinyal: {pattern_result.get('signal', 'NEUTRAL')} ({pattern_result.get('signal_strength', 'NONE')})")
    lines.append(f"Confidence: %{int(pattern_result.get('confidence', 0) * 100)}")
    lines.append(f"Trend Context: {pattern_result.get('trend_context', 'UNKNOWN')}")
    
    if pattern_result.get('is_reversal_position'):
        lines.append("⚡ Reversal pozisyonunda (doğru konum)")
    
    # Momentum
    momentum = pattern_result.get('momentum', {})
    if momentum.get('trend') and momentum['trend'] != 'UNKNOWN':
        lines.append(f"Momentum: {momentum.get('trend', 'STABLE')} | Pressure: {momentum.get('pressure', 'NONE')}")
    
    # Tüm tespit edilen pattern'lar
    all_patterns = pattern_result.get('all_patterns', [])
    if len(all_patterns) > 1:
        lines.append(f"Diğer pattern'lar: {', '.join(p['name'] for p in all_patterns[1:3])}")
    
    # Bias önerisi
    if pattern_result.get('bias_suggestion'):
        lines.append(f"🎯 Pattern Bias Önerisi: {pattern_result['bias_suggestion']}")
    
    if pattern_result.get('skip_recommended'):
        lines.append("⚠️ Belirsizlik yüksek - SKIP öneriliyor")
    
    return "\n".join(lines)


def detect_trading_setup(pair, market_data):
    """
    Otomatik tarama için - Tek setup döndürür.
    
    v2.6.0: Pattern detection entegrasyonu
    """
    try:
        if not market_data:
            logger.warning(f"⚠️ {pair}: Market data boş!")
            return False
        
        # v2.6.0: PDC bazlı bias belirleme (pattern dahil)
        daily_ohlcv = market_data.get('daily_ohlcv', [])
        if daily_ohlcv and len(daily_ohlcv) >= 5:
            pdc_result = calculate_pdc_bias(daily_ohlcv)
            bias = pdc_result['bias']
            bias_str = 'bullish' if bias == 'LONG' else 'bearish'
            pdc = pdc_result['pdc']
            doji_warning = pdc_result['doji_warning']
            reversal_mode = pdc_result['reversal_mode']
            pattern_result = pdc_result.get('pattern')  # v2.6.0: Yeni
            
            # Fibo zone hesapla
            fibo_data = calculate_fibo_zones(pdc, bias)
            
            # v2.6.0: Pattern bilgisini logla
            if pattern_result and pattern_result.get('pattern_detected'):
                logger.info(f"🕯️ {pair}: Pattern={pattern_result['pattern_name']} | "
                           f"Signal={pattern_result['signal']} | "
                           f"Confidence={pattern_result['confidence']:.2f} | "
                           f"Trend={pattern_result['trend_context']}")
            
            if doji_warning:
                logger.info(f"⚠️ {pair}: Doji uyarısı! Count={pdc_result['doji_count']}, PDC_is_Doji={pdc_result['pdc_is_doji']}, Reversal={reversal_mode}")
        else:
            # Fallback: Eski yöntem
            pdc = market_data.get('previous_day', {})
            bias = 'LONG' if pdc.get('candle_type') == 'green' else 'SHORT'
            bias_str = 'bullish' if bias == 'LONG' else 'bearish'
            fibo_data = None
            doji_warning = False
            reversal_mode = False
            pattern_result = None
        
        current_price = market_data.get('current_price', 0)
        
        # Volume verisini sözlük olarak gönder
        volume_data, timeframe = select_best_volume(market_data.get('volume', {}))
        
        # Seçilen TF'ye göre OB/FVG al
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        atr = market_data['atr'].get(timeframe, 0)
        
        # v2.5.1: Fibo zone filtresi (FVG için direction bazlı)
        if fibo_data:
            obs_before = len(obs)
            fvgs_before = len(fvgs)
            
            # OB filtreleme (detaylı log ile) - %70-90 PDC içi
            filtered_obs = []
            for ob in obs:
                ob_mid = ob.get('mid', (ob['high']+ob['low'])/2)
                if is_in_ob_zone(ob_mid, fibo_data):
                    filtered_obs.append(ob)
                else:
                    pdc_range = fibo_data['pdc_high'] - fibo_data['pdc_low']
                    if pdc_range > 0:
                        fibo_pct = ((ob_mid - fibo_data['pdc_low']) / pdc_range) * 100
                    else:
                        fibo_pct = 0
                    logger.info(f"📐 {pair}: OB {ob['type']} [{timeframe}] REJECTED - Fibo %{fibo_pct:.1f} (zone: %70-90)")
            obs = filtered_obs
            
            # FVG filtreleme (v2.5.1: direction bazlı, %100-150 extension)
            filtered_fvgs = []
            for fvg in fvgs:
                fvg_mid = fvg.get('mid', (fvg['high']+fvg['low'])/2)
                fvg_direction = 'LONG' if fvg['type'] == 'bullish' else 'SHORT'
                
                if is_in_fvg_zone(fvg_mid, fibo_data, fvg_direction):
                    filtered_fvgs.append(fvg)
                else:
                    pdc_range = fibo_data['pdc_high'] - fibo_data['pdc_low']
                    if pdc_range > 0:
                        fibo_pct = ((fvg_mid - fibo_data['pdc_low']) / pdc_range) * 100
                    else:
                        fibo_pct = 0
                    zone_str = f"%{int(FVG_ZONE_MIN*100)}-{int(FVG_ZONE_MAX*100)}"
                    logger.info(f"📐 {pair}: FVG {fvg['type']} [{timeframe}] REJECTED - Fibo %{fibo_pct:.1f} (zone: {zone_str})")
            fvgs = filtered_fvgs
            
            if obs_before > len(obs) or fvgs_before > len(fvgs):
                logger.info(f"📐 {pair}: Fibo filtre: OB {obs_before}→{len(obs)}, FVG {fvgs_before}→{len(fvgs)}")
        
        logger.info(f"🔍 {pair}: TF={timeframe}, OB={len(obs)}, FVG={len(fvgs)}, Bias={bias}, Doji={doji_warning}")
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            logger.debug(f"📦 {pair}: OB kontrol - Type={ob['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and ob['type'] == 'bullish':
                result = detect_ob_long(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair}: OB LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                result = detect_ob_short(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair}: OB SHORT setup bulundu!")
                return result
            else:
                # Bias mismatch
                logger.info(f"⚠️ {pair}: OB BIAS MISMATCH - OB={ob['type']}, Bias={bias_str} → SKIP")
        
        # FVG Kontrol
        if len(fvgs) > 0:
            fvg = fvgs[0]
            logger.debug(f"📊 {pair}: FVG kontrol - Type={fvg['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and fvg['type'] == 'bullish':
                result = detect_fvg_long(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair}: FVG LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                result = detect_fvg_short(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair}: FVG SHORT setup bulundu!")
                return result
            else:
                # Bias mismatch
                logger.info(f"⚠️ {pair}: FVG BIAS MISMATCH - FVG={fvg['type']}, Bias={bias_str} → SKIP")
        
        logger.debug(f"ℹ️ {pair}: Setup bulunamadı (Bias uyumsuz veya OB/FVG yok)")
        return False
        
    except Exception as e:
        logger.error(f"❌ {pair} Setup detection error: {e}")
        return False


def check_timeframe(pair, market_data, timeframe, bias, current_price, fibo_data=None, pattern_result=None):
    """
    Belirli bir timeframe için setup kontrol et.
    
    v2.6.0: pattern_result parametresi eklendi
    """
    setups = []
    try:
        volume = market_data['volume'].get(timeframe, {})
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        atr = market_data['atr'].get(timeframe, 0)
        
        # v2.5.1: Fibo zone filtresi (direction bazlı)
        if fibo_data:
            obs = [ob for ob in obs if is_in_ob_zone(ob.get('mid', (ob['high']+ob['low'])/2), fibo_data)]
            fvgs = [fvg for fvg in fvgs if is_in_fvg_zone(
                fvg.get('mid', (fvg['high']+fvg['low'])/2), 
                fibo_data, 
                'LONG' if fvg['type'] == 'bullish' else 'SHORT'
            )]
        
        logger.debug(f"🕐 {pair} [{timeframe}]: OB={len(obs)}, FVG={len(fvgs)}, Vol={volume.get('spike_ratio', 0):.2f}x")
        
        bias_str = 'bullish' if bias == 'LONG' else 'bearish'
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            if bias_str == 'bullish' and ob['type'] == 'bullish':
                s = detect_ob_long(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        s['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        s['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair} [{timeframe}]: OB LONG found!")
                    setups.append(s)
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                s = detect_ob_short(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        s['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        s['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair} [{timeframe}]: OB SHORT found!")
                    setups.append(s)
        
        # FVG Kontrol
        if len(fvgs) > 0:
            fvg = fvgs[0]
            if bias_str == 'bullish' and fvg['type'] == 'bullish':
                s = detect_fvg_long(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        s['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        s['pattern_data'] = pattern_result
                    logger.info(f"✅ {pair} [{timeframe}]: FVG LONG found!")
                    setups.append(s)
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                s = detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        s['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        s['pattern_data'] = pattern_result
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
    """
    Tüm timeframe'leri tarayarak setup bul.
    
    v2.6.0: Pattern detection entegrasyonu
    """
    try:
        if not market_data:
            logger.warning(f"⚠️ {pair}: scan_setups - Market data boş!")
            return []
        
        # v2.6.0: PDC bazlı bias belirleme (pattern dahil)
        daily_ohlcv = market_data.get('daily_ohlcv', [])
        if daily_ohlcv and len(daily_ohlcv) >= 5:
            pdc_result = calculate_pdc_bias(daily_ohlcv)
            bias = pdc_result['bias']
            pdc = pdc_result['pdc']
            doji_warning = pdc_result['doji_warning']
            reversal_mode = pdc_result['reversal_mode']
            pattern_result = pdc_result.get('pattern')  # v2.6.0: Yeni
            
            # Fibo zone hesapla
            fibo_data = calculate_fibo_zones(pdc, bias)
            
            # v2.6.0: Pattern bilgisini logla
            if pattern_result and pattern_result.get('pattern_detected'):
                logger.info(f"🕯️ {pair}: Pattern={pattern_result['pattern_name']} | "
                           f"Signal={pattern_result['signal']} | "
                           f"Confidence={pattern_result['confidence']:.2f}")
            
            if doji_warning:
                logger.info(f"⚠️ {pair}: Doji uyarısı! Count={pdc_result['doji_count']}, PDC_is_Doji={pdc_result['pdc_is_doji']}, Reversal={reversal_mode}")
        else:
            # Fallback: Eski yöntem
            pdc = market_data.get('previous_day', {})
            bias = 'LONG' if pdc.get('candle_type') == 'green' else 'SHORT'
            fibo_data = None
            doji_warning = False
            reversal_mode = False
            pattern_result = None
        
        current_price = market_data.get('current_price', 0)
        
        logger.info(f"🔎 {pair}: Scan başladı - Bias={bias}, Price=${current_price:.2f}, TFs={len(TIMEFRAMES)}, Doji={doji_warning}")
        
        all_setups = []
        
        for tf in TIMEFRAMES:
            # v2.6.0: pattern_result'u check_timeframe'e geç
            s = check_timeframe(pair, market_data, tf, bias, current_price, fibo_data, pattern_result)
            if s:
                # Doji bilgisini ekle
                for setup in s:
                    setup['doji_warning'] = doji_warning
                    setup['reversal_mode'] = reversal_mode
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
