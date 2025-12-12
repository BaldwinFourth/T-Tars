# -*- coding: utf-8 -*-
"""
T-TARS Configuration v2.0.3
===========================

v2.0.3:
- DEFAULT_LEVERAGE = 3 eklendi
- MONITOR_INTERVAL_MINUTES = 3 (Düzeltildi)
- OKX API credentials mevcut
- OKX_TRADING_ENABLED flag (/stopokx, /startokx)
"""

import os
from pathlib import Path


class Config:
    """T-TARS Configuration v2.0.3"""
    
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
    # OKX API
    # ============================================
    OKX_API_KEY = os.getenv('OKX_API_KEY', '')
    OKX_SECRET_KEY = os.getenv('OKX_SECRET_KEY', '')
    OKX_PASSPHRASE = os.getenv('OKX_PASSPHRASE', '')
    OKX_DEMO_MODE = os.getenv('OKX_DEMO_MODE', 'false').lower() == 'true'
    
    # Trading ON/OFF switch (/stopokx, /startokx)
    OKX_TRADING_ENABLED = os.getenv('OKX_TRADING_ENABLED', 'true').lower() == 'true'

    # v2.0.3: Default Leverage (3x)
    DEFAULT_LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '3'))
    
    # ============================================
    # CLAUDE AI
    # ============================================
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
    THINKING_BUDGET = int(os.getenv('THINKING_BUDGET', '20000'))
    
    # ============================================
    # CLOUD STORAGE
    # ============================================
    BUCKET_NAME = os.getenv('BUCKET_NAME', 'tars-trading-templates')
    BUCKET_NAME_DATA = os.getenv('BUCKET_NAME_DATA', 'tars-trading-data')
    
    # Template filenames
    PLAN_TEMPLATE = 'T-Tars Plan.md'
    EXECUTE_TEMPLATE = 'T-Tars Execute Log.md'
    LOG_TEMPLATE = 'T-Tars Trade Log.md'
    
    # ============================================
    # TRADING PAIRS
    # ============================================
    
    # Auto-scan listesi (13 coin)
    AUTO_SCAN_PAIRS = [
        'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT',
        'BNB/USDT:USDT', 'XRP/USDT:USDT', 'AVAX/USDT:USDT', 
        'LTC/USDT:USDT', 'TRX/USDT:USDT', 'DOGE/USDT:USDT', 
        'SHIB/USDT:USDT', 'PEPE/USDT:USDT', 'TRUMP/USDT:USDT', 
        'JUP/USDT:USDT', 'PUMP/USDT:USDT'
    ]
    
    # Manuel /plan için
    MANUAL_PAIRS = [
        'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT',
        'LTC/USDT:USDT', 'XRP/USDT:USDT', 'DOGE/USDT:USDT', 
        'TRUMP/USDT:USDT', 'JUP/USDT:USDT', 'AVAX/USDT:USDT', 
        'SHIB/USDT:USDT', 'BNB/USDT:USDT', 'HYPE/USDT:USDT', 
        'TRX/USDT:USDT', 'SUI/USDT:USDT', 'PEPE/USDT:USDT', 
        'PUMP/USDT:USDT', 'BCH/USDT:USDT', 'PUMP/USDT:USDT'
        
    ]
    
    # ============================================
    # RISK MANAGEMENT
    # ============================================
    RISK_PER_TRADE_MIN = float(os.getenv('RISK_PER_TRADE_MIN', '1.0'))
    RISK_PER_TRADE_MAX = float(os.getenv('RISK_PER_TRADE_MAX', '2.0'))
    DEFAULT_BALANCE = float(os.getenv('DEFAULT_BALANCE', '1000'))
    
    # Position limits
    MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '100'))
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '50'))
    MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '5'))
    
    # ============================================
    # MONITORING & SERVER
    # ============================================
    # v2.0.3: Monitor süresi 3 dakika
    MONITOR_INTERVAL_MINUTES = int(os.getenv('MONITOR_INTERVAL_MINUTES', '3'))
    PORT = int(os.getenv('PORT', '8080'))
    
    # ============================================
    # VALIDATION
    # ============================================
    @staticmethod
    def validate():
        """Validate required configuration"""
        required = ['ANTHROPIC_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        missing = [key for key in required if not getattr(Config, key)]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        return True
    
    @staticmethod
    def validate_okx():
        """Validate OKX API configuration"""
        required = ['OKX_API_KEY', 'OKX_SECRET_KEY', 'OKX_PASSPHRASE']
        missing = [key for key in required if not getattr(Config, key)]
        if missing:
            return False, f"Missing OKX config: {', '.join(missing)}"
        return True, "OKX config OK"
    
    @staticmethod
    def get_pair_symbol(ticker):
        """Convert user input to OKX format"""
        ticker = ticker.upper().replace('USDT', '')
        if ticker in ['LSK']: return f'{ticker}/USDT'
        return f'{ticker}/USDT:USDT'
    
    @staticmethod
    def get_clean_pair(okx_pair):
        """OKX formatından temiz parite adı al"""
        return okx_pair.replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
