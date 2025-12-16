# -*- coding: utf-8 -*-
"""
T-TARS Telegram Handlers v2.2.6
================================
Telegram bot komut handler'ları.

v2.2.6:
- FIX: Execute sonrası HER ZAMAN Telegram bildirimi gönderiliyor
- NEW: chat_id olmasa bile Config.TELEGRAM_CHAT_ID'ye gönderim

v2.2.1:
- FIX: Telegram Markdown ** → * (Telegram uyumluluğu)
- CHANGED: /help artık CHANGELOG gösteriyor
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
_exchange = None
_claude = None
_storage = None
_tracking = None
_trading_enabled = True 

def init_handlers(telegram, exchange, claude, storage, tracking):
    global _telegram, _exchange, _claude, _storage, _tracking, _trading_enabled
    _telegram = telegram
    _exchange = exchange
    _claude = claude
    _storage = storage
    _tracking = tracking
    _trading_enabled = getattr(Config, 'BITGET_TRADING_ENABLED', True)
    logger.info(f"✅ Telegram handlers initialized (v2.2.6) - Trading: {_trading_enabled}")

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
    """/plan [parite] - Detaylı Akıllı Plan"""
    def run_plan():
        try:
            parts = text.split()
            user_input = parts[1] if len(parts) > 1 else "BTCUSDT"
            ticker = Config.get_pair_symbol(user_input)
            coin_name = ticker.replace('/', '').replace(':USDT', '')
            
            _telegram.send(f"🔄 *{coin_name} taranıyor...*\n⏳ Tüm timeframe'ler analiz ediliyor...", chat_id=chat_id)
            
            market_data = _exchange.get_complete_analysis_data(ticker)
            if not market_data:
                _telegram.send("❌ Market verisi alınamadı.", chat_id=chat_id)
                return

            all_setups = detect_all_trading_setups(ticker, market_data)
            best_setup = select_best_timeframe_for_plan(all_setups)
            
            # Previous Day Candle bilgisi
            pdc = market_data.get('previous_day', {})
            bias = pdc.get('candle_type', 'unknown')
            bias_emoji = "🟢 BULLISH" if bias == 'green' else "🔴 BEARISH"
            pdc_high = pdc.get('high', 0)
            pdc_low = pdc.get('low', 0)
            pdc_open = pdc.get('open', 0)
            pdc_close = pdc.get('close', 0)
            
            # Fibo seviyeleri
            fibo = market_data.get('fibonacci', {}).get('levels', {})
            current_price = market_data.get('current_price', 0)
            
            # ATR bilgileri
            atr_data = market_data.get('atr', {})
            
            if best_setup:
                tf = best_setup['timeframe']
                direction = best_setup['direction']
                conf = best_setup['confidence']
                entry = best_setup.get('entry_zone', 'N/A')
                stop = best_setup.get('stop_loss', 'N/A')
                tp1 = best_setup.get('tp1', 'N/A')
                tp2 = best_setup.get('tp2', 'N/A')
                rr = best_setup.get('rr_ratio', 0)
                setup_type = best_setup.get('type', 'Unknown')
                
                atr_val = atr_data.get(tf, 0)
                vol = market_data.get('volume', {}).get(tf, {})
                vol_ratio = vol.get('spike_ratio', 0) if isinstance(vol, dict) else 0
                
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                conf_emoji = "🔥" if conf == "HIGH" else "⚡" if conf == "MEDIUM" else "💡"
                
                plan_msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
🎯 *T-TARS AKILLI PLAN*
━━━━━━━━━━━━━━━━━━━━━━

📊 *{coin_name}* | {tf} | {bias_emoji}
💵 Anlık Fiyat: {format_price(current_price)}

━━━━━━━━━━━━━━━━━━━━━━
{dir_emoji} *EN İYİ FIRSAT: {direction}*
━━━━━━━━━━━━━━━━━━━━━━

{conf_emoji} *Güven:* {conf}
📈 *Setup:* {setup_type}
⏱ *Timeframe:* {tf}

🎯 *Giriş:* {entry}
🛑 *Stop Loss:* {stop}
✅ *TP1:* {tp1}
🏆 *TP2:* {tp2}
📊 *R:R:* {rr:.2f}

━━━━━━━━━━━━━━━━━━━━━━
📉 *TEKNİK VERİLER*
━━━━━━━━━━━━━━━━━━━━━━

📏 ATR({tf}): {format_price(atr_val)}
📊 Hacim: {vol_ratio:.2f}x

━━━━━━━━━━━━━━━━━━━━━━
🕯 *PDC (Previous Day Candle)*
━━━━━━━━━━━━━━━━━━━━━━

• High: {format_price(pdc_high)}
• Low: {format_price(pdc_low)}
• Open: {format_price(pdc_open)}
• Close: {format_price(pdc_close)}

━━━━━━━━━━━━━━━━━━━━━━
📐 *FİBONACCİ SEVİYELERİ*
━━━━━━━━━━━━━━━━━━━━━━

• 0.0%: {format_price(fibo.get('0.0', 0))}
• 23.6%: {format_price(fibo.get('23.6', 0))}
• 38.2%: {format_price(fibo.get('38.2', 0))}
• 50.0%: {format_price(fibo.get('50.0', 0))}
• 61.8%: {format_price(fibo.get('61.8', 0))}
• 78.6%: {format_price(fibo.get('78.6', 0))}
• 100%: {format_price(fibo.get('100.0', 0))}

━━━━━━━━━━━━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')} TR
━━━━━━━━━━━━━━━━━━━━━━
"""
            else:
                # Setup bulunamadı - genel bakış
                plan_msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
