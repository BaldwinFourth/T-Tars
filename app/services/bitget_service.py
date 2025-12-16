# -*- coding: utf-8 -*-
"""
T-TARS Bitget Service v2.2.8
============================
Bitget Exchange Service + Copy Trade API (Direct HTTP)

v2.2.8:
- CHANGED: Marjin hesabı TOTAL BALANCE'a göre (available değil)
- NEW: Kademeli marjin sistemi:
  * Total >= $2000 → %1-2 dinamik ($20-40)
  * $1000 <= Total < $2000 → Sabit $20
  * Total < $1000 → Sabit $10

v2.2.7:
- FIX: Marjin hesabı log'ları netleştirildi (Marjin vs Notional ayrımı)
- FIX: Log'da GERÇEK marjin gösteriliyor
- KEPT: Place order sırasında TP/SL (v2.2.6'dan)

v2.2.6:
- NEW: Place order sırasında TP/SL (presetStopSurplusPrice, presetStopLossPrice)
"""

import ccxt
import time
import requests
import hmac
import hashlib
import base64
import json
import math
from datetime import datetime, timedelta, timezone
import logging
from app.config import Config
from app.strategies.ob_detector import scan_order_blocks
from app.strategies.fvg_detector import scan_fair_value_gaps

TURKEY_TZ = timezone(timedelta(hours=3))
logger = logging.getLogger(__name__)

# Bitget API Base URL
BITGET_API_URL = "https://api.bitget.com"

# TF bazlı geriye bakılacak bar sayısı
TF_LOOKBACK_BARS = {
    '5m': 288,   # 24 saat
    '15m': 96,   # 24 saat
    '30m': 48,   # 24 saat
    '1h': 36,    # 36 saat
    '4h': 9,     # 36 saat
    '3m': 480,   # 24 saat
    '1d': 30,    # 30 gün
}
DEFAULT_LOOKBACK = 20


def get_turkey_time():
    return datetime.now(TURKEY_TZ)


def format_price_string(price):
    """Scientific notation fix"""
    if price is None or price == 0:
        return "0"
    return f"{float(price):.10f}".rstrip('0').rstrip('.')


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


def round_price_to_precision(price, precision):
    """
    Fiyatı belirtilen precision'a yuvarla
    precision=2 → 4299.0685 → 4299.07
    precision=4 → 0.001234 → 0.0012
    """
    if price is None or price == 0:
        return 0
    
    multiplier = 10 ** precision
    return round(price * multiplier) / multiplier


