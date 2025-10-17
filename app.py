from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import csv
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from io import StringIO, BytesIO

# Crear la aplicación Flask primero
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_sistema_combustibles_2024')

# ================= CONFIGURACIÓN DE BASE DE DATOS - CON MÚLTIPLES FALLBACKS =================
def get_database_url():
    # Opción 1: PostgreSQL de Render (producción)
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Corregir formato de URL si es necesario
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        print(f"✅ Usando PostgreSQL: {database_url.split('@')[1] if '@' in database_url else database_url}")
        return database_url
    
    # Opción 2: SQLite local (para desarrollo/emergencia)
    print("⚠️  Usando SQLite (modo emergencia)")
    return 'sqlite:///combustibles.db'

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración mejorada para PostgreSQL
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql://'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 10,
            'application_name': 'sistema_combustibles'
        }
    }

# CONFIGURACIONES FALTANTES - AGREGADAS
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx', 'xls'}

# Inicializar SQLAlchemy después de configurar la app
db = SQLAlchemy(app)

# Crear directorio de uploads si no existe
try:
    os.makedirs('uploads', exist_ok=True)
except:
    pass

# ================= MODELOS =================
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    funcionario = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), default='user')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class RegistroCombustible(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    razon_social = db.Column(db.String(200), nullable=False)
    zona = db.Column(db.String(100), nullable=False)
    provincia = db.Column(db.String(100), nullable=False)
    municipio = db.Column(db.String(100), nullable=False)
    do_do_plus = db.Column(db.Integer, default=0)
    do_uls_plus = db.Column(db.Integer, default=0)
    ge_ge_plus = db.Column(db.Integer, default=0)
    gp_plus = db.Column(db.Integer, default=0)
    gp_ultra_100 = db.Column(db.Integer, default=0)
    funcionario = db.Column(db.String(100))
    filas_do_do_plus = db.Column(db.Integer, default=0)
    filas_ge_ge_plus = db.Column(db.Integer, default=0)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_actualizacion = db.Column(db.String(100))
    tipo_registro = db.Column(db.String(20), default='actualizacion')

    def calcular_volumen_total(self):
        return self.do_do_plus + self.do_uls_plus + self.ge_ge_plus + self.gp_plus + self.gp_ultra_100

    def calcular_dos(self):
        return self.do_do_plus + self.do_uls_plus

    def calcular_ges(self):
        return self.ge_ge_plus + self.gp_plus + self.gp_ultra_100

    def get_estado_volumen(self):
        total = self.calcular_volumen_total()
        if total > 7000:
            return {'class': 'volume-high', 'text': 'ALTO', 'color': 'success'}
        elif total >= 3000:
            return {'class': 'volume-medium', 'text': 'MEDIO', 'color': 'warning'}
        else:
            return {'class': 'volume-low', 'text': 'BAJO', 'color': 'danger'}

    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'razonSocial': self.razon_social,
            'zona': self.zona,
            'provincia': self.provincia,
            'municipio': self.municipio,
            'doDoPlus': self.do_do_plus,
            'doUlsPlus': self.do_uls_plus,
            'geGePlus': self.ge_ge_plus,
            'gpPlus': self.gp_plus,
            'gpUltra100': self.gp_ultra_100,
            'funcionario': self.funcionario,
            'filasDoDoPlus': self.filas_do_do_plus,
            'filasGeGePlus': self.filas_ge_ge_plus,
            'volumenTotal': self.calcular_volumen_total(),
            'volumenDOS': self.calcular_dos(),
            'volumenGES': self.calcular_ges(),
            'estadoVolumen': self.get_estado_volumen(),
            'fechaHora': self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S'),
            'usuarioActualizacion': self.usuario_actualizacion
        }

# ================= FUNCIONES DE UTILIDAD =================
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def crear_usuario_desde_funcionario(nombre_funcionario):
    username = nombre_funcionario.split()[0].lower()
    password = username + "1234"
    
    usuario_existente = Usuario.query.filter_by(username=username).first()
    if not usuario_existente:
        nuevo_usuario = Usuario(
            username=username,
            funcionario=nombre_funcionario,
            rol='user'
        )
        nuevo_usuario.set_password(password)
        db.session.add(nuevo_usuario)
        db.session.commit()
        print(f"✅ Usuario creado: {username} / {password}")
        return nuevo_usuario
    else:
        print(f"⚠️ Usuario ya existe: {username}")
        return usuario_existente

