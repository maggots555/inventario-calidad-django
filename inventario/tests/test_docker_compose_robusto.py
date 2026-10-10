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
        self.nginx = (RAIZ / "docker" / "nginx.conf").read_text(encoding="utf-8")

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

    def test_nginx_solo_escucha_en_localhost(self):
        """El 8080 no queda abierto en todas las tarjetas de red."""
        self.assertIn('127.0.0.1:${SIGMA_HTTP_PORT:-8080}:80', self.compose)

    def test_nginx_no_cree_la_ip_que_manda_el_visitante(self):
        """La IP sale de Cloudflare o del socket, no de X-Forwarded-For."""
        self.assertIn('$http_cf_connecting_ip', self.nginx)
        self.assertIn('proxy_set_header X-Real-IP $sigma_real_ip;', self.nginx)
        self.assertIn('proxy_set_header X-Forwarded-For $sigma_real_ip;', self.nginx)
        self.assertIn('proxy_set_header X-Forwarded-Host $host;', self.nginx)
        self.assertNotIn('$proxy_add_x_forwarded_for', self.nginx)
        self.assertNotIn('$http_x_forwarded_proto', self.nginx)
        self.assertNotIn('$http_x_forwarded_host', self.nginx)

    def test_media_no_se_entrega_sin_pasar_por_django(self):
        """/media/ va a Gunicorn. El disco solo se abre por la ruta interna."""
        self.assertIn('location /media-interno/', self.nginx)
        self.assertIn('internal;', self.nginx)
        self.assertNotIn('location /media/ {\n        alias /app/media/;', self.nginx)
