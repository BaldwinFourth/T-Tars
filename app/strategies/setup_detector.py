# -*- coding: utf-8 -*-
"""
T-TARS Setup Detector v1.4.5
============================
Trading setup tespit fonksiyonları.
OB, FVG, Volume Spike detection ve multi-timeframe scan.

Kullanım:
    from app.strategies.setup_detector import (
        detect_trading_setup,
        detect_all_trading_setups,
        check_timeframe_for_setups
    )
"""

import logging
from app.config import Config
from app.strategies.calculators import calculate_setup_strength, MIN_RR_RATIO

logger = logging.getLogger(__name__)


def detect_trading_setup(pair, market_data):
    """Trading setup tespit et + Entry/Stop/TP hesapla (v1.4.3: timeframe return eklendi)"""
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
        
        # DEBUG LOG
        logger.info(f"🔍 Setup check {pair}: volume_spike={has_volume_spike} ({volume['spike_ratio']:.1f}x), OB={has_order_block} ({len(obs)}), FVG={has_fvg} ({len(fvgs)}), bias={bias}, TF={timeframe}")
        
        atr_15m = market_data['atr']['15m']
        atr_5m = market_data['atr']['5m']
        atr_3m = market_data['atr']['3m']
        
        if has_order_block and has_volume_spike:
            ob = obs[0]
            
            if bias == 'bullish' and ob['type'] == 'bullish':
                entry_zone = f"${ob['low']:,.2f} - ${ob['price']:,.2f}"
                
                # ATR selection based on timeframe
                atr = atr_5m if timeframe == '5m' else atr_3m
                stop_distance = atr * 1.5
                stop_price = ob['low'] - stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                # Dual TP System
                tp1_price = current_price + (atr * 2.0)
                tp2_price = current_price + (atr * 3.5)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                # R:R Ratio (for TP1)
                risk = abs(current_price - stop_price)
                reward = abs(tp1_price - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                # Debug log
                logger.info(f"📊 LONG R:R: entry=${current_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1_price:.2f}, tp2=${tp2_price:.2f}, risk=${risk:.2f}, reward=${reward:.2f}, ratio={rr_ratio:.2f}")
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"LONG setup rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
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

💭 **AI:** _"OB seviyesi güçlü, önceki reaksiyonda belirgin hareket var. Volume spike güvenilir."_

🎯 **Entry Stratejisi:**
• Wait for pullback to OB zone
• Entry: {entry_zone}
• Risk: {risk_percent:.1f}% of balance (${risk_usd:,.0f} per position)

💭 **AI:** _"Pullback beklemek risk/reward oranını iyileştirir. Sabır kritik."_

📈 **TP/Stop Analizi:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: Below OB - 1.5 ATR = {stop_loss}
• TP1: +2.0 ATR = {tp1} (R:R 1:{rr_ratio:.1f})
• TP2: +3.5 ATR = {tp2} (Extended target)

⚡ **Volume Konfirmasyon:**
• Trend: {volume['trend'].upper()}
• Current/Avg: {volume['spike_ratio']:.1f}x
"""
                
                return {
                    'type': 'OB + Volume Spike (LONG)',
                    'confidence': 'HIGH',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    # Tracking fields
                    'current_price': current_price,
                    'stop_price': stop_price,
                    'tp1_price': tp1_price,
                    'tp2_price': tp2_price,
                    'volume_spike_ratio': volume['spike_ratio'],
                    'ob_strength': ob['strength'],
                    'rr_ratio': rr_ratio,
                    'detailed_explanation': detailed_explanation,
                    'details': f"Bullish OB @ ${ob['low']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                }
            
            elif bias == 'bearish' and ob['type'] == 'bearish':
                entry_zone = f"${ob['high']:,.2f} - ${ob['price']:,.2f}"
                
                # ATR selection based on timeframe
                atr = atr_5m if timeframe == '5m' else atr_3m
                stop_distance = atr * 1.5
                stop_price = ob['high'] + stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                # Dual TP System
                tp1_price = current_price - (atr * 2.0)
                tp2_price = current_price - (atr * 3.5)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                # R:R Ratio (for TP1)
                risk = abs(stop_price - current_price)
                reward = abs(current_price - tp1_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                # Debug log
                logger.info(f"📊 SHORT R:R: entry=${current_price:.2f}, stop=${stop_price:.2f}, tp1=${tp1_price:.2f}, tp2=${tp2_price:.2f}, risk=${risk:.2f}, reward=${reward:.2f}, ratio={rr_ratio:.2f}")
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"SHORT setup rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
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

💭 **AI:** _"Bearish OB seviyesi net, geçmişte rejection görmüş. Volume confirmation var."_

🎯 **Entry Stratejisi:**
• Wait for bounce to OB zone
• Entry: {entry_zone}
• Risk: {risk_percent:.1f}% of balance (${risk_usd:,.0f} per position)

💭 **AI:** _"Bounce bekle, aggressive entry riskli. Sweet zone'da sabır göster."_

📉 **TP/Stop Analizi:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: Above OB + 1.5 ATR = {stop_loss}
• TP1: -2.0 ATR = {tp1} (R:R 1:{rr_ratio:.1f})
• TP2: -3.5 ATR = {tp2} (Extended target)

⚡ **Volume Konfirmasyon:**
• Trend: {volume['trend'].upper()}
• Current/Avg: {volume['spike_ratio']:.1f}x
"""
                
                return {
                    'type': 'OB + Volume Spike (SHORT)',
                    'confidence': 'HIGH',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    # Tracking fields
                    'current_price': current_price,
                    'stop_price': stop_price,
                    'tp1_price': tp1_price,
                    'tp2_price': tp2_price,
                    'volume_spike_ratio': volume['spike_ratio'],
                    'ob_strength': ob['strength'],
                    'rr_ratio': rr_ratio,
                    'detailed_explanation': detailed_explanation,
                    'details': f"Bearish OB @ ${ob['high']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                }
        
        if has_fvg and has_volume_spike:
            fvg = fvgs[0]
            
            if bias == 'bullish' and fvg['type'] == 'bullish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                stop_distance = atr_5m * 1.5
                stop_loss_price = fvg['gap_low'] - stop_distance
                stop_loss = f"${stop_loss_price:,.2f}"
                tp = current_price + (atr_15m * 2)
                take_profit = f"${tp:,.2f}"
                
                risk = abs(current_price - stop_loss_price)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"FVG LONG setup rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
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

💭 **AI:** _"FVG dolumu beklenmeli. Volume confirmation var, R:R 1:{rr_ratio:.1f} solid."_

🎯 **Entry:**
• Wait for FVG fill
• Entry: {entry_zone}
• Risk: {risk_percent:.1f}% of balance (${risk_usd:,.0f})
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                
                return {
                    'type': f'FVG + Volume Spike (LONG)',
                    'confidence': 'MEDIUM',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'detailed_explanation': detailed_explanation,
                    'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                }
            
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                stop_distance = atr_5m * 1.5
                stop_loss_price = fvg['gap_high'] + stop_distance
                stop_loss = f"${stop_loss_price:,.2f}"
                tp = current_price - (atr_15m * 2)
                take_profit = f"${tp:,.2f}"
                
                risk = abs(stop_loss_price - current_price)
                reward = abs(current_price - tp)
                rr_ratio = reward / risk if risk > 0 else 0
                
                if rr_ratio < MIN_RR_RATIO:
                    logger.info(f"FVG SHORT setup rejected: R:R {rr_ratio:.1f} < {MIN_RR_RATIO}")
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

💭 **AI:** _"FVG fill zone kritik. Volume spike var, SHORT bias ile uyumlu. R:R 1:{rr_ratio:.1f}."_

🎯 **Entry:**
• Wait for FVG fill
• Entry: {entry_zone}
• Risk: {risk_percent:.1f}% of balance (${risk_usd:,.0f})
• R:R Ratio: 1:{rr_ratio:.1f}
"""
                
                return {
                    'type': f'FVG + Volume Spike (SHORT)',
                    'confidence': 'MEDIUM',
                    'timeframe': timeframe,
                    'entry_zone': entry_zone,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
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
    
    Args:
        pair: Trading pair
        market_data: Market data dict
        timeframe: '4h', '1h', '15m', '5m', '3m'
        bias: 'bullish' or 'bearish'
        current_price: Current market price
    
    Returns:
        list: Setup'lar (boş liste veya 1-2 setup)
    """
    setups = []
    
    try:
        # Data çek
        volume = market_data['volume'].get(timeframe, {})
        obs = market_data['smart_money']['order_blocks'].get(timeframe, [])
        fvgs = market_data['smart_money']['fair_value_gaps'].get(timeframe, [])
        
        # ATR mapping
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
        
        # OB Setup Check
        if len(obs) > 0:
            ob = obs[0]
            
            if bias == 'bullish' and ob['type'] == 'bullish':
                entry_zone = f"${ob['low']:,.2f} - ${ob['price']:,.2f}"
                stop_distance = atr * 1.5
                stop_price = ob['low'] - stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                # Dual TP System
                tp1_price = current_price + (atr * 2.0)
                tp2_price = current_price + (atr * 3.5)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                # R:R Ratio
                risk = abs(current_price - stop_price)
                reward = abs(tp1_price - current_price)
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

💭 **AI:** _"OB seviyesi güçlü, önceki reaksiyonda belirgin hareket var. Volume spike güvenilir."_

🎯 **Entry Stratejisi:**
• Wait for pullback to OB zone
• Entry: {entry_zone}
• Risk: {risk_percent:.1f}% of balance (${risk_usd:,.0f} per position)

💭 **AI:** _"Pullback beklemek risk/reward oranını iyileştirir. Sabır kritik."_

📈 **TP/Stop Analizi:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: Below OB - 1.5 ATR = {stop_loss}
• TP1: +2.0 ATR = {tp1} (R:R 1:{rr_ratio:.1f})
• TP2: +3.5 ATR = {tp2} (Extended target)

⚡ **Volume Konfirmasyon:**
• Trend: {volume['trend'].upper()}
• Current/Avg: {volume['spike_ratio']:.1f}x
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
                        'stop_price': stop_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'volume_spike_ratio': volume['spike_ratio'],
                        'ob_strength': ob['strength'],
                        'rr_ratio': rr_ratio,
                        'detailed_explanation': detailed_explanation,
                        'details': f"Bullish OB @ ${ob['low']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                    })
            
            elif bias == 'bearish' and ob['type'] == 'bearish':
                entry_zone = f"${ob['high']:,.2f} - ${ob['price']:,.2f}"
                stop_distance = atr * 1.5
                stop_price = ob['high'] + stop_distance
                stop_loss = f"${stop_price:,.2f}"
                
                # Dual TP System
                tp1_price = current_price - (atr * 2.0)
                tp2_price = current_price - (atr * 3.5)
                tp1 = f"${tp1_price:,.2f}"
                tp2 = f"${tp2_price:,.2f}"
                
                # R:R Ratio
                risk = abs(stop_price - current_price)
                reward = abs(current_price - tp1_price)
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

💭 **AI:** _"Bearish OB seviyesi net, geçmişte rejection görmüş. Volume confirmation var."_

🎯 **Entry Stratejisi:**
• Wait for bounce to OB zone
• Entry: {entry_zone}
• Risk: {risk_percent:.1f}% of balance (${risk_usd:,.0f} per position)

💭 **AI:** _"Bounce bekle, aggressive entry riskli. Sweet zone'da sabır göster."_

📉 **TP/Stop Analizi:**
• ATR({timeframe}): ${atr:,.2f}
• Stop: Above OB + 1.5 ATR = {stop_loss}
• TP1: -2.0 ATR = {tp1} (R:R 1:{rr_ratio:.1f})
• TP2: -3.5 ATR = {tp2} (Extended target)

⚡ **Volume Konfirmasyon:**
• Trend: {volume['trend'].upper()}
• Current/Avg: {volume['spike_ratio']:.1f}x
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
                        'stop_price': stop_price,
                        'tp1_price': tp1_price,
                        'tp2_price': tp2_price,
                        'volume_spike_ratio': volume['spike_ratio'],
                        'ob_strength': ob['strength'],
                        'rr_ratio': rr_ratio,
                        'detailed_explanation': detailed_explanation,
                        'details': f"Bearish OB @ ${ob['high']:,.2f}\nVolume: {volume['spike_ratio']}x spike"
                    })
        
        # FVG Setup Check
        if len(fvgs) > 0:
            fvg = fvgs[0]
            
            if bias == 'bullish' and fvg['type'] == 'bullish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                stop_distance = atr * 1.5
                stop_loss_price = fvg['gap_low'] - stop_distance
                stop_loss = f"${stop_loss_price:,.2f}"
                tp = current_price + (atr * 2)
                take_profit = f"${tp:,.2f}"
                
                risk = abs(current_price - stop_loss_price)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 {pair} {timeframe.upper()} LONG FVG R:R: {rr_ratio:.2f}")
                
                if rr_ratio >= MIN_RR_RATIO:
                    setups.append({
                        'type': f'FVG + Volume Spike (LONG)',
                        'confidence': 'MEDIUM',
                        'timeframe': timeframe,
                        'entry_zone': entry_zone,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'detailed_explanation': f"Bullish FVG @ {timeframe.upper()}, R:R {rr_ratio:.1f}",
                        'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                    })
            
            elif bias == 'bearish' and fvg['type'] == 'bearish':
                entry_zone = f"${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}"
                stop_distance = atr * 1.5
                stop_loss_price = fvg['gap_high'] + stop_distance
                stop_loss = f"${stop_loss_price:,.2f}"
                tp = current_price - (atr * 2)
                take_profit = f"${tp:,.2f}"
                
                risk = abs(stop_loss_price - current_price)
                reward = abs(current_price - tp)
                rr_ratio = reward / risk if risk > 0 else 0
                
                logger.info(f"📊 {pair} {timeframe.upper()} SHORT FVG R:R: {rr_ratio:.2f}")
                
                if rr_ratio >= MIN_RR_RATIO:
                    setups.append({
                        'type': f'FVG + Volume Spike (SHORT)',
                        'confidence': 'MEDIUM',
                        'timeframe': timeframe,
                        'entry_zone': entry_zone,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'detailed_explanation': f"Bearish FVG @ {timeframe.upper()}, R:R {rr_ratio:.1f}",
                        'details': f"FVG: ${fvg['gap_low']:,.2f} - ${fvg['gap_high']:,.2f}\nVolume: {volume['spike_ratio']}x"
                    })
        
        return setups
        
    except Exception as e:
        logger.error(f"Error checking {timeframe} setups: {e}")
        return []


def detect_all_trading_setups(pair, market_data):
    """
    TÜM timeframe'leri tara, R:R >= 2.0 olan TÜM setup'ları döndür
    v1.4.3: Multi-timeframe scan
    
    Returns:
        list: Setup'lar (boş liste veya N setup)
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
