# Revisión de calidad de código — SIGMA

**Alcance:** análisis estático del repo `inventario-calidad-django` (rama `master` al 18-sep-2026).  
**Método:** muestreo en `config`, `servicio_tecnico`, `almacen`, `inventario`, `scorecard` y `notificaciones`. No se revisó solo el último commit de OOW.  
**Restricción:** este documento es el único entregable; no hay refactors en esta PR.

---

## 1. Veredicto general

**Nota: 6.5 / 10 — producción funcional con deuda estructural visible.**  
Tier: **B−** (capaz de operar un negocio real; todavía no es ingeniería disciplinada).

SIGMA no es un prototipo. Hay dominio de taller, cotizador, PWA dual, Celery multi-país y una capa de tests de negocio que muchos sistemas internos nunca llegan a tener. También se nota que el equipo **ya se dio cuenta** de los monolitos: `AGENTS.md` es inusualmente honesto y el código nuevo (servicios de pagos, recotización con `select_for_update`, fachadas `views.py`) sigue esas reglas.

Lo que impide una nota más alta no son nits de estilo. Es la distancia entre las reglas escritas y el volumen histórico: `models.py` / `tasks.py` siguen siendo monolitos, **no hay CI**, scorecard casi no tiene red de seguridad, y hay un puñado de riesgos reales (defaults inseguros, `generar_compras` sin transacción, cache de dashboards mal entendida, rate limit público que no bloquea). El sistema puede seguir creciendo así, pero cada feature nueva encarece el siguiente cambio.

No es “código malo”. Es **código de producto que ya ganó complejidad de ERP** y todavía no tiene el andamiaje (CI, FSM, transacciones consistentes, módulos acotados) que esa complejidad exige.

---

## 2. Lo que está genuinamente bien

### Arquitectura multi-país (la parte más madura)

El diseño database-per-tenant está pensado, no parcheado:

- Router con prioridad documentada y bugs reales ya corregidos (`sessions`/`axes` fijos a `default` para no romper login): `config/db_router.py`.
- Middleware en el orden correcto (Auth → País → ForcePasswordChange): `config/settings.py` ~L145–169.
- Celery `task_prerun` / `task_postrun` copia el contexto de país porque el worker **no** pasa por middleware: `config/celery.py` L82–136.
- Beat con fan-out por país (encuestas, vigencia de cotizaciones, notificaciones).
- Transacciones bien hechas **donde duele**: recotización usa `atomic(using=)` + `select_for_update` (`almacen/utils/recotizacion.py`).

`default` y `mexico` apuntan a la misma BD a propósito (`config/settings.py` L205–211). Eso es correcto para `manage.py`; no es un duplicado accidental.

### Modularización de vistas: las fachadas sí cumplen

| Archivo | LOC | Contrato |
|---------|-----|----------|
| `servicio_tecnico/views.py` | 262 | Solo reexports |
| `almacen/views.py` | 127 | Solo reexports |

Hay tests de humo que **exigen** que `urls.py` no se rompa al partir módulos (`servicio_tecnico/tests/test_modularizacion_views.py`, `almacen/tests/test_modularizacion_views.py`). Eso es disciplina real, no un comentario en un README.

`detalle_orden` sí se partió: shell + handlers + context en `services/` + partials. `pagos_orden.py` es el patrón correcto de “el modelo no es el cerebro”.

### Sync Almacén ↔ ST y tests de dinero

El cotizador no es un CRUD suelto. Hay integración HTTP+BD que recorre aprobar → compras → sync ST → rechazo, con Celery mockeado:

- `almacen/tests/test_integracion_cotizacion_st.py` (el docstring describe el flujo de negocio, no “importa el módulo”).
- Regresiones concretas: `test_precios_cliente_rechazo_masivo.py`, `test_generar_compras_sin_orden.py`, `test_e2e_flujo_dinero.py`.
- Listas blancas de estados al empujar ST desde almacén (`almacen/utils/sincronizar_estado_st.py`).

