/* =============================================================================
   LISTA ÓRDENES — Panel lateral de carga de técnicos
   ---------------------------------------------------------------------------
   Objetivo (negocio):
     Tras cambiar Hoy/Semana/Histórico el formulario hace GET y la página
     recarga: el Offcanvas se cierra. Guardamos una bandera en sessionStorage
     para reabrirlo automáticamente y no forzar al usuario a volver a abrirlo.

   Args / efectos:
     - Lee #panelCargaTecnicos y el form [data-lo-carga-filtro]
     - Usa Bootstrap.Offcanvas (global en window desde base.html)
     - No toca BD ni hace fetch

   EXPLICACIÓN PARA PRINCIPIANTES:
     sessionStorage vive solo en esta pestaña del navegador y se borra al
     cerrarla. Es ideal para “recordar un momento” entre dos cargas de página.
   ============================================================================= */

/** Clave en sessionStorage para saber si debemos reabrir el panel. */
const LO_CARGA_REOPEN_KEY = 'loCargaPanelReopen';

/**
 * Acceso tipado al objeto Bootstrap expuesto en window.
 *
 * Returns: API Offcanvas de Bootstrap o null si aún no cargó.
 */
function getBootstrapOffcanvasApi(): {
    getOrCreateInstance: (el: Element) => { show: () => void };
} | null {
    // EXPLICACIÓN: Bootstrap se carga como script global en base.html
    const bootstrapGlobal = (window as Window & {
        bootstrap?: {
            Offcanvas: {
                getOrCreateInstance: (el: Element) => { show: () => void };
            };
        };
    }).bootstrap;

    if (!bootstrapGlobal || !bootstrapGlobal.Offcanvas) {
        return null;
    }
    return bootstrapGlobal.Offcanvas;
}

/**
 * Marca que el panel debe reabrirse tras el próximo submit del filtro.
 *
 * Args:
 *   form: formulario GET del filtro temporal dentro del Offcanvas
 *
 * Efectos secundarios: escribe en sessionStorage.
 */
function engancharFiltroParaReabrir(form: HTMLFormElement): void {
    form.addEventListener('submit', () => {
        // Paso 1: recordar la intención antes de que la página se recargue
        try {
            sessionStorage.setItem(LO_CARGA_REOPEN_KEY, '1');
        } catch {
            // Privacidad estricta / modo privado: ignoramos sin romper el filtro
        }
    });

    // onchange del <select> llama form.submit() sin disparar el evento 'submit'
    // en todos los navegadores; escuchamos el change del select también.
    const select = form.querySelector('select[name="filtro_temporal"]');
    if (select) {
        select.addEventListener('change', () => {
            try {
                sessionStorage.setItem(LO_CARGA_REOPEN_KEY, '1');
            } catch {
                /* no-op */
            }
        });
    }
}

/**
 * Si la bandera está activa, abre el Offcanvas y limpia la bandera.
 *
 * Args:
 *   panelEl: nodo #panelCargaTecnicos
 */
function reabrirPanelSiCorresponde(panelEl: HTMLElement): void {
    let debeReabrir = false;
    try {
        debeReabrir = sessionStorage.getItem(LO_CARGA_REOPEN_KEY) === '1';
        if (debeReabrir) {
            sessionStorage.removeItem(LO_CARGA_REOPEN_KEY);
        }
    } catch {
        debeReabrir = false;
    }

    if (!debeReabrir) {
        return;
    }

    const Offcanvas = getBootstrapOffcanvasApi();
    if (!Offcanvas) {
        return;
    }

    // Paso 2: reabrir el panel con la API nativa de Bootstrap
    Offcanvas.getOrCreateInstance(panelEl).show();
}

/**
 * Enter/Espacio en headers de sucursal (role=button en un div).
 *
 * Args:
 *   panelEl: nodo del Offcanvas donde viven los toggles
 *
 * Efectos secundarios: dispara click en el header al pulsar tecla.
 */
function engancharTecladoSucursales(panelEl: HTMLElement): void {
    panelEl.addEventListener('keydown', (evento: KeyboardEvent) => {
        const target = evento.target as HTMLElement | null;
        if (!target || !target.classList.contains('lo-carga-sucursal-toggle')) {
            return;
        }
        if (evento.key === 'Enter' || evento.key === ' ') {
            evento.preventDefault();
            target.click();
        }
    });
}

/**
 * Punto de entrada: solo corre si existe el panel en la página (vista activas).
 */
function inicializarPanelCargaTecnicos(): void {
    const panelEl = document.getElementById('panelCargaTecnicos');
    if (!panelEl) {
        return;
    }

    const formFiltro = document.querySelector<HTMLFormElement>(
        'form[data-lo-carga-filtro="1"]'
    );
    if (formFiltro) {
        engancharFiltroParaReabrir(formFiltro);
    }

    engancharTecladoSucursales(panelEl);
    reabrirPanelSiCorresponde(panelEl);
}

document.addEventListener('DOMContentLoaded', () => {
    inicializarPanelCargaTecnicos();
});
