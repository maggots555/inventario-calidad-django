/**
 * concentrado_semanal.ts
 * ======================
 * Lógica TypeScript para la página "Concentrado Semanal CIS".
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo controla todos los comportamientos interactivos de la página:
 *   1. Custom Week Picker: calendario personalizado que reemplaza <input type="week">
 *   2. Auto-envío del formulario al cambiar la sucursal
 *   3. Navegación con teclado (flecha izq/der = semana anterior/siguiente)
 *   4. Loading state en los botones ← Semana anterior / Semana siguiente →
 *   5. Botón flotante "Volver arriba" que aparece al hacer scroll
 *
 * IMPORTANTE: Este es el archivo fuente (.ts). No editar el .js generado.
 * Para compilar: npm run build
 */

// =============================================================================
// TIPOS E INTERFACES
// =============================================================================

/**
 * Representa una semana ISO (año + número de semana).
 * Ejemplo: { año: 2025, semana: 18, isoString: "2025-W18" }
 */
interface SemanaISO {
  año: number;
  semana: number;
  isoString: string;
}

/**
 * Representa un día en el calendario del picker.
 */
interface DiaPicker {
  fecha: Date;
  /** true si el día pertenece al mes que se está mostrando */
  esMesActual: boolean;
  /** true si es sábado o domingo */
  esFinDeSemana: boolean;
}

// =============================================================================
// UTILIDADES DE FECHA / ISO WEEK
// =============================================================================

/**
 * Obtiene el número de semana ISO 8601 para una fecha dada.
 *
 * EXPLICACIÓN:
 * El estándar ISO 8601 define que la semana comienza el lunes y la primera
 * semana del año es la que contiene el primer jueves.
 * Esto puede hacer que el 1 de enero sea semana 52 del año anterior.
 *
 * @param fecha - Fecha de referencia
 * @returns Objeto con año ISO, número de semana e isoString
 */
function obtenerSemanaISO(fecha: Date): SemanaISO {
  // Copiamos la fecha para no mutar el original
  const d = new Date(Date.UTC(fecha.getFullYear(), fecha.getMonth(), fecha.getDate()));
  // Ajustamos al jueves de la misma semana para obtener el año ISO correcto
  const diaSemana = d.getUTCDay() || 7; // 0 (dom) → 7
  d.setUTCDate(d.getUTCDate() + 4 - diaSemana);
  const añoISO = d.getUTCFullYear();
  // Primer día del año ISO
  const primerDiaAño = new Date(Date.UTC(añoISO, 0, 1));
  // Número de semana
  const semana = Math.ceil((((d.getTime() - primerDiaAño.getTime()) / 86400000) + 1) / 7);
  return {
    año: añoISO,
    semana,
    isoString: `${añoISO}-W${String(semana).padStart(2, '0')}`,
  };
}

/**
 * Obtiene el lunes (primer día) de una semana ISO dada.
 *
 * @param año - Año ISO
 * @param semana - Número de semana ISO
 * @returns Date del lunes de esa semana
 */
function lunesDeSemanaISO(año: number, semana: number): Date {
  // El 4 de enero siempre está en la semana 1
  const cuatroEnero = new Date(año, 0, 4);
  const diaSemana = cuatroEnero.getDay() || 7;
  const lunes = new Date(cuatroEnero);
  lunes.setDate(cuatroEnero.getDate() - (diaSemana - 1) + (semana - 1) * 7);
  return lunes;
}

/**
 * Parsea un string ISO de semana ("2025-W18") a objeto SemanaISO.
 *
 * @param isoString - String en formato "YYYY-Www"
 * @returns SemanaISO o null si el formato es inválido
 */
function parsearSemanaISO(isoString: string): SemanaISO | null {
  const match = /^(\d{4})-W(\d{2})$/.exec(isoString);
  if (!match) return null;
  return {
    año: parseInt(match[1], 10),
    semana: parseInt(match[2], 10),
    isoString,
  };
}

/**
 * Formatea una fecha como "28 Abr" o "28 Abr 2025".
 *
 * @param fecha - Fecha a formatear
 * @param conAño - Si incluir el año
 * @returns String formateado en español
 */
function formatearFecha(fecha: Date, conAño = false): string {
  const meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  const dia = fecha.getDate();
  const mes = meses[fecha.getMonth()];
  if (conAño) {
    return `${dia} ${mes} ${fecha.getFullYear()}`;
  }
  return `${dia} ${mes}`;
}

