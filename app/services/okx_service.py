# -*- coding: utf-8 -*-
"""
T-TARS OKX Service v2.1.2
=========================
OKX Exchange Service

v2.1.2:
- NEW: Market -> Limit emir (daha dusuk komisyon, slippage yok)
- FIX: TP/SL artik attachAlgoOrds array ile gonderiliyor (OKX API v5)
- FIX: Parameter ordType error (51000) duzeltildi

v2.1.1:
- FIX: tdMode 'isolated' -> 'cross' (Cross Margin)
- FIX: 'hedged' parametresi kaldirildi (OKX API hatasi)

v2.0.9:
- 10m timeframe kaldirildi (OKX desteklemiyor)
"""

import ccxt
from datetime import datetime, timedelta, timezone
import logging
from app.config import Config
from app.strategies.ob_detector import scan_order_blocks
from app.strategies.fvg_detector import scan_fair_value_gaps

TURKEY_TZ = timezone(timedelta(hours=3))
logger = logging.getLogger(__name__)

def get_turkey_time():
    return datetime.now(TURKEY_TZ)

class OKXService:
    """OKX Borsa Servisi - v2.1.2 (Limit Order + attachAlgoOrds)"""
    
    TIMEFRAME_MAP = {
        '1G': '1d', '1d': '1d',
        '4S': '4h', '4h': '4h',
        '2S': '2h', '2h': '2h',
        '1S': '1h', '1h': '1h',
        '30D': '30m', '30m': '30m',
        '15D': '15m', '15m': '15m',
        '5D': '5m', '5m': '5m',
        '3D': '3m', '3m': '3m'
    }
    
    ANALYSIS_TIMEFRAMES = ['4h', '2h', '1h', '30m', '15m', '5m', '3m']
    
    def __init__(self):
        self.authenticated = False
        self.exchange = None
        
        try:
            config = {
                'apiKey': Config.OKX_API_KEY,
                'secret': Config.OKX_SECRET_KEY,
                'password': Config.OKX_PASSPHRASE,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'}
            }
            
            if config['apiKey'] and config['secret']:
                self.authenticated = True
            else:
                logger.warning("⚠️ OKX Kimlik Bilgileri Eksik")

            self.exchange = ccxt.okx(config)
            
            if self.authenticated:
                if Config.OKX_DEMO_MODE:
                    self.exchange.set_sandbox_mode(True)
                    logger.info("🟡 OKX DEMO MOD")
                else:
                    logger.info("🔥 OKX LIVE MOD")
                
                self.exchange.load_markets()
                self._configure_account_mode()

            self._market_cache = {}
            logger.info(f"OKX Servisi v2.1.2 Hazir (Lev: {Config.DEFAULT_LEVERAGE}x, Mode: CROSS, Order: LIMIT)")

        except Exception as e:
            logger.error(f"OKX Başlatma Hatası: {e}")

    def check_connection(self):
        try:
            self.exchange.fetch_time()
            return True
        except:
            return False

    def _require_auth(self):
        if not self.authenticated:
            raise Exception("❌ OKX Yetkilendirme Hatası")

    def _configure_account_mode(self):
        """Hesabı Hedge Moduna zorla"""
        try:
            self.exchange.private_post_account_set_position_mode({'posMode': 'long_short_mode'})
            logger.info("✅ OKX: Hedge Mode Aktif")
        except Exception as e:
            logger.info(f"ℹ️ Position Mode: {e}")

    def _normalize_symbol(self, symbol):
        if ':' in symbol:
            return symbol
        symbol = symbol.replace('/', '')
        return f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"

    def set_leverage(self, symbol, leverage=None):
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            lev = leverage or Config.DEFAULT_LEVERAGE
            # v2.1.1: Cross margin için leverage ayarı
            self.exchange.set_leverage(lev, symbol, params={'mgnMode': 'cross', 'posSide': 'long'})
            self.exchange.set_leverage(lev, symbol, params={'mgnMode': 'cross', 'posSide': 'short'})
            return {'success': True}
        except Exception as e:
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
                'open': p[1],
                'high': p[2],
                'low': p[3],
                'close': p[4],
                'volume': p[5],
                'candle_type': candle_type,
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
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_list.append(tr)
            
            return sum(tr_list[-period:]) / period
        except Exception as e:
            logger.error(f"ATR error: {e}")
            return 0

    def calculate_fibonacci(self, ticker):
        try:
            pdc = self.get_previous_day_candle(ticker)
            high = pdc['high']
            low = pdc['low']
            diff = high - low
            
            levels = {
                '0.0': low,
                '23.6': low + (diff * 0.236),
                '38.2': low + (diff * 0.382),
                '50.0': low + (diff * 0.5),
                '61.8': low + (diff * 0.618),
                '78.6': low + (diff * 0.786),
                '100.0': high
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
            
            if spike_ratio >= 3.0:
                strength = 'high'
            elif spike_ratio >= 2.0:
                strength = 'medium'
            else:
                strength = 'low'
            
            if len(ohlcv) >= 6:
                recent_vols = [c[5] for c in ohlcv[-5:]]
                if recent_vols[-1] > recent_vols[0]:
                    trend = 'increasing'
                elif recent_vols[-1] < recent_vols[0]:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'stable'
            
            return {
                'spike': spike,
                'spike_ratio': round(spike_ratio, 2),
                'strength': strength,
                'trend': trend
            }
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
            
            atr_data = {}
            volume_data = {}
            order_blocks = {}
            fair_value_gaps = {}
            
            for tf in self.ANALYSIS_TIMEFRAMES:
                try:
                    ohlcv = self.get_ohlcv(symbol, tf, 100)
                    
                    if not ohlcv or len(ohlcv) < 10:
                        logger.warning(f"⚠️ {coin_name} {tf}: Yetersiz veri")
                        atr_data[tf] = 0
                        volume_data[tf] = {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}
                        order_blocks[tf] = []
                        fair_value_gaps[tf] = []
                        continue
                    
                    atr_data[tf] = self.calculate_atr(symbol, tf, 14)
                    volume_data[tf] = self.analyze_volume_for_tf(ohlcv, 20)
                    order_blocks[tf] = scan_order_blocks(ohlcv, tf)
                    fair_value_gaps[tf] = scan_fair_value_gaps(ohlcv, tf)
                    
                except Exception as e:
                    logger.error(f"❌ {coin_name} {tf} error: {e}")
                    atr_data[tf] = 0
                    volume_data[tf] = {'spike': False, 'spike_ratio': 0.0, 'strength': 'low', 'trend': 'stable'}
                    order_blocks[tf] = []
                    fair_value_gaps[tf] = []
            
            result = {
                'current_price': current_price,
                'current_date': now.strftime('%Y-%m-%d'),
                'current_time': now.strftime('%H:%M:%S'),
                'previous_day': pdc,
                'fibonacci': fibo,
                'atr': atr_data,
                'volume': volume_data,
                'smart_money': {
                    'order_blocks': order_blocks,
                    'fair_value_gaps': fair_value_gaps
                }
            }
            
            total_obs = sum(len(obs) for obs in order_blocks.values())
            total_fvgs = sum(len(fvgs) for fvgs in fair_value_gaps.values())
            logger.info(f"✅ {coin_name}: Price=${current_price:.2f}, OBs={total_obs}, FVGs={total_fvgs}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Complete analysis error ({ticker}): {e}")
            return None

    # ============================================
    # ORDER METHODS - v2.1.2 LIMIT + attachAlgoOrds
    # ============================================
    
    def calculate_contracts(self, symbol, usd_amount, current_price):
        try:
            market = self.exchange.market(symbol)
            contract_value = market['contractSize']
            
            if current_price == 0:
                return 0
            
            notional_per_contract = contract_value * current_price
            contracts_needed = usd_amount / notional_per_contract
            contracts_final = max(1, round(contracts_needed))
            
            logger.info(f"🧮 {symbol}: ${usd_amount} / (${notional_per_contract:.2f}/kontrat) = {contracts_final} kontrat")
            return int(contracts_final)
            
        except Exception as e:
            logger.error(f"Kontrat Hesaplama Hatası: {e}")
            return 1

    def place_order_with_tp_sl(self, symbol, side, amount_usd, tp_price=None, sl_price=None, entry_price=None):
        """
        v2.1.2: LIMIT Order + attachAlgoOrds (OKX API v5)
        - Limit emir: Daha dusuk komisyon (maker fee), slippage yok
        - attachAlgoOrds: TP/SL dogru formatta gonderiliyor
        """
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            self.set_leverage(symbol)
            
            # Entry price ZORUNLU (limit order icin)
            if not entry_price:
                ticker = self.exchange.fetch_ticker(symbol)
                entry_price = ticker['last']
                logger.warning(f"⚠️ Entry price verilmedi, current price kullaniliyor: {entry_price}")

            contracts = self.calculate_contracts(symbol, amount_usd, entry_price)
            
            pos_side = 'long' if side.lower() == 'buy' else 'short'
            
            # v2.1.2: Cross margin params
            params = {
                'tdMode': 'cross',
                'posSide': pos_side,
            }
            
            # v2.1.2: attachAlgoOrds array kullan (OKX API v5 standardi)
            if tp_price or sl_price:
                attach_algo = {}
                
                if tp_price:
                    attach_algo['tpTriggerPx'] = str(tp_price)
                    attach_algo['tpOrdPx'] = '-1'  # -1 = market price when triggered
                    attach_algo['tpTriggerPxType'] = 'last'
                
                if sl_price:
                    attach_algo['slTriggerPx'] = str(sl_price)
                    attach_algo['slOrdPx'] = '-1'  # -1 = market price when triggered
                    attach_algo['slTriggerPxType'] = 'last'
                
                params['attachAlgoOrds'] = [attach_algo]
                logger.info(f"📎 attachAlgoOrds: TP={tp_price}, SL={sl_price}")

            logger.info(f"🚀 LIMIT EMIR: {symbol} {side} {pos_side} | {contracts} Kontrat | Entry:{entry_price} TP:{tp_price} SL:{sl_price}")
            
            # v2.1.2: LIMIT order (market degil)
            order = self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=contracts,
                price=entry_price,  # Limit fiyati
                params=params
            )
            
            logger.info(f"✅ LIMIT EMIR BASARILI: {order['id']} @ {entry_price}")
            return {'success': True, 'order_id': order['id'], 'contracts': contracts, 'entry_price': entry_price}
            
        except Exception as e:
            logger.error(f"❌ OKX EMIR HATASI: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_order(self, order_id, symbol):
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            return {'success': True, 'raw': self.exchange.cancel_order(order_id, symbol)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def close_position(self, symbol, side=None):
        """v2.1.2: Cross margin - market order ile kapat"""
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
            
            # v2.1.1: Cross margin
            params = {
                'tdMode': 'cross',
                'posSide': target_pos['side'],
                'reduceOnly': True,
            }
            
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=close_side,
                amount=float(target_pos['contracts']),
                params=params
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
                if float(p['contracts']) > 0:
                    clean_positions.append({
                        'symbol': p['symbol'],
                        'side': p['side'],
                        'contracts': p['contracts'],
                        'entry_price': p['entryPrice'],
                        'unrealized_pnl': p['unrealizedPnl'],
                        'leverage': p['leverage']
                    })
            return clean_positions
        except:
            return []

    def get_balance(self):
        self._require_auth()
        try:
            bal = self.exchange.fetch_balance()
            return {'success': True, 'total': bal['USDT']['total'], 'free': bal['USDT']['free']}
        except:
            return {'success': False, 'total': 0, 'free': 0}
