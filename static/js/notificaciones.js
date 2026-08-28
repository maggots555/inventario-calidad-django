"use strict";
/**
 * Panel de Notificaciones Celery — Campanita 🔔
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja toda la lógica del panel de notificaciones
 * que aparece en el navbar como una campanita (🔔).
 *
 * ¿Qué hace?
 * 1. Consulta al servidor periódicamente: "¿Hay notificaciones nuevas?"
 * 2. El badge rojo cuenta SOLO las de «Por hacer» (trabajo pendiente)
 * 3. Pestañas: Por hacer (requiere acción) | Avisos (informativas)
 * 4. Al abrir, se marcan leídos los avisos; las de acción siguen pendientes
 *    hasta que haces clic en ellas o pulsas ✓✓
 *
 * Optimizaciones de producción:
 * - Polling adaptativo: 15s cuando hay actividad, 60s cuando está inactivo
 * - Pausa automática: deja de consultar si la pestaña no es visible
 * - Reanuda al volver: consulta inmediata al reactivar la pestaña
 *
 * Conceptos TypeScript usados:
 * - interface: Define la "forma" que deben tener los objetos (como un molde)
 * - class: Agrupa funciones relacionadas en un solo lugar
 * - async/await: Permite hacer peticiones al servidor sin bloquear la página
 * - Record<string, T>: Un objeto donde las claves son strings y los valores son T
 * - HTMLElement | null: El elemento puede existir o no en el HTML
 */
// ============================================================================
// CONFIGURACIÓN DE TIPOS — Iconos y colores por tipo de notificación
// ============================================================================
/**
 * EXPLICACIÓN: Record<string, TipoConfig> significa:
 * "un objeto donde cada clave es un string (como 'exito')
 *  y cada valor es un TipoConfig (con icono y clase)."
 */
const TIPO_CONFIG = {
    exito: { icono: '✅', clase: 'text-success' },
    error: { icono: '❌', clase: 'text-danger' },
    warning: { icono: '⚠️', clase: 'text-warning' },
    info: { icono: 'ℹ️', clase: 'text-info' },
};
// ============================================================================
// CLASE PRINCIPAL — PanelNotificaciones
// ============================================================================
/**
 * Maneja todo el ciclo de vida del panel de notificaciones.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Una "clase" en TypeScript es como un plano (blueprint) que agrupa:
 * - Propiedades (datos que necesita): badge, lista, intervalo
 * - Métodos (acciones que puede hacer): actualizar, renderizar, marcar leídas
 *
 * Al hacer `new PanelNotificaciones()`, se crea una instancia que
 * empieza a funcionar automáticamente.
 */
