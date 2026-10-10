"""
IP del visitante, ya filtrada por Nginx.

EXPLICACIÓN PARA PRINCIPIANTES:
El navegador puede mandar la cabecera X-Forwarded-For con la IP que
se le ocurra. Si Django se queda con la primera, un programa puede
parecer que viene de otra computadora y saltarse el límite de intentos.

Nginx (el portero) escribe la IP verdadera en X-Real-IP y reemplaza
X-Forwarded-For. Esta función solo lee esa cabecera. En la laptop,
sin Nginx, no existe y usamos la IP del socket (REMOTE_ADDR).
"""


def ip_cliente(request) -> str:
    """
    Devuelve la IP del visitante en la que sí podemos confiar.

    Objetivo de negocio:
        Los límites de login, el chat público y los registros de
        seguridad deben anotar a la persona real, no una IP inventada.

    Args:
        request: Petición HTTP de Django.

    Returns:
        str: IP (por ejemplo ``203.0.113.8``). Si no hay ninguna,
        ``127.0.0.1``.

    Efectos secundarios:
        Ninguno. No escribe en la base ni en logs.
    """
    # Paso 1: Nginx ya dejó una sola IP. No partimos listas ni
    # tomamos la primera que haya mandado el visitante.
    real = (request.META.get('HTTP_X_REAL_IP') or '').strip()
    if real:
        return real

    # Paso 2: runserver o una prueba sin proxy. La IP es la del socket.
    return request.META.get('REMOTE_ADDR') or '127.0.0.1'