OOW no está “sin tests”: `servicio_tecnico/tests/test_formato_oow.py` es una suite híbrida (~1900 LOC, decenas de casos: PDF, QR, HTTP, task). El QR usa `secrets.token_urlsafe(32)` y el alias de BD de la orden (`servicio_tecnico/services/enlace_seguimiento.py` L52–56).

### Seguridad de producto (cuando DEBUG=False)

- Admin **no** está en `/admin/`: `config/urls.py` L61–62 → `/sic-gestion-sistema/`.
- Django-Axes (5 intentos, user+IP), HSTS, cookies `Secure`, CSRF cookie `sigma_csrftoken` en prod.
- Staff TS lee `sigma_csrftoken` **y** `csrftoken` (`static/ts/csrf.ts`).
- Token de seguimiento con ~256 bits; la página HTML unifica inválido/expirado (anti-enumeración básica).
- Uploads de evidencia detrás de login; imágenes con PIL `verify()`; video recodificado con FFmpeg.
- `.env` no está en git; VAPID / SICSER no van hardcodeados.

### Documentación operativa

`AGENTS.md` + `docs/` (~74 markdown) describen el sistema que **quieren** tener. Un agente o un humano nuevo puede orientarse. Eso vale. El problema (abajo) es cuando el documento afirma cosas que el código ya no cumple del todo.

---

## 3. Riesgos y deuda (priorizados, con evidencia)

### P0 — Ingeniería de proceso

#### 3.1 No hay CI. Los tests existen; nadie los corre en el PR.

`.github/` solo tiene instrucciones de Copilot. Cero workflows, cero Dependabot, cero coverage.

Hay ~113 archivos `test_*.py` y ~960 métodos `test_*` (sobre todo `almacen` + `servicio_tecnico`). El README y AGENTS documentan `manage.py test`. `docs/PRODUCTION_CHECKLIST.md` L198–201 lista CI/CD como **pendiente a medio plazo**.

En un repo de este tamaño (~154k LOC Python de apps según el propio README), un PR puede romper sync de cotizaciones o el portal público y nadie se entera hasta producción. Los comentarios “para CI” en los tests son intención, no infraestructura.

**Scorecard:** `scorecard/tests.py` es el stub de Django (`# Create your tests here.`). `scorecard/views.py` tiene **2466** líneas. Cero red de regresión en incidencias/reportes/Excel.

**config/:** router, Celery, PWA — sin suite dedicada.

---

### P0 — Seguridad de despliegue (no de diseño del portal)

#### 3.2 `SECRET_KEY` y `DEBUG` con defaults de tutorial

```29:32:config/settings.py
SECRET_KEY = config('SECRET_KEY', default='django-insecure-c^$$m7)o4(**%esnl3ao&z^n&pn3*r=^qxu-!cmczpe#wdi372')
DEBUG = config('DEBUG', default=True, cast=bool)
```

Si un worker o un Gunicorn arranca **sin** `.env`, firma sesiones con una clave que está en git y sirve el sitio en modo debug. El código no falla cerrado.

Esto **no** prueba que producción esté mal configurada hoy. Prueba que el arranque no es a prueba de olvidos. Para un sistema multi-país en Internet, el default debería ser “no arranca”.

`ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` también traen una IP LAN (`192.168.1.235`) por default (`settings.py` L53–66).

#### 3.3 Vista media en DEBUG no confina la ruta al storage

```77:86:config/media_views.py
    path = os.path.normpath(path).replace('\\', '/')
    ...
        full_path = Path(location) / path
        if full_path.exists() and full_path.is_file():
```

El comentario dice que `normpath` elimina `..`. **No es cierto** si `..` queda al inicio (`../../etc/passwd`). `Path(location) / path` puede resolver fuera del media root. La ruta solo se monta con `DEBUG=True` (`config/urls.py` L143–152). Combinado con el default de DEBUG, el riesgo deja de ser “solo laptop del desarrollador”.

