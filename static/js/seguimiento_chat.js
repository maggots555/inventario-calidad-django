"use strict";
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
// CONSTANTES DE CONFIGURACIÓN
// ============================================================================
/** Máximo de turnos (pares user/assistant) a mantener en el historial */
const CHAT_MAX_TURNOS = 6;
/** Máximo de caracteres por pregunta del usuario */
const CHAT_MAX_CHARS = 500;
/** Clave localStorage para el badge "Nuevo" */
const CHAT_BADGE_KEY = 'sic_chat_opened';
/** Prefijo de la clave localStorage del historial (se concatena con el token) */
const CHAT_HIST_PREFIX = 'sic_chat_hist_';
/** Versión del formato guardado en localStorage */
const CHAT_HIST_VERSION = 1;
/** Días antes de descartar un historial guardado */
const CHAT_HIST_TTL_DIAS = 30;
/** Velocidad base de la animación de escritura (ms por carácter) */
const CHAT_TYPING_MS = 18;
/** Mensaje de bienvenida fijo del bot (no forma parte del historial enviado a la IA) */
const CHAT_WELCOME_MSG = '👋 Hola, soy el asistente virtual de SIC Fix. Puedo responder preguntas sobre tu equipo en reparación. ¿En qué puedo ayudarte?';
/**
 * Aplica negrita (**texto**) y cursiva (*texto*) de forma segura vía DOM.
 * No usa innerHTML para evitar XSS con contenido del modelo.
 */
