"""
Modelos del Formato Digital de Venta Mostrador (Nota de Venta Directa).

Objetivo de negocio:
    Guardar el wizard (borrador/finalizado), firmas opcionales, daños
    opcionales y el PDF generado, SIN hinchar models.py (~4500 LOC).

EXPLICACIÓN PARA PRINCIPIANTES:
    Django solo “ve” modelos que se importan desde models.py. Por eso
    al final de models.py hay un import de este archivo. Las tablas
    siguen siendo de la app servicio_tecnico.
"""

from django.core.validators import FileExtensionValidator
from django.db import models

from config.constants import ESTADO_FORMATO_OOW_CHOICES, TIPO_DIAGRAMA_OOW_CHOICES


def _orden_ref_formato_vm(orden) -> str:
    """
    Folio de carpeta media: orden_cliente o número interno.

    Args:
        orden: OrdenServicio dueña del formato.

    Returns:
        str: nombre de carpeta seguro (sin slashes).
    """
    # Import diferido: evita ciclo models.py ↔ este archivo al arrancar.
    from servicio_tecnico.models import _resolver_ref_carpeta_orden

    return _resolver_ref_carpeta_orden(orden)


def formato_vm_firma_upload_path(instance, filename):
    """
    Ruta de firmas (entrega CIS / entrega cliente).

    Args:
        instance: FormatoServicioVentaMostrador
        filename: Nombre del PNG (ej. firma_cis.png)

    Returns:
        str: Ruta relativa bajo MEDIA_ROOT
    """
    orden_ref = _orden_ref_formato_vm(instance.orden)
    return f'servicio_tecnico/formato_venta_mostrador/{orden_ref}/firmas/{filename}'


def formato_vm_pdf_upload_path(instance, filename):
    """
    Ruta del PDF de la Nota de Venta Directa.

    Args:
        instance: FormatoServicioVentaMostrador
        filename: Nombre del PDF

    Returns:
        str: Ruta relativa bajo MEDIA_ROOT
    """
    orden_ref = _orden_ref_formato_vm(instance.orden)
    return f'servicio_tecnico/formato_venta_mostrador/{orden_ref}/pdf/{filename}'


def dano_estetico_vm_upload_path(instance, filename):
    """
    Ruta de diagramas anotados (opcionales) del formato VM.

    Args:
        instance: DanoEsteticoVistaVentaMostrador
        filename: PNG del canvas

    Returns:
        str: Ruta relativa bajo MEDIA_ROOT
    """
    orden_ref = _orden_ref_formato_vm(instance.formato.orden)
    return f'servicio_tecnico/formato_venta_mostrador/{orden_ref}/danos/{filename}'


class FormatoServicioVentaMostrador(models.Model):
    """
    Formato digital de Nota de Venta Directa (venta mostrador / FL).

    Objetivo de negocio:
        El de front genera un PDF con lo vendido aunque el equipo aún
        no ingrese. Daños estéticos y firmas son OPCIONALES.

    Relación:
        OneToOne con OrdenServicio (una orden FL = un formato).

    Efectos secundarios:
        Al finalizar se genera y guarda un PDF; opcionalmente se encola
        un correo Celery con el adjunto.
    """

    orden = models.OneToOneField(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.CASCADE,
        related_name='formato_venta_mostrador',
        help_text='Orden de venta mostrador a la que pertenece este formato',
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_FORMATO_OOW_CHOICES,
        default='borrador',
        help_text='Borrador editable o finalizado (PDF generado)',
    )
    tipo_diagrama = models.CharField(
        max_length=20,
        choices=TIPO_DIAGRAMA_OOW_CHOICES,
        default='laptop',
        help_text='Tipo de esquema para marcar daños estéticos (opcional)',
    )

    # Overrides opcionales: DetalleEquipo no tiene “empresa” vs “contacto”
    empresa_cliente = models.CharField(
        max_length=200,
        blank=True,
        help_text='Razón social / empresa (si difiere del nombre del cliente)',
    )
    persona_contacto = models.CharField(
        max_length=200,
        blank=True,
        help_text='Persona de contacto (opcional; si vacío se usa nombre_cliente)',
    )
    numero_cargador = models.CharField(
        max_length=100,
        blank=True,
        help_text='Número de serie / descripción del cargador (opcional)',
    )

    email_envio = models.EmailField(
        blank=True,
        help_text='Correo principal (compatibilidad; ver emails_envio)',
    )
    emails_envio = models.JSONField(
        default=list,
        blank=True,
        help_text='Lista de hasta 3 correos para enviar el PDF',
    )

    firma_entrega_cis = models.ImageField(
        upload_to=formato_vm_firma_upload_path,
        null=True,
        blank=True,
        max_length=255,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg'])],
        help_text='Firma de entrega de equipo en CIS (opcional)',
    )
    firma_entrega_cliente = models.ImageField(
        upload_to=formato_vm_firma_upload_path,
        null=True,
        blank=True,
        max_length=255,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg'])],
        help_text='Firma de entrega de equipo a cliente (opcional)',
    )

    pdf = models.FileField(
        upload_to=formato_vm_pdf_upload_path,
        null=True,
        blank=True,
        max_length=255,
        help_text='PDF generado al finalizar el formato',
    )
    finalizado_en = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Fecha/hora en que se finalizó el formato',
    )

    creado_por = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='formatos_venta_mostrador_creados',
        help_text='Empleado que inició el formato',
    )
    actualizado_por = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='formatos_venta_mostrador_actualizados',
        help_text='Último empleado que guardó el formato',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"Formato VM {self.orden.numero_orden_interno} ({self.estado})"
        )

    class Meta:
        verbose_name = 'Formato de Venta Mostrador'
        verbose_name_plural = 'Formatos de Venta Mostrador'
        ordering = ['-fecha_actualizacion']


class DanoEsteticoVistaVentaMostrador(models.Model):
    """
    Captura anotada opcional de una vista del equipo (pantalla, top cover…).

    Objetivo de negocio:
        Si el equipo SÍ ingresa, el de front puede marcar rayones.
        Si no ingresa, esta tabla queda vacía y el PDF omite diagramas.

    Args/campos:
        formato: FormatoServicioVentaMostrador padre
        clave_vista: Identificador estable (pantalla, top_cover, …)
        etiqueta_dano: Tipo de daño (Rayado, Golpe, …)
        imagen_anotada: PNG del canvas
    """

    formato = models.ForeignKey(
        FormatoServicioVentaMostrador,
        on_delete=models.CASCADE,
        related_name='vistas_dano',
        help_text='Formato de venta mostrador al que pertenece esta vista',
    )
    clave_vista = models.CharField(
        max_length=40,
        help_text='Clave de la vista (pantalla, top_cover, palm, …)',
    )
    etiqueta_dano = models.CharField(
        max_length=80,
        blank=True,
        help_text='Etiqueta del tipo de daño (ej. Rayado)',
    )
    imagen_anotada = models.ImageField(
        upload_to=dano_estetico_vm_upload_path,
        null=True,
        blank=True,
        max_length=255,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg'])],
        help_text='Imagen del diagrama con anotaciones (opcional)',
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.clave_vista} — {self.formato.orden.numero_orden_interno}"

    class Meta:
        verbose_name = 'Vista de daño estético VM'
        verbose_name_plural = 'Vistas de daño estético VM'
        unique_together = [('formato', 'clave_vista')]
        ordering = ['clave_vista']
