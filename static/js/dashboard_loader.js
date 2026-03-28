"use strict";
/* =============================================================================
   DASHBOARD LOADER — Pantalla de carga animada para dashboards pesados
   
   Uso:
     // En cada dashboard, al final del bloque extra_js:
     const loader = new DashboardLoader({
         tituloExtra: 'Dashboard de Cotizaciones',
         mensajes: ['Cargando Plotly...', 'Calculando métricas...'],
         tips: ['Tip 1', 'Tip 2'],
     });
     // El loader se auto-oculta cuando window.load dispara.
     // Para form submit: loader.mostrarParaNavegacion()
   
   EXPLAIN TO USER:
     Esta clase maneja la pantalla de carga que aparece cuando abres
     los dashboards pesados. Funciona así:
     1. La pantalla de carga es visible desde el inicio (está en el HTML)
     2. Simula una barra de progreso que avanza gradualmente
     3. Cuando el navegador termina de cargar toda la página (window.load),
        la barra llega al 100% y la pantalla se desvanece
     4. El contenido del dashboard aparece con una animación suave
   ============================================================================= */
// La declaración de Window.sigmaLoader está en globals.d.ts
// (no se repite aquí para evitar conflicto de módulo ambient)
// ---- Clase principal ----
/**
 * Gestiona la pantalla de carga épica de los dashboards.
 *
 * Ciclo de vida:
 *   constructor() → iniciar() → [simulación de progreso] → completar() → salir() → revelarContenido()
 */
