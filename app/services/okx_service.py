# -*- coding: utf-8 -*-
"""
T-TARS OKX Service v2.1.4
=========================
OKX Exchange Service

v2.1.4:
- CHANGED: ANALYSIS_TIMEFRAMES artik Config.TIMEFRAMES'den (3m, 5m kaldirildi)
- NEW: Stop mesafesi limitleri (min %0.8, max %1.5 - Config'den)
- NEW: Dinamik marjin limitleri (bakiyenin %1-2'si - Config'den)
- FIX: Price format fix ($0.00 sorunu - kucuk fiyatli coinler)

v2.1.3:
- NEW: Risk bazli pozisyon hesaplama (gercek bakiye x RISK_PER_TRADE)
- NEW: Pending order kontrolu (ayni coin'de bekleyen emir varsa skip)
- NEW: Acik pozisyon kontrolu (ayni coin'de pozisyon varsa skip)
- FIX: Scientific notation fix (kucuk fiyatli coinler icin)
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


def format_price_string(price):
    """
    v2.1.3: Scientific notation fix
    Kucuk fiyatli coinlerde 1.23e-05 yerine 0.0000123 formatinda string dondurur
    """
    if price is None or price == 0:
        return "0"
    return f"{float(price):.10f}".rstrip('0').rstrip('.')


def format_price_display(price):
    """
    v2.1.4: Log/mesaj icin okunabilir fiyat formati
    PEPE: 0.00001234 -> $0.00001234
    BTC: 95000.5 -> $95,000.50
    """
    if price is None or price == 0:
        return "$0.00"
    
    if price < 0.0001:
        # Cok kucuk fiyatlar (SHIB, PEPE, PUMP)
        return f"${price:.8f}"
    elif price < 1:
        # Kucuk fiyatlar
        return f"${price:.6f}"
    elif price < 100:
        # Orta fiyatlar
        return f"${price:.4f}"
    else:
        # Buyuk fiyatlar (BTC, ETH)
        return f"${price:,.2f}"


class OKXService:
    """OKX Borsa Servisi - v2.1.4 (Dinamik Marjin + Stop Limitleri)"""
    
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
            logger.info(f"OKX Servisi v2.1.4 Hazir | Lev:{Config.DEFAULT_LEVERAGE}x | "
                       f"Risk:%{Config.RISK_PER_TRADE} | Stop:{Config.STOP_DISTANCE_MIN*100:.1f}-{Config.STOP_DISTANCE_MAX*100:.1f}% | "
                       f"Marjin:%{Config.MARGIN_MIN_PERCENT}-{Config.MARGIN_MAX_PERCENT} | TFs:{len(Config.TIMEFRAMES)}")

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
        """
        v2.1.4: Config.TIMEFRAMES kullaniliyor (3m, 5m kaldirildi)
        v2.1.4: format_price_display ile log'da $0.00 sorunu duzeltildi
        """
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
            
            # v2.1.4: Config.TIMEFRAMES kullan (3m, 5m yok)
            for tf in Config.TIMEFRAMES:
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
            
            # v2.1.4: format_price_display kullan
            logger.info(f"✅ {coin_name}: Price={format_price_display(current_price)}, OBs={total_obs}, FVGs={total_fvgs}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Complete analysis error ({ticker}): {e}")
            return None

    # ============================================
    # ORDER METHODS - v2.1.4 DINAMIK MARJIN
    # ============================================
    
    def has_pending_orders(self, symbol):
        """
        v2.1.3: Bekleyen emir kontrolu
        Ayni symbol'de acik limit emir varsa True doner
        """
        try:
            symbol = self._normalize_symbol(symbol)
            open_orders = self.exchange.fetch_open_orders(symbol)
            if open_orders and len(open_orders) > 0:
                logger.info(f"⏳ {symbol}: {len(open_orders)} bekleyen emir var")
                return True
            return False
        except Exception as e:
            logger.error(f"Pending order check error: {e}")
            return False
    
    def has_open_position(self, symbol):
        """
        v2.1.3: Acik pozisyon kontrolu
        Ayni symbol'de acik pozisyon varsa True doner
        """
        try:
            symbol = self._normalize_symbol(symbol)
            positions = self.get_positions(symbol)
            if positions and len(positions) > 0:
                for pos in positions:
                    if float(pos.get('contracts', 0)) > 0:
                        logger.info(f"📊 {symbol}: Açık pozisyon var ({pos['side']})")
                        return True
            return False
        except Exception as e:
            logger.error(f"Position check error: {e}")
            return False

    def calculate_contracts(self, symbol, usd_amount, current_price):
        """Kontrat hesaplama (degismedi)"""
        try:
            market = self.exchange.market(symbol)
            contract_value = market['contractSize']
            
            if current_price == 0:
                return 0
            
            notional_per_contract = contract_value * current_price
            contracts_needed = usd_amount / notional_per_contract
            contracts_final = max(1, round(contracts_needed))
            
            logger.info(f"🧮 {symbol}: ${usd_amount:.2f} / (${notional_per_contract:.4f}/kontrat) = {contracts_final} kontrat")
            return int(contracts_final)
            
        except Exception as e:
            logger.error(f"Kontrat Hesaplama Hatası: {e}")
            return 1

    def calculate_position_size(self, entry_price, stop_price):
        """
        v2.1.4: Risk bazli pozisyon + Stop limitleri + Dinamik marjin
        
        Degisiklikler:
        - Stop mesafesi min %0.8, max %1.5 (Config'den)
        - Marjin min %1, max %2 bakiye (Config'den)
        
        Formul:
        1. Stop mesafesi hesapla ve clamp et
        2. Risk = Bakiye x RISK_PER_TRADE%
        3. Pozisyon = Risk / Stop mesafesi
        4. Marjin = Pozisyon / Leverage
        5. Marjin'i min-max arasinda tut
        6. Final Pozisyon = Marjin x Leverage
        """
        try:
            # 1. Gercek bakiye al
            balance = self.get_balance()
            if not balance.get('success'):
                logger.error("❌ Bakiye alinamadi, fallback $500")
                real_balance = 500.0
            else:
                real_balance = float(balance['free'])
            
            # 2. Stop mesafesi hesapla
            stop_distance = abs(entry_price - stop_price)
            stop_distance_pct = stop_distance / entry_price if entry_price > 0 else 0.01
            
            # v2.1.4: Stop mesafesi limitleri (Config'den)
            original_stop_pct = stop_distance_pct
            stop_distance_pct = max(Config.STOP_DISTANCE_MIN, min(stop_distance_pct, Config.STOP_DISTANCE_MAX))
            
            stop_clamped = original_stop_pct != stop_distance_pct
            if stop_clamped:
                logger.info(f"📏 Stop mesafesi clamp: {original_stop_pct:.4%} → {stop_distance_pct:.4%}")
            
            # 3. Risk miktari hesapla
            risk_percent = Config.RISK_PER_TRADE / 100  # 1.0 -> 0.01
            risk_amount = real_balance * risk_percent
            
            # 4. Pozisyon boyutu (notional)
            position_size = risk_amount / stop_distance_pct
            
            # 5. v2.1.4: Dinamik marjin limitleri (Config'den)
            min_margin = real_balance * (Config.MARGIN_MIN_PERCENT / 100)
            max_margin = real_balance * (Config.MARGIN_MAX_PERCENT / 100)
            
            # Hesaplanan marjin
            calculated_margin = position_size / Config.DEFAULT_LEVERAGE
            
            # Marjin clamp
            original_margin = calculated_margin
            final_margin = max(min_margin, min(calculated_margin, max_margin))
            
            margin_clamped = original_margin != final_margin
            if margin_clamped:
                logger.info(f"💰 Marjin clamp: ${original_margin:.2f} → ${final_margin:.2f} (min:${min_margin:.2f}, max:${max_margin:.2f})")
            
            # 6. Final pozisyon boyutu
            final_position = final_margin * Config.DEFAULT_LEVERAGE
            
            logger.info(f"📐 Risk Hesabi: Bakiye=${real_balance:.2f} | Risk%={Config.RISK_PER_TRADE} | "
                       f"Risk$={risk_amount:.2f} | Stop={stop_distance_pct:.2%} | "
                       f"Marjin=${final_margin:.2f} | Pozisyon=${final_position:.2f}")
            
            return final_position
            
        except Exception as e:
            logger.error(f"Position size hesaplama hatasi: {e}")
            return 100.0  # Fallback

    def place_order_with_tp_sl(self, symbol, side, entry_price, stop_price, tp_price=None):
        """
        v2.1.4: Dinamik Marjin + Stop Limitleri ile LIMIT Order
        
        Degisiklikler:
        - calculate_position_size artik stop ve marjin limitlerini uyguluyor
        - format_price_display ile log'larda okunabilir fiyat
        """
        self._require_auth()
        try:
            symbol = self._normalize_symbol(symbol)
            coin_name = symbol.replace('/USDT:USDT', '')
            
            # v2.1.3: Pending order kontrolu
            if self.has_pending_orders(symbol):
                msg = f"⏳ {coin_name}: Bekleyen emir var, yeni emir ATLANACAK"
                logger.warning(msg)
                return {'success': False, 'error': msg, 'reason': 'pending_order_exists'}
            
            # v2.1.3: Acik pozisyon kontrolu
            if self.has_open_position(symbol):
                msg = f"📊 {coin_name}: Açık pozisyon var, yeni emir ATLANACAK"
                logger.warning(msg)
                return {'success': False, 'error': msg, 'reason': 'position_exists'}
            
            # Leverage ayarla
            self.set_leverage(symbol)
            
            # v2.1.4: Risk bazli + limit uygulanmis pozisyon boyutu
            position_usd = self.calculate_position_size(entry_price, stop_price)
            
            # Kontrat hesapla
            contracts = self.calculate_contracts(symbol, position_usd, entry_price)
            
            if contracts < 1:
                return {'success': False, 'error': 'Kontrat sayisi 0'}
            
            pos_side = 'long' if side.lower() == 'buy' else 'short'
            
            # Cross margin params
            params = {
                'tdMode': 'cross',
                'posSide': pos_side,
            }
            
            # attachAlgoOrds + Scientific notation fix
            if tp_price or stop_price:
                attach_algo = {}
                
                if tp_price:
                    attach_algo['tpTriggerPx'] = format_price_string(tp_price)
                    attach_algo['tpOrdPx'] = '-1'
                    attach_algo['tpTriggerPxType'] = 'last'
                
                if stop_price:
                    attach_algo['slTriggerPx'] = format_price_string(stop_price)
                    attach_algo['slOrdPx'] = '-1'
                    attach_algo['slTriggerPxType'] = 'last'
                
                params['attachAlgoOrds'] = [attach_algo]
                logger.info(f"📎 attachAlgoOrds: TP={format_price_string(tp_price)}, SL={format_price_string(stop_price)}")

            # Entry price format
            entry_str = format_price_string(entry_price)
            
            # v2.1.4: format_price_display kullan
            logger.info(f"🚀 LIMIT EMIR: {coin_name} {side.upper()} {pos_side} | "
                       f"{contracts} Kontrat | Entry:{format_price_display(entry_price)} | Pozisyon:${position_usd:.2f}")
            
            # LIMIT order
            order = self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=contracts,
                price=entry_price,
                params=params
            )
            
            logger.info(f"✅ EMIR BASARILI: {order['id']} | {coin_name} {pos_side.upper()} | "
                       f"{contracts} kontrat @ {format_price_display(entry_price)}")
            
            return {
                'success': True, 
                'order_id': order['id'], 
                'contracts': contracts, 
                'entry_price': entry_price,
                'position_usd': position_usd
            }
            
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
        """Cross margin - market order ile kapat"""
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
