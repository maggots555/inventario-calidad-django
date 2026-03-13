"use strict";
/**
 * Partículas interactivas para la encuesta de satisfacción.
 * Mismo efecto que el login pero con colores blancos semitransparentes
 * para ser visibles sobre el fondo degradado púrpura.
 */
(function () {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas)
        return;
    const ctx = canvas.getContext('2d');
    if (!ctx)
        return;
    let particlesArray = [];
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const mouse = {
        x: null,
        y: null,
        radius: 130
    };
    window.addEventListener('mousemove', (event) => {
        mouse.x = event.x;
        mouse.y = event.y;
    });
    window.addEventListener('mouseout', () => {
        mouse.x = null;
        mouse.y = null;
    });
    class FeedbackParticle {
        constructor() {
            this.size = Math.random() * 2.5 + 0.8;
            this.x = Math.random() * (canvas.width - this.size * 2) + this.size * 2;
            this.y = Math.random() * (canvas.height - this.size * 2) + this.size * 2;
            this.directionX = (Math.random() * 2) - 1;
            this.directionY = (Math.random() * 2) - 1;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.65)';
            ctx.fill();
        }
        update() {
            if (this.x > canvas.width || this.x < 0) {
                this.directionX = -this.directionX;
            }
            if (this.y > canvas.height || this.y < 0) {
                this.directionY = -this.directionY;
            }
            if (mouse.x !== null && mouse.y !== null) {
                const dx = mouse.x - this.x;
                const dy = mouse.y - this.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                if (distance < mouse.radius) {
                    const forceDirectionX = dx / distance;
                    const forceDirectionY = dy / distance;
                    const forceMagnitude = (mouse.radius - distance) / mouse.radius;
                    const force = forceMagnitude * 0.45;
                    this.directionX -= forceDirectionX * force;
                    this.directionY -= forceDirectionY * force;
                    const speed = Math.sqrt(this.directionX * this.directionX + this.directionY * this.directionY);
                    const maxSpeed = 3;
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
    function init() {
        particlesArray = [];
        const numberOfParticles = (canvas.height * canvas.width) / 9000;
        for (let i = 0; i < numberOfParticles; i++) {
            particlesArray.push(new FeedbackParticle());
        }
    }
    function connect() {
        for (let a = 0; a < particlesArray.length; a++) {
            for (let b = a; b < particlesArray.length; b++) {
                const distance = (particlesArray[a].x - particlesArray[b].x) ** 2 +
                    (particlesArray[a].y - particlesArray[b].y) ** 2;
                if (distance < (canvas.width / 7) * (canvas.height / 7)) {
                    const opacityValue = 1 - distance / 20000;
                    ctx.strokeStyle = `rgba(255, 255, 255, ${opacityValue * 0.35})`;
                    ctx.lineWidth = 0.8;
                    ctx.beginPath();
                    ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                    ctx.lineTo(particlesArray[b].x, particlesArray[b].y);
                    ctx.stroke();
                }
            }
        }
    }
    function animate() {
        requestAnimationFrame(animate);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < particlesArray.length; i++) {
            particlesArray[i].update();
        }
        connect();
    }
    window.addEventListener('resize', () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        init();
    });
    init();
    animate();
})();
//# sourceMappingURL=feedback_particles.js.map