"use strict";
/**
 * feedback_satisfaccion.ts
 * Lógica interactiva de la encuesta de satisfacción del cliente.
 * Maneja estrellas, NPS, progreso y confetti.
 * El sí/no de recomendación ya no se pregunta: Django lo deriva del NPS.
 *
 * One-Click Survey: si Django prellenó #id_calificacion_general (el cliente
 * tocó una estrella en el correo), pintamos esas estrellas al cargar.
 */
// ─── Etiquetas de estrellas ───────────────────────────────────────────────────
const STAR_LABELS = {
    1: 'Muy malo 😞',
    2: 'Malo 😕',
    3: 'Regular 😐',
    4: 'Bueno 🙂',
    5: '¡Excelente! 🤩',
};
// ─── Utilidades DOM ───────────────────────────────────────────────────────────
function getEl(id) {
    return document.getElementById(id);
}
function showError(id) {
    const el = document.getElementById(id);
    if (el)
        el.classList.add('visible');
}
function hideError(id) {
    const el = document.getElementById(id);
    if (el)
        el.classList.remove('visible');
}
// ─── Sistema de calificación con estrellas ────────────────────────────────────
function initStarGroup(containerId, inputId, labelId) {
    var _a, _b;
    const container = getEl(containerId);
    const hiddenInput = getEl(inputId);
    if (!container || !hiddenInput)
        return null;
    const stars = container.querySelectorAll('.fs-star');
    const label = labelId ? ((_a = getEl(labelId)) !== null && _a !== void 0 ? _a : undefined) : undefined;
    const group = { container, stars, hiddenInput, label, value: 0 };
    // EXPLICACIÓN PARA PRINCIPIANTES: el correo pone ?estrellas=N y Django
    // rellena el input hidden. Si ya hay un 1–5, pintamos esas estrellas.
    const initialVal = parseInt(hiddenInput.value.trim(), 10);
    if (initialVal >= 1 && initialVal <= 5) {
        group.value = initialVal;
        highlightStars(stars, initialVal);
        if (label) {
            label.textContent = (_b = STAR_LABELS[initialVal]) !== null && _b !== void 0 ? _b : '';
        }
    }
    stars.forEach((star) => {
        var _a;
        const val = parseInt((_a = star.dataset['value']) !== null && _a !== void 0 ? _a : '0', 10);
        // Hover
        star.addEventListener('mouseenter', () => {
            var _a;
            highlightStars(stars, val);
            if (label)
                label.textContent = (_a = STAR_LABELS[val]) !== null && _a !== void 0 ? _a : '';
        });
        star.addEventListener('mouseleave', () => {
            var _a;
            highlightStars(stars, group.value);
            if (label)
                label.textContent = group.value > 0 ? ((_a = STAR_LABELS[group.value]) !== null && _a !== void 0 ? _a : '') : 'Toca para calificar';
        });
        // Click
        star.addEventListener('click', () => {
            var _a;
            group.value = val;
            hiddenInput.value = String(val);
            highlightStars(stars, val);
            if (label)
                label.textContent = (_a = STAR_LABELS[val]) !== null && _a !== void 0 ? _a : '';
            updateProgress();
        });
    });
    return group;
}
function highlightStars(stars, upTo) {
    stars.forEach((star) => {
        var _a;
        const val = parseInt((_a = star.dataset['value']) !== null && _a !== void 0 ? _a : '0', 10);
        star.classList.toggle('active', val <= upTo);
    });
}
// ─── Sistema de mini-estrellas (calificaciones opcionales) ───────────────────
function initMiniStarGroup(groupName, inputId) {
    const container = document.querySelector(`[id="${groupName}Stars"]`);
    const hiddenInput = getEl(inputId);
    if (!container || !hiddenInput)
        return;
    const stars = container.querySelectorAll('.fs-mini-star');
    let currentValue = 0;
    stars.forEach((star) => {
        var _a;
        const val = parseInt((_a = star.dataset['value']) !== null && _a !== void 0 ? _a : '0', 10);
        star.addEventListener('mouseenter', () => highlightMiniStars(stars, val));
        star.addEventListener('mouseleave', () => highlightMiniStars(stars, currentValue));
        star.addEventListener('click', () => {
            currentValue = val;
            hiddenInput.value = String(val);
            highlightMiniStars(stars, val);
        });
    });
}
function highlightMiniStars(stars, upTo) {
    stars.forEach((star) => {
        var _a;
        const val = parseInt((_a = star.dataset['value']) !== null && _a !== void 0 ? _a : '0', 10);
        star.classList.toggle('active', val <= upTo);
    });
}
// ─── NPS Scale ───────────────────────────────────────────────────────────────
function initNPS() {
    const grid = getEl('npsGrid');
    const npsInput = getEl('id_nps');
    if (!grid || !npsInput)
        return;
    const buttons = grid.querySelectorAll('.fs-nps-btn');
    buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
            var _a;
            const val = (_a = btn.dataset['value']) !== null && _a !== void 0 ? _a : '';
            npsInput.value = val;
            buttons.forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            hideError('errorNps');
            updateProgress();
        });
    });
}
// ─── Toggle sección opcional ─────────────────────────────────────────────────
function initOptionalToggle() {
    const toggle = getEl('optionalToggle');
    const content = getEl('optionalContent');
    const wrapper = getEl('optionalWrapper');
    if (!toggle || !content || !wrapper)
        return;
    function doToggle() {
        const isOpen = content.classList.toggle('open');
        wrapper.classList.toggle('open', isOpen);
        toggle.setAttribute('aria-expanded', String(isOpen));
    }
    toggle.addEventListener('click', doToggle);
    toggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            doToggle();
        }
    });
}
// ─── Contador de caracteres para textarea ────────────────────────────────────
function initCharCounter() {
    const textarea = document.getElementById('id_comentario_satisfaccion');
    const counter = getEl('charCount');
    if (!textarea || !counter)
        return;
    textarea.addEventListener('input', () => {
        counter.textContent = String(textarea.value.length);
    });
}
// ─── Barra de progreso ────────────────────────────────────────────────────────
function updateProgress() {
    const fill = getEl('progressFill');
    const generalInput = getEl('id_calificacion_general');
    const npsInput = getEl('id_nps');
    if (!fill)
        return;
    // EXPLICACIÓN: solo hay 2 obligatorios (estrellas + NPS). El pulgar
    // ya no se pide: Django lo calcula del NPS al guardar.
    let filled = 0;
    if (generalInput && generalInput.value)
        filled++;
    if (npsInput && npsInput.value !== '')
        filled++;
    const pct = Math.round((filled / 2) * 100);
    fill.style.width = `${pct}%`;
}
// ─── Validación frontend ──────────────────────────────────────────────────────
function validateForm() {
    var _a, _b;
    let valid = true;
    const generalInput = getEl('id_calificacion_general');
    if (!(generalInput === null || generalInput === void 0 ? void 0 : generalInput.value)) {
        showError('errorGeneral');
        (_a = document.getElementById('section-estrellas')) === null || _a === void 0 ? void 0 : _a.scrollIntoView({ behavior: 'smooth', block: 'center' });
        valid = false;
    }
    else {
        hideError('errorGeneral');
    }
    const npsInput = getEl('id_nps');
    if (!(npsInput === null || npsInput === void 0 ? void 0 : npsInput.value) && (npsInput === null || npsInput === void 0 ? void 0 : npsInput.value) !== '0') {
        if (valid)
            (_b = document.getElementById('section-nps')) === null || _b === void 0 ? void 0 : _b.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showError('errorNps');
        valid = false;
    }
    else {
        hideError('errorNps');
    }
    return valid;
}
// ─── Confetti 🎉 ─────────────────────────────────────────────────────────────
function launchConfetti(config) {
    var _a;
    const wrapper = getEl('confettiWrapper');
    if (!wrapper)
        return;
    for (let i = 0; i < config.count; i++) {
        const piece = document.createElement('div');
        piece.className = 'fs-confetti-piece';
        piece.style.left = `${Math.random() * 100}%`;
        piece.style.animationDuration = `${1.5 + Math.random() * 2.5}s`;
        piece.style.animationDelay = `${Math.random() * 0.8}s`;
        piece.style.backgroundColor = (_a = config.colors[Math.floor(Math.random() * config.colors.length)]) !== null && _a !== void 0 ? _a : '#667eea';
        piece.style.transform = `rotate(${Math.random() * 360}deg)`;
        if (Math.random() > 0.5) {
            piece.style.borderRadius = '50%';
            piece.style.width = `${6 + Math.random() * 8}px`;
            piece.style.height = piece.style.width;
        }
        wrapper.appendChild(piece);
    }
}
// ─── Inicialización ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Estado "formulario"
    const form = document.getElementById('feedbackForm');
    if (form) {
        // Estrellas generales
        initStarGroup('generalStars', 'id_calificacion_general', 'generalStarLabel');
        // Mini-estrellas opcionales
        initMiniStarGroup('atencion', 'id_calificacion_atencion');
        initMiniStarGroup('tiempo', 'id_calificacion_tiempo');
        // NPS, toggle opcional, contador
        initNPS();
        initOptionalToggle();
        initCharCounter();
        // Validar al submit
        form.addEventListener('submit', (e) => {
            if (!validateForm()) {
                e.preventDefault();
                return;
            }
            // Deshabilitar botón para evitar doble-submit
            const btn = getEl('submitBtn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Enviando… ⏳';
            }
        });
        // Inicializar barra de progreso
        updateProgress();
    }
    // Estado "gracias" — lanzar confetti
    const confettiWrapper = getEl('confettiWrapper');
    if (confettiWrapper) {
        launchConfetti({
            count: 80,
            colors: ['#667eea', '#764ba2', '#fbbf24', '#10b981', '#f093fb', '#ef4444'],
        });
    }
});
//# sourceMappingURL=feedback_satisfaccion.js.map