ℹ️ *T-TARS GENEL BAKIŞ*
━━━━━━━━━━━━━━━━━━━━━━

📊 *{coin_name}* | {bias_emoji}
💵 Anlık Fiyat: {format_price(current_price)}

⚠️ *Şu an net bir setup bulunamadı.*

━━━━━━━━━━━━━━━━━━━━━━
🕯 *PDC (Previous Day Candle)*
━━━━━━━━━━━━━━━━━━━━━━

• High: {format_price(pdc_high)}
• Low: {format_price(pdc_low)}
• Open: {format_price(pdc_open)}
• Close: {format_price(pdc_close)}

━━━━━━━━━━━━━━━━━━━━━━
📐 *KRİTİK SEVİYELER (Fibo)*
━━━━━━━━━━━━━━━━━━━━━━

• Destek (61.8%): {format_price(fibo.get('61.8', 0))}
• Pivot (50.0%): {format_price(fibo.get('50.0', 0))}
• Direnç (38.2%): {format_price(fibo.get('38.2', 0))}

━━━━━━━━━━━━━━━━━━━━━━
💡 *ÖNERİ:* PDC High/Low kırılımı
veya Fibo 61.8% tepkisi bekleyin.
━━━━━━━━━━━━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')} TR
━━━━━━━━━━━━━━━━━━━━━━
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

    _telegram.send("⚡ *Durum Kontrol Ediliyor...*", chat_id=chat_id)
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

    _telegram.send("📋 *Log Hazırlanıyor...*", chat_id=chat_id)
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
                    market_data = _exchange.get_complete_analysis_data(pair)
                    
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
            
            msg = "🔍 *TARAMA SONUCU*\n\n" + "\n".join(results)
            msg += f"\n\n🎯 *Toplam:* {total_new_setups} yeni setup."
            
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Scan thread error: {e}")
            _telegram.send(f"❌ Tarama hatası: {str(e)}", chat_id=chat_id)

    _telegram.send(f"🔍 *Market Taraması Başlatıldı* ({len(Config.AUTO_SCAN_PAIRS)} coin)\n⏳ Analiz biraz zaman alabilir...", chat_id=chat_id)
    threading.Thread(target=run_scan).start()

def handle_score_command(chat_id):
    """
    /score - Performans raporu
    """
    def run_score():
        try:
            if not _tracking:
                _telegram.send("❌ Tracking servisi aktif değil.", chat_id=chat_id)
                return

            real_balance = None
            try:
                bal = _exchange.get_balance()
                if bal.get('success'):
                    real_balance = float(bal.get('free', 0))
                    if real_balance <= 0:
                        real_balance = None
            except Exception as e:
                logger.warning(f"Balance fetch error: {e}")
            
            stats = _tracking.get_aggregate_stats(real_balance=real_balance)
            
            display_balance = stats.get('starting_balance', 500.0)
            
            profit_emoji = "📈" if stats['profit'] >= 0 else "📉"
            profit_sign = "+" if stats['profit'] >= 0 else ""
            
            msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
