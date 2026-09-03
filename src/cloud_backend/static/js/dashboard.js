const API_URL = '/v1/findings';

async function fetchFindings() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) throw new Error('API request failed');
        const data = await response.json();
        renderTickets(data);
        updateStats(data);
    } catch (error) {
        console.error('Error fetching findings:', error);
        document.getElementById('tickets-container').innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--danger);">
                Error al conectar con la API central.
            </div>`;
    }
}

async function clearTickets() {
    try {
        await fetch(API_URL, { method: 'DELETE' });
        fetchFindings();
    } catch (error) {
        console.error('Error clearing tickets:', error);
    }
}

function updateStats(data) {
    document.getElementById('stat-total').innerText = data.length;
    const open = data.filter(t => t.estado === 'DETECTADO').length;
    document.getElementById('stat-open').innerText = open;
    const closed = data.filter(t => t.estado === 'CERRADO').length;
    document.getElementById('stat-closed').innerText = closed;
}

async function closeTicket(id) {
    try {
        const btn = document.getElementById('btn-'+id);
        btn.innerHTML = '<div class="loader" style="width:16px;height:16px;border-width:2px;"></div>';
        btn.disabled = true;

        const response = await fetch('/v1/findings/' + id + '/status', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'CERRADO' })
        });
        
        if (response.ok) {
            fetchFindings();
        } else {
            alert("Error al cerrar ticket");
            btn.innerHTML = 'Resolver';
            btn.disabled = false;
        }
    } catch (error) {
        console.error('Error updating status:', error);
        alert("Error al cerrar ticket");
    }
}

function renderTickets(tickets) {
    const container = document.getElementById('tickets-container');
    if (tickets.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted); background: var(--glass-bg); border-radius: 1rem;">
                No hay hallazgos registrados.
            </div>`;
        return;
    }

    container.innerHTML = '';
    tickets.forEach(ticket => {
        const isClosed = ticket.estado === 'CERRADO';
        const badgeClass = ticket.estado.toLowerCase();
        
        const card = document.createElement('div');
        card.className = 'ticket-card';
        card.innerHTML = `
            <div class="ticket-header">
                <span class="ticket-id">#TKT-${ticket.id.toString().padStart(4, '0')}</span>
                <span class="badge ${badgeClass}">${ticket.estado}</span>
            </div>
            <div class="ticket-title">${ticket.categoria}</div>
            <div class="ticket-meta">
                <div><strong>Creado:</strong> ${ticket.fecha_creacion}</div>
                ${ticket.categoria === 'Apertura Tardía' ? `
                    <div style="color: var(--danger); font-size: 0.95em; margin: 4px 0;">
                        <strong>Sistema_comienza:</strong> 09:15:00<br>
                        <strong>Sistema_detecta:</strong> ${ticket.fecha_creacion ? ticket.fecha_creacion.split(' ')[1] : 'Desconocida'}
                    </div>
                ` : ''}
                ${!isClosed ? `<div style="color: var(--warning)"><strong>Vencimiento SLA:</strong> ${ticket.fecha_vencimiento}</div>` : ''}
                ${isClosed ? `<div style="color: var(--success)"><strong>Cerrado:</strong> ${ticket.fecha_cierre}</div>` : ''}
            </div>
            <button id="btn-${ticket.id}" 
                    class="btn ${!isClosed ? 'btn-resolve' : ''}" 
                    ${isClosed ? 'disabled' : ''}
                    onclick="closeTicket(${ticket.id})">
                ${isClosed ? 'Resuelto' : 'Marcar como Resuelto'}
            </button>
        `;
        container.appendChild(card);
    });
}

fetchFindings();
setInterval(fetchFindings, 5000);
