#!/bin/bash
# Respaldo nocturno de SIGMA en sic-sigma.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# 1. Saca una copia de la base de México (y de las otras tres, hoy vacías)
#    desde el Postgres que vive dentro de Docker.
# 2. Sube ese archivo .sql.gz a Drive, carpeta SIGMA-Backups/postgresql.
# 3. Sube las fotos nuevas de media/mexico a Drive.
#
# Usa "rclone copy", no "sync". Copy solo manda lo que falta o cambió.
# No borra en Drive una foto que todavía no esté en este disco.
#
# El cron del servidor viejo queda apagado. Este script es el reemplazo.

set -euo pipefail

APP_DIR="/srv/sic/apps/sigma"
BACKUP_DIR="/srv/sic/backups/sigma"
MEDIA_MEXICO="/srv/sic/data/sigma/media/mexico"
RCLONE="/srv/sic/bin/rclone"
LOG_DIR="/srv/sic/data/sigma/logs"
LOG_FILE="${LOG_DIR}/backup_sigma.log"
DIAS_LOCALES=7

# Nombres de las bases dentro del contenedor postgres.
BASES="inventario_mexico inventario_argentina inventario_chile inventario_colombia"

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
    if ! docker compose --env-file docker/.env exec -T postgres \
        pg_dump -U sigma -d "$base" | gzip > "$destino"; then
        log "ERROR al volcar ${base}"
        exit 1
    fi
    log "Listo ${base} ($(du -h "$destino" | cut -f1))"
done

log "Borrando volcados locales de más de ${DIAS_LOCALES} días"
find "$BACKUP_DIR" -name 'postgres_inventario_*.sql.gz' -type f -mtime +"$DIAS_LOCALES" -delete

log "Subiendo volcados nuevos a Drive (no borra los antiguos de la nube)"
"$RCLONE" copy "$BACKUP_DIR" "gdrive:SIGMA-Backups/postgresql" \
    --include "postgres_inventario_*.sql.gz" \
    --transfers 2 \
    --stats 1m \
    --stats-one-line \
    >> "$LOG_FILE" 2>&1

if [ -d "$MEDIA_MEXICO" ]; then
    log "Subiendo fotos nuevas de México (copy: no borra nada en Drive)"
    "$RCLONE" copy "$MEDIA_MEXICO" "gdrive:SIGMA-Backups/media/mexico" \
        --transfers 4 \
        --checkers 8 \
        --stats 1m \
        --stats-one-line \
        >> "$LOG_FILE" 2>&1
else
    log "No existe ${MEDIA_MEXICO}. No se subieron fotos."
fi

log "=== Respaldo terminado ==="
