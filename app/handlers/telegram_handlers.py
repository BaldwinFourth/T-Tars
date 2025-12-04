# -*- coding: utf-8 -*-
"""
T-TARS Telegram Handlers v2.0.0
================================
Telegram bot komut handler'ları.

v2.0.0:
- YENİ: /balance - OKX bakiye
- YENİ: /positions - Açık pozisyonlar
- YENİ: /stopokx - Trading durdur
- YENİ: /startokx - Trading başlat
- /score: Top 3 timeframe + Top 3 coin eklendi
- AUTO_SCAN_PAIRS genişletildi (13 coin)
- Beta group kaldırıldı

v1.4.10.2:
- FIX: Duplicate detection - /scan'de aynı setup tekrar oluşturulmaz
- Duplicate ise mesaj gönderilmez
"""

import logging
import json
from datetime import datetime, timezone, timedelta
from app.config import Config
from app.strategies.setup_detector import detect_all_trading_setups

logger = logging.getLogger(__name__)

# Turkey timezone (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))

def get_turkey_time():
    """Get current time in Turkey timezone"""
    return datetime.now(TURKEY_TZ)


def format_price(price):
    """
    Fiyatı dinamik formatta string'e çevir.
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


# Service instances (set by init_handlers)
_telegram = None
_okx = None
_claude = None
_storage = None
_tracking = None

# v2.0.0: Trading flag (runtime control)
_trading_enabled = True


def init_handlers(telegram, okx, claude, storage, tracking):
    """Initialize handlers with service instances"""
    global _telegram, _okx, _claude, _storage, _tracking
    _telegram = telegram
    _okx = okx
    _claude = claude
    _storage = storage
    _tracking = tracking
    logger.info("✅ Telegram handlers initialized (v2.0.0)")


def handle_plan_command(text, chat_id):
    """
    /plan [parite] - İşlem öncesi plan oluştur
    """
    try:
        parts = text.split()
        user_input = parts[1] if len(parts) > 1 else "BTCUSDT"
        
        ticker = Config.get_pair_symbol(user_input)
        
        if ticker not in Config.MANUAL_PAIRS:
            supported = ', '.join([p.split('/')[0] for p in Config.MANUAL_PAIRS[:10]])
            _telegram.send(f"❌ **{user_input}** desteklenmiyor.\n\n✅ Desteklenen: {supported}... ve daha fazlası.\n\n`/help` yazarak tüm listeyi görebilirsin.", chat_id=chat_id)
            return
        
        _telegram.send(f"🔄 **{ticker.replace('/', '').replace(':USDT', '')} analizi bekleniyor...**\n\n⏳ Market data çekiliyor...", chat_id=chat_id)
        
        market_data = _okx.get_complete_analysis_data(ticker)
        template = _storage.get_plan_template()
        
        pdc = market_data['previous_day']
        bias_emoji = "🟢" if pdc['candle_type'] == 'green' else "🔴"
        bias_text = "**LONG**" if pdc['candle_type'] == 'green' else "**SHORT**"
        
        volume_4h = market_data['volume']['4h']
        volume_1h = market_data['volume']['1h']
        volume_15m = market_data['volume']['15m']
        volume_5m = market_data['volume']['5m']
        volume_3m = market_data['volume']['3m']
        
        prompt = f"""
Sen T-TARS trading asistanısın. Aşağıdaki KOMPAKT FORMAT'ta plan oluşturacaksın.

══════════════════════════════════════════
📊 GERÇEK MARKET DATA
══════════════════════════════════════════

**Tarih:** {market_data['current_date']}
**Saat:** {market_data['current_time']}
**Anlık Fiyat:** ${market_data['current_price']:,.2f}

**Önceki Gün Mumu (PDC) - {pdc['date']}:**
- Tip: {pdc['candle_type'].upper()}
- High: ${pdc['high']:,.2f}
- Low: ${pdc['low']:,.2f}
- Volume: {pdc['volume']:,.0f}

