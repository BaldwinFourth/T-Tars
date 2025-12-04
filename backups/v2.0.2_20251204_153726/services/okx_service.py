# -*- coding: utf-8 -*-
"""
T-TARS OKX Service v2.0.2
=========================
OKX Exchange Service - Market Data + Trade Execution + Account Management

v2.0.2:
- FIX: set_leverage() eklendi - işlem öncesi kaldıraç ayarı
- FIX: posSide='net' eklendi (one-way mode)
- FIX: Amount hesabı düzeltildi (kontrat boyutu)
- FIX: Order params düzeltildi

v2.0.0:
- Trade Execution: Market/Limit orders, TP/SL
- Account Info: Balance, Positions, Trade History
- Demo/Live mode switch
"""

import ccxt
from datetime import datetime, timedelta, timezone
import logging
import os

# Turkey timezone (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))

def get_turkey_time():
    """Get current time in Turkey timezone"""
    return datetime.now(TURKEY_TZ)

logger = logging.getLogger(__name__)


class OKXService:
    """OKX Exchange Service - Market Data + Trade Execution + Account Management"""
    
    # Türkçe → OKX timeframe mapping
    TIMEFRAME_MAP = {
        '1G': '1d',
        '4S': '4h',
        '1S': '1h',
        '30D': '30m',
        '15D': '15m',
        '5D': '5m',
        '3D': '3m',
        '2D': '2m',
        '1D': '1m'
    }
    
    # v2.0.2: Default leverage
    DEFAULT_LEVERAGE = 10
    
    def __init__(self):
        """
        Initialize OKX Service
        
        ENV Variables:
            OKX_API_KEY: API Key
            OKX_SECRET_KEY: Secret Key
            OKX_PASSPHRASE: Passphrase
            OKX_DEMO_MODE: 'true' for demo, 'false' for live
        """
        # API Credentials from ENV
        api_key = os.environ.get('OKX_API_KEY', '')
        secret_key = os.environ.get('OKX_SECRET_KEY', '')
        passphrase = os.environ.get('OKX_PASSPHRASE', '')
        demo_mode = os.environ.get('OKX_DEMO_MODE', 'true').lower() == 'true'
        
        # Initialize exchange
        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Perpetual Futures (USDT-M)
            }
        }
        
        # Add credentials if available
        if api_key and secret_key and passphrase:
            config['apiKey'] = api_key
            config['secret'] = secret_key
            config['password'] = passphrase
            self.authenticated = True
            logger.info("✅ OKX Service initialized with authentication")
        else:
            self.authenticated = False
            logger.warning("⚠️ OKX Service initialized WITHOUT authentication (public only)")
        
        self.exchange = ccxt.okx(config)
        
        # Demo mode
        self.demo_mode = demo_mode
        if self.authenticated and demo_mode:
            self.exchange.set_sandbox_mode(True)
            logger.info("🧪 OKX DEMO MODE enabled")
        elif self.authenticated:
            logger.info("🔴 OKX LIVE MODE enabled - REAL MONEY!")
        
        # v2.0.2: Cache for market info
        self._market_cache = {}
        
        logger.info(f"OKX Service ready (Auth: {self.authenticated}, Demo: {demo_mode})")
    
    # ============================================
    # AUTHENTICATION CHECK
    # ============================================
    
    def _require_auth(self):
        """Check if authenticated before private API calls"""
        if not self.authenticated:
            raise Exception("❌ OKX API credentials not configured. Set OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE")
    
    # ============================================
    # v2.0.2: LEVERAGE MANAGEMENT
    # ============================================
    
    def set_leverage(self, symbol, leverage=None):
        """
        v2.0.2: Kaldıraç ayarla
        
        Args:
            symbol: 'BTC/USDT:USDT'
            leverage: Kaldıraç değeri (default: 10)
        
        Returns:
            dict: Result
        """
        self._require_auth()
        
        try:
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            lev = leverage or self.DEFAULT_LEVERAGE
            
            # OKX set leverage
            result = self.exchange.set_leverage(lev, symbol, params={
                'mgnMode': 'isolated',  # isolated margin
                'posSide': 'net'        # one-way mode
            })
            
            logger.info(f"✅ Leverage set: {symbol} x{lev}")
            return {
                'success': True,
                'symbol': symbol,
                'leverage': lev,
                'raw': result
            }
            
        except Exception as e:
            logger.error(f"❌ Set leverage failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_contract_size(self, symbol):
        """
        v2.0.2: Kontrat boyutunu al
        
        Args:
            symbol: 'BTC/USDT:USDT'
        
        Returns:
            float: Contract size (örn: BTC=0.01, ETH=0.1)
        """
        try:
            if symbol in self._market_cache:
                return self._market_cache[symbol]
            
            market = self.exchange.market(symbol)
            contract_size = market.get('contractSize', 1)
            
            self._market_cache[symbol] = contract_size
            logger.info(f"📊 Contract size {symbol}: {contract_size}")
            
            return contract_size
            
        except Exception as e:
            logger.error(f"❌ Get contract size error: {e}")
            return 1  # Default
    
    def calculate_contracts(self, symbol, position_size_usd, entry_price):
        """
        v2.0.2: USD'den kontrat sayısı hesapla
        
        Args:
            symbol: 'BTC/USDT:USDT'
            position_size_usd: Pozisyon büyüklüğü ($)
            entry_price: Giriş fiyatı
        
        Returns:
            float: Kontrat sayısı
        """
        try:
            contract_size = self.get_contract_size(symbol)
            
            # Coin miktarı = USD / Fiyat
            coin_amount = position_size_usd / entry_price
            
            # Kontrat sayısı = Coin miktarı / Kontrat boyutu
            contracts = coin_amount / contract_size
            
            # Minimum 1 kontrat
            contracts = max(1, round(contracts))
            
            logger.info(f"📊 Contracts: ${position_size_usd} / ${entry_price} / {contract_size} = {contracts}")
            
            return contracts
            
        except Exception as e:
            logger.error(f"❌ Calculate contracts error: {e}")
            return 1
    
    # ============================================
    # TRADE EXECUTION
    # ============================================
    
    def place_market_order(self, symbol, side, amount, reduce_only=False):
        """
        Market order aç
        
        Args:
            symbol: 'BTC/USDT:USDT' veya 'BTCUSDT'
            side: 'buy' veya 'sell'
            amount: Kontrat sayısı
            reduce_only: Sadece pozisyon kapat
            
        Returns:
            dict: Order response
        """
        self._require_auth()
        
        try:
            # Symbol format
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            # v2.0.2: Leverage ayarla
            self.set_leverage(symbol)
            
            params = {
                'tdMode': 'isolated',  # isolated margin
                'posSide': 'net',      # v2.0.2: one-way mode
            }
            
            if reduce_only:
                params['reduceOnly'] = True
            
            logger.info(f"🚀 Placing market {side.upper()}: {symbol} x{amount}")
            
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params=params
            )
            
            logger.info(f"✅ Market {side.upper()} order placed: {symbol} x{amount}")
            logger.info(f"   Order ID: {order['id']}")
            
            return {
                'success': True,
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'type': 'market',
                'status': order['status'],
                'price': order.get('average') or order.get('price'),
                'filled': order.get('filled'),
                'raw': order
            }
            
        except Exception as e:
            logger.error(f"❌ Market order failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def place_limit_order(self, symbol, side, amount, price):
        """
        Limit order aç
        """
        self._require_auth()
        
        try:
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            # v2.0.2: Leverage ayarla
            self.set_leverage(symbol)
            
            params = {
                'tdMode': 'isolated',
                'posSide': 'net',
            }
            
            order = self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=amount,
                price=price,
                params=params
            )
            
            logger.info(f"✅ Limit {side.upper()} order placed: {symbol} x{amount} @ {price}")
            logger.info(f"   Order ID: {order['id']}")
            
            return {
                'success': True,
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price,
                'type': 'limit',
                'status': order['status'],
                'raw': order
            }
            
        except Exception as e:
            logger.error(f"❌ Limit order failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def place_order_with_tp_sl(self, symbol, side, amount, tp_price=None, sl_price=None, entry_price=None):
        """
        v2.0.2: TP/SL ile market order aç (DÜZELTILMIŞ)
        
        Args:
            symbol: 'BTC/USDT:USDT' veya 'BTCUSDT'
            side: 'buy' veya 'sell'
            amount: Kontrat sayısı (veya USD miktarı - otomatik convert)
            tp_price: Take Profit fiyat
            sl_price: Stop Loss fiyat
            entry_price: Giriş fiyatı (amount USD ise convert için)
            
        Returns:
            dict: Order response
        """
        self._require_auth()
        
        try:
            # Symbol format
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            # v2.0.2: Leverage ayarla
            lev_result = self.set_leverage(symbol)
            if not lev_result.get('success'):
                logger.warning(f"⚠️ Leverage set warning: {lev_result.get('error')}")
            
            # v2.0.2: Amount USD ise kontrata çevir
            actual_amount = amount
            if entry_price and amount > 100:  # Muhtemelen USD
                actual_amount = self.calculate_contracts(symbol, amount, entry_price)
                logger.info(f"📊 Converted ${amount} to {actual_amount} contracts")
            
            # v2.0.2: Düzeltilmiş params
            params = {
                'tdMode': 'isolated',   # Isolated margin
                'posSide': 'net',       # One-way mode (ZORUNLU!)
            }
            
            # TP/SL - ccxt format
            if tp_price and tp_price > 0:
                params['takeProfitPrice'] = str(tp_price)
            if sl_price and sl_price > 0:
                params['stopLossPrice'] = str(sl_price)
            
            logger.info(f"🚀 Placing order: {symbol} {side.upper()} x{actual_amount}")
            logger.info(f"   TP: {tp_price}, SL: {sl_price}")
            logger.info(f"   Params: {params}")
            
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=actual_amount,
                params=params
            )
            
            logger.info(f"✅ Market {side.upper()} order with TP/SL: {symbol} x{actual_amount}")
            logger.info(f"   Order ID: {order['id']}")
            logger.info(f"   Status: {order['status']}")
            logger.info(f"   Filled: {order.get('filled')}")
            
            return {
                'success': True,
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'amount': actual_amount,
                'type': 'market',
                'tp_price': tp_price,
                'sl_price': sl_price,
                'status': order['status'],
                'price': order.get('average') or order.get('price'),
                'filled': order.get('filled'),
                'raw': order
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Order with TP/SL failed: {error_msg}")
            
            # v2.0.2: Detaylı hata analizi
            if 'Parameter posSide' in error_msg:
                logger.error("🔴 HATA: posSide parametresi yanlış. Hesap ayarlarını kontrol et.")
            elif 'leverage' in error_msg.lower():
                logger.error("🔴 HATA: Kaldıraç ayarı yapılamadı.")
            elif 'insufficient' in error_msg.lower():
                logger.error("🔴 HATA: Yetersiz bakiye.")
            elif 'Invalid' in error_msg:
                logger.error(f"🔴 HATA: Geçersiz parametre: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def cancel_order(self, order_id, symbol):
        """Order iptal et"""
        self._require_auth()
        
        try:
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            result = self.exchange.cancel_order(order_id, symbol)
            
            logger.info(f"✅ Order cancelled: {order_id}")
            
            return {
                'success': True,
                'order_id': order_id,
                'symbol': symbol,
                'raw': result
            }
            
        except Exception as e:
            logger.error(f"❌ Cancel order failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def close_position(self, symbol, side=None):
        """Pozisyonu kapat (market order ile)"""
        self._require_auth()
        
        try:
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            positions = self.get_positions(symbol)
            
            if not positions or len(positions) == 0:
                return {
                    'success': False,
                    'error': 'No open position'
                }
            
            pos = positions[0]
            pos_side = pos.get('side')
            pos_amount = abs(float(pos.get('contracts', 0)))
            
            if pos_amount == 0:
                return {
                    'success': False,
                    'error': 'Position size is 0'
                }
            
            close_side = 'sell' if pos_side == 'long' else 'buy'
            
            result = self.place_market_order(
                symbol=symbol,
                side=close_side,
                amount=pos_amount,
                reduce_only=True
            )
            
            if result['success']:
                logger.info(f"✅ Position closed: {symbol}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Close position failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_order(self, order_id, symbol):
        """Order durumunu al"""
        self._require_auth()
        
        try:
            if ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            order = self.exchange.fetch_order(order_id, symbol)
            
            return {
                'success': True,
                'order_id': order['id'],
                'symbol': symbol,
                'side': order['side'],
                'type': order['type'],
                'amount': order['amount'],
                'filled': order['filled'],
                'remaining': order['remaining'],
                'price': order.get('price'),
                'average': order.get('average'),
                'status': order['status'],
                'raw': order
            }
            
        except Exception as e:
            logger.error(f"❌ Get order failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_open_orders(self, symbol=None):
        """Açık orderları getir"""
        self._require_auth()
        
        try:
            if symbol and ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            orders = self.exchange.fetch_open_orders(symbol)
            
            result = []
            for order in orders:
                result.append({
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'amount': order['amount'],
                    'filled': order['filled'],
                    'price': order.get('price'),
                    'status': order['status']
                })
            
            logger.info(f"📋 Open orders: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get open orders failed: {e}")
            return []
    
    # ============================================
    # ACCOUNT INFORMATION
    # ============================================
    
    def get_balance(self):
        """Hesap bakiyesi"""
        self._require_auth()
        
        try:
            balance = self.exchange.fetch_balance()
            
            usdt = balance.get('USDT', {})
            
            result = {
                'success': True,
                'total': usdt.get('total', 0),
                'free': usdt.get('free', 0),
                'used': usdt.get('used', 0),
                'currency': 'USDT',
                'raw': balance
            }
            
            logger.info(f"💰 Balance: ${result['total']:.2f} (Free: ${result['free']:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get balance failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_positions(self, symbol=None):
        """Açık pozisyonlar"""
        self._require_auth()
        
        try:
            if symbol and ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            positions = self.exchange.fetch_positions([symbol] if symbol else None)
            
            result = []
            for pos in positions:
                contracts = float(pos.get('contracts', 0))
                if contracts == 0:
                    continue
                
                result.append({
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'contracts': contracts,
                    'notional': pos.get('notional'),
                    'entry_price': pos.get('entryPrice'),
                    'mark_price': pos.get('markPrice'),
                    'liquidation_price': pos.get('liquidationPrice'),
                    'unrealized_pnl': pos.get('unrealizedPnl'),
                    'percentage': pos.get('percentage'),
                    'margin_mode': pos.get('marginMode'),
                    'leverage': pos.get('leverage'),
                    'raw': pos
                })
            
            logger.info(f"📊 Open positions: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get positions failed: {e}")
            return []
    
    def get_trade_history(self, symbol=None, limit=50):
        """Trade geçmişi"""
        self._require_auth()
        
        try:
            if symbol and ':' not in symbol:
                symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
            
            trades = self.exchange.fetch_my_trades(symbol, limit=limit)
            
            result = []
            for trade in trades:
                result.append({
                    'id': trade['id'],
                    'order_id': trade.get('order'),
                    'symbol': trade['symbol'],
                    'side': trade['side'],
                    'amount': trade['amount'],
                    'price': trade['price'],
                    'cost': trade['cost'],
                    'fee': trade.get('fee', {}).get('cost', 0),
                    'fee_currency': trade.get('fee', {}).get('currency', 'USDT'),
                    'timestamp': trade['timestamp'],
                    'datetime': trade['datetime']
                })
            
            logger.info(f"📜 Trade history: {len(result)} trades")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get trade history failed: {e}")
            return []
    
    def get_pnl_summary(self):
        """P/L özeti"""
        self._require_auth()
        
        try:
            positions = self.get_positions()
            balance = self.get_balance()
            
            total_unrealized_pnl = 0
            position_count = 0
            
            for pos in positions:
                pnl = pos.get('unrealized_pnl', 0)
                if pnl:
                    total_unrealized_pnl += float(pnl)
                    position_count += 1
            
            result = {
                'success': True,
                'total_balance': balance.get('total', 0),
                'free_balance': balance.get('free', 0),
                'unrealized_pnl': total_unrealized_pnl,
                'open_positions': position_count,
                'positions': positions
            }
            
            logger.info(f"📊 P/L Summary: ${total_unrealized_pnl:+.2f} ({position_count} positions)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get P/L summary failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ============================================
    # MARKET DATA (Değişmedi)
    # ============================================
    
    @staticmethod
    def convert_timeframe(turkish_tf):
        """Türkçe timeframe'i OKX formatına çevir"""
        return OKXService.TIMEFRAME_MAP.get(turkish_tf, '1d')
    
    def get_current_price(self, ticker="BTC/USDT"):
        """Mevcut fiyat"""
        try:
            ticker_data = self.exchange.fetch_ticker(ticker)
            price = ticker_data['last']
            logger.info(f"Current price {ticker}: {price}")
            return price
        except Exception as e:
            logger.error(f"OKX get_price error: {e}")
            raise
    
    def get_ohlcv(self, ticker="BTC/USDT", timeframe='1G', limit=100):
        """OHLCV data çek"""
        try:
            okx_timeframe = self.convert_timeframe(timeframe) if timeframe in self.TIMEFRAME_MAP else timeframe
            ohlcv = self.exchange.fetch_ohlcv(ticker, okx_timeframe, limit=limit)
            logger.info(f"OHLCV {ticker} {timeframe}: {len(ohlcv)} candles")
            return ohlcv
        except Exception as e:
            logger.error(f"OKX get_ohlcv error: {e}")
            raise
    
    def get_previous_day_candle(self, ticker="BTC/USDT"):
        """Önceki günün mumu (PDC)"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(ticker, '1d', limit=3)
            prev_candle = ohlcv[-2]
            
            result = {
                'timestamp': prev_candle[0],
                'open': prev_candle[1],
                'high': prev_candle[2],
                'low': prev_candle[3],
                'close': prev_candle[4],
                'volume': prev_candle[5],
                'date': datetime.fromtimestamp(prev_candle[0]/1000, tz=TURKEY_TZ).strftime('%Y-%m-%d'),
                'candle_type': 'green' if prev_candle[4] > prev_candle[1] else 'red'
            }
            
            logger.info(f"PDC {ticker}: {result['candle_type']} O:{result['open']} H:{result['high']} L:{result['low']} C:{result['close']}")
            return result
        except Exception as e:
            logger.error(f"OKX previous_day error: {e}")
            raise
    
    def calculate_atr(self, ticker="BTC/USDT", timeframe='1d', period=14):
        """ATR(14) hesapla"""
        try:
            ohlcv = self.get_ohlcv(ticker, timeframe, limit=period+1)
            
            tr_list = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_list.append(tr)
            
            atr = sum(tr_list[-period:]) / period
            logger.info(f"ATR({period}) {ticker} {timeframe}: {atr:.8f}")
            return round(atr, 8)
        except Exception as e:
            logger.error(f"OKX ATR error: {e}")
            raise
    
    def calculate_fibonacci(self, ticker="BTC/USDT", use_pdc=True):
        """Fibonacci seviyeleri - PDC'ye göre"""
        try:
            if use_pdc:
                prev_candle = self.get_previous_day_candle(ticker)
                high = prev_candle['high']
                low = prev_candle['low']
                candle_type = prev_candle['candle_type']
            else:
                ohlcv = self.get_ohlcv(ticker, '1d', limit=1)
                high = ohlcv[-1][2]
                low = ohlcv[-1][3]
                candle_type = 'green' if ohlcv[-1][4] > ohlcv[-1][1] else 'red'
            
            diff = high - low
            
            if candle_type == 'red':
                levels = {
                    '0.0': high,
                    '23.6': high - (diff * 0.236),
                    '38.2': high - (diff * 0.382),
                    '50.0': high - (diff * 0.500),
                    '61.8': high - (diff * 0.618),
                    '70.5': high - (diff * 0.705),
                    '78.6': high - (diff * 0.786),
                    '100.0': low
                }
            else:
                levels = {
                    '0.0': low,
                    '23.6': low + (diff * 0.236),
                    '38.2': low + (diff * 0.382),
                    '50.0': low + (diff * 0.500),
                    '61.8': low + (diff * 0.618),
                    '70.5': low + (diff * 0.705),
                    '78.6': low + (diff * 0.786),
                    '100.0': high
                }
            
            levels['1.272'] = high + (diff * 0.272) if candle_type == 'green' else low - (diff * 0.272)
            levels['1.618'] = high + (diff * 0.618) if candle_type == 'green' else low - (diff * 0.618)
            
            result = {
                'high': high,
                'low': low,
                'candle_type': candle_type,
                'levels': {k: round(v, 8) for k, v in levels.items()}
            }
            
            logger.info(f"Fibonacci {ticker} ({candle_type}): {low:.8f} - {high:.8f}")
            return result
        except Exception as e:
            logger.error(f"OKX Fibonacci error: {e}")
            raise
    
    def analyze_volume(self, ohlcv, lookback=20):
        """Volume analizi"""
        try:
            volumes = [x[5] for x in ohlcv[-lookback:]]
            current_volume = volumes[-1]
            avg_volume = sum(volumes[:-1]) / (lookback - 1)
            
            spike_ratio = current_volume / avg_volume
            is_spike = spike_ratio >= 2.0
            
            recent_avg = sum(volumes[-5:]) / 5
            previous_avg = sum(volumes[-10:-5]) / 5
            
            if recent_avg > previous_avg * 1.2:
                trend = 'increasing'
            elif recent_avg < previous_avg * 0.8:
                trend = 'decreasing'
            else:
                trend = 'neutral'
            
            if current_volume > avg_volume * 1.5:
                strength = 'high'
            elif current_volume > avg_volume * 0.8:
                strength = 'medium'
            else:
                strength = 'low'
            
            result = {
                'current': round(current_volume, 2),
                'average': round(avg_volume, 2),
                'spike': is_spike,
                'spike_ratio': round(spike_ratio, 2),
                'trend': trend,
                'strength': strength
            }
            
            logger.info(f"Volume analysis: {strength} ({spike_ratio:.2f}x, {trend})")
            return result
        except Exception as e:
            logger.error(f"Volume analysis error: {e}")
            raise
    
    def detect_order_blocks(self, ticker="BTC/USDT", timeframe='4h', lookback=50):
        """Order Block detection + VOLUME validation"""
        try:
            ohlcv = self.get_ohlcv(ticker, timeframe, limit=lookback)
            order_blocks = []
            
            for i in range(2, len(ohlcv) - 1):
                candle = ohlcv[i]
                prev_candle = ohlcv[i-1]
                next_candle = ohlcv[i+1]
                
                if (candle[4] < candle[1] and next_candle[4] > candle[2]):
                    volume_analysis = self.analyze_volume(ohlcv[:i+2], lookback=20)
                    volume_confirmed = volume_analysis['strength'] in ['high', 'medium']
                    
                    order_blocks.append({
                        'type': 'bullish',
                        'price': candle[2],
                        'low': candle[3],
                        'index': i,
                        'volume_confirmed': volume_confirmed,
                        'volume_strength': volume_analysis['strength'],
                        'strength': 'high' if volume_confirmed else 'low'
                    })
                
                elif (candle[4] > candle[1] and next_candle[4] < candle[3]):
                    volume_analysis = self.analyze_volume(ohlcv[:i+2], lookback=20)
                    volume_confirmed = volume_analysis['strength'] in ['high', 'medium']
                    
                    order_blocks.append({
                        'type': 'bearish',
                        'price': candle[3],
                        'high': candle[2],
                        'index': i,
                        'volume_confirmed': volume_confirmed,
                        'volume_strength': volume_analysis['strength'],
                        'strength': 'high' if volume_confirmed else 'low'
                    })
            
            recent_obs = order_blocks[-5:] if len(order_blocks) > 5 else order_blocks
            logger.info(f"Order Blocks {ticker} {timeframe}: {len(recent_obs)} found")
            return recent_obs
        except Exception as e:
            logger.error(f"OB detection error: {e}")
            return []
    
    def detect_fair_value_gaps(self, ticker="BTC/USDT", timeframe='1h', lookback=50):
        """Fair Value Gap detection + VOLUME validation"""
        try:
            ohlcv = self.get_ohlcv(ticker, timeframe, limit=lookback)
            fvgs = []
            
            for i in range(1, len(ohlcv) - 1):
                candle_before = ohlcv[i-1]
                candle = ohlcv[i]
                candle_after = ohlcv[i+1]
                
                if candle_after[3] > candle_before[2]:
                    volume_analysis = self.analyze_volume(ohlcv[:i+2], lookback=20)
                    
                    fvgs.append({
                        'type': 'bullish',
                        'gap_high': candle_after[3],
                        'gap_low': candle_before[2],
                        'gap_size': candle_after[3] - candle_before[2],
                        'index': i,
                        'volume_confirmed': volume_analysis['spike'],
                        'volume_strength': volume_analysis['strength']
                    })
                
                elif candle_after[2] < candle_before[3]:
                    volume_analysis = self.analyze_volume(ohlcv[:i+2], lookback=20)
                    
                    fvgs.append({
                        'type': 'bearish',
                        'gap_high': candle_before[3],
                        'gap_low': candle_after[2],
                        'gap_size': candle_before[3] - candle_after[2],
                        'index': i,
                        'volume_confirmed': volume_analysis['spike'],
                        'volume_strength': volume_analysis['strength']
                    })
            
            recent_fvgs = fvgs[-5:] if len(fvgs) > 5 else fvgs
            logger.info(f"FVG {ticker} {timeframe}: {len(recent_fvgs)} found")
            return recent_fvgs
        except Exception as e:
            logger.error(f"FVG detection error: {e}")
            return []
    
    def detect_liquidity_sweep(self, ticker="BTC/USDT", timeframe='1h', lookback=50):
        """Liquidity Sweep detection"""
        try:
            ohlcv = self.get_ohlcv(ticker, timeframe, limit=lookback)
            
            highs = [x[2] for x in ohlcv[-20:]]
            lows = [x[3] for x in ohlcv[-20:]]
            
            recent_high = max(highs[:-1])
            recent_low = min(lows[:-1])
            
            last_candle = ohlcv[-1]
            volume_analysis = self.analyze_volume(ohlcv, lookback=20)
            
            if last_candle[2] > recent_high and last_candle[4] < recent_high:
                return {
                    'detected': True,
                    'type': 'high',
                    'swept_level': recent_high,
                    'current_price': last_candle[4],
                    'volume_spike': volume_analysis['spike'],
                    'volume_strength': volume_analysis['strength']
                }
            
            elif last_candle[3] < recent_low and last_candle[4] > recent_low:
                return {
                    'detected': True,
                    'type': 'low',
                    'swept_level': recent_low,
                    'current_price': last_candle[4],
                    'volume_spike': volume_analysis['spike'],
                    'volume_strength': volume_analysis['strength']
                }
            
            return {
                'detected': False,
                'type': None,
                'volume_spike': False
            }
        except Exception as e:
            logger.error(f"Liquidity sweep error: {e}")
            return {'detected': False, 'type': None}
    
    def calculate_stop_loss(self, ticker="BTC/USDT", fixed_amount=1000):
        """Stop Loss - Sabit $1000 pay"""
        try:
            current_price = self.get_current_price(ticker)
            stop_price = current_price - fixed_amount
            
            return {
                'current_price': round(current_price, 8),
                'stop_price': round(stop_price, 8),
                'distance': fixed_amount
            }
        except Exception as e:
            logger.error(f"Stop Loss error: {e}")
            raise
    
    def get_complete_analysis_data(self, ticker="BTC/USDT"):
        """KOMPLE ANALİZ DATA - Multi-timeframe + Volume + Smart Money"""
        try:
            current_price = self.get_current_price(ticker)
            prev_candle = self.get_previous_day_candle(ticker)
            
            atr_1d = self.calculate_atr(ticker, '1d', 14)
            atr_4h = self.calculate_atr(ticker, '4h', 14)
            atr_1h = self.calculate_atr(ticker, '1h', 14)
            atr_15m = self.calculate_atr(ticker, '15m', 14)
            atr_5m = self.calculate_atr(ticker, '5m', 14)
            atr_3m = self.calculate_atr(ticker, '3m', 14)
            
            try:
                atr_2m = self.calculate_atr(ticker, '2m', 14)
            except:
                atr_2m = None
            
            fibo = self.calculate_fibonacci(ticker, use_pdc=True)
            stop = self.calculate_stop_loss(ticker, 1000)
            
            ohlcv_1d = self.get_ohlcv(ticker, '1d', limit=30)
            ohlcv_4h = self.get_ohlcv(ticker, '4h', limit=48)
            ohlcv_1h = self.get_ohlcv(ticker, '1h', limit=24)
            ohlcv_15m = self.get_ohlcv(ticker, '15m', limit=24)
            ohlcv_5m = self.get_ohlcv(ticker, '5m', limit=30)
            ohlcv_3m = self.get_ohlcv(ticker, '3m', limit=30)
            
            try:
                ohlcv_2m = self.get_ohlcv(ticker, '2m', limit=30)
            except:
                ohlcv_2m = None
            
            volume_1d = self.analyze_volume(ohlcv_1d, lookback=20)
            volume_4h = self.analyze_volume(ohlcv_4h, lookback=20)
            volume_1h = self.analyze_volume(ohlcv_1h, lookback=20)
            volume_15m = self.analyze_volume(ohlcv_15m, lookback=20)
            volume_5m = self.analyze_volume(ohlcv_5m, lookback=20)
            volume_3m = self.analyze_volume(ohlcv_3m, lookback=20)
            
            if ohlcv_2m:
                volume_2m = self.analyze_volume(ohlcv_2m, lookback=20)
            else:
                volume_2m = None
            
            obs_4h = self.detect_order_blocks(ticker, '4h', lookback=50)
            obs_1h = self.detect_order_blocks(ticker, '1h', lookback=50)
            obs_15m = self.detect_order_blocks(ticker, '15m', lookback=50)
            obs_5m = self.detect_order_blocks(ticker, '5m', lookback=50)
            obs_3m = self.detect_order_blocks(ticker, '3m', lookback=50)
            
            fvgs_4h = self.detect_fair_value_gaps(ticker, '4h', lookback=50)
            fvgs_1h = self.detect_fair_value_gaps(ticker, '1h', lookback=50)
            fvgs_15m = self.detect_fair_value_gaps(ticker, '15m', lookback=50)
            fvgs_5m = self.detect_fair_value_gaps(ticker, '5m', lookback=50)
            fvgs_3m = self.detect_fair_value_gaps(ticker, '3m', lookback=50)
            
            sweep_1h = self.detect_liquidity_sweep(ticker, '1h', lookback=50)
            
            result = {
                'ticker': ticker,
                'current_date': get_turkey_time().strftime('%Y-%m-%d'),
                'current_time': get_turkey_time().strftime('%H:%M:%S'),
                'current_price': current_price,
                'previous_day': prev_candle,
                'atr': {
                    '1d': atr_1d,
                    '4h': atr_4h,
                    '1h': atr_1h,
                    '15m': atr_15m,
                    '5m': atr_5m,
                    '3m': atr_3m,
                    '2m': atr_2m if atr_2m else 'N/A'
                },
                'fibonacci': fibo,
                'stop_loss': stop,
                'volume': {
                    '1d': volume_1d,
                    '4h': volume_4h,
                    '1h': volume_1h,
                    '15m': volume_15m,
                    '5m': volume_5m,
                    '3m': volume_3m,
                    '2m': volume_2m if volume_2m else 'N/A'
                },
                'smart_money': {
                    'order_blocks': {
                        '4h': obs_4h,
                        '1h': obs_1h,
                        '15m': obs_15m,
                        '5m': obs_5m,
                        '3m': obs_3m
                    },
                    'fair_value_gaps': {
                        '4h': fvgs_4h,
                        '1h': fvgs_1h,
                        '15m': fvgs_15m,
                        '5m': fvgs_5m,
                        '3m': fvgs_3m
                    },
                    'liquidity_sweep': sweep_1h
                }
            }
            
            logger.info(f"Complete analysis data prepared for {ticker}")
            return result
        except Exception as e:
            logger.error(f"Complete analysis error: {e}")
            raise
