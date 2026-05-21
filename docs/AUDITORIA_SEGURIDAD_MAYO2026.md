# Revisión de Configuración de Infraestructura — SigmaSystem

**Servidor:** Ubuntu 24.04
**Fecha:** Mayo 2026

---

## Stack revisado

- nginx 1.24.0 + Gunicorn + Django 5.2 + PostgreSQL 16
- Redis / Celery (Worker + Beat)
- FFmpeg para procesamiento de video/imagen
- Cloudflare Tunnel + Tailscale VPN

---

## Ajustes aplicados

### Almacenamiento

| # | Área | Acción | Estado |
|---|---|---|---|
| 1 | Espacio en disco | Limpieza de artefactos acumulados (caché de paquetes, imágenes de kernel en desuso) | ✅ |

### Acceso remoto

| # | Área | Acción | Estado |
|---|---|---|---|
| 2 | SSH | Acceso restringido a la interfaz de red interna (Tailscale) mediante override de socket y directiva de escucha dedicada | ✅ |

### Comunicaciones

| # | Área | Acción | Estado |
|---|---|---|---|
| 3 | TLS en nginx | Protocolo actualizado; versiones legacy deshabilitadas | ✅ |
| 4 | Configuración nginx | Eliminación de archivos de sitio sin uso activo | ✅ |

### Gestión de credenciales y permisos de sistema

| # | Área | Acción | Estado |
|---|---|---|---|
| 5 | Archivo de entorno `.env` | Permisos de lectura ajustados al grupo de aplicación | ✅ |
| 6 | Caché Redis | Autenticación habilitada; cadena de conexión actualizada en configuración | ✅ |

### Aislamiento de procesos

| # | Área | Acción | Estado |
|---|---|---|---|
| 7 | Gunicorn / Celery | Servicios migrados a usuario de sistema dedicado sin shell ni directorio home | ✅ |
| 8 | Permisos de directorios | Ajuste de permisos en directorios de media y logs para el usuario de servicio | ✅ |
| 9 | Unidades systemd | Directivas de sandboxing añadidas a los servicios de procesamiento en segundo plano | ✅ |

### Código de aplicación

| # | Área | Acción | Estado |
|---|---|---|---|
| 10 | Procesamiento de video (FFmpeg) | Restricción de protocolos habilitados en todos los puntos de invocación | ✅ |
| 11 | Subida de archivos | Validación de extensión y tamaño máximo implementada en todos los campos de imagen sin restricciones previas; migraciones aplicadas | ✅ |

---

## Archivos modificados

```
/etc/nginx/nginx.conf
/etc/ssh/sshd_config.d/99-listen-address.conf        (nuevo)
/etc/systemd/system/ssh.socket.d/override.conf       (nuevo)
/etc/systemd/system/gunicorn.service
/etc/systemd/system/celery-worker.service
/etc/systemd/system/celery-beat.service

/var/www/inventario-django/inventario-calidad-django/
  .env
  config/validators.py                               (nuevo)
  servicio_tecnico/views.py
  servicio_tecnico/tasks.py
  servicio_tecnico/models.py
  almacen/models.py
  inventario/models.py
  almacen/migrations/0015_alter_diferenciaauditoria_evidencia_and_more.py
  inventario/migrations/0017_alter_empleado_foto_perfil.py
  servicio_tecnico/migrations/0040_alter_bannerpromocional_imagen.py
```
