# Generated manually for integración SICSER Fase 2

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servicio_tecnico', '0045_enlace_pdf_diagnostico'),
    ]

    operations = [
        migrations.AddField(
            model_name='detalleequipo',
            name='folio_sicser',
            field=models.CharField(
                blank=True,
                help_text='Folio completo en SICSER (ej. MX_CIS_MX_DROPOFF_11954) para formato digital',
                max_length=80,
            ),
        ),
        migrations.AddField(
            model_name='detalleequipo',
            name='sicser_id_externo',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='ID único del registro en SICSER (id_orden OOW o numero_dps garantía)',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='detalleequipo',
            name='sicser_origen',
            field=models.CharField(
                blank=True,
                choices=[
                    ('oow', 'SICSER OOW'),
                    ('garantia', 'SICSER Garantía Dell'),
                ],
                help_text='Tipo de registro SICSER del que se importó esta orden',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='detalleequipo',
            constraint=models.UniqueConstraint(
                condition=models.Q(sicser_id_externo__gt=''),
                fields=('sicser_origen', 'sicser_id_externo'),
                name='unico_sicser_origen_id_externo',
            ),
        ),
    ]