/**
 * Formatea un mes y año como "Abril 2025".
 *
 * @param año - Año
 * @param mes - Índice de mes (0 = enero)
 * @returns String del mes en español
 */
function formatearMesAño(año: number, mes: number): string {
  const meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  return `${meses[mes]} ${año}`;
}

/**
 * Genera la etiqueta legible para una semana.
 * Ejemplo: "Semana 18 — 28 Abr al 2 May 2025"
 *
 * @param semanaISO - Objeto de semana
 * @returns String descriptivo
 */
function etiquetaSemana(semanaISO: SemanaISO): string {
  const lunes = lunesDeSemanaISO(semanaISO.año, semanaISO.semana);
  const viernes = new Date(lunes);
  viernes.setDate(lunes.getDate() + 4);
  return `Semana ${semanaISO.semana} — ${formatearFecha(lunes)} al ${formatearFecha(viernes, true)}`;
}

/**
 * Compara si dos fechas son el mismo día.
 */
function mismoMes(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}

// =============================================================================
// CLASE: CUSTOM WEEK PICKER
// =============================================================================

/**
 * WeekPicker — selector de semana personalizado.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta clase maneja todo el comportamiento del calendario desplegable:
 *
 * - Muestra un botón con el nombre de la semana actual
 * - Al hacer clic, abre un dropdown con un calendario mensual
 * - El usuario puede hacer clic en cualquier fila (semana completa) para seleccionarla
 * - Puede navegar meses con las flechas < y >
 * - Tiene botón "Semana actual" para volver a hoy rápidamente
 * - Al seleccionar una semana, actualiza el input oculto y envía el formulario
 */
class WeekPicker {
  private trigger: HTMLButtonElement;
  private hiddenInput: HTMLInputElement;
  private dropdown: HTMLDivElement;
  private mesLabel: HTMLSpanElement;
  private grid: HTMLDivElement;
  private form: HTMLFormElement;

  /** Semana actualmente seleccionada */
  private semanaActual: SemanaISO;
  /** Mes/año que se está mostrando en el calendario */
  private mesMostrado: Date;

  constructor() {
    // Obtenemos referencias a los elementos del DOM
    this.trigger  = document.getElementById('weekPickerTrigger') as HTMLButtonElement;
    this.hiddenInput = document.getElementById('semana') as HTMLInputElement;
    this.dropdown = document.getElementById('weekPickerDropdown') as HTMLDivElement;
    this.mesLabel = document.getElementById('wpMesLabel') as HTMLSpanElement;
    this.grid     = document.getElementById('wpGrid') as HTMLDivElement;
    this.form     = document.getElementById('formConcentrado') as HTMLFormElement;

    // SOLUCIÓN AL BUG DE RECORTE:
    // Movemos el dropdown al <body> para que no quede atrapado dentro del card
    // con overflow implícito. Esto se llama "portal" y es la técnica estándar
    // para dropdowns que se renderizan "encima" de todo.
    document.body.appendChild(this.dropdown);

    // Parseamos la semana inicial desde el input oculto
    const semanaInicial = parsearSemanaISO(this.hiddenInput.value);
    this.semanaActual = semanaInicial ?? obtenerSemanaISO(new Date());

    // El calendario abre en el mes del lunes de la semana seleccionada
    const lunesActual = lunesDeSemanaISO(this.semanaActual.año, this.semanaActual.semana);
    this.mesMostrado = new Date(lunesActual.getFullYear(), lunesActual.getMonth(), 1);

    this.inicializar();
  }

