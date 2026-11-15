#!/usr/bin/env bash
# Prepara un servidor Ubuntu (24.04, x86 o ARM; p. ej. Oracle Cloud Always Free) y levanta el
# sistema con HTTPS. Se ejecuta EN EL SERVIDOR, desde la carpeta del proyecto, con un usuario
# que tenga sudo. Es idempotente: se puede volver a correr sin perder datos.
#
#   DUENO_CORREO=... DUENO_PASSWORD=... [DUENO_NOMBRE=...] [EMPRESA_NOMBRE=...] \
#   [SITIO_DIRECCION=midominio.bo] scripts/instalar-servidor.sh
#
# Sin SITIO_DIRECCION se usa <ip-publica>.sslip.io (dirección gratuita que apunta a la IP), y
# Caddy obtiene el certificado HTTPS de Let's Encrypt automáticamente.
set -euo pipefail
cd "$(dirname "$0")/.."

paso() { printf '\n==> %s\n' "$*"; }

paso "Paquetes del sistema (Docker, cron, firewall persistente)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  docker.io docker-compose-v2 cron openssl curl iptables-persistent >/dev/null
sudo systemctl enable --now docker cron >/dev/null
sudo usermod -aG docker "$USER"
DOCKER="sudo docker"

paso "Firewall: abrir 80 y 443 (las imágenes de Oracle traen iptables cerrado)"
for puerto in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$puerto" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 5 -p tcp --dport "$puerto" -m state --state NEW -j ACCEPT
  fi
done
sudo netfilter-persistent save >/dev/null

paso "Hora del servidor: America/La_Paz"
sudo timedatectl set-timezone America/La_Paz

paso "Configuración (.env)"
if [ ! -f .env ]; then
  : "${DUENO_CORREO:?Indique DUENO_CORREO}" "${DUENO_PASSWORD:?Indique DUENO_PASSWORD}"
  ip="$(curl -fsS https://api.ipify.org)"
  sitio="${SITIO_DIRECCION:-${ip//./-}.sslip.io}"
  clave_bd="$(openssl rand -hex 24)"
  umask 077
  cat > .env <<EOF
# Generado por scripts/instalar-servidor.sh el $(date +%F). No subir a Git.
POSTGRES_DB=inventario
POSTGRES_USER=inventario
POSTGRES_PASSWORD=$clave_bd
PUERTO_DB=5433

ENTORNO=produccion
COOKIE_SEGURA=true
SESION_DURACION_HORAS=12
LOG_NIVEL=INFO

EMPRESA_NOMBRE=${EMPRESA_NOMBRE:-Mi Distribuidora}
DUENO_CORREO=$DUENO_CORREO
DUENO_PASSWORD=$DUENO_PASSWORD
DUENO_NOMBRE=${DUENO_NOMBRE:-Dueño}
DUENO_APELLIDO=${DUENO_APELLIDO:-}

PUERTO_WEB=80
PUERTO_WEB_HTTPS=443
SITIO_DIRECCION=$sitio

ARCHIVOS_DIR=/datos/archivos
EOF
  echo "Creado .env para https://$sitio"
else
  echo ".env ya existe: se conserva."
fi

paso "Construir y levantar los servicios (la primera vez tarda varios minutos)"
$DOCKER compose up -d --build
for _ in $(seq 60); do
  if $DOCKER compose exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/salud')" 2>/dev/null; then
    break
  fi
  sleep 5
done

paso "Permisos, roles, empresa y usuario dueño"
$DOCKER compose exec -T backend python -m app.cli inicializar

paso "Respaldo diario (23:00, se guardan 30 días) y limpieza semanal de imágenes viejas"
dir="$(pwd)"
( sudo crontab -l 2>/dev/null | grep -v 'sis_dis-respaldo' | grep -v 'sis_dis-limpieza' || true
  echo "0 23 * * * cd $dir && scripts/respaldo.sh >> $dir/respaldos/respaldo.log 2>&1 # sis_dis-respaldo"
  echo "30 3 * * 0 docker image prune -af --filter until=168h >/dev/null 2>&1 # sis_dis-limpieza"
) | sudo crontab -
mkdir -p respaldos

sitio="$(grep '^SITIO_DIRECCION=' .env | cut -d= -f2-)"
paso "Listo: https://$sitio"
echo "Si el certificado tarda, revise: sudo docker compose logs web"
