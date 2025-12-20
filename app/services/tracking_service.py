# -*- coding: utf-8 -*-
"""
T-TARS Tracking Service v2.3.11
===============================
Setup Logging & Performance Analytics Service

v2.3.11:
- NEW: check_and_expire_orders() - TF bazlı otomatik expiry
  - 5m/3m → 2 saat
  - 15m/30m/1h/4h → 4 saat
- NEW: get_expiry_hours() - TF'ye göre expiry süresi
- CHANGED: main.py'deki expiry logic buraya taşındı

v2.2.8:
- NEW: mark_setup_expired() - 4 saat sonra dolmayan emirler için

v2.2.4:
- REMOVED: check_setup_status() - Ezbere fiyat karşılaştırması KALDIRILDI
- NEW: update_setup_from_bitget() - Bitget'ten gelen gerçek sonuçla güncelle
- NEW: mark_setup_completed() - Manuel tamamlama
- CHANGED: Artık sadece log tutuyor, takip Bitget API üzerinden yapılıyor
"""

from google.cloud import storage
import json
import logging
from datetime import datetime, timezone, timedelta
import uuid

logger = logging.getLogger(__name__)

TURKEY_TZ = timezone(timedelta(hours=3))
MIN_TRADES_FOR_RANKING = 3

# v2.3.11: TF bazlı expiry süreleri (saat)
EXPIRY_HOURS_SHORT_TF = 2   # 5m, 3m
EXPIRY_HOURS_LONG_TF = 4    # 15m, 30m, 1h, 4h


def get_expiry_hours(timeframe):
    """
    v2.3.11: Timeframe'e göre expiry süresi döndür
    
    Args:
        timeframe: '5m', '15m', '1h', '5D', '15D' vb.
    
    Returns:
        int: Expiry süresi (saat)
    """
    short_tfs = ['3m', '5m', '3D', '5D']  # D = dakika formatı
    
    tf_lower = str(timeframe).lower()
    
    # 3m, 5m veya 3D, 5D → 2 saat
    if tf_lower in ['3m', '5m'] or timeframe in short_tfs:
        return EXPIRY_HOURS_SHORT_TF
    
    # Diğer tüm TF'ler → 4 saat
    return EXPIRY_HOURS_LONG_TF


def format_price(price):
    if price is None or price == 0:
        return "$0.00"
    abs_price = abs(price)
    if abs_price < 0.0001:
        return f"${price:.8f}"
    elif abs_price < 0.01:
        return f"${price:.6f}"
    elif abs_price < 1:
        return f"${price:.4f}"
    elif abs_price < 100:
        return f"${price:,.4f}"
    else:
        return f"${price:,.2f}"


def calculate_ranking_score(win_rate, trade_count):
    """Ağırlıklı sıralama skoru"""
    if trade_count == 0:
        return 0
    weight = 1 - (1 / (trade_count + 1))
    return win_rate * weight


