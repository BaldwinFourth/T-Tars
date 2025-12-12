# -*- coding: utf-8 -*-
"""
T-TARS Telegram Service v2.0.3
==============================
Telegram Bot API wrapper

v2.0.3:
- Sürüm güncellemesi (Mantıksal değişiklik yok)

v2.0.0:
- broadcast() kaldırıldı
- send_signal() sadece TELEGRAM_CHAT_ID'ye gönderir
- Beta group desteği kaldırıldı
"""

import requests
import logging
from app.config import Config

logger = logging.getLogger(__name__)


class TelegramService:
    """Telegram Bot API wrapper"""
    
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        logger.info("✅ Telegram Service initialized")
    
    def send(self, message, chat_id=None):
        """
        Mesaj gönder
        chat_id belirtilmezse default (kişisel) chat'e gönderir
        """
        target_chat = chat_id or self.chat_id
        
        try:
            url = f"{self.base_url}/sendMessage"
            
            payload = {
                "chat_id": target_chat,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(
                url, 
                json=payload, 
                timeout=10,
                headers={'Content-Type': 'application/json; charset=utf-8'}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"❌ Telegram send error (chat: {target_chat}): {e}")
            return False
    
    def send_signal(self, message):
        """
        v2.0.0: Sinyal mesajlarını SADECE ana chat'e gönder
        Broadcast kaldırıldı - beta group yok artık
        """
        return self.send(message, chat_id=self.chat_id)
