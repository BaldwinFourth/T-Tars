import os
from pathlib import Path

class Config:
    """T-TARS Configuration v1.4.0"""
    
    # Get base directory
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    # Auto-load version from VERSION file
    VERSION_FILE = BASE_DIR / "VERSION"
    try:
        with open(VERSION_FILE, 'r') as f:
            VERSION = f.read().strip()
    except FileNotFoundError:
        VERSION = "1.4.0"  # Fallback
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # MULTI-CHAT SUPPORT (Beta Test Group)
    TELEGRAM_BETA_GROUP_ID = os.getenv('TELEGRAM_BETA_GROUP_ID', '')
    
    # Allowed chat IDs (list)
    @staticmethod
    def get_allowed_chats():
        """Get all allowed chat IDs"""
        chats = [Config.TELEGRAM_CHAT_ID]
        if Config.TELEGRAM_BETA_GROUP_ID:
            chats.append(Config.TELEGRAM_BETA_GROUP_ID)
        return chats
    
    # Claude Settings
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')
    THINKING_BUDGET = int(os.getenv('THINKING_BUDGET', '20000'))
    
    # Storage - Templates
    BUCKET_NAME = os.getenv('BUCKET_NAME', 'tars-trading-templates')
    
    # Storage - Tracking Data (NEW v1.4.0)
    BUCKET_NAME_DATA = os.getenv('BUCKET_NAME_DATA', 'tars-trading-data')
    
    # Template filenames (in Cloud Storage bucket)
    PLAN_TEMPLATE = 'T-Tars Plan.md'
    EXECUTE_TEMPLATE = 'T-Tars Execute Log.md'
    LOG_TEMPLATE = 'T-Tars Trade Log.md'
    
    # TRADING PAIRS
    # Auto-scan (3 dakikada bir) - Bot yorulmasın
    AUTO_SCAN_PAIRS = [
        'BTC/USDT:USDT',
        'SOL/USDT:USDT'
    ]
    
    # Manuel /plan için - Desteklenen tüm pariteler
    MANUAL_PAIRS = [
        # Majors
        'BTC/USDT:USDT',
        'ETH/USDT:USDT',
        'SOL/USDT:USDT',
        
        # Alts - Perpetual
        'LTC/USDT:USDT',
        'XRP/USDT:USDT',
        'DOGE/USDT:USDT',
        'TRUMP/USDT:USDT',
        'JUP/USDT:USDT',
        'AVAX/USDT:USDT',
        'SHIB/USDT:USDT',
        'BNB/USDT:USDT',
        'HYPE/USDT:USDT',
        'TRX/USDT:USDT',
        'SUI/USDT:USDT',
        'PEPE/USDT:USDT',
        'PUMP/USDT:USDT',
        'LINEA/USDT:USDT',
        'BCH/USDT:USDT',
        
        # Spot
        'LSK/USDT'
    ]
    
    # Risk Management
    RISK_PER_TRADE_MIN = float(os.getenv('RISK_PER_TRADE_MIN', '1.0'))  # %1
    RISK_PER_TRADE_MAX = float(os.getenv('RISK_PER_TRADE_MAX', '2.0'))  # %2
    DEFAULT_BALANCE = float(os.getenv('DEFAULT_BALANCE', '1000'))  # $1000 default
    
    # Monitoring Settings (NEW v1.4.0)
    MONITOR_INTERVAL_MINUTES = int(os.getenv('MONITOR_INTERVAL_MINUTES', '5'))  # Cloud Scheduler interval
    
    # Server
    PORT = int(os.getenv('PORT', '8080'))
    
    @staticmethod
    def validate():
        """Validate required configuration"""
        required = [
            'ANTHROPIC_API_KEY',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        missing = [key for key in required if not getattr(Config, key)]
        
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        
        return True
    
    @staticmethod
    def get_pair_symbol(ticker):
        """
        Convert user input to OKX format
        Examples:
        - btcusdt → BTC/USDT:USDT
        - ETHUSDT → ETH/USDT:USDT
        - lskusdt → LSK/USDT (spot)
        """
        ticker = ticker.upper().replace('USDT', '')
        
        # Spot pairs
        if ticker in ['LSK']:
            return f'{ticker}/USDT'
        
        # Perpetual (default)
        return f'{ticker}/USDT:USDT'
