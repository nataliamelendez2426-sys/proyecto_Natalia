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

@app.route('/catalogo/ajax')
@login_required
def catalogo():
    # Obtener filtros del GET
    categorias = request.args.getlist('categoria')
    materiales = request.args.getlist('material')
    colores = request.args.getlist('color')
    precio_min = request.args.get('precio_min', type=float)
    precio_max = request.args.get('precio_max', type=float)

    # Query inicial
    productos = Producto.query

    if categorias:
        productos = productos.filter(Producto.ID_Categoria.in_(categorias))
    if materiales:
        productos = productos.filter(Producto.Material.in_(materiales))
    if colores:
        productos = productos.filter(Producto.Color.in_(colores))
    if precio_min is not None:
        productos = productos.filter(Producto.PrecioUnidad >= precio_min)
    if precio_max is not None:
        productos = productos.filter(Producto.PrecioUnidad <= precio_max)

    productos = productos.all()

    # Puntuar según preferencias del usuario
    def score(p):
        s = 0
        if p.ID_Categoria in [c.ID_Categoria for c in current_user.categorias_favoritas]: s += 3
        if p.Material in current_user.materiales_preferidos: s += 2
        if p.Color in current_user.colores_preferidos: s += 1
        return s

    productos = sorted(productos, key=lambda p: score(p), reverse=True)

    # Convertir a JSON
    result = []
    for p in productos:
        result.append({
            "ID_Producto": p.ID_Producto,
            "NombreProducto": p.NombreProducto,
            "PrecioUnidad": float(p.PrecioUnidad),
            "Stock": p.Stock,
            "Material": p.Material,
            "Color": p.Color,
            "CategoriaNombre": p.categoria.NombreCategoria if p.categoria else None,
            "ImagenPrincipal": p.ImagenPrincipal
        })

    return jsonify(result)




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
