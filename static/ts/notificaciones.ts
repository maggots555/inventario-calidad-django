/**
 * Panel de Notificaciones Celery — Campanita 🔔
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja toda la lógica del panel de notificaciones
 * que aparece en el navbar como una campanita (🔔).
 *
 * ¿Qué hace?
 * 1. Consulta al servidor periódicamente: "¿Hay notificaciones nuevas?"
 * 2. Si hay, muestra un badge rojo con el número en la campanita
 * 3. Cuando el usuario hace clic, se abre un dropdown con la lista
 * 4. Al abrir el dropdown, se marcan todas como leídas automáticamente
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
// INTERFACES — Definen la estructura de los datos del servidor
// ============================================================================

/**
 * Representa una notificación individual que viene del servidor.
 *
 * EXPLICACIÓN: Cuando TypeScript conoce la forma de los datos,
 * tu editor (VS Code) te sugiere las propiedades disponibles
 * y te avisa si intentas usar una que no existe.
 */
/** Pestaña activa en el filtro de la campanita. */
type NotifTabActiva = 'todas' | 'equipo_disponible';

interface NotificacionItem {
    id: number;
    titulo: string;
    mensaje: string;
    tipo: 'exito' | 'error' | 'warning' | 'info';
    /** Agrupación para pestañas (general, equipo_disponible, …) */
    categoria: string;
    leida: boolean;
    fecha: string;
    app: string;
    url: string;  // '' cuando no hay destino; si tiene valor, la notif es navegable
}

/**
 * Respuesta completa del endpoint /notificaciones/api/listar/.
 *
 * EXPLICACIÓN: El servidor devuelve un JSON con esta estructura:
 * {
 *   "no_leidas": 3,
 *   "notificaciones": [{...}, {...}, {...}]
 * }
 */
interface NotificacionesResponse {
    no_leidas: number;
    notificaciones: NotificacionItem[];
}

/**
 * Configuración visual por tipo de notificación.
 * Cada tipo tiene un icono y una clase CSS de Bootstrap.
 */
interface TipoConfig {
    icono: string;
    clase: string;
}


// ============================================================================
// CONFIGURACIÓN DE TIPOS — Iconos y colores por tipo de notificación
// ============================================================================

/**
 * EXPLICACIÓN: Record<string, TipoConfig> significa:
 * "un objeto donde cada clave es un string (como 'exito')
 *  y cada valor es un TipoConfig (con icono y clase)."
 */
