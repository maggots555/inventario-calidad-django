"""
Robustez del catálogo de diagnósticos: fallos, atomicidad y paridad de claves.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Los tests de `test_gama_por_mano_obra.py` comprueban que el flujo feliz
funcione. Este archivo comprueba lo contrario: qué pasa cuando algo sale mal.

Son tres preguntas incómodas que un cobro tiene que responder bien:

1. ¿Y si el tarifario no responde? No puede guardar $0 como si fuera un
   precio: borraría el cobro del diagnóstico sin que nadie se entere.
2. ¿Y si falla a media escritura? La orden y la cotización deben quedar
   iguales. Un descuadre entre ambas no se nota hasta que el total que vio
   el cliente no coincide con el de la factura.
3. ¿Y si alguien agrega un perfil solo en un lado? Las claves del catálogo
   y las del tarifario tienen que coincidir o el precio no se encuentra.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    HistorialOrden,
    OrdenServicio,
)
from servicio_tecnico.services.diagnostico_catalogo import (
    PERFILES_SIN_CARGO,
    PERFILES_VALIDOS,
    TarifarioNoDisponible,
    aplicar_perfil_diagnostico,
    opciones_diagnostico,
    tarifa_perfil,
    tarifa_perfil_estricta,
)
from servicio_tecnico.tests.helpers_tarifario import sembrar_tarifario


class ParidadDeClavesTest(SimpleTestCase):
    """
    El catálogo de ST y el tarifario de Almacén deben hablar el mismo idioma.

    Si alguien agrega un perfil en un solo lado, el precio no se encuentra y
    el diagnóstico se cobraría en $0 sin ningún error visible. Este test
    convierte ese descuido silencioso en un fallo ruidoso.
    """

    def test_catalogo_y_tarifario_tienen_las_mismas_claves(self):
        """Las claves de PERFIL_DIAGNOSTICO_CHOICES == PERFILES_PROFIT."""
        from almacen.utils.parametros_cotizador import PERFILES_PROFIT

        self.assertEqual(
            sorted(PERFILES_VALIDOS),
            sorted(PERFILES_PROFIT),
            msg=(
                'El catálogo de diagnósticos y el tarifario del cotizador se '
                'desincronizaron. Actualiza PERFIL_DIAGNOSTICO_CHOICES, '
                'PERFIL_DIAGNOSTICO_GAMA y PERFILES_PROFIT a la vez.'
            ),
        )

    def test_todo_perfil_tiene_regla_de_gama(self):
        """Ningún perfil puede quedarse sin decir qué hace con la gama."""
        from config.constants import PERFIL_DIAGNOSTICO_GAMA

        for perfil in PERFILES_VALIDOS:
            with self.subTest(perfil=perfil):
                self.assertIn(perfil, PERFIL_DIAGNOSTICO_GAMA)

    def test_perfiles_sin_cargo_existen_en_el_catalogo(self):
        """La lista de exentos no puede referirse a perfiles inventados."""
        for perfil in PERFILES_SIN_CARGO:
            with self.subTest(perfil=perfil):
                self.assertIn(perfil, PERFILES_VALIDOS)


class BaseCatalogoTest(TestCase):
    """Semilla mínima: sucursal, empleado y una orden con equipo."""

    databases = {'default', 'mexico'}

    def setUp(self):
        sembrar_tarifario()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Catalogo Robustez',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Tecnico Robustez',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.robustez@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('0.00'),
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-ROBUSTEZ-01',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='ProBook',
            numero_serie='SN-ROBUSTEZ-01',
            falla_principal='No enciende',
            gama='baja',
        )


class TarifarioCaidoTest(BaseCatalogoTest):
    """
    Un tarifario que no responde NO puede traducirse en un cobro de $0.

    Es el fallo más peligroso del diseño: silencioso, plausible (basta que el
    panel de parámetros esté a medio configurar en un tenant nuevo) y con
    consecuencia directa en dinero.
    """

    def test_tarifario_caido_no_guarda_nada(self):
        """Si el tarifario truena, la orden queda intacta."""
        with patch(
            'almacen.utils.parametros_cotizador.obtener_profit_config',
            side_effect=RuntimeError('BD no disponible'),
        ):
            with self.assertRaises(TarifarioNoDisponible):
                aplicar_perfil_diagnostico(self.orden, 'estandar')

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('0.00'))
        self.assertEqual(self.orden.perfil_diagnostico, '')

    def test_perfil_con_tarifa_cero_es_error_si_deberia_cobrar(self):
        """
        Estándar en $0 significa panel mal configurado, no diagnóstico gratis.

        Cobrar $0 por un diagnóstico que sí se hizo es una pérdida silenciosa,
        así que preferimos bloquear la captura y que alguien revise el panel.
        """
        with patch(
            'almacen.utils.parametros_cotizador.obtener_profit_config',
            return_value={'estandar': {'diagnostico': 0}},
        ):
            with self.assertRaises(TarifarioNoDisponible):
                tarifa_perfil_estricta('estandar')

    def test_perfil_sin_cargo_si_acepta_cero(self):
        """
        Mostrador vale $0 de verdad: ese cero sí es un precio válido.

        Es la contraparte del test anterior: distinguir los dos ceros era
        justamente el punto.
        """
        resultado = aplicar_perfil_diagnostico(self.orden, 'mostrador')
        self.orden.refresh_from_db()
        self.assertEqual(resultado.monto_nuevo, Decimal('0.00'))
        self.assertEqual(self.orden.perfil_diagnostico, 'mostrador')
        self.assertEqual(self.orden.costo_mano_obra, Decimal('0.00'))

    def test_lectura_tolerante_no_rompe_la_pantalla(self):
        """
        Para mostrar precios preferimos un $0 a una pantalla caída.

        tarifa_perfil() y opciones_diagnostico() se usan al pintar el selector;
        si el tarifario falla, la página debe seguir abriendo.
        """
        with patch(
            'almacen.utils.parametros_cotizador.obtener_profit_config',
            side_effect=RuntimeError('BD no disponible'),
        ):
            self.assertEqual(tarifa_perfil('estandar'), Decimal('0.00'))
            opciones = opciones_diagnostico()

        self.assertEqual(len(opciones), len(PERFILES_VALIDOS))


class AtomicidadTest(BaseCatalogoTest):
    """
    O se guarda todo, o no se guarda nada.

    La orden y la cotización guardan el MISMO monto en dos tablas distintas.
    Si una se escribe y la otra no, el descuadre queda latente y aparece
    cuando Contabilidad compara la factura contra lo cotizado.
    """

    def test_fallo_a_media_escritura_revierte_todo(self):
        """
        Si el historial falla, la orden y la cotización vuelven a su valor.

        Simulamos el fallo en el ÚLTIMO paso a propósito: para entonces la
        orden y la cotización ya se escribieron, así que solo la transacción
        puede deshacerlas.
        """
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('0.00'),
        )

        with patch.object(
            HistorialOrden.objects,
            'create',
            side_effect=RuntimeError('fallo al escribir historial'),
        ):
            with self.assertRaises(RuntimeError):
                aplicar_perfil_diagnostico(self.orden, 'alta_gama')

        self.orden.refresh_from_db()
        cotizacion.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('0.00'))
        self.assertEqual(self.orden.perfil_diagnostico, '')
        self.assertEqual(cotizacion.costo_mano_obra, Decimal('0.00'))

    def test_gama_tambien_se_revierte(self):
        """El equipo no puede quedar reclasificado si el cobro no se guardó."""
        with patch.object(
            HistorialOrden.objects,
            'create',
            side_effect=RuntimeError('fallo al escribir historial'),
        ):
            with self.assertRaises(RuntimeError):
                aplicar_perfil_diagnostico(self.orden, 'alta_gama')

        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.detalle_equipo.gama, 'baja')


class IdempotenciaTest(BaseCatalogoTest):
    """Repetir la misma captura no debe multiplicar efectos."""

    def test_guardar_dos_veces_el_mismo_perfil_deja_el_mismo_monto(self):
        """
        Doble clic: el monto final es el mismo, no se duplica ni se acumula.

        El historial sí registra las dos veces, y está bien: es una bitácora
        de quién tocó qué, no un estado.
        """
        aplicar_perfil_diagnostico(self.orden, 'estandar', usuario=self.empleado)
        aplicar_perfil_diagnostico(self.orden, 'estandar', usuario=self.empleado)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('570.00'))
        self.assertEqual(self.orden.perfil_diagnostico, 'estandar')

    def test_cambiar_de_perfil_reemplaza_el_monto(self):
        """Corregir el diagnóstico reemplaza el cobro, no lo suma."""
        aplicar_perfil_diagnostico(self.orden, 'estandar', usuario=self.empleado)
        aplicar_perfil_diagnostico(self.orden, 'server', usuario=self.empleado)

        self.orden.refresh_from_db()
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('1000.00'))
        self.assertEqual(self.orden.detalle_equipo.gama, 'alta')

    def test_bajar_de_server_a_estandar_corrige_la_gama(self):
        """
        Si se capturó mal y se corrige, la gama debe bajar también.

        Sin esto, un error de captura dejaría el equipo marcado como gama alta
        para siempre, contaminando los reportes.
        """
        aplicar_perfil_diagnostico(self.orden, 'server', usuario=self.empleado)
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.detalle_equipo.gama, 'alta')

        aplicar_perfil_diagnostico(self.orden, 'estandar', usuario=self.empleado)
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.detalle_equipo.gama, 'media')


class SinDetalleEquipoTest(TestCase):
    """Borde: órdenes sin DetalleEquipo no deben tumbar la captura."""

    databases = {'default', 'mexico'}

    def setUp(self):
        sembrar_tarifario()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Sin Detalle',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Tecnico Sin Detalle',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.sin.detalle@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
        )
        # A propósito NO creamos DetalleEquipo: el OneToOne queda ausente.
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('0.00'),
        )

    def test_cobra_aunque_no_haya_equipo_registrado(self):
        """El cobro se guarda; simplemente no hay gama que actualizar."""
        resultado = aplicar_perfil_diagnostico(self.orden, 'alta_gama')

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('864.00'))
        self.assertIsNone(resultado.gama_nueva)