En producción el comentario asume nginx; **no hay config de nginx en este repo**, así que no se pudo verificar el equivalente allí.

---

### P1 — Correctitud en caminos calientes

#### 3.4 `generar_compras` sin transacción ni bloqueo de fila

```4109:4154:almacen/models.py
        for linea in lineas_pendientes:
            compra = CompraProducto.objects.create(...)
            ...
            linea.save()
        ...
        self.estado = 'completada'
        self.save()
```

No hay `transaction.atomic(using=...)` ni `select_for_update`. Un fallo a mitad del loop deja compras a medias. Dos POST concurrentes pueden ver las mismas líneas `compra_generada__isnull=True`.

Contraste: recotización **sí** lo hace bien. La vista bloquea “sin orden vinculada” (`almacen/views_cotizacion_sync_st.py` L68–74) — eso está testeado — pero no cubre carrera ni rollback.

Además vive en el modelo gordo (`almacen/models.py`, **6593** LOC), en contra de la regla de fat models que el propio proyecto declara.

#### 3.5 Finalizar OOW/Garantía: `atomic()` sin `using=`

`aplicar_payload_borrador` usa el alias correcto. `finalizar_formato` genera el PDF **fuera** de la transacción y persiste así:

```696:703:servicio_tecnico/services/formato_oow.py
    with transaction.atomic():
        formato.pdf.save(...)
        formato.estado = 'finalizado'
        ...
        formato.save()
```

Mismo patrón en `servicio_tecnico/services/formato_garantia.py` L561. AGENTS §11 lo explica: sin `using=`, Django abre la transacción en `default` aunque el ORM escriba en `mexico`/`argentina`. En SQLite de desarrollo el bug se esconde. Si `save()` falla después de escribir bytes al storage, queda PDF huérfano.

Otros `atomic()` sueltos (mismo patrón, menor criticidad de dinero): `notificaciones_diagnostico.py` L312, `notificaciones_recepcion.py` L275.

#### 3.6 Folio FL- no es único a nivel de BD

`DetalleEquipo.orden_cliente` está indexado, **no** es `unique=True` (`servicio_tecnico/models.py` L894–899). La vista de crear orden FL hace `exists()` y luego `create()` (`almacen/views_cotizacion_sync_st.py` L397–404) sin transacción. Dos clics con el mismo folio pueden duplicar. El UNIQUE de BD que salvaría esto **no existe**.

#### 3.7 Cambio de estado en detalle de orden: no hay máquina de estados

`CambioEstadoForm.clean()` solo rellena fechas de `finalizado`/`entregado` (`servicio_tecnico/forms.py` L986–993). El modelo valida fechas, no transiciones (`servicio_tecnico/models.py` ~L419–430). El handler POST delega al form.

Un usuario con permiso puede saltar `almacen` → `entregado` o retroceder estados. El sync desde Almacén **sí** restringe avances; el formulario staff **no**. Con 22 estados (README), eso no es un detalle: es el ciclo de vida del negocio sin invariantes.

---

### P1 — Seguridad de aplicación (portal y APIs)

#### 3.8 Rate limit del portal público no bloquea

```40:40:servicio_tecnico/views_seguimiento_cliente.py
@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
```

Facturación web usa `block=True` (`views_facturacion_demanda.py` L80). El portal de seguimiento **no**. En django-ratelimit 4.x (`requirements.txt`: `django-ratelimit>=4.1.0`), sin `block=True` y sin leer `request.limited`, la vista sigue ejecutándose. Los `@ratelimit` del chat/push/eventos son en gran parte decorativos.

El token no es enumerable por fuerza bruta (32 bytes urlsafe). El hueco importa para abuso de chat IA, push y enumeración 404 vs 410 en sub-rutas (`views_seguimiento_cliente.py` L474–479).

#### 3.9 Media del cliente no vive detrás del token

