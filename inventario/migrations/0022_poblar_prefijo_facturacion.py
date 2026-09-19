"""
Rellena el prefijo de facturación de las sucursales que ya existen.

EXPLICACIÓN PARA PRINCIPIANTES:
Antes de esta migración el prefijo se adivinaba leyendo el nombre de la
sucursal ("Satelite" -> SAT). Esa lógica vive en Almacén y se usa para las
referencias de pago. Aquí la corremos UNA sola vez para dejar el valor
guardado en la tabla; de ahí en adelante el dato es explícito y una sucursal
nueva simplemente lo captura en el admin.

Las sucursales de prueba (Preview, Test) se quedan sin prefijo: eso significa
"esta sucursal no factura por el autofacturador".
"""

from django.db import migrations


# Palabra clave dentro del nombre o código -> prefijo del webId.
# Mismo criterio que almacen/utils/cotizacion_email_context.py para que la
# referencia de pago y el webId de facturación no se contradigan.
REGLAS_PREFIJO = (
    ('drop', 'DROP'),
    ('satelite', 'SAT'),
    ('guadalajara', 'GDL'),
    ('gdl', 'GDL'),
    ('monterrey', 'MTY'),
    ('mty', 'MTY'),
)


def _normalizar(texto):
    """Minúsculas sin acentos para comparar sin sorpresas ('Satélite' -> 'satelite')."""
    import unicodedata

    if not texto:
        return ''
    sin_acentos = ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
    )
    return sin_acentos.lower().strip()


def poblar_prefijos(apps, schema_editor):
    """Asigna el prefijo a cada sucursal existente según su nombre/código."""
    Sucursal = apps.get_model('inventario', 'Sucursal')
    db_alias = schema_editor.connection.alias

    for sucursal in Sucursal.objects.using(db_alias).all():
        # Paso 1: juntamos nombre y código en un solo texto normalizado.
        texto = _normalizar(f'{sucursal.nombre} {sucursal.codigo}')

        # Paso 2: primera regla que coincida gana (el orden importa).
        for palabra_clave, prefijo in REGLAS_PREFIJO:
            if palabra_clave in texto:
                sucursal.prefijo_facturacion = prefijo
                sucursal.save(update_fields=['prefijo_facturacion'])
                break
        # Paso 3: si ninguna coincide, se queda vacío a propósito.


def limpiar_prefijos(apps, schema_editor):
    """Reversa: deja el campo vacío (el dato se puede recalcular)."""
    Sucursal = apps.get_model('inventario', 'Sucursal')
    db_alias = schema_editor.connection.alias
    Sucursal.objects.using(db_alias).update(prefijo_facturacion='')


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0021_sucursal_prefijo_facturacion'),
    ]

    operations = [
        migrations.RunPython(poblar_prefijos, limpiar_prefijos),
    ]
