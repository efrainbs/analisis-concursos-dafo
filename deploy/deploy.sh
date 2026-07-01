#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/tu-usuario/Analisis_Concursos_DAFO.git"
APP_DIR="$HOME/Analisis_Concursos_DAFO"
DOMAIN="tudominio.pe"
EMAIL="tu-email@ejemplo.com"

echo "=== 1. Clonar/actualizar repositorio ==="
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && git pull
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

echo "=== 2. Copiar base de datos ==="
echo "Coloca concursos_dafo.db en $APP_DIR/"
echo "Ejemplo desde tu máquina local:"
echo "  rsync -avz concursos_dafo.db usuario@vps:$APP_DIR/"
read -rp "Presiona Enter cuando la base de datos esté en su lugar..."

echo "=== 3. Crear venv e instalar dependencias ==="
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r config/requirements.txt

echo "=== 4. Copiar servicio systemd ==="
sed "s|%USER%|$USER|g; s|%APP_DIR%|$APP_DIR|g" deploy/dafo-web.service | sudo tee /etc/systemd/system/dafo-web.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now dafo-web.service

echo "=== 5. Configurar nginx ==="
sudo apt install -y nginx certbot python3-certbot-nginx
sed "s|tudominio.pe|$DOMAIN|g" deploy/nginx.conf | sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null
sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "=== 6. SSL con Let's Encrypt ==="
sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "$EMAIL"

echo "=== Hecho! https://$DOMAIN ==="
