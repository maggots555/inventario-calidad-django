/**
 * ============================================================================
 * SCORECARD FORM — AUTOCOMPLETADO INTELIGENTE DE ÓRDENES
 * ============================================================================
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja la búsqueda automática de órdenes de servicio
 * cuando el usuario escribe un número de serie (Service Tag) en el formulario
 * de incidencias del Score Card.
 *
 * ¿QUÉ HACE AHORA?
 * 1. Mientras el usuario escribe, busca coincidencias PARCIALES en tiempo real
 *    (igual que el buscador de la lista de órdenes).
 * 2. Muestra un dropdown con las órdenes encontradas.
 * 3. Al seleccionar una orden del dropdown:
 *    - Auto-llena: Tipo de Equipo, Marca, Modelo, Número de Orden Cliente
 *    - Guarda el ID de la orden en el campo oculto (para el backend)
 *    - Muestra el panel de confirmación con los datos de la orden
 * 4. También soporta búsqueda por Número de Orden Cliente (campo alterno).
 *
 * MEJORA RESPECTO A LA VERSIÓN ANTERIOR:
 * - Antes: buscaba solo al perder el foco (blur) con coincidencia EXACTA → intermitente
 * - Ahora: busca mientras se escribe (input+debounce) con coincidencia PARCIAL → confiable
 *
 * TECNOLOGÍAS:
 * - TypeScript: JavaScript con tipos para prevenir errores
 * - Fetch API + AbortController: Peticiones HTTP cancelables
 * - Bootstrap: Estilos visuales
 * - Debounce: Evita búsquedas por cada tecla, espera 350ms de inactividad
 */

// ============================================================================
// INTERFACES — Estructura de datos esperada del API
// ============================================================================

/**
 * Resultado individual del autocompletado
 * (Viene del endpoint: /servicio-tecnico/api/buscar-ordenes-autocomplete/)
 */
interface ResultadoAutocomplete {
    id: number;
    orden_cliente: string;
    numero_serie: string;
    numero_orden_interno: string;
    marca: string;
    modelo: string;
    tipo_equipo: string;   // Clave del choice: 'PC', 'Laptop', 'AIO'
    sucursal_id: number;
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
 * Respuesta del API de búsqueda exacta por serie / orden
 * (Viene del endpoint: /servicio-tecnico/api/buscar-orden-por-serie/)
 */
interface ApiResponseExacta {
    success: boolean;
    encontrado: boolean;
    orden: OrdenDataCompleta | null;
    mensaje?: string;
    error?: string;
}

/**
 * Datos completos de una orden (del endpoint de búsqueda exacta)
 */
interface OrdenDataCompleta {
    id: number;
    numero_orden_interno: string;
    orden_cliente: string;
    tipo_equipo: string;
    tipo_equipo_display: string;
    marca: string;
    modelo: string;
    numero_serie: string;
    gama: string;
    gama_display: string;
    fecha_ingreso: string;
    fecha_ingreso_corta: string;
    estado: string;
    estado_display: string;
    dias_en_servicio: number;
    tecnico_responsable: string;
    tecnico_id: number;
    responsable_seguimiento: string;
    responsable_id: number;
    sucursal: string;
    sucursal_id: number;
    falla_principal: string;
    equipo_enciende: boolean;
    es_mis: boolean;
    es_reingreso: boolean;
    es_candidato_rhitso: boolean;
}

// ============================================================================
// CLASE PRINCIPAL: ScorecardFormHandler
// ============================================================================

class ScorecardFormHandler {

    // —— Campos del formulario ——
    private numeroSerieInput: HTMLInputElement | null;
    private numeroOrdenInput: HTMLInputElement | null;
    private ordenServicioInput: HTMLInputElement | null;  // Campo oculto con ID de la orden
    private tipoEquipoSelect: HTMLSelectElement | null;
    private marcaSelect: HTMLSelectElement | null;
    private modeloInput: HTMLInputElement | null;
    private infoContainer: HTMLElement | null;