**Bias (PDC'ye göre):** {bias_emoji} {bias_text}

**KRİTİK: BIAS'A GÖRE FİBO ENTRY MANTIK:**

🔴 SHORT BIAS (Ters Fibo):
- 0% = PDC HIGH (Direnç) → Entry buraya yakın olmalı
- 100% = PDC LOW (Destek) → TP buraya doğru
- **ENTRY SWEET ZONE:** 23.6% - 38.2% arası (Direnç yakını)
- AI karar ver: Volume, OB, FVG'ye göre en ideal entry noktasını 23.6-38.2 arasından seç
- TP: Extensions 1.272, 1.618 (Destek altı)

🟢 LONG BIAS (Normal Fibo):
- 0% = PDC LOW (Destek) → Entry buraya yakın olmalı
- 100% = PDC HIGH (Direnç) → TP buraya doğru
- **ENTRY SWEET ZONE:** 61.8% - 78.6% arası (Destek yakını)
- AI karar ver: Volume, OB, FVG'ye göre en ideal entry noktasını 61.8-78.6 arasından seç
- TP: 38.2%, 23.6%, 0% (Direnç'e doğru)

══════════════════════════════════════════
📈 ATR(14) - MULTI TIMEFRAME
══════════════════════════════════════════
- 1G: ${market_data['atr']['1d']:,.2f}
- 4S: ${market_data['atr']['4h']:,.2f}
- 1S: ${market_data['atr']['1h']:,.2f}
- 15D: ${market_data['atr']['15m']:,.2f}
- 5D: ${market_data['atr']['5m']:,.2f}
- 3D: ${market_data['atr']['3m']:,.2f}

**Kadircan Stop (Sabit):** ${market_data['stop_loss']['stop_price']:,.2f}

══════════════════════════════════════════
🎯 FIBONACCI SEVİYELERİ
══════════════════════════════════════════
- 0%: ${market_data['fibonacci']['levels']['0.0']:,.2f}
- 23.6%: ${market_data['fibonacci']['levels']['23.6']:,.2f}
- 38.2%: ${market_data['fibonacci']['levels']['38.2']:,.2f}
- 50%: ${market_data['fibonacci']['levels']['50.0']:,.2f}
- 61.8%: ${market_data['fibonacci']['levels']['61.8']:,.2f}
- 78.6%: ${market_data['fibonacci']['levels']['78.6']:,.2f}
- 100%: ${market_data['fibonacci']['levels']['100.0']:,.2f}
- Ext 1.272: ${market_data['fibonacci']['levels']['1.272']:,.2f}
- Ext 1.618: ${market_data['fibonacci']['levels']['1.618']:,.2f}

══════════════════════════════════════════
📊 VOLUME ANALİZİ
══════════════════════════════════════════
**4S:** {volume_4h['spike_ratio']}x, {volume_4h['trend']}, {volume_4h['strength']}
**1S:** {volume_1h['spike_ratio']}x, {volume_1h['trend']}, {volume_1h['strength']}
**15D:** {volume_15m['spike_ratio']}x, {volume_15m['trend']}, {volume_15m['strength']}
**5D:** {volume_5m['spike_ratio']}x, {volume_5m['trend']}, {volume_5m['strength']}
**3D:** {volume_3m['spike_ratio']}x, {volume_3m['trend']}, {volume_3m['strength']}

══════════════════════════════════════════
🧠 SMART MONEY
══════════════════════════════════════════
**OB (4S):** {json.dumps(market_data['smart_money']['order_blocks']['4h'][:3], indent=2)}
**OB (1S):** {json.dumps(market_data['smart_money']['order_blocks']['1h'][:3], indent=2)}
**FVG (4S):** {json.dumps(market_data['smart_money']['fair_value_gaps']['4h'][:2], indent=2)}
**FVG (1S):** {json.dumps(market_data['smart_money']['fair_value_gaps']['1h'][:2], indent=2)}

══════════════════════════════════════════
🎯 GÖREV - KOMPAKT FORMAT
══════════════════════════════════════════

Aşağıdaki **KOMPAKT FORMAT**ta plan oluştur:

```
📊 T-TARS PLAN - {ticker.replace('/', '')}
{market_data['current_date']} {market_data['current_time']}
---
## 📝 GENEL BİLGİ

Parite: {ticker.replace('/', '')}
Anlık Fiyat: ${market_data['current_price']:,.2f}
Bias: {bias_emoji} {bias_text}

---
## 📍 PDC + FİBO ({"Ters - Kırmızı Mum" if pdc['candle_type'] == 'red' else "Normal - Yeşil Mum"})

PDC: {bias_emoji} {pdc['candle_type'].upper()}
High: ${pdc['high']:,.2f}
Low: ${pdc['low']:,.2f}

KRİTİK SEVİYELER:
- 0%: $XXX ({"Direnç" if pdc['candle_type'] == 'red' else "Destek"})
- {"23.6-38.2" if pdc['candle_type'] == 'red' else "61.8-78.6"}%: $XXX (İdeal entry zone) ✅
- 100%: $XXX ({"Destek" if pdc['candle_type'] == 'red' else "Direnç"})
- Ext 1.272: $XXX (TP1)
- Ext 1.618: $XXX (TP2)

{"Mantık: SHORT → Entry direnç yakını, TP destek altı" if pdc['candle_type'] == 'red' else "Mantık: LONG → Entry destek yakını, TP direnç üstü"}

---
## 📊 ATR(14)

- 15D: $XXX ← Entry TF
- (Diğer TF'ler opsiyonel)

---
## 🛡️ STOP

Tars Stop: $XXX
- Hesaplama: 15D ATR ($XXX) × X.X
- Neden: (Volume/volatilite/sweep riski açıkla)

Kadircan Stop: ${market_data['stop_loss']['stop_price']:,.2f}

Tavsiye: Tars (AI güvenli)

---
## 📊 VOLUME

4S: X.Xx TREND 🔴/🟡/🟢 Seviye
1S: X.Xx TREND 🔴/🟡/🟢 Seviye
15D: X.Xx TREND 🔴/🟡/🟢 Seviye

Özet: (Genel durum - spike var mı, beklemeli mi?)

---
## 🧠 SMART MONEY

Order Blocks:
- $XXX (XS Bearish/Bullish, vol ✅/❌) - Açıklama
- En kritik 2-3 OB

Fair Value Gaps:
- $XXX-$XXX (XS, $XXX gap, vol ✅/❌) - Açıklama
- En kritik 1-2 FVG

Kritik: (Önemli uyarı varsa)

---
## 🎯 15D ENTRY

Fiyat: $XXX (Fibo hangi zone'da)
Volume: 🔴/🟡/🟢 (Durum)
OB Risk: (Varsa yakın OB uyarısı)

ENTRY OPTIONS:
A) Conservative: $XXX-$XXX (Fibo seviyesi)
   → (Ne beklemeli)
   
B) Aggressive: $XXX-$XXX
   → (Risk)

Tavsiye: A/B - (Sebep)

---
## 🎁 TP

TP1: $XXX (Ext X.XXX, R:R 1:X.X)
└─ XX% pozisyon kapat
└─ (Destek durumu)

TP2: $XXX (Ext X.XXX, R:R 1:X.X)
└─ XX% trailing
└─ (Volume desteği)

TP3: $XXX (BE sonrası XX%)

---
## ⚠️ KRİTİK UYARILAR

🔴 (En önemli 2-3 risk faktörü)
✅ (Olumlu faktörler)

---
## ✅ KARAR: 🟡/🟢/🔴 (DURUMU)

YAPILACAK:
1-5. (Adımlar)

YAPILMAYACAK:
❌ (3 yasak)

---
📊 T-TARS AI | Real-Time Data
```

**KRİTİK KURALLAR:**

1. **SHORT Entry:** 23.6-38.2% arası sweet zone belirle (direnç yakını)
2. **LONG Entry:** 61.8-78.6% arası sweet zone belirle (destek yakını)
3. **Tars Stop:** AI karar ver (TF, ATR, multiplier, sebep)
4. **Volume:** Her analiz volume ile değerlendir
5. **Kompakt:** Max 120 satır, 1 Telegram mesajı
6. **Emoji:** 🔴🟢🟡 kullan
7. **Gerçek fiyat:** İcat etme!

Sadece yukarıdaki formatı doldur, ekstra açıklama yapma!
"""
        
        result = _claude.analyze(prompt)
        
        message = f"📊 *T-TARS PLAN - {ticker.replace('/', '')}*\n\n{result['text']}"
        
        if len(message) > 4000:
            _telegram.send(message[:4000] + "...", chat_id=chat_id)
            _telegram.send("...(devam)\n" + message[4000:8000], chat_id=chat_id)
            if len(message) > 8000:
                _telegram.send("...(devam)\n" + message[8000:], chat_id=chat_id)
        else:
            _telegram.send(message, chat_id=chat_id)
        
        logger.info(f"✅ Plan sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Plan command error: {e}")
        
        error_msg = str(e).lower()
        if 'rate' in error_msg or 'limit' in error_msg:
            _telegram.send(f"❌ **Rate Limit:** Çok fazla istek. 1 dakika bekle ve tekrar dene.", chat_id=chat_id)
        elif 'network' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
            _telegram.send(f"❌ **Network Hatası:** Bağlantı sorunu. Tekrar dene.", chat_id=chat_id)
        elif 'token' in error_msg or 'api' in error_msg:
            _telegram.send(f"❌ **API Hatası:** Claude veya OKX servisi yanıt vermiyor. Daha sonra tekrar dene.", chat_id=chat_id)
        else:
            _telegram.send(f"❌ **Bilinmeyen Hata:** {str(e)[:100]}\n\nTekrar dene veya destek için bildir.", chat_id=chat_id)


def handle_execute_command(text, chat_id):
    """
    /execute [parite] - Aktif işlem durumu (deprecated - kept for backward compatibility)
    """
    try:
        parts = text.split()
        ticker = parts[1] if len(parts) > 1 else "BTCUSDT"
        
        template = _storage.get_execute_template()
        
        prompt = f"""
Sen T-TARS trading asistanısın. **T-Tars Execute** şablonunu doldur.

**ŞABLON:**
{template}

**GÖREV:**
1. {ticker} için aktif işlem durumunu raporla
2. Entry scout varsa listele
3. Gerçekleşen işlemleri kaydet
4. Senaryo analizi yap

Sadece doldurulmuş şablonu döndür.
"""
        
        result = _claude.analyze(prompt)
        message = f"⚡ *T-TARS EXECUTE - {ticker}*\n\n{result['text']}"
        
        if len(message) > 4000:
            _telegram.send(message[:4000] + "...", chat_id=chat_id)
            _telegram.send("...(devam)\n" + message[4000:], chat_id=chat_id)
        else:
            _telegram.send(message, chat_id=chat_id)
        
        logger.info(f"✅ Execute sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Execute command error: {e}")
        _telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)


def handle_log_command(text, chat_id):
    """
    /log - Tüm işlemlerin özet tablosu (deprecated - kept for backward compatibility)
    """
    try:
        template = _storage.get_log_template()
        
        prompt = f"""
Sen T-TARS trading asistanısın. **T-Tars Trade Log** şablonunu doldur.

**ŞABLON:**
{template}

**GÖREV:**
1. Son işlemlerin özet tablosunu oluştur
2. HTF ve LTF setup'ları özetle
3. P&L hesapla

Sadece doldurulmuş şablonu döndür.
"""
        
        result = _claude.analyze(prompt)
        message = f"📋 *T-TARS TRADE LOG*\n\n{result['text']}"
        
        if len(message) > 4000:
            _telegram.send(message[:4000] + "...", chat_id=chat_id)
            _telegram.send("...(devam)\n" + message[4000:], chat_id=chat_id)
        else:
            _telegram.send(message, chat_id=chat_id)
        
        logger.info(f"✅ Log sent: {result['input_tokens']}→{result['output_tokens']} tokens")
        
    except Exception as e:
        logger.error(f"❌ Log command error: {e}")
        _telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)


def handle_status_command(chat_id):
    """
    Bot durum kontrolü
    v2.0.0: OKX API durumu ve Trading flag eklendi
    """
    try:
        import time
        from anthropic import Anthropic
        
        check_start = time.time()
        
        services_status = {
            'telegram': '⏳',
            'okx_market': '⏳',
            'okx_api': '⏳',
            'claude': '⏳',
            'storage': '⏳'
        }
        
        try:
            _telegram.send("🔄 Kontrol yapılıyor...", chat_id=chat_id)
            services_status['telegram'] = '✅'
        except:
            services_status['telegram'] = '❌'
        
        # OKX Market Data (fiyat)
        try:
            test_price = _okx.get_current_price('BTC/USDT:USDT')
            services_status['okx_market'] = f'✅ (${test_price:,.2f})'
        except Exception as e:
            services_status['okx_market'] = f'❌ ({str(e)[:20]})'
        
        # v2.0.0: OKX API (authenticated)
        try:
            if _okx.authenticated:
                balance = _okx.get_balance()
                if balance.get('success'):
                    services_status['okx_api'] = f'✅ (${balance["total"]:,.2f})'
                else:
                    services_status['okx_api'] = '❌ (balance error)'
            else:
                services_status['okx_api'] = '⚠️ (no auth)'
        except Exception as e:
            services_status['okx_api'] = f'❌ ({str(e)[:20]})'
        
        try:
            client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            services_status['claude'] = '✅'
        except Exception as e:
            services_status['claude'] = f'❌ ({str(e)[:20]})'
        
        try:
            test_template = _storage.get_plan_template()
            services_status['storage'] = '✅'
        except Exception as e:
            services_status['storage'] = f'❌ ({str(e)[:20]})'
        
        check_time = (time.time() - check_start) * 1000
        
        # v2.0.0: Trading status
        trading_status = '🟢 AKTİF' if _trading_enabled else '🔴 DURDURULDU'
        
        status_message = f"""
🤖 **T-TARS BOT DURUM KONTROLÜ**

⏰ **Zaman:** {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
⚡ **Response Time:** {check_time:.0f}ms

---

📡 **SERVİSLER:**

• Telegram: {services_status['telegram']}
• OKX Market: {services_status['okx_market']}
• OKX API: {services_status['okx_api']}
• Claude AI: {services_status['claude']}
• Cloud Storage: {services_status['storage']}

---

📊 **SİSTEM BİLGİLERİ:**

• Bot Version: v{Config.VERSION}
• Model: {Config.CLAUDE_MODEL}
• Trading: {trading_status}
• Environment: Google Cloud Run
• Region: us-central1

---

✅ **BOT AKTİF VE HAZIR!**

Komutlar için: /help
"""
        
        _telegram.send(status_message, chat_id=chat_id)
        logger.info(f"✅ Check command completed in {check_time:.0f}ms")
        
    except Exception as e:
        logger.error(f"❌ Check command error: {e}")
        _telegram.send(f"❌ Kontrol hatası: {str(e)}", chat_id=chat_id)


def handle_scan_command(chat_id):
    """
    /scan - Manuel market taraması
    v1.4.10.2: Duplicate detection - aynı setup tekrar oluşturulmaz
    """
    try:
        coin_list = '\n'.join([f"🧪 {p.split('/')[0]}" for p in Config.AUTO_SCAN_PAIRS])
        _telegram.send(f"🔍 **Market taraması başlatılıyor...**\n\n{coin_list}\n\n⏳ Tüm timeframe'lerde analiz ediliyor...", chat_id=chat_id)
        
        pairs = Config.AUTO_SCAN_PAIRS
        results = []
        total_new_setups = 0
        skipped_duplicates = 0
        
        for pair in pairs:
            try:
                market_data = _okx.get_complete_analysis_data(pair)
                setups = detect_all_trading_setups(pair, market_data)
                
                if setups:
                    for setup in setups:
                        setup_type = setup['type']
                        confidence = setup['confidence']
                        entry_zone = setup.get('entry_zone', 'N/A')
                        stop_loss = setup.get('stop_loss', 'N/A')
                        tp1 = setup.get('tp1', 'N/A')
                        tp2 = setup.get('tp2', 'N/A')
                        timeframe = setup.get('timeframe', '5m')
                        
                        # v1.4.10.0: entry_price - OB/FVG mid-point
                        entry_price = setup.get('entry_price', setup.get('current_price', market_data['current_price']))
                        
                        # TRACKING KAYDI
                        try:
                            setup_id = _tracking.log_setup({
                                'pair': pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT'),
                                'timestamp': f"{market_data['current_date']} {market_data['current_time']}",
                                'setup_type': setup_type,
                                'confidence': confidence,
                                'timeframe': timeframe,
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
                            
                            # v1.4.10.2: Duplicate ise None döner, mesaj gönderme
                            if setup_id is None:
                                skipped_duplicates += 1
                                continue
                            
                            logger.info(f"✅ Setup #{setup_id} logged (entry: {format_price(entry_price)})")
                        except Exception as track_error:
                            logger.error(f"❌ Tracking failed: {track_error}")
                            setup_id = "N/A"
                        
                        # v2.0.1: SETUP DETECTED mesajı GÖNDERME - sessiz çalış
                        # Sadece tracking'e kaydet
                        logger.info(f"✅ Setup #{setup_id} logged [silent]")
                        total_new_setups += 1
                    
                    results.append(f"✅ {pair.replace('/USDT:USDT', 'USDT')}: {len(setups)} setup(s) found")
                else:
                    results.append(f"ℹ️ {pair.replace('/USDT:USDT', 'USDT')}: No setup")
                    
            except Exception as e:
                logger.error(f"Error scanning {pair}: {e}")
                results.append(f"❌ {pair.replace('/USDT:USDT', 'USDT')}: Error")
        
        # TARAMA SONUÇLARI
        try:
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "📊 **Yeni Setup'lar:**\n"
            summary += "\n".join(results)
            summary += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup bulundu"
            
            # v2.0.1: OKX'ten GERÇEK pozisyonları çek
            try:
                positions = _okx.get_positions() if _okx.authenticated else []
                
                if positions and len(positions) > 0:
                    summary += f"\n\n---\n📊 **AÇIK POZİSYONLAR:** {len(positions)} adet\n"
                    
                    total_pnl = 0
                    for pos in positions:
                        symbol = pos['symbol'].replace('/USDT:USDT', '').replace('/USDT', '')
                        side = pos['side'].upper()
                        side_emoji = '🟢' if side == 'LONG' else '🔴'
                        
                        entry = float(pos.get('entry_price', 0))
                        pnl = float(pos.get('unrealized_pnl', 0))
                        pnl_pct = float(pos.get('percentage', 0))
                        leverage = pos.get('leverage', 1)
                        
                        total_pnl += pnl
                        
                        pnl_emoji = '💚' if pnl >= 0 else '❤️'
                        
                        summary += f"\n{side_emoji} {symbol} {side} x{leverage} | {pnl_emoji} ${pnl:+.2f} ({pnl_pct:+.1f}%)"
                    
                    pnl_emoji = '💚' if total_pnl >= 0 else '❤️'
                    summary += f"\n\n{pnl_emoji} **Toplam P/L:** ${total_pnl:+.2f}"
                else:
                    summary += "\n\nℹ️ Açık pozisyon yok"
                    
            except Exception as pos_error:
                logger.error(f"❌ Error fetching OKX positions: {pos_error}")
                summary += "\n\n⚠️ OKX pozisyonları alınamadı"
            
            summary += f"\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}"
            _telegram.send(summary, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"❌ Error sending scan summary: {e}")
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "\n".join(results)
            summary += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup bulundu"
            if skipped_duplicates > 0:
                summary += f" ({skipped_duplicates} duplicate atlandı)"
            summary += f"\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}"
            _telegram.send(summary, chat_id=chat_id)
        
        logger.info(f"✅ Manual scan completed: {len(pairs)} pairs, {total_new_setups} new setups, {skipped_duplicates} duplicates skipped")
        
    except Exception as e:
        logger.error(f"❌ Scan command error: {e}")
        
        error_msg = str(e).lower()
        if 'rate' in error_msg or 'limit' in error_msg:
            _telegram.send(f"❌ **Rate Limit:** Çok fazla tarama. 1 dakika bekle.", chat_id=chat_id)
        elif 'network' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
            _telegram.send(f"❌ **Network Hatası:** OKX bağlantı sorunu. Tekrar dene.", chat_id=chat_id)
        else:
            _telegram.send(f"❌ **Tarama Hatası:** {str(e)[:100]}", chat_id=chat_id)


def handle_score_command(chat_id):
    """
    /score - Performance raporu
    v2.0.0: Top 3 timeframe + Top 3 coin eklendi
    """
    try:
        _telegram.send("📊 İstatistikler hesaplanıyor...", chat_id=chat_id)
        
        stats = _tracking.get_aggregate_stats()
        
        last_reset = _tracking.get_last_reset_time()
        if last_reset:
            try:
                reset_dt = datetime.fromisoformat(last_reset)
                reset_text = f"\n🔄 Son Reset: {reset_dt.strftime('%Y-%m-%d %H:%M')}"
            except:
                reset_text = f"\n🔄 Son Reset: {last_reset[:16]}"
        else:
            reset_text = ""
        
        avg_duration = stats.get('avg_duration_minutes', 0)
        duration_text = f"⏱️ Avg Duration: {avg_duration:.1f} minutes\n" if avg_duration > 0 else ""
        
        # v2.0.0: Top 3 Timeframe (win rate'e göre sıralı)
        tf_breakdown = stats.get('timeframe_breakdown', {})
        top_tf_text = ""
        if tf_breakdown:
            # Win rate'e göre sırala (min 3 completed trade olanlar)
            tf_sorted = []
            for tf, data in tf_breakdown.items():
                completed = data['wins'] + data['losses']
                if completed >= 3:
                    tf_sorted.append({
                        'tf': tf,
                        'wins': data['wins'],
                        'losses': data['losses'],
                        'win_rate': data['win_rate'],
                        'completed': completed
                    })
            
            tf_sorted.sort(key=lambda x: x['win_rate'], reverse=True)
            
            if tf_sorted:
                top_tf_text = "\n🏆 **Top 3 Timeframe:**\n"
                for i, item in enumerate(tf_sorted[:3], 1):
                    medal = '🥇' if i == 1 else ('🥈' if i == 2 else '🥉')
                    top_tf_text += f"{medal} {item['tf']}: {item['win_rate']:.0f}% ({item['wins']}W/{item['losses']}L)\n"
        
        # v2.0.0: Top 3 Coin (win rate'e göre sıralı)
        coin_breakdown = stats.get('coin_breakdown', {})
        top_coin_text = ""
        if coin_breakdown:
            coin_sorted = []
            for coin, data in coin_breakdown.items():
                completed = data['wins'] + data['losses']
                if completed >= 3:
                    coin_sorted.append({
                        'coin': coin,
                        'wins': data['wins'],
                        'losses': data['losses'],
                        'win_rate': data['win_rate'],
                        'completed': completed
                    })
            
            coin_sorted.sort(key=lambda x: x['win_rate'], reverse=True)
            
            if coin_sorted:
                top_coin_text = "\n💰 **Top 3 Coin:**\n"
                for i, item in enumerate(coin_sorted[:3], 1):
                    medal = '🥇' if i == 1 else ('🥈' if i == 2 else '🥉')
                    top_coin_text += f"{medal} {item['coin']}: {item['win_rate']:.0f}% ({item['wins']}W/{item['losses']}L)\n"
        
        total_setups = stats['total_setups']
        winning = stats['winning_trades']
        losing = stats['losing_trades']
        pending = stats.get('pending_setups', 0)
        win_rate = stats['win_rate']
        loss_rate = stats.get('loss_rate', 0)
        pending_rate = stats.get('pending_rate', 0)
        
        score_message = f"""
📊 **T-TARS PERFORMANCE REPORT**

🎯 **Setup İstatistikleri:**
• Total Setups: {total_setups}
• Winning Trades: {winning} ({win_rate:.1f}%)
• Losing Trades: {losing} ({loss_rate:.1f}%)
• Aktif Setuplar: {pending} ({pending_rate:.1f}%)

💰 **Balance Tracking:**
• Starting: ${stats['starting_balance']:,.2f}
• Current: ${stats['current_balance']:,.2f}
• Profit: {'+ ' if stats['profit'] >= 0 else ''}{stats['profit_percent']:.1f}% (${stats['profit']:,.2f})

{duration_text}📈 **Best Performer:**
{stats['best_setup_type']}
{top_tf_text}{top_coin_text}{reset_text}
---
⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        _telegram.send(score_message, chat_id=chat_id)
        logger.info(f"✅ Score command sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Score command error: {e}")
        _telegram.send(f"❌ İstatistik hatası: {str(e)}", chat_id=chat_id)


def handle_reset_score_command(chat_id):
    """
    /reset_score - Tüm istatistikleri sıfırla (GİZLİ KOMUT)
    """
    try:
        _telegram.send("🔄 İstatistikler sıfırlanıyor...", chat_id=chat_id)
        
        result = _tracking.reset_all_tracking()
        
        if result:
            reset_message = f"""
✅ **İSTATİSTİKLER SIFIRLANDI**

🗑️ Tüm setup'lar temizlendi
💰 Balance: $1,000.00 (başlangıç)
📊 Win Rate: 0%
🎯 Total Setups: 0

⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}

_Yeni setup'lar /scan ile oluşturulabilir._
"""
            _telegram.send(reset_message, chat_id=chat_id)
            logger.info(f"✅ Stats reset by chat_id: {chat_id}")
        else:
            _telegram.send("❌ Sıfırlama başarısız. Tekrar deneyin.", chat_id=chat_id)
        
    except Exception as e:
        logger.error(f"❌ Reset score error: {e}")
        _telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)


# ============================================
# v2.0.0: OKX API COMMANDS
# ============================================

def handle_balance_command(chat_id):
    """
    /balance - OKX hesap bakiyesi
    """
    try:
        _telegram.send("💰 OKX bakiye sorgulanıyor...", chat_id=chat_id)
        
        # OKX API'den bakiye al
        if not _okx.authenticated:
            _telegram.send("❌ OKX API bağlantısı yok. API key'leri kontrol edin.", chat_id=chat_id)
            return
        
        balance = _okx.get_balance()
        
        if not balance.get('success'):
            _telegram.send(f"❌ Bakiye alınamadı: {balance.get('error', 'Unknown')}", chat_id=chat_id)
            return
        
        message = f"""
💰 **OKX HESAP BAKİYESİ**

💵 **USDT:**
• Total: ${balance['total']:,.2f}
• Free: ${balance['free']:,.2f}
• Used: ${balance['used']:,.2f}

⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
        _telegram.send(message, chat_id=chat_id)
        logger.info(f"✅ Balance command sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Balance command error: {e}")
        _telegram.send(f"❌ Bakiye hatası: {str(e)}", chat_id=chat_id)


def handle_positions_command(chat_id):
    """
    /positions - Açık pozisyonları listele
    """
    try:
        _telegram.send("📊 OKX pozisyonlar sorgulanıyor...", chat_id=chat_id)
        
        if not _okx.authenticated:
            _telegram.send("❌ OKX API bağlantısı yok. API key'leri kontrol edin.", chat_id=chat_id)
            return
        
        positions = _okx.get_positions()
        
        if not positions:
            _telegram.send("ℹ️ Açık pozisyon yok.", chat_id=chat_id)
            return
        
        message = f"📊 **AÇIK POZİSYONLAR** ({len(positions)} adet)\n\n"
        
        total_pnl = 0
        for pos in positions:
            symbol = pos['symbol'].replace('/USDT:USDT', '').replace('/USDT', '')
            side = pos['side'].upper()
            side_emoji = '🟢' if side == 'LONG' else '🔴'
            
            entry = pos.get('entry_price', 0)
            mark = pos.get('mark_price', 0)
            pnl = pos.get('unrealized_pnl', 0)
            pnl_pct = pos.get('percentage', 0)
            contracts = pos.get('contracts', 0)
            leverage = pos.get('leverage', 1)
            
            total_pnl += float(pnl) if pnl else 0
            
            pnl_emoji = '💚' if float(pnl or 0) >= 0 else '❤️'
            
            message += f"{side_emoji} **{symbol}** {side} x{leverage}\n"
            message += f"   📍 Entry: ${float(entry):,.2f}\n"
            message += f"   📈 Mark: ${float(mark):,.2f}\n"
            message += f"   {pnl_emoji} P/L: ${float(pnl):+,.2f} ({float(pnl_pct):+.2f}%)\n\n"
        
        pnl_emoji = '💚' if total_pnl >= 0 else '❤️'
        message += f"---\n{pnl_emoji} **Toplam P/L:** ${total_pnl:+,.2f}\n"
        message += f"⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}"
        
        _telegram.send(message, chat_id=chat_id)
        logger.info(f"✅ Positions command sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Positions command error: {e}")
        _telegram.send(f"❌ Pozisyon hatası: {str(e)}", chat_id=chat_id)


def handle_stopokx_command(chat_id):
    """
    /stopokx - Trading'i durdur (yeni pozisyon açmaz)
    """
    global _trading_enabled
    
    try:
        _trading_enabled = False
        
        message = f"""
🔴 **TRADİNG DURDURULDU**

⛔ Bot artık yeni pozisyon AÇMAYACAK
📊 Mevcut pozisyonlar etkilenmez
🔍 Analiz ve tarama devam eder

Tekrar başlatmak için: /startokx

⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
        _telegram.send(message, chat_id=chat_id)
        logger.warning(f"🔴 Trading DISABLED by chat_id: {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ StopOKX command error: {e}")
        _telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)


def handle_startokx_command(chat_id):
    """
    /startokx - Trading'i başlat (yeni pozisyon açabilir)
    """
    global _trading_enabled
    
    try:
        _trading_enabled = True
        
        message = f"""
🟢 **TRADİNG BAŞLATILDI**

✅ Bot artık yeni pozisyon AÇABİLİR
📊 Risk limitleri aktif
🔍 Setup'lar değerlendirilecek

Durdurmak için: /stopokx

⏰ {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
        _telegram.send(message, chat_id=chat_id)
        logger.info(f"🟢 Trading ENABLED by chat_id: {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ StartOKX command error: {e}")
        _telegram.send(f"❌ Hata: {str(e)}", chat_id=chat_id)


def is_trading_enabled():
    """Trading durumunu kontrol et"""
    return _trading_enabled


def execute_trade_for_setup(setup_data, chat_id=None):
    """
    v2.0.0: Setup için OKX'te işlem aç
    
    Args:
        setup_data: Setup bilgileri (pair, direction, entry, stop, tp1, tp2, etc.)
        chat_id: Telegram chat ID for notifications
    
    Returns:
        dict: Order result or None
    """
    try:
        pair = setup_data.get('pair', 'UNKNOWN')
        direction = setup_data.get('direction', 'LONG')
        entry_price = setup_data.get('entry_price', 0)
        stop_price = setup_data.get('stop_price', 0)
        tp1_price = setup_data.get('tp1_price', 0)
        tp2_price = setup_data.get('tp2_price', 0)
        setup_type = setup_data.get('setup_type', 'Unknown')
        timeframe = setup_data.get('timeframe', 'N/A')
        setup_id = setup_data.get('setup_id', 'N/A')
        
        # 1. Trading enabled kontrolü
        if not _trading_enabled:
            logger.info(f"⏸️ Trading disabled, skipping order for {pair}")
            return {'success': False, 'reason': 'trading_disabled'}
        
        # 2. OKX authenticated kontrolü
        if not _okx.authenticated:
            logger.warning(f"❌ OKX not authenticated, cannot place order")
            return {'success': False, 'reason': 'not_authenticated'}
        
        # 3. Paritede mevcut pozisyon kontrolü
        existing_positions = _okx.get_positions(pair)
        if existing_positions and len(existing_positions) > 0:
            logger.info(f"⚠️ Position already exists for {pair}, skipping new order")
            if chat_id:
                _telegram.send(f"⚠️ {pair}: Mevcut pozisyon var, yeni işlem açılmadı.", chat_id=chat_id)
            return {'success': False, 'reason': 'position_exists', 'existing': existing_positions[0]}
        
        # 4. Risk hesaplama
        balance = _okx.get_balance()
        if not balance.get('success'):
            logger.error(f"❌ Could not get balance for risk calculation")
            return {'success': False, 'reason': 'balance_error'}
        
        available_balance = balance.get('free', 0)
        
        # Risk %1-2 (Config'den al)
        risk_percent = Config.RISK_PER_TRADE_MAX / 100  # 2%
        risk_amount = available_balance * risk_percent
        
        # Position size hesapla (stop loss mesafesine göre)
        if entry_price > 0 and stop_price > 0:
            stop_distance_percent = abs(entry_price - stop_price) / entry_price
            if stop_distance_percent > 0:
                position_size_usd = risk_amount / stop_distance_percent
            else:
                position_size_usd = risk_amount * 10  # Default leverage assumption
        else:
            position_size_usd = risk_amount * 10
        
        # Max position size kontrolü
        max_position = Config.MAX_POSITION_SIZE
        if position_size_usd > max_position:
            position_size_usd = max_position
            logger.info(f"📊 Position size capped at ${max_position}")
        
        # Min position size kontrolü
        if position_size_usd < 5:
            logger.warning(f"⚠️ Position size too small: ${position_size_usd:.2f}")
            return {'success': False, 'reason': 'position_too_small'}
        
        # 5. Order side belirle
        side = 'buy' if direction.upper() == 'LONG' else 'sell'
        
        # 6. OKX symbol format
        okx_symbol = pair.replace('USDT', '/USDT:USDT') if 'USDT' in pair and '/' not in pair else pair
        
        # 7. Amount hesapla (kontrat sayısı)
        # Position size USD / entry price = coin amount
        if entry_price > 0:
            amount = position_size_usd / entry_price
        else:
            logger.error(f"❌ Invalid entry price: {entry_price}")
            return {'success': False, 'reason': 'invalid_entry_price'}
        
        logger.info(f"🚀 Placing order: {okx_symbol} {side.upper()} ${position_size_usd:.2f} (amount: {amount})")
        
        # 8. Order gönder (TP/SL ile)
        order_result = _okx.place_order_with_tp_sl(
            symbol=okx_symbol,
            side=side,
            amount=amount,
            tp_price=tp1_price,  # İlk hedef TP1
            sl_price=stop_price
        )
        
        if order_result and order_result.get('success'):
            order_id = order_result.get('order_id', 'N/A')
            
            # Telegram bildirimi
            trade_message = f"""
🚀 **ORDER PLACED** ✅

📊 Parite: {pair}
🎯 Setup: {setup_type}
⏱️ TF: {timeframe}
{'🟢 LONG' if direction.upper() == 'LONG' else '🔴 SHORT'}

💰 Size: ${position_size_usd:.2f}
📍 Entry: ${entry_price:,.4f}
🛡️ Stop: ${stop_price:,.4f}
🎁 TP1: ${tp1_price:,.4f}

📋 Order ID: {order_id[:16]}...

⏰ {get_turkey_time().strftime('%H:%M:%S')}
"""
            
            target_chat = chat_id or Config.TELEGRAM_CHAT_ID
            _telegram.send(trade_message, chat_id=target_chat)
            
            logger.info(f"✅ Order placed successfully: {order_id}")
            return {
                'success': True,
                'order_id': order_id,
                'symbol': okx_symbol,
                'side': side,
                'amount': amount,
                'position_size_usd': position_size_usd
            }
        else:
            error_msg = order_result.get('error', 'Unknown error') if order_result else 'No response'
            logger.error(f"❌ Order failed: {error_msg}")
            
            if chat_id:
                _telegram.send(f"❌ Order başarısız: {error_msg}", chat_id=chat_id)
            
            return {'success': False, 'reason': 'order_failed', 'error': error_msg}
        
    except Exception as e:
        logger.error(f"❌ Execute trade error: {e}")
        return {'success': False, 'reason': 'exception', 'error': str(e)}


def handle_help_command(chat_id):
    """
    Yardım mesajı
    """
    try:
        version_features_list = []
        try:
            version_features_list = _storage.parse_version_features(Config.VERSION)
        except Exception as e:
            logger.warning(f"Could not parse CHANGELOG: {e}")
            version_features_list = []
        
        help_text = f"""
🤖 **T-TARS Trading Bot v{Config.VERSION}**

📊 /plan - BTCUSDT icin tam analiz
📊 /plan ETHUSDT - Farkli parite
🔍 /scan - Manuel market taramasi
📊 /score - Performance raporu
📡 /status - Bot durum kontrolu
❓ /help - Bu mesaj

💰 **OKX Komutlari:**
💵 /balance - Hesap bakiyesi
📊 /positions - Acik pozisyonlar
🔴 /stopokx - Trading durdur
🟢 /startokx - Trading baslat

🆕 **Desteklenen Coinler (13):**
BTC, ETH, SOL, BNB, XRP, AVAX
LTC, TRX, DOGE, SHIB, PEPE
TRUMP, JUP

⏰ Auto-scan her 3 dakikada calisir
"""
        
        if version_features_list and len(version_features_list) > 0:
            features_text = '\n'.join(version_features_list)
            help_text += f"""
---
📋 **v{Config.VERSION} Degisiklikler:**

{features_text}
"""
        
        _telegram.send(help_text, chat_id=chat_id)
        logger.info(f"✅ Help command sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Help command error: {e}")
        fallback_help = f"""
🤖 **T-TARS Trading Bot v{Config.VERSION}**

📊 /plan - BTCUSDT icin tam analiz
📊 /plan ETHUSDT - Farkli parite
🔍 /scan - Manuel market taramasi
📊 /score - Performance raporu
📡 /status - Bot durum kontrolu
❓ /help - Bu mesaj

💰 **OKX Komutlari:**
💵 /balance - Hesap bakiyesi
📊 /positions - Acik pozisyonlar
🔴 /stopokx - Trading durdur
🟢 /startokx - Trading baslat

🆕 **Desteklenen Coinler (13):**
BTC, ETH, SOL, BNB, XRP, AVAX
LTC, TRX, DOGE, SHIB, PEPE
TRUMP, JUP
"""
        _telegram.send(fallback_help, chat_id=chat_id)
