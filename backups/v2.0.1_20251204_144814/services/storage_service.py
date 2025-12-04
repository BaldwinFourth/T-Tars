# -*- coding: utf-8 -*-
"""
T-TARS Storage Service v1.4.9.3
===============================
Google Cloud Storage service for templates.

v1.4.9.3:
- _clean_markdown: telegram markdown fix (→, <, $ karakterleri)
"""

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
            logger.warning("⚠️ CHANGELOG is empty")
            return []
        
        features = []
        in_version = False
        in_code_block = False
        
        for line in changelog.split('\n'):
            line = line.strip()
            
            # Code block tracking
            if line.startswith('```'):
                in_code_block = not in_code_block
                continue
            
            # Skip code block content
            if in_code_block:
                continue
            
            # Version basligini bul: "## v1.4.5" veya "## [1.4.5]"
            if line.startswith('## ') and version in line:
                in_version = True
                logger.info(f"📄 Found version section: {line}")
                continue
            
            # Sonraki version basladi (## v ile baslayan yeni bolum)
            if in_version and line.startswith('## ') and version not in line:
                break
            
            if in_version:
                # ### Section header'lari atla
                if line.startswith('###'):
                    continue
                
                # "- **Label:** description" formati
                if line.startswith('- **') and ':**' in line:
                    try:
                        content = line[4:]
                        colon_pos = content.find(':**')
                        if colon_pos > 0:
                            label = content[:colon_pos].strip()
                            desc = content[colon_pos+3:].strip()
                            if len(desc) > 35:
                                desc = desc[:32] + "..."
                            clean_feature = f"✅ {label}: {desc}"
                            features.append(clean_feature)
                    except:
                        pass
                    continue
                
                # "- **feature**" formati (eski format)
                if line.startswith('- **') and '**' in line[4:]:
                    try:
                        content = line[4:]
                        end_bold = content.find('**')
                        if end_bold > 0:
                            feature = content[:end_bold].strip()
                            clean_feature = f"✅ {self._clean_markdown(feature)}"
                            if len(clean_feature) < 50:
                                features.append(clean_feature)
                    except:
                        pass
                    continue
                
                # "✅ feature" formati
                if line.startswith('✅'):
                    clean_line = self._clean_markdown(line)
                    if len(clean_line) < 50:
                        features.append(clean_line)
                    continue
                
                # "- ✅ feature" formati
                if line.startswith('- ✅'):
                    clean_line = self._clean_markdown(line[2:].strip())
                    if len(clean_line) < 50:
                        features.append(clean_line)
                    continue
                
                # "- feature" formati (basit liste)
                if line.startswith('- ') and not line.startswith('- `'):
                    content = line[2:].strip()
                    if not any(x in content.lower() for x in ['fonksiyon', 'import', '.py', '()', 'satir']):
                        if len(content) < 40:
                            clean_feature = f"✅ {self._clean_markdown(content)}"
                            features.append(clean_feature)
        
        logger.info(f"📄 Parsed {len(features)} features for v{version}")
        return features[:6]
    
    def _clean_markdown(self, text):
        """
        Clean text for Telegram Markdown compatibility
        Remove ALL problematic characters
        """
        text = text.replace('```', '')
        text = text.replace('**', '')
        text = text.replace('__', '')
        text = text.replace('`', '')
        text = text.replace('_', ' ')
        text = text.replace('*', '')
        text = text.replace('[', '')
        text = text.replace(']', '')
        text = text.replace('(', '')
        text = text.replace(')', '')
        text = text.replace('~', '')
        text = text.replace('>', '')
        text = text.replace('<', '')
        text = text.replace('#', '')
        text = text.replace('+', '')
        text = text.replace('-', '')
        text = text.replace('=', '')
        text = text.replace('|', '')
        text = text.replace('{', '')
        text = text.replace('}', '')
        text = text.replace('.', ' ')
        text = text.replace('/', ' ')
        text = text.replace('$', '')
        text = text.replace('→', ' ')
        while '  ' in text:
            text = text.replace('  ', ' ')
        return text.strip()
