#!/usr/bin/env bash
# Respaldo de la base de datos y de los archivos subidos (OC, constancias), con rotación.
#
# Uso:       scripts/respaldo.sh            (desde la raíz del proyecto)
# Programar: crontab -e  →  0 23 * * * cd /ruta/al/proyecto && scripts/respaldo.sh
# Restaurar: gunzip -c respaldos/ARCHIVO.sql.gz | docker compose exec -T db \
#              sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
#            docker compose exec -T backend tar -xzf - -C /datos < respaldos/ARCHIVOS.tar.gz
#
# IMPORTANTE: copie periódicamente la carpeta respaldos/ fuera de este equipo
# (disco externo o nube). Un respaldo en el mismo disco no protege contra su falla.
set -euo pipefail
# En Git Bash (Windows) evita que rutas del contenedor como /datos se conviertan a C:/...
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")/.."

DESTINO="${RESPALDO_DIR:-respaldos}"
DIAS="${RESPALDO_DIAS:-30}"
mkdir -p "$DESTINO"

marca="$(date +%Y%m%d_%H%M%S)"
archivo="$DESTINO/inventario_$marca.sql.gz"
archivos="$DESTINO/archivos_$marca.tar.gz"
trap 'rm -f "$archivo" "$archivos"; echo "ERROR: falló el respaldo" >&2' ERR
# Las variables POSTGRES_* se leen dentro del contenedor de la base de datos.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' \
  | gzip > "$archivo"

if [ ! -s "$archivo" ]; then
  echo "ERROR: el respaldo quedó vacío" >&2
  rm -f "$archivo"
  exit 1
fi

# Fotos y PDF de las OC y constancias de entrega (volumen del backend).
docker compose exec -T backend tar -czf - -C /datos archivos > "$archivos"

find "$DESTINO" \( -name 'inventario_*.sql.gz' -o -name 'archivos_*.tar.gz' \) \
  -mtime +"$DIAS" -delete
echo "Respaldo creado: $archivo y $archivos"
