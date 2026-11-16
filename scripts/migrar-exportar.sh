#!/usr/bin/env bash
# Empaqueta TODO lo necesario para llevar el sistema a otra computadora: un respaldo recién hecho
# de la base de datos y de los archivos subidos, más la configuración (.env).
#
#   scripts/migrar-exportar.sh      →  migracion_AAAAMMDD_HHMMSS.tar.gz
#
# ¡El paquete contiene las claves (.env) y los datos de la empresa! Cópielo con una memoria USB
# o por la red local; no lo suba a internet ni lo envíe por chat o correo.
# En la otra computadora: scripts/migrar-importar.sh migracion_....tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERROR: falta .env en $(pwd)" >&2; exit 1; }

salida="$(scripts/respaldo.sh | tail -1)"
# "Respaldo creado: respaldos/inventario_X.sql.gz y respaldos/archivos_X.tar.gz"
base="$(echo "$salida" | sed -E 's/.*(respaldos\/inventario_[0-9_]+\.sql\.gz).*/\1/')"
archivos="$(echo "$salida" | sed -E 's/.*(respaldos\/archivos_[0-9_]+\.tar\.gz).*/\1/')"
[ -s "$base" ] && [ -s "$archivos" ] || { echo "ERROR: no se pudo crear el respaldo" >&2; exit 1; }

paquete="migracion_$(date +%Y%m%d_%H%M%S).tar.gz"
temporal="$(mktemp -d)"
trap 'rm -rf "$temporal"' EXIT
cp .env "$temporal/env"
cp "$base" "$temporal/base.sql.gz"
cp "$archivos" "$temporal/archivos.tar.gz"
git rev-parse HEAD > "$temporal/version.txt" 2>/dev/null || true
umask 077
tar -czf "$paquete" -C "$temporal" .

echo "Paquete listo: $(pwd)/$paquete ($(du -h "$paquete" | cut -f1))"
echo "Contiene las claves y los datos: cópielo solo por USB o red local."
