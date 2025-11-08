from flask_login import login_required
from sqlalchemy import or_
from basedatos.models import db, Calendario, Pedido, Usuario
from basedatos.decoradores import role_required
from datetime import datetime, time
import os
import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from datetime import datetime
from flask import current_app
from flask_login import current_user
from basedatos.models import db, Usuario,Pedido, RegistroFotografico,Calendario, Notificaciones,Direccion
from basedatos.decoradores import role_required 
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from basedatos.notificaciones import crear_notificacion
from basedatos.decoradores import mail
from flask_mail import Message


from . import transportista

# ---------- DASHBOARD ----------
@transportista.route("/")
@login_required
@role_required("transportista")
def dashboard():
    return render_template("transportista/transportista_dashboard.html")

# ---------- CALENDARIO ----------

@transportista.route('/api/calendario')
@login_required
@role_required("transportista")
def api_calendario():
    eventos = []

    try:
        # --- Eventos de Calendario ---
        calendarios = db.session.query(Calendario, Usuario)\
            .join(Usuario, Calendario.ID_Usuario == Usuario.ID_Usuario, isouter=True).all()

        for c, u in calendarios:
            nombre_usuario = f"{u.Nombre} {u.Apellido or ''}".strip() if u else "Desconocido"

            try:
                start = datetime.combine(c.Fecha, c.Hora).isoformat()
            except Exception:
                start = f"{c.Fecha}T{c.Hora}"  # fallback

            eventos.append({
                "id": f"cal-{c.ID_Calendario}",
                "title": f"{c.Tipo} - Pedido #{c.ID_Pedido}",
                "start": start,
                "location": c.Ubicacion or "Sin ubicación",
                "tipo": c.Tipo or "Evento",
                "usuario": nombre_usuario
            })

        # --- Pedidos con FechaEntrega o HoraLlegada ---
        pedidos = Pedido.query.filter(
            or_(
                Pedido.FechaEntrega.isnot(None),
                Pedido.HoraLlegada.isnot(None)
            )
        ).all()

        for p in pedidos:
            usuario = Usuario.query.get(p.ID_Usuario)
            nombre_usuario = f"{usuario.Nombre} {usuario.Apellido or ''}".strip() if usuario else "Desconocido"

          
            fecha_evento = p.FechaEntrega or (p.HoraLlegada.date() if p.HoraLlegada else None)
            hora_evento = p.HoraLlegada.time() if p.HoraLlegada else time(12, 0)

            if fecha_evento:
                start = datetime.combine(fecha_evento, hora_evento).isoformat()
            else:
                continue  

            tipo_evento = "Instalación" if getattr(p, "Instalacion", 0) == 1 else "Entrega"

            eventos.append({
                "id": f"pedido-{p.ID_Pedido}",
                "title": f"{tipo_evento} - Pedido #{p.ID_Pedido}",
                "start": start,
                "location": getattr(p, "Destino", "Sin dirección"),
                "tipo": tipo_evento,
                "usuario": nombre_usuario
            })

        return jsonify(eventos)

    except Exception as e:
        print("Error en /api/calendario:", e)
        return jsonify({"error": str(e)}), 500


@transportista.route('/calendario')
@login_required
@role_required("transportista")
def calendario():
    return render_template("transportista/calendario.html")

# ---------- REGISTRO_FOTOGRAFICO ----------

@transportista.route('/registro_fotografico', methods=['POST'])
@login_required
def registrar_fotografia_transportista():
    if current_user.Rol != 'transportista':
        return jsonify({'status': 'danger', 'message': 'No autorizado.'})

    try:
        pedido_id = request.form.get('pedido_id')
        tipo = request.form.get('tipo', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        imagen = request.files.get('imagen')

        if not pedido_id or not imagen:
            return jsonify({'status': 'warning', 'message': 'Pedido e imagen son obligatorios.'})

        # Guardar imagen en carpeta estática
        carpeta = os.path.join('static', 'uploads', 'registros')
        os.makedirs(carpeta, exist_ok=True)
        nombre_archivo = secure_filename(imagen.filename)
        ruta_guardado = os.path.join(carpeta, nombre_archivo)
        imagen.save(ruta_guardado)

        
        registro = RegistroFotografico(
            pedido_id=int(pedido_id),
            usuario_id=current_user.ID_Usuario,  
            tipo=tipo,
            descripcion=descripcion,
            imagen_url=ruta_guardado
        )
        db.session.add(registro)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Foto registrada correctamente.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'danger', 'message': f'Error: {str(e)}'})
    
