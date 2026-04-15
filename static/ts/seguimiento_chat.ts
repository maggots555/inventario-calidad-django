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
 * - Historial de conversación (hasta 6 turnos = 12 mensajes)
 * - Chips de sugerencias rápidas al inicio
 * - Animación de "escribiendo..." mientras espera respuesta
 * - Auto-resize del textarea al escribir
 * - Compatible con modo oscuro del sistema
 * - Badge "Nuevo" que desaparece después de la primera apertura
 * - Sin CSRF token (endpoint público protegido por rate limiting + token de sesión)
 *
 * El historial de conversación se guarda SOLO en memoria (no en localStorage
 * ni en la base de datos). Si el cliente recarga la página, el historial se borra.
 */

// ============================================================================
// INTERFACES Y TIPOS
// ============================================================================

interface MensajeChat {
    role: 'user' | 'assistant';
    content: string;
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

/** Nombre de la clave en localStorage para recordar si el usuario ya abrió el chat */
const CHAT_BADGE_KEY: string = 'sic_chat_opened';

// ============================================================================
// MÓDULO PRINCIPAL: SeguimientoChat
// Encapsula toda la lógica del chatbot en un objeto para evitar variables globales.
// ============================================================================

class SeguimientoChat {
    // Referencias al DOM
    private bubble:     HTMLButtonElement;
    private panel:      HTMLElement;
    private closeBtn:   HTMLButtonElement;
    private messagesEl: HTMLElement;
    private inputEl:    HTMLTextAreaElement;
    private sendBtn:    HTMLButtonElement;
    private suggestEl:  HTMLElement | null;
    private badge:      HTMLElement | null;
    private statusLabel: HTMLElement | null;

    // Estado interno
    private historial:    MensajeChat[] = [];
    private cargando:     boolean = false;
    private panelAbierto: boolean = false;
    private chatEndpoint: string;
    private aiEnabled:    boolean;

    constructor(
        bubble: HTMLButtonElement,
        panel: HTMLElement,
        closeBtn: HTMLButtonElement,
        messagesEl: HTMLElement,
        inputEl: HTMLTextAreaElement,
        sendBtn: HTMLButtonElement,
        suggestEl: HTMLElement | null,
        badge: HTMLElement | null,
        statusLabel: HTMLElement | null,
    ) {
        this.bubble       = bubble;
        this.panel        = panel;
        this.closeBtn     = closeBtn;
        this.messagesEl   = messagesEl;
        this.inputEl      = inputEl;
        this.sendBtn      = sendBtn;
        this.suggestEl    = suggestEl;
        this.badge        = badge;
        this.statusLabel  = statusLabel;

        // Leer el endpoint y si la IA está habilitada desde el atributo data-* del botón
        this.chatEndpoint = bubble.dataset['chatEndpoint'] ?? '';
        this.aiEnabled    = bubble.dataset['aiEnabled'] === 'true';

        // Gestionar visibilidad del badge "Nuevo"
        this.inicializarBadge();

        // Registrar todos los listeners
        this.registrarEventListeners();
    }

    // ========================================================================
    // INICIALIZACIÓN DEL BADGE "NUEVO"
    // Se oculta permanentemente una vez que el usuario abre el chat por primera vez.
    // ========================================================================
    private inicializarBadge(): void {
        if (!this.badge) return;
        const yaAbrio = localStorage.getItem(CHAT_BADGE_KEY);
        if (yaAbrio) {
            this.badge.style.display = 'none';
        }
    }

