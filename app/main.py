# -*- coding: utf-8 -*-
"""
T-TARS Trading Bot v2.3.10
==========================
Main Flask application with routes.

v2.3.10:
- FIX: python_score hesaplaması düzeltildi
- CHANGED: setup_strength hem ob_strength hem fvg_strength'den okunuyor

v2.3.8:
- FIX: MARKET_CACHE_TTL 300→1200 (20 dakika) - HTF verisi expire olmuyordu
- DRY: Tüm threshold'lar calculators.py'den yönetiliyor

v2.3.7:
- NEW: volume_analyzer entegrasyonu (store_volume, get_volume)
- CHANGED: Webhook hem MARKET_CACHE hem volume_analyzer'a yazar
- ADD: cleanup_expired_volumes() çağrısı auto_analyze'da
- ADD: Bar kapanışı timing kontrolü (5m bar + 1dk sonra çalış)
- Detector'lar artık volume_analyzer'dan okuyabilir

v2.3.6:
- FIX: spike=0 artık kabul ediliyor (POST 400 hatası düzeltildi)
- FIX: 'spike' field yoksa reddet, 0 değeri kabul et
- Düşük volume = 0 demek, bu da geçerli bir değer!

v2.3.4:
- NEW: TradingView ATR Webhook entegrasyonu
- CHANGED: VOLUME_CACHE → MARKET_CACHE (volume + ATR birlikte)
- CHANGED: /webhook/volume → hem spike hem atr alır
- NEW: ATR de cache'den okunuyor (TradingView Binance)
- Fallback: Cache yoksa Bitget'ten hesaplama devam eder

v2.3.3:
- TradingView Volume Webhook entegrasyonu
- /webhook/volume endpoint - Binance volume spike alır

v2.3.0:
- Claude AI karar mekanizması (evaluate_setup)
"""

from flask import Flask, request, jsonify
from app.services.claude_service import ClaudeService
from app.services.telegram_service import TelegramService
from app.services.storage_service import StorageService
from app.services.bitget_service import BitgetService
from app.services.tracking_service import TrackingService
from app.config import Config
from app.strategies.setup_detector import detect_all_trading_setups
from app.strategies.calculators import calculate_setup_strength
# v2.3.7: Volume analyzer entegrasyonu
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

# ============================================
# v2.3.8: MARKET CACHE (TradingView'dan Volume + ATR)
# HTF (15m, 30m, 1h) verileri 15 dakikada bir geliyor
# TTL Config.MARKET_CACHE_TTL'den okunuyor (default 20 dakika)
# ============================================
# Format: {
#   "BTCUSDT_15m": {"spike": 2.34, "atr": 125.5, "ts": 1702...},
#   "ETHUSDT_1h": {"spike": 1.87, "atr": 45.2, "ts": 1702...}
# }
MARKET_CACHE = {}
# v2.3.8: TTL artık Config'den (hardcoded değil)

# Turkey timezone
TURKEY_TZ = timezone(timedelta(hours=3))