@transportista.route('/guardar_registro', methods=['POST'])
def guardar_registro():
    try:
        pedido_id = request.form.get('pedido_id')
        desc_antes = request.form.get('desc_antes')
        desc_despues = request.form.get('desc_despues')
        fotos_antes = request.files.getlist('fotos_antes')
        fotos_despues = request.files.getlist('fotos_despues')

        upload_folder = os.path.join(current_app.root_path, 'static/uploads')
        os.makedirs(upload_folder, exist_ok=True)

        for f in fotos_antes:
            filename = secure_filename(f.filename)
            f.save(os.path.join(upload_folder, filename))
            registro = RegistroFotografico(
                pedido_id=pedido_id,
                tipo='antes',
                descripcion=desc_antes,
                imagen_url=f'uploads/{filename}'
            )
            db.session.add(registro)

        for f in fotos_despues:
            filename = secure_filename(f.filename)
            f.save(os.path.join(upload_folder, filename))
            registro = RegistroFotografico(
                pedido_id=pedido_id,
                tipo='despues',
                descripcion=desc_despues,
                imagen_url=f'uploads/{filename}'
            )
            db.session.add(registro)

        db.session.commit()
        return jsonify({'status':'success'})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)})


@transportista.route('/registro_fotografico/<int:pedido_id>')
def get_registro_fotografico(pedido_id):
    registros = RegistroFotografico.query.filter_by(pedido_id=pedido_id).all()
    data = [{
        'tipo': r.tipo,
        'descripcion': r.descripcion,
        'imagen_url': r.imagen_url
    } for r in registros]
    return jsonify(data)

# ---------- PEDIDOS ----------

@transportista.route('/pedidos')
@login_required
@role_required('transportista')  
def ver_pedidos_transportista():
   
    pedidos = Pedido.query.filter_by(ID_Empleado=current_user.ID_Usuario).all()
    return render_template('transportista/pedidos.html', pedidos=pedidos)

@transportista.route("/seguimiento/<int:pedido_id>")
@login_required
@role_required('transportista')
def seguimiento_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template("transportista/seguimiento.html", pedido=pedido)


@transportista.route("/actualizar_estado/<int:id_pedido>", methods=["POST"])
@login_required
@role_required('transportista')
def actualizar_estado(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)
    nuevo_estado = request.form.get("estado")
    firma = request.form.get("firma")

    orden_estados = ["pendiente", "en proceso", "en reparto", "entregado"]
    actual_idx = orden_estados.index(pedido.Estado)
    nuevo_idx = orden_estados.index(nuevo_estado)

    if nuevo_idx < actual_idx:
        flash("⚠️ No puedes regresar a un estado anterior.", "warning")
        return redirect(url_for("transportista.seguimiento_pedido", pedido_id=id_pedido))

    pedido.Estado = nuevo_estado
    pedido.UltimaActualizacion = datetime.now()

    # ✅ Si el pedido se marca como entregado
    if nuevo_estado == "entregado":
        if hasattr(pedido, "TipoPago") and pedido.TipoPago.lower() == "contra entrega":
            if firma:
                pedido.FirmaCliente = firma
        else:
            # Enviar correo de confirmación
            return redirect(url_for("transportista.enviar_confirmacion", id_pedido=id_pedido))

    db.session.commit()
    flash("✅ Estado actualizado correctamente.", "success")
    return redirect(url_for("transportista.seguimiento_pedido", pedido_id=id_pedido))


