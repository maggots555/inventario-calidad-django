"""
Tests de confinamiento de /media/ en desarrollo (DEBUG).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
La vista de media busca archivos en disco principal y alterno. Un ``..``
en la URL no debe poder leer ``/etc/passwd`` ni nada fuera de esas carpetas.
"""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from config.media_views import _archivo_si_esta_dentro_de


class MediaPathConfinadoTest(SimpleTestCase):
    """El path de la URL no puede escapar de la carpeta media."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.dentro = self.raiz / 'fotos' / 'ok.txt'
        self.dentro.parent.mkdir(parents=True)
        self.dentro.write_text('seguro', encoding='utf-8')

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_archivo_legitimo_dentro_de_media(self) -> None:
        hallado = _archivo_si_esta_dentro_de(self.raiz, 'fotos/ok.txt')
        self.assertEqual(hallado, self.dentro.resolve())

    def test_puntos_puntos_no_salen_de_media(self) -> None:
        """El comentario viejo de normpath mentía: ../../etc/passwd escapaba."""
        self.assertIsNone(
            _archivo_si_esta_dentro_de(self.raiz, '../../etc/passwd')
        )

    def test_path_absoluto_no_se_sirve(self) -> None:
        # En Linux Path(media) / '/etc/passwd' ignoraba media.
        self.assertIsNone(_archivo_si_esta_dentro_de(self.raiz, '/etc/passwd'))
