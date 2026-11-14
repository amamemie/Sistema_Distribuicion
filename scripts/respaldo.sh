#!/usr/bin/env bash
# Respaldo de la base de datos con rotación.
#
# Uso:       scripts/respaldo.sh            (desde la raíz del proyecto)
# Programar: crontab -e  →  0 23 * * * cd /ruta/al/proyecto && scripts/respaldo.sh
# Restaurar: gunzip -c respaldos/ARCHIVO.sql.gz | docker compose exec -T db \
#              sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
#
# IMPORTANTE: copie periódicamente la carpeta respaldos/ fuera de este equipo
# (disco externo o nube). Un respaldo en el mismo disco no protege contra su falla.
set -euo pipefail

cd "$(dirname "$0")/.."

DESTINO="${RESPALDO_DIR:-respaldos}"
DIAS="${RESPALDO_DIAS:-30}"
mkdir -p "$DESTINO"

archivo="$DESTINO/inventario_$(date +%Y%m%d_%H%M%S).sql.gz"
trap 'rm -f "$archivo"; echo "ERROR: falló el respaldo" >&2' ERR
# Las variables POSTGRES_* se leen dentro del contenedor de la base de datos.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' \
  | gzip > "$archivo"

if [ ! -s "$archivo" ]; then
  echo "ERROR: el respaldo quedó vacío" >&2
  rm -f "$archivo"
  exit 1
fi

find "$DESTINO" -name 'inventario_*.sql.gz' -mtime +"$DIAS" -delete
echo "Respaldo creado: $archivo"