La galería pública mete `img.imagen.url` en el HTML (`views_seguimiento_cliente.py` L160–171). Esas URLs `/media/servicio_tecnico/imagenes/{orden_cliente}/...` **no caducan** con el enlace. `orden_cliente` es predecible (`OOW-11902`). Quien copie la URL (o la vea en logs/referrer) sigue viendo la foto cuando el token ya no sirve.

Esto es coherente con “capability URL + nginx sirve media”, no con “el portal protege la evidencia”. Hay que decidir el modelo de amenaza.

#### 3.10 APIs de scorecard con solo `login_required`

```323:340:scorecard/views.py
@login_required
def api_empleado_data(request, empleado_id):
    ...
                'email': empleado.email or '',
```

Cualquier cuenta autenticada (p. ej. un técnico) puede leer email/área/cargo de cualquier empleado por ID. `api_buscar_reincidencias` igual: serie → incidencias. Las listas HTML de scorecard sí llevan permiso (`lista_componentes` usa `scorecard.view_componenteequipo`). Las APIs JS se quedaron atrás.

#### 3.11 Cache de dashboards: el comentario es falso

```31:35:servicio_tecnico/decorators.py
# IMPORTANTE: cache_page debe ir DESPUÉS de @login_required para que
# cada usuario autenticado tenga su propio cache (no mezclar datos).
cache_page_dashboard = cache_page(...)
```

`cache_page` de Django cachea por URI, no por usuario. Poner `@cache_page_dashboard` debajo de `@login_required` solo evita cachear el redirect de login. El dashboard extiende `base.html`, que pinta `user.get_full_name` (`templates/base.html` L463). Durante 10 minutos, el siguiente staff que abra la misma URL puede ver el nombre (y el HTML, CSRF incluido) de quien “calentó” el cache.

Usado en `views_dashboard_cotizaciones.py` y `views_dashboard_oow_fl.py`. Redis `KEY_PREFIX` es solo `sigma` (`settings.py` L617). El host entra en `build_absolute_uri()`, así que **no** afirmo filtración cruzada México/Argentina; sí afirmo filtración de chrome de usuario **dentro del mismo tenant**.

---

### P1 — Mantenibilidad (el costo que ya están pagando)

#### 3.12 Los monolitos no se fueron: se partieron en monolitos medianos

Fachadas: OK. El volumen HTTP de ST en `views_*.py` sigue en ~23k LOC.

| Archivo | LOC | vs meta interna ~800–1000 |
|---------|-----|---------------------------|
| `servicio_tecnico/views_dashboard_cotizaciones.py` | **3426** | ~3.4× |
| `servicio_tecnico/views_dashboard_oow_fl.py` | 1454 | |
| `servicio_tecnico/views_seguimiento_cliente.py` | 1434 | |
| `almacen/views_solicitudes_cotizacion.py` | 1411 | |
| `inventario/views.py` (sin partir) | **2263** | |
| `scorecard/views.py` (sin partir) | **2466** | |
| `servicio_tecnico/models.py` | **4900** | |
| `almacen/models.py` | **6593** | |
| `servicio_tecnico/tasks.py` | **5856** (22 `@shared_task`) | |

La extracción `tasks_<dominio>.py` en ST cubre un puñado de tareas; el 90%+ del Celery de ST sigue en el archivo gordo. AGENTS dice “no hinchar”; el archivo ya está hinchado.

`dashboard_cotizaciones.html` tiene **2802** líneas y **75** `print()` en la vista. Eso no es un dashboard: es un reporte embebido en un request HTTP.

#### 3.13 Docs vs realidad (los que importan)

| Afirmación | Código |
|------------|--------|
| Dev usa SQLite (AGENTS §1) | `DB_ENGINE` default **PostgreSQL** (`settings.py` L213) |
| México `db_alias = default` (tabla AGENTS §10) | `'db_alias': 'mexico'` (`paises_config.py` L46). Las tareas con `db_alias='default'` caen a México por **fallback** del prerun (`celery.py` L100–111), no porque el alias sea `default`. |
| “Nunca `any` en TS” | `strict: true` en `tsconfig.json`, pero hay `any` explícito (`camara_integrada.ts`, `voz_diagnostico.ts`, autocompletes, etc.). |
| `static/js/` no se edita | Correcto como flujo; **sí está versionado** (151 archivos). Razonable para deploy sin Node; riesgo de drift TS/JS si alguien commitea uno y no el otro. |
| `package.json` description | Badges viejos (Django 5.2.5 / Python 3.10) vs README actual. |

