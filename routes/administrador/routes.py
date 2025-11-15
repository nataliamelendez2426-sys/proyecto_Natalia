import os
import json
from flask_login import current_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify,session
from flask_login import login_required, current_user
from datetime import date,datetime, timedelta
from flask import current_app
from basedatos.models import db, Usuario, Notificaciones, Direccion, Producto, Proveedor,Categorias,Resena,Compra,Pedido, Mensaje, Garantia ,Pagos, Categorias ,ProductoDefectuoso 
from werkzeug.security import generate_password_hash
from basedatos.decoradores import role_required
from basedatos.notificaciones import crear_notificacion
from werkzeug.utils import secure_filename
from sqlalchemy import func

UPLOAD_FOLDER = 'static/uploads/productos'

reviews = []

admin = Blueprint("admin", __name__, url_prefix="/admin")

# ---------- DASHBOARD ----------
@admin.route("/")
@login_required
@role_required("admin")
def dashboard():
    return render_template("administrador/admin_dashboard.html")

# ---------- GESTION_ROLES ----------
@admin.route("/gestion_roles", methods=["GET", "POST"])
@login_required
@role_required("admin")
def gestion_roles():
    roles_disponibles = ["admin", "cliente", "instalador", "transportista"]

    if request.method == "POST":
        user_id = request.form.get("user_id")
        nuevo_rol = request.form.get("rol")

        usuario = Usuario.query.get(user_id)
        if not usuario:
            flash("❌ Usuario no encontrado", "danger")
            return redirect(url_for("admin.gestion_roles"))

        usuario.Rol = nuevo_rol
        db.session.commit()

        flash(f"✅ Rol de {usuario.Nombre} actualizado a {nuevo_rol}", "success")
        return redirect(url_for("admin.gestion_roles"))

    # --- FILTRO ---
    q = request.args.get("q", "").strip()
    rol_filter = request.args.get("rol_filter", "").strip()

    usuarios_query = Usuario.query
    if q:
        usuarios_query = usuarios_query.filter(
            (Usuario.Nombre.ilike(f"%{q}%")) |
            (Usuario.Correo.ilike(f"%{q}%"))
        )
    if rol_filter:
        usuarios_query = usuarios_query.filter_by(Rol=rol_filter)

    usuarios = usuarios_query.all()
    # -----------------

    return render_template(
        "administrador/gestion_roles.html",
        usuarios=usuarios,
        roles=roles_disponibles,
        rol_filter=rol_filter,
        q=q
    )

