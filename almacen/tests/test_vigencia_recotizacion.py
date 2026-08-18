"""
Tests de vigencia de cotización (5 días hábiles) y flujo de recotización.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Reglas de negocio que se verifican aquí:

1. Una cotización vale 5 DÍAS HÁBILES desde que Compras la libera a Front.
   Los fines de semana no consumen plazo.
2. Cuando ese plazo vence, NADIE puede aprobar piezas ni servicios (bloqueo
   duro): los costos del proveedor ya no son confiables. Rechazar sí se puede,
   porque cerrar un caso viejo no cuesta dinero.
3. Si el cliente reaparece y quiere continuar, se abre una RONDA nueva: se
   guarda una foto de los precios viejos, la solicitud vuelve a borrador y
   Compras cotiza otra vez.
4. Solo se puede recotizar si el cliente NO respondió nada. Si ya aprobó o
   rechazó algo, hay precios congelados (y quizá compras) que no se pueden
   reciclar.

Las notificaciones (Celery, push, correo) se mockean para no tocar el broker
ni el servidor de correo durante las pruebas.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from almacen.models import (
    LineaCotizacion,
    LineaServicioAdicional,
    RondaCotizacion,
    SolicitudCotizacion,
)
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.utils.vigencia_cotizacion import (
    contar_dias_habiles_restantes,
    esta_vencida,
    puede_recotizar,
    sumar_dias_habiles,
)
from almacen.views import (
    aprobar_todas_lineas,
    iniciar_recotizacion_solicitud,
    rechazar_todas_lineas,
)


class SumarDiasHabilesTest(TestCase):
    """
    Objetivo: el cálculo del plazo debe saltar sábados y domingos.

    Efectos secundarios: ninguno (funciones puras, sin base de datos).
    """

    def test_viernes_mas_cinco_habiles_cae_viernes_siguiente(self) -> None:
        """
        Viernes + 5 días hábiles = viernes de la semana siguiente.

        EXPLICACIÓN: del viernes 14 se cuentan lunes 17, martes 18, miércoles 19,
        jueves 20 y viernes 21. Sábado 15 y domingo 16 no consumen plazo.
        """
        # 2026-08-14 es viernes
        viernes = datetime(2026, 8, 14, 10, 0)
        resultado = sumar_dias_habiles(viernes, 5)

        self.assertEqual(resultado.date(), datetime(2026, 8, 21).date())
        # La hora original se conserva (el plazo vence a la misma hora)
        self.assertEqual(resultado.hour, 10)

    def test_miercoles_mas_cinco_habiles_cruza_fin_de_semana(self) -> None:
        """Miércoles + 5 hábiles = miércoles siguiente (se saltan sáb y dom)."""
        # 2026-08-12 es miércoles
        miercoles = datetime(2026, 8, 12, 9, 30)
        resultado = sumar_dias_habiles(miercoles, 5)

        self.assertEqual(resultado.date(), datetime(2026, 8, 19).date())

    def test_dias_restantes_es_cero_si_ya_vencio(self) -> None:
        """Una fecha límite en el pasado no deja días restantes."""
        vencimiento = timezone.now() - timedelta(days=3)
        self.assertEqual(contar_dias_habiles_restantes(vencimiento), 0)


class VigenciaCotizacionTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Objetivo de negocio: el reloj arranca al notificar a Front y bloquea
    aprobaciones cuando vence.

    Efectos secundarios: crea orden ST, solicitud y líneas reales en la BD.
    """

    def setUp(self) -> None:
        """Crea contexto base, orden ST y una solicitud en borrador con línea."""
        self._crear_contexto_base(sufijo='VIG')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-VIG-01')
        self.solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=self.orden,
            estado='borrador',
            creado_por=self.user,
            tipo_servicio_cliente='estandar',
        )
        self.linea = LineaCotizacion.objects.create(
            solicitud=self.solicitud,
            producto=self.producto,
            proveedor=self.proveedor,
            descripcion_pieza='RAM 16GB vigencia',
            cantidad=1,
            costo_unitario=Decimal('200.00'),
            precio_unitario_cliente=None,
            estado_cliente='pendiente',
        )

    def _vencer_vigencia(self) -> None:
        """
        Empuja la fecha de vencimiento al pasado para simular que el plazo acabó.

        Efectos secundarios:
            Escribe ``fecha_vencimiento_vigencia`` en la base de datos.
        """
        self.solicitud.fecha_vencimiento_vigencia = timezone.now() - timedelta(days=1)
        self.solicitud.save(update_fields=['fecha_vencimiento_vigencia'])
        self.solicitud.refresh_from_db()

    def test_enviar_a_front_arranca_la_vigencia(self) -> None:
        """Al liberar la cotización a Front se calcula la fecha límite."""
        self.assertIsNone(self.solicitud.fecha_vencimiento_vigencia)

        self.assertTrue(self.solicitud.enviar_a_front(usuario=self.user))
        self.solicitud.refresh_from_db()

        self.assertEqual(self.solicitud.estado, 'enviada_front')
        self.assertIsNotNone(self.solicitud.fecha_inicio_vigencia)
        self.assertIsNotNone(self.solicitud.fecha_vencimiento_vigencia)
        # El plazo debe quedar en el futuro y no pasar de 7 días naturales
        # (5 hábiles como máximo cruzan un solo fin de semana)
        delta = self.solicitud.fecha_vencimiento_vigencia - timezone.now()
        self.assertGreater(delta.days, 4)
        self.assertLessEqual(delta.days, 7)
        self.assertFalse(self.solicitud.esta_vencida)

    def test_no_hay_vigencia_en_borrador(self) -> None:
        """En borrador el reloj todavía no corre: no aplica vigencia."""
        self.assertFalse(esta_vencida(self.solicitud))
        self.assertIsNone(self.solicitud.dias_habiles_restantes)

    @patch('almacen.utils.notificar_respuesta_cotizacion.notificar_cotizacion_aceptada')
    def test_vencida_bloquea_aprobar_todas(self, _mock_notif) -> None:
        """POST «Aprobar todas» con vigencia vencida no aprueba nada."""
        self.solicitud.enviar_a_front(usuario=self.user)
        self.solicitud.enviar_a_cliente(usuario=self.user)
        self._vencer_vigencia()

        url = reverse(
            'almacen:aprobar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user, url, {})
        respuesta = aprobar_todas_lineas(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 302)
        self.linea.refresh_from_db()
        # Núcleo del bloqueo duro: la línea sigue pendiente
        self.assertEqual(self.linea.estado_cliente, 'pendiente')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')

    @patch('almacen.utils.notificar_respuesta_cotizacion.notificar_cotizacion_rechazada')
    def test_vencida_permite_rechazar(self, _mock_notif) -> None:
        """Rechazar sigue funcionando aunque la vigencia haya vencido."""
        self.solicitud.enviar_a_front(usuario=self.user)
        self.solicitud.enviar_a_cliente(usuario=self.user)
        self._vencer_vigencia()

        url = reverse(
            'almacen:rechazar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(
            self.factory,
            self.user,
            url,
            {'motivo': 'El cliente ya no responde'},
        )
        respuesta = rechazar_todas_lineas(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 302)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.estado_cliente, 'rechazada')


class RecotizacionTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Objetivo de negocio: abrir una ronda nueva guarda el histórico, limpia los
    precios viejos y devuelve la solicitud a Compras.

    Efectos secundarios: crea solicitud, líneas, servicios y rondas reales.
    """

    def setUp(self) -> None:
        """Crea una solicitud vencida, enviada al cliente y sin respuesta."""
        self._crear_contexto_base(sufijo='REC')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-REC-01')
        self.solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=self.orden,
            estado='enviada_cliente',
            creado_por=self.user,
            tipo_servicio_cliente='estandar',
        )
        self.linea_a = LineaCotizacion.objects.create(
            solicitud=self.solicitud,
            producto=self.producto,
            proveedor=self.proveedor,
            descripcion_pieza='RAM 8GB recotiza',
            cantidad=2,
            costo_unitario=Decimal('150.00'),
            # Precio ya congelado de la ronda 1: debe limpiarse al recotizar
            precio_unitario_cliente=Decimal('300.00'),
            subtotal_cliente_sin_iva=Decimal('600.00'),
            estado_cliente='pendiente',
        )
        self.servicio = LineaServicioAdicional.objects.create(
            solicitud=self.solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('500.00'),
            estado_cliente='pendiente',
        )
        # Simulamos que la vigencia ya venció
        self.solicitud.fecha_inicio_vigencia = timezone.now() - timedelta(days=10)
        self.solicitud.fecha_vencimiento_vigencia = timezone.now() - timedelta(days=2)
        self.solicitud.fecha_precios_cliente = timezone.now() - timedelta(days=9)
        self.solicitud.save()
        self.solicitud.refresh_from_db()

    @patch('almacen.utils.recotizacion._notificar_compras_recotizacion')
    def test_iniciar_ronda_guarda_snapshot_y_reabre_en_borrador(self, _mock_notif) -> None:
        """
        Caso feliz: se archiva la ronda 1 y la solicitud vuelve a borrador.

        Verifica el corazón del flujo: histórico guardado, contador arriba,
        estado reiniciado y precios congelados limpiados.
        """
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        ronda = iniciar_nueva_ronda(
            self.solicitud,
            usuario=self.user,
            observaciones='El cliente llamó y quiere continuar',
        )
        self.solicitud.refresh_from_db()

        # ---- El histórico quedó guardado ----
        self.assertEqual(ronda.numero_ronda, 1)
        self.assertEqual(ronda.motivo_cierre, 'recotizacion')
        self.assertEqual(len(ronda.snapshot_lineas), 1)
        self.assertEqual(len(ronda.snapshot_servicios), 1)
        # 2 piezas x $150 de costo de proveedor
        self.assertEqual(ronda.costo_total_snapshot, Decimal('300.00'))
        # 2 piezas x $300 de precio al cliente
        self.assertEqual(ronda.precio_cliente_total_snapshot, Decimal('600.00'))
        self.assertEqual(
            ronda.snapshot_lineas[0]['descripcion_pieza'],
            'RAM 8GB recotiza',
        )

        # ---- La solicitud arrancó una ronda nueva ----
        self.assertEqual(self.solicitud.ronda_cotizacion, 2)
        self.assertEqual(self.solicitud.estado, 'borrador')
        self.assertIsNone(self.solicitud.fecha_vencimiento_vigencia)
        self.assertIsNone(self.solicitud.fecha_precios_cliente)
        self.assertFalse(self.solicitud.aviso_vencimiento_enviado)

        # ---- Los precios viejos se limpiaron ----
        self.linea_a.refresh_from_db()
        self.assertIsNone(self.linea_a.precio_unitario_cliente)
        self.assertIsNone(self.linea_a.subtotal_cliente_sin_iva)
        # El costo de proveedor NO se borra: Compras lo actualiza si cambió
        self.assertEqual(self.linea_a.costo_unitario, Decimal('150.00'))

    @patch('almacen.utils.recotizacion._notificar_compras_recotizacion')
    def test_segunda_recotizacion_incrementa_a_ronda_tres(self, _mock_notif) -> None:
        """Se pueden encadenar rondas: 1 → 2 → 3, cada una con su snapshot."""
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        iniciar_nueva_ronda(self.solicitud, usuario=self.user)
        self.solicitud.refresh_from_db()

        # Volvemos a dejarla vencida y esperando respuesta para la ronda 2
        self.solicitud.estado = 'enviada_cliente'
        self.solicitud.fecha_inicio_vigencia = timezone.now() - timedelta(days=10)
        self.solicitud.fecha_vencimiento_vigencia = timezone.now() - timedelta(days=1)
        self.solicitud.save()

        iniciar_nueva_ronda(self.solicitud, usuario=self.user)
        self.solicitud.refresh_from_db()

        self.assertEqual(self.solicitud.ronda_cotizacion, 3)
        self.assertEqual(
            RondaCotizacion.objects.filter(solicitud=self.solicitud).count(),
            2,
        )

    def test_no_se_puede_recotizar_si_hubo_respuesta_parcial(self) -> None:
        """
        Borde de negocio: si el cliente ya respondió algo, no aplica recotizar.

        Motivo: esa respuesta congeló precios y pudo generar compras; reciclar
        la solicitud rompería el histórico y el sync con Servicio Técnico.
        """
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        # El cliente rechazó el servicio adicional antes de que venciera
        self.servicio.estado_cliente = 'rechazada'
        self.servicio.save(update_fields=['estado_cliente'])

        self.assertFalse(puede_recotizar(self.solicitud))

        with self.assertRaises(ValueError):
            iniciar_nueva_ronda(self.solicitud, usuario=self.user)

        # Nada cambió: sigue en la ronda 1 y en su estado original
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.ronda_cotizacion, 1)
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')
        self.assertEqual(RondaCotizacion.objects.count(), 0)

    def test_no_se_puede_recotizar_si_la_vigencia_sigue_viva(self) -> None:
        """Una cotización dentro de plazo no se recotiza: hay que esperar."""
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        self.solicitud.fecha_vencimiento_vigencia = timezone.now() + timedelta(days=3)
        self.solicitud.save(update_fields=['fecha_vencimiento_vigencia'])

        self.assertFalse(puede_recotizar(self.solicitud))
        with self.assertRaises(ValueError):
            iniciar_nueva_ronda(self.solicitud, usuario=self.user)

    @patch('almacen.utils.recotizacion._notificar_compras_recotizacion')
    def test_vista_recotizacion_redirige_al_detalle(self, _mock_notif) -> None:
        """La vista HTTP corre el flujo completo y regresa al detalle."""
        url = reverse(
            'almacen:iniciar_recotizacion_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(
            self.factory,
            self.user,
            url,
            {'observaciones': 'Cliente confirmó por teléfono'},
        )
        respuesta = iniciar_recotizacion_solicitud(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 302)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.ronda_cotizacion, 2)
        self.assertEqual(self.solicitud.estado, 'borrador')

        ronda = RondaCotizacion.objects.get(solicitud=self.solicitud)
        self.assertEqual(ronda.observaciones, 'Cliente confirmó por teléfono')
        self.assertEqual(ronda.creada_por, self.user)


class AvisoVigenciaVencidaTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Objetivo de negocio: la tarea diaria avisa una sola vez por ronda.

    Efectos secundarios: crea solicitudes y marca la bandera de aviso.
    """

    def setUp(self) -> None:
        """Crea dos solicitudes: una vencida y otra todavía dentro de plazo."""
        self._crear_contexto_base(sufijo='AVI')

        self.vencida = SolicitudCotizacion.objects.create(
            estado='enviada_cliente',
            creado_por=self.user,
            sin_orden_activa=True,
            service_tag='SN-AVI-VENCIDA',
            fecha_vencimiento_vigencia=timezone.now() - timedelta(days=1),
        )
        self.vigente = SolicitudCotizacion.objects.create(
            estado='enviada_cliente',
            creado_por=self.user,
            sin_orden_activa=True,
            service_tag='SN-AVI-VIGENTE',
            fecha_vencimiento_vigencia=timezone.now() + timedelta(days=3),
        )

    @patch('almacen.utils.notificar_vigencia_cotizacion.enviar_push_y_campanita')
    def test_solo_notifica_las_vencidas_y_no_repite(self, mock_envio) -> None:
        """
        La primera corrida avisa; la segunda ya no (la bandera lo impide).

        EXPLICACIÓN: sin la bandera ``aviso_vencimiento_enviado``, el equipo
        recibiría la misma notificación todos los días hasta cerrar el caso.
        """
        from almacen.utils.notificar_vigencia_cotizacion import (
            procesar_solicitudes_vencidas,
        )
        mock_envio.return_value = 1

        primera = procesar_solicitudes_vencidas()
        self.assertEqual(primera['revisadas'], 1)
        self.assertEqual(primera['notificadas'], 1)

        self.vencida.refresh_from_db()
        self.vigente.refresh_from_db()
        self.assertTrue(self.vencida.aviso_vencimiento_enviado)
        # La que sigue dentro de plazo no se toca
        self.assertFalse(self.vigente.aviso_vencimiento_enviado)

        # Segunda corrida del día siguiente: ya no hay nada que avisar
        segunda = procesar_solicitudes_vencidas()
        self.assertEqual(segunda['revisadas'], 0)

    @patch('almacen.utils.notificar_vigencia_cotizacion.enviar_push_y_campanita')
    def test_recotizar_reactiva_el_aviso(self, mock_envio) -> None:
        """
        Tras abrir una ronda nueva, la bandera se reinicia.

        Así, si el cliente vuelve a no contestar en la ronda 2, el equipo
        recibe el aviso otra vez.
        """
        from almacen.utils.notificar_vigencia_cotizacion import (
            procesar_solicitudes_vencidas,
        )
        mock_envio.return_value = 1

        procesar_solicitudes_vencidas()
        self.vencida.refresh_from_db()
        self.assertTrue(self.vencida.aviso_vencimiento_enviado)

        # Al arrancar la vigencia de la ronda nueva, el aviso vuelve a estar activo
        self.vencida.iniciar_vigencia_cotizacion()
        self.vencida.refresh_from_db()
        self.assertFalse(self.vencida.aviso_vencimiento_enviado)
