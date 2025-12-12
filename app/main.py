# -*- coding: utf-8 -*-
"""
T-TARS Trading Bot v2.1.1
=========================
Main Flask application with routes.

v2.1.1:
- FIX: auto_analyze() başında OKX balance çekiliyor
- FIX: tracking.log_setup()'a gerçek balance geçiriliyor

v2.1.0:
- FIX: tracking.log_setup() eksik field'lar tamamlandı (timestamp, entry_price, stop_loss, vs.)
- FIX: Detector'dan gelen tüm veriler doğru mapping ile tracking'e geçiriliyor

v2.0.7 (STABILITY FIX):
- NEW: Scan Lock mekanizması eklendi. (Manuel ve Oto tarama çakışmaz)
- NEW: Garbage Collection (gc) eklendi. (RAM şişmesini önler)
"""

from flask import Flask, request, jsonify
from app.services.claude_service import ClaudeService
from app.services.telegram_service import TelegramService
from app.services.storage_service import StorageService
from app.services.okx_service import OKXService
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
    handle_stopokx_command,
    handle_startokx_command,
    is_trading_enabled,
    execute_trade_for_setup
)
import logging
import sys
import threading
import gc  # Garbage Collector (RAM temizliği için şart)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# SCAN LOCK: Aynı anda sadece tek bir analiz işleminin çalışmasına izin ver
SCAN_LOCK = threading.Lock()

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
    okx = OKXService()
    tracking = TrackingService()
    
    # Initialize handlers
    init_handlers(telegram, okx, claude, storage, tracking)
    
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
        
        # Bot koruması
        if message.get('from', {}).get('is_bot', False):
            return jsonify({"status": "ignored - bot message"}), 200

        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        if not text or not text.startswith('/'):
            return jsonify({"status": "ignored - not a command"}), 200
        
        # Auth Check
        allowed_chats = Config.get_allowed_chats()
        if str(chat_id) not in allowed_chats:
            logger.warning(f"Unauthorized chat_id: {chat_id}")
            return jsonify({"status": "unauthorized"}), 403
        
        # Komut Yönlendirme
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
        elif command == '/stopokx': handle_stopokx_command(chat_id)
        elif command == '/startokx': handle_startokx_command(chat_id)
        else: telegram.send("❌ Bilinmeyen komut.", chat_id=chat_id)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================
# ROUTES - MONITORING & AUTO-ANALYZE
# ============================================

@app.route('/monitor', methods=['POST', 'GET'])
def monitor_setups():
    """Otomatik setup takibi (3dk)"""
    try:
        pending_data = tracking.get_all_pending_setups()
        pending_setups = pending_data.get('setups', [])
        
        if not pending_setups:
            logger.info("ℹ️ Monitor: No pending setups")
            return jsonify({"status": "success", "count": 0})
        
        updates = []
        for setup in pending_setups:
            try:
                setup_id = setup.get('id')
                pair = setup.get('pair')
                
                if '/' not in pair: okx_pair = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}"
                else: okx_pair = pair
                
                current_price = okx.get_current_price(okx_pair)
                status_result = tracking.check_setup_status(setup_id, current_price)
                
                if status_result and status_result.get('status_changed'):
                    new_status = status_result['new_status']
                    
                    # Status'a göre emoji mapping
                    status_emojis = {
                        'TP1': '✅',
                        'TP2': '🎯', 
                        'STOPPED': '🛑',
                        'EXPIRED': '⏰'
                    }
                    emoji = status_emojis.get(new_status, '🚀')
                    
                    # Bildirim Gönder
                    profit = status_result['setup'].get('profit_loss', 0)
                    telegram.send(f"{emoji} **UPDATE:** {pair}\nDurum: {new_status}\nP/L: ${profit:.2f}")
                    updates.append(setup_id)
                    
            except Exception as e:
                logger.error(f"Monitor error for {setup.get('id')}: {e}")
        
        gc.collect()
        return jsonify({"status": "success", "updates": len(updates)})
        
    except Exception as e:
        logger.error(f"Monitor global error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """
    Otomatik Tarama (Thread-Safe & Memory Efficient)
    v2.1.1: Balance başta 1 kez çekiliyor
    """
    if SCAN_LOCK.locked():
        logger.warning("⚠️ Auto analyze SKIPPED: Previous scan still running or locked.")
        return jsonify({"status": "skipped", "reason": "locked"}), 200

    with SCAN_LOCK:
        try:
            logger.info("🔄 Auto analyze started...")
            
            # v2.1.1: Balance'ı başta 1 kez çek (tüm setup'lar için kullanılacak)
            current_balance = 500.0  # Fallback değer
            try:
                bal_result = okx.get_balance()
                if bal_result.get('success'):
                    current_balance = float(bal_result.get('free', 500.0))
                    logger.info(f"💰 Current balance: ${current_balance:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Balance fetch failed, using fallback: {e}")
            
            pairs = Config.AUTO_SCAN_PAIRS
            results = []
            total_setups = 0
            orders_placed = 0
            
            for pair in pairs:
                try:
                    market_data = okx.get_complete_analysis_data(pair)
                    if not market_data: 
                        continue
                    
                    setups = detect_all_trading_setups(pair, market_data)
                    
                    if setups:
                        for setup in setups:
                            # v2.1.1: Gerçek balance geçiriliyor
                            setup_data = {
                                'pair': pair.replace('/USDT:USDT', 'USDT'),
                                'setup_type': setup.get('type', 'UNKNOWN'),
                                'confidence': setup.get('confidence', 'MEDIUM'),
                                'timeframe': setup.get('timeframe', 'N/A'),
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
                                'balance_before': current_balance,  # v2.1.1: Gerçek balance
                                'risk_percent': 2.0,
                            }
                            
                            setup_id = tracking.log_setup(setup_data)
                            
                            if setup_id:
                                total_setups += 1
                                logger.info(f"✅ Setup logged: {pair} #{setup_id}")
                                
                                if is_trading_enabled():
                                    res = execute_trade_for_setup({
                                        'pair': pair,
                                        'direction': setup.get('direction', 'LONG'),
                                        'entry_price': setup.get('entry_price'),
                                        'stop_price': setup.get('stop_price'),
                                        'tp1_price': setup.get('tp1_price')
                                    })
                                    if res.get('success'): 
                                        orders_placed += 1
                                    
                    results.append(f"{pair}: {len(setups) if setups else 0}")
                    
                except Exception as e:
                    logger.error(f"Pair analyze error ({pair}): {e}")
            
            logger.info(f"✅ Auto analyze finished: {total_setups} setups, {orders_placed} orders")
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
