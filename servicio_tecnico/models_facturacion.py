"""
Documentos fiscales (CFDI) del autofacturador VO.

Objetivo de negocio:
    El cliente entra al portal del facturador, teclea un "webId" y pide su
    factura. SIGMA es quien decide QUÉ se puede facturar, con qué descripción
    y por cuánto. Esta tabla guarda esa decisión y, cuando VO timbra, el XML,
    el PDF y el UUID del SAT.

EXPLICACIÓN PARA PRINCIPIANTES — tres documentos, dos métodos SAT:
    * pue (webId -1): el diagnóstico, siempre pago en una sola exhibición.
    * pue_rep (webId -3): la reparación o los servicios pagados de contado.
      También es PUE ante el SAT (tipo_factura 1). El sufijo los distingue
      porque el diagnóstico se timbra al ingresar y la reparación, después.
    * ppd (webId -2): el anticipo. Es el único PPD.

    Una orden puede tener el diagnóstico y, además, el anticipo o el pago
    de contado. Por eso esto es una tabla hija y no un campo de la orden.

CRITICAL — este archivo es TABLA, no cerebro:
    Aquí solo van campos, choices y __str__. Los cálculos de dinero, el armado
    de conceptos y la generación del webId viven en services/ (ver
    facturacion_documentos.py y facturacion_web_id.py).
"""

from decimal import Decimal

from django.db import models


def cfdi_xml_upload_path(instance, filename):
    """
    Ruta del XML del CFDI dentro de MEDIA_ROOT.

    Args:
        instance: DocumentoFiscalOrden dueño del archivo.
        filename: Nombre sugerido (uuid.xml).

    Returns:
        str: facturacion/<orden_id>/cfdi/<filename>
    """
    return f'facturacion/{instance.orden_id}/cfdi/{filename}'


def cfdi_pdf_upload_path(instance, filename):
    """
    Ruta del PDF de la factura dentro de MEDIA_ROOT.

    Args:
        instance: DocumentoFiscalOrden dueño del archivo.
        filename: Nombre sugerido (uuid.pdf).

    Returns:
        str: facturacion/<orden_id>/pdf/<filename>
    """
    return f'facturacion/{instance.orden_id}/pdf/{filename}'


