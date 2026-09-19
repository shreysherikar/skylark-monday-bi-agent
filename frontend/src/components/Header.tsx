import React, { useEffect, useState } from 'react';
import { Layers } from 'lucide-react';
import { checkHealth } from '../api';
import { HealthResponse } from '../types';

export const Header: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(true);

  // Poll /health periodically (every 30 seconds per requirements), NOT on every render
  useEffect(() => {
    let isMounted = true;

    const fetchStatus = async () => {
      try {
        const data = await checkHealth();
        if (isMounted) {
          setHealth(data);
          setIsOnline(true);
        }
      } catch {
        if (isMounted) {
          setIsOnline(false);
        }
      }
    };

    // Initial check
    fetchStatus();

    // 30-second periodic poll
    const interval = setInterval(fetchStatus, 30000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-icon">
          <Layers size={20} />
        </div>
        <div>
          <h1 className="brand-title">Skylark Drones</h1>
          <p className="brand-subtitle">Commercial Monday.com BI Agent</p>
        </div>
      </div>

      <div className="header-status">
        <span className={`status-dot ${isOnline ? '' : 'offline'}`} />
        <span>
          {isOnline
            ? health?.environment
              ? `Live (${health.environment})`
              : 'Live (Monday.com)'
            : 'Connecting...'}
        </span>
      </div>
    </header>
  );
};
