"""
Tests del panel de parámetros del cotizador (BD + fallback .env).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Verificamos que:
1. Sin filas en BD se usan los valores del .env.
2. Al guardar en BD, los cálculos de profit/REAC usan esos valores.
3. Solo superusuario / gerente_general / gerente_operacional entran al panel.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from almacen.models import (
    ConfiguracionProfitPerfil,
    ConfiguracionReacondicionado,
)
from almacen.utils.costeo_reacondicionado import calcular_costeo
from almacen.utils.parametros_cotizador import (
    asegurar_parametros_iniciales,
    puede_editar_parametros_cotizador,
    obtener_costeo_reacondicionado_config,
    obtener_profit_config,
    guardar_profit_perfiles,
    guardar_reacondicionado,
)
from almacen.utils.pdf_cotizacion_cliente import calcular_precios_items_cotizacion
from inventario.models import Empleado, Sucursal


class ParametrosCotizadorGetterTest(TestCase):
    """Pruebas de lectura dinámica (BD sobre .env)."""

    # Multi-tenant: el router puede usar el alias 'mexico' además de 'default'
    databases = {'default', 'mexico'}

    def test_sin_filas_bd_usa_env(self):
        """Sin configuración guardada, hay perfiles y claves REAC válidas."""
        self.assertEqual(ConfiguracionProfitPerfil.objects.count(), 0)
        cfg = obtener_profit_config()
        self.assertIn('estandar', cfg)
        self.assertIn('profit_target', cfg['estandar'])
        self.assertIsInstance(cfg['estandar']['costos_fijos'], list)

        reac = obtener_costeo_reacondicionado_config()
        self.assertIn('pct_margen_ganancia', reac)
        self.assertIn('pct_iva', reac)

    def test_asegurar_parametros_siembra_desde_env(self):
        """La semilla crea 6 perfiles + 1 fila REAC."""
        creado = asegurar_parametros_iniciales()
        self.assertTrue(creado)
        self.assertEqual(ConfiguracionProfitPerfil.objects.count(), 6)
        self.assertTrue(ConfiguracionReacondicionado.objects.filter(pk=1).exists())
        # Segunda llamada no duplica
        self.assertFalse(asegurar_parametros_iniciales())

    def test_override_bd_cambia_profit_calculo(self):
        """
        Si el panel guarda profit 50% en estándar, el cálculo lo refleja.

        EXPLICACIÓN: costo 1000 con profit 0.50 → piezas = 2000; + diag 0 = 2000.
        """
        asegurar_parametros_iniciales()
        guardar_profit_perfiles({
            'estandar': {
                'profit_target': Decimal('0.50'),
                'costos_fijos': '25,160',
                'diagnostico': Decimal('0'),
            },
            'mostrador': {
                'profit_target': Decimal('0.42'),
                'costos_fijos': '50,40',
                'diagnostico': Decimal('0'),
            },
            'express': {
                'profit_target': Decimal('0.44'),
                'costos_fijos': '25,160',
                'diagnostico': Decimal('0'),
            },
            'alta_gama': {
                'profit_target': Decimal('0.44'),
                'costos_fijos': '25,160',
                'diagnostico': Decimal('0'),
            },
            'server': {
                'profit_target': Decimal('0.59'),
                'costos_fijos': '72,49,20,350',
                'diagnostico': Decimal('0'),
            },
            'rep_nivel_componente': {
                'profit_target': Decimal('0.42'),
                'costos_fijos': '50,40',
                'diagnostico': Decimal('0'),
            },
        })

        cfg = obtener_profit_config()
        self.assertEqual(cfg['estandar']['profit_target'], 0.5)
        self.assertEqual(cfg['estandar']['diagnostico'], 0.0)

        items = [
            {
                'descripcion': 'Pieza test',
                'cantidad': 1,
                'costo_unitario': 1000.0,
                'es_servicio': False,
            },
        ]
        calc = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
        )
        # 1000 / (1 - 0.50) + 0 = 2000
        self.assertAlmostEqual(calc['precio_sin_iva'], 2000.0, places=2)

    def test_override_bd_cambia_costeo_reacondicionado(self):
        """Cambiar margen REAC en BD altera el subtotal."""
        asegurar_parametros_iniciales()
        base = calcular_costeo(costo_proveedor=1000.0, dias_front_desk=1)

        guardar_reacondicionado({
            'recurso_front_desk_mensual': Decimal('10000'),
            'pct_front_desk': Decimal('0.21'),
            'mantenimiento_materiales': Decimal('25'),
            'gastos_operacion_ingeniero': Decimal('160'),
            'pct_overhead': Decimal('0.01'),
            'pct_mkt': Decimal('0.01'),
            'pct_comision_venta': Decimal('0.036'),
            # Margen más alto → precio de venta más alto
            'pct_margen_ganancia': Decimal('0.30'),
            'pct_iva': Decimal('0.16'),
            'pct_comision_cobro_base': Decimal('0.035'),
            'pct_comision_3m': Decimal('0.0469'),
            'pct_comision_6m': Decimal('0.0769'),
            'pct_comision_12m': Decimal('0.1289'),
        })

        nuevo = calcular_costeo(costo_proveedor=1000.0, dias_front_desk=1)
        self.assertGreater(nuevo['subtotal_sin_iva'], base['subtotal_sin_iva'])
        self.assertEqual(nuevo['pct_margen_ganancia_aplicado'], 0.30)


class ParametrosCotizadorPermisosTest(TestCase):
    """Permisos del panel y helper puede_editar_parametros_cotizador."""

    # Multi-tenant: alias default + mexico
    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.url = reverse('almacen:panel_parametros_cotizador')
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Parámetros',
            codigo='TST-PAR',
            activa=True,
        )

    def _crear_usuario(self, username, *, is_superuser=False, rol=None):
        """Crea User (+ Empleado con rol si se indica)."""
        user = User.objects.create_user(
            username=username,
            password='testpass123',
            is_superuser=is_superuser,
            is_staff=is_superuser,
        )
        if rol:
            Empleado.objects.create(
                user=user,
                nombre_completo=f'Empleado {username}',
                cargo='Prueba',
                area='Gerencia',
                rol=rol,
                sucursal=self.sucursal,
                activo=True,
                tiene_acceso_sistema=True,
                # Evitar redirección del middleware de contraseña inicial
                contraseña_configurada=True,
            )
        return user

    def _request_get(self, user):
        """
        Arma un request GET autenticado para llamar la vista sin Client HTTP.

        EXPLICACIÓN: RequestFactory no dispara PaisMiddleware (evita el
        conflicto default vs mexico en tests con dos BD en memoria).
        """
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore

        from almacen.views import panel_parametros_cotizador

        request = self.factory.get(self.url)
        request.user = user
        # Session + messages requeridos por messages.* en la vista
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return panel_parametros_cotizador(request)

    def test_helper_permisos(self):
        """Solo superuser y gerentes pueden editar."""
        su = self._crear_usuario('su', is_superuser=True)
        gg = self._crear_usuario('gg', rol='gerente_general')
        go = self._crear_usuario('go', rol='gerente_operacional')
        tec = self._crear_usuario('tec', rol='tecnico')

        self.assertTrue(puede_editar_parametros_cotizador(su))
        self.assertTrue(puede_editar_parametros_cotizador(gg))
        self.assertTrue(puede_editar_parametros_cotizador(go))
        self.assertFalse(puede_editar_parametros_cotizador(tec))

    def test_vista_rechaza_tecnico(self):
        """Un técnico es redirigido fuera del panel."""
        tec = self._crear_usuario('tec_panel', rol='tecnico')
        resp = self._request_get(tec)
        self.assertEqual(resp.status_code, 302)

    def test_vista_acepta_gerente_general(self):
        """Gerente general ve el formulario (200)."""
        gg = self._crear_usuario('gg_panel', rol='gerente_general')
        resp = self._request_get(gg)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Parámetros del cotizador')
        # Semilla automática al entrar
        self.assertEqual(ConfiguracionProfitPerfil.objects.count(), 6)

    def test_vista_acepta_superusuario(self):
        """Superusuario entra aunque no tenga Empleado."""
        su = self._crear_usuario('su_panel', is_superuser=True)
        resp = self._request_get(su)
        self.assertEqual(resp.status_code, 200)
