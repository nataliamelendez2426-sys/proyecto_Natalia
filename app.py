import os
from flask import Flask, render_template, session, redirect, request, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import joinedload
from flask_login import current_user



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

@app.route("/catalogo")
def catalogo():
    # Obtener filtros del query string
    categorias_seleccionadas = request.args.getlist('categoria')
    materiales_seleccionados = request.args.getlist('material')
    colores_seleccionados = request.args.getlist('color')
    precio_min = request.args.get('precio_min', type=float)
    precio_max = request.args.get('precio_max', type=float)

    # Convertir categorías a enteros
    try:
        categorias_seleccionadas = [int(c) for c in categorias_seleccionadas]
    except ValueError:
        categorias_seleccionadas = []

    # Base query
    query = Producto.query

    # Filtrar por categorías
    if categorias_seleccionadas:
        query = query.filter(Producto.ID_Categoria.in_(categorias_seleccionadas))

    # Filtrar por material
    if materiales_seleccionados:
        query = query.filter(Producto.Material.in_(materiales_seleccionados))

    # Filtrar por color
    if colores_seleccionados:
        query = query.filter(Producto.Color.in_(colores_seleccionados))

    # Filtrar por precio
    if precio_min is not None:
        query = query.filter(Producto.PrecioUnidad >= precio_min)
    if precio_max is not None:
        query = query.filter(Producto.PrecioUnidad <= precio_max)

    productos = query.all()

    # Datos para los filtros en el sidebar
    todas_categorias = Categorias.query.order_by(Categorias.NombreCategoria).all()
    todos_materiales = [m[0] for m in db.session.query(Producto.Material).distinct().all() if m[0]]
    todos_colores = [c[0] for c in db.session.query(Producto.Color).distinct().all() if c[0]]

    return render_template(
        "common/catalogo.html",
        productos=productos,
        todas_etiquetas=todas_categorias,
        etiquetas_seleccionadas=[str(c) for c in categorias_seleccionadas],
        materiales=todos_materiales,
        materiales_seleccionados=materiales_seleccionados,
        colores=todos_colores,
        colores_seleccionados=colores_seleccionados,
        precio_min=precio_min,
        precio_max=precio_max
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
