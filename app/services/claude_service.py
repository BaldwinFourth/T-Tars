# -*- coding: utf-8 -*-
"""
T-TARS Claude Service v2.0.3
============================
Claude AI API wrapper for market analysis.

v2.0.3:
- Sürüm güncellemesi (Mantıksal değişiklik yok)
"""

from anthropic import Anthropic
from app.config import Config
import logging

logger = logging.getLogger(__name__)

class ClaudeService:
    """Claude Haiku 4.5 API Service"""
    
    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        logger.info(f"Claude Service initialized: {Config.CLAUDE_MODEL}")
    
    def analyze(self, prompt):
        """
        Analiz yap
        
        Args:
            prompt: Analiz prompt'u
            
        Returns:
            dict: {text, input_tokens, output_tokens}
        """
        try:
            response = self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Response'u parse et
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
            
            result = {
                "text": text_content,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
            
            logger.info(f"Analysis complete: {result['input_tokens']}→{result['output_tokens']} tokens")
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
