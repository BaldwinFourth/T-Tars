# -*- coding: utf-8 -*-
"""
T-TARS Telegram Handlers v1.4.9.3
=================================
Telegram bot komut handler'ları.

v1.4.9.3:
- /help mesajı: telegram markdown fix
- /scan mesajı: coinler alt alta emoji ile
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

# Service instances (set by init_handlers)
_telegram = None
_okx = None
_claude = None
_storage = None
_tracking = None


def init_handlers(telegram, okx, claude, storage, tracking):
    """Initialize handlers with service instances"""
    global _telegram, _okx, _claude, _storage, _tracking
    _telegram = telegram
    _okx = okx
    _claude = claude
    _storage = storage
    _tracking = tracking
    logger.info("✅ Telegram handlers initialized")


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
    """Bot durum kontrolü"""
    try:
        import time
        from anthropic import Anthropic
        
        check_start = time.time()
        
        services_status = {
            'telegram': '⏳',
            'okx': '⏳',
            'claude': '⏳',
            'storage': '⏳'
        }
        
        try:
            _telegram.send("🔄 Kontrol yapılıyor...", chat_id=chat_id)
            services_status['telegram'] = '✅'
        except:
            services_status['telegram'] = '❌'
        
        try:
            test_price = _okx.get_current_price('BTC/USDT:USDT')
            services_status['okx'] = f'✅ (${test_price:,.2f})'
        except Exception as e:
            services_status['okx'] = f'❌ ({str(e)[:20]})'
        
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
        
        status_message = f"""
🤖 **T-TARS BOT DURUM KONTROLÜ**