    // —— Estado interno ——
    private debounceTimer: ReturnType<typeof setTimeout> | null = null;
    private abortController: AbortController | null = null;
    private dropdownSerie: HTMLDivElement | null = null;
    private dropdownOrden: HTMLDivElement | null = null;
    private resultadosSerie: ResultadoAutocomplete[] = [];
    private resultadosOrden: ResultadoAutocomplete[] = [];
    private indiceSerie: number = -1;
    private indiceOrden: number = -1;
    private ordenConfirmada: ResultadoAutocomplete | null = null;

    // —— Configuración ——
    private readonly API_AUTOCOMPLETE = '/servicio-tecnico/api/buscar-ordenes-autocomplete/';
    private readonly API_EXACTA = '/servicio-tecnico/api/buscar-orden-por-serie/';
    private readonly MIN_CHARS = 2;
    private readonly DEBOUNCE_MS = 350;

    // ============================================================
    // CONSTRUCTOR
    // ============================================================

    constructor() {
        // Campos de búsqueda
        this.numeroSerieInput  = document.getElementById('id_numero_serie') as HTMLInputElement;
        this.numeroOrdenInput  = document.getElementById('id_numero_orden') as HTMLInputElement;
        this.ordenServicioInput = document.getElementById('id_orden_servicio') as HTMLInputElement;

        // Campos de equipo a auto-llenar
        this.tipoEquipoSelect = document.getElementById('id_tipo_equipo') as HTMLSelectElement;
        this.marcaSelect      = document.getElementById('id_marca') as HTMLSelectElement;
        this.modeloInput      = document.getElementById('id_modelo') as HTMLInputElement;

        // Contenedor del panel de información
        this.infoContainer = document.getElementById('orden-info-container');

        this.init();
    }

    // ============================================================
    // INICIALIZACIÓN
    // ============================================================

    private init(): void {
        this.configurarCampoSerie();
        this.configurarCampoOrden();
        console.log('[ScorecardForm] Inicializado — autocompletado con dropdown activo.');
    }

    // ============================================================
    // CAMPO: NÚMERO DE SERIE (Service Tag) — búsqueda principal
    // ============================================================

    private configurarCampoSerie(): void {
        if (!this.numeroSerieInput) {
            console.warn('[ScorecardForm] Campo id_numero_serie no encontrado.');
            return;
        }

        // Crear dropdown de sugerencias
        this.dropdownSerie = this.crearDropdown(this.numeroSerieInput);

        // Evento: escribir en el campo → debounce → buscar
        this.numeroSerieInput.addEventListener('input', () => {
            this.manejarInputSerie();
        });

        // Evento: teclado especial (flechas, ESC, Enter)
        this.numeroSerieInput.addEventListener('keydown', (e: KeyboardEvent) => {
            this.manejarTecladoDropdown(e, this.dropdownSerie, this.resultadosSerie, this.indiceSerie,
                (nuevoIndice) => { this.indiceSerie = nuevoIndice; },
                (resultado) => { this.seleccionarOrden(resultado, 'serie'); }
            );
        });

        // Evento: cerrar dropdown si hace click fuera
        document.addEventListener('click', (e: MouseEvent) => {
            if (this.dropdownSerie &&
                !this.dropdownSerie.contains(e.target as Node) &&
                e.target !== this.numeroSerieInput) {
                this.cerrarDropdown(this.dropdownSerie);
            }
        });
    }

    private manejarInputSerie(): void {
        if (!this.numeroSerieInput) return;

        const query = this.numeroSerieInput.value.trim();

        // Limpiar timer anterior (debounce)
        if (this.debounceTimer) clearTimeout(this.debounceTimer);

        // Si el campo queda vacío, limpiar todo
        if (query.length < this.MIN_CHARS) {
            this.cerrarDropdown(this.dropdownSerie);
            if (query.length === 0) this.limpiarAutocompletado();
            return;
        }

        // Buscar después del debounce
        this.debounceTimer = setTimeout(() => {
            this.buscarOrdenes(query, 'serie');
        }, this.DEBOUNCE_MS);
    }

    // ============================================================
    // CAMPO: NÚMERO DE ORDEN CLIENTE — búsqueda alternativa
    // ============================================================

