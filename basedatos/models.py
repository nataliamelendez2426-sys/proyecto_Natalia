import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Enum
from datetime import datetime, date, time

db = SQLAlchemy()

usuario_categoria = db.Table(
    'usuario_categoria',
    db.Column('usuario_id', db.Integer, db.ForeignKey('Usuario.ID_Usuario'), primary_key=True),
    db.Column('categoria_id', db.Integer, db.ForeignKey('Categorias.ID_Categoria'), primary_key=True)
)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'Usuario'

    ID_Usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Apellido = db.Column(db.String(100))
    Genero = db.Column(db.String(10))
    Telefono = db.Column(db.String(20))
    Correo = db.Column(db.String(100), nullable=False, unique=True)
    Contraseña = db.Column(db.String(200), nullable=False)
    Rol = db.Column(db.String(50), default='cliente')
    Activo = db.Column(db.Boolean, default=True)
    horas_diurnas = db.Column(db.Float, default=0)
    horas_nocturnas = db.Column(db.Float, default=0)
    horas_extra = db.Column(db.Float, default=0)

    # Relaciones
    calendarios = db.relationship('Calendario', backref='usuario', lazy=True)
    notificaciones = db.relationship('Notificaciones', backref='usuario', lazy=True)
    novedades = db.relationship('Novedades', backref='usuario', lazy=True)
    pedidos = db.relationship('Pedido', backref='usuario', lazy=True, foreign_keys='Pedido.ID_Usuario')
    pedidos_asignados = db.relationship('Pedido', backref='empleado_usuario', lazy=True, foreign_keys='Pedido.ID_Empleado')
    direcciones = db.relationship('Direccion', backref='usuario', lazy=True, cascade="all, delete-orphan")
    resenas = db.relationship('Resena', back_populates='usuario', lazy=True)
    mensajes = db.relationship('Mensaje', backref='cliente', lazy=True)

    # Preferencias de catálogo
    categorias_favoritas = db.relationship('Categorias', secondary=usuario_categoria, lazy='subquery')
    materiales_preferidos = db.Column(db.Text)  # JSON de materiales preferidos
    colores_preferidos = db.Column(db.Text)     # JSON de colores preferidos

    def get_materiales_favoritos(self):
        return json.loads(self.materiales_preferidos or "[]")

    def get_colores_favoritos(self):
        return json.loads(self.colores_preferidos or "[]")

    def get_id(self):
        return str(self.ID_Usuario)

    @property
    def id(self):
        return self.ID_Usuario

    def __repr__(self):
        return f'<Usuario {self.Nombre} {self.Apellido or ""}>'

# ------------------ Direccion ------------------
class Direccion(db.Model):
    __tablename__ = 'Direccion'

    ID_Direccion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario', ondelete="CASCADE"), nullable=False)
    Pais = db.Column(db.String(100), default="Colombia")
    Departamento = db.Column(db.String(100))
    Ciudad = db.Column(db.String(100))
    Direccion = db.Column(db.String(200), nullable=False)
    InfoAdicional = db.Column(db.String(200))
    Barrio = db.Column(db.String(100))
    Destinatario = db.Column(db.String(100))

# ------------------ Proveedor ------------------
class Proveedor(db.Model):
    __tablename__ = 'Proveedor'

    ID_Proveedor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreEmpresa = db.Column(db.String(100), nullable=False)
    NombreContacto = db.Column(db.String(100))
    Telefono = db.Column(db.String(20))
    Pais = db.Column(db.String(50))
    CargoContacto = db.Column(db.String(50))
    Ciudad = db.Column(db.String(100))
    Direccion = db.Column(db.String(200))

    productos = db.relationship('Producto', back_populates='proveedor', lazy=True)
    compras = db.relationship('Compra', back_populates='proveedor', lazy=True)

# ------------------ Categorias ------------------
class Categorias(db.Model):
    __tablename__ = 'Categorias'

    ID_Categoria = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreCategoria = db.Column(db.String(100), nullable=False)
    Descripcion = db.Column(db.Text)

    productos = db.relationship('Producto', back_populates='categoria', lazy=True)



