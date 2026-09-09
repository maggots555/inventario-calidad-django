/* =============================================================================
   JAVASCRIPT BASE - Sistema de Inventario
   Descripción: Funciones JavaScript globales y utilidades del sistema
   ============================================================================= */

document.addEventListener('DOMContentLoaded', function() {
    // Toasts de sistema (messages de Django): X + auto-cierre.
    // EXPLICACIÓN: ya NO cerramos todos los .alert de la página;
    // eso apagaba avisos permanentes de formularios/dashboards.
    inicializarToastsSistema();

    // Inicializar tooltips de Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Inicializar popovers de Bootstrap
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Funciones globales para el sistema

/**
 * Función para confirmar eliminaciones
 * @param {string} mensaje - Mensaje personalizado de confirmación
 * @returns {boolean} - true si el usuario confirma
 */
function confirmarEliminacion(mensaje: string = '¿Estás seguro de que quieres eliminar este elemento?'): boolean {
    return confirm(mensaje);
}

/* =============================================================================
   TOASTS DE SISTEMA
   Objetivo: mismo look para messages de Django (HTML en base.html) y para
   avisos que lanza JS con mostrarNotificacion().
   ============================================================================= */

/** Tipos visuales que entiende toasts.css */
type TipoToastSistema = 'success' | 'error' | 'warning' | 'info';

/** Cuánto tarda en cerrarse solo, según la gravedad */
const DURACION_TOAST_MS: Record<TipoToastSistema, number> = {
    success: 5000,
    info: 5000,
    warning: 7000,
    error: 8000,
};

/**
 * Normaliza un string suelto al tipo del toast.
 *
 * @param tipo - Valor crudo (p. ej. "danger", "debug", "success")
 * @returns Uno de success | error | warning | info
 */
function normalizarTipoToast(tipo: string): TipoToastSistema {
    if (tipo === 'success' || tipo === 'error' || tipo === 'warning' || tipo === 'info') {
        return tipo;
    }
    // Bootstrap usa "danger"; Django a veces manda "debug"
    if (tipo === 'danger') {
        return 'error';
    }
    return 'info';
}

/**
 * Título corto que se muestra arriba del texto.
 *
 * @param tipo - Tipo ya normalizado
 * @returns Título en español
 */
function tituloDeTipoToast(tipo: TipoToastSistema): string {
    if (tipo === 'success') {
        return 'Éxito';
    }
    if (tipo === 'error') {
        return 'Error';
    }
    if (tipo === 'warning') {
        return 'Aviso';
    }
    return 'Información';
}

/**
 * Clase de Bootstrap Icons para el círculo de la izquierda.
 *
 * @param tipo - Tipo ya normalizado
 * @returns Nombre de clase bi-*
 */
function iconoDeTipoToast(tipo: TipoToastSistema): string {
    if (tipo === 'success') {
        return 'bi-check-lg';
    }
    if (tipo === 'error') {
        return 'bi-x-lg';
    }
    if (tipo === 'warning') {
        return 'bi-exclamation-lg';
    }
    return 'bi-info-lg';
}

/**
 * Escapa HTML para no inyectar scripts si el mensaje viene de un input.
 *
 * @param texto - Texto plano
 * @returns Texto seguro para innerHTML
 */
function escaparHtmlToast(texto: string): string {
    const div = document.createElement('div');
    div.textContent = texto;
    return div.innerHTML;
}

/**
 * Devuelve (o crea) el contenedor fijo #sigma-toast-stack.
 *
 * @returns El elemento de la pila
 */
function obtenerStackToasts(): HTMLElement {
    let stack = document.getElementById('sigma-toast-stack');
    if (!stack) {
        stack = document.createElement('div');
        stack.id = 'sigma-toast-stack';
        stack.className = 'sigma-toast-stack';
        stack.setAttribute('aria-live', 'polite');
        document.body.appendChild(stack);
    }
    return stack;
}

/**
 * Cierra un toast con la animación de salida y luego lo quita del DOM.
 *
 * @param toast - Tarjeta .sigma-toast
 */
function cerrarToastSistema(toast: HTMLElement): void {
    if (toast.classList.contains('sigma-toast--saliendo')) {
        return;
    }
    toast.classList.add('sigma-toast--saliendo');
    // 260 ms = duración de sigmaToastSalir; un poco más de colchón
    window.setTimeout(function () {
        toast.remove();
    }, 280);
}

/**
 * Programa el auto-cierre según el tipo (errores duran más).
 *
 * @param toast - Tarjeta .sigma-toast
 * @param tipo - Tipo ya normalizado
 */
function programarCierreToast(toast: HTMLElement, tipo: TipoToastSistema): void {
    const delay = DURACION_TOAST_MS[tipo];
    // No tocamos --toast-duracion aquí: ya la pone el CSS por tipo
    // (.sigma-toast--success = 5s, etc.). Si la cambiamos al cargar,
    // la barra se reinicia y se desincroniza.
    window.setTimeout(function () {
        if (document.body.contains(toast)) {
            cerrarToastSistema(toast);
        }
    }, delay);
}

/**
 * Enlaza el botón X de un toast.
 *
 * @param toast - Tarjeta .sigma-toast
 */
function enlazarCierreToast(toast: HTMLElement): void {
    const btn = toast.querySelector('.sigma-toast__close');
    if (!btn) {
        return;
    }
    btn.addEventListener('click', function () {
        cerrarToastSistema(toast);
    });
}

/**
 * Activa X + auto-cierre en los toasts que Django ya pintó en el HTML.
 */
function inicializarToastsSistema(): void {
    const stack = document.getElementById('sigma-toast-stack');
    if (!stack) {
        return;
    }
    const toasts = stack.querySelectorAll<HTMLElement>('.sigma-toast');
    toasts.forEach(function (toast) {
        const tipo = normalizarTipoToast(toast.dataset.toastTipo || 'info');
        enlazarCierreToast(toast);
        programarCierreToast(toast, tipo);
    });
}

/**
 * Muestra un toast desde JavaScript (mismo look que los de Django).
 *
 * @param mensaje - Texto a mostrar (se escapa; no uses HTML)
 * @param tipo - success | error | warning | info (también acepta "danger")
 */
function mostrarNotificacion(mensaje: string, tipo: string = 'info'): void {
    const tipoNormalizado = normalizarTipoToast(tipo);
    const stack = obtenerStackToasts();

    const toast = document.createElement('div');
    toast.className = 'sigma-toast sigma-toast--' + tipoNormalizado;
    toast.setAttribute('role', 'alert');
    toast.setAttribute(
        'aria-live',
        tipoNormalizado === 'error' ? 'assertive' : 'polite',
    );
    toast.dataset.toastTipo = tipoNormalizado;

    // Paso 1: escapar el texto (el usuario/API puede mandar <script>)
    const textoSeguro = escaparHtmlToast(mensaje);
    const titulo = tituloDeTipoToast(tipoNormalizado);
    const icono = iconoDeTipoToast(tipoNormalizado);

    // Paso 2: mismo markup que pinta Django en base.html
    toast.innerHTML =
        '<div class="sigma-toast__icon" aria-hidden="true"><i class="bi ' + icono + '"></i></div>' +
        '<div class="sigma-toast__body">' +
            '<p class="sigma-toast__title">' + titulo + '</p>' +
            '<p class="sigma-toast__text">' + textoSeguro + '</p>' +
        '</div>' +
        '<button type="button" class="sigma-toast__close" aria-label="Cerrar notificación">' +
            '<i class="bi bi-x"></i>' +
        '</button>' +
        '<div class="sigma-toast__timer" aria-hidden="true"><span class="sigma-toast__timer-bar"></span></div>';

    stack.appendChild(toast);
    enlazarCierreToast(toast);
    programarCierreToast(toast, tipoNormalizado);
}

// Expone la función para otros .ts (window.mostrarNotificacion)
window.mostrarNotificacion = mostrarNotificacion;

/**
 * Función para formatear números con separadores de miles
 * @param {number} numero - Número a formatear
 * @returns {string} - Número formateado
 */
function formatearNumero(numero: number): string {
    return numero.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Función para validar formularios antes de envío
 * @param {HTMLFormElement} formulario - Formulario a validar
 * @returns {boolean} - true si es válido
 */
function validarFormulario(formulario: HTMLFormElement): boolean {
    let esValido = true;
    const camposRequeridos = formulario.querySelectorAll('[required]');
    
    camposRequeridos.forEach(function(campo: Element) {
        const inputElement = campo as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
        if (!inputElement.value.trim()) {
            inputElement.classList.add('is-invalid');
            esValido = false;
        } else {
            inputElement.classList.remove('is-invalid');
            inputElement.classList.add('is-valid');
        }
    });
    
    return esValido;
}

/**
 * Función para limpiar validaciones de formulario
 * @param {HTMLFormElement} formulario - Formulario a limpiar
 */
function limpiarValidaciones(formulario: HTMLFormElement): void {
    const campos = formulario.querySelectorAll('.form-control, .form-select');
    campos.forEach(function(campo: Element) {
        campo.classList.remove('is-valid', 'is-invalid');
    });
}

// Event listeners globales
document.addEventListener('DOMContentLoaded', function() {
    // Agregar confirmación a botones de eliminar
    const botonesEliminar = document.querySelectorAll('.btn-eliminar, [data-action="delete"]');
    botonesEliminar.forEach(function(boton: Element) {
        boton.addEventListener('click', function(this: HTMLElement, e: Event) {
            const mensaje = this.getAttribute('data-confirm-message') || 
                           '¿Estás seguro de que quieres eliminar este elemento?';
            if (!confirmarEliminacion(mensaje)) {
                e.preventDefault();
            }
        });
    });
    
    // Agregar validación en tiempo real a formularios
    const formularios = document.querySelectorAll('form');
    formularios.forEach(function(form) {
        const campos = form.querySelectorAll('.form-control, .form-select');
        campos.forEach(function(campo: Element) {
            campo.addEventListener('blur', function(this: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement) {
                if (this.hasAttribute('required')) {
                    if (!this.value.trim()) {
                        this.classList.add('is-invalid');
                        this.classList.remove('is-valid');
                    } else {
                        this.classList.remove('is-invalid');
                        this.classList.add('is-valid');
                    }
                }
            });
        });
    });
    
    // Inicializar botón Scroll to Top
    inicializarScrollToTop();
});

/* =============================================================================
   SCROLL TO TOP - Funcionalidad del botón para volver arriba
   ============================================================================= */

/**
 * Inicializa el botón de Scroll to Top
 * Muestra/oculta el botón según la posición del scroll
 * y maneja el click para scroll suave hacia arriba
 */
function inicializarScrollToTop() {
    const scrollButton = document.getElementById('scrollToTop');
    
    if (!scrollButton) {
        return; // Si el botón no existe, salir
    }
    
    // Distancia en píxeles para mostrar el botón
    const scrollThreshold = 300;
    
    /**
     * Función para mostrar/ocultar el botón según el scroll
     */
    function toggleScrollButton() {
        if (scrollButton) {
            if (window.pageYOffset > scrollThreshold) {
                scrollButton.classList.add('visible');
            } else {
                scrollButton.classList.remove('visible');
            }
        }
    }
    
    /**
     * Función para hacer scroll suave hacia arriba
     */
    function scrollToTop() {
        // Usar smooth scroll nativo del navegador
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
        
        // Alternativa con animación manual para navegadores antiguos
        // (comentado, pero disponible si se necesita)
        /*
        const scrollStep = -window.scrollY / (500 / 15);
        const scrollInterval = setInterval(function() {
            if (window.scrollY !== 0) {
                window.scrollBy(0, scrollStep);
            } else {
                clearInterval(scrollInterval);
            }
        }, 15);
        */
    }
    
    // Event listener para el scroll (con throttle para mejor performance)
    let scrollTimeout: number | undefined;
    window.addEventListener('scroll', function() {
        if (scrollTimeout) {
            window.cancelAnimationFrame(scrollTimeout);
        }
        
        scrollTimeout = window.requestAnimationFrame(function() {
            toggleScrollButton();
        });
    });
    
    // Event listener para el click del botón
    scrollButton.addEventListener('click', function(e) {
        e.preventDefault();
        scrollToTop();
    });
    
    // Verificar posición inicial al cargar la página
    toggleScrollButton();
}

/* =============================================================================
   NAVBAR MODERNO - Funcionalidad de dropdowns y menú móvil
   ============================================================================= */

/**
 * Inicializa la funcionalidad del navbar moderno
 */
function inicializarNavbarModerno() {
    const mobileToggle = document.getElementById('navbarToggle');
    const navbarMenu = document.getElementById('navbarMenu');

    // Referencias para devolver el menú a su lugar en el DOM al cerrar
    let menuPadreOriginal: HTMLElement | null = null;
    let menuAnclaOriginal: Comment | null = null;
    let bloqueadorTouchFondo: ((e: TouchEvent) => void) | null = null;
    let scrollPosAlAbrirMenu = 0;

    const esVistaMovil = (): boolean => window.innerWidth <= 992;

    /**
     * Mueve el panel del menú al <body> para escapar del overflow:hidden del navbar.
     * Sin esto, el panel queda recortado dentro del navbar (~70px) y no scrollea.
     */
    function portalMenuAlBody(): void {
        if (!navbarMenu || navbarMenu.classList.contains('navbar-menu--portal')) return;

        menuPadreOriginal = navbarMenu.parentElement;
        if (!menuPadreOriginal) return;

        menuAnclaOriginal = document.createComment('navbar-menu-ancla');
        menuPadreOriginal.insertBefore(menuAnclaOriginal, navbarMenu);
        document.body.appendChild(navbarMenu);
        navbarMenu.classList.add('navbar-menu--portal');
    }

    /** Devuelve el menú a su posición original dentro del navbar */
    function restaurarMenuEnNavbar(): void {
        if (!navbarMenu || !menuPadreOriginal || !menuAnclaOriginal) return;

        menuPadreOriginal.insertBefore(navbarMenu, menuAnclaOriginal);
        menuAnclaOriginal.remove();
        navbarMenu.classList.remove('navbar-menu--portal');
        menuPadreOriginal = null;
        menuAnclaOriginal = null;
    }

    /** Impide que el scroll táctil mueva la página de fondo (solo el panel del menú scrollea) */
    function activarBloqueoScrollFondo(): void {
        bloqueadorTouchFondo = (e: TouchEvent): void => {
            const target = e.target as Node | null;
            if (navbarMenu && target && navbarMenu.contains(target)) return;
            e.preventDefault();
        };
        document.addEventListener('touchmove', bloqueadorTouchFondo, { passive: false });
    }

    function desactivarBloqueoScrollFondo(): void {
        if (bloqueadorTouchFondo) {
            document.removeEventListener('touchmove', bloqueadorTouchFondo);
            bloqueadorTouchFondo = null;
        }
    }

    /**
     * Abre o cierra el menú móvil.
     * Efectos: portal DOM, bloqueo scroll fondo, clase en html/body.
     */
    function setMenuMovilAbierto(abierto: boolean): void {
        if (!navbarMenu || !mobileToggle) return;

        if (abierto && esVistaMovil()) {
            scrollPosAlAbrirMenu = window.scrollY;
            portalMenuAlBody();
            mobileToggle.classList.add('active');
            navbarMenu.classList.add('active');
            document.documentElement.classList.add('navbar-menu-open');
            document.body.classList.add('navbar-menu-open');
            activarBloqueoScrollFondo();
        } else {
            mobileToggle.classList.remove('active');
            navbarMenu.classList.remove('active');
            document.documentElement.classList.remove('navbar-menu-open');
            document.body.classList.remove('navbar-menu-open');
            desactivarBloqueoScrollFondo();
            restaurarMenuEnNavbar();
            window.scrollTo(0, scrollPosAlAbrirMenu);
        }
    }

    if (mobileToggle && navbarMenu) {
        mobileToggle.addEventListener('click', function() {
            const vaAbrir = !navbarMenu.classList.contains('active');
            setMenuMovilAbierto(vaAbrir);
        });
    }

    /**
     * Cierra todos los submenús del navbar (clase .active).
     * EXPLICACIÓN PARA PRINCIPIANTES: en tablet el menú se abre con .active
     * (el hover no es fiable al tocar). Hay que quitar esa clase al elegir
     * un enlace o al volver a pulsar el botón del módulo.
     */
    function cerrarTodosLosDropdownsNavbar(): void {
        document.querySelectorAll('.navbar-menu-item').forEach(function(item) {
            item.classList.remove('active');
        });
    }

    /** Tablet landscape / menú por iconos: necesita .active (sin hover fiable) */
    const esVistaTabletIconos = (): boolean => {
        const w = window.innerWidth;
        return w > 992 && w <= 1200;
    };

    const dropdownLinks = document.querySelectorAll('.navbar-menu-link[data-dropdown]');

    dropdownLinks.forEach(function(link: Element) {
        link.addEventListener('click', function(this: HTMLElement, e: Event) {
            e.preventDefault();

            const parentItem = this.closest('.navbar-menu-item');
            if (!parentItem) return;

            // Móvil y tablet: abrir/cerrar al tocar el botón del módulo
            if (esVistaMovil() || esVistaTabletIconos()) {
                const yaEstabaAbierto = parentItem.classList.contains('active');
                cerrarTodosLosDropdownsNavbar();
                // Si no estaba abierto, abrirlo (toggle). Si sí, queda cerrado.
                if (!yaEstabaAbierto) {
                    parentItem.classList.add('active');
                }
            }
        });
    });

    document.addEventListener('click', function(e: Event) {
        const target = e.target as HTMLElement;
        if (target && !target.closest('.navbar-menu-item') && !target.closest('#navbarToggle')) {
            cerrarTodosLosDropdownsNavbar();
        }
    });

    // Enlaces reales del menú (no el botón del módulo): al pulsar, cerrar todo
    const navbarLinks = navbarMenu ? navbarMenu.querySelectorAll('a:not([data-dropdown])') : [];
    navbarLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            cerrarTodosLosDropdownsNavbar();
            if (esVistaMovil()) {
                setMenuMovilAbierto(false);
            }
        });
    });

    window.addEventListener('resize', function() {
        if (!esVistaMovil()) {
            setMenuMovilAbierto(false);
            cerrarTodosLosDropdownsNavbar();
        }
    });
}