    private configurarCampoOrden(): void {
        if (!this.numeroOrdenInput) {
            console.warn('[ScorecardForm] Campo id_numero_orden no encontrado.');
            return;
        }

        // Crear dropdown de sugerencias
        this.dropdownOrden = this.crearDropdown(this.numeroOrdenInput);

        this.numeroOrdenInput.addEventListener('input', () => {
            this.manejarInputOrden();
        });

        this.numeroOrdenInput.addEventListener('keydown', (e: KeyboardEvent) => {
            this.manejarTecladoDropdown(e, this.dropdownOrden, this.resultadosOrden, this.indiceOrden,
                (nuevoIndice) => { this.indiceOrden = nuevoIndice; },
                (resultado) => { this.seleccionarOrden(resultado, 'orden'); }
            );
        });

        document.addEventListener('click', (e: MouseEvent) => {
            if (this.dropdownOrden &&
                !this.dropdownOrden.contains(e.target as Node) &&
                e.target !== this.numeroOrdenInput) {
                this.cerrarDropdown(this.dropdownOrden);
            }
        });
    }

    private manejarInputOrden(): void {
        if (!this.numeroOrdenInput) return;

        const query = this.numeroOrdenInput.value.trim();

        if (this.debounceTimer) clearTimeout(this.debounceTimer);

        if (query.length < this.MIN_CHARS) {
            this.cerrarDropdown(this.dropdownOrden);
            if (query.length === 0) this.limpiarAutocompletado();
            return;
        }

        this.debounceTimer = setTimeout(() => {
            this.buscarOrdenes(query, 'orden');
        }, this.DEBOUNCE_MS);
    }

    // ============================================================
    // BÚSQUEDA EN EL API (fetch con AbortController)
    // ============================================================

    private async buscarOrdenes(query: string, origen: 'serie' | 'orden'): Promise<void> {
        // Cancelar petición anterior si aún está en vuelo
        if (this.abortController) this.abortController.abort();
        this.abortController = new AbortController();

        const dropdown = origen === 'serie' ? this.dropdownSerie : this.dropdownOrden;

        this.mostrarCargandoDropdown(dropdown);

        try {
            const url = `${this.API_AUTOCOMPLETE}?q=${encodeURIComponent(query)}&tipo=activas`;
            const respuesta = await fetch(url, {
                signal: this.abortController.signal,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });

            if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);

            const datos: RespuestaAutocomplete = await respuesta.json();
            const resultados = datos.resultados || [];

            if (origen === 'serie') {
                this.resultadosSerie = resultados;
                this.indiceSerie = -1;
            } else {
                this.resultadosOrden = resultados;
                this.indiceOrden = -1;
            }

            if (resultados.length > 0) {
                this.renderizarDropdown(dropdown, resultados, query, origen);
            } else {
                this.mostrarSinResultados(dropdown, query);
            }

        } catch (error: unknown) {
            if (error instanceof Error && error.name === 'AbortError') return;
            console.error('[ScorecardForm] Error al buscar:', error);
            this.cerrarDropdown(dropdown);
        }
    }

    // ============================================================
    // SELECCIÓN DE UNA ORDEN (del dropdown o confirmación exacta)
    // ============================================================

    /**
     * Llamado cuando el usuario hace click en un resultado del dropdown
     * o presiona Enter sobre un resultado seleccionado.
     *
     * Flujo:
     * 1. Llena los campos del formulario con los datos de la orden
     * 2. Cierra el dropdown
     * 3. Muestra el panel de confirmación (verde)
     */
    private seleccionarOrden(resultado: ResultadoAutocomplete, origen: 'serie' | 'orden'): void {
        this.ordenConfirmada = resultado;

        // —— Llenar campos de búsqueda (ambos, siempre) ——
        if (this.numeroSerieInput) {
            this.numeroSerieInput.value = resultado.numero_serie;  // Completa el service tag parcial
            this.numeroSerieInput.readOnly = true;
            this.numeroSerieInput.classList.add('bg-light', 'is-valid');
        }
        if (this.numeroOrdenInput) {
            this.numeroOrdenInput.value = resultado.orden_cliente;
            this.numeroOrdenInput.readOnly = true;
            this.numeroOrdenInput.classList.add('bg-light', 'is-valid');
        }

        // —— Auto-llenar campos de equipo ——
        this.autoLlenarCamposEquipo(resultado);

        // —— Guardar ID en el campo oculto ——
        if (this.ordenServicioInput) {
            this.ordenServicioInput.value = resultado.id.toString();
        }

        // —— Cerrar ambos dropdowns ——
        this.cerrarDropdown(this.dropdownSerie);
        this.cerrarDropdown(this.dropdownOrden);

        // —— Mostrar panel de confirmación ——
        this.mostrarPanelConfirmacion(resultado);

        console.log(`[ScorecardForm] Orden seleccionada: ${resultado.numero_orden_interno} (ID ${resultado.id})`);
    }

