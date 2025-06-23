#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Atualizando cache apt..."
apt-get update -y && apt-get install -y --no-install-recommends \
  build-essential git curl jq

echo "[2/5] Instalando dependências Python..."
if [[ -f ".env" ]]; then
  export $(grep -v '^#' .env | xargs)
fi
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/5] Instalando dependências Node..."
npm ci

echo "[4/5] Configuração GitHub Auth..."
if [[ -n "${API_GH_TOKEN:-}" ]]; then
  git config --global url."https://x-access-token:${API_GH_TOKEN}@github.com/".insteadOf "https://github.com/"
fi

echo "[5/5] Scripts de Lint e Testes..."
npm run lint || true
npm test || true

echo "✅ Setup concluído."