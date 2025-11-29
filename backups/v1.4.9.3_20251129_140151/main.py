# -*- coding: utf-8 -*-
"""
T-TARS Trading Bot v1.4.6
=========================
Main Flask application with routes.
Handlers moved to app/handlers/telegram_handlers.py
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
    handle_help_command
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
        
        # Komutları işle
        if text.startswith('/plan'):
            handle_plan_command(text, chat_id)
        elif text.startswith('/execute'):
            handle_execute_command(text, chat_id)
        elif text.startswith('/log'):
            handle_log_command(text, chat_id)
        elif text.startswith('/status'):
            handle_status_command(chat_id)
        elif text.startswith('/scan'):
            handle_scan_command(chat_id)
        elif text.startswith('/score'):
            handle_score_command(chat_id)
        elif text.startswith('/reset_score'):
            handle_reset_score_command(chat_id)
        elif text.startswith('/help'):
            handle_help_command(chat_id)
        else:
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
        
        pending_setups = tracking.get_all_pending_setups()
        
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
                    
                    # Timeframe from setup
                    timeframe = setup_data.get('timeframe', setup.get('timeframe', 'N/A'))
                    entry_price = setup_data.get('entry_price', setup.get('current_price', 0))
                    
                    # Emoji mapping (v1.4.8)
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
                    
                    # Duration text
                    duration_text = f"⏱️ Duration: {duration:.1f} minutes\n" if duration > 0 else ""
                    
                    # Movement text (v1.4.8: entry → target arası)
                    movement_text = f"📊 Movement: ${movement:.2f}\n" if movement > 0 else ""
                    
                    broadcast_message = f"""
{emoji} **SETUP #{setup_id[:8].upper()} → {status_text}** {header_emoji}

📊 **Parite:** {pair}
🎯 **Setup Type:** {setup_type}
⏱️ **Timeframe:** {timeframe.upper() if isinstance(timeframe, str) else timeframe}
{status_emoji} **Entry:** ${entry_price:,.2f} → **{new_status}:** ${current_price:,.2f}
💰 **Profit:** {'+' if profit >= 0 else ''}{profit_percent:+.2f}% (${profit:+,.2f})
{movement_text}{duration_text}{next_action}

---
📈 **Current Stats:**
• Total Setups: {stats['total_setups']}
• Win Rate: {stats['win_rate']:.1f}%
• Current Balance: ${stats['current_balance']:,.2f} ({stats['profit_percent']:+.1f}%)

⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
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
    """Cloud Scheduler tarafından her 3 dakikada tetiklenen otomatik analiz"""
    try:
        pairs = Config.AUTO_SCAN_PAIRS
        results = []
        total_setups = 0
        
        for pair in pairs:
            try:
                market_data = okx.get_complete_analysis_data(pair)
                setups = detect_all_trading_setups(pair, market_data)
                
                if setups:
                    # HER SETUP İÇİN AYRI MESAJ
                    for setup in setups:
                        entry_zone = setup.get('entry_zone', 'N/A')
                        stop_loss = setup.get('stop_loss', 'N/A')
                        tp1 = setup.get('tp1', 'N/A')
                        tp2 = setup.get('tp2', 'N/A')
                        detailed_explanation = setup.get('detailed_explanation', setup.get('details', ''))
                        timeframe = setup.get('timeframe', '5m')
                        
                        # TRACKING KAYDI EKLE
                        try:
                            setup_id = tracking.log_setup({
                                'pair': pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT'),
                                'timestamp': f"{market_data['current_date']} {market_data['current_time']}",
                                'setup_type': setup['type'],
                                'confidence': setup['confidence'],
                                'entry_zone': entry_zone,
                                'stop_loss': stop_loss,
                                'tp1': tp1,
                                'tp2': tp2,
                                'current_price': setup.get('current_price', market_data['current_price']),
                                'stop_price': setup.get('stop_price', 0),
                                'tp1_price': setup.get('tp1_price', 0),
                                'tp2_price': setup.get('tp2_price', 0),
                                'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                'ob_strength': setup.get('ob_strength', 'medium'),
                                'rr_ratio': setup.get('rr_ratio', 0),
                                'balance_before': 1000.00,
                                'risk_percent': 2.0
                            })
                            logger.info(f"✅ Setup #{setup_id} logged and tracked")
                        except Exception as track_error:
                            logger.error(f"❌ Tracking failed: {track_error}")
                        
                        message = f"""```
🚨 SETUP DETECTED!

📊 Parite: {pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')}
🎯 Setup: {setup['type']}
⏱️ Timeframe: {timeframe.upper()}
{"🔴 Bias: SHORT" if 'SHORT' in setup['type'] else "🟢 Bias: LONG"}
⚡ Confidence: {setup['confidence']}

💰 Mevcut Fiyat: ${market_data['current_price']:,.2f}
🎯 Entry Zone: {entry_zone}
🛡️ Stop Loss: {stop_loss}
🎁 TP1 (Tars TP): {tp1}
🎁 TP2 (Kadircan TP): {tp2}
📅 Time: {market_data['current_time']}
```

---
**📊 Detaylar:**

{detailed_explanation}

---
🤖 **AI Genel Düşünceler:**

_"Bu setup, güçlü OB reaction + volume spike kombinasyonuna dayanıyor. Stop tight ama realistic, TP mantıklı seviyede. Entry zone'da patience kritik - aggressive giriş riskli. R:R oranı solid setup sunuyor."_
"""
                        telegram.send_signal(message)
                        total_setups += 1
                    
                    results.append(f"{pair}: {len(setups)} setup(s) found")
                else:
                    results.append(f"{pair}: No setup")
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
                results.append(f"{pair}: Error")
        
        logger.info(f"✅ Auto analyze completed: {total_setups} total setups found")
        return jsonify({"status": "success", "timestamp": get_turkey_time().isoformat(), "results": results, "total_setups": total_setups})
    except Exception as e:
        logger.error(f"Auto analyze error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS Trading Bot v{Config.VERSION} on port {Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)
