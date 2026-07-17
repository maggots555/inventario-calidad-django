"""
Vistas públicas del portal de seguimiento del cliente (Fase 3 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Estas URLs viven en config/urls.py (sin login): /seguimiento/<token>/, feedback,
chat IA, PWA/push del cliente y eventos del embudo.

config/urls.py importa los nombres desde servicio_tecnico.views — por eso
views.py reexporta todo este módulo (no hay que editar config/urls.py).

NO mezclar con push/PWA del staff (PushSubscription vs PushSubscriptionCliente).
"""

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .models import HistorialOrden, ImagenOrden

logger = logging.getLogger(__name__)


# ============================================================================
# VISTA PÚBLICA: seguimiento_orden_cliente
# Página accesible sin autenticación. El cliente abre el link desde el correo
# de seguimiento y ve la información de su equipo, timeline de estados y
# datos de contacto de su responsable de seguimiento.
# ============================================================================

@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
def seguimiento_orden_cliente(request, token):
    """
    Vista pública de seguimiento de orden para el cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista NO usa @login_required porque la abre el cliente desde su correo.
    Valida el token antes de mostrar cualquier información.
    States del template:
      - 'tracking': Orden activa con timeline
      - 'finalizado': Orden finalizada, esperando confirmación de entrega
      - 'entregado': Agradecimiento + link a encuesta si existe
      - 'invalido': Token no existe, orden cancelada o link expirado
    """
    from .models import EnlaceSeguimientoCliente, FeedbackCliente, BannerPromocional
    from .chat_seguimiento_helpers import (
        construir_timeline_seguimiento_cliente,
        obtener_chips_chat_seguimiento,
    )
    from config.paises_config import PAISES_CONFIG

    TEMPLATE = 'servicio_tecnico/seguimiento_cliente.html'

    # ── Obtener IP del cliente para logging de seguridad ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR')

    # ── Buscar el enlace por token ──
    try:
        enlace = EnlaceSeguimientoCliente.objects.select_related(
            'orden__detalle_equipo',
            'orden__sucursal',
            'orden__responsable_seguimiento',
        ).get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        logger.warning(
            "[SEGURIDAD] Seguimiento con token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return render(request, TEMPLATE, {'estado': 'invalido'})

    orden = enlace.orden
    detalle = orden.detalle_equipo

    # ── Verificar disponibilidad (expirado, cancelado o desactivado) ──
    if not enlace.esta_disponible:
        return render(request, TEMPLATE, {'estado': 'invalido'})

    # ── Registrar acceso del cliente ──
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    ip_cliente = (
        x_forwarded.split(',')[0].strip() if x_forwarded
        else request.META.get('REMOTE_ADDR')
    )
    enlace.registrar_acceso(ip=ip_cliente)

    from servicio_tecnico.eventos_seguimiento import registrar_evento_seguimiento
    registrar_evento_seguimiento(enlace, 'visita_pagina', request=request)

    # ── Construir timeline de cambios de estado (lógica compartida con el chat IA) ──
    from .chat_seguimiento_helpers import construir_timeline_seguimiento_cliente

    historial_estados = HistorialOrden.objects.filter(
        orden=orden,
        tipo_evento='cambio_estado',
    ).order_by('fecha_evento').values(
        'estado_nuevo', 'fecha_evento'
    )

    ahora = timezone.now()
    timeline_ctx = construir_timeline_seguimiento_cliente(
        historial_estados,
        orden.estado,
        ahora=ahora,
    )
    timeline = timeline_ctx['timeline']
    siguiente_paso_texto = timeline_ctx['siguiente_paso_texto']
    estado_es_hito = timeline_ctx['estado_es_hito']

    estado_orden = orden.estado
    if estado_orden == 'cancelado':
        return render(request, TEMPLATE, {'estado': 'invalido'})

    # ── Datos del responsable de seguimiento ──
    responsable = orden.responsable_seguimiento
    whatsapp_url = None
    email_responsable = None
    nombre_responsable = None

    if responsable:
        nombre_responsable = responsable.nombre_completo
        email_responsable = responsable.email

        # Construir link de WhatsApp
        if responsable.numero_whatsapp:
            pais_code = getattr(orden.sucursal, 'pais', 'mexico') if orden.sucursal else 'mexico'
            pais_conf = PAISES_CONFIG.get(pais_code, PAISES_CONFIG.get('mexico', {}))
            codigo_tel = pais_conf.get('codigo_telefonico', '52')
            numero = responsable.numero_whatsapp
            folio = detalle.orden_cliente or orden.numero_orden_interno
            service_tag = detalle.numero_serie or ''
            msg = (
                f"Hola, me puedes ayudar con el seguimiento de mi orden "
                f"\"{folio}\" / \"{service_tag}\", por favor."
            )
            from urllib.parse import quote
            whatsapp_url = f"https://wa.me/{codigo_tel}{numero}?text={quote(msg)}"

    # Folio visible para el cliente
    folio_display = detalle.orden_cliente or orden.numero_orden_interno

    # ── Imágenes del equipo para la galería pública ──
    # Solo se muestran los tipos relevantes para el cliente (no autorizacion/packing).
    _TIPO_LABEL_GALERIA = {
        'ingreso':     'Ingreso',
        'diagnostico': 'Diagnóstico',
        'reparacion':  'Reparación',
        'egreso':      'Egreso',
    }
    imagenes_galeria = [
        {
            'url':        img.imagen.url,
            'tipo':       img.tipo,
            'tipo_label': _TIPO_LABEL_GALERIA.get(img.tipo, img.tipo.capitalize()),
            'descripcion': img.descripcion,
        }
        for img in ImagenOrden.objects.filter(
            orden=orden,
            tipo__in=['ingreso', 'diagnostico', 'reparacion', 'egreso'],
        ).order_by('tipo', 'fecha_subida')
    ]

    # ── Seguimientos de piezas (solo cuando el estado es 'esperando_piezas') ──
    # Solo se exponen al cliente: nombre del componente, descripción, timeline y fechas.
    # No se incluyen: proveedor, número de pedido, notas internas ni costos.
    seguimientos_piezas = []
    if estado_orden == 'esperando_piezas':
        # Flujo normal de estados en orden de progresion visual
        _PASOS_NORMALES = [
            ('pedido',     'Pedido'),
            ('confirmado', 'Confirmado'),
            ('transito',   'En Tránsito'),
            ('recibido',   'Recibido'),
        ]
        _IDX_NORMAL = {c: i for i, (c, _) in enumerate(_PASOS_NORMALES)}
        try:
            for s in orden.cotizacion.seguimientos_piezas.prefetch_related(
                'piezas__componente'
            ).order_by('fecha_pedido'):
                nombres = [p.componente.nombre for p in s.piezas.all()]
                estado_actual = s.estado

                # Construir timeline visual (lista de pasos con tipo para CSS)
                # Tipos: 'completado' | 'actual' | 'alerta' | 'pendiente' | 'problema'
                _timeline = []
                if estado_actual in ('incorrecto', 'danado'):
                    # Todos los pasos normales completados + paso final de problema
                    for _, nombre in _PASOS_NORMALES:
                        _timeline.append({'nombre': nombre, 'tipo': 'completado'})
                    _nombres_problema = {
                        'incorrecto': 'P. Incorrecta',
                        'danado':     'P. Dañada',
                    }
                    _timeline.append({
                        'nombre': _nombres_problema.get(estado_actual, estado_actual),
                        'tipo': 'problema',
                    })
                elif estado_actual == 'retrasado':
                    # Pedido/Confirmado completados, Retrasado como alerta, Recibido pendiente
                    _timeline.extend([
                        {'nombre': 'Pedido',     'tipo': 'completado'},
                        {'nombre': 'Confirmado', 'tipo': 'completado'},
                        {'nombre': 'Retrasado',  'tipo': 'alerta'},
                        {'nombre': 'Recibido',   'tipo': 'pendiente'},
                    ])
                else:
                    idx_actual = _IDX_NORMAL.get(estado_actual, 0)
                    # 'recibido' es el último paso y ya está finalizado: todos completados
                    es_ultimo_completado = (estado_actual == 'recibido')
                    for i, (_, nombre) in enumerate(_PASOS_NORMALES):
                        if i < idx_actual or es_ultimo_completado:
                            tipo = 'completado'
                        elif i == idx_actual:
                            tipo = 'actual'
                        else:
                            tipo = 'pendiente'
                        _timeline.append({'nombre': nombre, 'tipo': tipo})

                seguimientos_piezas.append({
                    'nombre':         ', '.join(nombres) if nombres else '',
                    'descripcion':    s.descripcion_piezas,
                    'estado':         estado_actual,
                    'estado_nombre':  s.get_estado_display(),
                    'fecha_pedido':   s.fecha_pedido,
                    'fecha_estimada': s.fecha_entrega_estimada,
                    'fecha_real':     s.fecha_entrega_real,
                    'timeline':       _timeline,
                })
        except Exception:
            pass

    # ── Construir contexto según estado ──
    context = {
        'orden': orden,
        'detalle': detalle,
        'timeline': timeline,
        'estado_actual_nombre': timeline_ctx['estado_actual_texto'],
        'folio_display': folio_display,
        'nombre_responsable': nombre_responsable,
        'email_responsable': email_responsable,
        'whatsapp_url': whatsapp_url,
        'dias_restantes': enlace.dias_restantes,
        'siguiente_paso': siguiente_paso_texto,
        'imagenes_galeria': imagenes_galeria,
        'seguimientos_piezas': seguimientos_piezas,
        # ── Chat de IA ──
        # token: lo necesita el template para construir la URL del endpoint AJAX
        # ai_enabled: controla si se renderiza el widget del chatbot
        'token': token,
        'ai_enabled': getattr(settings, 'AI_ENABLED', False),
        # PDF de diagnóstico persistente (para botón en la PWA)
        'tiene_pdf_diagnostico': bool(enlace.pdf_diagnostico),
        'url_diagnostico_pdf': reverse(
            'diagnostico_pdf_seguimiento',
            kwargs={'token': token},
        ) if enlace.pdf_diagnostico else '',
        'folio_diagnostico': enlace.folio_diagnostico or '',
        # Chips dinámicos del chat según estado de la orden
        'chat_chips': obtener_chips_chat_seguimiento(
            estado_orden,
            tiene_pdf_diagnostico=bool(enlace.pdf_diagnostico),
            tiene_seguimientos_piezas=bool(seguimientos_piezas),
        ),
    }

    if estado_orden == 'entregado':
        # Buscar encuesta de satisfacción activa
        encuesta_url = None
        try:
            from django.conf import settings as _settings
            fb = FeedbackCliente.objects.filter(
                orden=orden,
                tipo='satisfaccion',
                correo_enviado=True,
            ).first()
            if fb and fb.es_valido:
                from config.paises_config import get_pais_actual
                site_url = get_pais_actual().get('url_base', getattr(_settings, 'SITE_URL', 'http://localhost:8000'))
                encuesta_url = f"{site_url}/feedback-satisfaccion/{fb.token}/"
        except Exception:
            pass

        context['estado'] = 'entregado'
        context['encuesta_url'] = encuesta_url
        context['encuesta_dias_restantes'] = fb.dias_restantes if fb and fb.es_valido else None
    elif estado_orden == 'finalizado':
        context['estado'] = 'finalizado'
    else:
        context['estado'] = 'tracking'

    # ── Banners promocionales dinámicos ──
    # Obtenemos los banners vigentes agrupados por posición.
    # Si no hay banners activos, el dict estará vacío y el template no renderiza nada.
    try:
        banners = BannerPromocional.obtener_vigentes_por_estado(context['estado'])
    except Exception:
        banners = {}
    context['banners'] = banners

    return render(request, TEMPLATE, context)




@ratelimit(key='ip', rate='30/m', method=['GET'])
def diagnostico_pdf_seguimiento(request, token):
    """
    Sirve el PDF de diagnóstico del cliente de forma pública (protegida por token).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el técnico envía el diagnóstico por correo, guardamos una copia del
    PDF en el enlace de seguimiento. Esta vista permite abrirlo desde:
      - La notificación push (el cliente toca y se abre el PDF)
      - El botón "Ver diagnóstico" en la página de seguimiento

    Args:
        request: HttpRequest del navegador del cliente
        token: Token secreto del EnlaceSeguimientoCliente

    Returns:
        FileResponse con el PDF en modo inline (se abre en el navegador)
        o HttpResponse 404/410 si el enlace o el archivo no están disponibles.
    """
    from django.http import FileResponse, HttpResponse
    from .models import EnlaceSeguimientoCliente
    from servicio_tecnico.eventos_seguimiento import registrar_evento_seguimiento

    try:
        enlace = EnlaceSeguimientoCliente.objects.select_related('orden').get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        return HttpResponse('Enlace no válido.', status=404)

    if not enlace.esta_disponible:
        return HttpResponse('Enlace no disponible.', status=410)

    if not enlace.pdf_diagnostico:
        return HttpResponse('Diagnóstico no disponible.', status=404)

    # Registrar apertura del PDF para métricas del dashboard interno
    origen = request.GET.get('origen', 'directo')
    if origen not in ('pagina', 'push', 'directo'):
        origen = 'directo'

    registrar_evento_seguimiento(
        enlace,
        'diagnostico_pdf_abierto',
        request=request,
        metadata={
            'folio': enlace.folio_diagnostico or '',
            'origen': origen,
        },
    )

    nombre_archivo = enlace.pdf_diagnostico.name.rsplit('/', 1)[-1]
    response = FileResponse(
        enlace.pdf_diagnostico.open('rb'),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = f'inline; filename="{nombre_archivo}"'
    return response


# ============================================================================
# PWA — Manifest dinámico del seguimiento del cliente
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Un manifest.json le dice al navegador cómo debe verse la app cuando el
# cliente la "instala" en su celular (ícono, nombre, color, y sobre todo
# el 'start_url': la página que se abre al tocar el ícono).
#
# El manifest GLOBAL de SIGMA (static/manifest.json) tiene start_url="/",
# que llevaría al cliente a la pantalla de login — no sirve para él.
# Por eso generamos un manifest DIFERENTE para cada token: su start_url y
# su scope apuntan exactamente a su propia página de seguimiento, así el
# ícono que instale en su celular abre directo el estado de SU equipo.
# ============================================================================

@ratelimit(key='ip', rate='30/m', method=['GET'])
def manifest_seguimiento(request, token):
    """
    Genera el manifest.json de la PWA para la página pública de seguimiento.

    EXPLICACIÓN PARA PRINCIPIANTES:
    No valida si el token existe o no — siempre devuelve un manifest válido.
    Esto evita que alguien use esta URL para "adivinar" si un token es
    correcto o no (la validación real de seguridad ocurre en la vista
    'seguimiento_orden_cliente' al abrir la página).

    Parámetros:
        token (str): Token único del EnlaceSeguimientoCliente, tomado de la URL.

    Retorna:
        JsonResponse con el manifest, usando el content-type correcto
        ('application/manifest+json') para que el navegador lo reconozca.
    """
    ruta_seguimiento = f"/seguimiento/{token}/"

    manifest = {
        "name": "Seguimiento de tu equipo — SIC",
        "short_name": "Seguimiento SIC",
        "description": "Consulta rápida y notificaciones del estado de tu equipo en reparación.",
        # start_url + scope acotados a ESTE token: el ícono instalado abre
        # directo el seguimiento de este cliente, nunca el login del sistema.
        "start_url": ruta_seguimiento,
        "scope": ruta_seguimiento,
        "display": "standalone",
        "background_color": "#0a1628",
        "theme_color": "#1f6391",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/static/images/icon-192x192.png", "type": "image/png", "sizes": "192x192", "purpose": "any"},
            {"src": "/static/images/icon-192x192.png", "type": "image/png", "sizes": "192x192", "purpose": "maskable"},
            {"src": "/static/images/icon-512x512.png", "type": "image/png", "sizes": "512x512", "purpose": "any"},
            {"src": "/static/images/icon-512x512.png", "type": "image/png", "sizes": "512x512", "purpose": "maskable"},
        ],
        "categories": ["business"],
        "lang": "es-MX",
        "dir": "ltr",
    }

    # Cabecera anti-caché: obliga al navegador a revalidar el manifest en cada
    # consulta (Chromium en móvil lo cachea de forma agresiva). Así, si el
    # contenido del manifest cambia, el teléfono no usa una copia vieja.
    response = JsonResponse(manifest, content_type="application/manifest+json")
    response['Cache-Control'] = 'no-cache, must-revalidate'
    return response


# ============================================================================
# PUSH — Suscripción de notificaciones del CLIENTE en el seguimiento público
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Estos 3 endpoints son la versión "para clientes" de los que ya existen en
# notificaciones/views.py para empleados. La diferencia clave es la
# identidad: un empleado se identifica con su sesión (request.user), pero
# el cliente NO tiene cuenta — se identifica con el TOKEN de su enlace de
# seguimiento. Por eso son públicos (sin @login_required) pero validan el
# token en cada llamada, igual que el chat de IA (chat_seguimiento_cliente).
# ============================================================================

@csrf_exempt
@ratelimit(key='ip', rate='10/m', method=['GET'])
def vapid_key_seguimiento(request, token):
    """
    Entrega la llave pública VAPID al navegador del cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Es el mismo mecanismo que 'notificaciones.views.vapid_public_key',
    pero sin exigir login. Antes de suscribirse a push, el navegador
    necesita esta llave pública para cifrar los mensajes.
    """
    from .models import EnlaceSeguimientoCliente

    try:
        enlace = EnlaceSeguimientoCliente.objects.get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Enlace no válido.'}, status=404)

    if not enlace.esta_disponible:
        return JsonResponse({'ok': False, 'error': 'Enlace no disponible.'}, status=410)

    return JsonResponse({'vapid_public_key': settings.VAPID_PUBLIC_KEY})




@csrf_exempt
@ratelimit(key='ip', rate='10/m', method=['POST'])
def suscribir_push_seguimiento(request, token):
    """
    Guarda o reactiva la suscripción push de un cliente para su orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El navegador del cliente ya obtuvo permiso y generó una suscripción
    (endpoint + claves de cifrado). Aquí la guardamos en PushSubscriptionCliente,
    ligada al 'enlace' (el token), NO a un usuario Django — el cliente no
    tiene cuenta en el sistema.

    Body esperado (JSON):
        { "endpoint": "https://...", "keys": { "p256dh": "...", "auth": "..." } }
    """
    from .models import EnlaceSeguimientoCliente
    from notificaciones.models import PushSubscriptionCliente

    try:
        enlace = EnlaceSeguimientoCliente.objects.get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Enlace no válido.'}, status=404)

    if not enlace.esta_disponible:
        return JsonResponse({'ok': False, 'error': 'Enlace no disponible.'}, status=410)

    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint', '').strip()
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh', '').strip()
        auth = keys.get('auth', '').strip()

        if not all([endpoint, p256dh, auth]):
            return JsonResponse(
                {'ok': False, 'error': 'Datos de suscripción incompletos'},
                status=400
            )

        user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]

        # update_or_create: si el cliente ya tenía este mismo endpoint
        # registrado (recargó la página, por ejemplo), lo reactivamos
        # en vez de crear un duplicado.
        suscripcion, creada = PushSubscriptionCliente.objects.update_or_create(
            enlace=enlace,
            endpoint=endpoint,
            defaults={
                'p256dh': p256dh,
                'auth': auth,
                'activa': True,
                'fecha_desactivada': None,
                'user_agent': user_agent,
            }
        )

        from servicio_tecnico.eventos_seguimiento import registrar_evento_seguimiento
        registrar_evento_seguimiento(enlace, 'push_activado', request=request)

        logger.info(
            "[PushCliente] Suscripción %s para enlace token=%s... (id=%s)",
            'creada' if creada else 'reactivada', token[:8], suscripcion.pk
        )

        return JsonResponse({'ok': True, 'accion': 'creada' if creada else 'reactivada'})

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    except Exception as exc:
        logger.error(f'[PushCliente] Error al guardar suscripción: {exc}', exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)




