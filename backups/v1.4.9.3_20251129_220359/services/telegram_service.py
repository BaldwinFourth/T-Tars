# -*- coding: utf-8 -*-
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
            
            # UTF-8 encoding için ensure_ascii=False
            payload = {
                "chat_id": target_chat,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            # UTF-8 ile encode et
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
    
    def broadcast(self, message):
        """
        Tüm authorized chatlara mesaj gönder
        (Kişisel + Beta Group)
        """
        allowed_chats = Config.get_allowed_chats()
        results = {}
        
        for chat_id in allowed_chats:
            success = self.send(message, chat_id=chat_id)
            results[chat_id] = success
            logger.info(f"📡 Broadcast to {chat_id}: {'✅' if success else '❌'}")
        
        return results
    
    def send_signal(self, message):
        """
        Sinyal mesajlarını broadcast yap
        Beta test için kullan
        """
        return self.broadcast(message)
