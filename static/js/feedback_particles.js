"use strict";
/**
 * Malla interactiva para la encuesta de satisfacción.
 *
 * Objetivo de negocio: dar presencia visual al fondo azul SIC sin distraer
 * del formulario. La malla tiene ola sutil, cascada de brillo (como el portal
 * de seguimiento) y se deforma al pasar el cursor/dedo.
 *
 * Efectos secundarios: solo dibuja en el canvas `#particles-canvas`;
 * no toca DOM del formulario ni hace peticiones de red.
 */
(function () {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas)
        return;
    const ctx = canvas.getContext('2d');
    if (!ctx)
        return;
    let points = [];
    let cols = 0;
    let rows = 0;
    // Radio de influencia del cursor sobre la malla (en píxeles).
    const mouse = {
        x: null,
        y: null,
        radius: 140
    };
    // Constantes de física (ajustadas a ojo para un movimiento suave).
    const SPRING = 0.06; // Qué tan fuerte tira hacia home
    const FRICTION = 0.82; // Amortiguación (0–1; más bajo = más freno)
    const PUSH_STRENGTH = 2.8; // Fuerza del empujón del cursor
    const POINT_SIZE = 1.6;
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // La "ola" desplaza un poco la posición de casa de cada punto con senos.
    // El resorte sigue jalando hacia esa casa móvil; el cursor empuja encima.
    // Así hay movimiento continuo sutil + hover intacto.
    const WAVE_AMPLITUDE = 7.5; // píxeles de desplazamiento (un poco más pronunciado)
    const WAVE_SPEED = 0.00085; // qué tan rápido avanza la ola en el tiempo
    const WAVE_FREQ_X = 0.32; // frecuencia espacial por columna
    const WAVE_FREQ_Y = 0.26; // frecuencia espacial por fila
    // Cascada de brillo (inspirada en .st-fondo-cascada de seguimiento)
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Una franja horizontal baja por la pantalla. Los puntos cerca de esa
    // franja se iluminan en cyan; al alejarse vuelven a blanco tenue.
    const CASCADE_PERIOD_MS = 9000; // cuánto tarda un ciclo completo (ms)
    const CASCADE_BAND_PX = 140; // grosor de la franja iluminada
    const CASCADE_PAUSE = 0.12; // % del ciclo sin franja (pausa arriba)
    /**
     * Calcula el espaciado de la rejilla según el tamaño de pantalla.
     * Pantallas chicas → menos densas (mejor rendimiento en móvil).
     */
    function spacingForViewport() {
        const minSide = Math.min(window.innerWidth, window.innerHeight);
        if (minSide < 480)
            return 56;
        if (minSide < 900)
            return 52;
        return 48;
    }
    /**
     * Crea la rejilla de puntos centrada en el viewport.
     * Efecto secundario: reemplaza el array `points` y actualiza cols/rows.
     */
    function initMesh() {
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Dividimos el ancho/alto en celdas. Cada cruce de líneas es un punto.
        // Guardamos col/row para luego dibujar solo vecinos (derecha y abajo).
        const spacing = spacingForViewport();
        cols = Math.ceil(canvas.width / spacing) + 1;
        rows = Math.ceil(canvas.height / spacing) + 1;
        // Centramos un poco la malla para que no quede pegada a un borde.
        const offsetX = (canvas.width - (cols - 1) * spacing) / 2;
        const offsetY = (canvas.height - (rows - 1) * spacing) / 2;
        points = [];
        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                const homeX = offsetX + col * spacing;
                const homeY = offsetY + row * spacing;
                points.push({
                    homeX,
                    homeY,
                    x: homeX,
                    y: homeY,
                    vx: 0,
                    vy: 0,
                    col,
                    row
                });
            }
        }
    }
    /**
     * Calcula el desplazamiento de ola para un punto en el instante `timeMs`.
     * Devuelve offsets en X/Y que se suman a home (casa móvil).
     */
    function waveOffset(p, timeMs) {
        const phase = timeMs * WAVE_SPEED + p.col * WAVE_FREQ_X + p.row * WAVE_FREQ_Y;
        // Dos senos desfasados: la ola se siente más orgánica (no solo vertical).
        const ox = Math.sin(phase) * WAVE_AMPLITUDE * 0.55;
        const oy = Math.sin(phase * 0.85 + 1.2) * WAVE_AMPLITUDE;
        return { ox, oy };
    }
    /**
     * Intensidad de cascada (0–1) según la Y del punto y el tiempo.
     * 1 = justo en el centro de la franja que baja; 0 = fuera de la franja.
     */
    function cascadeGlow(y, timeMs) {
        const h = canvas.height;
        // Progreso 0→1 del ciclo; deja un pequeño “vacío” arriba entre pasadas.
        const t = (timeMs % CASCADE_PERIOD_MS) / CASCADE_PERIOD_MS;
        if (t < CASCADE_PAUSE)
            return 0;
        const travel = (t - CASCADE_PAUSE) / (1 - CASCADE_PAUSE);
        // Centro de la franja: de arriba (−band) hasta abajo (+band)
        const bandCenter = travel * (h + CASCADE_BAND_PX * 2) - CASCADE_BAND_PX;
        const dist = Math.abs(y - bandCenter);
        if (dist >= CASCADE_BAND_PX)
            return 0;
        // Caída suave: más brillante en el centro de la franja.
        const falloff = 1 - dist / CASCADE_BAND_PX;
        return falloff * falloff;
    }
    /**
     * Actualiza física: ola sutil + empujón del cursor + resorte a la casa móvil.
     *
     * @param p - Punto de la malla a actualizar
     * @param timeMs - Tiempo de animación en milisegundos (performance.now)
     */
    function updatePoint(p, timeMs) {
        // Empuje lejos del cursor si está cerca (se conserva igual que antes).
        if (mouse.x !== null && mouse.y !== null) {
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const distSq = dx * dx + dy * dy;
            const radiusSq = mouse.radius * mouse.radius;
            if (distSq < radiusSq && distSq > 0.01) {
                const dist = Math.sqrt(distSq);
                // Más cerca del cursor → más fuerza (0 en el borde, 1 en el centro).
                const force = (1 - dist / mouse.radius) * PUSH_STRENGTH;
                p.vx += (dx / dist) * force;
                p.vy += (dy / dist) * force;
            }
        }
        // Casa móvil = home fijo + ola. El resorte jala hacia ahí.
        const { ox, oy } = waveOffset(p, timeMs);
        const targetX = p.homeX + ox;
        const targetY = p.homeY + oy;
        p.vx += (targetX - p.x) * SPRING;
        p.vy += (targetY - p.y) * SPRING;
        p.vx *= FRICTION;
        p.vy *= FRICTION;
        p.x += p.vx;
        p.y += p.vy;
    }
    /**
     * Dibuja líneas a vecinos + puntos con brillo de cascada.
     * Así se ve una malla real (no un "spaghetti" de conexiones O(n²)).
     */
    function drawMesh(timeMs) {
        // Precalculamos glow por punto para reutilizarlo en líneas y nodos.
        const glows = new Float32Array(points.length);
        for (let i = 0; i < points.length; i++) {
            glows[i] = cascadeGlow(points[i].y, timeMs);
        }
        ctx.lineWidth = 0.85;
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            const g = glows[i];
            // Línea a la derecha (mismo row, col + 1)
            if (p.col < cols - 1) {
                const right = points[i + 1];
                const lineGlow = Math.max(g, glows[i + 1]);
                const alpha = 0.22 + lineGlow * 0.55;
                // Cyan SIC (#38bdf8) cuando brilla; blanco tenue en reposo.
                ctx.strokeStyle = lineGlow > 0.05
                    ? `rgba(125, 211, 252, ${alpha})`
                    : `rgba(255, 255, 255, ${alpha})`;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(right.x, right.y);
                ctx.stroke();
            }
            // Línea hacia abajo (row + 1, misma col)
            if (p.row < rows - 1) {
                const below = points[i + cols];
                const lineGlow = Math.max(g, glows[i + cols]);
                const alpha = 0.22 + lineGlow * 0.55;
                ctx.strokeStyle = lineGlow > 0.05
                    ? `rgba(125, 211, 252, ${alpha})`
                    : `rgba(255, 255, 255, ${alpha})`;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(below.x, below.y);
                ctx.stroke();
            }
            // Punto: más grande y cyan cuando la cascada lo toca.
            const size = POINT_SIZE + g * 1.8;
            const alpha = 0.45 + g * 0.55;
            ctx.fillStyle = g > 0.08
                ? `rgba(224, 242, 254, ${alpha})`
                : `rgba(255, 255, 255, ${alpha})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            ctx.fill();
            // Halo suave solo en el pico de la cascada (efecto “iluminado”).
            if (g > 0.35) {
                ctx.fillStyle = `rgba(56, 189, 248, ${g * 0.28})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, size * 2.4, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
    function animate(timeMs = 0) {
        requestAnimationFrame(animate);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < points.length; i++) {
            updatePoint(points[i], timeMs);
        }
        drawMesh(timeMs);
    }
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        initMesh();
    }
    // ── Eventos de cursor / touch ──────────────────────────────────
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // El canvas tiene pointer-events: none en CSS para no bloquear clics
    // del formulario. Por eso escuchamos en window, no en el canvas.
    window.addEventListener('mousemove', (event) => {
        mouse.x = event.clientX;
        mouse.y = event.clientY;
    });
    window.addEventListener('mouseout', () => {
        mouse.x = null;
        mouse.y = null;
    });
    // En móvil no hay mousemove: usamos el dedo.
    window.addEventListener('touchmove', (event) => {
        if (event.touches.length > 0) {
            mouse.x = event.touches[0].clientX;
            mouse.y = event.touches[0].clientY;
        }
    }, { passive: true });
    window.addEventListener('touchend', () => {
        mouse.x = null;
        mouse.y = null;
    });
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
    animate();
})();
//# sourceMappingURL=feedback_particles.js.map