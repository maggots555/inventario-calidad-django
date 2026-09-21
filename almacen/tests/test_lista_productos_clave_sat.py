"""
La lista de productos muestra y filtra la clave SAT.

Objetivo de negocio:
    En almacén se ve de un vistazo qué productos ya tienen ClaveProdServ
    y se puede dejar en pantalla solo los que faltan.
"""

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from almacen.models import ProductoAlmacen
from almacen.views_catalogo import lista_productos


STORAGES_TEST = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


@override_settings(STORAGES=STORAGES_TEST)
class ListaProductosClaveSatTest(TestCase):
    """Filtro y badge de clave SAT en el catálogo de almacén."""

    def setUp(self):
        """
        Un usuario con permiso de ver productos y dos artículos.

        Efectos secundarios:
            Inserta un usuario y dos productos en la base de prueba.
        """
        self.usuario = User.objects.create_user(
            username='almacen_clave',
            password='clave-test',
        )
        permiso = Permission.objects.get(codename='view_productoalmacen')
        self.usuario.user_permissions.add(permiso)
        self.factory = RequestFactory()
        ProductoAlmacen.objects.create(
            codigo_producto='CON-SAT',
            nombre='Con clave',
            clave_sat='43211600',
        )
        ProductoAlmacen.objects.create(
            codigo_producto='SIN-SAT',
            nombre='Sin clave',
            clave_sat='',
        )

    def _get(self, clave_sat: str):
        """
        Llama la vista sin pasar por el middleware de país.

        Args:
            clave_sat: 'con' o 'sin'.

        Returns:
            HttpResponse de lista_productos.
        """
        request = self.factory.get(
            '/almacen/productos/',
            {'clave_sat': clave_sat},
        )
        request.user = self.usuario
        return lista_productos(request)

    def test_sin_clave_solo_muestra_los_vacios(self):
        """El filtro 'sin' deja fuera al producto que ya tiene clave."""
        respuesta = self._get('sin')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'SIN-SAT')
        self.assertContains(respuesta, 'Sin clave')
        self.assertNotContains(respuesta, 'CON-SAT')

    def test_con_clave_muestra_el_numero(self):
        """El filtro 'con' muestra la clave de 8 dígitos y no el vacío."""
        respuesta = self._get('con')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '43211600')
        self.assertContains(respuesta, 'CON-SAT')
        self.assertNotContains(respuesta, 'SIN-SAT')
