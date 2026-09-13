import React, { useState, useEffect } from 'react';
import { Radar, Database, Activity, ThumbsUp, CheckCircle2, Clock3, RefreshCw, Lightbulb } from 'lucide-react';
import OpportunityCard from './components/OpportunityCard';
import ProblemModal from './components/ProblemModal';
import './App.css'; 

const API_URL = 'http://localhost:8000/api';

function App() {
  const [stats, setStats] = useState({ observations: 0, problems: 0, opportunities: 0 });
  
  const [activeTab, setActiveTab] = useState('pipeline');
  
  const [opportunities, setOpportunities] = useState([]);
  const [observations, setObservations] = useState([]);
  const [pipeline, setPipeline] = useState([]);
  const [recentProblems, setRecentProblems] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [obsLoading, setObsLoading] = useState(false);
  
  const [selectedOpp, setSelectedOpp] = useState(null);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, oppsRes, pipelineRes, recentProblemsRes] = await Promise.all([
        fetch(`${API_URL}/stats`),
        fetch(`${API_URL}/opportunities`),
        fetch(`${API_URL}/pipeline`),
        fetch(`${API_URL}/problems/recent`)
      ]);
      const statsData = await statsRes.json();
      const oppsData = await oppsRes.json();
      const pipelineData = await pipelineRes.json();
      const recentProblemsData = await recentProblemsRes.json();
      
      setStats(statsData);
      setOpportunities(oppsData.opportunities || []);
      setPipeline(pipelineData.stages || []);
      setRecentProblems(recentProblemsData.problems || []);
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchObservations = async () => {
    setObsLoading(true);
    try {
      const res = await fetch(`${API_URL}/observations`);
      const data = await res.json();
      setObservations(data.observations || []);
    } catch (err) {
      console.error("Failed to fetch observations", err);
    } finally {
      setObsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = window.setInterval(fetchDashboardData, 4000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'observations' && observations.length === 0) {
      fetchObservations();
    }
  }, [activeTab]);

  return (
    <div className="app-layout">
      <header className="header">
        <div className="container header-content">
          <div className="logo-group">
            <div className="logo-icon"><Radar size={20} /></div>
            <h1>IDEA HUNTER</h1>
          </div>
          
          <div className="stats-group">
            <div className="stat">
              <Database size={14} className="text-muted" />
              <span className="stat-val">{stats.observations}</span>
              <span className="stat-label">Observations</span>
            </div>
            <div className="stat">
              <Activity size={14} className="text-muted" />
              <span className="stat-val">{stats.problems}</span>
              <span className="stat-label">Problems</span>
            </div>
            <div className="stat">
              <Lightbulb size={14} className="text-muted" />
              <span className="stat-val">{stats.opportunities}</span>
              <span className="stat-label">Opportunities</span>
            </div>
          </div>
        </div>
      </header>

      <main className="container main-content">
        <div className="dashboard-title">
          <div>
            <p className="eyebrow">LIVE DATABASE VIEW</p>
            <h2>Pipeline control room</h2>
          </div>
          <div className="live-indicator"><RefreshCw size={13} /> Refreshes every 4s{lastUpdated ? ` · ${lastUpdated.toLocaleTimeString()}` : ''}</div>
        </div>
        <div className="section-header" style={{ display: 'flex', gap: '28px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px', marginBottom: '32px' }}>
          <h2 className={activeTab === 'pipeline' ? 'active-tab' : ''} onClick={() => setActiveTab('pipeline')}>Pipeline</h2>
          <h2 className={activeTab === 'candidates' ? 'active-tab' : ''} onClick={() => setActiveTab('candidates')}>Candidates</h2>
          <h2 
            className={activeTab === 'opportunities' ? 'active-tab' : ''}
            onClick={() => setActiveTab('opportunities')}
          >
            Opportunity Radar
          </h2>
          <h2 
            className={activeTab === 'observations' ? 'active-tab' : ''}
            onClick={() => setActiveTab('observations')}
          >
            Raw Observations
          </h2>
        </div>

        {activeTab === 'pipeline' && (
          <section>
            <p className="section-copy">Watch each stage populate as the command runs. Counts come directly from PostgreSQL.</p>
            <div className="pipeline-grid">
              {pipeline.map((stage, index) => (
                <div className={`pipeline-stage ${stage.state}`} key={stage.id}>
                  <div className="stage-topline"><span className="stage-number">{String(index + 1).padStart(2, '0')}</span>{stage.state === 'complete' ? <CheckCircle2 size={18} /> : <Clock3 size={18} />}</div>
                  <h3>{stage.label}</h3>
                  <strong>{stage.value.toLocaleString()} <span>/ {stage.total.toLocaleString()}</span></strong>
                  <p>{stage.detail}</p>
                  <div className="stage-track"><i style={{ width: `${stage.total ? Math.min(100, (stage.value / stage.total) * 100) : 0}%` }} /></div>
                </div>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'candidates' && (
          <section>
            <p className="section-copy">Newest extracted problems, including candidates that are awaiting verification or research.</p>
            <div className="candidate-list">
              {recentProblems.map(problem => (
                <article className="candidate-row" key={problem.id}>
                  <div><p className="candidate-title">{problem.title}</p><span>Severity {problem.severity || '—'} · Frequency {problem.frequency || '—'} · {problem.signal_type}</span></div>
                  <span className={`status-pill ${problem.verified ? 'verified' : 'pending'}`}>{problem.verified ? 'Verified' : 'Awaiting verification'}</span>
                </article>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'opportunities' && (
          <>
            {loading ? (
              <div className="loading-state text-secondary">Loading intel...</div>
            ) : opportunities.length === 0 ? (
              <div className="empty-state">
                <p className="text-secondary">No opportunities found.</p>
                <p className="text-muted">Run the engine to extract problems from raw data.</p>
              </div>
            ) : (
              <div className="grid">
                {opportunities.map((opp, idx) => (
                  <div key={opp.id} className="animate-fade-in" style={{ animationDelay: `${idx * 0.05}s` }}>
                    <OpportunityCard 
                      opp={opp} 
                      onClick={() => setSelectedOpp(opp)}
                    />
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {activeTab === 'observations' && (
          <>
            {obsLoading ? (
              <div className="loading-state text-secondary">Loading observations...</div>
            ) : observations.length === 0 ? (
              <div className="empty-state">
                <p className="text-secondary">No raw observations collected yet.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {observations.map((obs, idx) => (
                  <div key={obs.id} className="animate-fade-in" style={{ 
                    background: 'var(--panel-bg)', 
                    border: '1px solid var(--border-color)', 
                    padding: '24px', 
                    borderRadius: '8px',
                    animationDelay: `${idx * 0.02}s`
                  }}>
                    <em style={{ display: 'block', marginBottom: '16px', fontStyle: 'normal', color: 'var(--text-primary)', lineHeight: '1.6' }}>"{obs.text}"</em>
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      <span>Source: {obs.source} {obs.cluster_id ? `(Cluster #${obs.cluster_id})` : '(Unclustered)'}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <ThumbsUp size={12} /> {obs.engagement || 0}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {selectedOpp && (
        <ProblemModal 
          opportunity={selectedOpp} 
          onClose={() => setSelectedOpp(null)}
          onRefresh={fetchDashboardData}
          apiUrl={API_URL}
        />
      )}
    </div>
  );
}

export default App;
