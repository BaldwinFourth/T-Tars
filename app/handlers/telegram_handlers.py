# -*- coding: utf-8 -*-
"""
T-TARS Telegram Handlers v2.1.1
================================
Telegram bot komut handler'ları.

v2.1.1:
- NEW: /score detaylı rapor formatı (Top/Worst 5 coin & TF)
- NEW: OKX balance ile gerçek P/L hesaplama
- FIX: execute_trade_for_setup() parametre hatası düzeltildi (amount → amount_usd)
"""

import logging
import json
import threading
from datetime import datetime, timezone, timedelta
from app.config import Config
from app.strategies.setup_detector import detect_all_trading_setups

logger = logging.getLogger(__name__)
TURKEY_TZ = timezone(timedelta(hours=3))

def get_turkey_time():
    return datetime.now(TURKEY_TZ)

def format_price(price):
    if price is None or price == 0: return "$0.00"
    try:
        abs_price = abs(float(price))
        if abs_price < 0.0001: return f"${price:.8f}"
        elif abs_price < 0.01: return f"${price:.6f}"
        elif abs_price < 1: return f"${price:.4f}"
        elif abs_price < 100: return f"${price:.4f}"
        else: return f"${price:,.2f}"
    except: return "$0.00"

# --------------------------
# GLOBAL DEĞİŞKENLER
# --------------------------
_telegram = None
_okx = None
_claude = None
_storage = None
_tracking = None
_trading_enabled = True 

def init_handlers(telegram, okx, claude, storage, tracking):
    global _telegram, _okx, _claude, _storage, _tracking, _trading_enabled
    _telegram = telegram
    _okx = okx
    _claude = claude
    _storage = storage
    _tracking = tracking
    _trading_enabled = getattr(Config, 'OKX_TRADING_ENABLED', True)
    logger.info(f"✅ Telegram handlers initialized (v2.1.1) - Trading: {_trading_enabled}")

# --------------------------
# BEST TF SEÇİCİ
# --------------------------
def select_best_timeframe_for_plan(setups):
    if not setups:
        return None
    
    tf_scores = {'1G': 6, '4S': 5, '1S': 4, '15D': 3, '10D': 2.5, '5D': 2, '3D': 1}
    
    best_setup = None
    max_score = -1
    
    for setup in setups:
        tf = setup.get('timeframe', '5D')
        tf_score = tf_scores.get(tf, 0)
        conf = setup.get('confidence', 'LOW')
        conf_score = 2 if conf == 'HIGH' else 1
        rr = setup.get('rr_ratio', 0)
        total_score = (tf_score * 1.5) + (conf_score * 2) + rr
        
        if total_score > max_score:
            max_score = total_score
            best_setup = setup
            
    return best_setup

# --------------------------
# AI & ANALİZ KOMUTLARI
# --------------------------

