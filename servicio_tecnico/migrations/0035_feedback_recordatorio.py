from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Agrega el campo 'recordatorio_enviado' al modelo FeedbackCliente.
    Se usa para evitar enviar más de un recordatorio de encuesta de
    satisfacción por cada token. La tarea periódica diaria (Celery Beat)
    lo consulta antes de encolar el correo de recordatorio.
    """

    dependencies = [
        ('servicio_tecnico', '0034_alter_ordenservicio_responsable_seguimiento'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackcliente',
            name='recordatorio_enviado',
            field=models.BooleanField(
                default=False,
                help_text="True cuando se envió el correo de recordatorio al día 10 de vigencia (solo aplica a tipo='satisfaccion')",
                verbose_name='¿Recordatorio enviado?',
            ),
        ),
    ]
