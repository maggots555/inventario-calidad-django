"""
El worker de Celery debe abrir la base del país que encoló la vista.

EXPLICACIÓN PARA PRINCIPIANTES:
El botón de rewind arma una cadena de dos tareas (video y luego correo).
Antes el país viajaba suelto, como tercer valor, y la señal de Celery no
lo veía: el worker buscaba la orden en México. Estos tests comprueban
que el país llega con nombre y que, si una tarea vieja aún lo manda
suelto, la señal igual lo reconoce.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from config.celery import configurar_contexto_pais, limpiar_contexto_pais
from config.middleware_pais import get_current_db_alias
from servicio_tecnico.services.rewind_egreso import _delay_chain_rewind
from servicio_tecnico.tasks import (
    enviar_rewind_egreso_email_task,
    generar_video_resumen_task,
)


class ContextoPaisCeleryRewindTest(SimpleTestCase):
    """
    Objetivo: la señal task_prerun deja el alias del país en el hilo.

    Efectos: escribe y borra thread-locals. No toca la base de datos.
    """

    def tearDown(self):
        # La nota adhesiva del país no debe contaminar el siguiente test.
        limpiar_contexto_pais(
            task_id='test',
            task=None,
            args=(),
            kwargs={},
            retval=None,
            state='SUCCESS',
        )

    def _aplicar(self, task, args, kwargs):
        """Corre la misma señal que Celery dispara antes de la tarea."""
        configurar_contexto_pais(
            task_id='test-rewind',
            task=task,
            args=args,
            kwargs=kwargs,
        )

    def test_db_alias_con_nombre_abre_argentina(self):
        """Los correos y el video de galería mandan db_alias= por nombre."""
        self._aplicar(
            generar_video_resumen_task,
            args=(4360, 7),
            kwargs={'db_alias': 'argentina'},
        )
        self.assertEqual(get_current_db_alias(), 'argentina')

    def test_db_alias_suelto_en_el_video_tambien_abre_argentina(self):
        """Regresión: la cadena vieja pasaba el país en la posición 3."""
        self._aplicar(
            generar_video_resumen_task,
            args=(4360, 7, 'argentina'),
            kwargs={},
        )
        self.assertEqual(get_current_db_alias(), 'argentina')

    def test_db_alias_suelto_en_el_correo_de_la_cadena(self):
        """
        La segunda tarea recibe primero el resultado del video.
        El país sigue siendo el último valor, no el id de la orden.
        """
        self._aplicar(
            enviar_rewind_egreso_email_task,
            args=({'success': True}, 4360, 7, ['copia@sic.com.mx'], 'chile'),
            kwargs={},
        )
        self.assertEqual(get_current_db_alias(), 'chile')

    def test_sin_pais_el_worker_usa_mexico(self):
        """Beat y tareas viejas no traen db_alias: el país por defecto es México."""
        self._aplicar(generar_video_resumen_task, args=(4360, 7), kwargs={})
        self.assertEqual(get_current_db_alias(), 'mexico')

    def test_alias_desconocido_cae_en_mexico(self):
        """Un alias que no está en PAISES_CONFIG no debe abrir otra base."""
        self._aplicar(
            generar_video_resumen_task,
            args=(),
            kwargs={'db_alias': 'narnia'},
        )
        self.assertEqual(get_current_db_alias(), 'mexico')


class CadenaRewindPasaPaisPorNombreTest(SimpleTestCase):
    """
    Objetivo: al encolar el rewind, db_alias va en kwargs, no suelto en args.

    Efectos: no publica nada en Redis; la cadena se reemplaza por un mock.
    """

    def test_las_dos_tareas_llevan_db_alias_con_nombre(self):
        resultado = MagicMock()
        resultado.id = 'tarea-falsa'

        with patch('celery.chain') as cadena_mock:
            # chain(...) devuelve la cadena; .delay() es lo que encola en Redis.
            cadena_mock.return_value.delay.return_value = resultado
            devuelto = _delay_chain_rewind(
                orden_id=4360,
                usuario_id=7,
                destinatarios_copia=['copia@sic.com.mx'],
                db_alias='argentina',
            )

        self.assertIs(devuelto, resultado)
        firma_video, firma_correo = cadena_mock.call_args.args

        # El id de la orden sigue suelto. El país ya no: va con nombre.
        self.assertEqual(firma_video.args, (4360, 7))
        self.assertEqual(firma_video.kwargs.get('db_alias'), 'argentina')
        self.assertEqual(
            firma_correo.args,
            (4360, 7, ['copia@sic.com.mx']),
        )
        self.assertEqual(firma_correo.kwargs.get('db_alias'), 'argentina')
