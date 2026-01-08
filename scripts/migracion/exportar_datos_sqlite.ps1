# exportar_datos_sqlite.ps1
# Script para exportar datos de SQLite con encoding UTF-8 correcto (sin BOM)
# Para usar en Windows antes de migrar a PostgreSQL en Linux
# Genera carpeta "backup_sqlite_utf8" con archivos JSON listos para importar

# Configurar encoding UTF-8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Exportando datos de SQLite con UTF-8 correcto" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Activar entorno virtual
Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
    Write-Host "  Entorno virtual activado" -ForegroundColor Green
} else {
    Write-Host "  ERROR: No se encontro .venv" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Verificar base de datos actual
Write-Host "Verificando base de datos actual..." -ForegroundColor Yellow
$currentDb = python -c "from config.settings import DATABASES; print(DATABASES['default']['ENGINE'])"
Write-Host "Base de datos: $currentDb" -ForegroundColor Gray
Write-Host ""

if ($currentDb -notlike "*sqlite*") {
    Write-Host "ADVERTENCIA: No estas usando SQLite actualmente" -ForegroundColor Red
    Write-Host "Motor detectado: $currentDb" -ForegroundColor Red
    Write-Host ""
    Write-Host "Deseas continuar de todos modos? (S/N): " -ForegroundColor Yellow -NoNewline
    $respuesta = Read-Host
    if ($respuesta -ne "S" -and $respuesta -ne "s") {
        Write-Host ""
        Write-Host "Exportacion cancelada" -ForegroundColor Red
        exit 1
    }
}

# Crear carpeta para backups
$backupDir = "backup_sqlite_utf8"
Write-Host "Creando carpeta: $backupDir" -ForegroundColor Cyan

# Si existe, eliminar contenido anterior
if (Test-Path $backupDir) {
    Write-Host "  Limpiando carpeta existente..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $backupDir
}

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Host ""

# Exportar usuarios
Write-Host "Exportando usuarios..." -ForegroundColor Yellow
python manage.py dumpdata auth.user --indent 2 --output "$backupDir/users.json"
if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "$backupDir/users.json").Length / 1KB
    Write-Host "  OK - users.json: $("{0:N2}" -f $size) KB" -ForegroundColor Green
} else {
    Write-Host "  ERROR exportando usuarios" -ForegroundColor Red
    exit 1
}

# Exportar inventario
Write-Host "Exportando inventario..." -ForegroundColor Yellow
python manage.py dumpdata inventario --indent 2 --output "$backupDir/inventario.json"
if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "$backupDir/inventario.json").Length / 1KB
    Write-Host "  OK - inventario.json: $("{0:N2}" -f $size) KB" -ForegroundColor Green
} else {
    Write-Host "  ERROR exportando inventario" -ForegroundColor Red
    exit 1
}

# Exportar scorecard
Write-Host "Exportando scorecard..." -ForegroundColor Yellow
python manage.py dumpdata scorecard --indent 2 --output "$backupDir/scorecard.json"
if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "$backupDir/scorecard.json").Length / 1KB
    Write-Host "  OK - scorecard.json: $("{0:N2}" -f $size) KB" -ForegroundColor Green
} else {
    Write-Host "  ERROR exportando scorecard" -ForegroundColor Red
    exit 1
}

# Exportar servicio tecnico
Write-Host "Exportando servicio tecnico..." -ForegroundColor Yellow
python manage.py dumpdata servicio_tecnico --indent 2 --output "$backupDir/servicio_tecnico.json"
if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "$backupDir/servicio_tecnico.json").Length / 1KB
    Write-Host "  OK - servicio_tecnico.json: $("{0:N2}" -f $size) KB" -ForegroundColor Green
} else {
    Write-Host "  ERROR exportando servicio tecnico" -ForegroundColor Red
    exit 1
}

# Exportar almacen
Write-Host "Exportando almacen..." -ForegroundColor Yellow
python manage.py dumpdata almacen --indent 2 --output "$backupDir/almacen.json"
if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "$backupDir/almacen.json").Length / 1KB
    Write-Host "  OK - almacen.json: $("{0:N2}" -f $size) KB" -ForegroundColor Green
} else {
    Write-Host "  ERROR exportando almacen" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  EXPORTACION COMPLETADA CON EXITO" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Ubicacion: $backupDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Archivos generados:" -ForegroundColor Cyan
Get-ChildItem $backupDir -Filter "*.json" | ForEach-Object {
    $size = "{0:N2}" -f ($_.Length / 1KB)
    Write-Host "  - $($_.Name): $size KB" -ForegroundColor White
}

$totalSize = (Get-ChildItem $backupDir -Filter "*.json" | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ""
Write-Host "Tamaño total: $("{0:N2}" -f $totalSize) MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host "  PROXIMOS PASOS:" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host "1. Validar encoding: python validar_encoding_json.py" -ForegroundColor White
Write-Host "2. Copiar '$backupDir' a servidor Linux" -ForegroundColor White
Write-Host "3. En Linux - Migrar: python manage.py migrate" -ForegroundColor White
Write-Host "4. En Linux - Importar: python manage.py loaddata $backupDir/*.json" -ForegroundColor White
Write-Host ""
