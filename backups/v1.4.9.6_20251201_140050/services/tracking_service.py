# -*- coding: utf-8 -*-
"""
T-TARS Tracking Service v1.4.9.6
================================
Setup Tracking & Performance Analytics Service

v1.4.9.6:
- Timeframe breakdown (aktif + total)
- Detaylı istatistikler (loss_rate, pending_rate)
- get_all_pending_setups dict döndürüyor

v1.4.9.5:
- timeframe kaydediliyor
- format_price() ile düşük fiyatlı coinler
- Mesaj formatları düzeltildi
"""

from google.cloud import storage
import json
import logging
from datetime import datetime, timezone, timedelta
import uuid

logger = logging.getLogger(__name__)

# Turkey timezone (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))


def format_price(price):
    """
    Fiyatı dinamik formatta string'e çevir.
    SHIB/DOGE gibi düşük fiyatlı coinler için 8 ondalık,
    BTC gibi yüksek fiyatlılar için 2 ondalık kullanır.
    """
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
    
    def log_setup(self, setup_data):
        """
        Setup detected olduğunda kaydet
        
        Args:
            setup_data: {
                'pair': 'BTCUSDT',
                'timestamp': '2025-11-20 14:30:00',
                'setup_type': 'OB + Volume Spike (LONG)',
                'confidence': 'HIGH',
                'entry_zone': '$95,234 - $95,456',
                'stop_loss': '$94,500',
                'tp1': '$96,000',
                'tp2': '$96,500',
                'current_price': 95234.50,
                'stop_price': 94500.00,
                'tp1_price': 96000.00,
                'tp2_price': 96500.00,
                'volume_spike_ratio': 2.5,
                'ob_strength': 'high',
                'rr_ratio': 2.3,
                'balance_before': 1000.00,
                'risk_percent': 2.0,
                'timeframe': '5m'  # v1.4.9.5: timeframe eklendi
            }
        
        Returns:
            str: Setup UUID
        """
        try:
            # Generate UUID
            setup_id = str(uuid.uuid4())[:8]
            
            # Calculate risk amount in dollars
            balance = setup_data.get('balance_before', 1000.00)
            risk_percent = setup_data.get('risk_percent', 2.0)
            risk_dollars = balance * (risk_percent / 100)
            
            # Prepare setup record
            setup_record = {
                'setup_id': setup_id,
                'pair': setup_data['pair'],
                'timestamp': setup_data['timestamp'],
                'setup_type': setup_data['setup_type'],
                'confidence': setup_data['confidence'],
                'timeframe': setup_data.get('timeframe', 'N/A'),  # v1.4.9.5
                'entry_zone': setup_data['entry_zone'],
                'stop_loss': setup_data['stop_loss'],
                'tp1': setup_data['tp1'],
                'tp2': setup_data['tp2'],
                'current_price': setup_data['current_price'],
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
            
            # Save to Cloud Storage
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            blob.upload_from_string(
                json.dumps(setup_record, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Setup logged: {setup_id} ({setup_data['pair']}) TF:{setup_record['timeframe']}")
            return setup_id
            
        except Exception as e:
            logger.error(f"❌ Log setup error: {e}")
            raise
    
    def check_setup_status(self, setup_id, current_price):
        """
        Bir setup'ın durumunu check et (TP/Stop hit kontrolü)
        
        Returns:
            dict: {
                'status_changed': bool,
                'old_status': str,
                'new_status': str,
                'message': str
            }
        """
        try:
            # Setup'ı oku
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            setup = json.loads(blob.download_as_string())
            
            old_status = setup['status']
            new_status = old_status
            message = ""
            
            # COMPLETED olan setup'ları skip et
            if setup['status'] in ['COMPLETED', 'STOPPED']:
                return {'status_changed': False, 'old_status': old_status, 'new_status': new_status}
            
            pair = setup['pair']
            setup_type = setup['setup_type']
            timeframe = setup.get('timeframe', 'N/A')  # v1.4.9.5
            
            # LONG veya SHORT?
            is_long = 'LONG' in setup_type
            
            # Get values
            entry = setup['current_price']
            stop = setup['stop_price']
            tp1 = setup['tp1_price']
            tp2 = setup['tp2_price']
            balance_before = setup['balance_before']
            risk_dollars = setup.get('risk_dollars', balance_before * 0.02)
            rr_ratio = setup.get('rr_ratio', 2.0)
            
            # v1.4.9.5: Format prices for display
            entry_fmt = format_price(entry)
            stop_fmt = format_price(stop)
            tp1_fmt = format_price(tp1)
            tp2_fmt = format_price(tp2)
            current_fmt = format_price(current_price)
            
            # Status transitions
            if setup['status'] == 'PENDING':
                # Check TP1
                if is_long and current_price >= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    movement = abs(tp1 - entry)
                    setup['movement_captured_dollars'] = movement
                    message = f"""🎯 SETUP #{setup_id.upper()} → TP1 HIT! 💰💰💰

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
✅ Entry: {entry_fmt} → TP1: {tp1_fmt}
💰 Profit: +0.00% ($0.00)
📊 Movement: {format_price(movement)}
⏱️ Duration: {{duration}} minutes
📊 Status: Breakeven, TP2 bekliyor"""

                elif not is_long and current_price <= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    movement = abs(entry - tp1)
                    setup['movement_captured_dollars'] = movement
                    message = f"""🎯 SETUP #{setup_id.upper()} → TP1 HIT! 💰💰💰

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
✅ Entry: {entry_fmt} → TP1: {tp1_fmt}
💰 Profit: +0.00% ($0.00)
📊 Movement: {format_price(movement)}
⏱️ Duration: {{duration}} minutes
📊 Status: Breakeven, TP2 bekliyor"""
                
                # Check Stop
                elif is_long and current_price <= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    loss = risk_dollars
                    setup['profit_loss'] = -loss
                    setup['balance_after'] = balance_before - loss
                    movement = abs(entry - stop)
                    setup['movement_captured_dollars'] = movement
                    loss_percent = (loss / balance_before * 100)
                    message = f"""⛔ SETUP #{setup_id.upper()} → STOP HIT ❌

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
❌ Entry: {entry_fmt} → STOPPED: {stop_fmt}
💰 Profit: -{loss_percent:.2f}% (${-loss:.2f})
📊 Movement: {format_price(movement)}
⏱️ Duration: {{duration}} minutes
❌ Setup kapatıldı"""

                elif not is_long and current_price >= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    loss = risk_dollars
                    setup['profit_loss'] = -loss
                    setup['balance_after'] = balance_before - loss
                    movement = abs(stop - entry)
                    setup['movement_captured_dollars'] = movement
                    loss_percent = (loss / balance_before * 100)
                    message = f"""⛔ SETUP #{setup_id.upper()} → STOP HIT ❌

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
❌ Entry: {entry_fmt} → STOPPED: {stop_fmt}
💰 Profit: -{loss_percent:.2f}% (${-loss:.2f})
📊 Movement: {format_price(movement)}
⏱️ Duration: {{duration}} minutes
❌ Setup kapatıldı"""
            
            elif setup['status'] == 'TP1':
                # Check TP2
                if is_long and current_price >= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    profit = risk_dollars * rr_ratio
                    setup['profit_loss'] = profit
                    setup['balance_after'] = balance_before + profit
                    movement = abs(tp2 - entry)
                    setup['movement_captured_dollars'] = movement
                    profit_percent = (profit / balance_before * 100)
                    message = f"""🎉 SETUP #{setup_id.upper()} → TP2 HIT! 🚀🚀🚀

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
✅ Entry: {entry_fmt} → TP2: {tp2_fmt}
💰 Profit: +{profit_percent:.2f}% (+${profit:.2f})
📊 Movement: {format_price(movement)}
⏱️ Duration: {{duration}} minutes
✅ Setup COMPLETED - WIN!"""

                elif not is_long and current_price <= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    profit = risk_dollars * rr_ratio
                    setup['profit_loss'] = profit
                    setup['balance_after'] = balance_before + profit
                    movement = abs(entry - tp2)
                    setup['movement_captured_dollars'] = movement
                    profit_percent = (profit / balance_before * 100)
                    message = f"""🎉 SETUP #{setup_id.upper()} → TP2 HIT! 🚀🚀🚀

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
✅ Entry: {entry_fmt} → TP2: {tp2_fmt}
💰 Profit: +{profit_percent:.2f}% (+${profit:.2f})
📊 Movement: {format_price(movement)}
⏱️ Duration: {{duration}} minutes
✅ Setup COMPLETED - WIN!"""

                # Check Stop (after TP1 = breakeven)
                elif is_long and current_price <= entry:
                    new_status = 'COMPLETED'
                    setup['result'] = 'BREAKEVEN'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    movement = abs(tp1 - entry)
                    setup['movement_captured_dollars'] = movement
                    message = f"""📊 SETUP #{setup_id.upper()} → BREAKEVEN

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
📊 Entry: {entry_fmt} → BE: {entry_fmt}
💰 Profit: 0.00% ($0.00)
📊 Movement: {format_price(movement)} (TP1'e kadar)
⏱️ Duration: {{duration}} minutes
📊 Setup COMPLETED - Breakeven"""

                elif not is_long and current_price >= entry:
                    new_status = 'COMPLETED'
                    setup['result'] = 'BREAKEVEN'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    movement = abs(entry - tp1)
                    setup['movement_captured_dollars'] = movement
                    message = f"""📊 SETUP #{setup_id.upper()} → BREAKEVEN

📊 Parite: {pair}
🎯 Setup Type: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
📊 Entry: {entry_fmt} → BE: {entry_fmt}
💰 Profit: 0.00% ($0.00)
📊 Movement: {format_price(movement)} (TP1'e kadar)
⏱️ Duration: {{duration}} minutes
📊 Setup COMPLETED - Breakeven"""
            
            # Calculate duration and update if status changed
            if new_status != old_status:
                created_at = datetime.fromisoformat(setup['created_at'])
                now = datetime.now(TURKEY_TZ)
                duration = (now - created_at).total_seconds() / 60
                setup['duration_minutes'] = round(duration, 1)
                
                # Replace duration placeholder in message
                message = message.replace('{duration}', f"{duration:.1f}")
                
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
        """
        Tüm PENDING ve TP1 durumundaki setup'ları getir
        v1.4.9.6: timeframe_breakdown eklendi
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            pending_setups = []
            timeframe_counts = {}  # v1.4.9.6
            
            for blob in blobs:
                if blob.name.endswith('.json'):
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
                            'tp1_price': setup['tp1_price'],
                            'tp2_price': setup['tp2_price'],
                            'stop_price': setup['stop_price'],
                            'status': setup['status']
                        })
                        
                        # v1.4.9.6: Count by timeframe
                        if tf not in timeframe_counts:
                            timeframe_counts[tf] = 0
                        timeframe_counts[tf] += 1
            
            logger.info(f"📊 Pending setups: {len(pending_setups)} | TF breakdown: {timeframe_counts}")
            return {
                'setups': pending_setups,
                'timeframe_breakdown': timeframe_counts,
                'total': len(pending_setups)
            }
            
        except Exception as e:
            logger.error(f"❌ Get pending setups error: {e}")
            return {'setups': [], 'timeframe_breakdown': {}, 'total': 0}
    
    def get_aggregate_stats(self):
        """
        /score komutu için aggregate istatistikler
        v1.4.9.6: Timeframe breakdown eklendi
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            total_setups = 0
            winning_trades = 0
            losing_trades = 0
            breakeven_trades = 0
            pending_setups = 0  # v1.4.9.6
            starting_balance = 1000.00
            current_balance = 1000.00
            setup_type_stats = {}
            total_duration = 0
            completed_trades = 0
            
            # v1.4.9.6: Timeframe stats
            timeframe_stats = {}  # {'5m': {'total': 10, 'wins': 5, 'losses': 3, 'pending': 2}}
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    setup = json.loads(blob.download_as_string())
                    total_setups += 1
                    
                    # v1.4.9.6: Timeframe tracking
                    tf = setup.get('timeframe', 'N/A')
                    if tf not in timeframe_stats:
                        timeframe_stats[tf] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'breakeven': 0}
                    timeframe_stats[tf]['total'] += 1
                    
                    # Duration tracking
                    if setup.get('duration_minutes'):
                        total_duration += setup['duration_minutes']
                        completed_trades += 1
                    
                    # Win/Loss/Breakeven/Pending count
                    if setup['result'] == 'WIN':
                        winning_trades += 1
                        current_balance += setup['profit_loss']
                        timeframe_stats[tf]['wins'] += 1
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['wins'] += 1
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif setup['result'] == 'LOSS':
                        losing_trades += 1
                        current_balance += setup['profit_loss']
                        timeframe_stats[tf]['losses'] += 1
                        
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
            
            # Calculate win rate (only WIN/LOSS, not breakeven/pending)
            completed_count = winning_trades + losing_trades
            win_rate = (winning_trades / completed_count * 100) if completed_count > 0 else 0
            loss_rate = (losing_trades / completed_count * 100) if completed_count > 0 else 0
            pending_rate = (pending_setups / total_setups * 100) if total_setups > 0 else 0
            
            # Calculate profit
            profit = current_balance - starting_balance
            profit_percent = (profit / starting_balance * 100)
            
            # Average duration
            avg_duration = (total_duration / completed_trades) if completed_trades > 0 else 0
            
            # Best setup type
            best_setup_type = "N/A"
            best_win_rate = 0
            for setup_type, stats in setup_type_stats.items():
                if stats['total'] > 0:
                    type_win_rate = (stats['wins'] / stats['total'] * 100)
                    if type_win_rate > best_win_rate:
                        best_win_rate = type_win_rate
                        best_setup_type = f"{setup_type}: {type_win_rate:.0f}% win rate"
            
            # v1.4.9.6: Calculate timeframe win rates
            timeframe_breakdown = {}
            for tf, stats in timeframe_stats.items():
                tf_completed = stats['wins'] + stats['losses']
                tf_win_rate = (stats['wins'] / tf_completed * 100) if tf_completed > 0 else 0
                timeframe_breakdown[tf] = {
                    'total': stats['total'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'pending': stats['pending'],
                    'breakeven': stats['breakeven'],
                    'win_rate': round(tf_win_rate, 1)
                }
            
            result = {
                'total_setups': total_setups,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': breakeven_trades,
                'pending_setups': pending_setups,  # v1.4.9.6
                'win_rate': win_rate,
                'loss_rate': loss_rate,  # v1.4.9.6
                'pending_rate': pending_rate,  # v1.4.9.6
                'starting_balance': starting_balance,
                'current_balance': current_balance,
                'profit': profit,
                'profit_percent': profit_percent,
                'best_setup_type': best_setup_type,
                'avg_duration_minutes': round(avg_duration, 1),
                'timeframe_breakdown': timeframe_breakdown  # v1.4.9.6
            }
            
            logger.info(f"📊 Aggregate stats: {winning_trades}W/{losing_trades}L/{breakeven_trades}BE/{pending_setups}P ({win_rate:.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get aggregate stats error: {e}")
            return {
                'total_setups': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'breakeven_trades': 0,
                'pending_setups': 0,
                'win_rate': 0,
                'loss_rate': 0,
                'pending_rate': 0,
                'starting_balance': 1000.00,
                'current_balance': 1000.00,
                'profit': 0,
                'profit_percent': 0,
                'best_setup_type': 'N/A',
                'avg_duration_minutes': 0,
                'timeframe_breakdown': {}
            }
    
    def reset_all_tracking(self):
        """
        Tüm tracking verilerini sıfırla
        """
        try:
            blobs = list(self.bucket.list_blobs(prefix='setups/'))
            deleted_count = 0
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    blob.delete()
                    deleted_count += 1
            
            logger.info(f"🗑️ Reset complete: {deleted_count} setups deleted")
            return True
            
        except Exception as e:
            logger.error(f"❌ Reset tracking error: {e}")
            return False
