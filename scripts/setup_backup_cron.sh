#!/bin/bash
# ============================================================================
# Script para Configurar Backups Automáticos en Cron
# ============================================================================
# Este script agrega automáticamente los backups al crontab del usuario
# Se ejecutará todos los días a las 2:00 AM (hora del servidor)

CRON_JOB="0 2 * * * PGPASSWORD=\$(grep DB_PASSWORD /var/www/inventario-django/inventario-calidad-django/.env | cut -d '=' -f2 | tr -d \"'\") /var/www/inventario-django/scripts/backup_postgres.sh >> /var/log/postgres_backup.log 2>&1"

# Verificar si el cron job ya existe
if crontab -l 2>/dev/null | grep -q "backup_postgres.sh"; then
    echo "⚠️  El backup automático ya está configurado en cron"
    echo ""
    echo "Configuración actual:"
    crontab -l | grep backup_postgres.sh
else
    # Agregar el cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✓ Backup automático configurado correctamente"
    echo ""
    echo "Horario: Todos los días a las 2:00 AM"
    echo "Script: /var/www/inventario-django/scripts/backup_postgres.sh"
    echo "Log: /var/log/postgres_backup.log"
fi

echo ""
echo "Para ver todos los cron jobs configurados:"
echo "  crontab -l"
echo ""
echo "Para probar el backup manualmente:"
echo "  /var/www/inventario-django/scripts/backup_postgres.sh"
