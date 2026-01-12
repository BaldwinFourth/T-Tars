# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v2.8.0
=============================
Trading setup orchestrator with PDC bias + Fibo zone filtering + TF Hierarchy.

v2.8.0:
- NEW: Timeframe hierarchy enforcement (1D > 1h > 15m)
- NEW: is_higher_tf_aligned() kontrolü
- NEW: check_pdc_breakout() entegrasyonu
- NEW: Intraday bias değişiklik desteği
- IMPORT: TIMEFRAME_HIERARCHY, check_pdc_breakout, is_higher_tf_aligned, get_intraday_bias

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
    FVG_ZONE_MAX,
    # v2.7.0: Yeni import'lar
    TIMEFRAME_HIERARCHY,
    check_pdc_breakout,
    is_higher_tf_aligned,
    get_intraday_bias,
    format_price
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
    
    v2.7.0: TF Hierarchy + PDC Breakout entegrasyonu
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
            pdc_bias = pdc_result['bias']
            pdc = pdc_result['pdc']
            doji_warning = pdc_result['doji_warning']
            reversal_mode = pdc_result['reversal_mode']
            pattern_result = pdc_result.get('pattern')  # v2.6.0: Yeni
            
            # v2.7.0: PDC Breakout kontrolü - Intraday bias belirleme
            current_price = market_data.get('current_price', 0)
            intraday_result = get_intraday_bias(current_price, pdc, pdc_bias)
            bias = intraday_result['bias']
            bias_source = intraday_result['source']
            
            # v2.7.0: Breakout bildirimi için bilgi
            breakout_result = check_pdc_breakout(current_price, pdc, pdc_bias)
            if breakout_result['breakout_detected']:
                logger.info(f"🚨 {pair}: {breakout_result['message']}")
            
            bias_str = 'bullish' if bias == 'LONG' else 'bearish'
            
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
            
            # v2.7.0: Bias source loglama
            if bias_source != 'PDC':
                logger.info(f"📊 {pair}: Intraday bias={bias} (source: {bias_source})")
        else:
            # Fallback: Eski yöntem
            pdc = market_data.get('previous_day', {})
            bias = 'LONG' if pdc.get('candle_type') == 'green' else 'SHORT'
            bias_str = 'bullish' if bias == 'LONG' else 'bearish'
            bias_source = 'PDC'
            fibo_data = None
            doji_warning = False
            reversal_mode = False
            pattern_result = None
            breakout_result = None
        
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
        
        logger.info(f"🔍 {pair}: TF={timeframe}, OB={len(obs)}, FVG={len(fvgs)}, Bias={bias} ({bias_source}), Doji={doji_warning}")
        
        # OB Kontrol
        if len(obs) > 0:
            ob = obs[0]
            logger.debug(f"📦 {pair}: OB kontrol - Type={ob['type']}, Bias={bias_str}")
            if bias_str == 'bullish' and ob['type'] == 'bullish':
                result = detect_ob_long(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    result['bias_source'] = bias_source  # v2.7.0
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    # v2.7.0: Breakout bilgisi
                    if breakout_result:
                        result['pdc_breakout'] = breakout_result
                    logger.info(f"✅ {pair}: OB LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                result = detect_ob_short(ob, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    result['bias_source'] = bias_source  # v2.7.0
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    # v2.7.0: Breakout bilgisi
                    if breakout_result:
                        result['pdc_breakout'] = breakout_result
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
                    result['bias_source'] = bias_source  # v2.7.0
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    # v2.7.0: Breakout bilgisi
                    if breakout_result:
                        result['pdc_breakout'] = breakout_result
                    logger.info(f"✅ {pair}: FVG LONG setup bulundu!")
                return result
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                result = detect_fvg_short(fvg, volume_data, atr, timeframe, current_price, pair)
                if result:
                    result['doji_warning'] = doji_warning
                    result['reversal_mode'] = reversal_mode
                    result['bias_source'] = bias_source  # v2.7.0
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        result['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        result['pattern_data'] = pattern_result
                    # v2.7.0: Breakout bilgisi
                    if breakout_result:
                        result['pdc_breakout'] = breakout_result
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


def check_timeframe(pair, market_data, timeframe, bias, current_price, fibo_data=None, pattern_result=None, htf_bias=None):
    """
    Belirli bir timeframe için setup kontrol et.
    
    v2.7.0: htf_bias parametresi + TF hierarchy kontrolü
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
        
        # v2.7.0: TF Hierarchy kontrolü
        if htf_bias:
            alignment = is_higher_tf_aligned(timeframe, bias, htf_bias)
            if not alignment['aligned']:
                logger.info(f"⚠️ {pair} [{timeframe}]: TF HIERARCHY MISMATCH - {alignment['message']} → SKIP")
                return []
        
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
                    # v2.7.0: HTF alignment bilgisi
                    if htf_bias:
                        s['htf_aligned'] = True
                    logger.info(f"✅ {pair} [{timeframe}]: OB LONG found!")
                    setups.append(s)
            elif bias_str == 'bearish' and ob['type'] == 'bearish':
                s = detect_ob_short(ob, volume, atr, timeframe, current_price, pair)
                if s:
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        s['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        s['pattern_data'] = pattern_result
                    # v2.7.0: HTF alignment bilgisi
                    if htf_bias:
                        s['htf_aligned'] = True
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
                    # v2.7.0: HTF alignment bilgisi
                    if htf_bias:
                        s['htf_aligned'] = True
                    logger.info(f"✅ {pair} [{timeframe}]: FVG LONG found!")
                    setups.append(s)
            elif bias_str == 'bearish' and fvg['type'] == 'bearish':
                s = detect_fvg_short(fvg, volume, atr, timeframe, current_price, pair)
                if s:
                    # v2.6.0: Pattern bilgisi ekle
                    if pattern_result:
                        s['pattern_info'] = _format_pattern_for_grok(pattern_result)
                        s['pattern_data'] = pattern_result
                    # v2.7.0: HTF alignment bilgisi
                    if htf_bias:
                        s['htf_aligned'] = True
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
    
    v2.7.0: TF Hierarchy + PDC Breakout entegrasyonu
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
            pdc_bias = pdc_result['bias']
            pdc = pdc_result['pdc']
            doji_warning = pdc_result['doji_warning']
            reversal_mode = pdc_result['reversal_mode']
            pattern_result = pdc_result.get('pattern')  # v2.6.0: Yeni
            
            # v2.7.0: PDC Breakout kontrolü - Intraday bias belirleme
            current_price = market_data.get('current_price', 0)
            intraday_result = get_intraday_bias(current_price, pdc, pdc_bias)
            bias = intraday_result['bias']
            bias_source = intraday_result['source']
            
            # v2.7.0: Breakout bildirimi için kontrol
            breakout_result = check_pdc_breakout(current_price, pdc, pdc_bias)
            if breakout_result['breakout_detected']:
                logger.info(f"🚨 {pair}: {breakout_result['message']}")
            
            # Fibo zone hesapla
            fibo_data = calculate_fibo_zones(pdc, bias)
            
            # v2.7.0: HTF Bias dictionary oluştur
            htf_bias = {
                '1D': bias,  # PDC bias
                '1h': bias,  # Şimdilik aynı (gelecekte 1h verisi eklenebilir)
            }
            
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
            bias_source = 'PDC'
            fibo_data = None
            doji_warning = False
            reversal_mode = False
            pattern_result = None
            htf_bias = None
            breakout_result = None
        
        current_price = market_data.get('current_price', 0)
        
        logger.info(f"🔎 {pair}: Scan başladı - Bias={bias} ({bias_source}), Price={format_price(current_price)}, TFs={len(TIMEFRAMES)}, Doji={doji_warning}")
        
        all_setups = []
        
        for tf in TIMEFRAMES:
            # v2.7.0: htf_bias'ı check_timeframe'e geç
            s = check_timeframe(pair, market_data, tf, bias, current_price, fibo_data, pattern_result, htf_bias)
            if s:
                # Doji ve breakout bilgisini ekle
                for setup in s:
                    setup['doji_warning'] = doji_warning
                    setup['reversal_mode'] = reversal_mode
                    setup['bias_source'] = bias_source  # v2.7.0
                    if breakout_result:
                        setup['pdc_breakout'] = breakout_result
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
