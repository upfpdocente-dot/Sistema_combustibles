import os

# Configuración de seguridad
SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-combustibles-2024'

# Configuración de la aplicación
DEBUG = True

# Configuración de usuarios administradores
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'