⏰ **Zaman:** {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
⚡ **Response Time:** {check_time:.0f}ms

---

📡 **SERVİSLER:**

• Telegram: {services_status['telegram']}
• OKX Market: {services_status['okx']}
• Claude AI: {services_status['claude']}
• Cloud Storage: {services_status['storage']}

---

📊 **SİSTEM BİLGİLERİ:**

• Bot Version: v{Config.VERSION}
• Model: {Config.CLAUDE_MODEL}
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
    /scan - Manuel market taraması (v1.4.9.2: coin listesi alt alta)
    """
    try:
        # v1.4.9.2: Coinleri alt alta emoji ile listele
        coin_list = '\n'.join([f"🧪 {p.split('/')[0]}" for p in Config.AUTO_SCAN_PAIRS])
        _telegram.send(f"🔍 **Market taraması başlatılıyor...**\n\n{coin_list}\n\n⏳ Tüm timeframe'lerde analiz ediliyor...", chat_id=chat_id)
        
        pairs = Config.AUTO_SCAN_PAIRS
        results = []
        total_new_setups = 0
        
        for pair in pairs:
            try:
                market_data = _okx.get_complete_analysis_data(pair)
                setups = detect_all_trading_setups(pair, market_data)
                
                if setups:
                    # HER SETUP İÇİN AYRI MESAJ GÖNDER
                    for setup in setups:
                        setup_type = setup['type']
                        confidence = setup['confidence']
                        entry_zone = setup.get('entry_zone', 'N/A')
                        stop_loss = setup.get('stop_loss', 'N/A')
                        tp1 = setup.get('tp1', 'N/A')
                        tp2 = setup.get('tp2', 'N/A')
                        detailed_explanation = setup.get('detailed_explanation', setup.get('details', ''))
                        timeframe = setup.get('timeframe', '5m')
                        
                        # TRACKING KAYDI EKLE
                        try:
                            setup_id = _tracking.log_setup({
                                'pair': pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT'),
                                'timestamp': f"{market_data['current_date']} {market_data['current_time']}",
                                'setup_type': setup_type,
                                'confidence': confidence,
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
🎯 Setup: {setup_type}
⏱️ Timeframe: {timeframe.upper()}
{"🔴 Bias: SHORT" if 'SHORT' in setup_type else "🟢 Bias: LONG"}
⚡ Confidence: {confidence}

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
                        _telegram.send_signal(message)
                        total_new_setups += 1
                    
                    results.append(f"✅ {pair.replace('/USDT:USDT', 'USDT')}: {len(setups)} setup(s) found")
                else:
                    results.append(f"ℹ️ {pair.replace('/USDT:USDT', 'USDT')}: No setup")
                    
            except Exception as e:
                logger.error(f"Error scanning {pair}: {e}")
                results.append(f"❌ {pair.replace('/USDT:USDT', 'USDT')}: Error")
        
        # TARAMA SONUÇLARI + AKTİF SETUP LİSTESİ
        try:
            pending_setups = _tracking.get_all_pending_setups()
            
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "📊 **Yeni Setup'lar:**\n"
            summary += "\n".join(results)
            summary += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup bulundu"
            
            if pending_setups and len(pending_setups) > 0:
                summary += f"\n\n---\n📊 **AKTİF SETUP'LAR:** {len(pending_setups)} adet\n"
                for setup in pending_setups[:10]:  # Max 10 göster
                    setup_id = setup['id'][:8].upper()
                    pair = setup['pair']
                    setup_type = setup['setup_type']
                    status = setup['status']
                    status_emoji = '🎯' if status == 'TP1' else '⏳'
                    summary += f"\n{status_emoji} #{setup_id} - {pair} - {setup_type} ({status})"
                
                if len(pending_setups) > 10:
                    summary += f"\n... ve {len(pending_setups) - 10} setup daha"
            else:
                summary += "\n\nℹ️ Aktif setup yok"
            
            summary += f"\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}"
            _telegram.send(summary, chat_id=chat_id)
            
        except Exception as e:
            logger.error(f"❌ Error fetching active setups: {e}")
            summary = "🔍 **TARAMA TAMAMLANDI**\n\n"
            summary += "\n".join(results)
            summary += f"\n\n🎯 **Toplam:** {total_new_setups} yeni setup bulundu"
            summary += f"\n\n⏰ {get_turkey_time().strftime('%H:%M:%S')}"
            _telegram.send(summary, chat_id=chat_id)
        
        logger.info(f"✅ Manual scan completed: {len(pairs)} pairs, {total_new_setups} new setups")
        
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
    /score - Performance raporu (v1.4.3: avg duration eklendi)
    """
    try:
        _telegram.send("📊 İstatistikler hesaplanıyor...", chat_id=chat_id)
        
        # Aggregate stats
        stats = _tracking.get_aggregate_stats()
        
        # Duration formatı
        avg_duration = stats.get('avg_duration_minutes', 0)
        if avg_duration > 0:
            duration_text = f"⏱️ Avg Duration: {avg_duration:.1f} minutes\n"
        else:
            duration_text = ""
        
        score_message = f"""
📊 **T-TARS PERFORMANCE REPORT**

🎯 **Setup İstatistikleri:**
• Total Setups: {stats['total_setups']}
• Winning Trades: {stats['winning_trades']} ({stats['win_rate']:.1f}%)
• Losing Trades: {stats['losing_trades']}

💰 **Balance Tracking:**
• Starting: ${stats['starting_balance']:,.2f}
• Current: ${stats['current_balance']:,.2f}
• Profit: {'+ ' if stats['profit'] >= 0 else ''}{stats['profit_percent']:.1f}% (${stats['profit']:,.2f})

{duration_text}📈 **Best Performer:**
{stats['best_setup_type']}

---
⏱️ Last Updated: {get_turkey_time().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        _telegram.send(score_message, chat_id=chat_id)
        logger.info(f"✅ Score command sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Score command error: {e}")
        _telegram.send(f"❌ İstatistik hatası: {str(e)}", chat_id=chat_id)


def handle_reset_score_command(chat_id):
    """
    /reset_score - Tüm istatistikleri sıfırla (GİZLİ KOMUT - /help'te görünmez)
    """
    try:
        _telegram.send("🔄 İstatistikler sıfırlanıyor...", chat_id=chat_id)
        
        # Tracking service'de reset fonksiyonu çağır
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


def handle_help_command(chat_id):
    """Yardım mesajı"""
    
    help_text = f"""
🤖 **T-TARS Trading Bot v{Config.VERSION}**

📊 /plan - BTCUSDT icin tam analiz
📊 /plan ETHUSDT - Farkli parite
🔍 /scan - Manuel market taramasi
📊 /score - Performance raporu
📡 /status - Bot durum kontrolu
❓ /help - Bu mesaj

🆕 **Desteklenen Coinler:**
BTC, ETH, SOL, LTC, BNB, SHIB, DOGE

⏰ Auto-scan her 3 dakikada calisir
"""
    _telegram.send(help_text, chat_id=chat_id)
