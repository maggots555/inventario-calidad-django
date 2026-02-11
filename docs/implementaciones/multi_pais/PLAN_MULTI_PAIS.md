# Sistema Multi-País con Subdominios — Documentación Final

**Versión:** 4.0 (Implementación Completada)  
**Fecha de creación:** 9 de Febrero 2026  
**Fecha de implementación en producción:** 10-11 de Febrero 2026  
**Estado:** ✅ **COMPLETADO Y EN PRODUCCIÓN**  
**Última actualización:** 11 de Febrero 2026

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Estado Final del Sistema](#2-estado-final-del-sistema)
3. [Arquitectura Implementada](#3-arquitectura-implementada)
4. [Fases de Implementación (Completadas)](#4-fases-de-implementación-completadas)
5. [Decisiones Reales vs Plan Original](#5-decisiones-reales-vs-plan-original)
6. [Archivos Clave de la Implementación](#6-archivos-clave-de-la-implementación)
7. [Seguridad Multi-Tenant](#7-seguridad-multi-tenant)
8. [Auditoría de Código Hardcoded](#8-auditoría-de-código-hardcoded)
9. [Guía para Agregar un Nuevo País](#9-guía-para-agregar-un-nuevo-país)
10. [Rollback Plan](#10-rollback-plan)
11. [Consideraciones Futuras](#11-consideraciones-futuras)

---

## 1. Resumen Ejecutivo

### Objetivo

Expandir el sistema SigmaSystem para operar en múltiples países de Latinoamérica con **bases de datos completamente independientes** por país, comenzando con **Argentina** como país piloto junto a **México** (país existente).

### Resultado

El sistema multi-país está **100% operativo en producción** desde el 11 de Febrero 2026. Ambos países funcionan correctamente con aislamiento total de datos, sesiones y archivos.

### Decisiones Clave

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| Arquitectura | Database-per-Tenant manual (sin django-tenants) | Máximo 4-5 países, más simple y control total |
| Conectividad | Cloudflare Tunnel (ya existente) | No requiere port forwarding ni IP pública expuesta |
| SSL | Cloudflare Origin Certificate wildcard `*.sigmasystem.work` | Válido hasta 2041, cubre todos los subdominios |
| BD México | **NO se renombró** — `default` y `mexico` apuntan a `inventario_django` | Evita downtime y riesgo innecesario |
| Media | Storage dinámico con prefijo de país (sin UPDATE en BD) | `DynamicFileSystemStorage` agrega `mexico/` automáticamente |
| Costo | $0 (infraestructura existente) | Todo en mismo servidor |

### URLs en Producción

```
https://mexico.sigmasystem.work    → BD: inventario_django    → Media: /mnt/django_storage/media/mexico/
https://argentina.sigmasystem.work → BD: inventario_argentina → Media: /mnt/django_storage/media/argentina/
https://sigmasystem.work           → Redirect 301 → mexico.sigmasystem.work
```

---

## 2. Estado Final del Sistema

### 2.1 Verificación de Conectividad

| URL | Resultado | Verificado |
|-----|-----------|------------|
| `https://mexico.sigmasystem.work/login/` | HTTP 200 | ✅ 11 Feb 2026 |
| `https://argentina.sigmasystem.work/login/` | HTTP 200 | ✅ 11 Feb 2026 |
| `https://sigmasystem.work/` | HTTP 301 → `mexico.sigmasystem.work` | ✅ 11 Feb 2026 |
| `http://192.168.100.22/login/` | HTTP 200 (acceso LAN intacto) | ✅ 11 Feb 2026 |
| Imágenes media (fotos, evidencias, productos) | HTTP 200 via Nginx | ✅ 11 Feb 2026 |

### 2.2 Funcionalidad Verificada

| Funcionalidad | México | Argentina |
|---------------|--------|-----------|
| Login/Logout | ✅ | ✅ |
| Crear registros | ✅ | ✅ |
| Subir archivos (fotos) | ✅ | ✅ |
| Enviar correos | ✅ | ✅ |
| Dashboard con gráficas | ✅ | ✅ |
| Panel de administración | ✅ | ✅ |
| Aislamiento de datos | ✅ | ✅ |
| Sesiones independientes | ✅ | ✅ |

### 2.3 Estado de Archivos Media (México)

| Tipo | Encontrados | Total BD | Notas |
|------|-------------|----------|-------|
| Fotos empleados | 27/27 (100%) | 27 | Completo |
| Productos almacén | 2/2 (100%) | 2 | Completo |
| Evidencias scorecard | 181/212 (85%) | 212 | 31 faltantes pre-existentes (antes de multi-país) |
| Imágenes de órdenes | 10,554/27,715 (38%) | 27,715 | 17,161 perdidas en migración anterior Windows→Linux (esperado) |

### 2.4 Infraestructura

| Componente | Detalle |
|------------|---------|
| Servidor | sicubuserver (IP privada, detrás de NAT) |
| OS | Ubuntu 24.04 LTS |
| Stack | Cloudflare Tunnel → Nginx 1.24 → Gunicorn (5 workers, unix socket) → Django 5.2.5 → PostgreSQL 16.11 |
| Tunnel ID | `976b441d-7aef-41fe-a9f0-6fb8ef4c9b11` |
| Conexiones QUIC | 4 activas (2× Querétaro, 2× Atlanta) |
| Python | 3.12 |
| Dominio | sigmasystem.work (Cloudflare DNS, proxy mode ON) |
| Disco media | `/mnt/django_storage` — 916 GB total, ~845 GB libres |

---

## 3. Arquitectura Implementada

### 3.1 Diagrama General

```
                    ┌─────────────────────────┐
                    │    CLOUDFLARE TUNNEL     │
                    │  *.sigmasystem.work      │
                    │  (QUIC, 4 conexiones)    │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │       NGINX 1.24        │
                    │  5 bloques server       │
                    │  SSL Origin Certificate │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │      GUNICORN           │
                    │   (5 workers sync)      │
                    └───────────┬─────────────┘
                                │
                ┌───────────────▼───────────────┐
                │     DJANGO + PaisMiddleware    │
                │  Detecta subdominio del Host   │
                │  Thread-locals → DB Router     │
                └──┬──────────────────────────┬──┘
                   │                          │
          ┌────────▼────────┐       ┌────────▼────────┐
          │  BD México       │       │  BD Argentina    │
          │  inventario_     │       │  inventario_     │
          │  django          │       │  argentina       │
          │  (55 tablas)     │       │  (55 tablas)     │
          └────────┬────────┘       └────────┬────────┘
                   │                          │
          ┌────────▼────────┐       ┌────────▼────────┐
          │  Media           │       │  Media           │
          │  /mexico/        │       │  /argentina/     │
          │  (~25 GB)        │       │  (vacío)         │
          └─────────────────┘       └─────────────────┘
```

### 3.2 Flujo de un Request

```
1. Usuario accede a: mexico.sigmasystem.work/ordenes/
2. Cloudflare Tunnel (cloudflared) recibe → envía a Nginx via HTTPS localhost:443
3. Nginx recibe → pasa Host header a Gunicorn via unix socket
4. Django recibe request con Host: mexico.sigmasystem.work
5. PaisMiddleware:
   a. Extrae "mexico" del Host header
   b. Busca en PAISES_CONFIG → encuentra configuración de México
   c. Guarda en thread-locals: pais_codigo='MX', db_alias='mexico'
   d. Guarda en request.pais_config la configuración completa
6. PaisDBRouter:
   a. Para cada query, consulta thread-locals
   b. Retorna 'mexico' como alias de BD → Django usa inventario_django
7. DynamicFileSystemStorage:
   a. Al guardar/servir archivos, consulta thread-locals
   b. Agrega prefijo 'mexico/' a la ruta del archivo
8. Vista procesa normalmente
9. PaisMiddleware (finally): Limpia thread-locals
```

### 3.3 Estructura de Media en Disco

```
/mnt/django_storage/media/
├── mexico/
│   ├── almacen/
│   │   ├── productos/
│   │   └── cotizaciones/
│   ├── empleados/
│   │   └── fotos/            (27 fotos)
│   ├── scorecard/
│   │   └── evidencias/       (181 archivos)
│   ├── servicio_tecnico/
│   │   ├── imagenes/         (~10,500 archivos, ~25 GB)
│   │   └── imagenes_originales/
│   └── temp/
└── argentina/
    ├── empleados/fotos/
    └── servicio_tecnico/
        ├── imagenes/
        └── imagenes_originales/
```

### 3.4 Componentes Django del Multi-Tenancy

| Componente | Archivo | Función |
|------------|---------|---------|
| Config de países | `config/paises_config.py` | Diccionario centralizado con toda la info de cada país |
| Middleware | `config/middleware_pais.py` | Detecta país por subdominio, configura thread-locals |
| DB Router | `config/db_router.py` | Enruta queries a la BD correcta (prioridad: hints → thread-locals → default) |
| Context Processor | `config/context_processors.py` | Variables de país disponibles en todos los templates |
| Storage | `config/storage_utils.py` | `DynamicFileSystemStorage` con prefijo de país en `_save()`, `url()`, `path()` |

### 3.5 Orden del Middleware (Crítico)

```python
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # ← Pone request.user
    ...
    'config.middleware_pais.PaisMiddleware',                    # ← Configura BD del país
    'inventario.middleware.ForcePasswordChangeMiddleware',      # ← Usa request.user.empleado (necesita BD correcta)
]
```

---

## 4. Fases de Implementación (Completadas)

### Resumen de Progreso

| Fase | Descripción | Estado | Fecha | Notas |
|------|-------------|--------|-------|-------|
| **0** | Entorno de desarrollo local | ✅ Completada | 9 Feb 2026 | Commit `f16dbe6` |
| **1** | Cloudflare DNS + SSL | ✅ Completada | 11 Feb 2026 | Via Tunnel, no DNS directo |
| **2** | PostgreSQL Multi-Base | ✅ Completada | 11 Feb 2026 | BD México NO renombrada |
| **3** | Django Multi-Tenancy | ✅ Completada | 9 Feb 2026 | Commit `f16dbe6` |
| **4** | Nginx Subdominios | ✅ Completada | 11 Feb 2026 | 5 bloques server |
| **5** | Media Files por País | ✅ Completada | 11 Feb 2026 | Storage dinámico, sin UPDATE en BD |
| **6** | Código Hardcoded | ✅ Completada | 10 Feb 2026 | Commit `88016f8`, alcance reducido |
| **7** | Migraciones y Datos | ✅ Completada | 11 Feb 2026 | 55 tablas, 9 grupos, superusuario |
| **8** | Pruebas y Lanzamiento | ✅ Completada | 11 Feb 2026 | Todo verificado funcionando |

### Fase 0+3: Desarrollo Local + Django Multi-Tenancy

**Commit:** `f16dbe6` (9 Feb 2026)

Se implementaron juntas. Todo el código Django multi-tenant quedó listo en un solo commit:

- 4 archivos nuevos: `paises_config.py`, `middleware_pais.py`, `db_router.py`, `context_processors.py`
- `config/settings.py` modificado: DATABASES (3 aliases), DATABASE_ROUTERS, MIDDLEWARE, TEMPLATES, SESSION_COOKIE
- `config/storage_utils.py` modificado: `DynamicFileSystemStorage` v2.0 con prefijo de país
- Scripts de grupos/permisos actualizados con soporte `db_alias`
- Ambas BDs SQLite (dev) migradas y verificadas con aislamiento correcto

### Fase 1: Cloudflare — Tunnel + DNS

**Fecha:** 11 Feb 2026

**Descubrimiento:** El servidor ya usaba **Cloudflare Tunnel** (no port forwarding). El servicio `cloudflared` ya estaba corriendo como systemd service.

**Lo que se hizo:**

1. **Actualizado `/etc/cloudflared/config.yml`** — Se agregaron los hostnames `mexico.sigmasystem.work` y `argentina.sigmasystem.work`, cambiando de `http://localhost:80` a `https://localhost:443` con `noTLSVerify: true`
2. **DNS actualizado** — Los registros A existentes se sobreescribieron con CNAMEs al tunnel:
   ```bash
   cloudflared tunnel route dns --overwrite-dns sigmasystem-tunnel mexico.sigmasystem.work
   cloudflared tunnel route dns --overwrite-dns sigmasystem-tunnel argentina.sigmasystem.work
   ```
3. **SSL** — Ya existía Origin Certificate wildcard en `/etc/ssl/cloudflare/sigmasystem.work.pem` (válido hasta 2041)
4. **Reinicio de cloudflared** — 4 conexiones QUIC activas

### Fase 2: PostgreSQL Multi-Base

**Fecha:** 11 Feb 2026

**Decisión importante:** La BD de México **NO se renombró**. En lugar de `inventario_django` → `inventario_mexico`, los aliases `default` y `mexico` en Django apuntan ambos a `inventario_django`. Esto evitó downtime y riesgo innecesario.

**Lo que se hizo:**

1. Creada BD `inventario_argentina` con `OWNER django_user`, `ENCODING UTF8`, `LC_COLLATE es_ES.UTF-8` (se usó `es_ES` porque `es_AR` no estaba disponible)
2. Aplicadas todas las migraciones: `python manage.py migrate --database=argentina` → 55 tablas
3. Replicados 9 grupos con permisos usando `scripts/manage_grupos.py`
4. Creado superusuario `admin` (contraseña configurada)

### Fase 4: Nginx Subdominios

**Fecha:** 11 Feb 2026

Se editó el archivo existente `/etc/nginx/sites-available/inventario-django` (no se creó uno nuevo). La configuración final tiene **5 bloques server**:

| Bloque | Función | Puerto |
|--------|---------|--------|
| 1 | HTTP → HTTPS redirect (todos los dominios) | 80 |
| 2 | HTTPS `sigmasystem.work` → redirect 301 a `mexico.sigmasystem.work` | 443 |
| 3 | HTTPS subdominios de país (`mexico.*`, `argentina.*`) | 443 |
| 4 | Acceso LAN directo (`192.168.100.22`) | 80 |
| 5 | Acceso Tailscale (`100.82.148.52`) | 80 |

### Fase 5: Media Files por País

**Fecha:** 11 Feb 2026

**Decisión importante:** NO fue necesario ejecutar `UPDATE` en la BD para actualizar rutas de archivos. El `DynamicFileSystemStorage` agrega el prefijo `mexico/` automáticamente en `url()`, `path()` y `_save()`. La BD guarda rutas sin prefijo (ej: `servicio_tecnico/imagenes/2025/10/foto.jpg`).

**Lo que se hizo:**

1. **Mover archivos del disco 1TB:** `mv` de las carpetas existentes a `media/mexico/` (instantáneo, mismo filesystem)
2. **Copiar archivos del disco local:** ~3.5 GB adicionales desde `/var/www/.../media/` que no estaban en el disco 1TB
3. **Crear estructura Argentina:** Directorios vacíos `media/argentina/{empleados,servicio_tecnico}/`
4. **Permisos:** `chown -R sicsystem:www-data`, `chmod` apropiados

### Fase 6: Código Hardcoded (Alcance Reducido)

**Commit:** `88016f8` (10 Feb 2026)

**Alcance reducido por decisión del usuario:**

| Cambio | Estado | Razón |
|--------|--------|-------|
| Zona horaria dinámica en `inventario/views.py` | ✅ Hecho | Usa `fecha_local_pais()` con config del país |
| URLs dinámicas en `inventario/utils.py` | ✅ Hecho | Usa `pais['url_base']` |
| Empresa en template `imagenes_cliente.html` | ✅ Hecho | Usa `{{ empresa_nombre }}` |
| Contexto de email en `servicio_tecnico/views.py` | ✅ Hecho | Pasa empresa_nombre y pais_nombre |
| Removidas etiquetas `(MXN)` en `almacen/models.py` | ✅ Hecho | 3 campos + migración 0013 |
| Símbolo `$` en formato de moneda | ❌ Diferido | `$` es correcto para pesos MXN y ARS |
| Datos de empresa en PDFs RHITSO | ❌ Diferido | RHITSO es exclusivo de México |
| Precios de paquetes en `constants.py` | ❌ Diferido | Se implementará cuando se necesite |
| RHITSO condicional por país | ❌ Diferido | RHITSO deshabilitado en Argentina |

### Fase 7: Migraciones y Datos Iniciales

**Fecha:** 11 Feb 2026

- 55 tablas creadas en `inventario_argentina`
- 9 grupos de permisos con todos sus permisos asignados
- Superusuario `admin` creado
- Datos de Argentina aislados y funcionales

### Fase 8: Pruebas y Lanzamiento

**Fecha:** 11 Feb 2026

Todas las pruebas pasaron:
- Login en ambos países
- Creación de registros aislados
- Subida de archivos al directorio correcto
- Envío de correos
- Sesiones independientes entre subdominios
- Redirección del dominio raíz
- Acceso LAN intacto
- Imágenes media existentes accesibles

---

## 5. Decisiones Reales vs Plan Original

| Aspecto | Plan original (v2.0/v3.0) | Lo que se hizo realmente | Razón |
|---------|---------------------------|--------------------------|-------|
| BD México | Renombrar `inventario_django` → `inventario_mexico` | **NO se renombró**. `default` y `mexico` apuntan a `inventario_django` | Evitar downtime y riesgo. Funciona igual |
| Conectividad | Registros A con IP pública + port forwarding | **Cloudflare Tunnel** (ya existía). Se agregaron subdominios | El servidor ya usaba tunnel, no tenía port forwarding |
| DNS subdominios | Registros A apuntando a IP | **CNAMEs al tunnel** via `cloudflared tunnel route dns` | Requerido por la arquitectura de tunnel |
| Media rutas en BD | `UPDATE ... SET imagen = 'mexico/' \|\| imagen` | **NO necesario**. `DynamicFileSystemStorage` agrega prefijo dinámicamente | Diseño más limpio, sin riesgo de corrupción de datos |
| Media archivos | Solo mover del disco 1TB | Mover del disco 1TB **+ copiar ~3.5 GB del disco local** | Había archivos en ambas ubicaciones |
| Nginx config | Archivo nuevo `/etc/nginx/sites-available/sigmasystem` | Se editó el existente `inventario-django` | Ya existía y tenía bloques LAN/Tailscale que mantener |
| TIME_ZONE | Cambiar a UTC | Se dejó como `America/Mexico_City` | El código ya maneja timezone por país con `fecha_local_pais()` |
| Locale Argentina | `es_AR.UTF-8` | Se usó `es_ES.UTF-8` | `es_AR` no estaba disponible en el servidor |
| Cloudflared → Nginx | `http://localhost:80` | `https://localhost:443` + `noTLSVerify: true` | Evita redirect loop HTTP→HTTPS que causaba el Bloque 1 de Nginx |

---

## 6. Archivos Clave de la Implementación

### 6.1 Código Django (en el repositorio)

| Archivo | Descripción | Commit |
|---------|-------------|--------|
| `config/paises_config.py` | Config centralizada de países (México + Argentina) | `f16dbe6` |
| `config/middleware_pais.py` | PaisMiddleware con thread-locals, detección por subdominio | `f16dbe6` |
| `config/db_router.py` | PaisDBRouter (prioridad: hints → thread-locals → default) | `f16dbe6` |
| `config/context_processors.py` | Variables de país en templates | `f16dbe6` |
| `config/storage_utils.py` | DynamicFileSystemStorage v2.0 con prefijo de país | `f16dbe6` |
| `config/settings.py` | DATABASES (3 aliases), DATABASE_ROUTERS, MIDDLEWARE, etc. | `f16dbe6` |
| `inventario/views.py` | `fecha_local()` con timezone dinámico | `88016f8` |
| `inventario/utils.py` | URLs dinámicas por país en emails | `88016f8` |
| `almacen/models.py` | Removidas etiquetas `(MXN)` de help_texts | `88016f8` |
| `scripts/manage_grupos.py` | Gestión de grupos multi-país | `f16dbe6` |

### 6.2 Configuración del Servidor (fuera del repo)

| Archivo | Descripción |
|---------|-------------|
| `/var/www/inventario-django/inventario-calidad-django/.env` | Variables de entorno (DB_NAME_AR, ALLOWED_HOSTS, etc.) |
| `/etc/cloudflared/config.yml` | Config Cloudflare Tunnel (3 hostnames + catch-all 404) |
| `/etc/nginx/sites-available/inventario-django` | Config Nginx multi-país (5 bloques server) |
| `/etc/ssl/cloudflare/sigmasystem.work.pem` | Certificado Origin Cloudflare wildcard (hasta 2041) |
| `/etc/ssl/cloudflare/sigmasystem.work.key` | Clave privada del certificado |

### 6.3 Bases de Datos

| Alias Django | BD PostgreSQL | País | Notas |
|-------------|---------------|------|-------|
| `default` | `inventario_django` | México (fallback) | Misma BD que `mexico` |
| `mexico` | `inventario_django` | México | Misma BD que `default` |
| `argentina` | `inventario_argentina` | Argentina | BD independiente |

---

## 7. Seguridad Multi-Tenant

### 7.1 Principio de Aislamiento Total

```
Un usuario de México NUNCA puede ver, modificar ni acceder a datos de Argentina, y viceversa.

Capas de aislamiento:
1. Bases de datos separadas (aislamiento físico de datos)
2. Cookies de sesión por subdominio (aislamiento de autenticación)
3. Media files en carpetas separadas (aislamiento de archivos)
4. Thread-locals limpios con try/finally (aislamiento de runtime)
```

### 7.2 Mecanismos de Seguridad

| Aspecto | Implementación |
|---------|---------------|
| Sesiones | `SESSION_COOKIE_DOMAIN = None` → Django usa Host del request. Cookie de México no es válida en Argentina |
| CSRF | Tokens vinculados a la sesión → aislados por subdominio automáticamente |
| Thread-locals | Bloque `try/finally` en PaisMiddleware garantiza limpieza incluso con errores |
| `?pais=` override | Solo funciona con `DEBUG=True`. En producción se ignora completamente |
| ALLOWED_HOSTS | Solo acepta `mexico.sigmasystem.work`, `argentina.sigmasystem.work`, etc. |
| django-axes | Lockout por `username + ip_address`. Compartido entre países (aceptable como medida de seguridad) |
| Host header | Cloudflare Tunnel → Nginx (`proxy_set_header Host $host`) → Django. Sin modificación |

### 7.3 Bug Corregido vs v1.0

El middleware original no limpiaba thread-locals si ocurría una excepción:

```python
# ❌ v1.0 (bug):
self._set_thread_locals(...)
response = self.get_response(request)  # Si explota...
self._clear_thread_locals()             # ...esto NUNCA se ejecuta

# ✅ v2.0 (corregido):
self._set_thread_locals(...)
try:
    response = self.get_response(request)
finally:
    self._clear_thread_locals()  # SIEMPRE se ejecuta
```

---

## 8. Auditoría de Código Hardcoded

La auditoría encontró **178 ocurrencias en 24 archivos** de valores México-específicos. Se priorizaron y resolvieron las críticas. Las restantes están diferidas porque no afectan la operación.

### 8.1 Resueltas

| Tipo | Archivos | Estado |
|------|----------|--------|
| Zona horaria hardcoded | `inventario/views.py` | ✅ Usa `fecha_local_pais()` dinámico |
| URLs hardcoded en emails | `inventario/utils.py` | ✅ Usa `pais['url_base']` |
| Empresa en template email | `imagenes_cliente.html` | ✅ Usa `{{ empresa_nombre }}` |
| Contexto email con datos MX | `servicio_tecnico/views.py` | ✅ Pasa datos del país activo |
| Etiquetas `(MXN)` en models | `almacen/models.py` | ✅ Removidas (3 campos) |

### 8.2 Diferidas (No Bloqueantes)

| Tipo | Ocurrencias | Razón del diferimiento |
|------|-------------|----------------------|
| Símbolo `$` en formato moneda | 85+ en 15 archivos | `$` es correcto para MXN y ARS |
| Datos empresa en PDFs RHITSO | 5 en `pdf_generator.py` | RHITSO es exclusivo de México, deshabilitado en Argentina |
| Precios paquetes en `constants.py` | ~10 | Se implementará cuando Argentina necesite precios propios |
| Contactos RHITSO en `settings.py` | ~40 líneas | RHITSO solo opera en México |
| Sucursal "Satélite" hardcoded | 8 | Funciona por filtro sobre BD; Argentina no tiene esa sucursal |
| Proveedores MX en `constants.py` | ~15 | Argentina tendrá sus propios proveedores en su BD |
| Admin `site_header` conflictivo | 1 | Cosmético, no afecta funcionalidad |
| `base.html` sin indicador de país | 1 | Cosmético, mejora futura |

### 8.3 Aspectos de BD que Necesitan Awareness

Estos puntos fueron evaluados y confirmados como seguros con el router v2.0:

| Código | Riesgo | Mitigación |
|--------|--------|------------|
| `ForcePasswordChangeMiddleware` usa `request.user.empleado` | Query podría ir a BD equivocada | PaisMiddleware va ANTES en la lista de middlewares |
| Signal `pre_save` de `OrdenServicio` usa `objects.get()` | Sin `using=` explícito | Router v2.0 maneja correctamente via hints |
| `sincronizar_grupo_empleado` usa `Group.objects.get()` | Auth tables en BD diferente | Router redirige TODAS las queries (incluyendo auth) a BD del país |

---

## 9. Guía para Agregar un Nuevo País

> **Tiempo estimado: 1-2 horas** (vs 12-16 días la primera implementación)

El sistema está diseñado para ser escalable. Agregar un nuevo país (ej: Colombia) requiere solo configuración, **no cambios de código**.

### Requisitos Previos

- Acceso SSH al servidor (`sicsystem@sicubuserver`)
- Acceso al panel de Cloudflare
- Datos de la empresa del nuevo país (nombre, dirección, teléfono, etc.)

### Paso 1: Configuración Django — `config/paises_config.py`

Agregar un nuevo bloque al diccionario `PAISES_CONFIG`:

```python
# En config/paises_config.py, agregar dentro de PAISES_CONFIG:

'colombia': {
    # --- Identificación ---
    'codigo': 'CO',
    'nombre': 'Colombia',
    'nombre_completo': 'Colombia',
    
    # --- Base de datos ---
    'db_alias': 'colombia',
    
    # --- Zona horaria ---
    'timezone': 'America/Bogota',
    'language_code': 'es-co',
    
    # --- Moneda ---
    'moneda_codigo': 'COP',
    'moneda_simbolo': '$',
    'moneda_nombre': 'Peso Colombiano',
    'moneda_locale': 'es_CO',
    
    # --- Empresa ---
    'empresa_nombre': config('EMPRESA_NOMBRE_CO', default='SIC Colombia'),
    'empresa_nombre_corto': 'SIC Colombia',
    'empresa_direccion': config('EMPRESA_DIRECCION_CO', default='(Pendiente)'),
    'empresa_telefono': config('EMPRESA_TELEFONO_CO', default='(Pendiente)'),
    'empresa_email': config('EMPRESA_EMAIL_CO', default=''),
    
    # --- Contacto de seguimiento ---
    'agente_nombre': config('AGENTE_NOMBRE_CO', default='(Pendiente)'),
    'agente_celular': config('AGENTE_CELULAR_CO', default='(Pendiente)'),
    
    # --- RHITSO ---
    'rhitso_habilitado': False,
    'rhitso_email_recipients': [],
    
    # --- URLs ---
    'dominio': 'colombia.sigmasystem.work',
    'url_base': 'https://colombia.sigmasystem.work',
    
    # --- Media ---
    'media_subdir': 'colombia',
},
```

### Paso 2: Base de Datos — `config/settings.py` y `.env`

**En `.env`**, agregar:

```bash
# Base de datos Colombia
DB_NAME_CO=inventario_colombia

# Empresa Colombia
EMPRESA_NOMBRE_CO=SIC Colombia S.A.S.
EMPRESA_DIRECCION_CO=Calle XX #YY-ZZ, Bogotá, Colombia
EMPRESA_TELEFONO_CO=+57-XXX-XXX-XXXX
EMPRESA_EMAIL_CO=contacto.co@sigmasystem.work
AGENTE_NOMBRE_CO=Nombre del Agente
AGENTE_CELULAR_CO=XXX-XXX-XXXX
```

**En `config/settings.py`**, agregar la BD al diccionario DATABASES (sección PostgreSQL):

```python
'colombia': {
    'ENGINE': DB_ENGINE,
    'NAME': config('DB_NAME_CO', default='inventario_colombia'),
    'USER': config('DB_USER', default='django_user'),
    'PASSWORD': config('DB_PASSWORD', default=''),
    'HOST': config('DB_HOST', default='localhost'),
    'PORT': config('DB_PORT', default='5432'),
    'CONN_MAX_AGE': 600,
    'OPTIONS': {'connect_timeout': 10},
},
```

Y también en la sección SQLite (desarrollo):

```python
'colombia': {
    'ENGINE': DB_ENGINE,
    'NAME': BASE_DIR / config('DB_NAME_CO', default='db_colombia.sqlite3'),
},
```

### Paso 3: Actualizar ALLOWED_HOSTS y CSRF

**En `.env`**, agregar el nuevo subdominio:

```bash
ALLOWED_HOSTS=mexico.sigmasystem.work,argentina.sigmasystem.work,colombia.sigmasystem.work,sigmasystem.work,localhost,127.0.0.1,192.168.100.22,100.82.148.52

CSRF_TRUSTED_ORIGINS=https://mexico.sigmasystem.work,https://argentina.sigmasystem.work,https://colombia.sigmasystem.work,https://sigmasystem.work
```

### Paso 4: Crear Base de Datos PostgreSQL

```bash
# Conectar como superusuario de PostgreSQL
sudo -u postgres psql

# Crear la base de datos
CREATE DATABASE inventario_colombia
    OWNER django_user
    ENCODING 'UTF8'
    LC_COLLATE 'es_ES.UTF-8'
    LC_CTYPE 'es_ES.UTF-8'
    TEMPLATE template0;

# Verificar
\l
# Salir
\q
```

### Paso 5: Migraciones y Datos Iniciales

```bash
# Activar el entorno virtual
source /var/www/inventario-django/venv/bin/activate
cd /var/www/inventario-django/inventario-calidad-django

# Aplicar todas las migraciones
python manage.py migrate --database=colombia

# Verificar que se crearon las tablas (debe ser ~55)
python manage.py dbshell --database=colombia
# Dentro de psql:
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
\q

# Ejecutar script de grupos y permisos
python manage.py shell --database=colombia
# Dentro del shell, ejecutar el script de grupos
exec(open('scripts/manage_grupos.py').read())
# O alternativamente:
# python scripts/manage_grupos.py --database=colombia --action=setup

# Crear superusuario
python manage.py createsuperuser --database=colombia
# Username: admin
# Email: admin@sigmasystem.work
# Password: (elegir una contraseña segura)
```

### Paso 6: Cloudflare Tunnel — Agregar Hostname

**Editar `/etc/cloudflared/config.yml`** y agregar el nuevo hostname:

```yaml
ingress:
  - hostname: mexico.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: true
  - hostname: argentina.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: true
  # NUEVO:
  - hostname: colombia.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: true
  - hostname: sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

**Crear registro DNS del tunnel:**

```bash
cloudflared tunnel route dns --overwrite-dns sigmasystem-tunnel colombia.sigmasystem.work
```

**Reiniciar cloudflared:**

```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared
# Verificar que muestra 4 conexiones activas
```

### Paso 7: Nginx — Agregar `server_name`

**Editar `/etc/nginx/sites-available/inventario-django`** y agregar `colombia.sigmasystem.work` en:

1. **Bloque de HTTP redirect** (puerto 80):
   ```nginx
   server_name sigmasystem.work www.sigmasystem.work
               mexico.sigmasystem.work argentina.sigmasystem.work
               colombia.sigmasystem.work;  # NUEVO
   ```

2. **Bloque HTTPS de subdominios** (puerto 443):
   ```nginx
   server_name mexico.sigmasystem.work
               argentina.sigmasystem.work
               colombia.sigmasystem.work;  # NUEVO
   ```

**Verificar y recargar:**

```bash
sudo nginx -t
# Si dice "syntax is ok":
sudo systemctl reload nginx
```

### Paso 8: Crear Directorios de Media

```bash
sudo mkdir -p /mnt/django_storage/media/colombia/{empleados/fotos,servicio_tecnico/{imagenes,imagenes_originales},scorecard/evidencias,almacen/{productos,cotizaciones,qr_codes}}
sudo chown -R sicsystem:www-data /mnt/django_storage/media/colombia
sudo chmod -R 755 /mnt/django_storage/media/colombia
```

### Paso 9: Reiniciar Gunicorn

```bash
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
# Verificar que arrancó correctamente (5 workers)
```

### Paso 10: Verificar

```bash
# Verificar que responde
curl -I https://colombia.sigmasystem.work/login/
# Debe retornar HTTP 200

# Verificar redirección
curl -I https://sigmasystem.work/
# Debe retornar 301 → mexico.sigmasystem.work

# Probar login en el navegador
# https://colombia.sigmasystem.work/admin/
# Usar las credenciales del superusuario creado en Paso 5
```

### Checklist Rápido para Nuevo País

```
☐ 1. config/paises_config.py → Agregar bloque del país
☐ 2. config/settings.py → Agregar BD en DATABASES (PostgreSQL + SQLite)
☐ 3. .env → DB_NAME_XX, EMPRESA_*, AGENTE_*, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
☐ 4. PostgreSQL → CREATE DATABASE inventario_[pais]
☐ 5. Django → python manage.py migrate --database=[pais]
☐ 6. Grupos → Ejecutar script de permisos en la nueva BD
☐ 7. Superusuario → python manage.py createsuperuser --database=[pais]
☐ 8. /etc/cloudflared/config.yml → Agregar hostname
☐ 9. cloudflared tunnel route dns → Crear CNAME
☐ 10. sudo systemctl restart cloudflared
☐ 11. Nginx → Agregar server_name en bloques HTTP y HTTPS
☐ 12. sudo nginx -t && sudo systemctl reload nginx
☐ 13. mkdir media/[pais] → Crear directorios de media
☐ 14. sudo systemctl restart gunicorn
☐ 15. Verificar con curl y navegador
```

---

## 10. Rollback Plan

### 10.1 Desactivar un País (Sin Revertir Todo)

Si necesitas desactivar un país temporalmente:

1. Remover/comentar el hostname en `/etc/cloudflared/config.yml`
2. Remover el `server_name` en Nginx
3. Comentar la entrada en `PAISES_CONFIG`
4. Remover de `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`
5. Reiniciar servicios: `sudo systemctl restart cloudflared && sudo systemctl reload nginx && sudo systemctl restart gunicorn`

> Los datos se preservan en la BD por si se reactiva.

### 10.2 Rollback Completo a Single-Tenant

> Solo en caso de emergencia grave.

```bash
# 1. Detener servicios
sudo systemctl stop gunicorn

# 2. Restaurar Nginx
sudo cp /etc/nginx/sites-available/inventario-django.bak /etc/nginx/sites-available/inventario-django
sudo nginx -t && sudo systemctl reload nginx

# 3. Restaurar cloudflared
sudo cp /etc/cloudflared/config.yml.bak /etc/cloudflared/config.yml
sudo systemctl restart cloudflared

# 4. Restaurar media (mover de vuelta)
MEDIA="/mnt/django_storage/media"
for dir in servicio_tecnico empleados scorecard almacen; do
    [ -d "$MEDIA/mexico/$dir" ] && mv "$MEDIA/mexico/$dir" "$MEDIA/$dir"
done

# 5. Revertir código (git)
git revert HEAD~N..HEAD  # N = número de commits multi-país

# 6. Restaurar .env desde backup

# 7. Reiniciar
sudo systemctl start gunicorn
```

> **Nota:** NO es necesario revertir rutas en BD porque nunca se hicieron UPDATEs. El storage dinámico simplemente dejará de agregar prefijo.

---

## 11. Consideraciones Futuras

### 11.1 Mejoras Pendientes (No Bloqueantes)

| Mejora | Prioridad | Descripción |
|--------|-----------|-------------|
| Indicador visual de país en `base.html` | Baja | Mostrar bandera o nombre del país en el navbar |
| Admin `site_header` dinámico | Baja | Mostrar "SigmaSystem - México" o "- Argentina" |
| Formato de moneda por país | Media | Implementar `1.234,56` para Argentina cuando se necesite |
| PDFs con datos de empresa dinámicos | Media | Solo si Argentina necesita generar PDFs |
| RHITSO condicional | Baja | Solo si un nuevo país necesita integración con laboratorio externo |
| Precios de paquetes por país | Media | Cuando Argentina defina sus precios |
| Backups automatizados multi-país | Alta | Script cron que respalde ambas BDs independientemente |
| Monitoreo de salud multi-BD | Media | Script que verifique conectividad a todas las BDs |

### 11.2 Zona Horaria

El `TIME_ZONE` en `settings.py` se dejó como `America/Mexico_City` (no se cambió a UTC como proponía el plan). Esto funciona correctamente porque:

- La conversión a hora local se hace en las vistas con `fecha_local_pais()`
- `USE_TZ = True` está activo, Django guarda en UTC en la BD
- El admin de Django muestra la hora de México por defecto (aceptable, los admins están en México)

### 11.3 Backups por País

Recomendación para implementar:

```bash
#!/bin/bash
# scripts/backup_multi_pais.sh
BACKUP_DIR="/var/backups/django"
DATE=$(date +%Y%m%d_%H%M)

for bd in inventario_django inventario_argentina; do
    pg_dump -U django_user -h localhost "$bd" | gzip > "$BACKUP_DIR/${bd}_${DATE}.sql.gz"
done

# Limpieza: mantener últimos 30 días
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
```

---

**Fin del Documento v4.0**

*Implementación completada: 11 de Febrero 2026*  
*Documento actualizado: 11 de Febrero 2026*  
*Versión 4.0: Documentación final post-implementación*