const TIPO_CONFIG: Record<string, TipoConfig> = {
    exito:   { icono: '✅', clase: 'text-success' },
    error:   { icono: '❌', clase: 'text-danger'  },
    warning: { icono: '⚠️', clase: 'text-warning' },
    info:    { icono: 'ℹ️',  clase: 'text-info'    },
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
    // ── Propiedades privadas ──
    // EXPLICACIÓN: "private" significa que solo esta clase puede acceder a ellas.
    // "HTMLElement | null" significa que el elemento puede no existir en el HTML.
    private readonly badge: HTMLElement | null;
    private readonly lista: HTMLElement | null;
    private readonly btnTodas: HTMLElement | null;
    private readonly btnLimpiar: HTMLElement | null;
    private readonly tabTodas: HTMLElement | null;
    private readonly tabEquipo: HTMLElement | null;
    private readonly tabEquipoCount: HTMLElement | null;
    private intervalo: number | null = null;

    // ── Polling adaptativo ──
    // EXPLICACIÓN: Cuando hay notificaciones nuevas, consultamos rápido (15s).
    // Cuando no hay cambios por varias rondas seguidas, bajamos a cada 60s
    // para no desperdiciar requests al servidor.
    // "pollingsSinCambio" cuenta cuántas consultas seguidas NO trajeron nada nuevo.
    // Si llega a UMBRAL_IDLE (4 rondas = 1 minuto sin cambios), cambiamos a modo lento.
    private readonly POLLING_ACTIVO_MS: number = 15_000;    // 15s — modo activo
    private readonly POLLING_IDLE_MS: number = 60_000;      // 60s — modo inactivo
    private readonly UMBRAL_IDLE: number = 4;               // 4 rondas sin cambios → idle
    private pollingsSinCambio: number = 0;
    private ultimoNoLeidas: number = -1;

    /** Copia completa de la última respuesta (filtro de pestañas en cliente). */
    private notificacionesCache: NotificacionItem[] = [];
    /** Pestaña activa: 'todas' muestra todo; 'equipo_disponible' solo esa categoría. */
    private tabActiva: NotifTabActiva = 'todas';

    /**
     * Constructor: se ejecuta automáticamente al hacer `new PanelNotificaciones()`.
     *
     * EXPLICACIÓN: getElementById busca en el HTML un elemento con ese atributo id="...".
     * Si no lo encuentra, devuelve null.
     */
    constructor() {
        this.badge      = document.getElementById('notif-badge');
        this.lista      = document.getElementById('notif-lista');
        this.btnTodas   = document.getElementById('notif-marcar-todas');
        this.btnLimpiar = document.getElementById('notif-limpiar-todas');
        this.tabTodas = document.getElementById('notif-tab-todas');
        this.tabEquipo = document.getElementById('notif-tab-equipo');
        this.tabEquipoCount = document.getElementById('notif-tab-equipo-count');

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
    private iniciar(): void {
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
            } else {
                // Pestaña visible otra vez → consultar YA y reanudar
                this.actualizarNotificaciones();
                this.iniciarPolling(this.getIntervaloActual());
            }
        });

        // Evento: botón "Marcar todas como leídas"
        if (this.btnTodas) {
            this.btnTodas.addEventListener('click', (e: Event) => {
                e.preventDefault();
                e.stopPropagation();
                this.marcarTodasLeidas();
            });
        }

        // Evento: botón "Limpiar todas"
        if (this.btnLimpiar) {
            this.btnLimpiar.addEventListener('click', (e: Event) => {
                e.preventDefault();
                e.stopPropagation();
                this.eliminarTodas();
            });
        }

        // Evento: eliminar notificación individual (delegación de eventos)
        // EXPLICACIÓN: En lugar de agregar un listener a cada botón ✕,
        // escuchamos clicks en la lista completa y verificamos si el click
        // fue en un botón de eliminar. Esto funciona aunque las notificaciones
        // se añadan dinámicamente después de cargar la página.
        if (this.lista) {
            this.lista.addEventListener('click', (e: Event) => {
                const target = e.target as HTMLElement;
                const btnEliminar: HTMLElement | null = target.closest('.notif-btn-eliminar');
                if (btnEliminar) {
                    e.preventDefault();
                    e.stopPropagation();
                    const id: string | undefined = btnEliminar.dataset.id;
                    if (id) {
                        this.eliminarNotificacion(parseInt(id, 10), btnEliminar);
                    }
                }
            });
        }

        // Evento: cuando se ABRE el dropdown (Bootstrap dispara 'shown.bs.dropdown')
        const dropdownEl = document.getElementById('notif-dropdown');
        if (dropdownEl) {
            dropdownEl.addEventListener('shown.bs.dropdown', () => {
                this.marcarTodasLeidas();
            });
        }

        // Pestañas de filtro (Todas / Equipo disponible)
        this.registrarClicksTabs();
    }

    /**
     * Registra clics en las pestañas de filtro de la campanita.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * No volvemos a pedir datos al servidor: filtramos la lista que ya
     * tenemos en memoria (notificacionesCache).
     */
    private registrarClicksTabs(): void {
        const tabs: Array<{ el: HTMLElement | null; tab: NotifTabActiva }> = [
            { el: this.tabTodas, tab: 'todas' },
            { el: this.tabEquipo, tab: 'equipo_disponible' },
        ];

        for (const { el, tab } of tabs) {
            if (!el) {
                continue;
            }
            el.addEventListener('click', (e: Event) => {
                e.preventDefault();
                e.stopPropagation();
                this.cambiarTab(tab);
            });
        }
    }

    /**
     * Cambia la pestaña activa y vuelve a dibujar la lista filtrada.
     */
    private cambiarTab(tab: NotifTabActiva): void {
        this.tabActiva = tab;
        this.actualizarEstadoVisualTabs();
        this.renderListaFiltrada();
    }

    /**
     * Marca visualmente qué pestaña está activa (clase + aria-selected).
     */
    private actualizarEstadoVisualTabs(): void {
        const pares: Array<{ el: HTMLElement | null; tab: NotifTabActiva }> = [
            { el: this.tabTodas, tab: 'todas' },
            { el: this.tabEquipo, tab: 'equipo_disponible' },
        ];
        for (const { el, tab } of pares) {
            if (!el) {
                continue;
            }
            const activa = tab === this.tabActiva;
            el.classList.toggle('active', activa);
            el.setAttribute('aria-selected', activa ? 'true' : 'false');
        }
    }

    /**
     * Actualiza el contador del tab "Equipo disponible" (no leídas de esa categoría).
     */
    private actualizarContadorTabEquipo(): void {
        if (!this.tabEquipoCount) {
            return;
        }
        const noLeidasEquipo = this.notificacionesCache.filter(
            (n) =>
                (n.categoria || 'general') === 'equipo_disponible' && !n.leida
        ).length;

        if (noLeidasEquipo > 0) {
            this.tabEquipoCount.textContent = String(noLeidasEquipo);
            this.tabEquipoCount.classList.remove('d-none');
        } else {
            this.tabEquipoCount.classList.add('d-none');
        }
    }

    /**
     * Aplica el filtro de la pestaña activa y dibuja la lista.
     */
    private renderListaFiltrada(): void {
        const filtradas =
            this.tabActiva === 'todas'
                ? this.notificacionesCache
                : this.notificacionesCache.filter(
                      (n) => (n.categoria || 'general') === this.tabActiva
                  );
        this.renderLista(filtradas);
    }

    // ── Gestión del intervalo de polling ──

    /**
     * Inicia (o reinicia) el intervalo de polling.
     *
     * EXPLICACIÓN: Primero detiene cualquier intervalo existente para evitar
     * intervalos duplicados (que harían el doble de requests).
     * Luego crea uno nuevo con el tiempo indicado.
     */
    private iniciarPolling(ms: number): void {
        this.detenerPolling();
        this.intervalo = window.setInterval(
            () => this.actualizarNotificaciones(),
            ms
        );
    }

    /**
     * Detiene el polling completamente.
     *
     * EXPLICACIÓN: clearInterval cancela un setInterval previo.
     * Se usa cuando la pestaña se oculta o cuando necesitamos cambiar la velocidad.
     */
    private detenerPolling(): void {
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
    private getIntervaloActual(): number {
        return this.pollingsSinCambio >= this.UMBRAL_IDLE
            ? this.POLLING_IDLE_MS
            : this.POLLING_ACTIVO_MS;
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
     * - Compara no_leidas con la última vez. Si cambió, resetea el contador.
     * - Si no cambió, incrementa pollingsSinCambio.
     * - Al cruzar el umbral (4 rondas), cambia de 15s a 60s automáticamente.
     * - Si llega algo nuevo, vuelve a 15s.
     */
    private async actualizarNotificaciones(): Promise<void> {
        try {
            const response: Response = await fetch('/notificaciones/api/listar/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            if (!response.ok) {
                return;
            }

            const data: NotificacionesResponse = await response.json() as NotificacionesResponse;

            // ── Polling adaptativo: ajustar velocidad según actividad ──
            const eraIdle: boolean = this.pollingsSinCambio >= this.UMBRAL_IDLE;

            if (data.no_leidas !== this.ultimoNoLeidas) {
                // Algo cambió → resetear a modo activo
                this.pollingsSinCambio = 0;

                // Si estábamos en modo idle, cambiar a intervalo rápido
                if (eraIdle && !document.hidden) {
                    this.iniciarPolling(this.POLLING_ACTIVO_MS);
                }
            } else {
                // Sin cambios → incrementar contador
                this.pollingsSinCambio++;

                // Si acabamos de cruzar el umbral, cambiar a intervalo lento
                if (this.pollingsSinCambio === this.UMBRAL_IDLE && !document.hidden) {
                    this.iniciarPolling(this.POLLING_IDLE_MS);
                }
            }

            this.ultimoNoLeidas = data.no_leidas;
            // Normalizar categoria por si el backend aún no la envía (cache viejo).
            this.notificacionesCache = data.notificaciones.map((n) => ({
                ...n,
                categoria: n.categoria || 'general',
            }));
            this.renderBadge(data.no_leidas);
            this.actualizarContadorTabEquipo();
            this.renderListaFiltrada();

        } catch (error: unknown) {
            // Silencioso: errores de red son esperados (usuario sin conexión, etc.)
            void error;
        }
    }

    /**
     * Actualiza el número rojo (badge) en la campanita.
     *
     * EXPLICACIÓN:
     * - Si hay notificaciones sin leer: muestra el badge con el número.
     * - Si NO hay: oculta el badge con la clase CSS "d-none" (Bootstrap: display:none).
     * - Si hay más de 99, muestra "99+" para que el badge no se deforme.
     */
    private renderBadge(cantidad: number): void {
        if (!this.badge) return;

        if (cantidad > 0) {
            this.badge.textContent = cantidad > 99 ? '99+' : String(cantidad);
            this.badge.classList.remove('d-none');

            // Agregar animación de pulso si hay nuevas
            this.badge.classList.add('notif-pulse');
        } else {
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
     * - Template literals (`...`) permiten insertar variables con ${variable}.
     */
    private renderLista(notificaciones: NotificacionItem[]): void {
        if (!this.lista) return;

        if (notificaciones.length === 0) {
            const mensajeVacio =
                this.tabActiva === 'equipo_disponible'
                    ? 'Sin avisos de equipo disponible'
                    : 'Sin notificaciones recientes';
            this.lista.innerHTML = `
                <li class="notif-vacia">
                    <i class="bi bi-bell-slash text-muted"></i>
                    <span>${mensajeVacio}</span>
                </li>`;
            return;
        }

        this.lista.innerHTML = notificaciones.map((n: NotificacionItem) => {
            const cfg: TipoConfig = TIPO_CONFIG[n.tipo] ?? TIPO_CONFIG['info'];
            const claseLeida: string = n.leida ? 'notif-leida' : 'notif-nueva';

            /*
             * Si la notificación tiene URL, envolvemos el contenido en un <a>
             * para que sea navegable al pulsar. El botón de eliminar queda fuera
             * del <a> para no interferir con la navegación.
             * Si no hay URL, el contenido es solo un <div> estático (comportamiento
             * original — compatible con todas las notificaciones existentes).
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
                <li class="notif-item ${claseLeida}" data-id="${n.id}">
                    ${innerHtml}
                    <button class="notif-btn-eliminar" data-id="${n.id}" title="Eliminar notificación">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </li>`;
        }).join('');
    }

    /**
     * Llama al endpoint para marcar todas como leídas.
     *
     * EXPLICACIÓN:
     * - method: 'POST' indica que estamos MODIFICANDO datos (no solo leyendo).
     * - X-CSRFToken es obligatorio en Django para proteger contra ataques CSRF.
     *   Sin este header, Django rechaza la petición con error 403.
     */
    private async marcarTodasLeidas(): Promise<void> {
        const csrfToken: string = this.getCsrfToken();

        try {
            await fetch('/notificaciones/api/marcar-todas/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken':      csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            // Actualiza badge a 0 inmediatamente (sin esperar al próximo polling)
            this.renderBadge(0);

            // Sincronizar cache local (contadores de pestaña + re-render)
            this.notificacionesCache = this.notificacionesCache.map((n) => ({
                ...n,
                leida: true,
            }));
            this.actualizarContadorTabEquipo();

            // Marca visualmente todas como leídas
            if (this.lista) {
                const nuevas: NodeListOf<Element> = this.lista.querySelectorAll('.notif-nueva');
                nuevas.forEach((el: Element) => {
                    el.classList.replace('notif-nueva', 'notif-leida');
                });
            }

        } catch (error: unknown) {
            // Silencioso: si falla, el próximo polling actualizará correctamente
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
     * 4. Si no quedan notificaciones, muestra el mensaje vacío
     */
    private async eliminarNotificacion(id: number, btnElement: HTMLElement): Promise<void> {
        const csrfToken: string = this.getCsrfToken();
        const itemLi: HTMLElement | null = btnElement.closest('.notif-item');

        try {
            const response: Response = await fetch(`/notificaciones/api/eliminar/${id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken':      csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            if (!response.ok) return;

            this.notificacionesCache = this.notificacionesCache.filter(
                (n) => n.id !== id
            );
            this.actualizarContadorTabEquipo();

            // Animación de salida: el item se desliza y desvanece
            if (itemLi) {
                itemLi.classList.add('notif-removing');
                // Esperar a que termine la animación CSS (300ms) antes de remover
                setTimeout(() => {
                    itemLi.remove();
                    // Si ya no quedan items visibles, re-render filtrado (mensaje vacío)
                    if (this.lista && this.lista.querySelectorAll('.notif-item').length === 0) {
                        this.renderListaFiltrada();
                    }
                }, 300);
            }

        } catch (error: unknown) {
            void error;
        }
    }

    /**
     * Elimina TODAS las notificaciones del usuario.
     *
     * EXPLICACIÓN: Botón "Limpiar todas" en el header del dropdown.
     * Borra todo del servidor y limpia la UI de una vez.
     */
    private async eliminarTodas(): Promise<void> {
        const csrfToken: string = this.getCsrfToken();

        try {
            const response: Response = await fetch('/notificaciones/api/eliminar-todas/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken':      csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            if (!response.ok) return;

            // Limpiar la UI y el cache local
            this.notificacionesCache = [];
            this.renderBadge(0);
            this.actualizarContadorTabEquipo();
            this.renderListaFiltrada();

        } catch (error: unknown) {
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
     *
     * document.cookie contiene TODAS las cookies como un string:
     * "csrftoken=abc123; sessionid=xyz789; otros=valores"
     *
     * Esta función busca el token en ese string con una expresión regular.
     * Busca ambos nombres de cookie (desarrollo y producción).
     */
    private getCsrfToken(): string {
        // Intentar con el nombre de producción primero, luego el default de Django
        const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];

        for (const name of cookieNames) {
            const regex: RegExp = new RegExp(`(?:^|;\\s*)${name}=([^;]+)`);
            const match: RegExpMatchArray | null = document.cookie.match(regex);
            if (match) {
                return match[1];
            }
        }

        return '';
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
    private escaparHtml(texto: string): string {
        const div: HTMLDivElement = document.createElement('div');
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
