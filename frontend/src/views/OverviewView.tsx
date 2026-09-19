import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowUpRight,
  ShieldAlert,
} from 'lucide-react';
import { OverviewMetrics } from '../types';
import { fetchOverviewMetrics } from '../api';

interface OverviewViewProps {
  onAskAI: (prompt: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({ onAskAI }) => {
  const [data, setData] = useState<OverviewMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      try {
        setIsLoading(true);
        const res = await fetchOverviewMetrics();
        if (isMounted) {
          setData(res);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Failed to load metrics');
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <div className="dashboard-view-container">
        <div style={{ height: 28, width: 220 }} className="skeleton-pulse" />
        <div className="kpi-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ height: 140 }} className="skeleton-pulse" />
          ))}
        </div>
        <div style={{ height: 300 }} className="skeleton-pulse" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="dashboard-view-container">
        <div className="glass-panel" style={{ textAlign: 'center', padding: 40, borderColor: 'var(--rose-500)' }}>
          <AlertTriangle size={32} color="var(--rose-400)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ color: '#fff', marginBottom: 6 }}>Unable to Load Live Metrics</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{error || 'No data returned from backend'}</p>
        </div>
      </div>
    );
  }

  const { pipeline, revenue, delivery } = data;

  // Format currency helper
  const fmt = (n: number) => `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  return (
    <div className="dashboard-view-container">
      <div className="view-header-title">
        <div>
          <h2 className="view-heading">Commercial Executive Overview</h2>
          <p className="view-sub">Real-time deterministic aggregations from live Monday.com Work Orders & Deals</p>
        </div>
        <button
          className="search-command-btn"
          style={{ color: 'var(--amber-400)', borderColor: 'rgba(245, 158, 11, 0.3)' }}
          onClick={() => onAskAI("Give me this week's leadership update")}
        >
          <span>Run Leadership Briefing</span>
          <ArrowUpRight size={14} />
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        {/* Card 1: Active Pipeline */}
        <div className="kpi-card" onClick={() => onAskAI('How is our active deal pipeline looking across sectors?')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="kpi-top-row">
              <span className="kpi-label">Active Pipeline</span>
              <div className="kpi-icon"><TrendingUp size={16} /></div>
            </div>
            <div className="kpi-value">{fmt(pipeline.active_pipeline_unweighted_value)}</div>
          </div>
          <div className="kpi-subtext">
            <span>Weighted: <strong>{fmt(pipeline.active_pipeline_weighted_value)}</strong></span>
            <span style={{ color: 'var(--text-dim)' }}>•</span>
            <span>{pipeline.active_pipeline_count} active deals</span>
          </div>
        </div>

        {/* Card 2: Won Deal Bookings */}
        <div className="kpi-card" onClick={() => onAskAI('What is our total won deal volume and stage breakdown?')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="kpi-top-row">
              <span className="kpi-label">Closed Won Volume</span>
              <div className="kpi-icon" style={{ color: 'var(--emerald-400)' }}><CheckCircle2 size={16} /></div>
            </div>
            <div className="kpi-value" style={{ color: 'var(--emerald-400)' }}>{fmt(pipeline.won_deals_total_value)}</div>
          </div>
          <div className="kpi-subtext">
            <span>{pipeline.won_deals_count} won deals</span>
            <span style={{ color: 'var(--text-dim)' }}>•</span>
            <span>{pipeline.total_deals} total tracked deals</span>
          </div>
        </div>

        {/* Card 3: Billed Work Orders */}
        <div className="kpi-card" onClick={() => onAskAI('What are our total billed work orders and unbilled orders?')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="kpi-top-row">
              <span className="kpi-label">Billed Value (Excl. GST)</span>
              <div className="kpi-icon" style={{ color: 'var(--indigo-400)' }}><DollarSign size={16} /></div>
            </div>
            <div className="kpi-value">{fmt(revenue.total_billed_value_excl_gst)}</div>
          </div>
          <div className="kpi-subtext">
            <span>Total Orders: <strong>{fmt(revenue.total_order_value_excl_gst)}</strong></span>
            <span style={{ color: 'var(--text-dim)' }}>•</span>
            <span>{revenue.total_work_orders} orders</span>
          </div>
        </div>

        {/* Card 4: Net Receivables & Credit Balances */}
        <div className="kpi-card" onClick={() => onAskAI('What are our total outstanding receivables and credit balances?')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="kpi-top-row">
              <span className="kpi-label">Net Outstanding AR</span>
              <div className="kpi-icon" style={{ color: 'var(--amber-400)' }}><ShieldAlert size={16} /></div>
            </div>
            <div className="kpi-value" style={{ color: 'var(--amber-400)' }}>{fmt(revenue.net_receivables)}</div>
          </div>
          <div className="kpi-subtext">
            <span>Gross: {fmt(revenue.gross_positive_receivables)}</span>
            <span style={{ color: 'var(--text-dim)' }}>•</span>
            <span style={{ color: 'var(--amber-400)' }}>{revenue.credit_balance_accounts_count} credit accounts</span>
          </div>
        </div>
      </div>

      {/* Cross-Board Delivery Alignment Banner */}
      <div className="glass-panel">
        <div className="panel-header">
          <div className="panel-title">
            <Layers size={18} color="var(--sky-400)" />
            <span>Cross-Board Linkage (Work Orders ↔ Deals)</span>
          </div>
          <span style={{ fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: 'var(--sky-400)' }}>
            Live Coverage: {delivery.link_coverage_percentage}%
          </span>
        </div>

        <div className="progress-track" style={{ height: 10, marginBottom: 14 }}>
          <div className="progress-fill" style={{ width: `${delivery.link_coverage_percentage}%` }} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, fontSize: '0.82rem' }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 14px', borderRadius: 8 }}>
            <span style={{ color: 'var(--text-muted)' }}>Linked Work Orders:</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-mono)' }}>
              {delivery.matched_orders_count} / {delivery.total_work_orders}
            </div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 14px', borderRadius: 8 }}>
            <span style={{ color: 'var(--text-muted)' }}>Completed & Won:</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--emerald-400)', fontFamily: 'var(--font-mono)' }}>
              {delivery.completed_and_won_count} orders
            </div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 14px', borderRadius: 8 }}>
            <span style={{ color: 'var(--text-muted)' }}>Completed with Open Deal:</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--amber-400)', fontFamily: 'var(--font-mono)' }}>
              {delivery.completed_with_open_deal_count} orders
            </div>
          </div>
        </div>
      </div>

      {/* Sector Breakdown Panel */}
      <div className="glass-panel">
        <div className="panel-header">
          <div className="panel-title">
            <TrendingUp size={18} color="var(--indigo-400)" />
            <span>Sector Performance & Pipeline Distribution</span>
          </div>
        </div>

        <div className="breakdown-list">
          {Object.entries(pipeline.sector_breakdown).map(([sec, stats]) => {
            const maxVal = Math.max(...Object.values(pipeline.sector_breakdown).map((s) => s.active_value + s.won_value), 1);
            const totalSecVal = stats.active_value + stats.won_value;
            const pct = Math.min(100, Math.round((totalSecVal / maxVal) * 100));

            return (
              <div key={sec} className="breakdown-row">
                <div className="breakdown-meta">
                  <span className="breakdown-label">
                    {sec} <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>({stats.total_deals} deals: {stats.won_deals} won, {stats.active_deals} active)</span>
                  </span>
                  <span className="breakdown-val">
                    Won: {fmt(stats.won_value)} | Active: {fmt(stats.active_value)}
                  </span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Active Data Caveats Callout */}
      <div className="caveat-banner">
        <div className="caveat-banner-header">
          <AlertTriangle size={16} />
          <span>Active Data Integrity Caveats From Quality Report</span>
        </div>
        {pipeline.caveats.concat(revenue.caveats).map((c, idx) => (
          <div key={idx} className="caveat-bullet">{c}</div>
        ))}
      </div>
    </div>
  );
};
