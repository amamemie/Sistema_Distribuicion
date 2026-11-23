#!/usr/bin/env bash
# Pone en marcha el sistema en ESTA computadora con los datos de otra (paquete creado por
# scripts/migrar-exportar.sh). Se ejecuta desde la carpeta del proyecto (clonado de GitHub), con
# Docker instalado y SIN datos previos del sistema en esta computadora.
#
#   scripts/migrar-importar.sh /ruta/migracion_AAAAMMDD_HHMMSS.tar.gz
set -euo pipefail
# En Git Bash (Windows) evita que rutas del contenedor como /datos se conviertan a C:/...
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

paquete="${1:?Uso: scripts/migrar-importar.sh migracion_....tar.gz}"
[ -f "$paquete" ] || { echo "ERROR: no existe $paquete" >&2; exit 1; }
[ -f .env ] && { echo "ERROR: ya hay un .env aquí. Si quiere reemplazarlo, muévalo antes." >&2; exit 1; }

temporal="$(mktemp -d)"
trap 'rm -rf "$temporal"' EXIT
tar -xzf "$paquete" -C "$temporal"
for f in env base.sql.gz archivos.tar.gz; do
  [ -s "$temporal/$f" ] || { echo "ERROR: el paquete no tiene $f" >&2; exit 1; }
done

echo "==> Configuración"
install -m 600 "$temporal/env" .env

echo "==> Base de datos (solo el contenedor de la base, para restaurar antes de las migraciones)"
docker compose up -d db
for _ in $(seq 60); do
  docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 && break
  sleep 2
done
tablas="$(docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from information_schema.tables where table_schema = '"'"'public'"'"'"')"
if [ "$tablas" != "0" ]; then
  echo "ERROR: la base de esta computadora ya tiene datos ($tablas tablas). No se sobrescribe." >&2
  exit 1
fi
gunzip -c "$temporal/base.sql.gz" | docker compose exec -T db \
  sh -c 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null

echo "==> Resto del sistema (aplica migraciones nuevas si las hay)"
docker compose up -d --build
for _ in $(seq 90); do
  docker compose exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/salud')" >/dev/null 2>&1 && break
  sleep 3
done

echo "==> Archivos subidos (notas, fotos, comprobantes)"
docker compose exec -T backend tar -xzf - -C /datos < "$temporal/archivos.tar.gz"

usuarios="$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from usuario"')"
echo "Listo: sistema restaurado con $usuarios usuario(s). Abra http://localhost:$(grep -E '^PUERTO_WEB=' .env | cut -d= -f2- || echo 8080)"