class DocumentoFiscalOrden(models.Model):
    """
    Un documento facturable (PUE o PPD) de una orden de servicio.

    Args/campos:
        orden: orden de servicio dueña del documento (varios por orden).
        web_id: texto público que el cliente teclea en el portal (SAT9596-1).
        tipo: 'pue' (diagnóstico), 'pue_rep' (reparación de contado) o 'ppd'.
        descripcion: texto del concepto principal, ya resuelto por el servicio.
        subtotal / iva / total / tasa_iva: montos congelados al momento de
            quedar disponible; una vez timbrado ya no se recalculan.
        disponible_desde: cuándo el pago quedó validado y el cliente pudo ver
            el webId. Vacío = todavía no se le muestra a nadie.
        solicitado_en: cuándo el portal hizo el GET (requisito del PUT).
        uuid y archivos: se llenan en el PUT, cuando VO ya timbró.

    Efectos secundarios:
        Ninguno en save(). Historial y avisos los escriben los servicios.
    """

    # ── Tipos de comprobante ────────────────────────────────────────────────
    TIPO_PUE = 'pue'
    TIPO_PUE_REPARACION = 'pue_rep'
    TIPO_PPD = 'ppd'
    TIPO_CHOICES = [
        (TIPO_PUE, 'PUE — Diagnóstico'),
        (TIPO_PUE_REPARACION, 'PUE — Pago en una sola exhibición'),
        (TIPO_PPD, 'PPD — Anticipo'),
    ]

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # tipo_factura le dice a VO el método SAT: 1 = PUE, 2 = PPD. Los dos
    # documentos de contado comparten el 1. El sufijo del webId es otra cosa:
    # -1 diagnóstico, -2 anticipo, -3 reparación pagada de contado.
    CODIGO_TIPO = {
        TIPO_PUE: 1,
        TIPO_PUE_REPARACION: 1,
        TIPO_PPD: 2,
    }
    SUFIJO_TIPO = {
        TIPO_PUE: 1,
        TIPO_PPD: 2,
        TIPO_PUE_REPARACION: 3,
    }

    orden = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.CASCADE,
        related_name='documentos_fiscales',
        help_text='Orden cuya venta se factura',
    )
    web_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text='Identificador público del portal (ej. SAT9596-1)',
    )
    tipo = models.CharField(
        max_length=16,
        choices=TIPO_CHOICES,
        help_text='pue (diagnóstico), pue_rep (contado de la reparación) o ppd',
    )
    descripcion = models.CharField(
        max_length=200,
        help_text='Texto del concepto: Diagnóstico, Limpieza y Mantenimiento, Anticipo…',
    )

    # ── Montos congelados ───────────────────────────────────────────────────
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Guardamos los tres números por separado (antes de IVA, IVA y total) para
    # que el portal no tenga que calcular nada y para que quede evidencia de
    # cuánto se facturó, aunque después alguien edite precios en la orden.
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Importe antes de IVA',
    )
    tasa_iva = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal('0.1600'),
        help_text='Tasa de IVA aplicada (0.1600 = 16%)',
    )
    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Importe del IVA trasladado',
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Subtotal + IVA (lo que se factura)',
    )
    moneda = models.CharField(
        max_length=3,
        default='MXN',
        help_text='Moneda del comprobante (hoy siempre MXN)',
    )

    # ── Ciclo de vida ───────────────────────────────────────────────────────
    disponible_desde = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuándo se validó el pago y el cliente pudo ver el webId',
    )
    solicitado_en = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Momento del GET del portal. Sin esto el PUT responde 404.',
    )

    # ── Timbrado (lo llena el PUT de VO) ────────────────────────────────────
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

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Documento fiscal de orden'
        verbose_name_plural = 'Documentos fiscales de órdenes'
        ordering = ['orden_id', 'tipo']
        constraints = [
            # Una orden factura como máximo un documento de cada tipo
            # (diagnóstico, reparación de contado y anticipo).
            models.UniqueConstraint(
                fields=['orden', 'tipo'],
                name='unico_documento_fiscal_por_tipo',
            ),
            models.UniqueConstraint(
                fields=['uuid'],
                condition=models.Q(uuid__gt=''),
                name='unico_cfdi_uuid_sat',
            ),
        ]

    def __str__(self):
        estado = self.uuid or 'pendiente de timbrar'
        return f'{self.get_tipo_display()} {self.web_id} ({estado})'

    @property
    def esta_timbrado(self) -> bool:
        """True si ya llegó un UUID del SAT (el documento ya no se recalcula)."""
        return bool((self.uuid or '').strip())

    @property
    def codigo_tipo(self) -> int:
        """Número SAT que el API expone a VO: 1 = PUE, 2 = PPD."""
        return self.CODIGO_TIPO.get(self.tipo, 0)


class ConceptoDocumentoFiscal(models.Model):
    """
    Una línea del documento fiscal (un servicio facturado).

    Objetivo: el PUE de mostrador puede llevar varios servicios (Limpieza,
    kit, respaldo). El del diagnóstico y el PPD llevan una sola línea.

    Args/campos:
        documento: documento fiscal dueño de la línea.
        descripcion: texto que ve el cliente en la factura.
        clave_sat / clave_unidad: catálogos del SAT que exige el CFDI.
        cantidad / precio_unitario / importe: montos antes de IVA.

    Efectos secundarios:
        Ninguno. Las líneas las arma facturacion_documentos.py.
    """

    documento = models.ForeignKey(
        DocumentoFiscalOrden,
        on_delete=models.CASCADE,
        related_name='conceptos',
        help_text='Documento fiscal al que pertenece la línea',
    )
    descripcion = models.CharField(
        max_length=200,
        help_text='Texto del concepto tal como aparece en la factura',
    )
    clave_sat = models.CharField(
        max_length=12,
        help_text='ClaveProdServ del SAT (ej. 81111812 servicios técnicos)',
    )
    clave_unidad = models.CharField(
        max_length=6,
        help_text='ClaveUnidad del SAT (ej. E48 unidad de servicio)',
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
    )
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Precio antes de IVA',
    )
    importe = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='cantidad × precio_unitario (antes de IVA)',
    )
    orden_linea = models.PositiveSmallIntegerField(
        default=1,
        help_text='Posición de la línea dentro del documento',
    )

    class Meta:
        verbose_name = 'Concepto de documento fiscal'
        verbose_name_plural = 'Conceptos de documentos fiscales'
        ordering = ['documento_id', 'orden_linea', 'id']

    def __str__(self):
        return f'{self.descripcion} — ${self.importe}'