# ================= FUNCIONES AUXILIARES MEJORADAS =================
def calcular_estado(total):
    if total > 7000:
        return {'class': 'volume-high', 'text': 'ALTO', 'color': 'success'}
    elif total >= 3000:
        return {'class': 'volume-medium', 'text': 'MEDIO', 'color': 'warning'}
    else:
        return {'class': 'volume-low', 'text': 'BAJO', 'color': 'danger'}

def calcular_estadisticas():
    # Esta función calcula estadísticas para el dashboard de usuario
    # Por ahora retorna valores dummy - puedes implementar la lógica real después
    return {
        'alto_diesel': 0,
        'medio_diesel': 0, 
        'bajo_diesel': 0,
        'alto_gasolina': 0,
        'medio_gasolina': 0,
        'bajo_gasolina': 0
    }

# Hacer funciones disponibles en templates
app.jinja_env.globals.update(calcular_estado=calcular_estado)
app.jinja_env.globals.update(calcular_estadisticas=calcular_estadisticas)

def obtener_ultimos_registros(fecha_inicio=None, fecha_fin=None, hora_inicio=None, hora_fin=None):
    subquery = db.session.query(
        RegistroCombustible.codigo,
        db.func.max(RegistroCombustible.fecha_hora).label('max_fecha')
    )
    
    if fecha_inicio:
        if hora_inicio:
            fecha_inicio_completa = datetime.combine(fecha_inicio, datetime.strptime(hora_inicio, '%H:%M').time())
        else:
            fecha_inicio_completa = datetime.combine(fecha_inicio, datetime.min.time())
        subquery = subquery.filter(RegistroCombustible.fecha_hora >= fecha_inicio_completa)
    
    if fecha_fin:
        if hora_fin:
            fecha_fin_completa = datetime.combine(fecha_fin, datetime.strptime(hora_fin, '%H:%M').time())
        else:
            fecha_fin_completa = datetime.combine(fecha_fin, datetime.max.time())
        subquery = subquery.filter(RegistroCombustible.fecha_hora <= fecha_fin_completa)
    
    subquery = subquery.group_by(RegistroCombustible.codigo).subquery()
    
    registros = db.session.query(RegistroCombustible).join(
        subquery,
        db.and_(
            RegistroCombustible.codigo == subquery.c.codigo,
            RegistroCombustible.fecha_hora == subquery.c.max_fecha
        )
    ).all()
    
    return registros

