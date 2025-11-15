import os
from openai import OpenAI  
from dotenv import load_dotenv
from flask_login import current_user
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from basedatos.models import db, Usuario, Notificaciones, Direccion, Calendario,Pedido, Producto, Resena, Detalle_Pedido, Pagos,Mensaje,Garantia ,GarantiaArchivo ,Categorias ,FotoProductoDefectuoso ,ProductoDefectuoso ,GarantiaProducto
from basedatos.models import Mensaje
from basedatos.decoradores import role_required
from basedatos.notificaciones import crear_notificacion
from datetime import date,datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session, current_app
from sqlalchemy import text
from flask_mail import Message
from werkzeug.utils import secure_filename
from basedatos.decoradores import mail
from functools import wraps
from datetime import date
import re


UPLOAD_FOLDER = os.path.join('static', 'uploads', 'defectuosos')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

UPLOAD_FOLDER = 'static/uploads/garantias'

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


# ---------- CHAT CLIENTE (API) ----------
@cliente.route('/api/chat/send', methods=['POST'])
@login_required
def api_chat_send():
    data = request.get_json(silent=True) or {}
    texto = (data.get('mensaje') or '').strip()
    pedido_id = data.get('pedido_id')
    if not texto:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400

    # Guardar mensaje del cliente
    msg = Mensaje(cliente_id=current_user.ID_Usuario, contenido=texto, enviado_admin=False)
    db.session.add(msg)
    db.session.commit()

    # Generar respuesta básica de CasaBot según intentos simples
    lower = texto.lower()
    respuesta = None

    if 'ver mis pedidos' in lower or 'mis pedidos' in lower:
        respuesta = f"Puedes ver tus pedidos aquí: {url_for('cliente.historial')}"
    elif 'horarios' in lower or 'atencion' in lower:
        respuesta = "Nuestro horario de atención es L-V 8:00-18:00 y Sáb 9:00-13:00."
    elif 'estado de mi pedido' in lower or 'estado pedido' in lower:
        consulta = None
        if pedido_id:
            consulta = Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Usuario=current_user.ID_Usuario).first()
        if not consulta:
            consulta = Pedido.query.filter_by(ID_Usuario=current_user.ID_Usuario).order_by(Pedido.FechaPedido.desc()).first()
        if consulta:
            respuesta = f"El pedido #{consulta.ID_Pedido} está en estado: {consulta.Estado}."
        else:
            respuesta = "Aún no encuentro pedidos en tu cuenta."
    elif 'hablar con un asesor' in lower or 'asesor' in lower:
        respuesta = "He notificado a un asesor. Te responderá a la brevedad por este chat."
    elif 'solicitar garantia' in lower or 'garantia' in lower:
        respuesta = f"Para solicitar garantía, elige tu pedido aquí: {url_for('cliente.seleccionar_pedido_defectuoso')}"
    elif 'ver notificaciones' in lower or 'notificaciones' in lower:
        respuesta = f"Puedes ver tus notificaciones aquí: {url_for('cliente.ver_notificaciones_cliente')}"
    elif 'registrar producto defectuoso' in lower or 'producto defectuoso' in lower or 'defectuoso' in lower:
        respuesta = f"Registra tu producto defectuoso aquí: {url_for('cliente.seleccionar_pedido_defectuoso')}"
    else:
        respuesta = "Gracias por tu mensaje. Un asesor te responderá pronto. También puedes usar las sugerencias."

    bot = Mensaje(cliente_id=current_user.ID_Usuario, contenido=respuesta, enviado_admin=True)
    db.session.add(bot)
    db.session.commit()

    return jsonify({"ok": True})


@cliente.route('/api/chat/fetch', methods=['GET'])
@login_required
def api_chat_fetch():
    after = request.args.get('after')
    q = Mensaje.query.filter_by(cliente_id=current_user.ID_Usuario)
    if after:
        # formato ISO: 'YYYY-MM-DDTHH:MM:SS'
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(after)
            q = q.filter(Mensaje.fecha > dt)
        except Exception:
            pass
    msgs = q.order_by(Mensaje.fecha.asc()).all()
    return jsonify({
        "ok": True,
        "mensajes": [
            {
                "id": m.id,
                "contenido": m.contenido,
                "enviado_admin": bool(m.enviado_admin),
                "fecha": m.fecha.isoformat()
            } for m in msgs
        ]
    })


