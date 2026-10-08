"""
El concentrado semanal no debe contar dos veces un candidato RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Un equipo asignado a un técnico ya suma 1 en la fila de ese técnico.
Si además está marcado como candidato a RHITSO, es el mismo equipo:
no entró otro. Antes esa marca se sumaba otra vez al total.

Estos tests revisan el cálculo y que el PDF del resumen se genera.
"""

from datetime import date, datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from inventario.models import Empleado, Sucursal
from servicio_tecnico.concentrado_semanal import (
    comparar_concentrado_con_semana_anterior,
    obtener_concentrado_semanal,
)
from servicio_tecnico.models import OrdenServicio
from servicio_tecnico.pdf_concentrado import generar_pdf_concentrado


# Lunes 5 de octubre de 2026 (el 8 es jueves, así que el 5 es lunes).
LUNES_SEMANA = date(2026, 10, 5)


class ConcentradoRhitsoNoDobleConteoTest(TestCase):
    """
    El total de asignación cuenta cada equipo una sola vez.

    Objetivo:
        Un candidato RHITSO asignado a un técnico entra en la fila del
        técnico y en la tabla aparte, pero no infla el total.
    Efectos secundarios:
        Crea sucursal, dos técnicos y dos órdenes en la base de prueba.
    """

    def setUp(self):
        """
        Arma la semana de prueba.

        Dos equipos ingresan el mismo lunes:
        - Ana tiene uno normal.
        - Juan tiene uno marcado como candidato RHITSO.
        """
        self.sucursal = Sucursal.objects.create(
            codigo='TST-RHITSO',
            nombre='Sucursal Test Concentrado RHITSO',
            ciudad='CDMX',
        )
        self.ana = Empleado.objects.create(
            nombre_completo='Ana Tecnica Concentrado',
            cargo='Técnico',
            area='Laboratorio',
            sucursal=self.sucursal,
        )
        self.juan = Empleado.objects.create(
            nombre_completo='Juan Tecnico Concentrado',
            cargo='Técnico',
            area='Laboratorio',
            sucursal=self.sucursal,
        )
        # 10:00 UTC sigue siendo lunes 5; el filtro usa la fecha, no la hora.
        ingreso = timezone.make_aware(datetime(2026, 10, 5, 10, 0))

        OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.ana,
            es_candidato_rhitso=False,
            fecha_ingreso=ingreso,
        )
        OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.juan,
            es_candidato_rhitso=True,
            fecha_ingreso=ingreso,
        )

    def test_candidato_rhitso_no_infla_el_total(self):
        """
        Dos equipos reales: el total es 2, aunque uno sea candidato RHITSO.

        Si el bug volviera, el total diría 3 (2 técnicos + 1 fila RHITSO).
        """
        datos = obtener_concentrado_semanal(LUNES_SEMANA)

        nombres = [fila['nombre'] for fila in datos['asignacion']]
        self.assertNotIn('Candidatos RHITSO', nombres)

        # Cada técnico conserva su equipo, incluido el que va a RHITSO.
        por_nombre = {fila['nombre']: fila['total'] for fila in datos['asignacion']}
        self.assertEqual(por_nombre[self.ana.nombre_completo], 1)
        self.assertEqual(por_nombre[self.juan.nombre_completo], 1)

        # El total de la tabla de ingenieros no vuelve a sumar el candidato.
        self.assertEqual(datos['total_asignados'], 2)
        self.assertEqual(datos['totales_asignacion']['Lunes'], 2)
        self.assertEqual(datos['totales_asignacion']['total'], 2)

        # La tabla aparte sí lo muestra, pero no es un equipo nuevo.
        self.assertEqual(datos['candidatos_rhitso']['nombre'], 'Candidatos RHITSO')
        self.assertEqual(datos['candidatos_rhitso']['Lunes'], 1)
        self.assertEqual(datos['candidatos_rhitso']['total'], 1)

    def test_la_plantilla_separa_rhitso_del_total(self):
        """
        El HTML de la página muestra RHITSO aparte y el total de ingenieros en 2.

        EXPLICACIÓN PARA PRINCIPIANTES:
        No abrimos el navegador: Django rellena la misma plantilla que ve
        el usuario y aquí leemos el resultado.
        """
        datos = obtener_concentrado_semanal(LUNES_SEMANA)
        iso = LUNES_SEMANA.isocalendar()
        semana = f'{iso[0]}-W{iso[1]:02d}'
        request = RequestFactory().get('/servicio-tecnico/concentrado-semanal/')
        # En tests el manifiesto de estáticos no está armado; usamos el storage simple.
        storages = {
            **settings.STORAGES,
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        }
        with override_settings(STORAGES=storages):
            html = render_to_string(
                'servicio_tecnico/concentrado_semanal.html',
                {
                    **datos,
                    'semana_actual_iso': semana,
                    'semana_anterior_iso': semana,
                    'semana_siguiente_iso': semana,
                    'sucursal_id_seleccionada': None,
                    'sucursales': [],
                    'grupos_sucursales': [],
                    'grafico_ingresos_html': '',
                    'grafico_egresos_html': '',
                    'page_title': 'Concentrado de prueba',
                },
                request=request,
            )

        self.assertIn('Candidatos RHITSO', html)
        self.assertIn('no se suman al total', html)
        self.assertIn('Total Equipos Ingresados', html)
        # La fila RHITSO ya no vive dentro de la tabla de ingenieros.
        self.assertNotIn('concentrado-fila-rhitso', html.split('Total Equipos Ingresados')[0])

    def test_lista_rhitso_y_variacion_de_la_semana(self):
        """
        La lista nombra al candidato y la variación resta la semana anterior.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Esta semana Juan tiene el único candidato. La semana pasada Ana
        tenía otro. La variación de RHITSO es 1 - 1 = 0. El equipo de Ana
        de esta semana no entra a la lista porque no es candidato.
        """
        ingreso_previo = timezone.make_aware(datetime(2026, 9, 28, 10, 0))
        OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.ana,
            es_candidato_rhitso=True,
            fecha_ingreso=ingreso_previo,
        )

        datos = obtener_concentrado_semanal(LUNES_SEMANA)
        anterior = obtener_concentrado_semanal(date(2026, 9, 28))
        comparacion = comparar_concentrado_con_semana_anterior(datos, anterior)

        self.assertEqual(len(datos['lista_candidatos_rhitso']), 1)
        candidato = datos['lista_candidatos_rhitso'][0]
        self.assertEqual(candidato['dia'], 'Lunes')
        self.assertEqual(candidato['tecnico'], self.juan.nombre_completo)
        self.assertEqual(candidato['sucursal'], self.sucursal.nombre)
        self.assertTrue(candidato['folio'].startswith('ORD-'))
        self.assertNotIn(
            self.ana.nombre_completo,
            [item['tecnico'] for item in datos['lista_candidatos_rhitso']],
        )

        self.assertEqual(comparacion['candidatos_rhitso'], 1)
        self.assertEqual(comparacion['variacion_rhitso'], 0)
        # Sin detalle de equipo, ingreso y egreso de estas órdenes quedan en 0.
        self.assertEqual(comparacion['ingresaron'], 0)
        self.assertEqual(comparacion['balance'], 0)
        self.assertEqual(comparacion['variacion_ingresaron'], 0)
        self.assertEqual(
            datos['candidatos_rhitso']['total'],
            len(datos['lista_candidatos_rhitso']),
        )
        self.assertEqual(
            sum(datos['candidatos_rhitso'][dia] for dia in datos['dias_semana']),
            datos['candidatos_rhitso']['total'],
        )

        pdf = generar_pdf_concentrado(datos, anterior).getvalue()
        # El nombre va comprimido dentro del PDF; aquí revisamos que sea
        # una hoja vertical (carta) y que el título sea el del concentrado.
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(b'/MediaBox [ 0 0 612 792 ]', pdf)
        self.assertIn(b'Concentrado semanal', pdf)

    def test_grupo_cis_no_mezcla_sucursales_foraneas(self):
        """
        CIS y foráneas salen de la misma regla para la página, el Excel y el PDF.

        EXPLICACIÓN PARA PRINCIPIANTES:
        El nombre de la sucursal decide el grupo: si dice Drop o Satélite,
        es CIS. Esta prueba usa el filtro compartido, no una copia.
        """
        from servicio_tecnico.views_concentrado import resolver_filtros_concentrado

        drop = Sucursal.objects.create(
            codigo='DROP-REV',
            nombre='Drop Off Revision',
            ciudad='CDMX',
        )
        satelite = Sucursal.objects.create(
            codigo='SAT-REV',
            nombre='Satelite Revision',
            ciudad='CDMX',
        )
        request = RequestFactory().get('/', {
            'sucursal_id': 'grupo_cis',
            'semana': '2026-W41',
        })
        filtros = resolver_filtros_concentrado(request)
        ids = set(filtros['sucursal_ids'])

        self.assertEqual(filtros['lunes'], LUNES_SEMANA)
        self.assertIsNone(filtros['sucursal_id'])
        self.assertIn(drop.id, ids)
        self.assertIn(satelite.id, ids)
        self.assertNotIn(self.sucursal.id, ids)