class TrackingService:
    """Setup Logging & Performance Analytics Service v2.3.11"""
    
    def __init__(self, bucket_name='tars-trading-data'):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        logger.info(f"✅ Tracking Service v2.3.11 initialized: {bucket_name}")
    
    def check_and_expire_orders(self, exchange):
        """
        v2.3.11: TF bazlı otomatik expiry kontrolü
        
        Akış:
        1. PENDING durumundaki tüm setup'ları al
        2. Her birinin TF'sine göre expiry süresini hesapla
        3. Süre dolduysa → Bitget'te cancel et → EXPIRED işaretle
        
        Args:
            exchange: BitgetService instance (cancel_order için)
        
        Returns:
            tuple: (expired_count, cancelled_order_ids)
        """
        expired_count = 0
        cancelled_orders = []
        now = datetime.now(TURKEY_TZ)
        
        try:
            pending_setups = self.get_pending_setups()
            
            for setup in pending_setups:
                try:
                    setup_id = setup.get('setup_id')
                    order_id = setup.get('order_id')
                    status = setup.get('status')
                    created_at_str = setup.get('created_at')
                    timeframe = setup.get('timeframe', '15m')
                    pair = setup.get('pair', '')
                    
                    # Sadece PENDING ve order_id olan emirler
                    if status != 'PENDING' or not order_id or not created_at_str:
                        continue
                    
                    # TF bazlı expiry süresi
                    expiry_hours = get_expiry_hours(timeframe)
                    
                    # Yaş hesapla
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        # Timezone aware yap
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=TURKEY_TZ)
                        age_hours = (now - created_at).total_seconds() / 3600
                    except Exception as e:
                        logger.error(f"Date parse error ({setup_id}): {e}")
                        continue
                    
                    # Expiry kontrolü
                    if age_hours >= expiry_hours:
                        logger.info(f"⏰ Order expired ({age_hours:.1f}h >= {expiry_hours}h): {setup_id} [{timeframe}]")
                        
                        # 1. Bitget'te cancel et
                        try:
                            # Symbol format düzelt
                            if '/' not in pair:
                                symbol = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}"
                            else:
                                symbol = pair
                            
                            cancel_result = exchange.cancel_order(order_id, symbol)
                            
                            if cancel_result.get('success'):
                                cancelled_orders.append(order_id)
                                logger.info(f"✅ Order cancelled: {order_id}")
                            else:
                                logger.warning(f"⚠️ Cancel failed: {order_id} - {cancel_result.get('error', 'Unknown')}")
                        except Exception as e:
                            logger.error(f"Cancel order error ({order_id}): {e}")
                        
                        # 2. EXPIRED işaretle (cancel başarısız olsa bile)
                        self.mark_setup_expired(setup_id)
                        expired_count += 1
                        
                except Exception as e:
                    logger.error(f"Expiry check error ({setup.get('setup_id')}): {e}")
            
            if expired_count > 0:
                logger.info(f"📊 Expiry check complete: {expired_count} expired, {len(cancelled_orders)} cancelled")
            
            return expired_count, cancelled_orders
            
        except Exception as e:
            logger.error(f"❌ check_and_expire_orders error: {e}")
            return 0, []
    
    def log_setup(self, setup_data):
        """
        Setup/Trade kaydet
        
        v2.2.4: Sadece kayıt tutar, takip yapmaz
        """
        try:
            pair = setup_data['pair']
            timeframe = setup_data.get('timeframe', 'N/A')
            setup_type = setup_data['setup_type']
            
            setup_id = str(uuid.uuid4())[:8]
            
            balance = setup_data.get('balance_before', 500.0)
            risk_percent = setup_data.get('risk_percent', 2.0)
            risk_dollars = balance * (risk_percent / 100)
            
            entry_price = setup_data.get('entry_price', setup_data.get('current_price', 0))
            current_price = setup_data.get('current_price', 0)
            stop_price = setup_data.get('stop_price', setup_data.get('stop_loss', 0))
            tp1_price = setup_data.get('tp1_price', setup_data.get('tp1', 0))
            tp2_price = setup_data.get('tp2_price', setup_data.get('tp2', 0))
            entry_zone_val = setup_data.get('entry_zone', entry_price)
            
            # Bitget order bilgileri
            order_id = setup_data.get('order_id')
            tracking_no = setup_data.get('tracking_no')
            contracts = setup_data.get('contracts', 0)
            position_usd = setup_data.get('position_usd', 0)
            
            setup_record = {
                'setup_id': setup_id,
                'pair': pair,
                'timestamp': setup_data.get('timestamp', datetime.now(TURKEY_TZ).isoformat()),
                'setup_type': setup_type,
                'confidence': setup_data.get('confidence', 'MEDIUM'),
                'timeframe': timeframe,
                'direction': setup_data.get('direction', 'long' if 'LONG' in setup_type else 'short'),
                
                # Fiyatlar
                'entry_zone': entry_zone_val,
                'entry_price': entry_price,
                'current_price': current_price,
                'stop_price': stop_price,
                'stop_loss': stop_price,
                'tp1_price': tp1_price,
                'tp1': tp1_price,
                'tp2_price': tp2_price,
                'tp2': tp2_price,
                
                # Risk/Reward
                'volume_spike_ratio': setup_data.get('volume_spike_ratio', 0),
                'ob_strength': setup_data.get('ob_strength', 'medium'),
                'rr_ratio': setup_data.get('rr_ratio', 0),
                'balance_before': balance,
                'risk_percent': risk_percent,
                'risk_dollars': risk_dollars,
                
                # Bitget Order Info - v2.2.4
                'order_id': order_id,
                'tracking_no': tracking_no,
                'contracts': contracts,
                'position_usd': position_usd,
                
                # Status - Bitget'ten güncellenecek
                'status': 'PENDING',  # PENDING, FILLED, TP1, TP2, STOPPED, CANCELLED, EXPIRED
                'result': None,       # WIN, LOSS, BREAKEVEN, None
                'profit_loss': 0.0,
                'profit_loss_percent': 0.0,
                'balance_after': balance,
                
                # Timestamps
                'created_at': datetime.now(TURKEY_TZ).isoformat(),
                'filled_at': None,
                'closed_at': None,
                'expired_at': None,
                'duration_minutes': None,
                
                # Bitget gerçek veriler - sonradan güncellenecek
                'bitget_entry_price': None,
                'bitget_close_price': None,
                'bitget_pnl': None,
                'bitget_fee': None,
            }
            
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            blob.upload_from_string(
                json.dumps(setup_record, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Setup logged: {setup_id} | {pair} {setup_type} | TF:{timeframe} | "
                       f"Entry:{format_price(entry_price)} | trackingNo:{tracking_no}")
            return setup_id
            
        except Exception as e:
            logger.error(f"❌ Log setup error: {e}")
            raise
    
    def mark_setup_expired(self, setup_id):
        """
        v2.2.8: Emir expire edildiğinde çağır
        
        Status: PENDING → EXPIRED
        """
        try:
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            
            if not blob.exists():
                logger.warning(f"⚠️ Setup not found: {setup_id}")
                return False
            
            setup = json.loads(blob.download_as_string())
            old_status = setup['status']
            
            # Sadece PENDING durumundaki emirler expire edilebilir
            if old_status != 'PENDING':
                logger.warning(f"⚠️ Setup {setup_id} not PENDING ({old_status}), skipping expire")
                return False
            
            setup['status'] = 'EXPIRED'
            setup['expired_at'] = datetime.now(TURKEY_TZ).isoformat()
            setup['closed_at'] = datetime.now(TURKEY_TZ).isoformat()
            setup['result'] = None  # Expire = ne win ne loss
            
            # Duration hesapla
            start_time = setup.get('created_at')
            if start_time:
                try:
                    start = datetime.fromisoformat(start_time)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=TURKEY_TZ)
                    now = datetime.now(TURKEY_TZ)
                    setup['duration_minutes'] = round((now - start).total_seconds() / 60, 1)
                except:
                    pass
            
            blob.upload_from_string(
                json.dumps(setup, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"⏰ Setup {setup_id} marked as EXPIRED (was {old_status})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Mark setup expired error: {e}")
            return False
    
    def update_setup_from_bitget(self, setup_id, bitget_data):
        """
        v2.2.4: Bitget'ten gelen gerçek verilerle güncelle
        
        Args:
            setup_id: Setup ID
            bitget_data: {
                'status': 'FILLED' | 'TP1' | 'TP2' | 'STOPPED' | 'CANCELLED',
                'result': 'WIN' | 'LOSS' | 'BREAKEVEN' | None,
                'pnl': float,  # Gerçek P/L
                'fee': float,  # İşlem ücreti
                'entry_price': float,  # Gerçek giriş fiyatı
                'close_price': float,  # Kapanış fiyatı
            }
        """
        try:
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            
            if not blob.exists():
                logger.warning(f"⚠️ Setup not found: {setup_id}")
                return False
            
            setup = json.loads(blob.download_as_string())
            old_status = setup['status']
            
            # Güncelle
            new_status = bitget_data.get('status', setup['status'])
            setup['status'] = new_status
            
            if bitget_data.get('result'):
                setup['result'] = bitget_data['result']
            
            if bitget_data.get('pnl') is not None:
                setup['bitget_pnl'] = bitget_data['pnl']
                setup['profit_loss'] = bitget_data['pnl']
                setup['balance_after'] = setup['balance_before'] + bitget_data['pnl']
                
                if setup['balance_before'] > 0:
                    setup['profit_loss_percent'] = (bitget_data['pnl'] / setup['balance_before']) * 100
            
            if bitget_data.get('fee') is not None:
                setup['bitget_fee'] = bitget_data['fee']
            
            if bitget_data.get('entry_price'):
                setup['bitget_entry_price'] = bitget_data['entry_price']
            
            if bitget_data.get('close_price'):
                setup['bitget_close_price'] = bitget_data['close_price']
            
            # Filled timestamp
            if new_status == 'FILLED' and not setup.get('filled_at'):
                setup['filled_at'] = datetime.now(TURKEY_TZ).isoformat()
            
            # Closed timestamp & duration
            if new_status in ['TP1', 'TP2', 'STOPPED', 'CANCELLED', 'CLOSED'] and not setup.get('closed_at'):
                setup['closed_at'] = datetime.now(TURKEY_TZ).isoformat()
                
                start_time = setup.get('filled_at') or setup.get('created_at')
                if start_time:
                    try:
                        start = datetime.fromisoformat(start_time)
                        if start.tzinfo is None:
                            start = start.replace(tzinfo=TURKEY_TZ)
                        now = datetime.now(TURKEY_TZ)
                        setup['duration_minutes'] = round((now - start).total_seconds() / 60, 1)
                    except:
                        pass
            
            blob.upload_from_string(
                json.dumps(setup, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Setup {setup_id} updated from Bitget: {old_status} → {new_status} | "
                       f"P/L: {format_price(setup.get('profit_loss', 0))}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Update setup from Bitget error: {e}")
            return False
    
    def mark_setup_filled(self, setup_id, tracking_no=None, entry_price=None):
        """
        v2.2.4: Emir dolduğunda çağır
        """
        try:
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            
            if not blob.exists():
                return False
            
            setup = json.loads(blob.download_as_string())
            
            setup['status'] = 'FILLED'
            setup['filled_at'] = datetime.now(TURKEY_TZ).isoformat()
            
            if tracking_no:
                setup['tracking_no'] = tracking_no
            
            if entry_price:
                setup['bitget_entry_price'] = entry_price
            
            blob.upload_from_string(
                json.dumps(setup, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Setup {setup_id} marked as FILLED | trackingNo: {tracking_no}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Mark setup filled error: {e}")
            return False
    
    def get_setup_by_tracking_no(self, tracking_no):
        """
        v2.2.4: trackingNo ile setup bul
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    if setup.get('tracking_no') == tracking_no:
                        return setup
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Get setup by tracking_no error: {e}")
            return None
    
    def get_setup_by_order_id(self, order_id):
        """
        v2.2.4: order_id ile setup bul
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    if setup.get('order_id') == order_id:
                        return setup
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Get setup by order_id error: {e}")
            return None
    
    def get_pending_setups(self):
        """
        v2.2.4: Sadece PENDING ve FILLED durumundaki setup'lar
        (Henüz kapanmamış pozisyonlar)
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            pending = []
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    
                    if setup['status'] in ['PENDING', 'FILLED']:
                        pending.append({
                            'setup_id': setup['setup_id'],
                            'pair': setup['pair'],
                            'direction': setup.get('direction', 'long'),
                            'setup_type': setup['setup_type'],
                            'timeframe': setup.get('timeframe', 'N/A'),
                            'order_id': setup.get('order_id'),
                            'tracking_no': setup.get('tracking_no'),
                            'entry_price': setup.get('entry_price', 0),
                            'stop_price': setup.get('stop_price', 0),
                            'tp1_price': setup.get('tp1_price', 0),
                            'tp2_price': setup.get('tp2_price', 0),
                            'status': setup['status'],
                            'created_at': setup.get('created_at'),
                        })
                except:
                    continue
            
            logger.info(f"📊 Pending/Filled setups: {len(pending)}")
            return pending
            
        except Exception as e:
            logger.error(f"❌ Get pending setups error: {e}")
            return []
    
    def get_aggregate_stats(self, real_balance=None):
        """
        /score komutu için aggregate istatistikler
        
        v2.2.8: EXPIRED status eklendi
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            total_setups = 0
            winning_trades = 0
            losing_trades = 0
            breakeven_trades = 0
            pending_setups = 0
            expired_setups = 0
            
            starting_balance = real_balance if real_balance and real_balance > 0 else 500.0
            total_profit_loss = 0.0
            
            setup_type_stats = {}
            total_duration = 0
            completed_trades = 0
            
            timeframe_stats = {}
            coin_stats = {}
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    total_setups += 1
                    
                    tf = setup.get('timeframe', 'N/A')
                    if tf not in timeframe_stats:
                        timeframe_stats[tf] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'breakeven': 0, 'expired': 0}
                    timeframe_stats[tf]['total'] += 1
                    
                    coin = setup.get('pair', 'UNKNOWN').replace('USDT', '').replace('/USDT:USDT', '')
                    if coin not in coin_stats:
                        coin_stats[coin] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'expired': 0}
                    coin_stats[coin]['total'] += 1
                    
                    if setup.get('duration_minutes'):
                        total_duration += setup['duration_minutes']
                        completed_trades += 1
                    
                    result = setup.get('result')
                    status = setup.get('status')
                    
                    # EXPIRED status
                    if status == 'EXPIRED':
                        expired_setups += 1
                        timeframe_stats[tf]['expired'] += 1
                        coin_stats[coin]['expired'] += 1
                        continue
                    
                    if result in ['WIN', 'PARTIAL_WIN']:
                        winning_trades += 1
                        total_profit_loss += setup.get('profit_loss', 0)
                        timeframe_stats[tf]['wins'] += 1
                        coin_stats[coin]['wins'] += 1
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['wins'] += 1
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif result == 'LOSS':
                        losing_trades += 1
                        total_profit_loss += setup.get('profit_loss', 0)
                        timeframe_stats[tf]['losses'] += 1
                        coin_stats[coin]['losses'] += 1
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif result == 'BREAKEVEN':
                        breakeven_trades += 1
                        timeframe_stats[tf]['breakeven'] += 1
                    
                    elif status in ['PENDING', 'FILLED']:
                        pending_setups += 1
                        timeframe_stats[tf]['pending'] += 1
                        coin_stats[coin]['pending'] += 1
                        
                except Exception:
                    continue
            
            completed_count = winning_trades + losing_trades
            win_rate = (winning_trades / completed_count * 100) if completed_count > 0 else 0
            loss_rate = (losing_trades / completed_count * 100) if completed_count > 0 else 0
            
            current_balance = starting_balance + total_profit_loss
            profit_percent = (total_profit_loss / starting_balance * 100) if starting_balance > 0 else 0
            
            avg_duration = (total_duration / completed_trades) if completed_trades > 0 else 0
            
            # Best setup type
            best_setup_type = "N/A"
            best_win_rate = 0
            for setup_type, stats in setup_type_stats.items():
                if stats['total'] >= MIN_TRADES_FOR_RANKING:
                    type_win_rate = (stats['wins'] / stats['total'] * 100)
                    if type_win_rate > best_win_rate:
                        best_win_rate = type_win_rate
                        best_setup_type = f"{setup_type}: {type_win_rate:.0f}%"
            
            # Coin breakdown
            coin_breakdown = {}
            for coin, stats in coin_stats.items():
                coin_completed = stats['wins'] + stats['losses']
                coin_win_rate = (stats['wins'] / coin_completed * 100) if coin_completed > 0 else 0
                coin_loss_rate = (stats['losses'] / coin_completed * 100) if coin_completed > 0 else 0
                coin_breakdown[coin] = {
                    'total': stats['total'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'pending': stats['pending'],
                    'expired': stats.get('expired', 0),
                    'completed': coin_completed,
                    'win_rate': round(coin_win_rate, 1),
                    'loss_rate': round(coin_loss_rate, 1)
                }
            
            # Top/Worst coins
            coins_for_ranking = [(c, s) for c, s in coin_breakdown.items() if s['completed'] >= MIN_TRADES_FOR_RANKING]
            
            sorted_coins_top = sorted(coins_for_ranking, key=lambda x: calculate_ranking_score(x[1]['win_rate'], x[1]['completed']), reverse=True)
            top_5_coins = sorted_coins_top[:5]
            
            sorted_coins_worst = sorted(coins_for_ranking, key=lambda x: calculate_ranking_score(x[1]['win_rate'], x[1]['completed']))
            worst_5_coins = sorted_coins_worst[:5]
            
            # Timeframe breakdown
            timeframe_breakdown = {}
            for tf, stats in timeframe_stats.items():
                tf_completed = stats['wins'] + stats['losses']
                tf_win_rate = (stats['wins'] / tf_completed * 100) if tf_completed > 0 else 0
                tf_loss_rate = (stats['losses'] / tf_completed * 100) if tf_completed > 0 else 0
                timeframe_breakdown[tf] = {
                    'total': stats['total'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'pending': stats['pending'],
                    'breakeven': stats['breakeven'],
                    'expired': stats.get('expired', 0),
                    'completed': tf_completed,
                    'win_rate': round(tf_win_rate, 1),
                    'loss_rate': round(tf_loss_rate, 1)
                }
            
            # Top/Worst timeframes
            tfs_for_ranking = [(tf, s) for tf, s in timeframe_breakdown.items() if s['completed'] >= MIN_TRADES_FOR_RANKING]
            
            sorted_tfs_top = sorted(tfs_for_ranking, key=lambda x: calculate_ranking_score(x[1]['win_rate'], x[1]['completed']), reverse=True)
            top_5_timeframes = sorted_tfs_top[:5]
            
            sorted_tfs_worst = sorted(tfs_for_ranking, key=lambda x: calculate_ranking_score(x[1]['win_rate'], x[1]['completed']))
            worst_5_timeframes = sorted_tfs_worst[:5]
            
            result = {
                'total_setups': total_setups,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': breakeven_trades,
                'pending_setups': pending_setups,
                'expired_setups': expired_setups,
                'win_rate': round(win_rate, 1),
                'loss_rate': round(loss_rate, 1),
                'starting_balance': starting_balance,
                'current_balance': current_balance,
                'profit': total_profit_loss,
                'profit_percent': round(profit_percent, 1),
                'best_setup_type': best_setup_type,
                'avg_duration_minutes': round(avg_duration, 1),
                'timeframe_breakdown': timeframe_breakdown,
                'coin_breakdown': coin_breakdown,
                'top_5_coins': top_5_coins,
                'worst_5_coins': worst_5_coins,
                'top_5_timeframes': top_5_timeframes,
                'worst_5_timeframes': worst_5_timeframes,
            }
            
            logger.info(f"📊 Stats: {winning_trades}W/{losing_trades}L/{breakeven_trades}BE/{pending_setups}P/{expired_setups}E ({win_rate:.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get aggregate stats error: {e}")
            return {
                'total_setups': 0, 'winning_trades': 0, 'losing_trades': 0,
                'breakeven_trades': 0, 'pending_setups': 0, 'expired_setups': 0,
                'win_rate': 0, 'loss_rate': 0,
                'starting_balance': real_balance or 500.0, 'current_balance': real_balance or 500.0,
                'profit': 0, 'profit_percent': 0, 'best_setup_type': 'N/A',
                'avg_duration_minutes': 0, 'timeframe_breakdown': {}, 'coin_breakdown': {},
                'top_5_coins': [], 'worst_5_coins': [],
                'top_5_timeframes': [], 'worst_5_timeframes': [],
            }
    
    def reset_all_tracking(self):
        """Tüm tracking verilerini sıfırla"""
        try:
            blobs = list(self.bucket.list_blobs(prefix='setups/'))
            deleted_count = 0
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    blob.delete()
                    deleted_count += 1
            
            reset_time = datetime.now(TURKEY_TZ).isoformat()
            meta_blob = self.bucket.blob('meta/last_reset.json')
            meta_blob.upload_from_string(
                json.dumps({'last_reset': reset_time, 'deleted_count': deleted_count}),
                content_type='application/json'
            )
            
            logger.info(f"🗑️ Reset complete: {deleted_count} setups deleted at {reset_time}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Reset tracking error: {e}")
            return False
    
    def get_last_reset_time(self):
        """Son reset zamanını getir"""
        try:
            meta_blob = self.bucket.blob('meta/last_reset.json')
            if meta_blob.exists():
                data = json.loads(meta_blob.download_as_string())
                return data.get('last_reset', None)
            return None
        except Exception as e:
            logger.error(f"❌ Get last reset error: {e}")
            return None
