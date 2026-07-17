"""
Vistas AJAX de piezas cotizadas (Fase 6 modularización).

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
# VISTAS AJAX: GESTIÓN DE PIEZAS COTIZADAS
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.add_piezacotizada')
@require_http_methods(["POST"])
def agregar_pieza_cotizada(request, orden_id):
    """
    Agrega una nueva pieza a una cotización existente.

    """
    from django.http import JsonResponse
    from .forms import PiezaCotizadaForm
    from .models import PiezaCotizada, Cotizacion
    
    try:
        orden = get_object_or_404(OrdenServicio, id=orden_id)
        
        # Verificar que existe cotización
        if not hasattr(orden, 'cotizacion'):
            return JsonResponse({
                'success': False,
                'error': '❌ Esta orden no tiene cotización asociada'
            }, status=400)
        
        cotizacion = orden.cotizacion
        
        # Procesar formulario
        form = PiezaCotizadaForm(request.POST)
        
        if form.is_valid():
            pieza = form.save(commit=False)
            pieza.cotizacion = cotizacion
            pieza.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✅ Pieza agregada: {pieza.componente.nombre} (x{pieza.cantidad})",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza agregada: {pieza.componente.nombre}',
                'pieza_id': pieza.id,
                'pieza_html': _render_pieza_row(pieza, cotizacion)  # Función helper
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
@permission_required_with_message('servicio_tecnico.view_piezacotizada')
@require_http_methods(["GET"])
def obtener_pieza_cotizada(request, pieza_id):
    """
    Obtiene los datos de una pieza cotizada para edición
    
    Returns:
        JsonResponse: Datos de la pieza en formato JSON
    """
    from django.http import JsonResponse
    from .models import PiezaCotizada
    
    try:
        pieza = get_object_or_404(PiezaCotizada, id=pieza_id)
        
        # Construir diccionario con los datos de la pieza
        datos_pieza = {
            'id': pieza.id,
            'componente_id': pieza.componente_id,
            'componente_nombre': pieza.componente.nombre,
            'descripcion_adicional': pieza.descripcion_adicional or '',
            'proveedor': pieza.proveedor or '',  # ← NUEVO CAMPO (Noviembre 2025)
            'cantidad': pieza.cantidad,
            'costo_unitario': str(pieza.costo_unitario),
            'orden_prioridad': pieza.orden_prioridad,
            'es_necesaria': pieza.es_necesaria,
            'sugerida_por_tecnico': pieza.sugerida_por_tecnico,
        }
        
        return JsonResponse({
            'success': True,
            'pieza': datos_pieza
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al obtener pieza: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_piezacotizada')
@require_http_methods(["POST"])
def editar_pieza_cotizada(request, pieza_id):
    """
    Edita una pieza cotizada existente.

    """
    from django.http import JsonResponse
    from .forms import PiezaCotizadaForm
    from .models import PiezaCotizada
    
    try:
        pieza = get_object_or_404(PiezaCotizada, id=pieza_id)
        cotizacion = pieza.cotizacion
        orden = cotizacion.orden
        
        # Procesar formulario de edición
        form = PiezaCotizadaForm(request.POST, instance=pieza)
        
        if form.is_valid():
            pieza_actualizada = form.save()
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✏️ Pieza modificada: {pieza_actualizada.componente.nombre}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Pieza actualizada: {pieza_actualizada.componente.nombre}',
                'pieza_html': _render_pieza_row(pieza_actualizada, cotizacion)
            })
        else:
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
@permission_required_with_message('servicio_tecnico.delete_piezacotizada')
@require_http_methods(["POST"])
def eliminar_pieza_cotizada(request, pieza_id):
    """
    Elimina una pieza de la cotización.

    """
    from django.http import JsonResponse
    from .models import PiezaCotizada
    
    try:
        pieza = get_object_or_404(PiezaCotizada, id=pieza_id)
        cotizacion = pieza.cotizacion
        orden = cotizacion.orden
        
        # ⚠️ VALIDACIÓN: No eliminar si cotización aceptada
        if cotizacion.usuario_acepto:
            return JsonResponse({
                'success': False,
                'error': '❌ No puedes eliminar piezas de una cotización ya aceptada. ' +
                         'Puedes editarla y cambiar la cantidad a 0 si ya no la necesitas.'
            }, status=403)
        
        # Guardar info antes de eliminar
        componente_nombre = pieza.componente.nombre
        
        # Eliminar
        pieza.delete()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🗑️ Pieza eliminada: {componente_nombre}",
            es_sistema=False
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Pieza eliminada: {componente_nombre}'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)


# ============================================================================
# FUNCIONES HELPER: RENDER HTML Y NOTIFICACIONES
# ============================================================================

def _render_pieza_row(pieza, cotizacion):
    """
    Renderiza una fila de la tabla de piezas como HTML.

    NOTA: Idealmente esto debería usar un template parcial, pero por
    simplicidad lo generamos aquí directamente.
    """
    puede_eliminar = 'false' if cotizacion.usuario_acepto else 'true'
    
    html = f'''
    <tr data-pieza-id="{pieza.id}">
        <td>
            <span class="badge bg-primary">{pieza.orden_prioridad}</span>
        </td>
        <td>
            <strong>{pieza.componente.nombre}</strong><br>
            <small class="text-muted">{pieza.componente.get_tipo_equipo_display()}</small>
            {f'<br><small>{pieza.descripcion_adicional}</small>' if pieza.descripcion_adicional else ''}
        </td>
        <td class="text-center">{pieza.cantidad}</td>
        <td class="text-end">${pieza.costo_unitario:.2f}</td>
        <td class="text-end"><strong>${pieza.costo_total:.2f}</strong></td>
        <td class="text-center">
            {f'<span class="badge bg-secondary" style="font-size: 0.75rem;">🏪 {pieza.proveedor}</span>' if pieza.proveedor else '<span class="text-muted">-</span>'}
        </td>
        <td class="text-center">
            {'<span class="badge bg-success">Sí</span>' if pieza.es_necesaria else '<span class="badge bg-info">Opcional</span>'}
        </td>
        <td class="text-center">
            {'<span class="badge bg-warning text-dark">Técnico</span>' if pieza.sugerida_por_tecnico else ''}
        </td>
        <td class="text-center">
            <button type="button" class="btn btn-sm btn-outline-primary me-1" 
                    onclick="editarPieza({pieza.id})" title="Editar">
                📝
            </button>
            {'<button type="button" class="btn btn-sm btn-outline-danger" onclick="eliminarPieza(' + str(pieza.id) + ')" title="Eliminar">🗑️</button>' if not cotizacion.usuario_acepto else '<span class="text-muted" title="No se puede eliminar (cotización aceptada)">🔒</span>'}
        </td>
    </tr>
    '''
    
    return html.strip()

