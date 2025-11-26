/**
 * Script para Fondo de Partículas Interactivas (Canvas)
 * Crea un efecto de constelación que reacciona al mouse.
 */

const canvas = document.getElementById('particles-canvas') as HTMLCanvasElement;
const ctx = canvas.getContext('2d');

let particlesArray: Particle[] = [];

// Ajustar tamaño del canvas
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

// Manejo del mouse
const mouse = {
    x: null as number | null,
    y: null as number | null,
    radius: 150 // Radio de interacción
}

window.addEventListener('mousemove', (event) => {
    mouse.x = event.x;
    mouse.y = event.y;
});

// Clase Partícula
class Particle {
    x: number;
    y: number;
    directionX: number;
    directionY: number;
    size: number;
    color: string;

    constructor() {
        this.size = Math.random() * 3 + 1; // Tamaño aleatorio (definido PRIMERO)
        this.x = Math.random() * (canvas.width - this.size * 2) + this.size * 2;
        this.y = Math.random() * (canvas.height - this.size * 2) + this.size * 2;
        this.directionX = (Math.random() * 2) - 1; // Velocidad aleatoria X
        this.directionY = (Math.random() * 2) - 1; // Velocidad aleatoria Y
        this.color = '#818cf8'; // Color base (indigo suave)
    }

    // Dibujar partícula
    draw() {
        if (!ctx) return;
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

        // Detección de colisión con mouse
        if (mouse.x !== null && mouse.y !== null) {
            let dx = mouse.x - this.x;
            let dy = mouse.y - this.y;
            let distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < mouse.radius + this.size) {
                if (mouse.x < this.x && this.x < canvas.width - this.size * 10) {
                    this.x += 3;
                }
                if (mouse.x > this.x && this.x > this.size * 10) {
                    this.x -= 3;
                }
                if (mouse.y < this.y && this.y < canvas.height - this.size * 10) {
                    this.y += 3;
                }
                if (mouse.y > this.y && this.y > this.size * 10) {
                    this.y -= 3;
                }
            }
        }

        // Mover partícula
        this.x += this.directionX;
        this.y += this.directionY;

        // Dibujar
        this.draw();
    }
}

// Inicializar arreglo de partículas
function init() {
    particlesArray = [];
    let numberOfParticles = (canvas.height * canvas.width) / 9000; // Densidad de partículas
    for (let i = 0; i < numberOfParticles; i++) {
        particlesArray.push(new Particle());
    }
}

// Animar
function animate() {
    requestAnimationFrame(animate);
    if (!ctx) return;
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
                if (!ctx) return;
                ctx.strokeStyle = 'rgba(129, 140, 248,' + opacityValue + ')';
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

// Reset mouse al salir
window.addEventListener('mouseout', () => {
    mouse.x = null;
    mouse.y = null;
})

init();
animate();

// Toggle Password (mantenido)
document.addEventListener('DOMContentLoaded', () => {
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
});
