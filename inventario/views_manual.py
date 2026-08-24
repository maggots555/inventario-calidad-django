"""
Vistas del manual de órdenes con diagnóstico (OOW).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este archivo NO hincha inventario/views.py. Cada capítulo del manual es una
página HTML fija (no un wiki editable). Todas las vistas exigen login: el
manual es interno, no público.

El índice lateral y el recuadro «Tu área» se arman aquí para no repetir
la tabla de contenidos en cada plantilla.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from inventario.models import Empleado


# ---------------------------------------------------------------------------
# Mapa rol SIGMA → capítulo del manual
# En el piso se dice «Front» y «Calidad»; en SIGMA los grupos se llaman
# Recepcionista e Inspector. El manual usa ambos nombres a propósito.
# ---------------------------------------------------------------------------
ROL_A_AREA_MANUAL = {
    'recepcionista': 'front',
    'inspector': 'calidad',
    'tecnico': 'tecnico',
    'compras': 'compras',
    'almacenista': 'compras',
}

# Tabla de contenidos. `slug` coincide con `manual_slug` de cada vista.
MANUAL_PAGINAS = [
    {
        'slug': 'indice',
        'titulo': 'Portada',
        'grupo': 'inicio',
        'url_name': 'manual:indice',
        'area': None,
    },
    {
        'slug': 'proceso',
        'titulo': 'Proceso paso a paso',
        'grupo': 'proceso',
        'url_name': 'manual:proceso',
        'area': None,
    },
    {
        'slug': 'acepta',
        'titulo': 'El cliente acepta',
        'grupo': 'caminos',
        'url_name': 'manual:acepta',
        'area': None,
    },
    {
        'slug': 'rechaza',
        'titulo': 'El cliente rechaza',
        'grupo': 'caminos',
        'url_name': 'manual:rechaza',
        'area': None,
    },
    {
        'slug': 'pnc',
        'titulo': 'PNC (sin piezas)',
        'grupo': 'caminos',
        'url_name': 'manual:pnc',
        'area': None,
    },
    {
        'slug': 'recotizacion',
        'titulo': 'Recotización',
        'grupo': 'caminos',
        'url_name': 'manual:recotizacion',
        'area': None,
    },
    {
        'slug': 'front',
        'titulo': 'Front / Recepción',
        'grupo': 'roles',
        'url_name': 'manual:rol_front',
        'area': 'front',
    },
    {
        'slug': 'tecnico',
        'titulo': 'Técnico',
        'grupo': 'roles',
        'url_name': 'manual:rol_tecnico',
        'area': 'tecnico',
    },
    {
        'slug': 'calidad',
        'titulo': 'Calidad / Ingeniería',
        'grupo': 'roles',
        'url_name': 'manual:rol_calidad',
        'area': 'calidad',
    },
    {
        'slug': 'compras',
        'titulo': 'Compras / Almacén',
        'grupo': 'roles',
        'url_name': 'manual:rol_compras',
        'area': 'compras',
    },
    {
        'slug': 'glosario',
        'titulo': 'Glosario',
        'grupo': 'referencia',
        'url_name': 'manual:glosario',
        'area': None,
    },
]

MANUAL_GRUPOS = [
    {'id': 'inicio', 'titulo': 'Inicio'},
    {'id': 'proceso', 'titulo': 'El proceso'},
    {'id': 'caminos', 'titulo': 'Caminos'},
    {'id': 'roles', 'titulo': 'Por área'},
    {'id': 'referencia', 'titulo': 'Referencia'},
]


def resolver_area_manual(user):
    """
    Objetivo: traducir el rol del empleado al capítulo «Tu área».

    Args:
        user: usuario de Django (puede no tener perfil Empleado).

    Returns:
        str | None: clave de área (`front`, `tecnico`, `calidad`, `compras`)
        o None si el rol no tiene capítulo propio (gerente, facturación, etc.).

    Efectos secundarios: ninguno (solo lectura).
    """
    # Paso 1: sin usuario autenticado no hay área que destacar.
    if not user or not user.is_authenticated:
        return None
    # Paso 2: el OneToOne `empleado` lanza error si el user no tiene ficha.
    try:
        rol = user.empleado.rol
    except (Empleado.DoesNotExist, AttributeError):
        return None
    # Paso 3: gerentes y otros roles ven el manual completo, sin «Tu área».
    return ROL_A_AREA_MANUAL.get(rol)


def _contexto_manual(request, slug):
    """
    Objetivo: contexto compartido (índice + área del usuario) para cada capítulo.

    Args:
        request: HttpRequest autenticado.
        slug: identificador de la página actual (ej. `proceso`).

    Returns:
        dict para renderizar la plantilla del manual.
    """
    return {
        'manual_slug': slug,
        'manual_paginas': MANUAL_PAGINAS,
        'manual_grupos': MANUAL_GRUPOS,
        'manual_area_usuario': resolver_area_manual(request.user),
    }


@login_required
def manual_indice(request):
    """
    Objetivo: portada del manual OOW (diagrama de flujo y mapa clicable).

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno (solo lectura).
    """
    return render(
        request,
        'inventario/manual/indice.html',
        _contexto_manual(request, 'indice'),
    )


@login_required
def manual_proceso(request):
    """
    Objetivo: caso feliz OOW de punta a punta, con nombres reales de SIGMA.

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/proceso.html',
        _contexto_manual(request, 'proceso'),
    )


