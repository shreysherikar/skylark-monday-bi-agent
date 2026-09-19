import React, { useEffect, useState } from 'react';
import { Menu, Search, RefreshCw } from 'lucide-react';
import { ActiveView, HealthResponse } from '../types';
import { checkHealth } from '../api';

interface TopNavProps {
  activeView: ActiveView;
  onOpenMobileSidebar: () => void;
  onOpenCommandPalette: () => void;
  onRefreshData?: () => void;
}

const VIEW_TITLES: Record<ActiveView, { title: string; category: string }> = {
  chat: { title: 'AI Copilot Chat', category: 'Conversational Intelligence' },
  overview: { title: 'Executive Overview', category: 'Commercial KPIs' },
  funnel: { title: 'Deal Pipeline Funnel', category: 'Sales Pipeline' },
  delivery: { title: 'Work Orders & AR', category: 'Fulfillment & Billing' },
  quality: { title: 'Data Quality & Audit', category: 'Governance & Integrity' },
};

export const TopNav: React.FC<TopNavProps> = ({
  activeView,
  onOpenMobileSidebar,
  onOpenCommandPalette,
  onRefreshData,
}) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Poll /health periodically (every 30 seconds), NOT on every render
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

    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleRefresh = async () => {
    if (onRefreshData && !isRefreshing) {
      setIsRefreshing(true);
      await onRefreshData();
      setTimeout(() => setIsRefreshing(false), 600);
    }
  };

  const viewMeta = VIEW_TITLES[activeView];

  return (
    <header className="top-navbar">
      <div className="top-left">
        <button
          className="mobile-toggle"
          onClick={onOpenMobileSidebar}
          aria-label="Toggle menu"
        >
          <Menu size={20} />
        </button>

        <div className="view-breadcrumb">
          <span className="breadcrumb-root">{viewMeta.category}</span>
          <span style={{ color: 'var(--text-dim)' }}>/</span>
          <span className="breadcrumb-current">{viewMeta.title}</span>
        </div>
      </div>

      <div className="top-right">
        <button
          className="search-command-btn"
          onClick={onOpenCommandPalette}
          title="Search actions (Ctrl+K or ⌘K)"
        >
          <Search size={15} />
          <span>Quick actions</span>
          <kbd className="kbd-shortcut">⌘K</kbd>
        </button>

        {onRefreshData && (
          <button
            className="search-command-btn"
            style={{ padding: '6px 8px' }}
            onClick={handleRefresh}
            title="Refresh metrics from Monday.com"
          >
            <RefreshCw
              size={15}
              style={{
                animation: isRefreshing ? 'spin 0.8s linear infinite' : 'none',
              }}
            />
          </button>
        )}

        <div className="status-indicator-pill">
          <span className={`pulse-dot ${isOnline ? '' : 'offline'}`} />
          <span>
            {isOnline
              ? health?.environment
                ? `Monday.com (${health.environment})`
                : 'Monday.com (Live)'
              : 'Connecting...'}
          </span>
        </div>
      </div>
    </header>
  );
};
