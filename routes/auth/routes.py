from flask import render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_login import login_required, login_user, logout_user
from sqlalchemy import func
from basedatos.models import db, Usuario
from basedatos.decoradores import validar_password, validar_email, send_reset_email
from basedatos.notificaciones import crear_notificacion
from . import auth


s = URLSafeTimedSerializer("mi_clave_super_secreta_y_unica")

# ------------------ REGISTRO ------------------ #
@auth.route('/register', methods=['POST'])
def register():
    nombre_completo = request.form.get('name', '').strip()
    correo = request.form.get('email', '').strip().lower()
    telefono = request.form.get('phone', '').strip()
    password = request.form.get('password', '').strip()

    # Validaciones básicas
    if not nombre_completo or not correo or not password:
        return jsonify({'status': 'warning', 'message': 'Nombre, correo y contraseña son obligatorios.'})

    if not validar_email(correo):
        return jsonify({'status': 'danger', 'message': 'Correo inválido.'})

    error = validar_password(password)
    if error:
        return jsonify({'status': 'danger', 'message': error})

    
    usuario_existente = Usuario.query.filter(func.lower(Usuario.Correo) == correo).first()
    if usuario_existente:
        return jsonify({'status': 'danger', 'message': 'Este correo ya está registrado. Usa otro por favor.'})

    nombre, apellido = (nombre_completo.split(" ", 1) + [""])[:2]

    try:
        nuevo_usuario = Usuario(
            Nombre=nombre,
            Apellido=apellido,
            Telefono=telefono,
            Correo=correo,
            Contraseña=generate_password_hash(password),
            Rol="cliente",
            Activo=1
        )
        db.session.add(nuevo_usuario)
        db.session.commit()

        crear_notificacion(
            user_id=nuevo_usuario.ID_Usuario,
            titulo="¡Bienvenido!",
            mensaje="Tu cuenta se ha creado correctamente."
        )

      
        return jsonify({
            'status': 'success',
            'message': 'Cuenta creada correctamente.Ahora puedes iniciar sesión.',
            'redirect': url_for('index'),
            'delay': 3000  
        })

    except Exception as e:
        db.session.rollback()

        if 'Duplicate entry' in str(e):
            return jsonify({'status': 'danger', 'message': 'El correo ya está registrado. Intenta con otro.'})

        return jsonify({'status': 'danger', 'message': f'Error al registrar: {str(e)}'})


# ------------------ LOGIN ------------------ #
@auth.route('/login', methods=['POST'])
def login():
    try:
        correo = request.form.get('correo', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not correo or not password:
            return jsonify({'status': 'warning', 'message': 'Debes ingresar correo y contraseña.'})

        usuario = Usuario.query.filter(func.lower(Usuario.Correo) == correo).first()

        if usuario and check_password_hash(usuario.Contraseña, password):
            login_user(usuario)
            session['username'] = f"{usuario.Nombre} {usuario.Apellido or ''}".strip()

            rutas_por_rol = {
                'admin': 'admin.dashboard',
                'cliente': 'cliente.dashboard',
                'transportista': 'transportista.dashboard',
                'instalador': 'instalador.dashboard'
            }
            destino = rutas_por_rol.get(usuario.Rol, 'index')

            if usuario.Rol == 'cliente':
                session['mostrar_bienvenida'] = True

            return jsonify({
                'status': 'success',
                'message': 'Inicio de sesión exitoso.',
                'redirect': url_for(destino)
            })

        return jsonify({'status': 'danger', 'message': 'Correo o contraseña incorrectos.'})

    except Exception as e:
        print("❌ ERROR LOGIN:", e)
        return jsonify({'status': 'danger', 'message': f'Error interno: {str(e)}'})


# ------------------ LOGOUT ------------------ #
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('index'))


# ------------------ OLVIDÉ CONTRASEÑA ------------------ #
@auth.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get("email", "").strip().lower()
    user = Usuario.query.filter(func.lower(Usuario.Correo) == email).first()

    if not user:
        return jsonify({'status': 'warning', 'message': 'Correo no registrado.'})

    try:
        token = s.dumps(email, salt='password-recovery')
        send_reset_email(user_email=email, user_name=user.Nombre, token=token)
        return jsonify({'status': 'success', 'message': 'Correo enviado para restablecer contraseña.'})
    except Exception as e:
        return jsonify({'status': 'danger', 'message': f'Error al enviar correo: {str(e)}'})


# ------------------ RESTABLECER CONTRASEÑA ------------------ #
@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        try:
            email = s.loads(token, salt='password-recovery', max_age=3600)
            return render_template('common/index.html', token=token, mostrar_modal_reset=True, token_expirado=False)
        except (SignatureExpired, BadSignature):
            return render_template('common/index.html', mostrar_modal_reset=False, token_expirado=True, token=None)

  
    try:
        email = s.loads(token, salt='password-recovery', max_age=3600)
    except (SignatureExpired, BadSignature):
        return jsonify({'status': 'danger', 'message': 'Enlace inválido o expirado.'})

    new_password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not new_password or not confirm_password:
        return jsonify({'status': 'warning', 'message': 'Completa ambos campos.'})
    if new_password != confirm_password:
        return jsonify({'status': 'warning', 'message': 'Las contraseñas no coinciden.'})

    error = validar_password(new_password)
    if error:
        return jsonify({'status': 'warning', 'message': error})

    user = Usuario.query.filter(func.lower(Usuario.Correo) == email).first()
    if not user:
        return jsonify({'status': 'danger', 'message': 'Usuario no encontrado.'})

    user.Contraseña = generate_password_hash(new_password)
    db.session.commit()

    crear_notificacion(
        user_id=user.ID_Usuario,
        titulo="Contraseña actualizada",
        mensaje="Tu contraseña ha sido cambiada exitosamente."
    )

    return jsonify({
    'status': 'success',
    'message': 'Contraseña restablecida correctamente. Ahora puedes iniciar sesión.',
    'redirect': url_for('index')
})

