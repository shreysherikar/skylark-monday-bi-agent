import React from 'react';
import {
  Home,
  Bot,
  LayoutDashboard,
  TrendingUp,
  Truck,
  ShieldAlert,
  Sparkles,
  ExternalLink,
  LucideIcon,
  Quote,
} from 'lucide-react';
import { ActiveView } from '../types';
import { fetchOverviewMetrics } from '../api';
import { useApiResource } from '../hooks/useApiResource';

interface SidebarProps {
  activeView: ActiveView;
  onSelectView: (view: ActiveView) => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
  onTriggerLeadershipBriefing: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeView,
  onSelectView,
  isOpenMobile,
  onCloseMobile,
  onTriggerLeadershipBriefing,
}) => {
  const { data: boardSummary } = useApiResource(fetchOverviewMetrics);
  const workOrderCount = boardSummary?.revenue.total_work_orders;
  const dealCount = boardSummary?.pipeline.total_deals;

  const navItems: Array<{
    id: ActiveView;
    label: string;
    sublabel?: string;
    icon: LucideIcon;
    badge?: string;
    isAction?: boolean;
  }> = [
    { id: 'home', label: 'Home', sublabel: 'Product Tour', icon: Home },
    { id: 'chat', label: 'AI Copilot', icon: Bot, badge: 'LIVE' },
    { id: 'overview', label: 'Executive KPIs', icon: LayoutDashboard },
    { id: 'funnel', label: 'Deal Funnel', icon: TrendingUp },
    { id: 'delivery', label: 'Work Orders & AR', icon: Truck },
    { id: 'quality', label: 'Data Quality', icon: ShieldAlert },
    { id: 'chat', label: 'Leadership Briefing', icon: Sparkles, isAction: true },
  ];

  const handleNavClick = (item: typeof navItems[0]) => {
    if (item.isAction) {
      onTriggerLeadershipBriefing();
    } else {
      onSelectView(item.id);
    }
    onCloseMobile();
  };

  return (
    <aside className={`app-sidebar ${isOpenMobile ? 'open' : ''}`}>
      <div className="sidebar-top-section">
        {/* Brand Header */}
        <div
          className="sidebar-header"
          onClick={() => {
            onSelectView('home');
            onCloseMobile();
          }}
          style={{ cursor: 'pointer' }}
        >
          <div className="logo-badge">
            <div className="logo-icon-wrap">
              {/* Delta Wing Emblem matching reference image */}
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path
                  d="M3 18L12 4L21 18L12 14L3 18Z"
                  fill="url(#deltaGrad)"
                  stroke="#00d9ff"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
                <path d="M12 4L12 14" stroke="#ffffff" strokeWidth="1.2" opacity="0.8" />
                <defs>
                  <linearGradient id="deltaGrad" x1="3" y1="4" x2="21" y2="18">
                    <stop offset="0%" stopColor="#00d9ff" />
                    <stop offset="60%" stopColor="#0284c7" />
                    <stop offset="100%" stopColor="#6366f1" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div>
              <div className="logo-text-title">Skylark Drones</div>
              <div className="logo-text-subtitle">BUSINESS INTELLIGENCE</div>
            </div>
          </div>
        </div>

        {/* Navigation List */}
        <nav className="sidebar-nav">
          {navItems.map((item, idx) => {
            const Icon = item.icon;
            const isActive = !item.isAction && activeView === item.id;
            return (
              <button
                key={idx}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => handleNavClick(item)}
              >
                <div className="nav-item-icon-wrapper">
                  <Icon size={18} />
                </div>
                <div className="nav-item-label-group">
                  <span className="nav-item-title">{item.label}</span>
                  {item.sublabel && <span className="nav-item-sublabel">{item.sublabel}</span>}
                </div>
                {item.badge && <span className="nav-live-badge">{item.badge}</span>}
              </button>
            );
          })}
        </nav>

        {/* SYSTEM STATUS Section matching reference */}
        <div className="sidebar-status-section">
          <div className="sidebar-category-heading">SYSTEM STATUS</div>
          <div className="status-indicators-list">
            <div className="status-indicator-item">
              <span className="status-pulse-dot" />
              <span>Monday.com Connected</span>
            </div>
            <div className="status-indicator-item">
              <span className="status-pulse-dot" />
              <span>Boards Synced ({workOrderCount ?? 176} WOs, {dealCount ?? 344} Deals)</span>
            </div>
            <div className="status-indicator-item">
              <span className="status-pulse-dot" />
              <span>Analytics Engine Ready</span>
            </div>
            <div className="status-indicator-item">
              <span className="status-pulse-dot" />
              <span>AI Copilot Online</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar Footer Section */}
      <div className="sidebar-footer">
        {/* Monday.com Environment Card */}
        <div className="monday-environment-card">
          <div className="monday-card-left">
            <div className="monday-color-dots">
              <span style={{ background: '#f43f5e' }} />
              <span style={{ background: '#fbbf24' }} />
              <span style={{ background: '#10b981' }} />
            </div>
            <div>
              <div className="monday-card-title">Monday.com (Live Board)</div>
              <div className="monday-card-sub">Last sync: 2 min ago</div>
            </div>
          </div>
          <ExternalLink size={14} className="monday-card-link-icon" />
        </div>

        {/* Motivational Mission Quote Card */}
        <div className="sidebar-quote-card">
          <Quote size={16} className="sidebar-quote-icon" />
          <p className="sidebar-quote-text">
            “ Turning operational data into higher perspectives. ”
          </p>
        </div>
      </div>
    </aside>
  );
};
