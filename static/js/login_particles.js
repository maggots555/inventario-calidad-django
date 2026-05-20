"use strict";
/**
 * Script para Fondo de Partículas Interactivas (Canvas)
 * Crea un efecto de constelación que reacciona al mouse/touch.
 * + Efecto de tilt 3D en la tarjeta de login al mover el cursor.
 */
const canvas = document.getElementById('particles-canvas');
const ctx = canvas.getContext('2d');
let particlesArray = [];
// Ajustar tamaño del canvas
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
// Manejo del mouse (y touch)
const mouse = {
    x: null,
    y: null,
    radius: 150 // Radio de interacción con partículas
};
// Soporte mouse
window.addEventListener('mousemove', (event) => {
    mouse.x = event.clientX;
    mouse.y = event.clientY;
});
// ── Soporte touch (móvil) ──────────────────────────────────────
// EXPLICACIÓN PARA PRINCIPIANTES:
// En dispositivos táctiles no existe 'mousemove', solo 'touchmove'.
// Con esto las partículas reaccionan al dedo igual que al cursor.
window.addEventListener('touchmove', (event) => {
    // Tomamos el primer punto de contacto
    if (event.touches.length > 0) {
        mouse.x = event.touches[0].clientX;
        mouse.y = event.touches[0].clientY;
    }
}, { passive: true });
window.addEventListener('touchend', () => {
    mouse.x = null;
    mouse.y = null;
});
// Clase Partícula
class Particle {
    constructor() {
        this.size = Math.random() * 3 + 1; // Tamaño aleatorio (definido PRIMERO)
        this.x = Math.random() * (canvas.width - this.size * 2) + this.size * 2;
        this.y = Math.random() * (canvas.height - this.size * 2) + this.size * 2;
        this.directionX = (Math.random() * 2) - 1; // Velocidad aleatoria X
        this.directionY = (Math.random() * 2) - 1; // Velocidad aleatoria Y
        this.color = '#1897c9ff'; // Color base (azul sistema)
    }
    // Dibujar partícula
    draw() {
        if (!ctx)
            return;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
        ctx.fillStyle = this.color;
        ctx.fill();
    }
    // Actualizar posición y física
    update() {
        // Rebote en bordes
        if (this.x > canvas.width || this.x < 0) {
            this.directionX = -this.directionX;
        }
        if (this.y > canvas.height || this.y < 0) {
            this.directionY = -this.directionY;
        }
        // Sistema de repulsión suave basado en fuerzas
        if (mouse.x !== null && mouse.y !== null) {
            let dx = mouse.x - this.x;
            let dy = mouse.y - this.y;
            let distance = Math.sqrt(dx * dx + dy * dy);
            // Solo aplicar repulsión si está dentro del radio de interacción
            if (distance < mouse.radius) {
                let forceDirectionX = dx / distance;
                let forceDirectionY = dy / distance;
                // Fuerza de repulsión más suave cerca del radio
                let forceMagnitude = (mouse.radius - distance) / mouse.radius;
                let force = forceMagnitude * 0.5;
                this.directionX -= forceDirectionX * force;
                this.directionY -= forceDirectionY * force;
                // Limitar velocidad máxima
                let speed = Math.sqrt(this.directionX * this.directionX + this.directionY * this.directionY);
                let maxSpeed = 3;
                if (speed > maxSpeed) {
                    this.directionX = (this.directionX / speed) * maxSpeed;
                    this.directionY = (this.directionY / speed) * maxSpeed;
                }
            }
        }
        this.x += this.directionX;
        this.y += this.directionY;
        this.draw();
    }
}
// Inicializar arreglo de partículas
function init() {
    particlesArray = [];
    let numberOfParticles = (canvas.height * canvas.width) / 9000;
    for (let i = 0; i < numberOfParticles; i++) {
        particlesArray.push(new Particle());
    }
}
// Animar
function animate() {
    requestAnimationFrame(animate);
    if (!ctx)
        return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < particlesArray.length; i++) {
        particlesArray[i].update();
    }
    connect();
}
// Dibujar líneas entre partículas cercanas
function connect() {
    let opacityValue = 1;
    for (let a = 0; a < particlesArray.length; a++) {
        for (let b = a; b < particlesArray.length; b++) {
            let distance = ((particlesArray[a].x - particlesArray[b].x) * (particlesArray[a].x - particlesArray[b].x))
                + ((particlesArray[a].y - particlesArray[b].y) * (particlesArray[a].y - particlesArray[b].y));
            if (distance < (canvas.width / 7) * (canvas.height / 7)) {
                opacityValue = 1 - (distance / 20000);
                if (!ctx)
                    return;
                ctx.strokeStyle = 'rgb(50, 69, 89,' + opacityValue + ')';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                ctx.lineTo(particlesArray[b].x, particlesArray[b].y);
                ctx.stroke();
            }
        }
    }
}
// Redimensionar canvas
window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    init();
});
// Reset mouse al salir del viewport
window.addEventListener('mouseout', () => {
    mouse.x = null;
    mouse.y = null;
});
init();
animate();
// ═══════════════════════════════════════════════════════════════
// DOMContentLoaded — lógica de UI
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    // ── Toggle contraseña (ver/ocultar) ────────────────────────
    const toggleBtn = document.querySelector('.password-toggle-btn');
    const passwordInput = document.querySelector('input[name="password"]');
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
    const loginForm = document.querySelector('form[action]');
    const submitBtn = document.querySelector('.btn-login-3d');
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
    const card = document.querySelector('.login-card-3d');
    if (card) {
        // Intensidad máxima del tilt en grados
        const MAX_TILT = 8;
        document.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            // Posición del mouse relativa al centro de la tarjeta (valores -1 a 1)
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const relX = (e.clientX - centerX) / (window.innerWidth / 2);
            const relY = (e.clientY - centerY) / (window.innerHeight / 2);
            // Clampear para evitar rotaciones extremas fuera de la tarjeta
            const tiltX = Math.max(-1, Math.min(1, relY)) * MAX_TILT; // inclinación vertical
            const tiltY = Math.max(-1, Math.min(1, relX)) * -MAX_TILT; // inclinación horizontal
            card.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
        });
        // Restaurar posición al salir con transición suave
        document.addEventListener('mouseleave', () => {
            card.style.transition = 'transform 0.5s cubic-bezier(0.22, 1, 0.36, 1)';
            card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
            // Volver a la transición rápida para la siguiente interacción
            setTimeout(() => {
                card.style.transition = 'transform 0.08s ease-out, box-shadow 0.08s ease-out';
            }, 500);
        });
        // En touch: no hay tilt (evitar comportamiento raro en móvil)
        // El efecto es exclusivo para pointer devices
    }
});
//# sourceMappingURL=login_particles.js.map