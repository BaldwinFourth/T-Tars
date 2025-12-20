# -*- coding: utf-8 -*-
"""
T-TARS Services v2.3.11
=======================
Service layer initialization.

v2.3.11: OKXService deprecated, BitgetService aktif
"""

from .claude_service import ClaudeService
from .telegram_service import TelegramService
from .storage_service import StorageService
from .bitget_service import BitgetService
from .tracking_service import TrackingService

# Backward compatibility (deprecated)
try:
    from .okx_service import OKXService
except ImportError:
    OKXService = None

__all__ = [
    'ClaudeService',
    'TelegramService',
    'StorageService',
    'BitgetService',
    'TrackingService',
    'OKXService',  # Deprecated
]
