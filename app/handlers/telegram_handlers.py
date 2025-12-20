# -*- coding: utf-8 -*-
"""
T-TARS Telegram Handlers v2.3.11
================================
Telegram bot komut handler'ları.

v2.3.11:
- FIX: /score f-string format hatası düzeltildi
- FIX: available_balance ternary operatör sorunu çözüldü

v2.3.1:
- FIX: /score bakiye - Available yerine TOTAL bakiye gösteriliyor
- FIX: Best/Worst gösterimi - min trade yoksa da göster
- ADD: Debug bilgileri eklendi

v2.3.0:
- REMOVED: execute_trade_for_setup() → bitget_service.py'ye taşındı
- Telegram bildirimleri main.py'de yapılıyor
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from app.config import Config
from app.strategies.setup_detector import detect_all_trading_setups

logger = logging.getLogger(__name__)
TURKEY_TZ = timezone(timedelta(hours=3))


def get_turkey_time():
    return datetime.now(TURKEY_TZ)


def format_price(price):
    if price is None or price == 0:
        return "$0.00"
    try:
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
    except:
        return "$0.00"


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
    logger.info(f"✅ Telegram handlers initialized (v2.3.11) - Trading: {_trading_enabled}")


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
                            except:
                                pass
                        
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
    """/score - Performans raporu v2.3.11"""
    def run_score():
        try:
            if not _tracking:
                _telegram.send("❌ Tracking servisi aktif değil.", chat_id=chat_id)
                return

            # v2.3.1 FIX: TOTAL bakiye al, Available değil!
            total_balance = None
            available_balance = None
            try:
                bal = _exchange.get_balance()
                if bal.get('success'):
                    total_balance = float(bal.get('total', 0))
                    available_balance = float(bal.get('free', 0))
                    logger.info(f"📊 Score balance: Total=${total_balance:.2f}, Available=${available_balance:.2f}")
            except Exception as e:
                logger.warning(f"Balance fetch error: {e}")
            
            # v2.3.1: Total bakiye ile stats al
            stats = _tracking.get_aggregate_stats(real_balance=total_balance)
            
            # v2.3.1: Total bakiyeyi göster
            display_balance = total_balance if total_balance and total_balance > 0 else stats.get('starting_balance', 500.0)
            
            # v2.3.11 FIX: available_balance için safe değer
            available_display = available_balance if available_balance else 0.0
            
            profit_emoji = "📈" if stats['profit'] >= 0 else "📉"
            profit_sign = "+" if stats['profit'] >= 0 else ""
            
            # Tamamlanan işlem sayısı
            completed_trades = stats['winning_trades'] + stats['losing_trades']
            
            msg = f"""
━━━━━━━━━━━━━━━━━━━━━━
📊 *T-TARS İSTATİSTİK RAPORU*
━━━━━━━━━━━━━━━━━━━━━━

🎯 *Genel Durum*
• Total: {stats['total_setups']} | Win: {stats['winning_trades']} | Loss: {stats['losing_trades']}
• Win Rate: %{stats['win_rate']:.1f} | Loss Rate: %{stats['loss_rate']:.1f}
• Pending: {stats['pending_setups']} | BE: {stats['breakeven_trades']} | Expired: {stats.get('expired_setups', 0)}
• Completed: {completed_trades}