// Llamar inicialización del navbar al cargar el DOM
document.addEventListener('DOMContentLoaded', function() {
    inicializarNavbarModerno();
});

/* =============================================================================
   Layout: la sidebar lateral fue retirada (navegación solo en navbar superior).
   ============================================================================= */

/* =============================================================================
   Cursor personalizado: lógica movida a static/ts/cursor_personalizado.ts
   (preferencias localStorage + variantes). Se carga desde base.html.
   ============================================================================= */

// ============================================================
// PRE-NAV LOADER
// Muestra un overlay INMEDIATAMENTE al dar clic en un
// dashboard pesado, antes de que el servidor responda.
// ============================================================
(function iniciarPreNavLoader(): void {
    const overlay = document.getElementById('nav-pre-loader');
    if (!overlay) return;

    // useCapture=true: se ejecuta en fase de captura, antes
    // que cualquier handler hijo pueda llamar stopPropagation
    document.addEventListener('click', (e: MouseEvent) => {
        const link = (e.target as HTMLElement)
            .closest<HTMLAnchorElement>('a[data-nav-loader]');
        if (!link) return;

        // Ctrl/Cmd/Shift/Alt + clic → abrir en nueva pestaña, no interceptar
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

        overlay.classList.add('active');
    }, true);

    // Restablecer si el usuario vuelve con el botón "Atrás"
    // (bfcache restaura el DOM con la clase .active todavía presente)
    window.addEventListener('pageshow', (e: PageTransitionEvent) => {
        if (e.persisted) overlay.classList.remove('active');
    });
}());