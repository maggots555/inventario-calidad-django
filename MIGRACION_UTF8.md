# Migración SQLite a PostgreSQL - UTF-8 Correcto

## 📦 Archivos incluidos

### 1. `exportar_datos_sqlite.ps1`
Script de PowerShell para exportar datos desde SQLite con encoding UTF-8 sin BOM.

**Uso en Windows:**
```powershell
.\exportar_datos_sqlite.ps1
```

**Qué hace:**
- Activa el entorno virtual automáticamente
- Verifica que estés usando SQLite
- Exporta todos los datos a `backup_sqlite_utf8/`
- Genera archivos JSON con UTF-8 correcto (sin BOM)

### 2. `validar_encoding_json.py`
Script de Python para validar que los archivos JSON tienen encoding UTF-8 correcto.

**Uso:**
```bash
python validar_encoding_json.py
# O especificar carpeta:
python validar_encoding_json.py backup_sqlite_utf8
```

**Qué valida:**
- ✅ Encoding UTF-8 sin BOM (correcto)
- ❌ Detecta caracteres corruptos (Ã¡, Ã©, etc.)
- ✅ Cuenta caracteres especiales del español
- ✅ Verifica que el JSON sea válido
- ✅ Muestra ejemplos de texto con acentos

### 3. `backup_sqlite_utf8/`
Carpeta con los datos exportados listos para importar en PostgreSQL.

**Archivos:**
- `users.json` - Usuarios del sistema
- `inventario.json` - Productos, movimientos, sucursales
- `scorecard.json` - Datos de scorecard
- `servicio_tecnico.json` - Servicio técnico (el más grande)

## 🚀 Flujo de Trabajo Completo

### En Windows (Desarrollo - SQLite):

1. **Exportar datos:**
   ```powershell
   .\exportar_datos_sqlite.ps1
   ```

2. **Validar encoding:**
   ```bash
   python validar_encoding_json.py
   ```

3. **Copiar a Linux:**
   ```bash
   # Usando SCP, WinSCP, FileZilla, etc.
   scp -r backup_sqlite_utf8 usuario@servidor:/ruta/proyecto/
   ```

### En Linux (Producción - PostgreSQL):

4. **Configurar PostgreSQL en settings.py:**
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': os.environ.get('DB_NAME'),
           'USER': os.environ.get('DB_USER'),
           'PASSWORD': os.environ.get('DB_PASSWORD'),
           'HOST': os.environ.get('DB_HOST', 'localhost'),
           'PORT': os.environ.get('DB_PORT', '5432'),
       }
   }
   ```

5. **Crear estructura de base de datos:**
   ```bash
   python manage.py migrate
   ```

6. **Importar datos:**
   ```bash
   python manage.py loaddata backup_sqlite_utf8/users.json
   python manage.py loaddata backup_sqlite_utf8/inventario.json
   python manage.py loaddata backup_sqlite_utf8/scorecard.json
   python manage.py loaddata backup_sqlite_utf8/servicio_tecnico.json
   ```

7. **Verificar:**
   ```bash
   python manage.py runserver
   # Abre el admin y verifica que los acentos se vean correctamente
   ```

## ⚠️ Importante

- **UTF-8 sin BOM**: Los archivos se exportan SIN BOM para compatibilidad con Django/PostgreSQL
- **Orden de importación**: Importar `users.json` primero, luego los demás
- **Validación**: Siempre ejecutar `validar_encoding_json.py` antes de copiar a producción
- **Backup**: Mantén una copia de `db.sqlite3` por si necesitas re-exportar

## 🔍 Solución de Problemas

### Error: "Unexpected UTF-8 BOM"
Los archivos tienen BOM. Re-exportar con `exportar_datos_sqlite.ps1`.

### Error: "Unable to serialize database: 'charmap' codec can't encode"
El encoding no está configurado correctamente. El script ya lo maneja automáticamente.

### Acentos corruptos en PostgreSQL
Los archivos tienen double-encoding. Validar con `validar_encoding_json.py` y re-exportar.

## 📊 Estadísticas del Backup Actual

- **users.json**: 2.53 KB (5 usuarios)
- **inventario.json**: 78.66 KB (115 registros)
- **scorecard.json**: 327.49 KB (467 registros)
- **servicio_tecnico.json**: 16.85 MB (37,369 registros)
- **Total**: ~17.25 MB
- **Caracteres especiales**: 20,000+ acentos y ñ correctamente codificados

## ✅ Verificación Exitosa

Todos los archivos han sido validados:
- ✓ UTF-8 sin BOM
- ✓ Sin caracteres corruptos
- ✓ JSON válido
- ✓ Acentos y caracteres especiales correctos
