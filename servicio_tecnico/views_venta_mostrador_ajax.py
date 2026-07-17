"""
Vistas AJAX de venta mostrador (crear + piezas) — Fase 6.

urls.py sigue usando views.<nombre> porque views.py reexporta estos símbolos.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import OrdenServicio
from .services.historial import registrar_historial


# ============================================================================
# VISTAS AJAX PARA VENTA MOSTRADOR - FASE 3
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.add_ventamostrador')
@require_http_methods(["POST"])
def crear_venta_mostrador(request, orden_id):
    """
    Crea una nueva venta mostrador asociada a una orden.

    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden a la que se asocia la venta
    
    Returns:
        JsonResponse con success=True/False y datos de la venta
    """
    from django.http import JsonResponse
    from .forms import VentaMostradorForm
    from .models import VentaMostrador
    
    try:
        # Obtener la orden (CUALQUIER tipo)
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que NO tenga venta mostrador existente
        if hasattr(orden, 'venta_mostrador'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden ya tiene una venta mostrador registrada'
            }, status=400)
        
        # Procesar formulario
        form = VentaMostradorForm(request.POST)
        
        if form.is_valid():
            venta = form.save(commit=False)
            venta.orden = orden
            venta.save()
            
            # Registrar en historial
            empleado_actual = request.user.empleado if hasattr(request.user, 'empleado') else None
            registrar_historial(
                orden=orden,
                tipo_evento='actualizacion',
                usuario=empleado_actual,
                comentario=f"✅ Venta Mostrador creada: {venta.folio_venta} | Paquete: {venta.get_paquete_display()} | Total: ${venta.total_venta}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Venta Mostrador creada: {venta.folio_venta}',
                'folio_venta': venta.folio_venta,
                'total_venta': float(venta.total_venta),
                'paquete': venta.get_paquete_display(),
                'es_complemento': orden.tipo_servicio == 'diagnostico',  # Info contextual
                'redirect_url': f'/servicio-tecnico/ordenes/{orden_id}/'  # Redirigir para refrescar
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]  # Primer error de cada campo
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.add_piezaventamostrador')
@require_http_methods(["POST"])
def agregar_pieza_venta_mostrador(request, orden_id):
    """
    Agrega una nueva pieza a una venta mostrador existente.

    Args:
        request: HttpRequest con datos POST del formulario
        orden_id: ID de la orden que tiene la venta mostrador
    
    Returns:
        JsonResponse con success=True/False y HTML de la pieza
    """
    from django.http import JsonResponse
    from .forms import PiezaVentaMostradorForm
    from .models import PiezaVentaMostrador, VentaMostrador
    
    try:
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que existe venta mostrador
        if not hasattr(orden, 'venta_mostrador'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene venta mostrador asociada'
            }, status=400)
        
        venta_mostrador = orden.venta_mostrador
        
        # Procesar formulario
        form = PiezaVentaMostradorForm(request.POST)
        
        if form.is_valid():
            pieza = form.save(commit=False)
            pieza.venta_mostrador = venta_mostrador
            pieza.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='actualizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✅ Pieza agregada a venta mostrador: {pieza.descripcion_pieza} (x{pieza.cantidad}) - ${pieza.subtotal}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza agregada: {pieza.descripcion_pieza}',
                'pieza_id': pieza.id,
                'descripcion': pieza.descripcion_pieza,
                'cantidad': pieza.cantidad,
                'precio_unitario': float(pieza.precio_unitario),
                'subtotal': float(pieza.subtotal),
                'total_venta_actualizado': float(venta_mostrador.total_venta),
                'redirect_url': f'/servicio-tecnico/ordenes/{orden_id}/'  # Redirigir para refrescar
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]  # Primer error de cada campo
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_piezaventamostrador')
@require_http_methods(["POST"])
def editar_pieza_venta_mostrador(request, pieza_id):
    """
    Edita una pieza de venta mostrador existente.

    Args:
        request: HttpRequest con datos POST del formulario
        pieza_id: ID de la pieza a editar
    
    Returns:
        JsonResponse con success=True/False y datos actualizados
    """
    from django.http import JsonResponse
    from .forms import PiezaVentaMostradorForm
    from .models import PiezaVentaMostrador
    
    try:
        pieza = get_object_or_404(PiezaVentaMostrador, id=pieza_id)
        venta_mostrador = pieza.venta_mostrador
        orden = venta_mostrador.orden
        
        # Procesar formulario de edición
        form = PiezaVentaMostradorForm(request.POST, instance=pieza)
        
        if form.is_valid():
            pieza_actualizada = form.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='actualizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✏️ Pieza modificada: {pieza_actualizada.descripcion_pieza} - ${pieza_actualizada.subtotal}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza actualizada: {pieza_actualizada.descripcion_pieza}',
                'pieza_id': pieza_actualizada.id,
                'descripcion': pieza_actualizada.descripcion_pieza,
                'cantidad': pieza_actualizada.cantidad,
                'precio_unitario': float(pieza_actualizada.precio_unitario),
                'subtotal': float(pieza_actualizada.subtotal),
                'total_venta_actualizado': float(venta_mostrador.total_venta),
                'redirect_url': f'/servicio-tecnico/ordenes/{orden.id}/'
            })
        else:
            # Devolver errores del formulario
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.delete_piezaventamostrador')
@require_http_methods(["POST"])
def eliminar_pieza_venta_mostrador(request, pieza_id):
    """
    Elimina una pieza de venta mostrador.

    Returns:
        JsonResponse con success=True/False
    """
    from django.http import JsonResponse
    from .models import PiezaVentaMostrador
    
    try:
        pieza = get_object_or_404(PiezaVentaMostrador, id=pieza_id)
        venta_mostrador = pieza.venta_mostrador
        orden = venta_mostrador.orden
        
        # Guardar info antes de eliminar
        descripcion = pieza.descripcion_pieza
        subtotal = pieza.subtotal
        
        # Eliminar pieza
        pieza.delete()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='actualizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🗑️ Pieza eliminada de venta mostrador: {descripcion} (${subtotal})",
            es_sistema=False
        )
        
        # Recalcular total (se hace automáticamente por el property total_venta)
        return JsonResponse({
            'success': True,
            'message': f'✅ Pieza eliminada: {descripcion}',
            'total_venta_actualizado': float(venta_mostrador.total_venta),
            'redirect_url': f'/servicio-tecnico/ordenes/{orden.id}/'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)

