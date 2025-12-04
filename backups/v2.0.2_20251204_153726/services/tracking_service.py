# -*- coding: utf-8 -*-
"""
T-TARS Tracking Service v2.0.0
==============================
Setup Tracking & Performance Analytics Service

v2.0.0:
- coin_breakdown eklendi (/score için top 3 coin)
- OKX entegrasyonuna hazırlık

v1.4.10.3:
- FIX: TP1 (PARTIAL_WIN) artık winning olarak sayılıyor
- Stats'ta TP1 = Win, balance'a ekleniyor

v1.4.10.2:
- DUPLICATE DETECTION: Aynı pair+timeframe+direction için tekrar setup oluşturmaz
- 404 error handling güçlendirildi
- get_all_pending_setups: Silinmiş dosyaları skip eder

v1.4.9.9:
- entry_price ayrı kaydediliyor (current_price != entry_price)
- check_setup_status: entry_price kullanıyor (LONG/SHORT fix)
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
    
    def check_duplicate_setup(self, pair, timeframe, direction):
        """
        v1.4.10.2: Duplicate detection
        Aynı pair + timeframe + direction için PENDING/TP1 setup var mı kontrol et
        
        Args:
            pair: 'BTCUSDT'
            timeframe: '5m', '15m', etc.
            direction: 'LONG' veya 'SHORT'
        
        Returns:
            str or None: Mevcut setup_id varsa döndür, yoksa None
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    
                    # Sadece aktif setup'lara bak
                    if setup['status'] not in ['PENDING', 'TP1']:
                        continue
                    
                    # Pair eşleşmesi
                    if setup['pair'] != pair:
                        continue
                    
                    # Timeframe eşleşmesi
                    if setup.get('timeframe', 'N/A') != timeframe:
                        continue
                    
                    # Direction eşleşmesi (LONG/SHORT)
                    setup_direction = 'LONG' if 'LONG' in setup['setup_type'] else 'SHORT'
                    if setup_direction != direction:
                        continue
                    
                    # Duplicate bulundu!
                    logger.info(f"⚠️ Duplicate detected: {pair} {timeframe} {direction} → existing #{setup['setup_id']}")
                    return setup['setup_id']
                    
                except Exception as e:
                    # Dosya okunamadı, skip et
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Duplicate check error: {e}")
            return None
    
    def log_setup(self, setup_data):
        """
        Setup detected olduğunda kaydet
        
        v1.4.10.2: Duplicate detection - aynı pair+tf+direction için PENDING varsa skip
        v1.4.9.9: entry_price ayrı kaydediliyor
        
        Returns:
            str: Setup UUID (yeni veya mevcut)
        """
        try:
            pair = setup_data['pair']
            timeframe = setup_data.get('timeframe', 'N/A')
            setup_type = setup_data['setup_type']
            direction = 'LONG' if 'LONG' in setup_type else 'SHORT'
            
            # v1.4.10.2: DUPLICATE CHECK
            existing_id = self.check_duplicate_setup(pair, timeframe, direction)
            if existing_id:
                logger.info(f"⏭️ Skipping duplicate: {pair} {timeframe} {direction} (existing: #{existing_id})")
                return None  # None döndür, mesaj gönderilmesin
            
            # Generate UUID
            setup_id = str(uuid.uuid4())[:8]
            
            # Calculate risk amount in dollars
            balance = setup_data.get('balance_before', 1000.00)
            risk_percent = setup_data.get('risk_percent', 2.0)
            risk_dollars = balance * (risk_percent / 100)
            
            # v1.4.9.9: entry_price yoksa current_price kullan (backward compat)
            entry_price = setup_data.get('entry_price', setup_data.get('current_price', 0))
            
            # Prepare setup record
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
            
            # Save to Cloud Storage
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
        """
        Bir setup'ın durumunu check et (TP/Stop hit kontrolü)
        
        v1.4.10.2: 404 error handling güçlendirildi
        v1.4.9.9: entry_price kullanılıyor
        
        Returns:
            dict: status_changed, old_status, new_status, message
        """
        try:
            # Setup'ı oku
            blob = self.bucket.blob(f'setups/{setup_id}.json')
            
            # v1.4.10.2: Dosya var mı kontrol et
            if not blob.exists():
                logger.warning(f"⚠️ Setup not found: {setup_id}")
                return {'status_changed': False, 'old_status': None, 'new_status': None, 'not_found': True}
            
            setup = json.loads(blob.download_as_string())
            
            old_status = setup['status']
            new_status = old_status
            message = ""
            
            # COMPLETED veya STOPPED olan setup'ları skip et
            if setup['status'] in ['COMPLETED', 'STOPPED']:
                return {'status_changed': False, 'old_status': old_status, 'new_status': new_status}
            
            pair = setup['pair']
            setup_type = setup['setup_type']
            timeframe = setup.get('timeframe', 'N/A')
            
            # LONG veya SHORT?
            is_long = 'LONG' in setup_type
            
            # v1.4.9.9: entry_price kullan
            entry = setup.get('entry_price', setup['current_price'])
            stop = setup['stop_price']
            tp1 = setup['tp1_price']
            tp2 = setup['tp2_price']
            balance_before = setup['balance_before']
            risk_dollars = setup.get('risk_dollars', balance_before * 0.02)
            rr_ratio = setup.get('rr_ratio', 2.0)
            
            # Format prices for display
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
                    # v1.4.10.2: TP1'de partial profit (%50 pozisyon kapatıldı)
                    # 1R kar (risk_dollars kadar) - yarı pozisyondan
                    partial_profit = risk_dollars * 1.0  # 1R kar
                    setup['profit_loss'] = partial_profit
                    setup['balance_after'] = balance_before + partial_profit
                    setup['result'] = 'PARTIAL_WIN'  # v1.4.10.2: Partial win
                    movement = abs(tp1 - entry)
                    setup['movement_captured_dollars'] = movement
                    message = f"TP1_HIT"

                elif not is_long and current_price <= tp1:
                    new_status = 'TP1'
                    setup['tp1_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    # v1.4.10.2: TP1'de partial profit
                    partial_profit = risk_dollars * 1.0
                    setup['profit_loss'] = partial_profit
                    setup['balance_after'] = balance_before + partial_profit
                    setup['result'] = 'PARTIAL_WIN'
                    movement = abs(entry - tp1)
                    setup['movement_captured_dollars'] = movement
                    message = f"TP1_HIT"
                
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
                    message = f"STOP_HIT"

                elif not is_long and current_price >= stop:
                    new_status = 'STOPPED'
                    setup['result'] = 'LOSS'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    loss = risk_dollars
                    setup['profit_loss'] = -loss
                    setup['balance_after'] = balance_before - loss
                    movement = abs(stop - entry)
                    setup['movement_captured_dollars'] = movement
                    message = f"STOP_HIT"
            
            elif setup['status'] == 'TP1':
                # Check TP2
                if is_long and current_price >= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    # v1.4.10.2: Full profit = TP1 profit + TP2 profit
                    # TP1'de 1R kazandık, TP2'de kalan %50'den (rr_ratio - 1)R daha
                    tp1_profit = risk_dollars * 1.0
                    tp2_additional = risk_dollars * (rr_ratio - 1.0) * 0.5  # Kalan yarı pozisyon
                    profit = tp1_profit + tp2_additional
                    setup['profit_loss'] = profit
                    setup['balance_after'] = balance_before + profit
                    movement = abs(tp2 - entry)
                    setup['movement_captured_dollars'] = movement
                    message = f"TP2_HIT"

                elif not is_long and current_price <= tp2:
                    new_status = 'COMPLETED'
                    setup['result'] = 'WIN'
                    setup['tp2_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    # v1.4.10.2: Full profit
                    tp1_profit = risk_dollars * 1.0
                    tp2_additional = risk_dollars * (rr_ratio - 1.0) * 0.5
                    profit = tp1_profit + tp2_additional
                    setup['profit_loss'] = profit
                    setup['balance_after'] = balance_before + profit
                    movement = abs(entry - tp2)
                    setup['movement_captured_dollars'] = movement
                    message = f"TP2_HIT"

                # Check Stop after TP1 = breakeven
                elif is_long and current_price <= entry:
                    new_status = 'COMPLETED'
                    setup['result'] = 'BREAKEVEN'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    movement = abs(tp1 - entry)
                    setup['movement_captured_dollars'] = movement
                    message = f"BREAKEVEN"

                elif not is_long and current_price >= entry:
                    new_status = 'COMPLETED'
                    setup['result'] = 'BREAKEVEN'
                    setup['stop_hit_at'] = datetime.now(TURKEY_TZ).isoformat()
                    setup['profit_loss'] = 0.0
                    setup['balance_after'] = balance_before
                    movement = abs(entry - tp1)
                    setup['movement_captured_dollars'] = movement
                    message = f"BREAKEVEN"
            
            # Calculate duration and update if status changed
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
        """
        Tüm PENDING ve TP1 durumundaki setup'ları getir
        v1.4.10.2: 404 error handling - silinmiş dosyaları skip et
        """
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
                        
                except Exception as e:
                    # v1.4.10.2: Dosya okunamadı, skip et (404 veya corrupt)
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
    
    def get_aggregate_stats(self):
        """
        /score komutu için aggregate istatistikler
        v1.4.10.2: 404 error handling
        """
        try:
            blobs = self.bucket.list_blobs(prefix='setups/')
            
            total_setups = 0
            winning_trades = 0
            losing_trades = 0
            breakeven_trades = 0
            pending_setups = 0
            starting_balance = 1000.00
            current_balance = 1000.00
            setup_type_stats = {}
            total_duration = 0
            completed_trades = 0
            skipped_count = 0
            
            # Timeframe stats
            timeframe_stats = {}
            
            # v2.0.0: Coin stats
            coin_stats = {}
            
            for blob in blobs:
                if not blob.name.endswith('.json'):
                    continue
                
                try:
                    setup = json.loads(blob.download_as_string())
                    total_setups += 1
                    
                    # Timeframe tracking
                    tf = setup.get('timeframe', 'N/A')
                    if tf not in timeframe_stats:
                        timeframe_stats[tf] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'breakeven': 0}
                    timeframe_stats[tf]['total'] += 1
                    
                    # v2.0.0: Coin tracking
                    coin = setup.get('pair', 'UNKNOWN').replace('USDT', '')
                    if coin not in coin_stats:
                        coin_stats[coin] = {'total': 0, 'wins': 0, 'losses': 0, 'pending': 0}
                    
                    # Duration tracking
                    if setup.get('duration_minutes'):
                        total_duration += setup['duration_minutes']
                        completed_trades += 1
                    
                    # Win/Loss/Breakeven/Pending count
                    # v1.4.10.3: PARTIAL_WIN (TP1) da Win olarak sayılır
                    if setup['result'] in ['WIN', 'PARTIAL_WIN']:
                        winning_trades += 1
                        current_balance += setup.get('profit_loss', 0)
                        timeframe_stats[tf]['wins'] += 1
                        coin_stats[coin]['wins'] += 1  # v2.0.0
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['wins'] += 1
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif setup['result'] == 'LOSS':
                        losing_trades += 1
                        current_balance += setup['profit_loss']
                        timeframe_stats[tf]['losses'] += 1
                        coin_stats[coin]['losses'] += 1  # v2.0.0
                        
                        setup_type = setup['setup_type']
                        if setup_type not in setup_type_stats:
                            setup_type_stats[setup_type] = {'wins': 0, 'total': 0}
                        setup_type_stats[setup_type]['total'] += 1
                    
                    elif setup['result'] == 'BREAKEVEN':
                        breakeven_trades += 1
                        timeframe_stats[tf]['breakeven'] += 1
                    
                    elif setup['status'] == 'PENDING':
                        pending_setups += 1
                        timeframe_stats[tf]['pending'] += 1
                        coin_stats[coin]['pending'] += 1  # v2.0.0
                    
                    # v1.4.10.3: TP1 artık win olarak sayılıyor, pending değil
                    elif setup['status'] == 'TP1' and setup.get('result') != 'PARTIAL_WIN':
                        # Eski TP1'ler (result olmayan) pending olarak say
                        pending_setups += 1
                        timeframe_stats[tf]['pending'] += 1
                        coin_stats[coin]['pending'] += 1  # v2.0.0
                        
                except Exception as e:
                    # v1.4.10.2: Dosya okunamadı, skip et
                    skipped_count += 1
                    continue
            
            if skipped_count > 0:
                logger.warning(f"⚠️ Skipped {skipped_count} unreadable setup files in aggregate stats")
            
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
            
            # Calculate timeframe win rates
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
            
            # v2.0.0: Calculate coin win rates
            coin_breakdown = {}
            for coin, stats in coin_stats.items():
                coin_completed = stats['wins'] + stats['losses']
                coin_win_rate = (stats['wins'] / coin_completed * 100) if coin_completed > 0 else 0
                coin_breakdown[coin] = {
                    'total': stats['total'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'pending': stats['pending'],
                    'win_rate': round(coin_win_rate, 1)
                }
            
            result = {
                'total_setups': total_setups,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': breakeven_trades,
                'pending_setups': pending_setups,
                'win_rate': win_rate,
                'loss_rate': loss_rate,
                'pending_rate': pending_rate,
                'starting_balance': starting_balance,
                'current_balance': current_balance,
                'profit': profit,
                'profit_percent': profit_percent,
                'best_setup_type': best_setup_type,
                'avg_duration_minutes': round(avg_duration, 1),
                'timeframe_breakdown': timeframe_breakdown,
                'coin_breakdown': coin_breakdown  # v2.0.0
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
        v1.4.9.8: Reset timestamp kaydediliyor
        """
        try:
            blobs = list(self.bucket.list_blobs(prefix='setups/'))
            deleted_count = 0
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    blob.delete()
                    deleted_count += 1
            
            # Reset timestamp kaydet
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
        """
        Son reset zamanını getir
        """
        try:
            meta_blob = self.bucket.blob('meta/last_reset.json')
            if meta_blob.exists():
                data = json.loads(meta_blob.download_as_string())
                return data.get('last_reset', None)
            return None
        except Exception as e:
            logger.error(f"❌ Get last reset error: {e}")
            return None
