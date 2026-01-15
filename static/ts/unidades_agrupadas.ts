/**
 * TypeScript para Unidades Agrupadas - Vista Expandible/Colapsable
 * =================================================================
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * --------------------------------
 * Este archivo maneja la funcionalidad de expandir y colapsar grupos de unidades
 * en la vista de inventario. Usa Bootstrap Collapse y agrega animaciones personalizadas.
 * 
 * CARACTERÍSTICAS:
 * - Detecta clics en filas de grupos
 * - Rota el icono de flecha al expandir/colapsar
 * - Actualiza el atributo aria-expanded para accesibilidad
 * - Usa eventos nativos de Bootstrap Collapse
 * 
 * CONCEPTOS DE TYPESCRIPT QUE SE USAN AQUÍ:
 * - Type annotations: Especificamos tipos de variables (HTMLElement, Event, etc.)
 * - Type assertions: Usamos 'as HTMLElement' para convertir tipos
 * - Null checks: Verificamos que los elementos existan antes de usarlos
 * - Arrow functions: Funciones modernas de JavaScript (=>)
 * - Event listeners: Escuchamos eventos del DOM
 * 
 * CÓMO FUNCIONA:
 * 1. Espera a que el DOM esté completamente cargado
 * 2. Encuentra todos los elementos con data-bs-toggle="collapse"
 * 3. Agrega event listeners a cada elemento
 * 4. Cuando se hace clic, actualiza el icono y el estado aria-expanded
 */

/**
 * Interface para elementos de Bootstrap Collapse
 * 
 * EXPLICACIÓN:
 * Define la estructura de los elementos que tienen funcionalidad de collapse.
 * Esto ayuda a TypeScript a validar que estamos usando las propiedades correctas.
 */
interface CollapseElement extends HTMLElement {
    getAttribute(name: string): string | null;
}

/**
 * Inicializa la funcionalidad de grupos expandibles
 * 
 * EXPLICACIÓN:
 * Esta función se ejecuta cuando la página termina de cargar y configura
 * todos los event listeners necesarios para la funcionalidad de expandir/colapsar.
 */
function inicializarGruposExpandibles(): void {
    // Buscar todos los elementos que tienen collapse (botones y filas)
    const gruposExpandibles: NodeListOf<CollapseElement> = document.querySelectorAll('[data-bs-toggle="collapse"]');
    
    // Contador para debug (opcional)
    console.log(`[Unidades Agrupadas] Se encontraron ${gruposExpandibles.length} grupos expandibles`);
    
    // Iterar sobre cada elemento expandible
    gruposExpandibles.forEach((elemento: CollapseElement) => {
        // Agregar event listener al hacer clic
        elemento.addEventListener('click', function(event: Event): void {
            // Prevenir comportamiento por defecto si es necesario
            // event.preventDefault(); // Comentado porque Bootstrap ya lo maneja
            
            // Obtener el ID del target (elemento que se va a expandir/colapsar)
            const targetId: string | null = this.getAttribute('data-bs-target');
            
            if (!targetId) {
                console.warn('[Unidades Agrupadas] No se encontró data-bs-target');
                return;
            }
            
            // Buscar el elemento target
            const target: HTMLElement | null = document.querySelector(targetId);
            
            if (!target) {
                console.warn(`[Unidades Agrupadas] No se encontró el elemento ${targetId}`);
                return;
            }
            
            // Buscar la fila principal del grupo (puede ser el elemento actual o un ancestro)
            const row: HTMLElement | null = this.closest('tr.grupo-principal');
            
            if (!row) {
                console.warn('[Unidades Agrupadas] No se encontró la fila del grupo');
                return;
            }
            
            /**
             * Event listener: cuando el collapse se muestra completamente
             * 
             * EXPLICACIÓN:
             * Bootstrap dispara el evento 'shown.bs.collapse' cuando termina
             * la animación de expandir. Aquí actualizamos el atributo aria-expanded.
             */
            target.addEventListener('shown.bs.collapse', function(): void {
                row.setAttribute('aria-expanded', 'true');
                console.log(`[Unidades Agrupadas] Grupo expandido: ${targetId}`);
            }, { once: true }); // { once: true } = ejecutar solo una vez
            
            /**
             * Event listener: cuando el collapse se oculta completamente
             * 
             * EXPLICACIÓN:
             * Bootstrap dispara el evento 'hidden.bs.collapse' cuando termina
             * la animación de colapsar. Aquí actualizamos el atributo aria-expanded.
             */
            target.addEventListener('hidden.bs.collapse', function(): void {
                row.setAttribute('aria-expanded', 'false');
                console.log(`[Unidades Agrupadas] Grupo colapsado: ${targetId}`);
            }, { once: true });
        });
    });
}

/**
 * Event listener para DOMContentLoaded
 * 
 * EXPLICACIÓN:
 * Este evento se dispara cuando el HTML está completamente cargado y parseado.
 * Es el momento ideal para inicializar funcionalidades que dependen del DOM.
 * 
 * NOTA IMPORTANTE:
 * No usamos jQuery aquí, solo JavaScript/TypeScript vanilla para mejor rendimiento.
 */
document.addEventListener('DOMContentLoaded', (): void => {
    console.log('[Unidades Agrupadas] Inicializando vista de grupos expandibles...');
    inicializarGruposExpandibles();
});

/**
 * Exportar funciones si se usa en módulos (opcional)
 * 
 * EXPLICACIÓN:
 * Si en el futuro queremos usar este código como módulo de TypeScript,
 * podemos descomentar esta línea para exportar la función principal.
 */
// export { inicializarGruposExpandibles };