    /**
     * Auto-llena Tipo de Equipo, Marca y Modelo con los datos de la orden.
     *
     * NOTA IMPORTANTE: Los choices de tipo_equipo en el modelo Incidencia usan
     * claves en minúsculas ('pc', 'laptop', 'aio'), mientras que la API de
     * servicio_tecnico devuelve las claves en su formato original ('PC', 'Laptop', 'AIO').
     * Por eso hacemos el mapeo explícito.
     */
    private autoLlenarCamposEquipo(resultado: ResultadoAutocomplete): void {
        // —— TIPO DE EQUIPO (select con choices en minúsculas) ——
        if (this.tipoEquipoSelect && resultado.tipo_equipo) {
            // Mapeo: clave del servicio_tecnico → clave del scorecard (Incidencia)
            const mapaTipoEquipo: { [key: string]: string } = {
                'PC':     'pc',
                'Laptop': 'laptop',
                'AIO':    'aio',
                'pc':     'pc',
                'laptop': 'laptop',
                'aio':    'aio',
            };
            const claveScorecard = mapaTipoEquipo[resultado.tipo_equipo] || resultado.tipo_equipo.toLowerCase();

            // Intentar seleccionar la opción correspondiente
            const opcionEncontrada = Array.from(this.tipoEquipoSelect.options).some(opt => {
                if (opt.value === claveScorecard) {
                    this.tipoEquipoSelect!.value = claveScorecard;
                    return true;
                }
                return false;
            });

            if (opcionEncontrada) {
                this.tipoEquipoSelect.classList.add('is-valid');
                // Disparar evento change para que el filtro de componentes se actualice
                this.tipoEquipoSelect.dispatchEvent(new Event('change'));
            }
        }

        // —— MARCA (select con los mismos valores que la API) ——
        if (this.marcaSelect && resultado.marca) {
            // Los valores de marca coinciden directamente (Dell, Lenovo, HP, etc.)
            const opcionEncontrada = Array.from(this.marcaSelect.options).some(opt => {
                if (opt.value === resultado.marca) {
                    this.marcaSelect!.value = resultado.marca;
                    return true;
                }
                return false;
            });

            if (opcionEncontrada) {
                this.marcaSelect.classList.add('is-valid');
            } else {
                // Si la marca no está en las opciones, buscar "Otra"
                Array.from(this.marcaSelect.options).some(opt => {
                    if (opt.value === 'Otra') {
                        this.marcaSelect!.value = 'Otra';
                        return true;
                    }
                    return false;
                });
            }
        }

        // —— MODELO (input de texto) ——
        if (this.modeloInput && resultado.modelo) {
            this.modeloInput.value = resultado.modelo;
            this.modeloInput.classList.add('is-valid');
        }
    }

    // ============================================================
    // LIMPIAR AUTOCOMPLETADO
    // ============================================================

    private limpiarAutocompletado(): void {
        this.ordenConfirmada = null;

        // Restaurar campos de búsqueda
        if (this.numeroOrdenInput) {
            this.numeroOrdenInput.value = '';
            this.numeroOrdenInput.readOnly = false;
            this.numeroOrdenInput.classList.remove('bg-light', 'is-valid');
        }
        if (this.numeroSerieInput) {
            this.numeroSerieInput.readOnly = false;
            this.numeroSerieInput.classList.remove('bg-light', 'is-valid');
        }

        // Limpiar campo oculto
        if (this.ordenServicioInput) this.ordenServicioInput.value = '';

        // Limpiar campos de equipo
        if (this.tipoEquipoSelect) this.tipoEquipoSelect.classList.remove('is-valid');
        if (this.marcaSelect) this.marcaSelect.classList.remove('is-valid');
        if (this.modeloInput) this.modeloInput.classList.remove('is-valid');

        // Limpiar panel de información
        if (this.infoContainer) this.infoContainer.innerHTML = '';
    }

