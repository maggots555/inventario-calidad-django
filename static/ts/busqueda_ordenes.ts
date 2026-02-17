/* =============================================================================
   BÚSQUEDA INTELIGENTE DE ÓRDENES - Autocompletado en tiempo real
   Descripción: Maneja la búsqueda con autocompletado (typeahead) en la página
   de lista de órdenes, mostrando coincidencias mientras el usuario escribe.
   También gestiona el collapse de reasignaciones y el comportamiento del teclado.
   
   EXPLICACIÓN PARA PRINCIPIANTES:
   Este archivo TypeScript reemplaza el JavaScript inline que antes estaba en el
   template lista_ordenes.html. Centraliza toda la lógica de:
   1. Autocompletado: Mientras escribes, busca órdenes en el servidor y muestra
      un dropdown con las coincidencias (orden del cliente + service tag).
   2. Manejo de teclado: ESC limpia búsqueda, flechas navegan sugerencias, Enter selecciona.
   3. Collapse de reasignaciones: Maneja el estado abierto/cerrado del panel de reasignaciones.
   ============================================================================= */

// Bootstrap se accede como global del window (cargado desde el CDN en base.html)
// Se usa (window as any).bootstrap para evitar conflictos de redeclaración con otros .ts

// ============================================================================
// INTERFACES - Definición de tipos para TypeScript
// ============================================================================

/**
 * Representa un resultado individual del autocompletado
 */
interface ResultadoAutocomplete {
    id: number;
    orden_cliente: string;
    numero_serie: string;
    numero_orden_interno: string;
    marca: string;
    modelo: string;
    estado: string;
    url_detalle: string;
}

/**
 * Respuesta del API de autocompletado
 */
interface RespuestaAutocomplete {
    resultados: ResultadoAutocomplete[];
}

/**
 * Configuración del componente de búsqueda
 */
interface ConfiguracionBusqueda {
    apiUrl: string;
    tipo: string;
    minCaracteres: number;
    debounceMs: number;
    maxResultados: number;
}

// ============================================================================
// CLASE PRINCIPAL: BusquedaOrdenesAutocomplete
// ============================================================================

class BusquedaOrdenesAutocomplete {
    private inputBusqueda: HTMLInputElement | null = null;
    private formularioBusqueda: HTMLFormElement | null = null;
    private contenedorDropdown: HTMLDivElement | null = null;
    private config: ConfiguracionBusqueda;
    private debounceTimer: ReturnType<typeof setTimeout> | null = null;
    private indiceActivo: number = -1;
    private resultadosActuales: ResultadoAutocomplete[] = [];
    private abortController: AbortController | null = null;

    constructor() {
        this.config = {
            apiUrl: '',
            tipo: 'activas',
            minCaracteres: 2,
            debounceMs: 300,
            maxResultados: 10,
        };

        document.addEventListener('DOMContentLoaded', () => {
            this.inicializar();
        });
    }

    /**
     * Inicializa todos los componentes de la página
     */
    private inicializar(): void {
        this.configurarBusqueda();
        this.configurarCollapseReasignaciones();
    }

    // ========================================================================
    // SECCIÓN 1: BÚSQUEDA CON AUTOCOMPLETADO
    // ========================================================================

    /**
     * Configura el campo de búsqueda con autocompletado
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * 1. Obtiene el input de búsqueda del DOM
     * 2. Lee la URL del API y el tipo de vista desde atributos data-*
     * 3. Crea el dropdown donde se mostrarán las sugerencias
     * 4. Conecta los eventos: tecleo, teclado especial, clic fuera
     */
    private configurarBusqueda(): void {
        this.inputBusqueda = document.getElementById('busqueda') as HTMLInputElement;
        if (!this.inputBusqueda) return;

        // Leer configuración desde atributos data-* del input
        this.config.apiUrl = this.inputBusqueda.dataset.apiUrl || '';
        this.config.tipo = this.inputBusqueda.dataset.tipo || 'activas';

        // Obtener referencia al formulario padre
        this.formularioBusqueda = this.inputBusqueda.closest('form') as HTMLFormElement;

        // Crear el contenedor del dropdown de sugerencias
        this.crearDropdown();

        // Conectar eventos del input
        this.inputBusqueda.addEventListener('input', () => this.manejarInput());
        this.inputBusqueda.addEventListener('keydown', (e: KeyboardEvent) => this.manejarTeclado(e));
        this.inputBusqueda.addEventListener('focus', () => this.manejarFocus());

        // Cerrar dropdown al hacer clic fuera
        document.addEventListener('click', (e: MouseEvent) => {
            if (this.contenedorDropdown && !this.contenedorDropdown.contains(e.target as Node) &&
                e.target !== this.inputBusqueda) {
                this.cerrarDropdown();
            }
        });

        // Auto-focus en el campo de búsqueda al cargar la página
        this.inputBusqueda.focus();
    }

