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
    echo ""
    
    # Traffic'i en son revision'a yönlendir
    echo "🔄 Traffic en son revision'a yönlendiriliyor..."
    gcloud run services update-traffic tars-api --region=us-central1 --to-latest
    echo ""
    
    # CHANGELOG'u Cloud Storage'a yükle
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
    exit 1
fi
