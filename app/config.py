# -*- coding: utf-8 -*-
"""
T-TARS Configuration v2.4.13
============================

v2.4.13:
- REMOVED: XAUTUSDT çıkarıldı (yüksek fonlama oranı)
- ADDED: LTCUSDT, SUIUSDT, ADAUSDT, AVAXUSDT, HYPEUSDT eklendi
- Toplam: 14 coin

v2.4.8:
- REMOVED: BTCUSDT auto-scan'den çıkarıldı
- ADDED: NIGHTUSDT, BCHUSDT, DOGEUSDT eklendi

"""

import os
from pathlib import Path


class Config:
    """T-TARS Configuration v2.4.13"""
    
    # Get base directory
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    # Auto-load version from VERSION file
    VERSION_FILE = BASE_DIR / "VERSION"
    try:
        with open(VERSION_FILE, 'r') as f:
            VERSION = f.read().strip()
    except FileNotFoundError:
        raise Exception("❌ VERSION dosyası bulunamadı!")
    
    # ============================================
    # TELEGRAM
    # ============================================
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    @staticmethod
    def get_allowed_chats():
        """Get allowed chat IDs - sadece ana chat"""
        return [Config.TELEGRAM_CHAT_ID]
    
    # ============================================
    # BITGET API
    # ============================================
    BITGET_API_KEY = os.getenv('BITGET_API_KEY', '')
    BITGET_SECRET_KEY = os.getenv('BITGET_SECRET_KEY', '')
    BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE', '')
    
    BITGET_TRADING_ENABLED = os.getenv('BITGET_TRADING_ENABLED', 'true').lower() == 'true'
    DEFAULT_LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '20'))
    
    # ============================================
    # CLAUDE AI
    # ============================================
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
    THINKING_BUDGET = int(os.getenv('THINKING_BUDGET', '10000'))
    
    # ============================================
    # CLOUD STORAGE
    # ============================================
    BUCKET_NAME = os.getenv('BUCKET_NAME', 'tars-trading-templates')
    BUCKET_NAME_DATA = os.getenv('BUCKET_NAME_DATA', 'tars-trading-data')
    
    PLAN_TEMPLATE = 'T-Tars Plan.md'
    EXECUTE_TEMPLATE = 'T-Tars Execute Log.md'
    LOG_TEMPLATE = 'T-Tars Trade Log.md'
    
    # ============================================
    # TIMEFRAMES
    # ============================================
    TIMEFRAMES = ['1h', '15m']
    
    # ============================================
    # TRADING PAIRS (v2.4.13 - 14 coin)
    # ============================================
    
    AUTO_SCAN_PAIRS = [
        'ETH/USDT:USDT',   # Ethereum
        'SOL/USDT:USDT',   # Solana
        'BNB/USDT:USDT',   # BNB
        'JUP/USDT:USDT',   # Jupiter
        'XRP/USDT:USDT',   # Ripple
        'TRX/USDT:USDT',   # Tron
        'NIGHT/USDT:USDT', # Night
        'BCH/USDT:USDT',   # Bitcoin Cash
        'DOGE/USDT:USDT',  # Dogecoin
        'LTC/USDT:USDT',   # Litecoin (yeni)
        'SUI/USDT:USDT',   # Sui (yeni)
        'ADA/USDT:USDT',   # Cardano (yeni)
        'AVAX/USDT:USDT',  # Avalanche (yeni)
        'HYPE/USDT:USDT',  # Hype (yeni)
    ]
    
    MANUAL_PAIRS = [
        'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT',
        'LTC/USDT:USDT', 'XRP/USDT:USDT', 'DOGE/USDT:USDT', 
        'TRUMP/USDT:USDT', 'JUP/USDT:USDT', 'AVAX/USDT:USDT', 
        'SHIB/USDT:USDT', 'BNB/USDT:USDT', 'HYPE/USDT:USDT', 
        'TRX/USDT:USDT', 'SUI/USDT:USDT', 'PEPE/USDT:USDT', 
        'PUMP/USDT:USDT', 'BCH/USDT:USDT', 'ADA/USDT:USDT',
        'XAUT/USDT:USDT', 'FLOKI/USDT:USDT', 'NIGHT/USDT:USDT',
    ]
    
    # ============================================
    # RISK MANAGEMENT
    # ============================================
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '1.0'))
    STOP_DISTANCE_MIN = float(os.getenv('STOP_DISTANCE_MIN', '0.008'))
    STOP_DISTANCE_MAX = float(os.getenv('STOP_DISTANCE_MAX', '0.025'))
    MARGIN_MIN_PERCENT = float(os.getenv('MARGIN_MIN_PERCENT', '1.0'))
    MARGIN_MAX_PERCENT = float(os.getenv('MARGIN_MAX_PERCENT', '2.0'))
    CLOSE_ORDER_TYPE = os.getenv('CLOSE_ORDER_TYPE', 'limit')
    CLOSE_SLIPPAGE_PCT = float(os.getenv('CLOSE_SLIPPAGE_PCT', '0.002'))
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '500'))
    MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '200'))
    
    # ============================================
    # CACHE & MONITORING
    # ============================================
    MARKET_CACHE_TTL = int(os.getenv('MARKET_CACHE_TTL', '1200'))
    MONITOR_INTERVAL_MINUTES = int(os.getenv('MONITOR_INTERVAL_MINUTES', '5'))
    PORT = int(os.getenv('PORT', '8080'))
    
    # ============================================
    # VALIDATION
    # ============================================
    @staticmethod
    def validate():
        required = ['ANTHROPIC_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        missing = [key for key in required if not getattr(Config, key)]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        return True
    
    @staticmethod
    def validate_bitget():
        required = ['BITGET_API_KEY', 'BITGET_SECRET_KEY', 'BITGET_PASSPHRASE']
        missing = [key for key in required if not getattr(Config, key)]
        if missing:
            return False, f"Missing Bitget config: {', '.join(missing)}"
        return True, "Bitget config OK"
    
    @staticmethod
    def get_pair_symbol(ticker):
        ticker = ticker.upper().replace('USDT', '')
        return f'{ticker}/USDT:USDT'
    
    @staticmethod
    def get_clean_pair(bitget_pair):
        return bitget_pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
