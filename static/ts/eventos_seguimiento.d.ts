/**
 * Tipos globales para el módulo de eventos de seguimiento del cliente.
 */

interface EventosSeguimientoGlobal {
    registrarEvento(
        tipo: string,
        metadata?: Record<string, unknown>,
        unaVezPorSesion?: boolean,
    ): void;
    obtenerSessionId(): string;
}

interface Window {
    EventosSeguimiento?: EventosSeguimientoGlobal;
}
