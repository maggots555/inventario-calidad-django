/**
 * seguimiento_chat.ts — Chatbot de IA en la vista pública de seguimiento del cliente
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo controla el chat de inteligencia artificial que el cliente ve
 * en su página de seguimiento de orden. El cliente puede hacer preguntas sobre
 * su equipo y el asistente responde usando los datos reales de la orden.
 *
 * Características:
 * - Burbuja flotante que se expande en un panel de chat
 * - Historial persistente en localStorage (por token del enlace)
 * - Efecto visual de escritura letra a letra en respuestas del bot
 * - Markdown básico seguro en respuestas del bot (negrita, listas)
 * - Chips de sugerencias dinámicos según estado de la orden (renderizados en Django)
 * - Indicador de procesamiento por etapas ("Consultando...", "Preparando...")
 * - Botón para borrar la conversación
 * - Compatible con modo oscuro y prefers-reduced-motion
 */
/// <reference path="./eventos_seguimiento.d.ts" />

// ============================================================================
// INTERFACES Y TIPOS
// ============================================================================

interface MensajeChat {
    role: 'user' | 'assistant';
    content: string;
}

interface HistorialPersistido {
    version: number;
    mensajes: MensajeChat[];
    ultimaActualizacion: string;
}

interface RespuestaChat {
    success: boolean;
    respuesta?: string;
    modelo_usado?: string;
    error?: string;
}

// ============================================================================
// CONSTANTES DE CONFIGURACIÓN
// ============================================================================

/** Máximo de turnos (pares user/assistant) a mantener en el historial */
const CHAT_MAX_TURNOS: number = 6;

/** Máximo de caracteres por pregunta del usuario */
const CHAT_MAX_CHARS: number = 500;

/** Clave localStorage para el badge "Nuevo" */
const CHAT_BADGE_KEY: string = 'sic_chat_opened';

/** Prefijo de la clave localStorage del historial (se concatena con el token) */
const CHAT_HIST_PREFIX: string = 'sic_chat_hist_';

/** Versión del formato guardado en localStorage */
const CHAT_HIST_VERSION: number = 1;

/** Días antes de descartar un historial guardado */
const CHAT_HIST_TTL_DIAS: number = 30;

/** Velocidad base de la animación de escritura (ms por carácter) */
const CHAT_TYPING_MS: number = 18;

/** Mensaje de bienvenida fijo del bot (no forma parte del historial enviado a la IA) */
const CHAT_WELCOME_MSG: string =
    '👋 Hola, soy el asistente virtual de SIC Fix. Puedo responder preguntas sobre tu equipo en reparación. ¿En qué puedo ayudarte?';

/** Control del indicador de procesamiento con etapas de texto */
interface IndicadorProcesando {
    elemento: HTMLElement;
    setEtapa: (texto: string) => void;
}

/**
 * Aplica negrita (**texto**) y cursiva (*texto*) de forma segura vía DOM.
 * No usa innerHTML para evitar XSS con contenido del modelo.
 */
function aplicarFormatoInline(texto: string, padre: HTMLElement): void {
    const regex = /\*\*([^*]+)\*\*|\*([^*]+)\*/g;
    let ultimo = 0;
    let coincidencia: RegExpExecArray | null;

    while ((coincidencia = regex.exec(texto)) !== null) {
        if (coincidencia.index > ultimo) {
            padre.appendChild(document.createTextNode(texto.slice(ultimo, coincidencia.index)));
        }
        if (coincidencia[1] !== undefined) {
            const strong = document.createElement('strong');
            strong.textContent = coincidencia[1];
            padre.appendChild(strong);
        } else if (coincidencia[2] !== undefined) {
            const em = document.createElement('em');
            em.textContent = coincidencia[2];
            padre.appendChild(em);
        }
        ultimo = coincidencia.index + coincidencia[0].length;
    }

    if (ultimo < texto.length) {
        padre.appendChild(document.createTextNode(texto.slice(ultimo)));
    }
}

/**
 * Renderiza markdown básico en burbujas del bot: saltos de línea, listas y énfasis.
 */
