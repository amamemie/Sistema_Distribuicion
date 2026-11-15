#!/usr/bin/env bash
# Envía la versión de `main` al servidor y la pone en marcha. Se ejecuta EN ESTE EQUIPO.
#
#   scripts/desplegar.sh ubuntu@IP_DEL_SERVIDOR
#
# La primera vez instala todo (requiere DUENO_CORREO y DUENO_PASSWORD en el entorno, ver
# scripts/instalar-servidor.sh). Las siguientes, solo actualiza: el .env, la base de datos, los
# archivos subidos y los respaldos del servidor no se tocan. Las migraciones se aplican solas.
set -euo pipefail
cd "$(dirname "$0")/.."

destino="${1:?Uso: scripts/desplegar.sh usuario@servidor}"
carpeta="${CARPETA_REMOTA:-sis_dis}"
rama="${RAMA:-main}"

echo "==> Enviando $rama ($(git rev-parse --short "$rama")) a $destino:~/$carpeta"
git archive --format=tar "$rama" | ssh "$destino" "mkdir -p ~/$carpeta && tar -xf - -C ~/$carpeta"

if ssh "$destino" "test -f ~/$carpeta/.env"; then
  echo "==> Actualizando servicios"
  ssh "$destino" "cd ~/$carpeta && sudo docker compose up -d --build && sudo docker image prune -f >/dev/null"
else
  echo "==> Primera instalación"
  ssh -t "$destino" "cd ~/$carpeta && \
    DUENO_CORREO='${DUENO_CORREO:?Indique DUENO_CORREO}' \
    DUENO_PASSWORD='${DUENO_PASSWORD:?Indique DUENO_PASSWORD}' \
    DUENO_NOMBRE='${DUENO_NOMBRE:-Dueño}' \
    EMPRESA_NOMBRE='${EMPRESA_NOMBRE:-Mi Distribuidora}' \
    SITIO_DIRECCION='${SITIO_DIRECCION:-}' \
    bash scripts/instalar-servidor.sh"
fi