  /**
   * Conecta todos los event listeners.
   */
  private inicializar(): void {
    // Abrir/cerrar dropdown al hacer clic en el botón
    this.trigger.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      this.toggleDropdown();
    });

    // Botón mes anterior
    document.getElementById('wpPrevMonth')?.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      this.mesMostrado = new Date(this.mesMostrado.getFullYear(), this.mesMostrado.getMonth() - 1, 1);
      this.renderCalendario();
    });

    // Botón mes siguiente
    document.getElementById('wpNextMonth')?.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      this.mesMostrado = new Date(this.mesMostrado.getFullYear(), this.mesMostrado.getMonth() + 1, 1);
      this.renderCalendario();
    });

    // Botón "Semana actual"
    document.getElementById('wpBtnHoy')?.addEventListener('click', (e: Event) => {
      e.stopPropagation();
      const semanaHoy = obtenerSemanaISO(new Date());
      this.seleccionarSemana(semanaHoy);
    });

    // Cerrar dropdown si se hace clic fuera
    document.addEventListener('click', (e: Event) => {
      if (!this.dropdown.contains(e.target as Node) &&
          e.target !== this.trigger) {
        this.cerrarDropdown();
      }
    });

    // Cerrar con Escape
    document.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        this.cerrarDropdown();
      }
    });

    // Reposicionar el dropdown al hacer scroll o resize (mientras está abierto)
    const reposicionar = (): void => {
      if (this.dropdown.classList.contains('visible')) {
        this.posicionarDropdown();
      }
    };
    window.addEventListener('scroll', reposicionar, { passive: true });
    window.addEventListener('resize', reposicionar, { passive: true });

    // Renderizamos el calendario inicial (sin mostrarlo todavía)
    this.renderCalendario();
  }

  /**
   * Abre o cierra el dropdown.
   */
  private toggleDropdown(): void {
    const estaAbierto = this.dropdown.classList.contains('visible');
    if (estaAbierto) {
      this.cerrarDropdown();
    } else {
      this.abrirDropdown();
    }
  }

  private abrirDropdown(): void {
    // Calcular posición del trigger en la ventana
    this.posicionarDropdown();

    this.dropdown.classList.add('visible');
    this.trigger.classList.add('abierto');
    this.trigger.setAttribute('aria-expanded', 'true');
    // Nos posicionamos en el mes de la semana seleccionada
    const lunes = lunesDeSemanaISO(this.semanaActual.año, this.semanaActual.semana);
    this.mesMostrado = new Date(lunes.getFullYear(), lunes.getMonth(), 1);
    this.renderCalendario();
  }

  /**
   * Calcula y aplica la posición (fixed) del dropdown relativa al trigger.
   *
   * EXPLICACIÓN PARA PRINCIPIANTES:
   * Como movimos el dropdown al <body>, ya no tiene referencia de posición
   * con su padre original. Usamos getBoundingClientRect() para saber exactamente
   * dónde está el botón en la pantalla y colocamos el dropdown justo debajo.
   *
   * Si el dropdown se saldría por la derecha de la pantalla, lo alineamos
   * por la derecha en lugar de por la izquierda.
   */
  private posicionarDropdown(): void {
    const rect = this.trigger.getBoundingClientRect();
    const dropdownAncho = 280; // ancho definido en CSS
    const margen = 4; // espacio entre trigger y dropdown (en px)

    let top = rect.bottom + margen;
    let left = rect.left;

    // Ajustar si se sale por la derecha de la ventana
    if (left + dropdownAncho > window.innerWidth - 8) {
      left = rect.right - dropdownAncho;
    }

    // Ajustar si se sale por abajo (mostrar arriba del trigger en ese caso)
    const dropdownAlto = 320; // altura estimada del calendario
    if (top + dropdownAlto > window.innerHeight - 8) {
      top = rect.top - dropdownAlto - margen;
    }

    this.dropdown.style.position = 'fixed';
    this.dropdown.style.top = `${top}px`;
    this.dropdown.style.left = `${left}px`;
    this.dropdown.style.width = `${dropdownAncho}px`;
  }

  private cerrarDropdown(): void {
    this.dropdown.classList.remove('visible');
    this.trigger.classList.remove('abierto');
    this.trigger.setAttribute('aria-expanded', 'false');
  }

  /**
   * Renderiza el calendario del mes actual en el dropdown.
   *
   * EXPLICACIÓN:
   * Genera dinámicamente el HTML del calendario:
   *  - Una fila con los nombres de días (L M X J V S D)
   *  - Filas de semanas donde cada fila es clicable
   * Los días que pertenecen a otro mes se muestran atenuados.
   * La semana seleccionada y la semana que contiene "hoy" tienen estilos especiales.
   */
  private renderCalendario(): void {
    const año = this.mesMostrado.getFullYear();
    const mes = this.mesMostrado.getMonth();

    // Actualizar etiqueta del mes
    this.mesLabel.textContent = formatearMesAño(año, mes);

    // Primer día del mes y último
    const primerDia = new Date(año, mes, 1);
    const ultimoDia = new Date(año, mes + 1, 0);

    // El calendario empieza el lunes antes (o en) el primer día del mes
    const inicioCal = new Date(primerDia);
    const diaInicio = primerDia.getDay() || 7; // 0(dom)→7
    inicioCal.setDate(primerDia.getDate() - (diaInicio - 1));

    // El calendario termina el domingo después (o en) el último día del mes
    const finCal = new Date(ultimoDia);
    const diaFin = ultimoDia.getDay() || 7;
    finCal.setDate(ultimoDia.getDate() + (7 - diaFin));

    // Semana de hoy
    const semanaHoy = obtenerSemanaISO(new Date());

    // Lunes de la semana seleccionada actualmente
    const lunesSeleccionado = lunesDeSemanaISO(this.semanaActual.año, this.semanaActual.semana);
    const isoSeleccionado = this.semanaActual.isoString;

    // ---- Construir HTML ----
    let html = '';

    // Encabezados de días
    html += '<div class="wp-dias-semana">';
    const diasNombre = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
    for (const d of diasNombre) {
      html += `<div class="wp-dia-nombre">${d}</div>`;
    }
    html += '</div>';

    // Filas de semanas
    html += '<div class="wp-semanas">';

    const cursor = new Date(inicioCal);
    while (cursor <= finCal) {
      // Calcular la semana ISO de este lunes (cursor)
      const semanaFila = obtenerSemanaISO(cursor);
      const esSeleccionada = semanaFila.isoString === isoSeleccionado;
      const esHoy = semanaFila.isoString === semanaHoy.isoString;

      let clasesFila = 'wp-fila-semana';
      if (esSeleccionada) clasesFila += ' seleccionada';
      if (esHoy) clasesFila += ' semana-hoy';

      html += `<div class="${clasesFila}" data-semana="${semanaFila.isoString}" role="option" aria-selected="${esSeleccionada}" tabindex="-1">`;

      // 7 días de la semana (lun–dom)
      for (let i = 0; i < 7; i++) {
        const fecha = new Date(cursor);
        fecha.setDate(cursor.getDate() + i);

        let clasesDia = 'wp-dia-num';
        if (!mismoMes(fecha, new Date(año, mes, 1))) {
          clasesDia += ' otro-mes';
        }
        if (i >= 5) { // sábado (5) o domingo (6)
          clasesDia += ' fin-semana';
        }
        html += `<div class="${clasesDia}">${fecha.getDate()}</div>`;
      }

      html += '</div>';

      // Avanzar al próximo lunes
      cursor.setDate(cursor.getDate() + 7);
    }

    html += '</div>';

    this.grid.innerHTML = html;

    // Agregar listeners a cada fila-semana
    const filas = this.grid.querySelectorAll<HTMLDivElement>('.wp-fila-semana');
    filas.forEach((fila) => {
      fila.addEventListener('click', () => {
        const isoStr = fila.dataset['semana'];
        if (!isoStr) return;
        const semana = parsearSemanaISO(isoStr);
        if (semana) {
          this.seleccionarSemana(semana);
        }
      });
    });
  }

  /**
   * Selecciona una semana: actualiza el input oculto, la etiqueta del
   * botón disparador y envía el formulario para recargar los datos.
   *
   * @param semana - La semana ISO seleccionada
   */
  private seleccionarSemana(semana: SemanaISO): void {
    this.semanaActual = semana;

    // Actualizar el input oculto (este valor se envía con el formulario)
    this.hiddenInput.value = semana.isoString;

    // Actualizar la etiqueta del botón
    const labelEl = document.getElementById('weekPickerLabel');
    if (labelEl) {
      labelEl.textContent = etiquetaSemana(semana);
    }

    // Cerrar dropdown
    this.cerrarDropdown();

    // Enviar el formulario para recargar los datos
    this.form.submit();
  }
}

