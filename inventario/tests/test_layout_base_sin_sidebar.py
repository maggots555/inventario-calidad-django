"""
Humo del layout staff: navbar superior sin sidebar lateral.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Tras retirar la barra lateral, queremos un test automático que falle si
alguien vuelve a meter `id="appSidebar"` en base.html o si se rompe la
navbar superior (única navegación global del backoffice).

Usamos RequestFactory + render_to_string (no Client) para evitar el
middleware multi-tenant, igual que otros tests de inventario.
"""

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            # Evita exigir manifest de collectstatic para CSS/JS nuevos
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class LayoutBaseSinSidebarTest(TestCase):
    """
    Objetivo: confirmar que base.html ya no incluye la sidebar lateral
    y que la navbar superior sigue presente.

    Efectos secundarios: crea un User mínimo en la BD de pruebas.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory y un usuario autenticado para renderizar el layout."""
        self.factory = RequestFactory()
        self.usuario = User.objects.create_user(
            username='layout_sidebar_test',
            password='testpass123',
        )

    def _request_autenticado(self):
        """
        Arma un request GET con sesión y messages (como en páginas staff).

        Returns:
            HttpRequest listo para render_to_string con context processors.
        """
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_base_html_sin_sidebar_con_navbar_superior(self):
        """
        base.html no debe tener appSidebar/overlay; sí modern-navbar y menú.
        """
        # Paso 1: renderizar el layout completo (como hereda casi toda página staff)
        html = render_to_string('base.html', {}, request=self._request_autenticado())

        # Paso 2: la sidebar lateral y su overlay ya no deben existir
        self.assertNotIn('id="appSidebar"', html)
        self.assertNotIn('id="sidebarOverlay"', html)
        self.assertNotIn('id="sidebarToggle"', html)
        self.assertNotIn('class="app-sidebar"', html)

        # Paso 3: la navegación canónica (navbar superior) debe seguir ahí
        self.assertIn('modern-navbar', html)
        self.assertIn('id="navbarToggle"', html)
        self.assertIn('navbar-menu', html)

        # Paso 4: el wrapper de contenido sigue (ancho completo, sin colapso)
        self.assertIn('id="mainWrapper"', html)
        self.assertNotIn('sidebar-collapsed', html)
        self.assertNotIn('sidebar-loading', html)

    def test_navbar_almacen_usa_etiqueta_corta_en_desktop(self):
        """
        En desktop el menú muestra "Almacén"; el texto largo va a menu-text-full (móvil).

        EXPLICACIÓN PARA PRINCIPIANTES:
        Esto ahorra ancho horizontal para que la barra quepa al 100% de zoom
        en laptops típicas, igual que "Config" vs "Configuración".
        """
        html = render_to_string('base.html', {}, request=self._request_autenticado())

        # Label corta visible en desktop
        self.assertIn('class="menu-text">Almacén</span>', html)
        # Label completa para el panel móvil
        self.assertIn('class="menu-text-full">Almacén/Compras</span>', html)
        # No debe repetir el texto largo en menu-text (evitar overflow)
        self.assertNotIn('class="menu-text">Almacén/Compras</span>', html)

    def test_navbar_almacen_dos_pasillos_sin_etiquetas_duplicadas(self):
        """
        El mega-menú de Almacén agrupa por tarea (Inventario | Adquisición)
        y ya no usa 3 columnas ni el nombre duplicado "Lista de Solicitudes".

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes había dos enlaces con el mismo texto: uno era una baja de
        stock (SolicitudBaja) y otro una cotización a proveedores. Eso
        confundía. Ahora cada destino tiene un nombre distinto y las 14
        URLs siguen en el menú (no se perdió ninguna pantalla).
        """
        html = render_to_string('base.html', {}, request=self._request_autenticado())

        # Paso 1: un solo dropdown de 2 columnas (mismo patrón que Servicio Técnico)
        self.assertIn('id="dropdown-almacen"', html)
        self.assertNotIn('dropdown-mega-3col', html)
        self.assertIn('dropdown-lane--inventario', html)
        self.assertIn('dropdown-lane--adquisicion', html)

        # Paso 2: títulos de pasillo y nombres que ya no se confunden
        self.assertIn('Inventario', html)
        self.assertIn('Adquisición', html)
        self.assertIn('Ver cotizaciones', html)
        self.assertIn('Solicitudes de salida', html)
        self.assertIn('Pedir pieza', html)
        self.assertIn('Nueva cotización', html)
        self.assertIn('Nueva compra', html)
        self.assertEqual(html.count('Lista de Solicitudes'), 0)

        # Paso 3: las 14 pantallas del menú siguen enlazadas (nada se perdió)
        urls_menu_almacen = (
            'almacen:dashboard',
            'almacen:lista_productos',
            'almacen:lista_unidades',
            'almacen:dashboard_distribucion_sucursales',
            'almacen:lista_movimientos',
            'almacen:crear_solicitud',
            'almacen:lista_solicitudes',
            'almacen:crear_solicitud_cotizacion',
            'almacen:lista_solicitudes_cotizacion',
            'almacen:panel_cotizaciones',
            'almacen:crear_compra',
            'almacen:lista_compras',
            'almacen:lista_proveedores',
            'almacen:lista_categorias',
        )
        for nombre_url in urls_menu_almacen:
            self.assertIn(reverse(nombre_url), html, msg=f'Falta {nombre_url} en el menú')

    def test_navbar_pasillos_unificados_en_cuatro_menus(self):
        """
        Inventario, Calidad, Servicio Técnico y Config usan el mismo kit
        visual de pasillos que Almacén (riel, título, CTA).

        EXPLICACIÓN PARA PRINCIPIANTES:
        Almacén estrenó el estilo de “pasillo”. Este test evita que los
        otros cuatro menús vuelvan al listado plano sin riel ni acciones
        de crear destacadas, y confirma que ninguna URL se perdió.
        """
        html = render_to_string('base.html', {}, request=self._request_autenticado())

        # Paso 1: cada menú tiene su pasillo (color distinto por módulo)
        self.assertIn('id="dropdown-inventario"', html)
        self.assertIn('dropdown-lane--sky', html)
        self.assertIn('id="dropdown-calidad"', html)
        self.assertIn('dropdown-lane--rose', html)
        self.assertIn('id="dropdown-servicio"', html)
        self.assertIn('dropdown-lane--violet', html)
        self.assertIn('id="dropdown-configuracion"', html)
        self.assertIn('dropdown-lane--slate', html)

        # Paso 2: ST sigue en 2 pasillos; ya no hay color inline en el icono
        self.assertGreaterEqual(html.count('dropdown-lane--sky'), 2)
        self.assertIn('Operación', html)
        self.assertIn('Seguimiento', html)
        self.assertNotIn('style="color:#0d9488"', html)
        self.assertIn('data-nav-loader', html)

        # Paso 3: acciones de crear destacadas (mismo patrón que Almacén)
        self.assertIn('Nuevo producto', html)
        self.assertIn('Registrar movimiento', html)
        self.assertIn('Registrar incidencia', html)
        self.assertIn('Nueva orden', html)
        self.assertIn('Nueva sucursal', html)
        self.assertIn('Nuevo empleado', html)

        # Paso 4: URLs de los cuatro menús siguen en el HTML (usuario sin rol extra)
        urls_menus = (
            'dashboard_inventario',
            'lista_productos',
            'crear_producto',
            'lista_movimientos',
            'crear_movimiento',
            'movimiento_rapido',
            'movimiento_fraccionario',
            'scorecard:dashboard',
            'scorecard:reportes',
            'scorecard:lista_incidencias',
            'scorecard:crear_incidencia',
            'scorecard:lista_categorias',
            'scorecard:lista_componentes',
            'servicio_tecnico:inicio',
            'servicio_tecnico:dashboard_seguimiento_oow_fl',
            'servicio_tecnico:dashboard_cotizaciones',
            'servicio_tecnico:consultar_sicser',
            'servicio_tecnico:seleccionar_tipo_orden',
            'servicio_tecnico:lista_activas',
            'servicio_tecnico:lista_finalizadas',
            'servicio_tecnico:concentrado_semanal',
            'servicio_tecnico:dashboard_encuestas',
            'servicio_tecnico:dashboard_feedback_rechazo',
            'servicio_tecnico:dashboard_seguimiento_enlaces',
            'servicio_tecnico:dashboard_seguimiento_piezas',
            'servicio_tecnico:dashboard_rhitso',
            'servicio_tecnico:lista_referencias_gama',
            'lista_sucursales',
            'crear_sucursal',
            'lista_empleados',
            'crear_empleado',
            'admin_storage_monitor',
        )
        for nombre_url in urls_menus:
            self.assertIn(reverse(nombre_url), html, msg=f'Falta {nombre_url} en el menú')
