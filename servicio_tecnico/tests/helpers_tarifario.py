"""
Tarifario de diagnósticos con valores fijos para los tests.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El precio del diagnóstico ya no se teclea: sale del panel de parámetros del
cotizador, con respaldo en el archivo .env. Eso está bien en producción, pero
en los tests es un problema: si cada máquina tiene su propio .env, el mismo
test daría montos distintos según quién lo corra.

La solución es sembrar el tarifario en la base de prueba antes de cada test.
Así los tests afirman "Estándar cuesta $570" porque ellos mismos lo pusieron,
no porque confíen en la configuración local.

No tiene prefijo `test_` a propósito: es un ayudante, no una suite, y el
runner de Django solo recoge archivos que empiezan con `test`.
"""

from decimal import Decimal

# Tarifas de referencia del negocio (las mismas que los defaults del .env).
# Todas SIN IVA, que es como se guardan en OrdenServicio.costo_mano_obra.
TARIFAS_DIAGNOSTICO = {
    'mostrador': Decimal('0.00'),
    'estandar': Decimal('570.00'),
    'express': Decimal('774.00'),
    'alta_gama': Decimal('864.00'),
    'server': Decimal('1000.00'),
    'rep_nivel_componente': Decimal('0.00'),
}


def sembrar_tarifario():
    """
    Deja el tarifario del cotizador en valores conocidos.

    Llamar desde setUp() de cualquier test que toque mano de obra.

    Efectos secundarios:
        Crea o actualiza las 6 filas de ConfiguracionProfitPerfil en la BD
        de prueba del tenant activo.
    """
    from almacen.models import ConfiguracionProfitPerfil

    for perfil, diagnostico in TARIFAS_DIAGNOSTICO.items():
        ConfiguracionProfitPerfil.objects.update_or_create(
            perfil=perfil,
            defaults={
                'profit_target': Decimal('0.36'),
                'costos_fijos': '25,160',
                'diagnostico': diagnostico,
            },
        )