function renderizarMarkdownBot(contenedor: HTMLElement, texto: string): void {
    contenedor.textContent = '';
    contenedor.classList.add('st-chat-msg-bubble--md');

    const lineas = texto.split('\n');
    let primeraLinea = true;

    for (const linea of lineas) {
        const trimmed = linea.trim();

        if (!trimmed) {
            contenedor.appendChild(document.createElement('br'));
            continue;
        }

        const esLista = /^[-•*]\s+/.test(trimmed);
        const lineaEl = document.createElement(esLista ? 'div' : 'span');

        if (esLista) {
            lineaEl.className = 'st-chat-md-item';
            aplicarFormatoInline(trimmed.replace(/^[-•*]\s+/, '• '), lineaEl);
        } else {
            if (!primeraLinea) {
                contenedor.appendChild(document.createElement('br'));
            }
            aplicarFormatoInline(trimmed, lineaEl);
        }

        contenedor.appendChild(lineaEl);
        primeraLinea = false;
    }
}

/**
 * Renderiza markdown parcial durante la animación de escritura y opcionalmente el cursor.
 */
function renderizarBurbujaBotEnStreaming(
    contenedor: HTMLElement,
    textoParcial: string,
    mostrarCursor: boolean,
): void {
    renderizarMarkdownBot(contenedor, textoParcial);
    if (mostrarCursor) {
        const cursor = document.createElement('span');
        cursor.className = 'st-chat-cursor';
        cursor.setAttribute('aria-hidden', 'true');
        cursor.textContent = '▌';
        contenedor.appendChild(cursor);
    }
}

/** Pausa breve para que el usuario perciba el cambio de etapa */
function pausaMs(ms: number): Promise<void> {
    return new Promise(resolve => window.setTimeout(resolve, ms));
}

// ============================================================================
// MÓDULO PRINCIPAL: SeguimientoChat
// ============================================================================

class SeguimientoChat {
    private bubble:      HTMLButtonElement;
    private panel:       HTMLElement;
    private closeBtn:    HTMLButtonElement;
    private clearBtn:    HTMLButtonElement | null;
    private messagesEl:  HTMLElement;
    private inputEl:     HTMLTextAreaElement;
    private sendBtn:     HTMLButtonElement;
    private suggestEl:   HTMLElement | null;
    private badge:       HTMLElement | null;
    private statusLabel: HTMLElement | null;

    private historial:              MensajeChat[] = [];
    private cargando:               boolean = false;
    private panelAbierto:           boolean = false;
    private chatAbiertoRegistrado:  boolean = false;
    private ultimoEnvioViaChip:     boolean = false;
    private chatEndpoint:           string;
    private chatToken:              string;
    private aiEnabled:              boolean;
    private animacionActiva:        boolean = false;
    private cancelarAnimacion:      (() => void) | null = null;

    constructor(
        bubble: HTMLButtonElement,
        panel: HTMLElement,
        closeBtn: HTMLButtonElement,
        clearBtn: HTMLButtonElement | null,
        messagesEl: HTMLElement,
        inputEl: HTMLTextAreaElement,
        sendBtn: HTMLButtonElement,
        suggestEl: HTMLElement | null,
        badge: HTMLElement | null,
        statusLabel: HTMLElement | null,
    ) {
        this.bubble      = bubble;
        this.panel       = panel;
        this.closeBtn    = closeBtn;
        this.clearBtn    = clearBtn;
        this.messagesEl  = messagesEl;
        this.inputEl     = inputEl;
        this.sendBtn     = sendBtn;
        this.suggestEl   = suggestEl;
        this.badge       = badge;
        this.statusLabel = statusLabel;

        this.chatEndpoint = bubble.dataset['chatEndpoint'] ?? '';
        this.chatToken    = bubble.dataset['chatToken'] ?? '';
        this.aiEnabled    = bubble.dataset['aiEnabled'] === 'true';

        this.inicializarBadge();
        this.restaurarHistorial();
        this.registrarEventListeners();
    }

    // ========================================================================
    // CLAVE DE localStorage ACOTADA AL TOKEN DEL ENLACE
    // ========================================================================
    private claveHistorial(): string {
        return `${CHAT_HIST_PREFIX}${this.chatToken}`;
    }

