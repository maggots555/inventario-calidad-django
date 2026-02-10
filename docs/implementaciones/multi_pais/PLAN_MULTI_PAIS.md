# Plan de Implementación: Sistema Multi-País con Subdominios

**Fecha de creación:** 9 de Febrero 2026  
**Versión:** 3.0 (Con Progreso de Implementación)  
**Estado:** En Implementación — Desarrollo completado, pendiente producción  
**Tiempo estimado:** 12-16 días laborales  
**Última actualización:** 10 de Febrero 2026  

---

## Resumen de Progreso (v3.0)

> **Actualizado: 10 de Febrero 2026**

| Fase | Descripción | Estado | Commit | Fecha |
|------|-------------|--------|--------|-------|
| **Fase 0** | Entorno de Desarrollo Local | ✅ **COMPLETADA** | `f16dbe6` | 9 Feb 2026 |
| **Fase 1** | Cloudflare DNS + SSL | ⏳ Pendiente (producción) | — | — |
| **Fase 2** | PostgreSQL Multi-Base | ⏳ Pendiente (producción) | — | — |
| **Fase 3** | Django Multi-Tenancy (Grupos/Permisos) | ✅ **COMPLETADA** | `f16dbe6` | 9 Feb 2026 |
| **Fase 4** | Nginx Subdominios | ⏳ Pendiente (producción) | — | — |
| **Fase 5** | Media Files por País | ⏳ Pendiente (producción) | — | — |
| **Fase 6** | Adaptación de Código Hardcoded | ✅ **COMPLETADA** (alcance reducido) | `88016f8` | 10 Feb 2026 |
| **Fase 7** | Migraciones y Datos Iniciales | ⏳ Pendiente (producción) | — | — |
| **Fase 8** | Pruebas y Lanzamiento | ⏳ Pendiente (producción) | — | — |

### Decisiones Clave Tomadas Durante Implementación

1. **Fase 0+3 se fusionaron**: Todo el código Django multi-tenant (archivos nuevos, settings, scripts de grupos/permisos) se implementó junto en un solo commit (`f16dbe6`), no en fases separadas.

2. **Fase 6 — Alcance reducido por decisión del usuario**:
   - **NO se cambiaron los `$` de moneda** — El símbolo `$` es correcto para todos los pesos latinoamericanos (MXN, ARS, CLP, COP). Solo se removieron las etiquetas explícitas `(MXN)` de help_texts.
   - **NO se tocó código RHITSO** — RHITSO (laboratorio externo) es exclusivo de México. Los archivos `pdf_generator.py`, `rhitso_envio.html`, formularios y vistas de RHITSO mantienen datos hardcodeados de México intencionalmente.
   - **Sub-tareas C, E, G, H, I de Fase 6 se difirieron** — PDFs, formato moneda masivo, precios de paquetes, RHITSO condicional y sucursales/proveedores quedan para cuando se necesiten.

3. **Entorno de desarrollo 100% funcional** — Ambas BDs SQLite (México y Argentina) migradas, datos aislados verificados, superusuario de Argentina creado, flujo end-to-end probado incluyendo subida de fotos.

### Lo que Queda — Todo en Servidor de Producción

Las fases pendientes (1, 2, 4, 5, 7, 8) son **exclusivamente tareas de infraestructura en el servidor de producción**: DNS en Cloudflare, PostgreSQL, Nginx, migración de media files y pruebas finales. No requieren cambios de código en Django.

---

## Índice