function aplicarFormatoInline(texto, padre) {
    const regex = /\*\*([^*]+)\*\*|\*([^*]+)\*/g;
    let ultimo = 0;
    let coincidencia;
    while ((coincidencia = regex.exec(texto)) !== null) {
        if (coincidencia.index > ultimo) {
            padre.appendChild(document.createTextNode(texto.slice(ultimo, coincidencia.index)));
        }
        if (coincidencia[1] !== undefined) {
            const strong = document.createElement('strong');
            strong.textContent = coincidencia[1];
            padre.appendChild(strong);
        }
        else if (coincidencia[2] !== undefined) {
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
function renderizarMarkdownBot(contenedor, texto) {
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
        }
        else {
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
function renderizarBurbujaBotEnStreaming(contenedor, textoParcial, mostrarCursor) {
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
function pausaMs(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
}
// ============================================================================
// MÓDULO PRINCIPAL: SeguimientoChat
// ============================================================================
class SeguimientoChat {
    constructor(bubble, panel, closeBtn, clearBtn, messagesEl, inputEl, sendBtn, suggestEl, badge, statusLabel) {
        var _a, _b;
        this.historial = [];
        this.cargando = false;
        this.panelAbierto = false;
        this.chatAbiertoRegistrado = false;
        this.ultimoEnvioViaChip = false;
        this.animacionActiva = false;
        this.cancelarAnimacion = null;
        this.bubble = bubble;
        this.panel = panel;
        this.closeBtn = closeBtn;
        this.clearBtn = clearBtn;
        this.messagesEl = messagesEl;
        this.inputEl = inputEl;
        this.sendBtn = sendBtn;
        this.suggestEl = suggestEl;
        this.badge = badge;
        this.statusLabel = statusLabel;
        this.chatEndpoint = (_a = bubble.dataset['chatEndpoint']) !== null && _a !== void 0 ? _a : '';
        this.chatToken = (_b = bubble.dataset['chatToken']) !== null && _b !== void 0 ? _b : '';
        this.aiEnabled = bubble.dataset['aiEnabled'] === 'true';
        this.inicializarBadge();
        this.restaurarHistorial();
        this.registrarEventListeners();
    }
    // ========================================================================
    // CLAVE DE localStorage ACOTADA AL TOKEN DEL ENLACE
    // ========================================================================
    claveHistorial() {
        return `${CHAT_HIST_PREFIX}${this.chatToken}`;
    }
    // ========================================================================
    // BADGE "NUEVO"
    // ========================================================================
    inicializarBadge() {
        if (!this.badge)
            return;
        if (localStorage.getItem(CHAT_BADGE_KEY)) {
            this.badge.style.display = 'none';
        }
    }
    // ========================================================================
    // PERSISTENCIA DEL HISTORIAL EN localStorage
    // ========================================================================
    guardarHistorial() {
        if (!this.chatToken)
            return;
        const payload = {
            version: CHAT_HIST_VERSION,
            mensajes: this.historial.slice(-(CHAT_MAX_TURNOS * 2)),
            ultimaActualizacion: new Date().toISOString(),
        };
        try {
            localStorage.setItem(this.claveHistorial(), JSON.stringify(payload));
        }
        catch {
            // Si localStorage está lleno, ignoramos sin romper el chat
        }
    }
    restaurarHistorial() {
        if (!this.chatToken)
            return;
        const raw = localStorage.getItem(this.claveHistorial());
        if (!raw)
            return;
        try {
            const data = JSON.parse(raw);
            if (data.version !== CHAT_HIST_VERSION || !Array.isArray(data.mensajes))
                return;
            // Descartar historiales muy antiguos
            const fecha = new Date(data.ultimaActualizacion);
            const limiteMs = CHAT_HIST_TTL_DIAS * 24 * 60 * 60 * 1000;
            if (Date.now() - fecha.getTime() > limiteMs) {
                localStorage.removeItem(this.claveHistorial());
                return;
            }
            const mensajesValidos = data.mensajes.filter((m) => (m.role === 'user' || m.role === 'assistant') &&
                typeof m.content === 'string' &&
                m.content.length > 0 &&
                m.content.length <= 2000);
            if (mensajesValidos.length === 0)
                return;
            this.historial = mensajesValidos.slice(-(CHAT_MAX_TURNOS * 2));
            this.renderizarHistorialRestaurado();
        }
        catch {
            localStorage.removeItem(this.claveHistorial());
        }
    }
    renderizarHistorialRestaurado() {
        // Quitar solo el mensaje de bienvenida; conservar el contenedor
        const welcome = this.messagesEl.querySelector('[data-welcome="1"]');
        welcome === null || welcome === void 0 ? void 0 : welcome.remove();
        for (const msg of this.historial) {
            const rol = msg.role === 'user' ? 'user' : 'bot';
            this.agregarMensaje(msg.content, rol, false);
        }
        if (this.historial.length > 0) {
            this.ocultarSugerencias();
        }
    }
    limpiarHistorial() {
        if (!confirm('¿Borrar toda la conversación con el asistente?'))
            return;
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
    registrarEventListeners() {
        var _a;
        this.bubble.addEventListener('click', () => this.togglePanel());
        this.closeBtn.addEventListener('click', () => this.cerrarPanel());
        (_a = this.clearBtn) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.limpiarHistorial());
        this.sendBtn.addEventListener('click', () => this.enviarPregunta());
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!this.cargando)
                    void this.enviarPregunta();
            }
        });
        this.inputEl.addEventListener('input', () => {
            this.actualizarEstadoBotonEnviar();
            this.autoResizeTextarea();
        });
        if (this.suggestEl) {
            this.suggestEl.querySelectorAll('.st-chat-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    var _a, _b;
                    const texto = (_b = (_a = chip.textContent) === null || _a === void 0 ? void 0 : _a.trim()) !== null && _b !== void 0 ? _b : '';
                    if (texto && !this.cargando) {
                        this.ultimoEnvioViaChip = true;
                        this.inputEl.value = texto;
                        this.actualizarEstadoBotonEnviar();
                        void this.enviarPregunta();
                    }
                });
            });
        }
        document.addEventListener('click', (e) => {
            if (!this.panelAbierto)
                return;
            const target = e.target;
            if (!this.panel.contains(target) && !this.bubble.contains(target)) {
                this.cerrarPanel();
            }
        });
        window.addEventListener('resize', () => this.ajustarPosicion());
    }
    // ========================================================================
    // PANEL
    // ========================================================================
    togglePanel() {
        if (this.panelAbierto) {
            this.cerrarPanel();
        }
        else {
            this.abrirPanel();
        }
    }
    abrirPanel() {
        var _a;
        this.panelAbierto = true;
        if (!this.chatAbiertoRegistrado) {
            this.chatAbiertoRegistrado = true;
            (_a = window.EventosSeguimiento) === null || _a === void 0 ? void 0 : _a.registrarEvento('chat_abierto', {}, true);
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
    cerrarPanel() {
        this.panelAbierto = false;
        this.panel.classList.remove('st-chat-panel--visible');
        this.panel.setAttribute('aria-hidden', 'true');
        this.bubble.classList.remove('st-chat-bubble--active');
        this.bubble.setAttribute('aria-expanded', 'false');
    }
    ajustarPosicion() {
        if (window.visualViewport) {
            const vv = window.visualViewport;
            const keyboardOffset = window.innerHeight - vv.height - vv.offsetTop;
            if (keyboardOffset > 100 && this.panelAbierto) {
                this.panel.style.bottom = `${80 + keyboardOffset}px`;
            }
            else {
                this.panel.style.bottom = '';
            }
        }
    }
    autoResizeTextarea() {
        this.inputEl.style.height = 'auto';
        const maxHeight = 5 * 24;
        this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, maxHeight) + 'px';
    }
    actualizarEstadoBotonEnviar() {
        const texto = this.inputEl.value.trim();
        this.sendBtn.disabled = texto.length === 0 || this.cargando || !this.aiEnabled;
    }
    // ========================================================================
    // RENDERIZADO DE MENSAJES
    // ========================================================================
    agregarMensaje(texto, rol, scroll = true) {
        const msgEl = document.createElement('div');
        msgEl.classList.add('st-chat-msg', `st-chat-msg--${rol}`);
        const bubble = document.createElement('div');
        bubble.classList.add('st-chat-msg-bubble');
        if (rol === 'bot') {
            renderizarMarkdownBot(bubble, texto);
        }
        else {
            bubble.textContent = texto;
        }
        msgEl.appendChild(bubble);
        this.messagesEl.appendChild(msgEl);
        if (scroll)
            this.scrollAlFinal();
        return msgEl;
    }
    crearBurbujaBotVacia() {
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
    mostrarIndicadorProcesando(textoInicial) {
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
            setEtapa: (texto) => {
                label.textContent = texto;
                msgEl.setAttribute('aria-label', texto);
                this.scrollAlFinal();
            },
        };
    }
    scrollAlFinal() {
        requestAnimationFrame(() => {
            this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
        });
    }
    ocultarSugerencias() {
        if (this.suggestEl) {
            this.suggestEl.style.display = 'none';
        }
    }
    setEstadoLabel(texto, tipo) {
        if (!this.statusLabel)
            return;
        this.statusLabel.textContent = texto;
        this.statusLabel.className = 'st-chat-panel-status';
        if (tipo === 'pensando')
            this.statusLabel.classList.add('st-chat-panel-status--thinking');
        if (tipo === 'error')
            this.statusLabel.classList.add('st-chat-panel-status--error');
    }
    // ========================================================================
    // EFECTO DE ESCRITURA SIMULADO (letra a letra)
    // ========================================================================
    detenerAnimacionEscritura() {
        if (this.cancelarAnimacion) {
            this.cancelarAnimacion();
            this.cancelarAnimacion = null;
        }
        this.animacionActiva = false;
    }
    escribirProgresivo(msgEl, texto) {
        const bubble = msgEl.querySelector('.st-chat-msg-bubble');
        if (!bubble)
            return Promise.resolve();
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
            const finalizar = () => {
                renderizarMarkdownBot(bubble, texto);
                msgEl.classList.remove('st-chat-msg--streaming');
                bubble.classList.add('st-chat-msg-bubble--md-done');
                this.animacionActiva = false;
                this.cancelarAnimacion = null;
                resolve();
            };
            this.cancelarAnimacion = () => {
                cancelado = true;
                finalizar();
            };
            const tick = () => {
                if (cancelado)
                    return;
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
    async enviarPregunta() {
        var _a;
        const pregunta = this.inputEl.value.trim();
        if (!pregunta || this.cargando || !this.aiEnabled)
            return;
        if (pregunta.length > CHAT_MAX_CHARS) {
            this.agregarMensaje(`La pregunta es demasiado larga (máx. ${CHAT_MAX_CHARS} caracteres).`, 'bot');
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
            const data = await response.json();
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
            }
            else {
                const mensajeError = (_a = data.error) !== null && _a !== void 0 ? _a : 'No pude procesar tu pregunta. Intenta de nuevo.';
                this.agregarMensaje(mensajeError, 'bot');
                this.setEstadoLabel('Error al responder', 'error');
                setTimeout(() => this.setEstadoLabel('IA · Responde al instante', 'normal'), 3000);
            }
        }
        catch {
            indicador.elemento.remove();
            this.agregarMensaje('Error de conexión. Intenta de nuevo en unos momentos.', 'bot');
            this.setEstadoLabel('Error de conexión', 'error');
            setTimeout(() => this.setEstadoLabel('IA · Responde al instante', 'normal'), 3000);
        }
        finally {
            this.cargando = false;
            this.actualizarEstadoBotonEnviar();
            this.inputEl.focus();
        }
    }
}
// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', function () {
    const bubble = document.querySelector('#chat-ia-bubble');
    if (!bubble)
        return;
    const panel = document.querySelector('#chat-ia-panel');
    const closeBtn = document.querySelector('#chat-ia-close');
    const clearBtn = document.querySelector('#chat-ia-clear');
    const messagesEl = document.querySelector('#chat-ia-messages');
    const inputEl = document.querySelector('#chat-ia-input');
    const sendBtn = document.querySelector('#chat-ia-send');
    const suggestEl = document.querySelector('#chat-ia-suggestions');
    const badge = document.querySelector('#chat-ia-badge');
    const statusLabel = document.querySelector('#chat-ia-status-label');
    if (!panel || !closeBtn || !messagesEl || !inputEl || !sendBtn) {
        console.warn('[SeguimientoChat] Faltan elementos del DOM del chatbot.');
        return;
    }
    new SeguimientoChat(bubble, panel, closeBtn, clearBtn, messagesEl, inputEl, sendBtn, suggestEl, badge, statusLabel);
});
//# sourceMappingURL=seguimiento_chat.js.map