    /**
     * Crea el elemento HTML del dropdown de sugerencias
     * Se posiciona justo debajo del input de búsqueda
     */
    private crearDropdown(): void {
        if (!this.inputBusqueda) return;

        this.contenedorDropdown = document.createElement('div');
        this.contenedorDropdown.className = 'autocomplete-dropdown';
        this.contenedorDropdown.id = 'autocomplete-dropdown';

        // Insertar el dropdown justo después del input, dentro del mismo contenedor
        const contenedorInput = this.inputBusqueda.parentElement;
        if (contenedorInput) {
            // Asegurar que el contenedor padre tenga position relative
            contenedorInput.style.position = 'relative';
            contenedorInput.appendChild(this.contenedorDropdown);
        }
    }

    /**
     * Maneja cada tecleo en el input (con debounce)
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * "Debounce" significa esperar un momento después de que el usuario deje de escribir
     * antes de hacer la búsqueda. Si el usuario escribe "OOW-123", no queremos buscar
     * "O", "OO", "OOW", "OOW-", etc. Esperamos 300ms de inactividad y solo buscamos
     * el texto final.
     */
    private manejarInput(): void {
        if (!this.inputBusqueda) return;

        const query = this.inputBusqueda.value.trim();

        // Limpiar timer anterior para implementar debounce
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Si no hay suficientes caracteres, cerrar dropdown
        if (query.length < this.config.minCaracteres) {
            this.cerrarDropdown();
            return;
        }

        // Esperar el tiempo de debounce antes de buscar
        this.debounceTimer = setTimeout(() => {
            this.buscarOrdenes(query);
        }, this.config.debounceMs);
    }

    /**
     * Maneja las teclas especiales: ESC, flechas, Enter
     */
    private manejarTeclado(e: KeyboardEvent): void {
        const dropdownVisible = this.contenedorDropdown &&
            this.contenedorDropdown.style.display !== 'none' &&
            this.resultadosActuales.length > 0;

        switch (e.key) {
            case 'Escape':
                if (dropdownVisible) {
                    // Si el dropdown está visible, solo cerrarlo
                    this.cerrarDropdown();
                    e.preventDefault();
                } else if (this.inputBusqueda && this.inputBusqueda.value) {
                    // Si no hay dropdown pero hay texto, limpiar y enviar formulario
                    this.inputBusqueda.value = '';
                    if (this.formularioBusqueda) {
                        this.formularioBusqueda.submit();
                    }
                }
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
                if (dropdownVisible && this.indiceActivo >= 0) {
                    // Si hay un resultado seleccionado, navegar a su detalle
                    e.preventDefault();
                    const resultado = this.resultadosActuales[this.indiceActivo];
                    if (resultado) {
                        window.location.href = resultado.url_detalle;
                    }
                }
                // Si no hay resultado seleccionado, dejar que el formulario se envíe normalmente
                break;
        }
    }

    /**
     * Al hacer focus en el input, si hay texto suficiente, mostrar resultados
     */
    private manejarFocus(): void {
        if (!this.inputBusqueda) return;
        const query = this.inputBusqueda.value.trim();

        if (query.length >= this.config.minCaracteres && this.resultadosActuales.length > 0) {
            this.mostrarDropdown();
        }
    }