def handle_plan_command(text, chat_id):
    """/plan [parite] - Akıllı Plan"""
    def run_plan():
        try:
            parts = text.split()
            user_input = parts[1] if len(parts) > 1 else "BTCUSDT"
            ticker = Config.get_pair_symbol(user_input)
            
            _telegram.send(f"🔄 **{ticker.replace('/', '').replace(':USDT', '')} taranıyor...**\n⏳ En iyi setup aranıyor...", chat_id=chat_id)
            
            market_data = _okx.get_complete_analysis_data(ticker)
            if not market_data:
                _telegram.send("❌ Market verisi alınamadı.", chat_id=chat_id)
                return

            all_setups = detect_all_trading_setups(ticker, market_data)
            best_setup = select_best_timeframe_for_plan(all_setups)
            
            pdc = market_data.get('previous_day', {})
            bias_emoji = "🟢" if pdc.get('candle_type') == 'green' else "🔴"
            
            if best_setup:
                tf = best_setup['timeframe']
                direction = best_setup['direction']
                conf = best_setup['confidence']
                entry = best_setup['entry_zone']
                stop = best_setup['stop_loss']
                tp1 = best_setup['tp1']
                tp2 = best_setup['tp2']
                rr = best_setup.get('rr_ratio', 0)
                
                atr = market_data['atr'].get(tf, 0)
                vol = market_data['volume'].get(tf, {'spike_ratio': 0})
                
                plan_msg = f"""
🎯 **T-TARS AKILLI PLAN**
**{ticker.replace('/', '').replace(':USDT', '')}** | **{tf}** | {bias_emoji}

✅ **EN İYİ FIRSAT: {direction} ({conf})**
• **Giriş:** {entry}
• **Stop:** {stop}
• **TP1:** {tp1} | **TP2:** {tp2}
• **R:R:** {rr:.2f}

📊 **Teknik Detaylar:**
• Setup: {best_setup['type']}
• Hacim: {vol.get('spike_ratio')}x
• ATR({tf}): ${atr:.2f}
"""
            else:
                current_price = market_data.get('current_price', 0)
                fibo = market_data.get('fibonacci', {}).get('levels', {})
                
                plan_msg = f"""
ℹ️ **T-TARS GENEL BAKIŞ**
**{ticker.replace('/', '').replace(':USDT', '')}** | Şu an net bir setup yok.

📊 **Market Durumu:**
• Fiyat: ${current_price:,.2f}
• Günlük Yön: {bias_emoji}

🎯 **Kritik Seviyeler (Fibo):**
• Destek (61.8%): ${fibo.get('61.8', 0):,.2f}
• Pivot (50%): ${fibo.get('50.0', 0):,.2f}
• Direnç (38.2%): ${fibo.get('38.2', 0):,.2f}
"""

            _telegram.send(plan_msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Smart Plan Error: {e}", exc_info=True)
            _telegram.send(f"❌ Plan Hatası: {str(e)}", chat_id=chat_id)

    threading.Thread(target=run_plan).start()

def handle_execute_command(text, chat_id):
    def run_execute():
        try:
            parts = text.split()
            ticker = parts[1] if len(parts) > 1 else "BTCUSDT"
            template = _storage.get_execute_template()
            prompt = f"Sen T-TARS. {ticker} için Execute şablonunu doldur.\n{template}"
            result = _claude.analyze(prompt)
            message = f"⚡ *T-TARS EXECUTE - {ticker}*\n\n{result['text']}"
            _telegram.send(message[:4000], chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Execute Hatası: {e}", chat_id=chat_id)

    _telegram.send("⚡ **Durum Kontrol Ediliyor...**", chat_id=chat_id)
    threading.Thread(target=run_execute).start()

def handle_log_command(text, chat_id):
    def run_log():
        try:
            template = _storage.get_log_template()
            prompt = f"Sen T-TARS. Trade Log şablonunu doldur.\n{template}"
            result = _claude.analyze(prompt)
            message = f"📋 *T-TARS TRADE LOG*\n\n{result['text']}"
            _telegram.send(message[:4000], chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Log Hatası: {e}", chat_id=chat_id)

    _telegram.send("📋 **Log Hazırlanıyor...**", chat_id=chat_id)
    threading.Thread(target=run_log).start()

# --------------------------
# TARAMA & İSTATİSTİK KOMUTLARI
# --------------------------

def handle_scan_command(chat_id):
    def run_scan():
        try:
            pairs = Config.AUTO_SCAN_PAIRS
            results = []
            total_new_setups = 0
            
            for pair in pairs:
                try:
                    coin_name = pair.replace('/USDT:USDT', '').replace('/USDT', '')
                    market_data = _okx.get_complete_analysis_data(pair)
                    
                    if not market_data:
                        results.append(f"⚠️ {coin_name}: No Data")
                        continue

                    setups = detect_all_trading_setups(pair, market_data)
                    
                    if setups:
                        for setup in setups:
                            try:
                                if _tracking:
                                    _tracking.log_setup({
                                        'pair': pair.replace('/USDT:USDT', 'USDT'),
                                        'timestamp': f"{market_data.get('current_date', '')} {market_data.get('current_time', '')}",
                                        'setup_type': setup.get('type', 'Unknown'),
                                        'confidence': setup.get('confidence', 'LOW'),
                                        'timeframe': setup.get('timeframe', '5m'),
                                        'current_price': market_data.get('current_price', 0),
                                        'risk_percent': 2.0
                                    })
                                    total_new_setups += 1
                            except: pass
                        
                        results.append(f"✅ {coin_name}: {len(setups)} setup")
                    else:
                        results.append(f"ℹ️ {coin_name}: No setup")
                        
                except Exception as e:
                    logger.error(f"Scan error {pair}: {e}")
                    results.append(f"❌ {coin_name}: Err")
            
            msg = "🔍 **TARAMA SONUCU**\n\n" + "\n".join(results)
            msg += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup."
            
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Scan thread error: {e}")
            _telegram.send(f"❌ Tarama hatası: {str(e)}", chat_id=chat_id)

    _telegram.send(f"🔍 **Market Taraması Başlatıldı** ({len(Config.AUTO_SCAN_PAIRS)} coin)\n⏳ Analiz biraz zaman alabilir...", chat_id=chat_id)
    threading.Thread(target=run_scan).start()

def handle_score_command(chat_id):
    """
    /score - Performans raporu
    v2.1.1: Detaylı format + OKX balance + Top/Worst 5
    """
    def run_score():
        try:
            if not _tracking:
                _telegram.send("❌ Tracking servisi aktif değil.", chat_id=chat_id)
                return

            # v2.1.1: OKX'ten gerçek balance çek
            real_balance = 500.0  # Fallback
            try:
                bal = _okx.get_balance()
                if bal.get('success'):
                    real_balance = float(bal.get('free', 500.0))
            except:
                pass
            
            # v2.1.1: Gerçek balance ile stats al
            stats = _tracking.get_aggregate_stats(real_balance=real_balance)
            
            # Ana rapor
            profit_emoji = "📈" if stats['profit'] >= 0 else "📉"
            profit_sign = "+" if stats['profit'] >= 0 else ""
            
            msg = f"""
📊 **T-TARS İSTATİSTİK RAPORU**

🎯 **Genel Durum**
• Total: {stats['total_setups']} | Win: {stats['winning_trades']} | Loss: {stats['losing_trades']}
• Win Rate: %{stats['win_rate']:.1f} | Loss Rate: %{stats['loss_rate']:.1f}
• Pending: {stats['pending_setups']} | BE: {stats['breakeven_trades']}

{profit_emoji} **P/L Durumu**
• Bakiye: ${real_balance:,.2f}
• Kar/Zarar: {profit_sign}${stats['profit']:,.2f} ({profit_sign}%{stats['profit_percent']:.1f})
"""

            # Top 5 Coins
            if stats.get('top_5_coins'):
                msg += "\n🏆 **Top 5 Coin**\n"
                for i, (coin, data) in enumerate(stats['top_5_coins'], 1):
                    msg += f"  {i}. {coin} - W:{data['win_rate']}% L:{data['loss_rate']}%\n"
            
            # Top 5 Timeframes
            if stats.get('top_5_timeframes'):
                msg += "\n⏱️ **Top 5 TimeFrame**\n"
                for i, (tf, data) in enumerate(stats['top_5_timeframes'], 1):
                    msg += f"  {i}. {tf} - W:{data['win_rate']}% L:{data['loss_rate']}%\n"
            
            # Worst 5 Coins
            if stats.get('worst_5_coins') and len(stats['worst_5_coins']) > 0:
                msg += "\n💀 **Worst 5 Coin**\n"
                for i, (coin, data) in enumerate(stats['worst_5_coins'], 1):
                    msg += f"  {i}. {coin} - W:{data['win_rate']}% L:{data['loss_rate']}%\n"
            
            # Worst 5 Timeframes
            if stats.get('worst_5_timeframes') and len(stats['worst_5_timeframes']) > 0:
                msg += "\n⚠️ **Worst 5 TimeFrame**\n"
                for i, (tf, data) in enumerate(stats['worst_5_timeframes'], 1):
                    msg += f"  {i}. {tf} - W:{data['win_rate']}% L:{data['loss_rate']}%\n"
            
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Score error: {e}", exc_info=True)
            _telegram.send(f"❌ İstatistik hatası: {str(e)}", chat_id=chat_id)

    _telegram.send("📊 **İstatistikler Hesaplanıyor...**", chat_id=chat_id)
    threading.Thread(target=run_score).start()

def handle_reset_score_command(chat_id):
    def run_reset():
        try:
            if _tracking and _tracking.reset_all_tracking():
                _telegram.send("✅ **İSTATİSTİKLER SIFIRLANDI**", chat_id=chat_id)
            else:
                _telegram.send("❌ Sıfırlama başarısız.", chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("🔄 **Sıfırlanıyor...**", chat_id=chat_id)
    threading.Thread(target=run_reset).start()

# --- OKX KOMUTLARI ---

def handle_status_command(chat_id):
    def run_status():
        try:
            import time
            
            check_start = time.time()
            services_status = {'telegram': '✅', 'okx_market': '⏳', 'okx_api': '⏳', 'claude': '⏳', 'storage': '⏳'}
            
            try:
                price = _okx.get_current_price('BTC/USDT:USDT')
                services_status['okx_market'] = f'✅ (${price:,.0f})' if price > 0 else '❌'
            except: services_status['okx_market'] = '❌'
            
            try:
                if _okx.authenticated:
                    services_status['okx_api'] = '✅ (Auth)'
                else:
                    services_status['okx_api'] = '⚠️ (No Auth)'
            except: services_status['okx_api'] = '❌'
            
            services_status['claude'] = '✅' if Config.ANTHROPIC_API_KEY else '❌'
            services_status['storage'] = '✅'
            
            check_time = (time.time() - check_start) * 1000
            trading_status = '🔥🔥 AKTİF' if _trading_enabled else '🔴 DURDURULDU'
            
            msg = f"""
🤖 **T-TARS DURUM**
⏰ {get_turkey_time().strftime('%H:%M:%S')} | ⚡ {check_time:.0f}ms

📡 Telegram: {services_status['telegram']}
📡 OKX Market: {services_status['okx_market']}
📡 OKX API: {services_status['okx_api']}
🧠 Claude: {services_status['claude']}

📊 **SİSTEM:**
• Ver: v{Config.VERSION}
• Trading: {trading_status}
"""
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            _telegram.send(f"❌ Status hatası: {str(e)}", chat_id=chat_id)

    threading.Thread(target=run_status).start()

def handle_balance_command(chat_id):
    def run_bal():
        try:
            if not _okx.authenticated: return _telegram.send("❌ No Auth", chat_id=chat_id)
            bal = _okx.get_balance()
            if bal.get('success'):
                _telegram.send(f"💰 **BAKİYE:** ${bal['total']:,.2f} (Free: ${bal['free']:,.2f})", chat_id=chat_id)
            else: _telegram.send(f"❌ Hata: {bal.get('error')}", chat_id=chat_id)
        except Exception as e: _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("💰 **Sorgulanıyor...**", chat_id=chat_id)
    threading.Thread(target=run_bal).start()

def handle_positions_command(chat_id):
    def run_pos():
        try:
            if not _okx.authenticated: return _telegram.send("❌ No Auth", chat_id=chat_id)
            pos = _okx.get_positions()
            if not pos: return _telegram.send("ℹ️ Pozisyon Yok", chat_id=chat_id)
            msg = f"📊 **POZİSYONLAR ({len(pos)})**\n"
            for p in pos:
                s = '🟢' if str(p['side']).upper()=='LONG' else '🔴'
                pl = float(p.get('unrealized_pnl',0))
                msg += f"{s} {p['symbol'].replace('/USDT:USDT','')} | ${pl:+.2f}\n"
            _telegram.send(msg, chat_id=chat_id)
        except Exception as e: _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    _telegram.send("📊 **Çekiliyor...**", chat_id=chat_id)
    threading.Thread(target=run_pos).start()

def handle_help_command(chat_id):
    msg = f"""
🤖 **T-TARS v{Config.VERSION}**

/plan [coin] - Detaylı analiz
/scan - Market taraması
/score - Performans raporu
/status - Durum kontrolü
/balance - Bakiye
/positions - Pozisyonlar
/stopokx - Trading durdur
/startokx - Trading başlat
"""
    _telegram.send(msg, chat_id=chat_id)

# --- ANLIK KOMUTLAR ---

def handle_stopokx_command(chat_id):
    global _trading_enabled
    _trading_enabled = False
    _telegram.send("🔴 **DURDURULDU**", chat_id=chat_id)

def handle_startokx_command(chat_id):
    global _trading_enabled
    _trading_enabled = True
    _telegram.send("🔥🔥 **LIVE MOD BAŞLATILDI** 🔥🔥", chat_id=chat_id)

# --- TİCARET MOTORU ---

def is_trading_enabled():
    return _trading_enabled

def execute_trade_for_setup(setup_data, chat_id=None):
    """v2.1.0: Güvenli Trade Execution - Parametre fix"""
    try:
        if not _trading_enabled: return {'success': False, 'reason': 'disabled'}
        
        pair = setup_data.get('pair', '')
        direction = setup_data.get('direction', 'LONG')
        entry = float(setup_data.get('entry_price', 0))
        stop = float(setup_data.get('stop_price', 0))
        tp1 = float(setup_data.get('tp1_price', 0))
        
        bal = _okx.get_balance()
        if not bal.get('success'): return {'success': False, 'reason': 'balance_error'}
        
        risk_amt = float(bal['free']) * 0.02
        dist_pct = abs(entry - stop) / entry if entry > 0 else 0.01
        size_usd = risk_amt / dist_pct if dist_pct > 0 else 10.0
        
        size_usd = min(size_usd, float(Config.MAX_POSITION_SIZE))
        
        res = _okx.place_order_with_tp_sl(
            symbol=pair.replace('USDT', '/USDT:USDT') if '/' not in pair else pair,
            side='buy' if direction == 'LONG' else 'sell',
            amount_usd=size_usd,
            tp_price=tp1,
            sl_price=stop,
            entry_price=entry
        )
        
        if res.get('success'):
            if chat_id: _telegram.send(f"🚀 İşlem Açıldı: {pair} {direction}", chat_id=chat_id)
            return {'success': True}
        else:
            if chat_id: _telegram.send(f"❌ İşlem Hatası: {res.get('error')}", chat_id=chat_id)
            return {'success': False, 'reason': res.get('error')}
            
    except Exception as e:
        logger.error(f"Exec Error: {e}")
        return {'success': False, 'reason': str(e)}
