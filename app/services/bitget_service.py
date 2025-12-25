# -*- coding: utf-8 -*-
"""
T-TARS Bitget Service v2.4.7
============================
Bitget Exchange Service + Copy Trade API (Direct HTTP)

v2.4.7:
- FIX: get_pnl_history() '_signed_request' hatası düzeltildi
- CHANGED: order-history-track endpoint kullanılıyor (Copy Trade)
- CHANGED: achievedPL field'ından gerçek PnL hesaplanıyor

v2.4.6:
- NEW: get_pnl_history(days) - history-position'dan gerçek PnL hesaplama
- CHANGED: get_trade_history_stats() - Günlük/Haftalık/Aylık PnL artık history-position'dan
- FIX: lastWeekProfitList/lastMonthProfitList boş geliyordu (profit share, trade PnL değil)

v2.4.5:
- NEW: get_trade_history_stats() - Bitget history'den WIN/LOSS istatistikleri
- /score komutu artik GCS yerine Bitget API'den veri cekiyor

v2.4.4:
- NEW: get_order_history_track() - Kapanmış pozisyon geçmişi
- NEW: get_closed_position_pnl() - PnL ve WIN/LOSS bilgisi
- Endpoint: /api/v2/copy/mix-trader/order-history-track

v2.4.3:
- FIX: TP/SL preset parametreleri duzeltildi (Bitget API doc)
- CHANGED: stopSurplus/stopLoss → presetStopSurplusPrice/presetStopLossPrice

v2.4.2:
- FIX: Hedge mode params duzeltildi (Bitget API doc'a gore)
- CHANGED: holdSide kaldirildi, tradeSide='open'/'close' kullaniliyor
- side=buy (LONG), side=sell (SHORT), tradeSide=open/close

v2.4.1:
- FIX: Hedge mode icin holdSide parametresi eklendi
- FIX: "unilateral position" hatasi (40774) duzeltildi

v2.4.0:
- FIX: Copy Trade API endpoint duzeltildi (yanlıs endpoint -> CCXT create_order)
- CHANGED: Normal CCXT create_order kullaniliyor, trackingNo sonradan sorgulanıyor
- NEW: daily_ohlcv eklendi (PDC bias + Doji kontrolu icin)
- CHANGED: scan_order_blocks/scan_fair_value_gaps atr ve current_price parametreleri eklendi

v2.3.14:
- NEW: place_copy_trade_order() - Copy Trade API ile order aç
- CHANGED: place_order_with_tp_sl() → Copy Trade API kullanıyor
- NEW: trackingNo response'da döndürülüyor
- FIXED: trackingNo:None sorunu çözüldü

v2.3.13:
- NEW: close_position() → Limit order desteği (market yerine)
- NEW: Config.CLOSE_ORDER_TYPE ('limit' / 'market')
- NEW: Config.CLOSE_SLIPPAGE_PCT (%0.2 default)
- Slippage: LONG close → price * (1 - slippage), SHORT close → price * (1 + slippage)

v2.3.8:
- CHANGED: MARKET_CACHE_TTL → Config.MARKET_CACHE_TTL (DRY)
- CHANGED: Volume spike/strength thresholds → calculators.py'den import (DRY)
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
from app.strategies.calculators import (
    VOLUME_SPIKE_FLAG,
    VOLUME_STRENGTH_HIGH,
    VOLUME_STRENGTH_MEDIUM
)

TURKEY_TZ = timezone(timedelta(hours=3))
logger = logging.getLogger(__name__)

BITGET_API_URL = "https://api.bitget.com"

TF_LOOKBACK_BARS = {
    '5m': 288, '15m': 96, '30m': 48, '1h': 36,
    '4h': 9, '3m': 480, '1d': 30,
}
DEFAULT_LOOKBACK = 100


def get_turkey_time():
    return datetime.now(TURKEY_TZ)


def format_price_string(price):
    if price is None or price == 0:
        return "0"
    return f"{float(price):.10f}".rstrip('0').rstrip('.')


def format_price_display(price):
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
    if price is None or price == 0:
        return 0
    multiplier = 10 ** precision
    return round(price * multiplier) / multiplier


class BitgetService:
    """Bitget Borsa Servisi - v2.4.5 (Hedge Mode + Copy Trade API + Trade Stats)"""
    
    TIMEFRAME_MAP = {
        '1G': '1d', '1d': '1d', '4S': '4h', '4h': '4h',
        '1S': '1h', '1h': '1h', '30D': '30m', '30m': '30m',
        '15D': '15m', '15m': '15m', '5D': '5m', '5m': '5m',
        '3D': '3m', '3m': '3m'
    }
    
    SKIP_TIMEFRAMES = ['2h', '2S']
    
    def __init__(self):
        self.authenticated = False
        self.exchange = None
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
                    'defaultSubType': 'linear'
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
            logger.info(f"Bitget Servisi v2.4.5 Hazır | Lev:{Config.DEFAULT_LEVERAGE}x | "
                       f"Close:{Config.CLOSE_ORDER_TYPE} | Copy Trade API: Active")

        except Exception as e:
            logger.error(f"Bitget Başlatma Hatası: {e}")

    def _get_timestamp(self):
        return str(int(time.time() * 1000))
    
    def _sign_request(self, timestamp, method, request_path, body=''):
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

    def get_tracking_orders(self, symbol=None):
        self._require_auth()
        try:
            params = {'productType': 'USDT-FUTURES', 'limit': '50'}
            if symbol:
                params['symbol'] = self._get_bitget_symbol(symbol)
            
            logger.info(f"📋 Copy Trade pozisyonları çekiliyor...")
            response = self._copy_trade_request('GET', '/api/v2/copy/mix-trader/order-current-track', params=params)
            
            if response and response.get('code') == '00000':
                data = response.get('data')
                if data is None:
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
        self._require_auth()
        try:
            bitget_symbol = self._get_bitget_symbol(symbol) if '/' in symbol or ':' in symbol else symbol
            precision = self.get_price_precision(symbol)
            
            body = {'trackingNo': str(tracking_no), 'productType': 'USDT-FUTURES', 'symbol': bitget_symbol}
            
            if tp_price and tp_price > 0:
                body['stopSurplusPrice'] = str(round_price_to_precision(tp_price, precision))
            if sl_price and sl_price > 0:
                body['stopLossPrice'] = str(round_price_to_precision(sl_price, precision))
            
            logger.info(f"📎 Copy Trade TP/SL: trackingNo={tracking_no}")
            response = self._copy_trade_request('POST', '/api/v2/copy/mix-trader/order-modify-tpsl', body=body)
            
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
        self._require_auth()
        try:
            body = {'productType': 'USDT-FUTURES'}
            if tracking_no:
                body['trackingNo'] = str(tracking_no)
            if symbol:
                body['symbol'] = self._get_bitget_symbol(symbol) if '/' in symbol else symbol
            
            logger.info(f"🔴 Copy Trade pozisyon kapatılıyor: trackingNo={tracking_no}")
            response = self._copy_trade_request('POST', '/api/v2/copy/mix-trader/order-close-positions', body=body)
            
            if response and response.get('code') == '00000':
                closed = response.get('data', [])
                logger.info(f"✅ Copy Trade pozisyon kapatıldı")
                return {'success': True, 'closed': closed}
            else:
                error_msg = response.get('msg', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Copy Trade kapatma hatası: {error_msg}")
                return {'success': False, 'error': error_msg}
        except Exception as e:
            logger.error(f"❌ Copy Trade kapatma API hatası: {e}")
            return {'success': False, 'error': str(e)}
    
    def find_tracking_no_by_symbol(self, symbol, side=None):
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

    def get_order_history_track(self, tracking_no=None, symbol=None, limit=20):
        """
        v2.4.4: Kapanmış Copy Trade pozisyonlarının geçmişi
        
        Endpoint: /api/v2/copy/mix-trader/order-history-track
        
        Returns:
            dict: {
                'success': True/False,
                'orders': [{trackingNo, symbol, posSide, achievedProfits, ...}]
            }
        """
        self._require_auth()
        try:
            params = {
                'productType': 'USDT-FUTURES',
                'pageSize': str(limit)
            }
            
            if symbol:
                params['symbol'] = self._get_bitget_symbol(symbol)
            
            logger.info(f"📋 Copy Trade history çekiliyor...")
            response = self._copy_trade_request('GET', '/api/v2/copy/mix-trader/order-history-track', params=params)
            
            if response and response.get('code') == '00000':
                data = response.get('data')
                if data is None:
                    return {'success': True, 'orders': []}
                
                tracking_list = data.get('trackingList') or []
                logger.info(f"✅ Copy Trade history: {len(tracking_list)} kayıt")
                
                # Belirli trackingNo aranıyorsa filtrele
                if tracking_no:
                    for order in tracking_list:
                        if str(order.get('trackingNo')) == str(tracking_no):
                            return {'success': True, 'orders': [order]}
                    return {'success': True, 'orders': []}
                
                return {'success': True, 'orders': tracking_list}
            else:
                error_msg = response.get('msg', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Copy Trade history hatası: {error_msg}")
                return {'success': False, 'orders': [], 'error': error_msg}
        except Exception as e:
            logger.error(f"❌ Copy Trade history API hatası: {e}")
            return {'success': False, 'orders': [], 'error': str(e)}

    def get_closed_position_pnl(self, tracking_no):
        """
        v2.4.4: Kapanmış pozisyonun PnL bilgisini al
        
        Returns:
            dict: {
                'success': True/False,
                'pnl': float,
                'result': 'WIN'/'LOSS'/'BREAKEVEN',
                'entry_price': float,
                'close_price': float,
                'fees': float,
                'symbol': str,
                'side': str
            }
        """
        try:
            result = self.get_order_history_track(tracking_no=tracking_no)
            
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'API error')}
            
            orders = result.get('orders', [])
            if not orders:
                logger.warning(f"⚠️ trackingNo {tracking_no} history'de bulunamadı")
                return {'success': False, 'error': 'Order not found in history'}
            
            order = orders[0]
            
            # PnL bilgilerini çek
            pnl = float(order.get('achievedProfits', 0))
            entry_price = float(order.get('openAvgPrice', 0))
            close_price = float(order.get('closeAvgPrice', 0))
            open_fee = float(order.get('openFee', 0))
            close_fee = float(order.get('closeFee', 0))
            total_fees = open_fee + close_fee
            
            # WIN/LOSS/BREAKEVEN belirle
            if pnl > 0.01:
                trade_result = 'WIN'
            elif pnl < -0.01:
                trade_result = 'LOSS'
            else:
                trade_result = 'BREAKEVEN'
            
            symbol = order.get('symbol', '')
            side = order.get('posSide', 'unknown')
            
            logger.info(f"📊 PnL bilgisi: {symbol} {side.upper()} | PnL: ${pnl:.2f} | {trade_result}")
            
            return {
                'success': True,
                'pnl': pnl,
                'result': trade_result,
                'entry_price': entry_price,
                'close_price': close_price,
                'fees': total_fees,
                'symbol': symbol,
                'side': side
            }
            
        except Exception as e:
            logger.error(f"❌ get_closed_position_pnl error: {e}")
            return {'success': False, 'error': str(e)}

    def get_trade_history_stats(self, limit=100):
        """
        v2.4.6: Bitget API'den WIN/LOSS istatistikleri + History PnL
        
        - order-total-detail: Win/Loss sayıları, winRate
        - history-position: Haftalık/Aylık gerçek PnL
        
        Returns:
            dict: {
                'success': True/False,
                'total_trades': int,
                'winning_trades': int,
                'losing_trades': int,
                'win_rate': float,
                'total_pnl': float,
                'weekly_pnl': float,
                'monthly_pnl': float,
                'daily_pnl': float
            }
        """
        self._require_auth()
        try:
            logger.info(f"📊 Trade history stats çekiliyor...")
            
            # 1. order-total-detail'den win/loss sayıları
            response = self._copy_trade_request('GET', '/api/v2/copy/mix-trader/order-total-detail')
            
            if not response or response.get('code') != '00000':
                error_msg = response.get('msg', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Trade history stats hatası: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            data = response.get('data', {})
            
            # API response'dan değerleri al
            total_trades = int(data.get('tradingOrderNum', 0))
            winning_trades = int(data.get('gainNum', 0))
            losing_trades = int(data.get('lossNum', 0))
            win_rate = float(data.get('winRate', 0))
            
            # totalpl "$46.95" formatında geliyor, parse et (tüm zamanların toplamı)
            total_pnl_str = data.get('totalpl', '$0')
            try:
                total_pnl_str = total_pnl_str.replace('$', '').replace(',', '')
                total_pnl = float(total_pnl_str)
            except:
                total_pnl = 0.0
            
            # 2. history-position'dan gerçek PnL hesapla
            daily_pnl = 0.0
            weekly_pnl = 0.0
            monthly_pnl = 0.0
            
            # Günlük PnL (1 gün)
            daily_result = self.get_pnl_history(days=1)
            if daily_result.get('success'):
                daily_pnl = daily_result.get('total_net_profit', 0)
            
            # Haftalık PnL (7 gün)
            weekly_result = self.get_pnl_history(days=7)
            if weekly_result.get('success'):
                weekly_pnl = weekly_result.get('total_net_profit', 0)
            
            # Aylık PnL (30 gün)
            monthly_result = self.get_pnl_history(days=30)
            if monthly_result.get('success'):
                monthly_pnl = monthly_result.get('total_net_profit', 0)
            
            completed_trades = winning_trades + losing_trades
            breakeven_trades = total_trades - completed_trades
            
            logger.info(f"✅ Trade stats: {total_trades} trades, {winning_trades}W/{losing_trades}L, WR:{win_rate}%")
            logger.info(f"💰 PnL - Daily: ${daily_pnl:.2f}, Weekly: ${weekly_pnl:.2f}, Monthly: ${monthly_pnl:.2f}, Total: ${total_pnl:.2f}")
            
            return {
                'success': True,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': breakeven_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'weekly_pnl': weekly_pnl,
                'monthly_pnl': monthly_pnl,
                'coin_breakdown': {}
            }
            
        except Exception as e:
            logger.error(f"❌ Trade history stats exception: {e}")
            return {'success': False, 'error': str(e)}

    def get_pnl_history(self, days=30):
        """
        v2.4.6: Copy Trade order-history-track'den gerçek PnL hesapla
        
        Endpoint: /api/v2/copy/mix-trader/order-history-track
        
        Args:
            days: Kaç günlük veri çekilecek (default: 30)
            
        Returns:
            dict: {
                'success': True/False,
                'total_pnl': float,
                'positions_count': int,
                'winning_count': int,
                'losing_count': int
            }
        """
        self._require_auth()
        try:
            # Zaman aralığını hesapla
            now = int(time.time() * 1000)
            start_time = now - (days * 24 * 60 * 60 * 1000)
            
            logger.info(f"📊 PnL History çekiliyor (son {days} gün)...")
            
            all_trades = []
            end_id = None
            
            # Pagination ile tüm trade'leri çek (max 100 per request)
            for _ in range(10):  # Max 10 sayfa (1000 trade)
                params = {
                    'productType': 'USDT-FUTURES',
                    'startTime': str(start_time),
                    'endTime': str(now),
                    'limit': '100'
                }
                
                if end_id:
                    params['idLessThan'] = end_id
                
                response = self._copy_trade_request('GET', '/api/v2/copy/mix-trader/order-history-track', params)
                
                if not response or response.get('code') != '00000':
                    error_msg = response.get('msg', 'Unknown') if response else 'No response'
                    logger.warning(f"⚠️ PnL History API: {error_msg}")
                    break
                    
                data = response.get('data', {})
                tracking_list = data.get('trackingList', [])
                
                if not tracking_list:
                    break
                    
                all_trades.extend(tracking_list)
                end_id = data.get('endId')
                
                if len(tracking_list) < 100:
                    break
            
            # PnL hesapla
            total_pnl = 0.0
            winning_count = 0
            losing_count = 0
            
            for trade in all_trades:
                try:
                    # achievedPL field'ı realized PnL
                    pnl_str = trade.get('achievedPL', '0')
                    pnl = float(pnl_str)
                    
                    total_pnl += pnl
                    
                    if pnl > 0:
                        winning_count += 1
                    elif pnl < 0:
                        losing_count += 1
                except:
                    pass
            
            logger.info(f"✅ PnL History ({days}d): {len(all_trades)} trade, PnL: ${total_pnl:.2f}")
            
            return {
                'success': True,
                'total_pnl': total_pnl,
                'total_net_profit': total_pnl,  # Copy Trade'de achievedPL = net profit
                'positions_count': len(all_trades),
                'winning_count': winning_count,
                'losing_count': losing_count
            }
            
        except Exception as e:
            logger.error(f"❌ PnL History exception: {e}")
            return {'success': False, 'error': str(e)}

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
        try:
            symbol = self._normalize_symbol(symbol)
            market = self.exchange.market(symbol)
            precision = market.get('precision', {}).get('price')
            if precision is None:
                price = self.get_current_price(symbol)
                if price >= 1000: return 2
                elif price >= 1: return 4
                elif price >= 0.001: return 6
                else: return 8
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

    def get_complete_analysis_data(self, ticker, market_cache=None):
        try:
            symbol = self._normalize_symbol(ticker)
            coin_name = ticker.replace('/USDT:USDT', '').replace('/USDT', '').replace('USDT', '')
            cache_pair = coin_name + 'USDT'
            
            logger.info(f"📊 {coin_name}: Veri toplama başladı...")
            
            current_price = self.get_current_price(symbol)
            if current_price == 0:
                logger.error(f"❌ {coin_name}: Fiyat alınamadı")
                return None
            
            now = get_turkey_time()
            now_ts = int(datetime.now().timestamp())
            pdc = self.get_previous_day_candle(symbol)
            fibo = self.calculate_fibonacci(symbol)
            
            # v2.4.0: Daily OHLCV (PDC bias + Doji kontrolu icin)
            daily_ohlcv = self.get_ohlcv(symbol, '1d', 10)
            if not daily_ohlcv:
                daily_ohlcv = []
            
            atr_data, volume_data, order_blocks, fair_value_gaps = {}, {}, {}, {}
            cache_hits, cache_misses = 0, 0
            
            for tf in Config.TIMEFRAMES:
                if tf in self.SKIP_TIMEFRAMES:
                    continue
                try:
                    api_tf = self.TIMEFRAME_MAP.get(tf, tf)
                    lookback = TF_LOOKBACK_BARS.get(api_tf, DEFAULT_LOOKBACK)
                    ohlcv = self.get_ohlcv(symbol, tf, lookback)
                    
                    if not ohlcv or len(ohlcv) < 10:
                        atr_data[api_tf] = 0
                        volume_data[api_tf] = {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable', 'source': 'no_data'}
                        order_blocks[api_tf], fair_value_gaps[api_tf] = [], []
                        continue
                    
                    cache_key = f"{cache_pair}_{api_tf}"
                    cached = None
                    cache_fresh = False
                    
                    if market_cache and cache_key in market_cache:
                        cached = market_cache[cache_key]
                        cache_age = now_ts - cached.get('ts', 0)
                        cache_fresh = cache_age < Config.MARKET_CACHE_TTL
                    
                    if cache_fresh and cached.get('atr', 0) > 0:
                        atr_data[api_tf] = cached.get('atr')
                        cache_hits += 1
                    else:
                        atr_data[api_tf] = self.calculate_atr(symbol, tf, 14)
                        cache_misses += 1
                    
                    if cache_fresh:
                        spike_ratio = cached.get('spike', 0)
                        spike = spike_ratio >= VOLUME_SPIKE_FLAG
                        if spike_ratio >= VOLUME_STRENGTH_HIGH:
                            strength = 'high'
                        elif spike_ratio >= VOLUME_STRENGTH_MEDIUM:
                            strength = 'medium'
                        else:
                            strength = 'low'
                        volume_data[api_tf] = {
                            'spike': spike, 'spike_ratio': round(spike_ratio, 4),
                            'strength': strength, 'trend': 'unknown',
                            'source': 'tradingview_binance', 'cache_age': cache_age
                        }
                    else:
                        volume_data[api_tf] = {
                            'spike': False, 'spike_ratio': 0.0, 'strength': 'low',
                            'trend': 'unknown', 'source': 'no_cache'
                        }
                    
                    # v2.4.0: scan fonksiyonlarina atr ve current_price eklendi
                    tf_atr = atr_data.get(api_tf, 0)
                    order_blocks[api_tf] = scan_order_blocks(ohlcv, api_tf, atr=tf_atr, current_price=current_price)
                    fair_value_gaps[api_tf] = scan_fair_value_gaps(ohlcv, api_tf, atr=tf_atr, current_price=current_price)
                except Exception as e:
                    api_tf = self.TIMEFRAME_MAP.get(tf, tf)
                    logger.error(f"❌ {coin_name} {api_tf} error: {e}")
                    atr_data[api_tf] = 0
                    volume_data[api_tf] = {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable', 'source': 'error'}
                    order_blocks[api_tf], fair_value_gaps[api_tf] = [], []
            
            total_obs = sum(len(obs) for obs in order_blocks.values())
            total_fvgs = sum(len(fvgs) for fvgs in fair_value_gaps.values())
            logger.info(f"✅ {coin_name}: Price={format_price_display(current_price)}, OBs={total_obs}, FVGs={total_fvgs}")
            
            return {
                'current_price': current_price,
                'current_date': now.strftime('%Y-%m-%d'),
                'current_time': now.strftime('%H:%M:%S'),
                'previous_day': pdc,
                'daily_ohlcv': daily_ohlcv,  # v2.4.0: PDC bias + Doji icin
                'fibonacci': fibo,
                'atr': atr_data,
                'volume': volume_data,
                'smart_money': {'order_blocks': order_blocks, 'fair_value_gaps': fair_value_gaps}
            }
        except Exception as e:
            logger.error(f"❌ Complete analysis error ({ticker}): {e}")
            return None

    def calculate_contracts(self, symbol, notional_usd, current_price):
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
        try:
            balance = self.get_balance()
            total_balance = float(balance.get('total', 0)) if balance.get('success') else 500.0
            available_balance = float(balance.get('free', 0)) if balance.get('success') else 500.0
            
            stop_distance = abs(entry_price - stop_price)
            stop_distance_pct = stop_distance / entry_price if entry_price > 0 else 0.01
            original_stop_pct = stop_distance_pct
            stop_distance_pct = max(Config.STOP_DISTANCE_MIN, min(stop_distance_pct, Config.STOP_DISTANCE_MAX))
            
            if original_stop_pct != stop_distance_pct:
                logger.info(f"📏 Stop mesafesi clamp: {original_stop_pct:.4%} → {stop_distance_pct:.4%}")
            
            if total_balance >= 2000:
                min_margin = total_balance * (Config.MARGIN_MIN_PERCENT / 100)
                max_margin = total_balance * (Config.MARGIN_MAX_PERCENT / 100)
                risk_percent = Config.RISK_PER_TRADE / 100
                risk_amount = total_balance * risk_percent
                calculated_position = risk_amount / stop_distance_pct
                calculated_margin = calculated_position / Config.DEFAULT_LEVERAGE
                final_margin = max(min_margin, min(calculated_margin, max_margin))
                margin_mode = f"Dinamik %{Config.MARGIN_MIN_PERCENT}-{Config.MARGIN_MAX_PERCENT}"
            elif total_balance >= 1000:
                final_margin = 20.0
                margin_mode = "Sabit $20"
            else:
                final_margin = 10.0
                margin_mode = "Sabit $10"
            
            final_notional = final_margin * Config.DEFAULT_LEVERAGE
            
            logger.info(f"💰 Pozisyon Hesabı (v2.3.13):")
            logger.info(f"   Total: ${total_balance:.2f} | Marjin: ${final_margin:.2f} | Notional: ${final_notional:.2f}")
            
            return final_notional
        except Exception as e:
            logger.error(f"Position size hesaplama hatası: {e}")
            return 100.0

    def place_copy_trade_order(self, symbol, side, contracts, entry_price, tp_price=None, sl_price=None):
        """
        v2.4.0: Normal CCXT create_order + sonradan trackingNo sorgula
        
        Elite Trader Copy Trade API key ile normal order acilinca,
        Bitget otomatik olarak takipcilere kopyalar.
        trackingNo sonradan find_tracking_no_by_symbol ile alinir.
        
        Args:
            symbol: Trading pair (BTC/USDT:USDT)
            side: 'buy' (LONG) veya 'sell' (SHORT)
            contracts: Kontrat sayisi
            entry_price: Limit order fiyati
            tp_price: Take profit fiyati (opsiyonel)
            sl_price: Stop loss fiyati (opsiyonel)
        
        Returns:
            dict: {
                'success': True/False,
                'tracking_no': str,
                'order_id': str,
                ...
            }
        """
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            coin_name = symbol.replace('/USDT:USDT', '')
            
            precision = self.get_price_precision(symbol)
            entry_rounded = round_price_to_precision(entry_price, precision)
            
            # CCXT order params - Hedge mode (Bitget API doc)
            # side=buy → LONG, side=sell → SHORT
            # tradeSide=open → pozisyon aç (hedge mode'da zorunlu)
            params = {
                'marginMode': 'cross',
                'tradeSide': 'open',  # v2.4.2: Hedge mode için zorunlu
            }
            
            # TP/SL preset (Bitget API doc: presetStopSurplusPrice, presetStopLossPrice)
            if tp_price and tp_price > 0:
                tp_rounded = round_price_to_precision(tp_price, precision)
                params['presetStopSurplusPrice'] = str(tp_rounded)
            
            if sl_price and sl_price > 0:
                sl_rounded = round_price_to_precision(sl_price, precision)
                params['presetStopLossPrice'] = str(sl_rounded)
            
            logger.info(f"Order Aciliyor (CCXT): {coin_name} {side.upper()}")
            logger.info(f"   Entry: {format_price_display(entry_rounded)} | Contracts: {contracts}")
            if tp_price:
                logger.info(f"   TP: {format_price_display(tp_price)} | SL: {format_price_display(sl_price)}")
            
            # CCXT create_order (limit order)
            order = self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side.lower(),
                amount=contracts,
                price=entry_rounded,
                params=params
            )
            
            if order and order.get('id'):
                order_id = order.get('id')
                logger.info(f"Order Basarili! orderId: {order_id}")
                
                # trackingNo'yu bul (Copy Trade icin)
                tracking_no = None
                try:
                    import time
                    time.sleep(1)  # API'nin islemesi icin kisa bekle
                    tracking_no = self.find_tracking_no_by_symbol(symbol)
                    if tracking_no:
                        logger.info(f"   trackingNo: {tracking_no}")
                    else:
                        logger.warning(f"   trackingNo bulunamadi (normal hesap olabilir)")
                except Exception as te:
                    logger.warning(f"   trackingNo sorgu hatasi: {te}")
                
                return {
                    'success': True,
                    'tracking_no': tracking_no,
                    'order_id': order_id,
                    'contracts': contracts,
                    'entry_price': entry_rounded,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'response': order
                }
            else:
                logger.error(f"Order Hatasi: Bos yanit")
                return {
                    'success': False,
                    'error': 'Order response empty',
                    'response': order
                }
                
        except Exception as e:
            logger.error(f"Order Exception: {e}")
            return {'success': False, 'error': str(e)}

    def place_order_with_tp_sl(self, symbol, side, entry_price, stop_price, tp_price=None):
        """
        v2.3.14: Copy Trade API ile order aç (trackingNo döndürür)
        
        Eski CCXT versiyonu yerine Copy Trade API kullanır.
        """
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            coin_name = symbol.replace('/USDT:USDT', '')
            self.set_leverage(symbol)
            
            # SL minimum mesafe kontrolü
            original_stop = stop_price
            stop_distance_pct = abs(entry_price - stop_price) / entry_price if entry_price > 0 else 0
            min_stop_pct = Config.STOP_DISTANCE_MIN
            
            if stop_distance_pct < min_stop_pct:
                if side.lower() == 'sell':
                    stop_price = entry_price * (1 + min_stop_pct)
                else:
                    stop_price = entry_price * (1 - min_stop_pct)
                logger.info(f"📏 SL düzeltildi: {format_price_display(original_stop)} → {format_price_display(stop_price)}")
            
            notional_usd = self.calculate_position_size(entry_price, stop_price)
            contracts = self.calculate_contracts(symbol, notional_usd, entry_price)
            
            if contracts < 1:
                return {'success': False, 'error': 'Kontrat sayısı 0'}
            
            actual_margin = notional_usd / Config.DEFAULT_LEVERAGE
            precision = self.get_price_precision(symbol)
            
            tp_rounded = round_price_to_precision(tp_price, precision) if tp_price and tp_price > 0 else None
            sl_rounded = round_price_to_precision(stop_price, precision) if stop_price and stop_price > 0 else None
            
            logger.info(f"🚀 EMİR AÇILIYOR (Copy Trade API):")
            logger.info(f"   {coin_name} | {side.upper()} | Contracts: {contracts}")
            logger.info(f"   Entry: {format_price_display(entry_price)}")
            logger.info(f"   TP: {format_price_display(tp_rounded)} | SL: {format_price_display(sl_rounded)}")
            logger.info(f"   Marjin: ${actual_margin:.2f} | Notional: ${notional_usd:.2f}")
            
            # Copy Trade API ile order aç
            result = self.place_copy_trade_order(
                symbol=symbol,
                side=side,
                contracts=contracts,
                entry_price=entry_price,
                tp_price=tp_rounded,
                sl_price=sl_rounded
            )
            
            if result.get('success'):
                return {
                    'success': True,
                    'order_id': result.get('order_id'),
                    'tracking_no': result.get('tracking_no'),  # v2.3.14: trackingNo eklendi
                    'contracts': contracts,
                    'entry_price': entry_price,
                    'margin_usd': actual_margin,
                    'position_usd': notional_usd,
                    'tp_price': tp_rounded,
                    'sl_price': sl_rounded,
                    'tp_sl_preset': True
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Copy Trade API error')
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

    def close_position(self, symbol, side=None, order_type=None, slippage_pct=None):
        """
        v2.3.13: Pozisyon kapatma - LIMIT ORDER DESTEKLİ
        
        Args:
            symbol: Trading pair
            side: 'long' veya 'short' (None ise ilk pozisyonu kapat)
            order_type: 'limit' veya 'market' (None ise Config.CLOSE_ORDER_TYPE)
            slippage_pct: Limit order için slippage (None ise Config.CLOSE_SLIPPAGE_PCT)
        
        Limit Close:
            - LONG kapatma (SELL): current_price * (1 - slippage)
            - SHORT kapatma (BUY): current_price * (1 + slippage)
        """
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            coin_name = symbol.replace('/USDT:USDT', '')
            
            positions = self.get_positions(symbol)
            if not positions:
                return {'success': False, 'error': 'Pozisyon yok'}
            
            target_pos = positions[0]
            if side:
                for p in positions:
                    if p['side'] == side.lower():
                        target_pos = p
                        break
            
            close_order_type = order_type or Config.CLOSE_ORDER_TYPE
            close_slippage = slippage_pct if slippage_pct is not None else Config.CLOSE_SLIPPAGE_PCT
            
            close_side = 'sell' if target_pos['side'] == 'long' else 'buy'
            contracts = float(target_pos['contracts'])
            
            params = {
                'marginMode': 'cross',
                'tradeSide': 'close',  # v2.4.2: Hedge mode için zorunlu
                'reduceOnly': True
            }
            
            # LIMIT ORDER
            if close_order_type == 'limit':
                current_price = self.get_current_price(symbol)
                if current_price <= 0:
                    logger.warning(f"⚠️ Fiyat alınamadı, MARKET'e düşülüyor")
                    close_order_type = 'market'
                else:
                    precision = self.get_price_precision(symbol)
                    
                    if close_side == 'sell':  # LONG kapatma
                        limit_price = current_price * (1 - close_slippage)
                    else:  # SHORT kapatma
                        limit_price = current_price * (1 + close_slippage)
                    
                    limit_price = round_price_to_precision(limit_price, precision)
                    
                    logger.info(f"🔴 CLOSE (LIMIT): {coin_name} | {target_pos['side'].upper()} | "
                               f"Current: {format_price_display(current_price)} | Limit: {format_price_display(limit_price)} ({close_slippage:.2%})")
                    
                    order = self.exchange.create_order(
                        symbol=symbol, type='limit', side=close_side,
                        amount=contracts, price=limit_price, params=params
                    )
                    
                    return {
                        'success': True, 'order_id': order['id'], 'order_type': 'limit',
                        'close_price': limit_price, 'current_price': current_price,
                        'slippage_pct': close_slippage
                    }
            
            # MARKET ORDER
            logger.info(f"🔴 CLOSE (MARKET): {coin_name} | {target_pos['side'].upper()} | {contracts} kontrat")
            
            order = self.exchange.create_order(
                symbol=symbol, type='market', side=close_side,
                amount=contracts, params=params
            )
            
            return {'success': True, 'order_id': order['id'], 'order_type': 'market'}
            
        except Exception as e:
            logger.error(f"❌ Pozisyon kapatma hatası: {e}")
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

    def execute_trade_for_setup(self, setup_data, claude_decision=None):
        """
        v2.3.14: Unified Trade Execution - Copy Trade API ile
        tracking_no döndürür
        """
        try:
            pair = setup_data.get('pair', '')
            direction = setup_data.get('direction', 'LONG').upper()
            entry_price = float(setup_data.get('entry_price', 0))
            stop_price = float(setup_data.get('stop_price', 0))
            tp1_price = float(setup_data.get('tp1_price', 0))
            
            if not pair:
                return {'success': False, 'error': 'Pair belirtilmedi'}
            if entry_price <= 0:
                return {'success': False, 'error': 'Entry price geçersiz'}
            if stop_price <= 0:
                return {'success': False, 'error': 'Stop price geçersiz'}
            if tp1_price <= 0:
                return {'success': False, 'error': 'TP price geçersiz'}
            
            if '/' not in pair:
                if pair.endswith('USDT'):
                    symbol = f"{pair[:-4]}/USDT:USDT"
                else:
                    symbol = f"{pair}/USDT:USDT"
            else:
                symbol = pair
            
            coin_name = symbol.replace('/USDT:USDT', '')
            side = 'buy' if direction == 'LONG' else 'sell'
            
            if claude_decision:
                logger.info(f"🧠 Claude: {claude_decision.get('action', 'N/A')} ({claude_decision.get('confidence', 0)}%)")
            
            logger.info(f"🚀 Execute Trade: {coin_name} {direction}")
            
            result = self.place_order_with_tp_sl(
                symbol=symbol, side=side, entry_price=entry_price,
                stop_price=stop_price, tp_price=tp1_price
            )
            
            if result.get('success'):
                tracking_no = result.get('tracking_no')
                logger.info(f"✅ Trade executed: {coin_name} {direction} | trackingNo: {tracking_no}")
                return {
                    'success': True,
                    'order_id': result.get('order_id'),
                    'tracking_no': tracking_no,  # v2.3.14: trackingNo eklendi
                    'contracts': result.get('contracts', 0),
                    'margin_usd': result.get('margin_usd', 0),
                    'position_usd': result.get('position_usd', 0),
                    'entry_price': entry_price,
                    'stop_price': result.get('sl_price', stop_price),
                    'tp_price': result.get('tp_price', tp1_price),
                    'tp_sl_preset': result.get('tp_sl_preset', False)
                }
            else:
                logger.error(f"❌ Trade failed: {coin_name} {direction}")
                return {'success': False, 'error': result.get('error', 'Unknown error')}
                
        except Exception as e:
            logger.error(f"❌ Execute trade exception: {e}")
            return {'success': False, 'error': str(e)}
