import React, { useState, useEffect } from 'react';
import { X, ThumbsUp } from 'lucide-react';
import './ProblemModal.css';

export default function ProblemModal({ opportunity, onClose, onRefresh, apiUrl }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${apiUrl}/problems/${opportunity.problem_id}`)
      .then(r => r.json())
      .then(d => {
        setDetails(d);
        setLoading(false);
      })
      .catch(e => console.error(e));
  }, [opportunity, apiUrl]);

  const handleFeedback = async (verdict) => {
    try {
      await fetch(`${apiUrl}/feedback/${opportunity.problem_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict })
      });
      onClose();
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>{opportunity.title}</h2>
            <p>{opportunity.description}</p>
          </div>
          <button className="close-btn" onClick={onClose}><X size={20} /></button>
        </div>
        
        <div className="modal-body">
          {loading ? (
            <div className="text-secondary">Loading deep dive...</div>
          ) : (
            <>
              {details.problem.devils_advocate && (
                <div className="modal-section">
                  <h3>Devil's Advocate</h3>
                  <div className="devil-box">{details.problem.devils_advocate}</div>
                </div>
              )}

              {details.solutions && details.solutions.length > 0 && (
                <div className="modal-section">
                  <h3>Existing Solutions</h3>
                  <div className="evidence-list">
                    {details.solutions.map((s, i) => (
                      <div key={i} className="evidence-item">
                        <strong>{s.name}</strong>
                        <p className="text-secondary" style={{marginTop: '4px'}}>{s.gap_notes}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="modal-section">
                <h3>Raw Evidence</h3>
                <div className="evidence-list">
                  {details.evidence.map((e, i) => (
                    <div key={i} className="evidence-item">
                      <em>"{e.text}"</em>
                      <div className="evidence-meta">
                        <span>Source: {e.source}</span>
                        <span style={{display: 'flex', alignItems: 'center', gap: '4px'}}>
                          <ThumbsUp size={12} /> {e.engagement || 0}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <div className="footer-actions">
            <button className="btn btn-reject" onClick={() => handleFeedback('reject')}>Reject</button>
            <button className="btn btn-primary" onClick={() => handleFeedback('accept')}>Accept Idea</button>
          </div>
        </div>
      </div>
    </div>
  );
}
