from basedatos.models import db, Usuario
from basedatos.db import get_connection
from werkzeug.security import generate_password_hash

def seed_admin_user():
    """Crea un usuario administrador inicial"""
    try:
        # Configurar la conexión a la base de datos
        connection = get_connection()
        db.session = connection
        
        # Verificar si el usuario admin ya existe
        admin = Usuario.query.filter_by(Correo='lopexangel24@gmail.com').first()
        
        if not admin:
            # Crear el usuario administrador
            admin = Usuario(
                Nombre='admin',
                Correo='lopexangel24@gmail.com',
                Contraseña=generate_password_hash('admin123'),
                Rol='administrador',
                Activo=True
            )
            
            db.session.add(admin)
            db.session.commit()
            print('Usuario administrador creado exitosamente')
        else:
            print('El usuario administrador ya existe')
            
    except Exception as e:
        print(f'Error al crear usuario administrador: {str(e)}')
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == '__main__':
    seed_admin_user()
