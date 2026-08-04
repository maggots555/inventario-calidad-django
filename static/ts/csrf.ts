/**
 * Helper CSRF único para todo el front staff de SIGMA.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * --------------------------------
 * Django protege los POST/PUT/DELETE con un token CSRF. En producción la cookie
 * se llama `sigma_csrftoken`; en desarrollo suele llamarse `csrftoken`.
 *
 * Este proyecto NO usa bundler ni `import` entre archivos TS: cada `.ts` se
 * compila a un `.js` suelto y se carga con `<script>`. Por eso el helper se
 * expone en `window.getCsrfToken` (igual que el scanner o sigmaLoader).
 *
 * Orden de carga: `csrf.js` debe ir en base.html ANTES de notificaciones.js
 * y de cualquier script de página que haga fetch con `X-CSRFToken`.
 *
 * Efectos secundarios:
 * - Asigna `window.getCsrfToken` al cargar el script.
 */

(function inicializarCsrfGlobal(): void {
    /**
     * Lee el token CSRF de la cookie (prod → dev) o del input del formulario.
     *
     * Returns:
     *     Token listo para el header `X-CSRFToken`, o cadena vacía si no hay.
     */
    function getCsrfToken(): string {
        // Paso 1: cookies — producción primero, luego desarrollo
        const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];
        for (const name of cookieNames) {
            const match = document.cookie.match(
                new RegExp(`(?:^|;\\s*)${name}=([^;]*)`),
            );
            if (match && match[1]) {
                // decodeURIComponent: Django puede dejar el valor URL-encoded
                try {
                    return decodeURIComponent(match[1]);
                } catch {
                    return match[1];
                }
            }
        }

        // Paso 2: fallback — input oculto que pone {% csrf_token %} en el HTML
        const input = document.querySelector<HTMLInputElement>(
            'input[name="csrfmiddlewaretoken"]',
        );
        if (input && input.value) {
            return input.value;
        }

        return '';
    }

    // Exponer en window para que el resto de scripts (sin import) lo usen
    window.getCsrfToken = getCsrfToken;
})();
