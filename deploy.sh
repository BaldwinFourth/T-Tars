#!/bin/bash

echo "🚀 T-TARS Trading Bot Deployment"
echo "=================================="
echo ""

# Get version from VERSION file (ZORUNLU!)
if [ -f "VERSION" ]; then
    VERSION=$(cat VERSION)
    echo "📦 Version: v$VERSION"
else
    echo "❌ VERSION file not found!"
    echo "❌ VERSION dosyası olmadan deploy yapılamaz!"
    exit 1
fi

# OTOMATIK BACKUP
echo ""
echo "💾 Otomatik backup oluşturuluyor..."
BACKUP_DIR="backups/v${VERSION}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Mevcut dosyaları backup'la
if [ -f "app/main.py" ]; then
    cp app/main.py "$BACKUP_DIR/"
    echo "✅ main.py backup'landı"
fi

if [ -d "app/services" ]; then
    cp -r app/services "$BACKUP_DIR/"
    echo "✅ services/ backup'landı"
fi

if [ -f "app/config.py" ]; then
    cp app/config.py "$BACKUP_DIR/"
    echo "✅ config.py backup'landı"
fi

if [ -f "Dockerfile" ]; then
    cp Dockerfile "$BACKUP_DIR/"
    echo "✅ Dockerfile backup'landı"
fi

if [ -f "CHANGELOG.md" ]; then
    cp CHANGELOG.md "$BACKUP_DIR/"
    echo "✅ CHANGELOG.md backup'landı"
fi

echo "✅ Backup tamamlandı: $BACKUP_DIR"
echo ""

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found!"
    exit 1
fi

echo "✅ Dockerfile bulundu"
echo ""
echo "📦 Google Cloud Run'a deploy ediliyor..."
echo ""

# Deploy to Cloud Run
gcloud run deploy tars-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi \
  --timeout 300

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deploy tamamlandı! v$VERSION"
    echo "💾 Backup: $BACKUP_DIR"
    echo ""
    
    # Traffic'i en son revision'a yönlendir (v1.4.2+ fix)
    echo "🔄 Traffic en son revision'a yönlendiriliyor..."
    gcloud run services update-traffic tars-api --region=us-central1 --to-latest
    echo ""
    
    # CHANGELOG'u Cloud Storage'a yükle (v1.4.2+)
    echo "📄 CHANGELOG Cloud Storage'a yükleniyor..."
    if [ -f "CHANGELOG.md" ]; then
        gsutil cp CHANGELOG.md gs://tars-trading-templates/CHANGELOG.md
        if [ $? -eq 0 ]; then
            echo "✅ CHANGELOG.md Cloud Storage'a yüklendi"
        else
            echo "⚠️ CHANGELOG upload başarısız (devam ediliyor)"
        fi
    else
        echo "⚠️ CHANGELOG.md bulunamadı, upload atlandı"
    fi
    echo ""
    
    echo "📡 Service URL:"
    gcloud run services describe tars-api --region us-central1 --format="value(status.url)"
    echo ""
    echo "🧪 Test komutları:"
    echo "curl https://tars-api-609075413784.us-central1.run.app/health"
    echo ""
    echo "📊 Telegram'da test et:"
    echo "/status"
    echo ""
    echo "🎉 v$VERSION başarıyla deploy edildi!"
else
    echo ""
    echo "❌ Deploy başarısız!"
    echo "💾 Backup korundu: $BACKUP_DIR"
    echo ""
    echo "🔄 Eski versiyona dönmek için:"
    echo "   ls -lt backups/"
    echo "   cp -r backups/v${VERSION}_*/app/* app/"
    echo "   cp backups/v${VERSION}_*/Dockerfile ."
    exit 1
fi
