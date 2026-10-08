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

    def test_la_semana_iso_vuelve_al_mismo_lunes(self):
        """
        El texto de la semana que viaja en el modal abre el mismo lunes.

        EXPLICACIÓN PARA PRINCIPIANTES:
        El 29 de diciembre de 2025 cae en la semana 1 de 2026.
        Si el correo guardara «2025-W01», mandaría otra semana.
        """
        from servicio_tecnico.concentrado_semanal import (
            lunes_desde_numero_semana,
            semana_iso_desde_lunes,
        )

        lunes = date(2025, 12, 29)
        texto = semana_iso_desde_lunes(lunes)
        self.assertEqual(texto, '2026-W01')
        self.assertEqual(lunes_desde_numero_semana(2026, 1), lunes)

    def test_un_grupo_sin_sucursales_no_cuenta_todas(self):
        """
        Una lista vacía de sucursales deja el reporte en cero.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Elegir CIS cuando no hay sucursales CIS no puede mandar
        el concentrado de todo el país con la etiqueta de CIS.
        """
        datos = obtener_concentrado_semanal(LUNES_SEMANA, sucursal_ids=[])
        self.assertEqual(datos['total_asignados'], 0)


class CorreoConcentradoTest(TestCase):
    """
    El modal ofrece los contactos de dirección y el envío solo usa esos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    No se manda correo de verdad. Revisamos tres cosas:
    quién aparece en la lista, que el botón de confirmar encola la tarea,
    y que el mensaje lleva el Excel y el PDF.
    """

    def test_une_contactos_del_env_y_gerentes_sin_duplicar(self):
        """
        Un gerente cuyo correo ya está en el .env no sale dos veces.
        """
        from inventario.models import Empleado
        from servicio_tecnico.services.concentrado_correo import (
            destinatarios_concentrado,
            filtrar_destinatarios_elegidos,
        )

        Empleado.objects.create(
            nombre_completo='Gerente Duplicado',
            cargo='Gerente',
            area='Dirección',
            rol='gerente_general',
            activo=True,
            email='jefe@test.local',
        )
        Empleado.objects.create(
            nombre_completo='Otra Gerente',
            cargo='Gerente',
            area='Dirección',
            rol='gerente_general',
            activo=True,
            email='otra@test.local',
        )
        Empleado.objects.create(
            nombre_completo='Gerente Inactivo',
            cargo='Gerente',
            area='Dirección',
            rol='gerente_general',
            activo=False,
            email='inactivo@test.local',
        )
        Empleado.objects.create(
            nombre_completo='Técnico con correo',
            cargo='Técnico',
            area='Laboratorio',
            rol='tecnico',
            activo=True,
            email='tecnico@test.local',
        )

        with override_settings(
            JEFE_CALIDAD_EMAIL='calidad@test.local',
            JEFE_CALIDAD_NOMBRE='Ana Calidad',
            JEFE_CALIDAD_2_EMAIL='esto-no-es-un-correo',
            JEFE_GENERAL_EMAIL='jefe@test.local',
            JEFE_GENERAL_NOMBRE='Jefe General',
        ):
            personas = destinatarios_concentrado()
            elegidos = filtrar_destinatarios_elegidos([
                'calidad@test.local',
                'OTRA@test.local',
                'intruso@test.local',
            ])

        correos = [persona['email'] for persona in personas]
        self.assertEqual(correos, [
            'calidad@test.local',
            'jefe@test.local',
            'otra@test.local',
        ])
        self.assertEqual(personas[0]['origen'], 'Jefe de Calidad')
        self.assertEqual(personas[2]['origen'], 'Gerente General')
        self.assertEqual(elegidos, ['calidad@test.local', 'otra@test.local'])

    def test_el_modal_muestra_los_contactos_ya_marcados(self):
        """
        La plantilla trae el checkbox marcado: el usuario solo confirma.
        """
        datos = obtener_concentrado_semanal(LUNES_SEMANA)
        iso = LUNES_SEMANA.isocalendar()
        semana = f'{iso[0]}-W{iso[1]:02d}'
        request = RequestFactory().get('/servicio-tecnico/concentrado-semanal/')
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
                    'destinatarios_correo': [{
                        'nombre': 'Ana Calidad',
                        'email': 'calidad@test.local',
                        'origen': 'Jefe de Calidad',
                    }],
                },
                request=request,
            )

        self.assertIn('Compartir por correo', html)
        self.assertIn('modalCompartirConcentrado', html)
        self.assertIn('value="calidad@test.local"', html)
        self.assertIn('checked', html)
        self.assertIn('formCompartirConcentrado', html)
        self.assertIn('Enviar Excel y PDF', html)

    def test_confirmar_encola_solo_los_correos_marcados(self):
        """
        El POST del modal encola la tarea y deja fuera un correo ajeno.
        """
        from unittest.mock import patch

        from django.contrib.auth.models import User
        from django.contrib.messages.middleware import MessageMiddleware
        from django.contrib.sessions.middleware import SessionMiddleware

        from servicio_tecnico.views_concentrado import compartir_concentrado_semanal

        usuario = User.objects.create_superuser(
            username='direccion',
            email='direccion@test.local',
            password='pass-12345',
        )
        fabrica = RequestFactory()
        request = fabrica.post('/servicio-tecnico/concentrado-semanal/compartir/', {
            'semana': '2026-W41',
            'destinatarios': ['calidad@test.local', 'intruso@test.local'],
        })
        request.user = usuario
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        MessageMiddleware(lambda req: None).process_request(request)

        with override_settings(
            JEFE_CALIDAD_EMAIL='calidad@test.local',
            JEFE_CALIDAD_NOMBRE='Ana Calidad',
            JEFE_CALIDAD_2_EMAIL='',
            JEFE_GENERAL_EMAIL='',
        ):
            with patch(
                'servicio_tecnico.tasks_concentrado.enviar_concentrado_semanal_task.delay'
            ) as encolar:
                respuesta = compartir_concentrado_semanal(request)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('semana=2026-W41', respuesta.url)
        encolar.assert_called_once()
        kwargs = encolar.call_args.kwargs
        self.assertEqual(kwargs['lunes_iso'], '2026-10-05')
        self.assertEqual(kwargs['destinatarios'], ['calidad@test.local'])
        self.assertIn('db_alias', kwargs)

    def test_el_correo_adjunta_excel_y_pdf(self):
        """
        El mensaje sale con texto plano, HTML y los dos archivos.
        """
        from django.core import mail

        from servicio_tecnico.services.concentrado_correo import (
            enviar_correo_concentrado,
        )

        contexto = {
            'numero_semana': 41,
            'año': 2026,
            'lunes': '05/10/2026',
            'viernes': '09/10/2026',
            'alcance': 'Todas las sucursales',
            'ingresaron': 3,
            'salieron': 1,
            'balance': '+2',
            'candidatos_rhitso': 1,
            'variacion_ingresaron': '+1',
            'variacion_salieron': '0',
            'variacion_balance': '+1',
            'variacion_rhitso': '0',
            'ahora_local': None,
        }
        with override_settings(
            JEFE_CALIDAD_EMAIL='calidad@test.local',
            JEFE_CALIDAD_NOMBRE='Ana Calidad',
            JEFE_CALIDAD_2_EMAIL='',
            JEFE_GENERAL_EMAIL='',
        ):
            enviados = enviar_correo_concentrado(
                destinatarios=['calidad@test.local', 'intruso@test.local'],
                contexto=contexto,
                excel_bytes=b'excel-falso',
                pdf_bytes=b'%PDF-falso',
                nombre_excel='Concentrado_Semanal_S41_2026.xlsx',
                nombre_pdf='Concentrado_Semanal_S41_2026.pdf',
            )

        self.assertEqual(enviados, 1)
        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.to, ['calidad@test.local'])
        self.assertIn('Ingresaron: 3', mensaje.body)
        self.assertIn('Semana 41', mensaje.subject)
        nombres = []
        for adjunto in mensaje.attachments:
            if isinstance(adjunto, tuple):
                nombres.append(adjunto[0])
            else:
                nombres.append(adjunto.get_filename())
        self.assertIn('Concentrado_Semanal_S41_2026.xlsx', nombres)
        self.assertIn('Concentrado_Semanal_S41_2026.pdf', nombres)
        html = mensaje.alternatives[0][0]
        self.assertIn('Candidatos RHITSO', html)
        self.assertIn('cid:logo_sic_white', html)