{profit_emoji} *P/L Durumu*
• Bakiye (Total): ${display_balance:,.2f}
• Kullanılabilir: ${available_display:,.2f}
• Kar/Zarar: {profit_sign}${stats['profit']:,.2f} ({profit_sign}%{stats['profit_percent']:.1f})
"""

            # v2.3.1: Best/Worst Coin - min trade kontrolü kaldırıldı, tümünü göster
            coin_breakdown = stats.get('coin_breakdown', {})
            if coin_breakdown:
                # En iyi 5 coin (win_rate'e göre sırala)
                sorted_coins = sorted(
                    [(c, s) for c, s in coin_breakdown.items() if s['wins'] + s['losses'] > 0],
                    key=lambda x: x[1]['win_rate'],
                    reverse=True
                )
                
                if sorted_coins:
                    msg += "\n🏆 *Best Coins* (by Win Rate)\n"
                    for i, (coin, data) in enumerate(sorted_coins[:5], 1):
                        completed = data['wins'] + data['losses']
                        msg += f"  {i}. {coin} - W:{data['win_rate']}% ({data['wins']}/{completed})\n"
                    
                    # Worst coins (tersten)
                    worst_coins = sorted_coins[-5:] if len(sorted_coins) > 5 else []
                    if worst_coins:
                        msg += "\n💀 *Worst Coins* (by Win Rate)\n"
                        for i, (coin, data) in enumerate(reversed(worst_coins), 1):
                            completed = data['wins'] + data['losses']
                            msg += f"  {i}. {coin} - W:{data['win_rate']}% ({data['wins']}/{completed})\n"
            
            # v2.3.1: Best/Worst TF
            tf_breakdown = stats.get('timeframe_breakdown', {})
            if tf_breakdown:
                sorted_tfs = sorted(
                    [(tf, s) for tf, s in tf_breakdown.items() if s['wins'] + s['losses'] > 0],
                    key=lambda x: x[1]['win_rate'],
                    reverse=True
                )
                
                if sorted_tfs:
                    msg += "\n⏱ *Best TimeFrames* (by Win Rate)\n"
                    for i, (tf, data) in enumerate(sorted_tfs[:5], 1):
                        completed = data['wins'] + data['losses']
                        msg += f"  {i}. {tf} - W:{data['win_rate']}% ({data['wins']}/{completed})\n"
                    
                    worst_tfs = sorted_tfs[-5:] if len(sorted_tfs) > 5 else []
                    if worst_tfs:
                        msg += "\n⚠️ *Worst TimeFrames* (by Win Rate)\n"
                        for i, (tf, data) in enumerate(reversed(worst_tfs), 1):
                            completed = data['wins'] + data['losses']
                            msg += f"  {i}. {tf} - W:{data['win_rate']}% ({data['wins']}/{completed})\n"
            
            # Eğer hiç completed trade yoksa bilgi ver
            if completed_trades == 0:
                msg += "\n⚠️ *Not:* Henüz tamamlanan işlem yok.\n"
                msg += "Win/Loss oranları işlemler kapandıkça güncellenecek.\n"
            
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


# --------------------------
# BORSA KOMUTLARI
# --------------------------

def handle_status_command(chat_id):
    def run_status():
        try:
            import time
            
            check_start = time.time()
            services_status = {
                'telegram': '✅',
                'bitget_market': '⏳',
                'bitget_api': '⏳',
                'claude': '⏳',
                'storage': '⏳'
            }
            
            try:
                price = _exchange.get_current_price('BTC/USDT:USDT')
                services_status['bitget_market'] = f'✅ (${price:,.0f})' if price > 0 else '❌'
            except:
                services_status['bitget_market'] = '❌'
            
            try:
                if _exchange.authenticated:
                    services_status['bitget_api'] = '✅ (Auth)'
                else:
                    services_status['bitget_api'] = '⚠️ (No Auth)'
            except:
                services_status['bitget_api'] = '❌'
            
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
• AI Engine: Claude Haiku 4.5
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
                s = '🟢' if str(p['side']).upper() == 'LONG' else '🔴'
                pl = float(p.get('unrealized_pnl', 0))
                symbol = p['symbol'].replace('/USDT:USDT', '')
                msg += f"{s} *{symbol}* | P/L: ${pl:+.2f}\n"
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━"
            _telegram.send(msg, chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("📊 *Pozisyonlar çekiliyor...*", chat_id=chat_id)
    threading.Thread(target=run_pos).start()


def handle_help_command(chat_id):
    """/help - Yardım ve CHANGELOG"""
    def run_help():
        try:
            changelog_text = ""
            try:
                changelog = _storage.get_changelog()
                if changelog:
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
AI Engine: Claude Haiku 4.5

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


# --------------------------
# TRADING KONTROL
# --------------------------

def handle_stopbitget_command(chat_id):
    global _trading_enabled
    _trading_enabled = False
    msg = """
━━━━━━━━━━━━━━━━━━━━━━
🔴 *TRADİNG DURDURULDU*
━━━━━━━━━━━━━━━━━━━━━━

• Yeni emir açılmayacak
• Claude AI değerlendirme duracak
• Mevcut emirler etkilenmez

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
• Claude AI karar verecek
• Setup'lar değerlendirilecek

Durdurmak için:
/stopbitget
━━━━━━━━━━━━━━━━━━━━━━
"""
    _telegram.send(msg, chat_id=chat_id)


# --------------------------
# HELPER FUNCTIONS
# --------------------------

def is_trading_enabled():
    """Trading aktif mi?"""
    return _trading_enabled
