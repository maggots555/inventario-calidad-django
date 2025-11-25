#!/usr/bin/env python3
"""
Script para generar certificados SSL autofirmados para desarrollo local
Esto permite usar HTTPS en el servidor de desarrollo de Django
"""

import subprocess
import sys
import os
from pathlib import Path

def generar_certificado_ssl():
    """
    Genera un certificado SSL autofirmado usando OpenSSL
    """
    
    # Crear directorio para certificados
    ssl_dir = Path("ssl_certs")
    ssl_dir.mkdir(exist_ok=True)
    
    # Archivos de certificado
    key_file = ssl_dir / "server.key"
    cert_file = ssl_dir / "server.crt"
    
    # Comando OpenSSL para generar certificado autofirmado
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:4096", 
        "-keyout", str(key_file),
        "-out", str(cert_file),
        "-days", "365", "-nodes",
        "-subj", "/C=MX/ST=Estado/L=Ciudad/O=Desarrollo/CN=192.168.100.3"
    ]
    
    try:
        print("Generando certificado SSL...")
        subprocess.run(cmd, check=True)
        print(f"✅ Certificado generado exitosamente:")
        print(f"   - Clave privada: {key_file}")
        print(f"   - Certificado: {cert_file}")
        print()
        print("Para usar HTTPS, ejecuta:")
        print(f"python manage.py runsslserver 0.0.0.0:8443 --certificate {cert_file} --key {key_file}")
        print()
        print("Luego accede desde tu celular a: https://192.168.100.3:8443")
        print("(Acepta el certificado autofirmado cuando te lo pida)")
        
    except subprocess.CalledProcessError:
        print("❌ Error: OpenSSL no está instalado o no está en el PATH")
        print()
        print("Alternativas:")
        print("1. Instalar OpenSSL desde: https://slproweb.com/products/Win32OpenSSL.html")
        print("2. Usar django-sslserver: pip install django-sslserver")
        print("3. Usar entrada manual en lugar del scanner")
        
    except FileNotFoundError:
        print("❌ Error: OpenSSL no encontrado")
        print("Instala OpenSSL o usa una alternativa")

def instalar_django_sslserver():
    """
    Instala django-sslserver como alternativa
    """
    try:
        print("Instalando django-sslserver...")
        subprocess.run([sys.executable, "-m", "pip", "install", "django-sslserver"], check=True)
        print("✅ django-sslserver instalado")
        print()
        print("Agrega 'sslserver' a INSTALLED_APPS en settings.py")
        print("Luego ejecuta: python manage.py runsslserver 0.0.0.0:8443")
        print("Accede desde tu celular a: https://192.168.100.3:8443")
        
    except subprocess.CalledProcessError:
        print("❌ Error al instalar django-sslserver")

if __name__ == "__main__":
    print("Configuración SSL para usar scanner de cámara en Android")
    print("=" * 55)
    
    print("\nOpción 1: Generar certificado con OpenSSL")
    generar_certificado_ssl()
    
    print("\n" + "="*55)
    print("\nOpción 2: Usar django-sslserver (más fácil)")
    instalar_django_sslserver()