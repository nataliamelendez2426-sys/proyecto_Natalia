document.addEventListener('DOMContentLoaded', () => {

  // --- Menú lateral y secciones ---
  const menuPerfil = document.getElementById('menu-perfil');
  const menuDirecciones = document.getElementById('menu-direcciones');
  const menuPedidos = document.getElementById('menu-pedidos');

  const seccionPerfil = document.getElementById('seccion-perfil');
  const seccionDirecciones = document.getElementById('seccion-direcciones');
  const seccionPedidos = document.getElementById('seccion-pedidos');

  function ocultarSecciones() {
    [seccionPerfil, seccionDirecciones, seccionPedidos].forEach(sec => {
      if (sec) sec.style.display = 'none';
    });
    [menuPerfil, menuDirecciones, menuPedidos].forEach(menu => {
      if (menu) menu.classList.remove('active');
    });
  }

  if (menuPerfil) menuPerfil.addEventListener('click', () => {
    ocultarSecciones();
    if (seccionPerfil) seccionPerfil.style.display = 'block';
    menuPerfil.classList.add('active');
  });

  if (menuDirecciones) menuDirecciones.addEventListener('click', () => {
    ocultarSecciones();
    if (seccionDirecciones) seccionDirecciones.style.display = 'block';
    menuDirecciones.classList.add('active');
  });

  if (menuPedidos) menuPedidos.addEventListener('click', () => {
    ocultarSecciones();
    if (seccionPedidos) seccionPedidos.style.display = 'block';
    menuPedidos.classList.add('active');
  });

  // --- Confirmación de borrado de dirección ---
  let urlBorrar = null;
  const modalBorrarEl = document.getElementById('modalConfirmarBorrar');
  const modalBorrar = modalBorrarEl ? new bootstrap.Modal(modalBorrarEl) : null;

  document.querySelectorAll('.btn-borrar-direccion').forEach(btn => {
    btn.addEventListener('click', function () {
      urlBorrar = this.dataset.url;
      if (modalBorrar) modalBorrar.show();
    });
  });

  const formBorrar = document.createElement('form');
  formBorrar.method = 'POST';
  formBorrar.style.display = 'none';
  document.body.appendChild(formBorrar);

  const btnConfirmarBorrar = document.getElementById('btnConfirmarBorrar');
  if (btnConfirmarBorrar) {
    btnConfirmarBorrar.addEventListener('click', function () {
      if (urlBorrar) {
        formBorrar.action = urlBorrar;
        formBorrar.submit();
      }
    });
  }

  // --- Modal Detalle Pedido ---
  const modalPedido = document.getElementById('modalPedido');
  if (modalPedido) {
    modalPedido.addEventListener('show.bs.modal', event => {
      const button = event.relatedTarget;
      if (!button) return;

      const pedidoId = button.getAttribute('data-id');
      const contenido = document.getElementById('detalle-pedido-contenido');
      if (!contenido) return;

      contenido.innerHTML = `<p class="text-muted">Cargando detalles del pedido #${pedidoId}...</p>`;

      const urlDetalle = `{{ url_for('cliente.detalle_pedido_ajax', pedido_id=0) }}`.replace('/0', `/${pedidoId}`);

      fetch(urlDetalle)
        .then(response => {
          if (!response.ok) throw new Error('Error al obtener los detalles del pedido.');
          return response.json(); // JSON de tu ruta Flask
        })
        .then(detalles => {
          if (!detalles || detalles.length === 0) {
            contenido.innerHTML = `<p class="text-danger">❌ No se encontraron detalles para este pedido.</p>`;
            return;
          }

          let html = '<ul class="list-group">';
          detalles.forEach(detalle => {
            html += `
              <li class="list-group-item">
                <p class="mb-1"><strong>Producto:</strong> ${detalle.Producto}</p>
                <p class="mb-1 text-success"><strong>Precio unidad:</strong> $${detalle.PrecioUnidad.toFixed(2)}</p>
                <p class="mb-1"><strong>Cantidad:</strong> ${detalle.Cantidad}</p>
                <p class="mb-1"><strong>Total:</strong> $${detalle.Total.toFixed(2)}</p>
              </li>`;
          });
          html += '</ul>';
          contenido.innerHTML = html;
        })
        .catch(error => {
          contenido.innerHTML = `<p class="text-danger">❌ No se pudieron cargar los detalles: ${error.message}</p>`;
          console.error(error);
        });
    });
  }

});
