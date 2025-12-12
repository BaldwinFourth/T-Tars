# -*- coding: utf-8 -*-
"""
T-TARS Tracking Service v2.1.1
==============================
Setup Tracking & Performance Analytics Service

v2.1.1:
- NEW: get_aggregate_stats(real_balance) → OKX balance parametresi
- NEW: Top 5 / Worst 5 coin (win rate bazlı)
- NEW: Top 5 / Worst 5 timeframe (win rate bazlı)
- FIX: Hardcoded 1000$ kaldırıldı

v2.0.3:
- coin_breakdown eklendi (/score için top 3 coin)
"""

from google.cloud import storage
import json
import logging
from datetime import datetime, timezone, timedelta
import uuid

logger = logging.getLogger(__name__)

TURKEY_TZ = timezone(timedelta(hours=3))


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


class TrackingService:
    """Setup Tracking & Performance Analytics Service"""
    
    def __init__(self, bucket_name='tars-trading-data'):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        logger.info(f"✅ Tracking Service initialized: {bucket_name}")
    
    def check_duplicate_setup(self, pair, timeframe, direction):
        """Duplicate detection - aynı pair+tf+direction için PENDING/TP1 setup var mı"""
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    
                    if setup['status'] not in ['PENDING', 'TP1']:
                        continue
                    if setup['pair'] != pair:
                        continue
                    if setup.get('timeframe', 'N/A') != timeframe:
                        continue
                    
                    setup_direction = 'LONG' if 'LONG' in setup['setup_type'] else 'SHORT'
                    if setup_direction != direction:
                        continue
                    
                    logger.info(f"⚠️ Duplicate detected: {pair} {timeframe} {direction} → existing #{setup['setup_id']}")
                    return setup['setup_id']
                    
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Duplicate check error: {e}")
            return None
    
    def log_setup(self, setup_data):
        """Setup detected olduğunda kaydet"""
        try:
            pair = setup_data['pair']
            timeframe = setup_data.get('timeframe', 'N/A')
            setup_type = setup_data['setup_type']
            direction = 'LONG' if 'LONG' in setup_type else 'SHORT'
            
            existing_id = self.check_duplicate_setup(pair, timeframe, direction)
            if existing_id:
                logger.info(f"⏭️ Skipping duplicate: {pair} {timeframe} {direction} (existing: #{existing_id})")
                return None
            
            setup_id = str(uuid.uuid4())[:8]
            
            # v2.1.1: balance_before artık main.py'den geliyor (gerçek OKX balance)
            balance = setup_data.get('balance_before', 500.0)
            risk_percent = setup_data.get('risk_percent', 2.0)
            risk_dollars = balance * (risk_percent / 100)
            
            entry_price = setup_data.get('entry_price', setup_data.get('current_price', 0))
            
            setup_record = {
                'setup_id': setup_id,
                'pair': pair,
                'timestamp': setup_data['timestamp'],
                'setup_type': setup_type,
                'confidence': setup_data['confidence'],
                'timeframe': timeframe,
                'entry_zone': setup_data['entry_zone'],
                'stop_loss': setup_data['stop_loss'],
                'tp1': setup_data['tp1'],
                'tp2': setup_data['tp2'],
                'current_price': setup_data['current_price'],
                'entry_price': entry_price,
                'stop_price': setup_data['stop_price'],
                'tp1_price': setup_data['tp1_price'],
                'tp2_price': setup_data['tp2_price'],
                'volume_spike_ratio': setup_data.get('volume_spike_ratio', 0),
                'ob_strength': setup_data.get('ob_strength', 'medium'),
                'rr_ratio': setup_data.get('rr_ratio', 0),
                'balance_before': balance,
                'risk_percent': risk_percent,
                'risk_dollars': risk_dollars,
                'status': 'PENDING',
                'result': None,
                'profit_loss': 0.0,
                'balance_after': balance,
                'movement_captured_dollars': 0.0,
                'created_at': datetime.now(TURKEY_TZ).isoformat(),
                'tp1_hit_at': None,
                'tp2_hit_at': None,
                'stop_hit_at': None,
                'duration_minutes': None
            }
            
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            blob.upload_from_string(
                json.dumps(setup_record, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Setup logged: {setup_id} ({pair}) TF:{timeframe} Entry:{format_price(entry_price)}")
            return setup_id
            
        except Exception as e:
            logger.error(f"❌ Log setup error: {e}")
            raise
    
    def check_setup_status(self, setup_id, current_price):
        """Bir setup'ın durumunu check et (TP/Stop hit kontrolü)"""
        try:
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            
            if not blob.exists():
                logger.warning(f"⚠️ Setup not found: {setup_id}")
                return {'status_changed': False, 'old_status': None, 'new_status': None, 'not_found': True}
            
            setup = json.loads(blob.download_as_string())
            
            old_status = setup['status']
            new_status = old_status
            message = ""
            
            if setup['status'] in ['COMPLETED', 'STOPPED']:
                return {'status_changed': False, 'old_status': old_status, 'new_status': new_status}
            
            setup_type = setup['setup_type']
            is_long = 'LONG' in setup_type
            
            entry = setup.get('entry_price', setup['current_price'])
            stop = setup['stop_price']
            tp1 = setup['tp1_price']
            tp2 = setup['tp2_price']
            balance_before = setup['balance_before']
            risk_dollars = setup.get('risk_dollars', balance_before * 0.02)
            rr_ratio = setup.get('rr_ratio', 2.0)
            
            # PENDING → TP1 veya STOPPED
            if setup['status'] == 'PENDING':
                if is_long and current_price >= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    partial_profit = risk_dollars * 1.0
                    setup['profit_loss'] = partial_profit
                    setup['balance_after'] = balance_before + partial_profit
                    setup['result'] = 'PARTIAL_WIN'
                    setup['movement_captured_dollars'] = abs(tp1 - entry)
                    message = "TP1_HIT"

                elif not is_long and current_price <= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    partial_profit = risk_dollars * 1.0
                    setup['profit_loss'] = partial_profit
                    setup['balance_after'] = balance_before + partial_profit
                    setup['result'] = 'PARTIAL_WIN'
                    setup['movement_captured_dollars'] = abs(entry - tp1)
                    message = "TP1_HIT"
                
                elif is_long and current_price <= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = -risk_dollars
                    setup['balance_after'] = balance_before - risk_dollars
                    setup['movement_captured_dollars'] = abs(entry - stop)
                    message = "STOP_HIT"

                elif not is_long and current_price >= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = -risk_dollars
                    setup['balance_after'] = balance_before - risk_dollars
                    setup['movement_captured_dollars'] = abs(stop - entry)
                    message = "STOP_HIT"
            
            # TP1 → TP2 (COMPLETED) veya BREAKEVEN
            elif setup['status'] == 'TP1':
                if is_long and current_price >= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    tp1_profit = risk_dollars * 1.0
                    tp2_additional = risk_dollars * (rr_ratio - 1.0) * 0.5
                    setup['profit_loss'] = tp1_profit + tp2_additional
                    setup['balance_after'] = balance_before + setup['profit_loss']
                    setup['movement_captured_dollars'] = abs(tp2 - entry)
                    message = "TP2_HIT"

                elif not is_long and current_price <= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    tp1_profit = risk_dollars * 1.0
                    tp2_additional = risk_dollars * (rr_ratio - 1.0) * 0.5
                    setup['profit_loss'] = tp1_profit + tp2_additional
                    setup['balance_after'] = balance_before + setup['profit_loss']
                    setup['movement_captured_dollars'] = abs(entry - tp2)
                    message = "TP2_HIT"

                elif is_long and current_price <= entry:
                    new_status = 'COMPLETED'
                    setup['result'] = 'BREAKEVEN'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    setup['movement_captured_dollars'] = abs(tp1 - entry)
                    message = "BREAKEVEN"

                elif not is_long and current_price >= entry:
                    new_status = 'COMPLETED'
                    setup['result'] = 'BREAKEVEN'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    setup['movement_captured_dollars'] = abs(entry - tp1)
                    message = "BREAKEVEN"
            
            if new_status != old_status:
                created_at = datetime.fromisoformat(setup['created_at'])
                now = datetime.now(TURKEY_TZ)
                duration = (now - created_at).total_seconds() / 60
                setup['duration_minutes'] = round(duration, 1)
                
                setup['status'] = new_status
                blob.upload_from_string(
                    json.dumps(setup, indent=2),
                    content_type='application/json'
                )
                logger.info(f"✅ Setup {setup_id} status updated: {old_status} → {new_status} (Duration: {duration:.1f}m)")
                return {
                    'status_changed': True,
                    'old_status': old_status,
                    'new_status': new_status,
                    'message': message,
                    'setup': setup
                }
            
            return {'status_changed': False, 'old_status': old_status, 'new_status': new_status}
            
        except Exception as e:
            logger.error(f"❌ Check setup error: {e}")
            return {'status_changed': False, 'old_status': None, 'new_status': None}
    
    def get_all_pending_setups(self):
        """Tüm PENDING ve TP1 durumundaki setup'ları getir"""
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            pending_setups = []
            timeframe_counts = {}
            skipped_count = 0
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    
                    if setup['status'] in ['PENDING', 'TP1']:
                        tf = setup.get('timeframe', 'N/A')
                        pending_setups.append({
                            'id': setup['setup_id'],
                            'setup_id': setup['setup_id'],
                            'pair': setup['pair'],
                            'setup_type': setup['setup_type'],
                            'timeframe': tf,
                            'current_price': setup['current_price'],
                            'entry_price': setup.get('entry_price', setup['current_price']),
                            'tp1_price': setup['tp1_price'],
                            'tp2_price': setup['tp2_price'],
                            'stop_price': setup['stop_price'],
                            'status': setup['status']
                        })
                        
                        if tf not in timeframe_counts:
                            timeframe_counts[tf] = 0
                        timeframe_counts[tf] += 1
                        
                except Exception:
                    skipped_count += 1
                    continue
            
            if skipped_count > 0:
                logger.warning(f"⚠️ Skipped {skipped_count} unreadable setup files")
            
            logger.info(f"📊 Pending setups: {len(pending_setups)} | TF breakdown: {timeframe_counts}")
            return {
                'setups': pending_setups,
                'timeframe_breakdown': timeframe_counts,
                'total': len(pending_setups)
            }
            
        except Exception as e:
            logger.error(f"❌ Get pending setups error: {e}")
            return {'setups': [], 'timeframe_breakdown': {}, 'total': 0}
    
    def get_aggregate_stats(self, real_balance=None):
        """
        /score komutu için aggregate istatistikler
        
        v2.1.1:
        - real_balance parametresi eklendi (OKX'ten)
        - Top 5 / Worst 5 coin
        - Top 5 / Worst 5 timeframe
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            total_setups = 0
            winning_trades = 0
            losing_trades = 0
            breakeven_trades = 0
            pending_setups = 0
            
            # v2.1.1: Gerçek balance kullan (fallback 500)
            starting_balance = real_balance if real_balance else 500.0
            current_balance = starting_balance
            
            setup_type_stats = {}
            total_duration = 0
            completed_trades = 0
            total_profit_loss = 0.0
            
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
                        timeframe_stats[tf] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'breakeven': 0}
                    timeframe_stats[tf]['total'] += 1
                    
                    coin = setup.get('pair', 'UNKNOWN').replace('USDT', '')
                    if coin not in coin_stats:
                        coin_stats[coin] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0}
                    coin_stats[coin]['total'] += 1
                    
                    if setup.get('duration_minutes'):
                        total_duration += setup['duration_minutes']
                        completed_trades += 1
                    
                    if setup['result'] in ['WIN', 'PARTIAL_WIN']:
                        winning_trades += 1
                        total_profit_loss += setup.get('profit_loss', 0)
                        timeframe_stats[tf]['wins'] += 1
                        coin_stats[coin]['wins'] += 1
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['wins'] += 1
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif setup['result'] == 'LOSS':
                        losing_trades += 1
                        total_profit_loss += setup['profit_loss']
                        timeframe_stats[tf]['losses'] += 1
                        coin_stats[coin]['losses'] += 1
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif setup['result'] == 'BREAKEVEN':
                        breakeven_trades += 1
                        timeframe_stats[tf]['breakeven'] += 1
                    
                    elif setup['status'] in ['PENDING', 'TP1']:
                        pending_setups += 1
                        timeframe_stats[tf]['pending'] += 1
                        coin_stats[coin]['pending'] += 1
                        
                except Exception:
                    continue
            
            # Win rate hesapla
            completed_count = winning_trades + losing_trades
            win_rate = (winning_trades / completed_count * 100) if completed_count > 0 else 0
            loss_rate = (losing_trades / completed_count * 100) if completed_count > 0 else 0
            
            # Profit hesapla
            current_balance = starting_balance + total_profit_loss
            profit_percent = (total_profit_loss / starting_balance * 100) if starting_balance > 0 else 0
            
            # Average duration
            avg_duration = (total_duration / completed_trades) if completed_trades > 0 else 0
            
            # Best setup type
            best_setup_type = "N/A"
            best_win_rate = 0
            for setup_type, stats in setup_type_stats.items():
                if stats['total'] >= 3:  # En az 3 trade olsun
                    type_win_rate = (stats['wins'] / stats['total'] * 100)
                    if type_win_rate > best_win_rate:
                        best_win_rate = type_win_rate
                        best_setup_type = f"{setup_type}: {type_win_rate:.0f}%"
            
            # v2.1.1: Coin breakdown with win rates
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
                    'win_rate': round(coin_win_rate, 1),
                    'loss_rate': round(coin_loss_rate, 1)
                }
            
            # v2.1.1: Top 5 coins (en yüksek win rate, en az 2 completed trade)
            sorted_coins = sorted(
                [(c, s) for c, s in coin_breakdown.items() if s['wins'] + s['losses'] >= 2],
                key=lambda x: x[1]['win_rate'],
                reverse=True
            )
            top_5_coins = sorted_coins[:5]
            worst_5_coins = sorted_coins[-5:][::-1] if len(sorted_coins) >= 5 else sorted_coins[::-1]
            
            # v2.1.1: Timeframe breakdown with win rates
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
                    'win_rate': round(tf_win_rate, 1),
                    'loss_rate': round(tf_loss_rate, 1)
                }
            
            # v2.1.1: Top 5 timeframes (en yüksek win rate, en az 2 completed trade)
            sorted_tfs = sorted(
                [(tf, s) for tf, s in timeframe_breakdown.items() if s['wins'] + s['losses'] >= 2],
                key=lambda x: x[1]['win_rate'],
                reverse=True
            )
            top_5_timeframes = sorted_tfs[:5]
            worst_5_timeframes = sorted_tfs[-5:][::-1] if len(sorted_tfs) >= 5 else sorted_tfs[::-1]
            
            result = {
                'total_setups': total_setups,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': breakeven_trades,
                'pending_setups': pending_setups,
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
                # v2.1.1: Top/Worst 5
                'top_5_coins': top_5_coins,
                'worst_5_coins': worst_5_coins,
                'top_5_timeframes': top_5_timeframes,
                'worst_5_timeframes': worst_5_timeframes,
            }
            
            logger.info(f"📊 Aggregate stats: {winning_trades}W/{losing_trades}L/{breakeven_trades}BE/{pending_setups}P ({win_rate:.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get aggregate stats error: {e}")
            return {
                'total_setups': 0, 'winning_trades': 0, 'losing_trades': 0,
                'breakeven_trades': 0, 'pending_setups': 0, 'win_rate': 0, 'loss_rate': 0,
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
