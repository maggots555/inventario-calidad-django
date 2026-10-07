"""
Pantalla para renovar el candado de docker/.env.

EXPLICACIÓN PARA PRINCIPIANTES:
Solo un superusuario entra aquí. La clave de esta pantalla NO es la
de iniciar sesión. Si la escribe bien, se actualiza un archivo de fecha
en el disco. Un cron del servidor (no esta vista) es el que borra
docker/.env cuando esa fecha tiene más de 60 días.

La primera vez la persona define la clave: eso ARMA el candado.
Hasta ese momento el cron no borra nada.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from inventario.renovacion_env import (
    DIAS_VIGENCIA,
    cambiar_clave,
    dias_restantes,
    guardar_clave_inicial,
    hay_clave,
    leer_sello,
    renovar,
)

# 5 intentos malos y la pantalla deja de comprobar la clave por 15 minutos.
# Así nadie prueba miles de contraseñas seguidas.
_MAX_FALLOS = 5
_VENTANA_FALLOS_SEG = 15 * 60


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/inventario/acceso-denegado/')
@require_http_methods(['GET', 'POST'])
def renovar_entorno_docker(request):
    """
    Muestra el plazo y recibe la clave de renovación.

    Args:
        request: Petición HTTP. El usuario ya viene autenticado y
            tiene que ser superusuario.

    Returns:
        GET: la plantilla con días restantes.
        POST: redirección a esta misma pantalla (evita reenviar el form).

    Efectos secundarios:
        Puede escribir clave.hash y ultima_ok en RENOVACION_ENV_DIR.
        Cuenta intentos fallidos en la caché. No borra docker/.env.
    """
    if request.method == 'POST':
        return _procesar_post(request)
    return _pintar(request)


def _procesar_post(request):
    """
    Reparte el formulario: armar, renovar o cambiar la clave.

    Efectos secundarios:
        Mensajes de éxito o error, y a veces un archivo nuevo en disco.
    """
    accion = request.POST.get('accion', '')
    # Paso 1: armar solo existe mientras no hay hash. No gasta intentos,
    # porque todavía no hay una clave que adivinar.
    if accion == 'armar':
        return _armar(request)
    if accion == 'renovar':
        return _renovar(request)
    if accion == 'cambiar':
        return _cambiar(request)
    messages.error(request, 'No reconocí la acción del formulario.')
    return redirect('renovar_entorno_docker')


def _armar(request):
    """Primera clave: la guarda y deja el sello en hoy."""
    clave = request.POST.get('clave', '')
    clave2 = request.POST.get('clave2', '')
    if clave != clave2:
        messages.error(request, 'Las dos claves no coinciden. Escríbela otra vez.')
        return redirect('renovar_entorno_docker')
    try:
        guardar_clave_inicial(clave)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('renovar_entorno_docker')
    messages.success(
        request,
        'Candado armado. Si pasan 60 días sin esta clave, el cron del '
        'servidor apaga SIGMA y borra docker/.env.',
    )
    return redirect('renovar_entorno_docker')


def _renovar(request):
    """Clave correcta: mueve la fecha. Clave mala: suma un intento."""
    if _esta_bloqueado(request.user.pk):
        messages.error(
            request,
            'Demasiados intentos fallidos. Espera 15 minutos y vuelve a intentar.',
        )
        return redirect('renovar_entorno_docker')
    clave = request.POST.get('clave', '')
    if not renovar(clave):
        # Cada fallo reinicia la ventana de 15 minutos.
        hechos = _registrar_fallo(request.user.pk)
        messages.error(
            request,
            f'Clave incorrecta. Intento {hechos} de {_MAX_FALLOS}.',
        )
        return redirect('renovar_entorno_docker')
    _limpiar_fallos(request.user.pk)
    messages.success(
        request,
        'Renovación registrada. El plazo de 60 días vuelve a empezar hoy.',
    )
    return redirect('renovar_entorno_docker')


def _cambiar(request):
    """Pide la clave vieja y, si coincide, guarda la nueva y renueva."""
    if _esta_bloqueado(request.user.pk):
        messages.error(
            request,
            'Demasiados intentos fallidos. Espera 15 minutos y vuelve a intentar.',
        )
        return redirect('renovar_entorno_docker')
    anterior = request.POST.get('anterior', '')
    nueva = request.POST.get('nueva', '')
    nueva2 = request.POST.get('nueva2', '')
    if nueva != nueva2:
        messages.error(request, 'La clave nueva no coincide en los dos campos.')
        return redirect('renovar_entorno_docker')
    try:
        cambio_ok = cambiar_clave(anterior, nueva)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('renovar_entorno_docker')
    if not cambio_ok:
        hechos = _registrar_fallo(request.user.pk)
        messages.error(
            request,
            f'La clave anterior no coincide. Intento {hechos} de {_MAX_FALLOS}.',
        )
        return redirect('renovar_entorno_docker')
    _limpiar_fallos(request.user.pk)
    messages.success(request, 'Clave de renovación cambiada. El plazo vuelve a empezar hoy.')
    return redirect('renovar_entorno_docker')


def _pintar(request):
    """Arma el contexto de la plantilla: armado o no, y días que faltan."""
    restantes = dias_restantes()
    return render(request, 'inventario/renovar_entorno.html', {
        'armado': hay_clave(),
        'ultima_renovacion': leer_sello(),
        'dias_restantes': restantes,
        'dias_vigencia': DIAS_VIGENCIA,
        'bloqueado': _esta_bloqueado(request.user.pk),
        # Menos de 14 días: la pantalla lo marca para que no se les pase.
        'urgente': restantes is not None and restantes < 14,
    })


def _clave_cache(user_id: int) -> str:
    """Identificador de los intentos de este usuario en la caché."""
    return f'renovacion_env_fallos_{user_id}'


def _esta_bloqueado(user_id: int) -> bool:
    """True cuando ya acumuló 5 fallos dentro de la ventana."""
    return cache.get(_clave_cache(user_id), 0) >= _MAX_FALLOS


def _registrar_fallo(user_id: int) -> int:
    """
    Suma un intento fallido.

    Returns:
        Cuántos fallos van en esta ventana.

    Efectos secundarios:
        Escribe un contador en la caché, con vida de 15 minutos.
    """
    clave = _clave_cache(user_id)
    hechos = cache.get(clave, 0) + 1
    cache.set(clave, hechos, _VENTANA_FALLOS_SEG)
    return hechos


def _limpiar_fallos(user_id: int) -> None:
    """Olvida el contador cuando la clave fue correcta."""
    cache.delete(_clave_cache(user_id))
