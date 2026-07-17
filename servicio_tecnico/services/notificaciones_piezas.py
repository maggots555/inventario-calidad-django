"""
Notificación por email/push cuando una pieza se marca como recibida (Fase 6).

EXPLICACIÓN PARA PRINCIPIANTES:
Antes vivía en views.py y Almacén la importaba así:
  from servicio_tecnico.views import _enviar_notificacion_pieza_recibida
Eso acoplaba Almacén al monolito. Ahora vive en services/ (igual que historial).
Import correcto (Almacén y vistas AJAX):
  from servicio_tecnico.services.notificaciones_piezas import (
      enviar_notificacion_pieza_recibida,
  )
views.py aún reexporta el alias _enviar_... por compatibilidad.

Efectos secundarios:
  - Envía EmailMessage al técnico (+ CC jefe / JEFE_CALIDAD_EMAIL)
  - Intenta Web Push al usuario del técnico (fail-safe)
  - NO escribe HistorialOrden (eso lo hace quien llama)
"""

from decouple import config
from django.urls import reverse


def enviar_notificacion_pieza_recibida(orden, seguimiento):
    """
    Envía email al técnico notificando que una pieza fue recibida
    
    RETORNA:
    dict con 'success': True/False, 'message': str, 'destinatarios': list
    
    Args:
        orden (OrdenServicio): Orden de servicio
        seguimiento (SeguimientoPieza): Seguimiento de la pieza recibida
    
    Returns:
        dict: Estado del envío con detalles
            {
                'success': True,
                'message': 'Email enviado correctamente',
                'destinatarios': ['tecnico@sic.com', 'jefe@sic.com'],
                'destinatarios_copia': ['calidad@sic.com']
            }
    """
    from django.core.mail import EmailMessage
    from django.conf import settings
    import os
    
    try:
        # =================================================================
        # VALIDACIÓN 1: Verificar que hay técnico asignado con email
        # =================================================================
        if not orden.tecnico_asignado_actual:
            return {
                'success': False,
                'message': '⚠️ La orden no tiene técnico asignado',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        if not orden.tecnico_asignado_actual.email:
            return {
                'success': False,
                'message': f'⚠️ El técnico {orden.tecnico_asignado_actual.nombre_completo} no tiene email configurado',
                'destinatarios': [],
                'destinatarios_copia': []
            }
        
        # =================================================================
        # CONSTRUCCIÓN DE DESTINATARIOS
        # =================================================================
        destinatarios_principales = [orden.tecnico_asignado_actual.email]
        destinatarios_copia = []
        
        # Agregar jefe directo del técnico (si existe y tiene email)
        if (orden.tecnico_asignado_actual.jefe_directo and 
            orden.tecnico_asignado_actual.jefe_directo.email):
            destinatarios_copia.append(orden.tecnico_asignado_actual.jefe_directo.email)
        
        # IMPORTANTE: Agregar Jefe de Calidad desde .env
        # Este email SIEMPRE debe estar en copia
        jefe_calidad_email = config('JEFE_CALIDAD_EMAIL', default='').strip()
        if jefe_calidad_email:
            # Evitar duplicados (por si el jefe directo es el mismo que el jefe de calidad)
            if jefe_calidad_email not in destinatarios_copia:
                destinatarios_copia.append(jefe_calidad_email)
                print(f"🔔 Agregando Jefe de Calidad en CC: {jefe_calidad_email}")
        else:
            print("⚠️ ADVERTENCIA: JEFE_CALIDAD_EMAIL no está configurado en .env")
        
        # =================================================================
        # CONSTRUCCIÓN DEL EMAIL
        # =================================================================
        # Obtener nombre del técnico (solo primer nombre)
        nombre_tecnico = orden.tecnico_asignado_actual.nombre_completo.split()[0]
        
        # Obtener información del equipo
        detalle = orden.detalle_equipo
        orden_cliente = detalle.orden_cliente if detalle.orden_cliente else 'Sin orden de cliente'
        
        # =================================================================
        # CONSULTAR PIEZAS PENDIENTES DE OTROS PROVEEDORES
        # =================================================================
        # NUEVA FUNCIONALIDAD (Octubre 2025):
        # Consultar TODOS los seguimientos de la misma cotización
        # y filtrar solo los que NO estén recibidos (estados pendientes)
        from django.utils import timezone
        
        cotizacion = seguimiento.cotizacion
        seguimientos_pendientes = cotizacion.seguimientos_piezas.exclude(
            estado__in=['recibido', 'incorrecto', 'danado']
        ).exclude(
            id=seguimiento.id  # Excluir el seguimiento actual (que acaba de ser recibido)
        )
        
        # Construir sección de piezas pendientes si existen
        seccion_piezas_pendientes = ""
        
        if seguimientos_pendientes.exists():
            seccion_piezas_pendientes = "\n\n⚠️ PIEZAS PENDIENTES DE OTROS PROVEEDORES\n"
            seccion_piezas_pendientes += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            hoy = timezone.now().date()
            
            for seg_pendiente in seguimientos_pendientes:
                # Calcular días de retraso (si aplica)
                info_retraso = ""
                if seg_pendiente.fecha_entrega_estimada:
                    if hoy > seg_pendiente.fecha_entrega_estimada:
                        dias_retraso = (hoy - seg_pendiente.fecha_entrega_estimada).days
                        info_retraso = f" ⏰ RETRASADO {dias_retraso} días"
                    else:
                        dias_restantes = (seg_pendiente.fecha_entrega_estimada - hoy).days
                        info_retraso = f" (Estimado en {dias_restantes} días)"
                
                # Obtener estado legible
                estado_display = seg_pendiente.get_estado_display()
                
                # Obtener piezas vinculadas a este seguimiento
                piezas_vinculadas = seg_pendiente.piezas.all()
                if piezas_vinculadas.exists():
                    descripcion_piezas = ", ".join([f"{p.componente.nombre} × {p.cantidad}" for p in piezas_vinculadas])
                else:
                    descripcion_piezas = seg_pendiente.descripcion_piezas
                
                seccion_piezas_pendientes += f"\n• Proveedor: {seg_pendiente.proveedor}\n"
                seccion_piezas_pendientes += f"  Estado: {estado_display}{info_retraso}\n"
                seccion_piezas_pendientes += f"  Descripción: {descripcion_piezas}\n"
                if seg_pendiente.fecha_entrega_estimada:
                    seccion_piezas_pendientes += f"  Fecha estimada: {seg_pendiente.fecha_entrega_estimada.strftime('%d/%m/%Y')}\n"
            
            seccion_piezas_pendientes += "\n💡 NOTA: Aún hay piezas en camino. Te notificaremos cuando lleguen.\n"
        
        # Construir asunto
        asunto = f'📬 Pieza Recibida - Orden Cliente: {orden_cliente}'
        
        # Construir cuerpo del mensaje
        mensaje = f'''Hola {nombre_tecnico},

Te informamos que ha llegado una pieza para la orden que tienes asignada:

📋 INFORMACIÓN DE LA ORDEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Orden Cliente: {orden_cliente}
• Orden Interna: {orden.numero_orden_interno}
• Equipo: {detalle.get_tipo_equipo_display()} {detalle.marca} {detalle.modelo}
• N° Serie: {detalle.numero_serie}
• Estado actual: {orden.get_estado_display()}

📦 PIEZA RECIBIDA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Proveedor: {seguimiento.proveedor}
• Descripción: {seguimiento.descripcion_piezas}
• Fecha de recepción: {seguimiento.fecha_entrega_real.strftime('%d/%m/%Y')}
{f'• Número de pedido: {seguimiento.numero_pedido}' if seguimiento.numero_pedido else ''}{seccion_piezas_pendientes}

✅ PRÓXIMOS PASOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Recoge la pieza en almacén
2. {"Verifica si puedes proceder con esta pieza o espera las pendientes" if seguimientos_pendientes.exists() else "Actualiza el estado de la orden a 'En reparación'"}
3. Instala y verifica la pieza
4. Actualiza el progreso en el sistema

---
Sistema de Servicio Técnico SIC
Este es un mensaje automático. Si tienes dudas, contacta al responsable del seguimiento.
Hecho por Jorge Magos todos los derechos reservados.
'''
        
        # =================================================================
        # ENVÍO DEL EMAIL
        # =================================================================
        # Usar remitente personalizado para Servicio Técnico (si existe)
        # Si no existe, usar el remitente por defecto del sistema
        # IMPORTANTE: Usar config() de python-decouple, NO os.getenv()
        # os.getenv() solo lee variables del sistema, NO del archivo .env
        from_email = config('SERVICIO_TECNICO_FROM_EMAIL', default=settings.DEFAULT_FROM_EMAIL)
        
        email = EmailMessage(
            subject=asunto,
            body=mensaje,
            from_email=from_email,
            to=destinatarios_principales,
            cc=destinatarios_copia if destinatarios_copia else None,
        )
        
        email.send(fail_silently=False)
        
        # Log exitoso
        print(f"✅ Email enviado correctamente")
        print(f"   TO: {', '.join(destinatarios_principales)}")
        if destinatarios_copia:
            print(f"   CC: {', '.join(destinatarios_copia)}")
        
        # =================================================================
        # NOTIFICACIÓN PUSH AL TÉCNICO
        # =================================================================
        # Complementa el correo con una notificación push inmediata.
        # Se ejecuta en try/except propio para que un fallo de push NUNCA
        # bloquee ni revierta el envío del correo ya realizado.
        try:
            from notificaciones.push_service import enviar_push_a_usuario
            tecnico_user = orden.tecnico_asignado_actual.user
            url_orden = reverse('servicio_tecnico:detalle_orden', args=[orden.pk])
            # Truncar descripción a 100 chars para que quepa bien en la notificación
            descripcion_corta = seguimiento.descripcion_piezas[:100]
            if len(seguimiento.descripcion_piezas) > 100:
                descripcion_corta += '...'
            enviados = enviar_push_a_usuario(
                usuario=tecnico_user,
                titulo=f"📬 Pieza recibida — {orden_cliente}",
                mensaje=descripcion_corta,
                url=url_orden,
            )
            print(f"🔔 Push enviado a {enviados} dispositivo(s) de {tecnico_user.username}")
        except Exception as e_push:
            # El push falló pero el correo ya fue enviado — no es crítico
            print(f"⚠️ [PUSH] No se pudo notificar llegada de pieza: {e_push}")
        
        return {
            'success': True,
            'message': 'Email enviado correctamente',
            'destinatarios': destinatarios_principales,
            'destinatarios_copia': destinatarios_copia
        }
    
    except Exception as e:
        # Log de error
        print(f"❌ Error al enviar email de notificación: {str(e)}")
        
        return {
            'success': False,
            'message': f'Error al enviar email: {str(e)}',
            'destinatarios': [],
            'destinatarios_copia': [],
            'error_detalle': str(e)
        }

# Alias con guion bajo: compatibilidad con código que aún use el nombre antiguo
_enviar_notificacion_pieza_recibida = enviar_notificacion_pieza_recibida
