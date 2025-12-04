# -*- coding: utf-8 -*-
"""
T-TARS Trading Bot v2.0.0
=========================
Main Flask application with routes.

v2.0.0:
- OKX API entegrasyonu
- YENİ: /balance, /positions, /stopokx, /startokx komutları
- AUTO_SCAN_PAIRS: 13 coin (XRP, AVAX, TRUMP, JUP, PEPE, TRX eklendi)
- Beta group kaldırıldı - sadece Executer

v1.4.10.3:
- FIX: /analyze sessiz çalışır - SETUP DETECTED mesajı GÖNDERME
- FIX: Duplicate detection - aynı pair+tf+direction için tekrar setup oluşturma
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
    # v2.0.0: OKX komutları
    handle_balance_command,
    handle_positions_command,
    handle_stopokx_command,
    handle_startokx_command,
    is_trading_enabled
)
import logging
import sys

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def format_price(price):
    """
    Dinamik fiyat formatı - düşük fiyatlı coinler için daha fazla basamak
    """
    if price is None or price == 0:
        return "$0.00"
    
    abs_price = abs(float(price))
    
    if abs_price < 0.0001:
        return f"${price:.8f}"
    elif abs_price < 0.01:
        return f"${price:.6f}"
    elif abs_price < 1:
        return f"${price:.4f}"
    elif abs_price < 100:
        return f"${price:.4f}"
    else:
        return f"${price:,.2f}"

# Flask app
app = Flask(__name__)

# Config validation ve services init
try:
    Config.validate()
    claude = ClaudeService()
    telegram = TelegramService()
    storage = StorageService()
    okx = OKXService()
    tracking = TrackingService()
    
    # Initialize handlers with services
    init_handlers(telegram, okx, claude, storage, tracking)
    
    logger.info("✅ All services initialized")
except Exception as e:
    logger.error(f"❌ Service initialization failed: {e}")
    sys.exit(1)


# ============================================
# ROUTES - BASIC
# ============================================

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        "service": f"T-TARS Trading Bot v{Config.VERSION}",
        "version": Config.VERSION,
        "status": "running",
        "model": Config.CLAUDE_MODEL,
        "features": ["telegram_commands", "cloud_storage", "tradingview_webhook", "okx_realtime_data", "smart_money_detection", "volume_analysis", "auto_scan", "manual_scan", "setup_tracking"]
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": get_turkey_time().isoformat(),
        "model": Config.CLAUDE_MODEL,
        "bucket": Config.BUCKET_NAME
    })


# ============================================
# ROUTES - TELEGRAM WEBHOOK
# ============================================

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Telegram Webhook - Bot komutları"""
    try:
        data = request.json
        
        if not data or 'message' not in data:
            return jsonify({"status": "ignored"}), 200
        
        message = data['message']
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        # Sadece komutlara cevap ver (/ ile başlayanlar)
        if not text or not text.startswith('/'):
            return jsonify({"status": "ignored - not a command"}), 200
        
        logger.info(f"📱 Telegram command: {text} from {chat_id}")
        
        # Multi-chat authorization
        allowed_chats = Config.get_allowed_chats()
        if str(chat_id) not in allowed_chats:
            logger.warning(f"Unauthorized chat_id: {chat_id} (Allowed: {allowed_chats})")
            return jsonify({"status": "unauthorized"}), 403
        
        # ============================================
        # KOMUT PARSING - v1.4.10.1
        # Grup chatlerinde: /score@T_Tars_Executer_Bot
        # Bu yüzden @bot_username kısmını temizliyoruz
        # ============================================
        
        # Komutu parse et: "/score@BotName arg1" → "/score"
        command = text.split()[0].split('@')[0].lower()
        
        logger.info(f"🎯 Parsed command: '{command}' (original: '{text[:50]}')")
        
        if command == '/plan':
            logger.info(f"➡️ Routing to handle_plan_command")
            handle_plan_command(text, chat_id)
        elif command == '/execute':
            logger.info(f"➡️ Routing to handle_execute_command")
            handle_execute_command(text, chat_id)
        elif command == '/log':
            logger.info(f"➡️ Routing to handle_log_command")
            handle_log_command(text, chat_id)
        elif command == '/status':
            logger.info(f"➡️ Routing to handle_status_command")
            handle_status_command(chat_id)
        elif command == '/scan':
            logger.info(f"➡️ Routing to handle_scan_command")
            handle_scan_command(chat_id)
        elif command == '/reset_score':
            logger.info(f"➡️ Routing to handle_reset_score_command")
            handle_reset_score_command(chat_id)
        elif command == '/score':
            logger.info(f"➡️ Routing to handle_score_command")
            handle_score_command(chat_id)
        elif command == '/help':
            logger.info(f"➡️ Routing to handle_help_command")
            handle_help_command(chat_id)
        # v2.0.0: OKX komutları
        elif command == '/balance':
            logger.info(f"➡️ Routing to handle_balance_command")
            handle_balance_command(chat_id)
        elif command == '/positions':
            logger.info(f"➡️ Routing to handle_positions_command")
            handle_positions_command(chat_id)
        elif command == '/stopokx':
            logger.info(f"➡️ Routing to handle_stopokx_command")
            handle_stopokx_command(chat_id)
        elif command == '/startokx':
            logger.info(f"➡️ Routing to handle_startokx_command")
            handle_startokx_command(chat_id)
        else:
            logger.warning(f"⚠️ Unknown command: '{command}'")
            telegram.send("❌ Bilinmeyen komut. `/help` yazın.", chat_id=chat_id)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"❌ Telegram webhook error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ROUTES - TRADINGVIEW WEBHOOK
