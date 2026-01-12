#!/bin/bash
# ============================================================================
# Script de Backup Automático de PostgreSQL
# ============================================================================
# Este script crea backups diarios de la base de datos PostgreSQL
# Mantiene backups de los últimos 7 días y borra automáticamente los antiguos
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# - pg_dump: comando que exporta toda la base de datos a un archivo SQL
# - Fecha en el nombre: permite identificar cuándo se creó cada backup
# - Rotación automática: borra backups mayores a 7 días para ahorrar espacio

# Configuración
DB_NAME="inventario_django"
DB_USER="django_user"
BACKUP_DIR="/var/www/inventario-django/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/postgres_backup_$DATE.sql"
LOG_FILE="/var/log/postgres_backup.log"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

# Función para escribir en el log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Iniciar backup
log "=== Iniciando backup de PostgreSQL ==="
log "Base de datos: $DB_NAME"
log "Archivo destino: $BACKUP_FILE"

# Realizar backup con pg_dump
# PGPASSWORD se lee del entorno (configurado en .env)
if pg_dump -U "$DB_USER" -h localhost "$DB_NAME" > "$BACKUP_FILE" 2>> "$LOG_FILE"; then
    # Comprimir el backup para ahorrar espacio
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    
    # Obtener tamaño del backup
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "✓ Backup completado exitosamente"
    log "Tamaño: $SIZE"
    
    # Eliminar backups antiguos (mayores a 7 días)
    log "Eliminando backups antiguos (>7 días)..."
    find "$BACKUP_DIR" -name "postgres_backup_*.sql.gz" -type f -mtime +7 -delete
    
    # Contar backups restantes
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/postgres_backup_*.sql.gz 2>/dev/null | wc -l)
    log "Backups disponibles: $BACKUP_COUNT"
    
else
    log "✗ ERROR: Backup falló"
    exit 1
fi

log "=== Backup finalizado ==="
echo ""
