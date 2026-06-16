from django.db import migrations


def migrar_enviada_cliente_a_enviada_front(apps, schema_editor):
    """
    Migra los registros existentes con estado 'enviada_cliente' a 'enviada_front'.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Antes teníamos un solo estado 'enviada_cliente' que significaba "enviada a front".
    Ahora separamos en dos estados:
    - 'enviada_front': La solicitud fue enviada a recepción para revisión
    - 'enviada_cliente': La solicitud fue enviada al cliente final

    Los registros existentes que estaban en 'enviada_cliente' realmente estaban
    en el estado de "enviada a front", por lo que los migramos a 'enviada_front'.
    """
    SolicitudCotizacion = apps.get_model('almacen', 'SolicitudCotizacion')

    # Actualizar todos los registros de enviada_cliente a enviada_front
    actualizados = SolicitudCotizacion.objects.filter(
        estado='enviada_cliente'
    ).update(estado='enviada_front')

    if actualizados > 0:
        print(f'\n  → Migradas {actualizados} solicitud(es) de enviada_cliente a enviada_front')


def reversar_migracion(apps, schema_editor):
    """
    Reversa: migra 'enviada_front' de vuelta a 'enviada_cliente'.
    """
    SolicitudCotizacion = apps.get_model('almacen', 'SolicitudCotizacion')

    actualizados = SolicitudCotizacion.objects.filter(
        estado='enviada_front'
    ).update(estado='enviada_cliente')

    if actualizados > 0:
        print(f'\n  → Reversadas {actualizados} solicitud(es) de enviada_front a enviada_cliente')


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0017_agregar_estado_enviada_front'),
    ]

    operations = [
        migrations.RunPython(
            migrar_enviada_cliente_a_enviada_front,
            reversar_migracion,
        ),
    ]
