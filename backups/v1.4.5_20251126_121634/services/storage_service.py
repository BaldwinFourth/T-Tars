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
        
        v1.4.5: Updated to match CHANGELOG format:
        - ## v1.4.5 (2025-11-26) format
        - ### Section headers
        - - **feature** - description format
        - ✅ feature format
        """
        changelog = self.get_changelog()
        if not changelog:
            logger.warning("⚠️ CHANGELOG is empty")
            return []
        
        features = []
        in_version = False
        
        for line in changelog.split('\n'):
            line = line.strip()
            
            # Version başlığını bul: "## v1.4.5" veya "## [1.4.5]"
            if line.startswith('## ') and version in line:
                in_version = True
                logger.info(f"📄 Found version section: {line}")
                continue
            
            # Sonraki version başladı (## v ile başlayan yeni bölüm)
            if in_version and line.startswith('## ') and version not in line:
                break
            
            # Code block içindeyse atla
            if line.startswith('```'):
                continue
            
            if in_version:
                # ### Section header'ları atla
                if line.startswith('###'):
                    continue
                
                # "- **feature**" formatı (CHANGELOG'daki ana format)
                if line.startswith('- **') and '**' in line[4:]:
                    # "- **setup_detector.py modülü oluşturuldu** - açıklama"
                    # Extract: "setup_detector.py modülü oluşturuldu"
                    try:
                        content = line[4:]  # "**feature** - desc" kısmı
                        end_bold = content.find('**')
                        if end_bold > 0:
                            feature = content[:end_bold].strip()
                            clean_feature = f"✅ {self._clean_markdown(feature)}"
                            if len(clean_feature) < 50:  # Çok uzun olmasın
                                features.append(clean_feature)
                    except:
                        pass
                
                # "✅ feature" formatı
                elif line.startswith('✅'):
                    clean_line = self._clean_markdown(line)
                    if len(clean_line) < 50:
                        features.append(clean_line)
                
                # "- ✅ feature" formatı
                elif line.startswith('- ✅'):
                    clean_line = self._clean_markdown(line[2:].strip())
                    if len(clean_line) < 50:
                        features.append(clean_line)
                
                # "- feature" formatı (basit liste)
                elif line.startswith('- ') and not line.startswith('- `'):
                    content = line[2:].strip()
                    # Çok teknik satırları atla
                    if not any(x in content.lower() for x in ['fonksiyon', 'import', '.py', '()', 'satır']):
                        if len(content) < 40:
                            clean_feature = f"✅ {self._clean_markdown(content)}"
                            features.append(clean_feature)
        
        logger.info(f"📄 Parsed {len(features)} features for v{version}")
        return features[:6]  # Max 6 feature (daha kompakt)
    
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
        # Remove code ticks
        text = text.replace('`', '')
        return text.strip()