@csrf_exempt
@ratelimit(key='ip', rate='10/m', method=['POST'])
def cancelar_push_seguimiento(request, token):
    """
    Desactiva la suscripción push del cliente para su enlace de seguimiento.

    EXPLICACIÓN PARA PRINCIPIANTES:
    No borramos el registro (por si el cliente la reactiva después),
    solo lo marcamos como 'activa=False' para dejar de enviarle notificaciones.

    Body esperado (JSON): { "endpoint": "https://..." } (opcional)
    Si no se envía 'endpoint', desactiva TODAS las suscripciones de ese enlace.
    """
    from .models import EnlaceSeguimientoCliente
    from notificaciones.models import PushSubscriptionCliente

    try:
        enlace = EnlaceSeguimientoCliente.objects.get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Enlace no válido.'}, status=404)

    try:
        data = json.loads(request.body) if request.body else {}
        endpoint = data.get('endpoint', '').strip()

        qs = PushSubscriptionCliente.objects.filter(enlace=enlace, activa=True)
        if endpoint:
            qs = qs.filter(endpoint=endpoint)
        ahora = timezone.now()
        desactivadas = qs.update(activa=False, fecha_desactivada=ahora)

        from servicio_tecnico.eventos_seguimiento import registrar_evento_seguimiento
        if desactivadas:
            registrar_evento_seguimiento(enlace, 'push_desactivado', request=request)

        logger.info(
            "[PushCliente] %s suscripción(es) desactivada(s) para token=%s...",
            desactivadas, token[:8]
        )

        return JsonResponse({'ok': True, 'desactivadas': desactivadas})

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    except Exception as exc:
        logger.error(f'[PushCliente] Error al cancelar suscripción: {exc}', exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)