    // ========================================================================
    // BADGE "NUEVO"
    // ========================================================================
    private inicializarBadge(): void {
        if (!this.badge) return;
        if (localStorage.getItem(CHAT_BADGE_KEY)) {
            this.badge.style.display = 'none';
        }
    }

    // ========================================================================
    // PERSISTENCIA DEL HISTORIAL EN localStorage
    // ========================================================================
    private guardarHistorial(): void {
        if (!this.chatToken) return;
        const payload: HistorialPersistido = {
            version: CHAT_HIST_VERSION,
            mensajes: this.historial.slice(-(CHAT_MAX_TURNOS * 2)),
            ultimaActualizacion: new Date().toISOString(),
        };
        try {
            localStorage.setItem(this.claveHistorial(), JSON.stringify(payload));
        } catch {
            // Si localStorage está lleno, ignoramos sin romper el chat
        }
    }

    private restaurarHistorial(): void {
        if (!this.chatToken) return;

        const raw = localStorage.getItem(this.claveHistorial());
        if (!raw) return;

        try {
            const data = JSON.parse(raw) as HistorialPersistido;
            if (data.version !== CHAT_HIST_VERSION || !Array.isArray(data.mensajes)) return;

            // Descartar historiales muy antiguos
            const fecha = new Date(data.ultimaActualizacion);
            const limiteMs = CHAT_HIST_TTL_DIAS * 24 * 60 * 60 * 1000;
            if (Date.now() - fecha.getTime() > limiteMs) {
                localStorage.removeItem(this.claveHistorial());
                return;
            }

            const mensajesValidos = data.mensajes.filter(
                (m): m is MensajeChat =>
                    (m.role === 'user' || m.role === 'assistant') &&
                    typeof m.content === 'string' &&
                    m.content.length > 0 &&
                    m.content.length <= 2000,
            );

            if (mensajesValidos.length === 0) return;

            this.historial = mensajesValidos.slice(-(CHAT_MAX_TURNOS * 2));
            this.renderizarHistorialRestaurado();
        } catch {
            localStorage.removeItem(this.claveHistorial());
        }
    }

    private renderizarHistorialRestaurado(): void {
        // Quitar solo el mensaje de bienvenida; conservar el contenedor
        const welcome = this.messagesEl.querySelector('[data-welcome="1"]');
        welcome?.remove();

        for (const msg of this.historial) {
            const rol = msg.role === 'user' ? 'user' : 'bot';
            this.agregarMensaje(msg.content, rol, false);
        }

        if (this.historial.length > 0) {
            this.ocultarSugerencias();
        }
    }

    private limpiarHistorial(): void {
        if (!confirm('¿Borrar toda la conversación con el asistente?')) return;

        this.detenerAnimacionEscritura();

        if (this.chatToken) {
            localStorage.removeItem(this.claveHistorial());
        }

        this.historial = [];
        this.messagesEl.innerHTML = '';

        const welcome = document.createElement('div');
        welcome.classList.add('st-chat-msg', 'st-chat-msg--bot');
        welcome.setAttribute('data-welcome', '1');
        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble');
        bubble.textContent = CHAT_WELCOME_MSG;
        welcome.appendChild(bubble);
        this.messagesEl.appendChild(welcome);

        if (this.suggestEl) {
            this.suggestEl.style.display = '';
        }

        this.scrollAlFinal();
    }