    /**
     * Realiza la petición AJAX al API de autocompletado
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * fetch() es la forma moderna de hacer peticiones HTTP desde JavaScript.
     * AbortController permite cancelar peticiones anteriores si el usuario
     * sigue escribiendo (así no se solapan respuestas antiguas).
     */
    private async buscarOrdenes(query: string): Promise<void> {
        if (!this.config.apiUrl) return;

        // Cancelar petición anterior si existe
        if (this.abortController) {
            this.abortController.abort();
        }
        this.abortController = new AbortController();

        // Mostrar indicador de carga
        this.mostrarCargando();

        try {
            const url = `${this.config.apiUrl}?q=${encodeURIComponent(query)}&tipo=${encodeURIComponent(this.config.tipo)}`;
            const respuesta = await fetch(url, {
                signal: this.abortController.signal,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            if (!respuesta.ok) {
                throw new Error(`Error HTTP: ${respuesta.status}`);
            }

            const datos: RespuestaAutocomplete = await respuesta.json();
            this.resultadosActuales = datos.resultados || [];
            this.indiceActivo = -1;

            if (this.resultadosActuales.length > 0) {
                this.renderizarResultados(query);
            } else {
                this.mostrarSinResultados(query);
            }
        } catch (error: unknown) {
            // Ignorar errores de cancelación (AbortError)
            if (error instanceof Error && error.name === 'AbortError') return;
            this.cerrarDropdown();
        }
    }

    /**
     * Renderiza los resultados en el dropdown
     * Resalta las coincidencias del texto buscado
     */
    private renderizarResultados(query: string): void {
        if (!this.contenedorDropdown) return;

        let html = '<ul class="autocomplete-lista" role="listbox">';

        this.resultadosActuales.forEach((resultado, indice) => {
            const ordenCliente = this.resaltarCoincidencia(resultado.orden_cliente, query);
            const serviceTag = this.resaltarCoincidencia(resultado.numero_serie, query);
            const ordenInterno = this.resaltarCoincidencia(resultado.numero_orden_interno, query);

            html += `
                <li class="autocomplete-item" 
                    role="option" 
                    data-indice="${indice}"
                    data-url="${resultado.url_detalle}"
                    aria-selected="false">
                    <div class="autocomplete-item-principal">
                        <span class="autocomplete-orden">${ordenCliente}</span>
                        <span class="autocomplete-marca badge bg-secondary">${resultado.marca}</span>
                    </div>
                    <div class="autocomplete-item-secundario">
                        <span class="autocomplete-service-tag">
                            <i class="bi bi-upc-scan"></i> ${serviceTag}
                        </span>
                        <span class="autocomplete-orden-interna">
                            <i class="bi bi-hash"></i> ${ordenInterno}
                        </span>
                        <span class="autocomplete-estado badge bg-light text-dark">${resultado.estado}</span>
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
                const url = (item as HTMLElement).dataset.url;
                if (url) {
                    window.location.href = url;
                }
            });
            item.addEventListener('mouseenter', () => {
                const indice = parseInt((item as HTMLElement).dataset.indice || '-1', 10);
                this.actualizarSeleccion(indice);
            });
        });
    }

    /**
     * Resalta las partes del texto que coinciden con la búsqueda
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Si el usuario busca "OOW" y el texto es "OOW-12345", esta función
     * convierte "OOW" en "<mark>OOW</mark>-12345" para que se vea resaltado.
     */
    private resaltarCoincidencia(texto: string, query: string): string {
        if (!texto || !query) return texto || '';

        // Escapar caracteres especiales de regex
        const queryEscapado = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${queryEscapado})`, 'gi');
        return texto.replace(regex, '<mark>$1</mark>');
    }

    /**
     * Muestra mensaje de "Sin resultados"
     */
    private mostrarSinResultados(query: string): void {
        if (!this.contenedorDropdown) return;

        this.contenedorDropdown.innerHTML = `
            <div class="autocomplete-sin-resultados">
                <i class="bi bi-search"></i>
                <span>No se encontraron coincidencias para "<strong>${this.escaparHtml(query)}</strong>"</span>
                <small>Presiona Enter para buscar de todas formas</small>
            </div>
        `;
        this.mostrarDropdown();
    }

    /**
     * Muestra indicador de carga en el dropdown
     */
    private mostrarCargando(): void {
        if (!this.contenedorDropdown) return;

        this.contenedorDropdown.innerHTML = `
            <div class="autocomplete-cargando">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Buscando...</span>
                </div>
                <span>Buscando...</span>
            </div>
        `;
        this.mostrarDropdown();
    }

    /**
     * Navega entre resultados con las flechas del teclado
     */
    private navegarResultados(direccion: number): void {
        const total = this.resultadosActuales.length;
        if (total === 0) return;

        let nuevoIndice = this.indiceActivo + direccion;

        // Permitir ciclo: si está en el último y baja, va al primero
        if (nuevoIndice < 0) {
            nuevoIndice = total - 1;
        } else if (nuevoIndice >= total) {
            nuevoIndice = 0;
        }

        this.actualizarSeleccion(nuevoIndice);
    }

    /**
     * Actualiza visualmente cuál resultado está seleccionado
     */
    private actualizarSeleccion(indice: number): void {
        if (!this.contenedorDropdown) return;

        const items = this.contenedorDropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, i) => {
            if (i === indice) {
                item.classList.add('autocomplete-item-activo');
                item.setAttribute('aria-selected', 'true');
                // Scroll al elemento si no es visible
                (item as HTMLElement).scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('autocomplete-item-activo');
                item.setAttribute('aria-selected', 'false');
            }
        });

        this.indiceActivo = indice;
    }

    /**
     * Muestra el dropdown
     */
    private mostrarDropdown(): void {
        if (this.contenedorDropdown) {
            this.contenedorDropdown.style.display = 'block';
        }
    }

    /**
     * Cierra el dropdown y limpia resultados
     */
    private cerrarDropdown(): void {
        if (this.contenedorDropdown) {
            this.contenedorDropdown.style.display = 'none';
        }
        this.indiceActivo = -1;
    }

    /**
     * Escapa HTML para prevenir XSS
     */
    private escaparHtml(texto: string): string {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(texto));
        return div.innerHTML;
    }

