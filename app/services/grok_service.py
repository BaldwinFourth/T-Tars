# -*- coding: utf-8 -*-
"""
T-TARS Grok Service v2.5.7
==============================
Grok API wrapper for market analysis and setup evaluation.

v2.5.7:
- FIX: reasoning_effort parametresi kaldırıldı (grok-4-1-fast-reasoning desteklemiyor)

v2.5.6:
- FIX: Pre-filter mantığı Claude service v2.5.2'den birebir alındı
- FIX: Operatör hataları düzeltildi (<=, >= karışıklığı)
- ADD: Her fonksiyona ENTRY/EXIT log eklendi
- ADD: openai>=1.0.0 requirements.txt'e eklendi

v2.5.3:
- NEW: Claude → Grok 4.1 Fast Reasoning geçişi
- CHANGED: Anthropic API → xAI API (OpenAI-compatible)

v2.5.2 (Claude base):
- CHANGED: MIN_DISTANCE_PCT = 0.01 (%1.0) - Stop mesafesi artırıldı
- CHANGED: STOP_MIN_PCT = 1.0 (Config'den bağımsız hardcode)
"""

from openai import OpenAI
from app.config import Config
from app.strategies.calculators import (
    VOLUME_TRADEABLE_MIN,
    VOLUME_LOW,
    VOLUME_GOOD,
    VOLUME_EXCELLENT,
    MIN_RR_RATIO,
    TP_MULTIPLIER
)
import logging
import json
import re

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen T-TARS, profesyonel bir ICT/SMC (Inner Circle Trader / Smart Money Concepts) metodolojisi kullanan trading AI asistanısın.

## KİMLİĞİN:
- Adın: T-TARS (Trading - Technical Analysis & Risk System)
- Uzmanlık: Kripto futures trading, likidite analizi, order block/FVG tespiti
- Metodoloji: ICT/SMC konseptleri (likidite avı, OB/FVG tepkileri, PDC bias)

## GÖREVİN:
1. Setup'ları objektif ve disiplinli değerlendir
2. Likidite temizliği (sweep) kontrol et
3. OB/FVG tepki kalitesini analiz et
4. Confluence (birleşim) noktalarını tespit et
5. Risk/Reward oranını değerlendir

## KARAR PRENSİPLERİN:
- ENTER: Minimum 4/5 kriter pozitif, güçlü confluence var
- SKIP: 2+ kriter negatif veya belirsizlik var
- WAIT: Daha fazla konfirmasyon gerekiyor

## ÖNEMLİ KURALLAR:
- Sadece güçlü setup'lara ENTER ver
- Emin değilsen SKIP (para kaybetmemek kazanmaktan önemli)
- Duygusal değil, teknik analiz odaklı ol
- Her zaman JSON formatında cevap ver

