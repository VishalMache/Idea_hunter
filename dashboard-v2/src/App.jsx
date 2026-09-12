import React, { useState, useEffect } from 'react';
import { Radar, Database, Activity, ThumbsUp } from 'lucide-react';
import OpportunityCard from './components/OpportunityCard';
import ProblemModal from './components/ProblemModal';
import './App.css'; 

const API_URL = 'http://localhost:8000/api';

function App() {
  const [stats, setStats] = useState({ observations: 0, problems: 0, opportunities: 0 });
  
  const [activeTab, setActiveTab] = useState('opportunities'); // 'opportunities' | 'observations'
  
  const [opportunities, setOpportunities] = useState([]);
  const [observations, setObservations] = useState([]);
  
  const [loading, setLoading] = useState(true);
  const [obsLoading, setObsLoading] = useState(false);
  
  const [selectedOpp, setSelectedOpp] = useState(null);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, oppsRes] = await Promise.all([
        fetch(`${API_URL}/stats`),
        fetch(`${API_URL}/opportunities`)
      ]);
      const statsData = await statsRes.json();
      const oppsData = await oppsRes.json();
      
      setStats(statsData);
      setOpportunities(oppsData.opportunities || []);
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
              <span className="stat-val">{stats.opportunities}</span>
              <span className="stat-label">Opportunities</span>
            </div>
          </div>
        </div>
      </header>

      <main className="container main-content">
        <div className="section-header" style={{ display: 'flex', gap: '32px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px', marginBottom: '32px' }}>
          <h2 
            style={{ cursor: 'pointer', transition: 'color 0.2s', color: activeTab === 'opportunities' ? 'var(--text-primary)' : 'var(--text-muted)' }} 
            onClick={() => setActiveTab('opportunities')}
          >
            Opportunity Radar
          </h2>
          <h2 
            style={{ cursor: 'pointer', transition: 'color 0.2s', color: activeTab === 'observations' ? 'var(--text-primary)' : 'var(--text-muted)' }} 
            onClick={() => setActiveTab('observations')}
          >
            Raw Observations
          </h2>
        </div>

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
