"use strict";
/**
 * easter_egg_ganso.ts
 *
 * Objetivo de negocio:
 *   Easter egg de puro humor para el dashboard de inicio (home). Un ganso
 *   estilo "Untitled Goose Game" entra caminando por la barra superior, se
 *   lleva la foto del avatar del navbar, huye con un HONK y la devuelve.
 *   Sirve para dar personalidad al sistema sin cambiar ningún dato.
 *
 *   Funciona con mouse y con dedo: escritorio, celular, tablet y la PWA
 *   instalada. El truco manual son 5 clics o 5 toques en la cita del día.
 *
 * Efectos secundarios:
 *   - Inserta/quita un <div class="ganso-egg"> en <body> (temporal).
 *   - Añade/quita la clase .ganso-egg-robado en .navbar-user-avatar.
 *   - Lee/escribe localStorage clave 'sigma-ganso-robo-YYYY-MM-DD'.
 *   - Expone window.SigmaGansoEasterEgg para forzarlo desde la consola.
 *   - NO toca la base de datos: la foto de perfil (Empleado.foto_perfil)
 *     nunca se modifica; solo clonamos el <img> que ya está en la página.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *   Este archivo NO usa import/export porque el proyecto carga cada .js
 *   por separado con <script src="...">. Para que sus variables no choquen
 *   con las de otros archivos, todo vive dentro de una IIFE: una función
 *   que se declara y se ejecuta al instante, creando un ámbito privado.
 */
