/**
 * Plotly.js Industrial Chart Builder.
 * Standardizes dark industrial themes, threshold reference lines, and responsive layout.
 */

// Global Dark Theme Configuration for Plotly
const plotlyLayoutDefaults = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(15, 23, 42, 0.4)',
  font: {
    family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    color: '#94a3b8',
    size: 11
  },
  margin: { t: 30, r: 20, b: 40, l: 45 },
  xaxis: {
    gridcolor: '#334155',
    linecolor: '#334155',
    zerolinecolor: '#334155'
  },
  yaxis: {
    gridcolor: '#334155',
    linecolor: '#334155',
    zerolinecolor: '#334155'
  }
};

const plotlyConfig = {
  responsive: true,
  displayModeBar: false
};

// 1. Factory Zone Distribution Donut Chart
function renderZoneChart(sensors) {
  const container = document.getElementById('chartZones');
  if (!container || !sensors) return;

  const zoneCounts = {};
  sensors.forEach(s => {
    zoneCounts[s.factory_zone] = (zoneCounts[s.factory_zone] || 0) + 1;
  });

  const data = [{
    values: Object.values(zoneCounts),
    labels: Object.keys(zoneCounts),
    type: 'pie',
    hole: 0.55,
    marker: {
      colors: ['#3b82f6', '#06b6d4', '#10b981', '#8b5cf6']
    },
    textinfo: 'label+percent',
    hoverinfo: 'label+value',
    textposition: 'outside'
  }];

  const layout = {
    ...plotlyLayoutDefaults,
    showlegend: false,
    margin: { t: 20, r: 20, b: 20, l: 20 }
  };

  Plotly.react('chartZones', data, layout, plotlyConfig);
}

// 2. Alert Severity Breakdown Bar Chart
function renderAlertsSeverityChart(severityBreakdown) {
  const container = document.getElementById('chartSeverity');
  if (!container || !severityBreakdown) return;

  const categories = ['CRITICAL', 'WARNING', 'INFO'];
  const values = categories.map(c => severityBreakdown[c] || 0);
  const colors = ['#ef4444', '#f59e0b', '#06b6d4'];

  const data = [{
    x: categories,
    y: values,
    type: 'bar',
    marker: { color: colors },
    text: values.map(String),
    textposition: 'auto'
  }];

  const layout = {
    ...plotlyLayoutDefaults,
    title: { text: 'Alerts by Severity', font: { color: '#f8fafc', size: 13 } }
  };

  Plotly.react('chartSeverity', data, layout, plotlyConfig);
}

// 3. Sensor Historical Trends (Temperature, Pressure, Vibration)
function renderSensorTrendsPlots(sensorId, readings, meta) {
  if (!readings || readings.length === 0) return;

  // Sort chronologically ascending
  const sorted = [...readings].sort((a, b) => new Date(a.event_timestamp) - new Date(b.event_timestamp));
  const timestamps = sorted.map(r => r.event_timestamp ? r.event_timestamp.replace('T', ' ').substring(0, 19) : '');
  const temps = sorted.map(r => r.temperature_celsius);
  const pressures = sorted.map(r => r.pressure_bar);
  const vibrations = sorted.map(r => r.vibration_mm_s);

  // Temperature Plot with Limits
  const tempShapes = [];
  if (meta) {
    if (meta.temperature_limit_max) {
      tempShapes.push({
        type: 'line',
        y0: meta.temperature_limit_max,
        y1: meta.temperature_limit_max,
        x0: 0,
        x1: 1,
        xref: 'paper',
        line: { color: '#ef4444', dash: 'dash', width: 2 }
      });
    }
    if (meta.temperature_limit_min) {
      tempShapes.push({
        type: 'line',
        y0: meta.temperature_limit_min,
        y1: meta.temperature_limit_min,
        x0: 0,
        x1: 1,
        xref: 'paper',
        line: { color: '#3b82f6', dash: 'dash', width: 2 }
      });
    }
  }

  const tempData = [{
    x: timestamps,
    y: temps,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Temperature (°C)',
    line: { color: '#f97316', width: 2 },
    marker: { size: 4, color: '#f97316' }
  }];

  Plotly.react('chartTempTrend', tempData, {
    ...plotlyLayoutDefaults,
    shapes: tempShapes,
    yaxis: { ...plotlyLayoutDefaults.yaxis, title: '°C' }
  }, plotlyConfig);

  // Pressure Plot
  const pressShapes = [];
  if (meta && meta.pressure_limit_max) {
    pressShapes.push({
      type: 'line',
      y0: meta.pressure_limit_max,
      y1: meta.pressure_limit_max,
      x0: 0,
      x1: 1,
      xref: 'paper',
      line: { color: '#ef4444', dash: 'dash', width: 2 }
    });
  }

  const pressData = [{
    x: timestamps,
    y: pressures,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Pressure (bar)',
    line: { color: '#10b981', width: 2 },
    marker: { size: 4, color: '#10b981' }
  }];

  Plotly.react('chartPressTrend', pressData, {
    ...plotlyLayoutDefaults,
    shapes: pressShapes,
    yaxis: { ...plotlyLayoutDefaults.yaxis, title: 'bar' }
  }, plotlyConfig);

  // Vibration Plot
  const vibShapes = [];
  if (meta && meta.vibration_limit_max) {
    vibShapes.push({
      type: 'line',
      y0: meta.vibration_limit_max,
      y1: meta.vibration_limit_max,
      x0: 0,
      x1: 1,
      xref: 'paper',
      line: { color: '#ef4444', dash: 'dash', width: 2 }
    });
  }

  const vibData = [{
    x: timestamps,
    y: vibrations,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Vibration (mm/s)',
    line: { color: '#8b5cf6', width: 2 },
    marker: { size: 4, color: '#8b5cf6' }
  }];

  Plotly.react('chartVibTrend', vibData, {
    ...plotlyLayoutDefaults,
    shapes: vibShapes,
    yaxis: { ...plotlyLayoutDefaults.yaxis, title: 'mm/s' }
  }, plotlyConfig);
}

// 4. Data Quality Quarantine Reasons Bar Chart
function renderRejectionChart(reasonsBreakdown) {
  const container = document.getElementById('chartRejections');
  if (!container || !reasonsBreakdown || reasonsBreakdown.length === 0) return;

  const reasons = reasonsBreakdown.map(r => r.reason);
  const counts = reasonsBreakdown.map(r => r.count);

  const data = [{
    y: reasons,
    x: counts,
    type: 'bar',
    orientation: 'h',
    marker: {
      color: '#ef4444'
    }
  }];

  const layout = {
    ...plotlyLayoutDefaults,
    margin: { t: 20, r: 20, b: 30, l: 180 },
    yaxis: {
      ...plotlyLayoutDefaults.yaxis,
      autorange: 'reversed'
    }
  };

  Plotly.react('chartRejections', data, layout, plotlyConfig);
}

// 5. Stage Timings Bar Chart
function renderStageTimingsChart(stageTimings) {
  const container = document.getElementById('chartStageLatencies');
  if (!container || !stageTimings) return;

  const stages = Object.keys(stageTimings);
  const durations = Object.values(stageTimings);

  const data = [{
    x: stages,
    y: durations,
    type: 'bar',
    marker: {
      color: '#3b82f6'
    },
    text: durations.map(d => `${d} ms`),
    textposition: 'auto'
  }];

  const layout = {
    ...plotlyLayoutDefaults,
    yaxis: { ...plotlyLayoutDefaults.yaxis, title: 'Duration (ms)' }
  };

  Plotly.react('chartStageLatencies', data, layout, plotlyConfig);
}
