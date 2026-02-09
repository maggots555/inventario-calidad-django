# Plan de Implementación: Sistema Multi-País con Subdominios

**Fecha de creación:** 9 de Febrero 2026  
**Versión:** 1.0  
**Estado:** Planificación  
**Tiempo estimado:** 10-14 días laborales  

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Análisis del Sistema Actual](#2-análisis-del-sistema-actual)
3. [Arquitectura Propuesta](#3-arquitectura-propuesta)
4. [Fases de Implementación](#4-fases-de-implementación)
   - [Fase 1: Cloudflare DNS + SSL](#fase-1-cloudflare-dns--ssl-día-1-2)
   - [Fase 2: PostgreSQL Multi-Base](#fase-2-postgresql-multi-base-día-3)
   - [Fase 3: Django Multi-Tenancy](#fase-3-django-multi-tenancy-día-4-7)
   - [Fase 4: Nginx Subdominios](#fase-4-nginx-subdominios-día-8)
   - [Fase 5: Media Files por País](#fase-5-media-files-por-país-día-9)
   - [Fase 6: Migraciones y Datos](#fase-6-migraciones-y-datos-día-10-11)
   - [Fase 7: Pruebas y Lanzamiento](#fase-7-pruebas-y-lanzamiento-día-12-14)
5. [Consideraciones Especiales](#5-consideraciones-especiales)
6. [Rollback Plan](#6-rollback-plan)
7. [Checklist de Lanzamiento](#7-checklist-de-lanzamiento)

---

## 1. Resumen Ejecutivo

### Objetivo
Expandir el sistema SigmaSystem para operar en múltiples países de Latinoamérica, comenzando con **Argentina** como país piloto, manteniendo **bases de datos completamente independientes** por país.

### Decisiones Clave Tomadas

| Decisión | Elección |
|----------|----------|
| Arquitectura | Multi-tenancy por subdominio con BD separadas |
| País piloto | Argentina |
| SSL | Cloudflare Full Strict con Origin Certificate |
| Dominio México | Migrar a `mexico.sigmasystem.work` (consistencia) |
| Datos | Completamente independientes por país |
| Media Files | Carpetas separadas por país |
| Costo | $0 (infraestructura existente) |

### Estructura Final de Subdominios

```
mexico.sigmasystem.work    → BD: inventario_mexico    → Media: /mnt/django_storage/media/mexico/
argentina.sigmasystem.work → BD: inventario_argentina → Media: /mnt/django_storage/media/argentina/
colombia.sigmasystem.work  → BD: inventario_colombia  → Media: /mnt/django_storage/media/colombia/  (futuro)
peru.sigmasystem.work      → BD: inventario_peru      → Media: /mnt/django_storage/media/peru/      (futuro)
```

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

### 2.6 Valores Hardcoded que Requieren Adaptación por País

| Archivo | Valor | Descripción |
|---------|-------|-------------|
| `config/settings.py` | `TIME_ZONE = 'America/Mexico_City'` | Zona horaria |
| `config/settings.py` | `LANGUAGE_CODE = 'es-mx'` | Idioma/locale |
| `config/constants.py` | `PRECIOS_PAQUETES` | Precios en MXN |
| `inventario/views.py` | `ZoneInfo('America/Mexico_City')` | Función fecha_local() |
| `.env` | Credenciales RHITSO | Contactos específicos México |

---

## 3. Arquitectura Propuesta

### 3.1 Diagrama de Flujo

```
                              ┌─────────────────┐
                              │   CLOUDFLARE    │
                              │   DNS + SSL     │
                              └────────┬────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
mexico.sigmasystem.work    argentina.sigmasystem.work    (futuros países)
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │      NGINX      │
                              │  (Port 80/443)  │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │    GUNICORN     │
                              │  (5 workers)    │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │     DJANGO      │
                              │  Middleware de  │
                              │     País        │
                              └────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ inventario_     │    │ inventario_     │    │ inventario_     │
    │ mexico          │    │ argentina       │    │ (futuro)        │
    │ (PostgreSQL)    │    │ (PostgreSQL)    │    │                 │
    └─────────────────┘    └─────────────────┘    └─────────────────┘
              │                        │                        │
              ▼                        ▼                        ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ /media/mexico/  │    │ /media/argentina│    │ /media/(país)/  │
    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 3.2 Estrategia de Multi-Tenancy

**Enfoque elegido:** Database-per-Tenant con Middleware de detección por subdominio

1. **Middleware detecta país** del subdominio (ej: `argentina.sigmasystem.work` → `AR`)
2. **Database Router** dirige queries a la BD correcta
3. **Storage modificado** agrega prefijo de país a rutas de archivos
4. **Thread-local storage** mantiene contexto del país durante el request

### 3.3 Nuevos Archivos a Crear

```
config/
├── middleware_pais.py     # Middleware de detección de país
├── db_router.py           # Router de base de datos por país
└── paises_config.py       # Configuración por país (timezone, moneda, etc.)
```

---

## 4. Fases de Implementación

---

### Fase 1: Cloudflare DNS + SSL (Día 1-2)

**Objetivo:** Configurar subdominios con SSL Full Strict

#### 1.1 Crear Registros DNS en Cloudflare

Acceder al dashboard de Cloudflare → sigmasystem.work → DNS

| Tipo | Nombre | Contenido | Proxy | TTL |
|------|--------|-----------|-------|-----|
| A | mexico | 187.188.9.208 | Proxied (naranja) | Auto |
| A | argentina | 187.188.9.208 | Proxied (naranja) | Auto |

#### 1.2 Generar Origin Certificate

**Cloudflare Dashboard → SSL/TLS → Origin Server → Create Certificate**

```
Certificate type: RSA (2048)
Hostnames: 
  - *.sigmasystem.work
  - sigmasystem.work
Validity: 15 years (máximo)
```

**Guardar archivos generados:**
- Certificado (PEM) → `/etc/ssl/cloudflare/sigmasystem.work.pem`
- Clave privada → `/etc/ssl/cloudflare/sigmasystem.work.key`

#### 1.3 Instalar Certificado en Servidor

```bash
# Crear directorio para certificados
sudo mkdir -p /etc/ssl/cloudflare

# Copiar certificados (desde el contenido copiado de Cloudflare)
sudo nano /etc/ssl/cloudflare/sigmasystem.work.pem
# Pegar contenido del certificado

sudo nano /etc/ssl/cloudflare/sigmasystem.work.key
# Pegar contenido de la clave privada

# Establecer permisos seguros
sudo chmod 600 /etc/ssl/cloudflare/sigmasystem.work.key
sudo chmod 644 /etc/ssl/cloudflare/sigmasystem.work.pem
sudo chown root:root /etc/ssl/cloudflare/*
```

#### 1.4 Configurar SSL Mode en Cloudflare

**SSL/TLS → Overview → Encryption Mode: Full (strict)**

#### 1.5 Verificación

```bash
# Probar resolución DNS (después de propagación ~5 min)
dig mexico.sigmasystem.work +short
dig argentina.sigmasystem.work +short

# Ambos deben mostrar: 187.188.9.208
```

#### Criterios de Éxito Fase 1
- [ ] Registros DNS creados y propagados
- [ ] Origin Certificate generado y guardado
- [ ] SSL Mode configurado como Full (strict)
- [ ] `dig` resuelve ambos subdominios al IP correcto

---

### Fase 2: PostgreSQL Multi-Base (Día 3)

**Objetivo:** Crear bases de datos separadas para cada país

#### 2.1 Crear Base de Datos para Argentina

```bash
# Conectar a PostgreSQL como superusuario
sudo -u postgres psql

# En el prompt de PostgreSQL:
```

```sql
-- Crear base de datos para Argentina
CREATE DATABASE inventario_argentina
    WITH ENCODING 'UTF8'
    LC_COLLATE = 'es_AR.UTF-8'
    LC_CTYPE = 'es_AR.UTF-8'
    TEMPLATE template0;

-- Crear usuario específico para Argentina (opcional, puede usar el mismo)
CREATE USER inventario_ar WITH PASSWORD 'password_seguro_argentina';

-- Otorgar permisos
GRANT ALL PRIVILEGES ON DATABASE inventario_argentina TO django_user;
GRANT ALL PRIVILEGES ON DATABASE inventario_argentina TO inventario_ar;

-- Verificar bases de datos
\l

-- Salir
\q
```

#### 2.2 Renombrar Base de Datos México (Opcional pero Recomendado)

Para consistencia de nomenclatura:

```sql
-- Opción 1: Renombrar (requiere desconectar usuarios)
-- PRECAUCIÓN: Detener Gunicorn antes de ejecutar

-- Terminar conexiones activas
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'inventario_django';

-- Renombrar
ALTER DATABASE inventario_django RENAME TO inventario_mexico;

-- Actualizar .env después
```

**O mantener el nombre actual** y solo usar alias en Django settings.

#### 2.3 Verificar Locales del Sistema

```bash
# Verificar locales instalados
locale -a | grep es

# Si falta es_AR.UTF-8:
sudo locale-gen es_AR.UTF-8
sudo update-locale
```

#### 2.4 Actualizar requirements.txt

Verificar que `psycopg2-binary` esté instalado:

```bash
cd /var/www/inventario-django/inventario-calidad-django
source ../venv/bin/activate
pip show psycopg2-binary

# Si no está instalado:
pip install psycopg2-binary>=2.9.0
pip freeze | grep psycopg > requirements_updated.txt
```

#### Criterios de Éxito Fase 2
- [ ] Base de datos `inventario_argentina` creada
- [ ] Usuario con permisos correctos
- [ ] Locale es_AR.UTF-8 disponible
- [ ] psycopg2-binary instalado

---

### Fase 3: Django Multi-Tenancy (Día 4-7)

**Objetivo:** Implementar middleware, router y configuración por país

#### 3.1 Crear Archivo de Configuración por País

**Archivo:** `config/paises_config.py`

```python
"""
Configuración específica por país para el sistema multi-tenant.

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene toda la información específica de cada país:
- Zona horaria
- Idioma
- Moneda y formato de precios
- Alias de base de datos
- Subdominios permitidos
"""

PAISES = {
    'MX': {
        'codigo': 'MX',
        'nombre': 'México',
        'subdominio': 'mexico',
        'db_alias': 'mexico',  # Alias en DATABASES
        'timezone': 'America/Mexico_City',
        'language_code': 'es-mx',
        'moneda': 'MXN',
        'simbolo_moneda': '$',
        'formato_fecha': '%d/%m/%Y',
        'precios_paquetes': {
            'premium': 5500.00,
            'oro': 3850.00,
            'plata': 2900.00,
            'ninguno': 0.00,
        },
    },
    'AR': {
        'codigo': 'AR',
        'nombre': 'Argentina',
        'subdominio': 'argentina',
        'db_alias': 'argentina',
        'timezone': 'America/Argentina/Buenos_Aires',
        'language_code': 'es-ar',
        'moneda': 'ARS',
        'simbolo_moneda': '$',
        'formato_fecha': '%d/%m/%Y',
        'precios_paquetes': {
            'premium': 0.00,  # Definir precios para Argentina
            'oro': 0.00,
            'plata': 0.00,
            'ninguno': 0.00,
        },
    },
    # Agregar más países aquí cuando sea necesario
    # 'CO': { ... },  # Colombia
    # 'PE': { ... },  # Perú
}

# Mapeo de subdominio a código de país
SUBDOMINIO_A_PAIS = {
    config['subdominio']: codigo 
    for codigo, config in PAISES.items()
}

# País por defecto cuando no se detecta subdominio válido
PAIS_DEFAULT = 'MX'

def get_pais_config(codigo_pais):
    """
    Obtiene la configuración completa de un país.
    
    Args:
        codigo_pais: Código ISO del país (MX, AR, CO, PE)
        
    Returns:
        dict: Configuración del país o la de México si no existe
    """
    return PAISES.get(codigo_pais, PAISES[PAIS_DEFAULT])

def get_pais_por_subdominio(subdominio):
    """
    Obtiene el código de país basado en el subdominio.
    
    Args:
        subdominio: Subdominio extraído del host (ej: 'argentina')
        
    Returns:
        str: Código de país (ej: 'AR') o PAIS_DEFAULT
    """
    return SUBDOMINIO_A_PAIS.get(subdominio, PAIS_DEFAULT)
```

#### 3.2 Crear Middleware de Detección de País

**Archivo:** `config/middleware_pais.py`

```python
"""
Middleware para detección automática de país por subdominio.

EXPLICACIÓN PARA PRINCIPIANTES:
Este middleware se ejecuta en CADA request y hace lo siguiente:
1. Extrae el subdominio de la URL (ej: 'argentina' de 'argentina.sigmasystem.work')
2. Busca el país correspondiente en la configuración
3. Guarda el país en el request Y en thread-local para que otros componentes lo usen
4. El Database Router usa esta información para elegir la BD correcta
"""

import threading
from django.utils import timezone
from zoneinfo import ZoneInfo
from .paises_config import get_pais_por_subdominio, get_pais_config, PAIS_DEFAULT

# Thread-local storage para mantener el país durante todo el request
_thread_locals = threading.local()


def get_current_pais():
    """
    Obtiene el código de país del request actual.
    
    Usado por:
    - Database Router (db_router.py)
    - Storage dinámico (storage_utils.py)
    - Cualquier código que necesite saber el país actual
    
    Returns:
        str: Código de país (MX, AR, etc.) o PAIS_DEFAULT
    """
    return getattr(_thread_locals, 'pais_codigo', PAIS_DEFAULT)


def get_current_db_alias():
    """
    Obtiene el alias de base de datos para el país actual.
    
    Returns:
        str: Alias de BD ('mexico', 'argentina', etc.) o 'default'
    """
    return getattr(_thread_locals, 'db_alias', 'default')


def get_current_pais_config():
    """
    Obtiene la configuración completa del país actual.
    
    Returns:
        dict: Configuración del país
    """
    codigo = get_current_pais()
    return get_pais_config(codigo)


class PaisMiddleware:
    """
    Middleware que detecta el país basándose en el subdominio.
    
    Ejemplo:
        Request a 'argentina.sigmasystem.work' → request.pais = 'AR'
        Request a 'mexico.sigmasystem.work' → request.pais = 'MX'
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Extraer subdominio del host
        host = request.get_host().split(':')[0]  # Remover puerto si existe
        
        # Parsear subdominio (primera parte antes del dominio principal)
        # Ejemplos:
        #   'argentina.sigmasystem.work' → 'argentina'
        #   'mexico.sigmasystem.work' → 'mexico'
        #   'sigmasystem.work' → '' (dominio raíz)
        #   'localhost' → 'localhost'
        
        parts = host.split('.')
        
        if len(parts) >= 3 and 'sigmasystem' in host:
            # Es un subdominio de sigmasystem.work
            subdominio = parts[0]
        elif host in ('localhost', '127.0.0.1'):
            # Desarrollo local - usar país por defecto
            subdominio = 'mexico'
        else:
            # Dominio raíz o IP directa - país por defecto
            subdominio = 'mexico'
        
        # Obtener código de país
        pais_codigo = get_pais_por_subdominio(subdominio)
        pais_config = get_pais_config(pais_codigo)
        
        # Guardar en thread-local (para Database Router y Storage)
        _thread_locals.pais_codigo = pais_codigo
        _thread_locals.db_alias = pais_config['db_alias']
        _thread_locals.pais_config = pais_config
        
        # Guardar en request (para vistas y templates)
        request.pais_codigo = pais_codigo
        request.pais_config = pais_config
        request.db_alias = pais_config['db_alias']
        
        # Activar timezone del país
        try:
            tz = ZoneInfo(pais_config['timezone'])
            timezone.activate(tz)
        except Exception:
            pass  # Usar timezone por defecto si falla
        
        # Continuar con el request
        response = self.get_response(request)
        
        # Limpiar después del request
        timezone.deactivate()
        
        return response
```

#### 3.3 Crear Database Router

**Archivo:** `config/db_router.py`

```python
"""
Database Router para multi-tenancy por país.

EXPLICACIÓN PARA PRINCIPIANTES:
Django puede usar múltiples bases de datos. Este router decide
a cuál base de datos enviar cada consulta (SELECT, INSERT, UPDATE, DELETE).

El router usa el país detectado por el middleware para elegir la BD correcta:
- Request de argentina.sigmasystem.work → BD 'argentina'
- Request de mexico.sigmasystem.work → BD 'mexico'
"""

from .middleware_pais import get_current_db_alias


class PaisRouter:
    """
    Router que dirige todas las operaciones de BD al alias del país actual.
    
    Métodos requeridos por Django:
    - db_for_read: ¿De cuál BD leer?
    - db_for_write: ¿En cuál BD escribir?
    - allow_relation: ¿Permitir relaciones entre objetos?
    - allow_migrate: ¿Permitir migraciones en esta BD?
    """
    
    def db_for_read(self, model, **hints):
        """
        Retorna el alias de BD para operaciones de lectura (SELECT).
        """
        return get_current_db_alias()
    
    def db_for_write(self, model, **hints):
        """
        Retorna el alias de BD para operaciones de escritura (INSERT, UPDATE, DELETE).
        """
        return get_current_db_alias()
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Determina si se permite una relación entre dos objetos.
        
        Solo permitimos relaciones si ambos objetos están en la misma BD.
        Esto previene referencias cruzadas entre países.
        """
        # Obtener la BD de cada objeto
        db1 = getattr(obj1._state, 'db', None)
        db2 = getattr(obj2._state, 'db', None)
        
        if db1 and db2:
            return db1 == db2  # Solo permitir si están en la misma BD
        
        return True  # Si no hay BD asignada, permitir (Django lo manejará)
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Determina si se permite ejecutar migraciones en esta BD.
        
        Permitimos migraciones en todas las BD para que todas tengan
        la misma estructura de tablas.
        """
        return True
```

#### 3.4 Crear Context Processor para País

**Archivo:** `config/context_processors.py`

```python
"""
Context processors para hacer disponible la información del país en todos los templates.

EXPLICACIÓN PARA PRINCIPIANTES:
Un context processor es una función que agrega variables al contexto de TODOS
los templates. Esto permite usar {{ pais_nombre }} en cualquier template sin
tener que pasarlo explícitamente desde cada vista.
"""

from .paises_config import PAIS_DEFAULT, get_pais_config


def pais_context(request):
    """
    Agrega información del país actual al contexto de templates.
    
    Variables disponibles en templates:
    - {{ pais_codigo }}: 'MX', 'AR', etc.
    - {{ pais_nombre }}: 'México', 'Argentina', etc.
    - {{ pais_moneda }}: 'MXN', 'ARS', etc.
    - {{ pais_simbolo_moneda }}: '$'
    - {{ pais_config }}: Diccionario completo de configuración
    """
    pais_codigo = getattr(request, 'pais_codigo', PAIS_DEFAULT)
    pais_config = getattr(request, 'pais_config', get_pais_config(PAIS_DEFAULT))
    
    return {
        'pais_codigo': pais_codigo,
        'pais_nombre': pais_config.get('nombre', 'México'),
        'pais_moneda': pais_config.get('moneda', 'MXN'),
        'pais_simbolo_moneda': pais_config.get('simbolo_moneda', '$'),
        'pais_config': pais_config,
    }
```

#### 3.5 Modificaciones a settings.py

Agregar las siguientes secciones al archivo `config/settings.py`:

```python
# ============================================================================
# CONFIGURACIÓN MULTI-PAÍS (MULTI-TENANCY)
# ============================================================================

# Configuración de bases de datos por país
DATABASES = {
    'default': {
        # Default apunta a México (para compatibilidad y comandos de consola)
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='inventario_mexico'),
        'USER': config('DB_USER', default='django_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {'connect_timeout': 10},
    },
    'mexico': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME_MX', default='inventario_mexico'),
        'USER': config('DB_USER', default='django_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {'connect_timeout': 10},
    },
    'argentina': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME_AR', default='inventario_argentina'),
        'USER': config('DB_USER_AR', default='django_user'),
        'PASSWORD': config('DB_PASSWORD_AR', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {'connect_timeout': 10},
    },
}

# Router de base de datos
DATABASE_ROUTERS = ['config.db_router.PaisRouter']
```

**Agregar en MIDDLEWARE** (después de AxesMiddleware):
```python
'config.middleware_pais.PaisMiddleware',  # Detección de país por subdominio
```

**Agregar en TEMPLATES → OPTIONS → context_processors:**
```python
'config.context_processors.pais_context',  # Variables de país en templates
```

#### 3.6 Actualizar .env

Agregar nuevas variables al archivo `.env`:

```bash
# ============================================================================
# CONFIGURACIÓN MULTI-PAÍS
# ============================================================================

# Base de datos México (mantener nombre actual o renombrar)
DB_NAME_MX=inventario_django

# Base de datos Argentina
DB_NAME_AR=inventario_argentina
DB_USER_AR=django_user
DB_PASSWORD_AR=sicmexico2025%i

# Actualizar ALLOWED_HOSTS para incluir subdominios
ALLOWED_HOSTS=192.168.100.22,100.122.249.38,localhost,127.0.0.1,sicubuserver,sicubuserver.tailaa561.ts.net,sigmasystem.work,mexico.sigmasystem.work,argentina.sigmasystem.work

# Actualizar CSRF_TRUSTED_ORIGINS
CSRF_TRUSTED_ORIGINS=https://192.168.100.22,https://100.122.249.38,http://192.168.100.22,http://100.122.249.38,https://localhost,http://localhost,http://127.0.0.1,http://sicubuserver,https://sicubuserver.tailaa561.ts.net,http://sigmasystem.work,https://sigmasystem.work,https://mexico.sigmasystem.work,https://argentina.sigmasystem.work
```

#### Criterios de Éxito Fase 3
- [ ] `paises_config.py` creado con MX y AR
- [ ] `middleware_pais.py` detecta país por subdominio
- [ ] `db_router.py` dirige queries a BD correcta
- [ ] `context_processors.py` expone variables en templates
- [ ] `settings.py` actualizado con DATABASES multi-país
- [ ] `.env` actualizado con nuevas variables
- [ ] Servidor arranca sin errores

---

### Fase 4: Nginx Subdominios (Día 8)

**Objetivo:** Configurar Nginx para manejar múltiples subdominios con SSL

#### 4.1 Crear Nueva Configuración Nginx

**Archivo:** `/etc/nginx/sites-available/sigmasystem-multipais`

```nginx
# ============================================================================
# CONFIGURACIÓN NGINX MULTI-PAÍS - SigmaSystem
# ============================================================================
# Maneja subdominios: mexico.sigmasystem.work, argentina.sigmasystem.work
# SSL: Cloudflare Origin Certificate (Full Strict)

# Upstream de Gunicorn
upstream gunicorn_app {
    server unix:/run/gunicorn.sock fail_timeout=0;
}

# ============================================================================
# SERVIDOR HTTPS PRINCIPAL (Subdominios)
# ============================================================================
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name mexico.sigmasystem.work argentina.sigmasystem.work;
    
    # Certificado Cloudflare Origin (wildcard)
    ssl_certificate /etc/ssl/cloudflare/sigmasystem.work.pem;
    ssl_certificate_key /etc/ssl/cloudflare/sigmasystem.work.key;
    
    # Configuración SSL moderna
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Tamaño máximo de archivos (200MB)
    client_max_body_size 200M;
    
    # Logs
    access_log /var/log/nginx/sigmasystem-access.log;
    error_log /var/log/nginx/sigmasystem-error.log;
    
    # Archivos estáticos
    location /static/ {
        alias /var/www/inventario-django/inventario-calidad-django/staticfiles/;
        expires 1h;
        add_header Cache-Control "public, must-revalidate";
    }
    
    # Media para México
    location ~ ^/media/mexico/(.*)$ {
        alias /mnt/django_storage/media/mexico/$1;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Media para Argentina
    location ~ ^/media/argentina/(.*)$ {
        alias /mnt/django_storage/media/argentina/$1;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Fallback para media legacy
    location /media/ {
        root /mnt/django_storage;
        try_files $uri @old_media;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    location @old_media {
        root /var/www/inventario-django/inventario-calidad-django;
        try_files $uri =404;
    }
    
    # Proxy a Gunicorn
    location / {
        proxy_pass http://gunicorn_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Headers de seguridad
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        
        # Timeouts
        proxy_connect_timeout 120s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        client_body_timeout 300s;
        
        proxy_request_buffering on;
        proxy_buffering on;
        client_body_buffer_size 1m;
    }
}

# Redirección HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name mexico.sigmasystem.work argentina.sigmasystem.work;
    return 301 https://$host$request_uri;
}

# Redirección dominio raíz → México
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name sigmasystem.work www.sigmasystem.work;
    
    ssl_certificate /etc/ssl/cloudflare/sigmasystem.work.pem;
    ssl_certificate_key /etc/ssl/cloudflare/sigmasystem.work.key;
    
    return 301 https://mexico.sigmasystem.work$request_uri;
}

server {
    listen 80;
    listen [::]:80;
    server_name sigmasystem.work www.sigmasystem.work;
    return 301 https://mexico.sigmasystem.work$request_uri;
}
```

#### 4.2 Activar Nueva Configuración

```bash
# Respaldar configuración actual
sudo cp /etc/nginx/sites-enabled/inventario-django \
    /etc/nginx/sites-available/inventario-django.backup.$(date +%Y%m%d)

# Crear enlace simbólico
sudo ln -sf /etc/nginx/sites-available/sigmasystem-multipais \
    /etc/nginx/sites-enabled/sigmasystem-multipais

# Probar configuración
sudo nginx -t

# Recargar Nginx
sudo systemctl reload nginx
```

#### Criterios de Éxito Fase 4
- [ ] Configuración Nginx creada y probada
- [ ] Certificados SSL instalados
- [ ] Redirección HTTP → HTTPS funciona
- [ ] Redirección dominio raíz → mexico funciona
- [ ] Nginx recargado sin errores

---

### Fase 5: Media Files por País (Día 9)

**Objetivo:** Modificar el storage para separar archivos por país

#### 5.1 Modificar storage_utils.py

Agregar función para obtener país y modificar `DynamicFileSystemStorage`:

```python
def get_current_pais_codigo():
    """Obtiene el código de país del request actual."""
    try:
        from config.middleware_pais import get_current_pais_config
        config = get_current_pais_config()
        return config.get('subdominio', 'mexico')
    except Exception:
        return 'mexico'


class DynamicFileSystemStorage(FileSystemStorage):
    """Storage con soporte para disco alterno Y separación por país."""
    
    def __init__(self, **kwargs):
        active_path = get_active_storage_path()
        
        # Agregar subcarpeta de país
        pais = get_current_pais_codigo()
        country_path = active_path / pais
        country_path.mkdir(parents=True, exist_ok=True)
        
        kwargs['location'] = country_path
        super().__init__(**kwargs)
    
    def _save(self, name, content):
        active_path = get_active_storage_path()
        pais = get_current_pais_codigo()
        country_path = active_path / pais
        country_path.mkdir(parents=True, exist_ok=True)
        
        if Path(self.location) != country_path:
            self.location = country_path
        
        return super()._save(name, content)
```

#### 5.2 Crear Estructura de Carpetas

```bash
# Crear carpetas para cada país
sudo mkdir -p /mnt/django_storage/media/mexico
sudo mkdir -p /mnt/django_storage/media/argentina

# Establecer permisos
sudo chown -R sicsystem:www-data /mnt/django_storage/media/mexico
sudo chown -R sicsystem:www-data /mnt/django_storage/media/argentina
sudo chmod -R 775 /mnt/django_storage/media/mexico
sudo chmod -R 775 /mnt/django_storage/media/argentina
```

#### 5.3 Migrar Archivos Existentes de México

```bash
# PRECAUCIÓN: Hacer con servidor detenido
sudo systemctl stop gunicorn

cd /mnt/django_storage/media
sudo mv servicio_tecnico mexico/
sudo mv almacen mexico/
sudo mv empleados mexico/
sudo mv scorecard mexico/
sudo mv temp mexico/

sudo systemctl start gunicorn
```

#### Criterios de Éxito Fase 5
- [ ] Carpetas de país creadas con permisos correctos
- [ ] Archivos existentes migrados a `/mexico/`
- [ ] Storage modificado para incluir país
- [ ] Nuevas subidas van a la carpeta correcta

---

### Fase 6: Migraciones y Datos (Día 10-11)

**Objetivo:** Aplicar migraciones a la nueva base de datos y crear datos iniciales

#### 6.1 Aplicar Migraciones a Argentina

```bash
cd /var/www/inventario-django/inventario-calidad-django
source ../venv/bin/activate

# Verificar migraciones pendientes
python manage.py showmigrations --database=argentina

# Aplicar todas las migraciones
python manage.py migrate --database=argentina

# Verificar tablas creadas
python manage.py dbshell --database=argentina
# \dt
# \q
```

#### 6.2 Crear Superusuario para Argentina

```bash
python manage.py createsuperuser --database=argentina
```

#### 6.3 Verificar Conexiones

```python
# En Django shell:
python manage.py shell

from django.db import connections

# México
with connections['mexico'].cursor() as cursor:
    cursor.execute("SELECT current_database()")
    print(f"México: {cursor.fetchone()[0]}")

# Argentina
with connections['argentina'].cursor() as cursor:
    cursor.execute("SELECT current_database()")
    print(f"Argentina: {cursor.fetchone()[0]}")
```

#### Criterios de Éxito Fase 6
- [ ] Migraciones aplicadas en `inventario_argentina`
- [ ] Superusuario creado para Argentina
- [ ] Conexiones verificadas desde Django shell

---

### Fase 7: Pruebas y Lanzamiento (Día 12-14)

**Objetivo:** Validar funcionamiento completo y lanzar

#### 7.1 Pruebas Funcionales

| Prueba | México | Argentina |
|--------|--------|-----------|
| Login/logout funciona | [ ] | [ ] |
| Dashboard carga correctamente | [ ] | [ ] |
| Crear nueva orden de servicio | [ ] | [ ] |
| Subir imágenes (verificar ruta) | [ ] | [ ] |
| Cotizaciones funcionan | [ ] | [ ] |
| Scorecard (crear incidencia) | [ ] | [ ] |
| Almacén (crear producto) | [ ] | [ ] |
| Emails se envían | [ ] | [ ] |
| PDFs se generan | [ ] | [ ] |
| Reportes Excel funcionan | [ ] | [ ] |

#### 7.2 Pruebas de Aislamiento

- [ ] Orden creada en México NO aparece en Argentina
- [ ] Orden creada en Argentina NO aparece en México
- [ ] Imagen subida en Argentina se guarda en `/media/argentina/`
- [ ] Usuario de México no puede acceder a Argentina

#### 7.3 Monitoreo

```bash
# Logs en tiempo real
sudo tail -f /var/log/nginx/sigmasystem-error.log
sudo journalctl -u gunicorn -f
tail -f logs/django_errors.log
```

#### Criterios de Éxito Fase 7
- [ ] Todas las pruebas funcionales pasadas
- [ ] Aislamiento de datos verificado
- [ ] Usuarios notificados del cambio
- [ ] Sistema en producción

---

## 5. Consideraciones Especiales

### 5.1 Zona Horaria

| País | Timezone | UTC |
|------|----------|-----|
| México | America/Mexico_City | UTC-6 |
| Argentina | America/Argentina/Buenos_Aires | UTC-3 |

El middleware activa la zona horaria correcta para cada request automáticamente.

### 5.2 Moneda y Precios

Los precios de paquetes están en `paises_config.py` por país.

**PENDIENTE:** Definir precios para Argentina en ARS antes del lanzamiento.

### 5.3 Contactos RHITSO

Los contactos de RHITSO en `.env` son específicos de México. Para Argentina:
1. Agregar variables con prefijo `AR_` (ej: `AR_RHITSO_CONTACTO_1_EMAIL`)
2. Modificar código para leer según país activo

### 5.4 Backups

```bash
# Backup México
pg_dump -U django_user inventario_mexico > backup_mexico_$(date +%Y%m%d).sql

# Backup Argentina  
pg_dump -U django_user inventario_argentina > backup_argentina_$(date +%Y%m%d).sql
```

### 5.5 Usuarios y Autenticación

Los usuarios son **completamente separados** por país. Cada país tiene su propia tabla `auth_user`.

---

## 6. Rollback Plan

### 6.1 Rollback de Nginx

```bash
sudo rm /etc/nginx/sites-enabled/sigmasystem-multipais
sudo ln -sf /etc/nginx/sites-available/inventario-django.backup.YYYYMMDD \
    /etc/nginx/sites-enabled/inventario-django
sudo nginx -t && sudo systemctl reload nginx
```

### 6.2 Rollback de Django

```bash
cd /var/www/inventario-django/inventario-calidad-django
git checkout config/settings.py
cp .env.backup.YYYYMMDD .env
sudo systemctl restart gunicorn
```

### 6.3 Rollback de Media Files

```bash
cd /mnt/django_storage/media
sudo mv mexico/* ./
sudo rmdir mexico argentina
```

---

## 7. Checklist de Lanzamiento

### Pre-Lanzamiento
- [ ] Backup completo de base de datos México
- [ ] Backup de archivos de configuración
- [ ] DNS propagado (verificar con `dig`)
- [ ] Certificado SSL instalado
- [ ] Base de datos Argentina creada y migrada
- [ ] Carpetas de media creadas con permisos
- [ ] Pruebas funcionales completadas

### Día del Lanzamiento
- [ ] Verificar que México sigue funcionando
- [ ] Activar configuración Nginx multi-país
- [ ] Verificar https://mexico.sigmasystem.work
- [ ] Verificar https://argentina.sigmasystem.work
- [ ] Crear primera orden de prueba en Argentina
- [ ] Notificar a usuarios

### Post-Lanzamiento
- [ ] Monitorear logs por 24 horas
- [ ] Verificar backups incluyen nueva BD
- [ ] Documentar lecciones aprendidas

---

## Historial de Cambios

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-02-09 | 1.0 | Creación inicial del documento |

---

## Archivos de Referencia

### Nuevos archivos a crear (6)
- `config/paises_config.py` - Configuración por país
- `config/middleware_pais.py` - Middleware de detección
- `config/db_router.py` - Router de base de datos
- `config/context_processors.py` - Variables para templates
- `/etc/nginx/sites-available/sigmasystem-multipais` - Config Nginx
- `/etc/ssl/cloudflare/sigmasystem.work.pem` y `.key` - Certificados

### Archivos a modificar (3)
- `config/settings.py` - DATABASES, MIDDLEWARE, TEMPLATES
- `config/storage_utils.py` - Agregar prefijo de país
- `.env` - Nuevas variables de BD y hosts
