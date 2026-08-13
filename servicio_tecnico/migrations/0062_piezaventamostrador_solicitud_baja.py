"""
PiezaVentaMostrador puede nacer de una SolicitudBaja (stock interno).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El campo ``solicitud_baja`` es el espejo de ``linea_cotizacion``:
distingue piezas de cotización, de stock interno y de alta manual en ST.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0035_solicitudcotizacion_plantilla_pnc_front_enviada'),
        ('servicio_tecnico', '0061_rename_seguimiento_pieza_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='piezaventamostrador',
            name='solicitud_baja',
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    'Solicitud de baja de almacén que originó esta pieza '
                    '(NULL si nació de cotización o se agregó a mano en ST).'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pieza_venta_mostrador',
                to='almacen.solicitudbaja',
            ),
        ),
    ]
