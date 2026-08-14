"""
Sincronización Almacén ↔ ST desde cotización: generar compras, vincular/crear orden.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 4 de modularización Almacén).
Cuando el cliente ya aprobó líneas, estas vistas crean compras
o vinculan/crean la OrdenServicio (modo sin orden / FL-).

urls.py sigue usando views.generar_compras_solicitud, etc.
porque views.py reexporta estos nombres.

Efectos secundarios:
- Crea CompraProducto / actualiza VentaMostrador / SeguimientoPieza
- Puede crear OrdenServicio + DetalleEquipo en servicio_tecnico
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from inventario.models import Empleado

from .decorators import permission_required_with_message
from .models import CompraProducto, LineaCotizacion, SolicitudCotizacion

import logging

logger = logging.getLogger('almacen')


@login_required
@permission_required_with_message('almacen.add_compraproducto')
def generar_compras_solicitud(request, pk):
    """
    Genera CompraProducto para las líneas aprobadas y VentaMostrador para servicios adicionales.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Una vez que el cliente ha aprobado las líneas y/o servicios adicionales,
    esta acción crea:
    
    1. CompraProducto para cada línea de pieza aprobada
       - Queda vinculado a la línea de cotización
       - Tiene estado 'pendiente_llegada'
       - Hereda el producto, proveedor, cantidad y costo de la línea
       - Se vincula a la misma orden de servicio
    
    2. VentaMostrador (o actualiza si ya existe) para servicios adicionales aprobados
       - Mapea cada servicio a su campo correspondiente en VentaMostrador
       - Ejemplo: 'limpieza' → incluye_limpieza=True, costo_limpieza=$450
    
    3. En órdenes OOW de reparación (no FL-): crea SeguimientoPieza en ST
       agrupados por proveedor y pasa la orden a «Esperando Llegada de Piezas».
    
    Esto integra el flujo de cotizaciones con el flujo existente de compras
    y ventas mostrador.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if request.method == 'POST':
        # Bloquear compras en modo sin orden activa hasta vincular orden de servicio
        if solicitud.compras_pendientes_sin_orden():
            messages.error(
                request,
                'Debes crear o vincular una orden de servicio antes de generar las compras.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

        puede_generar_compras = solicitud.puede_generar_compras()
        puede_generar_venta = solicitud.puede_generar_venta_mostrador()
        
        # Validar que haya algo que generar
        if not puede_generar_compras and not puede_generar_venta:
            messages.error(
                request,
                'No hay líneas ni servicios aprobados pendientes de procesar.'
            )
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        
        mensajes_exito = []

        # ====== Piezas en Venta Mostrador (FL- o equipos reacondicionados en OOW) ======
        # Se llama ANTES de generar_compras() porque generar_compras() pasa las líneas
        # a estado 'compra_generada' y este método filtra por estado='aprobada'.
        necesita_piezas_vm = (
            puede_generar_compras
            and solicitud.orden_servicio
            and (
                solicitud.orden_servicio.tipo_servicio == 'venta_mostrador'
                or solicitud.lineas.filter(
                    es_linea_reacondicionado=True,
                    estado_cliente='aprobada',
                ).exists()
            )
        )
        if necesita_piezas_vm:
            n_piezas = solicitud.generar_piezas_venta_mostrador()
            if n_piezas:
                mensajes_exito.append(
                    f'{n_piezas} pieza(s) registrada(s) en sección Venta Mostrador'
                )

        # Generar compras para piezas (CompraProducto para control de inventario/almacén)
        if puede_generar_compras:
            compras = solicitud.generar_compras(usuario=request.user)
            if compras:
                mensajes_exito.append(
                    f'{len(compras)} compra(s) de piezas generada(s)'
                )
            # Mensaje del sync ST (seguimiento de piezas + estado esperando_piezas)
            sync_st = getattr(solicitud, '_resultado_sync_seguimiento_st', None) or {}
            n_seg = sync_st.get('seguimientos_creados', 0)
            if n_seg:
                mensajes_exito.append(
                    f'{n_seg} seguimiento(s) de piezas registrado(s) en Servicio Técnico'
                )
            if sync_st.get('estado_actualizado'):
                mensajes_exito.append(
                    'orden ST actualizada a «Esperando Llegada de Piezas»'
                )
        
        # Generar VentaMostrador para servicios adicionales (paquetes, limpieza, etc.)
        if puede_generar_venta:
            venta = solicitud.generar_venta_mostrador()
            if venta:
                mensajes_exito.append(
                    f'Venta Mostrador creada/actualizada ({venta.folio_venta})'
                )
        
        # Mostrar mensajes al usuario
        if mensajes_exito:
            messages.success(
                request,
                'Se generaron exitosamente: ' + '. '.join(mensajes_exito) + '.'
            )
        else:
            messages.warning(request, 'No se pudieron generar las compras/servicios.')
    
    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def vincular_orden_solicitud(request, pk):
    """
    Vincular una solicitud de cotización (sin orden activa) a una orden de servicio.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando una cotización se crea sin orden activa (el equipo aún no ingresa),
    esta vista permite buscar y vincular la orden de servicio correspondiente
    cuando el equipo ya ingresó formalmente.
    
    BÚSQUEDA:
    - Por número de orden interno (ORD-2025-0001)
    - Por número de orden cliente (OOW-12345, FL-67890)
    - Por service tag / número de serie
    - Por nombre del cliente
    """
    from servicio_tecnico.models import OrdenServicio, DetalleEquipo
    
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)
    
    if not solicitud.puede_vincular_orden():
        messages.error(
            request,
            'No se puede vincular una orden. La solicitud ya tiene orden activa '
            'o está completada/cancelada.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
    
    resultados = []
    termino_busqueda = ''
    
    if request.method == 'POST':
        termino_busqueda = request.POST.get('busqueda', '').strip()
        orden_pk = request.POST.get('orden_pk', '')
        
        # Si se seleccionó una orden específica, vincularla
        if orden_pk:
            orden = get_object_or_404(OrdenServicio, pk=orden_pk)
            
            try:
                solicitud.vincular_orden(orden)
                messages.success(
                    request,
                    f'Solicitud {solicitud.numero_solicitud} vinculada exitosamente '
                    f'a la orden {orden.numero_orden_interno}.'
                )
            except ValueError as e:
                messages.error(request, str(e))
            
            return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)
        
        # Buscar órdenes que coincidan
        if termino_busqueda:
            from django.db.models import Q
            
            # Buscar por número de orden interno, orden cliente, o service tag
            resultados = OrdenServicio.objects.filter(
                Q(numero_orden_interno__icontains=termino_busqueda) |
                Q(detalle_equipo__orden_cliente__icontains=termino_busqueda) |
                Q(detalle_equipo__numero_serie__icontains=termino_busqueda) |
                Q(detalle_equipo__nombre_cliente__icontains=termino_busqueda)
            ).select_related('detalle_equipo').order_by('-fecha_ingreso')[:20]
            
            # Si no hay resultados y tenemos service_tag de la solicitud, buscar por eso
            if not resultados and solicitud.service_tag:
                resultados = OrdenServicio.objects.filter(
                    detalle_equipo__numero_serie__icontains=solicitud.service_tag
                ).select_related('detalle_equipo').order_by('-fecha_ingreso')[:20]
    
    # Si es GET, buscar automáticamente por service_tag si existe
    elif solicitud.service_tag:
        from servicio_tecnico.models import OrdenServicio
        resultados = OrdenServicio.objects.filter(
            detalle_equipo__numero_serie__icontains=solicitud.service_tag
        ).select_related('detalle_equipo').order_by('-fecha_ingreso')[:20]
        termino_busqueda = solicitud.service_tag
    
    return render(request, 'almacen/cotizaciones/vincular_orden.html', {
        'solicitud': solicitud,
        'resultados': resultados,
        'termino_busqueda': termino_busqueda,
    })


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
def crear_orden_fl_desde_cotizacion(request, pk):
    """
    Crea una OrdenServicio tipo FL- (Venta Mostrador / Servicio Directo) directamente
    desde el detalle de una SolicitudCotizacion que no tiene orden vinculada.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando una cotización se creó en modo "sin orden activa" (el cliente solicitó
    precio antes de ingresar físicamente el equipo) y el cliente acepta la cotización,
    en lugar de obligar al usuario a ir a Servicio Técnico a crear la orden manualmente,
    esta vista crea la orden FL- (Servicio Directo sin Diagnóstico) aquí mismo,
    usando todos los datos del cliente y equipo que ya fueron capturados en la solicitud.

    Flujo:
    1. GET  → muestra modal con el formulario mínimo (técnico + número FL- sugerido)
    2. POST → crea OrdenServicio + DetalleEquipo con datos reales de la solicitud,
              llama a solicitud.vincular_orden() para sincronizar con ST,
              re-guarda las LineaCotizacion para que se sincronicen como PiezaCotizada,
              redirige al detalle con mensaje de éxito.

    Restricciones:
    - Solo aplica si solicitud.puede_vincular_orden() es True (sin_orden_activa + no completada/cancelada)
    - El tipo de servicio es siempre 'venta_mostrador' (Servicio Directo sin Diagnóstico)
    - El número FL- se auto-sugiere pero puede ser editado por el usuario

    Args:
        request: HttpRequest de Django
        pk     : PK de la SolicitudCotizacion

    Efectos secundarios:
        - Crea OrdenServicio y DetalleEquipo en servicio_tecnico
        - Modifica SolicitudCotizacion (vincula orden, desactiva sin_orden_activa)
        - Crea Cotizacion en servicio_tecnico (vía solicitud.vincular_orden → save)
        - Re-sincroniza LineaCotizacion → PiezaCotizada en servicio_tecnico
    """
    from servicio_tecnico.models import OrdenServicio, DetalleEquipo

    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    # Validar que la solicitud esté en modo sin_orden_activa y pueda vincularse
    if not solicitud.puede_vincular_orden():
        messages.error(
            request,
            'No se puede crear una orden. La solicitud ya tiene orden activa '
            'o está completada/cancelada.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if request.method == 'GET':
        # ====== PREPARAR DATOS PARA EL MODAL ======

        # Obtener lista de técnicos activos (rol del sistema) para el selector
        tecnicos = Empleado.objects.filter(
            activo=True,
            rol=Empleado.ROL_TECNICO,
        ).select_related('sucursal').order_by('nombre_completo')

        # El consecutivo FL-YYYY-NNNN vive en utils para compartirlo con baja.
        from almacen.utils.folio_orden_fl import sugerir_siguiente_folio_fl

        numero_fl_sugerido = sugerir_siguiente_folio_fl()

        return JsonResponse({
            'success': True,
            'tecnicos': [
                {
                    'id': t.pk,
                    'nombre': t.nombre_completo,
                    'sucursal': t.sucursal.nombre if t.sucursal else 'Sin asignar',
                }
                for t in tecnicos
            ],
            'numero_fl_sugerido': numero_fl_sugerido,
            # Datos del cliente/equipo para mostrar resumen en el modal
            'resumen': {
                'nombre_cliente': solicitud.nombre_cliente or '(sin nombre)',
                'email_cliente': solicitud.email_cliente or '(sin email)',
                'telefono_cliente': solicitud.telefono_cliente or '(sin teléfono)',
                'tipo_equipo': solicitud.tipo_equipo or 'Por definir',
                'marca': solicitud.marca or 'Por definir',
                'modelo': solicitud.modelo or 'Por definir',
                'numero_serie': solicitud.service_tag or '(sin service tag)',
            }
        })

    # ====== POST: Crear la orden FL- ======
    tecnico_id = request.POST.get('tecnico_id', '').strip()
    numero_fl = request.POST.get('numero_fl', '').strip().upper()

    # --- Validación de campos requeridos ---
    if not tecnico_id:
        messages.error(request, 'Debes seleccionar un técnico para crear la orden.')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    if not numero_fl:
        messages.error(request, 'El número de folio FL- es obligatorio.')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Validar que el número FL- tenga el formato correcto
    if not numero_fl.startswith('FL-'):
        messages.error(request, 'El folio debe comenzar con "FL-" (ej: FL-2026-0001).')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Verificar que el número FL- no esté ya en uso en DetalleEquipo
    if DetalleEquipo.objects.filter(orden_cliente=numero_fl).exists():
        messages.error(
            request,
            f'El folio {numero_fl} ya está registrado en otra orden. '
            'Por favor usa un número diferente.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # --- Obtener el técnico ---
    try:
        tecnico = Empleado.objects.get(pk=tecnico_id)
    except Empleado.DoesNotExist:
        messages.error(request, 'El técnico seleccionado no es válido.')
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # Sucursal: empleado creador, si no tiene, la del técnico (misma regla que baja).
    from almacen.utils.folio_orden_fl import resolver_sucursal_orden_almacen

    try:
        empleado_creador = Empleado.objects.get(user=solicitud.creado_por)
    except (Empleado.DoesNotExist, AttributeError):
        empleado_creador = None
    sucursal = resolver_sucursal_orden_almacen(empleado_creador, tecnico)

    if not sucursal:
        messages.error(
            request,
            'No se pudo determinar la sucursal. '
            'El creador de la solicitud o el técnico no tienen sucursal asignada.'
        )
        return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)

    # --- Obtener el responsable de seguimiento (el usuario actual) ---
    try:
        responsable = Empleado.objects.get(user=request.user)
    except Empleado.DoesNotExist:
        # Si el usuario actual no tiene empleado asociado, usar el técnico como responsable
        responsable = tecnico

    try:
        # ====== PASO 1: Crear la OrdenServicio ======
        # tipo_servicio='venta_mostrador' porque estas órdenes son Servicio Directo sin Diagnóstico
        # estado='almacen' porque se origina desde el módulo Almacén
        orden = OrdenServicio.objects.create(
            sucursal=sucursal,
            responsable_seguimiento=responsable,
            tecnico_asignado_actual=tecnico,
            estado='almacen',
            tipo_servicio='venta_mostrador',
        )

        # ====== PASO 2: Crear el DetalleEquipo con los datos REALES del cliente ======
        # A diferencia del flujo genérico de solicitudes de baja (que usa placeholders),
        # aquí ya tenemos datos reales del cliente capturados en la SolicitudCotizacion.

        # Determinar tipo_equipo: usar el de la solicitud o fallback a 'Laptop'
        tipo_equipo_real = solicitud.tipo_equipo if solicitud.tipo_equipo else 'Laptop'

        # Determinar marca: usar la de la solicitud o fallback a 'Otra'
        marca_real = solicitud.marca if solicitud.marca else 'Otra'

        # Determinar modelo: usar el de la solicitud o placeholder
        modelo_real = solicitud.modelo if solicitud.modelo else 'Por definir'

        # Determinar número de serie: usar service_tag de la solicitud o placeholder
        numero_serie_real = solicitud.service_tag if solicitud.service_tag else f'ALMACEN-{numero_fl}'

        # Determinar falla_principal: usar observaciones de la solicitud o texto genérico
        falla_real = (
            solicitud.observaciones
            if solicitud.observaciones
            else 'Servicio directo sin diagnóstico - Cotización aprobada por cliente'
        )

        # Email del cliente: usar el de la solicitud o placeholder
        email_real = solicitud.email_cliente if solicitud.email_cliente else 'pendiente@actualizar.com'

        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=numero_fl,        # Número FL- define es_fuera_garantia=True automáticamente
            tipo_equipo=tipo_equipo_real,
            marca=marca_real,
            modelo=modelo_real,
            numero_serie=numero_serie_real,
            gama='media',                   # Valor por defecto; el técnico puede ajustar después
            falla_principal=falla_real,
            email_cliente=email_real,
            # Datos adicionales del cliente (campos opcionales en DetalleEquipo)
            nombre_cliente=solicitud.nombre_cliente or '',
            telefono_cliente=solicitud.telefono_cliente or '',
            rfc_cliente=solicitud.rfc_cliente or '',
        )

        # ====== PASO 3: Vincular la solicitud con la nueva orden ======
        # vincular_orden() hace:
        #   - self.orden_servicio = orden
        #   - self.sin_orden_activa = False
        #   - Sincroniza numero_orden_cliente desde DetalleEquipo
        #   - self.save() → crea Cotizacion en ST vía _sincronizar_cotizacion_st()
        solicitud.vincular_orden(orden)

        # ====== PASO 4: Crear VentaMostrador vacío para la nueva orden ======
        # Para órdenes FL- (Venta Mostrador / Servicio Directo), NO se sincronizan
        # las líneas a PiezaCotizada (flujo de diagnóstico). En su lugar se crea el
        # VentaMostrador vacío ahora para que exista el objeto receptor; las piezas
        # individuales se crearán como PiezaVentaMostrador cuando el usuario pulse
        # "Generar Compras" en el detalle de la cotización.
        from servicio_tecnico.models import VentaMostrador as VentaMostradorModel
        VentaMostradorModel.objects.get_or_create(
            orden=orden,
            defaults={'fecha_venta': timezone.now()}
        )

        # Construir mensaje de éxito con información de la orden creada
        mensaje = (
            f'Orden {numero_fl} creada exitosamente y vinculada a la solicitud. '
            f'Orden interna: {orden.numero_orden_interno}. '
            f'Las piezas aprobadas se registrarán en Venta Mostrador al generar compras.'
        )

        messages.success(request, mensaje)

        logger.info(
            f"OrdenServicio {orden.numero_orden_interno} (FL: {numero_fl}) creada desde "
            f"SolicitudCotizacion {solicitud.numero_solicitud} por usuario {request.user}"
        )

    except ValueError as e:
        # Error de validación del método vincular_orden (ej: ya tiene otra solicitud activa)
        messages.error(request, f'Error al vincular la orden: {str(e)}')
        # Si la orden fue creada pero falló el vínculo, eliminarla para evitar órfanos
        try:
            orden.delete()
        except Exception:
            pass
    except Exception as e:
        messages.error(request, f'Error inesperado al crear la orden: {str(e)}')
        logger.error(
            f"Error al crear OrdenServicio desde SolicitudCotizacion {pk}: {e}",
            exc_info=True
        )
        # Intentar eliminar la orden parcialmente creada si existe
        try:
            orden.delete()
        except Exception:
            pass

    return redirect('almacen:detalle_solicitud_cotizacion', pk=pk)


