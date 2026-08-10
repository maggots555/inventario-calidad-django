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
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from almacen.models import (
    ConfiguracionProfitPerfil,
    ConfiguracionRangoProfitMinimo,
    ConfiguracionReacondicionado,
)
from almacen.utils.costeo_reacondicionado import calcular_costeo
from almacen.utils.parametros_cotizador import (
    asegurar_parametros_iniciales,
    puede_editar_parametros_cotizador,
    obtener_costeo_reacondicionado_config,
    obtener_profit_config,
    obtener_rangos_profit_minimo,
    obtener_todos_rangos_profit_minimo,
    guardar_profit_perfiles,
    guardar_rangos_profit_minimo,
    guardar_reacondicionado,
)
from almacen.utils.pdf_cotizacion_cliente import calcular_precios_items_cotizacion
from almacen.utils.profit_por_pieza import obtener_profit_minimo
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
        """La semilla crea 6 perfiles + 6 rangos mínimos + 1 fila REAC."""
        creado = asegurar_parametros_iniciales()
        self.assertTrue(creado)
        self.assertEqual(ConfiguracionProfitPerfil.objects.count(), 6)
        self.assertEqual(ConfiguracionRangoProfitMinimo.objects.count(), 6)
        self.assertTrue(ConfiguracionReacondicionado.objects.filter(pk=1).exists())
        # Segunda llamada no duplica
        self.assertFalse(asegurar_parametros_iniciales())

    def test_sin_filas_rangos_usa_semilla(self):
        """Sin ConfiguracionRangoProfitMinimo, obtener_rangos_profit_minimo cae a semilla."""
        self.assertEqual(ConfiguracionRangoProfitMinimo.objects.count(), 0)
        rangos = obtener_rangos_profit_minimo('estandar')
        self.assertEqual(len(rangos), 4)
        self.assertEqual(rangos[0]['profit_minimo'], 0.45)
        self.assertEqual(rangos[3]['profit_minimo'], 0.28)

    def test_override_rangos_por_perfil_no_afecta_otro(self):
        """
        Cambiar mínimos de Estándar no altera Mostrador.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Cada tipo de cotización tiene su propia fila. Si Gerencia baja el
        mínimo de Estándar en piezas baratas a 40%, Mostrador sigue en 45%.
        """
        asegurar_parametros_iniciales()
        guardar_rangos_profit_minimo({
            'estandar': {
                'min_0_499': Decimal('0.40'),
                'min_500_999': Decimal('0.36'),
                'min_1000_1499': Decimal('0.30'),
                'min_1500_mas': Decimal('0.28'),
            },
        })
        self.assertEqual(
            obtener_profit_minimo(100, perfil='estandar'),
            Decimal('0.40'),
        )
        self.assertEqual(
            obtener_profit_minimo(100, perfil='mostrador'),
            Decimal('0.45'),
        )
        # Motor: pieza barata con Estándar al 40% vs Mostrador elevado a 45%
        items = [{
            'descripcion': 'Pieza barata',
            'cantidad': 1,
            'costo_unitario': 100.0,
            'es_servicio': False,
        }]
        calc_est = calcular_precios_items_cotizacion(
            items=items, tipo_servicio='estandar',
        )
        calc_mos = calcular_precios_items_cotizacion(
            items=items, tipo_servicio='mostrador',
        )
        self.assertAlmostEqual(
            calc_est['items_calculados'][0]['profit_aplicado'], 0.40, places=4,
        )
        # Mostrador perfil ~42% → se eleva al mínimo 45% del perfil mostrador
        self.assertAlmostEqual(
            calc_mos['items_calculados'][0]['profit_aplicado'], 0.45, places=4,
        )

    def test_mapa_todos_rangos_incluye_seis_perfiles(self):
        """El modal recibe un mapa completo perfil → 4 tramos."""
        asegurar_parametros_iniciales()
        mapa = obtener_todos_rangos_profit_minimo()
        self.assertEqual(len(mapa), 6)
        self.assertIn('server', mapa)
        self.assertEqual(len(mapa['server']), 4)

    def test_override_bd_cambia_profit_calculo(self):
        """
        Si el panel guarda profit 50% en estándar, el cálculo lo refleja.

        EXPLICACIÓN: costo 1000 con profit 0.50 → piezas = 2000 (sin diagnóstico).
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
        # 1000 / (1 - 0.50) = 2000 (el diagnóstico del panel no suma)
        self.assertAlmostEqual(calc['precio_sin_iva'], 2000.0, places=2)

    def test_diagnostico_bd_no_infla_precio_reparacion(self):
        """
        Guardar diagnóstico alto en el panel NO debe subir el total de reparación.

        EXPLICACIÓN PARA PRINCIPIANTES:
        El campo sigue en BD por auditoría, pero el motor de cotización ya no
        lo suma ni lo diluye. Con profit 36%, 1000 de costo → 1562.50 siempre.
        """
        asegurar_parametros_iniciales()
        cfg_base = obtener_profit_config()
        perfiles = {}
        for clave, datos in cfg_base.items():
            costos = datos['costos_fijos']
            if isinstance(costos, list):
                costos_str = ','.join(str(c) for c in costos)
            else:
                costos_str = str(costos)
            perfiles[clave] = {
                'profit_target': Decimal(str(datos['profit_target'])),
                'costos_fijos': costos_str,
                'diagnostico': Decimal('9999') if clave == 'estandar' else Decimal(
                    str(datos['diagnostico'])
                ),
            }
        guardar_profit_perfiles(perfiles)

        cfg = obtener_profit_config()
        self.assertEqual(cfg['estandar']['diagnostico'], 9999.0)

        calc = calcular_precios_items_cotizacion(
            items=[{
                'descripcion': 'Pieza',
                'cantidad': 1,
                'costo_unitario': 1000.0,
                'es_servicio': False,
            }],
            tipo_servicio='estandar',
        )
        # Solo margen 36%: 1000 / 0.64 = 1562.50 (sin los 9999 de diagnóstico)
        self.assertAlmostEqual(calc['precio_sin_iva'], 1562.50, places=2)
        self.assertEqual(calc['diagnostico'], 0)
        self.assertIsNone(calc['precio_menos_diagnostico'])

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


@override_settings(
    # En tests no hay collectstatic: ManifestStaticFilesStorage rompe {% static %}
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
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
