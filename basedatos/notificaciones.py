from basedatos.models import db, Notificaciones

def crear_notificacion(user_id, titulo, mensaje):
    """Crea y guarda una notificación para un usuario."""
    noti = Notificaciones(
        ID_Usuario=user_id,
        Titulo=titulo,
        Mensaje=mensaje
    )
    db.session.add(noti)
    db.session.commit()
