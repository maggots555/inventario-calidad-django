"""
Script de prueba para verificar configuración de email

EXPLICACIÓN PARA PRINCIPIANTES:
Este script prueba si tu configuración de email en .env está correcta
y si Django puede conectarse al servidor SMTP de Gmail.
"""

import os
import django

# Configurar Django para poder usar sus funciones
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email_configuration():
    """Prueba la configuración de email"""
    
    print("=" * 60)
    print("🔍 VERIFICANDO CONFIGURACIÓN DE EMAIL")
    print("=" * 60)
    
    # Mostrar configuración actual (sin mostrar la contraseña completa)
    print(f"\n📧 Configuración detectada:")
    print(f"  - EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"  - EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"  - EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"  - EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"  - EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'NO CONFIGURADO'}")
    print(f"  - DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    
    # Verificar que todos los campos necesarios están configurados
    if not settings.EMAIL_HOST_USER:
        print("\n❌ ERROR: EMAIL_HOST_USER no está configurado en .env")
        return False
    
    if not settings.EMAIL_HOST_PASSWORD:
        print("\n❌ ERROR: EMAIL_HOST_PASSWORD no está configurado en .env")
        return False
    
    print("\n✅ Configuración básica completa")
    
    # Intentar enviar un email de prueba
    print("\n📨 Intentando enviar email de prueba...")
    try:
        send_mail(
            subject='Prueba de Configuración - Sistema Django',
            message='Este es un email de prueba para verificar que la configuración SMTP funciona correctamente.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],  # Se envía a ti mismo
            fail_silently=False,
        )
        print("✅ ¡Email enviado correctamente!")
        print(f"   Revisa tu bandeja de entrada: {settings.EMAIL_HOST_USER}")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR al enviar email:")
        print(f"   {type(e).__name__}: {str(e)}")
        print("\n💡 Posibles causas:")
        print("   1. La contraseña de aplicación de Gmail es incorrecta")
        print("   2. No has activado la verificación en 2 pasos en Gmail")
        print("   3. No has generado una 'Contraseña de aplicación' en Gmail")
        print("   4. Tu conexión a internet está bloqueando el puerto 587")
        print("   5. Gmail está bloqueando el acceso (revisa tu email por alertas de seguridad)")
        return False

if __name__ == '__main__':
    test_email_configuration()
