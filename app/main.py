# -*- coding: utf-8 -*-
"""
T-TARS Trading Bot v2.2.8
=========================
Main Flask application with routes.

v2.2.8:
- NEW: 4 saat limit order expiry (dolmayan emirler iptal)
- CHANGED: Marjin hesabı TOTAL balance'a göre

v2.2.7:
- REMOVED: Monitor'dan TP/SL ekleme kaldırıldı (artık order sırasında preset ediliyor)
- FIX: "batch TP/SL" hatası çözüldü

v2.2.6:
- NEW: Place order sırasında TP/SL preset
- NEW: Telegram bildirimleri her zaman gönderiliyor

v2.2.4:
- NEW: Bitget bazlı monitor
"""

from flask import Flask, request, jsonify
from app.services.claude_service import ClaudeService
from app.services.telegram_service import TelegramService
from app.services.storage_service import StorageService
from app.services.bitget_service import BitgetService
from app.services.tracking_service import TrackingService
from app.config import Config
from app.strategies.setup_detector import detect_all_trading_setups
from app.handlers.telegram_handlers import (
    init_handlers,
    get_turkey_time,
    handle_plan_command,
    handle_execute_command,
    handle_log_command,
    handle_status_command,
    handle_scan_command,
    handle_score_command,
    handle_reset_score_command,
    handle_help_command,
    handle_balance_command,
    handle_positions_command,
    handle_stopbitget_command,
    handle_startbitget_command,
    is_trading_enabled,
    execute_trade_for_setup
)
import logging
import sys
import threading
import gc
from datetime import datetime, timezone, timedelta

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# SCAN LOCK
SCAN_LOCK = threading.Lock()

# v2.2.8: Turkey timezone
TURKEY_TZ = timezone(timedelta(hours=3))

# v2.2.8: Order expiry saati (4 saat)
ORDER_EXPIRY_HOURS = 4

def format_price(price):
    if price is None or price == 0: return "$0.00"
    abs_price = abs(float(price))
    if abs_price < 0.0001: return f"${price:.8f}"
    elif abs_price < 0.01: return f"${price:.6f}"
    elif abs_price < 1: return f"${price:.4f}"
    elif abs_price < 100: return f"${price:.4f}"
    else: return f"${price:,.2f}"

app = Flask(__name__)

# Config validation ve services init
try:
    Config.validate()
    claude = ClaudeService()
    telegram = TelegramService()
    storage = StorageService()
    bitget = BitgetService()
    tracking = TrackingService()
    
    init_handlers(telegram, bitget, claude, storage, tracking)
    
    logger.info(f"✅ All services initialized (v{Config.VERSION})")
except Exception as e:
    logger.error(f"❌ Service initialization failed: {e}")
    sys.exit(1)


# ============================================
# ROUTES - BASIC
# ============================================

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": f"T-TARS Trading Bot v{Config.VERSION}",
        "version": Config.VERSION,
        "status": "running",
        "exchange": "Bitget",
        "lock_status": "locked" if SCAN_LOCK.locked() else "free"
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": get_turkey_time().isoformat()
    })

# ============================================
# ROUTES - TELEGRAM WEBHOOK
# ============================================

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"status": "ignored"}), 200
        
        message = data['message']
        
        if message.get('from', {}).get('is_bot', False):
            return jsonify({"status": "ignored - bot message"}), 200

        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        if not text or not text.startswith('/'):
            return jsonify({"status": "ignored - not a command"}), 200
        
        allowed_chats = Config.get_allowed_chats()
        if str(chat_id) not in allowed_chats:
            logger.warning(f"Unauthorized chat_id: {chat_id}")
            return jsonify({"status": "unauthorized"}), 403
        
        command = text.split()[0].split('@')[0].lower()
        logger.info(f"📱 CMD: {command}")
        
        if command == '/plan': handle_plan_command(text, chat_id)
        elif command == '/execute': handle_execute_command(text, chat_id)
        elif command == '/log': handle_log_command(text, chat_id)
        elif command == '/status': handle_status_command(chat_id)
        elif command == '/scan': 
            if SCAN_LOCK.locked():
                telegram.send("⚠️ Otomatik tarama sürüyor, performans düşebilir.", chat_id=chat_id)
            handle_scan_command(chat_id)
        elif command == '/reset_score': handle_reset_score_command(chat_id)
        elif command == '/score': handle_score_command(chat_id)
        elif command == '/help': handle_help_command(chat_id)
        elif command == '/balance': handle_balance_command(chat_id)
        elif command == '/positions': handle_positions_command(chat_id)
        elif command == '/stopbitget': handle_stopbitget_command(chat_id)
        elif command == '/startbitget': handle_startbitget_command(chat_id)
        elif command == '/stopokx': handle_stopbitget_command(chat_id)
        elif command == '/startokx': handle_startbitget_command(chat_id)
        else: telegram.send("❌ Bilinmeyen komut.", chat_id=chat_id)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# ROUTES - MONITORING (v2.2.8 - Order Expiry)
# ============================================

