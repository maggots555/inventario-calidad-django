# AGENTS.md - Development Guide for AI Coding Agents

> **Project**: Sistema Integrado de Gestión Técnica y Control de Calidad (SIGMA)  
> **Framework**: Django 5.2.5 | Python 3.12+ | TypeScript 5.9.3  
> **Purpose**: Enterprise technical service management with ML analytics  
> **Deployment**: PWA — instalable en móviles como app nativa

---

## Idioma, docstrings y usuario

**CRITICAL — comunicación:** TODA comunicación con el usuario DEBE ser en **español (es-MX)**.
- ✅ Siempre responder, explicar y usar terminología de negocio en español
- ❌ Nunca responder en inglés (excepto código / comentarios técnicos estándar)
- ❌ Nunca asumir que el usuario prefiere inglés

**Usuario principiante en Python:** explicar cada cambio en español, lenguaje simple, comentarios `EXPLICACIÓN PARA PRINCIPIANTES` cuando aporte claridad, señalar patrones Django.

### Reglas estrictas de documentación inline y docstrings

**Idioma y tono:** Todos los comentarios inline y docstrings DEBEN estar en **español (es-MX)**, con tono didáctico/pedagógico para que un principiante entienda el *por qué* de la lógica. No asumas que el código “se explica solo”.

**Cobertura de docstrings:** Toda clase, vista Django, tarea Celery, método o componente TypeScript DEBE iniciar con un bloque que detalle:
1. Objetivo principal (contexto de negocio)
2. Argumentos/parámetros y tipos esperados
3. Efectos secundarios (BD, eventos, tareas encoladas, etc.)

**Densidad de comentarios inline:** Toda lógica que involucre manipulación de archivos/multimedia (p. ej. FFmpeg), async/Celery, o QuerySets/filtros/condicionales complejos DEBE llevar comentarios paso a paso cada **3 o 5 líneas** de código lógico.

**Restricción:** Se PROHÍBE entregar funciones o bloques de más de **10 líneas** de lógica de negocio pura sin al menos **dos comentarios inline** que expliquen el flujo de los datos.

**Naming de dominio:** variables de negocio en español (`orden`, `precio_total`); términos técnicos estándar pueden ir en inglés (`queryset`, `DataFrame`, `pk`).

---

## 1. BUILD / TEST / DATOS

### Comandos frecuentes
Ver también **§9 Quick Reference**.

```bash
python manage.py runserver
python manage.py makemigrations && python manage.py migrate
python manage.py shell
python manage.py collectstatic   # producción
pnpm run build                   # TypeScript (nunca editar static/js/)
pnpm run watch
python scripts/poblado/poblar_sistema.py
python scripts/poblado/poblar_scorecard.py
```

### Política de tests (única fuente)

**CRITICAL:** si el trabajo introduce o cambia comportamiento verificable, **incluir o ampliar al menos un test**. No dejar solo checklist manual cuando se pueda automatizar.

```
✅ SÍ test: vista/API/URL nueva; regla en models/services/utils; sync Almacén↔ST / profit /
   cotizaciones / Celery+BD; modularización (reexport+resolve); bugfix (regresión)

❌ NO hace falta suite pesada: solo docs; CSS cosmético; rename sin cambio de comportamiento;
   el usuario pide explícitamente no testear aún

Mínimo: humo (resolve/reexport/import/status) → mejor 1 feliz + 1 borde
No enviar correos/PDF/FFmpeg reales en CI — mockear .delay() / IO
Dónde: almacen/tests/ o servicio_tecnico/tests/ (no scripts sueltos salvo scripts/testing/)
```

```bash
python manage.py test almacen
python manage.py test almacen.tests.test_profit_cotizacion
python manage.py test almacen.tests.test_sincronizar_componente_st
python manage.py test almacen.tests.test_generar_compras_sin_orden
python manage.py test almacen.tests.test_costeo_reacondicionado
python manage.py test almacen.tests.test_totales_cotizacion
python manage.py test servicio_tecnico.tests
./scripts/test_permisos.sh
# Manuales: scripts/testing/ (email, PDF RHITSO, ML, storage)
```