def calcular_estadisticas_globales(registros, fecha_inicio=None, fecha_fin=None):
    if not registros:
        return {
            'total_estaciones': 0,
            'total_volumen': 0,
            'estaciones_rojo': 0,
            'promedio_filas_ciudad': 0,
            'promedio_filas_provincia': 0,
            'volumen_por_producto': {
                'do_do_plus': 0, 'do_uls_plus': 0, 'ge_ge_plus': 0, 
                'gp_plus': 0, 'gp_ultra_100': 0
            },
            'volumen_por_grupo': {'dos': 0, 'ges': 0},
            'top_estaciones': {'do_do_plus': [], 'gp_plus': [], 'total': []},
            'top_estaciones_grupo': {'dos': [], 'ges': []},
            'evolucion_temporal': [],
            'rango_fechas': {
                'inicio': fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else '',
                'fin': fecha_fin.strftime('%Y-%m-%d') if fecha_fin else ''
            }
        }
    
    total_estaciones = len(registros)
    total_volumen = sum(r.calcular_volumen_total() for r in registros)
    estaciones_rojo = sum(1 for r in registros if r.calcular_volumen_total() < 3000)
    
    filas_ciudad = [r.filas_do_do_plus + r.filas_ge_ge_plus for r in registros]
    promedio_filas_ciudad = sum(filas_ciudad) / len(filas_ciudad) if filas_ciudad else 0
    
    provincias = {}
    for r in registros:
        if r.provincia not in provincias:
            provincias[r.provincia] = []
        provincias[r.provincia].append(r.filas_do_do_plus + r.filas_ge_ge_plus)
    
    promedios_provincia = {prov: sum(filas) / len(filas) for prov, filas in provincias.items()}
    promedio_filas_provincia = sum(promedios_provincia.values()) / len(promedios_provincia) if promedios_provincia else 0
    
    volumen_por_producto = {
        'do_do_plus': sum(r.do_do_plus for r in registros),
        'do_uls_plus': sum(r.do_uls_plus for r in registros),
        'ge_ge_plus': sum(r.ge_ge_plus for r in registros),
        'gp_plus': sum(r.gp_plus for r in registros),
        'gp_ultra_100': sum(r.gp_ultra_100 for r in registros)
    }
    
    volumen_por_grupo = {
        'dos': sum(r.calcular_dos() for r in registros),
        'ges': sum(r.calcular_ges() for r in registros)
    }
    
    top_15_do_do = sorted(registros, key=lambda x: x.do_do_plus, reverse=True)[:15]
    top_15_gp = sorted(registros, key=lambda x: x.gp_plus, reverse=True)[:15]
    top_15_total = sorted(registros, key=lambda x: x.calcular_volumen_total(), reverse=True)[:15]
    top_15_dos = sorted(registros, key=lambda x: x.calcular_dos(), reverse=True)[:15]
    top_15_ges = sorted(registros, key=lambda x: x.calcular_ges(), reverse=True)[:15]
    
    registros_recientes = sorted(registros, key=lambda x: x.fecha_hora, reverse=True)[:10]
    registros_recientes.reverse()
    
    evolucion_temporal = []
    for registro in registros_recientes:
        evolucion_temporal.append({
            'fecha_hora': registro.fecha_hora.strftime('%m-%d %H:%M'),
            'dos': registro.calcular_dos(),
            'ges': registro.calcular_ges()
        })
    
    return {
        'total_estaciones': total_estaciones,
        'total_volumen': total_volumen,
        'estaciones_rojo': estaciones_rojo,
        'promedio_filas_ciudad': round(promedio_filas_ciudad, 1),
        'promedio_filas_provincia': round(promedio_filas_provincia, 1),
        'volumen_por_producto': volumen_por_producto,
        'volumen_por_grupo': volumen_por_grupo,
        'top_estaciones': {
            'do_do_plus': [{'nombre': r.razon_social, 'volumen': r.do_do_plus} for r in top_15_do_do],
            'gp_plus': [{'nombre': r.razon_social, 'volumen': r.gp_plus} for r in top_15_gp],
            'total': [{'nombre': r.razon_social, 'volumen': r.calcular_volumen_total()} for r in top_15_total]
        },
        'top_estaciones_grupo': {
            'dos': [{'nombre': r.razon_social, 'volumen': r.calcular_dos()} for r in top_15_dos],
            'ges': [{'nombre': r.razon_social, 'volumen': r.calcular_ges()} for r in top_15_ges]
        },
        'evolucion_temporal': evolucion_temporal,
        'rango_fechas': {
            'inicio': fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else '',
            'fin': fecha_fin.strftime('%Y-%m-%d') if fecha_fin else ''
        }
    }