// =============================================================================
// FUNCIONES: NAVEGACIÓN CON LOADING STATE
// =============================================================================

/**
 * Agrega efecto de carga (spinner) a los botones ← / → de semana.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Cuando el usuario hace clic en "Semana anterior" o "Semana siguiente",
 * la página tarda un momento en recargarse (hay que consultar la BD).
 * Para que se vea que algo está pasando, mostramos un spinner y
 * deshabilitamos los botones para que no se pueda hacer doble clic.
 */
function inicializarNavegacionSemana(): void {
  const btnAnterior = document.getElementById('btnSemanaAnterior') as HTMLAnchorElement | null;
  const btnSiguiente = document.getElementById('btnSemanaSiguiente') as HTMLAnchorElement | null;

  function activarCarga(btn: HTMLAnchorElement): void {
    btn.classList.add('cargando');
    // También deshabilitamos el otro botón para evitar doble clic
    if (btnAnterior) btnAnterior.classList.add('cargando');
    if (btnSiguiente) btnSiguiente.classList.add('cargando');
  }

  if (btnAnterior) {
    btnAnterior.addEventListener('click', () => {
      activarCarga(btnAnterior);
    });
  }

  if (btnSiguiente) {
    btnSiguiente.addEventListener('click', () => {
      activarCarga(btnSiguiente);
    });
  }
}

