document.addEventListener('DOMContentLoaded', () => {

  const modalPedido = document.getElementById('modalPedido');

  if (modalPedido) {
    modalPedido.addEventListener('show.bs.modal', event => {
      const button = event.relatedTarget;
      if (!button) return;

      const pedidoId = button.getAttribute('data-id');
      const contenido = document.getElementById('detalle-pedido-contenido');
      if (!contenido) return;

      contenido.innerHTML = `<p class="text-muted">Cargando detalles del pedido #${pedidoId}...</p>`;

      fetch(`/cliente/pedido/${pedidoId}/detalle`)
        .then(resp => {
          if (!resp.ok) throw new Error('Error al obtener los detalles del pedido.');
          return resp.json();  // <-- ahora esperamos JSON
        })
        .then(data => {
          if (!data.detalles || data.detalles.length === 0) {
            contenido.innerHTML = '<p class="text-danger">❌ No se encontraron detalles para este pedido.</p>';
            return;
          }

          let html = '';

          // Dirección
          if (data.direccion) {
            html += `
              <div class="mb-3">
                <h6>Dirección de entrega</h6>
                <p>
                  ${data.direccion.Direccion || ''}, 
                  ${data.direccion.Barrio || ''}, 
                  ${data.direccion.Municipio || ''}, 
                  ${data.direccion.Departamento || ''}, 
                  ${data.direccion.Pais || ''}
                </p>
              </div>
            `;
          }

          html += `<h6>Productos</h6>`;
          html += `<ul class="list-group mb-3">`;

          let totalPedido = 0;

          data.detalles.forEach(detalle => {
            const cantidad = detalle.Cantidad || 0;
            const precioUnidad = detalle.PrecioUnidad || 0;
            const subtotal = detalle.Subtotal || cantidad * precioUnidad;
            totalPedido += subtotal;

            html += `
              <li class="list-group-item">
                <strong>${detalle.ProductoNombre || 'Producto'}</strong><br>
                Cantidad: ${cantidad}<br>
                Precio unidad: $${precioUnidad.toFixed(2)}<br>
                Subtotal: $${subtotal.toFixed(2)}
              </li>
            `;
          });

          html += `</ul>`;
          html += `<p class="text-end fw-bold">Total pedido: $${totalPedido.toFixed(2)}</p>`;

          contenido.innerHTML = html;
        })
        .catch(err => {
          contenido.innerHTML = `<p class="text-danger">❌ No se pudieron cargar los detalles: ${err.message}</p>`;
        });
    });
  }

});