# ============================================

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """TradingView Webhook Endpoint"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400
        
        logger.info(f"📊 TradingView Alert: {data}")
        
        ticker = data.get('ticker', 'UNKNOWN')
        interval = data.get('interval', 'N/A')
        close = data.get('close', 'N/A')
        
        message = f"""
🚨 *TRADINGVIEW ALERT*

📊 {ticker} | {interval}
💰 ${close}

⏰ {get_turkey_time().strftime('%H:%M:%S')}
"""
        
        telegram.send(message)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"❌ TradingView webhook error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/test/telegram', methods=['GET'])
def test_telegram():
    """Telegram test endpoint"""
    try:
        telegram.send(f"🧪 *T-TARS v{Config.VERSION} Test*\n\n✅ Sistem çalışıyor!\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# ROUTES - MONITORING & AUTO-ANALYZE
# ============================================

@app.route('/monitor', methods=['POST', 'GET'])
def monitor_setups():
    """
    Cloud Scheduler tarafından her 5 dakikada tetiklenen otomatik setup monitoring
    """
    try:
        logger.info("🔍 Monitor: Checking pending setups...")
        
        pending_data = tracking.get_all_pending_setups()
        pending_setups = pending_data.get('setups', [])
        
        if not pending_setups or len(pending_setups) == 0:
            logger.info("ℹ️ No pending setups to monitor")
            return jsonify({
                "status": "success",
                "timestamp": get_turkey_time().isoformat(),
                "pending_setups": 0,
                "updates": []
            })
        
        logger.info(f"📊 Found {len(pending_setups)} pending setup(s)")
        updates = []
        
        for setup in pending_setups:
            try:
                setup_id = setup['id']
                pair = setup['pair']
                setup_type = setup['setup_type']
                
                if '/' not in pair:
                    okx_pair = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}"
                else:
                    okx_pair = pair
                
                current_price = okx.get_current_price(okx_pair)
                logger.info(f"💰 {pair}: Current price ${current_price:,.2f}")
                
                status_result = tracking.check_setup_status(setup_id, current_price)
                
                if status_result and status_result.get('status_changed'):
                    new_status = status_result['new_status']
                    old_status = status_result['old_status']
                    setup_data = status_result.get('setup', {})
                    
                    profit = setup_data.get('profit_loss', 0)
                    balance_before = setup_data.get('balance_before', 1000)
                    balance_after = setup_data.get('balance_after', balance_before)
                    profit_percent = (profit / balance_before * 100) if balance_before > 0 else 0
                    duration = setup_data.get('duration_minutes', 0)
                    movement = setup_data.get('movement_captured_dollars', 0)
                    
                    stats = tracking.get_aggregate_stats()
                    
                    timeframe = setup_data.get('timeframe', setup.get('timeframe', 'N/A'))
                    entry_price = setup_data.get('entry_price', setup.get('current_price', 0))
                    stop_price = setup_data.get('stop_price', 0)
                    tp1_price = setup_data.get('tp1_price', 0)
                    tp2_price = setup_data.get('tp2_price', 0)
                    
                    # Doğru hedef fiyatı belirle
                    if new_status == 'TP1':
                        target_price = tp1_price
                    elif new_status == 'COMPLETED':
                        target_price = tp2_price
                    elif new_status == 'STOPPED':
                        target_price = stop_price
                    else:
                        target_price = current_price
                    
                    # Emoji mapping
                    if new_status == 'TP1':
                        emoji = '🎯'
                        header_emoji = '💰💰💰'
                        status_text = 'TP1 HIT!'
                        status_emoji = '✅'
                        next_action = '📊 Status: Breakeven, TP2 bekliyor'
                    elif new_status == 'COMPLETED':
                        emoji = '🎉'
                        header_emoji = '🎉🎉🎉'
                        status_text = 'TP2 HIT - FULL WIN!'
                        status_emoji = '🏆'
                        next_action = '✅ Setup tamamlandı!'
                    elif new_status == 'STOPPED':
                        emoji = '⛔'
                        header_emoji = '❌'
                        status_text = 'STOP HIT'
                        status_emoji = '❌'
                        next_action = '❌ Setup kapatıldı'
                    else:
                        emoji = '📊'
                        header_emoji = ''
                        status_text = 'Status Updated'
                        status_emoji = 'ℹ️'
                        next_action = ''
                    
                    duration_text = f"⏱️ {duration:.1f}m\n" if duration > 0 else ""
                    movement_text = f"📊 Move: {format_price(movement)}\n" if movement > 0 else ""
                    
                    broadcast_message = f"""
{emoji} **SETUP #{setup_id[:8].upper()} → {status_text}** {header_emoji}

