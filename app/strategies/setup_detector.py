# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v1.4.7
============================
Trading setup tespit fonksiyonları.
OB, FVG, Volume Spike detection ve multi-timeframe scan.

v1.4.7 Düzeltmeleri:
- FVG setup'lara dual TP sistemi (tp1, tp2) eklendi
- FVG için entry_price = FVG mid-point
- R:R hesabı entry_price'a göre düzeltildi
- Tüm tracking field'ları FVG'ye eklendi
"""

import logging
from app.config import Config
from app.strategies.calculators import (
    calculate_setup_strength, 
    MIN_RR_RATIO,
    STOP_MULTIPLIER,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER
)

logger = logging.getLogger(__name__)


def detect_trading_setup(pair, market_data):
    """Trading setup tespit et + Entry/Stop/TP hesapla"""
    try:
        pdc = market_data['previous_day']
        bias = 'bullish' if pdc['candle_type'] == 'green' else 'bearish'
        current_price = market_data['current_price']
        
        volume_5m = market_data['volume']['5m']
        volume_3m = market_data['volume']['3m']
        obs_5m = market_data['smart_money']['order_blocks']['5m']
        obs_3m = market_data['smart_money']['order_blocks']['3m']
        fvgs_5m = market_data['smart_money']['fair_value_gaps']['5m']
        fvgs_3m = market_data['smart_money']['fair_value_gaps']['3m']
        
        volume = volume_5m if volume_5m['spike'] else volume_3m
        obs = obs_5m if len(obs_5m) > 0 else obs_3m
        fvgs = fvgs_5m if len(fvgs_5m) > 0 else fvgs_3m
        timeframe = '5m' if (volume_5m['spike'] or len(obs_5m) > 0) else '3m'
        
        has_volume_spike = volume['spike']
        has_order_block = len(obs) > 0
        has_fvg = len(fvgs) > 0
        
        logger.info(f"🔍 Setup check {pair}: volume_spike={has_volume_spike} ({volume['spike_ratio']:.1f}x), OB={has_order_block} ({len(obs)}), FVG={has_fvg} ({len(fvgs)}), bias={bias}, TF={timeframe}")
        
        atr_15m = market_data['atr']['15m']
        atr_5m = market_data['atr']['5m']
        atr_3m = market_data['atr']['3m']
        
        # OB SETUP - LONG
        if has_order_block and has_volume_spike:
            ob = obs[0]
            
            if bias == 'bullish' and ob['type'] == 'bullish':
                entry_zone = f"${ob['low']:,.2f} - ${ob['price']:,.2f}"
                entry_price = (ob['low'] + ob['price']) / 2  # OB mid-point
                
                atr = atr_5m if timeframe == '5m' else atr_3m
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = ob['low'] - stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                tp1_price = entry_price + (atr * TP1_MULTIPLIER)
                tp2_price = entry_price + (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                risk = abs(entry_price - stop_price)
                reward = abs(tp1_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 LONG OB R:R: entry=${entry_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1_price:.2f}, risk=${risk:.2f}, reward={reward:.2f}, ratio={rr_ratio:.2f}")
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"LONG OB rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
                    return False
                
                balance = Config.DEFAULT_BALANCE
                setup_strength = calculate_setup_strength(
                    volume_spike_ratio=volume['spike_ratio'],
                    ob_or_fvg_strength=ob['strength'],
                    rr_ratio=rr_ratio,
                    confidence='HIGH'
                )
                risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                risk_usd = (balance * risk_percent) / 100
                
                detailed_explanation = f"""