# ------------------ Producto ------------------
class Producto(db.Model):
    __tablename__ = 'Producto'

    ID_Producto = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreProducto = db.Column(db.String(100), nullable=False)
    Stock = db.Column(db.Integer, nullable=False)
    Material = db.Column(db.String(50))
    PrecioUnidad = db.Column(db.Float, nullable=False)
    Color = db.Column(db.String(30))
    Descripcion = db.Column(db.Text)
    ImagenPrincipal = db.Column(db.String(200))
    ID_Proveedor = db.Column(db.Integer, db.ForeignKey('Proveedor.ID_Proveedor'), nullable=False)
    ID_Categoria = db.Column(db.Integer, db.ForeignKey('Categorias.ID_Categoria'))

    Comentario = db.Column(db.Text)
    Calificacion = db.Column(db.Integer)

    proveedor = db.relationship('Proveedor', back_populates='productos')
    categoria = db.relationship('Categorias', back_populates='productos')
    imagenes = db.relationship('ImagenProducto', backref='producto', lazy=True)
    novedades = db.relationship('Novedades', backref='producto', lazy=True)
    detalles_pedido = db.relationship('Detalle_Pedido', back_populates='producto', lazy=True)
    resenas = db.relationship('Resena', back_populates='producto', lazy=True)

# ------------------ ImagenProducto ------------------
class ImagenProducto(db.Model):
    __tablename__ = 'ImagenProducto'

    ID_Imagen = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ruta = db.Column(db.String(200), nullable=False)
    ID_Producto = db.Column(db.Integer, db.ForeignKey('Producto.ID_Producto'), nullable=False)

# ------------------ Pedido ------------------
class Pedido(db.Model):
    __tablename__ = 'Pedido'

    ID_Pedido = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreComprador = db.Column(db.String(100))
    Estado = db.Column(Enum('pendiente', 'en proceso', 'en reparto', 'entregado', name='estado_pedido'))
    FechaPedido = db.Column(db.Date, default=date.today)
    FechaEntrega = db.Column(db.Date)
    Destino = db.Column(db.String(200))
    Descuento = db.Column(db.Float, default=0)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    ID_Empleado = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'))
    HoraLlegada = db.Column(db.DateTime)

    detalles_pedido = db.relationship('Detalle_Pedido', backref='pedido', lazy=True)
    firmas = db.relationship('Firmas', backref='pedido', lazy=True)
    comentarios = db.relationship('Comentarios', backref='pedido', lazy=True)
    calendario = db.relationship('Calendario', backref='pedido', lazy=True)
    garantias = db.relationship('Garantia', backref='pedido', lazy=True)
    pagos = db.relationship('Pagos', back_populates='pedido', lazy=True)

    empleado = db.relationship('Usuario', foreign_keys=[ID_Empleado])

# ------------------ Detalle_Pedido ------------------
class Detalle_Pedido(db.Model):
    __tablename__ = 'Detalle_Pedido'

    ID_Pedido = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'), primary_key=True)
    ID_Producto = db.Column(db.Integer, db.ForeignKey('Producto.ID_Producto'), primary_key=True)
    Cantidad = db.Column(db.Integer, nullable=False)
    PrecioUnidad = db.Column(db.Float, nullable=False)

    producto = db.relationship('Producto', back_populates='detalles_pedido')

    @property
    def subtotal(self):
        precio = self.PrecioUnidad or 0
        cantidad = self.Cantidad or 0
        return cantidad * precio


# ------------------ Pagos ------------------
class Pagos(db.Model):
    __tablename__ = 'Pagos'

    ID_Pagos = db.Column(db.Integer, primary_key=True, autoincrement=True)
    MetodoPago = db.Column(db.String(50), nullable=False)
    FechaPago = db.Column(db.DateTime, default=datetime.utcnow)
    Monto = db.Column(db.Float, nullable=False)
    ID_Pedido = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'), nullable=False)

    pedido = db.relationship('Pedido', back_populates='pagos')

# ------------------ Firmas ------------------
class Firmas(db.Model):
    __tablename__ = 'Firmas'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'), nullable=False)
    nombre_cliente = db.Column(db.String(100), nullable=False)
    firma = db.Column(db.Text, nullable=False)
    fecha_firma = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------ Comentarios ------------------
