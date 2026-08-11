"""
Tests de humo tras modularizar vistas de Almacén (Fase 0 .. Fase 4).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Estos tests NO abren el dashboard ni generan Excel real. Solo confirman que:
1) Los nombres siguen disponibles en almacen.views (urls.py no se rompe).
2) El callable de views.py es EXACTAMENTE el del módulo nuevo (misma identidad).
3) reverse/resolve apuntan a las funciones del módulo extraído.

Si alguien borra un reexport por error, este test falla antes de producción.
"""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from almacen import views as almacen_views
from almacen import views_catalogo
from almacen import views_compras
from almacen import views_cotizacion_cliente
from almacen import views_cotizacion_pnc_cliente
from almacen import views_cotizacion_sync_st
from almacen import views_dashboard_distribucion
from almacen import views_parametros_cotizador
from almacen import views_solicitudes_cotizacion
from almacen import views_unidades
from almacen.decorators import permission_required_with_message
from almacen.utils import cotizacion_reacondicionado_helpers


class CompatibilidadReexportsFase0Test(SimpleTestCase):
    """
    Verifica que el decorador se reexporta desde views.py.

    Objetivo de negocio:
        Mantener compatibilidad con imports antiguos y con los
        decoradores @permission_required_with_message del monolito residual.
    """

    def test_views_reexporta_decorador(self):
        """permission_required_with_message en views es el de decorators.py."""
        self.assertTrue(callable(almacen_views.permission_required_with_message))
        self.assertIs(
            almacen_views.permission_required_with_message,
            permission_required_with_message,
        )


class CompatibilidadReexportsFase1Test(SimpleTestCase):
    """
    Verifica reexports y resolución de URLs de la Fase 1.

    Módulos extraídos:
        - views_dashboard_distribucion
        - views_parametros_cotizador
    """

    def test_views_reexporta_dashboard_distribucion(self):
        """Los símbolos públicos de distribución siguen en views."""
        self.assertIs(
            almacen_views.dashboard_distribucion_sucursales,
            views_dashboard_distribucion.dashboard_distribucion_sucursales,
        )
        self.assertIs(
            almacen_views.exportar_distribucion_excel,
            views_dashboard_distribucion.exportar_distribucion_excel,
        )

    def test_views_reexporta_parametros_cotizador(self):
        """panel_parametros_cotizador en views es el del módulo nuevo."""
        self.assertIs(
            almacen_views.panel_parametros_cotizador,
            views_parametros_cotizador.panel_parametros_cotizador,
        )

    def test_modulo_correcto_fase1(self):
        """__module__ apunta al archivo hermano, no al monolito."""
        self.assertEqual(
            almacen_views.dashboard_distribucion_sucursales.__module__,
            'almacen.views_dashboard_distribucion',
        )
        self.assertEqual(
            almacen_views.exportar_distribucion_excel.__module__,
            'almacen.views_dashboard_distribucion',
        )
        self.assertEqual(
            almacen_views.panel_parametros_cotizador.__module__,
            'almacen.views_parametros_cotizador',
        )

    def test_url_distribucion_resuelve_al_modulo_nuevo(self):
        """
        reverse/resolve de distribución apuntan al callable extraído.

        Nota: exportar_distribucion_excel no tiene path() propio; se invoca
        desde el dashboard con ?export=excel, por eso solo resolvemos el dashboard.
        """
        url = reverse('almacen:dashboard_distribucion_sucursales')
        match = resolve(url)
        self.assertIs(
            match.func,
            views_dashboard_distribucion.dashboard_distribucion_sucursales,
        )

    def test_url_parametros_resuelve_al_modulo_nuevo(self):
        """reverse/resolve de parámetros apuntan al callable extraído."""
        url = reverse('almacen:panel_parametros_cotizador')
        match = resolve(url)
        self.assertIs(
            match.func,
            views_parametros_cotizador.panel_parametros_cotizador,
        )