📊 **OB Analizi:**
• Bullish OB @ ${ob['low']:,.2f} - ${ob['price']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x ({volume['strength'].upper()})
• OB strength: {ob['strength'].upper()}
• Timeframe: {timeframe.upper()}

🎯 **Entry Stratejisi:**
• Entry Zone: {entry_zone}
• Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📈 **TP/Stop:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                
                return {
                    'type': 'OB + Volume Spike (LONG)',
                    'confidence': 'HIGH',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    'current_price': current_price,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'tp1_price': tp1_price,
                    'tp2_price': tp2_price,
                    'volume_spike_ratio': volume['spike_ratio'],
                    'ob_strength': ob['strength'],
                    'rr_ratio': rr_ratio,
                    'detailed_explanation': detailed_explanation,
                    'details': f"Bullish OB @ ${ob['low']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                }
            
            # OB SETUP - SHORT
            elif bias == 'bearish' and ob['type'] == 'bearish':
                entry_zone = f"${ob['price']:,.2f} - ${ob['high']:,.2f}"
                entry_price = (ob['price'] + ob['high']) / 2  # OB mid-point
                
                atr = atr_5m if timeframe == '5m' else atr_3m
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = ob['high'] + stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                tp1_price = entry_price - (atr * TP1_MULTIPLIER)
                tp2_price = entry_price - (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                risk = abs(stop_price - entry_price)
                reward = abs(entry_price - tp1_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 SHORT OB R:R: entry=${entry_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1_price:.2f}, risk=${risk:.2f}, reward={reward:.2f}, ratio={rr_ratio:.2f}")
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"SHORT OB rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
                    return False
                
                balance = Config.DEFAULT_BALANCE
                setup_strength = calculate_setup_strength(
                    volume_spike_ratio=volume['spike_ratio'],
                    ob_or_fvg_strength=ob['strength'],
                    rr_ratio=rr_ratio,
                    confidence='HIGH'
                )
                risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                risk_usd = (balance * risk_percent) / 100
                
                detailed_explanation = f"""
📊 **OB Analizi:**
• Bearish OB @ ${ob['price']:,.2f} - ${ob['high']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x ({volume['strength'].upper()})
• OB strength: {ob['strength'].upper()}
• Timeframe: {timeframe.upper()}

🎯 **Entry Stratejisi:**
• Entry Zone: {entry_zone}
• Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📉 **TP/Stop:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                
                return {
                    'type': 'OB + Volume Spike (SHORT)',
                    'confidence': 'HIGH',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    'current_price': current_price,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'tp1_price': tp1_price,
                    'tp2_price': tp2_price,
                    'volume_spike_ratio': volume['spike_ratio'],
                    'ob_strength': ob['strength'],
                    'rr_ratio': rr_ratio,
                    'detailed_explanation': detailed_explanation,
                    'details': f"Bearish OB @ ${ob['high']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                }
        
        # FVG SETUP - LONG
        if has_fvg and has_volume_spike:
            fvg = fvgs[0]
            
            if bias == 'bullish' and fvg['type'] == 'bullish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                entry_price = (fvg['gap_low'] + fvg['gap_high']) / 2  # FVG mid-point
                
                atr = atr_5m if timeframe == '5m' else atr_3m
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = fvg['gap_low'] - stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                tp1_price = entry_price + (atr * TP1_MULTIPLIER)
                tp2_price = entry_price + (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                risk = abs(entry_price - stop_price)
                reward = abs(tp1_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 LONG FVG R:R: entry=${entry_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1_price:.2f}, risk=${risk:.2f}, reward={reward:.2f}, ratio={rr_ratio:.2f}")
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"FVG LONG rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
                    return False
                
                balance = Config.DEFAULT_BALANCE
                fvg_strength = fvg.get('volume_strength', 'medium')
                setup_strength = calculate_setup_strength(
                    volume_spike_ratio=volume['spike_ratio'],
                    ob_or_fvg_strength=fvg_strength,
                    rr_ratio=rr_ratio,
                    confidence='MEDIUM'
                )
                risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                risk_usd = (balance * risk_percent) / 100
                
                detailed_explanation = f"""
📊 **FVG Analizi:**
• Bullish FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}
• Gap size: ${fvg['gap_size']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x
• Timeframe: {timeframe.upper()}

🎯 **Entry:**
• Entry Zone: {entry_zone}
• Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📈 **TP/Stop:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                
                return {
                    'type': 'FVG + Volume Spike (LONG)',
                    'confidence': 'MEDIUM',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    'current_price': current_price,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'tp1_price': tp1_price,
                    'tp2_price': tp2_price,
                    'volume_spike_ratio': volume['spike_ratio'],
                    'fvg_strength': fvg_strength,
                    'rr_ratio': rr_ratio,
                    'detailed_explanation': detailed_explanation,
                    'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                }
            
            # FVG SETUP - SHORT
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                entry_price = (fvg['gap_low'] + fvg['gap_high']) / 2  # FVG mid-point
                
                atr = atr_5m if timeframe == '5m' else atr_3m
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = fvg['gap_high'] + stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                tp1_price = entry_price - (atr * TP1_MULTIPLIER)
                tp2_price = entry_price - (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                risk = abs(stop_price - entry_price)
                reward = abs(entry_price - tp1_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 SHORT FVG R:R: entry=${entry_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1_price:.2f}, risk=${risk:.2f}, reward={reward:.2f}, ratio={rr_ratio:.2f}")
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"FVG SHORT rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
                    return False
                
                balance = Config.DEFAULT_BALANCE
                fvg_strength = fvg.get('volume_strength', 'medium')
                setup_strength = calculate_setup_strength(
                    volume_spike_ratio=volume['spike_ratio'],
                    ob_or_fvg_strength=fvg_strength,
                    rr_ratio=rr_ratio,
                    confidence='MEDIUM'
                )
                risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                risk_usd = (balance * risk_percent) / 100
                
                detailed_explanation = f"""
📊 **FVG Analizi:**
• Bearish FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}
• Gap size: ${fvg['gap_size']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x
• Timeframe: {timeframe.upper()}

🎯 **Entry:**
• Entry Zone: {entry_zone}
• Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📉 **TP/Stop:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                
                return {
                    'type': 'FVG + Volume Spike (SHORT)',
                    'confidence': 'MEDIUM',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    'current_price': current_price,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'tp1_price': tp1_price,
                    'tp2_price': tp2_price,
                    'volume_spike_ratio': volume['spike_ratio'],
                    'fvg_strength': fvg_strength,
                    'rr_ratio': rr_ratio,
                    'detailed_explanation': detailed_explanation,
                    'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                }
        
        return False
    except Exception as e:
        logger.error(f"Setup detection error: {e}")
        return False


def check_timeframe_for_setups(pair, market_data, timeframe, bias, current_price):
    """
    Belirli bir timeframe'de OB ve FVG setup'larını kontrol et
    v1.4.7: FVG dual TP + entry_price fix
    """
    setups = []
    
    try:
        volume = market_data['volume'].get(timeframe, {})
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        
        atr_map = {
            '4h': market_data['atr'].get('4h', 0),
            '1h': market_data['atr'].get('1h', 0),
            '15m': market_data['atr'].get('15m', 0),
            '5m': market_data['atr'].get('5m', 0),
            '3m': market_data['atr'].get('3m', 0)
        }
        atr = atr_map.get(timeframe, market_data['atr'].get('15m', 0))
        
        if not volume or not volume.get('spike'):
            return []
        
        # ==================== OB SETUP - LONG ====================
        if len(obs) > 0:
            ob = obs[0]
            
            if bias == 'bullish' and ob['type'] == 'bullish':
                entry_zone = f"${ob['low']:,.2f} - ${ob['price']:,.2f}"
                entry_price = (ob['low'] + ob['price']) / 2
                
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = ob['low'] - stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                tp1_price = entry_price + (atr * TP1_MULTIPLIER)
                tp2_price = entry_price + (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                risk = abs(entry_price - stop_price)
                reward = abs(tp1_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 {pair} {timeframe.upper()} LONG OB R:R: {rr_ratio:.2f}")
                
                if rr_ratio >= MIN_RR_RATIO:
                    balance = Config.DEFAULT_BALANCE
                    setup_strength = calculate_setup_strength(
                        volume_spike_ratio=volume['spike_ratio'],
                        ob_or_fvg_strength=ob['strength'],
                        rr_ratio=rr_ratio,
                        confidence='HIGH'
                    )
                    risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                    risk_usd = (balance * risk_percent) / 100
                    
                    detailed_explanation = f"""
📊 **OB Analizi:**
• Bullish OB @ ${ob['low']:,.2f} - ${ob['price']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x ({volume['strength'].upper()})
• OB strength: {ob['strength'].upper()}
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📈 **TP/Stop:**
• ATR: ${atr:,.2f} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                    
                    setups.append({
                        'type': 'OB + Volume Spike (LONG)',
                        'confidence': 'HIGH',
                        'timeframe': timeframe,
                        'entry_zone': entry_zone,
                        'stop_loss': stop_loss,
                        'tp1': tp1,
                        'tp2': tp2,
                        'current_price': current_price,
                        'entry_price': entry_price,
                        'stop_price': stop_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'volume_spike_ratio': volume['spike_ratio'],
                        'ob_strength': ob['strength'],
                        'rr_ratio': rr_ratio,
                        'detailed_explanation': detailed_explanation,
                        'details': f"Bullish OB @ ${ob['low']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                    })
            
            # ==================== OB SETUP - SHORT ====================
            elif bias == 'bearish' and ob['type'] == 'bearish':
                entry_zone = f"${ob['price']:,.2f} - ${ob['high']:,.2f}"
                entry_price = (ob['price'] + ob['high']) / 2
                
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = ob['high'] + stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                tp1_price = entry_price - (atr * TP1_MULTIPLIER)
                tp2_price = entry_price - (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                risk = abs(stop_price - entry_price)
                reward = abs(entry_price - tp1_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 {pair} {timeframe.upper()} SHORT OB R:R: {rr_ratio:.2f}")
                
                if rr_ratio >= MIN_RR_RATIO:
                    balance = Config.DEFAULT_BALANCE
                    setup_strength = calculate_setup_strength(
                        volume_spike_ratio=volume['spike_ratio'],
                        ob_or_fvg_strength=ob['strength'],
                        rr_ratio=rr_ratio,
                        confidence='HIGH'
                    )
                    risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                    risk_usd = (balance * risk_percent) / 100
                    
                    detailed_explanation = f"""
📊 **OB Analizi:**
• Bearish OB @ ${ob['price']:,.2f} - ${ob['high']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x ({volume['strength'].upper()})
• OB strength: {ob['strength'].upper()}
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📉 **TP/Stop:**
• ATR: ${atr:,.2f} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                    
                    setups.append({
                        'type': 'OB + Volume Spike (SHORT)',
                        'confidence': 'HIGH',
                        'timeframe': timeframe,
                        'entry_zone': entry_zone,
                        'stop_loss': stop_loss,
                        'tp1': tp1,
                        'tp2': tp2,
                        'current_price': current_price,
                        'entry_price': entry_price,
                        'stop_price': stop_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'volume_spike_ratio': volume['spike_ratio'],
                        'ob_strength': ob['strength'],
                        'rr_ratio': rr_ratio,
                        'detailed_explanation': detailed_explanation,
                        'details': f"Bearish OB @ ${ob['high']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                    })
        
        # ==================== FVG SETUP - LONG ====================
        if len(fvgs) > 0:
            fvg = fvgs[0]
            
            if bias == 'bullish' and fvg['type'] == 'bullish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                entry_price = (fvg['gap_low'] + fvg['gap_high']) / 2  # FVG mid-point
                
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = fvg['gap_low'] - stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                # Dual TP System (v1.4.7)
                tp1_price = entry_price + (atr * TP1_MULTIPLIER)
                tp2_price = entry_price + (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                # R:R based on entry_price, not current_price
                risk = abs(entry_price - stop_price)
                reward = abs(tp1_price - entry_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 {pair} {timeframe.upper()} LONG FVG R:R: {rr_ratio:.2f} (entry=${entry_price:.2f})")
                
                if rr_ratio >= MIN_RR_RATIO:
                    fvg_strength = fvg.get('volume_strength', 'medium')
                    balance = Config.DEFAULT_BALANCE
                    setup_strength = calculate_setup_strength(
                        volume_spike_ratio=volume['spike_ratio'],
                        ob_or_fvg_strength=fvg_strength,
                        rr_ratio=rr_ratio,
                        confidence='MEDIUM'
                    )
                    risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                    risk_usd = (balance * risk_percent) / 100
                    
                    detailed_explanation = f"""
📊 **FVG Analizi:**
• Bullish FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}
• Gap size: ${fvg['gap_size']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📈 **TP/Stop:**
• ATR: ${atr:,.2f} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                    
                    setups.append({
                        'type': 'FVG + Volume Spike (LONG)',
                        'confidence': 'MEDIUM',
                        'timeframe': timeframe,
                        'entry_zone': entry_zone,
                        'stop_loss': stop_loss,
                        'tp1': tp1,
                        'tp2': tp2,
                        'current_price': current_price,
                        'entry_price': entry_price,
                        'stop_price': stop_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'volume_spike_ratio': volume['spike_ratio'],
                        'fvg_strength': fvg_strength,
                        'rr_ratio': rr_ratio,
                        'detailed_explanation': detailed_explanation,
                        'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                    })
            
            # ==================== FVG SETUP - SHORT ====================
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                entry_price = (fvg['gap_low'] + fvg['gap_high']) / 2  # FVG mid-point
                
                stop_distance = atr * STOP_MULTIPLIER
                stop_price = fvg['gap_high'] + stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                # Dual TP System (v1.4.7)
                tp1_price = entry_price - (atr * TP1_MULTIPLIER)
                tp2_price = entry_price - (atr * TP2_MULTIPLIER)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                # R:R based on entry_price, not current_price
                risk = abs(stop_price - entry_price)
                reward = abs(entry_price - tp1_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 {pair} {timeframe.upper()} SHORT FVG R:R: {rr_ratio:.2f} (entry=${entry_price:.2f})")
                
                if rr_ratio >= MIN_RR_RATIO:
                    fvg_strength = fvg.get('volume_strength', 'medium')
                    balance = Config.DEFAULT_BALANCE
                    setup_strength = calculate_setup_strength(
                        volume_spike_ratio=volume['spike_ratio'],
                        ob_or_fvg_strength=fvg_strength,
                        rr_ratio=rr_ratio,
                        confidence='MEDIUM'
                    )
                    risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
                    risk_usd = (balance * risk_percent) / 100
                    
                    detailed_explanation = f"""
📊 **FVG Analizi:**
• Bearish FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}
• Gap size: ${fvg['gap_size']:,.2f}
• Volume spike: {volume['spike_ratio']:.1f}x
• Timeframe: {timeframe.upper()}

🎯 **Entry:** {entry_zone} | Risk: {risk_percent:.1f}% (${risk_usd:,.0f})

📉 **TP/Stop:**
• ATR: ${atr:,.2f} | Stop: {stop_loss} | TP1: {tp1} | TP2: {tp2}
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                    
                    setups.append({
                        'type': 'FVG + Volume Spike (SHORT)',
                        'confidence': 'MEDIUM',
                        'timeframe': timeframe,
                        'entry_zone': entry_zone,
                        'stop_loss': stop_loss,
                        'tp1': tp1,
                        'tp2': tp2,
                        'current_price': current_price,
                        'entry_price': entry_price,
                        'stop_price': stop_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'volume_spike_ratio': volume['spike_ratio'],
                        'fvg_strength': fvg_strength,
                        'rr_ratio': rr_ratio,
                        'detailed_explanation': detailed_explanation,
                        'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                    })
        
        return setups
        
    except Exception as e:
        logger.error(f"Error checking {timeframe} setups: {e}")
        return []


def detect_all_trading_setups(pair, market_data):
    """
    TÜM timeframe'leri tara, R:R >= 2.0 olan TÜM setup'ları döndür
    """
    try:
        pdc = market_data['previous_day']
        bias = 'bullish' if pdc['candle_type'] == 'green' else 'bearish'
        current_price = market_data['current_price']
        
        TIMEFRAMES = ['4h', '1h', '15m', '5m', '3m']
        all_setups = []
        
        logger.info(f"🔍 {pair}: Scanning {len(TIMEFRAMES)} timeframes (bias: {bias})")
        
        for timeframe in TIMEFRAMES:
            setups_in_tf = check_timeframe_for_setups(pair, market_data, timeframe, bias, current_price)
            if setups_in_tf:
                logger.info(f"✅ {pair} {timeframe.upper()}: {len(setups_in_tf)} setup(s) found")
                all_setups.extend(setups_in_tf)
            else:
                logger.info(f"ℹ️ {pair} {timeframe.upper()}: No setup")
        
        logger.info(f"📊 {pair}: Total {len(all_setups)} setup(s) found across all timeframes")
        return all_setups
        
    except Exception as e:
        logger.error(f"❌ Multi-timeframe detection error for {pair}: {e}")
        return []
