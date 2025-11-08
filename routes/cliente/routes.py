from flask_login import current_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from basedatos.models import db, Usuario, Notificaciones, Direccion, Calendario,Pedido, Producto, Resena, Detalle_Pedido, Pagos,Mensaje,Garantia ,GarantiaArchivo
from basedatos.decoradores import role_required
from basedatos.notificaciones import crear_notificacion
from datetime import date,datetime
from flask import render_template
from sqlalchemy import text
from flask_mail import Message
from flask import url_for
from basedatos.decoradores import mail


favoritos_usuario = set() 

from . import cliente
reviews = []

# ---------- DASHBOARD ----------
@cliente.route("/dashboard")
@login_required
@role_required("cliente")
def dashboard():
    mostrar_bienvenida = session.pop('mostrar_bienvenida', False)
    nombre_completo = session.get('username', '')  
    
    return render_template(
        "cliente/dashboard.html",
        mostrar_bienvenida=mostrar_bienvenida,
        nombre_completo=nombre_completo
    )


# ---------- NOTIFICACIONES ----------
@cliente.route("/notificaciones", methods=["GET", "POST"])
@login_required
def ver_notificaciones_cliente():
    if request.method == "POST":
        ids = request.form.getlist("ids")
        if ids:
            try:
                Notificaciones.query.filter(
                    Notificaciones.ID_Usuario == current_user.ID_Usuario,
                    Notificaciones.ID_Notificacion.in_(ids)
                ).delete(synchronize_session=False)
                db.session.commit()
                flash("✅ Notificaciones eliminadas", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error al eliminar: {str(e)}", "danger")
        return redirect(url_for("cliente.ver_notificaciones_cliente"))

    notificaciones = Notificaciones.query.filter_by(ID_Usuario=current_user.ID_Usuario).order_by(Notificaciones.Fecha.desc()).all()
    return render_template("cliente/notificaciones_cliente.html", notificaciones=notificaciones)


# ---------- PERFIL Y DIRECCIONES ----------
@cliente.route("/actualizacion_datos", methods=["GET", "POST"])
@login_required
@role_required("cliente", "admin")
def actualizacion_datos():
    usuario = current_user
    direcciones = Direccion.query.filter_by(ID_Usuario=usuario.ID_Usuario).all()
    notificaciones = Notificaciones.query.filter_by(
        ID_Usuario=usuario.ID_Usuario
    ).order_by(Notificaciones.Fecha.desc()).all()

    
    pedidos = Pedido.query.filter_by(ID_Usuario=usuario.ID_Usuario).order_by(Pedido.FechaPedido.desc()).all()

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
                db.session.commit()
                crear_notificacion(
                    user_id=usuario.ID_Usuario,
                    titulo="Perfil actualizado ✏️",
                    mensaje="Tus datos personales se han actualizado correctamente."
                )
                flash("✅ Perfil actualizado correctamente", "success")

    return render_template(
        "cliente/actualizacion_datos.html",
        usuario=usuario,
        direcciones=direcciones,
        pedidos=pedidos,  
        notificaciones=notificaciones
    )

@cliente.route("/direccion/agregar", methods=["POST"])
@login_required
def agregar_direccion():
    try:
        nueva_direccion = Direccion(
            ID_Usuario=current_user.ID_Usuario,
            Pais="Colombia",
            Departamento="Bogotá, D.C.",
            Ciudad="Bogotá",
            Direccion=request.form.get("direccion"),
            InfoAdicional=request.form.get("infoAdicional"),
            Barrio=request.form.get("barrio"),
            Destinatario=request.form.get("destinatario")
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

    return redirect(url_for("cliente.actualizacion_datos"))

@cliente.route("/direccion/borrar/<int:id_direccion>", methods=["POST"])
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

    return redirect(url_for("cliente.actualizacion_datos"))

@cliente.route('/perfil')
@login_required
def perfil():
    return redirect(url_for('cliente.actualizacion_datos'))

# ---------- DETALLE_PEDIDO ----------


@cliente.route("/pedido/<int:id_pedido>/detalle")
@login_required
def ver_detalle_pedido(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)

    try:
        detalles = pedido.detalles_pedido  
    except Exception as e:
        print("Error detalles pedido:", e)
        detalles = []

    return render_template(
        "Common/partials/detalle_pedido.html",
        pedido=pedido,
        detalles=detalles
    )





# ---------- AGENDAR_INSTALACION ----------

@cliente.route('/cliente/instalacion', methods=['GET', 'POST'])
@login_required
def agendar_instalacion():
    if request.method == 'POST':
        pedido_id = request.form.get('pedido_id')
        fecha = request.form.get('fecha')
        hora = request.form.get('hora')
        ubicacion = request.form.get('ubicacion')

        if not (pedido_id and fecha and hora and ubicacion):
            return jsonify({'success': False, 'message': 'Por favor completa todos los campos'}), 400

        nueva_cita = Calendario(
            Fecha=fecha,
            Hora=hora,
            Ubicacion=ubicacion,
            Tipo='Instalación',
            ID_Usuario=current_user.ID_Usuario,
            ID_Pedido=pedido_id
        )

        db.session.add(nueva_cita)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Instalación agendada exitosamente'})

    # GET
    pedidos = Pedido.query.filter_by(ID_Usuario=current_user.ID_Usuario).all()
    direcciones = Direccion.query.filter_by(ID_Usuario=current_user.ID_Usuario).all()

    return render_template('cliente/instalacion.html', pedidos=pedidos, direcciones=direcciones)

@cliente.route('/ver_instalaciones')
def ver_instalaciones():
    query = text("""
        SELECT 
            c.Fecha,
            c.Hora,
            c.Ubicacion,
            u.Nombre AS NombreUsuario
        FROM calendario c
        JOIN usuario u ON c.ID_Usuario = u.ID_Usuario
    """)

    result = db.session.execute(query)
    instalaciones = [dict(row) for row in result.mappings()] 

    return render_template("cliente/ver_instalaciones.html", instalaciones=instalaciones)



@cliente.route('/producto/<int:id>')
def detalle_producto_catalogo(id):
    producto = Producto.query.get_or_404(id)
    return render_template('cliente/detalle_producto_catalogo.html', producto=producto)

# ---------- RESEÑA ----------

@cliente.route('/productos/<int:id>/resena', methods=['GET'])
@login_required
def escribir_resena(id):
    producto = Producto.query.get_or_404(id)
    return render_template('cliente/escribir_reseña.html', producto=producto)


@cliente.route('/productos/<int:id>/resena', methods=['POST'])
@login_required
def guardar_resena(id):
    producto = Producto.query.get_or_404(id)
    calificacion = int(request.form.get('calificacion'))
    comentario = request.form.get('comentario')

    if not (1 <= calificacion <= 5):
        flash('La calificación debe estar entre 1 y 5.', 'danger')
        return redirect(url_for('cliente/escribir_reseña', id=id))

    if not comentario:
        flash('El comentario no puede estar vacío.', 'danger')
        return redirect(url_for('cliente/escribir_reseña', id=id))

    nueva_resena = Resena(
        ID_Producto=id,
        ID_Usuario=current_user.ID_Usuario,
        Calificacion=calificacion,
        Comentario=comentario
    )
    db.session.add(nueva_resena)
    db.session.commit()
    flash('Reseña creada exitosamente.', 'success')
    return redirect(url_for('cliente.detalle_producto_catalogo', id=id))  

# ---------- COMPARAR ----------

@cliente.route('/comparar')
def comparar():
    productos = Producto.query.all()  
    return render_template('cliente/comparar.html', productos=productos)

@cliente.route('/api/comprar', methods=['POST'])
@login_required
def comprar_producto():
    try:
        data = request.get_json()
        id_producto = int(data.get('ID_Producto'))
        id_direccion = int(data.get('ID_Direccion'))
        metodo_pago = data.get('MetodoPago')

       
        direccion = Direccion.query.filter_by(ID_Direccion=id_direccion, ID_Usuario=current_user.ID_Usuario).first()
        if not direccion:
            return jsonify({"mensaje":"Dirección no válida"}), 400

        producto = Producto.query.get(id_producto)
        if not producto:
            return jsonify({"mensaje":"Producto no encontrado"}), 404


        pedido = Pedido(
            NombreComprador=current_user.Nombre,
            Estado='pendiente',
            FechaPedido=datetime.today().date(),
            Destino=f"{direccion.Direccion}, {direccion.Barrio}, {direccion.Ciudad}, {direccion.Departamento}, {direccion.Pais}",
            Descuento=0.0,
            ID_Usuario=current_user.ID_Usuario
        )
        db.session.add(pedido)
        db.session.commit()  

       
        detalle = Detalle_Pedido(
            ID_Pedido=pedido.ID_Pedido,
            ID_Producto=producto.ID_Producto,
            Cantidad=1,
            PrecioUnidad=producto.PrecioUnidad
        )
        db.session.add(detalle)


        pago = Pagos(
            MetodoPago=metodo_pago,
            FechaPago=datetime.today().date(),
            Monto=producto.PrecioUnidad,
            ID_Pedido=pedido.ID_Pedido
        )
        db.session.add(pago)

        db.session.commit()
        return jsonify({"mensaje":"Compra registrada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print("Error al realizar la compra:", e)
        return jsonify({"mensaje":"Error al realizar la compra"}), 500

@cliente.route('/api/direcciones', methods=['GET'])
@login_required
def get_direcciones():
    direcciones = Direccion.query.filter_by(ID_Usuario=current_user.ID_Usuario).all()
    data = []
    for d in direcciones:
        data.append({
            "id": d.ID_Direccion,
            "pais": d.Pais,
            "departamento": d.Departamento,
            "ciudad": d.Ciudad,
            "direccion": d.Direccion,
            "barrio": d.Barrio,
            "destinatario": d.Destinatario,
            "info": d.InfoAdicional
        })
    return jsonify(data)

# ---------- CHAT_EN_TIEMPO_REAL ----------

@cliente.route('/chat', methods=['GET'])
@login_required
def chat_cliente():
    # Filtrar mensajes solo del cliente actual
    mensajes = Mensaje.query.filter_by(cliente_id=current_user.ID_Usuario).order_by(Mensaje.fecha).all()
    return render_template('Cliente/chat.html', mensajes=mensajes)


@cliente.route('/chat/enviar_mensaje', methods=['POST'])
@login_required
def enviar_mensaje_cliente():
    data = request.get_json()
    contenido = data.get('contenido')

    if not contenido:
        return jsonify({'status': 'error', 'message': 'Faltan datos'})

    msg = Mensaje(cliente_id=current_user.ID_Usuario, contenido=contenido, enviado_admin=False)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'status': 'ok'})

@cliente.route('/chat/mensajes')
@login_required
def mensajes_cliente_ajax():
    mensajes = Mensaje.query.filter_by(cliente_id=current_user.ID_Usuario).order_by(Mensaje.fecha).all()
    return jsonify([
        {
            'contenido': m.contenido,
            'enviado_admin': m.enviado_admin,
            'cliente_nombre': m.cliente.Nombre
        } for m in mensajes
    ])

# ---------- CARRITO ----------

@cliente.route('/carrito')
@login_required
def ver_carrito():
    return render_template('Cliente/carrito.html')

@cliente.route('/checkout', methods=['POST'])
@login_required
def checkout():
    data = request.get_json()
    direccion_id = data.get('direccion')
    carrito = data.get('carrito', [])
    metodo_pago = data.get('metodo')

    if not carrito:
        return jsonify({"success": False, "mensaje": "El carrito está vacío."})

    # 1. Guardar pedido en la base de datos
    pedido = Pedido(
        ID_Usuario=current_user.id,
        Destino="Dirección seleccionada o calculada",
        Estado="pendiente",
        FechaPedido=date.today(),
        # aquí podrías agregar más campos como método de pago
    )
    db.session.add(pedido)
    db.session.commit()

    # 2. Guardar detalles del pedido
    for item in carrito:
        detalle = Detalle_Pedido(
            ID_Pedido=pedido.ID_Pedido,
            ID_Producto=item['id'],
            Cantidad=item.get('cantidad', 1)
        )
        db.session.add(detalle)
    db.session.commit()

    # 3. Enviar correo con información del pedido
    link_pdf = url_for('cliente.ver_pedido_pdf', id_pedido=pedido.ID_Pedido, _external=True)
    msg = Message(
        subject=f"Detalle de tu pedido #{pedido.ID_Pedido}",
        sender='tuemail@dominio.com',
        recipients=[current_user.Email]
    )
    msg.html = f"""
    <p>Hola {current_user.Nombre},</p>
    <p>Gracias por tu compra. Aquí tienes la información de tu pedido:</p>
    <ul>
        <li>ID Pedido: {pedido.ID_Pedido}</li>
        <li>Dirección: {pedido.Destino}</li>
        <li>Método de pago: {metodo_pago}</li>
        <li>Total: ${sum([i['precio']*i.get('cantidad',1) for i in carrito]):.2f}</li>
    </ul>
    <p>Para descargar el PDF de tu pedido, haz clic en el siguiente botón:</p>
    <p><a href="{link_pdf}" style="background-color:#57a773;color:white;padding:10px 20px;border-radius:5px;text-decoration:none;">Exportar PDF</a></p>
    """
    mail.send(msg)

    return jsonify({"success": True, "mensaje": "Pago procesado correctamente."})

@cliente.route('/finalizar-compra', methods=['POST'])
@login_required
def finalizar_compra():
    nombre = request.form.get('nombre')
    direccion_id = request.form.get('select-direccion')
    metodo_pago = request.form.get('pago')
    numero_tarjeta = request.form.get('numero-tarjeta')
    numero_celular = request.form.get('numero-celular')


    flash(f'✅ Pago con {metodo_pago} realizado correctamente', 'success')
    return redirect(url_for('catalogo'))


# ---------- SEGUIMIENTO ----------

@cliente.route('/seguimiento/<int:id_pedido>')
@login_required
def seguimiento_cliente(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)

    if pedido.ID_Usuario != current_user.id and current_user.Rol not in ['admin', 'transportista']:
        return "Acceso denegado ❌", 403

 
    transportista = pedido.empleado  

    return render_template(
        'cliente/seguimiento.html',
        pedido=pedido,
        transportista=transportista
    )



@cliente.route('/como_encontrar_pedido/<int:id_pedido>')
@login_required
def como_encontrar_pedido(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)

    if pedido.ID_Usuario != current_user.id and current_user.Rol not in ['admin', 'transportista']:
        return "Acceso denegado ❌", 403
    
    # Fecha de envío = hoy
    fecha_envio = date.today()

    return render_template(
        'cliente/como_encontrar_pedido.html',
        pedido=pedido,
        fecha_envio=fecha_envio,
        transportista=None  # como no hay relación, puedes poner None o un texto genérico
    )




@cliente.route("/confirmar_entrega/<int:pedido_id>")
def confirmar_entrega(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    pedido.Estado = "entregado"
    db.session.commit()
    return "✅ Entrega confirmada. Gracias por tu compra."

# ---------- HISTORIAL_TRANSACCIONES ----------

@cliente.route('/historial')
@login_required
def historial():
    cliente_id = current_user.ID_Usuario
    
    pedidos = Pedido.query.filter_by(ID_Usuario=cliente_id).order_by(Pedido.FechaPedido.desc()).all()
    
  
    for pedido in pedidos:
        pedido.subtotal = sum(detalle.Cantidad * detalle.PrecioUnidad for detalle in pedido.detalles_pedido)
    
    return render_template('cliente/historial_transacciones.html', pedidos=pedidos)



@cliente.route('/pedido/<int:pedido_id>')
@login_required
def ver_pedido(pedido_id):
    pedido = Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Usuario=current_user.ID_Usuario).first_or_404()
    return render_template('cliente/ver_pedido.html', pedido=pedido)


@cliente.route('/pedido/<int:pedido_id>/eliminar', methods=['POST'])
@login_required
def eliminar_pedido(pedido_id):
    pedido = Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Usuario=current_user.ID_Usuario).first_or_404()
    
    db.session.delete(pedido)
    db.session.commit()
    flash('Pedido eliminado correctamente.', 'success')
    return redirect(url_for('cliente.historial'))

# ---------- GARANTIAS ----------

@cliente.route('/crear/<int:pedido_id>', methods=['GET', 'POST'])
@login_required
def crear_garantia(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if request.method == 'POST':
        motivo = request.form['motivo']
        archivos = request.files.getlist('archivos')  
       
        garantia = Garantia(ID_Pedido=pedido.ID_Pedido, ID_Usuario=current_user.ID_Usuario,
                            Motivo=motivo)
        db.session.add(garantia)
        db.session.commit()

        
        for f in archivos:
            if f.filename:
                ruta = f"/uploads/garantias/{f.filename}"
                f.save(f".{ruta}")  
                archivo = GarantiaArchivo(ID_Garantia=garantia.ID_Garantia,
                                          NombreArchivo=f.filename,
                                          RutaArchivo=ruta)
                db.session.add(archivo)
        db.session.commit()

        flash("Garantía creada correctamente.", "success")
        return redirect(url_for('mis_garantias'))

    return render_template('cliente/crear_garantia.html', pedido=pedido)


@cliente.route('/mis_garantias')
@login_required
def mis_garantias():
    garantias = Garantia.query.filter_by(ID_Usuario=current_user.ID_Usuario).all()
    return render_template('cliente/garantias.html', garantias=garantias)