@csrf_exempt
@ratelimit(key='ip', rate='30/m', method=['POST'])
def registrar_evento_seguimiento_cliente(request, token):
    """
    Endpoint público para que el navegador registre eventos de producto del cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    PWA, chat y permisos push ocurren en el navegador; este endpoint recibe
    esos eventos y los guarda ligados al enlace (token) del cliente.

    Body JSON: { "tipo": "pwa_banner_mostrado", "session_id": "uuid", "metadata": {} }
    """
    from .models import EnlaceSeguimientoCliente
    from servicio_tecnico.eventos_seguimiento import (
        TIPOS_EVENTO_CLIENTE,
        registrar_evento_seguimiento,
    )

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    try:
        enlace = EnlaceSeguimientoCliente.objects.get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Enlace no válido.'}, status=404)

    if not enlace.esta_disponible:
        return JsonResponse({'ok': False, 'error': 'Enlace no disponible.'}, status=410)

    try:
        data = json.loads(request.body)
        tipo = (data.get('tipo') or '').strip()
        session_id = (data.get('session_id') or '')[:36]
        metadata = data.get('metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {}

        if tipo not in TIPOS_EVENTO_CLIENTE:
            return JsonResponse({'ok': False, 'error': 'Tipo de evento no permitido.'}, status=400)

        ok = registrar_evento_seguimiento(
            enlace,
            tipo,
            request=request,
            session_id=session_id,
            metadata=metadata,
        )
        if not ok:
            return JsonResponse({'ok': False, 'error': 'No se pudo registrar el evento.'}, status=400)

        return JsonResponse({'ok': True})

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    except Exception as exc:
        logger.error('[EventosSeg] Error en endpoint público: %s', exc, exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)


# ============================================================================
# VISTA PÚBLICA: feedback_rechazo_view
# Página accesible sin autenticación. El cliente abre el link desde el correo,
# ve la información de su equipo y piezas, y puede escribir su comentario.
# ============================================================================

@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
def feedback_rechazo_view(request, token):
    """
    Vista pública para que el cliente deje su comentario de rechazo.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista NO usa @login_required porque la abre el cliente desde su correo.
    Valida el token antes de mostrar cualquier información.
    Si el token ya fue usado o expiró, muestra un mensaje genérico
    (no revelar si el token existió, expiró o fue usado — prevención de enumeración).
    """
    from django.core.signing import BadSignature, SignatureExpired
    from .models import FeedbackCliente
    from .forms import FeedbackRechazoClienteForm

    # ── Obtener IP para logging de seguridad ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR')

    # ── Buscar el feedback por token ──
    try:
        feedback = FeedbackCliente.objects.select_related(
            'cotizacion__orden__detalle_equipo',
        ).get(token=token)
    except FeedbackCliente.DoesNotExist:
        logger.warning(
            "[SEGURIDAD] Feedback rechazo con token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return render(request, 'servicio_tecnico/feedback_rechazo.html', {
            'estado': 'invalido',
            'mensaje': 'El enlace no es válido o ya no existe.',
        })

    # ── Validar estado del token ──
    # SEGURIDAD: Mensajes diferenciados en el template (ya_respondido, expirado)
    # son aceptables porque el atacante necesitaría un token válido de 256 bits
    # para llegar aquí. La protección real está en DoesNotExist (arriba).
    if feedback.utilizado:
        return render(request, 'servicio_tecnico/feedback_rechazo.html', {
            'estado': 'ya_respondido',
            'mensaje': 'Ya enviaste tu comentario. ¡Gracias por tu tiempo!',
        })

    if feedback.esta_expirado:
        return render(request, 'servicio_tecnico/feedback_rechazo.html', {
            'estado': 'expirado',
            'mensaje': 'Este enlace ha expirado. Los links son válidos por 7 días.',
        })

    orden = feedback.cotizacion.orden
    detalle = orden.detalle_equipo
    piezas = feedback.cotizacion.piezas_cotizadas.filter(aceptada_por_cliente=False)

    # ── Calcular monto total rechazado ──
    monto_piezas = sum(
        (p.costo_unitario or 0) * (p.cantidad or 1) for p in piezas
    )
    monto_mano_obra = feedback.cotizacion.costo_mano_obra or 0

    if request.method == 'POST':
        form = FeedbackRechazoClienteForm(request.POST)
        if form.is_valid():
            # ── Honeypot: Si el campo oculto tiene valor, es un bot ──
            if form.cleaned_data.get('website'):
                logger.warning(
                    "[SEGURIDAD] Honeypot activado en feedback rechazo | IP: %s",
                    _ip
                )
                # Simular éxito para no alertar al bot
                return render(request, 'servicio_tecnico/feedback_rechazo.html', {
                    'estado': 'gracias',
                    'mensaje': '¡Gracias por tu comentario! Tu opinión nos ayuda a mejorar.',
                })

            feedback.comentario_cliente = form.cleaned_data['comentario_cliente']
            feedback.utilizado = True
            feedback.fecha_respuesta = timezone.now()
            # Guardar IP del cliente para trazabilidad
            feedback.ip_respuesta = _ip
            feedback.save(update_fields=[
                'comentario_cliente', 'utilizado', 'fecha_respuesta', 'ip_respuesta'
            ])

            # Registrar en historial de la orden
            try:
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cotizacion',
                    comentario=(
                        f'💬 Cliente dejó comentario de rechazo (feedback)\n'
                        f'   {feedback.comentario_cliente[:200]}'
                    ),
                    usuario=None,
                    es_sistema=True
                )
            except Exception:
                pass

            return render(request, 'servicio_tecnico/feedback_rechazo.html', {
                'estado': 'gracias',
                'mensaje': '¡Gracias por tu comentario! Tu opinión nos ayuda a mejorar.',
            })
    else:
        form = FeedbackRechazoClienteForm()

    context = {
        'estado': 'formulario',
        'form': form,
        'feedback': feedback,
        'orden': orden,
        'detalle': detalle,
        'piezas': piezas,
        'monto_piezas': monto_piezas,
        'monto_mano_obra': monto_mano_obra,
        'monto_total': monto_piezas + monto_mano_obra,
        'motivo_rechazo': feedback.cotizacion.get_motivo_rechazo_display(),
        'dias_restantes': feedback.dias_restantes,
    }
    return render(request, 'servicio_tecnico/feedback_rechazo.html', context)


