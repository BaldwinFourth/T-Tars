from google.cloud import storage
import json
import logging
from datetime import datetime, timezone, timedelta
import uuid

logger = logging.getLogger(__name__)

# Turkey timezone (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))

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
                'risk_percent': 2.0  # v1.4.3: Risk percentage
            }
        
        Returns:
            str: Setup UUID
        """
        try:
            # Generate UUID
            setup_id = str(uuid.uuid4())[:8]
            
            # Calculate risk amount in dollars (v1.4.3)
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
                'risk_percent': risk_percent,  # v1.4.3
                'risk_dollars': risk_dollars,  # v1.4.3
                'status': 'PENDING',  # PENDING → TP1 → TP2 / STOP
                'result': None,  # WIN / LOSS / None
                'profit_loss': 0.0,
                'balance_after': balance,
                'movement_captured_dollars': 0.0,  # v1.4.3: Price movement in $
                'created_at': datetime.now(TURKEY_TZ).isoformat(),  # v1.4.3
                'tp1_hit_at': None,  # v1.4.3
                'tp2_hit_at': None,  # v1.4.3
                'stop_hit_at': None,  # v1.4.3
                'duration_minutes': None  # v1.4.3
            }
            
            # Save to Cloud Storage: setups/{setup_id}.json
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            blob.upload_from_string(
                json.dumps(setup_record, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Setup logged: {setup_id} ({setup_data['pair']})")
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
            
            # LONG veya SHORT?
            is_long = 'LONG' in setup_type
            
            # Get values
            entry = setup['current_price']
            stop = setup['stop_price']
            tp1 = setup['tp1_price']
            tp2 = setup['tp2_price']
            balance_before = setup['balance_before']
            risk_dollars = setup.get('risk_dollars', balance_before * 0.02)  # Default 2% if missing
            rr_ratio = setup.get('rr_ratio', 2.0)
            
            # Status transitions
            if setup['status'] == 'PENDING':
                # Check TP1
                if is_long and current_price >= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()  # v1.4.3
                    # TP1 = Breakeven, no profit/loss (v1.4.3 FIX)
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    setup['movement_captured_dollars'] = abs(tp1 - entry)  # v1.4.3
                    message = f"✅ TP1 HIT - BREAKEVEN!\n\n📊 {pair} (Setup #{setup_id})\nEntry: ${entry:,.2f}\nTP1: ${tp1:,.2f} ✅\n\n📄 Action: Moved to Breakeven\n💰 Balance: ${balance_before:,.2f} (unchanged)\nStatus: PENDING → TP1"
                elif not is_long and current_price <= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()  # v1.4.3
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    setup['movement_captured_dollars'] = abs(entry - tp1)  # v1.4.3
                    message = f"✅ TP1 HIT - BREAKEVEN!\n\n📊 {pair} (Setup #{setup_id})\nEntry: ${entry:,.2f}\nTP1: ${tp1:,.2f} ✅\n\n📄 Action: Moved to Breakeven\n💰 Balance: ${balance_before:,.2f} (unchanged)\nStatus: PENDING → TP1"
                
                # Check Stop
                elif is_long and current_price <= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()  # v1.4.3
                    # Loss = risk_dollars (v1.4.3 FIX)
                    loss = risk_dollars
                    setup['profit_loss'] = -loss
                    setup['balance_after'] = balance_before - loss
                    setup['movement_captured_dollars'] = abs(stop - entry)  # v1.4.3
                    loss_percent = (loss / balance_before * 100)
                    message = f"❌ STOP HIT - LOSS!\n\n📊 {pair} (Setup #{setup_id})\nEntry: ${entry:,.2f}\nStop: ${stop:,.2f} ❌\nLoss: -${loss:.2f} (-{loss_percent:.1f}%)\n📊 Movement: ${abs(stop - entry):.2f}\n\n💰 Balance: ${balance_before:,.2f} → ${setup['balance_after']:,.2f}\nStatus: COMPLETED ❌"
                elif not is_long and current_price >= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()  # v1.4.3
                    loss = risk_dollars
                    setup['profit_loss'] = -loss
                    setup['balance_after'] = balance_before - loss
                    setup['movement_captured_dollars'] = abs(stop - entry)  # v1.4.3
                    loss_percent = (loss / balance_before * 100)
                    message = f"❌ STOP HIT - LOSS!\n\n📊 {pair} (Setup #{setup_id})\nEntry: ${entry:,.2f}\nStop: ${stop:,.2f} ❌\nLoss: -${loss:.2f} (-{loss_percent:.1f}%)\n📊 Movement: ${abs(stop - entry):.2f}\n\n💰 Balance: ${balance_before:,.2f} → ${setup['balance_after']:,.2f}\nStatus: COMPLETED ❌"
            
            elif setup['status'] == 'TP1':
                # Check TP2
                if is_long and current_price >= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()  # v1.4.3
                    # Profit = risk_dollars * R:R (v1.4.3 FIX)
                    profit = risk_dollars * rr_ratio
                    setup['profit_loss'] = profit
                    setup['balance_after'] = balance_before + profit
                    setup['movement_captured_dollars'] = abs(tp2 - entry)  # v1.4.3
                    profit_percent = (profit / balance_before * 100)
                    message = f"🎉 TP2 HIT - WIN!\n\n📊 {pair} (Setup #{setup_id})\nEntry: ${entry:,.2f}\nTP2: ${tp2:,.2f} ✅\nProfit: +${profit:.2f} (+{profit_percent:.1f}%)\n📊 Movement: ${abs(tp2 - entry):.2f} captured\n\n💰 Balance: ${balance_before:,.2f} → ${setup['balance_after']:,.2f}\nStatus: COMPLETED ✅"
                elif not is_long and current_price <= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()  # v1.4.3
                    profit = risk_dollars * rr_ratio
                    setup['profit_loss'] = profit
                    setup['balance_after'] = balance_before + profit
                    setup['movement_captured_dollars'] = abs(entry - tp2)  # v1.4.3
                    profit_percent = (profit / balance_before * 100)
                    message = f"🎉 TP2 HIT - WIN!\n\n📊 {pair} (Setup #{setup_id})\nEntry: ${entry:,.2f}\nTP2: ${tp2:,.2f} ✅\nProfit: +${profit:.2f} (+{profit_percent:.1f}%)\n📊 Movement: ${abs(entry - tp2):.2f} captured\n\n💰 Balance: ${balance_before:,.2f} → ${setup['balance_after']:,.2f}\nStatus: COMPLETED ✅"
            
            # Calculate duration if status changed (v1.4.3)
            if new_status != old_status:
                created_at = datetime.fromisoformat(setup['created_at'])
                now = datetime.now(TURKEY_TZ)
                duration = (now - created_at).total_seconds() / 60  # minutes
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
        """
        Tüm PENDING ve TP1 durumundaki setup'ları getir
        
        Returns:
            list: [{id, setup_id, pair, setup_type, current_price, tp1_price, tp2_price, stop_price, status}]
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            pending_setups = []
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    setup = json.loads(blob.download_as_string())
                    if setup['status'] in ['PENDING', 'TP1']:
                        pending_setups.append({
                            'id': setup['setup_id'],              # ← v1.4.2 FIX: main.py bunu bekliyor
                            'setup_id': setup['setup_id'],
                            'pair': setup['pair'],
                            'setup_type': setup['setup_type'],    # ← v1.4.2 FIX: main.py bunu bekliyor
                            'current_price': setup['current_price'],
                            'tp1_price': setup['tp1_price'],
                            'tp2_price': setup['tp2_price'],
                            'stop_price': setup['stop_price'],
                            'status': setup['status']
                        })
            
            logger.info(f"📊 Pending setups: {len(pending_setups)}")
            return pending_setups
            
        except Exception as e:
            logger.error(f"❌ Get pending setups error: {e}")
            return []
    
    def get_aggregate_stats(self):
        """
        /score komutu için aggregate istatistikler
        
        Returns:
            dict: {
                'total_setups': int,
                'winning_trades': int,
                'losing_trades': int,
                'win_rate': float,
                'starting_balance': float,
                'current_balance': float,
                'profit': float,
                'profit_percent': float,
                'best_setup_type': str,
                'avg_duration_minutes': float  # v1.4.3
            }
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            total_setups = 0
            winning_trades = 0
            losing_trades = 0
            starting_balance = 1000.00
            current_balance = 1000.00
            setup_type_stats = {}
            total_duration = 0
            completed_trades = 0
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    setup = json.loads(blob.download_as_string())
                    total_setups += 1
                    
                    # Duration tracking (v1.4.3)
                    if setup.get('duration_minutes'):
                        total_duration += setup['duration_minutes']
                        completed_trades += 1
                    
                    # Win/Loss count (v1.4.3: TP1 is NOT a win)
                    if setup['result'] == 'WIN':
                        winning_trades += 1
                        current_balance += setup['profit_loss']
                        
                        # Setup type stats
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['wins'] += 1
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif setup['result'] == 'LOSS':
                        losing_trades += 1
                        current_balance += setup['profit_loss']  # negative
                        
                        # Setup type stats
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['total'] += 1
            
            # Calculate win rate (v1.4.3: Only count WIN/LOSS, not TP1)
            completed_count = winning_trades + losing_trades
            win_rate = (winning_trades / completed_count * 100) if completed_count > 0 else 0
            
            # Calculate profit
            profit = current_balance - starting_balance
            profit_percent = (profit / starting_balance * 100)
            
            # Average duration (v1.4.3)
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
            
            result = {
                'total_setups': total_setups,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'starting_balance': starting_balance,
                'current_balance': current_balance,
                'profit': profit,
                'profit_percent': profit_percent,
                'best_setup_type': best_setup_type,
                'avg_duration_minutes': round(avg_duration, 1)  # v1.4.3
            }
            
            logger.info(f"📊 Aggregate stats: {winning_trades}W/{losing_trades}L ({win_rate:.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Get aggregate stats error: {e}")
            return {
                'total_setups': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'starting_balance': 1000.00,
                'current_balance': 1000.00,
                'profit': 0,
                'profit_percent': 0,
                'best_setup_type': 'N/A',
                'avg_duration_minutes': 0
            }
    
    def reset_all_tracking(self):
        """
        Tüm tracking verilerini sıfırla (v1.4.2)
        
        Returns:
            dict: {'deleted_count': int, 'status': str}
        """
        try:
            blobs = list(self.bucket.list_blobs(prefix='setups/'))
            deleted_count = 0
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    blob.delete()
                    deleted_count += 1
            
            logger.info(f"🗑️ Reset complete: {deleted_count} setups deleted")
            return {
                'deleted_count': deleted_count,
                'status': 'success',
                'message': f'✅ {deleted_count} setup silindi. Score sıfırlandı.'
            }
            
        except Exception as e:
            logger.error(f"❌ Reset tracking error: {e}")
            return {
                'deleted_count': 0,
                'status': 'error',
                'message': f'❌ Reset failed: {str(e)}'
            }
