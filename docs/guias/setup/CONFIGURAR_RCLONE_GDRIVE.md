# Guía: Configurar rclone con Google Drive (Servidor Headless)

> **Para**: Administrador del sistema SIGMA  
> **Propósito**: Conectar el servidor con Google Drive para backups automáticos  
> **Servidor**: Headless (sin navegador — solo terminal SSH)  
> **Tiempo estimado**: 15–20 minutos

---

## ¿Qué es rclone?

`rclone` es un programa que sincroniza archivos entre tu servidor y servicios en la nube (Google Drive, S3, Dropbox, etc.). Funciona desde la terminal, sin interfaz gráfica.

En este proyecto lo usamos para:
- Subir backups diarios de PostgreSQL a Drive
- Sincronizar los archivos de media (imágenes de órdenes, evidencias de scorecard)

---

## PASO 1 — Verificar que rclone está instalado

```bash
/var/www/inventario-django/bin/rclone --version
```

Deberías ver algo como: `rclone v1.73.3`

---

## PASO 2 — Configurar el remote de Google Drive

Como el servidor no tiene navegador, el proceso requiere **dos terminales**:
- **Terminal A**: conectada al servidor (SSH)
- **Terminal B**: tu computadora personal (donde sí hay navegador)

### 2.1 Iniciar la configuración en el servidor (Terminal A)

```bash
/var/www/inventario-django/bin/rclone config
```

Aparecerá el menú interactivo. Sigue estos pasos:

```
No remotes found, make a new one?
n/s/q> n                          ← escribe n (new)

name> gdrive                      ← escribe exactamente: gdrive

Storage> drive                    ← escribe: drive  (o el número de Google Drive)

client_id>                        ← Enter (dejar vacío)
client_secret>                    ← Enter (dejar vacío)

scope> 1                          ← escribe 1 (acceso completo a Drive)

root_folder_id>                   ← Enter (dejar vacío)
service_account_file>             ← Enter (dejar vacío)

Edit advanced config?
y/n> n                            ← escribe n

Use auto config?
y/n> n                            ← escribe n  ← IMPORTANTE en servidor headless
```

### 2.2 Obtener el enlace de autorización

Después de responder `n` a "Use auto config?", rclone mostrará:

```
Please go to the following link: https://accounts.google.com/o/oauth2/...
Log in and authorize rclone for access
Enter verification code>
```

**Copia ese enlace completo.**

### 2.3 Autorizar en tu PC (Terminal B)

En tu computadora personal (con navegador):

```bash
# Si tienes rclone instalado en tu PC:
rclone authorize "drive"

# Si no tienes rclone en tu PC, abre el enlace directamente en el navegador
# El enlace lo copiaste en el paso anterior
```

1. Se abrirá el navegador con la pantalla de Google
2. Inicia sesión con la cuenta de Google donde quieres guardar los backups
3. Otorga permiso a rclone
4. Verás un código o una página con el token — **cópialo**

### 2.4 Pegar el token en el servidor (Terminal A)

```
Enter verification code> PEGA_AQUÍ_EL_TOKEN
```

### 2.5 Finalizar la configuración

```
Configure this as a Shared Drive (Team Drive)?
y/n> n                            ← escribe n (a menos que uses Google Workspace)

Keep this "gdrive" remote?
y/n> y                            ← escribe y para confirmar

q                                 ← escribe q para salir del menú
```

---

## PASO 3 — Verificar que la conexión funciona

```bash
# Listar los archivos en la raíz de tu Google Drive
/var/www/inventario-django/bin/rclone ls gdrive:

# Si no tienes archivos, no muestra nada (eso es normal)
# Prueba crear una carpeta de prueba:
/var/www/inventario-django/bin/rclone mkdir gdrive:SIGMA-Backups

# Verificar que la carpeta se creó en Drive:
/var/www/inventario-django/bin/rclone lsd gdrive:
```

Si ves `SIGMA-Backups` en la lista, la conexión está funcionando.

---

## PASO 4 — Instalar el cron job automático

```bash
bash /var/www/inventario-django/scripts/setup_backup_drive_cron.sh
```

Este script:
1. Verifica que rclone esté configurado
2. Agrega el cron job al crontab (todos los días a las 3:00 AM)
3. Muestra el crontab actualizado

---

## PASO 5 — Probar el backup manualmente

Antes de esperar las 3 AM, prueba el script a mano:

```bash
/var/www/inventario-django/scripts/backup_gdrive.sh
```

Verás en pantalla el progreso. Al finalizar, revisa en Google Drive que existan:
```
SIGMA-Backups/
├── postgresql/          ← archivos .sql.gz de los últimos 7 días
└── media/
    ├── mexico/          ← imágenes de órdenes de servicio (~76 GB)
    └── argentina/       ← evidencias Argentina (~32 MB)
```

> **Nota**: La primera ejecución tardará varias horas por los 76 GB de media.
> Las siguientes ejecuciones solo suben lo nuevo (incremental).

---

## Verificar los logs del backup

```bash
# Ver el log más reciente del backup a Drive
tail -50 /var/log/backup_gdrive.log

# Ver en tiempo real mientras se ejecuta
tail -f /var/log/backup_gdrive.log
```

---

## Archivos generados por esta configuración

| Archivo | Descripción |
|---------|-------------|
| `~/.config/rclone/rclone.conf` | Token de acceso a Google Drive (permisos 600) |
| `/var/www/inventario-django/bin/rclone` | Ejecutable de rclone v1.73.3 |
| `/var/www/inventario-django/scripts/backup_gdrive.sh` | Script de backup |
| `/var/www/inventario-django/scripts/setup_backup_drive_cron.sh` | Instalador del cron |
| `/var/log/backup_gdrive.log` | Log de resultados diarios |

---

## Seguridad del token

El archivo `~/.config/rclone/rclone.conf` contiene el token de acceso a tu Google Drive.

- Tiene permisos `600` (solo tu usuario puede leerlo) — rclone lo configura automáticamente
- **No lo compartas ni lo subas a git**
- Si crees que fue comprometido: ve a [myaccount.google.com/permissions](https://myaccount.google.com/permissions) y revoca el acceso de rclone

---

## Solución de problemas

### Error: "Token has been expired or revoked"
El token de Google expiró o fue revocado. Vuelve a ejecutar `rclone config` y selecciona el remote `gdrive` para re-autorizarlo.

### Error: "QUOTA_EXCEEDED"
Tu Google Drive no tiene espacio suficiente. Revisa el espacio disponible en drive.google.com.

### El backup corre pero no sube nada nuevo
Normal — significa que todos los archivos ya están en Drive y no han cambiado. `rclone sync` es incremental.

### Ver qué archivos subió rclone en el último backup
```bash
grep "INFO" /var/log/backup_gdrive.log | tail -30
```
