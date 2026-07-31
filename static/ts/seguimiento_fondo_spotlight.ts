/**
 * seguimiento_fondo_spotlight.ts
 *
 * Objetivo: portal de seguimiento — halo CSS original + puntitos en canvas
 * con gravedad (empujón del mouse) y pulso lento. La cascada sigue en CSS.
 *
 * Cómo funciona (para principiantes):
 * 1. CSS ::before/::after = halo y brillo fijo cerca del cursor (como antes).
 * 2. Canvas dibuja los puntitos (rejilla 24px) para poder moverlos.
 * 3. El mouse empuja los puntos (gravedad) y este script actualiza --st-spot-*.
 *
 * Efectos: CSS vars + canvas; no toca BD ni red.
 * Accesibilidad: con prefers-reduced-motion no hay gravedad ni spotlight.
 */

const SPOT_ACTIVO = '1';
const GRID = 24;

interface FondoPoint {
    homeX: number;
    homeY: number;
    x: number;
    y: number;
    vx: number;
    vy: number;
    col: number;
    row: number;
}

/**
 * Actualiza las variables CSS del halo según el puntero.
 */
function actualizarSpotlight(
    fondo: HTMLElement,
    clientX: number,
    clientY: number
): void {
    fondo.style.setProperty('--st-spot-x', `${clientX}px`);
    fondo.style.setProperty('--st-spot-y', `${clientY}px`);
    fondo.dataset.activo = SPOT_ACTIVO;
}

function apagarSpotlight(fondo: HTMLElement): void {
    delete fondo.dataset.activo;
}

/**
 * ¿Tema oscuro en <html data-bs-theme="dark">?
 */
function esTemaOscuro(): boolean {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
}

/**
 * Inicializa spotlight CSS + malla canvas (gravedad + pulso).
 */
function inicializarFondoSpotlight(): void {
    const fondo = document.querySelector('.st-fondo-puntos') as HTMLElement | null;
    if (!fondo) {
        return;
    }

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reduceMotion.matches) {
        return;
    }

    const mouse = {
        x: null as number | null,
        y: null as number | null,
        radius: 220,
        spotlightRadius: 200
    };

    const onPointerMove = (evento: PointerEvent): void => {
        mouse.x = evento.clientX;
        mouse.y = evento.clientY;
        actualizarSpotlight(fondo, evento.clientX, evento.clientY);
    };

    const onPointerUp = (evento: PointerEvent): void => {
        if (evento.pointerType === 'touch' || evento.pointerType === 'pen') {
            mouse.x = null;
            mouse.y = null;
            apagarSpotlight(fondo);
        }
    };

    const onPointerLeave = (): void => {
        mouse.x = null;
        mouse.y = null;
        apagarSpotlight(fondo);
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerup', onPointerUp, { passive: true });
    window.addEventListener('pointercancel', onPointerUp, { passive: true });
    document.documentElement.addEventListener('mouseleave', onPointerLeave);

    // ── Canvas: puntitos con gravedad (solo puntos, sin líneas = mismo look) ──
    const canvas = document.getElementById('st-fondo-canvas') as HTMLCanvasElement | null;
    const ctx = canvas ? canvas.getContext('2d') : null;
    if (!canvas || !ctx) {
        return;
    }

    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Misma física del login, pero solo dibujamos círculos (la grilla de
    // seguimiento no tenía líneas entre nodos).
    let points: FondoPoint[] = [];

    const SPRING = 0.06;
    const FRICTION = 0.82;
    const PUSH_STRENGTH = 4.0;
    const POINT_SIZE = 1.15;
    const PULSE_SPEED = 0.0014;
    const PULSE_SIZE = 0.4;
    const PULSE_ALPHA = 0.18;

    function initGrid(): void {
        const w = canvas!.width;
        const h = canvas!.height;
        const cols = Math.ceil(w / GRID) + 1;
        const rows = Math.ceil(h / GRID) + 1;
        const offsetX = (w - (cols - 1) * GRID) / 2;
        const offsetY = (h - (rows - 1) * GRID) / 2;

        points = [];
        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                const homeX = offsetX + col * GRID;
                const homeY = offsetY + row * GRID;
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

    function resize(): void {
        canvas!.width = window.innerWidth;
        canvas!.height = window.innerHeight;
        initGrid();
    }

    function mouseGlow(p: FondoPoint): number {
        if (mouse.x === null || mouse.y === null) return 0;
        const dx = p.x - mouse.x;
        const dy = p.y - mouse.y;
        const r = mouse.spotlightRadius;
        const distSq = dx * dx + dy * dy;
        if (distSq >= r * r) return 0;
        const falloff = 1 - Math.sqrt(distSq) / r;
        return Math.min(1, Math.pow(falloff, 1.4) * 1.15);
    }

    function pulseFactor(p: FondoPoint, timeMs: number): number {
        const phase = timeMs * PULSE_SPEED + p.col * 0.35 + p.row * 0.28;
        return (Math.sin(phase) + 1) / 2;
    }

    function updatePoint(p: FondoPoint): void {
        // Gravedad / empujón lejos del cursor
        if (mouse.x !== null && mouse.y !== null) {
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const distSq = dx * dx + dy * dy;
            const radiusSq = mouse.radius * mouse.radius;
            if (distSq < radiusSq && distSq > 0.01) {
                const dist = Math.sqrt(distSq);
                const force = (1 - dist / mouse.radius) * PUSH_STRENGTH;
                p.vx += (dx / dist) * force;
                p.vy += (dy / dist) * force;
            }
        }

        p.vx += (p.homeX - p.x) * SPRING;
        p.vy += (p.homeY - p.y) * SPRING;
        p.vx *= FRICTION;
        p.vy *= FRICTION;
        p.x += p.vx;
        p.y += p.vy;
    }

    function drawPoints(timeMs: number): void {
        const dark = esTemaOscuro();
        // Colores alineados con el CSS original de la grilla
        const baseRgb = dark ? '148, 163, 184' : '186, 230, 253';
        const litRgb = dark ? '125, 211, 252' : '224, 242, 254';

        ctx!.clearRect(0, 0, canvas!.width, canvas!.height);

        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            updatePoint(p);

            const g = mouseGlow(p);
            const pulse = pulseFactor(p, timeMs);
            const size = POINT_SIZE + g * 1.4 + pulse * PULSE_SIZE;
            const baseAlpha = dark ? 0.18 : 0.28;
            const alpha = Math.min(1, baseAlpha + pulse * PULSE_ALPHA + g * 0.55);

            ctx!.fillStyle = g > 0.12
                ? `rgba(${litRgb}, ${alpha})`
                : `rgba(${baseRgb}, ${alpha})`;
            ctx!.beginPath();
            ctx!.arc(p.x, p.y, size, 0, Math.PI * 2);
            ctx!.fill();
        }
    }

    function animate(timeMs: number = 0): void {
        requestAnimationFrame(animate);
        drawPoints(timeMs);
    }

    window.addEventListener('resize', resize);
    resize();
    animate();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarFondoSpotlight);
} else {
    inicializarFondoSpotlight();
}
