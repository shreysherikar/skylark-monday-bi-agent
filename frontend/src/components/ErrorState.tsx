import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

/** Consistent, user-facing failure state for dashboard views. */
export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Unable to Load Live Metrics',
  message,
  onRetry,
}) => (
  <div className="dashboard-view-container">
    <div
      className="glass-panel"
      style={{ textAlign: 'center', padding: 40, borderColor: 'var(--rose-500)' }}
    >
      <AlertTriangle size={32} color="var(--rose-400)" style={{ margin: '0 auto 12px' }} />
      <h3 style={{ color: '#fff', marginBottom: 6 }}>{title}</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{message}</p>
      {onRetry && (
        <button className="search-command-btn" style={{ marginTop: 18 }} onClick={onRetry}>
          <RefreshCw size={14} />
          <span>Retry</span>
        </button>
      )}
    </div>
  </div>
);
