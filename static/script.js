let lastItinerary = null;
let lastRevisionLog = null;
let selectedInterests = ['beaches', 'food'];

document.querySelectorAll('.interest-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const val = chip.dataset.val;
    chip.classList.toggle('selected');
    if (chip.classList.contains('selected')) {
      if (!selectedInterests.includes(val)) selectedInterests.push(val);
    } else {
      selectedInterests = selectedInterests.filter(v => v !== val);
    }
  });
});

function resetForm() {
  document.getElementById('feedSection').classList.remove('show');
  document.getElementById('errorBox').classList.remove('show');
  document.getElementById('itineraryCard').classList.remove('show');
}

function showError(msg) {
  const box = document.getElementById('errorBox');
  box.innerHTML = '<span style="font-size:18px">⚠️</span><span>' + msg + '</span>';
  box.classList.add('show');
  document.getElementById('statusDot').classList.remove('running');
  document.getElementById('runBtn').disabled = false;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function createAttemptCard(attempt) {
  const col = document.getElementById('attemptsCol');
  const card = document.createElement('div');
  card.className = 'attempt-card';
  card.id = 'attempt-' + attempt;
  card.innerHTML = `
    <div class="attempt-header">
      <div class="attempt-label">🧠 Attempt ${attempt}</div>
      <div class="attempt-status pending" id="attempt-status-${attempt}">Drafting...</div>
    </div>
    <div id="attempt-detail-${attempt}"></div>
  `;
  col.appendChild(card);
}

function updateAttemptStatus(attempt, valid, errors, total) {
  const statusEl = document.getElementById('attempt-status-' + attempt);
  const detailEl = document.getElementById('attempt-detail-' + attempt);

  if (valid) {
    statusEl.className = 'attempt-status pass';
    statusEl.textContent = '✓ Passed';
    detailEl.innerHTML = `<div class="attempt-total">Total cost: ₹${total} — within budget</div>`;
  } else {
    statusEl.className = 'attempt-status fail';
    statusEl.textContent = '✗ Failed';
    detailEl.innerHTML = `
      <div class="attempt-errors">${errors.map(e => '• ' + escapeHtml(e)).join('<br>')}</div>
      <div class="attempt-total">Calculated total: ₹${total}</div>
    `;
  }
}

function renderItinerary(itinerary, destination) {
  document.getElementById('itineraryDest').textContent = `${destination} Itinerary`;
  const container = document.getElementById('dayBlocks');
  container.innerHTML = (itinerary.days || []).map(day => `
    <div class="day-block">
      <div class="day-header">Day ${day.day}: ${escapeHtml(day.theme || '')}</div>
      ${(day.activities || []).map(act => `
        <div class="activity-row">
          <div>
            <div class="activity-name">${escapeHtml(act.name)}</div>
            ${act.note ? `<div class="activity-note">${escapeHtml(act.note)}</div>` : ''}
          </div>
          <div class="activity-cost">₹${act.cost_inr}</div>
        </div>
      `).join('')}
    </div>
  `).join('');

  const total = (itinerary.days || []).reduce((sum, day) =>
    sum + (day.activities || []).reduce((s, a) => s + (a.cost_inr || 0), 0), 0);
  document.getElementById('totalAmount').textContent = '₹' + total;
  document.getElementById('itineraryCard').classList.add('show');
  document.getElementById('itineraryCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function runPlanner() {
  const destination = document.getElementById('destInput').value.trim() || 'Goa, India';
  const days = document.getElementById('daysInput').value || 3;
  const budget = document.getElementById('budgetInput').value || 15000;
  const interests = selectedInterests.length ? selectedInterests : ['general sightseeing'];

  resetForm();
  document.getElementById('feedSection').classList.add('show');
  document.getElementById('feedTitle').textContent = 'Agent working...';
  document.getElementById('statusDot').classList.add('running');
  document.getElementById('runBtn').disabled = true;
  document.getElementById('attemptsCol').innerHTML = '';

  const params = new URLSearchParams({ destination, days, budget, interests: interests.join(',') });
  const es = new EventSource('/api/plan?' + params.toString());

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case 'step':
        if (data.phase === 'think') {
          createAttemptCard(data.attempt);
        }
        break;

      case 'validated':
        updateAttemptStatus(data.attempt, data.valid, data.errors || [], data.calculated_total);
        break;

      case 'error':
        showError(data.message);
        es.close();
        break;

      case 'done':
        document.getElementById('feedTitle').textContent = 'Agent finished ✓';
        document.getElementById('statusDot').classList.remove('running');
        document.getElementById('runBtn').disabled = false;

        lastItinerary = data.itinerary;
        lastRevisionLog = data.revision_log;
        renderItinerary(data.itinerary, destination);
        es.close();
        break;
    }
  };

  es.onerror = () => {
    showError('Connection to agent lost. Make sure the Flask server is running and GROQ_API_KEY is set.');
    es.close();
  };
}

function downloadItinerary() {
  if (!lastItinerary) return;
  const blob = new Blob([JSON.stringify({ itinerary: lastItinerary, revision_log: lastRevisionLog }, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'itinerary.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function checkHealth() {
  try {
    const r = await fetch('/api/health');
    const data = await r.json();
    if (!data.api_key_set) document.getElementById('setupAlert').classList.add('show');
  } catch (e) {}
}

checkHealth();