@cliente.route('/api/chat/pedidos', methods=['GET'])
@login_required
def api_chat_pedidos():
    pedidos = Pedido.query.filter_by(ID_Usuario=current_user.ID_Usuario).order_by(Pedido.FechaPedido.desc()).all()
    return jsonify({
        "ok": True,
        "pedidos": [
            {"id": p.ID_Pedido, "estado": p.Estado, "fecha": p.FechaPedido.isoformat() if p.FechaPedido else None}
            for p in pedidos
        ]
    })


@cliente.route("/notificaciones", methods=["GET", "POST"])
@login_required
def ver_notificaciones_cliente():
    if request.method == "POST":
        # --- Eliminación múltiple ---
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

    notificaciones = (
        Notificaciones.query
        .filter_by(ID_Usuario=current_user.ID_Usuario)
        .order_by(Notificaciones.Fecha.desc())
        .all()
    )

    # Construir info de cita para notificaciones de garantía aprobada
    cita_garantia_por_notif = {}
    try:
        for n in notificaciones:
            msg = (n.Mensaje or '')
            m = __import__('re').search(r"garant[ií]a\s*#(\d+)", msg, __import__('re').IGNORECASE)
            if not m:
                continue
            gid = int(m.group(1))
            g = Garantia.query.get(gid)
            if g and g.ID_Usuario == current_user.ID_Usuario and getattr(g, 'CitaAgendada', None):
                cita_dt = g.CitaAgendada
                cita_garantia_por_notif[n.ID_Notificacion] = {
                    'fecha': cita_dt.strftime('%d/%m/%Y'),
                    'hora': cita_dt.strftime('%H:%M')
                }
    except Exception:
        pass

    return render_template(
        "cliente/notificaciones_cliente.html",
        notificaciones=notificaciones,
        datetime=datetime,  # para usar datetime en el template
        cita_garantia_por_notif=cita_garantia_por_notif
    )

