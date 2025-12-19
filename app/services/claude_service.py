# -*- coding: utf-8 -*-
"""
T-TARS Claude Service v2.3.8
============================
Claude AI API wrapper for market analysis and setup evaluation.

v2.3.8:
- CHANGED: Volume threshold'lar calculators.py'den import ediliyor (DRY)
- CHANGED: MIN_RR_RATIO calculators.py'den import ediliyor (DRY)
- Prompt'taki hardcoded değerler kaldırıldı

v2.3.4:
- FIX: adjust_stop_and_tp() artık TP2'yi de hesaplıyor
- FIX: ATR=0 kontrolü eklendi (ATR yoksa SKIP)
- FIX: TP2 = TP1 * 2 formülü (R:R korunuyor)
- LONG/SHORT için doğru TP2 hesaplaması

v2.3.2:
- Otomatik Stop Adjustment sistemi
- Stop < 0.8% → %0.8'e çek, TP orantılı uzat
- Stop >= 2.5% → SKIP

v2.3.1:
- R:R floating point hatası düzeltildi
- Hardcoded değerler KALDIRILDI
"""

from anthropic import Anthropic
from app.config import Config
# v2.3.8: Threshold'ları calculators'tan al (DRY)
from app.strategies.calculators import (
    VOLUME_TRADEABLE_MIN,
    VOLUME_LOW,
    VOLUME_GOOD,
    VOLUME_EXCELLENT,
    MIN_RR_RATIO
)
from app.config import Config
import logging
import json
import re

logger = logging.getLogger(__name__)


def format_price_display(price):
    """Log/mesaj için okunabilir fiyat formatı"""
    if price is None or price == 0:
        return "$0.00"
    if price < 0.0001:
        return f"${price:.8f}"
    elif price < 1:
        return f"${price:.6f}"
    elif price < 100:
        return f"${price:.4f}"
    else:
        return f"${price:,.2f}"


