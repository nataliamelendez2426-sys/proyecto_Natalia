document.addEventListener('DOMContentLoaded', () => {

  // --- Menú lateral y secciones ---
  const menuItems = {
    'menu-perfil': document.getElementById('seccion-perfil'),
    'menu-direcciones': document.getElementById('seccion-direcciones'),
    'menu-pedidos': document.getElementById('seccion-pedidos')
  };

  function ocultarSecciones() {
    Object.values(menuItems).forEach(sec => sec && (sec.style.display = 'none'));
    Object.keys(menuItems).forEach(id => {
      const menu = document.getElementById(id);
      menu && menu.classList.remove('active');
    });
  }

  Object.keys(menuItems).forEach(id => {
    const menu = document.getElementById(id);
    if (!menu) return;
    menu.addEventListener('click', () => {
      ocultarSecciones();
      menuItems[id].style.display = 'block';
      menu.classList.add('active');
    });
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
    btnConfirmarBorrar.addEventListener('click', () => {
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

      const urlDetalle = button.getAttribute('data-url');
      const contenido = document.getElementById('detalle-pedido-contenido');
      if (!contenido) return;

      contenido.innerHTML = `<p class="text-muted">Cargando detalles del pedido...</p>`;

      fetch(urlDetalle)
        .then(response => {
          if (!response.ok) throw new Error('Error al obtener los detalles del pedido.');
          return response.json();
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