    // ============================================================
    // DROPDOWN — creación, renderizado, cierre
    // ============================================================

    /**
     * Crea el elemento HTML del dropdown y lo inserta después del input.
     */
    private crearDropdown(input: HTMLInputElement): HTMLDivElement {
        const dropdown = document.createElement('div');
        dropdown.className = 'sc-autocomplete-dropdown';
        dropdown.style.display = 'none';

        const contenedor = input.parentElement;
        if (contenedor) {
            contenedor.style.position = 'relative';
            contenedor.appendChild(dropdown);
        }

        return dropdown;
    }

    /**
     * Renderiza la lista de resultados en el dropdown.
     * Resalta las partes que coinciden con la búsqueda.
     */
    private renderizarDropdown(
        dropdown: HTMLDivElement | null,
        resultados: ResultadoAutocomplete[],
        query: string,
        origen: 'serie' | 'orden'
    ): void {
        if (!dropdown) return;

        let html = '<ul class="sc-autocomplete-lista" role="listbox">';

        resultados.forEach((resultado, indice) => {
            const ordenCliente = this.resaltar(resultado.orden_cliente, query);
            const serviceTag   = this.resaltar(resultado.numero_serie, query);
            const ordenInterna = this.resaltar(resultado.numero_orden_interno, query);

            html += `
                <li class="sc-autocomplete-item"
                    role="option"
                    data-indice="${indice}"
                    aria-selected="false">
                    <div class="sc-autocomplete-fila-principal">
                        <span class="sc-autocomplete-orden">${ordenCliente}</span>
                        <span class="sc-autocomplete-marca badge bg-secondary">${this.escaparHtml(resultado.marca)}</span>
                    </div>
                    <div class="sc-autocomplete-fila-secundaria">
                        <span class="sc-autocomplete-serie">
                            <i class="bi bi-upc-scan"></i> ${serviceTag}
                        </span>
                        <span class="sc-autocomplete-interna">
                            <i class="bi bi-hash"></i> ${ordenInterna}
                        </span>
                        <span class="sc-autocomplete-estado badge bg-light text-dark">${this.escaparHtml(resultado.estado)}</span>
                    </div>
                </li>
            `;
        });

        html += '</ul>';
        dropdown.innerHTML = html;
        dropdown.style.display = 'block';

        // Conectar click y hover a cada ítem
        const items = dropdown.querySelectorAll('.sc-autocomplete-item');
        items.forEach((item) => {
            item.addEventListener('click', () => {
                const idx = parseInt((item as HTMLElement).dataset.indice || '-1', 10);
                if (idx >= 0 && idx < resultados.length) {
                    this.seleccionarOrden(resultados[idx], origen);
                }
            });
            item.addEventListener('mouseenter', () => {
                const idx = parseInt((item as HTMLElement).dataset.indice || '-1', 10);
                this.actualizarSeleccionDropdown(dropdown, idx);
                if (origen === 'serie') this.indiceSerie = idx;
                else this.indiceOrden = idx;
            });
        });
    }

    private mostrarCargandoDropdown(dropdown: HTMLDivElement | null): void {
        if (!dropdown) return;
        dropdown.innerHTML = `
            <div class="sc-autocomplete-cargando">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Buscando...</span>
                </div>
                <span>Buscando en el sistema...</span>
            </div>
        `;
        dropdown.style.display = 'block';
    }

    private mostrarSinResultados(dropdown: HTMLDivElement | null, query: string): void {
        if (!dropdown) return;
        dropdown.innerHTML = `
            <div class="sc-autocomplete-sin-resultados">
                <i class="bi bi-search"></i>
                <span>Sin coincidencias para "<strong>${this.escaparHtml(query)}</strong>"</span>
                <small>Verifica el service tag o usa el campo de orden del cliente</small>
            </div>
        `;
        dropdown.style.display = 'block';
    }

