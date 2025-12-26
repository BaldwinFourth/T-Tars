# -*- coding: utf-8 -*-
"""
T-TARS Claude Service v2.4.12
==============================
Claude AI API wrapper for market analysis and setup evaluation.

v2.4.12:
- CHANGED: Limit Order Güvenlik Kontrolleri (3 katmanlı)
  1. Yön Kontrolü: LONG: Stop<Entry<Current, SHORT: Current<Entry<Stop
  2. Stop-Entry Mesafesi >= %0.8
  3. Stop-Current Mesafesi >= %0.8
- REMOVED: Entry/Current %1 fark kontrolü (yanlış mantık - OB/FVG uzak olabilir)

v2.4.11:
- NEW: Stop Sanity Check (LONG: Stop<Entry<TP, SHORT: TP<Entry<Stop)
- Limit order instant fill sorunu için ek güvenlik katmanı

v2.4.10:
- CHANGED: TP1/TP2 sistemi → Tek TP sistemi (TP_MULTIPLIER=3.0)
- REMOVED: tp1_price, tp2_price → tp_price
- CHANGED: adjust_stop_and_tp() tek TP döndürüyor
- CHANGED: MIN_RR_RATIO 2.0 → 3.0

v2.3.9:
- FIX: EXPAND adjustment artık risk olarak algılanmıyor
- CHANGED: "⚠️ STOP ADJUSTMENT" → "ℹ️ STOP/TP OPTİMİZASYONU"

v2.3.8:
- CHANGED: Volume threshold'lar calculators.py'den import ediliyor (DRY)
- CHANGED: MIN_RR_RATIO calculators.py'den import ediliyor (DRY)
"""