// =============================================================================
// FUNCIONES: BOTÓN SCROLL TO TOP
// =============================================================================

/**
 * Inicializa el botón flotante "Volver arriba" del concentrado.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * El botón aparece cuando el usuario baja más de 300px en la página.
 * Al hacer clic, la página hace scroll suave hasta el inicio.
 * La visibilidad se controla agregando/quitando la clase CSS "visible".
 *
 * Nota: tiene nombre distinto a la función en base.ts para evitar conflicto.
 */
function inicializarScrollTopConcentrado(): void {
  const btn = document.getElementById('btn-scroll-top');
  if (!btn) return;

  // Mostrar/ocultar según posición del scroll
  window.addEventListener('scroll', (): void => {
    if (window.scrollY > 300) {
      btn.classList.add('visible');
    } else {
      btn.classList.remove('visible');
    }
  }, { passive: true });

  // Al hacer clic, scrollear suavemente al tope
  btn.addEventListener('click', (): void => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

// =============================================================================
// FUNCIONES: NAVEGACIÓN CON TECLADO
// =============================================================================

/**
 * Permite navegar entre semanas con las teclas ← y → del teclado.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Si el usuario presiona la flecha izquierda, va a la semana anterior.
 * Si presiona la flecha derecha, va a la semana siguiente.
 * Solo funciona cuando el usuario NO está escribiendo en un input/textarea.
 */
function inicializarTeclado(): void {
  document.addEventListener('keydown', (event: KeyboardEvent): void => {
    // No interferir si el usuario está en un campo de texto
    const tagName = (event.target as HTMLElement).tagName.toLowerCase();
    if (['input', 'textarea', 'select'].includes(tagName)) {
      return;
    }

    if (event.key === 'ArrowLeft') {
      const btn = document.getElementById('btnSemanaAnterior') as HTMLAnchorElement | null;
      if (btn) {
        btn.classList.add('cargando');
        window.location.href = btn.href;
      }
    } else if (event.key === 'ArrowRight') {
      const btn = document.getElementById('btnSemanaSiguiente') as HTMLAnchorElement | null;
      if (btn) {
        btn.classList.add('cargando');
        window.location.href = btn.href;
      }
    }
  });
}

// =============================================================================
// INICIALIZACIÓN PRINCIPAL
// =============================================================================

document.addEventListener('DOMContentLoaded', (): void => {

  const form = document.getElementById('formConcentrado') as HTMLFormElement | null;
  if (!form) {
    // Si no está el formulario, no estamos en la página del concentrado
    return;
  }

  // 1. Inicializar el custom week picker
  new WeekPicker();

  // 2. Auto-envío al cambiar la sucursal
  const sucursalSelect = document.getElementById('sucursal_id') as HTMLSelectElement | null;
  if (sucursalSelect) {
    sucursalSelect.addEventListener('change', (): void => {
      form.submit();
    });
  }

  // 3. Loading state en botones de navegación ← →
  inicializarNavegacionSemana();

  // 4. Navegación con teclado
  inicializarTeclado();

  // 5. Botón scroll to top
  inicializarScrollTopConcentrado();

  // 6. Inicializar tooltips de Bootstrap (para los botones de exportar)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const bsGlobal = (window as unknown as { bootstrap?: { Tooltip: new (el: Element) => unknown } }).bootstrap;
  if (typeof bsGlobal !== 'undefined' && bsGlobal) {
    const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipEls.forEach((el: Element): void => {
      new bsGlobal.Tooltip(el);
    });
  }

});
