"""
SeguimientoPieza también para Venta Mostrador (FL / reacondicionado).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1. Añadimos ``orden`` nullable + hacemos ``cotizacion`` nullable.
2. Backfill: cada seguimiento existente hereda orden desde cotizacion.orden.
3. ``orden`` pasa a NOT NULL.
4. M2M ``piezas_venta_mostrador`` + OneToOne ``PiezaVentaMostrador.linea_cotizacion``.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_orden_desde_cotizacion(apps, schema_editor):
    """
    Rellena SeguimientoPieza.orden_id desde cotizacion.orden_id.

    Cotizacion usa OrdenServicio como PK (OneToOne primary_key=True),
    así que cotizacion_id == orden_id en la práctica.
    """
    SeguimientoPieza = apps.get_model('servicio_tecnico', 'SeguimientoPieza')
    actualizados = 0
    # Paso 1: recorrer solo los que aún no tienen orden
    for seguimiento in SeguimientoPieza.objects.filter(orden_id__isnull=True).iterator():
        if seguimiento.cotizacion_id is None:
            # No debería ocurrir en datos legacy (cotizacion era NOT NULL)
            continue
        # Paso 2: en Cotizacion el PK es la orden → cotizacion_id es el pk de OrdenServicio
        seguimiento.orden_id = seguimiento.cotizacion_id
        seguimiento.save(update_fields=['orden_id'])
        actualizados += 1
    if actualizados:
        print(f"[0060] Backfill orden en {actualizados} SeguimientoPieza")


def noop_reverse(apps, schema_editor):
    """Reverse vacío: no borramos orden al revertir."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0031_helptext_precios_primera_respuesta'),
        ('servicio_tecnico', '0059_analisis_sentimiento_tipo_encuesta'),
    ]

    operations = [
        # --- Paso A: schema flexible (orden nullable) ---
        migrations.AddField(
            model_name='seguimientopieza',
            name='orden',
            field=models.ForeignKey(
                help_text=(
                    'Orden de servicio a la que pertenece este seguimiento '
                    '(obligatoria; sirve para FL sin Cotizacion ST).'
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seguimientos_piezas',
                to='servicio_tecnico.ordenservicio',
            ),
        ),
        migrations.AlterField(
            model_name='seguimientopieza',
            name='cotizacion',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Cotización ST asociada (nullable). En órdenes FL / venta mostrador '
                    'queda vacío porque no se crea Cotizacion.'
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seguimientos_piezas',
                to='servicio_tecnico.cotizacion',
            ),
        ),
        migrations.AddField(
            model_name='seguimientopieza',
            name='piezas_venta_mostrador',
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    'Piezas de Venta Mostrador (FL / reacondicionado) '
                    'rastreadas en este pedido'
                ),
                related_name='seguimientos',
                to='servicio_tecnico.piezaventamostrador',
            ),
        ),
        migrations.AddField(
            model_name='piezaventamostrador',
            name='linea_cotizacion',
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    'Línea de cotización Almacén que originó esta pieza '
                    '(NULL si se agregó manualmente en ST).'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pieza_venta_mostrador',
                to='almacen.lineacotizacion',
            ),
        ),
        migrations.AlterField(
            model_name='seguimientopieza',
            name='piezas',
            field=models.ManyToManyField(
                blank=True,
                help_text='Piezas cotizadas (OOW) que se están rastreando en este pedido',
                related_name='seguimientos',
                to='servicio_tecnico.piezacotizada',
            ),
        ),
        # --- Paso B: backfill ---
        migrations.RunPython(backfill_orden_desde_cotizacion, noop_reverse),
        # --- Paso C: orden obligatoria ---
        migrations.AlterField(
            model_name='seguimientopieza',
            name='orden',
            field=models.ForeignKey(
                help_text=(
                    'Orden de servicio a la que pertenece este seguimiento '
                    '(obligatoria; sirve para FL sin Cotizacion ST).'
                ),
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seguimientos_piezas',
                to='servicio_tecnico.ordenservicio',
            ),
        ),
        migrations.AddIndex(
            model_name='seguimientopieza',
            index=models.Index(
                fields=['orden', 'estado'],
                name='servicio_te_orden_i_7e2a1b_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='seguimientopieza',
            index=models.Index(
                fields=['-fecha_pedido'],
                name='servicio_te_fecha_p_9c4d2e_idx',
            ),
        ),
    ]
