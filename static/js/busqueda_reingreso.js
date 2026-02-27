"use strict";
/* =============================================================================
   SELECTOR INTELIGENTE DE ORDEN ORIGINAL (REINGRESO)
   Descripción: Maneja el buscador con autocompletado para el campo "Orden Original"
   en la sección de Reingreso de detalle_orden.html.

   DIFERENCIA vs busqueda_ordenes.ts:
   - No navega a la orden al seleccionarla; la "selecciona" guardando su ID
     en un <input type="hidden"> que el formulario Django enviará al submit.
   - Muestra un "chip" (pastilla de resumen) con la orden seleccionada,
     con botón para deseleccionar.
   - Solo busca en órdenes entregadas (el filtro lo aplica el API Django).

   EXPLICACIÓN PARA PRINCIPIANTES:
   Piensa en esto como el selector de "Para:" de un correo electrónico:
   1. Escribes el nombre, aparecen sugerencias
   2. Haces clic en una sugerencia → aparece una "pastilla" con el nombre
   3. La pastilla tiene una "X" para quitarla
   4. Al enviar el formulario, se manda el ID interno (no el texto visible)
   ============================================================================= */
// ============================================================================
// CLASE PRINCIPAL: SelectorOrdenReingreso
// ============================================================================
class SelectorOrdenReingreso {
    constructor() {
        // Elemento <input type="text"> visible donde el usuario escribe
        this.inputBusqueda = null;
        // Elemento <input type="hidden"> que Django leerá al hacer submit del form
        this.inputHidden = null;
        // Contenedor flotante donde se muestran las sugerencias
        this.contenedorDropdown = null;
        // Zona donde aparece el "chip" de la orden seleccionada
        this.zonaSeleccionada = null;
        // Timer para implementar debounce (esperar que el usuario pare de escribir)
        this.debounceTimer = null;
        // Índice del item actualmente resaltado con el teclado (-1 = ninguno)
        this.indiceActivo = -1;
        // Resultados recibidos del servidor en la última búsqueda
        this.resultadosActuales = [];
        // AbortController para cancelar peticiones HTTP anteriores
        this.abortController = null;
        this.config = {
            apiUrl: '',
            excluirId: '',
            minCaracteres: 2,
            debounceMs: 300,
        };
        // Esperar a que el DOM esté listo antes de inicializar
        document.addEventListener('DOMContentLoaded', () => {
            this.inicializar();
        });
    }
    // ========================================================================
    // INICIALIZACIÓN
    // ========================================================================
    /**
     * Punto de entrada: busca los elementos del DOM y conecta los eventos
     */
    inicializar() {
        // Buscar el input de búsqueda visible por su ID
        this.inputBusqueda = document.getElementById('reingreso-busqueda');
        if (!this.inputBusqueda)
            return; // Si no existe en esta página, no hace nada
        // Leer configuración desde los atributos data-* del input visible
        this.config.apiUrl = this.inputBusqueda.dataset.apiUrl || '';
        this.config.excluirId = this.inputBusqueda.dataset.excluirId || '';
        // Obtener referencias a los demás elementos del DOM
        this.inputHidden = document.getElementById('id_orden_original_hidden');
        this.zonaSeleccionada = document.getElementById('reingreso-seleccionada');
        // Crear el dropdown de sugerencias
        this.crearDropdown();
        // Conectar los eventos de interacción
        this.inputBusqueda.addEventListener('input', () => this.manejarInput());
        this.inputBusqueda.addEventListener('keydown', (e) => this.manejarTeclado(e));
        this.inputBusqueda.addEventListener('focus', () => this.manejarFocus());
        // Cerrar el dropdown al hacer clic fuera del componente
        document.addEventListener('click', (e) => {
            const target = e.target;
            const dentroDropdown = this.contenedorDropdown && this.contenedorDropdown.contains(target);
            const dentroInput = target === this.inputBusqueda;
            if (!dentroDropdown && !dentroInput) {
                this.cerrarDropdown();
            }
        });
        // Si ya hay una orden seleccionada (cargada desde la base de datos),
        // mostrar su chip inmediatamente sin necesidad de buscar
        this.restaurarSeleccionInicial();
    }
    // ========================================================================
    // CREACIÓN DEL DROPDOWN
    // ========================================================================
    /**
     * Crea el elemento HTML del dropdown y lo inserta en el DOM
     * justo debajo del input de búsqueda
     */
    crearDropdown() {
        if (!this.inputBusqueda)
            return;
        this.contenedorDropdown = document.createElement('div');
        this.contenedorDropdown.className = 'autocomplete-dropdown';
        this.contenedorDropdown.id = 'reingreso-dropdown';
        this.contenedorDropdown.style.display = 'none';
        const contenedorInput = this.inputBusqueda.parentElement;
        if (contenedorInput) {
            contenedorInput.style.position = 'relative';
            contenedorInput.appendChild(this.contenedorDropdown);
        }
    }
    // ========================================================================
    // RESTAURACIÓN DEL ESTADO INICIAL
    // ========================================================================
    /**
     * Si la orden ya tenía una orden original guardada (por ejemplo, al editar),
     * carga los datos de esa orden y muestra el chip.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando Django renderiza la página, el campo hidden ya tiene el ID de la
     * orden original (si existe). Leemos ese ID y hacemos una petición al API
     * para obtener los detalles y mostrar el chip correctamente.
     */
    restaurarSeleccionInicial() {
        if (!this.inputHidden || !this.inputHidden.value)
            return;
        const idOrdenOriginal = this.inputHidden.value.trim();
        if (!idOrdenOriginal || idOrdenOriginal === '')
            return;
        // Pedir detalles de esa orden al API usando su ID
        // Buscamos por numero_orden_interno o directamente por el ID que ya tenemos
        // Usamos una búsqueda silenciosa (sin mostrar dropdown) para obtener sus datos
        this.cargarOrdenPorId(idOrdenOriginal);
    }
    /**
     * Carga los datos de una orden específica por su ID y muestra el chip
     */
    async cargarOrdenPorId(id) {
        if (!this.config.apiUrl)
            return;
        try {
            // EXPLICACIÓN PARA PRINCIPIANTES:
            // Usamos el parámetro ?id= (en vez de ?q=) para que el API haga una
            // búsqueda EXACTA por PK. Si usáramos ?q=47, el API buscaría el texto
            // "47" en campos como orden_cliente, numero_serie, etc., y probablemente
            // no encontraría nada. Con ?id=47, Django hace un .get(pk=47) directo.
            const url = `${this.config.apiUrl}?id=${encodeURIComponent(id)}&excluir=${encodeURIComponent(this.config.excluirId)}`;
            const respuesta = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!respuesta.ok)
                return;
            const datos = await respuesta.json();
            // El API devuelve exactamente 1 resultado cuando se usa ?id=
            const ordenExacta = datos.resultados[0];
            if (ordenExacta) {
                this.mostrarChipSeleccionado(ordenExacta);
                // Ocultar el input de texto ya que ya hay una selección activa
                if (this.inputBusqueda) {
                    this.inputBusqueda.value = '';
                    this.inputBusqueda.style.display = 'none';
                }
            }
        }
        catch {
            // Error silencioso — no interrumpir la carga de la página
        }
    }
    // ========================================================================
    // MANEJO DE EVENTOS DEL INPUT
    // ========================================================================
    /**
     * Maneja cada tecleo en el input (con debounce de 300ms)
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Debounce: esperamos 300ms después del último tecleo para buscar.
     * Si el usuario escribe "OOW-12345", no queremos hacer 9 peticiones al servidor.
     * Solo hacemos UNA petición cuando deja de escribir por 300ms.
     */
    manejarInput() {
        if (!this.inputBusqueda)
            return;
        const query = this.inputBusqueda.value.trim();
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        if (query.length < this.config.minCaracteres) {
            this.cerrarDropdown();
            return;
        }
        this.debounceTimer = setTimeout(() => {
            this.buscarOrdenes(query);
        }, this.config.debounceMs);
    }
    /**
     * Maneja teclas especiales: ESC, flechas arriba/abajo, Enter
     */
    manejarTeclado(e) {
        const dropdownVisible = this.contenedorDropdown &&
            this.contenedorDropdown.style.display !== 'none' &&
            this.resultadosActuales.length > 0;
        switch (e.key) {
            case 'Escape':
                this.cerrarDropdown();
                e.preventDefault();
                break;
            case 'ArrowDown':
                if (dropdownVisible) {
                    e.preventDefault();
                    this.navegarResultados(1);
                }
                break;
            case 'ArrowUp':
                if (dropdownVisible) {
                    e.preventDefault();
                    this.navegarResultados(-1);
                }
                break;
            case 'Enter':
                // Prevenir submit del formulario mientras el dropdown está abierto
                if (dropdownVisible) {
                    e.preventDefault();
                    if (this.indiceActivo >= 0) {
                        const resultado = this.resultadosActuales[this.indiceActivo];
                        if (resultado) {
                            this.seleccionarOrden(resultado);
                        }
                    }
                }
                break;
        }
    }
    /**
     * Al recuperar el foco en el input, mostrar resultados previos si los hay
     */
    manejarFocus() {
        if (!this.inputBusqueda)
            return;
        const query = this.inputBusqueda.value.trim();
        if (query.length >= this.config.minCaracteres && this.resultadosActuales.length > 0) {
            this.mostrarDropdown();
        }
    }
    // ========================================================================
    // PETICIÓN AL API Y RENDERIZADO
    // ========================================================================
    /**
     * Hace la petición fetch al API de Django para buscar órdenes entregadas
     */
    async buscarOrdenes(query) {
        if (!this.config.apiUrl)
            return;
        // Cancelar petición anterior si todavía está en curso
        if (this.abortController) {
            this.abortController.abort();
        }
        this.abortController = new AbortController();
        this.mostrarCargando();
        try {
            const url = `${this.config.apiUrl}?q=${encodeURIComponent(query)}&excluir=${encodeURIComponent(this.config.excluirId)}`;
            const respuesta = await fetch(url, {
                signal: this.abortController.signal,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!respuesta.ok)
                throw new Error(`HTTP ${respuesta.status}`);
            const datos = await respuesta.json();
            this.resultadosActuales = datos.resultados || [];
            this.indiceActivo = -1;
            if (this.resultadosActuales.length > 0) {
                this.renderizarResultados(query);
            }
            else {
                this.mostrarSinResultados(query);
            }
        }
        catch (error) {
            if (error instanceof Error && error.name === 'AbortError')
                return;
            this.cerrarDropdown();
        }
    }
    /**
     * Construye el HTML del dropdown con los resultados recibidos
     * Resalta en amarillo las partes del texto que coinciden con la búsqueda
     */
    renderizarResultados(query) {
        if (!this.contenedorDropdown)
            return;
        let html = '<ul class="autocomplete-lista" role="listbox">';
        this.resultadosActuales.forEach((resultado, indice) => {
            const ordenCliente = this.resaltarCoincidencia(resultado.orden_cliente, query);
            const serviceTag = this.resaltarCoincidencia(resultado.numero_serie, query);
            const ordenInterno = this.resaltarCoincidencia(resultado.numero_orden_interno, query);
            const marca = this.resaltarCoincidencia(resultado.marca, query);
            const modelo = this.resaltarCoincidencia(resultado.modelo, query);
            html += `
                <li class="autocomplete-item"
                    role="option"
                    data-indice="${indice}"
                    aria-selected="false">
                    <div class="autocomplete-item-principal">
                        <span class="autocomplete-orden">${ordenCliente}</span>
                        <span class="autocomplete-marca badge bg-secondary">${marca}</span>
                    </div>
                    <div class="autocomplete-item-secundario">
                        <span class="autocomplete-service-tag">
                            <i class="bi bi-upc-scan"></i> ${serviceTag}
                        </span>
                        <span class="autocomplete-orden-interna">
                            <i class="bi bi-hash"></i> ${ordenInterno}
                        </span>
                        <span class="autocomplete-estado badge bg-success text-white">
                            <i class="bi bi-box-seam"></i> Entregado ${resultado.fecha_entrega ? '· ' + resultado.fecha_entrega : ''}
                        </span>
                    </div>
                    <div class="autocomplete-item-modelo text-muted" style="font-size: 0.78rem; padding-top: 2px;">
                        <i class="bi bi-laptop"></i> ${modelo}
                    </div>
                </li>
            `;
        });
        html += '</ul>';
        this.contenedorDropdown.innerHTML = html;
        this.mostrarDropdown();
        // Conectar eventos de clic y hover a cada resultado
        const items = this.contenedorDropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item) => {
            item.addEventListener('click', () => {
                const indice = parseInt(item.dataset.indice || '-1', 10);
                if (indice >= 0 && this.resultadosActuales[indice]) {
                    this.seleccionarOrden(this.resultadosActuales[indice]);
                }
            });
            item.addEventListener('mouseenter', () => {
                const indice = parseInt(item.dataset.indice || '-1', 10);
                this.actualizarSeleccion(indice);
            });
        });
    }
    // ========================================================================
    // SELECCIÓN DE UNA ORDEN
    // ========================================================================
    /**
     * Registra la orden seleccionada y muestra el chip de confirmación
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * 1. Guardamos el ID numérico en el campo hidden (lo que Django necesita)
     * 2. Ocultamos el input de búsqueda (ya no se necesita escribir)
     * 3. Mostramos un "chip" (pastilla visual) con los datos de la orden
     * 4. El chip tiene un botón "×" para deseleccionar y volver a buscar
     */
    seleccionarOrden(resultado) {
        // Guardar ID en el campo hidden que Django enviará al servidor
        if (this.inputHidden) {
            this.inputHidden.value = String(resultado.id);
        }
        // Limpiar y ocultar el input de búsqueda
        if (this.inputBusqueda) {
            this.inputBusqueda.value = '';
            this.inputBusqueda.style.display = 'none';
        }
        // Cerrar el dropdown
        this.cerrarDropdown();
        this.resultadosActuales = [];
        // Mostrar el chip con la orden seleccionada
        this.mostrarChipSeleccionado(resultado);
    }
    /**
     * Renderiza el "chip" (tarjeta de resumen) de la orden seleccionada
     */
    mostrarChipSeleccionado(resultado) {
        if (!this.zonaSeleccionada)
            return;
        this.zonaSeleccionada.innerHTML = `
            <div class="reingreso-chip d-flex align-items-start gap-3 p-3 border rounded"
                 style="background: linear-gradient(135deg, #f0fdf4, #dcfce7); border-color: #16a34a !important;">
                <div class="flex-shrink-0" style="color: #16a34a; font-size: 1.6rem;">
                    <i class="bi bi-check-circle-fill"></i>
                </div>
                <div class="flex-grow-1" style="min-width: 0;">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="fw-bold text-dark" style="font-size: 0.95rem;">
                                ${this.escaparHtml(resultado.orden_cliente || resultado.numero_orden_interno)}
                            </div>
                            <div class="text-muted small mt-1">
                                <span class="me-3">
                                    <i class="bi bi-upc-scan"></i>
                                    <code>${this.escaparHtml(resultado.numero_serie)}</code>
                                </span>
                                <span class="me-3">
                                    <i class="bi bi-hash"></i>
                                    ${this.escaparHtml(resultado.numero_orden_interno)}
                                </span>
                                ${resultado.fecha_entrega ? `
                                <span class="badge bg-success">
                                    <i class="bi bi-calendar-check"></i> Entregado ${this.escaparHtml(resultado.fecha_entrega)}
                                </span>` : ''}
                            </div>
                            <div class="text-secondary small mt-1">
                                <i class="bi bi-laptop"></i>
                                ${this.escaparHtml(resultado.marca)} ${this.escaparHtml(resultado.modelo)}
                            </div>
                        </div>
                        <button type="button"
                                class="btn btn-sm btn-outline-danger ms-2 flex-shrink-0"
                                id="btn-deseleccionar-reingreso"
                                title="Quitar orden original seleccionada"
                                style="padding: 2px 8px;">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        this.zonaSeleccionada.style.display = 'block';
        // Conectar el botón de deseleccionar
        const btnDeseleccionar = document.getElementById('btn-deseleccionar-reingreso');
        if (btnDeseleccionar) {
            btnDeseleccionar.addEventListener('click', () => this.deseleccionarOrden());
        }
    }
    /**
     * Limpia la selección actual y restaura el input de búsqueda
     */
    deseleccionarOrden() {
        // Limpiar el campo hidden
        if (this.inputHidden) {
            this.inputHidden.value = '';
        }
        // Mostrar de nuevo el input de búsqueda
        if (this.inputBusqueda) {
            this.inputBusqueda.style.display = '';
            this.inputBusqueda.value = '';
            this.inputBusqueda.focus();
        }
        // Ocultar el chip
        if (this.zonaSeleccionada) {
            this.zonaSeleccionada.innerHTML = '';
            this.zonaSeleccionada.style.display = 'none';
        }
        this.resultadosActuales = [];
    }
    // ========================================================================
    // ESTADOS DEL DROPDOWN
    // ========================================================================
    mostrarDropdown() {
        if (this.contenedorDropdown) {
            this.contenedorDropdown.style.display = 'block';
        }
    }
    cerrarDropdown() {
        if (this.contenedorDropdown) {
            this.contenedorDropdown.style.display = 'none';
        }
        this.indiceActivo = -1;
    }
    mostrarCargando() {
        if (!this.contenedorDropdown)
            return;
        this.contenedorDropdown.innerHTML = `
            <div class="autocomplete-cargando">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Buscando...</span>
                </div>
                <span>Buscando en órdenes entregadas...</span>
            </div>
        `;
        this.mostrarDropdown();
    }
    mostrarSinResultados(query) {
        if (!this.contenedorDropdown)
            return;
        this.contenedorDropdown.innerHTML = `
            <div class="autocomplete-sin-resultados">
                <i class="bi bi-search"></i>
                <span>Sin resultados para "<strong>${this.escaparHtml(query)}</strong>"</span>
                <small>Solo se busca en órdenes entregadas al cliente</small>
            </div>
        `;
        this.mostrarDropdown();
    }
    // ========================================================================
    // NAVEGACIÓN CON TECLADO
    // ========================================================================
    navegarResultados(direccion) {
        const total = this.resultadosActuales.length;
        if (total === 0)
            return;
        let nuevoIndice = this.indiceActivo + direccion;
        if (nuevoIndice < 0)
            nuevoIndice = total - 1;
        else if (nuevoIndice >= total)
            nuevoIndice = 0;
        this.actualizarSeleccion(nuevoIndice);
    }
    actualizarSeleccion(indice) {
        if (!this.contenedorDropdown)
            return;
        const items = this.contenedorDropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, i) => {
            if (i === indice) {
                item.classList.add('autocomplete-item-activo');
                item.setAttribute('aria-selected', 'true');
                item.scrollIntoView({ block: 'nearest' });
            }
            else {
                item.classList.remove('autocomplete-item-activo');
                item.setAttribute('aria-selected', 'false');
            }
        });
        this.indiceActivo = indice;
    }
    // ========================================================================
    // UTILIDADES
    // ========================================================================
    /**
     * Resalta en amarillo las partes del texto que coinciden con la búsqueda
     */
    resaltarCoincidencia(texto, query) {
        if (!texto || !query)
            return texto || '';
        const queryEscapado = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${queryEscapado})`, 'gi');
        return texto.replace(regex, '<mark>$1</mark>');
    }
    /**
     * Escapa caracteres HTML para prevenir XSS
     */
    escaparHtml(texto) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(texto));
        return div.innerHTML;
    }
}
// ============================================================================
// INSTANCIAR AL CARGAR EL SCRIPT
// ============================================================================
const selectorOrdenReingreso = new SelectorOrdenReingreso();
// Exportar al ámbito global para depuración en consola si es necesario
// @ts-ignore
window.SelectorOrdenReingreso = SelectorOrdenReingreso;
//# sourceMappingURL=busqueda_reingreso.js.map