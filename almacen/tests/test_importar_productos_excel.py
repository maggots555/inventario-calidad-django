"""
El Excel de productos activos deja el catálogo local a la par.

Objetivo de negocio:
    Lo que viene en el archivo se crea o se actualiza. Lo que ya no viene
    se oculta, sin borrar unidades ni compras ligadas a ese producto.
"""

import tempfile
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, override_settings
from openpyxl import Workbook

from almacen.models import CategoriaAlmacen, ProductoAlmacen, Proveedor, UnidadInventario
from almacen.utils.importar_productos_excel import (
    ErrorImportacionProductos,
    importar_productos_activos,
)
from inventario.models import Sucursal


STORAGES_TEST = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

_ENCABEZADOS = [
    'Código',
    'Nombre',
    'Descripción',
    'Tipo',
    'Categoría',
    'Sucursal',
    'Ubicación física',
    'Stock actual',
    'Stock mínimo',
    'Stock máximo',
    'Estado de stock',
    'Clave SAT',
    'Costo unitario',
    'Valor del stock',
    'Proveedor',
    'Días de reposición',
    'Creado',
    'Última actualización',
]


def _fila(codigo, nombre, **cambios):
    """
    Arma una fila con los mismos encabezados del Excel de producción.

    Args:
        codigo: codigo_producto.
        nombre: nombre del producto.
        cambios: columnas por su nombre de encabezado.

    Returns:
        list en el orden de _ENCABEZADOS.
    """
    datos = {
        'Código': codigo,
        'Nombre': nombre,
        'Descripción': '',
        'Tipo': 'Resurtible (Stock Permanente)',
        'Categoría': 'Discos y Almacenamiento',
        'Sucursal': 'Almacén central',
        'Ubicación física': '',
        'Stock actual': 0,
        'Stock mínimo': 5,
        'Stock máximo': 50,
        'Estado de stock': 'Agotado',
        'Clave SAT': '43211600',
        'Costo unitario': 0,
        'Valor del stock': 0,
        'Proveedor': '',
        'Días de reposición': 7,
        'Creado': None,
        'Última actualización': None,
    }
    datos.update(cambios)
    return [datos[columna] for columna in _ENCABEZADOS]


def _guardar_excel(filas):
    """
    Escribe un .xlsx temporal y devuelve su ruta.

    Args:
        filas: listas ya ordenadas como el Excel real.

    Returns:
        str con la ruta. Quien llama debe borrarla.
    """
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Productos activos'
    hoja.append(_ENCABEZADOS)
    for fila in filas:
        hoja.append(fila)
    archivo = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    ruta = archivo.name
    archivo.close()
    libro.save(ruta)
    return ruta


@override_settings(STORAGES=STORAGES_TEST)
class ImportarProductosExcelTest(TestCase):
    """Altas, cambios y desactivación a partir del Excel."""

    def test_actualiza_crea_y_desactiva_sin_borrar_la_unidad(self):
        """
        El código que ya existe cambia de nombre, el nuevo se crea
        y el que no viene en el archivo queda inactivo con su unidad.
        """
        viejo = ProductoAlmacen.objects.create(
            codigo_producto='P-VIEJO',
            nombre='Nombre local',
            clave_sat='',
            costo_unitario=Decimal('1.00'),
        )
        sobra = ProductoAlmacen.objects.create(
            codigo_producto='P-SOBRA',
            nombre='Ya no está en producción',
        )
        unidad = UnidadInventario.objects.create(producto=sobra, marca='Kingston')
        sucursal = Sucursal.objects.create(codigo='SAT', nombre='Satelite')
        con_sucursal = ProductoAlmacen.objects.create(
            codigo_producto='P-SUC',
            nombre='En sucursal',
            sucursal=sucursal,
        )

        ruta = _guardar_excel([
            _fila('P-VIEJO', 'Nombre de producción', **{
                'Costo unitario': 12.5,
                'Clave SAT': 43211600,
                'Proveedor': 'SIC STOCK',
            }),
            _fila('P-NUEVO', 'Pieza nueva', **{
                'Categoría': 'Categoria Que No Existia',
                'Proveedor': 'SOL SATA',
                'Stock actual': 3,
            }),
            _fila('P-SUC', 'En sucursal'),
        ])
        try:
            resultado = importar_productos_activos(ruta)
        finally:
            Path(ruta).unlink(missing_ok=True)

        viejo.refresh_from_db()
        sobra.refresh_from_db()
        con_sucursal.refresh_from_db()
        nuevo = ProductoAlmacen.objects.get(codigo_producto='P-NUEVO')

        self.assertEqual(resultado.actualizados, ['P-VIEJO', 'P-SUC'])
        self.assertEqual(resultado.creados, ['P-NUEVO'])
        self.assertEqual(resultado.desactivados, ['P-SOBRA'])
        self.assertEqual(viejo.nombre, 'Nombre de producción')
        self.assertEqual(viejo.clave_sat, '43211600')
        self.assertEqual(viejo.costo_unitario, Decimal('12.50'))
        self.assertEqual(viejo.proveedor_principal.nombre, 'SIC STOCK')
        self.assertTrue(viejo.activo)
        self.assertEqual(nuevo.stock_actual, 3)
        self.assertEqual(nuevo.categoria.nombre, 'Categoria Que No Existia')
        self.assertEqual(nuevo.proveedor_principal.nombre, 'SOL SATA')
        self.assertIsNone(con_sucursal.sucursal_id)
        self.assertFalse(sobra.activo)
        self.assertTrue(UnidadInventario.objects.filter(pk=unidad.pk).exists())
        self.assertTrue(Proveedor.objects.filter(nombre='SIC STOCK').exists())
        self.assertTrue(
            CategoriaAlmacen.objects.filter(nombre='Categoria Que No Existia').exists()
        )

    def test_una_fila_invalida_no_guarda_nada(self):
        """
        Si la segunda fila trae un tipo desconocido, el nombre de la
        primera tampoco cambia.
        """
        producto = ProductoAlmacen.objects.create(
            codigo_producto='P-VIEJO',
            nombre='Nombre local',
        )
        ruta = _guardar_excel([
            _fila('P-VIEJO', 'Nombre de producción'),
            _fila('P-MAL', 'Roto', **{'Tipo': 'inventado'}),
        ])
        try:
            with self.assertRaises(ErrorImportacionProductos):
                importar_productos_activos(ruta)
        finally:
            Path(ruta).unlink(missing_ok=True)

        producto.refresh_from_db()
        self.assertEqual(producto.nombre, 'Nombre local')
        self.assertFalse(ProductoAlmacen.objects.filter(codigo_producto='P-MAL').exists())

    def test_sucursal_desconocida_detiene_el_archivo(self):
        """Un nombre de sucursal que no existe no deja productos a medias."""
        ruta = _guardar_excel([
            _fila('P-NUEVO', 'Pieza', **{'Sucursal': 'Sucursal Fantasma'}),
        ])
        try:
            with self.assertRaises(ErrorImportacionProductos):
                importar_productos_activos(ruta)
        finally:
            Path(ruta).unlink(missing_ok=True)
        self.assertFalse(ProductoAlmacen.objects.filter(codigo_producto='P-NUEVO').exists())
