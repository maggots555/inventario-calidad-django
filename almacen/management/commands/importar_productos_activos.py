"""
Comando para copiar el Excel de productos activos a la base local.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
La lógica vive en almacen/utils/importar_productos_excel.py.
Este archivo solo recibe la ruta, llama esa función e imprime el resumen.
La base es la de default (en esta máquina, db.sqlite3 de pruebas).
"""

from django.core.management.base import BaseCommand, CommandError

from almacen.utils.importar_productos_excel import (
    ErrorImportacionProductos,
    importar_productos_activos,
)


class Command(BaseCommand):
    """
    Aplica el Excel de productos activos sobre la base default.

    Objetivo de negocio:
        Dejar el catálogo de pruebas igual al que se descargó de producción.

    Efectos secundarios:
        Los de importar_productos_activos: altas, cambios y desactivaciones
        en una sola transacción.
    """

    help = (
        'Copia el Excel de productos activos al catálogo local. '
        'Crea, actualiza y desactiva. No borra historial.'
    )

    def add_arguments(self, parser):
        """
        Declara la ruta del archivo como argumento obligatorio.

        Args:
            parser: parser de argparse que arma Django.

        Efectos secundarios:
            Ninguno.
        """
        parser.add_argument(
            'archivo',
            help='Ruta del .xlsx descargado desde Productos de almacén.',
        )

    def handle(self, *args, **options):
        """
        Corre la importación e imprime cuántos productos se movieron.

        Args:
            args: no se usan.
            options: trae 'archivo', la ruta del Excel.

        Efectos secundarios:
            Escribe el catálogo en la base default. Si el archivo viene mal,
            no guarda nada y el comando termina con error.
        """
        try:
            resultado = importar_productos_activos(options['archivo'])
        except ErrorImportacionProductos as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f'Creados: {len(resultado.creados)}')
        self.stdout.write(f'Actualizados: {len(resultado.actualizados)}')
        self.stdout.write(f'Ya iguales: {len(resultado.iguales)}')
        self.stdout.write(f'Desactivados: {len(resultado.desactivados)}')
        if resultado.desactivados:
            self.stdout.write('  ' + ', '.join(resultado.desactivados))
        if resultado.categorias_creadas:
            self.stdout.write(
                'Categorías nuevas: ' + ', '.join(resultado.categorias_creadas)
            )
        if resultado.proveedores_creados:
            self.stdout.write(
                'Proveedores nuevos: ' + ', '.join(resultado.proveedores_creados)
            )
