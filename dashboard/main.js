const API_URL = 'http://localhost:8000/api';

let currentProblemId = null;

async function fetchStats() {
  try {
    const res = await fetch(`${API_URL}/stats`);
    const stats = await res.json();
    document.getElementById('stats-container').innerHTML = `
      <div class="stat-item"><span class="stat-label">Observations</span><span class="stat-value">${stats.observations}</span></div>
      <div class="stat-item"><span class="stat-label">Problems</span><span class="stat-value">${stats.problems}</span></div>
      <div class="stat-item"><span class="stat-label">Opportunities</span><span class="stat-value">${stats.opportunities}</span></div>
    `;
  } catch (e) {
    console.error('Stats failed:', e);
  }
}

async function fetchOpportunities() {
  try {
    const res = await fetch(`${API_URL}/opportunities`);
    const data = await res.json();
    const grid = document.getElementById('opportunity-grid');
    
    if (!data.opportunities || data.opportunities.length === 0) {
      grid.innerHTML = '<div class="loading">No opportunities found. Run the engine first!</div>';
      return;
    }
    
    grid.innerHTML = data.opportunities.map(opp => `
      <div class="card" onclick="openProblem(${opp.problem_id})">
        <div class="card-header">
          <div class="card-score">${opp.score.toFixed(2)}</div>
        </div>
        <h3 class="card-title">${opp.title}</h3>
        <p class="card-desc">${opp.description}</p>
        <div class="card-metrics">
          <div class="metric"><span>🔥</span> <span class="metric-val">Sev: ${opp.severity}/10</span></div>
          <div class="metric"><span>⏱️</span> <span class="metric-val">Freq: ${opp.frequency}/10</span></div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Opportunities failed:', e);
  }
}

window.openProblem = async function(id) {
  currentProblemId = id;
  const modal = document.getElementById('problem-modal');
  const body = document.getElementById('modal-body');
  
  body.innerHTML = '<div style="text-align:center; padding: 2rem;">Loading analysis...</div>';
  modal.classList.add('active');
  
  try {
    const res = await fetch(`${API_URL}/problems/${id}`);
    const data = await res.json();
    
    body.innerHTML = `
      <h2>${data.problem.title}</h2>
      <p>${data.problem.description}</p>
      
      <h3 class="section-title">😈 Devil's Advocate (Why this fails)</h3>
      <div class="devil-box">${data.problem.devils_advocate || 'None provided'}</div>
      
      <h3 class="section-title">⚔️ Existing Solutions & Gaps</h3>
      ${data.solutions.map(s => `
        <div class="evidence-box">
          <strong>${s.name}</strong><br/>
          ${s.gap_notes || 'No gap notes.'}
        </div>
      `).join('')}
      
      <h3 class="section-title">📄 Raw Evidence Chains</h3>
      ${data.evidence.map(e => `
        <div class="evidence-box" style="border-left-color: #94a3b8;">
          <em>"${e.text}"</em><br/>
          <small style="color: #94a3b8;">Engagement: ${e.engagement || 0} | Source: ${e.source}</small>
        </div>
      `).join('')}
    `;
  } catch(e) {
    body.innerHTML = '<div style="color:red;">Error loading details.</div>';
  }
}

document.getElementById('close-modal').addEventListener('click', () => {
  document.getElementById('problem-modal').classList.remove('active');
});

async function submitFeedback(verdict) {
  if (!currentProblemId) return;
  try {
    await fetch(`${API_URL}/feedback/${currentProblemId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verdict, notes: "" })
    });
    document.getElementById('problem-modal').classList.remove('active');
    fetchOpportunities(); // refresh list
  } catch (e) {
    console.error(e);
  }
}

document.getElementById('btn-accept').addEventListener('click', () => submitFeedback('accept'));
document.getElementById('btn-reject').addEventListener('click', () => submitFeedback('reject'));

// Init
fetchStats();
fetchOpportunities();
