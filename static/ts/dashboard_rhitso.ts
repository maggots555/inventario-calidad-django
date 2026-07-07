/**
 * DASHBOARD_RHITSO.TS
 * ===========================================================================
 * TypeScript para el Dashboard RHITSO
 * 
 * PARA PRINCIPIANTES - ¿Qué hace este archivo?
 * - Inicializa DataTables para las 3 pestañas (activos, pendientes, excluidos)
 * - Implementa filtros dinámicos por estado RHITSO
 * - La exportación Excel y el reporte de análisis se generan en el backend (openpyxl)
 * 
 * EXPLICACIÓN TÉCNICA:
 * - DOMContentLoaded: Espera a que el HTML esté completamente cargado
 * - DataTables: Librería jQuery para tablas interactivas (ordenamiento, búsqueda, paginación)
 * - XLSX: Librería para generar archivos Excel desde JavaScript
 * ===========================================================================
 */

// ===============================================================
// DECLARACIONES DE TIPOS PARA LIBRERÍAS EXTERNAS
// ===============================================================
// EXPLICACIÓN: Estas declaraciones le dicen a TypeScript que existen
// variables globales (jQuery $ y XLSX) que vienen de librerías CDN

declare const $: any; // jQuery
declare const XLSX: any; // SheetJS para Excel
declare const bootstrap: any; // Bootstrap

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    
    /**
     * PASO 1: INICIALIZAR DATATABLES PARA LAS 3 TABLAS
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * DataTables es una librería que convierte tablas HTML simples en
     * tablas interactivas con:
     * - Ordenamiento por columnas (click en el encabezado)
     * - Búsqueda/filtrado
     * - Paginación
     * - Diseño responsive
     */
    
    // Configuración común para las 3 tablas
    const dataTablesConfig = {
        // Idioma en español
        language: {
            url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json'
        },
        // Número de filas por página
        pageLength: 15,
        // Opciones de filas por página
        lengthMenu: [[5, 10, 15, 25, 50, -1], [5, 10, 15, 25, 50, "Todos"]],
        // Diseño responsive
        responsive: true,
        // Configuración de columnas
        columnDefs: [
            // La última columna (Acciones) no se puede ordenar
            { orderable: false, targets: -1 },
            // Columna de Estado RHITSO tiene configuración especial
            {
                targets: 6, // Índice de la columna "Estado RHITSO" (antes era 7, ahora 6 sin columna Servicio)
                type: 'html',
                render: function(data: any, type: string, row: any) {
                    if (type === 'display') {
                        return data; // Mostrar HTML completo
                    }
                    if (type === 'type' || type === 'sort' || type === 'search') {
                        // Para ordenamiento y búsqueda, extraer solo el texto
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = data;
                        return tempDiv.textContent.trim();
                    }
                    return data;
                }
            }
        ],
    // Ordenar por columna "Fecha Envío RHITSO" descendente (antes 9, ahora 8 sin columna Servicio)
    order: [[8, 'desc']]
};

/**
 * FUNCIÓN AUXILIAR: Verificar si una tabla tiene datos
 * ===================================================================
 * EXPLICACIÓN: Verifica si la tabla tiene filas de datos reales (no solo el mensaje "No hay órdenes")
 * Retorna true si hay datos, false si está vacía
 */
function tablaConDatos(tablaId: string): boolean {
    const tabla = document.getElementById(tablaId);
    if (!tabla) return false;
    
    const tbody = tabla.querySelector('tbody');
    if (!tbody) return false;
    
    const filas = tbody.querySelectorAll('tr');
    
    // Si hay filas
    if (filas.length > 0) {
        const primeraFila = filas[0];
        // Verificar si es una fila con colspan (mensaje de tabla vacía)
        const tieneColspan = primeraFila.querySelector('td[colspan]');
        return !tieneColspan; // Tiene datos si NO tiene colspan
    }
    return false;
}

