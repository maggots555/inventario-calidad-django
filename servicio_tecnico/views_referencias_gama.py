"""
Vistas CRUD de ReferenciaGamaEquipo (catálogo marca/modelo → gama).

EXPLICACIÓN PARA PRINCIPIANTES:
Estas pantallas viven aparte de detalle_orden. Clasifican equipos en gama
alta/media/baja; los formularios de nueva orden usan el MODELO
ReferenciaGamaEquipo.obtener_gama(), no estas vistas HTTP.

urls.py sigue usando views.lista_referencias_gama porque views.py reexporta.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .decorators import permission_required_with_message
from .forms import ReferenciaGamaEquipoForm
from .models import ReferenciaGamaEquipo


@login_required
@permission_required_with_message('servicio_tecnico.view_referenciagamaequipo')
def lista_referencias_gama(request):
    """
    Lista referencias de gama con búsqueda, filtros y paginación.

    Parámetros GET:
        busqueda, marca, gama, mostrar_inactivos, orden, page.

    Efectos secundarios:
        Solo lectura en BD (no modifica catálogo).
    """
    # Paso 1: queryset base
    referencias = ReferenciaGamaEquipo.objects.all()

    busqueda = request.GET.get('busqueda', '')
    filtro_marca = request.GET.get('marca', '')
    filtro_gama = request.GET.get('gama', '')
    mostrar_inactivos = request.GET.get('mostrar_inactivos', '') == 'on'

    # Paso 2: aplicar filtros de texto / marca / gama
    if busqueda:
        referencias = referencias.filter(
            Q(marca__icontains=busqueda) |
            Q(modelo_base__icontains=busqueda)
        )

    if filtro_marca:
        referencias = referencias.filter(marca__iexact=filtro_marca)

    if filtro_gama:
        referencias = referencias.filter(gama=filtro_gama)

    if not mostrar_inactivos:
        referencias = referencias.filter(activo=True)

    marcas_disponibles = (
        ReferenciaGamaEquipo.objects.values_list('marca', flat=True)
        .distinct()
        .order_by('marca')
    )

    # Paso 3: ordenamiento seguro (whitelist de campos)
    orden = request.GET.get('orden', 'marca')
    if orden in [
        'marca', '-marca', 'modelo_base', '-modelo_base',
        'gama', '-gama', 'rango_costo_min', '-rango_costo_min',
    ]:
        referencias = referencias.order_by(orden)

    # Paso 4: paginar 25 por página
    total_referencias = referencias.count()
    paginator = Paginator(referencias, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'referencias': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
        'filtro_marca': filtro_marca,
        'filtro_gama': filtro_gama,
        'mostrar_inactivos': mostrar_inactivos,
        'marcas_disponibles': marcas_disponibles,
        'total_referencias': total_referencias,
        'orden': orden,
        'gamas_choices': [
            ('alta', 'Alta'),
            ('media', 'Media'),
            ('baja', 'Baja'),
        ],
    }

    return render(request, 'servicio_tecnico/referencias_gama/lista.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.add_referenciagamaequipo')
def crear_referencia_gama(request):
    """
    Crea una nueva referencia de gama de equipo.

    Efectos secundarios:
        INSERT en ReferenciaGamaEquipo si el formulario es válido.
    """
    if request.method == 'POST':
        form = ReferenciaGamaEquipoForm(request.POST)

        if form.is_valid():
            try:
                referencia = form.save()
                messages.success(
                    request,
                    f'✅ Referencia creada: {referencia.marca} {referencia.modelo_base} - '
                    f'Gama {referencia.get_gama_display()}'
                )
                return redirect('servicio_tecnico:lista_referencias_gama')
            except Exception as e:
                messages.error(request, f'❌ Error al crear referencia: {str(e)}')
    else:
        form = ReferenciaGamaEquipoForm()

    context = {
        'form': form,
        'titulo': 'Crear Nueva Referencia de Gama',
        'accion': 'Crear',
    }

    return render(request, 'servicio_tecnico/referencias_gama/form.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.change_referenciagamaequipo')
def editar_referencia_gama(request, referencia_id):
    """
    Edita una referencia de gama existente.

    Args:
        referencia_id (int): PK de ReferenciaGamaEquipo.

    Efectos secundarios:
        UPDATE del registro si el POST es válido.
    """
    referencia = get_object_or_404(ReferenciaGamaEquipo, id=referencia_id)

    if request.method == 'POST':
        form = ReferenciaGamaEquipoForm(request.POST, instance=referencia)

        if form.is_valid():
            try:
                referencia = form.save()
                messages.success(
                    request,
                    f'✅ Referencia actualizada: {referencia.marca} {referencia.modelo_base}'
                )
                return redirect('servicio_tecnico:lista_referencias_gama')
            except Exception as e:
                messages.error(request, f'❌ Error al actualizar: {str(e)}')
    else:
        form = ReferenciaGamaEquipoForm(instance=referencia)

    context = {
        'form': form,
        'referencia': referencia,
        'titulo': f'Editar Referencia: {referencia.marca} {referencia.modelo_base}',
        'accion': 'Actualizar',
    }

    return render(request, 'servicio_tecnico/referencias_gama/form.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.delete_referenciagamaequipo')
def eliminar_referencia_gama(request, referencia_id):
    """
    Desactiva (soft delete) una referencia de gama.

    Nota: Es mejor desactivar que eliminar para mantener consistencia en el sistema.

    Efectos secundarios:
        En POST, pone activo=False (no borra la fila).
    """
    referencia = get_object_or_404(ReferenciaGamaEquipo, id=referencia_id)

    if request.method == 'POST':
        try:
            # Soft delete: solo marcar como inactivo
            referencia.activo = False
            referencia.save()

            messages.success(
                request,
                f'✅ Referencia desactivada: {referencia.marca} {referencia.modelo_base}. '
                f'Ya no se usará para clasificación automática.'
            )
        except Exception as e:
            messages.error(request, f'❌ Error al desactivar: {str(e)}')

        return redirect('servicio_tecnico:lista_referencias_gama')

    context = {
        'referencia': referencia,
    }

    return render(
        request,
        'servicio_tecnico/referencias_gama/confirmar_eliminar.html',
        context,
    )


@login_required
@permission_required_with_message('servicio_tecnico.change_referenciagamaequipo')
def reactivar_referencia_gama(request, referencia_id):
    """
    Reactiva una referencia previamente desactivada.

    Efectos secundarios:
        UPDATE activo=True y redirect a la lista.
    """
    referencia = get_object_or_404(ReferenciaGamaEquipo, id=referencia_id)

    try:
        referencia.activo = True
        referencia.save()

        messages.success(
            request,
            f'✅ Referencia reactivada: {referencia.marca} {referencia.modelo_base}'
        )
    except Exception as e:
        messages.error(request, f'❌ Error al reactivar: {str(e)}')

    return redirect('servicio_tecnico:lista_referencias_gama')
