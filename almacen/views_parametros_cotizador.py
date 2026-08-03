"""
Panel de parámetros del cotizador (Gerencia / Presidencia).

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Extraído de views.py (Fase 1 de modularización Almacén).
urls.py sigue usando views.panel_parametros_cotizador porque
views.py reexporta este nombre.

Acceso: superusuario, gerente_general o gerente_operacional
(vía puede_editar_parametros_cotizador).

Efectos secundarios:
- En POST válido guarda ConfiguracionProfitPerfil y ConfiguracionReacondicionado
- En GET siembra desde .env si la BD está vacía
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


# ============================================================================
# PANEL DE PARÁMETROS DEL COTIZADOR (Gerencia / Presidencia)
# ============================================================================


@login_required
def panel_parametros_cotizador(request):
    """
    Panel para ajustar márgenes de reparación y parámetros de reacondicionados.

    Objetivo de negocio:
        Que Presidencia / Gerencia cambie profit, costos fijos, diagnóstico
        y matriz REAC sin editar el .env ni reiniciar el servidor.

    Acceso:
        Superusuario, gerente_general o gerente_operacional.

    Args:
        request: HttpRequest autenticado.

    Efectos secundarios:
        En POST válido guarda ConfiguracionProfitPerfil y ConfiguracionReacondicionado.
        En GET siembra desde .env si la BD está vacía.
    """
    from .forms import ParametrosProfitPerfilForm, ParametrosReacondicionadoForm
    from .models import ConfiguracionProfitPerfil, ConfiguracionReacondicionado
    from .utils.parametros_cotizador import (
        PERFIL_ETIQUETAS,
        PERFILES_PROFIT,
        asegurar_parametros_iniciales,
        puede_editar_parametros_cotizador,
        guardar_profit_perfiles,
        guardar_reacondicionado,
    )

    # Control de acceso: solo gerencia y superusuario
    if not puede_editar_parametros_cotizador(request.user):
        messages.error(
            request,
            'No tienes permiso para editar los parámetros del cotizador. '
            'Solo superusuario, gerente general o gerente operacional.',
        )
        return redirect('almacen:panel_cotizaciones')

    # Primera visita: copiar valores actuales del .env a la BD
    asegurar_parametros_iniciales(usuario=request.user)

    if request.method == 'POST':
        # --- Validar un form por cada perfil de reparación ---
        forms_profit = {}
        todos_ok = True
        for perfil in PERFILES_PROFIT:
            form_p = ParametrosProfitPerfilForm(request.POST, prefix=perfil)
            forms_profit[perfil] = form_p
            if not form_p.is_valid():
                todos_ok = False

        # --- Validar formulario de reacondicionados ---
        reac_obj = ConfiguracionReacondicionado.objects.filter(pk=1).first()
        form_reac = ParametrosReacondicionadoForm(
            request.POST,
            instance=reac_obj,
            prefix='reac',
        )
        if not form_reac.is_valid():
            todos_ok = False

        if todos_ok:
            from django.db import transaction

            # Armar dict de perfiles y persistir reparación + REAC juntos
            datos_perfiles = {}
            for perfil, form_p in forms_profit.items():
                datos_perfiles[perfil] = {
                    'profit_target': form_p.cleaned_data['profit_target'],
                    'costos_fijos': form_p.cleaned_data['costos_fijos'],
                    'diagnostico': form_p.cleaned_data['diagnostico'],
                }
            # Una sola transacción: si falla REAC, no quedan perfiles a medias
            with transaction.atomic():
                guardar_profit_perfiles(datos_perfiles, usuario=request.user)
                guardar_reacondicionado(
                    form_reac.cleaned_data, usuario=request.user
                )
            messages.success(
                request,
                'Parámetros del cotizador guardados. '
                'Los cambios aplican a cotizaciones nuevas (las ya enviadas no se recalculan).',
            )
            return redirect('almacen:panel_parametros_cotizador')

        messages.error(
            request,
            'Hay errores en el formulario. Revisa los campos marcados en rojo.',
        )
    else:
        # GET: precargar valores desde BD (ya sembrados)
        forms_profit = {}
        for perfil in PERFILES_PROFIT:
            fila = ConfiguracionProfitPerfil.objects.filter(perfil=perfil).first()
            initial = {}
            if fila:
                initial = {
                    'profit_target': fila.profit_target,
                    'costos_fijos': fila.costos_fijos,
                    'diagnostico': fila.diagnostico,
                }
            forms_profit[perfil] = ParametrosProfitPerfilForm(
                initial=initial,
                prefix=perfil,
            )

        reac_obj = ConfiguracionReacondicionado.objects.filter(pk=1).first()
        form_reac = ParametrosReacondicionadoForm(
            instance=reac_obj,
            prefix='reac',
        )

    # Empaquetar perfiles con etiqueta para el template
    perfiles_ui = [
        {
            'clave': perfil,
            'etiqueta': PERFIL_ETIQUETAS.get(perfil, perfil),
            'form': forms_profit[perfil],
        }
        for perfil in PERFILES_PROFIT
    ]

    # Auditoría: última actualización conocida
    ultimo_profit = (
        ConfiguracionProfitPerfil.objects
        .order_by('-actualizado_en')
        .select_related('actualizado_por')
        .first()
    )
    ultimo_reac = ConfiguracionReacondicionado.objects.filter(pk=1).first()

    return render(
        request,
        'almacen/cotizaciones/panel_parametros_cotizador.html',
        {
            'perfiles_ui': perfiles_ui,
            'form_reac': form_reac,
            'ultimo_profit': ultimo_profit,
            'ultimo_reac': ultimo_reac,
        },
    )