    // ========================================================================
    // REGISTRO DE EVENT LISTENERS
    // ========================================================================
    private registrarEventListeners(): void {
        // Clic en la burbuja: toggle del panel
        this.bubble.addEventListener('click', () => this.togglePanel());

        // Botón de cerrar dentro del panel
        this.closeBtn.addEventListener('click', () => this.cerrarPanel());

        // Botón de enviar
        this.sendBtn.addEventListener('click', () => this.enviarPregunta());

        // Enter sin Shift en textarea: enviar
        this.inputEl.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!this.cargando) this.enviarPregunta();
            }
        });

        // Input: habilitar/deshabilitar botón de enviar + auto-resize
        this.inputEl.addEventListener('input', () => {
            this.actualizarEstadoBotonEnviar();
            this.autoResizeTextarea();
        });

        // Chips de sugerencias rápidas
        if (this.suggestEl) {
            this.suggestEl.querySelectorAll<HTMLButtonElement>('.st-chat-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    const texto = chip.textContent?.trim() ?? '';
                    if (texto && !this.cargando) {
                        this.inputEl.value = texto;
                        this.actualizarEstadoBotonEnviar();
                        this.enviarPregunta();
                    }
                });
            });
        }

        // Cerrar el panel si el usuario toca fuera de él (solo en mobile)
        document.addEventListener('click', (e: MouseEvent) => {
            if (!this.panelAbierto) return;
            const target = e.target as Node;
            if (!this.panel.contains(target) && !this.bubble.contains(target)) {
                this.cerrarPanel();
            }
        });

        // Ajustar la posición en resize (especialmente al aparecer el teclado en móvil)
        window.addEventListener('resize', () => this.ajustarPosicion());
    }

    // ========================================================================
    // TOGGLE DEL PANEL
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
        this.panel.classList.add('st-chat-panel--visible');
        this.panel.setAttribute('aria-hidden', 'false');
        this.bubble.classList.add('st-chat-bubble--active');
        this.bubble.setAttribute('aria-expanded', 'true');

        // Ocultar badge "Nuevo" permanentemente
        if (this.badge) {
            this.badge.style.display = 'none';
            localStorage.setItem(CHAT_BADGE_KEY, '1');
        }

        // Enfocar el input (con pequeño delay para esperar la animación CSS)
        setTimeout(() => {
            this.inputEl.focus();
        }, 200);

        // Scroll al final de los mensajes
        this.scrollAlFinal();
    }

    private cerrarPanel(): void {
        this.panelAbierto = false;
        this.panel.classList.remove('st-chat-panel--visible');
        this.panel.setAttribute('aria-hidden', 'true');
        this.bubble.classList.remove('st-chat-bubble--active');
        this.bubble.setAttribute('aria-expanded', 'false');
    }

    // ========================================================================
    // AJUSTE DINÁMICO DE POSICIÓN (cuando aparece el teclado en móvil)
    // ========================================================================
    private ajustarPosicion(): void {
        // Si el Visual Viewport API está disponible, lo usamos para detectar
        // cuánto sube el teclado en pantalla y ajustamos el panel
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

    // ========================================================================
    // AUTO-RESIZE DEL TEXTAREA
    // El textarea crece hasta 5 líneas y luego hace scroll.
    // ========================================================================
    private autoResizeTextarea(): void {
        this.inputEl.style.height = 'auto';
        const maxHeight: number = 5 * 24; // ~5 líneas de texto
        this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, maxHeight) + 'px';
    }

    // ========================================================================
    // GESTIÓN DEL BOTÓN DE ENVIAR
    // ========================================================================
    private actualizarEstadoBotonEnviar(): void {
        const texto = this.inputEl.value.trim();
        this.sendBtn.disabled = texto.length === 0 || this.cargando || !this.aiEnabled;
    }

    // ========================================================================
    // RENDERIZAR UN MENSAJE EN EL CHAT
    // ========================================================================
    private agregarMensaje(texto: string, rol: 'user' | 'bot'): HTMLElement {
        const msgEl = document.createElement('div');
        msgEl.classList.add('st-chat-msg', `st-chat-msg--${rol}`);

        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble');
        // Usamos textContent (no innerHTML) para evitar XSS con contenido del LLM
        bubble.textContent = texto;

        msgEl.appendChild(bubble);
        this.messagesEl.appendChild(msgEl);
        this.scrollAlFinal();
        return msgEl;
    }

    // ========================================================================
    // MOSTRAR INDICADOR "ESCRIBIENDO..."
    // ========================================================================
    private mostrarIndicadorEscribiendo(): HTMLElement {
        const msgEl = document.createElement('div');
        msgEl.classList.add('st-chat-msg', 'st-chat-msg--bot', 'st-chat-msg--typing');
        msgEl.setAttribute('aria-label', 'El asistente está escribiendo');

        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble', 'st-chat-typing-indicator');
        bubble.innerHTML = '<span></span><span></span><span></span>';

        msgEl.appendChild(bubble);
        this.messagesEl.appendChild(msgEl);
        this.scrollAlFinal();
        return msgEl;
    }

    // ========================================================================
    // SCROLL AL FINAL DEL HISTORIAL DE MENSAJES
    // ========================================================================
    private scrollAlFinal(): void {
        requestAnimationFrame(() => {
            this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
        });
    }

    // ========================================================================
    // OCULTAR LOS CHIPS DE SUGERENCIAS (después del primer mensaje)
    // ========================================================================
    private ocultarSugerencias(): void {
        if (this.suggestEl) {
            this.suggestEl.style.display = 'none';
        }
    }

    // ========================================================================
    // ACTUALIZAR EL LABEL DE ESTADO EN EL HEADER DEL PANEL
    // ========================================================================
    private setEstadoLabel(texto: string, tipo: 'normal' | 'pensando' | 'error'): void {
        if (!this.statusLabel) return;
        this.statusLabel.textContent = texto;
        this.statusLabel.className = 'st-chat-panel-status';
        if (tipo === 'pensando') this.statusLabel.classList.add('st-chat-panel-status--thinking');
        if (tipo === 'error')    this.statusLabel.classList.add('st-chat-panel-status--error');
    }

    // ========================================================================
    // ENVIAR PREGUNTA AL BACKEND Y PROCESAR RESPUESTA
    // ========================================================================
    async enviarPregunta(): Promise<void> {
        const pregunta = this.inputEl.value.trim();
        if (!pregunta || this.cargando || !this.aiEnabled) return;

        // Validación de longitud (también validada en el backend)
        if (pregunta.length > CHAT_MAX_CHARS) {
            this.agregarMensaje(
                `La pregunta es demasiado larga (máx. ${CHAT_MAX_CHARS} caracteres).`,
                'bot'
            );
            return;
        }

        // Ocultar sugerencias al primer envío
        this.ocultarSugerencias();

        // Mostrar el mensaje del usuario en el chat
        this.agregarMensaje(pregunta, 'user');

        // Limpiar y resetear el textarea
        this.inputEl.value = '';
        this.inputEl.style.height = 'auto';

        // Bloquear UI mientras se espera la respuesta
        this.cargando = true;
        this.actualizarEstadoBotonEnviar();
        this.setEstadoLabel('Escribiendo...', 'pensando');

        // Mostrar indicador de "escribiendo"
        const indicador = this.mostrarIndicadorEscribiendo();

        // Preparar el historial a enviar (solo los últimos CHAT_MAX_TURNOS turnos)
        // IMPORTANTE: Solo mandamos los mensajes role:user/assistant del historial
        // (no el mensaje de bienvenida hardcoded del DOM)
        const historialParaEnviar: MensajeChat[] = this.historial.slice(-(CHAT_MAX_TURNOS * 2));

        try {
            const formData = new FormData();
            formData.append('pregunta', pregunta);
            formData.append('historial', JSON.stringify(historialParaEnviar));

            const response = await fetch(this.chatEndpoint, {
                method: 'POST',
                body: formData,
                // Sin CSRF: endpoint público, protegido por rate limiting + token
            });

            const data = await response.json() as RespuestaChat;

            // Eliminar el indicador de "escribiendo"
            indicador.remove();

            if (data.success && data.respuesta) {
                // Mostrar la respuesta del asistente
                this.agregarMensaje(data.respuesta, 'bot');

                // Agregar ambos mensajes al historial en memoria
                this.historial.push({ role: 'user',      content: pregunta });
                this.historial.push({ role: 'assistant', content: data.respuesta });

                this.setEstadoLabel('IA · Responde al instante', 'normal');
            } else {
                const mensajeError = data.error ?? 'No pude procesar tu pregunta. Intenta de nuevo.';
                this.agregarMensaje(mensajeError, 'bot');
                this.setEstadoLabel('Error al responder', 'error');
                // Restaurar label normal después de 3 segundos
                setTimeout(() => this.setEstadoLabel('IA · Responde al instante', 'normal'), 3000);
            }
        } catch (err: unknown) {
            indicador.remove();
            const msgError = err instanceof Error && err.message.includes('fetch')
                ? 'Sin conexión a internet. Verifica tu red e intenta de nuevo.'
                : 'Error de conexión. Intenta de nuevo en unos momentos.';
            this.agregarMensaje(msgError, 'bot');
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
// INICIALIZACIÓN — Ejecutar cuando el DOM esté completamente cargado
// ============================================================================
document.addEventListener('DOMContentLoaded', function (): void {
    // Verificar que existe el botón de la burbuja (solo se renderiza si ai_enabled=True)
    const bubble = document.querySelector<HTMLButtonElement>('#chat-ia-bubble');
    if (!bubble) return; // La IA no está habilitada o es vista inválida — no hacer nada

    const panel      = document.querySelector<HTMLElement>('#chat-ia-panel');
    const closeBtn   = document.querySelector<HTMLButtonElement>('#chat-ia-close');
    const messagesEl = document.querySelector<HTMLElement>('#chat-ia-messages');
    const inputEl    = document.querySelector<HTMLTextAreaElement>('#chat-ia-input');
    const sendBtn    = document.querySelector<HTMLButtonElement>('#chat-ia-send');
    const suggestEl  = document.querySelector<HTMLElement>('#chat-ia-suggestions');
    const badge      = document.querySelector<HTMLElement>('#chat-ia-badge');
    const statusLabel = document.querySelector<HTMLElement>('#chat-ia-status-label');

    // Guardia de seguridad: si falta cualquier elemento crítico, no inicializar
    if (!panel || !closeBtn || !messagesEl || !inputEl || !sendBtn) {
        console.warn('[SeguimientoChat] Faltan elementos del DOM del chatbot. Verificar el template.');
        return;
    }

    // Inicializar el módulo del chat
    new SeguimientoChat(
        bubble,
        panel,
        closeBtn,
        messagesEl,
        inputEl,
        sendBtn,
        suggestEl,
        badge,
        statusLabel,
    );
});
