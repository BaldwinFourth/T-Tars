# -*- coding: utf-8 -*-
"""
T-TARS Services v2.5.3
=======================
Service layer initialization.

v2.5.3: 
- CHANGED: ClaudeService → GrokService (Grok 4.1 Fast Reasoning)
- ClaudeService alias korundu (backward compat)

v2.3.11: OKXService deprecated, BitgetService aktif
"""

from .grok_service import GrokService
from .telegram_service import TelegramService
from .storage_service import StorageService
from .bitget_service import BitgetService
from .tracking_service import TrackingService

# Backward compatibility - ClaudeService artık GrokService'e alias
ClaudeService = GrokService

# Backward compatibility (deprecated)
try:
    from .okx_service import OKXService
except ImportError:
    OKXService = None

__all__ = [
    'GrokService',      # v2.5.3: Yeni AI servisi
    'ClaudeService',    # Backward compat alias
    'TelegramService',
    'StorageService',
    'BitgetService',
    'TrackingService',
    'OKXService',       # Deprecated
]