# ---------- Enviar confirmación por correo ----------

@transportista.route("/enviar_confirmacion/<int:id_pedido>", methods=["GET", "POST"])
@login_required
@role_required('transportista')
def enviar_confirmacion(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)
    cliente = pedido.usuario

    # Enlaces para los botones
    link_rastrear = url_for(
        "cliente.rastrear_pedido",
        id_pedido=pedido.ID_Pedido,
        _scheme='http',
        _external=True
    )
    link_ayuda = url_for(
        "cliente.como_encontrar_pedido",
        id_pedido=pedido.ID_Pedido,
        _scheme='http',
        _external=True
    )

    # Construcción del correo
    msg = Message(
        subject=f"Actualización de tu pedido #{pedido.ID_Pedido}",
        sender="casaenelarbol236@gmail.com",
        recipients=[cliente.Correo]
    )

    msg.html = f"""
    <div style="font-family: Arial, sans-serif; color:#333; padding:20px;">
        <h2 style="color:#157145;">🌿 ¡Hola {cliente.Nombre}!</h2>
        <p>Tu pedido <b>#{pedido.ID_Pedido}</b> ha sido actualizado por el transportista.</p>
        <p>Puedes seguir su recorrido o recibir ayuda con su ubicación:</p>

        <div style="text-align:center; margin:30px 0;">
            <a href="{link_rastrear}" 
               style="background-color:#198754; color:white; padding:12px 25px; 
                      text-decoration:none; border-radius:6px; font-weight:bold; margin-right:15px;">
               🚚 Rastrear mi pedido
            </a>
            <a href="{link_ayuda}" 
               style="background-color:#0d6efd; color:white; padding:12px 25px; 
                      text-decoration:none; border-radius:6px; font-weight:bold;">
               ❓ Cómo encontrar mi paquete
            </a>
        </div>

        <p style="font-size:0.95rem; color:#555;">
            Si no hiciste este pedido, puedes ignorar este mensaje.
        </p>

        <hr style="margin-top:25px;">
        <p style="font-size:0.85rem; color:#999;">Gracias por confiar en <b>Casa en el Árbol</b> 💚</p>
    </div>
    """

    mail.send(msg)
    flash("✅ Correo de rastreo enviado correctamente al cliente.", "success")

    return redirect(url_for("transportista.ver_pedidos_transportista"))





# ---------- Confirmar entrega desde el correo ----------

@transportista.route('/confirmar_entrega/<int:id_pedido>')
def confirmar_entrega(id_pedido):
    respuesta = request.args.get('respuesta')
    pedido = Pedido.query.get_or_404(id_pedido)

    if respuesta == 'si':
        pedido.Estado = 'entregado'
        db.session.commit()
        return "✅ Gracias por confirmar. Tu pedido ha sido marcado como ENTREGADO."

    return "⚠️ Si aún no has recibido tu pedido, simplemente ignora este mensaje."


# ---------- ACTUALIZACION_DATOS ----------
@transportista.route("/actualizacion_datos", methods=["GET", "POST"])
@login_required
@role_required("transportista")
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
        "transportista/actualizacion_datos.html",
        usuario=usuario,
        direcciones=direcciones,
        notificaciones=notificaciones
    )


# ---------- AGREGAR DIRECCION ----------
@transportista.route("/direccion/agregar", methods=["POST"])
@login_required
def agregar_direccion():
    try:
        direccion_valor = request.form.get("direccion", "").strip()
        if not direccion_valor:
            flash("⚠️ La dirección es obligatoria.", "warning")
            return redirect(url_for("transportista.actualizacion_datos"))

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

    return redirect(url_for("transportista.actualizacion_datos"))


# ---------- BORRAR DIRECCION ----------
@transportista.route("/direccion/borrar/<int:id_direccion>", methods=["POST"])
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

    return redirect(url_for("transportista.actualizacion_datos"))