class DashboardLoader {
    constructor(config) {
        var _a, _b;
        this.plotlyMode = false; // inicializado aquí para el return temprano
        // Estado interno
        this.progreso = 0;
        this.indiceMensaje = 0;
        this.indiceTip = 0;
        this.cargaCompleta = false;
        // IDs de timers pendientes (para limpiarlos correctamente)
        this.timers = [];
        // Buscar todos los elementos necesarios en el DOM
        const overlay = document.getElementById('sigma-loader');
        const pFill = document.getElementById('loaderProgressFill');
        const pPct = document.getElementById('loaderProgressPct');
        const statusEl = document.getElementById('loaderStatus');
        const tipTextEl = document.getElementById('loaderTipText');
        const tipEl = document.querySelector('.loader-tip');
        // Si falta algún elemento, revelar contenido directamente (fallback seguro)
        if (!overlay || !pFill || !pPct || !statusEl || !tipTextEl || !tipEl) {
            console.warn('DashboardLoader: elementos del loader no encontrados — skip');
            this.revelarContenido();
            // Asignar elementos dummy para evitar errores de null
            const dummy = document.createElement('div');
            this.overlay = dummy;
            this.progressFill = dummy;
            this.progressPct = dummy;
            this.statusEl = dummy;
            this.tipTextEl = dummy;
            this.tipEl = dummy;
            this.mensajes = [];
            this.tips = [];
            this.delayExtra = 0;
            return;
        }
        this.overlay = overlay;
        this.progressFill = pFill;
        this.progressPct = pPct;
        this.statusEl = statusEl;
        this.tipTextEl = tipTextEl;
        this.tipEl = tipEl;
        // Fallbacks si los arrays están vacíos
        this.mensajes = config.mensajes.length > 0 ? config.mensajes : ['Cargando dashboard...'];
        this.tips = config.tips.length > 0 ? config.tips : ['Procesando datos...'];
        this.delayExtra = (_a = config.delayExtra) !== null && _a !== void 0 ? _a : 500;
        this.plotlyMode = (_b = config.plotlyMode) !== null && _b !== void 0 ? _b : false;
        // Aplicar título extra si se proporcionó
        if (config.tituloExtra) {
            const nameEl = document.getElementById('loaderDashboardName');
            if (nameEl)
                nameEl.textContent = config.tituloExtra;
        }
        // Activar clase CSS del modo Plotly si corresponde
        if (this.plotlyMode) {
            this.overlay.classList.add('plotly-mode');
        }
        // Registrar instancia globalmente
        window.sigmaLoader = this;
        this.iniciar();
    }
    // ---- Métodos privados ----
    /**
     * Arranca la animación, los rotadores y la estrategia de progreso.
     *
     * - Modo normal:  simularProgreso() con setTimeout
     * - Modo Plotly:  la barra avanza por CSS animation; aquí solo
     *                 iniciamos el sincronizador del número y los rotadores
     */
    iniciar() {
        // Primer mensaje y tip de inmediato
        this.statusEl.textContent = this.mensajes[0];
        this.tipTextEl.textContent = this.tips[0];
        if (this.plotlyMode) {
            // En plotlyMode la barra está oculta — no hay nada que sincronizar.
            // Solo iniciamos los rotadores de mensajes y tips.
        }
        else {
            this.simularProgreso();
        }
        // Rotar mensaje cada 2.2 s (setInterval se ejecuta cuando JS tiene tiempo libre)
        const tMsg = window.setInterval(() => this.rotarMensaje(), 2200);
        this.timers.push(tMsg);
        // Rotar tip cada 5 s
        const tTip = window.setInterval(() => this.rotarTip(), 5000);
        this.timers.push(tTip);
        console.log(`🚀 DashboardLoader iniciado [modo: ${this.plotlyMode ? 'plotly-css' : 'js-timeout'}]`);
    }
    /**
     * MODO PLOTLY: método eliminado — la barra está oculta en plotlyMode.
     * Se conserva el método vacío para evitar refactoring adicional.
     * @deprecated No llamar — solo existe como stub.
     */
    iniciarSincronizacionNumeroCss() {
        // no-op: barra oculta en plotlyMode
    }
    /**
     * Simula el avance gradual de la barra.
     * El progreso nunca supera 90 % hasta que se llame completar().
     */
    simularProgreso() {
        const paso = () => {
            if (this.cargaCompleta)
                return;
            // Incremento variable: rápido al principio, muy lento cerca de 90%
            let inc;
            if (this.progreso < 25)
                inc = Math.random() * 7 + 3;
            else if (this.progreso < 55)
                inc = Math.random() * 4 + 1;
            else if (this.progreso < 78)
                inc = Math.random() * 2 + 0.5;
            else
                inc = Math.random() * 0.6 + 0.1;
            this.progreso = Math.min(this.progreso + inc, 90);
            this.actualizarBarra(this.progreso);
            // Intervalo variable también
            const delay = this.progreso < 40 ? 120 : this.progreso < 75 ? 220 : 480;
            const t = window.setTimeout(paso, delay);
            this.timers.push(t);
        };
        const t = window.setTimeout(paso, 80);
        this.timers.push(t);
    }
    /** Actualiza DOM de la barra y el porcentaje (solo modo normal). */
    actualizarBarra(valor) {
        this.progressFill.style.width = `${valor.toFixed(1)}%`;
        this.progressPct.textContent = `${Math.min(Math.round(valor), 100)}%`;
    }
    /** Cambia al siguiente mensaje con fade-in/out. */
    rotarMensaje() {
        if (this.cargaCompleta)
            return;
        this.statusEl.classList.add('fade');
        const t = window.setTimeout(() => {
            this.indiceMensaje = (this.indiceMensaje + 1) % this.mensajes.length;
            this.statusEl.textContent = this.mensajes[this.indiceMensaje];
            this.statusEl.classList.remove('fade');
        }, 350);
        this.timers.push(t);
    }
    /** Cambia al siguiente tip con fade-in/out. */
    rotarTip() {
        if (this.cargaCompleta)
            return;
        this.tipEl.classList.add('fade');
        const t = window.setTimeout(() => {
            this.indiceTip = (this.indiceTip + 1) % this.tips.length;
            this.tipTextEl.textContent = this.tips[this.indiceTip];
            this.tipEl.classList.remove('fade');
        }, 350);
        this.timers.push(t);
    }
    /** Revela el contenido del dashboard. */
    revelarContenido() {
        const wrapper = document.getElementById('dashboard-content');
        if (wrapper)
            wrapper.classList.add('visible');
    }
    // ---- Métodos públicos ----
    /**
     * Completa la barra al 100 % y dispara la animación de salida.
     * Llamar cuando window.load ha disparado (o cuando Chart.js terminó de renderizar).
     *
     * En modo Plotly: primero se lee el ancho real de la barra CSS (puede estar en cualquier
     * punto de la animación), se congela con `.js-final`, y luego se completa con JS.
     */
    completar() {
        this.cargaCompleta = true;
        // Detener todos los timers
        this.timers.forEach(id => { window.clearTimeout(id); window.clearInterval(id); });
        this.timers = [];
        // Mensaje final
        this.statusEl.classList.remove('fade');
        this.statusEl.textContent = '¡Carga completa!';
        if (this.plotlyMode) {
            // Agregar .carga-lista al overlay activa el CSS que muestra
            // el texto de estado en verde (visible sobre visibility:hidden del padre)
            this.overlay.classList.add('carga-lista');
            window.setTimeout(() => this.salir(), this.delayExtra);
        }
        else {
            this.animarBarra100();
        }
    }
    /**
     * Anima la barra desde `this.progreso` hasta el 100 % con ease-out cúbico.
     * Solo se usa en modo normal (Chart.js). En plotlyMode, completar() usa
     * una única asignación scaleX(1) + CSS transition para evitar conflictos.
     */
    animarBarra100() {
        const valorInicio = this.progreso;
        const duracion = 640;
        const tiempoInicio = performance.now();
        const animarFinal = (ahora) => {
            const t = Math.min((ahora - tiempoInicio) / duracion, 1);
            const eased = 1 - Math.pow(1 - t, 3); // ease-out cúbico
            const valor = valorInicio + (100 - valorInicio) * eased;
            this.actualizarBarra(valor);
            if (t < 1) {
                requestAnimationFrame(animarFinal);
            }
            else {
                // Esperar delayExtra antes de iniciar el fade-out
                window.setTimeout(() => this.salir(), this.delayExtra);
            }
        };
        requestAnimationFrame(animarFinal);
    }
    /** Anima la salida del loader y revela el contenido. */
    salir() {
        this.overlay.classList.add('fadeout');
        window.setTimeout(() => {
            this.overlay.classList.add('hidden');
            this.revelarContenido();
            console.log('✅ DashboardLoader: contenido revelado');
        }, 850); // un poco más que el transition de 0.8s en CSS
    }
    /**
     * Muestra el loader para una navegación (submit de formulario de filtros).
     * NO hace fade-out — la página se recargará sola.
     */
    mostrarParaNavegacion() {
        this.overlay.classList.remove('hidden', 'fadeout');
        // Reiniciar estado
        this.progreso = 0;
        this.cargaCompleta = false;
        // Mensaje de contexto
        this.statusEl.classList.remove('fade');
        this.statusEl.textContent = 'Aplicando filtros...';
        // Ocultar contenido
        const wrapper = document.getElementById('dashboard-content');
        if (wrapper)
            wrapper.classList.remove('visible');
        if (this.plotlyMode) {
            // Barra oculta en plotlyMode — nada que resetear
            this.iniciarSincronizacionNumeroCss(); // no-op
        }
        else {
            this.actualizarBarra(0);
            this.simularProgreso();
        }
    }
}
// Inicializar referencia global a null hasta que se instancie
window.sigmaLoader = null;
//# sourceMappingURL=dashboard_loader.js.map