@cliente.route('/cliente/eliminar_notificacion/<int:notificacion_id>', methods=['POST'])
@login_required
def eliminar_notificacion(notificacion_id):
    notificacion = Notificaciones.query.get_or_404(notificacion_id)

    if notificacion.ID_Usuario != current_user.ID_Usuario:
        flash("No puedes eliminar esta notificación.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))
    try:
        db.session.delete(notificacion)
        db.session.commit()
        flash("Notificación eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar la notificación: {str(e)}", "danger")

    return redirect(url_for('cliente.ver_notificaciones_cliente'))

@cliente.route('/agendar_cita/<int:notificacion_id>', methods=['POST'])
@login_required
def agendar_cita_tecnico(notificacion_id):
    """Agendar cita del cliente con el técnico asociado a su producto defectuoso."""

    # --- Buscar notificación ---
    notificacion = Notificaciones.query.get_or_404(notificacion_id)

    # Validar que la notificación tenga un defecto asociado
    if not notificacion.defecto:
        flash("Esta notificación no tiene un producto para agendar cita.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    defecto = notificacion.defecto

    # Si ya hay cita, no permitir duplicar
    if defecto.CitaProgramada:
        flash("Esta solicitud ya tiene una cita programada.", "warning")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # --- Obtener datos del formulario (nombres únicos por notificación) ---
    fecha_str = request.form.get(f'fecha_{notificacion_id}') or request.form.get('fecha')
    hora_str = request.form.get(f'hora_{notificacion_id}') or request.form.get('hora')

    if not fecha_str or not hora_str:
        flash("⚠️ Debes seleccionar una fecha y hora para la cita.", "warning")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # Validar rango de hora permitido (08:00-19:00)
    try:
        hh, mm = map(int, hora_str.split(':', 1))
        if not (8 <= hh <= 19) or not (0 <= mm <= 59):
            flash("⚠️ Hora fuera de rango (permitido 08:00 a 19:00).", "warning")
            return redirect(url_for('cliente.ver_notificaciones_cliente'))
    except Exception:
        flash("❌ Formato de hora inválido.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    try:
        cita_datetime = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("❌ Formato de fecha u hora inválido.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # --- Guardar la cita programada en el defecto ---
    defecto.CitaProgramada = cita_datetime
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al guardar la cita: {str(e)}", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # --- Registrar en calendario usando la dirección del pedido, si existe ---
    try:
        pedido = defecto.pedido
        direccion = pedido.Destino if pedido and pedido.Destino else "Dirección no definida"
        evento = Calendario(
            Fecha=cita_datetime.date(),
            Hora=cita_datetime.time(),
            Ubicacion=direccion,
            Tipo="Técnico",
            ID_Usuario=current_user.ID_Usuario,
            ID_Pedido=defecto.ID_Pedido
        )
        db.session.add(evento)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # No bloquear por error en calendario; continuar

    # --- Crear notificación para el técnico ---
    try:
        noti_tecnico = Notificaciones(
            Titulo="📅 Nueva cita agendada",
            Mensaje=(
                f"El cliente <b>{current_user.Nombre}</b> ha agendado una cita "
                f"para el <b>{cita_datetime.strftime('%d/%m/%Y a las %H:%M')}</b> "
                f"relacionada con un producto defectuoso."
            ),
            Fecha=datetime.now(),
            Leida=False,
            ID_Usuario=defecto.ID_Empleado  # Técnico asignado
        )
        db.session.add(noti_tecnico)
        db.session.commit()

        flash("✅ Cita agendada correctamente con el técnico.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"⚠️ La cita se guardó, pero ocurrió un error al notificar al técnico: {str(e)}", "warning")

    return redirect(url_for('cliente.ver_notificaciones_cliente'))

    try:
        db.session.delete(notificacion)
        db.session.commit()
        flash("Notificación eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar la notificación: {str(e)}", "danger")

    return redirect(url_for('cliente.ver_notificaciones_cliente'))

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


@cliente.route('/detalle_pedido_ajax/<int:pedido_id>')
@login_required
def detalle_pedido_ajax(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    detalles = [{
        "Producto": det.producto.NombreProducto,
        "PrecioUnidad": float(det.PrecioUnidad),
        "Cantidad": det.Cantidad,
        "Total": float(det.PrecioUnidad * det.Cantidad)
    } for det in pedido.detalles_pedido]
    return jsonify(detalles)




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

@cliente.route('/carrito')
@login_required
def ver_carrito():
    # Obtiene las direcciones del usuario logueado
    direcciones = current_user.direcciones  # relación desde Usuario
    return render_template('cliente/carrito.html', direcciones=direcciones)


# ---------- Checkout ----------

def enviar_correo_confirmacion(usuario, pedido, total_pago, metodo, direccion_envio):
    """
    Envía un correo de confirmación con diseño HTML.
    """
    html_body = render_template(
        'email/confirmacion_pedido.html',
        nombre=usuario.Nombre,
        id_pedido=pedido.ID_Pedido,
        metodo=metodo.capitalize(),
        total=f"{total_pago:,.2f}",
        direccion=direccion_envio
    )

    msg = Message(
        subject=f"🧾 Confirmación de tu pedido #{pedido.ID_Pedido}",
        recipients=[usuario.Correo],
        html=html_body
    )

    mail.send(msg)


@cliente.route('/checkout', methods=['POST'])
@login_required
def checkout():
    data = request.get_json()
    carrito = data.get('carrito', [])
    metodo = data.get('metodo')
    direccion_id = data.get('direccion_id')

    if not carrito:
        return jsonify({"success": False, "mensaje": "Carrito vacío"})

    try:
        # 1️⃣ Traer la dirección
        direccion = Direccion.query.get(direccion_id)
        if not direccion:
            return jsonify({"success": False, "mensaje": "Dirección no válida"})

        # 2️⃣ Crear pedido
        pedido = Pedido(
            NombreComprador=f"{current_user.Nombre} {current_user.Apellido or ''}",
            Estado='pendiente',
            FechaPedido=date.today(),
            Destino=f"{direccion.Direccion} ({direccion.Ciudad}, {direccion.Departamento})",
            ID_Usuario=current_user.ID_Usuario
        )
        db.session.add(pedido)
        db.session.flush()  # Para obtener ID_Pedido

        total_compra = 0
        detalles_resumen = []

        # 3️⃣ Crear detalles del pedido y actualizar stock
        for item in carrito:
            producto = Producto.query.get(item['ID_Producto'])
            if not producto:
                continue
            cantidad = int(item.get('cantidad', 1))
            precio = float(item.get('precio', 0))
            subtotal = cantidad * precio
            total_compra += subtotal

            detalle = Detalle_Pedido(
                ID_Pedido=pedido.ID_Pedido,
                ID_Producto=producto.ID_Producto,
                Cantidad=cantidad,
                PrecioUnidad=precio
            )
            db.session.add(detalle)

            # Actualizar stock
            producto.Stock = max(producto.Stock - cantidad, 0)

            detalles_resumen.append({
                "NombreProducto": producto.NombreProducto,
                "cantidad": cantidad,
                "precio": precio
            })

        # 4️⃣ Guardar método de pago
        pago = Pagos(
            MetodoPago=metodo,
            Monto=total_compra,
            ID_Pedido=pedido.ID_Pedido
        )
        db.session.add(pago)

        db.session.commit()

        # 5️⃣ Enviar correo de confirmación (intenta pero no bloquea la respuesta)
        try:
            enviar_correo_confirmacion(
                usuario=current_user,
                pedido=pedido,
                total_pago=total_compra,
                metodo=metodo,
                direccion_envio=f"{direccion.Direccion} ({direccion.Ciudad}, {direccion.Departamento})"
            )
        except Exception as mail_err:
            # Solo loguea el error, no bloquea la respuesta
            print("Error al enviar correo:", mail_err)

        # ✅ Devolver JSON con resumen
        return jsonify({
            "success": True,
            "mensaje": "Pago procesado correctamente",
            "total": total_compra,
            "detalles": detalles_resumen
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)})

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
        subtotal = 0.0
        for detalle in pedido.detalles_pedido:
            cant = float(detalle.Cantidad or 0)
            precio = detalle.PrecioUnidad if detalle.PrecioUnidad not in (None, 0) else (detalle.producto.PrecioUnidad or 0)
            subtotal += cant * float(precio or 0)
        pedido.subtotal = subtotal
    
    return render_template('cliente/historial_transacciones.html', pedidos=pedidos)



@cliente.route('/pedido/<int:pedido_id>')
@login_required
def ver_pedido(pedido_id):
    pedido = Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Usuario=current_user.ID_Usuario).first_or_404()
    # Calcular totales de forma segura
    subtotal = 0.0
    for det in pedido.detalles_pedido:
        try:
            cantidad = float(det.Cantidad or 0)
            precio_raw = det.PrecioUnidad if det.PrecioUnidad not in (None, 0) else (getattr(det.producto, 'PrecioUnidad', 0) or 0)
            precio = float(precio_raw or 0)
        except Exception:
            cantidad = 0.0
            precio = 0.0
        subtotal += (cantidad * precio)
    # Fallback: si no hay detalle con precio/cantidad, usar suma de pagos
    if (subtotal == 0.0 or subtotal is None) and pedido.pagos:
        try:
            subtotal = float(sum(p.Monto or 0 for p in pedido.pagos))
        except Exception:
            subtotal = 0.0
    descuento = float(pedido.Descuento or 0)
    total_final = max(subtotal - descuento, 0.0)

    return render_template(
        'cliente/ver_pedido.html',
        pedido=pedido,
        subtotal=subtotal,
        descuento=descuento,
        total_final=total_final
    )


@cliente.route('/pedido/<int:pedido_id>/eliminar', methods=['POST'])
@login_required
def eliminar_pedido(pedido_id):
    pedido = Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Usuario=current_user.ID_Usuario).first_or_404()
    
    db.session.delete(pedido)
    db.session.commit()
    flash('Pedido eliminado correctamente.', 'success')
    return redirect(url_for('cliente.historial'))

# ---------- GARANTIAS ----------
@cliente.route('/garantia/<int:pedido_id>', methods=['GET', 'POST'])
@login_required
def solicitar_garantia(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    # Solo el usuario dueño del pedido
    if pedido.ID_Usuario != current_user.ID_Usuario:
        flash('No tienes permisos para solicitar garantía en este pedido.', 'danger')
        return redirect(url_for('cliente.index'))

    productos = Detalle_Pedido.query.filter_by(ID_Pedido=pedido_id).all()

    if request.method == 'POST':
        motivo = request.form.get('motivo')
        productos_seleccionados = request.form.getlist('productos')
        archivos = request.files.getlist('archivos')

        if not productos_seleccionados:
            flash('Debes seleccionar al menos un producto.', 'danger')
            return redirect(request.url)

        nueva_garantia = Garantia(
            ID_Pedido=pedido.ID_Pedido,
            ID_Usuario=current_user.ID_Usuario,
            Motivo=motivo
        )
        db.session.add(nueva_garantia)
        db.session.flush()

        # Guardar archivos
        for archivo in archivos:
            if archivo.filename != '':
                filename = secure_filename(archivo.filename)
                ruta = os.path.join(UPLOAD_FOLDER, filename)
                archivo.save(ruta)
                archivo_garantia = GarantiaArchivo(
                    ID_Garantia=nueva_garantia.ID_Garantia,
                    NombreArchivo=filename,
                    RutaArchivo=ruta
                )
                db.session.add(archivo_garantia)

        # Guardar productos seleccionados
        for id_producto in productos_seleccionados:
            detalle = Detalle_Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Producto=int(id_producto)).first()
            if detalle:
                db.session.add(GarantiaProducto(
                    ID_Garantia=nueva_garantia.ID_Garantia,
                    ID_Producto=int(id_producto)
                ))

        db.session.commit()
        flash('Solicitud de garantía enviada correctamente.', 'success')
        return redirect(url_for('cliente.ver_pedido', pedido_id=pedido.ID_Pedido))
    # Obtener la notificación
    notificacion = Notificaciones.query.get_or_404(notificacion_id)
    
    # Validar que la notificación tenga un defecto asociado
    if not notificacion.defecto:
        flash("Esta notificación no tiene un producto para agendar cita.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))
    
    garantia = notificacion.defecto  # ProductoDefectuoso

    # Solo permitir si el estado es resuelto_tecnico y no hay cita previa
    if garantia.Estado != 'resuelto_tecnico' or garantia.CitaProgramada:
        flash("No se puede agendar cita para este estado.", "warning")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # Obtener fecha y hora del formulario
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')

    if not fecha or not hora:
        flash("Debes ingresar fecha y hora válidas.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    try:
        # Combinar fecha y hora en datetime
        cita_datetime = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Formato de fecha u hora inválido.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # Asignar la cita al producto defectuoso
    garantia.CitaProgramada = cita_datetime

    # Obtener dirección del pedido, si existe
    pedido = garantia.pedido
    direccion = pedido.Destino if pedido and pedido.Destino else "Dirección no definida"

    # Registrar en calendario usando la dirección del pedido
    nuevo_evento = Calendario(
        Fecha=cita_datetime.date(),
        Hora=cita_datetime.time(),
        Ubicacion=direccion,
        Tipo="Garantía",
        ID_Usuario=current_user.ID_Usuario,
        ID_Pedido=garantia.ID_Pedido
    )
    db.session.add(nuevo_evento)
    db.session.commit()

    flash(f"Cita agendada correctamente para {cita_datetime.strftime('%d/%m/%Y %H:%M')} en {direccion}", "success")
    return redirect(url_for('cliente.ver_notificaciones_cliente'))


@cliente.route('/guardar_preferencias', methods=['POST'])
@login_required
def guardar_preferencias():
    categorias = request.form.getlist('categoria')  # lista de IDs seleccionadas
    materiales = request.form.getlist('material')
    colores = request.form.getlist('color')

    # Actualizar categorías favoritas
    current_user.categorias_favoritas = Categorias.query.filter(Categorias.ID_Categoria.in_(categorias)).all()

    # Guardar materiales y colores como JSON
    import json
    current_user.materiales_preferidos = json.dumps(materiales)
    current_user.colores_preferidos = json.dumps(colores)

    db.session.commit()
    return redirect(url_for('cliente.catalogo'))

def historial_actividades(usuario_id):
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return None

    actividades = []

    # ------------------ Pedidos ------------------
    for pedido in usuario.pedidos:
        actividades.append({
            "tipo": "pedido",
            "fecha": pedido.FechaPedido.isoformat(),
            "detalle": {
                "ID_Pedido": pedido.ID_Pedido,
                "Estado": pedido.Estado,
                "Destino": pedido.Destino or "Sin dirección",
                "detalles": [
                    {
                        "Producto": d.producto.NombreProducto,
                        "Cantidad": d.Cantidad or 0,
                        "PrecioUnidad": d.PrecioUnidad or 0,
                        "Subtotal": (d.Cantidad or 0) * (d.PrecioUnidad or 0)
                    } for d in pedido.detalles_pedido
                ]
            }
        })

        # Pagos de cada pedido
        for pago in pedido.pagos:
            actividades.append({
                "tipo": "pago",
                "fecha": pago.FechaPago.isoformat(),
                "detalle": {
                    "ID_Pago": pago.ID_Pagos,
                    "Monto": pago.Monto,
                    "MetodoPago": pago.MetodoPago,
                    "ID_Pedido": pedido.ID_Pedido
                }
            })

        # Comentarios del pedido
        for c in pedido.comentarios:
            actividades.append({
                "tipo": "comentario",
                "fecha": c.fecha.isoformat(),
                "detalle": {
                    "ID_Pedido": pedido.ID_Pedido,
                    "Texto": c.texto
                }
            })

    # ------------------ Reseñas ------------------
    for r in usuario.resenas:
        actividades.append({
            "tipo": "resena",
            "fecha": r.Fecha.isoformat(),
            "detalle": {
                "Producto": r.producto.NombreProducto,
                "Calificacion": r.Calificacion,
                "Comentario": r.Comentario
            }
        })

    # ------------------ Mensajes ------------------
    for m in usuario.mensajes:
        actividades.append({
            "tipo": "mensaje",
            "fecha": m.fecha.isoformat(),
            "detalle": {
                "Contenido": m.contenido,
                "EnviadoAdmin": m.enviado_admin
            }
        })

    # ------------------ Garantías ------------------
    for g in Garantia.query.filter_by(ID_Usuario=usuario_id).all():
        actividades.append({
            "tipo": "garantia",
            "fecha": g.FechaSolicitud.isoformat(),
            "detalle": {
                "ID_Garantia": g.ID_Garantia,
                "Estado": g.Estado,
                "Motivo": g.Motivo
            }
        })

    # ------------------ Notificaciones ------------------
    for n in usuario.notificaciones:
        actividades.append({
            "tipo": "notificacion",
            "fecha": n.Fecha.isoformat(),
            "detalle": {
                "Titulo": n.Titulo,
                "Mensaje": n.Mensaje,
                "Leida": n.Leida
            }
        })

    # ------------------ Novedades ------------------
    for nov in usuario.novedades:
        actividades.append({
            "tipo": "novedad",
            "fecha": nov.FechaReporte.isoformat(),
            "detalle": {
                "ID_Producto": nov.ID_Producto,
                "Tipo": nov.Tipo,
                "EstadoNovedad": nov.EstadoNovedad
            }
        })

    # Ordenar todas las actividades por fecha descendente
    actividades.sort(key=lambda x: x["fecha"], reverse=True)

    return {
        "usuario": {
            "Nombre": usuario.Nombre,
            "Apellido": usuario.Apellido,
            "Correo": usuario.Correo
        },
        "actividades": actividades
    }


@cliente.route('/historial_actividades')
@login_required
def historial_actividades_web():
    historial = historial_actividades(current_user.ID_Usuario)

    # Filtros por fecha (YYYY-MM-DD)
    fecha_inicio = (request.args.get('fecha_inicio') or '').strip()
    fecha_fin = (request.args.get('fecha_fin') or '').strip()

    if fecha_inicio or fecha_fin:
        filtradas = []
        for act in historial.get('actividades', []):
            fecha_str = (act.get('fecha') or '').split('T')[0]
            ok = True
            if fecha_inicio and fecha_str < fecha_inicio:
                ok = False
            if fecha_fin and fecha_str > fecha_fin:
                ok = False
            if ok:
                filtradas.append(act)
        historial['actividades'] = filtradas

    return render_template(
        "cliente/historial.html",
        historial=historial,
        filtros={
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
        }
    )



# ------------------ Seleccionar pedido y producto defectuoso ------------------
@cliente.route('/seleccionar_defectuoso')
@login_required
def seleccionar_pedido_defectuoso():
    # Traemos los pedidos del usuario actual
    pedidos = Pedido.query.filter_by(ID_Usuario=current_user.ID_Usuario).all()
    return render_template('cliente/seleccionar_pedido_defectuoso.html', pedidos=pedidos)

# ------------------ Registrar producto defectuoso ------------------

@cliente.route('/registrar_defectuoso/<int:pedido_id>/<int:id_producto>', methods=['GET', 'POST'])
@login_required
def registrar_defectuoso(pedido_id, id_producto):
    # Obtenemos el detalle del pedido
    detalle = Detalle_Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Producto=id_producto).first_or_404()

    if request.method == "POST":
        motivo = request.form.get("motivo")
        archivos = request.files.getlist("archivos")

        if not motivo:
            flash("Debe ingresar un motivo", "danger")
            return redirect(request.url)

        if not archivos or all(f.filename == "" for f in archivos):
            flash("Debe subir al menos una foto", "danger")
            return redirect(request.url)

        # Crear registro de ProductoDefectuoso
        producto_def = ProductoDefectuoso(
            ID_Usuario=current_user.ID_Usuario,
            ID_Producto=detalle.ID_Producto,
            ID_Pedido=pedido_id,
            Motivo=motivo
        )
        db.session.add(producto_def)
        db.session.commit()  # Necesario para obtener el ID del producto defectuoso

        # Carpeta donde se guardarán las fotos
        upload_folder = os.path.join('static', 'uploads', 'defectuosos')
        os.makedirs(upload_folder, exist_ok=True)

        # Guardar fotos
        for archivo in archivos:
            if archivo.filename != "":
                nombre_seguro = secure_filename(archivo.filename)
                ruta = os.path.join(upload_folder, nombre_seguro)
                archivo.save(ruta)

                foto = FotoProductoDefectuoso(
                    ID_ProductoDefectuoso=producto_def.ID,
                    RutaArchivo=ruta  # Ruta relativa para usar con url_for
                )
                db.session.add(foto)

        db.session.commit()
        flash("Producto defectuoso registrado correctamente", "success")
        return redirect(url_for('cliente.seleccionar_pedido_defectuoso'))

    return render_template('cliente/registrar_defectuoso.html', detalle=detalle)


@cliente.route('/agendar_cita_garantia_aprobada/<int:notificacion_id>', methods=['POST'])
@login_required
def agendar_cita_garantia_aprobada(notificacion_id):
    """Agendar cita asociada a una Garantía aprobada, extrayendo el ID de garantía del mensaje."""

    # --- Buscar notificación ---
    notificacion = Notificaciones.query.get_or_404(notificacion_id)

    # Leer fecha/hora del modal: usan nombres únicos por notificación
    fecha_str = request.form.get(f'fecha_{notificacion_id}') or request.form.get('fecha')
    hora_str = request.form.get(f'hora_{notificacion_id}') or request.form.get('hora')
    if not fecha_str or not hora_str:
        flash("⚠️ Debes seleccionar una fecha y hora para la cita.", "warning")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # Validar rango de hora permitido (08:00-19:00)
    try:
        hh, mm = map(int, hora_str.split(':', 1))
        if not (8 <= hh <= 19) or not (0 <= mm <= 59):
            flash("⚠️ Hora fuera de rango (permitido 08:00 a 19:00).", "warning")
            return redirect(url_for('cliente.ver_notificaciones_cliente'))
    except Exception:
        flash("❌ Formato de hora inválido.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    try:
        cita_datetime = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("❌ Formato de fecha u hora inválido.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # Extraer ID de garantía del mensaje tipo: "Tu garantía #10 ha sido aprobada"
    mensaje = (notificacion.Mensaje or '')
    m = re.search(r"garant[ií]a\s*#(\d+)", mensaje, re.IGNORECASE)
    if not m:
        flash("❌ No se pudo identificar la garantía en la notificación.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    garantia_id = int(m.group(1))
    garantia = Garantia.query.get(garantia_id)
    if not garantia or garantia.ID_Usuario != current_user.ID_Usuario:
        flash("❌ Garantía no válida para agendar.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # Guardar cita directamente en la garantía
    try:
        garantia.CitaAgendada = cita_datetime
        garantia.Estado = 'cita_agendada'
        db.session.commit()
        flash("✅ Cita de garantía agendada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al guardar la cita en la garantía: {str(e)}", "danger")
    return redirect(url_for('cliente.ver_notificaciones_cliente'))