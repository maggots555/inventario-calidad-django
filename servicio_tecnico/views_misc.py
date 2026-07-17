"""
Vistas misceláneas de Servicio Técnico (Fase 1 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
- acceso_denegado: página amigable cuando falta un permiso (la usa el decorador).
- actualizar_email_cliente: AJAX del modal de diagnóstico para cambiar el email.

urls.py sigue usando views.acceso_denegado / views.actualizar_email_cliente
porque views.py reexporta estos nombres.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import DetalleEquipo

logger = logging.getLogger(__name__)


@login_required
def acceso_denegado(request):
    """
    Vista para mostrar página de acceso denegado cuando el usuario no tiene permisos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista se muestra cuando un usuario intenta acceder a una funcionalidad
    para la cual no tiene los permisos necesarios según su grupo/rol.

    Args:
        request: Objeto HttpRequest con los parámetros GET
            - mensaje: Mensaje personalizado de error
            - permiso: Nombre del permiso requerido

    Returns:
        HttpResponse: Renderiza el template acceso_denegado.html
    """
    mensaje = request.GET.get('mensaje', 'No tienes permisos para acceder a esta sección.')
    permiso = request.GET.get('permiso', 'N/A')

    # Obtener grupos del usuario para mostrarle sus roles actuales
    grupos = request.user.groups.all()

    context = {
        'mensaje': mensaje,
        'permiso_requerido': permiso,
        'grupos_usuario': grupos,
    }

    return render(request, 'servicio_tecnico/acceso_denegado.html', context)


@login_required
@require_http_methods(["POST"])
def actualizar_email_cliente(request, detalle_id):
    """
    Vista AJAX para actualizar el email del cliente desde el modal de diagnóstico.

    EXPLICACIÓN PARA PRINCIPIANTES:
    - Esta vista recibe un POST con el nuevo email del cliente
    - Valida que el email sea válido y lo guarda en la base de datos
    - Retorna un JSON con el resultado (éxito o error)
    - Se usa desde el botón "Editar" en la sección de destinatario del modal

    Args:
        request: Petición HTTP con el nuevo email en el body
        detalle_id: ID del DetalleEquipo a actualizar

    Returns:
        JsonResponse: JSON con success=True/False y mensaje

    Efectos secundarios:
        Actualiza DetalleEquipo.email_cliente en la base de datos.
    """
    try:
        detalle = get_object_or_404(DetalleEquipo, pk=detalle_id)

        # Obtener el nuevo email del body (JSON)
        try:
            body = json.loads(request.body)
            nuevo_email = body.get('email', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de datos inválido.'
            }, status=400)

        # Validar que el email no esté vacío
        if not nuevo_email:
            return JsonResponse({
                'success': False,
                'error': 'El email no puede estar vacío.'
            }, status=400)

        # Validar formato básico del email
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_email(nuevo_email)
        except DjangoValidationError:
            return JsonResponse({
                'success': False,
                'error': 'El formato del email no es válido. Ejemplo: usuario@dominio.com'
            }, status=400)

        # Validar que no sea el email por defecto
        if nuevo_email == 'cliente@ejemplo.com':
            return JsonResponse({
                'success': False,
                'error': 'No puedes usar el email por defecto. Ingresa un email real.'
            }, status=400)

        # Guardar el email anterior para el log
        email_anterior = detalle.email_cliente

        # Actualizar el email
        detalle.email_cliente = nuevo_email
        detalle.save(update_fields=['email_cliente'])

        # Log del cambio
        nombre_empleado = ''
        if hasattr(request.user, 'empleado') and request.user.empleado:
            nombre_empleado = request.user.empleado.nombre_completo

        logger.info(
            f'Email del cliente actualizado por {nombre_empleado} ({request.user.username}): '
            f'"{email_anterior}" → "{nuevo_email}" | '
            f'Orden: {detalle.orden.numero_orden_interno if hasattr(detalle, "orden") else "N/A"} | '
            f'DetalleEquipo PK: {detalle.pk}'
        )

        return JsonResponse({
            'success': True,
            'mensaje': f'Email actualizado correctamente.',
            'email': nuevo_email,
            'email_anterior': email_anterior,
        })

    except Exception as e:
        logger.error(f'Error al actualizar email del cliente: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }, status=500)
