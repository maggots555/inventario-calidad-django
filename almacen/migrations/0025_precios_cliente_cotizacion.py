# Generated manually — precios al cliente en cotizaciones Almacén

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0024_lineaservicioadicional_es_necesaria'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='tipo_servicio_cliente',
            field=models.CharField(
                blank=True,
                choices=[
                    ('mostrador', 'Mostrador'),
                    ('estandar', 'Estándar'),
                    ('express', 'Express'),
                    ('alta_gama', 'Alta Gama'),
                    ('server', 'Server'),
                ],
                default='',
                help_text='Perfil de servicio usado al enviar la cotización por correo/PDF',
                max_length=20,
                verbose_name='Perfil de profit enviado al cliente',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='incluir_descuento_diagnostico_cliente',
            field=models.BooleanField(
                default=True,
                help_text='Si el PDF enviado al cliente incluía descuento de diagnóstico',
                verbose_name='Descontar diagnóstico (envío al cliente)',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='fecha_precios_cliente',
            field=models.DateTimeField(
                blank=True,
                help_text='Cuándo se calcularon y guardaron los precios al cliente (al aprobar)',
                null=True,
                verbose_name='Fecha precios cliente',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='precio_total_sin_iva_cliente',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total cotizado al cliente sin IVA (todas las líneas con costo)',
                max_digits=12,
                null=True,
                verbose_name='Total cliente sin IVA',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='precio_total_con_iva_cliente',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total cotizado al cliente con IVA incluido',
                max_digits=12,
                null=True,
                verbose_name='Total cliente con IVA',
            ),
        ),
        migrations.AddField(
            model_name='solicitudcotizacion',
            name='precio_total_menos_diagnostico_cliente',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total con IVA restando diagnóstico ya pagado (si aplica)',
                max_digits=12,
                null=True,
                verbose_name='Total cliente menos diagnóstico',
            ),
        ),
        migrations.AddField(
            model_name='lineacotizacion',
            name='precio_unitario_cliente',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Precio cotizado al cliente por unidad, calculado al aprobar la línea',
                max_digits=10,
                null=True,
                verbose_name='Precio unitario al cliente (sin IVA)',
            ),
        ),
        migrations.AddField(
            model_name='lineacotizacion',
            name='subtotal_cliente_sin_iva',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='cantidad × precio_unitario_cliente, guardado al aprobar',
                max_digits=12,
                null=True,
                verbose_name='Subtotal cliente sin IVA',
            ),
        ),
    ]