@login_required
def manual_acepta(request):
    """
    Objetivo: camino 10.1 cuando el cliente acepta (total o parcial).

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/acepta.html',
        _contexto_manual(request, 'acepta'),
    )


@login_required
def manual_rechaza(request):
    """
    Objetivo: camino 10.2 cuando el cliente rechaza toda la cotización.

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/rechaza.html',
        _contexto_manual(request, 'rechaza'),
    )


@login_required
def manual_pnc(request):
    """
    Objetivo: camino 10.3 PNC (parte no disponible) en dos pasos.

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/pnc.html',
        _contexto_manual(request, 'pnc'),
    )


@login_required
def manual_recotizacion(request):
    """
    Objetivo: camino cuando la cotización vence a los 5 días hábiles sin respuesta.

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/recotizacion.html',
        _contexto_manual(request, 'recotizacion'),
    )


@login_required
def manual_rol_front(request):
    """
    Objetivo: checklist de Front (rol Recepcionista en SIGMA).

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/rol_front.html',
        _contexto_manual(request, 'front'),
    )


@login_required
def manual_rol_tecnico(request):
    """
    Objetivo: checklist del técnico (diagnóstico SIC y reparación).

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/rol_tecnico.html',
        _contexto_manual(request, 'tecnico'),
    )


@login_required
def manual_rol_calidad(request):
    """
    Objetivo: checklist de Calidad/Ingeniería (fotos de ingreso y egreso).

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/rol_calidad.html',
        _contexto_manual(request, 'calidad'),
    )


@login_required
def manual_rol_compras(request):
    """
    Objetivo: checklist de Compras/Almacén (solicitud, compras, recepción).

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/rol_compras.html',
        _contexto_manual(request, 'compras'),
    )


@login_required
def manual_glosario(request):
    """
    Objetivo: estados de la orden vs estados de la cotización y siglas.

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios: ninguno.
    """
    return render(
        request,
        'inventario/manual/glosario.html',
        _contexto_manual(request, 'glosario'),
    )


# Lista para tests de humo: (nombre de URL, vista, slug esperado en contexto).
VISTAS_MANUAL_HUMOS = (
    ('manual:indice', manual_indice, 'indice'),
    ('manual:proceso', manual_proceso, 'proceso'),
    ('manual:acepta', manual_acepta, 'acepta'),
    ('manual:rechaza', manual_rechaza, 'rechaza'),
    ('manual:pnc', manual_pnc, 'pnc'),
    ('manual:recotizacion', manual_recotizacion, 'recotizacion'),
    ('manual:rol_front', manual_rol_front, 'front'),
    ('manual:rol_tecnico', manual_rol_tecnico, 'tecnico'),
    ('manual:rol_calidad', manual_rol_calidad, 'calidad'),
    ('manual:rol_compras', manual_rol_compras, 'compras'),
    ('manual:glosario', manual_glosario, 'glosario'),
)
