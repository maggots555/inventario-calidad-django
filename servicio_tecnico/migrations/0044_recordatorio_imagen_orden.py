from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Crea el modelo RecordatorioImagenOrden para controlar recordatorios
    diarios push/campanita cuando faltan fotos obligatorias en una orden.
    """

    dependencies = [
        ('servicio_tecnico', '0043_eventoseguimientocliente'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecordatorioImagenOrden',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'tipo',
                    models.CharField(
                        choices=[
                            ('ingreso_inspector', 'Ingreso pendiente — inspector'),
                            ('tecnico_faltantes', 'Evidencias pendientes — técnico'),
                        ],
                        help_text='Tipo de recordatorio enviado (inspector o técnico)',
                        max_length=20,
                    ),
                ),
                (
                    'fecha_ultimo_envio',
                    models.DateTimeField(help_text='Fecha y hora del último recordatorio enviado'),
                ),
                (
                    'orden',
                    models.ForeignKey(
                        help_text='Orden que aún tiene evidencias fotográficas pendientes',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='recordatorios_imagen',
                        to='servicio_tecnico.ordenservicio',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Recordatorio de imagen pendiente',
                'verbose_name_plural': 'Recordatorios de imágenes pendientes',
            },
        ),
        migrations.AddIndex(
            model_name='recordatorioimagenorden',
            index=models.Index(fields=['orden', 'tipo'], name='servicio_te_orden_i_6a8f21_idx'),
        ),
        migrations.AddIndex(
            model_name='recordatorioimagenorden',
            index=models.Index(fields=['-fecha_ultimo_envio'], name='servicio_te_fecha_u_2c4b9a_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='recordatorioimagenorden',
            unique_together={('orden', 'tipo')},
        ),
    ]