📊 *T-TARS İSTATİSTİK RAPORU*
━━━━━━━━━━━━━━━━━━━━━━

🎯 *Genel Durum*
• Total: {stats['total_setups']} | Win: {stats['winning_trades']} | Loss: {stats['losing_trades']}
• Win Rate: %{stats['win_rate']:.1f} | Loss Rate: %{stats['loss_rate']:.1f}
• Pending: {stats['pending_setups']} | BE: {stats['breakeven_trades']}

{profit_emoji} *P/L Durumu*
• Bakiye: ${display_balance:,.2f}
• Kar/Zarar: {profit_sign}${stats['profit']:,.2f} ({profit_sign}%{stats['profit_percent']:.1f})
"""

            if stats.get('top_5_coins'):
                msg += "\n🏆 *Top 5 Coin* (min 3 trade)\n"
                for i, (coin, data) in enumerate(stats['top_5_coins'], 1):
                    completed = data.get('completed', data['wins'] + data['losses'])
                    msg += f"  {i}. {coin} - W:{data['win_rate']}% L:{data['loss_rate']}% ({completed})\n"
            
            if stats.get('top_5_timeframes'):
                msg += "\n⏱ *Top 5 TimeFrame* (min 3 trade)\n"
                for i, (tf, data) in enumerate(stats['top_5_timeframes'], 1):
                    completed = data.get('completed', data['wins'] + data['losses'])
                    msg += f"  {i}. {tf} - W:{data['win_rate']}% L:{data['loss_rate']}% ({completed})\n"
            
            if stats.get('worst_5_coins') and len(stats['worst_5_coins']) > 0:
                msg += "\n💀 *Worst 5 Coin* (min 3 trade)\n"
                for i, (coin, data) in enumerate(stats['worst_5_coins'], 1):
                    completed = data.get('completed', data['wins'] + data['losses'])
                    msg += f"  {i}. {coin} - W:{data['win_rate']}% L:{data['loss_rate']}% ({completed})\n"
            
            if stats.get('worst_5_timeframes') and len(stats['worst_5_timeframes']) > 0:
                msg += "\n⚠️ *Worst 5 TimeFrame* (min 3 trade)\n"
                for i, (tf, data) in enumerate(stats['worst_5_timeframes'], 1):
                    completed = data.get('completed', data['wins'] + data['losses'])
                    msg += f"  {i}. {tf} - W:{data['win_rate']}% L:{data['loss_rate']}% ({completed})\n"
            
            msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')} TR"
            
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Score error: {e}", exc_info=True)
            _telegram.send(f"❌ İstatistik hatası: {str(e)}", chat_id=chat_id)

    _telegram.send("📊 *İstatistikler Hesaplanıyor...*", chat_id=chat_id)
    threading.Thread(target=run_score).start()

def handle_reset_score_command(chat_id):
    def run_reset():
        try:
            if _tracking and _tracking.reset_all_tracking():
                _telegram.send("✅ *İSTATİSTİKLER SIFIRLANDI*", chat_id=chat_id)
            else:
                _telegram.send("❌ Sıfırlama başarısız.", chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("🔄 *Sıfırlanıyor...*", chat_id=chat_id)
    threading.Thread(target=run_reset).start()

# --- BORSA KOMUTLARI ---

def handle_status_command(chat_id):
    def run_status():
        try:
            import time
            
            check_start = time.time()
            services_status = {'telegram': '✅', 'bitget_market': '⏳', 'bitget_api': '⏳', 'claude': '⏳', 'storage': '⏳'}
            
            try:
                price = _exchange.get_current_price('BTC/USDT:USDT')
                services_status['bitget_market'] = f'✅ (${price:,.0f})' if price > 0 else '❌'
            except: services_status['bitget_market'] = '❌'
            
            try:
                if _exchange.authenticated:
                    services_status['bitget_api'] = '✅ (Auth)'
                else:
                    services_status['bitget_api'] = '⚠️ (No Auth)'
            except: services_status['bitget_api'] = '❌'
            
            services_status['claude'] = '✅' if Config.ANTHROPIC_API_KEY else '❌'
            services_status['storage'] = '✅'
            
            check_time = (time.time() - check_start) * 1000
            trading_status = '🔥 AKTİF' if _trading_enabled else '🔴 DURDURULDU'
            
            msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
🤖 *T-TARS DURUM*
━━━━━━━━━━━━━━━━━━━━━━

📡 *Servisler*
• Telegram: {services_status['telegram']}
• Bitget Market: {services_status['bitget_market']}
• Bitget API: {services_status['bitget_api']}
• Claude AI: {services_status['claude']}
• Storage: {services_status['storage']}

📊 *Sistem*
• Versiyon: v{Config.VERSION}
• Exchange: Bitget
• Trading: {trading_status}
• Response: {check_time:.0f}ms

━━━━━━━━━━━━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')} TR
━━━━━━━━━━━━━━━━━━━━━━
"""
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            _telegram.send(f"❌ Status hatası: {str(e)}", chat_id=chat_id)

    threading.Thread(target=run_status).start()