    // ========================================================================
    // EVENT LISTENERS
    // ========================================================================
    private registrarEventListeners(): void {
        this.bubble.addEventListener('click', () => this.togglePanel());
        this.closeBtn.addEventListener('click', () => this.cerrarPanel());
        this.clearBtn?.addEventListener('click', () => this.limpiarHistorial());
        this.sendBtn.addEventListener('click', () => this.enviarPregunta());

        this.inputEl.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!this.cargando) void this.enviarPregunta();
            }
        });

        this.inputEl.addEventListener('input', () => {
            this.actualizarEstadoBotonEnviar();
            this.autoResizeTextarea();
        });

        if (this.suggestEl) {
            this.suggestEl.querySelectorAll<HTMLButtonElement>('.st-chat-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    const texto = chip.textContent?.trim() ?? '';
                    if (texto && !this.cargando) {
                        this.ultimoEnvioViaChip = true;
                        this.inputEl.value = texto;
                        this.actualizarEstadoBotonEnviar();
                        void this.enviarPregunta();
                    }
                });
            });
        }

        document.addEventListener('click', (e: MouseEvent) => {
            if (!this.panelAbierto) return;
            const target = e.target as Node;
            if (!this.panel.contains(target) && !this.bubble.contains(target)) {
                this.cerrarPanel();
            }
        });

        window.addEventListener('resize', () => this.ajustarPosicion());
    }

    // ========================================================================
    // PANEL
    // ========================================================================
    private togglePanel(): void {
        if (this.panelAbierto) {
            this.cerrarPanel();
        } else {
            this.abrirPanel();
        }
    }

    private abrirPanel(): void {
        this.panelAbierto = true;
        if (!this.chatAbiertoRegistrado) {
            this.chatAbiertoRegistrado = true;
            window.EventosSeguimiento?.registrarEvento('chat_abierto', {}, true);
        }
        this.panel.classList.add('st-chat-panel--visible');
        this.panel.setAttribute('aria-hidden', 'false');
        this.bubble.classList.add('st-chat-bubble--active');
        this.bubble.setAttribute('aria-expanded', 'true');

        if (this.badge) {
            this.badge.style.display = 'none';
            localStorage.setItem(CHAT_BADGE_KEY, '1');
        }

        setTimeout(() => this.inputEl.focus(), 200);
        this.scrollAlFinal();
    }

    private cerrarPanel(): void {
        this.panelAbierto = false;
        this.panel.classList.remove('st-chat-panel--visible');
        this.panel.setAttribute('aria-hidden', 'true');
        this.bubble.classList.remove('st-chat-bubble--active');
        this.bubble.setAttribute('aria-expanded', 'false');
    }

    private ajustarPosicion(): void {
        if (window.visualViewport) {
            const vv = window.visualViewport;
            const keyboardOffset = window.innerHeight - vv.height - vv.offsetTop;
            if (keyboardOffset > 100 && this.panelAbierto) {
                this.panel.style.bottom = `${80 + keyboardOffset}px`;
            } else {
                this.panel.style.bottom = '';
            }
        }
    }

    private autoResizeTextarea(): void {
        this.inputEl.style.height = 'auto';
        const maxHeight = 5 * 24;
        this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, maxHeight) + 'px';
    }

    private actualizarEstadoBotonEnviar(): void {
        const texto = this.inputEl.value.trim();
        this.sendBtn.disabled = texto.length === 0 || this.cargando || !this.aiEnabled;
    }

    // ========================================================================
    // RENDERIZADO DE MENSAJES
    // ========================================================================
    private agregarMensaje(texto: string, rol: 'user' | 'bot', scroll: boolean = true): HTMLElement {
        const msgEl = document.createElement('div');
        msgEl.classList.add('st-chat-msg', `st-chat-msg--${rol}`);

        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble');

        if (rol === 'bot') {
            renderizarMarkdownBot(bubble, texto);
        } else {
            bubble.textContent = texto;
        }

        msgEl.appendChild(bubble);
        this.messagesEl.appendChild(msgEl);
        if (scroll) this.scrollAlFinal();
        return msgEl;
    }

    private crearBurbujaBotVacia(): HTMLElement {
        const msgEl = document.createElement('div');
        msgEl.classList.add('st-chat-msg', 'st-chat-msg--bot', 'st-chat-msg--streaming');

        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble', 'st-chat-msg-bubble--md');
        // El contenido y el cursor los agrega escribirProgresivo en cada paso

        msgEl.appendChild(bubble);
        this.messagesEl.appendChild(msgEl);
        this.scrollAlFinal();
        return msgEl;
    }

    /**
     * Indicador de procesamiento con etapa de texto + puntos animados.
     * Muestra mensajes como "Consultando tu orden..." mientras espera al servidor.
     */
    private mostrarIndicadorProcesando(textoInicial: string): IndicadorProcesando {
        const msgEl = document.createElement('div');
        msgEl.classList.add('st-chat-msg', 'st-chat-msg--bot', 'st-chat-msg--typing');
        msgEl.setAttribute('aria-label', textoInicial);

        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble', 'st-chat-typing-box');

        const label = document.createElement('span');
        label.className = 'st-chat-thinking-label';
        label.textContent = textoInicial;

        const dots = document.createElement('span');
        dots.className = 'st-chat-typing-indicator';
        dots.setAttribute('aria-hidden', 'true');
        dots.innerHTML = '<span></span><span></span><span></span>';

        bubble.appendChild(label);
        bubble.appendChild(dots);
        msgEl.appendChild(bubble);
        this.messagesEl.appendChild(msgEl);
        this.scrollAlFinal();

        return {
            elemento: msgEl,
            setEtapa: (texto: string): void => {
                label.textContent = texto;
                msgEl.setAttribute('aria-label', texto);
                this.scrollAlFinal();
            },
        };
    }

    private scrollAlFinal(): void {
        requestAnimationFrame(() => {
            this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
        });
    }

    private ocultarSugerencias(): void {
        if (this.suggestEl) {
            this.suggestEl.style.display = 'none';
        }
    }

    private setEstadoLabel(texto: string, tipo: 'normal' | 'pensando' | 'error'): void {
        if (!this.statusLabel) return;
        this.statusLabel.textContent = texto;
        this.statusLabel.className = 'st-chat-panel-status';
        if (tipo === 'pensando') this.statusLabel.classList.add('st-chat-panel-status--thinking');
        if (tipo === 'error')    this.statusLabel.classList.add('st-chat-panel-status--error');
    }

    // ========================================================================
    // EFECTO DE ESCRITURA SIMULADO (letra a letra)
    // ========================================================================
    private detenerAnimacionEscritura(): void {
        if (this.cancelarAnimacion) {
            this.cancelarAnimacion();
            this.cancelarAnimacion = null;
        }
        this.animacionActiva = false;
    }

    private escribirProgresivo(msgEl: HTMLElement, texto: string): Promise<void> {
        const bubble = msgEl.querySelector<HTMLElement>('.st-chat-msg-bubble');
        if (!bubble) return Promise.resolve();

        const reducirMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (reducirMovimiento) {
            renderizarMarkdownBot(bubble, texto);
            msgEl.classList.remove('st-chat-msg--streaming');
            return Promise.resolve();
        }

        return new Promise(resolve => {
            this.animacionActiva = true;
            let indice = 0;
            let cancelado = false;

            // Cierra la animación: markdown final sin cursor + transición suave
            const finalizar = (): void => {
                renderizarMarkdownBot(bubble, texto);
                msgEl.classList.remove('st-chat-msg--streaming');
                bubble.classList.add('st-chat-msg-bubble--md-done');
                this.animacionActiva = false;
                this.cancelarAnimacion = null;
                resolve();
            };

            this.cancelarAnimacion = (): void => {
                cancelado = true;
                finalizar();
            };

            const tick = (): void => {
                if (cancelado) return;

                if (indice >= texto.length) {
                    finalizar();
                    return;
                }

                // Mismo formato markdown durante toda la animación (evita salto brusco al final)
                const parcial = texto.slice(0, indice + 1);
                renderizarBurbujaBotEnStreaming(bubble, parcial, true);

                indice += 1;
                this.scrollAlFinal();

                const char = texto[indice - 1];
                const pausa = (char === '.' || char === '?' || char === '!') ? 120 : CHAT_TYPING_MS;
                window.setTimeout(tick, pausa);
            };

            tick();
        });
    }

    // ========================================================================
    // ENVIAR PREGUNTA AL BACKEND
    // ========================================================================
    async enviarPregunta(): Promise<void> {
        const pregunta = this.inputEl.value.trim();
        if (!pregunta || this.cargando || !this.aiEnabled) return;

        if (pregunta.length > CHAT_MAX_CHARS) {
            this.agregarMensaje(
                `La pregunta es demasiado larga (máx. ${CHAT_MAX_CHARS} caracteres).`,
                'bot',
            );
            return;
        }

        // Si hay una animación en curso, completarla antes de seguir
        this.detenerAnimacionEscritura();

        this.ocultarSugerencias();
        this.agregarMensaje(pregunta, 'user');

        this.inputEl.value = '';
        this.inputEl.style.height = 'auto';

        this.cargando = true;
        this.actualizarEstadoBotonEnviar();
        this.setEstadoLabel('Consultando tu orden...', 'pensando');

        const indicador = this.mostrarIndicadorProcesando('Consultando tu orden...');
        const historialParaEnviar = this.historial.slice(-(CHAT_MAX_TURNOS * 2));

        try {
            const formData = new FormData();
            formData.append('pregunta', pregunta);
            formData.append('historial', JSON.stringify(historialParaEnviar));
            formData.append('via_chip', this.ultimoEnvioViaChip ? 'true' : 'false');
            this.ultimoEnvioViaChip = false;

            const response = await fetch(this.chatEndpoint, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json() as RespuestaChat;

            // Segunda etapa visible antes de mostrar la respuesta
            indicador.setEtapa('Preparando respuesta...');
            this.setEstadoLabel('Preparando respuesta...', 'pensando');
            await pausaMs(450);
            indicador.elemento.remove();

            if (data.success && data.respuesta) {
                this.setEstadoLabel('Escribiendo respuesta...', 'pensando');

                const msgEl = this.crearBurbujaBotVacia();
                await this.escribirProgresivo(msgEl, data.respuesta);

                this.historial.push({ role: 'user', content: pregunta });
                this.historial.push({ role: 'assistant', content: data.respuesta });
                this.guardarHistorial();

                const modelo = data.modelo_usado ? ` · ${data.modelo_usado}` : '';
                this.setEstadoLabel(`IA · Listo${modelo}`, 'normal');
            } else {
                const mensajeError = data.error ?? 'No pude procesar tu pregunta. Intenta de nuevo.';
                this.agregarMensaje(mensajeError, 'bot');
                this.setEstadoLabel('Error al responder', 'error');
                setTimeout(() => this.setEstadoLabel('IA · Responde al instante', 'normal'), 3000);
            }
        } catch {
            indicador.elemento.remove();
            this.agregarMensaje(
                'Error de conexión. Intenta de nuevo en unos momentos.',
                'bot',
            );
            this.setEstadoLabel('Error de conexión', 'error');
            setTimeout(() => this.setEstadoLabel('IA · Responde al instante', 'normal'), 3000);
        } finally {
            this.cargando = false;
            this.actualizarEstadoBotonEnviar();
            this.inputEl.focus();
        }
    }
}

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', function (): void {
    const bubble = document.querySelector<HTMLButtonElement>('#chat-ia-bubble');
    if (!bubble) return;

    const panel      = document.querySelector<HTMLElement>('#chat-ia-panel');
    const closeBtn   = document.querySelector<HTMLButtonElement>('#chat-ia-close');
    const clearBtn   = document.querySelector<HTMLButtonElement>('#chat-ia-clear');
    const messagesEl = document.querySelector<HTMLElement>('#chat-ia-messages');
    const inputEl    = document.querySelector<HTMLTextAreaElement>('#chat-ia-input');
    const sendBtn    = document.querySelector<HTMLButtonElement>('#chat-ia-send');
    const suggestEl  = document.querySelector<HTMLElement>('#chat-ia-suggestions');
    const badge      = document.querySelector<HTMLElement>('#chat-ia-badge');
    const statusLabel = document.querySelector<HTMLElement>('#chat-ia-status-label');

    if (!panel || !closeBtn || !messagesEl || !inputEl || !sendBtn) {
        console.warn('[SeguimientoChat] Faltan elementos del DOM del chatbot.');
        return;
    }

    new SeguimientoChat(
        bubble,
        panel,
        closeBtn,
        clearBtn,
        messagesEl,
        inputEl,
        sendBtn,
        suggestEl,
        badge,
        statusLabel,
    );
});
