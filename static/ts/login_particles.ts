/**
 * Login / logout: malla interactiva de fondo + UI de la tarjeta.
 *
 * Objetivo de negocio: mismo estilo visual que la encuesta de satisfacción
 * (rejilla con ola, cascada cyan y hover), sin perder tilt 3D ni helpers
 * del formulario de login.
 *
 * Efectos secundarios: dibuja en `#particles-canvas`; manipula DOM de
 * `.login-card-3d`, toggle de password y botón submit (solo si existen).
 */

// ═══════════════════════════════════════════════════════════════
// Malla interactiva (mismo efecto que feedback_particles.ts)
// ═══════════════════════════════════════════════════════════════

const canvas = document.getElementById('particles-canvas') as HTMLCanvasElement | null;
const ctx = canvas ? canvas.getContext('2d') : null;

if (canvas && ctx) {
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Cada punto tiene "casa" (homeX/homeY) y posición actual (x/y).
    // El cursor empuja; el resorte jala a la casa (más ola). Cascada = brillo.
    interface MeshPoint {
        homeX: number;
        homeY: number;
        x: number;
        y: number;
        vx: number;
        vy: number;
        col: number;
        row: number;
    }

    let points: MeshPoint[] = [];
    let cols = 0;
    let rows = 0;

    const mouse = {
        x: null as number | null,
        y: null as number | null,
        radius: 140
    };

    const SPRING = 0.06;
    const FRICTION = 0.82;
    const PUSH_STRENGTH = 2.8;
    const POINT_SIZE = 1.6;

    const WAVE_AMPLITUDE = 7.5;
    const WAVE_SPEED = 0.00085;
    const WAVE_FREQ_X = 0.32;
    const WAVE_FREQ_Y = 0.26;

    // Cascada de brillo (como encuesta / seguimiento)
    const CASCADE_PERIOD_MS = 9000;
    const CASCADE_BAND_PX = 140;
    const CASCADE_PAUSE = 0.12;

    /**
     * Espaciado de rejilla según viewport (móvil = menos denso).
     */
    function spacingForViewport(): number {
        const minSide = Math.min(window.innerWidth, window.innerHeight);
        if (minSide < 480) return 56;
        if (minSide < 900) return 52;
        return 48;
    }

    /**
     * Crea la rejilla centrada. Efecto: reemplaza `points` y cols/rows.
     */
    function initMesh(): void {
        const spacing = spacingForViewport();
        cols = Math.ceil(canvas!.width / spacing) + 1;
        rows = Math.ceil(canvas!.height / spacing) + 1;

        const offsetX = (canvas!.width - (cols - 1) * spacing) / 2;
        const offsetY = (canvas!.height - (rows - 1) * spacing) / 2;

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

    function waveOffset(p: MeshPoint, timeMs: number): { ox: number; oy: number } {
        const phase = timeMs * WAVE_SPEED + p.col * WAVE_FREQ_X + p.row * WAVE_FREQ_Y;
        const ox = Math.sin(phase) * WAVE_AMPLITUDE * 0.55;
        const oy = Math.sin(phase * 0.85 + 1.2) * WAVE_AMPLITUDE;
        return { ox, oy };
    }

    /**
     * Intensidad 0–1 de la franja de cascada que baja por la pantalla.
     */
    function cascadeGlow(y: number, timeMs: number): number {
        const h = canvas!.height;
        const t = (timeMs % CASCADE_PERIOD_MS) / CASCADE_PERIOD_MS;
        if (t < CASCADE_PAUSE) return 0;

        const travel = (t - CASCADE_PAUSE) / (1 - CASCADE_PAUSE);
        const bandCenter = travel * (h + CASCADE_BAND_PX * 2) - CASCADE_BAND_PX;
        const dist = Math.abs(y - bandCenter);
        if (dist >= CASCADE_BAND_PX) return 0;

        const falloff = 1 - dist / CASCADE_BAND_PX;
        return falloff * falloff;
    }

    function updatePoint(p: MeshPoint, timeMs: number): void {
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

    function drawMesh(timeMs: number): void {
        const glows = new Float32Array(points.length);
        for (let i = 0; i < points.length; i++) {
            glows[i] = cascadeGlow(points[i].y, timeMs);
        }

        ctx!.lineWidth = 0.85;

        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            const g = glows[i];

            if (p.col < cols - 1) {
                const right = points[i + 1];
                const lineGlow = Math.max(g, glows[i + 1]);
                const alpha = 0.22 + lineGlow * 0.55;
                ctx!.strokeStyle = lineGlow > 0.05
                    ? `rgba(125, 211, 252, ${alpha})`
                    : `rgba(255, 255, 255, ${alpha})`;
                ctx!.beginPath();
                ctx!.moveTo(p.x, p.y);
                ctx!.lineTo(right.x, right.y);
                ctx!.stroke();
            }

            if (p.row < rows - 1) {
                const below = points[i + cols];
                const lineGlow = Math.max(g, glows[i + cols]);
                const alpha = 0.22 + lineGlow * 0.55;
                ctx!.strokeStyle = lineGlow > 0.05
                    ? `rgba(125, 211, 252, ${alpha})`
                    : `rgba(255, 255, 255, ${alpha})`;
                ctx!.beginPath();
                ctx!.moveTo(p.x, p.y);
                ctx!.lineTo(below.x, below.y);
                ctx!.stroke();
            }

            const size = POINT_SIZE + g * 1.8;
            const alpha = 0.45 + g * 0.55;
            ctx!.fillStyle = g > 0.08
                ? `rgba(224, 242, 254, ${alpha})`
                : `rgba(255, 255, 255, ${alpha})`;
            ctx!.beginPath();
            ctx!.arc(p.x, p.y, size, 0, Math.PI * 2);
            ctx!.fill();

            if (g > 0.35) {
                ctx!.fillStyle = `rgba(56, 189, 248, ${g * 0.28})`;
                ctx!.beginPath();
                ctx!.arc(p.x, p.y, size * 2.4, 0, Math.PI * 2);
                ctx!.fill();
            }
        }
    }

    function animate(timeMs: number = 0): void {
        requestAnimationFrame(animate);
        ctx!.clearRect(0, 0, canvas!.width, canvas!.height);

        for (let i = 0; i < points.length; i++) {
            updatePoint(points[i], timeMs);
        }
        drawMesh(timeMs);
    }

    function resizeCanvas(): void {
        canvas!.width = window.innerWidth;
        canvas!.height = window.innerHeight;
        initMesh();
    }

    // EXPLICACIÓN PARA PRINCIPIANTES:
    // El canvas tiene pointer-events: none; escuchamos en window.
    window.addEventListener('mousemove', (event: MouseEvent) => {
        mouse.x = event.clientX;
        mouse.y = event.clientY;
    });

    window.addEventListener('mouseout', () => {
        mouse.x = null;
        mouse.y = null;
    });

    window.addEventListener('touchmove', (event: TouchEvent) => {
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
}

// ═══════════════════════════════════════════════════════════════
// DOMContentLoaded — lógica de UI (login; en logout no hay form)
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {

    // ── Toggle contraseña (ver/ocultar) ────────────────────────
    const toggleBtn = document.querySelector('.password-toggle-btn');
    const passwordInput = document.querySelector('input[name="password"]') as HTMLInputElement;

    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', () => {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);

            const icon = toggleBtn.querySelector('i');
            if (icon) {
                icon.classList.toggle('bi-eye-fill');
                icon.classList.toggle('bi-eye-slash-fill');
            }
        });
    }

    // ── Protección contra doble clic en submit ────────────────
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Si el usuario hace clic dos veces rápido, Django rota el token CSRF
    // después del primer envío y el segundo llega con token viejo → error 403.
    // Solución: deshabilitar el botón inmediatamente y mostrar spinner.
    // Si algo falla (error de red), lo re-habilitamos a los 10 segundos.
    const loginForm = document.querySelector<HTMLFormElement>('form[action]');
    const submitBtn = document.querySelector<HTMLButtonElement>('.btn-login-3d');

    if (loginForm && submitBtn) {
        loginForm.addEventListener('submit', () => {
            submitBtn.disabled = true;
            submitBtn.classList.add('btn-login-3d--loading');
            submitBtn.innerHTML = '<span class="btn-login-spinner"></span>Iniciando sesión...';

            setTimeout(() => {
                submitBtn.disabled = false;
                submitBtn.classList.remove('btn-login-3d--loading');
                submitBtn.innerHTML = 'Iniciar Sesión';
            }, 10000);
        });
    }

    // ── Efecto Tilt 3D en la tarjeta ──────────────────────────
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // El CSS define 'transform-style: preserve-3d' en .login-card-3d
    // pero necesita JavaScript para calcular cuánto rotar según donde
    // está el mouse relativo al centro de la tarjeta.
    // Resultado: la tarjeta se inclina suavemente siguiendo el cursor,
    // dando una sensación de profundidad y dimensión real.
    const card = document.querySelector<HTMLElement>('.login-card-3d');

    if (card) {
        const MAX_TILT = 8;

        document.addEventListener('mousemove', (e: MouseEvent) => {
            const rect = card.getBoundingClientRect();

            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const relX = (e.clientX - centerX) / (window.innerWidth / 2);
            const relY = (e.clientY - centerY) / (window.innerHeight / 2);

            const tiltX = Math.max(-1, Math.min(1, relY)) * MAX_TILT;
            const tiltY = Math.max(-1, Math.min(1, relX)) * -MAX_TILT;

            card.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
        });

        document.addEventListener('mouseleave', () => {
            card.style.transition = 'transform 0.5s cubic-bezier(0.22, 1, 0.36, 1)';
            card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';

            setTimeout(() => {
                card.style.transition = 'transform 0.08s ease-out, box-shadow 0.08s ease-out';
            }, 500);
        });

        // En touch: no hay tilt (evitar comportamiento raro en móvil)
    }
});
