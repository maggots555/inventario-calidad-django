# Implementación de Celery + Redis

> **Fecha**: 20 de febrero de 2026  
> **Commits**: `8a491c5` y `64a1811`  
> **Aplicación**: `servicio_tecnico`

---

## Descripción General

Se integró **Celery** como sistema de tareas en segundo plano y **Redis** como broker de mensajes y cache de Django. Esto permite que operaciones pesadas (envío de correos con PDFs e imágenes) se ejecuten sin bloquear al usuario.

### Antes
El usuario hacía clic en "Enviar correo" → el servidor procesaba todo (generar PDF, comprimir imágenes, enviar email) → el usuario esperaba 10-30 segundos viendo la pantalla cargando.

### Después
El usuario hace clic en "Enviar correo" → el servidor responde de inmediato "Enviando en segundo plano..." → Celery procesa todo en paralelo sin que el usuario espere.

---

## Arquitectura

```
Usuario → Nginx → Gunicorn (Django) ─→ Redis (BD 0: cola de tareas)  → Celery Worker (4 procesos)
                                     ─→ Redis (BD 1: resultados)    ← Resultados de tareas
                                     ─→ Redis (BD 2: cache)         ← Dashboards cacheados
```

### Separación de Redis por base de datos

| BD Redis | Uso | Descripción |
|----------|-----|-------------|
| `/0` | Broker Celery | Cola de mensajes (tareas pendientes) |
| `/1` | Result Backend | Resultados de tareas ejecutadas |
| `/2` | Cache Django | Dashboards Plotly, estadísticas, listas |

---

## Componentes Implementados

### 1. Celery App (`config/celery.py`)
- Configuración central de Celery
- Auto-descubrimiento de tareas en todas las apps
- Tarea `debug_task` para verificación

### 2. Inicialización (`config/__init__.py`)
- Importa la app de Celery al arrancar Django
- Garantiza que `@shared_task` funcione en todas las apps

### 3. Settings (`config/settings.py`)
- Variables de conexión a Redis (broker + result backend)
- Serialización JSON para seguridad
- Timeouts: 5 min soft, 10 min hard
- Máximo 3 reintentos automáticos por tarea
- Resultados expiran tras 24 horas
- Cache Redis con prefijo `sigma` y TTLs configurables

### 4. Tareas (`servicio_tecnico/tasks.py`)
Tres tareas en segundo plano:

| Tarea | Función | Qué hace |
|-------|---------|----------|
| `enviar_correo_rhitso_task` | Correo RHITSO | Genera PDF, comprime imágenes de ingreso, envía correo al laboratorio |
| `enviar_diagnostico_cliente_task` | Diagnóstico | Genera PDF diagnóstico, comprime imágenes, crea cotización/piezas, envía al cliente |
| `enviar_imagenes_cliente_task` | Imágenes | Comprime y envía imágenes de ingreso al cliente |

**Características comunes**:
- Máximo 3 reintentos automáticos (con 60s entre cada uno)
- Solo reciben tipos simples (int, str, list) — nunca objetos Django
- Registran historial de la orden al completarse
- Limpieza de archivos temporales al finalizar
- Logging detallado en cada paso

### 5. Cache para Dashboards
- `@cache_page_dashboard` aplicado a 4 vistas pesadas de analytics
- TTLs configurables: dashboards (10 min), listas (5 min), ML (30 min)
- Fallback automático si Redis cae (`IGNORE_EXCEPTIONS: True`)

---

## Configuración en Producción

### Variables de entorno requeridas (`.env`)
```
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_ALWAYS_EAGER=False
REDIS_CACHE_URL=redis://127.0.0.1:6379/2
```

> `CELERY_TASK_ALWAYS_EAGER=True` ejecuta tareas de forma síncrona (útil para debugging sin Worker).

### Servicios systemd

| Servicio | Archivo | Estado |
|----------|---------|--------|
| Redis Server | `redis-server.service` (instalado por apt) | `enabled` |
| Celery Worker | `/etc/systemd/system/celery-worker.service` | `enabled` |
| Gunicorn | `/etc/systemd/system/gunicorn.service` | `enabled` |

**Celery Worker** configurado con:
- 4 procesos paralelos (`--concurrency=4`)
- Reinicio automático tras 100 tareas (`--max-tasks-per-child=100`)
- Logs en `logs/celery-worker-*.log`
- Dependencia en `redis-server.service`
- Reinicio automático si falla (`Restart=on-failure`)

### Redis configurado con:
- **Memoria máxima**: 1 GB
- **Política de evicción**: `allkeys-lru` (elimina keys menos usadas al llenarse)
- **Bind**: `127.0.0.1` (solo localhost)
- **Protected mode**: `yes`

---

## Dependencias Agregadas

```
celery[redis]>=5.3.0        # Framework de tareas + soporte Redis
django-celery-beat>=2.5.0   # Tareas programadas (cron jobs desde Django Admin)
django-redis>=5.4.0         # Backend de cache Redis para Django
```

App agregada en `INSTALLED_APPS`:
```python
'django_celery_beat',  # Celery Beat: tareas programadas
```

---

## Migraciones

Se aplicaron 19 migraciones de `django_celery_beat` en **ambas** bases de datos:
- `python manage.py migrate django_celery_beat` (México / default)
- `python manage.py migrate django_celery_beat --database=argentina`

---

## Comandos Útiles

```bash
# Ver estado de servicios
sudo systemctl status celery-worker
sudo systemctl status redis-server

# Reiniciar worker (después de cambios en código)
sudo systemctl restart celery-worker gunicorn

# Ver logs en tiempo real
tail -f logs/celery-worker-celery-worker.service.log

# Probar conexión Redis
redis-cli ping

# Ver memoria Redis
redis-cli INFO memory | grep used_memory_human

# Limpiar cache manualmente
redis-cli -n 2 FLUSHDB

# Probar tarea desde Django shell
python manage.py shell
>>> from config.celery import debug_task
>>> debug_task.delay()
```

---

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `config/__init__.py` | Importación de Celery app |
| `config/celery.py` | **Nuevo** — Configuración de Celery |
| `config/settings.py` | Variables Celery + Cache Redis + `django_celery_beat` en INSTALLED_APPS |
| `requirements.txt` | 3 nuevas dependencias |
| `servicio_tecnico/tasks.py` | **Nuevo** — 3 tareas en segundo plano |
| `servicio_tecnico/views.py` | Refactorizado para usar `.delay()` en envíos de correo |
| `static/ts/diagnostico_modal.ts` | UI para manejo de envío asíncrono |
| `static/js/diagnostico_modal.js` | Compilado desde TypeScript |