def handle_balance_command(chat_id):
    def run_bal():
        try:
            if not _exchange.authenticated: 
                return _telegram.send("❌ Bitget API bağlantısı yok", chat_id=chat_id)
            bal = _exchange.get_balance()
            if bal.get('success'):
                msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
💰 *BAKİYE*
━━━━━━━━━━━━━━━━━━━━━━

• Toplam: ${bal['total']:,.2f}
• Kullanılabilir: ${bal['free']:,.2f}
• Kullanımda: ${bal.get('used', 0):,.2f}

━━━━━━━━━━━━━━━━━━━━━━
"""
                _telegram.send(msg, chat_id=chat_id)
            else: 
                _telegram.send(f"❌ Hata: {bal.get('error')}", chat_id=chat_id)
        except Exception as e: 
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("💰 *Sorgulanıyor...*", chat_id=chat_id)
    threading.Thread(target=run_bal).start()

def handle_positions_command(chat_id):
    def run_pos():
        try:
            if not _exchange.authenticated: 
                return _telegram.send("❌ Bitget API bağlantısı yok", chat_id=chat_id)
            pos = _exchange.get_positions()
            if not pos: 
                return _telegram.send("ℹ️ Açık pozisyon yok", chat_id=chat_id)
            
            msg = f"━━━━━━━━━━━━━━━━━━━━━━\n📊 *POZİSYONLAR* ({len(pos)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for p in pos:
                s = '🟢' if str(p['side']).upper()=='LONG' else '🔴'
                pl = float(p.get('unrealized_pnl',0))
                symbol = p['symbol'].replace('/USDT:USDT','')
                msg += f"{s} *{symbol}* | P/L: ${pl:+.2f}\n"
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━"
            _telegram.send(msg, chat_id=chat_id)
        except Exception as e: 
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("📊 *Pozisyonlar çekiliyor...*", chat_id=chat_id)
    threading.Thread(target=run_pos).start()

def handle_help_command(chat_id):
    """
    /help - Yardım ve CHANGELOG
    v2.2.1: Cloud Storage'dan CHANGELOG çeker
    """
    def run_help():
        try:
            # CHANGELOG'u Cloud Storage'dan çek
            changelog_text = ""
            try:
                changelog = _storage.get_changelog()
                if changelog:
                    # İlk 1500 karakter (Telegram limiti)
                    changelog_text = changelog[:1500]
                    if len(changelog) > 1500:
                        changelog_text += "\n... (devamı için CHANGELOG.md'ye bakın)"
            except Exception as e:
                logger.warning(f"CHANGELOG fetch error: {e}")
                changelog_text = "CHANGELOG yüklenemedi"
            
            msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
🤖 *T-TARS v{Config.VERSION}*
━━━━━━━━━━━━━━━━━━━━━━
Bitget Futures Trading Bot

📋 *KOMUTLAR*
━━━━━━━━━━━━━━━━━━━━━━

🔍 *Analiz*
• /plan [coin] - Detaylı analiz
• /scan - Market taraması

📊 *İstatistik*
• /score - Performans raporu
• /reset\_score - İstatistikleri sıfırla

💰 *Hesap*
• /balance - Bakiye
• /positions - Açık pozisyonlar
• /status - Sistem durumu

🎮 *Kontrol*
• /stopbitget - Trading durdur
• /startbitget - Trading başlat
• /help - Bu menü

━━━━━━━━━━━━━━━━━━━━━━
📝 *CHANGELOG*
━━━━━━━━━━━━━━━━━━━━━━
{changelog_text}
━━━━━━━━━━━━━━━━━━━━━━
"""
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Help error: {e}")
            _telegram.send(f"❌ Help hatası: {e}", chat_id=chat_id)
    
    threading.Thread(target=run_help).start()