# ---------- CAMBIAR_ROL ----------
@admin.route("/cambiar_rol/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def cambiar_rol(user_id):
    nuevo_rol = request.form["rol"]
    usuario = Usuario.query.get(user_id)

    if usuario:
        usuario.Rol = nuevo_rol
        db.session.commit()
        flash(f"✅ Rol de {usuario.Nombre} cambiado a {nuevo_rol}", "success")
    else:
        flash("❌ Usuario no encontrado", "danger")

    return redirect(url_for("admin.gestion_roles"))

# ---------- NOTIFICACIONES ----------
@admin.route("/notificaciones", methods=["GET", "POST"])
@login_required
@role_required("admin")
def ver_notificaciones():
    if request.method == "POST":
        ids = request.form.getlist("ids")
        if not ids:
            flash("❌ No seleccionaste ninguna notificación", "warning")
            return redirect(url_for("cliente.ver_notificaciones"))

        try:
            ids_int = [int(i) for i in ids if str(i).isdigit()]
            Notificaciones.query.filter(
                Notificaciones.ID_Usuario == current_user.ID_Usuario,
                Notificaciones.ID_Notificacion.in_(ids_int),
            ).delete(synchronize_session=False)
            db.session.commit()
            flash("✅ Notificaciones eliminadas", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error al eliminar: {e}", "danger")

        return redirect(url_for("admin.ver_notificaciones"))

    notificaciones = Notificaciones.query.filter_by(
        ID_Usuario=current_user.ID_Usuario
    ).order_by(Notificaciones.Fecha.desc()).all()

    return render_template("administrador/notificaciones_admin.html", notificaciones=notificaciones)


# ---------- ACTUALIZACION_DATOS ----------
@admin.route("/actualizacion_datos", methods=["GET", "POST"])
@login_required
@role_required("admin")
def actualizacion_datos():
    usuario = current_user
    direcciones = Direccion.query.filter_by(ID_Usuario=usuario.ID_Usuario).all()
    notificaciones = Notificaciones.query.filter_by(ID_Usuario=usuario.ID_Usuario).order_by(Notificaciones.Fecha.desc()).all()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        apellido = request.form.get("apellido", "").strip()
        correo = request.form.get("correo", "").strip()
        password = request.form.get("password", "").strip()

        if not nombre or not apellido or not correo:
            flash("⚠️ Los campos Nombre, Apellido y Correo son obligatorios.", "warning")
        else:
          
            usuario_existente = Usuario.query.filter(
                Usuario.Correo == correo,
                Usuario.ID_Usuario != usuario.ID_Usuario
            ).first()

            if usuario_existente:
                flash("El correo ya está registrado por otro usuario.", "danger")
            else:
                usuario.Nombre = nombre
                usuario.Apellido = apellido
                usuario.Correo = correo

                if password:
                    usuario.Contraseña = generate_password_hash(password)

                try:
                    db.session.commit()
                    crear_notificacion(
                        user_id=usuario.ID_Usuario,
                        titulo="Perfil actualizado ✏️",
                        mensaje="Tus datos personales se han actualizado correctamente."
                    )
                    flash("✅ Perfil actualizado correctamente", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"❌ Error al actualizar perfil: {str(e)}", "danger")

    return render_template(
        "administrador/admin_actualizacion_datos.html",
        usuario=usuario,
        direcciones=direcciones,
        notificaciones=notificaciones
    )


# ---------- AGREGAR DIRECCION ----------
@admin.route("/direccion/agregar", methods=["POST"])
@login_required
def agregar_direccion():
    try:
        direccion_valor = request.form.get("direccion", "").strip()
        if not direccion_valor:
            flash("⚠️ La dirección es obligatoria.", "warning")
            return redirect(url_for("admin.actualizacion_datos"))

        nueva_direccion = Direccion(
            ID_Usuario=current_user.ID_Usuario,
            Pais="Colombia",
            Departamento="Bogotá, D.C.",
            Ciudad="Bogotá",
            Direccion=direccion_valor,
            InfoAdicional=request.form.get("infoAdicional", "").strip(),
            Barrio=request.form.get("barrio", "").strip(),
            Destinatario=request.form.get("destinatario", "").strip()
        )
        db.session.add(nueva_direccion)
        db.session.commit()

        crear_notificacion(
            user_id=current_user.ID_Usuario,
            titulo="Dirección agregada 🏠",
            mensaje=f"Se ha agregado una nueva dirección: {nueva_direccion.Direccion}"
        )
        flash("Dirección agregada correctamente 🏠", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al agregar dirección: {str(e)}", "danger")

    return redirect(url_for("admin.actualizacion_datos"))


# ---------- BORRAR DIRECCION ----------
@admin.route("/direccion/borrar/<int:id_direccion>", methods=["POST"])
@login_required
def borrar_direccion(id_direccion):
    try:
        direccion = Direccion.query.get_or_404(id_direccion)
        db.session.delete(direccion)
        db.session.commit()

        crear_notificacion(
            user_id=current_user.ID_Usuario,
            titulo="Dirección eliminada 🗑️",
            mensaje=f"La dirección '{direccion.Direccion}' ha sido eliminada."
        )
        flash("Dirección eliminada correctamente 🗑️", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar dirección: {str(e)}", "danger")

    return redirect(url_for("admin.actualizacion_datos"))

# ---------- VER_PEDIDOS ----------


def get_pedidos_pendientes_usuario(usuario_id):
    pedidos = Pedido.query.filter_by(Estado='pendiente', ID_Usuario=usuario_id).all()
    pedidos_en_proceso = Pedido.query.filter_by(Estado='en proceso').all()
    
    pedidos_enriquecidos = []
    for pedido in pedidos:
        productos_info = []
        for detalle in pedido.detalles_pedido:
            producto = detalle.producto
            productos_info.append({
                'Nombre': producto.NombreProducto if producto else 'Producto no disponible',
                'Cantidad': detalle.Cantidad,
                'Imagen': producto.ImagenPrincipal if producto and producto.ImagenPrincipal else None
            })

        pedidos_enriquecidos.append({
            'ID': pedido.ID_Pedido,
            'Estado': pedido.Estado,
            'Productos': productos_info,
            'Nombre': pedido.NombreComprador,
            'Celular': pedido.usuario.Telefono if pedido.usuario else '',
            'Direccion': pedido.Destino
        })

    return pedidos_enriquecidos


def get_todos_los_pedidos():
    pedidos = Pedido.query.all()
    
    pedidos_enriquecidos = []
    for pedido in pedidos:
        productos_info = []
        for detalle in pedido.detalles_pedido:
            producto = detalle.producto
            productos_info.append({
                'Nombre': producto.NombreProducto if producto else 'Producto no disponible',
                'Cantidad': detalle.Cantidad,
                'Imagen': producto.ImagenPrincipal if producto and producto.ImagenPrincipal else None
            })

        pedidos_enriquecidos.append({
            'ID': pedido.ID_Pedido,
            'Estado': pedido.Estado or 'sin estado',
            'Productos': productos_info,
            'NombreComprador': pedido.NombreComprador,
            'TelefonoUsuario': pedido.usuario.Telefono if pedido.usuario else 'No disponible',
            'Direccion': pedido.Destino
        })

    return pedidos_enriquecidos



def get_usuario_actual():
    user_id = session.get('user_id')
    if user_id:
        return Usuario.query.get(user_id)
    return None


@admin.route('/ver_pedidos')
def ver_pedidos():
    now = datetime.now()

    # Filtros
    estado = (request.args.get('estado') or 'todos').strip()
    transportista_id = (request.args.get('transportista_id') or '').strip()
    q = (request.args.get('q') or '').strip()
    fecha_inicio = request.args.get('fecha_inicio') or ''
    fecha_fin = request.args.get('fecha_fin') or ''

    def apply_filters(query):
        if transportista_id and transportista_id.isdigit():
            query = query.filter(Pedido.ID_Empleado == int(transportista_id))
        if q:
            query = query.filter(
                (Pedido.NombreComprador.ilike(f"%{q}%")) |
                (Pedido.Destino.ilike(f"%{q}%"))
            )
        if fecha_inicio:
            try:
                fi = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                query = query.filter(Pedido.FechaPedido >= fi)
            except ValueError:
                pass
        if fecha_fin:
            try:
                ff = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                query = query.filter(Pedido.FechaPedido <= ff)
            except ValueError:
                pass
        return query

    # Actualiza estados a entregado si ya pasó la hora de llegada
    _en_proceso_all = Pedido.query.filter_by(Estado='en proceso').all()
    for pedido in _en_proceso_all:
        if pedido.HoraLlegada and pedido.HoraLlegada <= now:
            pedido.Estado = 'entregado'
            db.session.add(pedido)
    db.session.commit()

    pedidos_pendientes = []
    pedidos_en_proceso = []
    pedidos_entregados = []

    if estado in ('pendiente', 'en proceso', 'entregado'):
        base = Pedido.query.filter_by(Estado=estado)
        base = apply_filters(base)
        if estado == 'pendiente':
            pedidos_pendientes = base.all()
        elif estado == 'en proceso':
            pedidos_en_proceso = base.all()
        else:
            pedidos_entregados = base.all()
    else:
        pedidos_pendientes = apply_filters(Pedido.query.filter_by(Estado='pendiente')).all()
        pedidos_en_proceso = apply_filters(Pedido.query.filter_by(Estado='en proceso')).all()
        pedidos_entregados = apply_filters(Pedido.query.filter_by(Estado='entregado')).all()

    usuarios_transportistas = Usuario.query.filter_by(Rol='transportista').all()

    return render_template(
        'administrador/ver_pedidos.html',
        pedidos_pendientes=pedidos_pendientes,
        pedidos_en_proceso=pedidos_en_proceso,
        pedidos_entregados=pedidos_entregados,
        usuarios_transportistas=usuarios_transportistas,
        filtros={
            'estado': estado,
            'transportista_id': transportista_id,
            'q': q,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
        }
    )


# ---------- AGREGAR PRODUCTO ----------
@admin.route('/productos', methods=['GET', 'POST'])
def lista_productos():
    productos = Producto.query.all()  
    proveedores = Proveedor.query.all() 
    categorias = Categorias.query.all()

    if request.method == 'POST':
      
        pass

    return render_template(
        'Administrador/productos.html', 
        productos=productos, 
        proveedores=proveedores, 
        categorias=categorias
    )

@admin.route('/admin/agregar-producto', methods=['GET', 'POST'])
def agregar_producto():
    proveedores = Proveedor.query.all()
    categorias = Categorias.query.all()

    if request.method == 'POST':
        nombre = request.form['nombre']
        stock = int(request.form['stock'])
        material = request.form.get('material', '')  # Previene error si no se envía
        precio = float(request.form['precio'])
        color = request.form.get('color', '')
        id_proveedor = int(request.form['proveedor'])
        id_categoria = int(request.form['categoria'])

        # Manejo de imagen
        imagen = request.files.get('imagen_principal')
        imagen_ruta = 'img/default.png'

        if imagen and imagen.filename != '':
            filename = secure_filename(imagen.filename)
            ruta_img = os.path.join(current_app.static_folder, 'img', filename)
            imagen.save(ruta_img)
            imagen_ruta = f'img/{filename}'

        # Crear producto
        nuevo = Producto(
            NombreProducto=nombre,
            Stock=stock,
            Material=material,
            PrecioUnidad=precio,
            Color=color,
            ID_Proveedor=id_proveedor,
            ID_Categoria=id_categoria,
            ImagenPrincipal=imagen_ruta
        )

        db.session.add(nuevo)
        db.session.commit()
        flash('Producto agregado con éxito', 'success')
        return redirect(url_for('admin.agregar_producto'))

    return render_template('administrador/agregar_producto.html',
                           proveedores=proveedores,
                           categorias=categorias)

@admin.route('/productos/editar/<int:id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    producto = Producto.query.get_or_404(id_producto)

    if request.method == 'POST':
        try:
            # Datos del formulario
            producto.NombreProducto = request.form['nombre']
            producto.Stock = int(request.form['stock'])
            producto.PrecioUnidad = float(request.form['precio'])
            producto.Material = request.form.get('material', '')
            producto.Color = request.form.get('color', '')
            producto.Descripcion = request.form.get('descripcion', '')
            producto.ID_Proveedor = int(request.form['proveedor'])
            producto.ID_Categoria = int(request.form['categoria'])

            # Imagen (opcional)
            if 'imagen' in request.files:
                imagen = request.files['imagen']
                if imagen and imagen.filename != '':
                    filename = secure_filename(imagen.filename)
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    imagen_path = os.path.join(UPLOAD_FOLDER, filename)
                    imagen.save(imagen_path)
                    producto.ImagenPrincipal = f'uploads/productos/{filename}'

            db.session.commit()
            flash('✅ Producto actualizado correctamente', 'success')
            return redirect(url_for('admin.lista_productos'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar el producto: {e}', 'danger')

    # Datos para el formulario
    proveedores = Proveedor.query.all()
    categorias = Categorias.query.all()

    return render_template(
        'administrador/editar_producto.html',
        producto=producto,
        proveedores=proveedores,
        categorias=categorias
    )

# ---------- RESEÑAS ----------


@admin.route('/resenas')
@login_required
def ver_resenas():
    productos = db.session.query(Producto).all()
    return render_template('administrador/ver_reseñas.html', productos=productos)

# ---------- ESTADISTICAS ----------

@admin.route('/estadisticas')
@login_required
def estadisticas_reseñas():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    canal = request.args.get('canal', 'todos')
    segmento = request.args.get('segmento', 'todos')

    query = Resena.query

    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            query = query.filter(Resena.Fecha >= fecha_inicio_dt)
        except:
            pass

    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")
            query = query.filter(Resena.Fecha <= fecha_fin_dt)
        except:
            pass

    if canal != 'todos':
        query = query.filter(Resena.canal == canal)

    if segmento != 'todos':
        query = query.filter(Resena.segmento_cliente == segmento)

    reseñas_filtradas = query.all()

    
    rating_distribution = {str(i): 0 for i in range(1, 6)}
    total_respuestas = len(reseñas_filtradas)
    respuestas_positivas = 0
    comentarios_negativos_por_producto = {}

    for r in reseñas_filtradas:
        cal = r.Calificacion
        rating_distribution[str(cal)] += 1
        if cal >= 4:
            respuestas_positivas += 1
        elif cal <= 2:
            nombre_producto = r.producto.NombreProducto
            comentarios_negativos_por_producto[nombre_producto] = comentarios_negativos_por_producto.get(nombre_producto, 0) + 1

    porcentaje_positivas = round((respuestas_positivas / total_respuestas) * 100, 2) if total_respuestas else 0

 
    productos_data = []
    productos = Producto.query.all()

    for producto in productos:
        reseñas_producto = [r for r in reseñas_filtradas if r.ID_Producto == producto.ID_Producto]
        if reseñas_producto:
            suma = sum(r.Calificacion for r in reseñas_producto)
            cantidad = len(reseñas_producto)
            promedio = round(suma / cantidad, 2)
            productos_data.append({
                'nombre': producto.NombreProducto,
                'promedio': promedio,
                'cantidad': cantidad
            })

   
    from sqlalchemy import func
    compras_por_mes = (
        db.session.query(
            func.date_format(Resena.Fecha, "%Y-%m").label("mes"),
            func.count(Resena.ID_Resena)
        )
        .filter(Resena.ID_Resena.in_([r.ID_Resena for r in reseñas_filtradas]))
        .group_by("mes")
        .order_by("mes")
        .all()
    )

   
    resolucion_por_mes = {
        "2023-05": 12,
        "2023-06": 17,
        "2023-07": 14,
        "2023-08": 19,
        "2023-09": 21,
    }

    return render_template('administrador/estadisticas.html',
        filtros={
            "fecha_inicio": fecha_inicio or '',
            "fecha_fin": fecha_fin or '',
            "canal": canal,
            "segmento": segmento
        },
        total_respuestas=total_respuestas,
        porcentaje_positivas=porcentaje_positivas,
        distribucion_json=json.dumps(rating_distribution),
        comentarios_negativos=comentarios_negativos_por_producto,
        productos=productos_data,
        compras_por_mes=compras_por_mes,
        resolucion_json=json.dumps(resolucion_por_mes)
    )

# ---------- PROVEEDORES ----------

@admin.route('/proveedores', methods=['GET'])
@login_required
@role_required("admin")
def vista_proveedores():
    return render_template('administrador/proveedores.html')



@admin.route('/api/proveedores', methods=['GET'])
@login_required
@role_required("admin")
def obtener_proveedores():
    try:
        proveedores = Proveedor.query.all()
        data = [
            {
                "id": p.ID_Proveedor,
                "empresa": p.NombreEmpresa,
                "contacto": p.NombreContacto,
                "cargo": p.CargoContacto,
                "direccion": p.Direccion,
                "ciudad": p.Ciudad,
                "pais": p.Pais,
                "telefono": p.Telefono
            } for p in proveedores
        ]
        return jsonify(data), 200
    except Exception as e:
        print("❌ ERROR GET PROVEEDORES:", e)
        return jsonify({"mensaje": "Error interno"}), 500



@admin.route('/api/proveedores', methods=['POST'])
@login_required
@role_required("admin")
def agregar_proveedor():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"mensaje": "No se recibió JSON válido"}), 400

        nuevo = Proveedor(
            NombreEmpresa=data.get('empresa'),
            NombreContacto=data.get('contacto'),
            CargoContacto=data.get('cargo'),
            Direccion=data.get('direccion'),
            Ciudad=data.get('ciudad'),
            Pais=data.get('pais'),
            Telefono=data.get('telefono')
        )

        db.session.add(nuevo)
        db.session.commit()
        return jsonify({"mensaje": "Proveedor agregado correctamente ✅"}), 201
    except Exception as e:
        db.session.rollback()
        print("❌ ERROR POST PROVEEDOR:", e)
        return jsonify({"mensaje": "Error al guardar el proveedor ❌"}), 500



@admin.route('/api/proveedores/<int:id>', methods=['PUT'])
@login_required
@role_required("admin")
def editar_proveedor(id):
    try:
        proveedor = Proveedor.query.get_or_404(id)
        data = request.get_json()

        proveedor.NombreEmpresa = data.get('empresa', proveedor.NombreEmpresa)
        proveedor.NombreContacto = data.get('contacto', proveedor.NombreContacto)
        proveedor.CargoContacto = data.get('cargo', proveedor.CargoContacto)
        proveedor.Direccion = data.get('direccion', proveedor.Direccion)
        proveedor.Ciudad = data.get('ciudad', proveedor.Ciudad)
        proveedor.Pais = data.get('pais', proveedor.Pais)
        proveedor.Telefono = data.get('telefono', proveedor.Telefono)

        db.session.commit()
        return jsonify({"mensaje": "Proveedor actualizado correctamente ✅"}), 200
    except Exception as e:
        db.session.rollback()
        print("❌ ERROR PUT PROVEEDOR:", e)
        return jsonify({"mensaje": "Error al editar el proveedor ❌"}), 500



@admin.route('/api/proveedores/<int:id>', methods=['DELETE'])
@login_required
@role_required("admin")
def eliminar_proveedor(id):
    try:
        proveedor = Proveedor.query.get_or_404(id)
        db.session.delete(proveedor)
        db.session.commit()
        return jsonify({"mensaje": "Proveedor eliminado ✅"}), 200
    except Exception as e:
        db.session.rollback()
        print("❌ ERROR DELETE PROVEEDOR:", e)
        return jsonify({"mensaje": "Error al eliminar proveedor ❌"}), 500



@admin.route('/api/compras', methods=['GET'])
@login_required
def obtener_compras():
    compras = Compra.query.all()
    data = []
    for c in compras:
        data.append({
            "id": c.ID_Compra,
            "producto": c.Producto,
            "cantidad": c.Cantidad,
            "proveedor": c.proveedor.NombreEmpresa,  
            "fecha": c.Fecha.strftime('%Y-%m-%d')
        })
    return jsonify(data), 200

@admin.route('/api/compras', methods=['POST'])
@login_required
def agregar_compra():
    try:
        data = request.get_json()
      
        proveedor = Proveedor.query.get(data['proveedor_id'])
        if not proveedor:
            return jsonify({"mensaje": "Proveedor no encontrado"}), 404

       
        fecha_obj = datetime.strptime(data['fecha'], '%Y-%m-%d').date()

        nueva = Compra(
            Producto=data['producto'],
            Cantidad=data['cantidad'],
            Fecha=fecha_obj,
            ProveedorID=proveedor.ID_Proveedor
        )
        db.session.add(nueva)
        db.session.commit()
        return jsonify({"mensaje": "Compra registrada correctamente ✅"}), 201

    except Exception as e:
        db.session.rollback()
        print("Error al registrar compra:", e)
        return jsonify({"mensaje": "Error al registrar compra ❌"}), 500
    
# ---------- ASIGNAR_TRANSPORTISTA ----------

@admin.route('/asignar_transportista/<int:id_pedido>', methods=['POST'])
def asignar_transportista(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)

    transportista_id = request.form.get('transportista_id')
    hora_llegada_str = request.form.get('hora_llegada')


    if not transportista_id or not hora_llegada_str:
        flash('Por favor, completa todos los campos.', 'warning')
        return redirect(url_for('admin.ver_pedidos'))

  
    transportista = Usuario.query.get(transportista_id)
    if not transportista:
        flash('El transportista no existe.', 'danger')
        return redirect(url_for('admin.ver_pedidos'))

 
    try:
        hora_llegada = datetime.strptime(hora_llegada_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('El formato de la hora de llegada no es válido.', 'danger')
        return redirect(url_for('admin.ver_pedidos'))

   
    if pedido.Estado == 'en proceso':
        flash('Este pedido ya tiene un transportista asignado.', 'warning')
        return redirect(url_for('admin.ver_pedidos'))

   
    pedido.ID_Empleado = int(transportista_id)
    pedido.HoraLlegada = hora_llegada
    pedido.Estado = 'en proceso'  

    db.session.commit()

    flash(f'Transportista {transportista.Nombre} asignado al pedido #{id_pedido} correctamente.', 'success')
    return redirect(url_for('admin.ver_pedidos'))

# ---------- REPORTES ----------

@admin.route('/reportes')
def reporte_entregas():
    pedidos_entregados = Pedido.query.filter_by(Estado='entregado').all()

   

    return render_template(
        'administrador/reportes_entregas.html',
        pedidos_entregados=pedidos_entregados
    )


# ---------- CHAT_EN_TIEMPO_REAL ----------

@admin.route('/chat', methods=['GET'])
@login_required
def chat_admin():
    
    clientes = (
        db.session.query(Usuario)
        .join(Mensaje, Usuario.ID_Usuario == Mensaje.cliente_id)
        .filter(Mensaje.enviado_admin == False)  
        .distinct()
        .all()
    )

    mensajes = []

    return render_template('Administrador/chat.html', clientes=clientes, mensajes=mensajes)


@admin.route('/chat/enviar_mensaje', methods=['POST'])
@login_required
def enviar_mensaje_admin():
    data = request.get_json()
    contenido = data.get('contenido')
    cliente_id = data.get('cliente_id')

    if not contenido or not cliente_id:
        return jsonify({'status': 'error', 'message': 'Faltan datos'})

    msg = Mensaje(cliente_id=cliente_id, contenido=contenido, enviado_admin=True)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'status': 'ok'})

@admin.route('/chat/mensajes/<int:cliente_id>', methods=['GET'])
@login_required
def mensajes_cliente(cliente_id):
    mensajes = Mensaje.query.filter_by(cliente_id=cliente_id).order_by(Mensaje.fecha).all()
    mensajes_list = [
        {
            'contenido': m.contenido,
            'enviado_admin': m.enviado_admin,
            'cliente_nombre': m.cliente.Nombre
        } for m in mensajes
    ]
    return jsonify(mensajes_list)

@admin.route('/garantias')
@login_required
def ver_garantias():
    if current_user.Rol != 'admin':
        flash("No tienes permisos para acceder a esta sección", "danger")
        return redirect(url_for('cliente.index'))

    # Traer garantías con usuario y productos relacionados
    garantias = Garantia.query.order_by(Garantia.FechaSolicitud.desc()).all()
    return render_template('administrador/garantia_lista.html', garantias=garantias)


@admin.route('/garantia/<int:garantia_id>')
@login_required
def detalle_garantia(garantia_id):
    if current_user.Rol != 'admin':
        flash("No tienes permisos", "danger")
        return redirect(url_for('cliente.index'))

    garantia = Garantia.query.get_or_404(garantia_id)

    # Traer solo los usuarios con rol instalador
    instaladores = Usuario.query.filter_by(Rol='instalador').all()

    return render_template(
        'administrador/detalle_garantia.html',
        garantia=garantia,
        instaladores=instaladores
    )


@admin.route('/garantia/<int:garantia_id>/actualizar', methods=['POST'])
@login_required
def actualizar_garantia(garantia_id):
    if current_user.Rol != 'admin':
        flash("No tienes permisos", "danger")
        return redirect(url_for('cliente.index'))

    garantia = Garantia.query.get_or_404(garantia_id)
    nuevo_estado = request.form.get('estado')
    comentario = request.form.get('comentario')
    instalador_id = request.form.get('instalador_id')

    garantia.Estado = nuevo_estado
    garantia.ComentarioAdmin = comentario
    garantia.FechaResolucion = datetime.utcnow()

    # Asignar instalador si el estado es aprobada y hay uno seleccionado
    if nuevo_estado == 'aprobada' and instalador_id:
        garantia.ID_Empleado = int(instalador_id)

        # Crear notificación al cliente
        notificacion = Notificaciones(
            Titulo=f"Estado de garantía #{garantia.ID_Garantia}",
            Mensaje=f"Tu garantía #{garantia.ID_Garantia} ha sido aprobada. <a href='/cliente/notificaciones'>Agendar cita</a>",
            Fecha=datetime.utcnow(),
            Leida=False,
            ID_Usuario=garantia.ID_Usuario
        )
        db.session.add(notificacion)

    db.session.commit()  # Solo un commit al final

    flash("Garantía actualizada correctamente", "success")
    return redirect(url_for('admin.detalle_garantia', garantia_id=garantia.ID_Garantia))







# ---------- RECURSOS HUMANOS ----------

@admin.route('/recursos-humanos')
@login_required
def lista_empleados():
    """
    Lista todos los empleados que son instaladores o transportistas
    """
    empleados = Usuario.query.filter(Usuario.Rol.in_(['instalador', 'transportista'])).all()
    return render_template('recursos_humanos/lista_empleados.html', empleados=empleados)


@admin.route('/recursos-humanos/<int:id_empleado>', methods=['GET', 'POST'])
@login_required
def detalle_empleado(id_empleado):
    """
    Muestra detalle de un empleado, incluyendo pedidos, instalaciones,
    pagos y horas trabajadas. Permite actualizar horas diurnas y nocturnas
    y calcula automáticamente horas extra desde los pedidos.
    """
    empleado = Usuario.query.get_or_404(id_empleado)
    pedidos = Pedido.query.filter_by(ID_Empleado=id_empleado).all()

    # Recuperar horas existentes en DB o inicializar
    horas_diurnas = getattr(empleado, 'horas_diurnas', 0) or 0
    horas_nocturnas = getattr(empleado, 'horas_nocturnas', 0) or 0
    total_horas_extra = getattr(empleado, 'horas_extra', 0) or 0

    instalaciones = []

    # Procesar POST si se envían horas manualmente
    if request.method == 'POST':
        try:
            horas_diurnas = float(request.form.get('horas_diurnas', 0))
            horas_nocturnas = float(request.form.get('horas_nocturnas', 0))
        except ValueError:
            flash("Horas inválidas, ingrese números válidos.", "danger")
            return redirect(url_for('admin.detalle_empleado', id_empleado=id_empleado))

       
        empleado.horas_diurnas = horas_diurnas
        empleado.horas_nocturnas = horas_nocturnas

        db.session.commit()
        flash("Horas actualizadas correctamente.", "success")
        return redirect(url_for('admin.detalle_empleado', id_empleado=id_empleado))

    
    total_horas = 0
    total_horas_extra = 0
    for pedido in pedidos:
        if pedido.HoraLlegada and pedido.FechaEntrega:
 
            if isinstance(pedido.FechaEntrega, date) and not isinstance(pedido.FechaEntrega, datetime):
                fecha_entrega_dt = datetime.combine(pedido.FechaEntrega, datetime.min.time())
            else:
                fecha_entrega_dt = pedido.FechaEntrega

            horas = (fecha_entrega_dt - pedido.HoraLlegada).total_seconds() / 3600
            total_horas += horas
            if horas > 8: 
                total_horas_extra += horas - 8

       
        eventos_instalacion = [c for c in pedido.calendario if c.Tipo and c.Tipo.lower() == 'instalacion']
        instalaciones.extend(eventos_instalacion)


    empleado.horas_totales = total_horas
    empleado.horas_extra = total_horas_extra
    db.session.commit()

   
    pagos = Pagos.query.join(Pedido).filter(Pedido.ID_Empleado == id_empleado).all()
    pagos_por_mes = {}
    for pago in pagos:
        if pago.FechaPago:
            mes = pago.FechaPago.strftime('%Y-%m')
            pagos_por_mes[mes] = pagos_por_mes.get(mes, 0) + pago.Monto

    return render_template(
        'recursos_humanos/detalle_empleado.html',
        empleado=empleado,
        pedidos=pedidos,
        total_horas=round(total_horas, 2),
        total_horas_extra=round(total_horas_extra, 2),
        instalaciones=instalaciones,
        pagos_por_mes=pagos_por_mes,
        horas_diurnas=horas_diurnas,
        horas_nocturnas=horas_nocturnas
    )


@admin.route('/finanzas')
def admin_finanzas():
    pagos = Pagos.query.order_by(Pagos.FechaPago.desc()).all()
    total_pagos = sum(p.Monto for p in pagos)


    metodos = {
        'credito': 0,
        'nequi': 0,
        'daviplata': 0,
        'efectivo': 0
    }

    for p in pagos:
        if p.MetodoPago in metodos:
            metodos[p.MetodoPago] += p.Monto

    return render_template('administrador/finanzas.html', pagos=pagos, total_pagos=total_pagos, metodos=metodos)

@admin.route('/finanzas/ajax')
def finanzas_ajax():
    metodo = request.args.get('metodo', type=str)
    fecha_inicio = request.args.get('fecha_inicio', type=str)
    fecha_fin = request.args.get('fecha_fin', type=str)

    query = Pagos.query.join(Pagos.pedido).join(Pedido.usuario)

    # Normalización de métodos
    metodo_map = {
        'Tarjeta': 'credito',
        'Transferencia': 'credito',
        'efectivo': 'efectivo',
        'Efectivo': 'efectivo',
        'nequi': 'nequi',
        'daviplata': 'daviplata'
    }

    # Filtrado por método
    if metodo:
        # Buscamos en los valores originales que correspondan al método normalizado
        query = query.filter(Pagos.MetodoPago.in_([k for k, v in metodo_map.items() if v == metodo]))

    # Filtrado por fechas
    if fecha_inicio:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        query = query.filter(Pagos.FechaPago >= fecha_inicio_dt)
    if fecha_fin:
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
        query = query.filter(Pagos.FechaPago <= fecha_fin_dt)

    pagos = query.order_by(Pagos.FechaPago.desc()).all()

    # Total y estadísticas
    total = sum(p.Monto for p in pagos)

    metodos = { 'credito': 0, 'nequi': 0, 'daviplata': 0, 'efectivo': 0 }
    for p in pagos:
        clave = metodo_map.get(p.MetodoPago)
        if clave:
            metodos[clave] += p.Monto

    # Preparar JSON
    pagos_json = []
    for p in pagos:
        pagos_json.append({
            "ID_Pagos": p.ID_Pagos,
            "usuario": {
                "Nombre": p.pedido.usuario.Nombre,
                "Apellido": p.pedido.usuario.Apellido or ""
            },
            "MetodoPago": metodo_map.get(p.MetodoPago, p.MetodoPago),
            "FechaPago": p.FechaPago.strftime('%Y-%m-%d'),
            "Monto": p.Monto
        })

    return jsonify({
        "pagos": pagos_json,
        "total": total,
        "metodos": metodos
    })

@admin.route('/admin/productos_defectuosos')
@login_required
@role_required('admin')
def admin_productos_defectuosos():
    registros = ProductoDefectuoso.query.order_by(ProductoDefectuoso.FechaRegistro.desc()).all()
    instaladores = Usuario.query.filter_by(Rol='instalador', Activo=True).all()

    return render_template(
        'administrador/productos_defectuosos.html',
        registros=registros,
        instaladores=instaladores
    )


@admin.route('/admin/solucionar_defecto/<int:id_garantia>', methods=['POST'])
@login_required
@role_required('admin')
def solucionar_defecto(id_garantia):
    # Obtener el registro de producto defectuoso
    garantia = ProductoDefectuoso.query.get_or_404(id_garantia)

    accion = request.form.get('accion')
    empleado_id = request.form.get('empleado')
    motivo_rechazo = request.form.get('motivo_rechazo', '').strip()

    # Caso: Producto rechazado
    if accion == 'rechazada':
        if not motivo_rechazo:
            flash("Debes ingresar el motivo del rechazo.", "danger")
            return redirect(url_for('admin.admin_productos_defectuosos'))

        garantia.Estado = 'rechazada'
        garantia.ComentarioAdmin = motivo_rechazo
        garantia.ID_Empleado = None  # No necesita técnico

        mensaje = f"Tu reporte de producto defectuoso ha sido <strong>rechazado</strong>."
        mensaje += f"<br>Motivo: {motivo_rechazo}"

    else:
        # Para otras acciones, se requiere técnico
        if not empleado_id:
            flash("Debes seleccionar un técnico.", "danger")
            return redirect(url_for('admin.admin_productos_defectuosos'))

        tecnico = Usuario.query.get(empleado_id)
        if not tecnico or tecnico.Rol != 'instalador':
            flash("El empleado seleccionado no es válido.", "danger")
            return redirect(url_for('admin.admin_productos_defectuosos'))

        garantia.ID_Empleado = tecnico.ID_Usuario

        estados = {
            "proceso": "en_proceso",
            "tecnico": "resuelto_tecnico",
            "devolucion": "resuelto_devolucion"
        }

        if accion not in estados:
            flash("Acción inválida.", "danger")
            return redirect(url_for('admin.admin_productos_defectuosos'))

        garantia.Estado = estados[accion]

        # Crear mensaje según acción
        if accion == "proceso":
            mensaje = (
                f"El técnico <strong>{tecnico.Nombre}</strong> fue asignado para revisar tu producto defectuoso."
                f"<br>Puedes agendar la cita con él a continuación."
                f"<br><button class='btn btn-sm btn-success mt-2' "
                f"data-bs-toggle='modal' data-bs-target='#agendarCitaModal{garantia.ID}'>"
                f"Agendar cita</button>"
            )
        elif accion == "tecnico":
            mensaje = f"El técnico {tecnico.Nombre} ha reparado tu producto defectuoso."
        elif accion == "devolucion":
            mensaje = "Tu producto defectuoso ha sido devuelto y se procesará el reembolso correspondiente."

    # Guardar cambios y notificación
    db.session.commit()

    notificacion = Notificaciones(
        Titulo="Actualización de producto defectuoso",
        Mensaje=mensaje,
        Fecha=datetime.utcnow(),
        Leida=False,
        ID_Usuario=garantia.ID_Usuario,
        ID_Defecto=garantia.ID
    )

    db.session.add(notificacion)
    db.session.commit()

    flash("Estado actualizado y notificación enviada correctamente.", "success")
    return redirect(url_for('admin.admin_productos_defectuosos'))