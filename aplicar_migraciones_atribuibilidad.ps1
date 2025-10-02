# Script para aplicar migraciones de atribuibilidad

# Activar entorno virtual y ejecutar migraciones
& "C:/Users/DELL/Proyecto_Django/inventario-calidad-django/.venv/Scripts/python.exe" manage.py migrate

Write-Host ""
Write-Host "✅ Migraciones aplicadas exitosamente" -ForegroundColor Green
Write-Host ""
Write-Host "Nuevas funcionalidades agregadas:" -ForegroundColor Cyan
Write-Host "1. Campo 'es_atribuible' en Incidencia" -ForegroundColor Yellow
Write-Host "2. Campos de justificación y fecha para incidencias no atribuibles" -ForegroundColor Yellow  
Write-Host "3. Tipos de notificación mejorados" -ForegroundColor Yellow
Write-Host ""
