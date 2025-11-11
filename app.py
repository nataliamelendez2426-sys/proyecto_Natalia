import os
import json
from flask import Flask, render_template, session, redirect, request, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import joinedload
from flask_login import current_user , login_required



# ------------------ MODELOS ------------------ #
from basedatos.models import db, Usuario, Producto,Pedido,Categorias

# ------------------ EXTENSIONES ------------------ #
from basedatos.decoradores import mail

# ------------------ BLUEPRINTS ------------------ #
from routes.auth import auth
from routes.cliente import cliente
from routes.administrador import admin
from routes.transportista import transportista

# ------------------ APP ------------------ #
app = Flask(__name__)

# ------------------ CONFIGURACIÓN PRINCIPAL ------------------ #
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "mi_clave_super_secreta_y_unica"),
    SQLALCHEMY_DATABASE_URI=os.getenv(
        "DATABASE_URI", "mysql+pymysql://root:2426@127.0.0.1:3306/Tienda_db"
    ),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
)

# ------------------ CONFIGURACIÓN MAIL ------------------ #
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "casaenelarbol236@gmail.com"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "usygdligtlewedju"),
    MAIL_DEFAULT_SENDER=("Casa en el Árbol", os.getenv("MAIL_USERNAME", "casaenelarbol236@gmail.com")),
)
mail.init_app(app)

# ------------------ DB ------------------ #
db.init_app(app)

with app.app_context():
    db.create_all()
# ------------------ FLASK LOGIN ------------------ #
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."
login_manager.login_message_category = "warning"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    try:
        return Usuario.query.get(int(user_id))
    except Exception as e:
        print(f"⚠️ Error cargando usuario: {e}")
        return None

# ------------------ REGISTRO DE BLUEPRINTS ------------------ #
app.register_blueprint(auth)
app.register_blueprint(cliente)
app.register_blueprint(admin)
app.register_blueprint(transportista)
# ------------------ RUTAS PÚBLICAS ------------------ #

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

@app.route("/")
def index():
    return render_template("common/index.html")

@app.route("/nosotros")
def nosotros():
    return render_template("common/nosotros.html")

@app.route('/catalogo')
@login_required
def catalogo():
    # --- Filtros desde GET ---
    categorias_seleccionadas = request.args.getlist('categoria')
    materiales_seleccionados = request.args.getlist('material')
    colores_seleccionados = request.args.getlist('color')
    precio_min = request.args.get('precio_min', type=float)
    precio_max = request.args.get('precio_max', type=float)

    # --- Construir query base ---
    query = Producto.query

    # Filtrar por categorías
    if categorias_seleccionadas:
        query = query.filter(Producto.ID_Categoria.in_([int(c) for c in categorias_seleccionadas]))

    # Filtrar por materiales
    if materiales_seleccionados:
        query = query.filter(Producto.Material.in_(materiales_seleccionados))

    # Filtrar por colores
    if colores_seleccionados:
        query = query.filter(Producto.Color.in_(colores_seleccionados))

    # Filtrar por precio
    if precio_min is not None:
        query = query.filter(Producto.PrecioUnidad >= precio_min)
    if precio_max is not None:
        query = query.filter(Producto.PrecioUnidad <= precio_max)

    productos = query.all()

    # --- Obtener todas las categorías, materiales y colores para los filtros ---
    # Evitar duplicados por nombre de categoría (p.ej., 'Sillas' repetida)
    _cats_raw = Categorias.query.order_by(Categorias.NombreCategoria.asc()).all()
    _seen = set()
    todas_etiquetas = []
    for c in _cats_raw:
        k = (c.NombreCategoria or '').strip().lower()
        if not k or k in _seen:
            continue
        _seen.add(k)
        todas_etiquetas.append(c)
    materiales = [m[0] for m in db.session.query(Producto.Material).distinct().all() if m[0]]
    colores = [c[0] for c in db.session.query(Producto.Color).distinct().all() if c[0]]

    # --- Guardar automáticamente preferencias del usuario ---
    try:
        current_user.categorias_favoritas = Categorias.query.filter(
            Categorias.ID_Categoria.in_([int(c) for c in categorias_seleccionadas])
        ).all() if categorias_seleccionadas else current_user.categorias_favoritas
    except:
        current_user.categorias_favoritas = []

    try:
        current_user.materiales_preferidos = json.dumps(materiales_seleccionados) if materiales_seleccionados else current_user.materiales_preferidos
    except:
        current_user.materiales_preferidos = '[]'

    try:
        current_user.colores_preferidos = json.dumps(colores_seleccionados) if colores_seleccionados else current_user.colores_preferidos
    except:
        current_user.colores_preferidos = '[]'

    db.session.commit()  # Guardar cambios automáticamente

    # --- Preparar datos para mostrar en la plantilla ---
    categorias_favoritas = [c.ID_Categoria for c in current_user.categorias_favoritas]
    materiales_preferidos = json.loads(current_user.materiales_preferidos or '[]')
    colores_preferidos = json.loads(current_user.colores_preferidos or '[]')

    def _score(p):
        s = 0
        try:
            if p.ID_Categoria in categorias_favoritas:
                s += 3
            if p.Material and p.Material in materiales_preferidos:
                s += 2
            if p.Color and p.Color in colores_preferidos:
                s += 1
        except Exception:
            pass
        return s
    try:
        productos = sorted(productos, key=lambda p: _score(p), reverse=True)
    except Exception:
        pass

    return render_template(
        'common/catalogo.html',
        productos=productos,
        todas_etiquetas=todas_etiquetas,
        categorias_seleccionadas=categorias_seleccionadas,
        materiales=materiales,
        materiales_seleccionados=materiales_seleccionados,
        colores=colores,
        colores_seleccionados=colores_seleccionados,
        precio_min=precio_min,
        precio_max=precio_max,
        categorias_favoritas=categorias_favoritas,
        materiales_preferidos=materiales_preferidos,
        colores_preferidos=colores_preferidos
    )




@app.route("/favoritos", methods=["POST"])
def favoritos():
    data = request.get_json()
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"html": "<p>No tienes productos favoritos.</p>"})
    productos = Producto.query.filter(Producto.ID_Producto.in_(ids)).all()
    html = render_template("cliente/lista_favoritos.html", productos=productos)
    return jsonify({"html": html})

@app.route('/admin/pedidos')
def pedidos_admin():
    pedidos = Pedido.query.options(joinedload(Pedido.Productos)).all()
    print(f"Pedidos: {pedidos}")
    for p in pedidos:
        print(f"Pedido {p.ID} con productos: {p.Productos}")
    return render_template('administrador/admin_actualizacion_datos.html', pedidos=pedidos)


# ------------------ TEMPLATE FILTER ------------------ #
@app.template_filter("dict_get")
def dict_get(d, key):
    return d.get(int(key), 0)

# ------------------ DEBUG: MOSTRAR RUTAS ------------------ #
with app.app_context():
    print("\n🔗 RUTAS REGISTRADAS:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint:35s} -> {rule}")
    print("-----------------------------\n")

# ------------------ MAIN ------------------ #
if __name__ == "__main__":
    app.run(debug=True)