---

## 2. CODE STYLE (compacto)

**Imports:** stdlib → Django → third-party → local. Explícitos; no `import *`.

**Naming:** Models `PascalCase`; funciones/vars `snake_case`; constantes `UPPER_SNAKE`. Dominio en español; constructs genéricos en inglés.

**Django:**
- FBV preferidas; `get_object_or_404`; feedback con `messages`; URLs con nombre (`redirect` / `{% url %}`).
- Models: docstring, `__str__()`, `Meta` con `verbose_name`.
- Forms: widgets con clases Bootstrap (`form-control`, etc.).
- Vistas nuevas de ST: módulo `views_*.py` + reexport (ver Modularidad), no hinchar `views.py`.

**TypeScript:** ver §4 (única lista crítica). Tipado explícito; no `any`.

**Templates:** `{% extends 'base.html' %}`, `{% static %}`, CSS/JS externos (nunca bloques grandes inline).

**Features nuevas (checklist):** model → admin → form → view → urls → template → static CSS/TS → migrate → **test**.

---

## 3. PROJECT STRUCTURE

```
inventario-calidad-django/
├── config/                 # settings, urls, storage, constants, multi-país, PWA views
├── inventario/             # inventario + empleados; ForcePasswordChangeMiddleware
├── servicio_tecnico/       # app principal ST
│   ├── views.py            # reexports + detalle_orden (NO re-inflar monolito)
│   ├── views_*.py          # vistas por dominio
│   ├── services/           # historial, multimedia, notifs, analytics VM
│   ├── decorators.py       # permission_required_with_message, cache_page_dashboard
│   ├── tests/              # humo modularización
│   ├── models.py, tasks.py, signals.py
│   ├── plotly_visualizations.py, ml_*, ollama/gemini, sicser_*, utils_*
│   └── ...
├── scorecard/
├── almacen/                # cotizador; utils/; tests/ formales; tasks.py
├── notificaciones/         # Push staff + cliente
├── static/
│   ├── ts/                 # FUENTE (editar aquí) — módulos por feature, ver §5
│   ├── js/                 # AUTO-GENERADO — no editar
│   ├── css/                # base.css (dark mode), components, forms
│   └── audio/, images/
├── templates/              # base.html, offline.html
├── media/                  # por país
├── scripts/                # testing/, poblado/, verificacion/
├── ml_models/
├── manage.py, requirements.txt, package.json
├── tsconfig.json, tsconfig.sw.json
└── AGENTS.md
```

**Middleware (no reordenar):** Auth → `PaisMiddleware` → `ForcePasswordChangeMiddleware`.

---

## 4. CRITICAL PROJECT RULES

### Static / CSS / JS
- ❌ CSS/JS extensos en templates → ✅ `{% static %}` a `static/css/` y `static/js/` (compilado desde TS).
- Ejemplo: `<link rel="stylesheet" href="{% static 'css/components.css' %}">`

### TypeScript (única lista)
- ❌ NUNCA editar `static/js/` (auto-generado)
- ✅ SIEMPRE crear/editar `static/ts/`
- ❌ NUNCA `any`; tipar parámetros y retornos
- ✅ SIEMPRE `pnpm run build` antes de probar/commitear
- ❌ NUNCA ignorar errores de `tsc`

### Database
- Dev: SQLite (`DB_ENGINE=django.db.backends.sqlite3`)
- Prod: PostgreSQL (pooling según settings)
- Secrets solo vía `python-decouple` / `.env` (nunca commitear `.env`)

### Security
- Django-Axes; CSRF activo (`CSRF_COOKIE_NAME = 'sigma_csrftoken'` en producción)
- HSTS con `DEBUG=False`
- Fetch/TS: leer cookie CSRF de producción (no asumir `csrftoken`)

