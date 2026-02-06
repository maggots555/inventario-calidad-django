#!/bin/bash
#
# Script de limpieza de archivos temporales de uploads
# 
# Propósito: Limpiar archivos temporales de Django en /var/www/django_temp
#            que tengan más de 24 horas de antigüedad
#
# Uso: Ejecutar manualmente o agregar a crontab
#      Ejemplo crontab (diario a las 3:00 AM):
#      0 3 * * * /var/www/inventario-django/inventario-calidad-django/scripts/mantenimiento/limpiar_uploads_temp.sh >> /var/www/inventario-django/inventario-calidad-django/logs/limpieza_temp.log 2>&1
#
# Fecha: 6 de Febrero 2026
# Autor: OpenCode AI Assistant
#

# Directorio temporal de Django
DJANGO_TEMP="/var/www/django_temp"

# Log timestamp
echo "=========================================="
echo "Limpieza de archivos temporales: $(date)"
echo "Directorio: $DJANGO_TEMP"

# Contar archivos antes de limpiar
ARCHIVOS_ANTES=$(find "$DJANGO_TEMP" -type f 2>/dev/null | wc -l)
echo "Archivos antes de limpieza: $ARCHIVOS_ANTES"

# Eliminar archivos con más de 24 horas
# -type f : solo archivos (no directorios)
# -mtime +1 : modificados hace más de 24 horas
# -delete : eliminar
ELIMINADOS=$(find "$DJANGO_TEMP" -type f -mtime +1 -delete -print 2>/dev/null | wc -l)

echo "Archivos eliminados: $ELIMINADOS"

# Contar archivos después de limpiar
ARCHIVOS_DESPUES=$(find "$DJANGO_TEMP" -type f 2>/dev/null | wc -l)
echo "Archivos restantes: $ARCHIVOS_DESPUES"

# Espacio usado
DU_OUTPUT=$(du -sh "$DJANGO_TEMP" 2>/dev/null | cut -f1)
echo "Espacio usado en $DJANGO_TEMP: $DU_OUTPUT"

echo "Limpieza completada exitosamente"
echo "=========================================="