(function () {
    'use strict';
    // ========================================================================
    // CONFIGURACIÓN — cuándo aparece y cuánto dura cada tramo
    // ========================================================================
    /** Prefijo de localStorage; se le pega la fecha para limitar a 1 vez al día. */
    const PREFIJO_STORAGE = 'sigma-ganso-robo-';
    /** Probabilidad de que el ganso salga al abrir el home (12%). */
    const PROBABILIDAD_APARICION = 0.12;
    /** Clics (o toques) seguidos en la cita diaria que fuerzan la escena. */
    const CLICS_SECRETOS = 5;
    /** Máximo de milisegundos entre toque y toque para que cuenten como "seguidos". */
    const VENTANA_CLICS_MS = 2500;
    /** Espera inicial: dejamos que el usuario lea la cita antes del robo. */
    const MS_DEMORA_INICIAL = 2600;
    /** Duraciones de cada tramo de la coreografía (en milisegundos). */
    const MS_CAMINATA = 1900; // entra caminando hasta el avatar
    const MS_ROBO = 700; // se agacha y agarra la foto
    const MS_HONK = 850; // grita HONK antes de escapar
    const MS_HUIDA = 1000; // sale corriendo de la pantalla
    const MS_AUSENCIA = 2800; // el avatar se queda vacío
    const MS_REGRESO = 1400; // vuelve arrepentido
    const MS_DEVOLUCION = 700; // deja la foto en su lugar
    const MS_SALIDA = 900; // se va definitivamente
    /** Distancia horizontal desde donde arranca la caminata (px antes del avatar). */
    const PX_CARRERILLA = 420;
    /**
     * Ancho mínimo de pantalla para que valga la pena la escena.
     * Por debajo (relojes, ventanas diminutas) el ganso taparía la barra.
     */
    const ANCHO_MINIMO_PANTALLA = 300;
    /**
     * Proporción de la pantalla que como máximo usa la carrerilla.
     * EXPLICACIÓN PARA PRINCIPIANTES: en un celular de 375px no caben los
     * 420px de carrerilla del escritorio, así que la recortamos a un 60%
     * del ancho. El ganso entra desde el borde y se ve igual de natural.
     */
    const FRACCION_CARRERILLA_MOVIL = 0.6;
    /**
     * Dibujo del ganso mirando a la DERECHA (blanco, pico naranja, patas naranjas).
     * Mismo lenguaje visual que el cursor "Ganso" de Mi Perfil, pero más grande.
     * Las patas van en grupos separados para animarlas alternadas (paso a paso).
     *
     * No lleva width/height: el tamaño lo decide el CSS (más chico en celular)
     * y el viewBox se encarga de escalar el dibujo sin deformarlo.
     */
    const SVG_GANSO = `
<svg viewBox="0 0 84 78" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="gansoEggSombra" x="-30%" y="-30%" width="180%" height="180%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="1.4"/>
      <feOffset dx="1.5" dy="2.5" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#gansoEggSombra)">
    <g class="ganso-egg__pata ganso-egg__pata--a">
      <path d="M28 60 L27 70" stroke="#f97316" stroke-width="3" stroke-linecap="round"/>
      <path d="M27 70 L22 74 M27 70 L27 75 M27 70 L32 74" stroke="#f97316" stroke-width="2.2" stroke-linecap="round"/>
    </g>
    <g class="ganso-egg__pata ganso-egg__pata--b">
      <path d="M42 61 L41 70" stroke="#ea580c" stroke-width="3" stroke-linecap="round"/>
      <path d="M41 70 L36 74 M41 70 L41 75 M41 70 L46 74" stroke="#ea580c" stroke-width="2.2" stroke-linecap="round"/>
    </g>
    <path d="M11 40 C4 35 1 42 5 47 C8 45 10 42 11 40 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.2" stroke-linejoin="round"/>
    <ellipse cx="33" cy="46" rx="25" ry="18" fill="#f8fafc" stroke="#64748b" stroke-width="2"/>
    <path d="M19 44 C25 37 37 37 47 43 C37 49 25 49 19 44 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.2" stroke-linejoin="round"/>
    <path d="M45 41 C49 33 52 23 54 16 L61 18 C59 26 55 36 51 43 Z" fill="#f8fafc" stroke="#64748b" stroke-width="2" stroke-linejoin="round"/>
    <circle cx="59" cy="14" r="8.5" fill="#f8fafc" stroke="#64748b" stroke-width="2"/>
    <circle cx="62.5" cy="11.5" r="2" fill="#1e293b"/>
    <circle cx="63.2" cy="10.8" r="0.65" fill="#ffffff"/>
    <path d="M66.5 15.5 L80 12 L66.5 8" fill="#f97316" stroke="#c2410c" stroke-width="1.4" stroke-linejoin="round"/>
  </g>
</svg>`.trim();
    // ========================================================================
    // ESTADO INTERNO
    // ========================================================================
    /** Evita que dos escenas corran encimadas (ej. clic secreto durante el azar). */
    let escenaActiva = false;
    /** Se pone en true si hay que abortar (usuario cambió de pestaña). */
    let cancelado = false;
    // ========================================================================
    // HELPERS BÁSICOS
    // ========================================================================
    /**
     * Pausa la ejecución sin bloquear el navegador.
     *
     * Args:
     *   ms: milisegundos a esperar.
     * Efectos secundarios: ninguno (solo un setTimeout interno).
     */
    function esperar(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }
    /**
     * Clave de localStorage con la fecha de hoy (así el límite es diario).
     *
     * Returns: 'sigma-ganso-robo-2026-08-21'
     */
    function claveHoy() {
        const hoy = new Date();
        const mes = String(hoy.getMonth() + 1).padStart(2, '0');
        const dia = String(hoy.getDate()).padStart(2, '0');
        return `${PREFIJO_STORAGE}${hoy.getFullYear()}-${mes}-${dia}`;
    }
    /** ¿El ganso ya hizo su travesura hoy en este navegador? */
    function yaCorrioHoy() {
        try {
            return localStorage.getItem(claveHoy()) === '1';
        }
        catch {
            // Modo privado estricto puede bloquear localStorage: preferimos no repetir
            return true;
        }
    }
    /** Marca la travesura del día como hecha (silencioso si falla). */
    function marcarCorridoHoy() {
        try {
            localStorage.setItem(claveHoy(), '1');
        }
        catch {
            // Sin localStorage el easter egg podría repetirse; no es grave
        }
    }
    /** Elemento del avatar en el navbar (dueño de la foto que el ganso "roba"). */
    function obtenerAvatar() {
        return document.querySelector('.navbar-user-avatar');
    }
    /**
     * ¿Este dispositivo/navegador puede correr la escena?
     *
     * Funciona igual con mouse y con dedo (celular, tablet y la PWA
     * instalada): en móvil el nombre del usuario se oculta, pero el avatar
     * sigue en la barra, así que el ganso tiene qué robar.
     *
     * Solo se descarta si: el usuario pidió menos movimiento, la pantalla es
     * tan angosta que el ganso taparía media barra, o no hay avatar
     * (visitante sin sesión).
     */
    function puedeCorrer() {
        // Paso 1: respetar la preferencia de accesibilidad del sistema
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return false;
        }
        // Paso 2: por debajo de esto no queda espacio para el recorrido
        if (window.innerWidth < ANCHO_MINIMO_PANTALLA) {
            return false;
        }
        // Paso 3: sin avatar (visitante anónimo) no hay nada que robar
        return obtenerAvatar() !== null;
    }
    // ========================================================================
    // CONSTRUCCIÓN Y MOVIMIENTO DEL GANSO
    // ========================================================================
    /**
     * Crea el ganso (SVG + globito HONK + hueco para el botín) y lo mete al DOM.
     *
     * Efectos secundarios: agrega un div a document.body.
     * Returns: el contenedor recién creado.
     */
    function crearGanso() {
        const contenedor = document.createElement('div');
        contenedor.className = 'ganso-egg';
        contenedor.setAttribute('aria-hidden', 'true');
        // El flip voltea solo el dibujo; el botín es hermano para no salir espejado
        contenedor.innerHTML = `
            <div class="ganso-egg__flip">
                <div class="ganso-egg__cuerpo">${SVG_GANSO}</div>
            </div>
            <div class="ganso-egg__botin" aria-hidden="true"></div>
            <span class="ganso-egg__honk">HONK!</span>
        `;
        document.body.appendChild(contenedor);
        return contenedor;
    }
    /**
     * Teletransporta al ganso (sin animación) para arrancar un tramo nuevo.
     *
     * Efectos secundarios: escribe el transform inline y actualiza actor.x/y.
     */
    function ubicar(actor, x, y) {
        actor.x = Math.round(x);
        actor.y = Math.round(y);
        actor.el.style.transform = `translate3d(${actor.x}px, ${actor.y}px, 0)`;
    }
    /**
     * Camina/corre hasta un punto y espera a que el tramo termine de verse.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Usamos la Web Animations API (el.animate) en lugar de una transición
     * CSS. La diferencia importa: animate() declara el punto de salida y el
     * de llegada juntos, y nos devuelve una promesa que se cumple cuando el
     * navegador REALMENTE terminó de dibujar el recorrido. Así la historia
     * (robar, gritar, huir) va al ritmo de lo que el usuario ve y no de un
     * cronómetro a ciegas.
     *
     * El transform inline se escribe ANTES de animar: es el estado final
     * "de verdad", así que al acabar la animación no hay ningún salto.
     *
     * Args: actor; x, y destino; ms duración; easing curva de velocidad.
     * Efectos secundarios: mueve el elemento y actualiza actor.x/y.
     */
    async function caminarHasta(actor, x, y, ms, easing) {
        const desde = `translate3d(${actor.x}px, ${actor.y}px, 0)`;
        ubicar(actor, x, y);
        const hasta = `translate3d(${actor.x}px, ${actor.y}px, 0)`;
        // Navegador muy viejo sin Web Animations: aparece ya en su destino
        if (typeof actor.el.animate !== 'function') {
            await esperar(ms);
            return;
        }
        const animacion = actor.el.animate([{ transform: desde }, { transform: hasta }], { duration: ms, easing: easing });
        // Red de seguridad: si el navegador congela la animación (pestaña en
        // segundo plano), el margen extra evita que la escena quede colgada
        // con el avatar vacío.
        await Promise.race([
            animacion.finished.then(() => undefined).catch(() => undefined),
            esperar(ms + 400),
        ]);
        // Mientras una animación vive, su transform PISA al estilo inline.
        // Si quedó congelada a medio camino, el ganso se vería clavado en el
        // punto de salida el resto de la escena. Al cancelarla, vuelve a
        // mandar el inline, que ya apunta al destino de este tramo.
        if (animacion.playState !== 'finished') {
            animacion.cancel();
        }
    }
    /**
     * Calcula dónde debe pararse el ganso para que su pico toque el avatar.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * En el dibujo, el pico está en el punto (80, 12) de un lienzo de 84x78.
     * Como en celular el ganso se dibuja más chico, no podemos restar "80px"
     * a secas: usamos la PROPORCIÓN sobre el tamaño real que tiene ahora.
     * Así el pico cae en el centro del avatar en cualquier pantalla.
     *
     * Args: ganso, el contenedor ya insertado en el DOM (necesita medirse).
     * Returns: {x, y} en coordenadas de viewport, o null si no hay avatar.
     */
    function posicionJuntoAlAvatar(ganso) {
        const avatar = obtenerAvatar();
        if (!avatar) {
            return null;
        }
        const caja = avatar.getBoundingClientRect();
        const anchoGanso = ganso.offsetWidth || 84;
        const altoGanso = ganso.offsetHeight || 78;
        const picoX = anchoGanso * (80 / 84);
        const picoY = altoGanso * (12 / 78);
        return {
            x: caja.left + caja.width / 2 - picoX,
            y: caja.top + caja.height / 2 - picoY,
        };
    }
    /**
     * Punto de entrada del ganso: lo más lejos que convenga por la izquierda.
     *
     * Args: ganso; destinoX, la x donde acabará parado.
     * Returns: x inicial, nunca más lejos de lo que hace falta para entrar
     *          justo fuera del borde izquierdo.
     */
    function xDeEntrada(ganso, destinoX) {
        const carrerilla = Math.min(PX_CARRERILLA, Math.round(window.innerWidth * FRACCION_CARRERILLA_MOVIL));
        const fueraPorLaIzquierda = -(ganso.offsetWidth + 40);
        return Math.max(fueraPorLaIzquierda, destinoX - carrerilla);
    }
    /** x fuera de cuadro por la derecha (para la huida con el botín). */
    function xDeHuida(ganso) {
        return window.innerWidth + ganso.offsetWidth + 40;
    }
    // ========================================================================
    // EL ROBO (puro DOM: clonamos lo que ya se ve en pantalla)
    // ========================================================================
    /**
     * Pasa la foto (o las iniciales) del avatar al pico del ganso.
     *
     * Args:
     *   botin: div del ganso donde se cuelga el clon.
     * Efectos secundarios:
     *   - Clona el <img>/<span> visible del avatar dentro del botín.
     *   - Marca el avatar con .ganso-egg-robado (CSS lo deja como hueco vacío).
     * Returns: true si logró robar algo.
     */
    function robarAvatar(botin) {
        const avatar = obtenerAvatar();
        if (!avatar) {
            return false;
        }
        // El avatar es un <a> que contiene una foto (<img>) o las iniciales (<span>)
        const contenidoVisible = avatar.querySelector('img, span');
        if (!contenidoVisible) {
            return false;
        }
        // Clonamos: el original sigue en su sitio, solo lo escondemos con CSS
        botin.appendChild(contenidoVisible.cloneNode(true));
        botin.classList.add('ganso-egg__botin--lleno');
        avatar.classList.add('ganso-egg-robado');
        return true;
    }
    /**
     * Devuelve todo a la normalidad. Es idempotente: se puede llamar varias veces.
     *
     * Args:
     *   contenedor: el ganso a retirar del DOM (o null si nunca se creó).
     * Efectos secundarios: quita la clase del avatar y borra el div del ganso.
     */
    function restaurarTodo(contenedor) {
        const avatar = obtenerAvatar();
        if (avatar) {
            avatar.classList.remove('ganso-egg-robado');
        }
        if (contenedor && contenedor.parentNode) {
            contenedor.parentNode.removeChild(contenedor);
        }
    }
    // ========================================================================
    // COREOGRAFÍA COMPLETA
    // ========================================================================
    /**
     * Corre la escena entera: entra, roba, huye, vuelve y devuelve.
     *
     * Args:
     *   consumirDelDia: true cuando la escena viene del azar; marca el cupo
     *                   diario SOLO si de verdad arrancó (así una pestaña en
     *                   segundo plano no desperdicia la sorpresa del día).
     * Efectos secundarios: DOM (ganso + clase en avatar) y localStorage.
     *   El bloque finally garantiza que el avatar NUNCA se quede vacío,
     *   incluso si algo falla a medio camino.
     */
    async function correrEscena(consumirDelDia) {
        // Si la pestaña está en segundo plano, el navegador congela las
        // transiciones pero NO los temporizadores: la escena "pasaría" sin
        // que nadie la vea. Mejor no gastarla y dejarla para otro día.
        if (escenaActiva || document.hidden || !puedeCorrer()) {
            return;
        }
        escenaActiva = true;
        cancelado = false;
        if (consumirDelDia) {
            marcarCorridoHoy();
        }
        const contenedor = crearGanso();
        const botin = contenedor.querySelector('.ganso-egg__botin');
        const honk = contenedor.querySelector('.ganso-egg__honk');
        const actor = { el: contenedor, x: 0, y: 0 };
        try {
            // ── Tramo 1: entra caminando desde la izquierda ──────────────────
            const destino = posicionJuntoAlAvatar(contenedor);
            if (!destino || !botin || !honk) {
                return;
            }
            // Arranca fuera de cuadro (o lo más lejos que quepa) y camina hacia el avatar
            ubicar(actor, xDeEntrada(contenedor, destino.x), destino.y);
            contenedor.classList.add('ganso-egg--caminando');
            await caminarHasta(actor, destino.x, destino.y, MS_CAMINATA, 'linear');
            if (cancelado) {
                return;
            }
            // ── Tramo 2: se detiene y agarra la foto ─────────────────────────
            contenedor.classList.remove('ganso-egg--caminando');
            contenedor.classList.add('ganso-egg--robando');
            await esperar(MS_ROBO);
            if (cancelado) {
                return;
            }
            if (!robarAvatar(botin)) {
                return; // sin foto ni iniciales no hay chiste
            }
            // ── Tramo 3: HONK triunfal ──────────────────────────────────────
            contenedor.classList.remove('ganso-egg--robando');
            honk.classList.add('ganso-egg__honk--visible');
            await esperar(MS_HONK);
            if (cancelado) {
                return;
            }
            honk.classList.remove('ganso-egg__honk--visible');
            // ── Tramo 4: huye por la derecha con el botín ────────────────────
            contenedor.classList.add('ganso-egg--corriendo');
            await caminarHasta(actor, xDeHuida(contenedor), destino.y, MS_HUIDA, 'ease-in');
            if (cancelado) {
                return;
            }
            contenedor.classList.remove('ganso-egg--corriendo');
            // El avatar se queda como hueco punteado unos segundos
            await esperar(MS_AUSENCIA);
            if (cancelado) {
                return;
            }
            // ── Tramo 5: vuelve arrepentido, de nuevo desde la izquierda ────
            // Recalculamos la posición: el usuario pudo hacer scroll o resize
            const regreso = posicionJuntoAlAvatar(contenedor);
            if (!regreso) {
                return;
            }
            // OJO: el avatar vive pegado al borde derecho de la pantalla. Si el
            // ganso volviera "de frente" (espejado), su cuerpo caería fuera del
            // viewport y se vería cortado. Por eso reaparece por la izquierda,
            // igual que en la entrada, y así siempre queda dentro de cuadro.
            ubicar(actor, xDeEntrada(contenedor, regreso.x), regreso.y);
            contenedor.classList.add('ganso-egg--caminando');
            await caminarHasta(actor, regreso.x, regreso.y, MS_REGRESO, 'ease-out');
            if (cancelado) {
                return;
            }
            // ── Tramo 6: deja la foto en su lugar ───────────────────────────
            contenedor.classList.remove('ganso-egg--caminando');
            contenedor.classList.add('ganso-egg--robando');
            await esperar(MS_DEVOLUCION);
            if (cancelado) {
                return;
            }
            botin.classList.remove('ganso-egg__botin--lleno');
            botin.innerHTML = '';
            const avatar = obtenerAvatar();
            if (avatar) {
                avatar.classList.remove('ganso-egg-robado');
                // Pequeño "pop" de bienvenida al recuperar la foto
                avatar.classList.add('ganso-egg-devuelto');
                window.setTimeout(() => avatar.classList.remove('ganso-egg-devuelto'), 700);
            }
            // ── Tramo 7: da media vuelta y se va como si nada ───────────────
            // Aquí sí espejamos el dibujo: se aleja del borde derecho, así que
            // el cuerpo queda dentro de la pantalla mientras camina de salida.
            contenedor.classList.remove('ganso-egg--robando');
            contenedor.classList.add('ganso-egg--mirando-izq');
            contenedor.classList.add('ganso-egg--corriendo');
            await caminarHasta(actor, -(contenedor.offsetWidth + 120), regreso.y, MS_SALIDA, 'ease-in');
        }
        finally {
            // Red de seguridad: pase lo que pase, el avatar vuelve a la normalidad
            restaurarTodo(contenedor);
            escenaActiva = false;
        }
    }
    /**
     * Lanza la escena de forma segura (nunca rompe la página si algo falla).
     *
     * Args:
     *   forzado: true cuando viene del truco de los 5 clics; en ese caso no
     *            se consume ni se respeta el límite de una vez al día.
     */
    function ejecutar(forzado) {
        // El .catch evita un "unhandled promise rejection" en consola
        correrEscena(!forzado).catch(() => {
            /* el finally de correrEscena ya restauró el avatar */
        });
    }
    // ========================================================================
    // DISPARADORES
    // ========================================================================
    /**
     * Cuenta clics (o toques) seguidos en la cita diaria para forzar la escena.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * El evento 'click' también lo disparan los navegadores móviles al tocar
     * la pantalla, así que este mismo código sirve para mouse y para dedo.
     * El CSS añade touch-action: manipulation a la cita para que los toques
     * rápidos no se interpreten como "doble toque para acercar".
     *
     * Efectos secundarios: registra un listener en .cita-diaria.
     */
    function activarTrucoDeClics() {
        const cita = document.querySelector('.cita-diaria');
        if (!cita) {
            return;
        }
        let clics = 0;
        let ultimoClic = 0;
        cita.addEventListener('click', () => {
            const ahora = Date.now();
            // Si pasó mucho tiempo desde el clic previo, la cuenta arranca de nuevo
            clics = ahora - ultimoClic > VENTANA_CLICS_MS ? 1 : clics + 1;
            ultimoClic = ahora;
            if (clics >= CLICS_SECRETOS) {
                clics = 0;
                ejecutar(true);
            }
        });
    }
    /**
     * Si el usuario se va a otra pestaña, abortamos y devolvemos la foto ya.
     * Así nadie vuelve y encuentra su avatar vacío sin explicación.
     */
    function activarCancelacionPorPestana() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && escenaActiva) {
                cancelado = true;
            }
        });
    }
    /** Arranque: tira el dado, prepara el truco manual y expone la API de debug. */
    function inicializar() {
        activarTrucoDeClics();
        activarCancelacionPorPestana();
        window.SigmaGansoEasterEgg = {
            ejecutar: () => ejecutar(true),
            puedeCorrer,
        };
        // Azar + límite diario: la sorpresa debe ser rara, no una molestia
        if (!puedeCorrer() || yaCorrioHoy()) {
            return;
        }
        if (Math.random() > PROBABILIDAD_APARICION) {
            return;
        }
        window.setTimeout(() => ejecutar(false), MS_DEMORA_INICIAL);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inicializar);
    }
    else {
        inicializar();
    }
})();
//# sourceMappingURL=easter_egg_ganso.js.map