class Comentarios(db.Model):
    __tablename__ = 'Comentarios'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido', ondelete="CASCADE"), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------ Calendario ------------------
class Calendario(db.Model):
    __tablename__ = 'Calendario'

    ID_Calendario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Fecha = db.Column(db.Date, nullable=False)
    Hora = db.Column(db.Time, nullable=False)
    Ubicacion = db.Column(db.String(255), nullable=False)
    Tipo = db.Column(db.String(50), nullable=False)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    ID_Pedido = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'))

# ------------------ Notificaciones ------------------
class Notificaciones(db.Model):
    __tablename__ = 'Notificaciones'

    ID_Notificacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Titulo = db.Column(db.String(200), nullable=False)
    Mensaje = db.Column(db.Text, nullable=False)
    Fecha = db.Column(db.DateTime, default=datetime.utcnow)
    Leida = db.Column(db.Boolean, default=False)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)

    # 🔹 Nuevo campo y relación con ProductoDefectuoso
    ID_Defecto = db.Column(db.Integer, db.ForeignKey('ProductoDefectuoso.ID'), nullable=True)
    defecto = db.relationship('ProductoDefectuoso', backref='notificaciones', lazy=True)


# ------------------ Novedades ------------------
class Novedades(db.Model):
    __tablename__ = 'Novedades'

    ID_Novedad = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Tipo = db.Column(db.String(50))
    EstadoNovedad = db.Column(db.String(50))
    FechaReporte = db.Column(db.Date, default=date.today)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    ID_Producto = db.Column(db.Integer, db.ForeignKey('Producto.ID_Producto'), nullable=False)

# ------------------ Resena ------------------
class Resena(db.Model):
    __tablename__ = 'Resena'

    ID_Resena = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_Producto = db.Column(db.Integer, db.ForeignKey('Producto.ID_Producto'), nullable=False)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    Calificacion = db.Column(db.Integer, nullable=False)
    Comentario = db.Column(db.Text, nullable=False)
    Fecha = db.Column(db.DateTime, default=datetime.utcnow)

    producto = db.relationship('Producto', back_populates='resenas')
    usuario = db.relationship('Usuario', back_populates='resenas')

    __table_args__ = (
        CheckConstraint('Calificacion >= 1 AND Calificacion <= 5', name='check_calificacion_range'),
    )

# ------------------ Compra ------------------
class Compra(db.Model):
    __tablename__ = 'Compra'

    ID_Compra = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Producto = db.Column(db.String(100), nullable=False)
    Cantidad = db.Column(db.Integer, nullable=False)
    Fecha = db.Column(db.Date, default=date.today)
    ProveedorID = db.Column(db.Integer, db.ForeignKey('Proveedor.ID_Proveedor'), nullable=False)

    proveedor = db.relationship('Proveedor', back_populates='compras')

