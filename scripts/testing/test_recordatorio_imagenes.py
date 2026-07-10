#!/usr/bin/env python
"""
Script manual para validar la lógica de recordatorios de imágenes faltantes.

Uso:
    python scripts/testing/test_recordatorio_imagenes.py
"""
import os
import sys
from datetime import timedelta
from unittest.mock import MagicMock, patch

# Configurar Django antes de importar modelos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.utils import timezone

from servicio_tecnico.models import Cotizacion
from servicio_tecnico.utils_recordatorio_imagenes import (
    DIAS_MAX_VENTANA_RECORDATORIO,
    HORAS_ANTES_RECORDATORIO,
    construir_mensaje_recordatorio_egreso_inspector,
    construir_mensaje_recordatorio_ingreso_inspector,
    construir_mensaje_recordatorio_tecnico,
    orden_requiere_recordatorio_egreso_inspector,
    orden_requiere_recordatorio_ingreso_inspector,
    orden_requiere_recordatorio_tecnico,
    tipos_faltantes_tecnico,
)


class _StubOrden:
    """
    Stub simple de OrdenServicio para pruebas de lógica (sin BD).

    EXPLICACIÓN PARA PRINCIPIANTES:
    MagicMock crea atributos automáticamente y rompe el caso "sin cotización"
    (devolvería otro mock en vez de DoesNotExist). Este stub controla eso.
    """

    def __init__(self, **kwargs):
        self.estado = kwargs.get('estado', 'recepcion')
        self.tipo_servicio = kwargs.get('tipo_servicio', 'diagnostico')
        self.fecha_ingreso = kwargs.get(
            'fecha_ingreso',
            timezone.now() - timedelta(hours=72),
        )
        self.numero_orden_interno = kwargs.get('numero_orden_interno', 'ORD-2026-0001')
        self.tecnico_asignado_actual = kwargs.get('tecnico_asignado_actual')
        self.fecha_finalizacion = kwargs.get(
            'fecha_finalizacion',
            timezone.now() - timedelta(hours=1) if kwargs.get('estado') == 'finalizado' else None,
        )
        self._tipos_imagen = set(kwargs.get('tipos_imagen', set()))
        self._cotizacion = kwargs.get('cotizacion', 'SIN_COTIZACION')
        self._fecha_creacion_historial = kwargs.get('fecha_creacion_historial')

        detalle = MagicMock()
        detalle.orden_cliente = kwargs.get('orden_cliente', 'OOW-12345')
        self.detalle_equipo = detalle

        # Historial: evento 'creacion' opcional
        historial_mock = MagicMock()
        historial_mock.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = (
            self._fecha_creacion_historial
        )
        self.historial = historial_mock

        # Imágenes: values_list('tipo') y filter(tipo=...)
        imagenes_mock = MagicMock()
        imagenes_mock.values_list.return_value.distinct.return_value = list(self._tipos_imagen)

        def _filter_imagenes(**filter_kwargs):
            tipo = filter_kwargs.get('tipo')
            mock_qs = MagicMock()
            if tipo in self._tipos_imagen:
                fecha = kwargs.get(f'fecha_{tipo}', timezone.now() - timedelta(hours=72))
                mock_qs.order_by.return_value.values_list.return_value.first.return_value = fecha
            else:
                mock_qs.order_by.return_value.values_list.return_value.first.return_value = None
            return mock_qs

        imagenes_mock.filter.side_effect = _filter_imagenes
        self.imagenes = imagenes_mock

    @property
    def cotizacion(self):
        """Simula OneToOne: sin cotización → DoesNotExist."""
        if self._cotizacion == 'SIN_COTIZACION' or self._cotizacion is None:
            raise Cotizacion.DoesNotExist
        return self._cotizacion


def _cotizacion(usuario_acepto):
    cot = MagicMock()
    cot.usuario_acepto = usuario_acepto
    return cot


def test_inspector_sin_ingreso_48h():
    orden = _StubOrden(tipos_imagen=set(), estado='recepcion')
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is True
    print('OK: inspector — sin ingreso tras 48h')


def test_inspector_con_ingreso():
    orden = _StubOrden(tipos_imagen={'ingreso'})
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is False
    print('OK: inspector — con ingreso no notifica')


def test_inspector_cancelada():
    orden = _StubOrden(tipos_imagen=set(), estado='cancelado')
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is False
    print('OK: inspector — orden cancelada excluida')


def test_inspector_egreso_finalizado_sin_fotos():
    orden = _StubOrden(estado='finalizado', tipos_imagen={'ingreso'})
    assert orden_requiere_recordatorio_egreso_inspector(orden) is True
    print('OK: inspector — finalizado sin egreso')