# Order expiry (4 saat)
ORDER_EXPIRY_HOURS = 4


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
    # v2.3.7: Volume store stats ekle
    vol_stats = get_volume_store_stats()
    return jsonify({
        "service": f"T-TARS Trading Bot v{Config.VERSION}",
        "version": Config.VERSION,
        "status": "running",
        "exchange": "Bitget",
        "ai_engine": "Claude Haiku 4.5",
        "market_source": "TradingView (Binance) - Volume + ATR",
        "lock_status": "locked" if SCAN_LOCK.locked() else "free",
        "market_cache_size": len(MARKET_CACHE),
        "market_cache_ttl": Config.MARKET_CACHE_TTL,
        "volume_store_size": vol_stats.get('total', 0)
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
# ROUTES - TRADINGVIEW MARKET WEBHOOK (v2.3.7)
# ============================================

@app.route('/webhook/volume', methods=['POST'])
def volume_webhook():
    """
    v2.3.7: TradingView Market Data Webhook (Volume + ATR)
    
    TradingView Pine Script'ten gelen volume spike ve ATR verisini cache'le.
    Binance USDT-M Futures chartlarından alınıyor.
    
    v2.3.7: Hem MARKET_CACHE hem volume_analyzer'a yazılıyor
    v2.3.6 FIX: spike=0 artık kabul ediliyor!
    
    Expected payload:
    {
        "pair": "BTCUSDT",      # veya "BTC" veya "BTCUSDT.P"
        "tf": "15",             # veya "15m", "1h", "4h"
        "spike": 2.34,          # volume spike ratio (0 da kabul!)
        "atr": 125.5,           # ATR değeri (opsiyonel)
        "price": 104500.50      # opsiyonel - current price
    }
    
    Cache key format: "BTCUSDT_15m"
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        # Pair normalize et
        pair = data.get('pair', '').upper()
        if not pair:
            return jsonify({"status": "error", "message": "Missing pair"}), 400
        
        # Pair temizle: "BTCUSDT.P" → "BTCUSDT", "BTC" → "BTCUSDT"
        pair = pair.replace('.P', '').replace('PERP', '')
        if not pair.endswith('USDT'):
            pair = pair + 'USDT'
        
        # Timeframe normalize et
        tf_raw = str(data.get('tf', '15'))
        tf_map = {
            '1': '1m', '3': '3m', '5': '5m', '15': '15m', '30': '30m',
            '60': '1h', '240': '4h', '1D': '1d', 'D': '1d',
            '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d'
        }
        tf = tf_map.get(tf_raw, '15m')
        
        # v2.3.6 FIX: spike field kontrolü - 0 DA KABUL!
        if 'spike' not in data:
            return jsonify({"status": "error", "message": "Missing spike field"}), 400
        
        spike = float(data.get('spike', 0))
        
        # v2.3.4: ATR değeri (opsiyonel)
        atr = float(data.get('atr', 0)) if data.get('atr') else 0
        
        # Cache key oluştur
        cache_key = f"{pair}_{tf}"
        
        # v2.3.7: Volume analyzer'a yaz (YENİ!)
        store_volume(pair, tf, spike, atr)
        
        # MARKET_CACHE'e de yaz (backward compatibility)
        MARKET_CACHE[cache_key] = {
            'spike': round(spike, 2),
            'atr': round(atr, 6) if atr > 0 else 0,
            'ts': int(datetime.now().timestamp()),
            'price': float(data.get('price', 0)),
            'source': 'tradingview_binance'
        }
        
        # Log mesajı - ATR için dinamik format (küçük değerler için 6 decimal)
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
        # v2.3.4: ATR varsa ekle
        if val.get('atr', 0) > 0:
            entry['atr'] = val.get('atr')
        cache_info.append(entry)
    
    # v2.3.7: Volume store stats
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
        
        # Command routing
        if command == '/plan':
            handle_plan_command(text, chat_id)
        elif command == '/execute':
            handle_execute_command(text, chat_id)
        elif command == '/log':
            handle_log_command(text, chat_id)
        elif command == '/status':
            handle_status_command(chat_id)
        elif command == '/scan':
            if SCAN_LOCK.locked():
                telegram.send("⚠️ Otomatik tarama sürüyor, performans düşebilir.", chat_id=chat_id)
            handle_scan_command(chat_id)
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
            # Legacy OKX commands → Bitget
            if 'stop' in command:
                handle_stopbitget_command(chat_id)
            else:
                handle_startbitget_command(chat_id)
        elif command == '/volume':
            # v2.3.7: Volume store + market cache status
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
                f"*Volume Store (v2.3.7)*\n"
                f"Toplam: {vol_stats.get('total', 0)}\n"
                f"Pair'ler: {', '.join(vol_stats.get('pairs', []))}", 
                chat_id=chat_id
            )
        else:
            telegram.send("❌ Bilinmeyen komut.", chat_id=chat_id)
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ROUTES - MONITORING
# ============================================

@app.route('/monitor', methods=['POST', 'GET'])
def monitor_setups():
    """
    v2.3.0: Bitget Bazlı Monitor + Order Expiry
    
    1. Bekleyen limit emirleri kontrol et
    2. 4 saat geçen PENDING emirleri iptal et
    3. Emir dolmuşsa → trackingNo al, status güncelle
    4. Copy Trade pozisyonlarını kontrol et
    """
    try:
        if not is_trading_enabled():
            return jsonify({"status": "skipped", "reason": "trading_disabled"}), 200
        
        updates = 0
        expired_count = 0
        now = datetime.now(TURKEY_TZ)
        
        # ADIM 1: Bekleyen emirleri kontrol et
        pending_setups = tracking.get_pending_setups()
        
        for setup in pending_setups:
            try:
                setup_id = setup.get('setup_id')
                order_id = setup.get('order_id')
                tracking_no = setup.get('tracking_no')
                pair = setup.get('pair')
                direction = setup.get('direction', 'long')
                status = setup.get('status')
                created_at_str = setup.get('created_at')
                
                # 4 saat expiry kontrolü
                if status == 'PENDING' and order_id and created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        age_hours = (now - created_at).total_seconds() / 3600
                        
                        if age_hours >= ORDER_EXPIRY_HOURS:
                            logger.info(f"⏰ Order expired ({age_hours:.1f}h): {setup_id}")
                            
                            symbol = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}" if '/' not in pair else pair
                            bitget.cancel_order(order_id, symbol)
                            tracking.mark_setup_expired(setup_id)
                            expired_count += 1
                            continue
                            
                    except Exception as e:
                        logger.error(f"Expiry check error ({setup_id}): {e}")
                
                # trackingNo kontrolü
                if not tracking_no and order_id and status == 'PENDING':
                    symbol = f"{pair[:-4]}/{pair[-4:]}:{pair[-4:]}" if '/' not in pair else pair
                    found_tracking_no = bitget.find_tracking_no_by_symbol(symbol, direction)
                    
                    if found_tracking_no:
                        logger.info(f"✅ Emir doldu: {setup_id} → trackingNo: {found_tracking_no}")
                        tracking.mark_setup_filled(setup_id, found_tracking_no)
                        updates += 1
                        
            except Exception as e:
                logger.error(f"Pending setup error ({setup.get('setup_id')}): {e}")
        
        # ADIM 2: Copy Trade pozisyonlarını kontrol et
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
                        logger.info(f"🔴 Pozisyon kapanmış: {setup_id}")
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
# ROUTES - AUTO ANALYZE (v2.3.8 - Volume Analyzer)
# ============================================

@app.route('/analyze', methods=['POST', 'GET'])
def auto_analyze():
    """
    v2.3.8: Otomatik Tarama + Volume Analyzer + Claude AI
    
    Akış:
    1. Market verisi topla (volume_analyzer ile)
    2. Setup'ları tespit et (Python)
    3. Setup puanı hesapla (calculators.py)
    4. Claude AI değerlendir → ENTER / SKIP / WAIT
    5. Sadece ENTER kararı varsa emir aç
    6. Telegram bildirimi gönder
    
    v2.3.8:
    - MARKET_CACHE_TTL 300→1200 (HTF verisi expire olmuyordu)
    v2.3.7: 
    - Volume analyzer entegrasyonu
    - Bar kapanışı timing kontrolü (5m bar kapandıktan 1 dk sonra)
    v2.3.3: TradingView'dan gelen volume spike kullanılıyor
    v2.3.1 FIX: setup['pair'] = pair eklendi!
    """
    # v2.3.7: Bar kapanışı timing kontrolü
    # 5m bar xx:00, xx:05, xx:10... kapanır → webhook gelir
    # xx:01, xx:06, xx:11... çalış → fresh data!
    # Cloud Scheduler her MONITOR_INTERVAL_MINUTES çağırır
    interval = Config.MONITOR_INTERVAL_MINUTES
    current_minute = datetime.now().minute
    if current_minute % interval != 1:
        logger.debug(f"⏳ Analyze skipped: minute={current_minute}, interval={interval}, waiting for bar close +1")
        return jsonify({
            "status": "skipped", 
            "reason": "waiting_for_bar_close",
            "current_minute": current_minute,
            "interval": interval,
            "next_run": f"xx:{((current_minute // interval) + 1) * interval + 1:02d}"
        }), 200
    
    if SCAN_LOCK.locked():
        logger.warning("⚠️ Auto analyze SKIPPED: Lock active")
        return jsonify({"status": "skipped", "reason": "locked"}), 200

    with SCAN_LOCK:
        try:
            logger.info(f"🔄 Auto analyze started (v{Config.VERSION} - TradingView Volume + ATR)")
            
            # v2.3.7: Volume analyzer temizliği
            vol_cleaned = cleanup_expired_volumes()
            if vol_cleaned > 0:
                logger.info(f"🧹 Volume store temizlendi: {vol_cleaned} expired entry")
            
            # v2.3.8: Eski cache entry'lerini temizle (MARKET_CACHE - 20dk TTL)
            now_ts = int(datetime.now().timestamp())
            expired_keys = [k for k, v in MARKET_CACHE.items() 
                          if (now_ts - v.get('ts', 0)) > Config.MARKET_CACHE_TTL]
            for k in expired_keys:
                del MARKET_CACHE[k]
            
            if expired_keys:
                logger.info(f"🧹 Market cache temizlendi: {len(expired_keys)} eski entry (TTL={Config.MARKET_CACHE_TTL}s)")
            
            # Balance çek
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
            claude_skips = 0
            
            # v2.3.4: Market cache log (Volume + ATR)
            cache_hits = 0
            cache_misses = 0
            
            for pair in pairs:
                try:
                    # 1. Market verisi topla (v2.3.4: market_cache parametresi - Volume + ATR)
                    market_data = bitget.get_complete_analysis_data(pair, market_cache=MARKET_CACHE)
                    if not market_data:
                        continue
                    
                    # v2.3.3: Cache hit/miss say
                    volume_data = market_data.get('volume', {})
                    for tf, vol_info in volume_data.items():
                        if vol_info.get('source') == 'tradingview_binance':
                            cache_hits += 1
                        else:
                            cache_misses += 1
                    
                    # 2. Setup'ları tespit et
                    setups = detect_all_trading_setups(pair, market_data)
                    
                    if not setups:
                        continue
                    
                    for setup in setups:
                        # v2.3.1 FIX: pair'i setup'a ekle!
                        setup['pair'] = pair
                        
                        # Trading kontrolü
                        if not is_trading_enabled():
                            logger.info(f"⏸️ Trading kapalı, atlanıyor: {pair}")
                            continue
                        
                        # 3. Python puanı hesapla
                        # v2.3.10: OB için ob_strength, FVG için fvg_strength
                        setup_strength = setup.get('ob_strength') or setup.get('fvg_strength', 'medium')
                        python_score = calculate_setup_strength(
                            volume_spike_ratio=setup.get('volume_spike_ratio', 0),
                            ob_or_fvg_strength=setup_strength,
                            rr_ratio=setup.get('rr_ratio', 0),
                            confidence=setup.get('confidence', 'MEDIUM')
                        )
                        
                        # 4. Claude AI değerlendir
                        direction = setup.get('direction', 'LONG')
                        timeframe = setup.get('timeframe', 'N/A')
                        logger.info(f"🧠 Claude değerlendiriyor: {pair} {direction} [{timeframe}]")
                        
                        decision = claude.evaluate_setup(
                            setup_data=setup,
                            market_data=market_data,
                            python_score=python_score
                        )
                        
                        # 5. Karar: ENTER / SKIP / WAIT
                        action = decision.get('action', 'SKIP')
                        confidence = decision.get('confidence', 0)
                        reasoning = decision.get('reasoning', 'N/A')
                        
                        if action == 'SKIP':
                            claude_skips += 1
                            logger.info(f"⏭️ Claude SKIP: {pair} [{timeframe}] - {reasoning}")
                            continue
                        
                        if action == 'WAIT':
                            logger.info(f"⏸️ Claude WAIT: {pair} [{timeframe}] - {reasoning}")
                            continue
                        
                        # ENTER - Emir aç
                        if action == 'ENTER':
                            logger.info(f"✅ Claude ENTER: {pair} [{timeframe}] ({confidence}%) - {reasoning}")
                            
                            # v2.3.2: Adjusted değerler varsa kullan
                            adjustments = decision.get('adjustments', {})
                            stop_price = adjustments.get('stop_price', setup.get('stop_price'))
                            tp1_price = adjustments.get('tp1_price', setup.get('tp1_price'))
                            
                            # 6. Emir aç
                            exec_result = bitget.execute_trade_for_setup(
                                setup_data={
                                    'pair': pair,
                                    'direction': direction,
                                    'entry_price': setup.get('entry_price'),
                                    'stop_price': stop_price,
                                    'tp1_price': tp1_price
                                },
                                claude_decision=decision
                            )
                            
                            if exec_result.get('success'):
                                orders_placed += 1
                                
                                # Tracking'e kaydet
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
                                    'tp1': format_price(tp1_price),
                                    'tp1_price': tp1_price,
                                    'tp2_price': setup.get('tp2_price', 0),
                                    'rr_ratio': setup.get('rr_ratio', 0),
                                    'volume_spike_ratio': setup.get('volume_spike_ratio', 0),
                                    'ob_strength': setup.get('ob_strength', 'medium'),
                                    'balance_before': total_balance,
                                    'risk_percent': Config.RISK_PER_TRADE,
                                    'order_id': exec_result.get('order_id'),
                                    'tracking_no': exec_result.get('tracking_no'),
                                    'contracts': exec_result.get('contracts', 0),
                                    'position_usd': exec_result.get('position_usd', 0),
                                    # Claude AI bilgileri
                                    'claude_action': action,
                                    'claude_confidence': confidence,
                                    'claude_reasoning': reasoning,
                                    'python_score': python_score,
                                    # v2.3.2: Adjustment bilgisi
                                    'stop_adjusted': adjustments.get('adjusted', False),
                                    'adjustment_type': adjustments.get('type'),
                                }
                                
                                setup_id = tracking.log_setup(setup_data)
                                
                                if setup_id:
                                    total_setups += 1
                                    
                                    # Telegram bildirimi
                                    coin_name = pair.replace('/USDT:USDT', '')
                                    dir_emoji = "🟢" if direction == "LONG" else "🔴"
                                    
                                    # v2.3.2: Adjustment bilgisi göster
                                    adj_info = ""
                                    if adjustments.get('adjusted'):
                                        adj_info = f"\n⚙️ Stop Adj: {adjustments.get('type', 'N/A')}"
                                    
                                    notify_msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
{dir_emoji} *YENİ EMİR AÇILDI*
━━━━━━━━━━━━━━━━━━━━━━

📊 *{coin_name}* | {direction} | {timeframe}
💵 Entry: {format_price(setup.get('entry_price', 0))}
🛑 SL: {format_price(exec_result.get('stop_price', 0))}
✅ TP: {format_price(exec_result.get('tp_price', 0))}{adj_info}

📦 Kontrat: {exec_result.get('contracts', 'N/A')}
💰 Pozisyon: ${exec_result.get('position_usd', 0):.2f}

🧠 *Claude AI*
• Karar: {action} ({confidence}%)
• Sebep: {reasoning[:50]}...
• Python Score: {python_score*100:.0f}/100

━━━━━━━━━━━━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%H:%M:%S')} TR
━━━━━━━━━━━━━━━━━━━━━━
"""
                                    telegram.send(notify_msg, chat_id=Config.TELEGRAM_CHAT_ID)
                            else:
                                # Hata bildirimi
                                error = exec_result.get('error', 'Unknown')
                                logger.error(f"❌ Execute failed: {pair} [{timeframe}] - {error}")
                                telegram.send(f"❌ *EMİR HATASI*\n\n{pair} [{timeframe}]\nHata: {error}", chat_id=Config.TELEGRAM_CHAT_ID)
                            
                except Exception as e:
                    logger.error(f"Pair analyze error ({pair}): {e}")
            
            # v2.3.7: Volume store stats
            vol_stats = get_volume_store_stats()
            logger.info(f"✅ Auto analyze: {orders_placed} orders, {claude_skips} skipped | Cache: {cache_hits} hits, {cache_misses} misses | Store: {vol_stats.get('total', 0)} entries")
            gc.collect()
            
            return jsonify({
                "status": "success",
                "orders": orders_placed,
                "claude_skips": claude_skips,
                "setups_logged": total_setups,
                "volume_cache_hits": cache_hits,
                "volume_cache_misses": cache_misses,
                "volume_store_size": vol_stats.get('total', 0)
            })
            
        except Exception as e:
            logger.error(f"❌ Auto analyze CRASH: {e}")
            return jsonify({"error": str(e)}), 500


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    logger.info(f"🚀 Starting T-TARS v{Config.VERSION} (TradingView Volume + Claude AI)")
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, threaded=True)
