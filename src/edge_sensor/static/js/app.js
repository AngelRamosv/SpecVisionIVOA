// Configuración inicial de Chart.js
Chart.defaults.color = '#8A96A8';
Chart.defaults.font.family = 'Inter';

const ctx = document.getElementById('afluenciaChart').getContext('2d');

// Gradiente para la gráfica
let gradient = ctx.createLinearGradient(0, 0, 0, 200);
gradient.addColorStop(0, 'rgba(0, 230, 118, 0.5)');
gradient.addColorStop(1, 'rgba(0, 230, 118, 0.0)');

const chartData = {
  labels: Array(20).fill(''),
  datasets: [{
    label: 'Personas en toma',
    data: Array(20).fill(0),
    borderColor: '#00E676',
    backgroundColor: gradient,
    borderWidth: 2,
    fill: true,
    tension: 0.4,
    pointRadius: 0
  }]
};

const afluenciaChart = new Chart(ctx, {
  type: 'line',
  data: chartData,
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: true, color: 'rgba(255,255,255,0.05)' } },
      y: { grid: { display: true, color: 'rgba(255,255,255,0.05)' }, beginAtZero: true, suggestedMax: 10 }
    },
    animation: { duration: 0 }
  }
});

async function fetchEvents() {
  try {
    const res = await fetch('/api/events');
    const events = await res.json();
    
    const container = document.getElementById('logContainer');
    container.innerHTML = '';
    
    events.forEach(ev => {
      const div = document.createElement('div');
      div.className = 'log-box';
      
      let icon = 'ℹ️';
      let borderColor = 'rgba(255,255,255,0.1)';
      let iconColor = '#8A96A8';
      let title = ev.event_type.toUpperCase();
      let msg = ev.details?.message || ev.details?.action_required || 'Evento registrado';
      
      if (ev.severity === 'error') {
        icon = '⚠️'; borderColor = 'rgba(255, 23, 68, 0.3)'; iconColor = '#FF1744';
      } else if (ev.severity === 'warning') {
        icon = '⚠️'; borderColor = 'rgba(255, 179, 0, 0.3)'; iconColor = '#FFB300';
      } else if (ev.severity === 'info' && ev.event_type === 'camera_online') {
        icon = '✓'; borderColor = 'rgba(0, 230, 118, 0.3)'; iconColor = '#00E676';
      } else if (ev.severity === 'info') {
        icon = '✓'; borderColor = 'rgba(0, 191, 165, 0.2)'; iconColor = '#00BFA5';
      }
      
      div.style.borderColor = borderColor;
      
      div.innerHTML = `
        <div class="log-icon" style="color: ${iconColor}; font-size: 20px;">${icon}</div>
        <div>
          <p style="margin-bottom:2px;">${title}: ${msg}</p>
          <span style="color: var(--text-muted)">Generado: ${ev.timestamp}</span>
        </div>
      `;
      container.appendChild(div);
    });
  } catch(e) {}
}

async function fetchStats() {
  try {
    const res = await fetch('/stats');
    const data = await res.json();

    document.getElementById('personasToma').textContent = data.personas_en_toma;
    document.getElementById('inCount').textContent = data.in_count;
    document.getElementById('outCount').textContent = data.out_count;
    document.getElementById('filaCount').textContent = data.fila_count;
    document.getElementById('esperaEstimada').textContent = `~${data.fila_count * 2} min`;

    const filaStatus = document.getElementById('filaStatus');
    if(data.alerta_saturacion) {
      filaStatus.innerHTML = `⚠️ Cuello de botella detectado. Sugerimos abrir ventanilla.`;
      filaStatus.style.color = '#FF1744';
    } else {
      filaStatus.innerHTML = `✓ Fila fluida sin cuellos de botella`;
      filaStatus.style.color = '#00E676';
    }

    const mod1Box = document.getElementById('boxMod1');
    const pillMod1 = document.getElementById('pillMod1');
    const timeMod1 = document.getElementById('timeMod1');
    
    let ocupados = 0;
    
    if (data.modulo_count > 0) {
      mod1Box.className = 'module-box occupied';
      pillMod1.className = 'pill-yellow';
      pillMod1.textContent = 'OCUPADO';
      timeMod1.textContent = 'Atendiendo...';
      ocupados++;
    } else {
      mod1Box.className = 'module-box free';
      pillMod1.className = 'pill-green';
      pillMod1.textContent = 'LIBRE';
      timeMod1.textContent = 'Disponible';
    }
    
    document.getElementById('modulosActivos').textContent = ocupados;

    const chartArr = afluenciaChart.data.datasets[0].data;
    chartArr.push(data.personas_en_toma);
    chartArr.shift();
    afluenciaChart.update();

  } catch(e) {}
}

setInterval(fetchStats, 1000);
setInterval(fetchEvents, 2000);

fetchStats();
fetchEvents();