# ================= RUTAS PRINCIPALES =================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if 'user' in session:
            if session.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            usuario = Usuario.query.filter_by(username=username).first()
            
            if usuario and usuario.check_password(password):
                session['user'] = usuario.username
                session['role'] = usuario.rol
                session['funcionario'] = usuario.funcionario
                session['login_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if usuario.rol == 'admin':
                    flash('¡Bienvenido Administrador!', 'success')
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash(f'Bienvenido {usuario.funcionario}', 'success')
                    return redirect(url_for('user_dashboard'))
            else:
                flash('Credenciales incorrectas. Intente nuevamente.', 'error')
        
        return render_template('login.html')
        
    except Exception as e:
        print(f"❌ ERROR en login: {str(e)}")
        import traceback
        print(f"🔍 TRACEBACK: {traceback.format_exc()}")
        flash('Error interno del servidor', 'error')
        return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('login'))
    
    try:
        fecha_inicio_str = request.args.get('fecha_inicio')
        fecha_fin_str = request.args.get('fecha_fin')
        hora_inicio_str = request.args.get('hora_inicio')
        hora_fin_str = request.args.get('hora_fin')
        
        fecha_inicio = None
        fecha_fin = None
        
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        
        if not fecha_inicio and not fecha_fin:
            fecha_fin = datetime.now()
            fecha_inicio = fecha_fin - timedelta(days=7)
        
        registros = obtener_ultimos_registros(fecha_inicio, fecha_fin, hora_inicio_str, hora_fin_str)
        fuel_data = [registro.to_dict() for registro in registros]
        
        stats = calcular_estadisticas_globales(registros, fecha_inicio, fecha_fin)
        
        usuarios = Usuario.query.all()
        
        return render_template('admin_dashboard.html', 
                             fuel_data=fuel_data, 
                             stats=stats,
                             usuarios=usuarios,
                             username=session['user'],
                             fecha_inicio=fecha_inicio_str or fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else '',
                             fecha_fin=fecha_fin_str or fecha_fin.strftime('%Y-%m-%d') if fecha_fin else '',
                             hora_inicio=hora_inicio_str or '',
                             hora_fin=hora_fin_str or '')
    except Exception as e:
        flash(f'Error al cargar datos: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/user/dashboard')