# ============================================================================
# MISC: viven en views_misc.py (acceso_denegado, actualizar_email_cliente — reexport al inicio).
# ============================================================================

# ============================================================================
# CONCENTRADO SEMANAL: vive en views_concentrado.py (reexport al inicio).
# ============================================================================


# ============================================================================
# VISTA: confirmar_feedback_satisfaccion
# El operador acepta o cancela el envío de la encuesta de satisfacción.
# Se llama vía POST desde el modal en detalle_orden.html.
# ============================================================================

@login_required
@require_http_methods(['POST'])
def confirmar_feedback_satisfaccion(request, feedback_id):
    """
    Recibe la decisión del operador sobre si enviar o no la encuesta de satisfacción.

    Si acepta → encola enviar_feedback_satisfaccion_task.
    Si cancela → no hace nada (el token queda guardado pero sin correo enviado).
    """
    from .models import FeedbackCliente
    from .tasks import enviar_feedback_satisfaccion_task

    feedback = get_object_or_404(FeedbackCliente, pk=feedback_id)
    accion   = request.POST.get('accion', 'cancelar')
    orden_id = feedback.orden.pk

    if accion == 'enviar':
        if feedback.correo_enviado:
            messages.warning(request, '⚠️ La encuesta de satisfacción ya fue enviada anteriormente.')
        else:
            usuario_id = request.user.pk if request.user.is_authenticated else None
            from config.paises_config import get_pais_actual
            enviar_feedback_satisfaccion_task.delay(
                feedback_id=feedback.pk,
                usuario_id=usuario_id,
                db_alias=get_pais_actual()['db_alias'],
            )
            messages.success(
                request,
                f'⭐ Encuesta de satisfacción enviada a '
                f'{feedback.orden.detalle_equipo.email_cliente}. '
                f'El cliente tiene 12 días para responder.'
            )
    else:
        messages.info(request, 'ℹ️ Envío de encuesta de satisfacción cancelado.')

    return redirect('servicio_tecnico:detalle_orden', orden_id=orden_id)


