"""
Modelos del historial de rondas de cotización (recotización)
=============================================================

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Una cotización que enviamos al cliente tiene vigencia de **5 días hábiles**.
Si el cliente no contesta en ese plazo y después quiere aceptar, los precios
ya no sirven: hay que pedirle a Compras que confirme si la pieza sigue
disponible y a qué costo. A ese "volver a cotizar" le llamamos RECOTIZACIÓN.

Cuando eso pasa NO creamos una solicitud nueva: reciclamos la misma
``SolicitudCotizacion`` (mismo folio SOL-XXXX) y subimos su contador
``ronda_cotizacion``. Pero antes de borrar los precios viejos guardamos una
"foto" (snapshot) de cómo estaba la cotización en esa ronda. Esa foto es
justamente este modelo: ``RondaCotizacion``.

¿Para qué sirve la foto?
- Comparar cuánto subió el costo entre la ronda 1 y la ronda 2.
- Auditar qué se le ofreció al cliente y cuándo venció.
- No perder el precio congelado que ya se le había comunicado.

¿Por qué este modelo vive en un archivo aparte y no en ``models.py``?
``almacen/models.py`` ya pasa de 6,400 líneas. La regla del proyecto es no
seguir engordándolo. Django solo autodescubre el módulo ``models`` de cada
app, así que al FINAL de ``almacen/models.py`` hay un import de este archivo
para que Django registre la tabla y genere su migración.
"""

from decimal import Decimal

from django.db import models


class RondaCotizacion(models.Model):
    """
    Snapshot histórico de una ronda de cotización ya cerrada.

    Objetivo principal (contexto de negocio):
        Conservar los costos y precios que se le ofrecieron al cliente en una
        ronda antes de que la solicitud se recotice (ronda siguiente) o se
        cierre por respuesta del cliente. Es el "antes" contra el que se
        compara el "después" cuando Compras vuelve a cotizar.

    Argumentos/parámetros (campos principales):
        solicitud (FK SolicitudCotizacion): Cotización dueña de la ronda.
        numero_ronda (int): 1 para la primera cotización, 2 tras recotizar, etc.
        fecha_inicio_vigencia / fecha_vencimiento (datetime): Ventana de los
            5 días hábiles que tuvo esa ronda.
        motivo_cierre (str): Por qué terminó la ronda (ver MOTIVO_CIERRE_CHOICES).
        snapshot_lineas / snapshot_servicios (list[dict]): Copia de las piezas y
            servicios con sus costos y precios al cliente en ese momento.

    Efectos secundarios:
        Ninguno: es una tabla de solo lectura una vez creada. La escribe
        ``almacen/utils/recotizacion.py`` al iniciar una ronda nueva.
    """

    # ========== MOTIVOS POR LOS QUE SE CIERRA UNA RONDA ==========
    # EXPLICACIÓN: una ronda termina de tres formas posibles. Guardar cuál fue
    # nos permite después contar cuántas cotizaciones se pierden por vigencia.
    MOTIVO_CIERRE_CHOICES = [
        ('recotizacion', 'Cerrada por recotización (vigencia vencida)'),
        ('respuesta_cliente', 'Cerrada por respuesta del cliente'),
        ('cancelada', 'Cerrada por cancelación de la solicitud'),
    ]

    # ========== VINCULACIÓN ==========
    solicitud = models.ForeignKey(
        'almacen.SolicitudCotizacion',
        on_delete=models.CASCADE,
        related_name='rondas',
        verbose_name='Solicitud de Cotización',
        help_text='Cotización a la que pertenece esta ronda'
    )
    numero_ronda = models.PositiveSmallIntegerField(
        verbose_name='Número de Ronda',
        help_text='1 = cotización original, 2 = primera recotización, etc.'
    )

    # ========== VENTANA DE VIGENCIA QUE TUVO LA RONDA ==========
    fecha_inicio_vigencia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Inicio de Vigencia',
        help_text='Cuándo arrancaron los 5 días hábiles de esta ronda'
    )
    fecha_vencimiento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Vencimiento',
        help_text='Fecha límite que tuvo esta ronda'
    )
    fecha_cierre = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Cierre',
        help_text='Cuándo se archivó esta ronda (se creó el snapshot)'
    )
    motivo_cierre = models.CharField(
        max_length=25,
        choices=MOTIVO_CIERRE_CHOICES,
        default='recotizacion',
        verbose_name='Motivo de Cierre',
        help_text='Por qué terminó esta ronda de cotización'
    )

    # ========== SNAPSHOT DE PRECIOS ==========
    # EXPLICACIÓN: un JSONField guarda una lista de diccionarios. Es la forma
    # más barata de conservar el "cómo estaba" sin duplicar tablas enteras de
    # líneas y servicios (que además pueden editarse o borrarse después).
    snapshot_lineas = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Snapshot de Piezas',
        help_text='Copia de las líneas con costo y precio al cliente de esta ronda'
    )
    snapshot_servicios = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Snapshot de Servicios',
        help_text='Copia de los servicios adicionales de esta ronda'
    )

    # ========== TOTALES PARA COMPARACIÓN RÁPIDA ==========
    # EXPLICACIÓN: aunque los totales se pueden recalcular desde el JSON,
    # guardarlos como columnas permite ordenar y comparar en SQL sin abrir
    # cada snapshot (útil en dashboards de "cuánto subió el costo").
    costo_total_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Costo Total (Proveedor)',
        help_text='Suma de cantidad × costo_unitario de todas las piezas'
    )
    precio_cliente_total_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Precio Total al Cliente (sin IVA)',
        help_text='Suma de los precios congelados que vio el cliente'
    )

    # ========== AUDITORÍA ==========
    creada_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rondas_cotizacion_cerradas',
        verbose_name='Cerrada por',
        help_text='Usuario que solicitó la recotización'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Nota opcional de por qué se recotizó'
    )

    class Meta:
        verbose_name = 'Ronda de Cotización'
        verbose_name_plural = 'Rondas de Cotización'
        ordering = ['solicitud', 'numero_ronda']
        # EXPLICACIÓN: una solicitud no puede tener dos rondas con el mismo
        # número. Esto protege contra dobles clics en "Solicitar Recotización".
        unique_together = [('solicitud', 'numero_ronda')]

    def __str__(self):
        """Texto legible en el admin y en logs."""
        return f"{self.solicitud.numero_solicitud} - Ronda {self.numero_ronda}"
