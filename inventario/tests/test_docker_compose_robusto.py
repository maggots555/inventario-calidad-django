"""
Candados del compose de SIGMA para que un cambio futuro no reabra huecos.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No levanta Docker. Solo lee compose.yaml y el script de respaldo
y comprueba tres reglas que ya nos mordieron o podían morder:
la cola de Celery no se borra si Redis se llena, un volcado roto
no se sube a Drive, y el túnel no sigue la etiqueta latest.
"""

from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]


class ComposeDockerRobustoTests(SimpleTestCase):
    """Lee los archivos de Docker y exige las reglas de robustez."""

    def setUp(self):
        """Carga el texto de compose y del respaldo una vez por test."""
        self.compose = (RAIZ / "compose.yaml").read_text(encoding="utf-8")
        self.respaldo = (RAIZ / "docker" / "backup_sigma.sh").read_text(encoding="utf-8")

    def test_redis_no_borra_la_cola(self):
        """volatile-lru conserva la cola; allkeys-lru podía borrarla."""
        self.assertIn('"--maxmemory-policy", "volatile-lru"', self.compose)
        self.assertNotIn('"--maxmemory-policy", "allkeys-lru"', self.compose)

    def test_logs_de_docker_tienen_tope(self):
        """Cada contenedor guarda como mucho unos 30 MB de log."""
        self.assertIn('max-size: "10m"', self.compose)
        self.assertIn('max-file: "3"', self.compose)

    def test_cloudflared_no_usa_latest(self):
        """El túnel queda en una versión concreta."""
        self.assertNotIn("cloudflare/cloudflared:latest", self.compose)
        self.assertIn("cloudflare/cloudflared:2026.10.0", self.compose)

    def test_celery_y_beat_tienen_healthcheck(self):
        """El worker contesta ping y Beat vigila su pidfile."""
        self.assertIn("inspect ping", self.compose)
        self.assertIn("celerybeat.pid", self.compose)

    def test_respaldo_no_sube_un_volcado_roto(self):
        """Un .sql.gz que no abre se borra antes de rclone."""
        self.assertIn("gzip -t", self.respaldo)
        self.assertIn('rm -f "$destino"', self.respaldo)
        self.assertIn('rm -f "$archivo"', self.respaldo)