# --- TRADING KONTROL ---

def handle_stopbitget_command(chat_id):
    global _trading_enabled
    _trading_enabled = False
    msg = """
━━━━━━━━━━━━━━━━━━━━━━
🔴 *TRADİNG DURDURULDU*
━━━━━━━━━━━━━━━━━━━━━━

• Yeni emir açılmayacak
• Mevcut emirler etkilenmez
• Bildirimler kapalı

Tekrar başlatmak için:
/startbitget
━━━━━━━━━━━━━━━━━━━━━━
"""
    _telegram.send(msg, chat_id=chat_id)

def handle_startbitget_command(chat_id):
    global _trading_enabled
    _trading_enabled = True
    msg = """
━━━━━━━━━━━━━━━━━━━━━━
🔥 *LIVE MOD AKTİF*
━━━━━━━━━━━━━━━━━━━━━━

• Otomatik trading başladı
• Setup'lar işleme alınacak
• Bildirimler açık

Durdurmak için:
/stopbitget
━━━━━━━━━━━━━━━━━━━━━━
"""
    _telegram.send(msg, chat_id=chat_id)

# --- TİCARET MOTORU ---

def is_trading_enabled():
    return _trading_enabled

def execute_trade_for_setup(setup_data, chat_id=None):
    """
    v2.2.6: Bitget ile Trade Execution + HER ZAMAN Telegram Bildirimi
    
    chat_id olmasa bile Config.TELEGRAM_CHAT_ID'ye gönderir
    """
    try:
        if not _trading_enabled:
            return {'success': False, 'reason': 'disabled'}
        
        pair = setup_data.get('pair', '')
        direction = setup_data.get('direction', 'LONG')
        entry = float(setup_data.get('entry_price', 0))
        stop = float(setup_data.get('stop_price', 0))
        tp1 = float(setup_data.get('tp1_price', 0))
        
        coin_name = pair.replace('/USDT:USDT', '').replace('USDT', '').replace('/', '')
        
        res = _exchange.place_order_with_tp_sl(
            symbol=pair.replace('USDT', '/USDT:USDT') if '/' not in pair else pair,
            side='buy' if direction == 'LONG' else 'sell',
            entry_price=entry,
            stop_price=stop,
            tp_price=tp1
        )
        
        # v2.2.6: HER ZAMAN bildirim gönder (chat_id yoksa Config'den al)
        notify_chat = chat_id or Config.TELEGRAM_CHAT_ID
        
        if res.get('success'):
            dir_emoji = "🟢" if direction == "LONG" else "🔴"
            
            # v2.2.6: Detaylı başarı bildirimi
            success_msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
{dir_emoji} *YENİ EMİR AÇILDI*
━━━━━━━━━━━━━━━━━━━━━━

📊 *{coin_name}* | {direction}
💵 Entry: {format_price(entry)}
🛑 SL: {format_price(stop)}
✅ TP: {format_price(tp1)}

📦 Kontrat: {res.get('contracts', 'N/A')}
💰 Pozisyon: ${res.get('position_usd', 0):.2f}
🔖 Order ID: {res.get('order_id', 'N/A')[:16]}...

━━━━━━━━━━━━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%H:%M:%S')} TR
━━━━━━━━━━━━━━━━━━━━━━
"""
            _telegram.send(success_msg, chat_id=notify_chat)
            logger.info(f"📱 Telegram bildirimi gönderildi: {coin_name} {direction}")
            
            return {
                'success': True,
                'order_id': res.get('order_id'),
                'contracts': res.get('contracts'),
                'position_usd': res.get('position_usd')
            }
        else:
            # v2.2.6: Hata bildirimi
            error_msg = f"❌ *EMİR HATASI*\n\n{coin_name} {direction}\nHata: {res.get('error', 'Unknown')}"
            _telegram.send(error_msg, chat_id=notify_chat)
            
            return {'success': False, 'reason': res.get('error')}
            
    except Exception as e:
        logger.error(f"Exec Error: {e}")
        
        # v2.2.6: Exception durumunda da bildirim
        try:
            notify_chat = chat_id or Config.TELEGRAM_CHAT_ID
            _telegram.send(f"❌ *Execute Exception*\n\n{str(e)}", chat_id=notify_chat)
        except:
            pass
        
        return {'success': False, 'reason': str(e)}