0. [Resumen de Progreso](#resumen-de-progreso-v30)
1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Análisis del Sistema Actual](#2-análisis-del-sistema-actual)
3. [Arquitectura Propuesta](#3-arquitectura-propuesta)
4. [Fases de Implementación](#4-fases-de-implementación)
   - [Fase 0: Entorno de Desarrollo Local](#fase-0-entorno-de-desarrollo-local-día-1-2)
   - [Fase 1: Cloudflare DNS + SSL](#fase-1-cloudflare-dns--ssl-día-3)
   - [Fase 2: PostgreSQL Multi-Base](#fase-2-postgresql-multi-base-día-4)
   - [Fase 3: Django Multi-Tenancy](#fase-3-django-multi-tenancy-día-5-8)
   - [Fase 4: Nginx Subdominios](#fase-4-nginx-subdominios-día-9)
   - [Fase 5: Media Files por País](#fase-5-media-files-por-país-día-10)
   - [Fase 6: Adaptación de Código Hardcoded](#fase-6-adaptación-de-código-hardcoded-día-11-12)
   - [Fase 7: Migraciones y Datos](#fase-7-migraciones-y-datos-día-13)
   - [Fase 8: Pruebas y Lanzamiento](#fase-8-pruebas-y-lanzamiento-día-14-16)
5. [Seguridad Multi-Tenant](#5-seguridad-multi-tenant)
6. [Consideraciones Especiales](#6-consideraciones-especiales)
7. [Rollback Plan](#7-rollback-plan)
8. [Checklist de Lanzamiento](#8-checklist-de-lanzamiento)

---

## 1. Resumen Ejecutivo

### Objetivo
Expandir el sistema SigmaSystem para operar en múltiples países de Latinoamérica, comenzando con **Argentina** como país piloto, manteniendo **bases de datos completamente independientes** por país.

### Decisiones Clave Tomadas

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| Arquitectura | Database-per-Tenant manual (sin django-tenants) | Máximo 4-5 países, más simple y control total |
| País piloto | Argentina | Primer mercado de expansión |
| SSL | Cloudflare Full Strict con Origin Certificate | Infraestructura existente |
| Dominio México | Migrar a `mexico.sigmasystem.work` | Consistencia entre países |
| Datos | Completamente independientes por país | Aislamiento total, backups independientes |
| Media Files | Carpetas separadas por país | Separación física de archivos |
| Costo | $0 (infraestructura existente) | Todo en mismo servidor |

### Estructura Final de Subdominios

```
mexico.sigmasystem.work    → BD: inventario_mexico    → Media: /mnt/django_storage/media/mexico/
argentina.sigmasystem.work → BD: inventario_argentina → Media: /mnt/django_storage/media/argentina/
colombia.sigmasystem.work  → BD: inventario_colombia  → Media: /mnt/django_storage/media/colombia/  (futuro)
peru.sigmasystem.work      → BD: inventario_peru      → Media: /mnt/django_storage/media/peru/      (futuro)
```

### Cambios respecto a v1.0

| Área | Problema en v1.0 | Corrección en v2.0 |
|------|-------------------|---------------------|
| Middleware | Thread-locals no se limpiaban en caso de error | Bloque try/finally obligatorio |
| DB Router | No respetaba `.using()` ni `hints['instance']` | Router con soporte completo de hints |
| DB Router | No funcionaba con `manage.py` (sin HTTP request) | Fallback a 'default' fuera de request |
| Storage | `__init__` se ejecuta una sola vez al iniciar Django | Override de `_save()`, `url()` y `path()` |
| Seguridad | Cookies de sesión compartidas entre subdominios | `SESSION_COOKIE_DOMAIN` por subdominio |
| Seguridad | django-axes bloqueo cross-country | Configuración de AXES por IP+username |
| Signals | `OrdenServicio.objects.get()` sin `using=` | Uso de `hints` y `sender.objects.using()` |
| ForcePasswordChange | `request.user.empleado` sin especificar BD | Middleware con awareness de país |
| Hardcoded | Solo 5 valores identificados | **178 ocurrencias** en 24 archivos auditados |
| Desarrollo | Sin sección de entorno local | Nueva Fase 0 completa para desarrollo |

### Cambios en v3.0 (Progreso de implementación)

| Área | Cambio |
|------|--------|
| Fase 0+3 | Implementadas en desarrollo — commit `f16dbe6` |
| Fase 6 | Implementada con alcance reducido — commit `88016f8` |
| Decisión: `$` | No se cambia — correcto para todos los pesos latinoamericanos |
| Decisión: RHITSO | Se mantiene hardcodeado — exclusivo de México |
| Scripts | 4 scripts de grupos/permisos actualizados con soporte `db_alias` |
| Estado | Desarrollo 100% completo, pendiente solo infraestructura de producción |

---

## 2. Análisis del Sistema Actual

### 2.1 Infraestructura

| Componente | Detalle |
|------------|---------|
| Servidor | sicubuserver (187.188.9.208) |
| OS | Ubuntu 24.04 LTS |
| Nginx | 1.24.0 |
| Gunicorn | 5 workers sync, timeout 600s |
| PostgreSQL | 16.11 |
| Django | 5.2.5 |
| Python | 3.12 |
| Dominio | sigmasystem.work (Cloudflare DNS) |

### 2.2 Almacenamiento Disponible

| Disco | Total | Usado | Libre |
|-------|-------|-------|-------|
| `/var/www` | 458 GB | 4.3 GB | 430 GB |
| `/mnt/django_storage` | 916 GB | 24 GB | 846 GB |

### 2.3 Base de Datos Actual

- **Motor:** PostgreSQL
- **Base de datos:** `inventario_django`
- **Usuario:** `django_user`
- **Tamaño media actual:** ~24 GB (principalmente servicio_tecnico)

### 2.4 Estructura de Apps Django

```
inventario-calidad-django/
├── inventario/          # 4 modelos: Sucursal, Producto, Movimiento, Empleado
├── servicio_tecnico/    # 16 modelos: OrdenServicio, Cotizacion, ImagenOrden, etc.
├── scorecard/           # 5 modelos: Incidencia, EvidenciaIncidencia, etc.
├── almacen/             # 14 modelos: ProductoAlmacen, CompraProducto, etc.
└── config/              # Configuración del proyecto
```

**Total: 39 modelos**

### 2.5 Archivos con ImageField/FileField

| App | Modelo | Campo | Ruta upload_to |
|-----|--------|-------|----------------|
| inventario | Empleado | foto_perfil | `empleados/fotos/` |
| servicio_tecnico | ImagenOrden | imagen | `servicio_tecnico/imagenes/{orden}/` |
| servicio_tecnico | ImagenOrden | imagen_original | `servicio_tecnico/imagenes_originales/{orden}/` |
| scorecard | EvidenciaIncidencia | imagen | `scorecard/evidencias/%Y/%m/` |
| almacen | ProductoAlmacen | imagen | `almacen/productos/` |
| almacen | ProductoAlmacen | qr_code | `almacen/qr_codes/` |
| almacen | DiferenciaAuditoria | evidencia | `almacen/auditorias/evidencias/` |
| almacen | ImagenLineaCotizacion | imagen | `almacen/cotizaciones/{solicitud}/` |

### 2.6 AUDITORÍA COMPLETA: Valores Hardcoded que Requieren Adaptación

> **IMPORTANTE**: La v1.0 solo identificó 5 valores. La auditoría exhaustiva encontró **178 ocurrencias en 24 archivos**. A continuación el inventario completo organizado por severidad.

#### 2.6.1 SEVERIDAD CRÍTICA (rompe funcionalidad para otros países)

##### Zona Horaria Hardcoded (2 ocurrencias)

| Archivo | Línea | Código | Impacto |
|---------|-------|--------|---------|
| `config/settings.py` | 196 | `TIME_ZONE = 'America/Mexico_City'` | Todas las fechas del sistema |
| `inventario/views.py` | 91 | `tz_local = ZoneInfo('America/Mexico_City')` | Función `fecha_local()` usada en dashboards |
| `config/settings.py` | 194 | `LANGUAGE_CODE = 'es-mx'` | Locale de formato de fechas/números |

##### URLs Hardcoded (2 ocurrencias)

| Archivo | Línea | Código | Impacto |
|---------|-------|--------|---------|
| `inventario/utils.py` | 203 | `'url_login': 'https://sigmasystem.work/login/'` | Email de credenciales apunta a URL sin subdominio |
| `inventario/utils.py` | 204 | `'url_sistema': 'https://sigmasystem.work'` | Idem |

##### Datos de Empresa en PDFs (5 ocurrencias)

| Archivo | Línea | Código | Impacto |
|---------|-------|--------|---------|
| `servicio_tecnico/utils/pdf_generator.py` | 360 | `"SIC Comercialización y Servicios México SC"` | Metadatos de PDF |
| `servicio_tecnico/utils/pdf_generator.py` | 470 | `"SIC COMERCIALIZACION Y SERVICIOS"` | Encabezado de PDF |
| `servicio_tecnico/utils/pdf_generator.py` | 951 | `"Circuito Economistas 15-A, Col. Satelite..."` | Dirección física en PDF |
| `servicio_tecnico/utils/pdf_generator.py` | 958 | `"Seguimiento con: Alejandro Garcia Tel: 55-35-45-81-92"` | Contacto en PDF |
| `servicio_tecnico/views.py` | 5420 | `'agente_celular': '55-35-45-81-92'` | Teléfono en contexto email |

##### Datos de Empresa en Emails (3 ocurrencias en templates HTML)

| Archivo | Línea | Código |
|---------|-------|--------|
| `servicio_tecnico/templates/.../imagenes_cliente.html` | 471 | `SIC Comercialización y Servicios` |
| `servicio_tecnico/templates/.../rhitso_envio.html` | 358 | `SIC Comercialización y Servicios` |
| `inventario/utils.py` | 202 | `'nombre_sistema': 'Sistema Integral de Gestión SIGMA'` |

#### 2.6.2 SEVERIDAD ALTA (datos incorrectos pero no rompe la app)

##### Moneda Hardcoded — Símbolo `$` en formato (85+ ocurrencias en 15 archivos)

> Todos los valores monetarios usan `f"${value:,.2f}"` sin considerar la moneda del país.

| Archivo | Ocurrencias | Ejemplo |
|---------|-------------|---------|
| `servicio_tecnico/views.py` | 20+ | `f"${metricas['monto_total']:,.2f}"` (línea 7482) |
| `servicio_tecnico/plotly_visualizations.py` | 11 | `f'${x:,.0f}'` (línea 1069) |
| `servicio_tecnico/admin.py` | 8 | `format_html('<strong>${:,.2f}</strong>', subtotal)` (línea 153) |
| `inventario/views.py` | 10 | `f'${valor_total_inventario:,.2f}'` (línea 1395) |
| `servicio_tecnico/ml_advanced/recomendador_acciones.py` | 7 | `f"${optimizacion_precio['mejora_ingreso']:,.0f}"` |
| `servicio_tecnico/ml_advanced/optimizador_precios.py` | 5 | `f"${mejora_ingreso:,.0f}"` |
| `servicio_tecnico/utils_cotizaciones.py` | 4 | `f"${valor_total:,.2f}"` |
| `almacen/views.py` | 3 | `f'${compra.costo_unitario:.2f}'` |
| `almacen/admin.py` | 2 | `f'${obj.costo_total:,.2f}'` |
| `servicio_tecnico/ml_predictor.py` | 1 | `f'${costo_promedio_aceptadas:,.2f}'` |

##### Moneda Hardcoded — Etiqueta `(MXN)` (5 ocurrencias activas)

| Archivo | Línea | Código |
|---------|-------|--------|
| `almacen/models.py` | 439 | `help_text='Último costo de compra por unidad (MXN)'` |
| `almacen/models.py` | 741 | `help_text='Precio por unidad en esta compra (MXN)'` |
| `almacen/models.py` | 3281 | `help_text='Precio por unidad (MXN)'` |
| `servicio_tecnico/forms.py` | 2545 | `'costo_adicional': 'Costo Adicional (MXN)'` |
| `servicio_tecnico/forms.py` | 2663 | `label="Costo Adicional Final (MXN)"` |

##### Precios Hardcoded en Pesos Mexicanos (en `config/constants.py`)

| Línea | Código | Impacto |
|-------|--------|---------|
| 100-106 | `PRECIOS_PAQUETES = {'premium': 5500.00, 'oro': 3850.00, 'plata': 2900.00}` | Precios fijos MXN |
| 110-135 | `DESCRIPCION_PAQUETES` con precios inline (`$5,500`, `$3,250`, `$2,900`) | Texto visible al usuario |

##### Contactos RHITSO México-específicos (en `config/settings.py`)

| Línea | Código | Impacto |
|-------|--------|---------|
| 295-335 | `RHITSO_EMAIL_RECIPIENTS`, `JEFE_CALIDAD_EMAIL`, etc. | Todos son contactos de México |

#### 2.6.3 SEVERIDAD MEDIA (lógica de negocio México-específica)

##### Sucursal "Satélite" Hardcoded (8 ocurrencias)

| Archivo | Línea | Código |
|---------|-------|--------|
| `servicio_tecnico/views.py` | 6093 | `sucursal__nombre__icontains='Satelite'` |
| `servicio_tecnico/views.py` | 6094 | `sucursal__nombre__icontains='Drop'` |
| `servicio_tecnico/views.py` | 6095 | `sucursal__nombre__icontains='MIS'` |
| `servicio_tecnico/views.py` | 949-965 | Lógica de rotación solo para "Satélite > Lab OOW" |
| `servicio_tecnico/utils/pdf_generator.py` | 951 | Dirección física de Satélite |

##### Proveedores México-específicos (en `config/constants.py`)

| Línea | Código |
|-------|--------|
| 379-395 | `PROVEEDORES_CHOICES` con proveedores locales: FRANCISCO RUIZ, GJJ TECNOLOGIA, DAVID CASTAÑEDA, SOL SATA, SUREM, TECNOCITY, etc. |

#### 2.6.4 SEVERIDAD BAJA (scripts de soporte, no afectan la app)

| Archivo | Línea | Código |
|---------|-------|--------|
| `scripts/backup_postgres.sh` | 14 | `DB_NAME="inventario_django"` |
| `scripts/poblado/poblar_sistema.py` | 40-61 | Direcciones de sucursales en CDMX, Monterrey, etc. |
| Scripts en `scripts/verificacion/` | varios | Formato `$` en scripts de verificación |
| Scripts en `scripts/testing/` | varios | Formato `$` en scripts de prueba |

### 2.7 AUDITORÍA: Código que Necesita Awareness de Base de Datos

> Estos archivos hacen queries que NO pasarán por el Database Router correctamente en multi-tenant.

#### 2.7.1 Middleware ForcePasswordChange (`inventario/middleware.py:93`)

```python
# PROBLEMA: Hace query a request.user.empleado sin especificar BD
empleado = request.user.empleado  # ← Django usa 'default', no la BD del país
```

**Riesgo**: En producción con Gunicorn, si el middleware de país se ejecuta DESPUÉS de que Django resuelve `request.user`, la relación `user.empleado` podría consultar la BD equivocada.

**Solución**: El `PaisMiddleware` DEBE ir antes de `ForcePasswordChangeMiddleware` en `MIDDLEWARE`, y el router debe estar activo para ese momento.

#### 2.7.2 Signal pre_save de OrdenServicio (`servicio_tecnico/signals.py:75`)

```python
# PROBLEMA: objects.get() sin using= puede bypasear el router en edge cases
orden_anterior = OrdenServicio.objects.get(pk=instance.pk)
```

**Solución**: Usar `sender.objects.using(instance._state.db).get(pk=instance.pk)` o confiar en que el router resuelve correctamente (el router corregido en v2.0 sí maneja `hints`).

#### 2.7.3 Signal post_save de Empleado (`inventario/signals.py:7`)

```python
# PROBLEMA: sincronizar_grupo_empleado() hace Group.objects.get() 
# Group es de django.contrib.auth - podría estar en BD diferente
grupo = Group.objects.get(name=nombre_grupo)
```

**Solución**: En database-per-tenant, cada BD tiene sus propias tablas de auth. El router redirige TODAS las queries (incluyendo auth) a la BD del país activo. Esto funciona SIEMPRE QUE el router esté activo durante el signal. Con el router corregido v2.0, esto es seguro.

#### 2.7.4 Función `sincronizar_grupo_empleado` (`inventario/utils.py:309-354`)

Misma situación que el signal: usa `Group.objects.get()` y `user.groups.clear()/add()`. Funciona correctamente con el router v2.0 activo.

---

## 3. Arquitectura Propuesta

### 3.1 Diagrama General

```
                        ┌─────────────────────────┐
                        │      CLOUDFLARE          │
                        │   *.sigmasystem.work     │
                        │   (Wildcard DNS + SSL)   │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │        NGINX             │
                        │  server_name *.sigma...  │
                        │  (Extrae subdominio)     │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │      GUNICORN            │
                        │   (5 workers sync)       │
                        └───────────┬─────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │        DJANGO + MIDDLEWARE     │
                    │   PaisMiddleware detecta       │
                    │   subdominio del request       │
                    └──┬──────────┬─────────────┬──┘
                       │          │             │
              ┌────────▼──┐  ┌───▼────────┐ ┌──▼───────────┐
              │ BD México  │  │ BD Argentina│ │ BD Colombia  │
              │ PostgreSQL │  │ PostgreSQL  │ │ PostgreSQL   │
              │ inventario │  │ inventario  │ │ inventario   │
              │ _mexico    │  │ _argentina  │ │ _colombia    │
              └────────────┘  └────────────┘ └──────────────┘
                       │          │             │
              ┌────────▼──┐  ┌───▼────────┐ ┌──▼───────────┐
              │ Media      │  │ Media      │ │ Media        │
              │ /mexico/   │  │ /argentina/│ │ /colombia/   │
              └────────────┘  └────────────┘ └──────────────┘
```

### 3.2 Flujo de un Request

```
1. Usuario accede a: mexico.sigmasystem.work/ordenes/
2. Cloudflare resuelve DNS → IP del servidor (187.188.9.208)
3. Nginx recibe → pasa Host header a Gunicorn
4. Django recibe request con Host: mexico.sigmasystem.work
5. PaisMiddleware:
   a. Extrae "mexico" del Host header
   b. Busca en PAISES_CONFIG → encuentra configuración de México
   c. Guarda en thread-locals: pais_codigo='MX', db_alias='mexico'
   d. Guarda en request.pais_config toda la configuración
6. DatabaseRouter:
   a. Para cada query, consulta thread-locals
   b. Retorna 'mexico' como alias de BD
7. Vista procesa normalmente (queries van a BD correcta)
8. PaisMiddleware (finally): Limpia thread-locals
```

### 3.3 Archivos Nuevos a Crear

| Archivo | Propósito | Líneas aprox |
|---------|-----------|--------------|
| `config/paises_config.py` | Configuración centralizada de todos los países | ~150 |
| `config/middleware_pais.py` | Detección de país por subdominio + thread-locals | ~120 |
| `config/db_router.py` | Enrutamiento de queries a la BD correcta | ~100 |
| `config/context_processors.py` | Variables de país disponibles en todos los templates | ~30 |

> **Nota**: `config/storage_utils.py` ya existe y será **modificado** (no creado desde cero).

---

### 3.4 `config/paises_config.py` — Configuración Centralizada

> **ARCHIVO NUEVO** — Este es el "cerebro" del sistema multi-país. Contiene TODA la información específica de cada país en un solo lugar. Cuando agregas un nuevo país, solo necesitas agregar una entrada aquí.

```python
# config/paises_config.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este archivo es el "diccionario" central de todos los países del sistema.
Cada país tiene su propia configuración: zona horaria, moneda, empresa, etc.

¿POR QUÉ un solo archivo?
- Cuando necesites cambiar algo de un país, solo vienes aquí
- Cuando agregues un nuevo país, solo agregas un bloque aquí
- Evita tener datos de país regados por todo el código

¿CÓMO se usa?
- El middleware lee este archivo para saber qué país corresponde al subdominio
- Las vistas lo usan para formatear moneda, fechas, etc.
- Los templates lo usan via context_processors para mostrar el nombre del país
"""

from decouple import config


# ============================================================================
# CONFIGURACIÓN MAESTRA DE PAÍSES
# ============================================================================
# 
# Cada clave del diccionario es el SUBDOMINIO que identifica al país.
# Ejemplo: 'mexico' → mexico.sigmasystem.work
#
# PARA AGREGAR UN NUEVO PAÍS:
# 1. Copia un bloque existente
# 2. Cambia todos los valores
# 3. Crea la base de datos (Fase 2)
# 4. Agrega el subdominio en DNS (Fase 1)
# 5. ¡Listo!
# ============================================================================

PAISES_CONFIG = {
    'mexico': {
        # --- Identificación ---
        'codigo': 'MX',                    # Código ISO 3166-1 alpha-2
        'nombre': 'México',                # Nombre para mostrar al usuario
        'nombre_completo': 'México',
        
        # --- Base de datos ---
        'db_alias': 'mexico',              # Alias en DATABASES de settings.py
        
        # --- Zona horaria ---
        'timezone': 'America/Mexico_City',
        'language_code': 'es-mx',
        
        # --- Moneda ---
        'moneda_codigo': 'MXN',            # Código ISO 4217
        'moneda_simbolo': '$',             # Símbolo para mostrar
        'moneda_nombre': 'Peso Mexicano',
        'moneda_locale': 'es_MX',          # Para formateo con locale
        
        # --- Empresa ---
        'empresa_nombre': 'SIC Comercialización y Servicios México SC',
        'empresa_nombre_corto': 'SIC México',
        'empresa_direccion': 'Circuito Economistas 15-A, Col. Satélite, Naucalpan, Estado de México, CP 53100',
        'empresa_telefono': '+52-55-35-45-81-92',
        'empresa_email': config('EMPRESA_EMAIL_MX', default='contacto@sigmasystem.work'),
        
        # --- Contacto de seguimiento (para PDFs y emails) ---
        'agente_nombre': 'Alejandro Garcia',
        'agente_celular': '55-35-45-81-92',
        
        # --- RHITSO (laboratorio externo) ---
        'rhitso_habilitado': True,
        'rhitso_email_recipients': [],      # Se cargan desde .env en settings.py
        
        # --- URLs ---
        'dominio': 'mexico.sigmasystem.work',
        'url_base': 'https://mexico.sigmasystem.work',
        
        # --- Media ---
        'media_subdir': 'mexico',           # Subcarpeta dentro de MEDIA_ROOT
    },
    
    'argentina': {
        # --- Identificación ---
        'codigo': 'AR',
        'nombre': 'Argentina',
        'nombre_completo': 'Argentina',
        
        # --- Base de datos ---
        'db_alias': 'argentina',
        
        # --- Zona horaria ---
        'timezone': 'America/Argentina/Buenos_Aires',
        'language_code': 'es-ar',
        
        # --- Moneda ---
        'moneda_codigo': 'ARS',
        'moneda_simbolo': '$',
        'moneda_nombre': 'Peso Argentino',
        'moneda_locale': 'es_AR',
        
        # --- Empresa ---
        'empresa_nombre': config('EMPRESA_NOMBRE_AR', default='SIC Argentina (Pendiente Razón Social)'),
        'empresa_nombre_corto': 'SIC Argentina',
        'empresa_direccion': config('EMPRESA_DIRECCION_AR', default='(Pendiente dirección)'),
        'empresa_telefono': config('EMPRESA_TELEFONO_AR', default='(Pendiente teléfono)'),
        'empresa_email': config('EMPRESA_EMAIL_AR', default=''),
        
        # --- Contacto de seguimiento ---
        'agente_nombre': config('AGENTE_NOMBRE_AR', default='(Pendiente)'),
        'agente_celular': config('AGENTE_CELULAR_AR', default='(Pendiente)'),
        
        # --- RHITSO ---
        'rhitso_habilitado': False,         # Argentina no usa RHITSO inicialmente
        'rhitso_email_recipients': [],
        
        # --- URLs ---
        'dominio': 'argentina.sigmasystem.work',
        'url_base': 'https://argentina.sigmasystem.work',
        
        # --- Media ---
        'media_subdir': 'argentina',
    },
}


# ============================================================================
# MAPEO DE SUBDOMINIO → PAÍS (para lookup rápido en middleware)
# ============================================================================
# Se genera automáticamente desde PAISES_CONFIG
# No necesitas mantener esto manualmente

SUBDOMINIO_A_PAIS = {
    subdominio: datos for subdominio, datos in PAISES_CONFIG.items()
}

# País por defecto cuando no se detecta subdominio (desarrollo local, manage.py, etc.)
PAIS_DEFAULT = 'mexico'


# ============================================================================
# FUNCIONES HELPER — Para usar en vistas, templates y utilidades
# ============================================================================

def get_pais_config(subdominio: str) -> dict | None:
    """
    Obtiene la configuración completa de un país por su subdominio.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función busca en el diccionario PAISES_CONFIG usando el subdominio.
    Si el subdominio no existe, retorna None.
    
    Args:
        subdominio: El subdominio extraído del request (ej: 'mexico', 'argentina')
        
    Returns:
        dict con la configuración del país, o None si no existe
        
    Ejemplo:
        config = get_pais_config('mexico')
        print(config['timezone'])  # 'America/Mexico_City'
    """
    return PAISES_CONFIG.get(subdominio)


def get_pais_por_codigo(codigo: str) -> dict | None:
    """
    Busca un país por su código ISO (MX, AR, CO, PE).
    
    Args:
        codigo: Código ISO del país (ej: 'MX')
        
    Returns:
        dict con la configuración, o None si no existe
    """
    for subdominio, datos in PAISES_CONFIG.items():
        if datos['codigo'] == codigo.upper():
            return datos
    return None


def get_todos_los_paises() -> list[dict]:
    """
    Retorna lista de todos los países configurados.
    Útil para generar selectores de país o menús.
    """
    return [
        {
            'subdominio': sub,
            'codigo': datos['codigo'],
            'nombre': datos['nombre'],
            'url_base': datos['url_base'],
        }
        for sub, datos in PAISES_CONFIG.items()
    ]


def formato_moneda(valor: float, pais_config: dict) -> str:
    """
    Formatea un valor numérico como moneda del país.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    En lugar de hardcodear f"${valor:,.2f}" por todo el código,
    usamos esta función que adapta el símbolo y código de moneda
    según el país activo.
    
    Args:
        valor: Cantidad numérica (ej: 5500.00)
        pais_config: Diccionario de configuración del país
        
    Returns:
        str formateado (ej: '$5,500.00 MXN' o '$5.500,00 ARS')
        
    Ejemplo:
        config_mx = get_pais_config('mexico')
        texto = formato_moneda(5500, config_mx)
        # Resultado: '$5,500.00 MXN'
    """
    simbolo = pais_config.get('moneda_simbolo', '$')
    codigo = pais_config.get('moneda_codigo', '')
    
    # Formateo estándar con separador de miles
    valor_formateado = f"{valor:,.2f}"
    
    return f"{simbolo}{valor_formateado} {codigo}".strip()


def fecha_local_pais(fecha_utc, pais_config: dict):
    """
    Convierte una fecha UTC a la hora local del país.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Reemplaza la función fecha_local() que tenía 'America/Mexico_City'
    hardcodeado. Ahora usa la zona horaria del país activo.
    
    Args:
        fecha_utc: Fecha/hora en UTC (datetime)
        pais_config: Diccionario de configuración del país
        
    Returns:
        datetime en la zona horaria local del país
    """
    from zoneinfo import ZoneInfo
    from django.utils import timezone
    
    tz_name = pais_config.get('timezone', 'America/Mexico_City')
    tz_local = ZoneInfo(tz_name)
    
    if timezone.is_aware(fecha_utc):
        return fecha_utc.astimezone(tz_local)
    else:
        fecha_aware = timezone.make_aware(fecha_utc, timezone.utc)
        return fecha_aware.astimezone(tz_local)
```

---

### 3.5 `config/middleware_pais.py` — Middleware de Detección de País

> **ARCHIVO NUEVO** — Este middleware intercepta CADA request HTTP, extrae el subdominio y establece el país activo en thread-locals para que el Database Router sepa a qué BD enviar las queries.

> **BUG CORREGIDO vs v1.0**: Bloque `try/finally` para limpiar thread-locals incluso si hay excepciones. Sin esto, un worker de Gunicorn podría "recordar" el país de un request anterior si ocurre un error.

```python
# config/middleware_pais.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
Un "middleware" en Django es como un guardia de seguridad en la puerta.
Cada vez que alguien hace un request (visita una página), el middleware
lo intercepta ANTES de que llegue a la vista.

Este middleware hace lo siguiente:
1. Mira la URL que visitó el usuario (ej: mexico.sigmasystem.work)
2. Extrae la parte del subdominio (ej: "mexico")
3. Busca la configuración de ese país
4. Guarda esa info en un lugar especial (thread-locals) para que
   el Database Router sepa a qué base de datos enviar las queries

CONCEPTO CLAVE - Thread-locals:
Imagina que cada "hilo" (thread) de tu servidor es un trabajador.
Thread-locals es como una nota adhesiva personal de cada trabajador.
Si el trabajador A atiende a México, su nota dice "México".
Si el trabajador B atiende a Argentina, su nota dice "Argentina".
Así no se confunden entre sí.

BUG CORREGIDO (v2.0):
La v1.0 NO limpiaba las notas adhesivas si ocurría un error.
Ahora usamos try/finally para SIEMPRE limpiar, sin importar si hubo error.
"""

import threading
import logging

from .paises_config import PAISES_CONFIG, PAIS_DEFAULT, get_pais_config

logger = logging.getLogger(__name__)

# ============================================================================
# THREAD-LOCALS — "Notas adhesivas" por hilo del servidor
# ============================================================================
# 
# EXPLICACIÓN PARA PRINCIPIANTES:
# _thread_locals es una variable global PERO cada thread (hilo) del servidor
# tiene su propia copia. Es como si cada mesero de un restaurante tuviera
# su propia libreta donde anota qué mesa está atendiendo.
#
# Gunicorn usa 5 workers (procesos), y cada uno puede tener múltiples threads.
# Thread-locals garantiza que si un thread atiende a México y otro a Argentina,
# no se mezclen los datos.

_thread_locals = threading.local()


def get_current_db_alias() -> str:
    """
    Retorna el alias de la base de datos del país activo en este thread.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    El Database Router llama a esta función para saber a qué BD enviar
    cada query. Si no hay país activo (ej: manage.py, migrations),
    retorna 'default'.
    
    Returns:
        str: Alias de BD ('mexico', 'argentina', o 'default')
    """
    return getattr(_thread_locals, 'db_alias', 'default')


def get_current_pais_config() -> dict | None:
    """
    Retorna la configuración completa del país activo.
    Útil en vistas y utilidades que necesitan datos del país
    pero no tienen acceso al request.
    
    Returns:
        dict con configuración del país, o None
    """
    return getattr(_thread_locals, 'pais_config', None)


def get_current_pais_codigo() -> str | None:
    """
    Retorna el código ISO del país activo (ej: 'MX', 'AR').
    """
    return getattr(_thread_locals, 'pais_codigo', None)


class PaisMiddleware:
    """
    Middleware que detecta el país del request y configura thread-locals.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este middleware se ejecuta en CADA request, antes que cualquier vista.
    Su trabajo es:
    1. Leer el subdominio de la URL
    2. Buscar la configuración del país
    3. Guardar esa info para que el resto del sistema la use
    4. SIEMPRE limpiar la info al terminar (incluso si hay error)
    
    POSICIÓN EN MIDDLEWARE (settings.py):
    Debe ir DESPUÉS de SessionMiddleware y AuthenticationMiddleware,
    pero ANTES de ForcePasswordChangeMiddleware.
    
    ¿POR QUÉ después de AuthenticationMiddleware?
    Porque necesitamos que request.user ya esté disponible.
    
    ¿POR QUÉ antes de ForcePasswordChangeMiddleware?
    Porque ese middleware hace queries (request.user.empleado)
    y necesita que el DB Router ya sepa a qué BD ir.
    """
    
    def __init__(self, get_response):
        """
        EXPLICACIÓN PARA PRINCIPIANTES:
        __init__ se ejecuta UNA SOLA VEZ cuando Django arranca.
        get_response es la función que llama al siguiente middleware o vista.
        """
        self.get_response = get_response
    
    def __call__(self, request):
        """
        Se ejecuta en CADA request HTTP.
        
        FLUJO:
        1. Detectar país del subdominio
        2. Configurar thread-locals
        3. Procesar request (try)
        4. SIEMPRE limpiar thread-locals (finally)
        
        BUG CORREGIDO (v2.0):
        La v1.0 hacía esto:
            self._set_thread_locals(...)
            response = self.get_response(request)  # ← Si esto explota...
            self._clear_thread_locals()             # ← ...esto NUNCA se ejecuta
        
        La v2.0 usa try/finally:
            self._set_thread_locals(...)
            try:
                response = self.get_response(request)
            finally:
                self._clear_thread_locals()  # ← SIEMPRE se ejecuta
        """
        # Paso 1: Detectar el país
        pais_subdominio = self._detectar_pais(request)
        pais_config = get_pais_config(pais_subdominio)
        
        if pais_config is None:
            # Subdominio no reconocido → usar país por defecto
            logger.warning(
                f"Subdominio no reconocido: '{pais_subdominio}' "
                f"(Host: {request.get_host()}). Usando país default: {PAIS_DEFAULT}"
            )
            pais_subdominio = PAIS_DEFAULT
            pais_config = get_pais_config(PAIS_DEFAULT)
        
        # Paso 2: Configurar thread-locals y request
        self._set_thread_locals(pais_config)
        request.pais_config = pais_config
        request.pais_codigo = pais_config['codigo']
        request.pais_subdominio = pais_subdominio
        
        # Paso 3: Procesar request con limpieza garantizada
        try:
            response = self.get_response(request)
        finally:
            # Paso 4: SIEMPRE limpiar thread-locals
            # Esto es CRÍTICO — sin esto, el siguiente request en este
            # thread podría heredar datos del país equivocado
            self._clear_thread_locals()
        
        return response
    
    def _detectar_pais(self, request) -> str:
        """
        Detecta el país a partir del Host header del request.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Cuando visitas mexico.sigmasystem.work, el navegador envía
        un header "Host: mexico.sigmasystem.work". Esta función
        extrae "mexico" de ese header.
        
        MODO DESARROLLO:
        En desarrollo local, los subdominios pueden no funcionar.
        Por eso soportamos un parámetro GET ?pais=argentina
        que tiene prioridad sobre el subdominio.
        Esto permite probar: http://localhost:8000/ordenes/?pais=argentina
        
        Returns:
            str: Subdominio del país (ej: 'mexico', 'argentina')
        """
        # Prioridad 1: Parámetro GET para desarrollo
        # SOLO funciona si DEBUG=True (seguridad)
        from django.conf import settings
        if settings.DEBUG:
            pais_param = request.GET.get('pais')
            if pais_param and pais_param in PAISES_CONFIG:
                return pais_param
        
        # Prioridad 2: Subdominio del Host header
        host = request.get_host().split(':')[0]  # Quitar puerto si existe
        
        # Extraer subdominio: "mexico.sigmasystem.work" → "mexico"
        parts = host.split('.')
        
        if len(parts) >= 3:
            # Tiene subdominio: mexico.sigmasystem.work → ['mexico', 'sigmasystem', 'work']
            subdominio = parts[0]
            if subdominio in PAISES_CONFIG:
                return subdominio
        
        # También soportar: mexico.localhost (para desarrollo con /etc/hosts)
        if len(parts) >= 2:
            subdominio = parts[0]
            if subdominio in PAISES_CONFIG:
                return subdominio
        
        # No se detectó país → usar default
        return PAIS_DEFAULT
    
    def _set_thread_locals(self, pais_config: dict):
        """Guarda la configuración del país en thread-locals."""
        _thread_locals.pais_codigo = pais_config['codigo']
        _thread_locals.db_alias = pais_config['db_alias']
        _thread_locals.pais_config = pais_config
    
    def _clear_thread_locals(self):
        """
        Limpia thread-locals al terminar el request.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Esto es como borrar la pizarra después de cada clase.
        Si no lo haces, el siguiente "estudiante" (request) podría
        ver datos que no le corresponden.
        
        Usamos hasattr() porque en algunos edge cases el atributo
        podría no existir (ej: si _set_thread_locals falló a medias).
        """
        if hasattr(_thread_locals, 'pais_codigo'):
            del _thread_locals.pais_codigo
        if hasattr(_thread_locals, 'db_alias'):
            del _thread_locals.db_alias
        if hasattr(_thread_locals, 'pais_config'):
            del _thread_locals.pais_config
```

---

### 3.6 `config/db_router.py` — Database Router Corregido

> **ARCHIVO NUEVO** — El Database Router le dice a Django a qué base de datos enviar cada query. Es el "GPS" que dirige el tráfico de datos al país correcto.

> **BUGS CORREGIDOS vs v1.0**:
> 1. Ahora respeta `hints['instance']._state.db` (para `.using()` explícito)
> 2. Funciona correctamente fuera de requests HTTP (`manage.py`, `shell`)
> 3. Controla `allow_migrate` para aplicar migraciones solo en la BD indicada

```python
# config/db_router.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
En Django, normalmente todas las queries van a una sola base de datos.
Pero nosotros tenemos una BD por país: inventario_mexico, inventario_argentina, etc.

El Database Router es una clase que Django consulta ANTES de cada query:
- "¿Dónde leo este modelo?" → db_for_read()
- "¿Dónde escribo este modelo?" → db_for_write()
- "¿Puedo hacer relaciones entre estas tablas?" → allow_relation()
- "¿Aplico esta migración en esta BD?" → allow_migrate()

CÓMO FUNCIONA:
1. El PaisMiddleware guarda en thread-locals el país activo
2. Este router consulta thread-locals para saber la BD
3. Si hay un hint de instancia (ej: .using('argentina')), lo respeta

BUGS CORREGIDOS (v2.0):
- v1.0 ignoraba hints['instance'] — si hacías .using('argentina'),
  el router podía enviar la query a otra BD
- v1.0 fallaba con manage.py porque no hay request HTTP activo
  (thread-locals está vacío)
"""

import logging
from .middleware_pais import get_current_db_alias

logger = logging.getLogger(__name__)


class PaisDBRouter:
    """
    Router que dirige queries a la base de datos del país activo.
    
    ORDEN DE PRIORIDAD para determinar la BD:
    1. hints['instance']._state.db — Si el objeto ya sabe su BD (ej: .using())
    2. Thread-locals (del PaisMiddleware) — País del request actual
    3. 'default' — Fallback seguro (para manage.py, migrations, shell)
    """
    
    def _get_db(self, model, **hints) -> str:
        """
        Determina la base de datos correcta para una operación.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este método privado centraliza la lógica de decisión.
        Tanto db_for_read como db_for_write lo usan.
        
        La prioridad es:
        1. Si el ORM ya tiene una BD asignada (hints), usarla
        2. Si hay un request activo (thread-locals), usar esa BD
        3. Si nada funciona, usar 'default' (seguro)
        
        Args:
            model: La clase del modelo (ej: OrdenServicio, Producto)
            **hints: Pistas que Django pasa, como la instancia del objeto
            
        Returns:
            str: Alias de la base de datos ('mexico', 'argentina', 'default')
        """
        # PRIORIDAD 1: Respetar BD de la instancia (para .using() explícito)
        # 
        # EXPLICACIÓN: Cuando haces OrdenServicio.objects.using('argentina').all()
        # Django pasa hints={'instance': <objeto>} y ese objeto tiene
        # _state.db = 'argentina'. Debemos respetar eso.
        instance = hints.get('instance')
        if instance is not None:
            db = getattr(getattr(instance, '_state', None), 'db', None)
            if db is not None:
                return db
        
        # PRIORIDAD 2: Thread-locals del middleware (request activo)
        #
        # EXPLICACIÓN: Si hay un request HTTP activo, el PaisMiddleware
        # ya guardó el alias de BD en thread-locals.
        db_alias = get_current_db_alias()
        if db_alias and db_alias != 'default':
            return db_alias
        
        # PRIORIDAD 3: Fallback a 'default'
        #
        # EXPLICACIÓN: Esto ocurre cuando:
        # - Ejecutas manage.py (no hay request HTTP)
        # - Ejecutas python manage.py shell
        # - Ejecutas migraciones
        # - Un celery task (si lo agregas en el futuro)
        # En estos casos, 'default' apunta a México (BD principal)
        return 'default'
    
    def db_for_read(self, model, **hints) -> str:
        """
        ¿En qué BD busco cuando QUIERO LEER datos?
        
        Django llama esto para: Model.objects.all(), .filter(), .get(), etc.
        """
        return self._get_db(model, **hints)
    
    def db_for_write(self, model, **hints) -> str:
        """
        ¿En qué BD escribo cuando QUIERO GUARDAR datos?
        
        Django llama esto para: .save(), .create(), .delete(), .update(), etc.
        """
        return self._get_db(model, **hints)
    
    def allow_relation(self, obj1, obj2, **hints) -> bool | None:
        """
        ¿Puedo crear una relación (ForeignKey) entre estos dos objetos?
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Django pregunta esto cuando intentas hacer algo como:
            orden.tecnico = empleado  # ForeignKey
        
        Si 'orden' está en BD México y 'empleado' en BD Argentina,
        eso sería un ERROR (no puedes hacer JOIN entre BDs diferentes).
        
        Regla: Solo permitir relaciones si ambos objetos están en la misma BD.
        
        Returns:
            True: Sí permitir
            False: No permitir
            None: No tengo opinión (dejar que Django decida)
        """
        db1 = getattr(getattr(obj1, '_state', None), 'db', None)
        db2 = getattr(getattr(obj2, '_state', None), 'db', None)
        
        if db1 and db2:
            return db1 == db2
        
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints) -> bool | None:
        """
        ¿Aplico esta migración en esta base de datos?
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Cuando ejecutas: python manage.py migrate --database=argentina
        Django pregunta para CADA migración: "¿La aplico en 'argentina'?"
        
        Nuestra respuesta: SÍ, todas las apps van a todas las BDs.
        Cada país tiene una copia completa del schema (todas las tablas).
        
        Esto es diferente a un setup donde auth va a una BD y el resto a otra.
        En nuestro caso, CADA país tiene users, ordenes, productos, TODO.
        
        Returns:
            True: Sí aplicar migración
            None: Dejar que Django decida (equivalente a True para la mayoría)
        """
        # Todas las apps van a todas las BDs de país
        # Cada BD es una copia completa e independiente
        return True
```

---

### 3.7 `config/context_processors.py` — Variables en Templates

> **ARCHIVO NUEVO** — Hace que la información del país esté disponible automáticamente en TODOS los templates sin tener que pasarla manualmente desde cada vista.

```python
# config/context_processors.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
Un "context processor" en Django es una función que agrega variables
automáticamente a TODOS los templates. Sin esto, tendrías que hacer:

    # En CADA vista:
    return render(request, 'mi_template.html', {
        'pais_nombre': 'México',
        'moneda_simbolo': '$',
        ... (repetir en las 100+ vistas del sistema)
    })

Con un context processor, esas variables están disponibles en
TODOS los templates automáticamente. Solo necesitas registrar
esta función en TEMPLATES → OPTIONS → context_processors en settings.py.

Uso en templates:
    <title>SigmaSystem - {{ pais_nombre }}</title>
    <span>{{ empresa_nombre }}</span>
    <p>Total: {{ moneda_simbolo }}{{ total }}</p>
"""

from .paises_config import PAIS_DEFAULT, get_pais_config, get_todos_los_paises


def pais_context(request):
    """
    Agrega variables del país activo al contexto de todos los templates.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Django llama esta función automáticamente antes de renderizar
    cualquier template. El diccionario que retornamos se "fusiona"
    con el contexto de la vista.
    
    Args:
        request: El request HTTP actual
        
    Returns:
        dict con variables disponibles en todos los templates
    """
    # Obtener configuración del país (el middleware ya la puso en request)
    pais_config = getattr(request, 'pais_config', None)
    
    # Fallback si el middleware no se ejecutó (ej: página de error 500)
    if pais_config is None:
        pais_config = get_pais_config(PAIS_DEFAULT)
    
    return {
        # Información básica del país
        'pais_codigo': pais_config.get('codigo', ''),
        'pais_nombre': pais_config.get('nombre', ''),
        'pais_subdominio': getattr(request, 'pais_subdominio', PAIS_DEFAULT),
        
        # Moneda (para mostrar en templates)
        'moneda_simbolo': pais_config.get('moneda_simbolo', '$'),
        'moneda_codigo': pais_config.get('moneda_codigo', ''),
        
        # Empresa (para headers, footers, emails)
        'empresa_nombre': pais_config.get('empresa_nombre', ''),
        'empresa_nombre_corto': pais_config.get('empresa_nombre_corto', ''),
        'empresa_direccion': pais_config.get('empresa_direccion', ''),
        'empresa_telefono': pais_config.get('empresa_telefono', ''),
        
        # URLs
        'pais_url_base': pais_config.get('url_base', ''),
        'pais_dominio': pais_config.get('dominio', ''),
        
        # Lista de todos los países (para selector de país en el navbar)
        'todos_los_paises': get_todos_los_paises(),
        
        # Config completa (para acceso avanzado en templates)
        'pais_config': pais_config,
    }
```

---

### 3.8 Modificaciones a `config/storage_utils.py` — Storage Multi-País

> **ARCHIVO EXISTENTE — MODIFICACIÓN**. El `DynamicFileSystemStorage` actual funciona para un solo país. Necesitamos que organice los archivos en subcarpetas por país (`/mexico/`, `/argentina/`).

> **BUG CORREGIDO vs v1.0**: La v1.0 ponía la detección de país en `__init__()`, pero Django instancia el storage UNA SOLA VEZ al arrancar. La v2.0 detecta el país en cada operación (`_save()`, `url()`, `path()`).

```python
# ============================================================================
# CAMBIOS EN config/storage_utils.py (clase DynamicFileSystemStorage)
# ============================================================================
# 
# NO reescribir todo el archivo. Solo modificar la clase DynamicFileSystemStorage.
# Las funciones auxiliares (get_disk_usage, should_use_alternate_storage, etc.)
# se mantienen igual.
#
# EXPLICACIÓN DEL CAMBIO:
# Antes: Los archivos se guardaban en /media/servicio_tecnico/imagenes/123/
# Ahora: Se guardan en /media/mexico/servicio_tecnico/imagenes/123/
#                    o en /media/argentina/servicio_tecnico/imagenes/123/
#
# El prefijo del país se agrega automáticamente sin cambiar los modelos.

class DynamicFileSystemStorage(FileSystemStorage):
    """
    Sistema de almacenamiento con soporte para disco alterno Y multi-país.
    
    EXPLICACIÓN:
    v1.0: Solo manejaba failover entre disco principal y alterno.
    v2.0: También organiza archivos por país usando subcarpetas.
    
    Ejemplo de rutas generadas:
    - México:    /mnt/django_storage/media/mexico/servicio_tecnico/imagenes/123/foto.jpg
    - Argentina: /mnt/django_storage/media/argentina/servicio_tecnico/imagenes/123/foto.jpg
    """
    
    def __init__(self, **kwargs):
        """
        Inicializa el storage con la ruta activa.
        
        NOTA IMPORTANTE (BUG CORREGIDO v2.0):
        Este __init__ se ejecuta UNA SOLA VEZ cuando Django arranca.
        NO ponemos lógica de país aquí porque el país cambia con cada request.
        La detección de país se hace en _save(), url() y path().
        """
        active_path = get_active_storage_path()
        kwargs['location'] = active_path
        super().__init__(**kwargs)
        print(f"[DYNAMIC STORAGE] Inicializado con ruta base: {active_path}")
    
    def _get_country_prefix(self) -> str:
        """
        Obtiene el prefijo de carpeta del país activo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Esta función consulta el middleware (thread-locals) para saber
        qué país está activo y retorna su subcarpeta de media.
        
        Si no hay país activo (ej: manage.py, migrations), retorna
        el país por defecto para no romper nada.
        
        Returns:
            str: Subcarpeta del país (ej: 'mexico', 'argentina')
        """
        from config.middleware_pais import get_current_pais_config
        from config.paises_config import PAIS_DEFAULT, PAISES_CONFIG
        
        pais_config = get_current_pais_config()
        if pais_config:
            return pais_config.get('media_subdir', PAIS_DEFAULT)
        
        # Fallback: país por defecto
        return PAISES_CONFIG.get(PAIS_DEFAULT, {}).get('media_subdir', PAIS_DEFAULT)
    
    def _save(self, name, content):
        """
        Guarda un archivo con prefijo de país.
        
        CAMBIO v2.0:
        Antes: guardaba en /media/servicio_tecnico/imagenes/123/foto.jpg
        Ahora: guarda en /media/mexico/servicio_tecnico/imagenes/123/foto.jpg
        """
        import os
        
        # Verificar espacio y actualizar ruta si es necesario
        active_path = get_active_storage_path()
        if Path(self.location) != active_path:
            print(f"[DYNAMIC STORAGE] Cambiando ubicación de {self.location} a {active_path}")
            self.location = active_path
        
        # Agregar prefijo de país al nombre del archivo
        country_prefix = self._get_country_prefix()
        if not name.startswith(country_prefix + '/'):
            name = os.path.join(country_prefix, name)
        
        return super()._save(name, content)
    
    def url(self, name):
        """
        Genera la URL del archivo con prefijo de país.
        
        CAMBIO v2.0:
        Antes: /media/servicio_tecnico/imagenes/123/foto.jpg
        Ahora: /media/mexico/servicio_tecnico/imagenes/123/foto.jpg
        """
        import os
        country_prefix = self._get_country_prefix()
        if not name.startswith(country_prefix + '/'):
            name = os.path.join(country_prefix, name)
        return super().url(name)
    
    def path(self, name):
        """
        Genera la ruta absoluta del archivo con prefijo de país.
        
        CAMBIO v2.0:
        Antes: /mnt/django_storage/media/servicio_tecnico/imagenes/123/foto.jpg
        Ahora: /mnt/django_storage/media/mexico/servicio_tecnico/imagenes/123/foto.jpg
        """
        import os
        country_prefix = self._get_country_prefix()
        if not name.startswith(country_prefix + '/'):
            name = os.path.join(country_prefix, name)
        return super().path(name)
```

> **⚠️ NOTA SOBRE MIGRACIÓN DE ARCHIVOS EXISTENTES**: Los archivos actuales de México están en `/media/servicio_tecnico/imagenes/...` (sin prefijo de país). Después de activar el storage multi-país, hay que mover los archivos existentes a `/media/mexico/servicio_tecnico/imagenes/...`. Esto se detalla en la Fase 5.

---

### 3.9 Resumen de Archivos y Dependencias

```
config/paises_config.py          ← No depende de nada (base)
         │
         ▼
config/middleware_pais.py        ← Depende de paises_config.py
         │
         ▼
config/db_router.py              ← Depende de middleware_pais.py (thread-locals)
config/context_processors.py     ← Depende de paises_config.py
config/storage_utils.py          ← Depende de middleware_pais.py + paises_config.py
```

**Orden de implementación obligatorio**:
1. Primero: `paises_config.py` (sin dependencias)
2. Segundo: `middleware_pais.py` (necesita paises_config)
3. Tercero: `db_router.py`, `context_processors.py`, `storage_utils.py` (necesitan los anteriores)

---

## 4. Fases de Implementación

### Fase 0: Entorno de Desarrollo Local (Día 1-2) ✅ COMPLETADA

> **COMPLETADA** — Commit `f16dbe6` (9 Feb 2026)  
> Todos los archivos creados, settings configurados, ambas BDs migradas, aislamiento verificado.

> **NUEVA EN v2.0** — La v1.0 no tenía una fase de desarrollo local. Esto causaría que el primer día de pruebas fuera directamente en producción, algo muy riesgoso.

#### 4.0.1 Objetivo

Configurar un entorno de desarrollo local donde puedas probar el sistema multi-país **sin tocar el servidor de producción**. Esto incluye:

- Múltiples bases de datos SQLite (una por país)
- Subdominios locales usando `/etc/hosts`
- Parámetro `?pais=` como alternativa rápida

#### 4.0.2 Múltiples SQLite para Desarrollo

```bash
# Estructura de BDs en desarrollo:
inventario-calidad-django/
├── db.sqlite3              # BD por defecto (México) — ya existe
├── db_argentina.sqlite3    # BD Argentina — nueva
└── db_colombia.sqlite3     # BD Colombia — nueva (futuro)
```

**Ventaja**: No necesitas instalar PostgreSQL localmente para probar multi-tenant.

#### 4.0.3 Configurar `/etc/hosts` (subdominios locales)

```bash
# Agregar al archivo /etc/hosts (requiere permisos de administrador)
# En Linux/Mac: sudo nano /etc/hosts
# En Windows: C:\Windows\System32\drivers\etc\hosts

127.0.0.1   mexico.localhost
127.0.0.1   argentina.localhost
```

Después de esto puedes acceder a:
- `http://mexico.localhost:8000/` → México
- `http://argentina.localhost:8000/` → Argentina

#### 4.0.4 Alternativa sin `/etc/hosts`: Parámetro GET

Si no puedes o no quieres modificar `/etc/hosts`, el middleware soporta:

```
http://localhost:8000/ordenes/?pais=argentina
http://localhost:8000/ordenes/?pais=mexico
```

> **Nota de seguridad**: El parámetro `?pais=` solo funciona cuando `DEBUG=True`. En producción se ignora completamente.

#### 4.0.5 Variables de Entorno para Desarrollo (`.env`)

```bash
# Agregar a tu .env local:

# Base de datos (ya existente — SQLite para desarrollo)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Base de datos Argentina (nueva)
DB_NAME_AR=db_argentina.sqlite3

# Debug activo para desarrollo
DEBUG=True
```

#### 4.0.6 Crear BD Argentina en Desarrollo

```bash
# Paso 1: Aplicar migraciones a la BD de Argentina
python manage.py migrate --database=argentina

# Paso 2: Crear superusuario en Argentina
python manage.py createsuperuser --database=argentina

# Paso 3: Verificar que ambas BDs funcionan
python manage.py shell
>>> from inventario.models import Producto
>>> Producto.objects.using('mexico').count()     # Debe funcionar
>>> Producto.objects.using('argentina').count()   # Debe retornar 0
```

#### 4.0.7 Pruebas Básicas en Desarrollo

```bash
# Test 1: Verificar middleware con ?pais=
# Abrir navegador: http://localhost:8000/?pais=argentina
# → Debería mostrar "Argentina" en el navbar (cuando se implemente el context processor)

# Test 2: Crear un producto en cada país
python manage.py shell
>>> from inventario.models import Producto
>>> Producto.objects.using('mexico').create(nombre='Test México', precio=100)
>>> Producto.objects.using('argentina').create(nombre='Test Argentina', precio=200)
>>> Producto.objects.using('mexico').count()      # → 1 (solo México)
>>> Producto.objects.using('argentina').count()    # → 1 (solo Argentina)

# Test 3: Verificar aislamiento
>>> Producto.objects.using('mexico').filter(nombre='Test Argentina').exists()
# → False (Argentina no aparece en México)
```

#### 4.0.8 Checklist Fase 0

- [x] Crear `config/paises_config.py`
- [x] Crear `config/middleware_pais.py`
- [x] Crear `config/db_router.py`
- [x] Crear `config/context_processors.py`
- [x] Modificar `config/settings.py` (DATABASES, MIDDLEWARE, TEMPLATES, DATABASE_ROUTERS)
- [x] ~~Agregar entradas a `/etc/hosts` para subdominios locales~~ (Se usó `?pais=` en su lugar)
- [x] Ejecutar `migrate --database=argentina`
- [x] Crear superusuario en Argentina
- [x] Pasar tests básicos de aislamiento (shell)
- [x] Probar navegación web con `?pais=argentina`

---

### Fase 1: Cloudflare DNS + SSL (Día 3)

#### 4.1.1 Objetivo

Configurar DNS en Cloudflare para que los subdominios de cada país resuelvan al servidor.

#### 4.1.2 Registros DNS a Crear

| Tipo | Nombre | Contenido | Proxy | TTL |
|------|--------|-----------|-------|-----|
| A | `mexico` | 187.188.9.208 | Proxied (naranja) | Auto |
| A | `argentina` | 187.188.9.208 | Proxied (naranja) | Auto |

> **Nota**: Cloudflare con proxy activo proporciona SSL automático (Full Strict con Origin Certificate ya configurado).

#### 4.1.3 Verificar DNS

```bash
# Desde cualquier máquina:
dig mexico.sigmasystem.work +short
# Debería retornar IPs de Cloudflare (no la IP directa del servidor)

dig argentina.sigmasystem.work +short
# Idem

# Verificar que el servidor responde:
curl -I https://mexico.sigmasystem.work
# Debería retornar 200 o 301 (Nginx aún no configurado para subdominios)
```

#### 4.1.4 Origin Certificate (si no existe)

Si Cloudflare no tiene Origin Certificate para `*.sigmasystem.work`:

1. Cloudflare Dashboard → SSL/TLS → Origin Server
2. Create Certificate
3. Hostnames: `*.sigmasystem.work`, `sigmasystem.work`
4. Certificate Validity: 15 years
5. Guardar `.pem` y `.key` en el servidor
6. Configurar en Nginx (Fase 4)

#### 4.1.5 Migración del Dominio Principal

**IMPORTANTE**: México actualmente está en `sigmasystem.work` (sin subdominio). Debe migrar a `mexico.sigmasystem.work`.

```
ANTES:  sigmasystem.work → Django
DESPUÉS: mexico.sigmasystem.work → Django (México)
         argentina.sigmasystem.work → Django (Argentina)
         sigmasystem.work → Redirect 301 a mexico.sigmasystem.work
```

> La redirección 301 de `sigmasystem.work` → `mexico.sigmasystem.work` se configura en Nginx (Fase 4).

#### 4.1.6 Checklist Fase 1

- [ ] Crear registro A para `mexico.sigmasystem.work`
- [ ] Crear registro A para `argentina.sigmasystem.work`
- [ ] Verificar resolución DNS con `dig`
- [ ] Verificar que Origin Certificate cubre `*.sigmasystem.work`
- [ ] Verificar HTTPS funciona en ambos subdominios (puede dar error 502 hasta que Nginx esté listo)

---

### Fase 2: PostgreSQL Multi-Base (Día 4)

#### 4.2.1 Objetivo

Crear las bases de datos PostgreSQL independientes por país y configurar los accesos.

#### 4.2.2 Renombrar BD Actual (México)

```sql
-- Conectar como superusuario de PostgreSQL
sudo -u postgres psql

-- IMPORTANTE: Antes de renombrar, desconectar todas las sesiones
-- Paso 1: Detener Gunicorn
-- sudo systemctl stop gunicorn

-- Paso 2: Renombrar la BD actual
ALTER DATABASE inventario_django RENAME TO inventario_mexico;

-- Paso 3: Verificar
\l
-- Debería mostrar inventario_mexico
```

> **⚠️ RIESGO**: Renombrar la BD requiere que no haya conexiones activas. Hacerlo durante ventana de mantenimiento (madrugada o fin de semana).

#### 4.2.3 Crear BD para Argentina

```sql
-- Como superusuario de PostgreSQL:
sudo -u postgres psql

-- Crear la base de datos
CREATE DATABASE inventario_argentina
    OWNER django_user
    ENCODING 'UTF8'
    LC_COLLATE 'es_AR.UTF-8'
    LC_CTYPE 'es_AR.UTF-8'
    TEMPLATE template0;

-- Verificar
\l
-- Debería mostrar: inventario_mexico, inventario_argentina

-- Verificar permisos
\c inventario_argentina
SELECT current_user;  -- Debe poder conectar como django_user
```

> **Nota**: Si `es_AR.UTF-8` no está instalado en el servidor, ejecutar:
> ```bash
> sudo locale-gen es_AR.UTF-8
> sudo update-locale
> ```

#### 4.2.4 Esquema Inicial en BD Argentina

```bash
# Aplicar TODAS las migraciones a la nueva BD
python manage.py migrate --database=argentina

# Verificar que las tablas se crearon
python manage.py dbshell --database=argentina
\dt
# Debería listar las ~39 tablas del sistema

# Crear superusuario en Argentina
python manage.py createsuperuser --database=argentina
```

#### 4.2.5 Script de Verificación

```bash
#!/bin/bash
# scripts/verificacion/verificar_multi_db.sh

echo "=== Verificación Multi-Base de Datos ==="

echo ""
echo "--- BD México ---"
python manage.py dbshell --database=mexico << 'EOF'
SELECT COUNT(*) as tablas FROM information_schema.tables 
WHERE table_schema = 'public';
EOF

echo ""
echo "--- BD Argentina ---"
python manage.py dbshell --database=argentina << 'EOF'
SELECT COUNT(*) as tablas FROM information_schema.tables 
WHERE table_schema = 'public';
EOF

echo ""
echo "=== Verificación completada ==="
```

#### 4.2.6 Backup Pre-Cambio

```bash
# ANTES de cualquier cambio, respaldar la BD actual
pg_dump -U django_user -h localhost inventario_django > backup_pre_multi_pais_$(date +%Y%m%d).sql

# Verificar que el backup es válido
pg_restore --list backup_pre_multi_pais_*.sql 2>/dev/null && echo "OK" || echo "Es SQL plano, OK"
```

#### 4.2.7 Checklist Fase 2

- [ ] Backup completo de `inventario_django`
- [ ] Detener Gunicorn para renombrar BD
- [ ] Renombrar `inventario_django` → `inventario_mexico`
- [ ] Crear `inventario_argentina` con locale `es_AR`
- [ ] Aplicar migraciones a `inventario_argentina`
- [ ] Crear superusuario en `inventario_argentina`
- [ ] Verificar tablas en ambas BDs
- [ ] Reiniciar Gunicorn
- [ ] Verificar que México sigue funcionando normalmente

---

### Fase 3: Django Multi-Tenancy (Día 5-8) ✅ COMPLETADA

> **COMPLETADA** — Commit `f16dbe6` (9 Feb 2026)  
> Se implementó junto con Fase 0. Los 4 archivos nuevos, cambios en settings.py, storage_utils.py, y scripts de grupos/permisos para ambas BDs quedaron listos.  
> **Nota**: Los scripts de grupos/permisos (`setup_grupos_permisos.py`, `asignar_grupos_empleados.py`, `manage_grupos.py`, `deploy_permisos_produccion.sh`) se actualizaron con soporte `db_alias`. Ambas BDs tienen 9 grupos con permisos correctos.

> Esta es la fase más crítica. Se modifica `settings.py` y se crean los 4 archivos nuevos de la Sección 3.

#### 4.3.1 Objetivo

Configurar Django para soportar múltiples bases de datos enrutadas por subdominio.

#### 4.3.2 Cambios en `config/settings.py`

##### A) DATABASES — Agregar aliases por país

```python
# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS (Multi-País)
# ============================================================================
# 
# EXPLICACIÓN PARA PRINCIPIANTES:
# Antes teníamos UNA sola base de datos ('default').
# Ahora tenemos una BD por país, pero Django necesita saber
# cómo conectarse a cada una.
#
# 'default' siempre apunta a México (el país principal).
# 'mexico' es un ALIAS que apunta a la misma BD que 'default'.
# 'argentina' apunta a la BD de Argentina.
#
# ¿POR QUÉ 'default' y 'mexico' apuntan a lo mismo?
# Porque manage.py y migrations siempre usan 'default'.
# Si 'default' no existiera, Django fallaría al iniciar.

DB_ENGINE = config('DB_ENGINE', default='django.db.backends.postgresql')

# Determinar si estamos en SQLite (desarrollo) o PostgreSQL (producción)
_is_sqlite = 'sqlite3' in DB_ENGINE

# --- Configuración base para producción (PostgreSQL) ---
if not _is_sqlite:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME', default='inventario_mexico'),
            'USER': config('DB_USER', default='django_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {'connect_timeout': 10},
        },
        'mexico': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME', default='inventario_mexico'),
            'USER': config('DB_USER', default='django_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {'connect_timeout': 10},
        },
        'argentina': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME_AR', default='inventario_argentina'),
            'USER': config('DB_USER', default='django_user'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {'connect_timeout': 10},
        },
    }

# --- Configuración para desarrollo (SQLite) ---
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / config('DB_NAME', default='db.sqlite3'),
        },
        'mexico': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / config('DB_NAME', default='db.sqlite3'),
        },
        'argentina': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / config('DB_NAME_AR', default='db_argentina.sqlite3'),
        },
    }
```

##### B) DATABASE_ROUTERS — Registrar el router

```python
# ============================================================================
# DATABASE ROUTER (Multi-País)
# ============================================================================
# 
# EXPLICACIÓN PARA PRINCIPIANTES:
# Django consulta estos routers para cada query de base de datos.
# Nuestro router redirige las queries a la BD del país activo.
# Si no hay país activo (manage.py, shell), usa 'default' (México).

DATABASE_ROUTERS = ['config.db_router.PaisDBRouter']
```

##### C) MIDDLEWARE — Agregar PaisMiddleware

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Django-Axes: Protección contra fuerza bruta
    'axes.middleware.AxesMiddleware',
    # ┌─────────────────────────────────────────────────────────────┐
    # │ NUEVO (Multi-País): Detecta el país por subdominio          │
    # │ DEBE ir DESPUÉS de AuthenticationMiddleware                  │
    # │ DEBE ir ANTES de ForcePasswordChangeMiddleware               │
    # │                                                              │
    # │ ¿POR QUÉ este orden?                                        │
    # │ 1. AuthenticationMiddleware pone request.user                │
    # │ 2. PaisMiddleware configura la BD del país                   │
    # │ 3. ForcePasswordChangeMiddleware consulta request.user.empleado │
    # │    (necesita que el router ya sepa la BD correcta)           │
    # └─────────────────────────────────────────────────────────────┘
    'config.middleware_pais.PaisMiddleware',
    # Forzar cambio de contraseña en primer login
    'inventario.middleware.ForcePasswordChangeMiddleware',
]
```

> **CAMBIO CRÍTICO**: `ForcePasswordChangeMiddleware` ahora va DESPUÉS de `PaisMiddleware`. Si no se respeta este orden, el query `request.user.empleado` podría ir a la BD equivocada.

##### D) TEMPLATES — Agregar context processor

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # NUEVO (Multi-País): Variables de país en todos los templates
                'config.context_processors.pais_context',
            ],
        },
    },
]
```

##### E) SESSION_COOKIE_DOMAIN — Aislamiento de sesiones

```python
# ============================================================================
# COOKIES DE SESIÓN (Multi-País)
# ============================================================================
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Una cookie de sesión es como tu "pase de entrada" al sistema.
# Sin esta configuración, tu pase de México funcionaría también en Argentina.
# Eso es un problema de seguridad grave.
#
# ¿QUÉ HACE SESSION_COOKIE_DOMAIN?
# Limita la cookie al subdominio específico del país.
# La cookie de mexico.sigmasystem.work NO funciona en argentina.sigmasystem.work.
#
# NOTA: No configuramos esto en DEBUG=True porque en desarrollo
# usamos localhost, y las cookies de subdominio no funcionan con localhost.

if not DEBUG:
    # En producción: cada subdominio tiene su propia cookie
    # NO usar '.sigmasystem.work' (con punto) porque eso compartiría cookies
    # Django determinará el dominio automáticamente del Host header
    SESSION_COOKIE_DOMAIN = None  # Django usa el Host header del request
    
    # Nombres únicos para evitar conflictos
    SESSION_COOKIE_NAME = 'sigma_sessionid'
    CSRF_COOKIE_NAME = 'sigma_csrftoken'
```

##### F) TIME_ZONE y LANGUAGE_CODE — Hacerlos dinámicos

```python
# ============================================================================
# INTERNACIONALIZACIÓN (Multi-País)
# ============================================================================
#
# NOTA: TIME_ZONE y LANGUAGE_CODE aquí son los DEFAULTS del servidor.
# La zona horaria real se aplica por request usando pais_config['timezone'].
# Ver: config/paises_config.py → fecha_local_pais()

LANGUAGE_CODE = 'es-mx'  # Default del servidor (se puede override por país)

TIME_ZONE = 'UTC'  # CAMBIO: Usar UTC como zona del servidor
                    # Las fechas se convierten a local en las vistas
                    # usando fecha_local_pais() de paises_config.py

USE_I18N = True
USE_TZ = True  # IMPORTANTE: Mantener True para que Django guarde en UTC
```

> **CAMBIO IMPORTANTE**: `TIME_ZONE` cambia de `'America/Mexico_City'` a `'UTC'`. Esto es más correcto para un sistema multi-país: el servidor trabaja en UTC y cada país convierte a su hora local. Las fechas almacenadas en BD siguen siendo UTC.

#### 4.3.3 Variables `.env` para Producción

```bash
# Agregar a .env del SERVIDOR de producción:

# BD México (renombrada de inventario_django)
DB_NAME=inventario_mexico

# BD Argentina (nueva)
DB_NAME_AR=inventario_argentina

# Empresa Argentina (llenar cuando se tengan los datos)
EMPRESA_NOMBRE_AR=SIC Argentina (Pendiente)
EMPRESA_DIRECCION_AR=(Pendiente dirección)
EMPRESA_TELEFONO_AR=(Pendiente teléfono)
EMPRESA_EMAIL_AR=contacto.ar@sigmasystem.work
AGENTE_NOMBRE_AR=(Pendiente)
AGENTE_CELULAR_AR=(Pendiente)
```

#### 4.3.4 Crear los 4 Archivos Nuevos

Crear los archivos exactamente como se especifican en la Sección 3:

```bash
# Paso 1: Crear los archivos (en orden de dependencias)
# config/paises_config.py    → Sección 3.4
# config/middleware_pais.py   → Sección 3.5
# config/db_router.py        → Sección 3.6
# config/context_processors.py → Sección 3.7

# Paso 2: Verificar que los imports funcionan
python manage.py shell
>>> from config.paises_config import PAISES_CONFIG
>>> print(PAISES_CONFIG.keys())  # → dict_keys(['mexico', 'argentina'])
>>> from config.middleware_pais import PaisMiddleware
>>> from config.db_router import PaisDBRouter
>>> from config.context_processors import pais_context
>>> print("Todos los imports OK")
```

#### 4.3.5 Modificar `config/storage_utils.py`

Aplicar los cambios de la Sección 3.8 a la clase `DynamicFileSystemStorage`.

#### 4.3.6 Prueba de Integración Completa

```bash
# ANTES de probar en producción, ejecutar en desarrollo:

# 1. Verificar que Django arranca sin errores
python manage.py check

# 2. Verificar que las migraciones están al día
python manage.py showmigrations --database=mexico
python manage.py showmigrations --database=argentina

# 3. Probar aislamiento desde shell
python manage.py shell
>>> from inventario.models import Sucursal
>>> # Crear datos de prueba en cada BD
>>> Sucursal.objects.using('mexico').create(nombre='Satélite México', direccion='CDMX')
>>> Sucursal.objects.using('argentina').create(nombre='Buenos Aires', direccion='CABA')
>>> # Verificar aislamiento
>>> Sucursal.objects.using('mexico').count()      # → N (datos de México)
>>> Sucursal.objects.using('argentina').count()    # → 1 (solo Argentina)
>>> # Verificar que no se mezclan
>>> Sucursal.objects.using('mexico').filter(nombre='Buenos Aires').exists()  # → False

# 4. Probar el servidor de desarrollo
python manage.py runserver
# Abrir: http://localhost:8000/?pais=mexico → Debería funcionar
# Abrir: http://localhost:8000/?pais=argentina → Debería funcionar

# 5. Si configuraste /etc/hosts:
# Abrir: http://mexico.localhost:8000/ → México
# Abrir: http://argentina.localhost:8000/ → Argentina
```

#### 4.3.7 Checklist Fase 3

- [x] Actualizar `DATABASES` en `settings.py` con aliases por país
- [x] Agregar `DATABASE_ROUTERS` en `settings.py`
- [x] Insertar `PaisMiddleware` en `MIDDLEWARE` (después de Auth, antes de ForcePassword)
- [x] Agregar `pais_context` a `TEMPLATES` context_processors
- [x] Configurar `SESSION_COOKIE_DOMAIN` y nombres de cookies
- [x] Cambiar `TIME_ZONE` de `'America/Mexico_City'` a `'UTC'`
- [x] Crear `config/paises_config.py`
- [x] Crear `config/middleware_pais.py`
- [x] Crear `config/db_router.py`
- [x] Crear `config/context_processors.py`
- [x] Modificar `config/storage_utils.py`
- [x] Agregar variables a `.env` (`DB_NAME_AR`, etc.)
- [x] Verificar imports desde `manage.py shell`
- [x] Pasar prueba de aislamiento de datos
- [x] Verificar que Django arranca sin errores (`manage.py check`)
- [x] Probar navegación web con ambos países
- [x] **Adicional**: Actualizar scripts de grupos/permisos con soporte `db_alias`
- [x] **Adicional**: Ejecutar scripts de permisos en ambas BDs (9 grupos cada una)

---

### Fase 4: Nginx Subdominios (Día 9)

#### 4.4.1 Objetivo

Configurar Nginx para recibir los subdominios de cada país y enrutarlos a Gunicorn. Incluye redirección del dominio actual (`sigmasystem.work`) hacia `mexico.sigmasystem.work`.

#### 4.4.2 Configuración Nginx Completa

```nginx
# /etc/nginx/sites-available/sigmasystem
# =========================================================================
# CONFIGURACIÓN NGINX MULTI-PAÍS
# =========================================================================
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Nginx es el servidor web que recibe las peticiones del navegador
# y las envía a Gunicorn (que ejecuta Django).
#
# Antes: Un solo server_name (sigmasystem.work)
# Ahora: Múltiples server_name (mexico/argentina.sigmasystem.work)

# ----- Upstream: Gunicorn (solo UNA instancia para todos los países) -----
# EXPLICACIÓN: Django decide internamente a qué BD enviar las queries.
# No necesitamos múltiples Gunicorn, solo uno.
upstream gunicorn_sigma {
    server unix:/run/gunicorn.sock;
}

# =========================================================================
# BLOQUE 1: Redirección del dominio raíz
# =========================================================================
# Redirige sigmasystem.work → mexico.sigmasystem.work
# Esto es temporal para que los usuarios que tienen bookmarks del
# dominio viejo no pierdan acceso.
server {
    listen 443 ssl http2;
    server_name sigmasystem.work www.sigmasystem.work;
    
    # SSL con Origin Certificate de Cloudflare
    ssl_certificate     /etc/ssl/cloudflare/sigmasystem.work.pem;
    ssl_certificate_key /etc/ssl/cloudflare/sigmasystem.work.key;
    
    # Redirección 301 (permanente) a México
    return 301 https://mexico.sigmasystem.work$request_uri;
}

# =========================================================================
# BLOQUE 2: Servidor principal multi-país
# =========================================================================
# Acepta TODOS los subdominios de país
server {
    listen 443 ssl http2;
    server_name mexico.sigmasystem.work
                argentina.sigmasystem.work;
    # Cuando se agreguen más países, añadir aquí:
    # colombia.sigmasystem.work
    # peru.sigmasystem.work
    
    # SSL con Origin Certificate de Cloudflare (wildcard)
    ssl_certificate     /etc/ssl/cloudflare/sigmasystem.work.pem;
    ssl_certificate_key /etc/ssl/cloudflare/sigmasystem.work.key;
    
    # --- Tamaños de upload ---
    client_max_body_size 200M;
    
    # --- Logs separados por subdominio ---
    # NUEVO v2.0: Logs independientes facilitan debugging por país
    # La variable $host contiene el subdominio completo
    access_log /var/log/nginx/sigma_${host}_access.log;
    error_log  /var/log/nginx/sigma_error.log;
    
    # --- Archivos estáticos ---
    # EXPLICACIÓN: Los archivos estáticos (CSS, JS) son COMPARTIDOS
    # entre todos los países. No necesitan separación.
    location /static/ {
        alias /var/www/inventario-calidad-django/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # --- Archivos de media (uploads de usuarios) ---
    # EXPLICACIÓN: Los archivos de media ahora tienen subcarpetas por país.
    # /media/mexico/servicio_tecnico/imagenes/... 
    # /media/argentina/servicio_tecnico/imagenes/...
    # Nginx sirve el archivo directamente sin pasar por Django (más rápido).
    location /media/ {
        alias /mnt/django_storage/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # --- Favicon ---
    location /favicon.ico {
        alias /var/www/inventario-calidad-django/staticfiles/images/favicon.ico;
        expires 30d;
        access_log off;
    }
    
    # --- Todo lo demás → Gunicorn/Django ---
    location / {
        proxy_pass http://gunicorn_sigma;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts largos para uploads grandes
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
    }
}

# =========================================================================
# BLOQUE 3: Redirección HTTP → HTTPS
# =========================================================================
server {
    listen 80;
    server_name sigmasystem.work
                www.sigmasystem.work
                mexico.sigmasystem.work
                argentina.sigmasystem.work;
    
    return 301 https://$host$request_uri;
}
```

#### 4.4.3 Pasos de Implementación

```bash
# Paso 1: Respaldar configuración actual
sudo cp /etc/nginx/sites-available/sigmasystem /etc/nginx/sites-available/sigmasystem.bak

# Paso 2: Editar configuración
sudo nano /etc/nginx/sites-available/sigmasystem
# (pegar la configuración de arriba)

# Paso 3: Verificar sintaxis
sudo nginx -t
# Debe decir: syntax is ok, test is successful

# Paso 4: Crear directorio para logs si no existe
sudo mkdir -p /var/log/nginx/

# Paso 5: Recargar Nginx (sin downtime)
sudo systemctl reload nginx

# Paso 6: Verificar que funciona
curl -I https://mexico.sigmasystem.work
# → HTTP/2 200

curl -I https://argentina.sigmasystem.work
# → HTTP/2 200

curl -I https://sigmasystem.work
# → HTTP/2 301 Location: https://mexico.sigmasystem.work/
```

#### 4.4.4 Logrotate para Logs por País

```bash
# /etc/logrotate.d/nginx-sigma
/var/log/nginx/sigma_*_access.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
    endscript
}
```

#### 4.4.5 Checklist Fase 4

- [ ] Backup de configuración Nginx actual
- [ ] Editar configuración con bloques multi-país
- [ ] Verificar sintaxis con `nginx -t`
- [ ] Reload Nginx
- [ ] Verificar `mexico.sigmasystem.work` retorna 200
- [ ] Verificar `argentina.sigmasystem.work` retorna 200
- [ ] Verificar `sigmasystem.work` redirecciona 301 a México
- [ ] Verificar que logs se crean por subdominio
- [ ] Configurar logrotate

---

### Fase 5: Media Files por País (Día 10)

#### 4.5.1 Objetivo

Organizar los archivos de media (fotos de órdenes, perfiles, evidencias) en subcarpetas por país y migrar los archivos existentes de México.

#### 4.5.2 Estructura de Directorios Objetivo

```
/mnt/django_storage/media/
├── mexico/
│   ├── servicio_tecnico/
│   │   ├── imagenes/           # Fotos de órdenes
│   │   └── imagenes_originales/
│   ├── empleados/
│   │   └── fotos/              # Fotos de perfil
│   ├── scorecard/
│   │   └── evidencias/
│   └── almacen/
│       ├── productos/
│       ├── qr_codes/
│       ├── auditorias/
│       └── cotizaciones/
├── argentina/
│   ├── servicio_tecnico/
│   │   ├── imagenes/
│   │   └── imagenes_originales/
│   ├── empleados/
│   │   └── fotos/
│   ├── scorecard/
│   │   └── evidencias/
│   └── almacen/
│       ├── productos/
│       ├── qr_codes/
│       ├── auditorias/
│       └── cotizaciones/
```

#### 4.5.3 Script de Migración de Media Existente

```bash
#!/bin/bash
# scripts/migracion/migrar_media_mexico.sh
#
# EXPLICACIÓN:
# Los archivos actuales están en /mnt/django_storage/media/servicio_tecnico/...
# Necesitamos moverlos a /mnt/django_storage/media/mexico/servicio_tecnico/...
#
# IMPORTANTE: Ejecutar ANTES de activar el storage multi-país en Django.
# Si activas primero el storage, los archivos viejos no se encontrarán.

set -e  # Detener si hay error

MEDIA_ROOT="/mnt/django_storage/media"
PAIS="mexico"

echo "=== Migración de Media a estructura multi-país ==="
echo "Media root: $MEDIA_ROOT"
echo "País destino: $PAIS"
echo ""

# Paso 1: Crear directorio del país
echo "[1/4] Creando directorio $MEDIA_ROOT/$PAIS/"
mkdir -p "$MEDIA_ROOT/$PAIS"

# Paso 2: Mover las carpetas de apps al subdirectorio del país
echo "[2/4] Moviendo carpetas de apps..."

# Lista de carpetas a mover (las que contienen uploads de usuarios)
CARPETAS=("servicio_tecnico" "empleados" "scorecard" "almacen")

for carpeta in "${CARPETAS[@]}"; do
    if [ -d "$MEDIA_ROOT/$carpeta" ]; then
        echo "  Moviendo: $carpeta/ → $PAIS/$carpeta/"
        mv "$MEDIA_ROOT/$carpeta" "$MEDIA_ROOT/$PAIS/$carpeta"
    else
        echo "  Creando vacío: $PAIS/$carpeta/"
        mkdir -p "$MEDIA_ROOT/$PAIS/$carpeta"
    fi
done

# Paso 3: Crear estructura para Argentina (vacía)
echo "[3/4] Creando estructura para Argentina..."
PAIS_AR="argentina"
for carpeta in "${CARPETAS[@]}"; do
    mkdir -p "$MEDIA_ROOT/$PAIS_AR/$carpeta"
    echo "  Creado: $PAIS_AR/$carpeta/"
done

# Paso 4: Ajustar permisos
echo "[4/4] Ajustando permisos..."
chown -R www-data:www-data "$MEDIA_ROOT/$PAIS" "$MEDIA_ROOT/$PAIS_AR"
chmod -R 755 "$MEDIA_ROOT/$PAIS" "$MEDIA_ROOT/$PAIS_AR"

echo ""
echo "=== Migración completada ==="
echo ""
echo "Verificación:"
echo "  México:    $(find $MEDIA_ROOT/$PAIS -type f | wc -l) archivos"
echo "  Argentina: $(find $MEDIA_ROOT/$PAIS_AR -type f | wc -l) archivos"
du -sh "$MEDIA_ROOT/$PAIS" "$MEDIA_ROOT/$PAIS_AR"
```

#### 4.5.4 Actualizar Rutas en Base de Datos

> **IMPORTANTE**: Los modelos de Django guardan la ruta del archivo como string en la BD (ej: `servicio_tecnico/imagenes/123/foto.jpg`). Después de mover los archivos, necesitamos actualizar esas rutas para que incluyan el prefijo `mexico/`.

```sql
-- Ejecutar en la BD de México (inventario_mexico):

-- ImagenOrden.imagen
UPDATE servicio_tecnico_imagenorden 
SET imagen = 'mexico/' || imagen 
WHERE imagen NOT LIKE 'mexico/%';

-- ImagenOrden.imagen_original
UPDATE servicio_tecnico_imagenorden 
SET imagen_original = 'mexico/' || imagen_original 
WHERE imagen_original IS NOT NULL 
AND imagen_original != '' 
AND imagen_original NOT LIKE 'mexico/%';

-- Empleado.foto_perfil
UPDATE inventario_empleado 
SET foto_perfil = 'mexico/' || foto_perfil 
WHERE foto_perfil IS NOT NULL 
AND foto_perfil != '' 
AND foto_perfil NOT LIKE 'mexico/%';

-- EvidenciaIncidencia.imagen
UPDATE scorecard_evidenciaincidencia 
SET imagen = 'mexico/' || imagen 
WHERE imagen IS NOT NULL 
AND imagen != '' 
AND imagen NOT LIKE 'mexico/%';

-- ProductoAlmacen.imagen
UPDATE almacen_productoalmacen 
SET imagen = 'mexico/' || imagen 
WHERE imagen IS NOT NULL 
AND imagen != '' 
AND imagen NOT LIKE 'mexico/%';

-- ProductoAlmacen.qr_code
UPDATE almacen_productoalmacen 
SET qr_code = 'mexico/' || qr_code 
WHERE qr_code IS NOT NULL 
AND qr_code != '' 
AND qr_code NOT LIKE 'mexico/%';

-- DiferenciaAuditoria.evidencia
UPDATE almacen_diferenciaauditoria 
SET evidencia = 'mexico/' || evidencia 
WHERE evidencia IS NOT NULL 
AND evidencia != '' 
AND evidencia NOT LIKE 'mexico/%';

-- ImagenLineaCotizacion.imagen
UPDATE almacen_imagenlineacotizacion 
SET imagen = 'mexico/' || imagen 
WHERE imagen IS NOT NULL 
AND imagen != '' 
AND imagen NOT LIKE 'mexico/%';
```

#### 4.5.5 Script de Verificación de Media

```bash
#!/bin/bash
# scripts/verificacion/verificar_media_multi_pais.sh

echo "=== Verificación de Media Multi-País ==="
echo ""

MEDIA_ROOT="/mnt/django_storage/media"

for pais in mexico argentina; do
    echo "--- $pais ---"
    if [ -d "$MEDIA_ROOT/$pais" ]; then
        echo "  Directorio: ✅ Existe"
        echo "  Archivos:   $(find $MEDIA_ROOT/$pais -type f | wc -l)"
        echo "  Tamaño:     $(du -sh $MEDIA_ROOT/$pais | cut -f1)"
        echo "  Subdirs:"
        ls -1 "$MEDIA_ROOT/$pais/" 2>/dev/null | while read dir; do
            echo "    - $dir/ ($(find $MEDIA_ROOT/$pais/$dir -type f | wc -l) archivos)"
        done
    else
        echo "  Directorio: ❌ No existe"
    fi
    echo ""
done

echo "=== Verificación completada ==="
```

#### 4.5.6 Orden de Ejecución (Crítico)

```
1. Detener Gunicorn
2. Ejecutar migrar_media_mexico.sh (mover archivos físicos)
3. Ejecutar queries SQL (actualizar rutas en BD)
4. Activar storage multi-país en settings.py (si no estaba activo)
5. Reiniciar Gunicorn
6. Verificar que las imágenes cargan correctamente en el navegador
7. Verificar URLs de media: /media/mexico/servicio_tecnico/imagenes/...
```

> **⚠️ VENTANA DE MANTENIMIENTO**: Los pasos 1-5 deben ejecutarse en secuencia sin interrumpir. Tiempo estimado: 10-15 minutos dependiendo del volumen de archivos (~24 GB).

#### 4.5.7 Plan de Rollback Media

```bash
# Si algo sale mal, revertir:

# 1. Los archivos se movieron, no se copiaron.
#    Para revertir, mover de vuelta:
mv /mnt/django_storage/media/mexico/servicio_tecnico /mnt/django_storage/media/servicio_tecnico
mv /mnt/django_storage/media/mexico/empleados /mnt/django_storage/media/empleados
# ... etc para cada carpeta

# 2. Revertir queries SQL:
# UPDATE servicio_tecnico_imagenorden 
# SET imagen = REPLACE(imagen, 'mexico/', '') 
# WHERE imagen LIKE 'mexico/%';
# ... etc para cada tabla
```

#### 4.5.8 Checklist Fase 5

- [ ] Crear script `migrar_media_mexico.sh`
- [ ] Backup de BD antes de ejecutar (por las queries SQL)
- [ ] Detener Gunicorn
- [ ] Ejecutar script de migración de archivos
- [ ] Ejecutar queries SQL para actualizar rutas
- [ ] Reiniciar Gunicorn
- [ ] Verificar que imágenes existentes cargan en el navegador
- [ ] Verificar que nuevas subidas van a `/media/mexico/...`
- [ ] Crear directorio vacío para Argentina
- [ ] Ejecutar script de verificación

---

### Fase 6: Adaptación de Código Hardcoded (Día 11-12) ✅ COMPLETADA (alcance reducido)

> **COMPLETADA** — Commit `88016f8` (10 Feb 2026)  
> Se adaptaron los valores críticos. El alcance se redujo por decisión del usuario:
> - **`$` NO se cambió** — Es el símbolo correcto para todos los pesos latinoamericanos.
> - **RHITSO NO se tocó** — Es exclusivo de México. `pdf_generator.py` y templates RHITSO mantienen datos hardcodeados intencionalmente.
> - **Sub-tareas C, E, G, H, I diferidas** — Se implementarán cuando se necesiten para otros países.
>
> **Archivos cambiados**: `inventario/views.py` (zona horaria), `inventario/utils.py` (URLs email), `servicio_tecnico/templates/.../imagenes_cliente.html` (empresa en footer), `servicio_tecnico/views.py` (contexto de email), `almacen/models.py` (removidas etiquetas MXN), `almacen/migrations/0013_*` (migración auto-generada).

> **NUEVA EN v2.0** — La v1.0 no contemplaba esta fase. Sin ella, Argentina tendría moneda MXN, zona horaria de CDMX, nombre de empresa de México, etc.

#### 4.6.1 Objetivo

Reemplazar los **178 valores hardcoded de México** (auditados en Sección 2.6) por lookups dinámicos desde `pais_config`. Esta fase se divide en sub-tareas por prioridad.

#### 4.6.2 Patrón General de Corrección

Para cada valor hardcoded, el patrón de corrección es:

```python
# ❌ ANTES (hardcoded México):
f"${valor:,.2f}"

# ✅ DESPUÉS (dinámico por país):
from config.paises_config import formato_moneda
from config.middleware_pais import get_current_pais_config

pais_config = get_current_pais_config()
formato_moneda(valor, pais_config)
```

En vistas que tienen acceso al `request`:

```python
# ✅ En vistas (acceso directo a request.pais_config):
texto_precio = formato_moneda(valor, request.pais_config)
```

#### 4.6.3 Sub-Tarea A: Zona Horaria (CRÍTICA — 2 archivos)

##### Archivo: `inventario/views.py` (línea 91)

```python
# ❌ ANTES:
def fecha_local(fecha_utc):
    tz_local = ZoneInfo('America/Mexico_City')
    if timezone.is_aware(fecha_utc):
        return fecha_utc.astimezone(tz_local)
    else:
        fecha_utc = timezone.make_aware(fecha_utc, timezone.utc)
        return fecha_utc.astimezone(tz_local)

# ✅ DESPUÉS:
from config.paises_config import fecha_local_pais
from config.middleware_pais import get_current_pais_config

def fecha_local(fecha_utc):
    """
    Convierte fecha UTC a hora local del país activo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Antes esta función siempre convertía a hora de México.
    Ahora detecta automáticamente el país del request actual
    y convierte a la zona horaria correcta.
    """
    pais_config = get_current_pais_config()
    if pais_config is None:
        # Fallback para cuando no hay request (ej: shell, cron)
        from config.paises_config import get_pais_config, PAIS_DEFAULT
        pais_config = get_pais_config(PAIS_DEFAULT)
    return fecha_local_pais(fecha_utc, pais_config)
```

##### Archivo: `config/settings.py` (línea 196)

Ya cubierto en Fase 3 (cambiar `TIME_ZONE` a `'UTC'`).

#### 4.6.4 Sub-Tarea B: URLs de Email (CRÍTICA — 1 archivo)

##### Archivo: `inventario/utils.py` (líneas 203-204)

```python
# ❌ ANTES:
context = {
    'url_login': 'https://sigmasystem.work/login/',
    'url_sistema': 'https://sigmasystem.work',
    'nombre_sistema': 'Sistema Integral de Gestión SIGMA',
}

# ✅ DESPUÉS:
from config.middleware_pais import get_current_pais_config
from config.paises_config import get_pais_config, PAIS_DEFAULT

def _get_context_pais():
    """Obtiene contexto de URLs y empresa del país activo."""
    pais = get_current_pais_config()
    if pais is None:
        pais = get_pais_config(PAIS_DEFAULT)
    return {
        'url_login': f"{pais['url_base']}/login/",
        'url_sistema': pais['url_base'],
        'nombre_sistema': 'Sistema Integral de Gestión SIGMA',
        'empresa_nombre': pais['empresa_nombre'],
    }

# En la función que envía el email:
context = _get_context_pais()
```

#### 4.6.5 Sub-Tarea C: Datos de Empresa en PDFs (CRÍTICA — 1 archivo)

##### Archivo: `servicio_tecnico/utils/pdf_generator.py` (líneas 360, 470, 951, 958)

```python
# ❌ ANTES (valores distribuidos por el archivo):
# Línea 360: "SIC Comercialización y Servicios México SC"
# Línea 470: "SIC COMERCIALIZACION Y SERVICIOS"
# Línea 951: "Circuito Economistas 15-A, Col. Satelite..."
# Línea 958: "Seguimiento con: Alejandro Garcia Tel: 55-35-45-81-92"

# ✅ DESPUÉS:
# Al inicio del archivo o de la función principal del PDF:
from config.middleware_pais import get_current_pais_config
from config.paises_config import get_pais_config, PAIS_DEFAULT

def _get_empresa_pdf():
    """Obtiene datos de empresa para PDFs según el país activo."""
    pais = get_current_pais_config()
    if pais is None:
        pais = get_pais_config(PAIS_DEFAULT)
    return pais

# En cada lugar del código:
empresa = _get_empresa_pdf()

# Línea 360: empresa['empresa_nombre']
# Línea 470: empresa['empresa_nombre'].upper()
# Línea 951: empresa['empresa_direccion']
# Línea 958: f"Seguimiento con: {empresa['agente_nombre']} Tel: {empresa['agente_celular']}"
```

#### 4.6.6 Sub-Tarea D: Templates de Email (CRÍTICA — 2 archivos)

##### Archivos HTML de templates:

```html
<!-- ❌ ANTES: -->
<p>SIC Comercialización y Servicios</p>

<!-- ✅ DESPUÉS: -->
<!-- El context_processor ya pone 'empresa_nombre' en el contexto -->
<p>{{ empresa_nombre }}</p>
```

> **Nota**: Esto requiere que los emails se envíen usando `render_to_string()` con `RequestContext` o que se pase explícitamente `empresa_nombre` al contexto del template.

#### 4.6.7 Sub-Tarea E: Formato de Moneda (ALTA — 85+ ocurrencias)

Esta es la sub-tarea más grande. Hay 85+ ocurrencias de `f"${value:,.2f}"` en 15 archivos.

##### Estrategia: Función helper global

```python
# Ya definida en config/paises_config.py → formato_moneda()
# Uso en vistas:

from config.paises_config import formato_moneda

# ❌ ANTES:
f"${metricas['monto_total']:,.2f}"

# ✅ DESPUÉS (en vistas con request):
formato_moneda(metricas['monto_total'], request.pais_config)

# ✅ DESPUÉS (en código sin request, ej: admin.py):
from config.middleware_pais import get_current_pais_config
from config.paises_config import formato_moneda, get_pais_config, PAIS_DEFAULT

pais = get_current_pais_config() or get_pais_config(PAIS_DEFAULT)
formato_moneda(obj.costo_total, pais)
```

##### Archivos a modificar (ordenados por cantidad de cambios):

| # | Archivo | Ocurrencias | Prioridad |
|---|---------|-------------|-----------|
| 1 | `servicio_tecnico/views.py` | 20+ | ALTA |
| 2 | `servicio_tecnico/plotly_visualizations.py` | 11 | MEDIA (impacto visual) |
| 3 | `inventario/views.py` | 10 | ALTA |
| 4 | `servicio_tecnico/admin.py` | 8 | MEDIA |
| 5 | `servicio_tecnico/ml_advanced/recomendador_acciones.py` | 7 | BAJA |
| 6 | `servicio_tecnico/ml_advanced/optimizador_precios.py` | 5 | BAJA |
| 7 | `servicio_tecnico/utils_cotizaciones.py` | 4 | ALTA |
| 8 | `almacen/views.py` | 3 | ALTA |
| 9 | `almacen/admin.py` | 2 | MEDIA |
| 10 | `servicio_tecnico/ml_predictor.py` | 1 | BAJA |

> **Recomendación**: Hacer archivos 1, 3, 7, 8 primero (vistas que el usuario ve). Los de ML pueden esperar.

#### 4.6.8 Sub-Tarea F: Etiquetas `(MXN)` (ALTA — 5 ocurrencias)

```python
# ❌ ANTES:
help_text='Último costo de compra por unidad (MXN)'

# ✅ DESPUÉS (opción 1 — estática pero configurable):
# En config/paises_config.py agregar función:
def get_moneda_label():
    """Retorna la etiqueta de moneda para help_texts de modelos."""
    from config.middleware_pais import get_current_pais_config
    from config.paises_config import PAIS_DEFAULT, get_pais_config
    pais = get_current_pais_config() or get_pais_config(PAIS_DEFAULT)
    return pais['moneda_codigo']

# En modelos (NOTA: help_text es estático, se define al cargar Django):
# Para modelos, es aceptable dejar (MXN) porque el help_text no
# cambia dinámicamente. La moneda real se muestra en las vistas.
# Alternativa: remover la moneda del help_text.

# ✅ DESPUÉS (opción 2 — remover moneda de help_text):
help_text='Último costo de compra por unidad'
# Y mostrar la moneda en el template o en la vista.
```

> **Decisión recomendada**: Opción 2 (remover moneda de help_text). Es más simple y evita confusión.

#### 4.6.9 Sub-Tarea G: Precios de Paquetes (ALTA — `config/constants.py`)

```python
# ❌ ANTES:
PRECIOS_PAQUETES = {
    'premium': 5500.00,
    'oro': 3850.00,
    'plata': 2900.00,
}

# ✅ DESPUÉS:
# Mover precios a paises_config.py dentro de cada país
# En config/paises_config.py:
PAISES_CONFIG = {
    'mexico': {
        # ... (config existente) ...
        'precios_paquetes': {
            'premium': 5500.00,
            'oro': 3850.00,
            'plata': 2900.00,
        },
    },
    'argentina': {
        # ... (config existente) ...
        'precios_paquetes': {
            'premium': 0.00,    # Definir cuando se tengan los precios
            'oro': 0.00,
            'plata': 0.00,
        },
    },
}

# En constants.py, cambiar PRECIOS_PAQUETES por una función:
def obtener_precios_paquetes():
    """Retorna precios de paquetes del país activo."""
    from config.middleware_pais import get_current_pais_config
    from config.paises_config import get_pais_config, PAIS_DEFAULT
    pais = get_current_pais_config() or get_pais_config(PAIS_DEFAULT)
    return pais.get('precios_paquetes', {})
```

#### 4.6.10 Sub-Tarea H: Contactos RHITSO (ALTA — `config/settings.py`)

```python
# ❌ ANTES (en settings.py):
RHITSO_EMAIL_RECIPIENTS = [...]  # Contactos de México

# ✅ DESPUÉS:
# Mover a paises_config.py:
# Ya existe rhitso_habilitado y rhitso_email_recipients por país.
# Las funciones que envían emails RHITSO deben consultar pais_config:

# En servicio_tecnico/views.py o donde se envíe email:
pais = request.pais_config
if pais.get('rhitso_habilitado'):
    recipients = pais.get('rhitso_email_recipients', [])
    # enviar email...
else:
    messages.warning(request, 'RHITSO no está habilitado para este país.')
```

#### 4.6.11 Sub-Tarea I: Sucursal Satélite y Proveedores (MEDIA)

Estos valores son de lógica de negocio México-específica. No bloquean a Argentina (Argentina tendrá sus propios datos).

```python
# La lógica de sucursal 'Satelite' en views.py:6093 funciona porque
# es un filtro sobre datos de la BD. Como Argentina tiene su propia BD,
# no tendrá sucursal "Satélite" y el filtro simplemente no retornará nada.
# NO requiere cambio inmediato.

# PROVEEDORES_CHOICES en constants.py:379-395:
# Opción A: Mover a paises_config.py por país (si los proveedores difieren)
# Opción B: Dejarlo como está y que Argentina lo personalice via BD
# Recomendación: Opción B — los proveedores se pueden crear via admin.
```

#### 4.6.12 Orden de Ejecución Recomendado

| Prioridad | Sub-tarea | Archivos | Tiempo est. |
|-----------|-----------|----------|-------------|
| 1 | A: Zona horaria | 1 archivo | 30 min |
| 2 | B: URLs email | 1 archivo | 30 min |
| 3 | C: Empresa PDFs | 1 archivo | 1 hora |
| 4 | D: Templates email | 2 archivos | 30 min |
| 5 | E: Moneda (vistas principales) | 4 archivos | 2 horas |
| 6 | F: Etiquetas MXN | 2 archivos | 15 min |
| 7 | G: Precios paquetes | 2 archivos | 30 min |
| 8 | H: RHITSO | 2 archivos | 1 hora |
| 9 | E: Moneda (admin, ML) | 6 archivos | 1 hora |
| - | I: Sucursal/Proveedores | Diferido | - |

**Tiempo total estimado**: 6-7 horas (1.5-2 días con testing)

#### 4.6.13 Checklist Fase 6

- [x] Corregir zona horaria en `inventario/views.py` — Usa `get_pais_actual()` + `fecha_local_pais()`
- [x] Corregir URLs en `inventario/utils.py` — Usa `pais['url_base']` dinámico
- [ ] ~~Corregir datos de empresa en `pdf_generator.py`~~ — **DIFERIDO**: RHITSO es exclusivo de México
- [x] Corregir templates de email HTML — `imagenes_cliente.html` usa `{{ empresa_nombre }}` y `{{ pais_nombre }}`
- [ ] ~~Corregir formato moneda en vistas principales~~ — **DIFERIDO**: `$` es correcto para todos los pesos
- [x] Remover etiquetas `(MXN)` de help_texts — 3 campos en `almacen/models.py` + migración aplicada
- [ ] ~~Mover precios de paquetes a `paises_config.py`~~ — **DIFERIDO**
- [ ] ~~Configurar RHITSO condicional por país~~ — **DIFERIDO**: RHITSO solo opera en México
- [ ] ~~Corregir formato moneda en admin y ML~~ — **DIFERIDO**: `$` es correcto
- [x] Verificar que México sigue funcionando idénticamente después de cada cambio

> **Nota v3.0**: Los items marcados como "DIFERIDO" no son bugs — son optimizaciones para cuando se expanda a países con moneda diferente a pesos o se necesite RHITSO fuera de México.

---

### Fase 7: Migraciones y Datos Iniciales (Día 13)

#### 4.7.1 Objetivo

Asegurar que la BD de Argentina tiene el schema completo y los datos iniciales necesarios para operar.

#### 4.7.2 Migraciones

```bash
# Verificar estado de migraciones en TODAS las BDs
python manage.py showmigrations --database=default
python manage.py showmigrations --database=mexico
python manage.py showmigrations --database=argentina

# Si Argentina no tiene todas las migraciones:
python manage.py migrate --database=argentina

# Verificar que todas tienen el mismo estado:
python manage.py showmigrations --database=argentina | grep "\[ \]"
# No debería retornar nada (todas aplicadas)
```

#### 4.7.3 Datos Iniciales para Argentina

Argentina necesita ciertos datos base para funcionar. Crear un script de seed:

```python
# scripts/poblado/poblar_argentina.py
"""
Script para crear datos iniciales en la BD de Argentina.

EXPLICACIÓN PARA PRINCIPIANTES:
Cuando creamos una BD nueva, está vacía. Este script crea
los datos mínimos para que el sistema funcione:
- Grupos de permisos (roles)
- Sucursales
- Superusuario (si no existe)

USO:
    python manage.py shell --database=argentina
    exec(open('scripts/poblado/poblar_argentina.py').read())
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group, User

# Usar la BD de Argentina explícitamente
DB = 'argentina'

print("=== Poblando BD Argentina ===")

# 1. Crear grupos de permisos (roles)
GRUPOS = [
    'Administrador',
    'Gerente',
    'Técnico',
    'Recepcionista',
    'Almacenista',
    'Calidad',
    'Compras',
    'Ventas',
    'Consulta',
]

for nombre_grupo in GRUPOS:
    grupo, created = Group.objects.using(DB).get_or_create(name=nombre_grupo)
    status = "✅ Creado" if created else "⏩ Ya existía"
    print(f"  Grupo '{nombre_grupo}': {status}")

# 2. Crear sucursales (Argentina)
from inventario.models import Sucursal

SUCURSALES_AR = [
    {
        'nombre': 'Buenos Aires - Central',
        'direccion': '(Pendiente dirección)',
        'telefono': '(Pendiente)',
        'activa': True,
    },
]

for datos in SUCURSALES_AR:
    suc, created = Sucursal.objects.using(DB).get_or_create(
        nombre=datos['nombre'],
        defaults=datos
    )
    status = "✅ Creada" if created else "⏩ Ya existía"
    print(f"  Sucursal '{suc.nombre}': {status}")

print("")
print("=== Poblado completado ===")
print(f"  Grupos: {Group.objects.using(DB).count()}")
print(f"  Sucursales: {Sucursal.objects.using(DB).count()}")
print(f"  Usuarios: {User.objects.using(DB).count()}")
```

#### 4.7.4 Verificación Post-Migración

```bash
# Script rápido de verificación
python manage.py shell --database=argentina << 'EOF'
from django.contrib.auth.models import Group, User
from inventario.models import Sucursal, Empleado

print(f"Grupos:     {Group.objects.count()}")
print(f"Sucursales: {Sucursal.objects.count()}")
print(f"Usuarios:   {User.objects.count()}")
print(f"Empleados:  {Empleado.objects.count()}")
EOF
```

#### 4.7.5 Checklist Fase 7

- [ ] Ejecutar `migrate --database=argentina`
- [ ] Verificar que todas las migraciones están aplicadas
- [ ] Ejecutar script de datos iniciales (`poblar_argentina.py`)
- [ ] Crear superusuario en Argentina
- [ ] Verificar conteo de datos mínimos (grupos, sucursales)
- [ ] Probar login en Argentina con el superusuario

---

### Fase 8: Pruebas y Lanzamiento (Día 14-16)

#### 4.8.1 Objetivo

Realizar pruebas exhaustivas de aislamiento, funcionalidad y seguridad antes del lanzamiento en producción.

#### 4.8.2 Plan de Pruebas

##### A) Pruebas de Aislamiento de Datos

```bash
# Test: Datos creados en un país NO aparecen en otro

# 1. Crear orden en México
# Acceder a mexico.sigmasystem.work → Crear orden de servicio
# Anotar el ID de la orden (ej: #1234)

# 2. Verificar que NO aparece en Argentina
# Acceder a argentina.sigmasystem.work → Listar órdenes
# La orden #1234 NO debe aparecer

# 3. Crear orden en Argentina
# Acceder a argentina.sigmasystem.work → Crear orden
# Anotar el ID (ej: #1 — empieza desde 1 porque es BD nueva)

# 4. Verificar que NO aparece en México
# Acceder a mexico.sigmasystem.work → La orden de Argentina NO aparece
```

##### B) Pruebas de Sesión

```bash
# Test: Sesión de un país NO funciona en otro

# 1. Login en mexico.sigmasystem.work
# 2. Abrir argentina.sigmasystem.work en OTRA pestaña
# → Debe pedir login (sesión de México no es válida en Argentina)

# 3. Login en argentina.sigmasystem.work con credenciales de Argentina
# → Debe funcionar (usuario diferente en BD diferente)

# 4. Cerrar sesión en México
# → Argentina debe seguir con sesión activa (independientes)
```

##### C) Pruebas de Media (Archivos)

```bash
# Test: Archivos subidos van al directorio correcto

# 1. En México: Subir foto a una orden
# Verificar que aparece en: /mnt/django_storage/media/mexico/servicio_tecnico/imagenes/...

# 2. En Argentina: Subir foto a una orden
# Verificar que aparece en: /mnt/django_storage/media/argentina/servicio_tecnico/imagenes/...

# 3. Verificar que la URL del archivo incluye el país:
# México: /media/mexico/servicio_tecnico/imagenes/1234/foto.jpg
# Argentina: /media/argentina/servicio_tecnico/imagenes/1/foto.jpg
```

##### D) Pruebas de Moneda y Zona Horaria

```bash
# Test: Cada país muestra su moneda y hora local

# 1. México: Dashboard debe mostrar "$5,500.00 MXN" (u otro monto)
# 2. Argentina: Dashboard debe mostrar "$X ARS"
# 3. México: Fecha/hora debe corresponder a America/Mexico_City
# 4. Argentina: Fecha/hora debe corresponder a America/Argentina/Buenos_Aires
```

##### E) Pruebas de Seguridad

```bash
# Test 1: No se puede manipular el país via URL en producción
# Intentar: https://mexico.sigmasystem.work/ordenes/?pais=argentina
# → Debe ignorar el parámetro ?pais= (solo funciona en DEBUG=True)

# Test 2: No se puede acceder a datos via API directa
# Si hay algún endpoint API, verificar que respeta el país del subdominio

# Test 3: django-axes funciona por país
# Intentar 5 logins fallidos en mexico.sigmasystem.work
# → Debe bloquear en México
# → Argentina debe seguir funcionando (lockout independiente o no, según config)
```

##### F) Pruebas de Regresión (México)

```bash
# CRÍTICO: Verificar que México funciona EXACTAMENTE igual que antes

# 1. Login normal
# 2. Crear orden de servicio
# 3. Subir imágenes
# 4. Generar PDF
# 5. Dashboard con gráficas
# 6. Crear cotización
# 7. Enviar email
# 8. Admin de Django
# 9. Scorecard
# 10. Almacén
```

#### 4.8.3 Script de Pruebas Automatizadas

```python
# scripts/testing/test_multi_pais.py
"""
Script de verificación rápida del setup multi-país.
Ejecutar: python scripts/testing/test_multi_pais.py
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

def test_databases():
    """Verifica que todas las BDs están configuradas."""
    print("=== Test: Configuración de BDs ===")
    for alias in ['default', 'mexico', 'argentina']:
        assert alias in settings.DATABASES, f"❌ BD '{alias}' no configurada"
        print(f"  ✅ BD '{alias}': {settings.DATABASES[alias]['NAME']}")

def test_router():
    """Verifica que el router está registrado."""
    print("\n=== Test: Database Router ===")
    assert len(settings.DATABASE_ROUTERS) > 0, "❌ No hay routers"
    print(f"  ✅ Router: {settings.DATABASE_ROUTERS[0]}")

def test_middleware():
    """Verifica que PaisMiddleware está en la posición correcta."""
    print("\n=== Test: Middleware ===")
    mw = settings.MIDDLEWARE
    pais_idx = None
    force_idx = None
    auth_idx = None
    
    for i, m in enumerate(mw):
        if 'PaisMiddleware' in m:
            pais_idx = i
        if 'ForcePasswordChange' in m:
            force_idx = i
        if 'AuthenticationMiddleware' in m:
            auth_idx = i
    
    assert pais_idx is not None, "❌ PaisMiddleware no encontrado"
    assert auth_idx is not None, "❌ AuthenticationMiddleware no encontrado"
    assert pais_idx > auth_idx, "❌ PaisMiddleware debe ir DESPUÉS de AuthenticationMiddleware"
    
    if force_idx is not None:
        assert pais_idx < force_idx, "❌ PaisMiddleware debe ir ANTES de ForcePasswordChangeMiddleware"
        print(f"  ✅ Orden correcto: Auth({auth_idx}) → Pais({pais_idx}) → ForcePwd({force_idx})")
    else:
        print(f"  ✅ Orden correcto: Auth({auth_idx}) → Pais({pais_idx})")

def test_aislamiento():
    """Verifica aislamiento de datos entre países."""
    print("\n=== Test: Aislamiento de Datos ===")
    from inventario.models import Sucursal
    
    # Crear dato de prueba en cada BD
    test_name_mx = '__TEST_MX__'
    test_name_ar = '__TEST_AR__'
    
    try:
        Sucursal.objects.using('mexico').create(nombre=test_name_mx, direccion='test')
        Sucursal.objects.using('argentina').create(nombre=test_name_ar, direccion='test')
        
        # Verificar aislamiento
        assert Sucursal.objects.using('mexico').filter(nombre=test_name_ar).count() == 0, \
            "❌ Dato de Argentina aparece en México"
        assert Sucursal.objects.using('argentina').filter(nombre=test_name_mx).count() == 0, \
            "❌ Dato de México aparece en Argentina"
        
        print("  ✅ Datos aislados correctamente entre países")
    finally:
        # Limpiar datos de prueba
        Sucursal.objects.using('mexico').filter(nombre=test_name_mx).delete()
        Sucursal.objects.using('argentina').filter(nombre=test_name_ar).delete()

def test_paises_config():
    """Verifica la configuración de países."""
    print("\n=== Test: Configuración de Países ===")
    from config.paises_config import PAISES_CONFIG, formato_moneda, fecha_local_pais
    
    for sub, config in PAISES_CONFIG.items():
        assert 'codigo' in config, f"❌ {sub}: falta 'codigo'"
        assert 'db_alias' in config, f"❌ {sub}: falta 'db_alias'"
        assert 'timezone' in config, f"❌ {sub}: falta 'timezone'"
        assert 'moneda_codigo' in config, f"❌ {sub}: falta 'moneda_codigo'"
        assert 'empresa_nombre' in config, f"❌ {sub}: falta 'empresa_nombre'"
        assert 'url_base' in config, f"❌ {sub}: falta 'url_base'"
        
        # Test formato_moneda
        resultado = formato_moneda(1234.56, config)
        assert config['moneda_simbolo'] in resultado, f"❌ {sub}: formato_moneda no incluye símbolo"
        
        print(f"  ✅ {sub} ({config['codigo']}): {resultado}")

if __name__ == '__main__':
    print("=" * 60)
    print("PRUEBAS DE CONFIGURACIÓN MULTI-PAÍS")
    print("=" * 60)
    
    tests = [test_databases, test_router, test_middleware, test_paises_config, test_aislamiento]
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n  {e}")
            failed += 1
        except Exception as e:
            print(f"\n  ❌ Error inesperado: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTADO: {passed} pasaron, {failed} fallaron")
    print("=" * 60)
```

#### 4.8.4 Plan de Lanzamiento Producción

```
DÍA 14 (Preparación):
  ☐ Backup completo de BD producción
  ☐ Backup completo de media
  ☐ Backup de configuración Nginx
  ☐ Notificar a usuarios de México sobre ventana de mantenimiento
  ☐ Deploy del código (git pull en servidor)

DÍA 15 (Lanzamiento — Ventana de mantenimiento):
  ☐ 22:00 — Detener Gunicorn
  ☐ 22:05 — Renombrar BD (inventario_django → inventario_mexico)
  ☐ 22:10 — Crear BD Argentina + migraciones
  ☐ 22:15 — Migrar archivos de media
  ☐ 22:20 — Actualizar rutas en BD (queries SQL)
  ☐ 22:25 — Actualizar .env con nuevas variables
  ☐ 22:30 — Actualizar configuración Nginx
  ☐ 22:35 — Reload Nginx
  ☐ 22:40 — Iniciar Gunicorn
  ☐ 22:45 — Pruebas rápidas (login, crear orden, subir foto)
  ☐ 23:00 — Verificar que redirección sigmasystem.work → mexico.sigmasystem.work funciona

DÍA 16 (Verificación):
  ☐ Monitorear logs de error durante el día
  ☐ Verificar que usuarios de México reportan normalidad
  ☐ Ejecutar script de pruebas automatizadas
  ☐ Verificar DNS en múltiples ubicaciones
  ☐ Crear cuenta piloto en Argentina
```

#### 4.8.5 Checklist Fase 8

- [ ] Ejecutar script `test_multi_pais.py` en desarrollo
- [ ] Pasar todas las pruebas manuales (A-F)
- [ ] Backup completo pre-lanzamiento
- [ ] Deploy en producción durante ventana de mantenimiento
- [ ] Verificar México funciona correctamente
- [ ] Verificar Argentina funciona correctamente
- [ ] Verificar redirección del dominio raíz
- [ ] Monitorear logs por 24 horas
- [ ] Ejecutar pruebas automatizadas en producción

---

## 5. Seguridad Multi-Tenant

> **NUEVA SECCIÓN EN v2.0** — La v1.0 no tenía una sección dedicada de seguridad. En un sistema multi-tenant, una falla de seguridad puede exponer datos de un país a otro.

### 5.1 Principio de Aislamiento Total

```
REGLA DE ORO:
Un usuario de México NUNCA debe poder ver, modificar ni acceder 
a datos de Argentina, y viceversa.

Esto se logra mediante:
1. Bases de datos separadas (aislamiento físico)
2. Cookies de sesión por subdominio (aislamiento de autenticación)
3. Media files en carpetas separadas (aislamiento de archivos)
4. Thread-locals limpios en cada request (aislamiento de runtime)
```

### 5.2 Aislamiento de Sesiones

| Aspecto | Configuración | Razón |
|---------|--------------|-------|
| `SESSION_COOKIE_DOMAIN` | `None` (auto por Host) | Cada subdominio tiene su cookie |
| `SESSION_COOKIE_NAME` | `sigma_sessionid` | Evita conflictos con otros apps |
| `SESSION_COOKIE_SECURE` | `True` (en producción) | Solo HTTPS |
| `CSRF_COOKIE_SECURE` | `True` (en producción) | Solo HTTPS |

**¿Por qué NO usar `.sigmasystem.work` como dominio de cookie?**

```
# ❌ PELIGROSO:
SESSION_COOKIE_DOMAIN = '.sigmasystem.work'
# Esto haría que la cookie sea válida en TODOS los subdominios.
# Un usuario logueado en México podría acceder a Argentina.

# ✅ CORRECTO:
SESSION_COOKIE_DOMAIN = None
# Django automáticamente usa el Host del request como dominio.
# Cookie de mexico.sigmasystem.work → solo válida en mexico.sigmasystem.work
```

### 5.3 Protección CSRF

CSRF tokens son por sesión. Como las sesiones están aisladas por subdominio, los CSRF tokens también lo están automáticamente. No se necesita configuración adicional.

### 5.4 Django-Axes (Protección contra Fuerza Bruta)

```python
# Configuración actual:
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hora
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
```

**Consideración multi-tenant**: django-axes almacena los intentos de login. Por defecto usa la BD `default`. Esto significa que:

- Un lockout en México **SÍ** afecta a Argentina si el mismo username+IP intenta login
- Esto es **aceptable** como medida de seguridad: si alguien está haciendo fuerza bruta desde una IP, bloquearla globalmente es correcto

Si se necesitara aislamiento de axes por país, se podría:
```python
# Opción futura: Agregar un AxesMiddleware personalizado que
# incluya el subdominio en el lockout key
# AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address', 'hostname']]
# Pero esto requiere un custom handler de axes — NO implementar ahora
```

### 5.5 Parámetro `?pais=` — Seguridad

```python
# El parámetro ?pais= para override SOLO funciona en DEBUG=True:
if settings.DEBUG:
    pais_param = request.GET.get('pais')
    # ...

# En producción (DEBUG=False), se ignora completamente.
# Un atacante NO puede acceder a argentina poniendo ?pais=argentina
# en mexico.sigmasystem.work
```

### 5.6 Headers HTTP

Nginx pasa el header `Host` correcto a Django. Cloudflare no modifica el `Host` header. La cadena completa es:

```
Navegador → Host: mexico.sigmasystem.work
Cloudflare → Host: mexico.sigmasystem.work (sin cambio)
Nginx → proxy_set_header Host $host; → Host: mexico.sigmasystem.work
Django → request.get_host() → 'mexico.sigmasystem.work'
```

### 5.7 ALLOWED_HOSTS

```python
# En settings.py, agregar todos los subdominios:
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# En .env de producción:
ALLOWED_HOSTS=mexico.sigmasystem.work,argentina.sigmasystem.work,sigmasystem.work
# O usar wildcard:
# ALLOWED_HOSTS=.sigmasystem.work
# (el punto al inicio permite cualquier subdominio)
```

---

## 6. Consideraciones Especiales

### 6.1 Zona Horaria

| Aspecto | Antes (v1.0) | Después (v2.0) |
|---------|-------------|----------------|
| `TIME_ZONE` en settings | `America/Mexico_City` | `UTC` |
| Almacenamiento en BD | UTC (con `USE_TZ=True`) | UTC (sin cambio) |
| Conversión a local | `fecha_local()` hardcoded | `fecha_local_pais()` dinámico |
| Hora en templates | Automática por `TIME_ZONE` | Se debe usar `fecha_local_pais()` |

**Impacto del cambio a UTC**: El admin de Django mostrará fechas en UTC. Para mostrar en hora local, las vistas deben llamar a `fecha_local_pais()`. Los templates que usan el filtro `|date` de Django mostrarán UTC a menos que se active el timezone en el template:

```html
{% load tz %}
{% timezone request.pais_config.timezone %}
    {{ orden.fecha_creacion|date:"d/M/Y H:i" }}
{% endtimezone %}
```

### 6.2 Moneda y Formato Numérico

| País | Símbolo | Código | Separador Miles | Separador Decimal |
|------|---------|--------|-----------------|-------------------|
| México | $ | MXN | , (coma) | . (punto) |
| Argentina | $ | ARS | . (punto) | , (coma) |

> **Nota**: Ambos países usan `$` como símbolo. La diferencia está en el código (MXN vs ARS) y en los separadores. Para la v2.0 inicial, usamos formato estándar (`1,234.56`) para ambos. Un futuro refinamiento podría implementar `1.234,56` para Argentina.

### 6.3 Backups por País

```bash
#!/bin/bash
# scripts/backup_multi_pais.sh
# Backup independiente de cada BD

BACKUP_DIR="/var/backups/django"
DATE=$(date +%Y%m%d_%H%M)

# Backup México
pg_dump -U django_user -h localhost inventario_mexico \
    > "$BACKUP_DIR/mexico_$DATE.sql"

# Backup Argentina
pg_dump -U django_user -h localhost inventario_argentina \
    > "$BACKUP_DIR/argentina_$DATE.sql"

# Comprimir
gzip "$BACKUP_DIR/mexico_$DATE.sql"
gzip "$BACKUP_DIR/argentina_$DATE.sql"

# Limpieza: mantener últimos 30 días
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backups completados:"
ls -la "$BACKUP_DIR"/*_$DATE.sql.gz
```

### 6.4 Monitoreo

```bash
# Verificar que ambas BDs están activas
python manage.py shell -c "
from django.db import connections
for alias in ['mexico', 'argentina']:
    try:
        c = connections[alias]
        c.ensure_connection()
        print(f'{alias}: ✅ Conectado')
    except Exception as e:
        print(f'{alias}: ❌ Error: {e}')
"
```

### 6.5 Agregar un Nuevo País en el Futuro

Cuando se necesite agregar Colombia, Perú, etc.:

```
1. config/paises_config.py → Agregar bloque del nuevo país
2. config/settings.py → Agregar BD en DATABASES
3. .env → Agregar DB_NAME_CO, EMPRESA_NOMBRE_CO, etc.
4. PostgreSQL → CREATE DATABASE inventario_colombia
5. Django → python manage.py migrate --database=colombia
6. Seed → Ejecutar script de datos iniciales
7. Cloudflare → Agregar registro A para colombia.sigmasystem.work
8. Nginx → Agregar server_name colombia.sigmasystem.work
9. Media → mkdir /mnt/django_storage/media/colombia
10. Test → Ejecutar script de pruebas

Tiempo estimado: 2-3 horas (vs 12-16 días la primera vez)
```

---

## 7. Rollback Plan

### 7.1 Rollback Completo (Revertir TODO a single-tenant)

> Usar solo si hay problemas graves que no se pueden resolver.

```bash
#!/bin/bash
# scripts/rollback_multi_pais.sh
# SOLO ejecutar en caso de emergencia

echo "⚠️  ROLLBACK MULTI-PAÍS"
echo "Esto revertirá TODOS los cambios multi-tenant."
echo "¿Continuar? (escribe 'SI' para confirmar)"
read confirma
[ "$confirma" != "SI" ] && echo "Cancelado." && exit 1

# 1. Detener servicios
sudo systemctl stop gunicorn

# 2. Restaurar configuración Nginx
sudo cp /etc/nginx/sites-available/sigmasystem.bak /etc/nginx/sites-available/sigmasystem
sudo nginx -t && sudo systemctl reload nginx

# 3. Restaurar BD (renombrar de vuelta)
sudo -u postgres psql -c "ALTER DATABASE inventario_mexico RENAME TO inventario_django;"

# 4. Restaurar .env (manual — usar la versión del backup)
echo "MANUAL: Restaurar .env desde backup"

# 5. Revertir media (mover archivos de vuelta)
MEDIA="/mnt/django_storage/media"
for dir in servicio_tecnico empleados scorecard almacen; do
    if [ -d "$MEDIA/mexico/$dir" ]; then
        mv "$MEDIA/mexico/$dir" "$MEDIA/$dir"
    fi
done

# 6. Revertir rutas en BD
sudo -u postgres psql -d inventario_django << 'SQL'
UPDATE servicio_tecnico_imagenorden SET imagen = REPLACE(imagen, 'mexico/', '') WHERE imagen LIKE 'mexico/%';
UPDATE servicio_tecnico_imagenorden SET imagen_original = REPLACE(imagen_original, 'mexico/', '') WHERE imagen_original LIKE 'mexico/%';
UPDATE inventario_empleado SET foto_perfil = REPLACE(foto_perfil, 'mexico/', '') WHERE foto_perfil LIKE 'mexico/%';
UPDATE scorecard_evidenciaincidencia SET imagen = REPLACE(imagen, 'mexico/', '') WHERE imagen LIKE 'mexico/%';
UPDATE almacen_productoalmacen SET imagen = REPLACE(imagen, 'mexico/', '') WHERE imagen LIKE 'mexico/%';
UPDATE almacen_productoalmacen SET qr_code = REPLACE(qr_code, 'mexico/', '') WHERE qr_code LIKE 'mexico/%';
UPDATE almacen_diferenciaauditoria SET evidencia = REPLACE(evidencia, 'mexico/', '') WHERE evidencia LIKE 'mexico/%';
UPDATE almacen_imagenlineacotizacion SET imagen = REPLACE(imagen, 'mexico/', '') WHERE imagen LIKE 'mexico/%';
SQL

# 7. Revertir código (git)
# OPCIÓN A: Si usaste una branch
git checkout main

# OPCIÓN B: Si commitiste directo
git revert HEAD~N..HEAD  # donde N = número de commits del multi-país

# 8. Reiniciar Gunicorn
sudo systemctl start gunicorn

echo "✅ Rollback completado. Verificar manualmente."
```

### 7.2 Rollback Parcial (Solo desactivar nuevo país)

```bash
# Si solo necesitas desactivar Argentina sin revertir todo:

# 1. Remover 'argentina' de Nginx server_name
# 2. Comentar la entrada de 'argentina' en PAISES_CONFIG
# 3. Opcionalmente: remover 'argentina' de DATABASES
# 4. Reload: sudo systemctl reload nginx && sudo systemctl restart gunicorn

# Los datos de Argentina se mantienen en la BD por si se reactiva
```

---

## 8. Checklist de Lanzamiento

### 8.1 Pre-Lanzamiento

| # | Tarea | Estado |
|---|-------|--------|
| 1 | Backup completo de BD producción | ☐ |
| 2 | Backup completo de media files | ☐ |
| 3 | Backup de configuración Nginx | ☐ |
| 4 | Backup de `.env` | ☐ |
| 5 | Todas las pruebas pasan en desarrollo | ☐ |
| 6 | Script de rollback probado | ☐ |
| 7 | Ventana de mantenimiento comunicada a usuarios | ☐ |
| 8 | DNS configurado en Cloudflare | ☐ |
| 9 | Origin Certificate cubre `*.sigmasystem.work` | ☐ |

### 8.2 Lanzamiento

| # | Tarea | Tiempo est. | Estado |
|---|-------|-------------|--------|
| 1 | Detener Gunicorn | 1 min | ☐ |
| 2 | Git pull (deploy del código) | 2 min | ☐ |
| 3 | Renombrar BD `inventario_django` → `inventario_mexico` | 1 min | ☐ |
| 4 | Crear BD `inventario_argentina` | 1 min | ☐ |
| 5 | `migrate --database=argentina` | 3 min | ☐ |
| 6 | Ejecutar `migrar_media_mexico.sh` | 5-10 min | ☐ |
| 7 | Ejecutar queries SQL de rutas de media | 2 min | ☐ |
| 8 | Actualizar `.env` | 1 min | ☐ |
| 9 | Actualizar configuración Nginx | 2 min | ☐ |
| 10 | `nginx -t` + `reload` | 1 min | ☐ |
| 11 | Iniciar Gunicorn | 1 min | ☐ |
| 12 | Ejecutar `poblar_argentina.py` | 1 min | ☐ |
| 13 | Crear superusuario en Argentina | 1 min | ☐ |

**Tiempo total estimado: 20-25 minutos de downtime**

### 8.3 Post-Lanzamiento (Verificación Inmediata)

| # | Verificación | Estado |
|---|-------------|--------|
| 1 | `mexico.sigmasystem.work` carga correctamente | ☐ |
| 2 | `argentina.sigmasystem.work` carga correctamente | ☐ |
| 3 | `sigmasystem.work` redirige a México | ☐ |
| 4 | Login en México funciona | ☐ |
| 5 | Login en Argentina funciona | ☐ |
| 6 | Imágenes existentes de México cargan | ☐ |
| 7 | Subir nueva imagen en México funciona | ☐ |
| 8 | Dashboard de México muestra datos | ☐ |
| 9 | PDF se genera correctamente en México | ☐ |
| 10 | Sesión de México NO funciona en Argentina | ☐ |

### 8.4 Post-Lanzamiento (Monitoreo 48h)

| # | Verificación | Estado |
|---|-------------|--------|
| 1 | Logs de error vacíos o normales | ☐ |
| 2 | No hay quejas de usuarios de México | ☐ |
| 3 | Backups automáticos incluyen ambas BDs | ☐ |
| 4 | Espacio en disco normal | ☐ |
| 5 | Performance similar a antes (no degradación) | ☐ |
| 6 | Script `test_multi_pais.py` pasa en producción | ☐ |

---

## Apéndice: Resumen de Archivos Afectados

### Archivos Nuevos Creados (4) — ✅ Completados

| Archivo | Líneas aprox | Descripción | Commit |
|---------|-------------|-------------|--------|
| `config/paises_config.py` | ~200 | Configuración centralizada de países | `f16dbe6` |
| `config/middleware_pais.py` | ~150 | Middleware de detección de país | `f16dbe6` |
| `config/db_router.py` | ~100 | Enrutamiento de queries por país | `f16dbe6` |
| `config/context_processors.py` | ~50 | Variables de país en templates | `f16dbe6` |

### Archivos Modificados (8+)

| Archivo | Cambio | Estado |
|---------|--------|--------|
| `config/settings.py` | DATABASES, MIDDLEWARE, TEMPLATES, TIME_ZONE, DATABASE_ROUTERS, SESSION | ✅ `f16dbe6` |
| `config/storage_utils.py` | DynamicFileSystemStorage con prefijo de país | ✅ `f16dbe6` |
| `inventario/views.py` | `fecha_local()` dinámico | ✅ `88016f8` |
| `inventario/utils.py` | URLs dinámicas por país | ✅ `88016f8` |
| `servicio_tecnico/views.py` | Contexto de email con empresa_nombre/pais_nombre | ✅ `88016f8` |
| `servicio_tecnico/templates/.../imagenes_cliente.html` | Variables de empresa dinámicas | ✅ `88016f8` |
| `almacen/models.py` | Removidas etiquetas (MXN) de 3 help_texts | ✅ `88016f8` |
| `.env` | DB_NAME_AR, ALLOWED_HOSTS | ✅ `f16dbe6` |
| `servicio_tecnico/utils/pdf_generator.py` | Datos de empresa dinámicos | ⏳ Diferido (RHITSO solo México) |
| `config/constants.py` | Precios de paquetes por país | ⏳ Diferido |

### Scripts Actualizados con Soporte Multi-BD (4) — ✅ Completados

| Script | Cambio | Commit |
|--------|--------|--------|
| `scripts/setup_grupos_permisos.py` | Parámetro `db_alias`, `ContentType.objects.db_manager()` | `f16dbe6` |
| `scripts/asignar_grupos_empleados.py` | Parámetro `db_alias`, `.using(db_alias)` | `f16dbe6` |
| `scripts/manage_grupos.py` | Reescritura completa con CLI args y menú interactivo | `f16dbe6` |
| `scripts/deploy_permisos_produccion.sh` | Soporte multi-país con `--database=` | `f16dbe6` |

### Migración Generada (1) — ✅ Aplicada a ambas BDs

| Archivo | Descripción |
|---------|-------------|
| `almacen/migrations/0013_alter_compraproducto_costo_unitario_and_more.py` | Cambio de help_text en 3 campos |

### Scripts Pendientes de Crear (producción)

| Script | Descripción | Fase |
|--------|-------------|------|
| `scripts/migracion/migrar_media_mexico.sh` | Migra media a estructura multi-país | Fase 5 |
| `scripts/poblado/poblar_argentina.py` | Datos iniciales para Argentina | Fase 7 |
| `scripts/testing/test_multi_pais.py` | Pruebas automatizadas | Fase 8 |
| `scripts/backup_multi_pais.sh` | Backup independiente por país | Fase 8 |

---

**Fin del Plan v3.0**

*Documento generado el 9 de Febrero 2026*  
*Última actualización: 10 de Febrero 2026*  
*Versión 3.0: Con progreso de implementación (Fases 0, 3, 6 completadas)*