# ============================================================================
# VISTA PÚBLICA: feedback_satisfaccion_cliente
# El cliente llena la encuesta desde el link del correo de entrega.
# NO requiere autenticación.
# ============================================================================

@ratelimit(key='ip', rate='20/m', method=['GET', 'POST'])
def feedback_satisfaccion_cliente(request, token):
    """
    Vista pública para la encuesta de satisfacción post-entrega.
    Valida el token, muestra el formulario interactivo y guarda la respuesta.
    """
    from .models import FeedbackCliente
    from .forms import FeedbackSatisfaccionClienteForm

    TEMPLATE = 'servicio_tecnico/feedback_satisfaccion.html'

    # ── Obtener IP para logging de seguridad ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR')

    # ── Buscar feedback por token y tipo ──────────────────────────────────
    try:
        feedback = FeedbackCliente.objects.select_related(
            'orden__detalle_equipo',
            'orden__sucursal',
        ).get(token=token, tipo='satisfaccion')
    except FeedbackCliente.DoesNotExist:
        logger.warning(
            "[SEGURIDAD] Feedback satisfacción con token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return render(request, TEMPLATE, {'estado': 'invalido'})

    # ── Validar estado del token ──────────────────────────────────────────
    # SEGURIDAD: Mensajes 'ya_respondido' y 'expirado' son seguros aquí porque
    # el atacante necesitaría adivinar un token de 256 bits para llegar a este punto.
    if feedback.utilizado:
        return render(request, TEMPLATE, {'estado': 'ya_respondido'})

    if feedback.esta_expirado:
        return render(request, TEMPLATE, {'estado': 'expirado'})

    orden   = feedback.orden
    detalle = orden.detalle_equipo

    if request.method == 'POST':
        form = FeedbackSatisfaccionClienteForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data

            # ── Honeypot: Si el campo oculto tiene valor, es un bot ──
            if d.get('website'):
                logger.warning(
                    "[SEGURIDAD] Honeypot activado en feedback satisfacción | IP: %s",
                    _ip
                )
                # Simular éxito para no alertar al bot
                return render(request, TEMPLATE, {
                    'estado': 'gracias',
                    'calificacion': 5,
                    'sucursal_nombre': orden.sucursal.nombre,
                })

            feedback.calificacion_general  = d['calificacion_general']
            feedback.nps                   = d['nps']
            feedback.recomienda            = d['recomienda']
            feedback.calificacion_atencion = d.get('calificacion_atencion')
            feedback.calificacion_tiempo   = d.get('calificacion_tiempo')
            feedback.comentario_cliente    = d.get('comentario_cliente', '')
            feedback.utilizado             = True
            feedback.fecha_respuesta       = timezone.now()
            feedback.ip_respuesta          = _ip
            feedback.save(update_fields=[
                'calificacion_general', 'nps', 'recomienda',
                'calificacion_atencion', 'calificacion_tiempo',
                'comentario_cliente', 'utilizado', 'fecha_respuesta', 'ip_respuesta',
            ])

            # Notificar a responsable de seguimiento y superusers
            try:
                from notificaciones.utils import notificar_info
                responsable = orden.responsable_seguimiento
                if responsable and responsable.usuario:
                    notificar_info(
                        titulo="Encuesta de satisfacción respondida",
                        mensaje=(
                            f"Orden {orden.numero_orden_interno} — "
                            f"Calificación: {d['calificacion_general']}/5 | "
                            f"NPS: {d['nps']}/10 | "
                            f"Recomienda: {'Sí' if d['recomienda'] else 'No'}"
                        ),
                        usuario=responsable.usuario,
                        app_origen='servicio_tecnico',
                    )
            except Exception:
                pass

            # Registrar en historial de la orden
            try:
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='cotizacion',
                    comentario=(
                        f'⭐ Cliente completó encuesta de satisfacción\n'
                        f'   Calificación: {d["calificacion_general"]}/5 | '
                        f'NPS: {d["nps"]}/10 | '
                        f'Recomienda: {"Sí" if d["recomienda"] else "No"}'
                    ),
                    usuario=None,
                    es_sistema=True,
                )
            except Exception:
                pass

            return render(request, TEMPLATE, {
                'estado': 'gracias',
                'calificacion': d['calificacion_general'],
                'sucursal_nombre': orden.sucursal.nombre,
            })
    else:
        form = FeedbackSatisfaccionClienteForm()

    return render(request, TEMPLATE, {
        'estado': 'formulario',
        'form': form,
        'feedback': feedback,
        'orden': orden,
        'detalle': detalle,
        'dias_restantes': feedback.dias_restantes,
    })