### Modularidad de vistas — no re-inflar monolitos (Julio 2026)

**Contexto:** `servicio_tecnico/views.py` llegó a ~19 000 LOC; se modularizó (`views_*.py` + `services/` + reexports). Hoy es principalmente reexports + `detalle_orden`. Objetivo cumplido: archivos navegables.

```
❌ NUNCA features grandes en un views.py denso
❌ NUNCA meter dashboards/AJAX/APIs nuevas en el monolito residual
❌ NUNCA cambiar urls.py si views.py ya reexporta (salvo pedido explícito)
❌ NUNCA lógica de negocio en templates → services/ o utils/

✅ Módulo hermano por dominio: views_mi_feature.py | services/mi_helper.py | tests/
✅ Reexport desde views.py si urls usa views.foo
✅ Preferir < ~800–1000 LOC; si crece, partir ANTES de seguir sumando
✅ En services/: from servicio_tecnico.models import ... (NO from .models)
✅ Comportamiento nuevo/cambiado → test (ver §1 Política de tests)
```

| Módulo | Dominio |
|--------|---------|
| `views_ordenes.py` | inicio, crear, listas, cerrar |
| `views_rhitso.py` / `views_envios_cliente.py` | RHITSO por orden + envíos cliente |
| `views_dashboard_*.py` | Dashboards Plotly/Excel |
| `views_piezas_*` / `views_venta_mostrador_ajax.py` | AJAX piezas / VM |
| `views_multimedia.py`, `views_seguimiento_cliente.py`, `views_encuestas.py`, … | Multimedia, portal, APIs |
| `services/` | historial, multimedia, notificaciones_piezas, ventas_mostrador_analytics |
| `views.py` | reexports + `detalle_orden` |

**Pendiente opcional (no urgente):** `detalle_orden` → `views_detalle_orden.py`; luego handlers por `form_type`. Features nuevas van a módulos propios.

Misma idea en TS/CSS: no un único archivo gigante; no hinchar más `detalle_orden.html` con CSS/JS inline.

---

## 5. SPECIAL FEATURES & INTEGRATIONS

### ML / Analytics
- `servicio_tecnico/ml_advanced/`, `ml_predictor.py`, modelos en `ml_models/`
- Charts: `plotly_visualizations.py`; concentrado CIS (`concentrado_semanal.py` + TS); analytics RHITSO; embudo seguimiento

### RHITSO
Lab externo: correos, PDF ReportLab, estados, analytics candidatos (`utils_rhitso_analytics.py`). Gestión por orden: `views_rhitso.py`; dashboard: `views_dashboard_rhitso.py`.

### Dynamic storage
Failover disco primario/alterno (`.env`: `PRIMARY_MEDIA_ROOT`, `ALTERNATE_MEDIA_ROOT`, `MIN_FREE_SPACE_GB`).

### Video / cámaras / resumen
- TS: `upload_video.ts`, `camara_integrada.ts`, `camara_video.ts`, `compartir_video.ts`, `video_resumen.ts`
- Celery en `servicio_tecnico/tasks.py`: comprimir, resumen, evidencia, rewind egreso
- Envíos HTTP: `views_envios_cliente.py`

### IA en diagnóstico / encuestas / home
- Voz SIC: `voz_diagnostico.ts` (Web Speech → Whisper → Gemini)
- Pulir diag: `ollama_sic.ts` + `pulir_diagnostico_sic_ia` (distinto de voz)
- Inspector visual ingreso: `ollama_client.py` / `gemini_client.py` (fail-safe)
- Sentimientos encuestas + PDF ejecutivo; cita diaria home (`inventario/views.py`)

