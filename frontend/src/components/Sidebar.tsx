import React from 'react';
import {
  MessageSquare,
  LayoutDashboard,
  TrendingUp,
  Truck,
  ShieldAlert,
  Layers,
  Sparkles,
  ExternalLink,
  LucideIcon,
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
  // Live board item counts (never hardcoded). Renders '—' while loading or if the
  // backend is unreachable, instead of displaying a stale number.
  const { data: boardSummary } = useApiResource(fetchOverviewMetrics);
  const workOrderCount = boardSummary?.revenue.total_work_orders;
  const dealCount = boardSummary?.pipeline.total_deals;
  const navItems: Array<{ id: ActiveView; label: string; icon: LucideIcon }> = [
    { id: 'chat', label: 'AI Copilot', icon: MessageSquare },
    { id: 'overview', label: 'Executive KPIs', icon: LayoutDashboard },
    { id: 'funnel', label: 'Deal Funnel', icon: TrendingUp },
    { id: 'delivery', label: 'Work Orders & AR', icon: Truck },
    { id: 'quality', label: 'Data Quality Audit', icon: ShieldAlert },
  ];

  const handleNavClick = (view: ActiveView) => {
    onSelectView(view);
    onCloseMobile();
  };

  return (
    <aside className={`app-sidebar ${isOpenMobile ? 'open' : ''}`}>
      <div>
        <div className="sidebar-header">
          <div className="logo-badge">
            <div className="logo-icon-wrap">
              <Layers size={22} />
            </div>
            <div>
              <div className="logo-text-title">Skylark Drones</div>
              <div className="logo-text-subtitle">Commercial Monday.com BI</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-category">Intelligence Views</div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => handleNavClick(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}

          <div className="nav-category" style={{ marginTop: 12 }}>Executive Actions</div>
          <button
            className="nav-item"
            style={{ color: 'var(--amber-400)', borderColor: 'rgba(245, 158, 11, 0.2)' }}
            onClick={() => {
              onTriggerLeadershipBriefing();
              onCloseMobile();
            }}
          >
            <Sparkles size={17} color="#fbbf24" />
            <span>Generate Briefing</span>
          </button>
        </nav>
      </div>

      <div className="sidebar-footer">
        <div className="boards-status-widget">
          <div className="widget-title">Live Monday.com Boards</div>
          <div className="widget-row">
            <span>Work Orders:</span>
            <span className="widget-count">{workOrderCount ?? '—'} items</span>
          </div>
          <div className="widget-row">
            <span>Deal Funnel:</span>
            <span className="widget-count">{dealCount ?? '—'} items</span>
          </div>
          <div className="widget-row" style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
            <span>Connect Boards:</span>
            <span style={{ color: 'var(--emerald-400)' }}>Live Relation</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          <span>Skylark BI v0.1.0</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            Read-Only MCP <ExternalLink size={11} />
          </span>
        </div>
      </div>
    </aside>
  );
};
