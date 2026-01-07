# -*- coding: utf-8 -*-
"""
T-TARS Grok Service v2.5.3
==============================
Grok 4.1 Fast Reasoning API wrapper for market analysis and setup evaluation.

v2.5.3:
- NEW: Claude → Grok 4.1 Fast Reasoning geçişi
- CHANGED: Anthropic API → xAI API (OpenAI-compatible)
- Model: grok-4-1-fast-reasoning (reasoning enabled)

v2.5.2:
- CHANGED: MIN_DISTANCE_PCT = 0.01 (%1.0) - Stop mesafesi artırıldı
- CHANGED: STOP_MIN_PCT = 1.0 (Config'den bağımsız hardcode)
- Win rate artırmak için daha geniş stop
"""

import requests
import json
import re
import logging
from app.config import Config
from app.strategies.calculators import (
    VOLUME_TRADEABLE_MIN,
    VOLUME_LOW,
    VOLUME_GOOD,
    VOLUME_EXCELLENT,
    MIN_RR_RATIO,
    TP_MULTIPLIER
)

logger = logging.getLogger(__name__)

# Grok API Endpoint
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

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
    """Grok 4.1 Fast Reasoning API Service - v2.5.3 (AI Decision Engine + %1.0 Stop)"""
    
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
    
    # v2.5.2: Minimum mesafe sabiti - %0.8 → %1.0
    MIN_DISTANCE_PCT = 0.01  # %1.0 - Stop-Entry ve Stop-Current için minimum
    
    def __init__(self):
        self.api_key = Config.XAI_API_KEY
        self.model = Config.GROK_MODEL
        
        # v2.5.2: %1.0 hardcode (Config'den bağımsız)
        self.STOP_MIN_PCT = 1.0         # %1.0 minimum stop mesafesi
        self.STOP_ADJUST_MAX = 2.5      # %2.5 maksimum stop mesafesi
        
        # v2.5.3: Thinking budget (Grok reasoning için)
        self.thinking_budget = Config.THINKING_BUDGET
        
        logger.info(f"✅ Grok Service v2.5.3 initialized: {self.model} | "
                   f"Reasoning: enabled | "
                   f"Stop: {self.STOP_MIN_PCT}%-{self.STOP_ADJUST_MAX}% | "
                   f"MIN_RR: {MIN_RR_RATIO} | TP_MULT: {TP_MULTIPLIER}")
    
    def _call_grok_api(self, messages, max_tokens=8000):
        """
        Grok API çağrısı (OpenAI-compatible format)
        
        Args:
            messages: List of message dicts [{"role": "user/system/assistant", "content": "..."}]
            max_tokens: Maximum response tokens
            
        Returns:
            dict: {"text": str, "input_tokens": int, "output_tokens": int}
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            
            response = requests.post(
                GROK_API_URL,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Grok API error: {response.status_code} - {response.text[:200]}")
                raise Exception(f"Grok API error: {response.status_code}")
            
            data = response.json()
            
            # Response parse
            text_content = ""
            if data.get("choices") and len(data["choices"]) > 0:
                text_content = data["choices"][0].get("message", {}).get("content", "")
            
            # Token usage
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            
            return {
                "text": text_content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ Grok API timeout")
            raise Exception("Grok API timeout")
        except Exception as e:
            logger.error(f"❌ Grok API call error: {e}")
            raise
    
    def analyze(self, prompt):
        """
        Genel analiz yap (eski fonksiyon - backward compat)
        v2.5.3: Grok API kullanıyor
        """
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
            
            result = self._call_grok_api(messages, max_tokens=16000)
            
            logger.info(f"Analysis complete: {result['input_tokens']}→{result['output_tokens']} tokens")
            return result
            
        except Exception as e:
            logger.error(f"Grok API error: {e}")
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
        # KURAL 1: Stop < 1.0% → EXPAND
        # ============================================
        if stop_pct < self.STOP_MIN_PCT:
            new_stop_pct = self.STOP_MIN_PCT
            new_stop_distance = entry * (new_stop_pct / 100)
            
            if is_long:
                new_stop = entry - new_stop_distance
            else:
                new_stop = entry + new_stop_distance
            
            # TP'yi orantılı uzat (R:R koru)
            new_tp_distance = new_stop_distance * original_rr
            if is_long:
                new_tp = entry + new_tp_distance
            else:
                new_tp = entry - new_tp_distance
            
            result['stop_price'] = new_stop
            result['tp_price'] = new_tp
            result['adjusted'] = True
            result['adjustment_type'] = 'EXPAND'
            result['new_stop_pct'] = round(new_stop_pct, 2)
            result['new_rr'] = round(original_rr, 2)  # R:R korundu
            
            logger.info(f"📏 Stop EXPAND: %{stop_pct:.2f} → %{new_stop_pct:.2f} | R:R korundu: {original_rr:.2f}")
            return result
        
        # ============================================
        # KURAL 2: Stop 1.0-1.5% → İDEAL (değişiklik yok)
        # ============================================
        if stop_pct <= self.STOP_IDEAL_MAX:
            logger.debug(f"✅ Stop ideal: %{stop_pct:.2f} (1.0-1.5% arası)")
            return result
        
        # ============================================
        # KURAL 3: Stop 1.5-2.0% → SHRINK to 1.5%
        # ============================================
        if stop_pct <= 2.0:
            new_stop_pct = self.STOP_IDEAL_MAX  # 1.5%
            new_stop_distance = entry * (new_stop_pct / 100)
            
            if is_long:
                new_stop = entry - new_stop_distance
            else:
                new_stop = entry + new_stop_distance
            
            # TP'yi orantılı kısalt (R:R koru)
            new_tp_distance = new_stop_distance * original_rr
            if is_long:
                new_tp = entry + new_tp_distance
            else:
                new_tp = entry - new_tp_distance
            
            result['stop_price'] = new_stop
            result['tp_price'] = new_tp
            result['adjusted'] = True
            result['adjustment_type'] = 'SHRINK'
            result['new_stop_pct'] = round(new_stop_pct, 2)
            result['new_rr'] = round(original_rr, 2)
            
            logger.info(f"📏 Stop SHRINK: %{stop_pct:.2f} → %{new_stop_pct:.2f} | R:R korundu: {original_rr:.2f}")
            return result
        
        # ============================================
        # KURAL 4: Stop 2.0-2.5% → AGGRESSIVE (1.8%, 3R)
        # ============================================
        new_stop_pct = self.STOP_AGGRESSIVE_TARGET  # 1.8%
        new_stop_distance = entry * (new_stop_pct / 100)
        
        if is_long:
            new_stop = entry - new_stop_distance
        else:
            new_stop = entry + new_stop_distance
        
        # TP'yi 3R yap
        new_tp_distance = new_stop_distance * self.AGGRESSIVE_RR
        if is_long:
            new_tp = entry + new_tp_distance
        else:
            new_tp = entry - new_tp_distance
        
        result['stop_price'] = new_stop
        result['tp_price'] = new_tp
        result['adjusted'] = True
        result['adjustment_type'] = 'AGGRESSIVE'
        result['new_stop_pct'] = round(new_stop_pct, 2)
        result['new_rr'] = round(self.AGGRESSIVE_RR, 2)
        
        logger.info(f"📏 Stop AGGRESSIVE: %{stop_pct:.2f} → %{new_stop_pct:.2f} | R:R: {original_rr:.2f} → {self.AGGRESSIVE_RR}")
        return result
    
    def evaluate_setup(self, setup_data, market_data, python_score=None, confidence_label=None, strength_score=None):
        """
        Setup değerlendir ve ENTER/SKIP/WAIT kararı ver.
        v2.5.3: Grok 4.1 Fast Reasoning kullanıyor
        
        Args:
            setup_data: Setup bilgileri (pair, direction, entry, stop, tp, etc.)
            market_data: Market verileri (PDC, ATR, volume, OB/FVG, etc.)
            python_score: Python tarafından hesaplanan skor (0-1)
            confidence_label: Güven etiketi (HIGH/MEDIUM/LOW)
            strength_score: Güç skoru
            
        Returns:
            dict: {'action': str, 'confidence': int, 'reasoning': str, 'adjustments': dict}
        """
        try:
            # Setup verilerini çıkar
            pair = setup_data.get('pair', 'UNKNOWN')
            direction = setup_data.get('direction', 'LONG').upper()
            setup_type = setup_data.get('type', 'UNKNOWN')
            timeframe = setup_data.get('timeframe', '15m')
            
            entry_price = float(setup_data.get('entry_price', 0))
            stop_price = float(setup_data.get('stop_price', 0))
            tp_price = float(setup_data.get('tp_price', 0))
            
            current_price = float(market_data.get('current_price', 0))
            
            # TEMEL KONTROLLER
            if entry_price <= 0 or stop_price <= 0:
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Invalid prices")
                return self._skip_response(f"{pair}: Entry veya Stop 0")
            
            # YÖNLÜ SANITY CHECK
            is_long = direction == 'LONG'
            
            # Entry-Current mesafe kontrolü
            entry_current_pct = abs(entry_price - current_price) / current_price if current_price > 0 else 0
            if entry_current_pct > 0.05:  # %5'ten uzaksa
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Entry-Current çok uzak (%{entry_current_pct*100:.2f})")
                return self._skip_response(f"{pair}: Entry current'tan %{entry_current_pct*100:.1f} uzakta")
            
            # Yön kontrolü
            if is_long:
                if stop_price >= entry_price:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: LONG Stop >= Entry")
                    return self._skip_response(f"{pair}: LONG Stop >= Entry")
                if current_price <= stop_price:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: LONG Current <= Stop (zaten SL'de)")
                    return self._skip_response(f"{pair}: Current zaten stop altında")
            else:
                if stop_price <= entry_price:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: SHORT Stop <= Entry")
                    return self._skip_response(f"{pair}: SHORT Stop <= Entry")
                if current_price >= stop_price:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: SHORT Current >= Stop")
                    return self._skip_response(f"{pair}: Current zaten stop üstünde")
            
            # LIMIT ORDER GÜVENLİK KONTROLÜ
            stop_entry_pct = abs(stop_price - entry_price) / entry_price if entry_price > 0 else 0
            if stop_entry_pct < self.MIN_DISTANCE_PCT:
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Stop-Entry mesafesi çok küçük!")
                logger.warning(f"   Stop: {format_price_display(stop_price)} | Entry: {format_price_display(entry_price)}")
                logger.warning(f"   Stop-Entry: %{stop_entry_pct*100:.2f} < %{self.MIN_DISTANCE_PCT*100}")
                return self._skip_response(f"{pair}: Stop-Entry %{stop_entry_pct*100:.2f} < %1.0 minimum")
            
            # LIMIT PRICE SANITY CHECK
            if is_long:
                if entry_price > current_price * 1.02:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: LONG Entry fiyat çok yüksek!")
                    logger.warning(f"   Entry({format_price_display(entry_price)}) > Current({format_price_display(current_price)}) * 1.02")
                    return self._skip_response(f"{pair}: LONG Entry current'tan %2+ yüksek")
            else:
                if entry_price < current_price * 0.98:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: SHORT Entry fiyat çok düşük!")
                    logger.warning(f"   Entry({format_price_display(entry_price)}) < Current({format_price_display(current_price)}) * 0.98")
                    return self._skip_response(f"{pair}: SHORT Entry current'tan %2+ düşük")
            
            # ORDER YÖN KONTROLÜ
            if is_long:
                if entry_price >= stop_price:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: LONG Entry >= Stop - Geçersiz!")
                    return self._skip_response(f"{pair}: LONG Entry >= Stop")
                if current_price <= entry_price:
                    pass
                else:
                    logger.warning(f"⚠️ [{pair}]: LONG Current({format_price_display(current_price)}) > Entry({format_price_display(entry_price)})")
                    logger.warning(f"   Stop({format_price_display(stop_price)}) < Entry({format_price_display(entry_price)}) < Current({format_price_display(current_price)}) olmalı")
                    if stop_price >= entry_price:
                        return self._skip_response(f"{pair}: LONG Stop >= Entry")
                    if current_price <= stop_price:
                        return self._skip_response(f"{pair}: LONG Current <= Stop, limit hemen fill olur")
            else:
                if entry_price <= stop_price:
                    logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: SHORT Entry <= Stop - Geçersiz!")
                    return self._skip_response(f"{pair}: SHORT Entry <= Stop")
                if current_price >= entry_price:
                    pass
                else:
                    logger.warning(f"⚠️ [{pair}]: SHORT Current({format_price_display(current_price)}) < Entry({format_price_display(entry_price)})")
                    logger.warning(f"   Current({format_price_display(current_price)}) < Entry({format_price_display(entry_price)}) < Stop({format_price_display(stop_price)}) olmalı")
                    if entry_price >= stop_price:
                        return self._skip_response(f"{pair}: SHORT Entry >= Stop")
                    if current_price >= entry_price:
                        return self._skip_response(f"{pair}: SHORT Current >= Entry, limit hemen fill olur")
            
            # TP Sanity Check
            if is_long and tp_price <= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP ({tp_price}) <= Entry ({entry_price}) - LONG için geçersiz!")
                return self._skip_response(f"{pair}: TP entry'den düşük veya eşit")
            if not is_long and tp_price >= entry_price:
                logger.error(f"❌ SKIP [{pair}]: TP ({tp_price}) >= Entry ({entry_price}) - SHORT için geçersiz!")
                return self._skip_response(f"{pair}: TP entry'den yüksek veya eşit")
            
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
            
            # STOP-CURRENT KONTROLÜ (ADJUSTED değerlerle!)
            stop_current_pct = abs(stop_price - current_price) / current_price if current_price > 0 else 0
            if stop_current_pct < self.MIN_DISTANCE_PCT:
                logger.warning(f"⏭️ Pre-filter SKIP [{pair}]: Stop-Current mesafesi çok küçük (ADJUSTED)!")
                logger.warning(f"   Adjusted Stop: {format_price_display(stop_price)} | Current: {format_price_display(current_price)}")
                logger.warning(f"   Stop-Current: %{stop_current_pct*100:.2f} < %{self.MIN_DISTANCE_PCT*100}")
                return self._skip_response(f"{pair}: Stop-Current %{stop_current_pct*100:.2f} < %1.0 minimum")
            
            logger.debug(f"✅ [{pair}] Güvenlik kontrolleri geçti (ADJUSTED): Stop-Current: %{stop_current_pct*100:.2f}")
            
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

SADECE JSON formatında cevap ver:
{{"action": "ENTER", "confidence": 85, "reasoning": "kısa açıklama max 80 karakter"}}"""

            # GROK API ÇAĞRISI
            logger.debug(f"🧠 [{pair}]: Grok API çağrılıyor (reasoning: enabled)...")
            
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
            
            response = self._call_grok_api(messages, max_tokens=8000)
            text_content = response.get("text", "").strip()
            
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
                'input_tokens': response.get('input_tokens', 0),
                'output_tokens': response.get('output_tokens', 0)
            }
            
            # Log
            emoji = "✅" if action == "ENTER" else "⏭️" if action == "SKIP" else "⏸️"
            adj_tag = f" [ADJ:{adjustment_result['adjustment_type']}]" if adjustment_result['adjusted'] else ""
            logger.info(f"🧠 Grok [{pair}] {direction} [{timeframe}]{adj_tag} → {emoji} {action} ({result['confidence']}%) | {result['reasoning'][:50]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Grok evaluate_setup error: {e}", exc_info=True)
            return self._skip_response(f"Grok API error: {str(e)[:50]}")
    
    def _skip_response(self, reason):
        """Standart SKIP response oluştur"""
        return {
            'action': 'SKIP',
            'confidence': 0,
            'reasoning': reason,
            'adjustments': {}
        }


# Backward compatibility alias
ClaudeService = GrokService