    private cerrarDropdown(dropdown: HTMLDivElement | null): void {
        if (dropdown) dropdown.style.display = 'none';
    }

    private actualizarSeleccionDropdown(dropdown: HTMLDivElement | null, indice: number): void {
        if (!dropdown) return;
        dropdown.querySelectorAll('.sc-autocomplete-item').forEach((item, i) => {
            if (i === indice) {
                item.classList.add('sc-autocomplete-item-activo');
                item.setAttribute('aria-selected', 'true');
                (item as HTMLElement).scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('sc-autocomplete-item-activo');
                item.setAttribute('aria-selected', 'false');
            }
        });
    }

    /**
     * Maneja flechas ↑↓, ESC y Enter en el dropdown.
     * Es genérico para poder usarlo tanto en el campo serie como en el de orden.
     */
    private manejarTecladoDropdown(
        e: KeyboardEvent,
        dropdown: HTMLDivElement | null,
        resultados: ResultadoAutocomplete[],
        indiceActual: number,
        setIndice: (n: number) => void,
        onSeleccionar: (r: ResultadoAutocomplete) => void
    ): void {
        const visible = dropdown && dropdown.style.display !== 'none' && resultados.length > 0;

        switch (e.key) {
            case 'Escape':
                if (visible) {
                    this.cerrarDropdown(dropdown);
                    e.preventDefault();
                }
                break;

            case 'ArrowDown':
                if (visible) {
                    e.preventDefault();
                    const siguiente = indiceActual + 1 >= resultados.length ? 0 : indiceActual + 1;
                    setIndice(siguiente);
                    this.actualizarSeleccionDropdown(dropdown, siguiente);
                }
                break;

            case 'ArrowUp':
                if (visible) {
                    e.preventDefault();
                    const anterior = indiceActual - 1 < 0 ? resultados.length - 1 : indiceActual - 1;
                    setIndice(anterior);
                    this.actualizarSeleccionDropdown(dropdown, anterior);
                }
                break;

            case 'Enter':
                if (visible && indiceActual >= 0) {
                    e.preventDefault();
                    onSeleccionar(resultados[indiceActual]);
                }
                break;
        }
    }

    // ============================================================
    // PANEL DE CONFIRMACIÓN — muestra info de la orden encontrada
    // ============================================================

    private mostrarPanelConfirmacion(resultado: ResultadoAutocomplete): void {
        if (!this.infoContainer) return;

        const iconoEquipo = this.iconoPorTipo(resultado.tipo_equipo);
        const tipoDisplay = this.displayTipoEquipo(resultado.tipo_equipo);

        // NOTA: No usamos las clases Bootstrap "alert-dismissible fade show" ni
        // "data-bs-dismiss" para evitar que Bootstrap auto-procese el elemento y
        // lo elimine del DOM de forma inesperada.
        this.infoContainer.innerHTML = `
            <div class="sc-orden-confirmada">
                <div class="sc-orden-confirmada-header">
                    <span>
                        <i class="bi bi-check-circle-fill me-2"></i>
                        Orden vinculada — <strong>${this.escaparHtml(resultado.numero_orden_interno)}</strong>
                    </span>
                    <button type="button"
                            class="sc-btn-cambiar-orden"
                            id="btn-cambiar-orden"
                            title="Seleccionar otra orden">
                        <i class="bi bi-arrow-repeat me-1"></i>Cambiar orden
                    </button>
                </div>
                <div class="sc-orden-confirmada-body">
                    <div class="sc-orden-dato">
                        ${iconoEquipo}
                        <span><strong>Equipo:</strong> ${this.escaparHtml(tipoDisplay)} ${this.escaparHtml(resultado.marca)}${resultado.modelo ? ' — ' + this.escaparHtml(resultado.modelo) : ''}</span>
                    </div>
                    <div class="sc-orden-dato">
                        <i class="bi bi-upc-scan me-1"></i>
                        <span><strong>Service Tag:</strong> <code>${this.escaparHtml(resultado.numero_serie)}</code></span>
                    </div>
                    <div class="sc-orden-dato">
                        <i class="bi bi-receipt me-1"></i>
                        <span><strong>Orden Cliente:</strong> ${this.escaparHtml(resultado.orden_cliente)}</span>
                    </div>
                    <div class="sc-orden-dato">
                        <i class="bi bi-circle-fill me-1" style="font-size:0.5rem; vertical-align: middle;"></i>
                        <span><strong>Estado:</strong> <span class="badge bg-secondary">${this.escaparHtml(resultado.estado)}</span></span>
                    </div>
                </div>
                <div class="sc-orden-confirmada-footer">
                    <i class="bi bi-magic me-1"></i>
                    Tipo de equipo, marca y modelo auto-rellenados. Para cambiar la orden, haz clic en <strong>Cambiar orden</strong>.
                </div>
            </div>
        `;

        // Botón "Cambiar orden" — desbloquea campos y limpia la selección
        const btnCambiar = document.getElementById('btn-cambiar-orden');
        if (btnCambiar) {
            btnCambiar.addEventListener('click', () => {
                this.resetearSeleccion();
            });
        }
    }

