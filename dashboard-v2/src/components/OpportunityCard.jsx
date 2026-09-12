import React from 'react';
import { AlertCircle, Clock } from 'lucide-react';
import './OpportunityCard.css';

export default function OpportunityCard({ opp, onClick }) {
  return (
    <div className="opp-card" onClick={onClick}>
      <div className="opp-card-header">
        <div className="opp-score">{(opp.score * 100).toFixed(0)}% Match</div>
        {opp.unresearched_count > 0 && (
          <div className="opp-score" style={{ color: 'var(--text-muted)', borderColor: 'var(--border-subtle)', background: 'transparent' }}>
            {opp.unresearched_count} Unresearched Dims
          </div>
        )}
      </div>
      
      <h3 className="opp-title">{opp.title}</h3>
      <p className="opp-desc">{opp.description}</p>
      
      <div className="opp-metrics">
        <div className="opp-metric">
          <AlertCircle size={14} className="opp-metric-icon" />
          <span>Sev: {opp.severity}/10</span>
        </div>
        <div className="opp-metric">
          <Clock size={14} className="opp-metric-icon" />
          <span>Freq: {opp.frequency}/10</span>
        </div>
      </div>
    </div>
  );
}
