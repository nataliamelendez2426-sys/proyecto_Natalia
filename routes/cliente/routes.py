import os
from openai import OpenAI  
from dotenv import load_dotenv
from flask_login import current_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session , current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from basedatos.models import db, Usuario, Notificaciones, Direccion, Calendario,Pedido, Producto, Resena, Detalle_Pedido, Pagos,Mensaje,Garantia ,GarantiaArchivo ,Categorias ,FotoProductoDefectuoso ,ProductoDefectuoso
from basedatos.decoradores import role_required
from basedatos.notificaciones import crear_notificacion
from datetime import date,datetime
from flask import render_template
from sqlalchemy import text
from flask_mail import Message
from flask import url_for
from werkzeug.utils import secure_filename
from basedatos.decoradores import mail
from functools import wraps
from datetime import date

UPLOAD_FOLDER_DEFECTUOSO = 'static/uploads/productos_defectuosos'
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

    notificaciones = (
        Notificaciones.query
        .filter_by(ID_Usuario=current_user.ID_Usuario)
        .order_by(Notificaciones.Fecha.desc())
        .all()
    )

    # 🔹 Pasamos datetime al template
    return render_template(
        "cliente/notificaciones_cliente.html",
        notificaciones=notificaciones,
        datetime=datetime  # 👈 esto es lo que hace falta
    )
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
    try:
        data = request.get_json()
        carrito = data.get('carrito', [])
        metodo = data.get('metodo')
        numero_celular = data.get('numero_celular')
        numero_tarjeta = data.get('numero_tarjeta')
        direccion_id = data.get('direccion_id')

        if not carrito:
            return jsonify({"success": False, "mensaje": "El carrito está vacío."}), 400

        # Buscar dirección seleccionada
        direccion_envio = "Dirección no especificada"
        if direccion_id:
            direccion = Direccion.query.filter_by(
                ID_Direccion=direccion_id,
                ID_Usuario=current_user.ID_Usuario
            ).first()
            if direccion:
                direccion_envio = f"{direccion.Direccion}, {direccion.Barrio or ''}, {direccion.Ciudad or ''}"
            else:
                direccion_envio = "Dirección no encontrada"

        # Crear pedido
        pedido = Pedido(
            NombreComprador=f"{current_user.Nombre} {current_user.Apellido or ''}".strip(),
            Destino=direccion_envio,
            Estado="pendiente",
            FechaPedido=date.today(),
            ID_Usuario=current_user.ID_Usuario
        )
        db.session.add(pedido)
        db.session.commit()

        # Calcular total y registrar pago
        total_pago = sum(i.get('precio', 0) * i.get('cantidad', 1) for i in carrito)
        pago = Pagos(
            MetodoPago=metodo,
            Monto=total_pago,
            ID_Pedido=pedido.ID_Pedido
        )
        db.session.add(pago)
        db.session.commit()

        # ✅ Enviar correo de confirmación (usando la función externa)
        enviar_correo_confirmacion(
            usuario=current_user,
            pedido=pedido,
            total_pago=total_pago,
            metodo=metodo,
            direccion_envio=direccion_envio
        )

        # Notificación opcional para Nequi/Daviplata
        if metodo in ['nequi', 'daviplata'] and numero_celular:
            print(f"📱 Notificación enviada al número: {numero_celular}")

        return jsonify({"success": True, "mensaje": "Pago procesado correctamente."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"success": False, "mensaje": str(e)}), 500


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
@cliente.route('/garantia/<int:pedido_id>', methods=['GET', 'POST'])
@login_required
def solicitar_garantia(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if request.method == 'POST':
        motivo = request.form.get('motivo')
        archivos = request.files.getlist('archivos')

        nueva_garantia = Garantia(
            ID_Pedido=pedido.ID_Pedido,
            ID_Usuario=current_user.ID_Usuario,
            Motivo=motivo
        )
        db.session.add(nueva_garantia)
        db.session.commit()  

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

        db.session.commit()
        flash('Solicitud de garantía enviada correctamente.', 'success')
        return redirect(url_for('cliente.mis_pedidos'))

    return render_template('cliente/solicitar_garantia.html', pedido=pedido)


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
    return render_template("cliente/historial.html", historial=historial)



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
    # Obtener el detalle del pedido
    detalle = Detalle_Pedido.query.filter_by(ID_Pedido=pedido_id, ID_Producto=id_producto).first_or_404()

    if request.method == 'POST':
        motivo = request.form.get('motivo')
        archivos = request.files.getlist('archivos')

        if not motivo:
            flash('Debes escribir un motivo', 'danger')
            return redirect(request.url)
        if not archivos or archivos[0].filename == '':
            flash('Debes subir al menos una foto', 'danger')
            return redirect(request.url)

        # Crear registro del producto defectuoso
        registro = ProductoDefectuoso(
            ID_Pedido=pedido_id,
            ID_Usuario=current_user.ID_Usuario,
            ID_Producto=id_producto,
            Motivo=motivo,
            Estado='pendiente'
        )
        db.session.add(registro)
        db.session.commit()  # Guardamos primero para obtener el ID del registro

        # Guardar archivos
        for archivo in archivos:
            filename = secure_filename(archivo.filename)
            # Crear carpeta si no existe
            carpeta = os.path.join(UPLOAD_FOLDER)
            os.makedirs(carpeta, exist_ok=True)
            ruta = os.path.join(carpeta, filename)
            archivo.save(ruta)

            # Guardar en la tabla de archivos
            garantia_archivo = GarantiaArchivo(
                ID_Garantia=registro.ID,
                NombreArchivo=filename,
                RutaArchivo=ruta
            )
            db.session.add(garantia_archivo)

        db.session.commit()
        flash('Producto registrado como defectuoso exitosamente', 'success')
        return redirect(url_for('cliente.seleccionar_pedido_defectuoso'))

    return render_template('cliente/registrar_defectuoso.html', detalle=detalle)


@cliente.route('/cliente/agendar_cita/<int:notificacion_id>', methods=['POST'])
@login_required
def agendar_cita_tecnico(notificacion_id):
    """Agendar cita del cliente con el técnico asociado a su producto defectuoso."""

    # --- Buscar notificación ---
    notificacion = Notificaciones.query.get_or_404(notificacion_id)

    # --- Obtener datos del formulario ---
    fecha_str = request.form.get('fecha')
    hora_str = request.form.get('hora')

    if not fecha_str or not hora_str:
        flash("⚠️ Debes seleccionar una fecha y hora para la cita.", "warning")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    try:
        cita_datetime = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("❌ Formato de fecha u hora inválido.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # --- Buscar último producto defectuoso del usuario ---
    defecto = ProductoDefectuoso.query.filter_by(
        ID_Usuario=current_user.ID_Usuario
    ).order_by(ProductoDefectuoso.FechaRegistro.desc()).first()

    if not defecto:
        flash("❌ No se encontró un producto defectuoso relacionado para agendar la cita.", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

    # --- Guardar la cita programada ---
    defecto.CitaProgramada = cita_datetime
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al guardar la cita: {str(e)}", "danger")
        return redirect(url_for('cliente.ver_notificaciones_cliente'))

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