def test_inspector_egreso_con_fotos():
    orden = _StubOrden(estado='finalizado', tipos_imagen={'ingreso', 'egreso'})
    assert orden_requiere_recordatorio_egreso_inspector(orden) is False
    print('OK: inspector — finalizado con egreso no notifica')


def test_tecnico_aceptada_pide_diag_y_rep():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _StubOrden(
        estado='finalizado',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
        cotizacion=_cotizacion(True),
    )
    faltantes = tipos_faltantes_tecnico(orden)
    assert faltantes == ['diagnostico', 'reparacion']
    print('OK: técnico — cotización aceptada pide diag+rep')


def test_tecnico_rechazada_solo_diag():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _StubOrden(
        estado='finalizado',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
        cotizacion=_cotizacion(False),
    )
    faltantes = tipos_faltantes_tecnico(orden)
    assert faltantes == ['diagnostico']
    print('OK: técnico — cotización rechazada solo diagnóstico')


def test_tecnico_pendiente_solo_diag():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _StubOrden(
        estado='finalizado',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
        cotizacion=_cotizacion(None),
    )
    faltantes = tipos_faltantes_tecnico(orden)
    assert faltantes == ['diagnostico']
    print('OK: técnico — cotización pendiente solo diagnóstico')


def test_tecnico_vm_sin_cotizacion_solo_rep():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _StubOrden(
        estado='finalizado',
        tipo_servicio='venta_mostrador',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
        cotizacion=None,
    )
    faltantes = tipos_faltantes_tecnico(orden)
    assert faltantes == ['reparacion']
    print('OK: técnico VM sin cotización — solo reparación')


def test_tecnico_no_finalizado_no_pide():
    orden = _StubOrden(
        estado='reparacion',
        tipos_imagen={'ingreso'},
        cotizacion=_cotizacion(True),
    )
    faltantes = tipos_faltantes_tecnico(orden)
    assert faltantes == []
    print('OK: técnico — fuera de finalizado no pide fotos')


def test_ingreso_mas_de_una_semana_no_pide():
    orden = _StubOrden(
        tipos_imagen=set(),
        estado='recepcion',
        fecha_ingreso=timezone.now() - timedelta(days=10),
    )
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is False
    print('OK: inspector ingreso — más de 1 semana no notifica')


def test_egreso_mas_de_una_semana_no_pide():
    orden = _StubOrden(
        estado='finalizado',
        tipos_imagen={'ingreso'},
        fecha_finalizacion=timezone.now() - timedelta(days=10),
    )
    assert orden_requiere_recordatorio_egreso_inspector(orden) is False
    print('OK: inspector egreso — finalizado hace >1 semana no notifica')


def test_tecnico_mas_de_una_semana_no_pide():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _StubOrden(
        estado='finalizado',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
        cotizacion=_cotizacion(True),
        fecha_finalizacion=timezone.now() - timedelta(days=10),
    )
    assert orden_requiere_recordatorio_tecnico(orden) is False
    print('OK: técnico — finalizado hace >1 semana no notifica')


def test_mensajes():
    orden = _StubOrden(
        orden_cliente='OOW-999',
        estado='finalizado',
        cotizacion=_cotizacion(True),
    )
    t1, m1 = construir_mensaje_recordatorio_ingreso_inspector(orden)
    assert 'ingreso' in m1.lower()
    assert 'OOW-999' in t1

    t_egr, m_egr = construir_mensaje_recordatorio_egreso_inspector(orden)
    assert 'egreso' in m_egr.lower()

    with patch(
        'servicio_tecnico.utils_recordatorio_imagenes.tipos_faltantes_tecnico',
        return_value=['reparacion'],
    ):
        t2, m2 = construir_mensaje_recordatorio_tecnico(orden)
    assert 'reparación' in m2.lower() or 'reparacion' in m2.lower() or 'Reparación' in m2
    print('OK: mensajes construidos correctamente')


if __name__ == '__main__':
    print(
        f'Validando lógica (ingreso ≥{HORAS_ANTES_RECORDATORIO} h, '
        f'ventana máx {DIAS_MAX_VENTANA_RECORDATORIO} días)...'
    )
    test_inspector_sin_ingreso_48h()
    test_inspector_con_ingreso()
    test_inspector_cancelada()
    test_inspector_egreso_finalizado_sin_fotos()
    test_inspector_egreso_con_fotos()
    test_tecnico_aceptada_pide_diag_y_rep()
    test_tecnico_rechazada_solo_diag()
    test_tecnico_pendiente_solo_diag()
    test_tecnico_vm_sin_cotizacion_solo_rep()
    test_tecnico_no_finalizado_no_pide()
    test_ingreso_mas_de_una_semana_no_pide()
    test_egreso_mas_de_una_semana_no_pide()
    test_tecnico_mas_de_una_semana_no_pide()
    test_mensajes()
    print('\nTodas las pruebas de lógica pasaron.')