# ------------------ Mensaje ------------------
class Mensaje(db.Model):
    __tablename__ = 'Mensajes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario', ondelete='CASCADE'), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    enviado_admin = db.Column(db.Boolean, default=False, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# ------------------ RegistroFotografico ------------------
class RegistroFotografico(db.Model):
    __tablename__ = 'registro_fotografico'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    tipo = db.Column(db.String(10))
    descripcion = db.Column(db.Text)
    imagen_url = db.Column(db.Text, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------ Garantia ------------------
class Garantia(db.Model):
    __tablename__ = 'Garantia'

    ID_Garantia = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_Pedido = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'), nullable=False)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    FechaSolicitud = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    Estado = db.Column(Enum('pendiente','aprobada','rechazada','completada'), default='pendiente', nullable=False)
    Motivo = db.Column(db.Text, nullable=False)
    ComentarioAdmin = db.Column(db.Text)
    FechaResolucion = db.Column(db.DateTime)

    # NUEVO CAMPO
    CitaAgendada = db.Column(db.DateTime, nullable=True)

    archivos = db.relationship('GarantiaArchivo', backref='garantia', lazy=True, cascade="all, delete-orphan")

    # Relación con el cliente que solicitó la garantía
    usuario = db.relationship('Usuario', foreign_keys=[ID_Usuario], backref='garantias', lazy=True)

    # Relación con el empleado (instalador) asignado a la garantía
    ID_Empleado = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=True)
    empleado = db.relationship('Usuario', foreign_keys=[ID_Empleado], backref='garantias_asignadas')


# ------------------ GarantiaArchivo ------------------
class GarantiaArchivo(db.Model):
    __tablename__ = 'GarantiaArchivo'

    ID_Archivo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_Garantia = db.Column(db.Integer, db.ForeignKey('Garantia.ID_Garantia', ondelete='CASCADE'), nullable=False)
    NombreArchivo = db.Column(db.String(200))
    RutaArchivo = db.Column(db.String(500), nullable=False)
    FechaSubida = db.Column(db.DateTime, default=datetime.utcnow)



# ------------------ Etiqueta ------------------
class Etiqueta(db.Model):
    __tablename__ = 'Etiqueta'

    ID_Etiqueta = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreEtiqueta = db.Column(db.String(100), nullable=False)
    ID_Categoria = db.Column(db.Integer, db.ForeignKey('Categorias.ID_Categoria'), nullable=False)

    # Relación con Categoría
    categoria = db.relationship('Categorias', backref='etiquetas', lazy=True)

# ------------------ Tabla intermedia producto_etiqueta ------------------
producto_etiqueta = db.Table(
    'producto_etiqueta',
    db.Column('ID_Producto', db.Integer, db.ForeignKey('Producto.ID_Producto'), primary_key=True),
    db.Column('ID_Etiqueta', db.Integer, db.ForeignKey('Etiqueta.ID_Etiqueta'), primary_key=True)
)

# ------------------ Relación en Producto ------------------
Producto.etiquetas = db.relationship(
    'Etiqueta',
    secondary=producto_etiqueta,
    backref=db.backref('productos', lazy='dynamic'),
    lazy='dynamic'
)

class ProductoDefectuoso(db.Model):
    __tablename__ = 'ProductoDefectuoso'

    ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_Usuario = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=False)
    ID_Producto = db.Column(db.Integer, db.ForeignKey('Producto.ID_Producto'), nullable=False)
    ID_Pedido = db.Column(db.Integer, db.ForeignKey('Pedido.ID_Pedido'), nullable=False)
    Motivo = db.Column(db.String(255), nullable=False)
    CitaProgramada = db.Column(db.DateTime, nullable=True)
    Estado = db.Column(
    db.Enum('pendiente', 'en_proceso', 'resuelto_tecnico', 'resuelto_devolucion', 'rechazada', name='estado_defectuoso'),
    nullable=False,
    default='pendiente'
)

    FechaRegistro = db.Column(db.DateTime, default=datetime.utcnow)
    ID_Empleado = db.Column(db.Integer, db.ForeignKey('Usuario.ID_Usuario'), nullable=True)
    usuario = db.relationship('Usuario', foreign_keys=[ID_Usuario], backref='productos_defectuosos_cliente')
    empleado = db.relationship('Usuario', foreign_keys=[ID_Empleado], backref='productos_defectuosos_tecnico')
    producto = db.relationship('Producto', backref='productos_defectuosos')
    pedido = db.relationship('Pedido', backref='productos_defectuosos')
    fotos = db.relationship('FotoProductoDefectuoso', backref='producto_defectuoso', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProductoDefectuoso ID={self.ID} Estado='{self.Estado}' CitaProgramada={self.CitaProgramada}>"
class FotoProductoDefectuoso(db.Model):
    __tablename__ = 'FotoProductoDefectuoso'

    ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_ProductoDefectuoso = db.Column(
        db.Integer,
        db.ForeignKey('ProductoDefectuoso.ID', ondelete='CASCADE'),
        nullable=False
    )
    RutaArchivo = db.Column(db.String(255), nullable=False)
    FechaSubida = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FotoProductoDefectuoso ID={self.ID} Ruta='{self.RutaArchivo}'>"


class GarantiaProducto(db.Model):
    __tablename__ = 'GarantiaProducto'

    ID_GarantiaProducto = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ID_Garantia = db.Column(db.Integer, db.ForeignKey('Garantia.ID_Garantia'), nullable=False)
    ID_Producto = db.Column(db.Integer, db.ForeignKey('Producto.ID_Producto'), nullable=False)

    garantia = db.relationship('Garantia', backref='productos_garantia')
    producto = db.relationship('Producto')