### SICSER (Fase 1 — solo lectura + import SIGMA)
- Cliente: `sicser_client.py` (caché Redis); import: `sicser_import.py`; UI: `consultar_sicser.ts`
- Campos: `folio_sicser` (y relacionados) en `DetalleEquipo`
- Env: `SICSER_BASE_URL`, `SICSER_TOKEN_*`, `SICSER_CACHE_TTL`
- ❌ NUNCA inventar writes a SICSER; no hardcodear URLs/tokens

### Portal seguimiento cliente (ecosistema dual)

URL pública `/seguimiento/<token>/` (`config/urls.py`); modelo `EnlaceSeguimientoCliente`.  
Chat: `seguimiento_chat.ts` + `chat_seguimiento_helpers.py` + `CHAT_SEGUIMIENTO_*`.  
Analytics: `EventoSeguimientoCliente` + `eventos_seguimiento.ts`.  
Banners: `BannerPromocional` + `banner_carousel.ts`.

| Canal | Manifest / Install | Push TS | Suscripción |
|-------|-------------------|---------|-------------|
| **Staff** | `manifest.json` + `pwa_install.ts` | `push_notifications.ts` | `PushSubscription` → User |
| **Cliente** | `manifest_seguimiento` + `pwa_install_seguimiento.ts` | `push_notifications_cliente.ts` | `PushSubscriptionCliente` → Enlace |

```
❌ NUNCA mezclar scripts/modelos staff ↔ cliente
❌ NUNCA asumir push en todo cambio de estado — solo ESTADOS_PUSH_TECNICO / ESTADOS_PUSH_CLIENTE
✅ Preservar hooks de eventos_seguimiento.ts al editar el portal
```

### PWA Staff — reglas
- NO quitar `rel=manifest`, meta `apple-mobile-web-app-*`, ni `viewport-fit=cover`
- NO `maximum-scale` > 1; NO alterar registro del service worker en `base.html`
- Mobile-first (375px+); touch ≥44×44px; sin hover-only
- SW: `service_worker.ts` + `tsconfig.sw.json`; offline: `templates/offline.html`
- Push staff: `pywebpush` + VAPID; modelo `PushSubscription`; solo si estado ∈ `ESTADOS_PUSH_TECNICO`
- Recordatorio imágenes: inmediato al pasar a `finalizado` + Beat diario (`RecordatorioImagenOrden` / `verificar_recordatorios_imagenes`)

### Sync Almacén ↔ ST (cotizaciones)

**Almacén → ST:** `SolicitudCotizacion`+orden → `Cotizacion`; líneas → `PiezaCotizada`; aprobar/rechazar → `aceptada_por_cliente`; `precio_unitario_cliente` manda en totales ST.

**Cotizador cliente:** `cotizacion_cliente_modal.ts`, PDF `almacen/utils/pdf_cotizacion_cliente.py`, task `enviar_cotizacion_cliente_task`. Márgenes solo `.env` (`PROFIT_*`, `COSTOS_FIJOS_*`, `DIAGNOSTICO_*`).

**Reacondicionado (paralelo):** `costeo_reacondicionado.py`, PDF/modal propios — ❌ no reusar profit de reparación a ciegas.

**VM / servicios adicionales:** `LineaServicioAdicional` → al generar compras crea/actualiza `VentaMostrador`.

**Sin orden:** modo `sin_orden_activa`; vincular o `crear_orden_fl_desde_cotizacion`.  
**Catálogo:** `resolver_componente.py` + keywords en `config/constants.py`.

```
❌ Piezas con linea_cotizacion_almacen: no editar/eliminar desde ST
❌ generar_compras_solicitud exige orden_servicio vinculada
✅ costo_mano_obra arranca en $0; sync en save()
✅ Al tocar cotizaciones/sync: python manage.py test almacen
```

Archivos: `almacen/models.py`, `almacen/views.py` (`vincular_orden_solicitud`, `generar_compras_solicitud`, …), `almacen/utils/`.

### Dark mode

