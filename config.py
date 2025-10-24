import os

# Configuración de seguridad
SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-combustibles-2024'

# Configuración de la aplicación
DEBUG = True

# Configuración de usuarios administradores
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Configuración de base de datos
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///combustibles.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Configuración de archivos
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
