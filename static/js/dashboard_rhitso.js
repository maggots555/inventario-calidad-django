/**
 * DASHBOARD_RHITSO.JS
 * ===========================================================================
 * JavaScript para el Dashboard RHITSO
 * 
 * PARA PRINCIPIANTES - ¿Qué hace este archivo?
 * - Inicializa DataTables para las 3 pestañas (activos, pendientes, excluidos)
 * - Implementa filtros dinámicos por estado RHITSO
 * - Maneja la exportación a Excel de todas las órdenes
 * - Maneja la generación del reporte RHITSO (solo órdenes "En RHITSO")
 * - Agrega estados de carga a los botones durante operaciones
 * 
 * EXPLICACIÓN TÉCNICA:
 * - DOMContentLoaded: Espera a que el HTML esté completamente cargado
 * - DataTables: Librería jQuery para tablas interactivas (ordenamiento, búsqueda, paginación)
 * - XLSX: Librería para generar archivos Excel desde JavaScript
 * ===========================================================================
 */

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
                render: function(data, type, row) {
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
function tablaConDatos(tablaId) {
    const tabla = document.getElementById(tablaId);
    const tbody = tabla.querySelector('tbody');
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
    document.getElementById('filtro_estado_rhitso_activos').addEventListener('change', function() {
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
    
    // Filtro para tabla PENDIENTES
    document.getElementById('filtro_estado_rhitso_pendientes').addEventListener('change', function() {
        if (!tablePendientes) return; // Si no hay tabla, salir
        
        const valorFiltro = this.value;
        
        if (valorFiltro === '') {
            tablePendientes.column(6).search('').draw();
        } else {
            tablePendientes.column(6).search(valorFiltro).draw();
        }
    });
    
    // Filtro para tabla EXCLUIDOS
    document.getElementById('filtro_estado_rhitso_excluidos').addEventListener('change', function() {
        if (!tableExcluidos) return; // Si no hay tabla, salir
        
        const valorFiltro = this.value;
        
        if (valorFiltro === '') {
            tableExcluidos.column(6).search('').draw();
        } else {
            tableExcluidos.column(6).search(valorFiltro).draw();
        }
    });
    
    /**
     * PASO 3: FUNCIÓN AUXILIAR PARA EXTRAER DATOS DE LA TABLA
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Esta función lee todas las filas de una tabla HTML y extrae los datos
     * en formato array para poder exportarlos a Excel.
     * 
     * ¿Cómo funciona?
     * 1. Recorre cada fila <tr> de la tabla
     * 2. Para cada fila, extrae el texto de cada celda <td>
     * 3. Limpia el texto (quita espacios extra, HTML, etc.)
     * 4. Retorna un array de arrays: [[fila1], [fila2], ...]
     */
    
    function extraerDatosTabla(tablaId) {
        const datos = [];
        const tabla = document.getElementById(tablaId);
        const filas = tabla.querySelectorAll('tbody tr');
        
        filas.forEach(fila => {
            // Ignorar filas vacías (mensaje "No hay órdenes")
            if (fila.querySelector('td[colspan]')) {
                return;
            }
            
            const celdas = fila.querySelectorAll('td');
            const filaDatos = [];
            
            // Iterar sobre todas las celdas excepto la última (Acciones)
            for (let i = 0; i < celdas.length - 1; i++) {
                const celda = celdas[i];
                
                // Extraer solo el texto, eliminando HTML
                let texto = celda.textContent.trim();
                
                // Limpiar espacios múltiples
                texto = texto.replace(/\s+/g, ' ');
                
                filaDatos.push(texto);
            }
            
            datos.push(filaDatos);
        });
        
        return datos;
    }
    
    /**
     * PASO 4: EXPORTAR TODO A EXCEL
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando el usuario hace click en "Exportar Excel", este código:
     * 1. Extrae datos de las 3 tablas (activos, pendientes, excluidos)
     * 2. Combina todos los datos en un solo array
     * 3. Usa la librería XLSX para crear un archivo Excel
     * 4. Descarga el archivo automáticamente
     * 
     * XLSX.utils.aoa_to_sheet():
     * - aoa = "Array of Arrays" (array de arrays)
     * - Convierte datos de JavaScript a formato Excel
     */
    
    document.getElementById('exportExcelRhitso').addEventListener('click', function() {
        const boton = this;
        const contenidoOriginal = boton.innerHTML;
        
        // Mostrar estado de carga
        boton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generando Excel...';
        boton.disabled = true;
        boton.classList.add('loading');
        
        try {
            // Extraer datos de las 3 tablas
            const datosActivos = extraerDatosTabla('candidatosRhitsoTableActivos');
            const datosPendientes = extraerDatosTabla('candidatosRhitsoTablePendientes');
            const datosExcluidos = extraerDatosTabla('candidatosRhitsoTableExcluidos');
            
            // Combinar todos los datos
            const todosDatos = [
                // Encabezados de columna
                [
                    'Servicio',
                    'N° Serie',
                    'Marca',
                    'Modelo',
                    'Fecha Ingreso',
                    'Sucursal',
                    'Estado SIC',
                    'Estado RHITSO',
                    'Incidencias',
                    'Fecha Envío',
                    'Tiempo',
                    'Días sin actualizar'
                ],
                // Datos de activos
                ...datosActivos,
                // Separador
                [''],
                ['--- PENDIENTES ---'],
                [''],
                // Datos de pendientes
                ...datosPendientes,
                // Separador
                [''],
                ['--- EXCLUIDOS ---'],
                [''],
                // Datos de excluidos
                ...datosExcluidos
            ];
            
            // Crear libro de Excel
            const libroTrabajo = XLSX.utils.book_new();
            const hojaTrabajo = XLSX.utils.aoa_to_sheet(todosDatos);
            
            // Configurar ancho de columnas
            hojaTrabajo['!cols'] = [
                { wch: 30 }, // Servicio
                { wch: 15 }, // N° Serie
                { wch: 15 }, // Marca
                { wch: 20 }, // Modelo
                { wch: 12 }, // Fecha Ingreso
                { wch: 15 }, // Sucursal
                { wch: 15 }, // Estado SIC
                { wch: 25 }, // Estado RHITSO
                { wch: 20 }, // Incidencias
                { wch: 12 }, // Fecha Envío
                { wch: 25 }, // Tiempo
                { wch: 18 }  // Días sin actualizar
            ];
            
            // Agregar hoja al libro
            XLSX.utils.book_append_sheet(libroTrabajo, hojaTrabajo, "Candidatos RHITSO");
            
            // Generar nombre de archivo con fecha actual
            const fechaHoy = new Date().toISOString().split('T')[0];
            const nombreArchivo = `Candidatos_RHITSO_${fechaHoy}.xlsx`;
            
            // Descargar archivo
            XLSX.writeFile(libroTrabajo, nombreArchivo);
            
            // Mostrar mensaje de éxito
            alert(`✅ Excel generado exitosamente: ${nombreArchivo}`);
            
        } catch (error) {
            console.error('Error al exportar Excel:', error);
            alert('❌ Error al generar el archivo Excel. Por favor, inténtelo de nuevo.');
        } finally {
            // Restaurar botón
            boton.innerHTML = contenidoOriginal;
            boton.disabled = false;
            boton.classList.remove('loading');
        }
    });
    
    /**
     * PASO 5: GENERAR REPORTE RHITSO (SOLO ÓRDENES "EN RHITSO")
     * ===================================================================
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este reporte es más específico: solo incluye equipos que están
     * actualmente en proceso RHITSO (enviados pero no regresados).
     * 
     * ¿Cómo identificamos equipos "En RHITSO"?
     * - Tienen fecha de envío a RHITSO
     * - La columna "Tiempo" muestra días en RHITSO (badge con color)
     * - El badge NO dice "Solo SIC" ni "Completado"
     */
    
    document.getElementById('reporteRhitso').addEventListener('click', function() {
        const boton = this;
        const contenidoOriginal = boton.innerHTML;
        
        // Mostrar estado de carga
        boton.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generando Reporte...';
        boton.disabled = true;
        boton.classList.add('loading');
        
        try {
            // Extraer solo datos de ACTIVOS (los que están en proceso)
            const datosActivos = extraerDatosTabla('candidatosRhitsoTableActivos');
            
            // Filtrar solo los que tienen días en RHITSO (no cero)
            // Esto se identifica porque la columna "Tiempo" contiene "RHITSO"
            const datosEnRhitso = datosActivos.filter(fila => {
                const columnaTiempo = fila[10]; // Índice de la columna "Tiempo"
                return columnaTiempo.includes('RHITSO') && !columnaTiempo.includes('Completado');
            });
            
            if (datosEnRhitso.length === 0) {
                alert('⚠️ No hay equipos con estado "En RHITSO" para generar el reporte.');
                return;
            }
            
            // Preparar datos para Excel
            const datosReporte = [
                // Encabezados
                [
                    'Servicio',
                    'N° Serie',
                    'Marca',
                    'Modelo',
                    'Fecha Ingreso',
                    'Sucursal',
                    'Estado SIC',
                    'Estado RHITSO',
                    'Incidencias',
                    'Fecha Envío',
                    'Tiempo',
                    'Días sin actualizar'
                ],
                // Datos filtrados
                ...datosEnRhitso
            ];
            
            // Crear libro de Excel
            const libroTrabajo = XLSX.utils.book_new();
            const hojaTrabajo = XLSX.utils.aoa_to_sheet(datosReporte);
            
            // Configurar ancho de columnas
            hojaTrabajo['!cols'] = [
                { wch: 30 }, // Servicio
                { wch: 15 }, // N° Serie
                { wch: 15 }, // Marca
                { wch: 20 }, // Modelo
                { wch: 12 }, // Fecha Ingreso
                { wch: 15 }, // Sucursal
                { wch: 15 }, // Estado SIC
                { wch: 25 }, // Estado RHITSO
                { wch: 20 }, // Incidencias
                { wch: 12 }, // Fecha Envío
                { wch: 25 }, // Tiempo
                { wch: 18 }  // Días sin actualizar
            ];
            
            // Agregar hoja al libro
            XLSX.utils.book_append_sheet(libroTrabajo, hojaTrabajo, "Reporte RHITSO");
            
            // Generar nombre de archivo con fecha actual
            const fechaHoy = new Date().toISOString().split('T')[0];
            const nombreArchivo = `Reporte_RHITSO_${fechaHoy}.xlsx`;
            
            // Descargar archivo
            XLSX.writeFile(libroTrabajo, nombreArchivo);
            
            // Mostrar mensaje de éxito
            alert(`✅ Reporte generado exitosamente: ${nombreArchivo}\n${datosEnRhitso.length} equipos en RHITSO`);
            
        } catch (error) {
            console.error('Error al generar reporte:', error);
            alert('❌ Error al generar el reporte RHITSO. Por favor, inténtelo de nuevo.');
        } finally {
            // Restaurar botón
            boton.innerHTML = contenidoOriginal;
            boton.disabled = false;
            boton.classList.remove('loading');
        }
    });
    
    /**
     * PASO 6: ANIMACIONES DE ENTRADA PARA STATS CARDS
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
     * PASO 7: LOGS DE DEPURACIÓN (SOLO DESARROLLO)
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
