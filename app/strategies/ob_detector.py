# -*- coding: utf-8 -*-
"""
T-TARS OB Detector v2.1.0
=========================
Order Block setup detection (Scanning + Validation)

v2.1.0:
- FIX: Entry hesabı düzeltildi → (OB_Low + OB_High) / 2
- FIX: Stop hesabı düzeltildi → Entry ± ATR (OB'den değil, Entry'den)
- FIX: scan_order_blocks key'leri tutarlı hale getirildi (high/low)
- FIX: timestamp field eklendi (tracking_service uyumu)
- REMOVE: STOP_MULTIPLIER kullanımı kaldırıldı (direkt ATR)

Formül (Kadircan):
LONG:  Entry = (OB_H + OB_L) / 2, Stop = Entry - ATR, TP1 = Entry + 2*ATR, TP2 = Entry + 4*ATR
SHORT: Entry = (OB_H + OB_L) / 2, Stop = Entry + ATR, TP1 = Entry - 2*ATR, TP2 = Entry - 4*ATR
"""

import logging
import datetime
from app.config import Config
from app.strategies.calculators import (
    calculate_setup_strength,
    format_price,
    MIN_RR_RATIO,
    TP1_MULTIPLIER,
    TP2_MULTIPLIER
)
from app.strategies.volume_analyzer import analyze_volume

logger = logging.getLogger(__name__)

# Volume threshold - 0.5x ve üzeri kabul edilir
VOLUME_THRESHOLD = 0.5


# --- SCANNING LOGIC (GÖZLER) ---
def scan_order_blocks(ohlcv, timeframe_str):
    """
    Mum verilerini tarayarak potansiyel Order Block'ları bulur.
    """
    obs = []
    try:
        if len(ohlcv) < 5:
            logger.debug(f"OB Scan [{timeframe_str}]: Yetersiz mum ({len(ohlcv)})")
            return []
        
        # Son 50 muma bakmak yeterli
        lookback_data = ohlcv[-50:]
        
        # Mum yapısı: [timestamp, open, high, low, close, volume]
        for i in range(2, len(lookback_data)-1):
            prev = lookback_data[i-1]
            curr = lookback_data[i]
            next_candle = lookback_data[i+1]
            
            # Bullish OB: Kırmızı mum, ardından gelen yeşil mum önceki kırmızının High'ını kırarsa
            if curr[4] < curr[1]:  # Kırmızı (Düşüş)
                if next_candle[4] > curr[2]:  # Sonraki mum, kırmızının tepesini geçti
                    obs.append({
                        'type': 'bullish',
                        'high': curr[2],   # OB High (mumun high'ı)
                        'low': curr[3],    # OB Low (mumun low'u)
                        'strength': 'high',
                        'volume_confirmed': True
                    })

            # Bearish OB: Yeşil mum, ardından gelen kırmızı mum önceki yeşilin Low'unu kırarsa
            elif curr[4] > curr[1]:  # Yeşil (Yükseliş)
                if next_candle[4] < curr[3]:  # Sonraki mum, yeşilin dibini kırdı
                    obs.append({
                        'type': 'bearish',
                        'high': curr[2],   # OB High (mumun high'ı)
                        'low': curr[3],    # OB Low (mumun low'u)
                        'strength': 'high',
                        'volume_confirmed': True
                    })
        
        if obs:
            logger.debug(f"📦 OB Scan [{timeframe_str}]: {len(obs)} OB bulundu")
        
        return obs[-5:]  # Son 5 OB'yi döndür
        
    except Exception as e:
        logger.error(f"❌ OB Scan Error [{timeframe_str}]: {e}")
        return []


# --- VALIDATION LOGIC (BEYİN) ---
def detect_ob_long(ob, volume, atr, timeframe, current_price, pair=""):
    """Bullish Order Block setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        # Volume kontrolü (threshold: 0.5x)
        if not volume.get('spike', False) and vol_ratio < VOLUME_THRESHOLD:
            logger.info(f"{coin} OB LONG rejected: Low Volume ({vol_ratio}x < {VOLUME_THRESHOLD}x)")
            return None
        
        # v2.1.0 FIX: Doğru formül
        # Entry = OB mid-point
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        # Stop = Entry - ATR (1R risk)
        stop_price = entry_price - atr
        stop_loss = format_price(stop_price)
        
        # TP1 = Entry + 2*ATR (2R), TP2 = Entry + 4*ATR (4R)
        tp1_price = entry_price + (atr * TP1_MULTIPLIER)
        tp2_price = entry_price + (atr * TP2_MULTIPLIER)
        
        # R:R hesabı
        risk = abs(entry_price - stop_price)  # = ATR
        reward = abs(tp1_price - entry_price)  # = 2*ATR
        rr_ratio = reward / risk if risk > 0 else 0  # = 2.0
        
        # R:R kontrolü
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"{coin} OB LONG rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # Setup Strength Hesapla
        setup_strength = calculate_setup_strength(
            volume_spike_ratio=vol_ratio,
            ob_or_fvg_strength=ob.get('strength', 'medium'),
            rr_ratio=rr_ratio,
            confidence='HIGH'
        )
        balance = Config.DEFAULT_BALANCE
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100
        
        detailed_explanation = f"""