    /**
     * Limpia la selección y devuelve los campos a su estado editable.
     * Se llama desde el botón "Cambiar orden" del panel de confirmación.
     */
    private resetearSeleccion(): void {
        // Limpiar campos de búsqueda y desbloquear
        if (this.numeroSerieInput) {
            this.numeroSerieInput.value = '';
            this.numeroSerieInput.readOnly = false;
            this.numeroSerieInput.classList.remove('bg-light', 'is-valid');
            this.numeroSerieInput.focus();
        }
        if (this.numeroOrdenInput) {
            this.numeroOrdenInput.value = '';
            this.numeroOrdenInput.readOnly = false;
            this.numeroOrdenInput.classList.remove('bg-light', 'is-valid');
        }

        // Limpiar campo oculto de la orden
        if (this.ordenServicioInput) this.ordenServicioInput.value = '';

        // Quitar validación visual de los campos de equipo
        if (this.tipoEquipoSelect) this.tipoEquipoSelect.classList.remove('is-valid');
        if (this.marcaSelect) this.marcaSelect.classList.remove('is-valid');
        if (this.modeloInput) this.modeloInput.classList.remove('is-valid');

        // Limpiar panel de confirmación
        if (this.infoContainer) this.infoContainer.innerHTML = '';

        this.ordenConfirmada = null;

        console.log('[ScorecardForm] Selección limpiada — campos desbloqueados.');
    }

    // ============================================================
    // UTILIDADES
    // ============================================================

    /** Resalta la parte del texto que coincide con el query */
    private resaltar(texto: string, query: string): string {
        if (!texto || !query) return this.escaparHtml(texto || '');
        const queryEsc = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${queryEsc})`, 'gi');
        return this.escaparHtml(texto).replace(regex, '<mark>$1</mark>');
    }

    /** Previene XSS al insertar texto en el HTML */
    private escaparHtml(texto: string): string {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(texto));
        return div.innerHTML;
    }

    /** Devuelve un icono Bootstrap según el tipo de equipo */
    private iconoPorTipo(tipo: string): string {
        const iconos: { [key: string]: string } = {
            'PC':     '<i class="bi bi-pc-display-horizontal me-1"></i>',
            'pc':     '<i class="bi bi-pc-display-horizontal me-1"></i>',
            'Laptop': '<i class="bi bi-laptop me-1"></i>',
            'laptop': '<i class="bi bi-laptop me-1"></i>',
            'AIO':    '<i class="bi bi-display me-1"></i>',
            'aio':    '<i class="bi bi-display me-1"></i>',
        };
        return iconos[tipo] || '<i class="bi bi-pc me-1"></i>';
    }

    /** Devuelve el nombre legible del tipo de equipo */
    private displayTipoEquipo(tipo: string): string {
        const nombres: { [key: string]: string } = {
            'PC':     'PC',
            'pc':     'PC',
            'Laptop': 'Laptop',
            'laptop': 'Laptop',
            'AIO':    'AIO (All-in-One)',
            'aio':    'AIO (All-in-One)',
        };
        return nombres[tipo] || tipo;
    }
}

// ============================================================================
// INICIALIZACIÓN — esperar a que el DOM esté listo
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    new ScorecardFormHandler();
});