## CEVAP FORMATI:
{"action": "ENTER|SKIP|WAIT", "confidence": 0-100, "reasoning": "kısa açıklama max 100 karakter"}"""


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


class GrokService:
    """Grok 4.1 Fast Reasoning API Service - v2.5.6 (AI Decision Engine + %1.0 Stop)"""
    
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
    
    # v2.5.2: Stop Adjustment Sabitleri - %1.0 minimum
    STOP_IDEAL_MAX = 1.5    # İdeal maksimum (ara değer)
    STOP_AGGRESSIVE_TARGET = 1.8  # 2-2.5% arası için hedef
    AGGRESSIVE_RR = 3.0     # 2-2.5% arası için R:R
    
    # v2.5.2: Minimum mesafe sabiti - %1.0
    MIN_DISTANCE_PCT = 0.01  # %1.0 - Stop-Entry ve Stop-Price için minimum
    
    def __init__(self):
        # Grok API client (xAI - OpenAI compatible)
        self.client = OpenAI(
            api_key=Config.XAI_API_KEY,
            base_url="https://api.x.ai/v1"
        )
        
        # v2.5.2: %1.0 hardcode (Config'den bağımsız)
        self.STOP_MIN_PCT = 1.0         # %1.0 minimum stop mesafesi
        self.STOP_ADJUST_MAX = 2.5      # %2.5 maksimum stop mesafesi
        
        # v2.4.14: Thinking budget (Grok reasoning için)
        self.thinking_budget = Config.THINKING_BUDGET
        
        logger.info(f"✅ Grok Service v2.5.6 initialized: {Config.GROK_MODEL} | "
                   f"Thinking: {self.thinking_budget} tokens | "
                   f"Stop: {self.STOP_MIN_PCT}%-{self.STOP_ADJUST_MAX}% | "
                   f"MIN_RR: {MIN_RR_RATIO} | TP_MULT: {TP_MULTIPLIER}")
    
    def analyze(self, prompt):
        """
        Genel analiz yap (eski fonksiyon - backward compat)
        """
        logger.info(f"🔍 analyze() ENTRY | prompt_len: {len(prompt)} chars")
        try:
            response = self.client.chat.completions.create(
                model=Config.GROK_MODEL,
                max_tokens=16000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            
            text_content = response.choices[0].message.content
            
            result = {
                "text": text_content,
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
            
            logger.info(f"Analysis complete: {result['input_tokens']}→{result['output_tokens']} tokens")
            logger.info(f"🔍 analyze() EXIT | SUCCESS")
            return result
            
        except Exception as e:
            logger.error(f"Grok API error: {e}")
            logger.error(f"🔍 analyze() EXIT | ERROR: {e}")
            raise
    
    def adjust_stop_and_tp(self, entry_price, stop_price, tp_price, direction):
        """
        v2.5.2: Otomatik Stop/TP Adjustment - %1.0 minimum!
        
        Kurallar:
        1. Stop < 1.0% → %1.0'e çek, TP orantılı uzat
        2. Stop 1.0-1.5% → Değişiklik yok (ideal)
        3. Stop 1.5-2% → %1.5'e çek, TP orantılı kısalt
        4. Stop 2-2.5% → %1.8'e çek, TP 3R yap
        5. Stop >= 2.5% → None döndür (SKIP)
        
        Returns:
            dict: {'stop_price', 'tp_price', 'adjusted', 'adjustment_type', ...}
            None: SKIP gerekiyorsa
        """
        logger.debug(f"🔧 adjust_stop_and_tp() ENTRY | {direction} | Entry: {entry_price} | Stop: {stop_price} | TP: {tp_price}")
        
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
            logger.debug(f"🔧 adjust_stop_and_tp() EXIT | SKIP (stop too large)")
            return None
        
        # ============================================
        # KURAL 2: Stop 1.0-1.5% → İdeal, değişiklik yok
        # ============================================
        if self.STOP_MIN_PCT <= stop_pct <= self.STOP_IDEAL_MAX:
            logger.debug(f"✅ Stop ideal aralıkta: %{stop_pct:.2f}")
            logger.debug(f"🔧 adjust_stop_and_tp() EXIT | NO_CHANGE (ideal range)")
            return result
        
        # ============================================
        # KURAL 1: Stop < 1.0% → %1.0'e çek, TP orantılı uzat
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
            
            logger.debug(f"🔧 adjust_stop_and_tp() EXIT | EXPAND")
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
            
            logger.debug(f"🔧 adjust_stop_and_tp() EXIT | SHRINK")
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
            
            logger.debug(f"🔧 adjust_stop_and_tp() EXIT | AGGRESSIVE")
            return result
        
        # Buraya gelmemeli ama güvenlik için
        logger.debug(f"🔧 adjust_stop_and_tp() EXIT | FALLBACK (no adjustment matched)")
        return result
    
    def evaluate_setup(self, setup_data, market_data, python_score):
        """
        v2.5.6: AI Setup Değerlendirmesi - Claude v2.5.2 mantığı + Grok API
        """
        pair = setup_data.get('pair', 'UNKNOWN')
        direction = setup_data.get('direction', 'UNKNOWN')
        logger.info(f"🎯 evaluate_setup() ENTRY | {pair} {direction} | python_score: {python_score}")
        
        try:
            # DEBUG: Gelen veriyi logla
            logger.debug(f"📥 setup_data keys: {list(setup_data.keys())}")
            logger.debug(f"📥 market_data keys: {list(market_data.keys())}")
            
            # KRİTİK VERİLERİ ÇIKAR
            pair = setup_data.get('pair')
            if not pair:
                logger.error(f"❌ SKIP: 'pair' bilgisi eksik! Keys: {list(setup_data.keys())}")
                return self._skip_response("pair bilgisi eksik")
            
            direction = setup_data.get('direction')
            if not direction:
                logger.error(f"❌ SKIP [{pair}]: 'direction' bilgisi eksik!")
                return self._skip_response(f"{pair}: direction eksik")
            
            timeframe = setup_data.get('timeframe')
            if not timeframe:
                logger.error(f"❌ SKIP [{pair}]: 'timeframe' bilgisi eksik!")
                return self._skip_response(f"{pair}: timeframe eksik")
            
            entry_price = setup_data.get('entry_price')
            if entry_price is None or entry_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'entry_price' eksik veya 0!")
                return self._skip_response(f"{pair}: entry_price eksik")
            entry_price = float(entry_price)
            
            stop_price = setup_data.get('stop_price')
            if stop_price is None or stop_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'stop_price' eksik veya 0!")
                return self._skip_response(f"{pair}: stop_price eksik")
            stop_price = float(stop_price)
            
            tp_price = setup_data.get('tp_price')
            if tp_price is None or tp_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'tp_price' eksik veya 0!")
                return self._skip_response(f"{pair}: tp_price eksik")
            tp_price = float(tp_price)
            
            rr_ratio = setup_data.get('rr_ratio')
            if rr_ratio is None:
                logger.error(f"❌ SKIP [{pair}]: 'rr_ratio' bilgisi eksik!")
                return self._skip_response(f"{pair}: rr_ratio eksik")
            rr_ratio = float(rr_ratio)
            
            setup_type = setup_data.get('type')
            if not setup_type:
                logger.warning(f"⚠️ [{pair}]: 'type' eksik, 'Unknown' kullanılıyor")
                setup_type = 'Unknown'
            
            confidence_label = setup_data.get('confidence')
            strength_score = setup_data.get('strength_score')
            if strength_score is not None:
                strength_score = float(strength_score)
            
            # MARKET VERİLERİ
            current_price = market_data.get('current_price')
            if current_price is None or current_price == 0:
                logger.error(f"❌ SKIP [{pair}]: 'current_price' eksik!")
                return self._skip_response(f"{pair}: current_price eksik")
            current_price = float(current_price)
            
            # ==============================================
            # LİMİT ORDER GÜVENLİK KONTROLLERİ
            # (Claude v2.5.2'den birebir - TEK BLOK)
            # ==============================================
            is_long = direction.upper() == 'LONG'
            
            # 📊 DETAYLI LOG - Gelen Değerler
            logger.info(f"📊 [{pair}] {direction} Pre-filter başlıyor:")
            logger.info(f"   Entry: {format_price_display(entry_price)} | Stop: {format_price_display(stop_price)} | TP: {format_price_display(tp_price)}")
            logger.info(f"   Price: {format_price_display(current_price)}")
            
            # YÖN KONTROLÜ - LONG: stop < entry < price
            if is_long:
                if not (stop_price < entry_price < current_price):
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: LONG sıralama yanlış!")
                    logger.warning(f"   Stop({format_price_display(stop_price)}) < Entry({format_price_display(entry_price)}) < Price({format_price_display(current_price)}) olmalı")
                    if stop_price >= entry_price:
                        return self._skip_response(f"{pair}: LONG Stop({format_price_display(stop_price)}) >= Entry({format_price_display(entry_price)})")
                    if entry_price >= current_price:
                        return self._skip_response(f"{pair}: LONG Entry({format_price_display(entry_price)}) >= Price({format_price_display(current_price)}), limit hemen fill olur")
            # YÖN KONTROLÜ - SHORT: price < entry < stop
            else:
                if not (current_price < entry_price < stop_price):
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: SHORT sıralama yanlış!")
                    logger.warning(f"   Price({format_price_display(current_price)}) < Entry({format_price_display(entry_price)}) < Stop({format_price_display(stop_price)}) olmalı")
                    if entry_price >= stop_price:
                        return self._skip_response(f"{pair}: SHORT Entry({format_price_display(entry_price)}) >= Stop({format_price_display(stop_price)})")
                    if current_price >= entry_price:
                        return self._skip_response(f"{pair}: SHORT Price({format_price_display(current_price)}) >= Entry({format_price_display(entry_price)}), limit hemen fill olur")
            
            # TP Sanity Check
            if is_long and tp_price <= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP ({format_price_display(tp_price)}) <= Entry ({format_price_display(entry_price)}) - LONG için geçersiz!")
                return self._skip_response(f"{pair}: TP entry'den düşük veya eşit")
            if not is_long and tp_price >= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP ({format_price_display(tp_price)}) >= Entry ({format_price_display(entry_price)}) - SHORT için geçersiz!")
                return self._skip_response(f"{pair}: TP entry'den yüksek veya eşit")
            
            logger.info(f"✅ [{pair}] Pre-filter geçti: {direction} sıralaması doğru")
            
            # PDC
            pdc = market_data.get('previous_day', {})
            pdc_bias = pdc.get('candle_type')
            pdc_high = float(pdc.get('high', 0))
            pdc_low = float(pdc.get('low', 0))
            pdc_open = float(pdc.get('open', 0))
            pdc_close = float(pdc.get('close', 0))
            
            # ATR
            atr_data = market_data.get('atr', {})
            atr_key = self.TF_MAP.get(timeframe.lower(), timeframe.lower())
            atr = float(atr_data.get(atr_key, 0))
            
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
            
            # STOP/TP ADJUSTMENT
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
            
            # Adjusted değerleri kullan
            stop_price = adjustment_result['stop_price']
            tp_price = adjustment_result['tp_price']
            stop_distance_pct = adjustment_result['new_stop_pct']
            rr_ratio = adjustment_result['new_rr']
            
            # Adjustment bilgisini logla
            if adjustment_result['adjusted']:
                logger.info(f"🔧 [{pair}] Stop/TP Adjusted ({direction}): {adjustment_result['adjustment_type']} | "
                           f"Stop: %{adjustment_result['original_stop_pct']} → %{adjustment_result['new_stop_pct']} | "
                           f"R:R: {adjustment_result['original_rr']} → {adjustment_result['new_rr']}")
            
            # STOP-PRICE KONTROLÜ (ADJUSTED değerlerle!)
            stop_current_pct = abs(stop_price - current_price) / current_price if current_price > 0 else 0
            if stop_current_pct < self.MIN_DISTANCE_PCT:
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Stop-Price mesafesi çok küçük (ADJUSTED)!")
                logger.warning(f"   Adjusted Stop: {format_price_display(stop_price)} | Price: {format_price_display(current_price)}")
                logger.warning(f"   Stop-Price: %{stop_current_pct*100:.2f} < %{self.MIN_DISTANCE_PCT*100}")
                return self._skip_response(f"{pair}: Stop-Price %{stop_current_pct*100:.2f} < %1.0 minimum")
            
            logger.debug(f"✅ [{pair}] Güvenlik kontrolleri geçti (ADJUSTED): Stop-Price: %{stop_current_pct*100:.2f}")
            
            # ÖN KONTROLLER
            if round(rr_ratio, 2) < MIN_RR_RATIO:
                logger.info(f"⏭️ Pre-filter SKIP [{pair}]: RR {rr_ratio:.2f} < {MIN_RR_RATIO}")
                return {
                    'action': 'SKIP',
                    'confidence': 100,
                    'reasoning': f'RR cok dusuk: {rr_ratio:.2f} < {MIN_RR_RATIO} minimum',
                    'adjustments': {}
                }
            
            # GROK PROMPT hazırla
            score_info = ""
            if confidence_label:
                score_info += f"- Confidence: {confidence_label}\n"
            if strength_score is not None:
                score_info += f"- Strength Score: {strength_score:.2f}\n"
            if python_score:
                score_info += f"- Python Score: {python_score:.2f}/1.0 ({python_score*100:.0f}/100)\n"
            
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
            
            prompt = f"""Aşağıdaki setup'ı değerlendir:

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
- Price: {format_price_display(current_price)}
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