Ninguno de estos es un CVE. Todos hacen que un agente o un junior aplique la regla equivocada.

#### 3.14 Márgenes de negocio en el código

Fallbacks `PROFIT_*` / `COSTOS_FIJOS_*` / `DIAGNOSTICO_*` en `almacen/utils/pdf_cotizacion_cliente.py` L116–138. AGENTS dice no hardcodearlos. El `.env` puede pisarlos; git igual publica la política comercial default. `docs/COTIZADOR_PROFIT.md` está en `.gitignore` — el código no.

---

### P2 — Rendimiento (olor, no benchmark)

No se midió latencia. Esto es lectura de queries:

1. **Home ST** itera **todas** las órdenes no entregadas/canceladas en Python para armar un top 10 (`views_ordenes.py` L212–228). Crece con el backlog abierto.
2. En el mismo home, N+1 de `Empleado.objects.get` por técnico (`views_ordenes.py` L121–123).
3. **Lista activas:** el queryset principal está bien (paginación 24, `select_related`/`prefetch_related`, L511–523). Encima, cada request dispara un bloque grande de agregaciones por técnico/sucursal (PASO 1–5).
4. PDF OOW se genera **síncrono en el request** (`views_formato_oow.py` + `finalizar_formato`); el correo sí va a Celery. Con campañas/flyers, el worker HTTP se bloquea.
5. Dataframe de cotizaciones carga el rango completo a pandas (dashboard 3426 LOC). El cache de 10 min mitiga repetición, no el cold start.

`detalle_orden.html` (500 líneas) + partials (~6666 líneas) es grande pero **ya modularizado**. El problema de tamaño ahora está en dashboards, no en detalle de orden.

---

### P2 — Portal seguimiento: diseño, no IDOR clásico

Lo que **no** vi: saltar de un token a la orden de otro cliente. El lookup es `get(token=token)`. Multi-país: el token de México no resuelve en Argentina (misma UI que inválido).

Lo que sí hay:

- Sub-rutas 404 vs 410 (enumeración de “existió”).
- `@csrf_exempt` en push/chat (PWA; riesgo acotado al filtrarse el token).
- Enlace activo mientras la orden no esté `entregado`+3 días.

Eso es el modelo capability-URL. Hay que tratar el token como secreto (correo, logs, QR impreso).

---

## 4. Quick wins vs trabajo de fondo

### Quick wins (horas, no un rediseño)

| Acción | Por qué |
|--------|---------|
| GitHub Action: `python manage.py test almacen` + `servicio_tecnico.tests` + `pnpm run build` en cada PR | El valor de los ~960 tests hoy es potencial, no red. |
| Arranque: exigir `SECRET_KEY` y `DEBUG` en env; sin default inseguro | Cierra el fallo de configuración más barato. |
| `block=True` (o 429) en `@ratelimit` del portal público | Copiar el patrón de facturación. |
| Confirmar media path: `resolve().is_relative_to(media_root)` | El comentario de `normpath` miente. |
| `atomic(using=db_alias_de(formato))` en finalizar OOW/Garantía | El helper ya existe; el borrador ya lo usa. |
| Envolver `generar_compras` en `atomic(using=)` + `select_for_update` de la solicitud | Mismo patrón que recotización. |
| Permiso en `api_empleado_data` / reincidencias | Una línea de decorador. |
| `@vary_on_cookie` o fragment-cache (no cachear `base.html`) en dashboards | El comentario actual da falsa seguridad. |
| `unique=True` (o constraint) en `orden_cliente` si el negocio lo permite | Cierra duplicados FL- de verdad. |
| Unificar 404 en sub-rutas de seguimiento | Cierra enumeración barata. |

