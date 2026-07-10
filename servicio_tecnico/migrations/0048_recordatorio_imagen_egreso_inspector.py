# Generated manually — solo agrega choice egreso_inspector al recordatorio de imágenes

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Amplía las opciones de RecordatorioImagenOrden.tipo para soportar
    el aviso inmediato a inspectores cuando falta egreso en finalizado.
    """

    dependencies = [
        ('servicio_tecnico', '0047_detalleequipo_sicser_ciudad_cis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recordatorioimagenorden',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('ingreso_inspector', 'Ingreso pendiente — inspector'),
                    ('egreso_inspector', 'Egreso pendiente — inspector'),
                    ('tecnico_faltantes', 'Evidencias pendientes — técnico'),
                ],
                help_text='Tipo de recordatorio enviado (inspector ingreso/egreso o técnico)',
                max_length=20,
            ),
        ),
    ]