from anthropic import Anthropic
from app.config import Config
# v2.3.8: Threshold'ları calculators'tan al (DRY)
from app.strategies.calculators import (
    VOLUME_TRADEABLE_MIN,
    VOLUME_LOW,
    VOLUME_GOOD,
    VOLUME_EXCELLENT,
    MIN_RR_RATIO,
    TP_MULTIPLIER  # v2.4.10: tek TP
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
    """Claude Haiku 4.5 API Service - v2.4.12 (AI Decision Engine + Safety Checks)"""
    
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
    
    # v2.4.10: Stop Adjustment Sabitleri
    STOP_IDEAL_MAX = 1.5    # İdeal maksimum (ara değer)
    STOP_AGGRESSIVE_TARGET = 1.8  # 2-2.5% arası için hedef
    AGGRESSIVE_RR = 3.0     # 2-2.5% arası için R:R
    
    # v2.4.12: Minimum mesafe sabiti (Config'den alınıyor ama class seviyesinde de tanımlı)
    MIN_DISTANCE_PCT = 0.008  # %0.8 - Stop-Entry ve Stop-Current için minimum
    
    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
        # Stop thresholds Config'den türetiliyor (DRY)
        self.STOP_MIN_PCT = Config.STOP_DISTANCE_MIN * 100      # 0.008 → 0.8
        self.STOP_ADJUST_MAX = Config.STOP_DISTANCE_MAX * 100   # 0.025 → 2.5
        
        logger.info(f"✅ Claude Service v2.4.12 initialized: {Config.CLAUDE_MODEL} | "
                   f"Stop: {self.STOP_MIN_PCT}%-{self.STOP_ADJUST_MAX}% | "
                   f"MIN_RR: {MIN_RR_RATIO} | TP_MULT: {TP_MULTIPLIER}")
    
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
    
    def adjust_stop_and_tp(self, entry_price, stop_price, tp_price, direction):
        """
        v2.4.10: Otomatik Stop/TP Adjustment (Tek TP!)
        
        Kurallar:
        1. Stop < 0.8% → %0.8'e çek, TP orantılı uzat
        2. Stop 0.8-1.5% → Değişiklik yok (ideal)
        3. Stop 1.5-2% → %1.5'e çek, TP orantılı kısalt
        4. Stop 2-2.5% → %1.8'e çek, TP 3R yap
        5. Stop >= 2.5% → None döndür (SKIP)
        
        Returns:
            dict: {'stop_price', 'tp_price', 'adjusted', 'adjustment_type', ...}
            None: SKIP gerekiyorsa
        """
        entry = float(entry_price)
        stop = float(stop_price)
        tp = float(tp_price)
        
        # Direction normalize
        is_long = direction.upper() == 'LONG'
        
        # Orijinal stop mesafesi
        stop_distance = abs(entry - stop)
        stop_pct = (stop_distance / entry) * 100 if entry > 0 else 0
        
        # Orijinal TP mesafesi
        tp_distance = abs(tp - entry)
        
        # Orijinal R:R
        original_rr = tp_distance / stop_distance if stop_distance > 0 else 0
        
        result = {
            'stop_price': stop,
            'tp_price': tp,
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
            
            # Yeni TP mesafesi (aynı R:R'ı korumak için orantılı)
            new_tp_distance = tp_distance * expansion_ratio
            
            # Yeni fiyatlar - LONG/SHORT ayrımı
            if is_long:
                new_stop = entry - new_stop_distance
                new_tp = entry + new_tp_distance
            else:  # SHORT
                new_stop = entry + new_stop_distance
                new_tp = entry - new_tp_distance
            
            new_rr = new_tp_distance / new_stop_distance if new_stop_distance > 0 else original_rr
            
            result['stop_price'] = round(new_stop, 8)
            result['tp_price'] = round(new_tp, 8)
            result['adjusted'] = True
            result['adjustment_type'] = 'EXPAND'
            result['new_stop_pct'] = self.STOP_MIN_PCT
            result['new_rr'] = round(new_rr, 2)
            
            logger.info(f"📐 Stop EXPAND ({direction}): %{stop_pct:.2f} → %{self.STOP_MIN_PCT} | "
                       f"Stop: {format_price_display(stop)} → {format_price_display(new_stop)} | "
                       f"TP: {format_price_display(tp)} → {format_price_display(new_tp)} | "
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
            
            # Yeni TP mesafesi (aynı R:R'ı korumak için orantılı)
            new_tp_distance = tp_distance * shrink_ratio
            
            # Yeni fiyatlar - LONG/SHORT ayrımı
            if is_long:
                new_stop = entry - new_stop_distance
                new_tp = entry + new_tp_distance
            else:  # SHORT
                new_stop = entry + new_stop_distance
                new_tp = entry - new_tp_distance
            
            new_rr = new_tp_distance / new_stop_distance if new_stop_distance > 0 else original_rr
            
            result['stop_price'] = round(new_stop, 8)
            result['tp_price'] = round(new_tp, 8)
            result['adjusted'] = True
            result['adjustment_type'] = 'SHRINK'
            result['new_stop_pct'] = self.STOP_IDEAL_MAX
            result['new_rr'] = round(new_rr, 2)
            
            logger.info(f"📐 Stop SHRINK ({direction}): %{stop_pct:.2f} → %{self.STOP_IDEAL_MAX} | "
                       f"Stop: {format_price_display(stop)} → {format_price_display(new_stop)} | "
                       f"TP: {format_price_display(tp)} → {format_price_display(new_tp)} | "
                       f"R:R: {original_rr:.2f} → {new_rr:.2f}")
            
            return result
        
        # ============================================
        # KURAL 4: Stop 2-2.5% → %1.8'e çek, TP 3R yap
        # ============================================
        if 2.0 <= stop_pct < self.STOP_ADJUST_MAX:
            # Yeni stop mesafesi: %1.8
            new_stop_distance = entry * (self.STOP_AGGRESSIVE_TARGET / 100)
            
            # Yeni TP mesafesi: 3R
            new_tp_distance = new_stop_distance * self.AGGRESSIVE_RR
            
            # Yeni fiyatlar - LONG/SHORT ayrımı
            if is_long:
                new_stop = entry - new_stop_distance
                new_tp = entry + new_tp_distance
            else:  # SHORT
                new_stop = entry + new_stop_distance
                new_tp = entry - new_tp_distance
            
            result['stop_price'] = round(new_stop, 8)
            result['tp_price'] = round(new_tp, 8)
            result['adjusted'] = True
            result['adjustment_type'] = 'AGGRESSIVE'
            result['new_stop_pct'] = self.STOP_AGGRESSIVE_TARGET
            result['new_rr'] = self.AGGRESSIVE_RR
            
            logger.info(f"📐 Stop AGGRESSIVE ({direction}): %{stop_pct:.2f} → %{self.STOP_AGGRESSIVE_TARGET} | "
                       f"Stop: {format_price_display(stop)} → {format_price_display(new_stop)} | "
                       f"TP: {format_price_display(tp)} → {format_price_display(new_tp)} | "
                       f"R:R: {original_rr:.2f} → {self.AGGRESSIVE_RR}")
            
            return result
        
        # Buraya gelmemeli ama güvenlik için
        return result
    
    def evaluate_setup(self, setup_data, market_data, python_score):
        """
        v2.4.11: AI Setup Değerlendirmesi - Tek TP Sistemi + Safety Checks
        
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
            
            # v2.4.10: TP PRICE (tek TP)
            tp_price = setup_data.get('tp_price')
            if tp_price is None or tp_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'tp_price' eksik veya 0!")
                return self._skip_response(f"{pair}: tp_price eksik")
            tp_price = float(tp_price)
            
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
            
            # ============================================
            # v2.4.12: LİMİT ORDER GÜVENLİK KONTROLLERİ
            # ============================================
            is_long = direction.upper() == 'LONG'
            
            # -------------------------------------------
            # KONTROL 1: YÖN KONTROLÜ (Tam Sıralama)
            # LONG:  Stop < Entry < Current (fiyat aşağı gelecek, bekleyecek)
            # SHORT: Current < Entry < Stop (fiyat yukarı çıkacak, bekleyecek)
            # -------------------------------------------
            if is_long:
                if not (stop_price < entry_price < current_price):
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: LONG sıralama yanlış!")
                    logger.warning(f"   Stop({format_price_display(stop_price)}) < Entry({format_price_display(entry_price)}) < Current({format_price_display(current_price)}) olmalı")
                    if stop_price >= entry_price:
                        return self._skip_response(f"{pair}: LONG Stop >= Entry")
                    if entry_price >= current_price:
                        return self._skip_response(f"{pair}: LONG Entry >= Current, limit hemen fill olur")
            else:  # SHORT
                if not (current_price < entry_price < stop_price):
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: SHORT sıralama yanlış!")
                    logger.warning(f"   Current({format_price_display(current_price)}) < Entry({format_price_display(entry_price)}) < Stop({format_price_display(stop_price)}) olmalı")
                    if entry_price >= stop_price:
                        return self._skip_response(f"{pair}: SHORT Entry >= Stop")
                    if current_price >= entry_price:
                        return self._skip_response(f"{pair}: SHORT Current >= Entry, limit hemen fill olur")
            
            # -------------------------------------------
            # KONTROL 2: STOP-ENTRY MESAFESİ >= %0.8
            # -------------------------------------------
            stop_entry_pct = abs(stop_price - entry_price) / entry_price if entry_price > 0 else 0
            if stop_entry_pct < self.MIN_DISTANCE_PCT:
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Stop-Entry mesafesi çok küçük!")
                logger.warning(f"   Stop-Entry: %{stop_entry_pct*100:.2f} < %{self.MIN_DISTANCE_PCT*100}")
                return self._skip_response(f"{pair}: Stop-Entry %{stop_entry_pct*100:.2f} < %0.8 minimum")
            
            # -------------------------------------------
            # KONTROL 3: STOP-CURRENT MESAFESİ >= %0.8
            # Volatilite güvenliği - fill olsa bile stop tetiklenmez
            # -------------------------------------------
            stop_current_pct = abs(stop_price - current_price) / current_price if current_price > 0 else 0
            if stop_current_pct < self.MIN_DISTANCE_PCT:
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Stop-Current mesafesi çok küçük!")
                logger.warning(f"   Stop-Current: %{stop_current_pct*100:.2f} < %{self.MIN_DISTANCE_PCT*100}")
                return self._skip_response(f"{pair}: Stop-Current %{stop_current_pct*100:.2f} < %0.8 minimum")
            
            # Log: Tüm kontroller geçti
            logger.debug(f"✅ [{pair}] Güvenlik kontrolleri geçti: "
                        f"Stop-Entry: %{stop_entry_pct*100:.2f}, Stop-Current: %{stop_current_pct*100:.2f}")
            
            # ============================================
            # v2.4.10: TP Sanity Check (ATR=0 durumunu yakala)
            # ============================================
            if is_long and tp_price <= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP ({tp_price}) <= Entry ({entry_price}) - LONG için geçersiz!")
                return self._skip_response(f"{pair}: TP entry'den düşük veya eşit (muhtemelen ATR=0)")
            if not is_long and tp_price >= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP ({tp_price}) >= Entry ({entry_price}) - SHORT için geçersiz!")
                return self._skip_response(f"{pair}: TP entry'den yüksek veya eşit (muhtemelen ATR=0)")
            
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
            # v2.4.10: STOP/TP ADJUSTMENT (Tek TP!)
            # ============================================
            
            adjustment_result = self.adjust_stop_and_tp(
                entry_price=entry_price,
                stop_price=stop_price,
                tp_price=tp_price,
                direction=direction
            )
            
            # Adjustment None döndüyse → SKIP (stop >= 2.5%)
            if adjustment_result is None:
                original_stop_pct = abs(entry_price - stop_price) / entry_price * 100
                logger.info(f"⏭️ Pre-filter SKIP [{pair}]: Stop %{original_stop_pct:.2f} >= %{self.STOP_ADJUST_MAX} (çok riskli)")
                return {
                    'action': 'SKIP',
                    'confidence': 100,
                    'reasoning': f'Stop cok uzak: %{original_stop_pct:.2f} >= %{self.STOP_ADJUST_MAX} maximum',
                    'adjustments': {}
                }
            
            # v2.4.10: Adjusted değerleri kullan (tek TP)
            stop_price = adjustment_result['stop_price']
            tp_price = adjustment_result['tp_price']
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
   Entry: {entry_price} | Stop: {stop_price} | TP: {tp_price}
   R:R: {rr_ratio:.2f} | Stop%: {stop_distance_pct:.2f}%
   Current: {current_price} | Diff: {price_diff_pct*100:.2f}%
   Adjusted: {adjustment_result['adjusted']} | Type: {adjustment_result['adjustment_type']}
   Confidence: {confidence_label} | Score: {strength_score}
   PDC Bias: {pdc_bias} | ATR: {atr} | Vol: {volume_spike:.2f}x
""")
            
            # ============================================
            # ÖN KONTROLLER (Claude'a göndermeden önce)
            # ============================================
            
            # v2.4.10: MIN_RR_RATIO = 3.0
            if round(rr_ratio, 2) < MIN_RR_RATIO:
                logger.info(f"⏭️ Pre-filter SKIP [{pair}]: RR {rr_ratio:.2f} < {MIN_RR_RATIO}")
                return {
                    'action': 'SKIP',
                    'confidence': 100,
                    'reasoning': f'RR cok dusuk: {rr_ratio:.2f} < {MIN_RR_RATIO} minimum',
                    'adjustments': {}
                }
            
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
            
            # Adjustment bilgisi - EXPAND pozitif algı
            adjustment_info = ""
            if adjustment_result['adjusted']:
                adj_type = adjustment_result['adjustment_type']
                if adj_type == 'EXPAND':
                    adjustment_info = f"""
## ℹ️ STOP/TP OPTİMİZASYONU (EXPAND):
- Stop %{adjustment_result['original_stop_pct']:.2f} → %{adjustment_result['new_stop_pct']:.2f} (minimum mesafeye genişletildi)
- TP de orantılı genişletildi (R:R korundu)
- R:R: {adjustment_result['original_rr']:.2f} → {adjustment_result['new_rr']:.2f} (AYNI)
- NOT: Bu bir risk DEĞİL, güvenlik optimizasyonu. R:R aynı kaldığı için trade kalitesi değişmedi.
"""
                else:
                    adjustment_info = f"""
## ℹ️ STOP/TP AYARLANDI ({adj_type}):
- Orijinal Stop: %{adjustment_result['original_stop_pct']:.2f}
- Yeni Stop: %{adjustment_result['new_stop_pct']:.2f}
- R:R: {adjustment_result['original_rr']:.2f} → {adjustment_result['new_rr']:.2f}
"""
            
            # v2.4.10: Tek TP promptu
            prompt = f"""Sen T-TARS Trading AI'sın. Profesyonel bir ICT/SMC trader olarak aşağıdaki setup'ı değerlendir.

## SETUP BİLGİLERİ:
- Pair: {pair}
- Direction: {direction}
- Setup Type: {setup_type}
- Timeframe: {timeframe}
- Entry: {format_price_display(entry_price)}
- Stop Loss: {format_price_display(stop_price)} (mesafe: %{stop_distance_pct:.2f})
- TP: {format_price_display(tp_price)}
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
            
            # v2.4.10: tek TP
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
                    'tp_price': tp_price
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