class CompatibilidadReexportsFase2Test(SimpleTestCase):
    """
    Verifica reexports y resolución de URLs de la Fase 2.

    Módulos extraídos:
        - views_catalogo (dashboard, productos, bajas, APIs producto, acceso denegado)
        - views_unidades (CRUD unidades + APIs + buscar/crear orden)
    """

    def test_views_reexporta_catalogo_representativo(self):
        """Símbolos clave del catálogo siguen en views con la misma identidad."""
        pares = [
            ('dashboard_almacen', views_catalogo.dashboard_almacen),
            ('lista_productos', views_catalogo.lista_productos),
            ('lista_proveedores', views_catalogo.lista_proveedores),
            ('lista_categorias', views_catalogo.lista_categorias),
            ('lista_solicitudes', views_catalogo.lista_solicitudes),
            ('lista_movimientos', views_catalogo.lista_movimientos),
            ('api_buscar_productos', views_catalogo.api_buscar_productos),
            ('api_info_producto', views_catalogo.api_info_producto),
            ('acceso_denegado', views_catalogo.acceso_denegado),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_views_reexporta_unidades_representativo(self):
        """Símbolos clave de unidades siguen en views con la misma identidad."""
        pares = [
            ('lista_unidades', views_unidades.lista_unidades),
            ('crear_unidad', views_unidades.crear_unidad),
            ('detalle_unidad', views_unidades.detalle_unidad),
            ('cambiar_estado_unidad', views_unidades.cambiar_estado_unidad),
            ('unidades_por_producto', views_unidades.unidades_por_producto),
            ('api_unidad_info', views_unidades.api_unidad_info),
            ('api_unidades_producto', views_unidades.api_unidades_producto),
            ('api_tecnicos_disponibles', views_unidades.api_tecnicos_disponibles),
            (
                'api_buscar_crear_orden_cliente',
                views_unidades.api_buscar_crear_orden_cliente,
            ),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_modulo_correcto_fase2(self):
        """__module__ apunta a views_catalogo / views_unidades."""
        self.assertEqual(
            almacen_views.dashboard_almacen.__module__,
            'almacen.views_catalogo',
        )
        self.assertEqual(
            almacen_views.acceso_denegado.__module__,
            'almacen.views_catalogo',
        )
        self.assertEqual(
            almacen_views.lista_unidades.__module__,
            'almacen.views_unidades',
        )
        self.assertEqual(
            almacen_views.api_buscar_crear_orden_cliente.__module__,
            'almacen.views_unidades',
        )

    def test_urls_catalogo_resuelven_al_modulo_nuevo(self):
        """reverse/resolve de catálogo apuntan a views_catalogo."""
        casos = [
            ('almacen:dashboard', {}, views_catalogo.dashboard_almacen),
            ('almacen:lista_productos', {}, views_catalogo.lista_productos),
            ('almacen:lista_proveedores', {}, views_catalogo.lista_proveedores),
            ('almacen:lista_categorias', {}, views_catalogo.lista_categorias),
            ('almacen:lista_solicitudes', {}, views_catalogo.lista_solicitudes),
            ('almacen:lista_movimientos', {}, views_catalogo.lista_movimientos),
            ('almacen:api_buscar_productos', {}, views_catalogo.api_buscar_productos),
            (
                'almacen:api_info_producto',
                {'pk': 1},
                views_catalogo.api_info_producto,
            ),
            (
                'almacen:acceso_denegado_almacen',
                {},
                views_catalogo.acceso_denegado,
            ),
        ]
        for name, kwargs, expected in casos:
            match = resolve(reverse(name, kwargs=kwargs))
            self.assertIs(match.func, expected, msg=name)

    def test_urls_unidades_resuelven_al_modulo_nuevo(self):
        """reverse/resolve de unidades apuntan a views_unidades."""
        casos = [
            ('almacen:lista_unidades', {}, views_unidades.lista_unidades),
            ('almacen:crear_unidad', {}, views_unidades.crear_unidad),
            (
                'almacen:detalle_unidad',
                {'pk': 1},
                views_unidades.detalle_unidad,
            ),
            (
                'almacen:unidades_por_producto',
                {'producto_id': 1},
                views_unidades.unidades_por_producto,
            ),
            (
                'almacen:api_unidad_info',
                {'pk': 1},
                views_unidades.api_unidad_info,
            ),
            (
                'almacen:api_unidades_producto',
                {},
                views_unidades.api_unidades_producto,
            ),
            (
                'almacen:api_tecnicos_disponibles',
                {},
                views_unidades.api_tecnicos_disponibles,
            ),
            (
                'almacen:api_buscar_crear_orden',
                {},
                views_unidades.api_buscar_crear_orden_cliente,
            ),
        ]
        for name, kwargs, expected in casos:
            match = resolve(reverse(name, kwargs=kwargs))
            self.assertIs(match.func, expected, msg=name)


class CompatibilidadReexportsFase3Test(SimpleTestCase):
    """
    Verifica reexports y resolución de URLs de la Fase 3.

    Módulo extraído:
        - views_compras (CompraProducto + panel_cotizaciones)

    Nota: los helpers _clave_grupo_compra_cotizacion y
    _agrupar_compras_por_orden son privados del módulo y NO se reexportan.
    """

    def test_views_reexporta_compras_representativo(self):
        """Símbolos clave de compras siguen en views con la misma identidad."""
        pares = [
            ('lista_compras', views_compras.lista_compras),
            ('panel_cotizaciones', views_compras.panel_cotizaciones),
            ('crear_compra', views_compras.crear_compra),
            ('detalle_compra', views_compras.detalle_compra),
            ('editar_compra', views_compras.editar_compra),
            ('aprobar_cotizacion', views_compras.aprobar_cotizacion),
            ('rechazar_cotizacion', views_compras.rechazar_cotizacion),
            ('recibir_compra', views_compras.recibir_compra),
            ('reportar_problema_compra', views_compras.reportar_problema_compra),
            ('iniciar_devolucion', views_compras.iniciar_devolucion),
            ('confirmar_devolucion', views_compras.confirmar_devolucion),
            ('cancelar_compra', views_compras.cancelar_compra),
            ('recibir_unidad_compra', views_compras.recibir_unidad_compra),
            ('problema_unidad_compra', views_compras.problema_unidad_compra),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_helpers_agrupacion_no_se_reexportan(self):
        """
        Los helpers de agrupación viven solo en views_compras.

        EXPLICACIÓN: son detalle de implementación de lista_compras;
        no forman parte del contrato público de urls.py.
        """
        self.assertTrue(callable(views_compras._clave_grupo_compra_cotizacion))
        self.assertTrue(callable(views_compras._agrupar_compras_por_orden))
        self.assertFalse(hasattr(almacen_views, '_clave_grupo_compra_cotizacion'))
        self.assertFalse(hasattr(almacen_views, '_agrupar_compras_por_orden'))

    def test_modulo_correcto_fase3(self):
        """__module__ apunta a views_compras."""
        self.assertEqual(
            almacen_views.lista_compras.__module__,
            'almacen.views_compras',
        )
        self.assertEqual(
            almacen_views.recibir_compra.__module__,
            'almacen.views_compras',
        )
        self.assertEqual(
            almacen_views.panel_cotizaciones.__module__,
            'almacen.views_compras',
        )

    def test_urls_compras_resuelven_al_modulo_nuevo(self):
        """reverse/resolve de compras apuntan a views_compras."""
        casos = [
            ('almacen:lista_compras', {}, views_compras.lista_compras),
            ('almacen:panel_cotizaciones', {}, views_compras.panel_cotizaciones),
            ('almacen:crear_compra', {}, views_compras.crear_compra),
            (
                'almacen:detalle_compra',
                {'pk': 1},
                views_compras.detalle_compra,
            ),
            (
                'almacen:editar_compra',
                {'pk': 1},
                views_compras.editar_compra,
            ),
            (
                'almacen:aprobar_cotizacion',
                {'pk': 1},
                views_compras.aprobar_cotizacion,
            ),
            (
                'almacen:rechazar_cotizacion',
                {'pk': 1},
                views_compras.rechazar_cotizacion,
            ),
            (
                'almacen:recibir_compra',
                {'pk': 1},
                views_compras.recibir_compra,
            ),
            (
                'almacen:reportar_problema',
                {'pk': 1},
                views_compras.reportar_problema_compra,
            ),
            (
                'almacen:iniciar_devolucion',
                {'pk': 1},
                views_compras.iniciar_devolucion,
            ),
            (
                'almacen:confirmar_devolucion',
                {'pk': 1},
                views_compras.confirmar_devolucion,
            ),
            (
                'almacen:cancelar_compra',
                {'pk': 1},
                views_compras.cancelar_compra,
            ),
            (
                'almacen:recibir_unidad',
                {'compra_pk': 1, 'pk': 1},
                views_compras.recibir_unidad_compra,
            ),
            (
                'almacen:problema_unidad',
                {'compra_pk': 1, 'pk': 1},
                views_compras.problema_unidad_compra,
            ),
        ]
        for name, kwargs, expected in casos:
            match = resolve(reverse(name, kwargs=kwargs))
            self.assertIs(match.func, expected, msg=name)


class CompatibilidadReexportsFase4Test(SimpleTestCase):
    """
    Verifica reexports y resolución de URLs de la Fase 4.

    Módulos extraídos:
        - views_solicitudes_cotizacion
        - views_cotizacion_cliente
        - views_cotizacion_sync_st
        - utils/cotizacion_reacondicionado_helpers (compartido)
    """

    def test_views_reexporta_solicitudes_representativo(self):
        """Símbolos clave de solicitudes siguen en views."""
        pares = [
            (
                'lista_solicitudes_cotizacion',
                views_solicitudes_cotizacion.lista_solicitudes_cotizacion,
            ),
            (
                'crear_solicitud_cotizacion',
                views_solicitudes_cotizacion.crear_solicitud_cotizacion,
            ),
            (
                'detalle_solicitud_cotizacion',
                views_solicitudes_cotizacion.detalle_solicitud_cotizacion,
            ),
            (
                'editar_lineas_cotizacion',
                views_solicitudes_cotizacion.editar_lineas_cotizacion,
            ),
            (
                'agregar_servicio_adicional',
                views_solicitudes_cotizacion.agregar_servicio_adicional,
            ),
            (
                'cancelar_solicitud_cotizacion',
                views_solicitudes_cotizacion.cancelar_solicitud_cotizacion,
            ),
            (
                'gestionar_imagenes_linea',
                views_solicitudes_cotizacion.gestionar_imagenes_linea,
            ),
            (
                'api_imagenes_linea',
                views_solicitudes_cotizacion.api_imagenes_linea,
            ),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_views_reexporta_cliente_representativo(self):
        """Símbolos clave de envío/PDF/rechazo siguen en views."""
        pares = [
            (
                'api_enviar_cotizacion_cliente',
                views_cotizacion_cliente.api_enviar_cotizacion_cliente,
            ),
            (
                'preview_pdf_cotizacion',
                views_cotizacion_cliente.preview_pdf_cotizacion,
            ),
            (
                'descargar_pdf_cotizacion_final',
                views_cotizacion_cliente.descargar_pdf_cotizacion_final,
            ),
            (
                'notificar_front',
                views_cotizacion_cliente.notificar_front,
            ),
            (
                'notificar_cliente_pnc',
                views_cotizacion_pnc_cliente.notificar_cliente_pnc,
            ),
            (
                'responder_linea_cotizacion',
                views_cotizacion_cliente.responder_linea_cotizacion,
            ),
            (
                'rechazar_todas_lineas',
                views_cotizacion_cliente.rechazar_todas_lineas,
            ),
            (
                'registrar_motivo_rechazo_st',
                views_cotizacion_cliente.registrar_motivo_rechazo_st,
            ),
            (
                'registrar_motivo_rechazo_solicitud',
                views_cotizacion_cliente.registrar_motivo_rechazo_solicitud,
            ),
            (
                'enviar_solicitud_cliente',
                views_cotizacion_cliente.enviar_solicitud_cliente,
            ),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_views_reexporta_sync_st(self):
        """Símbolos de sync ST siguen en views."""
        pares = [
            (
                'generar_compras_solicitud',
                views_cotizacion_sync_st.generar_compras_solicitud,
            ),
            (
                'vincular_orden_solicitud',
                views_cotizacion_sync_st.vincular_orden_solicitud,
            ),
            (
                'crear_orden_fl_desde_cotizacion',
                views_cotizacion_sync_st.crear_orden_fl_desde_cotizacion,
            ),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_helpers_viven_en_utils_compartido(self):
        """
        Helpers REAC/profit NO están en views.py; viven en utils.

        EXPLICACIÓN: así solicitudes y cliente los usan sin import circular.
        """
        self.assertTrue(
            callable(cotizacion_reacondicionado_helpers._serializar_profit_config)
        )
        self.assertTrue(
            callable(
                cotizacion_reacondicionado_helpers._validar_y_calcular_reacondicionado
            )
        )
        self.assertTrue(
            callable(
                cotizacion_reacondicionado_helpers._crear_o_actualizar_linea_reacondicionado
            )
        )
        self.assertFalse(hasattr(almacen_views, '_serializar_profit_config'))
        self.assertFalse(
            hasattr(almacen_views, '_validar_y_calcular_reacondicionado')
        )

    def test_modulo_correcto_fase4(self):
        """__module__ apunta a los archivos hermanos correctos."""
        self.assertEqual(
            almacen_views.detalle_solicitud_cotizacion.__module__,
            'almacen.views_solicitudes_cotizacion',
        )
        self.assertEqual(
            almacen_views.api_enviar_cotizacion_cliente.__module__,
            'almacen.views_cotizacion_cliente',
        )
        self.assertEqual(
            almacen_views.generar_compras_solicitud.__module__,
            'almacen.views_cotizacion_sync_st',
        )
        self.assertEqual(
            cotizacion_reacondicionado_helpers._serializar_profit_config.__module__,
            'almacen.utils.cotizacion_reacondicionado_helpers',
        )

    def test_urls_fase4_resuelven_al_modulo_nuevo(self):
        """reverse/resolve de cotización apuntan a los módulos extraídos."""
        casos = [
            (
                'almacen:lista_solicitudes_cotizacion',
                {},
                views_solicitudes_cotizacion.lista_solicitudes_cotizacion,
            ),
            (
                'almacen:detalle_solicitud_cotizacion',
                {'pk': 1},
                views_solicitudes_cotizacion.detalle_solicitud_cotizacion,
            ),
            (
                'almacen:crear_solicitud_cotizacion',
                {},
                views_solicitudes_cotizacion.crear_solicitud_cotizacion,
            ),
            (
                'almacen:api_enviar_cotizacion_cliente',
                {'pk': 1},
                views_cotizacion_cliente.api_enviar_cotizacion_cliente,
            ),
            (
                'almacen:notificar_cliente_pnc',
                {'pk': 1},
                views_cotizacion_pnc_cliente.notificar_cliente_pnc,
            ),
            (
                'almacen:preview_pdf_cotizacion',
                {'pk': 1},
                views_cotizacion_cliente.preview_pdf_cotizacion,
            ),
            (
                'almacen:rechazar_todas_lineas',
                {'pk': 1},
                views_cotizacion_cliente.rechazar_todas_lineas,
            ),
            (
                'almacen:registrar_motivo_rechazo_st',
                {'pk': 1},
                views_cotizacion_cliente.registrar_motivo_rechazo_st,
            ),
            (
                'almacen:registrar_motivo_rechazo_solicitud',
                {'pk': 1},
                views_cotizacion_cliente.registrar_motivo_rechazo_solicitud,
            ),
            (
                'almacen:generar_compras_solicitud',
                {'pk': 1},
                views_cotizacion_sync_st.generar_compras_solicitud,
            ),
            (
                'almacen:vincular_orden_solicitud',
                {'pk': 1},
                views_cotizacion_sync_st.vincular_orden_solicitud,
            ),
            (
                'almacen:crear_orden_fl_desde_cotizacion',
                {'pk': 1},
                views_cotizacion_sync_st.crear_orden_fl_desde_cotizacion,
            ),
        ]
        for name, kwargs, expected in casos:
            match = resolve(reverse(name, kwargs=kwargs))
            self.assertIs(match.func, expected, msg=name)

    def test_views_py_es_fachada_sin_defs_http(self):
        """
        Tras Fase 4, views.py no define vistas HTTP propias.

        Solo reexporta callables; no debe quedar `def lista_...` en el monolito.
        """
        import inspect

        source = inspect.getsource(almacen_views)
        # No debe haber definiciones de vistas de negocio residuales
        self.assertNotIn('def lista_solicitudes_cotizacion', source)
        self.assertNotIn('def api_enviar_cotizacion_cliente', source)
        self.assertNotIn('def generar_compras_solicitud', source)
        self.assertNotIn('def _serializar_profit_config', source)
