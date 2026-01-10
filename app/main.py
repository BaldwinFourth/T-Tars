# -*- coding: utf-8 -*-
"""
T-TARS Trading Bot v2.7.1
===========================
Main Flask application with routes.

v2.7.1:
- NEW: Position stacking limit kontrolü (per coin + per direction)
- NEW: check_position_limit() entegrasyonu - execute_trade_for_setup öncesi
- Limitler: MAX_MARGIN_PER_COIN_DIRECTION=$200, MAX_POSITION_VALUE=$4000

v2.7.0:
- REMOVED: /plan, /scan, /execute, /log komutları
- NEW: Trade notification'larına pattern bilgisi eklendi
- CLEANUP: Kullanılmayan import'lar kaldırıldı

v2.6.1:
- FIX: Momentum body_sizes artık body_ratio kullanıyor

v2.6.0:
- NEW: Kapsamlı Candle Pattern Detection sistemi
"""

from flask import Flask, request, jsonify
from app.services.grok_service import GrokService
from app.services.telegram_service import TelegramService
from app.services.storage_service import StorageService
from app.services.bitget_service import BitgetService
from app.services.tracking_service import TrackingService
from app.config import Config
from app.strategies.setup_detector import detect_all_trading_setups
from app.strategies.calculators import calculate_setup_strength
from app.strategies.volume_analyzer import (
    store_volume, 
    get_volume, 
    get_all_volumes, 
    cleanup_expired_volumes,
    get_volume_store_stats
)
from app.handlers.telegram_handlers import (
    init_handlers,
    get_turkey_time,
    handle_status_command,
    handle_score_command,
    handle_reset_score_command,
    handle_help_command,
    handle_balance_command,
    handle_positions_command,
    handle_stopbitget_command,
    handle_startbitget_command,
    is_trading_enabled
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

# MARKET CACHE (TradingView'dan Volume + ATR)
MARKET_CACHE = {}

# Turkey timezone
TURKEY_TZ = timezone(timedelta(hours=3))

# Son cleanup zamanı (günde 1 kez)
LAST_CLEANUP_DATE = None


def format_price(price):
    """Fiyat formatlama"""
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


app = Flask(__name__)

# ============================================
# SERVICE INITIALIZATION
# ============================================
try:
    Config.validate()
    grok = GrokService()
    telegram = TelegramService()
    storage = StorageService()
    bitget = BitgetService()
    tracking = TrackingService()
    
    init_handlers(telegram, bitget, grok, storage, tracking, market_cache=MARKET_CACHE)
    
    logger.info(f"✅ All services initialized (v{Config.VERSION})")
except Exception as e:
    logger.error(f"❌ Service initialization failed: {e}")
    sys.exit(1)


# ============================================
# ROUTES - BASIC
# ============================================

@app.route('/', methods=['GET'])
def index():
    vol_stats = get_volume_store_stats()
    return jsonify({
        "service": f"T-TARS Trading Bot v{Config.VERSION}",
        "version": Config.VERSION,
        "status": "running",
        "exchange": "Bitget",
        "ai_engine": "Grok 4.1 Fast Reasoning",
        "market_source": "TradingView (Binance) - Volume + ATR",
        "lock_status": "locked" if SCAN_LOCK.locked() else "free",
        "market_cache_size": len(MARKET_CACHE),
        "market_cache_ttl": Config.MARKET_CACHE_TTL,
        "volume_store_size": vol_stats.get('total', 0),
        "position_limits": {
            "max_margin_per_coin_direction": Config.MAX_MARGIN_PER_COIN_DIRECTION,
            "max_position_value_per_coin_direction": Config.MAX_POSITION_VALUE_PER_COIN_DIRECTION
        }
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": get_turkey_time().isoformat(),
        "market_cache_entries": len(MARKET_CACHE),
        "market_cache_ttl": Config.MARKET_CACHE_TTL
    })


# ============================================
# ROUTES - TRADINGVIEW MARKET WEBHOOK
# ============================================

@app.route('/webhook/volume', methods=['POST'])
def volume_webhook():
    """TradingView Market Data Webhook (Volume + ATR)"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        pair = data.get('pair', '').upper()
        if not pair:
            return jsonify({"status": "error", "message": "Missing pair"}), 400
        
        pair = pair.replace('.P', '').replace('PERP', '')
        if not pair.endswith('USDT'):
            pair = pair + 'USDT'
        
        tf_raw = str(data.get('tf', '15'))
        tf_map = {
            '1': '1m', '3': '3m', '5': '5m', '15': '15m', '30': '30m',
            '60': '1h', '240': '4h', '1D': '1d', 'D': '1d',
            '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d'
        }
        tf = tf_map.get(tf_raw, '15m')
        
        if 'spike' not in data:
            return jsonify({"status": "error", "message": "Missing spike field"}), 400
        
        spike = float(data.get('spike', 0))
        atr = float(data.get('atr', 0)) if data.get('atr') else 0
        
        cache_key = f"{pair}_{tf}"
        
        store_volume(pair, tf, spike, atr)
        
        MARKET_CACHE[cache_key] = {
            'spike': round(spike, 2),
            'atr': round(atr, 6) if atr > 0 else 0,
            'ts': int(datetime.now().timestamp()),
            'price': float(data.get('price', 0)),
            'source': 'tradingview_binance'
        }
        
        atr_str = f", ATR={atr:.6g}" if atr > 0 else ""
        logger.info(f"📊 Market Webhook: {cache_key} = {spike:.2f}x{atr_str} (Binance)")
        
        return jsonify({
            "status": "success",
            "cached": cache_key,
            "spike": spike,
            "atr": atr if atr > 0 else None,
            "cache_size": len(MARKET_CACHE)
        })
        
    except Exception as e:
        logger.error(f"Market webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/webhook/volume/status', methods=['GET'])
def volume_cache_status():
    """Market cache durumunu göster"""
    now = int(datetime.now().timestamp())
    
    cache_info = []
    for key, val in MARKET_CACHE.items():
        age = now - val.get('ts', 0)
        entry = {
            'key': key,
            'spike': val.get('spike', 0),
            'age_seconds': age,
            'fresh': age < Config.MARKET_CACHE_TTL
        }
        if val.get('atr', 0) > 0:
            entry['atr'] = val.get('atr')
        cache_info.append(entry)
    
    vol_stats = get_volume_store_stats()
    
    return jsonify({
        "status": "success",
        "cache_ttl_seconds": Config.MARKET_CACHE_TTL,
        "entries": len(cache_info),
        "cache": cache_info,
        "volume_store": vol_stats
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
        
        # v2.7.0: Sadeleştirilmiş komutlar
        if command == '/status':
            handle_status_command(chat_id)
        elif command == '/reset_score':
            handle_reset_score_command(chat_id)
        elif command == '/score':
            handle_score_command(chat_id)
        elif command == '/help':
            handle_help_command(chat_id)
        elif command == '/balance':
            handle_balance_command(chat_id)
        elif command == '/positions':
            handle_positions_command(chat_id)
        elif command == '/stopbitget':
            handle_stopbitget_command(chat_id)
        elif command == '/startbitget':
            handle_startbitget_command(chat_id)
        elif command in ['/stopokx', '/startokx']:
            if 'stop' in command:
                handle_stopbitget_command(chat_id)
            else:
                handle_startbitget_command(chat_id)
        elif command == '/volume':
            cache_count = len(MARKET_CACHE)
            fresh_count = sum(1 for v in MARKET_CACHE.values() 
                           if (int(datetime.now().timestamp()) - v.get('ts', 0)) < Config.MARKET_CACHE_TTL)
            atr_count = sum(1 for v in MARKET_CACHE.values() if v.get('atr', 0) > 0)
            vol_stats = get_volume_store_stats()
            telegram.send(
                f"📊 *Market Cache*\n\n"
                f"MARKET_CACHE: {cache_count}\n"
                f"Taze (<{Config.MARKET_CACHE_TTL//60}dk): {fresh_count}\n"
                f"ATR mevcut: {atr_count}\n\n"
                f"*Volume Store*\n"
                f"Toplam: {vol_stats.get('total', 0)}\n"
                f"Pair'ler: {', '.join(vol_stats.get('pairs', []))}", 
                chat_id=chat_id
            )
        else:
            telegram.send("❌ Bilinmeyen komut. /help yazın.", chat_id=chat_id)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ROUTES - MONITORING
# ============================================

@app.route('/monitor', methods=['POST', 'GET'])
def monitor_setups():
    """Bitget Bazlı Monitor + TF Bazlı Order Expiry"""
    try:
        if not is_trading_enabled():
            return jsonify({"status": "skipped", "reason": "trading_disabled"}), 200
        
        updates = 0
        
        # ADIM 1: TF bazlı order expiry kontrolü
        expired_count, cancelled_orders = tracking.check_and_expire_orders(bitget)
        
        # ADIM 2: Bekleyen emirlerin trackingNo kontrolü
        pending_setups = tracking.get_pending_setups()
        
        for setup in pending_setups:
            try:
                setup_id = setup.get('setup_id')
                order_id = setup.get('order_id')
                tracking_no = setup.get('tracking_no')
                pair = setup.get('pair')
                direction = setup.get('direction', 'long')
                status = setup.get('status')
                
                if not tracking_no and order_id and status == 'PENDING':
                    symbol = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}" if '/' not in pair else pair
                    found_tracking_no = bitget.find_tracking_no_by_symbol(symbol, direction)
                    
                    if found_tracking_no:
                        logger.info(f"✅ Emir doldu: {setup_id} → trackingNo: {found_tracking_no}")
                        tracking.mark_setup_filled(setup_id, found_tracking_no)
                        updates += 1
                        
            except Exception as e:
                logger.error(f"Pending setup error ({setup.get('setup_id')}): {e}")
        
        # ADIM 3: Copy Trade pozisyonlarını kontrol et
        try:
            ct_result = bitget.get_tracking_orders()
            
            if ct_result.get('success'):
                bitget_positions = ct_result.get('orders', [])
                active_tracking_nos = {str(pos.get('trackingNo')) for pos in bitget_positions if pos.get('trackingNo')}
                
                for setup in pending_setups:
                    if setup.get('status') != 'FILLED':
                        continue
                    
                    setup_tracking_no = setup.get('tracking_no')
                    if not setup_tracking_no:
                        continue
                    
                    if str(setup_tracking_no) not in active_tracking_nos:
                        setup_id = setup.get('setup_id')
                        pair = setup.get('pair', 'UNKNOWN')
                        direction = setup.get('direction', 'UNKNOWN').upper()
                        coin_name = pair.replace('USDT', '').replace('/USDT:USDT', '')
                        
                        logger.info(f"🔴 Pozisyon kapanmış: {setup_id} ({coin_name} {direction})")
                        
                        pnl_data = bitget.get_closed_position_pnl(setup_tracking_no)
                        
                        if pnl_data.get('success'):
                            pnl = pnl_data.get('pnl', 0)
                            trade_result = pnl_data.get('result', 'BREAKEVEN')
                            entry_price = pnl_data.get('entry_price', 0)
                            close_price = pnl_data.get('close_price', 0)
                            
                            tracking.update_setup_from_bitget(setup_id, {
                                'status': 'CLOSED',
                                'result': trade_result,
                                'pnl': pnl,
                                'entry_price': entry_price,
                                'close_price': close_price
                            })
                            
                            # v2.7.0: Pozisyon kapanış mesajı (TP/SL bilgisi)
                            if trade_result == 'WIN':
                                result_emoji = "✅"
                                header = "TP - POZİSYON KAPANDI"
                            elif trade_result == 'LOSS':
                                result_emoji = "❌"
                                header = "SL - POZİSYON KAPANDI"
                            else:
                                result_emoji = "⚪"
                                header = "POZİSYON KAPANDI"
                            
                            pnl_sign = "+" if pnl >= 0 else ""
                            dir_emoji = "🟢" if direction == "LONG" else "🔴"
                            
                            close_msg = f"""
━━━━━━━━━━━
{result_emoji} *{header}*
━━━━━━━━━━━

{dir_emoji} *{coin_name}* | {direction}
💵 Entry: {format_price(entry_price)}
💰 Exit: {format_price(close_price)}

{result_emoji} *P/L: {pnl_sign}${pnl:.2f}*
🔢 Tracking: `{setup_tracking_no}`

━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%H:%M:%S')} TR
"""
                            telegram.send(close_msg, chat_id=Config.TELEGRAM_CHAT_ID)
                        else:
                            logger.warning(f"⚠️ PnL alınamadı: {setup_id} - {pnl_data.get('error')}")
                            tracking.update_setup_from_bitget(setup_id, {'status': 'CLOSED', 'result': None})
                        
                        updates += 1
                        
        except Exception as e:
            logger.error(f"Copy Trade check error: {e}")
        
        if updates > 0 or expired_count > 0:
            logger.info(f"📊 Monitor: {updates} updates, {expired_count} expired")
        
        gc.collect()
        return jsonify({"status": "success", "updates": updates, "expired": expired_count})
        
    except Exception as e:
        logger.error(f"Monitor error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ROUTES - AUTO ANALYZE
# ============================================

@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """Grok 4.1 Fast Reasoning ile Otomatik Tarama + Pattern Detection + Position Limit"""
    global LAST_CLEANUP_DATE
    
    interval = Config.MONITOR_INTERVAL_MINUTES
    current_minute = datetime.now().minute
    if current_minute % interval != 1:
        logger.debug(f"⏳ Analyze skipped: minute={current_minute}, interval={interval}")
        return jsonify({
            "status": "skipped", 
            "reason": "waiting_for_bar_close",
            "current_minute": current_minute,
            "interval": interval
        }), 200
    
    if SCAN_LOCK.locked():
        logger.warning("⚠️ Auto analyze SKIPPED: Lock active")
        return jsonify({"status": "skipped", "reason": "locked"}), 200

    with SCAN_LOCK:
        try:
            logger.info(f"🔄 Auto analyze started (v{Config.VERSION})")
            
            # Günde 1 kez GCS cleanup
            today = datetime.now(TURKEY_TZ).date()
            cleanup_result = None
            if LAST_CLEANUP_DATE != today:
                cleanup_result = tracking.cleanup_old_setups()
                LAST_CLEANUP_DATE = today
                if cleanup_result.get('deleted', 0) > 0:
                    logger.info(f"🧹 GCS Cleanup: {cleanup_result['deleted']} eski kayıt silindi")
            
            vol_cleaned = cleanup_expired_volumes()
            if vol_cleaned > 0:
                logger.info(f"🧹 Volume store temizlendi: {vol_cleaned} expired entry")
            
            now_ts = int(datetime.now().timestamp())
            expired_keys = [k for k, v in MARKET_CACHE.items() 
                          if (now_ts - v.get('ts', 0)) > Config.MARKET_CACHE_TTL]
            for k in expired_keys:
                del MARKET_CACHE[k]
            
            if expired_keys:
                logger.info(f"🧹 Market cache temizlendi: {len(expired_keys)} eski entry")
            
            current_balance = 500.0
            total_balance = 500.0
            try:
                bal_result = bitget.get_balance()
                if bal_result.get('success'):
                    current_balance = float(bal_result.get('free', 500.0))
                    total_balance = float(bal_result.get('total', 500.0))
                    logger.info(f"💰 Balance: Total=${total_balance:.2f} | Available=${current_balance:.2f}")
            except Exception as e:
                logger.warning(f"Balance fetch failed: {e}")
            
            pairs = Config.AUTO_SCAN_PAIRS
            total_setups = 0
            orders_placed = 0
            grok_skips = 0
            limit_skips = 0  # v2.7.1: Position limit nedeniyle atlanlar
            cache_hits = 0
            cache_misses = 0
            
            for pair in pairs:
                try:
                    market_data = bitget.get_complete_analysis_data(pair, market_cache=MARKET_CACHE)
                    if not market_data:
                        continue
                    
                    volume_data = market_data.get('volume', {})
                    for tf, vol_info in volume_data.items():
                        if vol_info.get('source') == 'tradingview_binance':
                            cache_hits += 1
                        else:
                            cache_misses += 1
                    
                    setups = detect_all_trading_setups(pair, market_data)
                    
                    if not setups:
                        continue
                    
                    for setup in setups:
                        setup['pair'] = pair
                        
                        if not is_trading_enabled():
                            logger.info(f"⏸️ Trading kapalı, atlanıyor: {pair}")
                            continue
                        
                        setup_strength = setup.get('ob_strength') or setup.get('fvg_strength', 'medium')
                        python_score = calculate_setup_strength(
                            volume_spike_ratio=setup.get('volume_spike_ratio', 0),
                            ob_or_fvg_strength=setup_strength,
                            rr_ratio=setup.get('rr_ratio', 0)
                        )
                        
                        direction = setup.get('direction', 'LONG')
                        timeframe = setup.get('timeframe', 'N/A')
                        
                        # v2.7.0: Pattern bilgisini logla
                        pattern_data = setup.get('pattern_data', {})
                        pattern_name = pattern_data.get('pattern_name', 'None')
                        pattern_conf = pattern_data.get('confidence', 0)
                        
                        if pattern_name and pattern_name != 'None':
                            logger.info(f"🧠 Grok değerlendiriyor: {pair} {direction} [{timeframe}] [PAT:{pattern_name}]")
                        else:
                            logger.info(f"🧠 Grok değerlendiriyor: {pair} {direction} [{timeframe}]")
                        
                        decision = grok.evaluate_setup(
                            setup_data=setup,
                            market_data=market_data,
                            python_score=python_score
                        )
                        
                        action = decision.get('action', 'SKIP')
                        confidence = decision.get('confidence', 0)
                        reasoning = decision.get('reasoning', 'N/A')
                        
                        if action == 'SKIP':
                            grok_skips += 1
                            logger.info(f"⏭️ Grok SKIP: {pair} [{timeframe}] - {reasoning}")
                            continue
                        
                        if action == 'WAIT':
                            logger.info(f"⏸️ Grok WAIT: {pair} [{timeframe}] - {reasoning}")
                            continue
                        
                        if action == 'ENTER':
                            logger.info(f"✅ Grok ENTER: {pair} [{timeframe}] ({confidence}%) - {reasoning}")
                            
                            coin_name = pair.replace('/USDT:USDT', '')
                            dup_check = tracking.check_duplicate_setup(
                                coin=coin_name,
                                direction=direction,
                                entry_price=setup.get('entry_price'),
                                tp_price=setup.get('tp_price'),
                                sl_price=setup.get('stop_price')
                            )
                            
                            if dup_check['status'] == 'DUPLICATE':
                                logger.info(f"⚠️ DUPLICATE: {coin_name} {direction} [{timeframe}] - Skipping")
                                continue
                            
                            is_replace = False
                            old_order_id_cancelled = None
                            replace_reason = None
                            
                            if dup_check['status'] == 'REPLACE':
                                is_replace = True
                                existing = dup_check.get('existing_setup', {})
                                old_order_id_cancelled = existing.get('order_id')
                                old_setup_id = existing.get('setup_id')
                                replace_reason = dup_check.get('reason', '')
                                
                                logger.info(f"🔄 REPLACE: {coin_name} {direction} - {replace_reason}")
                                
                                if old_order_id_cancelled:
                                    cancel_result = bitget.cancel_order(old_order_id_cancelled, pair)
                                    if cancel_result.get('success'):
                                        logger.info(f"🗑️ Eski order cancelled: {old_order_id_cancelled}")
                                        if old_setup_id:
                                            tracking.mark_setup_expired(old_setup_id)
                                    else:
                                        logger.warning(f"⚠️ Cancel failed: {old_order_id_cancelled} - {cancel_result.get('error')}")
                            
                            adjustments = decision.get('adjustments', {})
                            stop_price = adjustments.get('stop_price', setup.get('stop_price'))
                            tp_price = adjustments.get('tp_price', setup.get('tp_price'))
                            
                            # ============================================
                            # v2.7.1: POSITION STACKING LIMIT KONTROLÜ
                            # ============================================
                            entry_price = setup.get('entry_price', 0)
                            
                            # Pozisyon değerini hesapla (calculate_position_size fonksiyonu notional döner)
                            notional_usd = bitget.calculate_position_size(entry_price, stop_price)
                            
                            # Coin+direction bazlı limit kontrolü
                            limit_check = bitget.check_position_limit(
                                symbol=pair,
                                direction=direction,
                                new_position_value=notional_usd
                            )
                            
                            if not limit_check.get('allowed'):
                                limit_skips += 1
                                reason = limit_check.get('reason', 'Position limit exceeded')
                                current_val = limit_check.get('current_value', 0)
                                new_total = limit_check.get('new_total', 0)
                                limit_val = limit_check.get('limit', 0)
                                pos_count = limit_check.get('position_count', 0)
                                
                                logger.warning(f"🚫 LIMIT: {coin_name} {direction} - {reason}")
                                
                                # Telegram'a bildir
                                telegram.send(
                                    f"🚫 *POZİSYON LİMİTİ*\n\n"
                                    f"📊 *{coin_name}* | {direction}\n"
                                    f"⏱️ {timeframe}\n\n"
                                    f"📦 Mevcut: ${current_val:.2f} ({pos_count} poz)\n"
                                    f"➕ Yeni: ${notional_usd:.2f}\n"
                                    f"📊 Toplam: ${new_total:.2f}\n"
                                    f"🚧 Limit: ${limit_val:.2f}\n\n"
                                    f"❌ *Bu trade atlandı*",
                                    chat_id=Config.TELEGRAM_CHAT_ID
                                )
                                continue
                            # ============================================
                            
                            exec_result = bitget.execute_trade_for_setup(
                                setup_data={
                                    'pair': pair,
                                    'direction': direction,
                                    'entry_price': entry_price,
                                    'stop_price': stop_price,
                                    'tp_price': tp_price
                                },
                                ai_decision=decision
                            )
                            
                            if exec_result.get('success'):
                                orders_placed += 1
                                
                                setup_data = {
                                    'pair': pair.replace('/USDT:USDT', 'USDT'),
                                    'setup_type': setup.get('type', 'UNKNOWN'),
                                    'confidence': setup.get('confidence', 'MEDIUM'),
                                    'timeframe': timeframe,
                                    'direction': direction,
                                    'timestamp': setup.get('timestamp'),
                                    'current_price': market_data.get('current_price', 0),
                                    'entry_price': setup.get('entry_price', 0),
                                    'entry_zone': setup.get('entry_zone', 'N/A'),
                                    'stop_loss': format_price(stop_price),
                                    'stop_price': stop_price,
                                    'tp': format_price(tp_price),
                                    'tp_price': tp_price,
                                    'rr_ratio': setup.get('rr_ratio', 0),
                                    'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                    'ob_strength': setup.get('ob_strength', 'medium'),
                                    'balance_before': total_balance,
                                    'risk_percent': Config.RISK_PER_TRADE,
                                    'order_id': exec_result.get('order_id'),
                                    'tracking_no': exec_result.get('tracking_no'),
                                    'contracts': exec_result.get('contracts', 0),
                                    'position_usd': exec_result.get('position_usd', 0),
                                    'status': 'FILLED',
                                    'ai_action': action,
                                    'ai_confidence': confidence,
                                    'ai_reasoning': reasoning,
                                    'python_score': python_score,
                                    'stop_adjusted': adjustments.get('adjusted', False),
                                    'adjustment_type': adjustments.get('type'),
                                    'pattern_name': pattern_name,
                                    'pattern_confidence': pattern_conf,
                                }
                                
                                setup_id = tracking.log_setup(setup_data)
                                
                                if setup_id:
                                    total_setups += 1
                                    
                                    dir_emoji = "🟢" if direction == "LONG" else "🔴"
                                    
                                    # v2.7.0: Pattern bilgisi notification'a eklendi
                                    pattern_info = ""
                                    if pattern_name and pattern_name != 'None' and pattern_conf > 0:
                                        pattern_info = f"\n🕯️ Pattern: {pattern_name} ({int(pattern_conf*100)}%)"
                                    
                                    adj_info = ""
                                    if adjustments.get('adjusted'):
                                        adj_info = f"\n⚙️ Stop Adj: {adjustments.get('type', 'N/A')}"
                                    
                                    if is_replace:
                                        header = "🔄 *EMİR GÜNCELLENDİ*"
                                        replace_info = f"\n🗑️ Eski: `{old_order_id_cancelled}`\n📝 {replace_reason}"
                                    else:
                                        header = f"{dir_emoji} *YENİ EMİR AÇILDI*"
                                        replace_info = ""
                                    
                                    notify_msg = f"""
━━━━━━━━━━━
{header}
━━━━━━━━━━━
{replace_info}
📊 *{coin_name}* | {direction} | {timeframe}
💵 Entry: {format_price(setup.get('entry_price', 0))}
🛑 SL: {format_price(exec_result.get('stop_price', 0))}
✅ TP: {format_price(exec_result.get('tp_price', 0))}{adj_info}{pattern_info}

📦 Kontrat: {exec_result.get('contracts', 'N/A')}
💰 Pozisyon: ${exec_result.get('position_usd', 0):.2f}
🔢 Order: `{exec_result.get('order_id', 'N/A')}`

🧠 *Grok AI*
• Karar: {action} ({confidence}%)
• Python: {python_score*100:.0f}/100

━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%H:%M:%S')} TR
"""
                                    telegram.send(notify_msg, chat_id=Config.TELEGRAM_CHAT_ID)
                            else:
                                error = exec_result.get('error', 'Unknown')
                                logger.error(f"❌ Execute failed: {pair} [{timeframe}] - {error}")
                                telegram.send(f"❌ *EMİR HATASI*\n\n{pair} [{timeframe}]\nHata: {error}", chat_id=Config.TELEGRAM_CHAT_ID)
                            
                except Exception as e:
                    logger.error(f"Pair analyze error ({pair}): {e}")
            
            vol_stats = get_volume_store_stats()
            logger.info(f"✅ Auto analyze: {orders_placed} orders, {grok_skips} grok_skips, {limit_skips} limit_skips | Cache: {cache_hits} hits, {cache_misses} misses")
            gc.collect()
            
            response = {
                "status": "success",
                "orders": orders_placed,
                "grok_skips": grok_skips,
                "limit_skips": limit_skips,  # v2.7.1
                "setups_logged": total_setups,
                "volume_cache_hits": cache_hits,
                "volume_cache_misses": cache_misses,
                "volume_store_size": vol_stats.get('total', 0)
            }
            
            if cleanup_result:
                response['gcs_cleanup'] = cleanup_result
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"❌ Auto analyze CRASH: {e}")
            return jsonify({"error": str(e)}), 500


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS v{Config.VERSION}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, threaded=True)
