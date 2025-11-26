# -*- coding: utf-8 -*-
from google.cloud import storage
import logging

logger = logging.getLogger(__name__)

class StorageService:
    """Google Cloud Storage service for templates"""
    
    def __init__(self, bucket_name='tars-trading-templates'):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        logger.info(f"✅ Storage Service initialized: {bucket_name}")
    
    def get_plan_template(self):
        """Get Plan template"""
        blob = self.bucket.blob('T-Tars Plan.md')
        return blob.download_as_text(encoding='utf-8')
    
    def get_execute_template(self):
        """Get Execute template"""
        blob = self.bucket.blob('T-Tars Execute Log.md')
        return blob.download_as_text(encoding='utf-8')
    
    def get_log_template(self):
        """Get Trade Log template"""
        blob = self.bucket.blob('T-Tars Trade Log.md')
        return blob.download_as_text(encoding='utf-8')
    
    def get_changelog(self):
        """Get CHANGELOG.md"""
        try:
            blob = self.bucket.blob('CHANGELOG.md')
            return blob.download_as_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"⚠️ CHANGELOG.md not found in bucket: {e}")
            return ""
    
    def parse_version_features(self, version):
        """
        Parse CHANGELOG.md for specific version features
        Returns list of feature strings (cleaned for Telegram Markdown)
        """
        changelog = self.get_changelog()
        if not changelog:
            return []
        
        features = []
        in_version = False
        in_changes = False
        
        for line in changelog.split('\n'):
            line = line.strip()
            
            # Version başlığını bul
            if f'[{version}]' in line:
                in_version = True
                continue
            
            # Sonraki version başladı
            if in_version and line.startswith('## ['):
                break
            
            if in_version:
                # ### bölümlerini atla
                if line.startswith('###'):
                    in_changes = True
                    continue
                
                # Features topla
                if line.startswith('✅'):
                    # Clean for Telegram Markdown
                    clean_line = self._clean_markdown(line)
                    features.append(clean_line)
                elif line.startswith('- ✅'):
                    clean_line = self._clean_markdown(line[2:].strip())
                    features.append(clean_line)
                # Alt maddeleri de ekle
                elif in_changes and '→' in line and '✅' in line:
                    # "  - Grupta mesaj → Bot sessiz ✅" gibi
                    clean = line.replace('  - ', '').replace('- ', '').strip()
                    if len(clean) < 60:  # Çok uzun olmasın
                        clean_line = self._clean_markdown(f"✅ {clean.split('→')[0].strip()}")
                        features.append(clean_line)
        
        return features[:8]  # Max 8 feature
    
    def _clean_markdown(self, text):
        """
        Clean text for Telegram Markdown compatibility
        Remove problematic characters: ```, _, *, [, ]
        """
        # Remove triple backticks
        text = text.replace('```', '')
        # Remove markdown bold/italic
        text = text.replace('**', '')
        text = text.replace('__', '')
        return text