Todo CSS nuevo debe ser compatible. Bootstrap 5.3 usa `<html data-bs-theme>`. Toggle: `dark_mode.ts`. Variables en `static/css/base.css` (`:root` + `[data-bs-theme="dark"]`).

| Pieza | Archivo |
|-------|---------|
| Tema + anti-flash | `templates/base.html` (script anti-flash: **no tocar**) |
| Toggle | `#darkModeToggle` |
| Lógica | `static/ts/dark_mode.ts` |
| Variables/overrides | `static/css/base.css` |

**Paleta oscura (referencia):** `--body-bg #0f172a`, `--card-bg #1e293b`, `--text-primary #e2e8f0`, `--border-color #334155`, estados `#60a5fa/#34d399/#f87171/#fbbf24/#22d3ee`. Theme-color: claro `#1f6391` / oscuro `#0f172a`.

Preferir `var(--primary-color)`, `var(--gray-*)`, `var(--white)`, sombras del tema.

```css
/* Preferir variables; si hardcodeas, añade override oscuro */
.mi-bloque { background-color: var(--gray-50); color: var(--gray-900); }
.especial { background-color: #1f6391; color: #fff; }
[data-bs-theme="dark"] .especial { background-color: #1e293b; color: #e2e8f0; }
```

```
❌ Colores hardcodeados sin override dark; background:white / color:black sueltos
❌ Tocar script anti-flash; data-bs-theme fuera de <html>
❌ Gradientes / glassmorphism genéricos (IA Slop) salvo pedido explícito
✅ Overrides [data-bs-theme="dark"] en CSS nuevo; probar ambos modos
✅ En TS: document.documentElement.getAttribute('data-bs-theme')
```

---

## 6. ENVIRONMENT VARIABLES

Fuente de verdad: **`.env.example`**. No hardcodear secretos ni márgenes.