class BitgetService:
    """Bitget Borsa Servisi - v2.2.8 (Total Balance Margin)"""
    
    TIMEFRAME_MAP = {
        '1G': '1d', '1d': '1d',
        '4S': '4h', '4h': '4h',
        '1S': '1h', '1h': '1h',
        '30D': '30m', '30m': '30m',
        '15D': '15m', '15m': '15m',
        '5D': '5m', '5m': '5m',
        '3D': '3m', '3m': '3m'
    }
    
    SKIP_TIMEFRAMES = ['2h', '2S']
    
    def __init__(self):
        self.authenticated = False
        self.exchange = None
        
        # Copy Trade API credentials
        self.api_key = Config.BITGET_API_KEY
        self.secret_key = Config.BITGET_SECRET_KEY
        self.passphrase = Config.BITGET_PASSPHRASE
        
        try:
            config = {
                'apiKey': self.api_key,
                'secret': self.secret_key,
                'password': self.passphrase,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',
                    'defaultSubType': 'linear',
                }
            }
            
            if config['apiKey'] and config['secret']:
                self.authenticated = True
            else:
                logger.warning("⚠️ Bitget Kimlik Bilgileri Eksik")

            self.exchange = ccxt.bitget(config)
            
            if self.authenticated:
                logger.info("🔥 Bitget LIVE MOD")
                self.exchange.load_markets()
                self._configure_account_mode()

            self._market_cache = {}
            logger.info(f"Bitget Servisi v2.2.8 Hazır | Lev:{Config.DEFAULT_LEVERAGE}x | "
                       f"Kademeli Marjin Aktif | TP/SL at Order")

        except Exception as e:
            logger.error(f"Bitget Başlatma Hatası: {e}")

    # ============================================
    # BITGET API SIGNING - v2.2.4
    # ============================================
    
    def _get_timestamp(self):
        """Milliseconds timestamp"""
        return str(int(time.time() * 1000))
    
    def _sign_request(self, timestamp, method, request_path, body=''):
        """
        Bitget API HMAC-SHA256 imzalama
        Sign = Base64(HMAC-SHA256(timestamp + method + requestPath + body, secretKey))
        """
        if body and isinstance(body, dict):
            body = json.dumps(body)
        
        message = timestamp + method.upper() + request_path + (body or '')
        
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method, request_path, body=''):
        """Bitget API headers with signature"""
        timestamp = self._get_timestamp()
        sign = self._sign_request(timestamp, method, request_path, body)
        
        return {
            'ACCESS-KEY': self.api_key,
            'ACCESS-SIGN': sign,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }
    
    def _copy_trade_request(self, method, endpoint, params=None, body=None):
        """Copy Trade API request helper"""
        try:
            url = BITGET_API_URL + endpoint
            
            if method.upper() == 'GET' and params:
                query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
                request_path = endpoint + '?' + query_string
                url = url + '?' + query_string
            else:
                request_path = endpoint
            
            body_str = ''
            if method.upper() == 'POST' and body:
                body_str = json.dumps(body)
            
            headers = self._get_headers(method.upper(), request_path, body_str)
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, data=body_str, timeout=10)
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Copy Trade API timeout: {endpoint}")
            return {'code': 'TIMEOUT', 'msg': 'Request timeout'}
        except Exception as e:
            logger.error(f"❌ Copy Trade API error: {e}")
            return {'code': 'ERROR', 'msg': str(e)}

    # ============================================
    # COPY TRADE API METHODS
    # ============================================
    
    def get_tracking_orders(self, symbol=None):
        """GET /api/v2/copy/mix-trader/order-current-track"""
        self._require_auth()
        try:
            params = {
                'productType': 'USDT-FUTURES',
                'limit': '50'
            }
            
            if symbol:
                bitget_symbol = self._get_bitget_symbol(symbol)
                params['symbol'] = bitget_symbol
            
            logger.info(f"📋 Copy Trade pozisyonları çekiliyor...")
            
            response = self._copy_trade_request(
                'GET',
                '/api/v2/copy/mix-trader/order-current-track',
                params=params
            )
            
            if response and response.get('code') == '00000':
                data = response.get('data')
                if data is None:
                    logger.info(f"✅ Copy Trade: 0 açık pozisyon (data=None)")
                    return {'success': True, 'orders': []}
                
                tracking_list = data.get('trackingList') or []
                logger.info(f"✅ Copy Trade: {len(tracking_list)} açık pozisyon")
                return {'success': True, 'orders': tracking_list}
            else:
                error_msg = response.get('msg', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Copy Trade pozisyon hatası: {error_msg}")
                return {'success': False, 'orders': [], 'error': error_msg}
                
        except Exception as e:
            logger.error(f"❌ Copy Trade API hatası: {e}")
            return {'success': False, 'orders': [], 'error': str(e)}
    
    def modify_tracking_tpsl(self, tracking_no, symbol, tp_price=None, sl_price=None):
        """POST /api/v2/copy/mix-trader/order-modify-tpsl"""
        self._require_auth()
        try:
            bitget_symbol = self._get_bitget_symbol(symbol) if '/' in symbol or ':' in symbol else symbol
            
            precision = self.get_price_precision(symbol)
            
            body = {
                'trackingNo': str(tracking_no),
                'productType': 'USDT-FUTURES',
                'symbol': bitget_symbol,
            }
            
            if tp_price and tp_price > 0:
                tp_rounded = round_price_to_precision(tp_price, precision)
                body['stopSurplusPrice'] = str(tp_rounded)
            
            if sl_price and sl_price > 0:
                sl_rounded = round_price_to_precision(sl_price, precision)
                body['stopLossPrice'] = str(sl_rounded)
            
            logger.info(f"📎 Copy Trade TP/SL: trackingNo={tracking_no} | TP={format_price_display(tp_price)} SL={format_price_display(sl_price)}")
            
            response = self._copy_trade_request(
                'POST',
                '/api/v2/copy/mix-trader/order-modify-tpsl',
                body=body
            )
            
            if response and response.get('code') == '00000':
                logger.info(f"✅ Copy Trade TP/SL eklendi: {tracking_no}")
                return {'success': True, 'response': response}
            else:
                error_msg = response.get('msg', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Copy Trade TP/SL hatası: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            logger.error(f"❌ Copy Trade TP/SL API hatası: {e}")
            return {'success': False, 'error': str(e)}
    
    def close_tracking_order(self, tracking_no=None, symbol=None):
        """POST /api/v2/copy/mix-trader/order-close-positions"""
        self._require_auth()
        try:
            body = {
                'productType': 'USDT-FUTURES',
            }
            
            if tracking_no:
                body['trackingNo'] = str(tracking_no)
            
            if symbol:
                bitget_symbol = self._get_bitget_symbol(symbol) if '/' in symbol else symbol
                body['symbol'] = bitget_symbol
            
            logger.info(f"🔴 Copy Trade pozisyon kapatılıyor: trackingNo={tracking_no} symbol={symbol}")
            
            response = self._copy_trade_request(
                'POST',
                '/api/v2/copy/mix-trader/order-close-positions',
                body=body
            )
            
            if response and response.get('code') == '00000':
                closed = response.get('data', [])
                logger.info(f"✅ Copy Trade pozisyon kapatıldı: {len(closed) if isinstance(closed, list) else 1} adet")
                return {'success': True, 'closed': closed}
            else:
                error_msg = response.get('msg', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Copy Trade kapatma hatası: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            logger.error(f"❌ Copy Trade kapatma API hatası: {e}")
            return {'success': False, 'error': str(e)}
    
    def find_tracking_no_by_symbol(self, symbol, side=None):
        """Symbol'e göre trackingNo bul"""
        try:
            result = self.get_tracking_orders(symbol)
            if not result.get('success'):
                return None
            
            orders = result.get('orders', [])
            if not orders:
                return None
            
            if side:
                for order in orders:
                    if order.get('posSide', '').lower() == side.lower():
                        return order.get('trackingNo')
            
            return orders[0].get('trackingNo') if orders else None
            
        except Exception as e:
            logger.error(f"trackingNo arama hatası: {e}")
            return None

    # ============================================
    # CCXT HELPER METHODS
    # ============================================

    def check_connection(self):
        try:
            self.exchange.fetch_time()
            return True
        except:
            return False

    def _require_auth(self):
        if not self.authenticated:
            raise Exception("❌ Bitget Yetkilendirme Hatası")

    def _configure_account_mode(self):
        try:
            self.exchange.set_position_mode(True)
            logger.info("✅ Bitget: Hedge Mode (double_hold) Aktif")
        except Exception as e:
            logger.info(f"ℹ️ Position Mode: {e}")

    def _normalize_symbol(self, symbol):
        if ':' in symbol:
            return symbol
        symbol = symbol.replace('/', '')
        return f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"

    def _get_bitget_symbol(self, symbol):
        symbol = self._normalize_symbol(symbol)
        return symbol.replace('/USDT:USDT', 'USDT').replace('/', '')

    def get_price_precision(self, symbol):
        """
        Coin için fiyat hassasiyetini al (decimal places)
        XAU → 2, BTC → 1, PEPE → 10
        """
        try:
            symbol = self._normalize_symbol(symbol)
            market = self.exchange.market(symbol)
            
            precision = market.get('precision', {}).get('price')
            
            if precision is None:
                price = self.get_current_price(symbol)
                if price >= 1000:
                    return 2
                elif price >= 1:
                    return 4
                elif price >= 0.001:
                    return 6
                else:
                    return 8
            
            if isinstance(precision, float) and precision < 1:
                return abs(int(math.log10(precision)))
            
            return int(precision)
            
        except Exception as e:
            logger.warning(f"⚠️ Price precision alınamadı ({symbol}): {e}")
            return 4

    def set_leverage(self, symbol, leverage=None):
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            lev = leverage or Config.DEFAULT_LEVERAGE
            
            self.exchange.set_leverage(lev, symbol, params={'marginMode': 'cross', 'holdSide': 'long'})
            self.exchange.set_leverage(lev, symbol, params={'marginMode': 'cross', 'holdSide': 'short'})
            return {'success': True}
        except Exception as e:
            logger.warning(f"Leverage ayarı: {e}")
            return {'success': False, 'error': str(e)}

    # ============================================
    # MARKET DATA METHODS
    # ============================================
    
    def get_current_price(self, ticker):
        try:
            return self.exchange.fetch_ticker(self._normalize_symbol(ticker))['last']
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return 0

    def get_ohlcv(self, ticker, timeframe, limit=100):
        if timeframe in self.SKIP_TIMEFRAMES:
            return []
        try:
            tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)
            return self.exchange.fetch_ohlcv(self._normalize_symbol(ticker), tf, limit=limit)
        except Exception as e:
            logger.error(f"OHLCV error ({ticker}, {timeframe}): {e}")
            return []

    def get_previous_day_candle(self, ticker):
        try:
            ohlcv = self.get_ohlcv(ticker, '1d', 3)
            if len(ohlcv) < 2:
                return {'high': 0, 'low': 0, 'open': 0, 'close': 0, 'candle_type': 'red'}
            
            p = ohlcv[-2]
            candle_type = 'green' if p[4] > p[1] else 'red'
            
            return {
                'open': p[1], 'high': p[2], 'low': p[3], 'close': p[4],
                'volume': p[5], 'candle_type': candle_type,
                'date': datetime.fromtimestamp(p[0]/1000).strftime('%Y-%m-%d')
            }
        except Exception as e:
            logger.error(f"PDC error: {e}")
            return {'high': 0, 'low': 0, 'open': 0, 'close': 0, 'candle_type': 'red'}

    def calculate_atr(self, ticker, timeframe, period=14):
        try:
            ohlcv = self.get_ohlcv(ticker, timeframe, period + 5)
            if len(ohlcv) < period + 1:
                return 0
            
            tr_list = []
            for i in range(1, len(ohlcv)):
                high, low, prev_close = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
            
            return sum(tr_list[-period:]) / period
        except Exception as e:
            logger.error(f"ATR error: {e}")
            return 0

    def calculate_fibonacci(self, ticker):
        try:
            pdc = self.get_previous_day_candle(ticker)
            high, low = pdc['high'], pdc['low']
            diff = high - low
            
            levels = {
                '0.0': low, '23.6': low + (diff * 0.236), '38.2': low + (diff * 0.382),
                '50.0': low + (diff * 0.5), '61.8': low + (diff * 0.618),
                '78.6': low + (diff * 0.786), '100.0': high
            }
            return {'high': high, 'low': low, 'levels': levels}
        except Exception as e:
            logger.error(f"Fibo error: {e}")
            return {'high': 0, 'low': 0, 'levels': {}}

    def analyze_volume_for_tf(self, ohlcv, lookback=20):
        try:
            if len(ohlcv) < lookback + 1:
                return {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}
            
            current_vol = ohlcv[-1][5]
            avg_vol = sum([c[5] for c in ohlcv[-(lookback+1):-1]]) / lookback
            
            if avg_vol == 0:
                return {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}
            
            spike_ratio = current_vol / avg_vol
            spike = spike_ratio >= 1.5
            strength = 'high' if spike_ratio >= 3.0 else ('medium' if spike_ratio >= 2.0 else 'low')
            
            trend = 'stable'
            if len(ohlcv) >= 6:
                recent_vols = [c[5] for c in ohlcv[-5:]]
                if recent_vols[-1] > recent_vols[0]:
                    trend = 'increasing'
                elif recent_vols[-1] < recent_vols[0]:
                    trend = 'decreasing'
            
            return {'spike': spike, 'spike_ratio': round(spike_ratio, 2), 'strength': strength, 'trend': trend}
        except Exception as e:
            logger.error(f"Volume analysis error: {e}")
            return {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}

    def get_complete_analysis_data(self, ticker):
        try:
            symbol = self._normalize_symbol(ticker)
            coin_name = ticker.replace('/USDT:USDT', '').replace('/USDT', '').replace('USDT', '')
            
            logger.info(f"📊 {coin_name}: Veri toplama başladı...")
            
            current_price = self.get_current_price(symbol)
            if current_price == 0:
                logger.error(f"❌ {coin_name}: Fiyat alınamadı")
                return None
            
            now = get_turkey_time()
            pdc = self.get_previous_day_candle(symbol)
            fibo = self.calculate_fibonacci(symbol)
            
            atr_data, volume_data, order_blocks, fair_value_gaps = {}, {}, {}, {}
            
            for tf in Config.TIMEFRAMES:
                if tf in self.SKIP_TIMEFRAMES:
                    continue
                try:
                    lookback = TF_LOOKBACK_BARS.get(tf, DEFAULT_LOOKBACK)
                    ohlcv = self.get_ohlcv(symbol, tf, lookback)
                    if not ohlcv or len(ohlcv) < 10:
                        atr_data[tf] = 0
                        volume_data[tf] = {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}
                        order_blocks[tf], fair_value_gaps[tf] = [], []
                        continue
                    
                    atr_data[tf] = self.calculate_atr(symbol, tf, 14)
                    volume_data[tf] = self.analyze_volume_for_tf(ohlcv, 20)
                    order_blocks[tf] = scan_order_blocks(ohlcv, tf)
                    fair_value_gaps[tf] = scan_fair_value_gaps(ohlcv, tf)
                except Exception as e:
                    logger.error(f"❌ {coin_name} {tf} error: {e}")
                    atr_data[tf] = 0
                    volume_data[tf] = {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}
                    order_blocks[tf], fair_value_gaps[tf] = [], []
            
            total_obs = sum(len(obs) for obs in order_blocks.values())
            total_fvgs = sum(len(fvgs) for fvgs in fair_value_gaps.values())
            logger.info(f"✅ {coin_name}: Price={format_price_display(current_price)}, OBs={total_obs}, FVGs={total_fvgs}")
            
            return {
                'current_price': current_price,
                'current_date': now.strftime('%Y-%m-%d'),
                'current_time': now.strftime('%H:%M:%S'),
                'previous_day': pdc,
                'fibonacci': fibo,
                'atr': atr_data,
                'volume': volume_data,
                'smart_money': {'order_blocks': order_blocks, 'fair_value_gaps': fair_value_gaps}
            }
        except Exception as e:
            logger.error(f"❌ Complete analysis error ({ticker}): {e}")
            return None

    # ============================================
    # ORDER METHODS - v2.2.8 (Total Balance Margin)
    # ============================================

    def calculate_contracts(self, symbol, notional_usd, current_price):
        """
        v2.2.8: Kontrat hesabı
        
        notional_usd: Kaldıraçlı pozisyon değeri (marjin * leverage)
        
        Returns: kontrat sayısı
        """
        try:
            market = self.exchange.market(symbol)
            contract_value = market.get('contractSize', 1)
            
            if current_price == 0:
                return 0
            
            notional_per_contract = contract_value * current_price
            contracts_needed = notional_usd / notional_per_contract
            contracts_final = max(1, round(contracts_needed))
            
            logger.info(f"🧮 Kontrat: ${notional_usd:.2f} / (${notional_per_contract:.4f}/kontrat) = {contracts_final} kontrat")
            return int(contracts_final)
        except Exception as e:
            logger.error(f"Kontrat Hesaplama Hatası: {e}")
            return 1

    def calculate_position_size(self, entry_price, stop_price):
        """
        v2.2.8: Pozisyon boyutu hesaplama - TOTAL BALANCE BAZLI
        
        Kademeli Marjin Sistemi:
        - Total >= $2000 → %1-2 dinamik ($20-40)
        - $1000 <= Total < $2000 → Sabit $20
        - Total < $1000 → Sabit $10
        
        Returns: notional_value (kaldıraçlı pozisyon değeri)
        """
        try:
            balance = self.get_balance()
            
            # v2.2.8: TOTAL balance kullan (available değil!)
            total_balance = float(balance.get('total', 0)) if balance.get('success') else 500.0
            available_balance = float(balance.get('free', 0)) if balance.get('success') else 500.0
            
            # Stop mesafesi hesapla
            stop_distance = abs(entry_price - stop_price)
            stop_distance_pct = stop_distance / entry_price if entry_price > 0 else 0.01
            
            # Stop mesafesi clamp
            original_stop_pct = stop_distance_pct
            stop_distance_pct = max(Config.STOP_DISTANCE_MIN, min(stop_distance_pct, Config.STOP_DISTANCE_MAX))
            
            if original_stop_pct != stop_distance_pct:
                logger.info(f"📏 Stop mesafesi clamp: {original_stop_pct:.4%} → {stop_distance_pct:.4%}")
            
            # ============================================
            # v2.2.8: KADEMELİ MARJİN SİSTEMİ
            # ============================================
            
            if total_balance >= 2000:
                # $2000+ → %1-2 dinamik
                min_margin = total_balance * (Config.MARGIN_MIN_PERCENT / 100)  # %1
                max_margin = total_balance * (Config.MARGIN_MAX_PERCENT / 100)  # %2
                
                # Risk bazlı hesaplama
                risk_percent = Config.RISK_PER_TRADE / 100
                risk_amount = total_balance * risk_percent
                calculated_position = risk_amount / stop_distance_pct
                calculated_margin = calculated_position / Config.DEFAULT_LEVERAGE
                
                # Marjin clamp
                final_margin = max(min_margin, min(calculated_margin, max_margin))
                margin_mode = f"Dinamik %{Config.MARGIN_MIN_PERCENT}-{Config.MARGIN_MAX_PERCENT}"
                
            elif total_balance >= 1000:
                # $1000-1999 → Sabit $20
                final_margin = 20.0
                margin_mode = "Sabit $20"
                
            else:
                # $0-999 → Sabit $10
                final_margin = 10.0
                margin_mode = "Sabit $10"
            
            # Final notional (kaldıraçlı değer)
            final_notional = final_margin * Config.DEFAULT_LEVERAGE
            
            # v2.2.8: Detaylı log
            logger.info(f"💰 Pozisyon Hesabı (v2.2.8):")
            logger.info(f"   Total Balance: ${total_balance:.2f} | Available: ${available_balance:.2f}")
            logger.info(f"   Marjin Modu: {margin_mode}")
            logger.info(f"   Final Marjin: ${final_margin:.2f}")
            logger.info(f"   Notional (Kaldıraçlı): ${final_notional:.2f} ({Config.DEFAULT_LEVERAGE}x)")
            
            return final_notional
            
        except Exception as e:
            logger.error(f"Position size hesaplama hatası: {e}")
            return 100.0

    def place_order_with_tp_sl(self, symbol, side, entry_price, stop_price, tp_price=None):
        """
        v2.2.8: Bitget Order with TP/SL at Place Time
        
        presetStopSurplusPrice → Take Profit
        presetStopLossPrice → Stop Loss
        
        Artık sonradan TP/SL eklemeye gerek yok!
        """
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            coin_name = symbol.replace('/USDT:USDT', '')
            
            self.set_leverage(symbol)
            
            # v2.2.8: Notional value hesapla (kaldıraçlı) - TOTAL BALANCE BAZLI
            notional_usd = self.calculate_position_size(entry_price, stop_price)
            contracts = self.calculate_contracts(symbol, notional_usd, entry_price)
            
            if contracts < 1:
                return {'success': False, 'error': 'Kontrat sayısı 0'}
            
            hold_side = 'long' if side.lower() == 'buy' else 'short'
            
            # v2.2.8: Gerçek marjin hesapla (log için)
            actual_margin = notional_usd / Config.DEFAULT_LEVERAGE
            
            # v2.2.6: Price precision al
            precision = self.get_price_precision(symbol)
            
            # v2.2.6: TP/SL'yi doğru precision'a yuvarla
            tp_rounded = round_price_to_precision(tp_price, precision) if tp_price and tp_price > 0 else None
            sl_rounded = round_price_to_precision(stop_price, precision) if stop_price and stop_price > 0 else None
            
            # v2.2.6: PARAMS with TP/SL at order time
            params = {
                'marginMode': 'cross',
                'holdSide': hold_side,
                'tradeSide': 'open',
            }
            
            # v2.2.6: Add TP/SL to params
            if tp_rounded and tp_rounded > 0:
                params['presetStopSurplusPrice'] = str(tp_rounded)
            
            if sl_rounded and sl_rounded > 0:
                params['presetStopLossPrice'] = str(sl_rounded)
            
            # v2.2.8: Detaylı emir log'u
            logger.info(f"🚀 EMİR AÇILIYOR:")
            logger.info(f"   {coin_name} | {side.upper()} {hold_side.upper()}")
            logger.info(f"   Kontrat: {contracts}")
            logger.info(f"   Entry: {format_price_display(entry_price)}")
            logger.info(f"   TP: {format_price_display(tp_rounded)} | SL: {format_price_display(sl_rounded)}")
            logger.info(f"   Marjin: ${actual_margin:.2f} | Notional: ${notional_usd:.2f}")
            
            order = self.exchange.create_order(
                symbol=symbol, type='limit', side=side,
                amount=contracts, price=entry_price, params=params
            )
            
            order_id = order['id']
            logger.info(f"✅ EMİR BAŞARILI: {order_id}")
            
            return {
                'success': True,
                'order_id': order_id,
                'contracts': contracts,
                'entry_price': entry_price,
                'margin_usd': actual_margin,      # v2.2.8: Gerçek marjin
                'position_usd': notional_usd,     # Notional (kaldıraçlı)
                'tp_price': tp_rounded,
                'sl_price': sl_rounded,
                'tp_sl_preset': True
            }
            
        except Exception as e:
            logger.error(f"❌ Bitget EMİR HATASI: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_order(self, order_id, symbol):
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            return {'success': True, 'raw': self.exchange.cancel_order(order_id, symbol)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def cancel_all_orders(self, symbol=None):
        self._require_auth()
        try:
            if symbol:
                symbol = self._normalize_symbol(symbol)
                orders = self.exchange.cancel_all_orders(symbol)
            else:
                orders = self.exchange.cancel_all_orders()
            return {'success': True, 'cancelled': len(orders) if orders else 0}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def close_position(self, symbol, side=None):
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            positions = self.get_positions(symbol)
            if not positions:
                return {'success': False, 'error': 'Pozisyon yok'}
            
            target_pos = positions[0]
            if side:
                for p in positions:
                    if p['side'] == side.lower():
                        target_pos = p
                        break
            
            close_side = 'sell' if target_pos['side'] == 'long' else 'buy'
            params = {'marginMode': 'cross', 'holdSide': target_pos['side'], 'tradeSide': 'close', 'reduceOnly': True}
            
            order = self.exchange.create_order(
                symbol=symbol, type='market', side=close_side,
                amount=float(target_pos['contracts']), params=params
            )
            return {'success': True, 'order_id': order['id']}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_positions(self, symbol=None):
        self._require_auth()
        try:
            if symbol:
                symbol = self._normalize_symbol(symbol)
            raw_positions = self.exchange.fetch_positions([symbol] if symbol else None)
            
            clean_positions = []
            for p in raw_positions:
                contracts = float(p.get('contracts', 0))
                if contracts > 0:
                    clean_positions.append({
                        'symbol': p['symbol'],
                        'side': p.get('side', 'long'),
                        'contracts': contracts,
                        'entry_price': p.get('entryPrice', 0),
                        'unrealized_pnl': p.get('unrealizedPnl', 0),
                        'leverage': p.get('leverage', Config.DEFAULT_LEVERAGE)
                    })
            return clean_positions
        except Exception as e:
            logger.error(f"Positions fetch error: {e}")
            return []

    def get_open_orders(self, symbol=None):
        self._require_auth()
        try:
            if symbol:
                symbol = self._normalize_symbol(symbol)
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"Open orders fetch error: {e}")
            return []

    def get_balance(self):
        self._require_auth()
        try:
            bal = self.exchange.fetch_balance()
            usdt_balance = bal.get('USDT', {})
            return {'success': True, 'total': usdt_balance.get('total', 0), 'free': usdt_balance.get('free', 0)}
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return {'success': False, 'total': 0, 'free': 0}