class ClaudeService:
    """Claude Haiku 4.5 API Service - v2.3.8 (AI Decision Engine + Stop/TP Adjustment)"""
    
    # Timeframe mapping: Türkçe → API format
    TF_MAP = {
        '5d': '5m', '5m': '5m',
        '15d': '15m', '15m': '15m',
        '30d': '30m', '30m': '30m',
        '1s': '1h', '1h': '1h',
        '4s': '4h', '4h': '4h',
        '1g': '1d', '1d': '1d',
        '3d': '3m', '3m': '3m'
    }
    
    # v2.3.8: Stop Adjustment Sabitleri - Config'den türetiliyor (DRY)
    # Config.STOP_DISTANCE_MIN = 0.008 → %0.8
    # Config.STOP_DISTANCE_MAX = 0.025 → %2.5
    STOP_IDEAL_MAX = 1.5    # İdeal maksimum (ara değer)
    STOP_AGGRESSIVE_TARGET = 1.8  # 2-2.5% arası için hedef
    AGGRESSIVE_RR = 3.0     # 2-2.5% arası için R:R
    
    # v2.3.4: TP Multipliers
    TP1_RR = 2.0  # TP1 = 2R
    TP2_RR = 4.0  # TP2 = 4R
    
    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
        # v2.3.8: Stop thresholds Config'den türetiliyor (DRY)
        self.STOP_MIN_PCT = Config.STOP_DISTANCE_MIN * 100      # 0.008 → 0.8
        self.STOP_ADJUST_MAX = Config.STOP_DISTANCE_MAX * 100   # 0.025 → 2.5
        
        logger.info(f"✅ Claude Service v2.3.8 initialized: {Config.CLAUDE_MODEL} | "
                   f"Stop: {self.STOP_MIN_PCT}%-{self.STOP_ADJUST_MAX}%")
    
    def analyze(self, prompt):
        """
        Genel analiz yap (eski fonksiyon - backward compat)
        """
        try:
            response = self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
            
            result = {
                "text": text_content,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
            
            logger.info(f"Analysis complete: {result['input_tokens']}→{result['output_tokens']} tokens")
            return result
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
    
    def adjust_stop_and_tp(self, entry_price, stop_price, tp1_price, tp2_price, direction):
        """
        v2.3.4: Otomatik Stop/TP Adjustment (TP2 dahil!)
        
        Kurallar:
        1. Stop < 0.8% → %0.8'e çek, TP orantılı uzat
        2. Stop 0.8-1.5% → Değişiklik yok (ideal)
        3. Stop 1.5-2% → %1.5'e çek, TP orantılı kısalt
        4. Stop 2-2.5% → %1.8'e çek, TP 3R yap
        5. Stop >= 2.5% → None döndür (SKIP)
        
        v2.3.4 FIX: TP2 de hesaplanıyor (TP2 = TP1 * 2 oranı korunuyor)
        
        Returns:
            dict: {'stop_price', 'tp1_price', 'tp2_price', 'adjusted', 'adjustment_type', ...}
            None: SKIP gerekiyorsa
        """
        entry = float(entry_price)
        stop = float(stop_price)
        tp1 = float(tp1_price)
        tp2 = float(tp2_price) if tp2_price else tp1 * 2  # Fallback
        
        # Direction normalize
        is_long = direction.upper() == 'LONG'
        
        # Orijinal stop mesafesi
        stop_distance = abs(entry - stop)
        stop_pct = (stop_distance / entry) * 100 if entry > 0 else 0
        
        # Orijinal TP mesafeleri
        tp1_distance = abs(tp1 - entry)
        tp2_distance = abs(tp2 - entry)
        
        # Orijinal R:R
        original_rr = tp1_distance / stop_distance if stop_distance > 0 else 0
        
        # TP2/TP1 oranı (genellikle 2.0)
        tp2_tp1_ratio = tp2_distance / tp1_distance if tp1_distance > 0 else 2.0
        
        result = {
            'stop_price': stop,
            'tp1_price': tp1,
            'tp2_price': tp2,
            'adjusted': False,
            'adjustment_type': None,
            'original_stop_pct': round(stop_pct, 2),
            'new_stop_pct': round(stop_pct, 2),
            'original_rr': round(original_rr, 2),
            'new_rr': round(original_rr, 2)
        }
        
        # ============================================
        # KURAL 5: Stop >= 2.5% → SKIP
        # ============================================
        if stop_pct >= self.STOP_ADJUST_MAX:
            logger.info(f"🚫 Stop Adjustment: %{stop_pct:.2f} >= %{self.STOP_ADJUST_MAX} → SKIP gerekli")
            return None
        
        # ============================================
        # KURAL 2: Stop 0.8-1.5% → İdeal, değişiklik yok
        # ============================================
        if self.STOP_MIN_PCT <= stop_pct <= self.STOP_IDEAL_MAX:
            logger.debug(f"✅ Stop ideal aralıkta: %{stop_pct:.2f}")
            return result
        
        # ============================================
        # KURAL 1: Stop < 0.8% → %0.8'e çek, TP orantılı uzat
        # ============================================
        if stop_pct < self.STOP_MIN_PCT:
            # Genişletme oranı
            expansion_ratio = self.STOP_MIN_PCT / stop_pct if stop_pct > 0 else 1.0
            
            # Yeni stop mesafesi
            new_stop_distance = entry * (self.STOP_MIN_PCT / 100)
            
            # Yeni TP mesafeleri (aynı R:R'ı korumak için orantılı)
            new_tp1_distance = tp1_distance * expansion_ratio
            new_tp2_distance = new_tp1_distance * tp2_tp1_ratio
            
            # Yeni fiyatlar - LONG/SHORT ayrımı
            if is_long:
                new_stop = entry - new_stop_distance
                new_tp1 = entry + new_tp1_distance
                new_tp2 = entry + new_tp2_distance
            else:  # SHORT
                new_stop = entry + new_stop_distance
                new_tp1 = entry - new_tp1_distance
                new_tp2 = entry - new_tp2_distance
            
            new_rr = new_tp1_distance / new_stop_distance if new_stop_distance > 0 else original_rr
            
            result['stop_price'] = round(new_stop, 8)
            result['tp1_price'] = round(new_tp1, 8)
            result['tp2_price'] = round(new_tp2, 8)
            result['adjusted'] = True
            result['adjustment_type'] = 'EXPAND'
            result['new_stop_pct'] = self.STOP_MIN_PCT
            result['new_rr'] = round(new_rr, 2)
            
            logger.info(f"📐 Stop EXPAND ({direction}): %{stop_pct:.2f} → %{self.STOP_MIN_PCT} | "
                       f"Stop: {format_price_display(stop)} → {format_price_display(new_stop)} | "
                       f"TP1: {format_price_display(tp1)} → {format_price_display(new_tp1)} | "
                       f"TP2: {format_price_display(tp2)} → {format_price_display(new_tp2)} | "
                       f"R:R: {original_rr:.2f} → {new_rr:.2f}")
            
            return result
        
        # ============================================
        # KURAL 3: Stop 1.5-2% → %1.5'e çek, TP orantılı kısalt
        # ============================================
        if self.STOP_IDEAL_MAX < stop_pct < 2.0:
            # Kısaltma oranı
            shrink_ratio = self.STOP_IDEAL_MAX / stop_pct
            
            # Yeni stop mesafesi
            new_stop_distance = entry * (self.STOP_IDEAL_MAX / 100)
            
            # Yeni TP mesafeleri (aynı R:R'ı korumak için orantılı)
            new_tp1_distance = tp1_distance * shrink_ratio
            new_tp2_distance = new_tp1_distance * tp2_tp1_ratio
            
            # Yeni fiyatlar - LONG/SHORT ayrımı
            if is_long:
                new_stop = entry - new_stop_distance
                new_tp1 = entry + new_tp1_distance
                new_tp2 = entry + new_tp2_distance
            else:  # SHORT
                new_stop = entry + new_stop_distance
                new_tp1 = entry - new_tp1_distance
                new_tp2 = entry - new_tp2_distance
            
            new_rr = new_tp1_distance / new_stop_distance if new_stop_distance > 0 else original_rr
            
            result['stop_price'] = round(new_stop, 8)
            result['tp1_price'] = round(new_tp1, 8)
            result['tp2_price'] = round(new_tp2, 8)
            result['adjusted'] = True
            result['adjustment_type'] = 'SHRINK'
            result['new_stop_pct'] = self.STOP_IDEAL_MAX
            result['new_rr'] = round(new_rr, 2)
            
            logger.info(f"📐 Stop SHRINK ({direction}): %{stop_pct:.2f} → %{self.STOP_IDEAL_MAX} | "
                       f"Stop: {format_price_display(stop)} → {format_price_display(new_stop)} | "
                       f"TP1: {format_price_display(tp1)} → {format_price_display(new_tp1)} | "
                       f"TP2: {format_price_display(tp2)} → {format_price_display(new_tp2)} | "
                       f"R:R: {original_rr:.2f} → {new_rr:.2f}")
            
            return result
        
        # ============================================
        # KURAL 4: Stop 2-2.5% → %1.8'e çek, TP 3R yap
        # ============================================
        if 2.0 <= stop_pct < self.STOP_ADJUST_MAX:
            # Yeni stop mesafesi: %1.8
            new_stop_distance = entry * (self.STOP_AGGRESSIVE_TARGET / 100)
            
            # Yeni TP mesafeleri: 3R ve 6R (veya orijinal oran)
            new_tp1_distance = new_stop_distance * self.AGGRESSIVE_RR
            new_tp2_distance = new_tp1_distance * tp2_tp1_ratio
            
            # Yeni fiyatlar - LONG/SHORT ayrımı
            if is_long:
                new_stop = entry - new_stop_distance
                new_tp1 = entry + new_tp1_distance
                new_tp2 = entry + new_tp2_distance
            else:  # SHORT
                new_stop = entry + new_stop_distance
                new_tp1 = entry - new_tp1_distance
                new_tp2 = entry - new_tp2_distance
            
            result['stop_price'] = round(new_stop, 8)
            result['tp1_price'] = round(new_tp1, 8)
            result['tp2_price'] = round(new_tp2, 8)
            result['adjusted'] = True
            result['adjustment_type'] = 'AGGRESSIVE'
            result['new_stop_pct'] = self.STOP_AGGRESSIVE_TARGET
            result['new_rr'] = self.AGGRESSIVE_RR
            
            logger.info(f"📐 Stop AGGRESSIVE ({direction}): %{stop_pct:.2f} → %{self.STOP_AGGRESSIVE_TARGET} | "
                       f"Stop: {format_price_display(stop)} → {format_price_display(new_stop)} | "
                       f"TP1: {format_price_display(tp1)} → {format_price_display(new_tp1)} | "
                       f"TP2: {format_price_display(tp2)} → {format_price_display(new_tp2)} | "
                       f"R:R: {original_rr:.2f} → {self.AGGRESSIVE_RR}")
            
            return result
        
        # Buraya gelmemeli ama güvenlik için
        return result
    
    def evaluate_setup(self, setup_data, market_data, python_score):
        """
        v2.3.2: AI Setup Değerlendirmesi - Stop Adjustment + "Neyse O" Modeli
        
        Kritik veri eksikse → LOG + SKIP (hardcoded default YOK!)
        
        Returns:
            {
                'action': 'ENTER' | 'SKIP' | 'WAIT',
                'confidence': 0-100,
                'reasoning': 'Neden bu karar?',
                'adjustments': {}
            }
        """
        try:
            # ============================================
            # DEBUG: Gelen veriyi logla
            # ============================================
            logger.debug(f"📥 setup_data keys: {list(setup_data.keys())}")
            logger.debug(f"📥 market_data keys: {list(market_data.keys())}")
            
            # ============================================
            # KRİTİK VERİLERİ ÇIKAR (Hardcoded YOK!)
            # ============================================
            
            # PAIR
            pair = setup_data.get('pair')
            if not pair:
                logger.error(f"❌ SKIP: 'pair' bilgisi eksik! Keys: {list(setup_data.keys())}")
                return self._skip_response("pair bilgisi eksik")
            
            # DIRECTION
            direction = setup_data.get('direction')
            if not direction:
                logger.error(f"❌ SKIP [{pair}]: 'direction' bilgisi eksik!")
                return self._skip_response(f"{pair}: direction eksik")
            
            # TIMEFRAME
            timeframe = setup_data.get('timeframe')
            if not timeframe:
                logger.error(f"❌ SKIP [{pair}]: 'timeframe' bilgisi eksik!")
                return self._skip_response(f"{pair}: timeframe eksik")
            
            # ENTRY PRICE
            entry_price = setup_data.get('entry_price')
            if entry_price is None or entry_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'entry_price' eksik veya 0!")
                return self._skip_response(f"{pair}: entry_price eksik")
            entry_price = float(entry_price)
            
            # STOP PRICE
            stop_price = setup_data.get('stop_price')
            if stop_price is None or stop_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'stop_price' eksik veya 0!")
                return self._skip_response(f"{pair}: stop_price eksik")
            stop_price = float(stop_price)
            
            # TP1 PRICE
            tp1_price = setup_data.get('tp1_price')
            if tp1_price is None or tp1_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'tp1_price' eksik veya 0!")
                return self._skip_response(f"{pair}: tp1_price eksik")
            tp1_price = float(tp1_price)
            
            # TP2 PRICE (opsiyonel - yoksa tp1 kullan)
            tp2_price = setup_data.get('tp2_price')
            if tp2_price:
                tp2_price = float(tp2_price)
            else:
                tp2_price = tp1_price
                logger.debug(f"⚠️ [{pair}]: tp2_price yok, tp1 kullanılıyor")
            
            # v2.3.4: TP2 Sanity Check (ATR=0 durumunu yakala)
            if direction.upper() == 'LONG' and tp2_price <= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP2 ({tp2_price}) <= Entry ({entry_price}) - LONG için geçersiz!")
                return self._skip_response(f"{pair}: TP2 entry'den düşük veya eşit (muhtemelen ATR=0)")
            if direction.upper() == 'SHORT' and tp2_price >= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP2 ({tp2_price}) >= Entry ({entry_price}) - SHORT için geçersiz!")
                return self._skip_response(f"{pair}: TP2 entry'den yüksek veya eşit (muhtemelen ATR=0)")
            
            # R:R RATIO
            rr_ratio = setup_data.get('rr_ratio')
            if rr_ratio is None:
                logger.error(f"❌ SKIP [{pair}]: 'rr_ratio' bilgisi eksik!")
                return self._skip_response(f"{pair}: rr_ratio eksik")
            rr_ratio = float(rr_ratio)
            
            # SETUP TYPE
            setup_type = setup_data.get('type')
            if not setup_type:
                logger.warning(f"⚠️ [{pair}]: 'type' eksik, 'Unknown' kullanılıyor")
                setup_type = 'Unknown'
            
            # CONFIDENCE (detector'dan)
            confidence_label = setup_data.get('confidence')
            if not confidence_label:
                logger.warning(f"⚠️ [{pair}]: 'confidence' eksik!")
                confidence_label = None  # Prompt'ta belirtilecek
            
            # STRENGTH SCORE (detector'dan)
            strength_score = setup_data.get('strength_score')
            if strength_score is None:
                logger.warning(f"⚠️ [{pair}]: 'strength_score' eksik!")
                strength_score = None  # Prompt'ta belirtilecek
            else:
                strength_score = float(strength_score)
            
            # ============================================
            # MARKET VERİLERİNİ ÇIKAR
            # ============================================
            
            # CURRENT PRICE
            current_price = market_data.get('current_price')
            if current_price is None or current_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'current_price' eksik!")
                return self._skip_response(f"{pair}: current_price eksik")
            current_price = float(current_price)
            
            # PDC (Previous Day Candle)
            pdc = market_data.get('previous_day', {})
            pdc_bias = pdc.get('candle_type')
            pdc_high = pdc.get('high')
            pdc_low = pdc.get('low')
            pdc_open = pdc.get('open')
            pdc_close = pdc.get('close')
            
            if not pdc_bias:
                logger.warning(f"⚠️ [{pair}]: PDC bias eksik!")
            
            # PDC değerlerini float'a çevir (varsa)
            pdc_high = float(pdc_high) if pdc_high else 0
            pdc_low = float(pdc_low) if pdc_low else 0
            pdc_open = float(pdc_open) if pdc_open else 0
            pdc_close = float(pdc_close) if pdc_close else 0
            
            # ATR - timeframe bazlı
            atr_data = market_data.get('atr', {})
            atr_key = self.TF_MAP.get(timeframe.lower(), timeframe.lower())
            atr = atr_data.get(atr_key)
            
            if atr is None:
                logger.warning(f"⚠️ [{pair}]: ATR[{atr_key}] eksik! Mevcut keys: {list(atr_data.keys())}")
                atr = 0
            else:
                atr = float(atr)
            
            # OB/FVG bilgisi
            smart_money = market_data.get('smart_money', {})
            obs = smart_money.get('order_blocks', {})
            fvgs = smart_money.get('fair_value_gaps', {})
            
            total_obs = sum(len(v) for v in obs.values()) if isinstance(obs, dict) else 0
            total_fvgs = sum(len(v) for v in fvgs.values()) if isinstance(fvgs, dict) else 0
            
            # Fibo bilgisi
            fibo = market_data.get('fibonacci', {})
            fibo_levels = fibo.get('levels', {})
            
            # Volume bilgisi
            volume_data = market_data.get('volume', {})
            tf_volume = volume_data.get(atr_key, {})
            
            if isinstance(tf_volume, dict):
                volume_spike = float(tf_volume.get('spike_ratio', 0))
                volume_trend = tf_volume.get('trend', 'unknown')
            else:
                volume_spike = 0.0
                volume_trend = 'unknown'
                logger.warning(f"⚠️ [{pair}]: Volume[{atr_key}] eksik veya format yanlış!")
            
            # ============================================
            # v2.3.4: STOP/TP ADJUSTMENT (TP2 dahil!)
            # ============================================
            
            adjustment_result = self.adjust_stop_and_tp(
                entry_price=entry_price,
                stop_price=stop_price,
                tp1_price=tp1_price,
                tp2_price=tp2_price,
                direction=direction
            )
            
            # Adjustment None döndüyse → SKIP (stop >= 2.5%)
            if adjustment_result is None:
                original_stop_pct = abs(entry_price - stop_price) / entry_price * 100
                logger.info(f"⏭️ Pre-filter SKIP [{pair}]: Stop %{original_stop_pct:.2f} >= %{self.STOP_ADJUST_MAX} (çok riskli)")
                return {
                    'action': 'SKIP',
                    'confidence': 100,
                    'reasoning': f'Stop çok uzak: %{original_stop_pct:.2f} >= %{self.STOP_ADJUST_MAX} maximum',
                    'adjustments': {}
                }
            
            # Adjusted değerleri kullan (v2.3.4: TP2 dahil!)
            stop_price = adjustment_result['stop_price']
            tp1_price = adjustment_result['tp1_price']
            tp2_price = adjustment_result['tp2_price']
            stop_distance_pct = adjustment_result['new_stop_pct']
            rr_ratio = adjustment_result['new_rr']
            
            # Adjustment bilgisini logla
            if adjustment_result['adjusted']:
                logger.info(f"🔧 [{pair}] Stop/TP Adjusted ({direction}): {adjustment_result['adjustment_type']} | "
                           f"Stop: %{adjustment_result['original_stop_pct']} → %{adjustment_result['new_stop_pct']} | "
                           f"R:R: {adjustment_result['original_rr']} → {adjustment_result['new_rr']}")
            
            # ============================================
            # DEBUG LOG - Toplanan veriler
            # ============================================
            logger.debug(f"""
📊 [{pair}] Evaluate Setup Debug:
   Direction: {direction} | TF: {timeframe} | Type: {setup_type}
   Entry: {entry_price} | Stop: {stop_price} | TP1: {tp1_price} | TP2: {tp2_price}
   R:R: {rr_ratio:.2f} | Stop%: {stop_distance_pct:.2f}%
   Adjusted: {adjustment_result['adjusted']} | Type: {adjustment_result['adjustment_type']}
   Confidence: {confidence_label} | Score: {strength_score}
   PDC Bias: {pdc_bias} | ATR: {atr} | Vol: {volume_spike:.2f}x
""")
            
            # ============================================
            # ÖN KONTROLLER (Claude'a göndermeden önce)
            # ============================================
            
            # v2.3.8: MIN_RR_RATIO calculators'tan (DRY)
            if round(rr_ratio, 2) < MIN_RR_RATIO:
                logger.info(f"⏭️ Pre-filter SKIP [{pair}]: RR {rr_ratio:.2f} < {MIN_RR_RATIO}")
                return {
                    'action': 'SKIP',
                    'confidence': 100,
                    'reasoning': f'RR çok düşük: {rr_ratio:.2f} < {MIN_RR_RATIO} minimum',
                    'adjustments': {}
                }
            
            # NOT: Stop mesafesi kontrolü artık adjust_stop_and_tp() içinde yapılıyor
            # Eski sabit %0.8 min ve %1.5 max kontrolleri kaldırıldı
            
            # ============================================
            # CLAUDE PROMPT
            # ============================================
            
            # Confidence/Score bilgisi varsa göster
            score_info = ""
            if confidence_label:
                score_info += f"- Confidence: {confidence_label}\n"
            if strength_score is not None:
                score_info += f"- Strength Score: {strength_score:.2f}\n"
            if python_score:
                score_info += f"- Python Score: {python_score:.2f}/1.0 ({python_score*100:.0f}/100)\n"
            
            # Adjustment bilgisi
            adjustment_info = ""
            if adjustment_result['adjusted']:
                adjustment_info = f"""
## ⚠️ STOP ADJUSTMENT YAPILDI:
- Adjustment Type: {adjustment_result['adjustment_type']}
- Orijinal Stop: %{adjustment_result['original_stop_pct']:.2f}
- Yeni Stop: %{adjustment_result['new_stop_pct']:.2f}
- Orijinal R:R: {adjustment_result['original_rr']:.2f}
- Yeni R:R: {adjustment_result['new_rr']:.2f}
"""
            
            # v2.3.8: Volume threshold'lar calculators'tan (DRY)
            prompt = f"""Sen T-TARS Trading AI'sın. Profesyonel bir ICT/SMC trader olarak aşağıdaki setup'ı değerlendir.

## SETUP BİLGİLERİ:
- Pair: {pair}
- Direction: {direction}
- Setup Type: {setup_type}
- Timeframe: {timeframe}
- Entry: {format_price_display(entry_price)}
- Stop Loss: {format_price_display(stop_price)} (mesafe: %{stop_distance_pct:.2f})
- TP1: {format_price_display(tp1_price)}
- TP2: {format_price_display(tp2_price)}
- R:R Ratio: {rr_ratio:.2f}
{score_info}{adjustment_info}
## MARKET VERİSİ:
- Current Price: {format_price_display(current_price)}
- PDC Bias: {pdc_bias.upper() if pdc_bias else 'UNKNOWN'}
- PDC High: {format_price_display(pdc_high)}
- PDC Low: {format_price_display(pdc_low)}
- ATR(14): {format_price_display(atr)}
- Volume Spike: {volume_spike:.2f}x
- Volume Trend: {volume_trend}
- Order Blocks: {total_obs} adet
- Fair Value Gaps: {total_fvgs} adet

## FİBONACCİ SEVİYELERİ:
- 23.6%: {format_price_display(fibo_levels.get('23.6', 0))}
- 38.2%: {format_price_display(fibo_levels.get('38.2', 0))}
- 50.0%: {format_price_display(fibo_levels.get('50.0', 0))}
- 61.8%: {format_price_display(fibo_levels.get('61.8', 0))}
- 78.6%: {format_price_display(fibo_levels.get('78.6', 0))}

## KONTROL LİSTESİ:

1. LİKİDİTE TEMİZLİĞİ: 
   - LONG için: Fiyat PDC Low ({format_price_display(pdc_low)}) altına inip geri dönmüş mü?
   - SHORT için: Fiyat PDC High ({format_price_display(pdc_high)}) üstüne çıkıp geri dönmüş mü?
   
2. REVERSAL SİNYALİ:
   - OB/FVG'den tepki var mı?
   
3. CONFLUENCE:
   - Entry bölgesinde OB + FVG + Fibo birleşimi var mı?
   
4. BIAS UYUMU:
   - {direction} yönü PDC bias ({pdc_bias if pdc_bias else 'unknown'}) ile uyumlu mu?

5. SETUP GÜCÜ:
   - Volume spike: {volume_spike:.2f}x (>{VOLUME_LOW} kabul, >{VOLUME_GOOD} iyi, >{VOLUME_EXCELLENT} cok iyi)
   - R:R: {rr_ratio:.2f} (>={MIN_RR_RATIO} minimum)

## KARAR KRİTERLERİ:
- ENTER: Minimum 4/5 kriter pozitif
- SKIP: 2+ kriter negatif
- WAIT: Belirsiz

ÖNEMLİ: Sadece güçlü setup'lara ENTER ver. Emin değilsen SKIP.

SADECE aşağıdaki JSON formatında cevap ver:
{{"action": "ENTER", "confidence": 85, "reasoning": "kısa açıklama max 80 karakter"}}"""

            # ============================================
            # CLAUDE API ÇAĞRISI
            # ============================================
            logger.debug(f"🧠 [{pair}]: Claude API çağrılıyor...")
            
            response = self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Response'u parse et
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text.strip()
            
            logger.debug(f"🧠 [{pair}]: Claude response: {text_content[:100]}...")
            
            # ============================================
            # JSON PARSE
            # ============================================
            try:
                json_match = re.search(r'\{[^{}]*\}', text_content, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group())
                else:
                    decision = json.loads(text_content)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ [{pair}]: JSON parse failed: {e} | Response: {text_content[:100]}")
                # Fallback
                if 'ENTER' in text_content.upper():
                    decision = {'action': 'ENTER', 'confidence': 50, 'reasoning': 'JSON parse failed, ENTER detected'}
                elif 'SKIP' in text_content.upper():
                    decision = {'action': 'SKIP', 'confidence': 50, 'reasoning': 'JSON parse failed, SKIP detected'}
                else:
                    decision = {'action': 'WAIT', 'confidence': 30, 'reasoning': 'JSON parse failed, defaulting to WAIT'}
            
            # Normalize action
            action = decision.get('action', 'WAIT').upper()
            if action not in ['ENTER', 'SKIP', 'WAIT']:
                action = 'WAIT'
            
            result = {
                'action': action,
                'confidence': int(decision.get('confidence', 50)),
                'reasoning': decision.get('reasoning', 'No reasoning provided')[:100],
                'adjustments': {
                    'adjusted': adjustment_result['adjusted'],
                    'type': adjustment_result['adjustment_type'],
                    'original_stop_pct': adjustment_result['original_stop_pct'],
                    'new_stop_pct': adjustment_result['new_stop_pct'],
                    'stop_price': stop_price,
                    'tp1_price': tp1_price
                },
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
            
            # Log
            emoji = "✅" if action == "ENTER" else "⏭️" if action == "SKIP" else "⏸️"
            adj_tag = f" [ADJ:{adjustment_result['adjustment_type']}]" if adjustment_result['adjusted'] else ""
            logger.info(f"🧠 Claude [{pair}] {direction} [{timeframe}]{adj_tag} → {emoji} {action} ({result['confidence']}%) | {result['reasoning'][:50]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Claude evaluate_setup error: {e}", exc_info=True)
            return self._skip_response(f"Claude API error: {str(e)[:50]}")
    
    def _skip_response(self, reason):
        """Standart SKIP response oluştur"""
        return {
            'action': 'SKIP',
            'confidence': 0,
            'reasoning': reason,
            'adjustments': {}
        }