// Inicializar DataTable para ACTIVOS (solo si tiene datos)
let tableActivos = null;
if (tablaConDatos('candidatosRhitsoTableActivos')) {
    tableActivos = $('#candidatosRhitsoTableActivos').DataTable(dataTablesConfig);
}

// Inicializar DataTable para PENDIENTES (solo si tiene datos)
let tablePendientes = null;
if (tablaConDatos('candidatosRhitsoTablePendientes')) {
    tablePendientes = $('#candidatosRhitsoTablePendientes').DataTable(dataTablesConfig);
}

// Inicializar DataTable para EXCLUIDOS (solo si tiene datos)
let tableExcluidos = null;
if (tablaConDatos('candidatosRhitsoTableExcluidos')) {
    tableExcluidos = $('#candidatosRhitsoTableExcluidos').DataTable(dataTablesConfig);
}    /**
     * PASO 2: IMPLEMENTAR FILTROS POR ESTADO RHITSO
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando el usuario selecciona un estado en el dropdown, filtramos
     * la tabla para mostrar solo las filas que coincidan con ese estado.
     * 
     * ¿Cómo funciona?
     * 1. Detectamos el cambio en el <select> con 'change' event
     * 2. Obtenemos el valor seleccionado
     * 3. Usamos DataTables API para filtrar la columna 7 (Estado RHITSO)
     * 4. DataTables automáticamente actualiza la tabla
     */
    
    // Filtro para tabla ACTIVOS
    const filtroActivos = document.getElementById('filtro_estado_rhitso_activos') as HTMLSelectElement;
    if (filtroActivos) {
        filtroActivos.addEventListener('change', function(this: HTMLSelectElement) {
            if (!tableActivos) return; // Si no hay tabla, salir
            
            const valorFiltro = this.value;
            
            if (valorFiltro === '') {
                // Si selecciona "Todos", limpiar el filtro
                tableActivos.column(6).search('').draw();
            } else {
                // Filtrar por el estado seleccionado (columna 6: Estado RHITSO)
                tableActivos.column(6).search(valorFiltro).draw();
            }
        });
    }
    
    // Filtro para tabla PENDIENTES
    const filtroPendientes = document.getElementById('filtro_estado_rhitso_pendientes') as HTMLSelectElement;
    if (filtroPendientes) {
        filtroPendientes.addEventListener('change', function(this: HTMLSelectElement) {
            if (!tablePendientes) return; // Si no hay tabla, salir
            
            const valorFiltro = this.value;
            
            if (valorFiltro === '') {
                tablePendientes.column(6).search('').draw();
            } else {
                tablePendientes.column(6).search(valorFiltro).draw();
            }
        });
    }
    
    // Filtro para tabla EXCLUIDOS
    const filtroExcluidos = document.getElementById('filtro_estado_rhitso_excluidos') as HTMLSelectElement;
    if (filtroExcluidos) {
        filtroExcluidos.addEventListener('change', function(this: HTMLSelectElement) {
            if (!tableExcluidos) return; // Si no hay tabla, salir
            
            const valorFiltro = this.value;
            
            if (valorFiltro === '') {
                tableExcluidos.column(6).search('').draw();
            } else {
                tableExcluidos.column(6).search(valorFiltro).draw();
            }
        });
    }
    
    /**
     * ===================================================================
     * ⚠️ NOTA IMPORTANTE - MIGRACIÓN A OPENPYXL (Octubre 2025)
     * ===================================================================
     * 
     * El código de exportación Excel que sigue (funciones extraerDatosTabla
     * y el event listener de exportExcelRhitso) YA NO SE EJECUTA.
     * 
     * RAZÓN: Se migró la exportación Excel del frontend (XLSX.js) al 
     * backend (openpyxl en views.py) para obtener mejor control de estilos
     * y formato profesional idéntico al Excel de inventario.
     * 
     * El botón "Exportar Excel" ahora es un enlace <a> que llama directamente
     * a la URL /servicio_tecnico/rhitso/exportar-excel/ (backend).
     * 
     * VENTAJAS DE LA MIGRACIÓN:
     * ✅ Control total sobre estilos (colores, fuentes, bordes, alineación)
     * ✅ Consistencia con el Excel de inventario (#366092 azul corporativo)
     * ✅ No requiere versión PRO de XLSX.js
     * ✅ Más estable y confiable (procesa en servidor)
     * ✅ Mismo formato profesional que otros reportes del sistema
     * 
     * Este código se mantiene comentado SOLO como referencia histórica.
     * Si necesitas modificar el Excel, edita la función exportar_excel_rhitso()
     * en servicio_tecnico/views.py (líneas 4878+).
     * ===================================================================
     */
    
    /**
     * PASO 3: FUNCIÓN AUXILIAR PARA EXTRAER DATOS DE LA TABLA
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta función lee todas las filas de una tabla HTML y extrae los datos
     * en formato array para poder exportarlos a Excel.
     * 
     * ACTUALIZADO: Ahora extrae 17 columnas incluyendo datos ocultos en data-attributes
     * 
     * ¿Cómo funciona?
     * 1. Recorre cada fila <tr> de la tabla
     * 2. Para cada fila, extrae el texto de cada celda <td> Y los atributos data-*
     * 3. Limpia el texto (quita espacios extra, HTML, etc.)
     * 4. Retorna un array de arrays: [[fila1], [fila2], ...]
     * 
     * Columnas extraídas (17 total):
     * 1. Servicio Cliente (data-orden-cliente)
     * 2. N° Serie (celda 0 - primera línea)
     * 3. Marca (celda 1)
     * 4. Modelo (celda 2)
     * 5. Fecha Ingreso a SIC (celda 3)
     * 6. Sucursal (celda 4)
     * 7. Estado General/SIC (celda 5)
     * 8. Estado RHITSO (celda 6 - primera línea)
     * 9. Owner (celda 6 - segunda línea)
     * 10. Incidencias (celda 7)
     * 11. Fecha Envío RHITSO (celda 8)
     * 12. Días Hábiles SIC (data-dias-sic)
     * 13. Días Hábiles RHITSO (data-dias-rhitso)
     * 14. Días en estatus (data-dias-estatus)
     * 15. Estado Proceso (data-estado-proceso)
     * 16. Fecha Último Comentario (data-fecha-comentario)
     * 17. Comentario (data-comentario)
     */
    
    function extraerDatosTabla(tablaId: string): string[][] {
        const datos: string[][] = [];
        const tabla = document.getElementById(tablaId);
        if (!tabla) return datos;
        
        const filas = tabla.querySelectorAll('tbody tr');
        
        filas.forEach((fila: Element) => {
            // Ignorar filas vacías (mensaje "No hay órdenes")
            if (fila.querySelector('td[colspan]')) {
                return;
            }
            
            const celdas = fila.querySelectorAll('td');
            const filaHTML = fila as HTMLTableRowElement;
            
            // Extraer datos de los atributos data-*
            const ordenCliente = filaHTML.dataset.ordenCliente || 'Sin orden';
            const diasSic = filaHTML.dataset.diasSic || '0';
            const diasRhitso = filaHTML.dataset.diasRhitso || '0';
            const diasEstatus = filaHTML.dataset.diasEstatus || '0';
            const estadoProceso = filaHTML.dataset.estadoProceso || 'Solo SIC';
            const fechaComentario = filaHTML.dataset.fechaComentario || 'Sin comentario';
            const comentario = filaHTML.dataset.comentario || 'Sin comentario';
            
            // Extraer datos de las celdas visibles
            // CELDA 0: N° Serie (extraer solo la primera línea, sin el texto pequeño)
            const numeroSerie = celdas[0].querySelector('strong')?.textContent.trim() || celdas[0].textContent.trim().split('\n')[0].trim();
            
            // CELDA 1: Marca
            const marca = celdas[1].textContent.trim();
            
            // CELDA 2: Modelo
            const modelo = celdas[2].textContent.trim();
            
            // CELDA 3: Fecha Ingreso
            const fechaIngreso = celdas[3].textContent.trim();
            
            // CELDA 4: Sucursal
            const sucursal = celdas[4].textContent.trim();
            
            // CELDA 5: Estado General (SIC) - extraer texto del badge
            const estadoGeneral = celdas[5].textContent.trim();
            
            // CELDA 6: Estado RHITSO y Owner
            // Dividir el contenido: primera línea es estado, segunda línea es owner
            const celda6Texto = celdas[6].textContent.trim();
            const celda6Lineas = celda6Texto.split('\n').map(l => l.trim()).filter(l => l);
            const estadoRhitso = celda6Lineas[0] || '';
            const owner = celda6Lineas.length > 1 ? celda6Lineas[1] : '';
            
            // CELDA 7: Incidencias
            const incidencias = celdas[7].textContent.trim();
            
            // CELDA 8: Fecha Envío RHITSO
            const fechaEnvio = celdas[8].textContent.trim();
            
            // Construir array de datos (17 columnas)
            const filaDatos = [
                ordenCliente,        // 1. Servicio Cliente
                numeroSerie,         // 2. N° Serie
                marca,               // 3. Marca
                modelo,              // 4. Modelo
                fechaIngreso,        // 5. Fecha Ingreso a SIC
                sucursal,            // 6. Sucursal
                estadoGeneral,       // 7. Estado General (SIC)
                estadoRhitso,        // 8. Estado RHITSO
                owner,               // 9. Owner
                incidencias,         // 10. Incidencias
                fechaEnvio,          // 11. Fecha Envío RHITSO
                diasSic,             // 12. Días Hábiles SIC
                diasRhitso,          // 13. Días Hábiles RHITSO
                diasEstatus,         // 14. Días en estatus
                estadoProceso,       // 15. Estado Proceso
                fechaComentario,     // 16. Fecha Último Comentario
                comentario           // 17. Comentario
            ];
            
            datos.push(filaDatos);
        });
        
        return datos;
    }
    
    /**
     * PASO 4: EXPORTAR TODO A EXCEL CON HOJAS SEPARADAS
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando el usuario hace click en "Exportar Excel", este código:
     * 1. Extrae datos de las 3 tablas (activos, pendientes, excluidos)
     * 2. Crea 3 hojas separadas en Excel (una por categoría)
     * 3. Aplica formato profesional inspirado en el Excel de inventario
     * 4. Usa la librería XLSX para crear un archivo Excel
     * 5. Descarga el archivo automáticamente
     * 
     * MEJORAS APLICADAS:
     * - Hojas separadas por categoría (Activos, Pendientes, Excluidos)
     * - Encabezados con estilo profesional (azul #366092, texto blanco)
     * - Colores por estado en cada fila
     * - Borders y alineación profesional
     * - Filtros automáticos y primera fila congelada
     */
    
    const btnExportExcel = document.getElementById('exportExcelRhitso');
    if (btnExportExcel) {
        btnExportExcel.addEventListener('click', function(this: HTMLElement) {
            const boton = this;
            const contenidoOriginal = boton.innerHTML;
            
            // Mostrar estado de carga
            boton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generando Excel...';
            (boton as HTMLButtonElement).disabled = true;
            boton.classList.add('loading');
            
            try {
                // Extraer datos de las 3 tablas
                const datosActivos = extraerDatosTabla('candidatosRhitsoTableActivos');
                const datosPendientes = extraerDatosTabla('candidatosRhitsoTablePendientes');
                const datosExcluidos = extraerDatosTabla('candidatosRhitsoTableExcluidos');
                
                // Encabezados de columna (17 columnas) - Reutilizable para todas las hojas
                const encabezados = [
                    'Servicio Cliente',
                    'N° Serie',
                    'Marca',
                    'Modelo',
                    'Fecha Ingreso a SIC',
                    'Sucursal',
                    'Estado General',
                    'Estado RHITSO',
                    'Owner',
                    'Incidencias',
                    'Fecha Envío RHITSO',
                    'Días Hábiles SIC',
                    'Días Hábiles RHITSO',
                    'Días en estatus',
                    'Estado Proceso',
                    'Fecha Último Comentario',
                    'Comentario'
                ];
                
                // ===============================================================
                // CREAR LIBRO DE EXCEL CON 3 HOJAS SEPARADAS
                // ===============================================================
                const libroTrabajo = XLSX.utils.book_new();
                
                // ===============================================================
                // FUNCIÓN AUXILIAR: CREAR Y FORMATEAR HOJA
                // ===============================================================
                function crearHojaFormateada(datos: string[][], nombreHoja: string, colorCategoria: string): any {
                // Preparar datos con encabezados
                const datosConEncabezados = [encabezados, ...datos];
                
                // Crear hoja
                const hoja = XLSX.utils.aoa_to_sheet(datosConEncabezados);
                
                // Configurar ancho de columnas (17 columnas)
                hoja['!cols'] = [
                    { wch: 30 }, // 1. Servicio Cliente
                    { wch: 15 }, // 2. N° Serie
                    { wch: 15 }, // 3. Marca
                    { wch: 20 }, // 4. Modelo
                    { wch: 18 }, // 5. Fecha Ingreso a SIC
                    { wch: 15 }, // 6. Sucursal
                    { wch: 18 }, // 7. Estado General
                    { wch: 35 }, // 8. Estado RHITSO (más ancho)
                    { wch: 12 }, // 9. Owner
                    { wch: 20 }, // 10. Incidencias
                    { wch: 18 }, // 11. Fecha Envío RHITSO
                    { wch: 16 }, // 12. Días Hábiles SIC
                    { wch: 18 }, // 13. Días Hábiles RHITSO
                    { wch: 15 }, // 14. Días en estatus
                    { wch: 18 }, // 15. Estado Proceso
                    { wch: 20 }, // 16. Fecha Último Comentario
                    { wch: 50 }  // 17. Comentario (más ancho)
                ];
                
                // ===============================================================
                // ESTILO PARA ENCABEZADOS (Inspirado en inventario)
                // ===============================================================
                const estiloEncabezado = {
                    font: { 
                        bold: true, 
                        color: { rgb: "FFFFFF" },  // Blanco
                        sz: 11,
                        name: 'Calibri'
                    },
                    fill: { 
                        fgColor: { rgb: "366092" }  // Azul profesional (mismo que inventario)
                    },
                    alignment: { 
                        horizontal: "center", 
                        vertical: "center",
                        wrapText: true 
                    },
                    border: {
                        top: { style: "thin", color: { rgb: "000000" } },
                        bottom: { style: "thin", color: { rgb: "000000" } },
                        left: { style: "thin", color: { rgb: "000000" } },
                        right: { style: "thin", color: { rgb: "000000" } }
                    }
                };
                
                // Aplicar estilo a encabezados (fila 1)
                const rango = XLSX.utils.decode_range(hoja['!ref']);
                for (let C = rango.s.c; C <= rango.e.c; ++C) {
                    const direccion = XLSX.utils.encode_cell({ r: 0, c: C });
                    if (!hoja[direccion]) continue;
                    hoja[direccion].s = estiloEncabezado;
                }
                
                // ===============================================================
                // APLICAR ESTILOS A FILAS DE DATOS
                // ===============================================================
                for (let R = rango.s.r + 1; R <= rango.e.r; ++R) {
                    // Obtener Estado Proceso (columna 15, índice 14)
                    const celdaEstadoProceso = hoja[XLSX.utils.encode_cell({ r: R, c: 14 })];
                    const estadoProceso = celdaEstadoProceso ? celdaEstadoProceso.v : '';
                    
                    // Obtener Días en estatus (columna 14, índice 13)
                    const celdaDiasEstatus = hoja[XLSX.utils.encode_cell({ r: R, c: 13 })];
                    const diasEstatus = celdaDiasEstatus ? parseInt(celdaDiasEstatus.v) : 0;
                    
                    // Determinar color de fondo según Estado Proceso y Días
                    let colorFondo = 'FFFFFF'; // Blanco por defecto
                    let colorTexto = '000000'; // Negro por defecto
                    
                    // Colores según estado (inspirados en inventario pero adaptados a RHITSO)
                    if (estadoProceso === 'Completado') {
                        colorFondo = 'D4EDDA'; // Verde claro suave
                        colorTexto = '155724';
                    } else if (estadoProceso === 'En RHITSO') {
                        colorFondo = 'FFF3CD'; // Amarillo claro suave
                        colorTexto = '856404';
                    } else if (estadoProceso === 'Solo SIC') {
                        colorFondo = 'F8F9FA'; // Gris muy claro
                        colorTexto = '495057';
                    }
                    
                    // Si lleva más de 5 días sin actualizar, marcar en rojo claro (urgente)
                    if (diasEstatus > 5 && estadoProceso !== 'Completado') {
                        colorFondo = 'F8D7DA'; // Rojo claro suave
                        colorTexto = '721C24';
                    }
                    
                    // Aplicar estilo a toda la fila
                    for (let C = rango.s.c; C <= rango.e.c; ++C) {
                        const direccion = XLSX.utils.encode_cell({ r: R, c: C });
                        if (!hoja[direccion]) continue;
                        
                        hoja[direccion].s = {
                            font: {
                                name: 'Calibri',
                                sz: 10,
                                color: { rgb: colorTexto }
                            },
                            fill: { fgColor: { rgb: colorFondo } },
                            alignment: { 
                                vertical: "top",
                                wrapText: true,
                                // Alineación especial para columnas numéricas
                                horizontal: (C >= 11 && C <= 13) ? "center" : "left"
                            },
                            border: {
                                top: { style: "thin", color: { rgb: "DEE2E6" } },
                                bottom: { style: "thin", color: { rgb: "DEE2E6" } },
                                left: { style: "thin", color: { rgb: "DEE2E6" } },
                                right: { style: "thin", color: { rgb: "DEE2E6" } }
                            }
                        };
                        
                        // Formato numérico para columnas de días
                        if (C >= 11 && C <= 13) {
                            hoja[direccion].t = 'n'; // Tipo numérico
                        }
                    }
                }
                
                // Congelar primera fila (encabezados)
                hoja['!freeze'] = { xSplit: 0, ySplit: 1 };
                
                // Aplicar filtros automáticos a los encabezados
                hoja['!autofilter'] = { ref: XLSX.utils.encode_range(rango) };
                
                return hoja;
            }
            
            // ===============================================================
            // CREAR LAS 3 HOJAS
            // ===============================================================
            
            // HOJA 1: ACTIVOS (Verde)
            if (datosActivos.length > 0) {
                const hojaActivos = crearHojaFormateada(datosActivos, 'Activos', '28a745');
                XLSX.utils.book_append_sheet(libroTrabajo, hojaActivos, `Activos (${datosActivos.length})`);
            }
            
            // HOJA 2: PENDIENTES (Amarillo)
            if (datosPendientes.length > 0) {
                const hojaPendientes = crearHojaFormateada(datosPendientes, 'Pendientes', 'ffc107');
                XLSX.utils.book_append_sheet(libroTrabajo, hojaPendientes, `Pendientes (${datosPendientes.length})`);
            }
            
            // HOJA 3: EXCLUIDOS (Gris)
            if (datosExcluidos.length > 0) {
                const hojaExcluidos = crearHojaFormateada(datosExcluidos, 'Excluidos', '6c757d');
                XLSX.utils.book_append_sheet(libroTrabajo, hojaExcluidos, `Excluidos (${datosExcluidos.length})`);
            }
            
            // ===============================================================
            // DESCARGAR ARCHIVO EXCEL
            // ===============================================================
            
            // Generar nombre de archivo con fecha actual
            const fechaHoy = new Date().toISOString().split('T')[0];
            const nombreArchivo = `Candidatos_RHITSO_${fechaHoy}.xlsx`;
            
            // Descargar archivo
            XLSX.writeFile(libroTrabajo, nombreArchivo);
            
            // Calcular totales
            const totalRegistros = datosActivos.length + datosPendientes.length + datosExcluidos.length;
            const totalHojas = (datosActivos.length > 0 ? 1 : 0) + 
                              (datosPendientes.length > 0 ? 1 : 0) + 
                              (datosExcluidos.length > 0 ? 1 : 0);
            
            // Mostrar mensaje de éxito detallado (estilo inventario)
            alert(`✅ Excel generado exitosamente\n\n` +
                  `📄 Archivo: ${nombreArchivo}\n\n` +
                  `📊 Resumen:\n` +
                  `• Total de registros: ${totalRegistros}\n` +
                  `• Hojas creadas: ${totalHojas}\n` +
                  `  - Activos: ${datosActivos.length}\n` +
                  `  - Pendientes: ${datosPendientes.length}\n` +
                  `  - Excluidos: ${datosExcluidos.length}\n\n` +
                  `🎨 Formato aplicado:\n` +
                  `• Diseño profesional con colores por estado\n` +
                  `• Hojas separadas por categoría\n` +
                  `• Filtros automáticos en encabezados\n` +
                  `• Primera fila congelada en cada hoja\n` +
                  `• 17 columnas con información completa`);
                
            } catch (error) {
                console.error('Error al exportar Excel:', error);
                const errorMsg = error instanceof Error ? error.message : 'Error desconocido';
                alert('❌ Error al generar el archivo Excel.\n\n' +
                      'Detalles: ' + errorMsg + '\n\n' +
                      'Por favor, inténtelo de nuevo o contacte a soporte.');
            } finally {
                // Restaurar botón
                boton.innerHTML = contenidoOriginal;
                (boton as HTMLButtonElement).disabled = false;
                boton.classList.remove('loading');
            }
        });
    }
    
    /**
     * PASO 5: ANIMACIONES DE ENTRADA PARA STATS CARDS
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este código hace que las tarjetas de estadísticas aparezcan
     * con una animación suave cuando se carga la página.
     * 
     * ¿Cómo funciona?
     * 1. Usa Intersection Observer API (detecta cuando un elemento es visible)
     * 2. Cuando una tarjeta entra en el viewport (área visible), agrega una clase CSS
     * 3. La clase CSS activa una animación definida en dashboard_rhitso.css
     */
    
    const observerOptions = {
        threshold: 0.1, // Activar cuando el 10% del elemento sea visible
        rootMargin: '0px 0px -50px 0px' // Margen para detectar antes de que sea completamente visible
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target); // Dejar de observar después de animar
            }
        });
    }, observerOptions);
    
    // Observar todas las tarjetas de estadísticas
    document.querySelectorAll('.stat-card').forEach(card => {
        observer.observe(card);
    });
    
    /**
     * PASO 6: LOGS DE DEPURACIÓN (SOLO DESARROLLO)
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Estos console.log() ayudan a depurar el código durante desarrollo.
     * Muestra información útil en la Consola del navegador (F12).
     * 
     * Puedes comentar o eliminar estos logs en producción.
     */
    
    console.log('✅ Dashboard RHITSO inicializado correctamente');
    console.log('📊 DataTables configuradas:', {
        activos: tableActivos ? tableActivos.rows().count() : 0,
        pendientes: tablePendientes ? tablePendientes.rows().count() : 0,
        excluidos: tableExcluidos ? tableExcluidos.rows().count() : 0
    });
});