📊 Parite: {pair}
🎯 Setup: {setup_type}
⏱️ TF: {timeframe.lower() if isinstance(timeframe, str) else timeframe}
{status_emoji} Entry: {format_price(entry_price)} → {new_status}: {format_price(target_price)}
💰 P/L: {'+' if profit >= 0 else ''}{profit_percent:.2f}% (${profit:+.2f})
{movement_text}{duration_text}{next_action}

📈 Stats: {stats['winning_trades']}W/{stats['losing_trades']}L ({stats['win_rate']:.0f}%) | ${stats['current_balance']:,.0f}

⏰ {get_turkey_time().strftime('%H:%M:%S')}
"""
                    
                    telegram.send_signal(broadcast_message)
                    
                    updates.append({
                        'setup_id': setup_id,
                        'pair': pair,
                        'old_status': old_status,
                        'new_status': new_status,
                        'profit': profit,
                        'profit_percent': profit_percent,
                        'duration_minutes': duration,
                        'movement_dollars': movement
                    })
                    
                    logger.info(f"✅ {pair} #{setup_id[:8]}: {old_status} → {new_status} (Profit: {profit_percent:+.2f}%, Duration: {duration:.1f}m)")
                
            except Exception as e:
                logger.error(f"❌ Error monitoring setup {setup.get('id', 'unknown')}: {e}")
                updates.append({
                    'setup_id': setup.get('id', 'unknown'),
                    'error': str(e)
                })
        
        logger.info(f"✅ Monitor completed: {len(updates)} update(s)")
        
        return jsonify({
            "status": "success",
            "timestamp": get_turkey_time().isoformat(),
            "pending_setups": len(pending_setups),
            "updates": updates
        })
        
    except Exception as e:
        logger.error(f"❌ Monitor error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """
    Cloud Scheduler tarafından her 3 dakikada tetiklenen otomatik analiz
    v1.4.10.3: 
    - Duplicate detection
    - SETUP DETECTED mesajı GÖNDERİLMEZ (sessiz çalışır)
    - Sadece tracking'e kaydeder
    """
    try:
        pairs = Config.AUTO_SCAN_PAIRS
        results = []
        total_setups = 0
        skipped_duplicates = 0
        
        for pair in pairs:
            try:
                market_data = okx.get_complete_analysis_data(pair)
                setups = detect_all_trading_setups(pair, market_data)
                
                if setups:
                    for setup in setups:
                        entry_zone = setup.get('entry_zone', 'N/A')
                        stop_loss = setup.get('stop_loss', 'N/A')
                        tp1 = setup.get('tp1', 'N/A')
                        tp2 = setup.get('tp2', 'N/A')
                        timeframe = setup.get('timeframe', '5m')
                        
                        entry_price = setup.get('entry_price', setup.get('current_price', market_data['current_price']))
                        
                        # TRACKING KAYDI (sessiz - mesaj yok)
                        try:
                            setup_id = tracking.log_setup({
                                'pair': pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT'),
                                'timeframe': timeframe,
                                'timestamp': f"{market_data['current_date']} {market_data['current_time']}",
                                'setup_type': setup['type'],
                                'confidence': setup['confidence'],
                                'entry_zone': entry_zone,
                                'stop_loss': stop_loss,
                                'tp1': tp1,
                                'tp2': tp2,
                                'current_price': market_data['current_price'],
                                'entry_price': entry_price,
                                'stop_price': setup.get('stop_price', 0),
                                'tp1_price': setup.get('tp1_price', 0),
                                'tp2_price': setup.get('tp2_price', 0),
                                'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                'ob_strength': setup.get('ob_strength', 'medium'),
                                'rr_ratio': setup.get('rr_ratio', 0),
                                'balance_before': 1000.00,
                                'risk_percent': 2.0
                            })
                            
                            # v1.4.10.3: Duplicate ise None döner
                            if setup_id is None:
                                skipped_duplicates += 1
                                continue
                            
                            # v1.4.10.3: SETUP DETECTED mesajı GÖNDERME - sessiz çalış
                            logger.info(f"✅ Setup #{setup_id} logged (entry: {format_price(entry_price)}) [silent]")
                            total_setups += 1
                            
                        except Exception as track_error:
                            logger.error(f"❌ Tracking failed: {track_error}")
                    
                    results.append(f"{pair}: {len(setups)} setup(s) found")
                else:
                    results.append(f"{pair}: No setup")
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
                results.append(f"{pair}: Error")
        
        logger.info(f"✅ Auto analyze completed: {total_setups} new setups, {skipped_duplicates} duplicates skipped [silent mode]")
        return jsonify({"status": "success", "timestamp": get_turkey_time().isoformat(), "results": results, "total_setups": total_setups, "skipped_duplicates": skipped_duplicates})
    except Exception as e:
        logger.error(f"Auto analyze error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS Trading Bot v{Config.VERSION} on port {Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)
