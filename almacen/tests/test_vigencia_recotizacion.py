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

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, override_settings
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
    alerta_vigencia_panel,
    contar_dias_habiles_restantes,
    esta_vencida,
    puede_recotizar,
    sumar_dias_habiles,
)
from almacen.views import (
    api_enviar_cotizacion_cliente,
    aprobar_todas_lineas,
    detalle_solicitud_cotizacion,
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

    def test_cotizar_de_noche_no_regala_un_dia_habil(self) -> None:
        """
        El plazo se cuenta con el calendario local, no con el de UTC.

        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        El servidor guarda todo en UTC y México va 6 horas atrás. Un jueves a
        las 19:00 en México ya es viernes 01:00 en UTC. Si preguntáramos el día
        de la semana sobre la hora UTC, el sistema contaría desde el viernes y
        le regalaría al cliente un día hábil de más.

        Jueves 13/08/2026 + 5 hábiles = jueves 20/08/2026 (correcto).
        Si contara desde el viernes daría viernes 21/08 (un día de más).
        """
        # Jueves 13 de agosto de 2026, 19:00 en México = viernes 01:00 UTC
        jueves_noche_utc = datetime(
            2026, 8, 14, 1, 0, tzinfo=dt_timezone.utc,
        )

        resultado = sumar_dias_habiles(jueves_noche_utc, 5)

        # El vencimiento debe caer en jueves, no en viernes
        self.assertEqual(resultado.weekday(), 3, 'El plazo debe vencer en jueves')
        self.assertEqual(resultado.date(), date(2026, 8, 20))


class AlertaVigenciaPanelTest(TestCase):
    """
    Objetivo: el panel clasifica con la regla de 5 días hábiles, no con 3 calendario.

    Efectos secundarios: ninguno (SimpleNamespace, sin base de datos).
    """

    def _solicitud(self, *, vencimiento, estado='enviada_cliente'):
        """
        Arma un objeto mínimo con lo que ``alerta_vigencia_panel`` necesita.

        Args:
            vencimiento (datetime | None): Fecha límite de vigencia.
            estado (str): Estado de la solicitud.

        Returns:
            SimpleNamespace: Falso modelo con estado y fecha de vencimiento.
        """
        return SimpleNamespace(
            estado=estado,
            fecha_vencimiento_vigencia=vencimiento,
        )

    def test_ok_cuando_queda_margen(self) -> None:
        """Feliz: si faltan varios días hábiles, no hay alerta."""
        solicitud = self._solicitud(
            vencimiento=timezone.now() + timedelta(days=5),
        )
        self.assertEqual(alerta_vigencia_panel(solicitud), 'ok')

    def test_urgente_cuando_vence_en_horas(self) -> None:
        """Borde: vence hoy (aún no pasa la hora) → por vencer, no vencida."""
        solicitud = self._solicitud(
            vencimiento=timezone.now() + timedelta(hours=3),
        )
        self.assertEqual(alerta_vigencia_panel(solicitud), 'urgente')

    def test_vencida_cuando_el_plazo_ya_paso(self) -> None:
        """Borde: fecha límite en el pasado → vencida."""
        solicitud = self._solicitud(
            vencimiento=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(alerta_vigencia_panel(solicitud), 'vencida')

    def test_ok_en_borrador_sin_reloj(self) -> None:
        """En borrador el reloj no corre: no alertamos."""
        solicitud = self._solicitud(vencimiento=None, estado='borrador')
        self.assertEqual(alerta_vigencia_panel(solicitud), 'ok')


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

    def test_vencida_bloquea_enviar_cotizacion_al_cliente(self) -> None:
        """
        La API de envío al cliente rechaza el POST si la vigencia venció.

        EXPLICACIÓN: reenviar una cotización caducada le prometería al cliente
        un precio que el proveedor ya pudo haber cambiado. El bloqueo vive en
        el servidor porque ocultar el botón no basta: el POST se puede disparar
        a mano desde la consola del navegador.
        """
        import json

        self.solicitud.enviar_a_front(usuario=self.user)
        self.solicitud.enviar_a_cliente(usuario=self.user)
        self._vencer_vigencia()

        url = reverse(
            'almacen:api_enviar_cotizacion_cliente',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(
            self.factory,
            self.user,
            url,
            {
                'modo_cotizacion': 'reparacion',
                'tipo_servicio': 'estandar',
                'email_cliente': 'cliente.vencida@test.local',
                'modo_agrupacion': 'todo_junto',
            },
        )
        respuesta = api_enviar_cotizacion_cliente(request, self.solicitud.pk)

        datos = json.loads(respuesta.content)
        self.assertFalse(datos['success'])
        self.assertIn('recotización', datos['error'].lower())

    def _html_detalle(self) -> str:
        """
        Renderiza el detalle de la solicitud y devuelve el HTML como texto.

        Returns:
            str: HTML completo de la página de detalle.

        Efectos secundarios:
            Ninguno (solo lectura); usa RequestFactory igual que el resto
            de los tests de este módulo.
        """
        url = reverse(
            'almacen:detalle_solicitud_cotizacion',
            kwargs={'pk': self.solicitud.pk},
        )
        request = self.factory.get(url)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        respuesta = detalle_solicitud_cotizacion(request, self.solicitud.pk)
        return respuesta.content.decode('utf-8')

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        # EXPLICACIÓN: en producción los estáticos llevan hash (Manifest...),
        # pero en tests no corrimos collectstatic, así que usamos el storage
        # simple para poder renderizar el template completo.
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    })
    def test_detalle_oculta_boton_reenviar_cotizacion_si_vencio(self) -> None:
        """
        El botón «Reenviar Cotización» desaparece al vencer la vigencia.

        EXPLICACIÓN: buscamos el disparador del modal de envío al cliente.
        El modal en sí siempre está en el HTML; lo que debe desaparecer es
        cualquier botón que lo abra (panel de acciones y dock móvil).
        """
        disparador_modal = 'data-bs-target="#modalEnviarCotizacionCliente"'

        self.solicitud.enviar_a_front(usuario=self.user)
        self.solicitud.enviar_a_cliente(usuario=self.user)

        # Antes de vencer el botón sí debe estar disponible
        self.assertIn(disparador_modal, self._html_detalle())

        self._vencer_vigencia()

        self.assertNotIn(disparador_modal, self._html_detalle())

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

    @patch('almacen.utils.recotizacion._notificar_compras_recotizacion')
    def test_recotizar_regresa_la_orden_st_al_hito_de_proveedores(
        self,
        _mock_notif,
    ) -> None:
        """
        La orden de Servicio Técnico no se queda «Esperando Aprobación Cliente».

        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Al recotizar, el equipo vuelve a manos de Compras. Si la orden se
        quedara en «cotizacion», el técnico creería que se espera al cliente.
        Peor aún: las guardias anti-regresión del sync no permiten avanzar
        desde ese estado, así que el siguiente «Notificar a Front» se omitiría
        y la orden quedaría congelada. Aquí verificamos las dos cosas.
        """
        from almacen.utils.recotizacion import iniciar_nueva_ronda
        from almacen.utils.sincronizar_estado_st import (
            sincronizar_estado_st_al_notificar_front,
        )

        # Estado real tras enviar la cotización al cliente
        self.orden.estado = 'cotizacion'
        self.orden.save(update_fields=['estado'])

        iniciar_nueva_ronda(self.solicitud, usuario=self.user)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'cotizacion_enviada_proveedor')

        # El historial debe explicar por qué retrocedió
        ultimo = self.orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo='cotizacion_enviada_proveedor',
        ).order_by('-fecha_evento').first()
        self.assertIsNotNone(ultimo)
        self.assertIn('Recotización solicitada', ultimo.comentario)

        # Y el flujo de la ronda 2 debe volver a funcionar de punta a punta
        self.solicitud.refresh_from_db()
        self.solicitud.enviar_a_front(usuario=self.user)
        cambiado = sincronizar_estado_st_al_notificar_front(
            self.solicitud,
            usuario=self.user,
        )
        self.orden.refresh_from_db()
        self.assertTrue(cambiado)
        self.assertEqual(self.orden.estado, 'cotizacion_recibida_proveedor')

    @patch('almacen.utils.recotizacion._notificar_compras_recotizacion')
    def test_recotizar_no_pisa_una_orden_ya_en_reparacion(
        self,
        _mock_notif,
    ) -> None:
        """
        Guardia: si la orden avanzó a reparación, la recotización no la mueve.

        Retroceder una orden que ya está en el taller sería peor que dejarla
        desincronizada, así que el sync se omite a propósito.
        """
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        self.orden.estado = 'reparacion'
        self.orden.save(update_fields=['estado'])

        iniciar_nueva_ronda(self.solicitud, usuario=self.user)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'reparacion')

    def test_alias_de_base_sale_de_la_instancia(self) -> None:
        """
        La transacción debe abrirse en la base del país, no en 'default'.

        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cada país tiene su propia base (México vive en el alias ``mexico``).
        El router enruta las consultas solo, pero las transacciones NO pasan
        por el router: hay que decirle a Django explícitamente en qué base
        abrirla. Django deja anotado en cada objeto de dónde lo leyó
        (``_state.db``), y esa es la fuente que usamos.
        """
        from almacen.utils.recotizacion import resolver_db_alias

        # Simulamos una solicitud leída desde la base de México
        self.solicitud._state.db = 'mexico'
        self.assertEqual(resolver_db_alias(self.solicitud), 'mexico')

    def test_alias_de_base_cae_al_router_si_la_instancia_no_lo_sabe(self) -> None:
        """
        Si el objeto no viene de la base, le preguntamos al router.

        Caso raro (objeto recién construido en memoria), pero necesitamos un
        alias válido de todos modos para poder abrir la transacción.
        """
        from almacen.utils.recotizacion import resolver_db_alias

        self.solicitud._state.db = None
        alias = resolver_db_alias(self.solicitud)

        # No sabemos cuál será en cada entorno, pero nunca puede quedar vacío
        self.assertTrue(alias)

    def test_aviso_a_compras_se_encola_despues_del_commit(self) -> None:
        """
        La tarea Celery se encola al confirmar la transacción, no antes.

        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Si se encolara dentro de la transacción, el worker podría leer la
        solicitud antes de que la base confirme los cambios y mandaría el
        correo con los datos de la ronda vieja. ``captureOnCommitCallbacks``
        ejecuta los callbacks pendientes para poder comprobarlo en el test.
        """
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        with patch(
            'almacen.tasks.notificar_recotizacion_solicitada_task.delay'
        ) as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                iniciar_nueva_ronda(self.solicitud, usuario=self.user)
                # Dentro de la transacción todavía NO debe haberse encolado
                mock_delay.assert_not_called()

            # Ya confirmada la transacción, el aviso sí sale
            mock_delay.assert_called_once()

        self.solicitud.refresh_from_db()
        # El worker recibirá la solicitud con la ronda ya actualizada
        self.assertEqual(self.solicitud.ronda_cotizacion, 2)

    @patch('almacen.utils.recotizacion._notificar_compras_recotizacion')
    def test_segundo_intento_no_crea_una_ronda_duplicada(
        self,
        _mock_notif,
    ) -> None:
        """
        Doble clic en el botón: el segundo intento se rechaza con mensaje.

        Tras la primera recotización la solicitud queda en borrador, así que
        ya no cumple las condiciones y ``iniciar_nueva_ronda`` lanza ValueError
        en lugar de chocar contra la restricción de unicidad de la ronda.
        """
        from almacen.utils.recotizacion import iniciar_nueva_ronda

        iniciar_nueva_ronda(self.solicitud, usuario=self.user)

        with self.assertRaises(ValueError):
            iniciar_nueva_ronda(self.solicitud, usuario=self.user)

        self.assertEqual(
            RondaCotizacion.objects.filter(solicitud=self.solicitud).count(),
            1,
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
