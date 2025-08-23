#!/bin/bash

echo "🧪 TEST APPLICATION VTC - VÉRIFICATION FONCTIONNEMENT"
echo "====================================================="

# Attendre que l'application démarre
echo "⏳ Attente démarrage application (5 secondes)..."
sleep 5

# Test 1: Health Check
echo "🔍 Test 1: Health Check"
HEALTH_RESPONSE=$(curl -s --max-time 10 http://localhost:8009/health)
if [ $? -eq 0 ] && [[ $HEALTH_RESPONSE == *"healthy"* ]]; then
    echo "✅ Health Check: RÉUSSI"
    echo "   Réponse: $HEALTH_RESPONSE"
else
    echo "❌ Health Check: ÉCHEC"
    echo "   Réponse: $HEALTH_RESPONSE"
fi

# Test 2: Documentation API
echo -e "\n🔍 Test 2: Documentation API"
DOC_RESPONSE=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" http://localhost:8009/docs)
if [ "$DOC_RESPONSE" = "200" ]; then
    echo "✅ Documentation API: ACCESSIBLE"
    echo "   URL: http://localhost:8009/docs"
else
    echo "❌ Documentation API: INACCESSIBLE"
    echo "   Code: $DOC_RESPONSE"
fi

# Test 3: Monitoring
echo -e "\n🔍 Test 3: Monitoring"
MONITOR_RESPONSE=$(curl -s --max-time 10 http://localhost:8009/api/v1/monitoring/summary)
if [ $? -eq 0 ] && [[ $MONITOR_RESPONSE == *"timestamp"* ]]; then
    echo "✅ Monitoring: FONCTIONNEL"
    echo "   Endpoint: /api/v1/monitoring/summary"
else
    echo "❌ Monitoring: PROBLÈME"
fi

# Test 4: Processus
echo -e "\n🔍 Test 4: Processus uvicorn"
PROCESS_COUNT=$(ps aux | grep uvicorn | grep -v grep | wc -l)
if [ $PROCESS_COUNT -gt 0 ]; then
    echo "✅ Processus uvicorn: ACTIF ($PROCESS_COUNT processus)"
    ps aux | grep uvicorn | grep -v grep | head -2
else
    echo "❌ Processus uvicorn: AUCUN"
fi

# Test 5: Port
echo -e "\n🔍 Test 5: Port 8009"
PORT_CHECK=$(netstat -tlnp 2>/dev/null | grep :8009)
if [ -n "$PORT_CHECK" ]; then
    echo "✅ Port 8009: UTILISÉ"
    echo "   $PORT_CHECK"
else
    echo "❌ Port 8009: LIBRE (application non démarrée?)"
fi

echo -e "\n====================================================="
echo "🎯 RÉSUMÉ DES TESTS"
echo "====================================================="

# Résumé
if [ $? -eq 0 ] && [[ $HEALTH_RESPONSE == *"healthy"* ]] && [ "$DOC_RESPONSE" = "200" ]; then
    echo "🎉 APPLICATION VTC: PARFAITEMENT FONCTIONNELLE"
    echo "🌐 URL principale: http://localhost:8009"
    echo "📚 Documentation: http://localhost:8009/docs"
    echo "📊 Monitoring: http://localhost:8009/api/v1/monitoring/summary"
    echo "✅ PROBLÈME 'NO OUTPUT FROM TERMINAL' RÉSOLU !"
else
    echo "⚠️ APPLICATION VTC: PROBLÈMES DÉTECTÉS"
    echo "💡 Vérifiez que l'application est démarrée avec ./start_app_simple.sh"
fi

