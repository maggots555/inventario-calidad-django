"""
Vistas AJAX de seguimiento de piezas a proveedor (Fase 6).

La notificación de pieza recibida vive en services/notificaciones_piezas.py
(también la usa Almacén al sincronizar compras recibidas).

urls.py sigue usando views.<nombre> porque views.py reexporta estos símbolos.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import OrdenServicio
from .services.historial import registrar_historial


from .services.notificaciones_piezas import (
    enviar_notificacion_pieza_recibida as _enviar_notificacion_pieza_recibida,
)


# ============================================================================
# VISTAS AJAX: GESTIÓN DE SEGUIMIENTOS DE PIEZAS
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_seguimientopieza')
@require_http_methods(["GET"])
def obtener_seguimiento_pieza(request, seguimiento_id):
    """
    Obtiene los datos de un seguimiento en formato JSON.

    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        
        # Preparar datos en formato JSON
        data = {
            'success': True,
            'seguimiento': {
                'id': seguimiento.id,
                'proveedor': seguimiento.proveedor,
                'descripcion_piezas': seguimiento.descripcion_piezas,
                'numero_pedido': seguimiento.numero_pedido or '',
                'fecha_pedido': seguimiento.fecha_pedido.isoformat(),  # Formato: YYYY-MM-DD
                'fecha_entrega_estimada': seguimiento.fecha_entrega_estimada.isoformat(),
                'fecha_entrega_real': seguimiento.fecha_entrega_real.isoformat() if seguimiento.fecha_entrega_real else '',
                'estado': seguimiento.estado,
                'notas_seguimiento': seguimiento.notas_seguimiento or '',
                # Piezas relacionadas (IDs)
                'piezas': list(seguimiento.piezas.values_list('id', flat=True))
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error al obtener seguimiento: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.add_seguimientopieza')
@require_http_methods(["POST"])
def agregar_seguimiento_pieza(request, orden_id):
    """
    Agrega un nuevo seguimiento de pedido a proveedor.

    """
    from django.http import JsonResponse
    from .forms import SeguimientoPiezaForm
    from .models import SeguimientoPieza
    
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
        form = SeguimientoPiezaForm(request.POST, cotizacion=cotizacion)
        
        if form.is_valid():
            seguimiento = form.save(commit=False)
            seguimiento.cotizacion = cotizacion
            seguimiento.save()
            form.save_m2m()  # Guardar relaciones ManyToMany (piezas)
            
            # ===================================================================
            # NUEVA FUNCIONALIDAD: Cambiar estado automáticamente si es el primer seguimiento
            # ===================================================================
            # Contar cuántos seguimientos tiene esta cotización (incluyendo el recién agregado)
            total_seguimientos = cotizacion.seguimientos_piezas.count()
            
            if total_seguimientos == 1:
                # Es el PRIMER seguimiento → Cambiar estado a "esperando_piezas"
                estado_anterior = orden.estado
                orden.estado = 'esperando_piezas'
                orden.save()
                
                # Registrar el cambio de estado en el historial
                registrar_historial(
                    orden=orden,
                    tipo_evento='estado',
                    usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                    comentario=f"🔄 Estado cambiado automáticamente: '{dict(orden._meta.get_field('estado').choices).get(estado_anterior)}' → 'Esperando Llegada de Piezas' (Primer seguimiento agregado)",
                    es_sistema=True
                )
            # ===================================================================
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"📦 Seguimiento agregado - Proveedor: {seguimiento.proveedor}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Seguimiento agregado: {seguimiento.proveedor}',
                'seguimiento_id': seguimiento.id,
                'seguimiento_html': _render_seguimiento_card(seguimiento)
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
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def editar_seguimiento_pieza(request, seguimiento_id):
    """
    Edita un seguimiento existente.

    """
    from django.http import JsonResponse
    from .forms import SeguimientoPiezaForm
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        estado_anterior = seguimiento.estado
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # Procesar formulario
        form = SeguimientoPiezaForm(request.POST, instance=seguimiento, cotizacion=cotizacion)
        
        if form.is_valid():
            seguimiento_actualizado = form.save()
            
            # Si cambió a "recibido", enviar notificación
            if estado_anterior != 'recibido' and seguimiento_actualizado.estado == 'recibido':
                _enviar_notificacion_pieza_recibida(orden, seguimiento_actualizado)
            
            # Registrar en historial
            registrar_historial(
                orden=orden,
                tipo_evento='cotizacion',
                usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
                comentario=f"✏️ Seguimiento actualizado - {seguimiento_actualizado.proveedor}",
                es_sistema=False
            )
            
            return JsonResponse({
                'success': True,
                'message': f'✅ Seguimiento actualizado: {seguimiento_actualizado.proveedor}',
                'seguimiento_html': _render_seguimiento_card(seguimiento_actualizado)
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
@permission_required_with_message('servicio_tecnico.delete_seguimientopieza')
@require_http_methods(["POST"])
def eliminar_seguimiento_pieza(request, seguimiento_id):
    """
    Elimina un seguimiento de pieza.
    
    NOTA:
    A diferencia de las piezas, los seguimientos SÍ se pueden eliminar
    incluso después de aceptar la cotización (son solo para tracking).
    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        proveedor_nombre = seguimiento.proveedor
        
        # Eliminar
        seguimiento.delete()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=f"🗑️ Seguimiento eliminado - Proveedor: {proveedor_nombre}",
            es_sistema=False
        )
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Seguimiento eliminado: {proveedor_nombre}'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def marcar_pieza_recibida(request, seguimiento_id):
    """
    Marca una pieza como recibida y envía notificación al técnico.

    """
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # Obtener fecha de entrega real del POST
        fecha_entrega_real_str = request.POST.get('fecha_entrega_real')
        
        if not fecha_entrega_real_str:
            return JsonResponse({
                'success': False,
                'error': '❌ Debes proporcionar la fecha de entrega real'
            }, status=400)
        
        # Convertir string a date
        from datetime import datetime
        try:
            fecha_entrega_real = datetime.strptime(fecha_entrega_real_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': '❌ Formato de fecha inválido (debe ser YYYY-MM-DD)'
            }, status=400)
        
        # Actualizar seguimiento
        seguimiento.estado = 'recibido'
        seguimiento.fecha_entrega_real = fecha_entrega_real
        seguimiento.save()
        
        # =================================================================
        # NUEVO (Enero 2026): Verificar si el usuario desea enviar email
        # =================================================================
        enviar_email_param = request.POST.get('enviar_email', 'true')
        debe_enviar_email = enviar_email_param.lower() == 'true'
        
        # Variable para rastrear si el email fue omitido por decisión del usuario
        email_omitido = False
        
        # Enviar notificación solo si el usuario lo solicitó
        if debe_enviar_email:
            resultado_email = _enviar_notificacion_pieza_recibida(orden, seguimiento)
        else:
            # Usuario decidió NO enviar email
            email_omitido = True
            resultado_email = {
                'success': False,
                'message': 'Email omitido por decisión del usuario',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        # =================================================================
        # REGISTRAR EN HISTORIAL CON DETALLES DEL ENVÍO
        # =================================================================
        if email_omitido:
            # Usuario decidió NO enviar email
            mensaje_historial = f"📬 Pieza recibida - {seguimiento.proveedor}\n"
            mensaje_historial += f"📭 Email omitido por decisión del usuario\n"
            mensaje_historial += f"ℹ️ El técnico deberá ser notificado manualmente"
        elif resultado_email['success']:
            # Email enviado exitosamente
            destinatarios_str = ', '.join(resultado_email['destinatarios'])
            mensaje_historial = f"📬 Pieza recibida - {seguimiento.proveedor}\n"
            mensaje_historial += f"✉️ Email enviado a: {destinatarios_str}"
            
            if resultado_email['destinatarios_copia']:
                cc_str = ', '.join(resultado_email['destinatarios_copia'])
                mensaje_historial += f"\n📧 Con copia a: {cc_str}"
        else:
            # Error al enviar email
            mensaje_historial = f"📬 Pieza recibida - {seguimiento.proveedor}\n"
            mensaje_historial += f"❌ Error al enviar email: {resultado_email['message']}\n"
            mensaje_historial += f"⚠️ El técnico NO fue notificado automáticamente"
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RESPUESTA JSON CON INFORMACIÓN DEL ENVÍO
        # =================================================================
        mensaje_respuesta = '✅ Pieza marcada como recibida.'
        
        if email_omitido:
            mensaje_respuesta += ' Email omitido por decisión del usuario.'
        elif resultado_email['success']:
            mensaje_respuesta += ' Email enviado al técnico.'
        else:
            mensaje_respuesta += f" ⚠️ No se pudo enviar el email: {resultado_email['message']}"
        
        return JsonResponse({
            'success': True,
            'message': mensaje_respuesta,
            'email_enviado': resultado_email['success'],
            'email_omitido': email_omitido,  # NUEVO: Indicador de email omitido
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def reenviar_notificacion_pieza(request, seguimiento_id):
    """
    Reenvía la notificación de pieza recibida al técnico.

    Args:
        request: HttpRequest con el usuario autenticado
        seguimiento_id: ID del seguimiento de la pieza
    
    Returns:
        JsonResponse con el resultado del reenvío
    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    try:
        # Obtener el seguimiento
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # =================================================================
        # VALIDACIÓN: Solo se puede reenviar si está marcado como recibido
        # =================================================================
        if seguimiento.estado != 'recibido':
            return JsonResponse({
                'success': False,
                'error': '❌ Solo se pueden reenviar notificaciones de piezas marcadas como recibidas'
            }, status=400)
        
        # =================================================================
        # NUEVO (Enero 2026): Verificar si el usuario desea enviar email
        # En reenvíos normalmente siempre se quiere enviar, pero mantenemos
        # consistencia con la función marcar_recibido()
        # =================================================================
        enviar_email_param = request.POST.get('enviar_email', 'true')
        debe_enviar_email = enviar_email_param.lower() == 'true'
        
        email_omitido = False
        
        # =================================================================
        # INTENTAR ENVIAR EL EMAIL NUEVAMENTE (si el usuario lo solicitó)
        # =================================================================
        if debe_enviar_email:
            resultado_email = _enviar_notificacion_pieza_recibida(orden, seguimiento)
        else:
            # Usuario decidió NO reenviar
            email_omitido = True
            resultado_email = {
                'success': False,
                'message': 'Reenvío omitido por decisión del usuario',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        # =================================================================
        # REGISTRAR EN HISTORIAL EL INTENTO DE REENVÍO
        # =================================================================
        if email_omitido:
            # Usuario decidió NO reenviar
            mensaje_historial = f"🔄 Reenvío de notificación - {seguimiento.proveedor}\n"
            mensaje_historial += f"📭 Email omitido por decisión del usuario\n"
            mensaje_historial += f"ℹ️ El técnico deberá ser notificado manualmente si es necesario"
            
            mensaje_respuesta = '✓ Reenvío omitido por decisión del usuario'
        elif resultado_email['success']:
            # Éxito en el reenvío
            destinatarios_str = ', '.join(resultado_email['destinatarios'])
            mensaje_historial = f"🔄 Notificación reenviada - {seguimiento.proveedor}\n"
            mensaje_historial += f"✉️ Email enviado a: {destinatarios_str}"
            
            if resultado_email['destinatarios_copia']:
                cc_str = ', '.join(resultado_email['destinatarios_copia'])
                mensaje_historial += f"\n📧 Con copia a: {cc_str}"
            
            mensaje_respuesta = '✅ Notificación reenviada exitosamente al técnico'
        else:
            # Error en el reenvío
            mensaje_historial = f"🔄 Intento de reenvío - {seguimiento.proveedor}\n"
            mensaje_historial += f"❌ Error al enviar email: {resultado_email['message']}\n"
            mensaje_historial += f"⚠️ El técnico NO fue notificado"
            
            mensaje_respuesta = f"❌ Error al reenviar: {resultado_email['message']}"
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RETORNAR RESPUESTA
        # =================================================================
        return JsonResponse({
            'success': True,  # Siempre True porque la operación se completó (con o sin email)
            'message': mensaje_respuesta,
            'email_enviado': resultado_email['success'],
            'email_omitido': email_omitido  # NUEVO: Indicador de email omitido
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def marcar_pieza_incorrecta(request, seguimiento_id):
    """
    Marca una pieza como incorrecta (WPB - Wrong Part Boxed).

    IMPORTANTE:
    - Solo se puede marcar como incorrecta si está en estado 'recibido'
    - El seguimiento queda cerrado con estado 'incorrecto'
    - Se debe crear un NUEVO seguimiento para el reemplazo
    
    Args:
        request: HttpRequest con el usuario autenticado
        seguimiento_id: ID del seguimiento de la pieza
    
    Returns:
        JsonResponse con el resultado de la operación
    """
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # =================================================================
        # VALIDACIÓN: Solo se puede marcar si está recibido
        # =================================================================
        if seguimiento.estado != 'recibido':
            return JsonResponse({
                'success': False,
                'error': '❌ Solo se pueden marcar como incorrectas las piezas que ya fueron recibidas'
            }, status=400)
        
        # =================================================================
        # ACTUALIZAR ESTADO A INCORRECTO
        # =================================================================
        seguimiento.estado = 'incorrecto'
        seguimiento.save()
        
        # =================================================================
        # REGISTRAR EN HISTORIAL
        # =================================================================
        mensaje_historial = f"❌ PIEZA INCORRECTA (WPB) - {seguimiento.proveedor}\n"
        mensaje_historial += f"Descripción: {seguimiento.descripcion_piezas}\n"
        mensaje_historial += f"⚠️ La pieza recibida NO es la correcta o NO es compatible\n"
        mensaje_historial += f"📝 Acción requerida: Crear nuevo pedido de la pieza correcta"
        
        registrar_historial(
            orden=orden,
            tipo_evento='pieza',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RESPUESTA JSON
        # =================================================================
        return JsonResponse({
            'success': True,
            'message': '❌ Pieza marcada como INCORRECTA. Crea un nuevo pedido para la pieza correcta.',
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
@require_http_methods(["POST"])
def marcar_pieza_danada(request, seguimiento_id):
    """
    Marca una pieza como dañada o no funcional (DOA - Dead On Arrival).

    Args:
        request: HttpRequest con el usuario autenticado
        seguimiento_id: ID del seguimiento de la pieza
    
    Returns:
        JsonResponse con el resultado de la operación
    """
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import SeguimientoPieza
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # =================================================================
        # VALIDACIÓN: Solo se puede marcar si está recibido
        # =================================================================
        if seguimiento.estado != 'recibido':
            return JsonResponse({
                'success': False,
                'error': '❌ Solo se pueden marcar como dañadas las piezas que ya fueron recibidas'
            }, status=400)
        
        # =================================================================
        # ACTUALIZAR ESTADO A DAÑADO
        # =================================================================
        seguimiento.estado = 'danado'
        seguimiento.save()
        
        # =================================================================
        # REGISTRAR EN HISTORIAL
        # =================================================================
        mensaje_historial = f"⚠️ PIEZA DAÑADA/NO FUNCIONAL (DOA) - {seguimiento.proveedor}\n"
        mensaje_historial += f"Descripción: {seguimiento.descripcion_piezas}\n"
        mensaje_historial += f"❌ La pieza llegó dañada o no funciona correctamente\n"
        mensaje_historial += f"📝 Acción requerida: Solicitar reemplazo al proveedor/garantía"
        
        registrar_historial(
            orden=orden,
            tipo_evento='pieza',
            usuario=request.user.empleado if hasattr(request.user, 'empleado') else None,
            comentario=mensaje_historial,
            es_sistema=False
        )
        
        # =================================================================
        # RESPUESTA JSON
        # =================================================================
        return JsonResponse({
            'success': True,
            'message': '⚠️ Pieza marcada como DAÑADA/NO FUNCIONAL. Solicita reemplazo al proveedor.',
            'seguimiento_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




@login_required
@permission_required_with_message('servicio_tecnico.change_seguimientopieza')
def cambiar_estado_seguimiento(request, seguimiento_id):
    """
    Cambia el estado de un seguimiento de pieza de forma rápida.

    RETORNA:
    JSON con el HTML actualizado del card para reemplazarlo dinámicamente
    """
    from django.http import JsonResponse
    from .models import SeguimientoPieza
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        seguimiento = get_object_or_404(SeguimientoPieza, id=seguimiento_id)
        cotizacion = seguimiento.cotizacion
        orden = cotizacion.orden
        
        # Obtener empleado actual
        try:
            empleado_actual = request.user.empleado
        except AttributeError:
            return JsonResponse({
                'success': False,
                'error': '❌ Usuario no asociado a un empleado'
            }, status=403)
        
        # Obtener nuevo estado
        nuevo_estado = request.POST.get('nuevo_estado')
        
        # Validar estado
        estados_validos = ['pedido', 'confirmado', 'transito', 'retrasado', 'recibido']
        if nuevo_estado not in estados_validos:
            return JsonResponse({
                'success': False,
                'error': f'❌ Estado inválido: {nuevo_estado}'
            }, status=400)
        
        # Guardar estado anterior para historial
        estado_anterior = seguimiento.get_estado_display()
        
        # Actualizar estado
        seguimiento.estado = nuevo_estado
        seguimiento.save()
        
        # Obtener nombre del nuevo estado
        estado_nuevo_display = seguimiento.get_estado_display()
        
        # Registrar en historial
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=empleado_actual,
            comentario=f"📦 Estado de seguimiento actualizado: {estado_anterior} → {estado_nuevo_display} ({seguimiento.proveedor})",
            es_sistema=False
        )
        
        # Si cambió a "recibido", enviar notificación
        if nuevo_estado == 'recibido' and not seguimiento.fecha_entrega_real:
            from django.utils import timezone
            seguimiento.fecha_entrega_real = timezone.now().date()
            seguimiento.save()
            _enviar_notificacion_pieza_recibida(orden, seguimiento)
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Estado actualizado a: {estado_nuevo_display}',
            'card_html': _render_seguimiento_card(seguimiento)
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'❌ Error inesperado: {str(e)}'
        }, status=500)




def _render_seguimiento_card(seguimiento):
    """
    Renderiza una card de seguimiento como HTML.
    
    EXPLICACIÓN:
    Genera el HTML de una card de seguimiento para insertarla
    dinámicamente después de agregar/editar via AJAX.
    """
    from django.utils import timezone
    
    # Calcular si hay retraso
    retraso_dias = 0
    hay_retraso = False
    if seguimiento.estado != 'recibido' and seguimiento.fecha_entrega_estimada:
        hoy = timezone.now().date()
        if hoy > seguimiento.fecha_entrega_estimada:
            retraso_dias = (hoy - seguimiento.fecha_entrega_estimada).days
            hay_retraso = True
    
    # Definir estilos según estado (ACTUALIZADOS según ESTADO_PIEZA_CHOICES - Nov 2025)
    estado_badges = {
        'pedido': 'bg-primary',
        'confirmado': 'bg-info',
        'transito': 'bg-warning text-dark',
        'retrasado': 'bg-danger',
        'recibido': 'bg-success',
        'incorrecto': 'bg-danger',      # NUEVO: Pieza incorrecta (WPB)
        'danado': 'bg-warning text-dark',  # NUEVO: Pieza dañada (DOA)
    }
    
    estado_nombres = {
        'pedido': '📋 Pedido Realizado',
        'confirmado': '✅ Confirmado',
        'transito': '🚚 En Tránsito',
        'retrasado': '⚠️ Retrasado',
        'recibido': '📬 Recibido',
        'incorrecto': '❌ Pieza Incorrecta (WPB)',  # NUEVO
        'danado': '⚠️ Pieza Dañada (DOA)',          # NUEVO
    }
    
    border_class = ''
    if seguimiento.estado == 'recibido':
        border_class = 'border-success'
    elif seguimiento.estado in ['incorrecto', 'danado']:  # NUEVO: Borde rojo para problemas
        border_class = 'border-danger'
    elif hay_retraso or seguimiento.estado == 'retrasado':
        border_class = 'border-danger'
    
    html = f'''
    <div class="card seguimiento-card {border_class}" data-seguimiento-id="{seguimiento.id}">
        <div class="card-body">
            <h6 class="card-title">
                🏪 {seguimiento.proveedor}
                <span class="badge {estado_badges.get(seguimiento.estado, 'bg-secondary')} float-end">
                    {estado_nombres.get(seguimiento.estado, seguimiento.estado)}
                </span>
            </h6>
            
            <p class="card-text">
                <small><strong>Piezas:</strong> {seguimiento.descripcion_piezas}</small><br>
                {f'<small><strong>Pedido:</strong> {seguimiento.numero_pedido}</small><br>' if seguimiento.numero_pedido else ''}
                <small><strong>Fecha Pedido:</strong> {seguimiento.fecha_pedido.strftime('%d/%m/%Y')}</small><br>
                <small><strong>Entrega Estimada:</strong> {seguimiento.fecha_entrega_estimada.strftime('%d/%m/%Y')}</small><br>
                {f'<small><strong>Entrega Real:</strong> {seguimiento.fecha_entrega_real.strftime("%d/%m/%Y")}</small><br>' if seguimiento.fecha_entrega_real else ''}
            </p>
            
            <!-- NUEVO: Piezas Vinculadas -->
            {'<div class="mt-2 p-2" style="background-color: rgba(13, 110, 253, 0.05); border-left: 3px solid #0d6efd; border-radius: 4px;"><small class="text-primary fw-bold"><i class="bi bi-box-seam"></i> Piezas Vinculadas:</small><ul class="list-unstyled mb-0 mt-1">' + ''.join([f'<li class="small text-muted"><i class="bi bi-check2"></i> {pieza.componente.nombre} × {pieza.cantidad}</li>' for pieza in seguimiento.piezas.all()]) + '</ul></div>' if seguimiento.piezas.exists() else ''}
            
            {f'<div class="alert alert-danger alert-sm mb-2"><strong>⚠️ RETRASO:</strong> {retraso_dias} días</div>' if hay_retraso else ''}
            
            {f'<p class="card-text"><small class="text-muted"><strong>Notas:</strong> {seguimiento.notas_seguimiento}</small></p>' if seguimiento.notas_seguimiento else ''}
            
            <div class="mt-3">
                <!-- Fila 1: Cambio rápido de estado -->
                {f'''
                <div class="btn-group btn-group-sm w-100 mb-2" role="group">
                    {f'<button type="button" class="btn btn-info" onclick="cambiarEstadoSeguimiento({seguimiento.id}, \'confirmado\')" title="Confirmar pedido">✅ Confirmar</button>' if seguimiento.estado == 'pedido' else ''}
                    {f'<button type="button" class="btn btn-warning" onclick="cambiarEstadoSeguimiento({seguimiento.id}, \'transito\')" title="Marcar en tránsito">� En Tránsito</button>' if seguimiento.estado in ['pedido', 'confirmado'] else ''}
                    {f'<button type="button" class="btn btn-danger" onclick="cambiarEstadoSeguimiento({seguimiento.id}, \'retrasado\')" title="Marcar como retrasado">⚠️ Retrasado</button>' if seguimiento.estado in ['pedido', 'confirmado', 'transito'] else ''}
                    <button type="button" class="btn btn-success" onclick="marcarRecibido({seguimiento.id})" title="Marcar como recibido">📬 Recibido</button>
                </div>
                ''' if seguimiento.estado not in ['recibido', 'incorrecto', 'danado'] else ''}
                
                <!-- Fila 2: Reportar problemas con pieza recibida (NUEVO Nov 2025) -->
                {f'''
                <div class="btn-group btn-group-sm w-100 mb-2" role="group">
                    <button type="button" class="btn btn-outline-danger" onclick="marcarIncorrecto({seguimiento.id})" title="La pieza recibida es incorrecta">
                        ❌ Pieza Incorrecta
                    </button>
                    <button type="button" class="btn btn-outline-warning" onclick="marcarDanado({seguimiento.id})" title="La pieza recibida está dañada o no funciona">
                        ⚠️ Pieza Dañada
                    </button>
                </div>
                ''' if seguimiento.estado == 'recibido' else ''}
                
                <!-- Fila 3: Editar, Eliminar y Reenviar -->
                <div class="btn-group btn-group-sm w-100" role="group">
                    <button type="button" class="btn btn-outline-primary" onclick="editarSeguimiento({seguimiento.id})" title="Editar">
                        📝 Editar
                    </button>
                    <button type="button" class="btn btn-outline-danger" onclick="eliminarSeguimiento({seguimiento.id})" title="Eliminar">
                        🗑️ Eliminar
                    </button>
                    {f'<button type="button" class="btn btn-outline-info" onclick="reenviarNotificacion({seguimiento.id})" title="Reenviar notificación al técnico">📧 Reenviar</button>' if seguimiento.estado == 'recibido' else ''}
                </div>
            </div>
        </div>
    </div>
    '''
    
    return html.strip()

