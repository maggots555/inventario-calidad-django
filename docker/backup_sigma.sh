#!/bin/bash
# Respaldo nocturno de SIGMA en sic-sigma.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# 1. Saca una copia de las cuatro bases (México, Argentina, Chile y Colombia)
#    desde el Postgres que vive dentro de Docker.
# 2. Sube ese archivo .sql.gz a Drive, carpeta SIGMA-Backups/postgresql.
# 3. Sube las fotos nuevas de media/{mexico,argentina,chile,colombia} a Drive.
#
# Usa "rclone copy", no "sync". Copy solo manda lo que falta o cambió.
# No borra en Drive una foto que todavía no esté en este disco.
# Las fotos de Argentina, Chile y Colombia ya están en Drive: esta noche
# solo va a comparar y a subir lo que sea nuevo.
#
# El cron del servidor viejo queda apagado. Este script es el reemplazo.

set -euo pipefail

APP_DIR="/srv/sic/apps/sigma"
BACKUP_DIR="/srv/sic/backups/sigma"
# Carpeta de fotos en el disco del servidor. Cada país es una subcarpeta.
MEDIA_ROOT="/srv/sic/data/sigma/media"
RCLONE="/srv/sic/bin/rclone"
LOG_DIR="/srv/sic/data/sigma/logs"
LOG_FILE="${LOG_DIR}/backup_sigma.log"
DIAS_LOCALES=7

# Nombres de las bases dentro del contenedor postgres.
BASES="inventario_mexico inventario_argentina inventario_chile inventario_colombia"
# Mismas carpetas de fotos que hay en Drive: gdrive:SIGMA-Backups/media/<pais>
PAISES_MEDIA="mexico argentina chile colombia"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

# Si el respaldo de anoche sigue corriendo, este no se empalma.
exec 9>/tmp/backup_sigma.lock
if ! flock -n 9; then
    log "Ya hay un respaldo en curso. Se omite esta corrida."
    exit 0
fi

cd "$APP_DIR"
FECHA="$(date +%Y%m%d_%H%M%S)"

log "=== Inicio del respaldo ==="

for base in $BASES; do
    destino="${BACKUP_DIR}/postgres_${base}_${FECHA}.sql.gz"
    log "Volcando ${base} → ${destino}"
    # pg_dump corre DENTRO del contenedor. gzip corre en el servidor.
    # -T evita que Docker pida una terminal (en cron no hay pantalla).
    # Si pg_dump falla a la mitad, gzip deja un archivo roto. Hay que
    # borrarlo: si se queda, la subida de otra noche lo manda a Drive.
    if ! docker compose --env-file docker/.env exec -T postgres \
        pg_dump -U sigma -d "$base" | gzip > "$destino"; then
        log "ERROR al volcar ${base}. Se borra el archivo incompleto."
        rm -f "$destino"
        exit 1
    fi
    if ! gzip -t "$destino"; then
        log "ERROR: el volcado de ${base} no abre. Se borra."
        rm -f "$destino"
        exit 1
    fi
    # Un .gz válido de una base vacía pesa decenas de KB. Menos de 100
    # bytes es un archivo vacío que gzip cerró bien, no un respaldo.
    tamano="$(stat -c%s "$destino")"
    if [ "$tamano" -lt 100 ]; then
        log "ERROR: el volcado de ${base} pesa ${tamano} bytes. Se borra."
        rm -f "$destino"
        exit 1
    fi
    log "Listo ${base} ($(du -h "$destino" | cut -f1))"
done

# Volcados viejos que hayan quedado rotos tampoco se suben.
# copy no borra en Drive lo que ya estaba; solo evitamos mandar otro roto.
log "Revisando volcados locales antes de subirlos"
shopt -s nullglob
for archivo in "$BACKUP_DIR"/postgres_inventario_*.sql.gz; do
    if ! gzip -t "$archivo"; then
        log "Volcado dañado, no se sube: ${archivo}"
        rm -f "$archivo"
    fi
done
shopt -u nullglob

log "Borrando volcados locales de más de ${DIAS_LOCALES} días"
find "$BACKUP_DIR" -name 'postgres_inventario_*.sql.gz' -type f -mtime +"$DIAS_LOCALES" -delete

log "Subiendo volcados nuevos a Drive (no borra los antiguos de la nube)"
"$RCLONE" copy "$BACKUP_DIR" "gdrive:SIGMA-Backups/postgresql" \
    --include "postgres_inventario_*.sql.gz" \
    --transfers 2 \
    --stats 1m \
    --stats-one-line \
    >> "$LOG_FILE" 2>&1

# México va primero: es la carpeta grande. Las otras tres son pocas fotos.
# copy compara con Drive y no vuelve a subir un archivo que ya está igual.
for pais in $PAISES_MEDIA; do
    origen="${MEDIA_ROOT}/${pais}"
    if [ ! -d "$origen" ]; then
        log "No existe ${origen}. No se subieron fotos de ${pais}."
        continue
    fi
    log "Subiendo fotos nuevas de ${pais} (copy: no borra nada en Drive)"
    "$RCLONE" copy "$origen" "gdrive:SIGMA-Backups/media/${pais}" \
        --transfers 4 \
        --checkers 8 \
        --stats 1m \
        --stats-one-line \
        >> "$LOG_FILE" 2>&1
done

log "=== Respaldo terminado ==="