@app.route('/monitor', methods=['POST', 'GET'])
def monitor_setups():
    """
    v2.2.8: Bitget Bazlı Monitor + 4 Saat Order Expiry
    
    1. Bekleyen limit emirleri kontrol et (doldu mu?)
    2. 4 saat geçen PENDING emirleri iptal et (YENİ!)
    3. Emir dolmuşsa → trackingNo al, status güncelle
    4. Copy Trade pozisyonlarını kontrol et (kapanmış mı?)
    5. Kapanmışsa → tracking güncelle
    
    NOT: TP/SL artık order sırasında preset ediliyor (v2.2.6)
         Monitor sadece status takibi yapıyor.
    """
    try:
        if not is_trading_enabled():
            logger.debug("⏸️ Trading kapalı, monitor atlandı")
            return jsonify({"status": "skipped", "reason": "trading_disabled"}), 200
        
        updates = 0
        expired_count = 0
        
        # ========================================
        # ADIM 1: Bekleyen Limit Emirleri Kontrol Et
        # ========================================
        pending_setups = tracking.get_pending_setups()
        now = datetime.now(TURKEY_TZ)
        
        for setup in pending_setups:
            try:
                setup_id = setup.get('setup_id')
                order_id = setup.get('order_id')
                tracking_no = setup.get('tracking_no')
                pair = setup.get('pair')
                direction = setup.get('direction', 'long')
                status = setup.get('status')
                created_at_str = setup.get('created_at')
                
                # ========================================
                # v2.2.8: 4 SAAT ORDER EXPIRY
                # ========================================
                if status == 'PENDING' and order_id and created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        age_hours = (now - created_at).total_seconds() / 3600
                        
                        if age_hours >= ORDER_EXPIRY_HOURS:
                            # 4 saat geçmiş, emri iptal et!
                            logger.info(f"⏰ Order expired ({age_hours:.1f}h): {setup_id} | {pair}")
                            
                            # Bitget'ten emri iptal et
                            symbol = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}" if '/' not in pair else pair
                            cancel_result = bitget.cancel_order(order_id, symbol)
                            
                            if cancel_result.get('success'):
                                # Tracking'i güncelle
                                tracking.mark_setup_expired(setup_id)
                                expired_count += 1
                                logger.info(f"✅ Order cancelled & expired: {setup_id}")
                            else:
                                # İptal başarısız olsa bile expired olarak işaretle
                                # (belki emir zaten dolmuştur veya iptal edilmiştir)
                                error = cancel_result.get('error', 'Unknown')
                                logger.warning(f"⚠️ Cancel failed ({setup_id}): {error} - marking as expired anyway")
                                tracking.mark_setup_expired(setup_id)
                                expired_count += 1
                            
                            continue  # Bu setup için devam etme
                            
                    except Exception as e:
                        logger.error(f"❌ Expiry check error ({setup_id}): {e}")
                
                # ========================================
                # Eğer tracking_no yoksa, emir henüz dolmamış olabilir
                # ========================================
                if not tracking_no and order_id and status == 'PENDING':
                    # Bitget'ten trackingNo ara
                    symbol = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}" if '/' not in pair else pair
                    found_tracking_no = bitget.find_tracking_no_by_symbol(symbol, direction)
                    
                    if found_tracking_no:
                        # Emir dolmuş! trackingNo bulundu
                        logger.info(f"✅ Emir doldu: {setup_id} → trackingNo: {found_tracking_no}")
                        
                        # v2.2.7: Sadece status güncelle
                        # TP/SL artık order sırasında preset ediliyor (presetStopSurplusPrice/presetStopLossPrice)
                        # Bu yüzden burada modify_tracking_tpsl çağrılmıyor!
                        tracking.mark_setup_filled(setup_id, found_tracking_no)
                        
                        updates += 1
                        
            except Exception as e:
                logger.error(f"❌ Pending setup kontrol hatası ({setup.get('setup_id')}): {e}")
        
        # ========================================
        # ADIM 2: Copy Trade Pozisyonlarını Kontrol Et
        # ========================================
        try:
            ct_result = bitget.get_tracking_orders()
            
            if ct_result.get('success'):
                bitget_positions = ct_result.get('orders', [])
                
                # Mevcut Bitget pozisyonlarının trackingNo'larını al
                active_tracking_nos = set()
                for pos in bitget_positions:
                    tn = pos.get('trackingNo')
                    if tn:
                        active_tracking_nos.add(str(tn))
                
                # FILLED durumundaki setup'ları kontrol et
                for setup in pending_setups:
                    if setup.get('status') != 'FILLED':
                        continue
                    
                    setup_tracking_no = setup.get('tracking_no')
                    if not setup_tracking_no:
                        continue
                    
                    # Bu tracking_no Bitget'te aktif mi?
                    if str(setup_tracking_no) not in active_tracking_nos:
                        # Pozisyon kapanmış!
                        setup_id = setup.get('setup_id')
                        logger.info(f"🔴 Pozisyon kapanmış: {setup_id} (trackingNo: {setup_tracking_no})")
                        
                        tracking.update_setup_from_bitget(setup_id, {
                            'status': 'CLOSED',
                            'result': None,
                        })
                        
                        updates += 1
                        
        except Exception as e:
            logger.error(f"❌ Copy Trade pozisyon kontrol hatası: {e}")
        
        if updates > 0 or expired_count > 0:
            logger.info(f"📊 Monitor: {updates} güncelleme, {expired_count} expired")
        
        gc.collect()
        return jsonify({"status": "success", "updates": updates, "expired": expired_count})
        
    except Exception as e:
        logger.error(f"❌ Monitor global error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """
    Otomatik Tarama (Thread-Safe & Memory Efficient)
    
    v2.2.8:
    - Setup tespit edilir
    - Trading aktifse execute edilir (limit emir + TP/SL preset)
    - Execute başarılıysa tracking'e kaydet
    - Marjin hesabı TOTAL balance'a göre
    """
    if SCAN_LOCK.locked():
        logger.warning("⚠️ Auto analyze SKIPPED: Previous scan still running or locked.")
        return jsonify({"status": "skipped", "reason": "locked"}), 200

    with SCAN_LOCK:
        try:
            logger.info("🔄 Auto analyze started...")
            
            # Balance'ı başta 1 kez çek
            current_balance = 500.0
            try:
                bal_result = bitget.get_balance()
                if bal_result.get('success'):
                    current_balance = float(bal_result.get('free', 500.0))
                    total_balance = float(bal_result.get('total', 500.0))
                    logger.info(f"💰 Balance: Total=${total_balance:.2f} | Available=${current_balance:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Balance fetch failed, using fallback: {e}")
            
            pairs = Config.AUTO_SCAN_PAIRS
            results = []
            total_setups = 0
            orders_placed = 0
            
            for pair in pairs:
                try:
                    market_data = bitget.get_complete_analysis_data(pair)
                    if not market_data: 
                        continue
                    
                    setups = detect_all_trading_setups(pair, market_data)
                    
                    if setups:
                        for setup in setups:
                            # Trading kapalıysa hiçbir şey yapma
                            if not is_trading_enabled():
                                logger.info(f"⏸️ Trading kapalı, setup atlandı: {pair}")
                                continue
                            
                            # ADIM 1: EXECUTE ET (TP/SL preset ile)
                            exec_result = execute_trade_for_setup({
                                'pair': pair,
                                'direction': setup.get('direction', 'LONG'),
                                'entry_price': setup.get('entry_price'),
                                'stop_price': setup.get('stop_price'),
                                'tp1_price': setup.get('tp1_price')
                            })
                            
                            # ADIM 2: BAŞARILIYSA LOG'LA
                            if exec_result.get('success'):
                                orders_placed += 1
                                
                                setup_data = {
                                    'pair': pair.replace('/USDT:USDT', 'USDT'),
                                    'setup_type': setup.get('type', 'UNKNOWN'),
                                    'confidence': setup.get('confidence', 'MEDIUM'),
                                    'timeframe': setup.get('timeframe', 'N/A'),
                                    'direction': setup.get('direction', 'long'),
                                    'timestamp': setup.get('timestamp'),
                                    'current_price': market_data.get('current_price', 0),
                                    'entry_price': setup.get('entry_price', 0),
                                    'entry_zone': setup.get('entry_zone', 'N/A'),
                                    'stop_loss': format_price(setup.get('stop_price', 0)),
                                    'stop_price': setup.get('stop_price', 0),
                                    'tp1': setup.get('tp1', format_price(setup.get('tp1_price', 0))),
                                    'tp2': setup.get('tp2', format_price(setup.get('tp2_price', 0))),
                                    'tp1_price': setup.get('tp1_price', 0),
                                    'tp2_price': setup.get('tp2_price', 0),
                                    'rr_ratio': setup.get('rr_ratio', 0),
                                    'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                    'ob_strength': setup.get('ob_strength', 'medium'),
                                    'balance_before': current_balance,
                                    'risk_percent': Config.RISK_PER_TRADE,
                                    
                                    # Bitget order bilgileri
                                    'order_id': exec_result.get('order_id'),
                                    'tracking_no': exec_result.get('tracking_no'),
                                    'contracts': exec_result.get('contracts', 0),
                                    'position_usd': exec_result.get('position_usd', 0),
                                }
                                
                                setup_id = tracking.log_setup(setup_data)
                                
                                if setup_id:
                                    total_setups += 1
                                    logger.info(f"✅ Execute + Log: {pair} #{setup_id} | "
                                               f"order_id={exec_result.get('order_id')}")
                            else:
                                reason = exec_result.get('reason', 'Unknown')
                                logger.warning(f"⚠️ Execute başarısız, atlandı: {pair} - {reason}")
                                    
                    results.append(f"{pair}: {len(setups) if setups else 0}")
                    
                except Exception as e:
                    logger.error(f"Pair analyze error ({pair}): {e}")
            
            logger.info(f"✅ Auto analyze finished: {total_setups} logged, {orders_placed} orders")
            gc.collect()
            
            return jsonify({
                "status": "success",
                "setups": total_setups,
                "orders": orders_placed
            })
            
        except Exception as e:
            logger.error(f"❌ Auto analyze CRASH: {e}")
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS v{Config.VERSION}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, threaded=True)
