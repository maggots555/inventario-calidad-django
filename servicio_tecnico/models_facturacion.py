"""
Comprobante fiscal (CFDI) recibido del autofacturador VO.

Objetivo de negocio:
    Cuando el portal timbra una venta, manda XML y PDF a SIGMA (PUT).
    Esta tabla guarda esos archivos y el UUID del SAT, sin inflar OrdenServicio.

EXPLICACIÓN PARA PRINCIPIANTES:
    El GET del API “reserva” la venta (solicitado_en). El PUT solo se acepta
    si esa reserva existe; si no, 404 como en el PDF de SICSER 4.
"""

from django.db import models


def cfdi_xml_upload_path(instance, filename):
    """
    Ruta del XML del CFDI dentro de MEDIA_ROOT.

    Args:
        instance: ComprobanteFiscalOrden dueño del archivo.
        filename: Nombre sugerido (uuid.xml).

    Returns:
        str: facturacion/<orden_id>/cfdi/<filename>
    """
    return f'facturacion/{instance.orden_id}/cfdi/{filename}'


def cfdi_pdf_upload_path(instance, filename):
    """
    Ruta del PDF de la factura dentro de MEDIA_ROOT.

    Args:
        instance: ComprobanteFiscalOrden dueño del archivo.
        filename: Nombre sugerido (uuid.pdf).
    """
    return f'facturacion/{instance.orden_id}/pdf/{filename}'


class ComprobanteFiscalOrden(models.Model):
    """
    Un CFDI timbrado (o la solicitud previa al timbrado) por orden.

    Args/campos:
        orden: orden de servicio (1 a 1).
        web_id: dígitos de orden_cliente usados en el API.
        solicitado_en: cuándo el portal hizo GET (requisito del PUT).
        uuid / archivos: se llenan en el PUT.

    Efectos secundarios:
        Ninguno en save(). El servicio escribe historial/flags.
    """

    orden = models.OneToOneField(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.CASCADE,
        related_name='comprobante_fiscal',
        help_text='Orden cuya venta se facturó o se está facturando',
    )
    web_id = models.PositiveBigIntegerField(
        db_index=True,
        help_text='Número público del API (dígitos de orden_cliente)',
    )
    solicitado_en = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Momento del GET previo. Sin esto el PUT responde 404.',
    )
    uuid = models.CharField(
        max_length=36,
        blank=True,
        db_index=True,
        help_text='UUID fiscal del SAT (vacío hasta el PUT)',
    )
    fecha_timbrado = models.DateTimeField(
        null=True,
        blank=True,
        help_text='fechaTimbrado del payload VO',
    )
    cadena_original_sat = models.TextField(blank=True)
    no_certificado_sat = models.CharField(max_length=40, blank=True)
    no_certificado_cfdi = models.CharField(max_length=40, blank=True)
    sello_sat = models.TextField(blank=True)
    sello_cfdi = models.TextField(blank=True)
    qr_code = models.TextField(
        blank=True,
        help_text='QR del timbrado (texto o base64, como lo manda VO)',
    )
    cfdi_xml = models.FileField(
        upload_to=cfdi_xml_upload_path,
        max_length=255,
        blank=True,
        help_text='XML del CFDI (campo cfdi del PUT)',
    )
    pdf = models.FileField(
        upload_to=cfdi_pdf_upload_path,
        max_length=255,
        blank=True,
        help_text='PDF de la factura (campo pdf64 del PUT, base64)',
    )
    recibido_en = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuándo SIGMA aceptó el PUT timbrado',
    )

    class Meta:
        verbose_name = 'Comprobante fiscal de orden'
        verbose_name_plural = 'Comprobantes fiscales de órdenes'
        constraints = [
            models.UniqueConstraint(
                fields=['uuid'],
                condition=models.Q(uuid__gt=''),
                name='unico_cfdi_uuid_sat',
            ),
        ]

    def __str__(self):
        estado = self.uuid or 'pendiente de timbrar'
        return f'CFDI web_id={self.web_id} ({estado})'

    @property
    def esta_timbrado(self) -> bool:
        """True si ya llegó un UUID del SAT."""
        return bool((self.uuid or '').strip())