Grupos clave: Django (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`); DB; email; storage (`PRIMARY_MEDIA_ROOT`, …); `REDIS_CACHE_URL` (cache `/2`; Celery `/0`–`/1`); `CHAT_SEGUIMIENTO_*`; `PROFIT_*` / `COSTOS_FIJOS_*` / `DIAGNOSTICO_*`; `SICSER_*`.

**CSRF prod:** cookie `sigma_csrftoken` — todo `fetch` debe leerla.

---

## 7. TESTING (resumen)

Política y comandos: **§1**. Suites: `almacen/tests/` (formal), `servicio_tecnico/tests/` (humo modularización), `scripts/testing/` (manual). Ampliar tests ST (seguimiento/SICSER/push) cuando se toquen esas áreas.

---

## 8. COMMON PITFALLS

1. No editar JS compilado — solo `.ts`
2. No hardcodear URLs — `{% url %}` / `reverse()`
3. No saltar migraciones
4. No commitear secrets (`.env`)
5. Siempre `messages` al usuario en acciones
6. Dominio en español; tech estándar en inglés
7. Widgets Bootstrap en forms
8. `__str__()` en models
9. No CSS/JS inline masivo en templates
10. `pnpm run build` antes de probar TS
11. No romper PWA (`manifest`, apple-meta, `viewport-fit=cover`, registro SW)
12. UI mobile-first; sin hover-only
13. Colores: variables o override dark — ver §5 Dark mode
14. No tocar anti-flash en `base.html`
15. No gradientes genéricos salvo pedido
16. Celery + BD → siempre `db_alias` — ver §10
17. No mezclar PWA/push staff ↔ cliente
18. No hardcodear `PROFIT_*` / `COSTOS_FIJOS_*` / `DIAGNOSTICO_*`
19. No `generar_compras` sin orden vinculada
20. No writes inventados a SICSER
21. Push solo en `ESTADOS_PUSH_*`
22. CSRF prod = `sigma_csrftoken`
23. No re-inflar monolitos de vistas — §4 Modularidad; en `services/` no `from .models`
24. Comportamiento nuevo → test (§1); excepción: docs/CSS cosmético o pedido del usuario

---

## 9. QUICK REFERENCE

| Task | Command |
|------|---------|
| Server | `python manage.py runserver` |
| Migrate | `python manage.py migrate` |
| Makemigrations | `python manage.py makemigrations` |
| Superuser | `python manage.py createsuperuser` |
| Shell | `python manage.py shell` |
| Build TS | `pnpm run build` |
| Watch TS | `pnpm run watch` |
| Tests all | `python manage.py test` |
| Tests Almacén | `python manage.py test almacen` |
| Tests ST | `python manage.py test servicio_tecnico.tests` |
| Seed | `python scripts/poblado/poblar_sistema.py` |

---

## 10. CELERY MULTI-TENANT — REGLAS CRÍTICAS

Arquitectura **Database-per-Tenant** (subdominio → BD). Workers Celery **no** pasan por `PaisMiddleware`; sin `db_alias` todo cae en BD `default` (México).

| Componente | Archivo | Rol |
|---|---|---|
| `task_prerun` | `config/celery.py` | Lee `db_alias` de kwargs → thread-locals |
| DB Router | `config/db_router.py` | Enruta queries al tenant |
| `get_pais_actual()` | `config/paises_config.py` | HTTP: subdominio; tasks: thread-locals ya set |

**Toda tarea que toque BD:**

1. Firma con `db_alias='default'`:
```python
@shared_task(bind=True, ...)
def mi_nueva_tarea(self, param1, param2, usuario_id=None, db_alias='default'):
    # ORM se enruta solo — NO hace falta .using(db_alias)
    objeto = MiModelo.objects.get(pk=param1)
```

2. Encolar desde vista con país actual:
```python
from config.paises_config import get_pais_actual
mi_nueva_tarea.delay(
    param1=valor, param2=valor,
    usuario_id=request.user.pk,
    db_alias=get_pais_actual()['db_alias'],
)
# ❌ .delay(...) sin db_alias → siempre México
```

3. En chains, `db_alias` dentro de cada `.s()`:
```python
_db = get_pais_actual()['db_alias']
celery_chain(tarea_a.s(orden_id, usuario_id, _db), tarea_b.s(orden_id, usuario_id, _db)).delay()
```

| País | Subdominio | `db_alias` |
|---|---|---|
| México | `app.sigmasystem.work` | `default` |
| Argentina | `argentina.sigmasystem.work` | `argentina` |
| Chile | `chile.sigmasystem.work` | `chile` |
| Colombia | `colombia.sigmasystem.work` | `colombia` |

**Beat** (`CELERY_BEAT_SCHEDULE` en settings): también multi-tenant si toca BD por país.

| Job | Task | Schedule |
|-----|------|----------|
| Limpiar notificaciones | `notificaciones.limpiar_antiguas` | 24 h |
| Encuestas pendientes | `servicio_tecnico.verificar_encuestas_pendientes` | Diario 8:00 |
| Recordatorio imágenes | `servicio_tecnico.verificar_recordatorios_imagenes` | Diario 8:00 |

**Redis:** Celery `/0`–`/1`; cache Django `/2` (`REDIS_CACHE_URL`). Cache con `IGNORE_EXCEPTIONS=True`. No mezclar DBs.

**Tasks (inventario breve):**  
ST — RHITSO/feedback/vigencia, diagnóstico/imágenes, seguimiento, video resumen/comprimir/evidencia/rewind.  
Almacén — `notificar_front_cotizacion_task`, `notificar_compras_nueva_cotizacion_task`, `enviar_cotizacion_cliente_task`.  
Todas ya llevan `db_alias` en firma; nuevas igual.

---

**Last Updated**: Julio 2026  
**Django Version**: 5.2.5  
**Python Version**: 3.12+  
**TypeScript Version**: 5.9.3
