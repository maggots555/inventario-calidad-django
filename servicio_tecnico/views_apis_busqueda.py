"""
APIs HTTP de búsqueda / autocompletado para Servicio Técnico (Fase 1 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
Estas vistas vivían en views.py (~L13836–14286). Las movimos aquí porque son
endpoints JSON independientes: no tocan detalle_orden ni dashboards Plotly.

urls.py sigue usando views.api_buscar_* porque views.py reexporta estos nombres.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import DetalleEquipo, OrdenServicio


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def api_buscar_ordenes_autocomplete(request):
    """
    API endpoint para autocompletado typeahead de órdenes de servicio.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Recibe lo que el usuario escribe y devuelve hasta 10 coincidencias en JSON.
    Se usa en lista de órdenes ST, cotizaciones y el formulario de Nueva solicitud
    del almacén (con filtro de prefijo OOW/FL según tipo de solicitud).

    Parámetros GET:
        q (str): Texto de búsqueda (mínimo 2 caracteres)
        tipo (str): 'activas' (default) o 'finalizadas'
        prefijo (str, opcional): 'OOW' o 'FL' — filtra orden_cliente por prefijo

    Returns:
        JsonResponse: { "resultados": [ { id, orden_cliente, numero_serie, ..., piezas_sugeridas } ] }

        piezas_sugeridas: lista de { componente_db, dpn, es_necesaria } guardada al
        enviar el diagnóstico (ayuda para Almacén; no crea cotización en ST).
    """
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', 'activas').strip()
    prefijo = request.GET.get('prefijo', '').strip().upper()

    # Requerir mínimo 2 caracteres para buscar
    if len(query) < 2:
        return JsonResponse({'resultados': []})

    # Construir queryset base según el tipo de vista
    if tipo == 'finalizadas':
        ordenes = OrdenServicio.objects.filter(
            estado__in=['entregado', 'cancelado']
        )
    else:
        ordenes = OrdenServicio.objects.exclude(
            estado__in=['entregado', 'cancelado']
        )

    # Filtro opcional por prefijo de orden del cliente (OOW- diagnóstico, FL- venta mostrador)
    if prefijo == 'OOW':
        ordenes = ordenes.filter(detalle_equipo__orden_cliente__istartswith='OOW-')
    elif prefijo == 'FL':
        ordenes = ordenes.filter(detalle_equipo__orden_cliente__istartswith='FL-')

    # Aplicar filtro de búsqueda en los 3 campos relevantes
    ordenes = ordenes.filter(
        Q(detalle_equipo__orden_cliente__icontains=query) |
        Q(detalle_equipo__numero_serie__icontains=query) |
        Q(numero_orden_interno__icontains=query)
    ).select_related(
        'detalle_equipo', 'sucursal'
    ).order_by('-fecha_ingreso')[:10]

    # Construir respuesta JSON con la información relevante
    resultados = []
    for orden in ordenes:
        detalle = orden.detalle_equipo
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # piezas_sugeridas_diagnostico es un JSON guardado al enviar el diagnóstico.
        # Solo se muestran en Almacén como ayuda; no crean líneas de cotización solas.
        sugerencias_raw = detalle.piezas_sugeridas_diagnostico or []
        piezas_sugeridas = []
        if isinstance(sugerencias_raw, list):
            for item in sugerencias_raw:
                if not isinstance(item, dict):
                    continue
                componente = (item.get('componente_db') or '').strip()
                if not componente:
                    continue
                piezas_sugeridas.append({
                    'componente_db': componente,
                    'dpn': (item.get('dpn') or '').strip(),
                    'es_necesaria': bool(item.get('es_necesaria', True)),
                })

        resultados.append({
            'id': orden.id,
            'orden_cliente': detalle.orden_cliente or '',
            'numero_serie': detalle.numero_serie or '',
            'numero_orden_interno': orden.numero_orden_interno or '',
            'marca': detalle.marca or '',
            'modelo': detalle.modelo or '',
            'tipo_equipo': detalle.tipo_equipo or '',
            'sucursal_id': orden.sucursal.id if orden.sucursal else 0,
            'estado': orden.get_estado_display(),
            'url_detalle': reverse('servicio_tecnico:detalle_orden', args=[orden.id]),
            'piezas_sugeridas': piezas_sugeridas,
        })

    return JsonResponse({'resultados': resultados})


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def api_buscar_ordenes_reingreso(request):
    """
    API endpoint para el selector inteligente de "Orden Original" en el módulo
    de Reingreso de la vista detalle_orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario marca una orden como "Reingreso", necesita indicar cuál fue
    la orden original (la primera vez que se reparó ese equipo). Esta API permite
    buscar esa orden original de forma inteligente, mostrando sugerencias mientras
    el usuario escribe la orden del cliente, el número de serie, etc.

    Solo busca en órdenes con estado='entregado' porque:
    - Un reingreso implica que el equipo YA fue reparado y devuelto al cliente
    - Si el equipo sigue en servicio activo, no puede ser una "orden original" de un reingreso

    Parámetros GET:
        q (str): Texto de búsqueda (mínimo 2 caracteres) — para búsqueda typeahead
        id (int): ID exacto de una orden — para restaurar la selección guardada
        excluir (int): ID de la orden actual (para no mostrarse a sí misma)

    Returns:
        JsonResponse con lista de coincidencias (máximo 15)
        Cada resultado incluye: id, orden_cliente, numero_serie, numero_orden_interno,
        marca, modelo, fecha_entrega (para identificar cuándo fue entregada)
    """
    query = request.GET.get('q', '').strip()
    buscar_por_id = request.GET.get('id', '').strip()
    excluir_id = request.GET.get('excluir', '').strip()

    # ── MODO RESTAURACIÓN: búsqueda por ID exacto ──────────────────────────────
    # Cuando el usuario ya guardó la selección, al recargar la página llamamos
    # a este API con ?id=<pk> para recuperar los datos del chip sin necesidad de
    # hacer una búsqueda de texto (que fallaría con un número como "47").
    if buscar_por_id and buscar_por_id.isdigit():
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(
                pk=int(buscar_por_id)
            )
            detalle = orden.detalle_equipo
            resultado = {
                'id': orden.id,
                'orden_cliente': detalle.orden_cliente or '',
                'numero_serie': detalle.numero_serie or '',
                'numero_orden_interno': orden.numero_orden_interno or '',
                'marca': detalle.marca or '',
                'modelo': detalle.modelo or '',
                'fecha_entrega': orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else '',
            }
            return JsonResponse({'resultados': [resultado]})
        except OrdenServicio.DoesNotExist:
            return JsonResponse({'resultados': []})

    # ── MODO BÚSQUEDA: typeahead por texto ────────────────────────────────────
    # Requerir mínimo 2 caracteres para buscar
    if len(query) < 2:
        return JsonResponse({'resultados': []})

    # Base: solo órdenes entregadas (la única fuente válida para "orden original")
    ordenes = OrdenServicio.objects.filter(estado='entregado')

    # Excluir la orden actual para evitar auto-referencia
    if excluir_id and excluir_id.isdigit():
        ordenes = ordenes.exclude(pk=int(excluir_id))

    # Filtro de búsqueda en los campos más relevantes para identificar una orden
    ordenes = ordenes.filter(
        Q(detalle_equipo__orden_cliente__icontains=query) |
        Q(detalle_equipo__numero_serie__icontains=query) |
        Q(numero_orden_interno__icontains=query) |
        Q(detalle_equipo__marca__icontains=query) |
        Q(detalle_equipo__modelo__icontains=query)
    ).select_related(
        'detalle_equipo', 'sucursal'
    ).order_by('-fecha_entrega')[:15]

    # Construir respuesta JSON con información suficiente para identificar el equipo
    resultados = []
    for orden in ordenes:
        detalle = orden.detalle_equipo
        resultados.append({
            'id': orden.id,
            'orden_cliente': detalle.orden_cliente or '',
            'numero_serie': detalle.numero_serie or '',
            'numero_orden_interno': orden.numero_orden_interno or '',
            'marca': detalle.marca or '',
            'modelo': detalle.modelo or '',
            'fecha_entrega': orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else '',
        })

    return JsonResponse({'resultados': resultados})


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
@require_http_methods(["GET"])
def api_buscar_orden_por_serie(request):
    """
    API para buscar órdenes de servicio por número de serie o orden del cliente.

    Este endpoint busca órdenes de servicio de manera inteligente:

    USO:
    /servicio-tecnico/api/buscar-orden-por-serie/?numero_serie=ABC123
    /servicio-tecnico/api/buscar-orden-por-serie/?orden_cliente=OOW-12345
    """
    # Obtener parámetros de búsqueda
    numero_serie = request.GET.get('numero_serie', '').strip().upper()
    orden_cliente = request.GET.get('orden_cliente', '').strip().upper()

    # Validar que al menos uno de los parámetros venga
    if not numero_serie and not orden_cliente:
        return JsonResponse({
            'success': False,
            'error': 'Debe proporcionar al menos número de serie o orden del cliente'
        })

    # ========================================================================
    # LÓGICA DE BÚSQUEDA INTELIGENTE
    # ========================================================================

    # Lista de palabras que indican que el número de serie no es válido
    SERIES_INVALIDAS = [
        'NO VISIBLE',
        'NO IDENTIFICADO',
        'NO LEGIBLE',
        'SIN SERIE',
        'N/A',
        'NA',
        'NO APLICA',
        'DESCONOCIDO',
        'NO SE VE',
    ]

    # Determinar si el número de serie es inválido
    serie_invalida = any(keyword in numero_serie for keyword in SERIES_INVALIDAS) if numero_serie else True

    try:
        # CASO 1: Si la serie es inválida o no existe, buscar por orden_cliente
        if serie_invalida and orden_cliente:
            detalle = DetalleEquipo.objects.select_related('orden').get(
                orden_cliente__iexact=orden_cliente
            )

        # CASO 2: Si hay orden_cliente explícita, buscar por ella (prioridad)
        elif orden_cliente and not numero_serie:
            detalle = DetalleEquipo.objects.select_related('orden').get(
                orden_cliente__iexact=orden_cliente
            )

        # CASO 3: Buscar por número de serie normal
        elif numero_serie and not serie_invalida:
            detalle = DetalleEquipo.objects.select_related('orden').get(
                numero_serie__iexact=numero_serie
            )

        # CASO 4: Última opción - buscar por cualquiera de los dos
        else:
            detalle = DetalleEquipo.objects.select_related('orden').filter(
                Q(numero_serie__iexact=numero_serie) | Q(orden_cliente__iexact=orden_cliente)
            ).first()

            if not detalle:
                raise DetalleEquipo.DoesNotExist

        # Si encontramos el detalle, extraer información de la orden
        orden = detalle.orden

        # Preparar respuesta con todos los datos relevantes
        return JsonResponse({
            'success': True,
            'encontrado': True,
            'orden': {
                # Identificadores
                'id': orden.id,
                'numero_orden_interno': orden.numero_orden_interno,
                'orden_cliente': detalle.orden_cliente,

                # Información del equipo
                'tipo_equipo': detalle.tipo_equipo,
                'tipo_equipo_display': detalle.get_tipo_equipo_display(),
                'marca': detalle.marca,
                'modelo': detalle.modelo,
                'numero_serie': detalle.numero_serie,
                'gama': detalle.gama,
                'gama_display': detalle.get_gama_display(),

                # Información de la orden
                'fecha_ingreso': orden.fecha_ingreso.strftime('%d/%m/%Y %H:%M'),
                'fecha_ingreso_corta': orden.fecha_ingreso.strftime('%d/%m/%Y'),
                'estado': orden.estado,
                'estado_display': orden.get_estado_display(),
                'dias_en_servicio': orden.dias_en_servicio,

                # Responsables
                'tecnico_responsable': orden.tecnico_asignado_actual.nombre_completo,
                'tecnico_id': orden.tecnico_asignado_actual.id,
                'responsable_seguimiento': orden.responsable_seguimiento.nombre_completo if orden.responsable_seguimiento else 'Sin asignar',
                'responsable_id': orden.responsable_seguimiento.id if orden.responsable_seguimiento else 0,

                # Ubicación
                'sucursal': orden.sucursal.nombre,
                'sucursal_id': orden.sucursal.id,

                # Información adicional
                'falla_principal': detalle.falla_principal,
                'equipo_enciende': detalle.equipo_enciende,
                'es_mis': detalle.es_mis,
                'es_reingreso': orden.es_reingreso,
                'es_candidato_rhitso': orden.es_candidato_rhitso,
            },
            'mensaje': f'Orden {orden.numero_orden_interno} encontrada exitosamente'
        })

    except DetalleEquipo.DoesNotExist:
        # No se encontró ninguna orden con los criterios proporcionados
        criterio_busqueda = f"número de serie '{numero_serie}'" if numero_serie and not serie_invalida else f"orden del cliente '{orden_cliente}'"

        return JsonResponse({
            'success': True,
            'encontrado': False,
            'orden': None,
            'mensaje': f'No se encontró ninguna orden con {criterio_busqueda} en el sistema'
        })

    except DetalleEquipo.MultipleObjectsReturned:
        # Se encontraron múltiples órdenes (no debería pasar, pero por si acaso)
        return JsonResponse({
            'success': False,
            'encontrado': False,
            'orden': None,
            'error': f'Se encontraron múltiples órdenes con los criterios proporcionados. Por favor, sea más específico.'
        })

    except Exception as e:
        # Error inesperado
        return JsonResponse({
            'success': False,
            'encontrado': False,
            'orden': None,
            'error': f'Error al buscar la orden: {str(e)}'
        })


@login_required
@permission_required_with_message('servicio_tecnico.view_referenciagamaequipo')
@require_http_methods(["GET"])
def api_buscar_modelos_por_marca(request):
    """
    API endpoint para buscar modelos de equipos disponibles según la marca.

    Este endpoint se usa para el autocompletado del campo "Modelo" en los
    formularios de creación de órdenes. Busca en la tabla ReferenciaGamaEquipo
    y retorna los modelos disponibles para la marca seleccionada.

    PARÁMETROS GET:
    - marca: str (requerido) - Marca del equipo (DELL, LENOVO, HP, etc.)
    - q: str (opcional) - Término de búsqueda para filtrar modelos (Select2 usa 'q')

    RETORNA:
    JSON con formato compatible con Select2:
    {
        'results': [
            {'id': 'Inspiron 3000', 'text': 'Inspiron 3000 - Gama Baja', 'gama': 'baja'},
            {'id': 'XPS 13', 'text': 'XPS 13 - Gama Alta', 'gama': 'alta'},
            ...
        ]
    }

    EJEMPLO DE USO:
    /servicio-tecnico/api/buscar-modelos-por-marca/?marca=DELL&q=inspiron

    EXPLICACIÓN PARA PRINCIPIANTES:
    - Esta función se ejecuta cuando el usuario escribe en el campo "Modelo"
    - Busca en la base de datos los modelos que coincidan con la marca seleccionada
    - Retorna un JSON que Select2 puede entender y mostrar como opciones
    - Si el usuario escribe algo (parámetro 'q'), filtra los resultados
    """
    from .models import ReferenciaGamaEquipo

    # Obtener parámetros de la URL
    marca = request.GET.get('marca', '').strip()
    query = request.GET.get('q', '').strip()  # Select2 usa 'q' por defecto para el término de búsqueda

    # Validar que la marca esté presente
    if not marca:
        return JsonResponse({
            'results': [],
            'mensaje': 'Debe seleccionar una marca primero'
        })

    try:
        # ====================================================================
        # BÚSQUEDA EN LA BASE DE DATOS
        # ====================================================================

        # Buscar referencias de gama para la marca seleccionada
        # iexact = case-insensitive exact match (DELL = dell = DeLl)
        referencias = ReferenciaGamaEquipo.objects.filter(
            marca__iexact=marca,
            activo=True
        )

        # Si hay término de búsqueda, filtrar por modelo_base
        # icontains = case-insensitive contains (busca coincidencias parciales)
        if query:
            referencias = referencias.filter(
                modelo_base__icontains=query
            )

        # Ordenar alfabéticamente por modelo
        referencias = referencias.order_by('modelo_base')

        # ====================================================================
        # FORMATEAR RESULTADOS PARA SELECT2
        # ====================================================================

        # Select2 espera un formato específico:
        # - 'id': El valor que se guardará en el formulario
        # - 'text': El texto que se mostrará al usuario
        resultados = []

        for ref in referencias:
            resultados.append({
                'id': ref.modelo_base,  # Valor que se guardará
                'text': ref.modelo_base,  # Solo el nombre del modelo (sin gama)
                'gama': ref.gama,  # Información adicional (opcional, no se muestra)
                'rango_costo': f"${ref.rango_costo_min} - ${ref.rango_costo_max}"  # Info adicional
            })

        # Retornar JSON en formato Select2
        return JsonResponse({
            'results': resultados,
            'total': len(resultados)
        })

    except Exception as e:
        # Si hay algún error, retornar respuesta vacía con mensaje de error
        return JsonResponse({
            'results': [],
            'error': f'Error al buscar modelos: {str(e)}'
        })