class PanelNotificaciones {
    /**
     * Constructor: se ejecuta automáticamente al hacer `new PanelNotificaciones()`.
     *
     * EXPLICACIÓN: getElementById busca en el HTML un elemento con ese atributo id="...".
     * Si no lo encuentra, devuelve null.
     */
    constructor() {
        this.intervalo = null;
        // ── Polling adaptativo ──
        // EXPLICACIÓN: Cuando hay notificaciones nuevas, consultamos rápido (15s).
        // Cuando no hay cambios por varias rondas seguidas, bajamos a cada 60s
        // para no desperdiciar requests al servidor.
        // "pollingsSinCambio" cuenta cuántas consultas seguidas NO trajeron nada nuevo.
        // Si llega a UMBRAL_IDLE (4 rondas = 1 minuto sin cambios), cambiamos a modo lento.
        this.POLLING_ACTIVO_MS = 15000; // 15s — modo activo
        this.POLLING_IDLE_MS = 60000; // 60s — modo inactivo
        this.UMBRAL_IDLE = 4; // 4 rondas sin cambios → idle
        this.pollingsSinCambio = 0;
        this.ultimoNoLeidas = -1;
        /** Cortes independientes que mandó el servidor. */
        this.cacheAccion = [];
        this.cacheAvisos = [];
        /** Contadores de no leídas (badge y pestañas). */
        this.noLeidasAccion = 0;
        this.noLeidasAvisos = 0;
        this.noLeidasEquipo = 0;
        /** Pestaña activa: 'accion' = Por hacer; 'avisos' = informativas. */
        this.tabActiva = 'accion';
        /** Chip Equipo disponible (solo filtra dentro de Por hacer). */
        this.chipEquipoActivo = false;
        this.badge = document.getElementById('notif-badge');
        this.lista = document.getElementById('notif-lista');
        this.btnTodas = document.getElementById('notif-marcar-todas');
        this.btnLimpiar = document.getElementById('notif-limpiar-todas');
        this.tabAccion = document.getElementById('notif-tab-accion');
        this.tabAvisos = document.getElementById('notif-tab-avisos');
        this.tabAccionCount = document.getElementById('notif-tab-accion-count');
        this.tabAvisosCount = document.getElementById('notif-tab-avisos-count');
        this.chipsAccion = document.getElementById('notif-chips-accion');
        this.chipEquipo = document.getElementById('notif-chip-equipo');
        this.chipEquipoCount = document.getElementById('notif-chip-equipo-count');
        // Solo iniciar si los elementos existen en el HTML
        // (no existen si el usuario no está logueado)
        if (this.badge && this.lista) {
            this.iniciar();
        }
    }
    /**
     * Inicia el polling automático y registra eventos.
     *
     * EXPLICACIÓN:
     * - Primera consulta inmediata: para que el badge aparezca sin esperar.
     * - iniciarPolling: arranca el intervalo con la velocidad adecuada.
     * - visibilitychange: el navegador avisa cuando cambias de pestaña.
     *   Si la pestaña se oculta, pausamos el polling para no gastar recursos.
     *   Cuando el usuario vuelve, consultamos inmediatamente y reanudamos.
     */
    iniciar() {
        // Primera consulta inmediata
        this.actualizarNotificaciones();
        // Iniciar polling con intervalo activo
        this.iniciarPolling(this.POLLING_ACTIVO_MS);
        // ── Optimización: pausar cuando la pestaña no es visible ──
        // EXPLICACIÓN: Si el usuario cambió a otra pestaña del navegador,
        // no tiene sentido seguir haciendo requests cada 15 segundos.
        // document.hidden = true cuando la pestaña está en segundo plano.
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Pestaña oculta → pausar polling completamente
                this.detenerPolling();
            }
            else {
                // Pestaña visible otra vez → consultar YA y reanudar
                this.actualizarNotificaciones();
                this.iniciarPolling(this.getIntervaloActual());
            }
        });
        // Evento: botón "Marcar todas como leídas" (incluye Por hacer)
        if (this.btnTodas) {
            this.btnTodas.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.marcarTodasLeidas();
            });
        }
        // Evento: botón "Limpiar todas"
        if (this.btnLimpiar) {
            this.btnLimpiar.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.eliminarTodas();
            });
        }
        // Delegación: ✕ elimina; clic en un ítem de acción lo marca leído.
        if (this.lista) {
            this.lista.addEventListener('click', (e) => {
                this.onClickLista(e);
            });
        }
        // Al ABRIR: solo avisos informativos (el badge de Por hacer no se apaga)
        const dropdownEl = document.getElementById('notif-dropdown');
        if (dropdownEl) {
            dropdownEl.addEventListener('shown.bs.dropdown', () => {
                this.marcarAvisosLeidos();
            });
        }
        this.registrarClicksTabs();
        this.registrarClickChipEquipo();
    }
    /**
     * Clic en la lista: eliminar o marcar una de «Por hacer» como leída.
     *
     * EXPLICACIÓN: Si el usuario pulsa el enlace de un pendiente, primero
     * avisamos al servidor (marcar/<id>/) y luego navegamos. Si no
     * preventDefault, el cambio de página cancela el fetch.
     */
    onClickLista(e) {
        const target = e.target;
        const btnEliminar = target.closest('.notif-btn-eliminar');
        if (btnEliminar) {
            e.preventDefault();
            e.stopPropagation();
            const idEliminar = btnEliminar.dataset.id;
            if (idEliminar) {
                this.eliminarNotificacion(parseInt(idEliminar, 10), btnEliminar);
            }
            return;
        }
        const itemLi = target.closest('.notif-item');
        if (!itemLi) {
            return;
        }
        const esAccion = itemLi.dataset.requiereAccion === 'true';
        if (!esAccion) {
            return;
        }
        const idStr = itemLi.dataset.id;
        if (!idStr) {
            return;
        }
        const id = parseInt(idStr, 10);
        const link = target.closest('.notif-link');
        const urlDestino = link && link.getAttribute('href') ? link.getAttribute('href') : '';
        // Paso: marcar en servidor; si hay URL, ir después para no perder el POST.
        if (urlDestino) {
            e.preventDefault();
            void this.marcarUnaLeida(id).then(() => {
                window.location.href = urlDestino;
            });
        }
        else {
            void this.marcarUnaLeida(id);
        }
    }
    /**
     * Registra clics en las pestañas Por hacer / Avisos.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * No volvemos a pedir datos al servidor: filtramos las listas que ya
     * tenemos en memoria (cacheAccion / cacheAvisos).
     */
    registrarClicksTabs() {
        const tabs = [
            { el: this.tabAccion, tab: 'accion' },
            { el: this.tabAvisos, tab: 'avisos' },
        ];
        for (const { el, tab } of tabs) {
            if (!el) {
                continue;
            }
            el.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.cambiarTab(tab);
            });
        }
    }
    /**
     * Chip «Equipo disponible»: atajo de Recepción dentro de Por hacer.
     */
    registrarClickChipEquipo() {
        if (!this.chipEquipo) {
            return;
        }
        this.chipEquipo.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.chipEquipoActivo = !this.chipEquipoActivo;
            this.actualizarEstadoVisualTabs();
            this.renderListaFiltrada();
        });
    }
    /**
     * Cambia la pestaña activa y vuelve a dibujar la lista filtrada.
     */
    cambiarTab(tab) {
        this.tabActiva = tab;
        // Al salir de Por hacer el chip deja de aplicar (sigue el estado visual).
        this.actualizarEstadoVisualTabs();
        this.renderListaFiltrada();
    }
    /**
     * Marca visualmente pestaña activa, visibilidad del chip y aria.
     */
    actualizarEstadoVisualTabs() {
        const pares = [
            { el: this.tabAccion, tab: 'accion' },
            { el: this.tabAvisos, tab: 'avisos' },
        ];
        for (const { el, tab } of pares) {
            if (!el) {
                continue;
            }
            const activa = tab === this.tabActiva;
            el.classList.toggle('active', activa);
            el.setAttribute('aria-selected', activa ? 'true' : 'false');
        }
        if (this.chipsAccion) {
            this.chipsAccion.classList.toggle('d-none', this.tabActiva !== 'accion');
        }
        if (this.chipEquipo) {
            this.chipEquipo.classList.toggle('active', this.chipEquipoActivo);
            this.chipEquipo.setAttribute('aria-pressed', this.chipEquipoActivo ? 'true' : 'false');
        }
    }
    /**
     * Actualiza los numeritos de pestañas y del chip Equipo.
     */
    actualizarContadoresTabs() {
        this.pintarContador(this.tabAccionCount, this.noLeidasAccion);
        this.pintarContador(this.tabAvisosCount, this.noLeidasAvisos);
        this.pintarContador(this.chipEquipoCount, this.noLeidasEquipo);
    }
    /**
     * Muestra u oculta un badge numérico (0 → d-none).
     */
    pintarContador(el, cantidad) {
        if (!el) {
            return;
        }
        if (cantidad > 0) {
            el.textContent = String(cantidad);
            el.classList.remove('d-none');
        }
        else {
            el.classList.add('d-none');
        }
    }
    /**
     * Aplica el filtro de la pestaña (y el chip) y dibuja la lista.
     */
    renderListaFiltrada() {
        let items;
        if (this.tabActiva === 'avisos') {
            items = this.cacheAvisos;
        }
        else if (this.chipEquipoActivo) {
            items = this.cacheAccion.filter((n) => (n.categoria || 'general') === 'equipo_disponible');
        }
        else {
            items = this.cacheAccion;
        }
        this.renderLista(items);
    }
    // ── Gestión del intervalo de polling ──
    /**
     * Inicia (o reinicia) el intervalo de polling.
     *
     * EXPLICACIÓN: Primero detiene cualquier intervalo existente para evitar
     * intervalos duplicados (que harían el doble de requests).
     * Luego crea uno nuevo con el tiempo indicado.
     */
    iniciarPolling(ms) {
        this.detenerPolling();
        this.intervalo = window.setInterval(() => this.actualizarNotificaciones(), ms);
    }
    /**
     * Detiene el polling completamente.
     *
     * EXPLICACIÓN: clearInterval cancela un setInterval previo.
     * Se usa cuando la pestaña se oculta o cuando necesitamos cambiar la velocidad.
     */
    detenerPolling() {
        if (this.intervalo !== null) {
            clearInterval(this.intervalo);
            this.intervalo = null;
        }
    }
    /**
     * Calcula el intervalo adecuado según la actividad reciente.
     *
     * EXPLICACIÓN: Si llevamos varias rondas sin notificaciones nuevas,
     * usamos el intervalo lento (60s). Si acaba de llegar algo nuevo,
     * usamos el rápido (15s).
     */
    getIntervaloActual() {
        return this.pollingsSinCambio >= this.UMBRAL_IDLE
            ? this.POLLING_IDLE_MS
            : this.POLLING_ACTIVO_MS;
    }
    /**
     * Normaliza un ítem del JSON (cache viejo o campos opcionales).
     */
    normalizarItem(n) {
        return {
            ...n,
            categoria: n.categoria || 'general',
            requiere_accion: Boolean(n.requiere_accion),
        };
    }
    /**
     * Consulta el servidor y actualiza la UI.
     *
     * EXPLICACIÓN:
     * - fetch() es la forma moderna de hacer peticiones HTTP desde el navegador.
     * - await pausa la función hasta que el servidor responda.
     * - response.json() convierte el texto JSON en un objeto TypeScript.
     *
     * Polling adaptativo:
     * - Compara no_leidas_accion con la última vez. Si cambió, resetea el contador.
     * - Si no cambió, incrementa pollingsSinCambio.
     * - Al cruzar el umbral (4 rondas), cambia de 15s a 60s automáticamente.
     * - Si llega algo nuevo, vuelve a 15s.
     */
    async actualizarNotificaciones() {
        var _a, _b, _c, _d;
        try {
            const response = await fetch('/notificaciones/api/listar/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            const noLeidasAccion = (_b = (_a = data.no_leidas_accion) !== null && _a !== void 0 ? _a : data.no_leidas) !== null && _b !== void 0 ? _b : 0;
            // ── Polling adaptativo: ajustar velocidad según actividad ──
            const eraIdle = this.pollingsSinCambio >= this.UMBRAL_IDLE;
            if (noLeidasAccion !== this.ultimoNoLeidas) {
                this.pollingsSinCambio = 0;
                if (eraIdle && !document.hidden) {
                    this.iniciarPolling(this.POLLING_ACTIVO_MS);
                }
            }
            else {
                this.pollingsSinCambio++;
                if (this.pollingsSinCambio === this.UMBRAL_IDLE && !document.hidden) {
                    this.iniciarPolling(this.POLLING_IDLE_MS);
                }
            }
            this.ultimoNoLeidas = noLeidasAccion;
            this.noLeidasAccion = noLeidasAccion;
            this.noLeidasAvisos = (_c = data.no_leidas_avisos) !== null && _c !== void 0 ? _c : 0;
            this.noLeidasEquipo = (_d = data.no_leidas_equipo) !== null && _d !== void 0 ? _d : 0;
            this.cacheAccion = (data.accion || []).map((n) => this.normalizarItem(n));
            this.cacheAvisos = (data.avisos || []).map((n) => this.normalizarItem(n));
            this.renderBadge(this.noLeidasAccion);
            this.actualizarContadoresTabs();
            this.actualizarEstadoVisualTabs();
            this.renderListaFiltrada();
        }
        catch (error) {
            // Silencioso: errores de red son esperados (usuario sin conexión, etc.)
            void error;
        }
    }
    /**
     * Actualiza el número rojo (badge) en la campanita.
     *
     * EXPLICACIÓN:
     * - Solo cuenta «Por hacer» no leídas: el ruido de Celery no enciende el punto.
     * - Si hay más de 99, muestra "99+" para que el badge no se deforme.
     */
    renderBadge(cantidad) {
        if (!this.badge)
            return;
        if (cantidad > 0) {
            this.badge.textContent = cantidad > 99 ? '99+' : String(cantidad);
            this.badge.classList.remove('d-none');
            this.badge.classList.add('notif-pulse');
        }
        else {
            this.badge.classList.add('d-none');
            this.badge.classList.remove('notif-pulse');
        }
    }
    /**
     * Dibuja la lista de notificaciones en el dropdown.
     *
     * EXPLICACIÓN:
     * - .map() transforma cada notificación en un string de HTML.
     * - .join('') une todos los strings en uno solo.
     * - innerHTML reemplaza el contenido existente con el nuevo HTML.
     */
    renderLista(notificaciones) {
        if (!this.lista)
            return;
        if (notificaciones.length === 0) {
            let mensajeVacio = 'Sin avisos recientes';
            if (this.tabActiva === 'accion' && this.chipEquipoActivo) {
                mensajeVacio = 'Sin avisos de equipo disponible';
            }
            else if (this.tabActiva === 'accion') {
                mensajeVacio = 'Nada pendiente por hacer';
            }
            this.lista.innerHTML = `
                <li class="notif-vacia">
                    <i class="bi bi-bell-slash text-muted"></i>
                    <span>${mensajeVacio}</span>
                </li>`;
            return;
        }
        this.lista.innerHTML = notificaciones.map((n) => {
            var _a;
            const cfg = (_a = TIPO_CONFIG[n.tipo]) !== null && _a !== void 0 ? _a : TIPO_CONFIG['info'];
            const claseLeida = n.leida ? 'notif-leida' : 'notif-nueva';
            /*
             * Si la notificación tiene URL, envolvemos el contenido en un <a>
             * para que sea navegable al pulsar. El botón de eliminar queda fuera
             * del <a> para no interferir con la navegación.
             */
            const contenidoHtml = `
                    <div class="notif-icono">${cfg.icono}</div>
                    <div class="notif-contenido">
                        <div class="notif-titulo ${cfg.clase}">${this.escaparHtml(n.titulo)}</div>
                        <div class="notif-mensaje">${this.escaparHtml(n.mensaje)}</div>
                        <div class="notif-meta">
                            ${n.app ? `<span class="notif-app">${this.escaparHtml(n.app)}</span>` : ''}
                            <span class="notif-fecha">${this.escaparHtml(n.fecha)}</span>
                        </div>
                    </div>`;
            const innerHtml = n.url
                ? `<a href="${this.escaparHtml(n.url)}" class="notif-link">${contenidoHtml}</a>`
                : `<div class="notif-link notif-link--static">${contenidoHtml}</div>`;
            return `
                <li class="notif-item ${claseLeida}" data-id="${n.id}" data-requiere-accion="${n.requiere_accion ? 'true' : 'false'}">
                    ${innerHtml}
                    <button class="notif-btn-eliminar" data-id="${n.id}" title="Eliminar notificación">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </li>`;
        }).join('');
    }
    /**
     * Headers comunes de POST (CSRF + AJAX).
     */
    headersPost() {
        return {
            'X-CSRFToken': this.getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
        };
    }
    /**
     * Marca una notificación de acción como leída (clic en el ítem).
     */
    async marcarUnaLeida(id) {
        try {
            await fetch(`/notificaciones/api/marcar/${id}/`, {
                method: 'POST',
                headers: this.headersPost(),
            });
            this.marcarLocalmente(id);
            this.recalcularContadoresLocales();
            this.renderBadge(this.noLeidasAccion);
            this.actualizarContadoresTabs();
            this.renderListaFiltrada();
        }
        catch (error) {
            void error;
        }
    }
    /**
     * Pone leida=true en el cache local de un id.
     */
    marcarLocalmente(id) {
        this.cacheAccion = this.cacheAccion.map((n) => n.id === id ? { ...n, leida: true } : n);
        this.cacheAvisos = this.cacheAvisos.map((n) => n.id === id ? { ...n, leida: true } : n);
    }
    /**
     * Recuenta no leídas desde el cache (puede subestimar si hay >20; el
     * próximo polling corrige con el count real de la BD).
     */
    recalcularContadoresLocales() {
        this.noLeidasAccion = this.cacheAccion.filter((n) => !n.leida).length;
        this.noLeidasAvisos = this.cacheAvisos.filter((n) => !n.leida).length;
        this.noLeidasEquipo = this.cacheAccion.filter((n) => !n.leida && (n.categoria || 'general') === 'equipo_disponible').length;
        this.ultimoNoLeidas = this.noLeidasAccion;
    }
    /**
     * Al abrir la campanita: solo marca Avisos (informativas).
     *
     * EXPLICACIÓN: El badge rojo = trabajo pendiente. Si marcáramos todo
     * al abrir, parecería que ya no hay nada que hacer.
     */
    async marcarAvisosLeidos() {
        try {
            await fetch('/notificaciones/api/marcar-avisos/', {
                method: 'POST',
                headers: this.headersPost(),
            });
            this.cacheAvisos = this.cacheAvisos.map((n) => ({ ...n, leida: true }));
            this.noLeidasAvisos = 0;
            this.actualizarContadoresTabs();
            if (this.tabActiva === 'avisos') {
                this.renderListaFiltrada();
            }
        }
        catch (error) {
            void error;
        }
    }
    /**
     * Botón ✓✓: marca TODAS (Por hacer + Avisos) como leídas.
     */
    async marcarTodasLeidas() {
        try {
            await fetch('/notificaciones/api/marcar-todas/', {
                method: 'POST',
                headers: this.headersPost(),
            });
            this.renderBadge(0);
            this.cacheAccion = this.cacheAccion.map((n) => ({ ...n, leida: true }));
            this.cacheAvisos = this.cacheAvisos.map((n) => ({ ...n, leida: true }));
            this.noLeidasAccion = 0;
            this.noLeidasAvisos = 0;
            this.noLeidasEquipo = 0;
            this.ultimoNoLeidas = 0;
            this.actualizarContadoresTabs();
            if (this.lista) {
                const nuevas = this.lista.querySelectorAll('.notif-nueva');
                nuevas.forEach((el) => {
                    el.classList.replace('notif-nueva', 'notif-leida');
                });
            }
        }
        catch (error) {
            void error;
        }
    }
    /**
     * Elimina una notificación individual.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando el usuario hace clic en la ✕ de una notificación:
     * 1. Envía un POST al servidor para borrarla de la BD
     * 2. Anima el item (se desliza hacia afuera)
     * 3. Lo remueve del DOM
     */
    async eliminarNotificacion(id, btnElement) {
        const itemLi = btnElement.closest('.notif-item');
        try {
            const response = await fetch(`/notificaciones/api/eliminar/${id}/`, {
                method: 'POST',
                headers: this.headersPost(),
            });
            if (!response.ok)
                return;
            this.cacheAccion = this.cacheAccion.filter((n) => n.id !== id);
            this.cacheAvisos = this.cacheAvisos.filter((n) => n.id !== id);
            this.recalcularContadoresLocales();
            this.renderBadge(this.noLeidasAccion);
            this.actualizarContadoresTabs();
            if (itemLi) {
                itemLi.classList.add('notif-removing');
                setTimeout(() => {
                    itemLi.remove();
                    if (this.lista && this.lista.querySelectorAll('.notif-item').length === 0) {
                        this.renderListaFiltrada();
                    }
                }, 300);
            }
        }
        catch (error) {
            void error;
        }
    }
    /**
     * Elimina TODAS las notificaciones del usuario.
     *
     * EXPLICACIÓN: Botón "Limpiar todas" en el header del dropdown.
     * Borra todo del servidor y limpia la UI de una vez.
     */
    async eliminarTodas() {
        try {
            const response = await fetch('/notificaciones/api/eliminar-todas/', {
                method: 'POST',
                headers: this.headersPost(),
            });
            if (!response.ok)
                return;
            this.cacheAccion = [];
            this.cacheAvisos = [];
            this.noLeidasAccion = 0;
            this.noLeidasAvisos = 0;
            this.noLeidasEquipo = 0;
            this.ultimoNoLeidas = 0;
            this.renderBadge(0);
            this.actualizarContadoresTabs();
            this.renderListaFiltrada();
        }
        catch (error) {
            void error;
        }
    }
    /**
     * Obtiene el CSRF token de las cookies de Django.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Django pone una cookie llamada "csrftoken" (o "sigma_csrftoken" en producción)
     * en tu navegador. Es un código de seguridad que debes enviar en cada petición POST.
     * Sin él, Django piensa que la petición es un ataque y la rechaza.
     */
    getCsrfToken() {
        var _a, _b;
        // Helper global: static/ts/csrf.ts (cargado en base.html)
        return (_b = (_a = window.getCsrfToken) === null || _a === void 0 ? void 0 : _a.call(window)) !== null && _b !== void 0 ? _b : '';
    }
    /**
     * Escapa caracteres HTML para prevenir ataques XSS.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Si un título de notificación contiene HTML como <script>alert('hack')</script>,
     * y lo insertamos directamente con innerHTML, el navegador lo ejecutaría.
     * Esta función convierte los caracteres peligrosos en versiones seguras:
     * < se convierte en &lt;  (el navegador lo muestra como < pero no lo ejecuta)
     * > se convierte en &gt;
     */
    escaparHtml(texto) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(texto));
        return div.innerHTML;
    }
}
// ============================================================================
// INICIALIZACIÓN — Arrancar cuando el DOM esté listo
// ============================================================================
/**
 * EXPLICACIÓN:
 * DOMContentLoaded se dispara cuando el HTML se terminó de cargar.
 * Es el momento seguro para buscar elementos con getElementById.
 * Si ejecutamos antes, los elementos aún no existen y obtenemos null.
 */
document.addEventListener('DOMContentLoaded', () => {
    new PanelNotificaciones();
});
//# sourceMappingURL=notificaciones.js.map