📊 **OB Analizi (LONG):**
• Zone: {entry_zone}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.2f}x

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {stop_loss}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Risk: ${risk_usd:.1f}
"""
        
        logger.info(f"✅ {coin} OB LONG VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.2f}x")
        
        return {
            'type': 'OB + Volume (LONG)',
            'direction': 'LONG',
            'timeframe': timeframe,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'rr_ratio': rr_ratio,
            'confidence': 'HIGH',
            'entry_zone': entry_zone,
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB LONG error ({pair}): {e}")
        return None


def detect_ob_short(ob, volume, atr, timeframe, current_price, pair=""):
    """Bearish Order Block setup onayı"""
    try:
        coin = pair.replace('/USDT:USDT', '').replace('/USDT', '') if pair else "?"
        vol_ratio = volume.get('spike_ratio', 0)
        
        # Volume kontrolü (threshold: 0.5x)
        if not volume.get('spike', False) and vol_ratio < VOLUME_THRESHOLD:
            logger.info(f"{coin} OB SHORT rejected: Low Volume ({vol_ratio}x < {VOLUME_THRESHOLD}x)")
            return None
        
        # v2.1.0 FIX: Doğru formül
        # Entry = OB mid-point
        entry_price = (ob['low'] + ob['high']) / 2
        entry_zone = f"{format_price(ob['low'])} - {format_price(ob['high'])}"
        
        # Stop = Entry + ATR (1R risk)
        stop_price = entry_price + atr
        stop_loss = format_price(stop_price)
        
        # TP1 = Entry - 2*ATR (2R), TP2 = Entry - 4*ATR (4R)
        tp1_price = entry_price - (atr * TP1_MULTIPLIER)
        tp2_price = entry_price - (atr * TP2_MULTIPLIER)
        
        # R:R hesabı
        risk = abs(stop_price - entry_price)  # = ATR
        reward = abs(entry_price - tp1_price)  # = 2*ATR
        rr_ratio = reward / risk if risk > 0 else 0  # = 2.0
        
        # R:R kontrolü
        if rr_ratio < MIN_RR_RATIO:
            logger.info(f"{coin} OB SHORT rejected: Low R:R ({rr_ratio:.2f} < {MIN_RR_RATIO})")
            return None
        
        # Setup Strength Hesapla
        setup_strength = calculate_setup_strength(
            volume_spike_ratio=vol_ratio,
            ob_or_fvg_strength=ob.get('strength', 'medium'),
            rr_ratio=rr_ratio,
            confidence='HIGH'
        )
        balance = Config.DEFAULT_BALANCE
        risk_percent = Config.RISK_PER_TRADE_MIN + (setup_strength * (Config.RISK_PER_TRADE_MAX - Config.RISK_PER_TRADE_MIN))
        risk_usd = (balance * risk_percent) / 100
        
        detailed_explanation = f"""
📊 **OB Analizi (SHORT):**
• Zone: {entry_zone}
• TF: {timeframe.upper()} | Vol: {vol_ratio:.2f}x

🎯 **Trade:**
• Entry: {format_price(entry_price)}
• Stop: {stop_loss}
• TP1: {format_price(tp1_price)} | TP2: {format_price(tp2_price)}
• R:R: {rr_ratio:.2f} | Risk: ${risk_usd:.1f}
"""
        
        logger.info(f"✅ {coin} OB SHORT VALID: R:R={rr_ratio:.2f}, Vol={vol_ratio:.2f}x")
        
        return {
            'type': 'OB + Volume (SHORT)',
            'direction': 'SHORT',
            'timeframe': timeframe,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'entry_price': entry_price,
            'stop_price': stop_price,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'rr_ratio': rr_ratio,
            'confidence': 'HIGH',
            'entry_zone': entry_zone,
            'tp1': format_price(tp1_price),
            'tp2': format_price(tp2_price),
            'detailed_explanation': detailed_explanation
        }
        
    except Exception as e:
        logger.error(f"❌ OB SHORT error ({pair}): {e}")
        return None
