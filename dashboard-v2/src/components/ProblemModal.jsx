import React, { useState, useEffect } from 'react';
import { X, ThumbsUp, ExternalLink, CheckCircle2, AlertTriangle } from 'lucide-react';
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
            <p className="modal-kicker">STRUCTURED PROBLEM #{opportunity.problem_id}</p>
            <h2>{details?.problem?.title || opportunity.title}</h2>
            <div className="modal-badges">
              <span>{details?.problem?.status || 'loading'}</span>
              <span>{details?.problem?.verified ? 'Verified' : 'Needs validation'}</span>
              {details?.score && <span>Score {Math.round(details.score.final_score * 100)}%</span>}
            </div>
          </div>
          <button className="close-btn" onClick={onClose}><X size={20} /></button>
        </div>
        
        <div className="modal-body">
          {loading ? (
            <div className="text-secondary">Loading deep dive...</div>
          ) : (
            <>
              <div className="modal-section">
                <h3>Problem Overview</h3>
                <p className="problem-description">{details.problem.description || 'No description recorded.'}</p>
                <div className="detail-grid">
                  <div><label>Target user</label><strong>{details.problem.user_segment || 'Not specified'}</strong></div>
                  <div><label>Industry</label><strong>{details.problem.industry || 'Not specified'}</strong></div>
                  <div><label>Severity</label><strong>{details.problem.severity ?? '—'} / 10</strong></div>
                  <div><label>Frequency</label><strong>{details.problem.frequency ?? '—'} / 10</strong></div>
                  <div><label>Signal type</label><strong>{details.problem.signal_type || '—'}</strong></div>
                  <div><label>Verification attempts</label><strong>{details.problem.verification_attempts || 0}</strong></div>
                </div>
              </div>

              <div className="modal-section">
                <h3>Current Workaround</h3>
                <div className="info-box">{details.problem.workaround || 'No workaround was extracted.'}</div>
              </div>

              <div className="modal-section">
                <h3>Evidence Assessment</h3>
                <div className="assessment-box">
                  {details.problem.verified ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                  <div><strong>{details.problem.verified ? 'Evidence verified' : 'More evidence needed'}</strong><p>{details.problem.verification_reason || 'Not evaluated yet.'}</p></div>
                </div>
                {details.problem.verification_details && <pre className="metrics-json">{JSON.stringify(details.problem.verification_details, null, 2)}</pre>}
              </div>

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
                        {s.url && <a href={s.url} target="_blank" rel="noreferrer" className="solution-link">{s.url} <ExternalLink size={11} /></a>}
                        <p className="text-secondary" style={{marginTop: '4px'}}>{s.gap_notes || 'No gap notes recorded.'}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {details.research && (
                <div className="modal-section">
                  <h3>Research Brief</h3>
                  <div className="research-verdict"><strong>{details.research.debate_verdict || 'REVIEW'}</strong></div>
                  <div className="research-grid">
                    <div><label>Bull case</label><p>{details.research.bull_case || '—'}</p></div>
                    <div><label>Bear case</label><p>{details.research.bear_case || '—'}</p></div>
                    <div><label>Market</label><p>{details.research.market_research?.estimated_size || 'Unknown'} · {details.research.market_research?.growth_trajectory || 'Unknown growth'}</p></div>
                    <div><label>Why now</label><p>{details.research.why_now?.explanation || 'No timing thesis recorded.'}</p></div>
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
                        <span>Source: {e.source}{e.author ? ` · ${e.author}` : ''}</span>
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
