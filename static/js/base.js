"use strict";
/* =============================================================================
   JAVASCRIPT BASE - Sistema de Inventario
   Descripción: Funciones JavaScript globales y utilidades del sistema
   ============================================================================= */
// Auto-hide de mensajes después de 5 segundos
document.addEventListener('DOMContentLoaded', function () {
    // Configurar auto-hide de alertas
    setTimeout(function () {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function (alert) {
            if (alert.classList.contains('show')) {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        });
    }, 5000);
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
function confirmarEliminacion(mensaje = '¿Estás seguro de que quieres eliminar este elemento?') {
    return confirm(mensaje);
}
/**
 * Función para mostrar notificaciones toast
 * @param {string} mensaje - Mensaje a mostrar
 * @param {string} tipo - Tipo de notificación (success, error, warning, info)
 */
function mostrarNotificacion(mensaje, tipo = 'info') {
    // Crear elemento toast
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${tipo === 'error' ? 'danger' : tipo}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${mensaje}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    // Agregar al contenedor de toasts (si existe)
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    toastContainer.innerHTML = toastHtml;
    const toastElement = toastContainer.querySelector('.toast');
    if (toastElement) {
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
    }
}
/**
 * Función para formatear números con separadores de miles
 * @param {number} numero - Número a formatear
 * @returns {string} - Número formateado
 */
function formatearNumero(numero) {
    return numero.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
/**
 * Función para validar formularios antes de envío
 * @param {HTMLFormElement} formulario - Formulario a validar
 * @returns {boolean} - true si es válido
 */
function validarFormulario(formulario) {
    let esValido = true;
    const camposRequeridos = formulario.querySelectorAll('[required]');
    camposRequeridos.forEach(function (campo) {
        const inputElement = campo;
        if (!inputElement.value.trim()) {
            inputElement.classList.add('is-invalid');
            esValido = false;
        }
        else {
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
function limpiarValidaciones(formulario) {
    const campos = formulario.querySelectorAll('.form-control, .form-select');
    campos.forEach(function (campo) {
        campo.classList.remove('is-valid', 'is-invalid');
    });
}
// Event listeners globales
document.addEventListener('DOMContentLoaded', function () {
    // Agregar confirmación a botones de eliminar
    const botonesEliminar = document.querySelectorAll('.btn-eliminar, [data-action="delete"]');
    botonesEliminar.forEach(function (boton) {
        boton.addEventListener('click', function (e) {
            const mensaje = this.getAttribute('data-confirm-message') ||
                '¿Estás seguro de que quieres eliminar este elemento?';
            if (!confirmarEliminacion(mensaje)) {
                e.preventDefault();
            }
        });
    });
    // Agregar validación en tiempo real a formularios
    const formularios = document.querySelectorAll('form');
    formularios.forEach(function (form) {
        const campos = form.querySelectorAll('.form-control, .form-select');
        campos.forEach(function (campo) {
            campo.addEventListener('blur', function () {
                if (this.hasAttribute('required')) {
                    if (!this.value.trim()) {
                        this.classList.add('is-invalid');
                        this.classList.remove('is-valid');
                    }
                    else {
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
            }
            else {
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
    let scrollTimeout;
    window.addEventListener('scroll', function () {
        if (scrollTimeout) {
            window.cancelAnimationFrame(scrollTimeout);
        }
        scrollTimeout = window.requestAnimationFrame(function () {
            toggleScrollButton();
        });
    });
    // Event listener para el click del botón
    scrollButton.addEventListener('click', function (e) {
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
    let menuPadreOriginal = null;
    let menuAnclaOriginal = null;
    let bloqueadorTouchFondo = null;
    let scrollPosAlAbrirMenu = 0;
    const esVistaMovil = () => window.innerWidth <= 992;
    /**
     * Mueve el panel del menú al <body> para escapar del overflow:hidden del navbar.
     * Sin esto, el panel queda recortado dentro del navbar (~70px) y no scrollea.
     */
    function portalMenuAlBody() {
        if (!navbarMenu || navbarMenu.classList.contains('navbar-menu--portal'))
            return;
        menuPadreOriginal = navbarMenu.parentElement;
        if (!menuPadreOriginal)
            return;
        menuAnclaOriginal = document.createComment('navbar-menu-ancla');
        menuPadreOriginal.insertBefore(menuAnclaOriginal, navbarMenu);
        document.body.appendChild(navbarMenu);
        navbarMenu.classList.add('navbar-menu--portal');
    }
    /** Devuelve el menú a su posición original dentro del navbar */
    function restaurarMenuEnNavbar() {
        if (!navbarMenu || !menuPadreOriginal || !menuAnclaOriginal)
            return;
        menuPadreOriginal.insertBefore(navbarMenu, menuAnclaOriginal);
        menuAnclaOriginal.remove();
        navbarMenu.classList.remove('navbar-menu--portal');
        menuPadreOriginal = null;
        menuAnclaOriginal = null;
    }
    /** Impide que el scroll táctil mueva la página de fondo (solo el panel del menú scrollea) */
    function activarBloqueoScrollFondo() {
        bloqueadorTouchFondo = (e) => {
            const target = e.target;
            if (navbarMenu && target && navbarMenu.contains(target))
                return;
            e.preventDefault();
        };
        document.addEventListener('touchmove', bloqueadorTouchFondo, { passive: false });
    }
    function desactivarBloqueoScrollFondo() {
        if (bloqueadorTouchFondo) {
            document.removeEventListener('touchmove', bloqueadorTouchFondo);
            bloqueadorTouchFondo = null;
        }
    }
    /**
     * Abre o cierra el menú móvil.
     * Efectos: portal DOM, bloqueo scroll fondo, clase en html/body.
     */
    function setMenuMovilAbierto(abierto) {
        if (!navbarMenu || !mobileToggle)
            return;
        if (abierto && esVistaMovil()) {
            scrollPosAlAbrirMenu = window.scrollY;
            portalMenuAlBody();
            mobileToggle.classList.add('active');
            navbarMenu.classList.add('active');
            document.documentElement.classList.add('navbar-menu-open');
            document.body.classList.add('navbar-menu-open');
            activarBloqueoScrollFondo();
        }
        else {
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
        mobileToggle.addEventListener('click', function () {
            const vaAbrir = !navbarMenu.classList.contains('active');
            setMenuMovilAbierto(vaAbrir);
        });
    }
    const dropdownLinks = document.querySelectorAll('.navbar-menu-link[data-dropdown]');
    dropdownLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            if (esVistaMovil()) {
                const parentItem = this.closest('.navbar-menu-item');
                if (parentItem) {
                    parentItem.classList.toggle('active');
                }
            }
        });
    });
    document.addEventListener('click', function (e) {
        const target = e.target;
        if (target && !target.closest('.navbar-menu-item') && !target.closest('#navbarToggle')) {
            document.querySelectorAll('.navbar-menu-item').forEach(function (item) {
                item.classList.remove('active');
            });
        }
    });
    const navbarLinks = navbarMenu ? navbarMenu.querySelectorAll('a:not([data-dropdown])') : [];
    navbarLinks.forEach(function (link) {
        link.addEventListener('click', function () {
            if (esVistaMovil()) {
                setMenuMovilAbierto(false);
            }
        });
    });
    window.addEventListener('resize', function () {
        if (!esVistaMovil()) {
            setMenuMovilAbierto(false);
            document.querySelectorAll('.navbar-menu-item').forEach(function (item) {
                item.classList.remove('active');
            });
        }
    });
}
// Llamar inicialización del navbar al cargar el DOM
document.addEventListener('DOMContentLoaded', function () {
    inicializarNavbarModerno();
});
/* =============================================================================
   SIDEBAR PROFESIONAL - Funcionalidad de la barra lateral colapsable
   ============================================================================= */
/**
 * Inicializa la funcionalidad de la sidebar
 */
function inicializarSidebar() {
    const sidebar = document.getElementById('appSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const mainWrapper = document.getElementById('mainWrapper');
    if (!sidebar)
        return; // Si no hay sidebar, salir
    // Toggle de colapsar/expandir sidebar en desktop
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            if (mainWrapper) {
                mainWrapper.classList.toggle('sidebar-collapsed');
            }
            // Guardar estado en localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', String(isCollapsed));
            // Cerrar todos los submenús abiertos al cambiar de modo
            const openSubmenus = sidebar.querySelectorAll('.sidebar-item.has-submenu.open');
            openSubmenus.forEach(function (submenu) {
                submenu.classList.remove('open');
                // Limpiar estilos inline de posición
                const submenuList = submenu.querySelector('.sidebar-submenu');
                if (submenuList) {
                    submenuList.style.top = '';
                }
            });
        });
    }
    // Sincronizar mainWrapper con el estado inicial de la sidebar
    // (la sidebar ya tiene la clase 'collapsed' del script inline si corresponde)
    if (sidebar.classList.contains('collapsed') && mainWrapper) {
        mainWrapper.classList.add('sidebar-collapsed');
    }
    // NOTA: El botón flotante mobileSidebarToggle ha sido eliminado
    // Ahora solo se usa la navbar superior para navegación móvil
    // Cerrar sidebar en móvil al hacer click en overlay
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function () {
            sidebar.classList.remove('mobile-open');
            sidebarOverlay.classList.remove('active');
        });
    }
    // Funcionalidad de submenús - SIMPLE Y ROBUSTO
    const submenus = document.querySelectorAll('.sidebar-item.has-submenu');
    submenus.forEach(function (submenu) {
        const link = submenu.querySelector('.sidebar-link');
        const submenuList = submenu.querySelector('.sidebar-submenu');
        if (!link || !submenuList)
            return;
        // Click en el link del menú principal (para abrir/cerrar)
        link.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation(); // CRÍTICO: Evitar que el evento burbujee al document
            const isCurrentlyOpen = submenu.classList.contains('open');
            // Cerrar todos los demás submenús (acordeón)
            submenus.forEach(function (otherSubmenu) {
                if (otherSubmenu !== submenu) {
                    otherSubmenu.classList.remove('open');
                    const otherList = otherSubmenu.querySelector('.sidebar-submenu');
                    if (otherList) {
                        otherList.style.top = '';
                    }
                }
            });
            // Toggle del actual
            if (isCurrentlyOpen) {
                submenu.classList.remove('open');
                // Limpiar style top inline
                submenuList.style.top = '';
            }
            else {
                submenu.classList.add('open');
                // Calcular posición top dinámica en modo colapsado
                const isCollapsed = sidebar.classList.contains('collapsed');
                if (isCollapsed) {
                    // Esperar a que el tooltip se renderice completamente
                    setTimeout(function () {
                        // Obtener posición del item clickeado
                        const itemRect = submenu.getBoundingClientRect();
                        // Obtener altura real del tooltip
                        const tooltipHeight = submenuList.offsetHeight;
                        // Centrar verticalmente el tooltip respecto al item
                        const centeredTop = itemRect.top + (itemRect.height / 2) - (tooltipHeight / 2);
                        // Asegurar que no se salga por arriba (navbar = 70px + margen)
                        const minTop = 80;
                        // No salirse por abajo
                        const maxTop = window.innerHeight - tooltipHeight - 20;
                        // Aplicar posición limitada
                        const finalTop = Math.max(minTop, Math.min(centeredTop, maxTop));
                        submenuList.style.top = finalTop + 'px';
                    }, 50); // Esperar 50ms para que se renderice
                }
            }
        });
        // NUEVO: Event listener en el submenu para cerrar al hacer click en opciones
        submenuList.addEventListener('click', function (e) {
            // Si el click es en un link de navegación (no en el contenedor)
            const target = e.target;
            const clickedLink = target ? target.closest('a') : null;
            if (clickedLink && clickedLink.href && clickedLink.href !== '#') {
                console.log('🔗 Click detectado en link:', clickedLink.href);
                console.log('🚪 Cerrando submenu...');
                // Cerrar el submenu inmediatamente
                submenu.classList.remove('open');
                submenuList.style.top = '';
                // Cerrar sidebar móvil si está abierta
                if (window.innerWidth <= 992) {
                    sidebar.classList.remove('mobile-open');
                    if (sidebarOverlay) {
                        sidebarOverlay.classList.remove('active');
                    }
                }
                // No prevenir default - dejar que navegue normalmente
            }
        });
        // ADICIONAL: Capturar clicks específicamente en los links <a>
        const allLinks = submenuList.querySelectorAll('a[href]:not([href="#"])');
        allLinks.forEach(function (navLink) {
            navLink.addEventListener('click', function (e) {
                console.log('🎯 Click directo en link detectado');
                // Cerrar submenu inmediatamente
                submenu.classList.remove('open');
                submenuList.style.top = '';
                // Cerrar sidebar móvil
                if (window.innerWidth <= 992) {
                    sidebar.classList.remove('mobile-open');
                    if (sidebarOverlay) {
                        sidebarOverlay.classList.remove('active');
                    }
                }
            }, true); // useCapture = true para capturar ANTES que otros handlers
        });
    });
    // Cerrar tooltips al hacer click FUERA de la sidebar (solo modo colapsado)
    document.addEventListener('click', function (e) {
        const isCollapsed = sidebar.classList.contains('collapsed');
        if (!isCollapsed)
            return;
        const target = e.target;
        // Si el click NO fue en la sidebar ni en sus elementos
        if (target && !sidebar.contains(target)) {
            const openSubmenus = sidebar.querySelectorAll('.sidebar-item.has-submenu.open');
            openSubmenus.forEach(function (submenu) {
                submenu.classList.remove('open');
            });
        }
    });
    // Ajustar sidebar en cambio de tamaño de ventana
    let resizeTimer;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            if (window.innerWidth > 992) {
                // Desktop: remover clases móviles
                sidebar.classList.remove('mobile-open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('active');
                }
            }
            // No cerrar submenús automáticamente - dejar que el usuario los controle
        }, 250);
    });
    // Marcar enlace activo basado en URL actual
    marcarEnlaceActivo();
    // CRÍTICO: Cerrar todos los tooltips antes de que la página se descargue
    window.addEventListener('beforeunload', function () {
        const openSubmenus = sidebar.querySelectorAll('.sidebar-item.has-submenu.open');
        openSubmenus.forEach(function (submenu) {
            submenu.classList.remove('open');
            const submenuList = submenu.querySelector('.sidebar-submenu');
            if (submenuList) {
                submenuList.style.top = '';
            }
        });
    });
    // ADICIONAL: Detectar cambios de página con pagehide (más confiable que beforeunload)
    window.addEventListener('pagehide', function () {
        const openSubmenus = sidebar.querySelectorAll('.sidebar-item.has-submenu.open');
        openSubmenus.forEach(function (submenu) {
            submenu.classList.remove('open');
        });
    });
}
/**
 * Marca el enlace activo en la sidebar según la URL actual
 */
function marcarEnlaceActivo() {
    const currentPath = window.location.pathname;
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    const sidebar = document.getElementById('appSidebar');
    sidebarLinks.forEach(function (link) {
        const href = link.getAttribute('href');
        // Remover clase active de todos los enlaces
        link.classList.remove('active');
        // Marcar como activo si coincide la URL
        if (href && currentPath.startsWith(href) && href !== '#') {
            link.classList.add('active');
            // Si está dentro de un submenú, abrir el submenú padre
            // SOLO si la sidebar está EXPANDIDA (no colapsada)
            const parentSubmenu = link.closest('.sidebar-item.has-submenu');
            if (parentSubmenu && sidebar && !sidebar.classList.contains('collapsed')) {
                parentSubmenu.classList.add('open');
            }
        }
    });
}
/**
 * Actualiza los badges de notificación en la sidebar
 * @param {string} menuId - ID del menú a actualizar
 * @param {number} count - Número de notificaciones
 */
function actualizarBadgeSidebar(menuId, count) {
    const menu = document.getElementById(menuId);
    if (!menu)
        return;
    let badge = menu.querySelector('.sidebar-badge');
    if (count > 0) {
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'sidebar-badge';
            const link = menu.querySelector('.sidebar-link');
            if (link) {
                link.appendChild(badge);
            }
        }
        badge.textContent = count > 99 ? '99+' : String(count);
    }
    else if (badge) {
        badge.remove();
    }
}
// Inicializar sidebar al cargar el DOM
document.addEventListener('DOMContentLoaded', function () {
    inicializarSidebar();
    // Remover clase de loading para habilitar transiciones
    setTimeout(function () {
        document.body.classList.remove('sidebar-loading');
    }, 100);
    // Inicializar cursor personalizado
    inicializarCursorPersonalizado();
});
/**
 * Crea una partícula de estela en la posición dada
 * @param {number} x - Posición X
 * @param {number} y - Posición Y
 */
function crearParticulaTrail(x, y) {
    const particle = document.createElement('div');
    particle.className = 'cursor-trail';
    particle.style.left = x + 'px';
    particle.style.top = y + 'px';
    // Añadir al body
    document.body.appendChild(particle);
    // Animar y eliminar
    // Usamos setTimeout para permitir que el navegador renderice el estado inicial
    setTimeout(() => {
        particle.style.transform = 'translate(-50%, -50%) scale(0)';
        particle.style.opacity = '0';
    }, 10);
    // Eliminar del DOM después de la transición
    setTimeout(() => {
        particle.remove();
    }, 510); // Un poco más que la transición CSS (0.5s)
}
/**
 * Oculta el SVG del cursor personalizado y deja el cursor del sistema.
 * Se usa cuando el dispositivo es táctil/híbrido o falla la inicialización.
 *
 * Efectos secundarios:
 * - Quita html.custom-cursor-active (el CSS deja de forzar cursor: none)
 * - Oculta #tech-cursor para que no quede un SVG flotante
 */
function desactivarCursorPersonalizado(motivo) {
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Sin esta clase, base.css NO oculta el cursor del sistema.
    // Así las laptops con pantalla táctil ven el puntero normal (fallback).
    document.documentElement.classList.remove('custom-cursor-active');
    const cursor = document.getElementById('tech-cursor');
    if (cursor) {
        cursor.style.display = 'none';
    }
    console.log(`Cursor personalizado deshabilitado (${motivo}) — fallback al cursor del sistema`);
}
/**
 * Inicializa el comportamiento del cursor personalizado.
 * Solo se activa en desktop con mouse real (sin touch).
 *
 * Si no se puede activar (laptop táctil, tablet, error), cae en fallback:
 * el cursor normal del sistema permanece visible porque NO se agrega
 * la clase html.custom-cursor-active que el CSS usa para cursor: none.
 */
function inicializarCursorPersonalizado() {
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Muchas laptops Windows tienen pantalla táctil. El navegador reporta
    // maxTouchPoints > 0 aunque también tengan mouse. Antes el JS salía
    // sin activar el cursor custom, pero el CSS igual ocultaba el del sistema
    // → la persona no veía ningún cursor. Ahora solo ocultamos el del sistema
    // cuando este método confirma que el custom está activo.
    // Detectar si es un dispositivo táctil o híbrido (touch + mouse)
    const isTouchDevice = (('ontouchstart' in window) ||
        (navigator.maxTouchPoints > 0) ||
        (window.matchMedia('(hover: none)').matches) ||
        (window.matchMedia('(pointer: coarse)').matches) ||
        (window.innerWidth <= 1024) // Tablets y móviles
    );
    // Si es táctil/híbrido: no custom → cursor del sistema (fallback)
    if (isTouchDevice) {
        desactivarCursorPersonalizado('dispositivo táctil o híbrido');
        return;
    }
    const cursor = document.getElementById('tech-cursor');
    if (!cursor) {
        // Sin el elemento DOM no hay cursor custom; no ocultar el del sistema
        desactivarCursorPersonalizado('elemento #tech-cursor no encontrado');
        return;
    }
    // Confirmar al CSS que el custom está vivo → ahora sí cursor: none
    document.documentElement.classList.add('custom-cursor-active');
    cursor.style.display = '';
    // Variable para controlar la creación de partículas (throttling)
    let lastTrailTime = 0;
    const trailInterval = 30; // Crear partícula cada 30ms
    // Mover el cursor
    document.addEventListener('mousemove', function (e) {
        // Usar requestAnimationFrame para rendimiento óptimo
        requestAnimationFrame(() => {
            cursor.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
            // Crear partículas de estela con throttling
            const now = Date.now();
            if (now - lastTrailTime > trailInterval) {
                crearParticulaTrail(e.clientX, e.clientY);
                lastTrailTime = now;
            }
        });
    });
    // Detectar elementos interactivos para efecto hover
    const interactiveElements = document.querySelectorAll('a, button, input, select, textarea, .btn, .card, .select2-container, .select2-selection, .select2-results__option');
    interactiveElements.forEach(el => {
        el.addEventListener('mouseenter', () => {
            cursor.classList.add('hover-active');
        });
        el.addEventListener('mouseleave', () => {
            cursor.classList.remove('hover-active');
        });
    });
    // Ocultar cursor si sale de la ventana
    document.addEventListener('mouseleave', () => {
        cursor.style.opacity = '0';
    });
    document.addEventListener('mouseenter', () => {
        cursor.style.opacity = '1';
    });
}
// ============================================================
// PRE-NAV LOADER
// Muestra un overlay INMEDIATAMENTE al dar clic en un
// dashboard pesado, antes de que el servidor responda.
// ============================================================
(function iniciarPreNavLoader() {
    const overlay = document.getElementById('nav-pre-loader');
    if (!overlay)
        return;
    // useCapture=true: se ejecuta en fase de captura, antes
    // que cualquier handler hijo pueda llamar stopPropagation
    document.addEventListener('click', (e) => {
        const link = e.target
            .closest('a[data-nav-loader]');
        if (!link)
            return;
        // Ctrl/Cmd/Shift/Alt + clic → abrir en nueva pestaña, no interceptar
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey)
            return;
        overlay.classList.add('active');
    }, true);
    // Restablecer si el usuario vuelve con el botón "Atrás"
    // (bfcache restaura el DOM con la clase .active todavía presente)
    window.addEventListener('pageshow', (e) => {
        if (e.persisted)
            overlay.classList.remove('active');
    });
}());
//# sourceMappingURL=base.js.map