### Trabajo de fondo (semanas de diseño, no “partir el archivo”)

1. **CI verde + coverage mínimo** en almacén/ST; después scorecard. Sin esto, extraer modelos es teatro.
2. **FSM de `OrdenServicio`** (transiciones permitidas por rol). Hoy el sync Almacén y el form staff cuentan historias distintas.
3. **Seguir extrayendo** `tasks.py` ST y `views_dashboard_cotizaciones.py` con el patrón que ya funciona — congelar tamaño de `models.py`.
4. **Media sensible:** URLs firmadas o proxy que exija token. Si no, documentar que `/media/` es público y no hablar de “portal privado”.
5. **Scorecard al patrón ST/Almacén** (fachada + `views_*.py` + tests). Es el módulo de calidad del sistema y el peor cubierto.
6. **`generar_compras` y sync** fuera del modelo, en `almacen/utils/`, como ya hicieron con recotización y bajas.
7. Medir de verdad home/lista/dashboard en PostgreSQL con datos de producción (EXPLAIN), no optimizar a ciegas.

No recomiendo “partir `models.py` de golpe”. AGENTS tiene razón: rompe templates y sync. Extraer **solo** lo que se toque por un bug.

---

## 5. Qué no se verificó

| Ítem | Motivo |
|------|--------|
| Suite completa (`manage.py test`) y si está verde en `master` | Revisión estática; no se ejecutaron tests en este entorno. |
| Comportamiento transaccional real en **PostgreSQL** multi-país | Dev/SQLite oculta `select_for_update` / `atomic(using=)`. |
| `.env` / nginx / Cloudflare de producción | No están en el repo. |
| Si la `SECRET_KEY` default **alguna vez** se usó en prod | No hay evidencia aquí; el riesgo es hipotético pero el default es real. |
| Carga concurrente (doble clic en compras / FL) | Solo análisis de TOCTOU. |
| XSS almacenado en chat IA / campos libres del cliente | Templates de seguimiento no usan `\|safe` obvio; no se auditó cada escape en TS. |
| Escrituras accidentales a SICSER | Se respetó el cliente de solo lectura en el muestreo; no se leyó cada llamada. |
| Drift `static/ts` vs `static/js` commiteado | No se corrió `pnpm run build` ni un diff. |
| Tiempos reales de PDF OOW con campañas | No hay profiling. |
| PWA / service worker / push en dispositivo | Fuera de alcance. |
| Permisos reales de grupos Django en un tenant poblado | `scripts/test_permisos.sh` no se ejecutó. |
| ML / Plotly correctness | Scripts manuales en `scripts/testing/`; no suite formal. |

---

## Apéndice: muestreo (para no sesgar por OOW)

| App | Qué se miró | Impresión |
|-----|-------------|-----------|
| `config` | settings, urls, router, celery, media_views | Multi-país sólido; defaults y media DEBUG flojos. |
| `servicio_tecnico` | órdenes, detalle, seguimiento, OOW, dashboards, tasks | Núcleo rico; módulos aún enormes; tests densos en lo tocado. |
| `almacen` | compras, cotización, sync ST, profit | Mejor disciplina de tests; `generar_compras` es el hueco serio. |
| `inventario` | views 2263 LOC, empleados/sucursales | Hub razonable; sin modularizar. |
| `scorecard` | views 2466, APIs, tests stub | El punto ciego del repo. |
| `notificaciones` | push staff/cliente (referencia cruzada) | Separación staff/cliente respetada en URLs. |

Últimos commits de `master` al revisar: portada OOW con QR, campañas PDF. Se usaron como *un* hot path, no como el único.

---

*Revisión honesta para Jorge. Si hay que atacar una sola cosa después de leer esto: **CI que corra la suite de almacén + ST**, y en paralelo el `atomic` de `generar_compras`. Lo demás puede esperar un sprint; eso no.*
