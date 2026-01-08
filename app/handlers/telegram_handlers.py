# -*- coding: utf-8 -*-
"""
T-TARS Telegram Handlers v2.7.0
=================================
Telegram bot komut handler'ları.

v2.7.0:
- REMOVED: /plan, /scan, /execute, /log komutları kaldırıldı
- UPDATED: /help menüsü sadeleştirildi
- CLEANUP: Kullanılmayan fonksiyonlar temizlendi

v2.5.4:
- CHANGED: _claude → _grok (global değişken)
- CHANGED: Claude AI referansları → Grok AI
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from app.config import Config

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
_grok = None
_storage = None
_tracking = None
_trading_enabled = True
_market_cache = None


def init_handlers(telegram, exchange, grok, storage, tracking, market_cache=None):
    """Handler'ları başlat"""
    global _telegram, _exchange, _grok, _storage, _tracking, _trading_enabled, _market_cache
    _telegram = telegram
    _exchange = exchange
    _grok = grok
    _storage = storage
    _tracking = tracking
    _market_cache = market_cache
    _trading_enabled = getattr(Config, 'BITGET_TRADING_ENABLED', True)
    logger.info(f"✅ Telegram handlers initialized (v2.7.0) - Trading: {_trading_enabled}")


# --------------------------
# İSTATİSTİK KOMUTLARI
# --------------------------

def handle_score_command(chat_id):
    """/score - Performans raporu"""
    def run_score():
        try:
            if not _exchange:
                _telegram.send("❌ Exchange servisi aktif değil.", chat_id=chat_id)
                return

            total_balance = 0.0
            available_balance = 0.0
            try:
                bal = _exchange.get_balance()
                if bal.get('success'):
                    total_balance = float(bal.get('total', 0))
                    available_balance = float(bal.get('free', 0))
            except Exception as e:
                logger.warning(f"Balance fetch error: {e}")
            
            stats = _exchange.get_trade_history_stats(limit=100)
            
            if not stats.get('success'):
                _telegram.send(f"❌ Trade history alınamadı: {stats.get('error', 'Unknown')}", chat_id=chat_id)
                return
            
            total_trades = stats.get('total_trades', 0)
            winning_trades = stats.get('winning_trades', 0)
            losing_trades = stats.get('losing_trades', 0)
            win_rate = stats.get('win_rate', 0)
            total_pnl = stats.get('total_pnl', 0)
            
            completed_trades = winning_trades + losing_trades
            loss_rate = 100 - win_rate if completed_trades > 0 else 0
            
            profit_sign = "+" if total_pnl >= 0 else ""
            
            coin_info = ""
            worst_coin = stats.get('worst_coin')
            best_coin = stats.get('best_coin')
            
            if worst_coin or best_coin:
                coin_info = "\n🎰 *Coin Performansı (30g)*\n"
                
                if worst_coin:
                    wc_pnl = worst_coin.get('pnl', 0)
                    wc_symbol = worst_coin.get('symbol', 'N/A')
                    wc_wins = worst_coin.get('wins', 0)
                    wc_losses = worst_coin.get('losses', 0)
                    coin_info += f"• 🔴 *En Kötü:* {wc_symbol} (${wc_pnl:+.2f}) [{wc_wins}W/{wc_losses}L]\n"
                
                if best_coin:
                    bc_pnl = best_coin.get('pnl', 0)
                    bc_symbol = best_coin.get('symbol', 'N/A')
                    bc_wins = best_coin.get('wins', 0)
                    bc_losses = best_coin.get('losses', 0)
                    coin_info += f"• 🟢 *En İyi:* {bc_symbol} (${bc_pnl:+.2f}) [{bc_wins}W/{bc_losses}L]\n"
            
            msg = f"""
━━━━━━━━━━━
📊 *T-TARS İSTATİSTİK*
━━━━━━━━━━━

🎯 *Genel Durum*
• Total: {total_trades} | Win: {winning_trades} | Loss: {losing_trades}
• Win Rate: %{win_rate:.1f} | Loss Rate: %{loss_rate:.1f}

💰 *Bakiye*
• Toplam: ${total_balance:,.2f}
• Kullanılabilir: ${available_balance:,.2f}

📊 *Performans*
• Günlük: {'+' if stats.get('daily_pnl', 0) >= 0 else ''}${stats.get('daily_pnl', 0):,.2f}
• Haftalık: {'+' if stats.get('weekly_pnl', 0) >= 0 else ''}${stats.get('weekly_pnl', 0):,.2f}
• Aylık: {'+' if stats.get('monthly_pnl', 0) >= 0 else ''}${stats.get('monthly_pnl', 0):,.2f}
• Toplam: {profit_sign}${total_pnl:,.2f}
{coin_info}
━━━━━━━━━━━
📡 Bitget API
⏰ {get_turkey_time().strftime('%H:%M:%S')} TR
"""
            
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"Score error: {e}", exc_info=True)
            _telegram.send(f"❌ İstatistik hatası: {str(e)}", chat_id=chat_id)

    _telegram.send("📊 *İstatistikler Hesaplanıyor...*", chat_id=chat_id)
    threading.Thread(target=run_score).start()


