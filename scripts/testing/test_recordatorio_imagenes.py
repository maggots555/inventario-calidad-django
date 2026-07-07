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

from servicio_tecnico.utils_recordatorio_imagenes import (
    orden_requiere_recordatorio_ingreso_inspector,
    tipos_faltantes_tecnico,
    construir_mensaje_recordatorio_tecnico,
    construir_mensaje_recordatorio_ingreso_inspector,
    HORAS_ANTES_RECORDATORIO,
)


def _orden_mock(**kwargs):
    """Crea un mock de OrdenServicio con atributos mínimos."""
    orden = MagicMock()
    orden.estado = kwargs.get('estado', 'recepcion')
    orden.tipo_servicio = kwargs.get('tipo_servicio', 'diagnostico')
    orden.fecha_ingreso = kwargs.get('fecha_ingreso', timezone.now() - timedelta(hours=72))
    orden.numero_orden_interno = kwargs.get('numero_orden_interno', 'ORD-2026-0001')
    orden.tecnico_asignado_actual = kwargs.get('tecnico_asignado_actual')
    orden.detalle_equipo.orden_cliente = kwargs.get('orden_cliente', 'OOW-12345')

    tipos = kwargs.get('tipos_imagen', set())
    orden.imagenes.values_list.return_value.distinct.return_value = list(tipos)

    def _filter_imagenes(**filter_kwargs):
        tipo = filter_kwargs.get('tipo')
        mock_qs = MagicMock()
        if tipo in tipos:
            fecha = kwargs.get(f'fecha_{tipo}', timezone.now() - timedelta(hours=72))
            mock_qs.order_by.return_value.values_list.return_value.first.return_value = fecha
        else:
            mock_qs.order_by.return_value.values_list.return_value.first.return_value = None
        return mock_qs

    orden.imagenes.filter.side_effect = lambda **kw: _filter_imagenes(**kw)

    historial_mock = MagicMock()
    historial_mock.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = (
        kwargs.get('fecha_creacion_historial')
    )
    orden.historial = historial_mock
    return orden


def test_inspector_sin_ingreso_48h():
    orden = _orden_mock(tipos_imagen=set(), estado='recepcion')
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is True
    print('OK: inspector — sin ingreso tras 48h')


def test_inspector_con_ingreso():
    orden = _orden_mock(tipos_imagen={'ingreso'})
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is False
    print('OK: inspector — con ingreso no notifica')


def test_inspector_cancelada():
    orden = _orden_mock(tipos_imagen=set(), estado='cancelado')
    assert orden_requiere_recordatorio_ingreso_inspector(orden) is False
    print('OK: inspector — orden cancelada excluida')


def test_tecnico_vm_falta_reparacion():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _orden_mock(
        tipo_servicio='venta_mostrador',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
    )
    with patch(
        'servicio_tecnico.utils_recordatorio_imagenes.obtener_tipos_imagen',
        return_value={'ingreso', 'egreso'},
    ):
        faltantes = tipos_faltantes_tecnico(orden)
    assert faltantes == ['reparacion']
    print('OK: técnico VM — falta reparación tras egreso')


def test_tecnico_diagnostico_faltan_ambas():
    tecnico = MagicMock()
    tecnico.user_id = 1
    tecnico.user.is_active = True
    orden = _orden_mock(
        tipo_servicio='diagnostico',
        tipos_imagen={'ingreso', 'egreso'},
        tecnico_asignado_actual=tecnico,
    )
    with patch(
        'servicio_tecnico.utils_recordatorio_imagenes.obtener_tipos_imagen',
        return_value={'ingreso', 'egreso'},
    ):
        faltantes = tipos_faltantes_tecnico(orden)
    assert 'diagnostico' in faltantes
    assert 'reparacion' in faltantes
    print('OK: técnico diagnóstico — faltan diagnóstico y reparación')


def test_mensajes():
    orden = _orden_mock(orden_cliente='OOW-999')
    t1, m1 = construir_mensaje_recordatorio_ingreso_inspector(orden)
    assert 'ingreso' in m1.lower()
    assert 'OOW-999' in t1

    orden_vm = _orden_mock(tipo_servicio='venta_mostrador', orden_cliente='FL-100')
    with patch(
        'servicio_tecnico.utils_recordatorio_imagenes.tipos_faltantes_tecnico',
        return_value=['reparacion'],
    ):
        t2, m2 = construir_mensaje_recordatorio_tecnico(orden_vm)
    assert 'reparación' in m2.lower() or 'reparacion' in m2.lower()
    print('OK: mensajes construidos correctamente')


if __name__ == '__main__':
    print(f'Validando lógica (umbral: {HORAS_ANTES_RECORDATORIO} h)...')
    test_inspector_sin_ingreso_48h()
    test_inspector_con_ingreso()
    test_inspector_cancelada()
    test_tecnico_vm_falta_reparacion()
    test_tecnico_diagnostico_faltan_ambas()
    test_mensajes()
    print('\nTodas las pruebas de lógica pasaron.')