# ============================================================================
# PERFIL / DIRECTORIO: viven en views_perfil.py (reexport al inicio).
# ============================================================================


# ============================================================================
# IA DIAGNÓSTICO (pulir): vive en views_ia_diagnostico.py (reexport al inicio).
# ============================================================================
# VISTA AJAX PÚBLICA: chat_seguimiento_cliente
# Endpoint del chatbot de IA para la vista de seguimiento del cliente.
#
# Esta vista es PÚBLICA (no requiere @login_required) porque la abre el cliente
# desde su enlace de seguimiento por token. La seguridad se basa en:
#   1. Validación del token (mismo mecanismo que seguimiento_orden_cliente)
#   2. Rate limiting estricto por IP (10 req/minuto — conversaciones más largas)
#   3. El contexto del prompt se construye EXCLUSIVAMENTE con los datos de esa orden
#   4. El prompt prohíbe explícitamente revelar datos de otras órdenes
#
# Endpoint: POST /seguimiento/<token>/chat/
# Formato POST:
#   - pregunta (str): Pregunta del cliente (máx 500 caracteres)
#   - historial (str, JSON): Array de {role, content} con los últimos turnos
#
# Respuesta JSON exitosa:
#   {success: true, respuesta: "...", modelo_usado: "..."}
# Respuesta de error:
#   {success: false, error: "...mensaje amigable..."}
# ============================================================================