def handle_reset_score_command(chat_id):
    """/reset_score - İstatistikleri sıfırla"""
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
    """/status - Sistem durumu"""
    def run_status():
        try:
            import time
            
            check_start = time.time()
            services_status = {
                'telegram': '✅',
                'bitget_market': '⏳',
                'bitget_api': '⏳',
                'grok': '⏳',
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
            
            services_status['grok'] = '✅' if Config.XAI_API_KEY else '❌'
            services_status['storage'] = '✅'
            
            check_time = (time.time() - check_start) * 1000
            trading_status = '🔥 AKTİF' if _trading_enabled else '🔴 DURDURULDU'
            
            cache_info = f"Cache: {len(_market_cache)} entries" if _market_cache else "Cache: N/A"
            
            msg = f"""
━━━━━━━━━━━
🤖 *T-TARS DURUM*
━━━━━━━━━━━

📡 *Servisler*
• Telegram: {services_status['telegram']}
• Bitget Market: {services_status['bitget_market']}
• Bitget API: {services_status['bitget_api']}
• Grok AI: {services_status['grok']}
• Storage: {services_status['storage']}

📊 *Sistem*
• Versiyon: v{Config.VERSION}
• Exchange: Bitget
• AI Engine: Grok 4.1
• Trading: {trading_status}
• {cache_info}
• Response: {check_time:.0f}ms

━━━━━━━━━━━
⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')} TR
"""
            _telegram.send(msg, chat_id=chat_id)
            
        except Exception as e:
            _telegram.send(f"❌ Status hatası: {str(e)}", chat_id=chat_id)

    threading.Thread(target=run_status).start()


def handle_balance_command(chat_id):
    """/balance - Bakiye sorgula"""
    def run_bal():
        try:
            if not _exchange.authenticated:
                return _telegram.send("❌ Bitget API bağlantısı yok", chat_id=chat_id)
            bal = _exchange.get_balance()
            if bal.get('success'):
                msg = f"""
━━━━━━━━━━━
💰 *BAKİYE*
━━━━━━━━━━━

• Toplam: ${bal['total']:,.2f}
• Kullanılabilir: ${bal['free']:,.2f}
• Kullanımda: ${bal.get('used', 0):,.2f}

━━━━━━━━━━━
"""
                _telegram.send(msg, chat_id=chat_id)
            else:
                _telegram.send(f"❌ Hata: {bal.get('error')}", chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("💰 *Sorgulanıyor...*", chat_id=chat_id)
    threading.Thread(target=run_bal).start()


def handle_positions_command(chat_id):
    """/positions - Açık pozisyonlar"""
    def run_pos():
        try:
            if not _exchange.authenticated:
                return _telegram.send("❌ Bitget API bağlantısı yok", chat_id=chat_id)
            pos = _exchange.get_positions()
            if not pos:
                return _telegram.send("ℹ️ Açık pozisyon yok", chat_id=chat_id)
            
            msg = f"━━━━━━━━━━━\n📊 *POZİSYONLAR* ({len(pos)})\n━━━━━━━━━━━\n\n"
            for p in pos:
                s = '🟢' if str(p['side']).upper() == 'LONG' else '🔴'
                pl = float(p.get('unrealized_pnl', 0))
                symbol = p['symbol'].replace('/USDT:USDT', '')
                msg += f"{s} *{symbol}* | P/L: ${pl:+.2f}\n"
            msg += "\n━━━━━━━━━━━"
            _telegram.send(msg, chat_id=chat_id)
        except Exception as e:
            _telegram.send(f"❌ Hata: {e}", chat_id=chat_id)
    
    _telegram.send("📊 *Pozisyonlar çekiliyor...*", chat_id=chat_id)
    threading.Thread(target=run_pos).start()


def handle_help_command(chat_id):
    """/help - Yardım menüsü (v2.7.0 sadeleştirilmiş)"""
    def run_help():
        try:
            changelog_text = ""
            try:
                changelog = _storage.get_changelog()
                if changelog:
                    lines = changelog.split('\n')
                    current_version_lines = []
                    found_first_version = False
                    
                    for line in lines:
                        if line.startswith('## v') and not found_first_version:
                            found_first_version = True
                            current_version_lines.append(line)
                            continue
                        
                        if line.startswith('## v') and found_first_version:
                            break
                        
                        if found_first_version:
                            current_version_lines.append(line)
                    
                    changelog_text = '\n'.join(current_version_lines).strip()
                    
                    if len(changelog_text) > 500:
                        changelog_text = changelog_text[:500] + "\n..."
                        
            except Exception as e:
                logger.warning(f"CHANGELOG fetch error: {e}")
                changelog_text = "CHANGELOG yüklenemedi"
            
            msg = f"""
━━━━━━━━━━━
🤖 *T-TARS v{Config.VERSION}*
━━━━━━━━━━━
Bitget Futures Trading Bot
AI Engine: Grok 4.1

📋 *KOMUTLAR*
━━━━━━━━━━━

📊 *İstatistik*
• /score - Performans raporu
• /reset\\_score - İstatistikleri sıfırla

💰 *Hesap*
• /balance - Bakiye
• /positions - Açık pozisyonlar
• /status - Sistem durumu

🎮 *Kontrol*
• /stopbitget - Trading durdur
• /startbitget - Trading başlat
• /help - Bu menü

━━━━━━━━━━━
📝 *SON GÜNCELLEME*
━━━━━━━━━━━
{changelog_text}
━━━━━━━━━━━
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
    """/stopbitget - Trading durdur"""
    global _trading_enabled
    _trading_enabled = False
    msg = """
━━━━━━━━━━━
🔴 *TRADİNG DURDURULDU*
━━━━━━━━━━━

• Yeni emir açılmayacak
• Grok AI değerlendirme duracak
• Mevcut emirler etkilenmez

Tekrar başlatmak için:
/startbitget
━━━━━━━━━━━
"""
    _telegram.send(msg, chat_id=chat_id)


def handle_startbitget_command(chat_id):
    """/startbitget - Trading başlat"""
    global _trading_enabled
    _trading_enabled = True
    msg = """
━━━━━━━━━━━
🔥 *LIVE MOD AKTİF*
━━━━━━━━━━━

• Otomatik trading başladı
• Grok AI karar verecek
• Setup'lar değerlendirilecek

Durdurmak için:
/stopbitget
━━━━━━━━━━━
"""
    _telegram.send(msg, chat_id=chat_id)


# --------------------------
# HELPER FUNCTIONS
# --------------------------

def is_trading_enabled():
    """Trading aktif mi?"""
    return _trading_enabled
