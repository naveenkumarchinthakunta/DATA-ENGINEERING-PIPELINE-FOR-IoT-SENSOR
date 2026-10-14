/**
 * Sensors Monitoring View Controller.
 * Handles client-side filtering, searching, and pagination across 200 sensors.
 */

let allSensors = [];
let filteredSensors = [];
let currentPage = 1;
const pageSize = 25;

document.addEventListener('DOMContentLoaded', () => {
  loadSensorsData();
});

function onAutoRefresh() {
  loadSensorsData(false);
}

async function loadSensorsData(resetPagination = true) {
  try {
    const res = await fetch('/api/sensors');
    const data = await res.json();
    if (data.status === 'success') {
      allSensors = data.data.sensors;
      if (resetPagination) {
        currentPage = 1;
      }
      applyFilters();
    }
  } catch (err) {
    console.error('Failed fetching sensors:', err);
    document.getElementById('sensorsTableBody').innerHTML = `
      <tr><td colspan="8" class="empty-state" style="color: var(--color-danger);">Failed loading sensors from API: ${err}</td></tr>
    `;
  }
}

function applyFilters() {
  const searchTerm = (document.getElementById('sensorSearchInput').value || '').trim().toUpperCase();
  const zoneFilter = document.getElementById('filterZone').value;
  const statusFilter = document.getElementById('filterStatus').value;

  filteredSensors = allSensors.filter(s => {
    const matchSearch = !searchTerm || s.sensor_id.includes(searchTerm) || s.machine_id.includes(searchTerm);
    const matchZone = zoneFilter === 'All' || s.factory_zone === zoneFilter;
    const matchStatus = statusFilter === 'All' || s.sensor_status === statusFilter;
    return matchSearch && matchZone && matchStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filteredSensors.length / pageSize));
  if (currentPage > totalPages) currentPage = totalPages;

  renderSensorsTable();
}

function resetFilters() {
  document.getElementById('sensorSearchInput').value = '';
  document.getElementById('filterZone').value = 'All';
  document.getElementById('filterStatus').value = 'All';
  currentPage = 1;
  applyFilters();
}

function renderSensorsTable() {
  const tbody = document.getElementById('sensorsTableBody');
  const counterEl = document.getElementById('sensorCounter');
  const pageInfoEl = document.getElementById('pageInfo');
  const btnPrev = document.getElementById('btnPrevPage');
  const btnNext = document.getElementById('btnNextPage');

  counterEl.textContent = `Showing ${filteredSensors.length} of ${allSensors.length} sensors`;

  if (filteredSensors.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No sensors match the selected criteria.</td></tr>';
    pageInfoEl.textContent = 'Page 0 of 0';
    btnPrev.disabled = true;
    btnNext.disabled = true;
    return;
  }

  const totalPages = Math.ceil(filteredSensors.length / pageSize);
  pageInfoEl.textContent = `Page ${currentPage} of ${totalPages}`;
  btnPrev.disabled = currentPage <= 1;
  btnNext.disabled = currentPage >= totalPages;

  const startIdx = (currentPage - 1) * pageSize;
  const pageItems = filteredSensors.slice(startIdx, startIdx + pageSize);

  tbody.innerHTML = pageItems.map(s => {
    let statusBadge = 'badge-success';
    if (s.sensor_status === 'INACTIVE') statusBadge = 'badge-danger';
    if (s.sensor_status === 'MAINTENANCE') statusBadge = 'badge-warning';

    return `
      <tr>
        <td style="font-family: var(--font-mono); font-weight: 700;">${s.sensor_id}</td>
        <td>${s.machine_id}</td>
        <td>${s.factory_zone}</td>
        <td><span class="badge ${statusBadge}">${s.sensor_status}</span></td>
        <td style="font-family: var(--font-mono); color: #f97316;">${s.temperature_limit_min} - ${s.temperature_limit_max}</td>
        <td style="font-family: var(--font-mono); color: #10b981;">${s.pressure_limit_min} - ${s.pressure_limit_max}</td>
        <td style="font-family: var(--font-mono); color: #8b5cf6;">${s.vibration_limit_min} - ${s.vibration_limit_max}</td>
        <td>
          <a href="/trends?sensor=${s.sensor_id}" class="btn btn-outline btn-sm">Inspect Trends →</a>
        </td>
      </tr>
    `;
  }).join('');
}

function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    renderSensorsTable();
  }
}

function nextPage() {
  const totalPages = Math.ceil(filteredSensors.length / pageSize);
  if (currentPage < totalPages) {
    currentPage++;
    renderSensorsTable();
  }
}