SADECE JSON formatında cevap ver:
{{"action": "ENTER", "confidence": 85, "reasoning": "kısa açıklama max 80 karakter"}}"""

            # GROK API ÇAĞRISI
            logger.debug(f"🧠 [{pair}]: Grok API çağrılıyor...")
            
            response = self.client.chat.completions.create(
                model=Config.GROK_MODEL,
                max_tokens=16000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Response'u parse et
            text_content = response.choices[0].message.content.strip()
            
            logger.debug(f"🧠 [{pair}]: Grok response: {text_content[:100]}...")
            
            # JSON PARSE
            try:
                json_match = re.search(r'\{[^{}]*\}', text_content, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group())
                else:
                    decision = json.loads(text_content)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ [{pair}]: JSON parse failed: {e} | Response: {text_content[:100]}")
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
                    'tp_price': tp_price
                },
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens
            }
            
            # Log
            emoji = "✅" if action == "ENTER" else "⏭️" if action == "SKIP" else "⏸️"
            adj_tag = f" [ADJ:{adjustment_result['adjustment_type']}]" if adjustment_result['adjusted'] else ""
            logger.info(f"🧠 Grok [{pair}] {direction} [{timeframe}]{adj_tag} → {emoji} {action} ({result['confidence']}%) | {result['reasoning'][:50]}...")
            
            logger.info(f"🎯 evaluate_setup() EXIT | {pair} → {action} | tokens: {result['input_tokens']}→{result['output_tokens']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Grok evaluate_setup error: {e}", exc_info=True)
            logger.error(f"🎯 evaluate_setup() EXIT | ERROR: {e}")
            return self._skip_response(f"Grok API error: {str(e)[:50]}")
    
    def _skip_response(self, reason):
        """Standart SKIP response oluştur"""
        logger.debug(f"⏭️ _skip_response() | reason: {reason}")
        return {
            'action': 'SKIP',
            'confidence': 0,
            'reasoning': reason,
            'adjustments': {}
        }


# Backward compatibility alias
ClaudeService = GrokService