def user_dashboard():
    if 'user' not in session:
        flash('Debe iniciar sesión para acceder a esta página', 'error')
        return redirect(url_for('login'))
    
    try:
        funcionario = session.get('funcionario')
        
        subquery = db.session.query(
            RegistroCombustible.codigo,
            db.func.max(RegistroCombustible.fecha_hora).label('max_fecha')
        ).filter(RegistroCombustible.funcionario == funcionario).group_by(RegistroCombustible.codigo).subquery()
        
        registros = db.session.query(RegistroCombustible).join(
            subquery,
            db.and_(
                RegistroCombustible.codigo == subquery.c.codigo,
                RegistroCombustible.fecha_hora == subquery.c.max_fecha
            )
        ).filter(RegistroCombustible.funcionario == funcionario).all()
        
        fuel_data = [registro.to_dict() for registro in registros]
        
        return render_template('user_dashboard.html', 
                             fuel_data=fuel_data,
                             username=session['user'],
                             funcionario=funcionario)
    except Exception as e:
        flash(f'Error al cargar datos: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    username = session.get('user', 'Usuario')
    session.clear()
    flash(f'Sesión cerrada correctamente. ¡Hasta pronto {username}!', 'info')
    return redirect(url_for('login'))

# ================= RUTAS DE GESTIÓN DE USUARIOS =================
@app.route('/admin/crear_usuario', methods=['POST'])
def crear_usuario():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    nombre_funcionario = request.form.get('funcionario')
    if not nombre_funcionario:
        return jsonify({'success': False, 'message': 'Nombre de funcionario requerido'}), 400
    
    try:
        usuario = crear_usuario_desde_funcionario(nombre_funcionario)
        return jsonify({
            'success': True, 
            'message': f'Usuario creado: {usuario.username} / {usuario.username}1234'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al crear usuario: {str(e)}'}), 500

# ================= RUTAS MEJORADAS PARA GESTIÓN DE USUARIOS =================
@app.route('/admin/editar_usuario', methods=['POST'])
def editar_usuario():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    try:
        data = request.get_json()
        usuario_id = data.get('id')
        username = data.get('username')
        funcionario = data.get('funcionario')
        rol = data.get('rol')
        
        if not usuario_id or not username or not funcionario:
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400
        
        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
        
        # Verificar si el username ya existe (excluyendo el usuario actual)
        usuario_existente = Usuario.query.filter(
            Usuario.username == username, 
            Usuario.id != usuario_id
        ).first()
        
        if usuario_existente:
            return jsonify({'success': False, 'message': 'El nombre de usuario ya existe'}), 400
        
        usuario.username = username
        usuario.funcionario = funcionario
        usuario.rol = rol
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Usuario actualizado correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al editar usuario: {str(e)}'}), 500

@app.route('/admin/eliminar_usuario', methods=['POST'])
def eliminar_usuario():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    try:
        data = request.get_json()
        usuario_id = data.get('id')
        
        if not usuario_id:
            return jsonify({'success': False, 'message': 'ID de usuario requerido'}), 400
        
        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
        
        # No permitir eliminar al usuario admin principal
        if usuario.username == 'admin':
            return jsonify({'success': False, 'message': 'No se puede eliminar el usuario admin principal'}), 400
        
        db.session.delete(usuario)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Usuario eliminado correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al eliminar usuario: {str(e)}'}), 500

# ================= RUTA CORREGIDA PARA ACTUALIZAR ESTACIONES =================
@app.route('/user/actualizar_estacion', methods=['POST'])
def actualizar_estacion():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Debe iniciar sesión'}), 403
    
    try:
        data = request.get_json()
        codigo = data.get('codigo')
        
        if not codigo:
            return jsonify({'success': False, 'message': 'Código de estación requerido'}), 400
        
        # Buscar si existe un registro anterior para esta estación
        registro_anterior = RegistroCombustible.query.filter_by(
            codigo=codigo, 
            funcionario=session.get('funcionario')
        ).order_by(RegistroCombustible.fecha_hora.desc()).first()
        
        # Crear NUEVO registro (siempre crear nuevo, no actualizar existente)
        nuevo_registro = RegistroCombustible(
            codigo=codigo,
            razon_social=data.get('razon_social', registro_anterior.razon_social if registro_anterior else ''),
            zona=data.get('zona', registro_anterior.zona if registro_anterior else ''),
            provincia=data.get('provincia', registro_anterior.provincia if registro_anterior else ''),
            municipio=data.get('municipio', registro_anterior.municipio if registro_anterior else ''),
            do_do_plus=int(data.get('do_do_plus', 0)),
            do_uls_plus=int(data.get('do_uls_plus', 0)),
            ge_ge_plus=int(data.get('ge_ge_plus', 0)),
            gp_plus=int(data.get('gp_plus', 0)),
            gp_ultra_100=int(data.get('gp_ultra_100', 0)),
            funcionario=session.get('funcionario'),
            filas_do_do_plus=int(data.get('filas_do_do_plus', 0)),
            filas_ge_ge_plus=int(data.get('filas_ge_ge_plus', 0)),
            fecha_hora=datetime.utcnow(),
            usuario_actualizacion=session.get('user'),
            tipo_registro='actualizacion'
        )
        
        db.session.add(nuevo_registro)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Datos guardados correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error en actualizar_estacion: {str(e)}")
        return jsonify({'success': False, 'message': f'Error interno del servidor: {str(e)}'}), 500

# ================= CARGA Y EXPORTACIÓN DE ARCHIVOS =================
@app.route('/admin/upload', methods=['POST'])
def upload_file():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se seleccionó archivo'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No se seleccionó archivo'}), 400
    
    if file and allowed_file(file.filename):
        try:
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            
            headers = [h.strip().upper() for h in next(csv_input)]
            
            fecha_hora_columna = None
            for i, header in enumerate(headers):
                if 'FECHA' in header and 'HORA' in header and 'ACTUALIZACION' in header:
                    fecha_hora_columna = i
                    break
            
            if fecha_hora_columna is None:
                headers.append('FECHA Y HORA DE ACTUALIZACION')
                fecha_hora_columna = len(headers) - 1
            
            required_columns = [
                'CODIGO', 'RAZON SOCIAL ANH', 'ZONA', 'PROVINCIA', 'MUNICIPIO',
                'DO/DO+ (LTS)', 'DO ULS+ (LTS)', 'GE/GE+ (LTS)', 'GP+ (LTS)', 
                'GPULTRA100 (LTS)', 'FUNCIONARIO', 'FILAS DO/DO+', 'FILAS GE/GE+'
            ]
            
            required_columns_normalized = [col.upper().strip() for col in required_columns]
            headers_normalized = [h.upper().strip() for h in headers]
            
            missing_columns = []
            for req_col in required_columns_normalized:
                found = False
                for header in headers_normalized:
                    if req_col in header or header in req_col:
                        found = True
                        break
                if not found:
                    missing_columns.append(req_col)
            
            if missing_columns:
                return jsonify({
                    'success': False, 
                    'message': f'Columnas faltantes o con nombres diferentes: {", ".join(missing_columns)}'
                }), 400
            
            processed_count = 0
            usuarios_creados = set()
            
            for row in csv_input:
                if len(row) < len(headers) - 1:
                    continue
                
                try:
                    def get_column_index(column_name):
                        for i, header in enumerate(headers_normalized):
                            if column_name in header or header in column_name:
                                return i
                        return -1
                    
                    codigo_idx = get_column_index('CODIGO')
                    razon_social_idx = get_column_index('RAZON SOCIAL ANH')
                    zona_idx = get_column_index('ZONA')
                    provincia_idx = get_column_index('PROVINCIA')
                    municipio_idx = get_column_index('MUNICIPIO')
                    do_do_plus_idx = get_column_index('DO/DO+ (LTS)')
                    do_uls_plus_idx = get_column_index('DO ULS+ (LTS)')
                    ge_ge_plus_idx = get_column_index('GE/GE+ (LTS)')
                    gp_plus_idx = get_column_index('GP+ (LTS)')
                    gp_ultra_idx = get_column_index('GPULTRA100 (LTS)')
                    funcionario_idx = get_column_index('FUNCIONARIO')
                    filas_do_idx = get_column_index('FILAS DO/DO+')
                    filas_ge_idx = get_column_index('FILAS GE/GE+')
                    
                    if -1 in [codigo_idx, razon_social_idx, funcionario_idx]:
                        continue
                    
                    codigo = str(row[codigo_idx]) if codigo_idx < len(row) else ''
                    funcionario = str(row[funcionario_idx]) if funcionario_idx < len(row) else ''
                    
                    if not codigo or not funcionario:
                        continue
                    
                    if funcionario and funcionario not in usuarios_creados:
                        crear_usuario_desde_funcionario(funcionario)
                        usuarios_creados.add(funcionario)
                    
                    fecha_hora_actualizacion = datetime.utcnow()
                    if fecha_hora_columna < len(row) and row[fecha_hora_columna]:
                        try:
                            fecha_hora_str = row[fecha_hora_columna].strip()
                            if fecha_hora_str:
                                for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']:
                                    try:
                                        fecha_hora_actualizacion = datetime.strptime(fecha_hora_str, fmt)
                                        break
                                    except ValueError:
                                        continue
                        except:
                            fecha_hora_actualizacion = datetime.utcnow()
                    
                    nuevo_registro = RegistroCombustible(
                        codigo=codigo,
                        razon_social=str(row[razon_social_idx]) if razon_social_idx < len(row) else '',
                        zona=str(row[zona_idx]) if zona_idx < len(row) else '',
                        provincia=str(row[provincia_idx]) if provincia_idx < len(row) else '',
                        municipio=str(row[municipio_idx]) if municipio_idx < len(row) else '',
                        do_do_plus=int(float(row[do_do_plus_idx] or 0)) if do_do_plus_idx < len(row) else 0,
                        do_uls_plus=int(float(row[do_uls_plus_idx] or 0)) if do_uls_plus_idx < len(row) else 0,
                        ge_ge_plus=int(float(row[ge_ge_plus_idx] or 0)) if ge_ge_plus_idx < len(row) else 0,
                        gp_plus=int(float(row[gp_plus_idx] or 0)) if gp_plus_idx < len(row) else 0,
                        gp_ultra_100=int(float(row[gp_ultra_idx] or 0)) if gp_ultra_idx < len(row) else 0,
                        funcionario=funcionario,
                        filas_do_do_plus=int(float(row[filas_do_idx] or 0)) if filas_do_idx < len(row) else 0,
                        filas_ge_ge_plus=int(float(row[filas_ge_idx] or 0)) if filas_ge_idx < len(row) else 0,
                        fecha_hora=fecha_hora_actualizacion,
                        usuario_actualizacion=session.get('user'),
                        tipo_registro='inicial'
                    )
                    
                    db.session.add(nuevo_registro)
                    processed_count += 1
                    
                except Exception as e:
                    print(f"Error procesando fila: {e}")
                    continue
            
            db.session.commit()
            
            mensaje = f'Archivo procesado correctamente. {processed_count} registros creados.'
            if usuarios_creados:
                mensaje += f' {len(usuarios_creados)} usuarios creados.'
            
            return jsonify({
                'success': True, 
                'message': mensaje
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False, 
                'message': f'Error al procesar archivo: {str(e)}'
            }), 500
    
    return jsonify({'success': False, 'message': 'Tipo de archivo no permitido'}), 400

@app.route('/admin/export/csv')
def export_csv():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('login'))
    
    try:
        fecha_inicio_str = request.args.get('fecha_inicio')
        fecha_fin_str = request.args.get('fecha_fin')
        hora_inicio_str = request.args.get('hora_inicio')
        hora_fin_str = request.args.get('hora_fin')
        
        fecha_inicio = None
        fecha_fin = None
        
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        
        registros = obtener_ultimos_registros(fecha_inicio, fecha_fin, hora_inicio_str, hora_fin_str)
        
        output = StringIO()
        writer = csv.writer(output)
        
        headers = [
            'CODIGO', 'RAZON SOCIAL ANH', 'ZONA', 'PROVINCIA', 'MUNICIPIO',
            'DO/DO+ (LTS)', 'DO ULS+ (LTS)', 'GE/GE+ (LTS)', 'GP+ (LTS)', 
            'GPULTRA100 (LTS)', 'VOLUMEN TOTAL', 'ESTADO', 'FUNCIONARIO',
            'FILAS DO/DO+', 'FILAS GE/GE+', 'FECHA Y HORA DE ACTUALIZACION', 'USUARIO_ACTUALIZACION'
        ]
        writer.writerow(headers)
        
        for registro in registros:
            estado = registro.get_estado_volumen()
            
            row = [
                registro.codigo,
                registro.razon_social,
                registro.zona,
                registro.provincia,
                registro.municipio,
                registro.do_do_plus,
                registro.do_uls_plus,
                registro.ge_ge_plus,
                registro.gp_plus,
                registro.gp_ultra_100,
                registro.calcular_volumen_total(),
                estado['text'],
                registro.funcionario,
                registro.filas_do_do_plus,
                registro.filas_ge_ge_plus,
                registro.fecha_hora.strftime('%Y-%m-%d %H:%M:%S'),
                registro.usuario_actualizacion or ''
            ]
            writer.writerow(row)
        
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'datos_combustibles_{timestamp}.csv'
        
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        flash(f'Error al exportar datos: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/force-init')
def force_init():
    try:
        with app.app_context():
            db.drop_all()
            db.create_all()
            
            admin = Usuario(username='admin', funcionario='Administrador', rol='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            
            return """
            <h1>🎉 BASE DE DATOS INICIALIZADA</h1>
            <p><strong>Usuario admin creado:</strong></p>
            <p>Usuario: <code>admin</code></p>
            <p>Contraseña: <code>admin123</code></p>
            <br>
            <a href="/login" class="btn btn-success">Ir al Login</a>
            """
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ================= INICIALIZACIÓN =================
def create_tables():
    """Función separada para crear tablas que se puede llamar desde wsgi"""
    with app.app_context():
        try:
            db.create_all()
            print("✅ Tablas creadas/verificadas")
            
            # Crear usuario admin si no existe
            admin_existente = Usuario.query.filter_by(username='admin').first()
            if not admin_existente:
                admin = Usuario(
                    username='admin',
                    funcionario='Administrador', 
                    rol='admin'
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("✅ Usuario admin creado")
            else:
                print("✅ Usuario admin ya existe")
                
        except Exception as e:
            print(f"❌ Error al crear tablas: {e}")

# Inicializar la base de datos cuando se ejecute el archivo directamente
if __name__ == '__main__':
    create_tables()
    app.run(debug=True, host='0.0.0.0', port=5000)