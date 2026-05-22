const irradianceEl = document.getElementById('irradiance');
const efficiencyEl = document.getElementById('efficiency');

const ctx = document.getElementById('irradianceChart').getContext('2d');
const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Irradiance (W/m²)',
      data: [],
      borderColor: 'rgb(75, 192, 192)',
      tension: 0.1
    }]
  },
  options: {
    scales: {
      x: { title: { display: true, text: 'Time' } },
      y: { title: { display: true, text: 'W/m²' } }
    }
  }
});

const source = new EventSource('/data_stream');
source.onmessage = function (event) {
  const data = JSON.parse(event.data.replace(/'/g, '"'));
  irradianceEl.textContent = data.irradiance.toFixed(2);
  efficiencyEl.textContent = data.efficiency.toFixed(1);

  const now = data.timestamp;
  chart.data.labels.push(now);
  chart.data.datasets[0].data.push(data.irradiance);
  if (chart.data.labels.length > 50) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update();
};
