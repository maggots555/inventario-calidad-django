# Migración: campos para cotización de equipos reacondicionados

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0025_precios_cliente_cotizacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='modo_cotizacion_cliente',
            field=models.CharField(
                blank=True,
                choices=[
                    ('reparacion', 'Reparación'),
                    ('reacondicionado', 'Equipo reacondicionado'),
                ],
                default='reparacion',
                help_text='Reparación por piezas o propuesta de equipo reacondicionado',
                max_length=20,
                verbose_name='Modo de cotización enviada',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='costo_proveedor_reac',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Costo de adquisición del equipo sin IVA',
                max_digits=12,
                null=True,
                verbose_name='Costo proveedor (reacondicionado)',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='dias_front_desk_reac',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='Días proporcionales de recurso front desk para el costeo',
                verbose_name='Días front desk (reacondicionado)',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_marca',
            field=models.CharField(blank=True, max_length=100, verbose_name='Marca equipo ofertado'),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_modelo',
            field=models.CharField(blank=True, max_length=150, verbose_name='Modelo equipo ofertado'),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_procesador',
            field=models.CharField(blank=True, max_length=150, verbose_name='Procesador equipo ofertado'),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_ram',
            field=models.CharField(blank=True, max_length=80, verbose_name='RAM equipo ofertado'),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_sistema_operativo',
            field=models.CharField(blank=True, max_length=100, verbose_name='Sistema operativo equipo ofertado'),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_incluye_cargador',
            field=models.BooleanField(
                default=False,
                help_text='Si el equipo reacondicionado incluye cargador original o compatible',
                verbose_name='Incluye cargador',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='reac_especificaciones',
            field=models.TextField(
                blank=True,
                help_text='Detalles extra del equipo (almacenamiento, pantalla, etc.)',
                verbose_name='Especificaciones adicionales',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='resultado_costeo_reac',
            field=models.JSONField(
                blank=True,
                help_text='Resultado JSON de calcular_costeo al enviar la propuesta',
                null=True,
                verbose_name='Snapshot costeo reacondicionado',
            ),
        ),
    ]