    // ========================================================================
    // SECCIÓN 2: MANEJO DE COLLAPSE/EXPAND DE REASIGNACIONES
    // ========================================================================

    /**
     * Configura el comportamiento del panel colapsable de reasignaciones
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * El panel de "Historial de Reasignaciones del Día" puede expandirse o
     * colapsarse haciendo clic en su encabezado. Este código:
     * 1. Restaura el estado guardado (localStorage) al cargar la página
     * 2. Cambia el ícono de flecha (↓ o ↑) según esté abierto o cerrado
     * 3. Guarda el estado para que al recargar la página, se mantenga
     */
    private configurarCollapseReasignaciones(): void {
        const collapseReasignaciones = document.getElementById('collapseReasignaciones');
        if (!collapseReasignaciones) return;

        // Restaurar estado guardado en localStorage
        const estadoGuardado = localStorage.getItem('collapseReasignaciones');
        if (estadoGuardado === 'visible') {
            const bsCollapse = new (window as any).bootstrap.Collapse(collapseReasignaciones, { toggle: false });
            bsCollapse.show();
        }

        // Configurar toggle de iconos y persistencia
        this.configurarToggleCollapse(collapseReasignaciones, 'collapseReasignaciones');
    }

    /**
     * Configura el comportamiento de toggle para un elemento colapsable
     */
    private configurarToggleCollapse(elementoCollapse: HTMLElement, claveStorage: string): void {
        const header = document.querySelector<HTMLElement>(`[data-bs-target="#${elementoCollapse.id}"]`);
        if (!header) return;

        const icono = header.querySelector<HTMLElement>('.collapse-icon');

        // Evento: cuando el collapse se muestra
        elementoCollapse.addEventListener('show.bs.collapse', () => {
            if (icono) {
                icono.classList.remove('bi-chevron-down');
                icono.classList.add('bi-chevron-up');
            }
            header.setAttribute('aria-expanded', 'true');
            localStorage.setItem(claveStorage, 'visible');
        });

        // Evento: cuando el collapse se oculta
        elementoCollapse.addEventListener('hide.bs.collapse', () => {
            if (icono) {
                icono.classList.remove('bi-chevron-up');
                icono.classList.add('bi-chevron-down');
            }
            header.setAttribute('aria-expanded', 'false');
            localStorage.setItem(claveStorage, 'hidden');
        });

        // Sincronizar icono con estado actual al cargar
        if (elementoCollapse.classList.contains('show')) {
            if (icono) {
                icono.classList.remove('bi-chevron-down');
                icono.classList.add('bi-chevron-up');
            }
            header.setAttribute('aria-expanded', 'true');
        } else {
            if (icono) {
                icono.classList.remove('bi-chevron-up');
                icono.classList.add('bi-chevron-down');
            }
            header.setAttribute('aria-expanded', 'false');
        }
    }
}

// ============================================================================
// INSTANCIAR LA CLASE AL CARGAR EL SCRIPT
// ============================================================================
const busquedaOrdenesAutocomplete = new BusquedaOrdenesAutocomplete();

// Exportar al ámbito global para acceso desde consola/otros scripts si es necesario
// @ts-ignore
window.BusquedaOrdenesAutocomplete = BusquedaOrdenesAutocomplete;
