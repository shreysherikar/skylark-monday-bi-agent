import React, { useEffect, useState } from 'react';
import { Menu, Search, RefreshCw, Bell } from 'lucide-react';
import { ActiveView, HealthResponse } from '../types';
import { checkHealth } from '../api';

interface TopNavProps {
  activeView: ActiveView;
  onOpenMobileSidebar: () => void;
  onOpenCommandPalette: () => void;
  onRefreshData?: () => void;
  onLaunchCopilot?: () => void;
}

export const TopNav: React.FC<TopNavProps> = ({
  onOpenMobileSidebar,
  onOpenCommandPalette,
  onRefreshData,
}) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

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
        if (isMounted) setIsOnline(false);
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

  return (
    <header className="top-navbar">
      {/* Left: Delta logo & Aerospace nav links matching reference */}
      <div className="top-left">
        <button
          className="mobile-toggle"
          onClick={onOpenMobileSidebar}
          aria-label="Toggle menu"
        >
          <Menu size={20} />
        </button>

        <div className="top-brand-links">
          <div className="top-delta-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M3 18L12 4L21 18L12 14L3 18Z"
                fill="#00d9ff"
                stroke="#38bdf8"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <span className="top-link active">Skylark Ops</span>
          <span className="top-link">Analyse</span>
          <span className="top-link">Operate</span>
          <span className="top-link">Grow</span>
        </div>
      </div>

      {/* Right: Search, Notifications, Refresh, User avatar */}
      <div className="top-right">
        {/* Search Command Input matching reference */}
        <div className="top-search-bar" onClick={onOpenCommandPalette}>
          <Search size={14} className="search-icon" />
          <span className="search-placeholder">Ask anything...</span>
          <kbd className="search-kbd-pill">⌘K</kbd>
        </div>

        {/* Refresh Live Metrics Button */}
        {onRefreshData && (
          <button
            className="top-icon-button"
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

        {/* Notification Bell with red dot */}
        <button className="top-icon-button relative-btn" title="System alerts">
          <Bell size={16} />
          <span className="bell-alert-dot" />
        </button>

        {/* Live Status Indicator Pill */}
        <div className="top-status-indicator" title="Monday.com GraphQL Live Sync">
          <span className={`pulse-dot ${isOnline ? '' : 'offline'}`} />
          <span className="status-label">
            {isOnline
              ? health?.environment
                ? `Monday.com (${health.environment})`
                : 'Monday.com (Live)'
              : 'Offline'}
          </span>
        </div>

        {/* User Avatar Circle 'S' */}
        <div className="top-user-avatar" title="Skylark Admin">
          <span>S</span>
        </div>
      </div>
    </header>
  );
};
