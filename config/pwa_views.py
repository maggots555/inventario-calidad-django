"""
Vistas PWA — Service Worker y página Offline

EXPLICACIÓN PARA PRINCIPIANTES:
Estas dos vistas resuelven un requisito técnico de los Service Workers:
el archivo service_worker.js DEBE servirse desde la raíz del dominio
(ej. https://tusitio.com/service_worker.js) para poder controlar
todas las páginas del sitio.

Si lo sirviéramos desde /static/js/service_worker.js, el SW solo
podría interceptar peticiones a rutas que empiecen con /static/js/,
que en la práctica no sirve para nada útil.

Solución: estas vistas leen el archivo compilado del sistema de archivos
de Django y lo devuelven con las cabeceras HTTP correctas.
"""

import os
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.staticfiles import finders


def service_worker_view(request) -> HttpResponse:
    """
    Sirve el Service Worker compilado desde la raíz del dominio.

    URL: /service_worker.js
    Cabeceras importantes:
      - Content-Type: application/javascript — el navegador lo ejecutará como SW.
      - Service-Worker-Allowed: / — permite que el SW controle todo el sitio,
        no solo la ruta /service_worker.js.
      - Cache-Control: no-store — el NAVEGADOR (no el SW) NUNCA debe cachear
        este archivo. Debe comprobar si hay una versión nueva en cada carga.
        Si el navegador cacheara el SW, nunca recibirías actualizaciones.

    Usa django.contrib.staticfiles.finders para ubicar el archivo compilado.
    Esto funciona tanto en DEBUG=True (busca en STATICFILES_DIRS) como en
    DEBUG=False con collectstatic (busca en STATIC_ROOT/staticfiles/).
    """
    # Buscar el archivo usando el sistema de archivos estáticos de Django
    sw_path: str | None = finders.find('js/service_worker.js')

    if sw_path and os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            content: str = f.read()

        response = HttpResponse(
            content,
            content_type='application/javascript; charset=utf-8'
        )
        # CRÍTICO: permite que el SW controle todo el sitio (scope = raíz)
        response['Service-Worker-Allowed'] = '/'
        # CRÍTICO: el SW nunca debe cachearse a sí mismo
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return response

    # Si el archivo no existe (aún no se compiló el TS), devolver un SW vacío
    # con comentario informativo para facilitar el diagnóstico
    return HttpResponse(
        '// [SIGMA] service_worker.js no encontrado. Ejecuta: npm run build',
        content_type='application/javascript; charset=utf-8',
        status=200  # 200 para no romper el registro del SW
    )


def offline_view(request) -> HttpResponse:
    """
    Página offline que muestra el Service Worker cuando el usuario no tiene
    conexión y trata de navegar a una página que no está en el caché.

    URL: /offline/
    Esta ruta está excluida de @login_required intencionalmente:
    si el usuario no tiene conexión, tampoco puede autenticarse.
    La página no expone información sensible del sistema.
    """
    return render(request, 'offline.html')
