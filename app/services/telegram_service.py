# -*- coding: utf-8 -*-
"""
T-TARS Telegram Service v2.2.1
==============================
Telegram Bot API wrapper

v2.2.1:
- FIX: Markdown parse hatası olursa plain text'e fallback
- CHANGED: parse_mode önce Markdown dene, hata olursa None

v2.0.3:
- Sürüm güncellemesi

v2.0.0:
- broadcast() kaldırıldı
- send_signal() sadece TELEGRAM_CHAT_ID'ye gönderir
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
        logger.info("✅ Telegram Service initialized (v2.2.1)")
    
    def send(self, message, chat_id=None):
        """
        Mesaj gönder
        v2.2.1: Markdown hata verirse plain text dene
        """
        target_chat = chat_id or self.chat_id
        url = f"{self.base_url}/sendMessage"
        
        # Önce Markdown ile dene
        try:
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
            
        except requests.exceptions.HTTPError as e:
            # 400 Bad Request = muhtemelen Markdown hatası
            if "400" in str(e):
                logger.warning(f"⚠️ Markdown parse hatası, plain text deneniyor...")
                try:
                    # Plain text olarak tekrar dene
                    payload_plain = {
                        "chat_id": target_chat,
                        "text": message
                        # parse_mode yok = plain text
                    }
                    response = requests.post(
                        url,
                        json=payload_plain,
                        timeout=10,
                        headers={'Content-Type': 'application/json; charset=utf-8'}
                    )
                    response.raise_for_status()
                    logger.info("✅ Plain text ile gönderildi")
                    return True
                except Exception as e2:
                    logger.error(f"❌ Plain text de başarısız: {e2}")
                    return False
            else:
                logger.error(f"❌ Telegram send error (chat: {target_chat}): {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Telegram send error (chat: {target_chat}): {e}")
            return False
    
    def send_signal(self, message):
        """
        v2.0.0: Sinyal mesajlarını SADECE ana chat'e gönder
        """
        return self.send(message, chat_id=self.chat_id)
