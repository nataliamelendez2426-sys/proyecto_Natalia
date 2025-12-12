# Sistema de Gestión de Casa en el arbol

## Descripción
Sistema integral de gestión para tienda en línea desarrollado con Python, Flask y MySQL. La plataforma permite la administración de productos, pedidos, usuarios, proveedores y garantías, con diferentes roles de usuario (administrador, cliente , transportista y instalador).

## Características Principales

## Gestión de Usuarios
- Registro y autenticación de usuarios con diferentes roles (administrador, cliente , transportista y instalador)
- Perfiles de usuario personalizables
- Gestión de direcciones de envío
- Preferencias de catálogo

## Catálogo de Productos
- Gestión de productos con categorías y etiquetas
- Imágenes múltiples por producto
- Búsqueda y filtrado avanzado
- Sistema de reseñas y calificaciones

## Carrito y Pedidos
- Carrito de compras
- Proceso de pago integrado
- Seguimiento de pedidos en tiempo real
- Historial de compras

## Gestión de Inventario
- Control de stock
- Alertas de inventario bajo
- Gestión de proveedores
- Registro de compras

## Calendario y Citas
- Agendamiento de citas para servicio técnico
- Seguimiento de garantías
- Recordatorios automáticos

## Notificaciones
- Sistema de notificaciones en tiempo real
- Notificaciones por correo electrónico
- Historial de notificaciones

## Tecnologías Utilizadas

## Backend
- Python 3.x
- Flask
- SQLAlchemy 
- MySQL

## Frontend
- HTML5
- CSS3
- JavaScript
- Bootstrap 5

## Otras Herramientas
- Git para control de versiones
- JWT para autenticación
- SMTP para envío de correos

## Instalación

## Requisitos Previos
- Python 3.8 o superior
- MySQL Server
- pip (gestor de paquetes de Python)

## Pasos de Instalación

1. **Clonar el repositorio**
   ```bash
   git clone [URL_DEL_REPOSITORIO]
   cd PROYECTO_NATALIA
   ```

2. **Crear un entorno virtual**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # En Windows
   source venv/bin/activate  # En Linux/Mac
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**
   Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:
   ```
   SECRET_KEY=tu_clave_secreta_aqui
   DATABASE_URI=mysql+pymysql://usuario:contraseña@localhost:3306/tienda_db
   MAIL_USERNAME=tu_correo@gmail.com
   MAIL_PASSWORD=tu_contraseña_app_especifica
   ```

5. **Inicializar la base de datos**
   ```bash
   python
   >>> from app import app, db
   >>> with app.app_context():
   ...     db.create_all()
   ```


## Ejecución

Para iniciar el servidor de desarrollo:

```bash
python app.py
```
El sistema estará disponible en: `http://localhost:5000`

---

## Despliegue en Railway

La aplicación está desplegada en Railway y puede ser accedida en:
[![Railway](https://railway.app/button.svg)](https://proyectonatalia-production.up.railway.app/)


5. **Configurar variables de entorno**
   Asegúrate de configurar las mismas variables de entorno que en desarrollo:
   - `SECRET_KEY`
   - `DATABASE_URI` (puedes usar la base de datos proporcionada por Railway)
   - `MAIL_USERNAME`
   - `MAIL_PASSWORD`

6. **Desplegar la aplicación**
   ```bash
   git push railway main
   ```

## Estructura del Proyecto

```
PROYECTO_NATALIA/
├── app.py                  # Punto de entrada de la aplicación
├── basedatos/              # Modelos y configuración de base de datos
│   ├── db.py               # Configuración de SQLAlchemy
│   ├── decoradores.py      # Decoradores personalizados
│   ├── models.py           # Modelos de la base de datos
│   └── notificaciones.py   # Lógica de notificaciones
├── routes/                 # Rutas de la aplicación
│   ├── administrador/      # Vistas de administrador
│   ├── auth/               # Autenticación y autorización
│   ├── cliente/            # Vistas de cliente
│   └── transportista/      # Vistas de transportista
├── static/                 # Archivos estáticos (CSS, JS, imágenes)
│   ├── css/
│   ├── js/
│   └── img/
└── templates/              # Plantillas HTML
    ├── admin/              # Plantillas de administrador
    ├── auth/               # Plantillas de autenticación
    ├── cliente/            # Plantillas de cliente
    └── transportista/      # Plantillas de transportista
```

## Roles de Usuario

## Administrador
- Gestión completa de productos y categorías
- Administración de usuarios
- Seguimiento de pedidos
- Gestión de garantías
- Reportes y estadísticas

## Cliente
- Navegación por el catálogo
- Gestión de pedidos
- Sistema de reseñas
- Seguimiento de garantías
- Perfil personalizable

## Transportista
- Gestión de entregas
- Actualización de estado de pedidos
- Registro fotográfico de entregas
- Calendario de entregas

## Contribución

1.  Haz un Fork del proyecto.
2.  Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
3.  Commit de tus cambios (`git commit -m 'Agrega nueva funcionalidad'`).
4.  Push a la rama (`git push origin feature/nueva-funcionalidad`).
5.  Abre un Pull Request.

---