@csrf_exempt
@ratelimit(key='ip', rate='10/m', method=['POST'])
def chat_seguimiento_cliente(request, token):
    """
    API AJAX del chatbot de IA en la vista pública de seguimiento del cliente.

    Construye el contexto completo de la orden y lo inyecta en el prompt
    del sistema para que la IA pueda responder preguntas del cliente de forma
    precisa y segura, sin revelar datos de otras órdenes ni información interna.

    SEGURIDAD:
    - Valida el token antes de procesar cualquier pregunta
    - Rate limit: 10 peticiones/minuto por IP (protección contra abuso)
    - El contexto del prompt está acotado a los datos de esta orden específica
    - Prompt con instrucciones explícitas anti-prompt-injection
    """
    import json as _json
    import time as _time
    from .models import EnlaceSeguimientoCliente
    from .ollama_client import (
        construir_prompt_seguimiento,
        chat_seguimiento_dispatch,
        formatear_contexto_sucursales_chat,
    )
    from .chat_seguimiento_helpers import construir_timeline_seguimiento_cliente

    # ── Verificar que al menos un proveedor de IA está habilitado ──
    if not getattr(settings, 'AI_ENABLED', False):
        return JsonResponse({
            'success': False,
            'error': 'El asistente no está habilitado en este entorno.'
        }, status=503)

    # ── Solo aceptar POST ──
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    # ── Obtener IP del cliente para logging ──
    _xfwd = request.META.get('HTTP_X_FORWARDED_FOR')
    _ip = _xfwd.split(',')[0].strip() if _xfwd else request.META.get('REMOTE_ADDR', '?')

    # ── Validar el token (mismo mecanismo que la vista padre) ──
    try:
        enlace = EnlaceSeguimientoCliente.objects.select_related(
            'orden__detalle_equipo',
            'orden__sucursal',
            'orden__responsable_seguimiento',
        ).get(token=token)
    except EnlaceSeguimientoCliente.DoesNotExist:
        logger.warning(
            "[ChatSeg][SEGURIDAD] Token inexistente | IP: %s | token: %s...",
            _ip, token[:8]
        )
        return JsonResponse({'success': False, 'error': 'Enlace de seguimiento no válido.'}, status=404)

    if not enlace.esta_disponible:
        return JsonResponse({
            'success': False,
            'error': 'Este enlace de seguimiento ha expirado.'
        }, status=410)

    # ── Extraer y validar la pregunta del cliente ──
    pregunta = request.POST.get('pregunta', '').strip()
    if not pregunta:
        return JsonResponse({'success': False, 'error': 'La pregunta no puede estar vacía.'}, status=400)

    if len(pregunta) > 500:
        return JsonResponse({
            'success': False,
            'error': 'La pregunta es demasiado larga. Por favor, sé más específico (máx. 500 caracteres).'
        }, status=400)

    # ── Parsear el historial de conversación del cliente (enviado como JSON) ──
    historial_raw = request.POST.get('historial', '[]')
    try:
        historial_mensajes: list[dict] = _json.loads(historial_raw)
        # Validar estructura básica: debe ser lista de dicts con 'role' y 'content'
        if not isinstance(historial_mensajes, list):
            historial_mensajes = []
        else:
            historial_mensajes = [
                msg for msg in historial_mensajes
                if isinstance(msg, dict)
                and msg.get('role') in ('user', 'assistant')
                and isinstance(msg.get('content'), str)
                and len(msg.get('content', '')) <= 2000  # Límite de seguridad por mensaje
            ]
    except (_json.JSONDecodeError, ValueError):
        historial_mensajes = []

    # ── Construir el contexto de la orden para el prompt ──
    orden = enlace.orden
    detalle = orden.detalle_equipo

    # ── Timeline y estado actual (misma lógica que la página pública de seguimiento) ──
    historial_estados_qs = HistorialOrden.objects.filter(
        orden=orden,
        tipo_evento='cambio_estado',
    ).order_by('fecha_evento').values('estado_nuevo', 'fecha_evento')

    timeline_ctx = construir_timeline_seguimiento_cliente(
        historial_estados_qs,
        orden.estado or '',
    )
    estado_actual_texto = timeline_ctx['estado_actual_texto']
    timeline_texto = timeline_ctx['timeline_texto']
    siguiente_paso_texto = timeline_ctx['siguiente_paso_texto']
    aclaraciones_cotizacion_texto = timeline_ctx['aclaraciones_cotizacion_texto']

    # Nombre del responsable de seguimiento
    nombre_responsable = ""
    if orden.responsable_seguimiento:
        nombre_responsable = orden.responsable_seguimiento.nombre_completo

    # ── Estado de piezas en tránsito (SeguimientoPieza) ──
    piezas_texto = ""
    from .models import SeguimientoPieza
    seguimientos_piezas_qs = SeguimientoPieza.objects.filter(
        cotizacion__orden=orden
    ).order_by('fecha_pedido')
    if seguimientos_piezas_qs.exists():
        piezas_lineas = []
        ESTADOS_PIEZA_CHAT = {
            'pedido':      'Pedido realizado',
            'confirmado':  'Confirmado por proveedor',
            'transito':    'En tránsito',
            'retrasado':   'Retrasado',
            'recibido':    'Recibido en taller',
            'incorrecto':  'Pieza incorrecta (en gestión)',
            'danado':      'Pieza dañada (en gestión)',
            # aliases legacy
            'pendiente':   'Pedido en camino',
            'wpb':         'Pieza incorrecta (en gestión)',
            'doa':         'Pieza dañada (en gestión)',
            'pnc':         'Pieza no disponible',
        }
        for seg in seguimientos_piezas_qs:
            estado_seg = ESTADOS_PIEZA_CHAT.get(
                getattr(seg, 'estado', ''), getattr(seg, 'estado', 'Desconocido')
            )
            desc_seg = getattr(seg, 'descripcion_piezas', '') or ''
            # Intentar obtener nombres de las piezas vinculadas al seguimiento
            piezas_vinculadas = seg.piezas.all()
            if piezas_vinculadas.exists():
                nombres = ', '.join(
                    p.componente.nombre for p in piezas_vinculadas if p.componente_id
                )
                etiqueta = nombres or desc_seg or 'Piezas'
            else:
                etiqueta = desc_seg or 'Piezas'
            # Agregar fechas estimada / real si están disponibles
            fecha_est = seg.fecha_entrega_estimada.strftime('%d/%m/%Y') if seg.fecha_entrega_estimada else None
            fecha_real = seg.fecha_entrega_real.strftime('%d/%m/%Y') if seg.fecha_entrega_real else None
            detalle_fecha = ""
            if fecha_real:
                detalle_fecha = f" — Llegó el {fecha_real}"
            elif fecha_est:
                detalle_fecha = f" — Estimado: {fecha_est}"
                if seg.esta_retrasado:
                    detalle_fecha += f" (retrasado {seg.dias_retraso} días)"
            piezas_lineas.append(f"  • {etiqueta}: {estado_seg}{detalle_fecha}")
        piezas_texto = "\n".join(piezas_lineas)

    # ── Cotización y piezas cotizadas (PiezaCotizada) ──
    # Se incluye: nombre, cantidad, si es necesaria, estado de aceptación.
    # Se EXCLUYE explícitamente: costos, proveedores, motivos de rechazo.
    cotizacion_texto = ""
    from .models import Cotizacion, PiezaCotizada
    try:
        cotizacion_obj = Cotizacion.objects.get(orden=orden)
        # Estado global de la cotización
        if cotizacion_obj.usuario_acepto is True:
            estado_cot = "Aceptada por el cliente"
        elif cotizacion_obj.usuario_acepto is False:
            estado_cot = "Rechazada por el cliente"
        else:
            estado_cot = "En espera de respuesta del cliente"

        fecha_envio_cot = (
            cotizacion_obj.fecha_envio.strftime('%d/%m/%Y')
            if cotizacion_obj.fecha_envio else 'No registrada'
        )
        fecha_resp_cot = (
            cotizacion_obj.fecha_respuesta.strftime('%d/%m/%Y')
            if cotizacion_obj.fecha_respuesta else 'Sin respuesta aún'
        )

        lineas_cot = [
            f"  Estado: {estado_cot}",
            f"  Enviada: {fecha_envio_cot}  |  Respuesta: {fecha_resp_cot}",
            f"  Piezas cotizadas:",
        ]

        piezas_cotizadas_qs = PiezaCotizada.objects.filter(
            cotizacion=cotizacion_obj
        ).select_related('componente').order_by('orden_prioridad', 'fecha_creacion')

        for pc in piezas_cotizadas_qs:
            nombre_pc = pc.componente.nombre if pc.componente_id else 'Pieza sin nombre'
            if pc.descripcion_adicional:
                nombre_pc = f"{nombre_pc} ({pc.descripcion_adicional[:60]})"

            tipo_pc = "Necesaria" if pc.es_necesaria else "Mejora opcional"

            if pc.aceptada_por_cliente is True:
                estado_pc = "Aceptada ✓"
            elif pc.aceptada_por_cliente is False:
                estado_pc = "Rechazada"
            else:
                estado_pc = "Pendiente de decisión"

            origen_pc = "sugerida por el técnico" if pc.sugerida_por_tecnico else "solicitada externamente"

            lineas_cot.append(
                f"    - {nombre_pc} × {pc.cantidad}  [{tipo_pc}]  [{estado_pc}]  ({origen_pc})"
            )

        if not piezas_cotizadas_qs.exists():
            lineas_cot.append("    (Sin piezas registradas en la cotización)")

        cotizacion_texto = "\n".join(lineas_cot)

    except Cotizacion.DoesNotExist:
        # La orden aún no tiene cotización — no se agrega nada
        pass

    # ── Venta mostrador: servicios y productos adicionales ──
    # Se incluye: paquete, servicios contratados (bools), piezas vendidas.
    # Se EXCLUYE explícitamente: costos, precios, totales.
    venta_mostrador_texto = ""
    from .models import VentaMostrador
    try:
        vm = VentaMostrador.objects.get(orden=orden)
        lineas_vm = []

        # Paquete contratado (si aplica)
        if vm.paquete and vm.paquete != 'ninguno':
            lineas_vm.append(f"  Paquete contratado: {vm.get_paquete_display()}")

        # Servicios individuales contratados
        servicios_activos = []
        if vm.incluye_limpieza:
            servicios_activos.append("Limpieza y mantenimiento")
        if vm.incluye_reinstalacion_so:
            servicios_activos.append("Reinstalación de sistema operativo")
        if vm.incluye_respaldo:
            servicios_activos.append("Respaldo de información")
        if vm.incluye_kit_limpieza:
            servicios_activos.append("Kit de limpieza")
        if vm.incluye_cambio_pieza:
            servicios_activos.append("Cambio de pieza (directo, sin diagnóstico)")

        if servicios_activos:
            lineas_vm.append("  Servicios incluidos:")
            for svc in servicios_activos:
                lineas_vm.append(f"    • {svc}")

        # Piezas/productos vendidos directamente (sin precios)
        piezas_vm_qs = vm.piezas_vendidas.select_related('componente').all()
        if piezas_vm_qs.exists():
            lineas_vm.append("  Piezas/productos adquiridos directamente:")
            for pvm in piezas_vm_qs:
                nombre_pvm = (
                    pvm.componente.nombre if pvm.componente_id
                    else pvm.descripcion_pieza or 'Producto sin nombre'
                )
                lineas_vm.append(f"    • {nombre_pvm} × {pvm.cantidad}")

        # Notas adicionales (si hay, truncadas)
        if vm.notas_adicionales and vm.notas_adicionales.strip():
            notas_trunc = vm.notas_adicionales.strip()[:120]
            lineas_vm.append(f"  Notas: {notas_trunc}")

        if lineas_vm:
            venta_mostrador_texto = "\n".join(lineas_vm)

    except VentaMostrador.DoesNotExist:
        # La orden no tiene venta mostrador — no se agrega nada
        pass

    # Folio de la orden (público: orden_cliente del detalle, o número interno como fallback)
    folio = (detalle.orden_cliente if detalle and detalle.orden_cliente else None) \
            or orden.numero_orden_interno or str(orden.pk)

    # ── Sucursal de la orden + catálogo de sucursales activas ──
    sucursal_texto, sucursales_catalogo_texto = formatear_contexto_sucursales_chat(
        orden.sucursal
    )

    # ── Construir los mensajes para el modelo ──
    mensajes = construir_prompt_seguimiento(
        pregunta=pregunta,
        folio=folio,
        tipo_equipo=getattr(detalle, 'tipo_equipo', '') or '',
        marca=getattr(detalle, 'marca', '') or '',
        modelo_equipo=getattr(detalle, 'modelo', '') or '',
        numero_serie=getattr(detalle, 'numero_serie', '') or '',
        falla_principal=getattr(detalle, 'falla_principal', '') or '',
        diagnostico_sic=getattr(detalle, 'diagnostico_sic', '') or '',
        estado_actual=estado_actual_texto,
        timeline_texto=timeline_texto,
        siguiente_paso_texto=siguiente_paso_texto,
        aclaraciones_cotizacion_texto=aclaraciones_cotizacion_texto,
        nombre_responsable=nombre_responsable,
        piezas_texto=piezas_texto,
        historial_mensajes=historial_mensajes,
        cotizacion_texto=cotizacion_texto,
        venta_mostrador_texto=venta_mostrador_texto,
        sucursal_texto=sucursal_texto,
        sucursales_catalogo_texto=sucursales_catalogo_texto,
        dias_restantes=enlace.dias_restantes,
        tiene_pdf_diagnostico=bool(enlace.pdf_diagnostico),
    )

    logger.info(
        "[ChatSeg] Pregunta del cliente | Folio: %s | IP: %s | Turns: %d | Sucursal: %s | Catálogo: %d chars | Pregunta: %.80s...",
        folio, _ip, len(historial_mensajes) // 2,
        (orden.sucursal.nombre if orden.sucursal_id else 'N/A'),
        len(sucursales_catalogo_texto),
        pregunta,
    )

    # ── Llamar al dispatcher (Ollama o Gemini según el modelo configurado) ──
    _t_inicio = _time.monotonic()
    resultado = chat_seguimiento_dispatch(mensajes=mensajes)
    tiempo_ms = int((_time.monotonic() - _t_inicio) * 1000)

    if resultado['success']:
        from servicio_tecnico.eventos_seguimiento import registrar_evento_seguimiento
        via_chip = request.POST.get('via_chip', '').lower() in ('1', 'true', 'yes')
        registrar_evento_seguimiento(
            enlace,
            'chat_mensaje_enviado',
            request=request,
            metadata={'longitud': len(pregunta), 'via_chip': via_chip},
        )
        logger.info(
            "[ChatSeg] Respuesta generada | Folio: %s | Modelo: %s | Tiempo: %dms",
            folio, resultado.get('modelo_usado', '?'), tiempo_ms
        )
        return JsonResponse({
            'success': True,
            'respuesta': resultado['respuesta'],
            'modelo_usado': resultado.get('modelo_usado', ''),
        })
    else:
        logger.warning(
            "[ChatSeg] Error al generar respuesta | Folio: %s | Error: %s",
            folio, resultado.get('error', '?')
        )
        return JsonResponse({
            'success': False,
            'error': resultado.get('error', 'Error desconocido del asistente.')
        })

