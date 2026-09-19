import React from 'react';
import { TrendingUp, AlertTriangle, ArrowUpRight, ShieldAlert, BarChart3 } from 'lucide-react';
import { fetchOverviewMetrics } from '../api';
import { useApiResource } from '../hooks/useApiResource';
import { ErrorState } from '../components/ErrorState';

interface FunnelViewProps {
  onAskAI: (prompt: string) => void;
}

export const FunnelView: React.FC<FunnelViewProps> = ({ onAskAI }) => {
  const { data, isLoading, error, reload } = useApiResource(fetchOverviewMetrics);

  if (isLoading) {
    return (
      <div className="dashboard-view-container">
        <div style={{ height: 28, width: 260 }} className="skeleton-pulse" />
        <div className="kpi-grid">
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ height: 130 }} className="skeleton-pulse" />
          ))}
        </div>
        <div style={{ height: 350 }} className="skeleton-pulse" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Unable to Load Pipeline Metrics"
        message={error || 'No data returned from the backend.'}
        onRetry={reload}
      />
    );
  }

  const { pipeline } = data;
  const fmt = (n: number) => `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  // All data-quality figures below come from the live API payload, never hardcoded.
  const metrics = data.data_quality?.caveat_metrics;
  const weighted = metrics?.weighted_pipeline;
  const missingValues = metrics?.deal_values_missing;
  const dealsTotal = data.data_quality?.deals_total_rows ?? pipeline.total_deals;
  const closeDateNulls = data.data_quality?.deals_close_date_null_count;
  const closeDateNullPct =
    closeDateNulls !== undefined && dealsTotal > 0
      ? (closeDateNulls / dealsTotal) * 100
      : undefined;
  const closeDatesPopulated =
    closeDateNulls !== undefined ? dealsTotal - closeDateNulls : undefined;

  return (
    <div className="dashboard-view-container">
      <div className="view-header-title">
        <div>
          <h2 className="view-heading">Deal Pipeline & Funnel Velocity</h2>
          <p className="view-sub">Stage progression, weighted probabilities, and severe null rate tracking</p>
        </div>
        <button
          className="search-command-btn"
          onClick={() => onAskAI('Break down active deal pipeline by probability and stage')}
        >
          <span>Analyze Funnel with AI</span>
          <ArrowUpRight size={14} />
        </button>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Unweighted Pipeline</span>
            <div className="kpi-icon"><TrendingUp size={16} /></div>
          </div>
          <div className="kpi-value">{fmt(pipeline.active_pipeline_unweighted_value)}</div>
          <div className="kpi-subtext">Sum of all recorded active deal values</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Probability-Weighted</span>
            <div className="kpi-icon" style={{ color: 'var(--indigo-400)' }}><BarChart3 size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--indigo-400)' }}>{fmt(pipeline.active_pipeline_weighted_value)}</div>
          <div className="kpi-subtext">High: 80% | Med: 50% | Low: 20%</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Deals Missing Value</span>
            <div className="kpi-icon" style={{ color: 'var(--amber-400)' }}><ShieldAlert size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--amber-400)' }}>{pipeline.deals_missing_value_pct}%</div>
          <div className="kpi-subtext">{pipeline.deals_missing_value_count} of {pipeline.total_deals} deals lack values</div>
        </div>
      </div>

      {/* Severe Null Rates Callout */}
      <div className="caveat-banner">
        <div className="caveat-banner-header">
          <AlertTriangle size={16} />
          <span>Severe Deals Board Null-Rate Governance Warnings</span>
        </div>
        <div className="caveat-bullet">
          <strong>Closure Probability:</strong>{' '}
          {weighted
            ? `${weighted.probability_null_pct.toFixed(1)}% of deals (${weighted.probability_null_count} of ${weighted.total_deals}) do NOT have a closure probability set. Weighted pipeline reflects only the ${weighted.deals_with_probability} deals with probabilities recorded.`
            : 'Closure probability null rate is unavailable from the quality report.'}
        </div>
        <div className="caveat-bullet">
          <strong>Masked Deal Value:</strong>{' '}
          {missingValues
            ? `${missingValues.missing_value_pct.toFixed(1)}% of deals (${missingValues.missing_value_count} of ${missingValues.total_deals}) lack recorded deal values. Total pipeline figures represent partial recorded data, not ground-truth totality.`
            : 'Deal-value null rate is unavailable from the quality report.'}
        </div>
        <div className="caveat-bullet">
          <strong>Close Date (A):</strong>{' '}
          {closeDateNullPct !== undefined && closeDatesPopulated !== undefined
            ? `${closeDateNullPct.toFixed(1)}% null rate (only ${closeDatesPopulated} dates populated out of ${dealsTotal}).`
            : 'Close-date null rate is unavailable from the quality report.'}
        </div>
      </div>

      {/* Stage Breakdown Table */}
      <div className="glass-panel">
        <div className="panel-header">
          <div className="panel-title">
            <BarChart3 size={18} color="var(--sky-400)" />
            <span>Deal Stage Breakdown & Recorded Values</span>
          </div>
        </div>

        <div className="premium-table-wrap">
          <table className="premium-table">
            <thead>
              <tr>
                <th>Deal Stage</th>
                <th>Total Deals</th>
                <th>Total Recorded Value</th>
                <th>Missing Value Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(pipeline.stage_breakdown).map(([stageName, stats]) => (
                <tr key={stageName}>
                  <td style={{ fontWeight: 600, color: '#fff' }}>{stageName}</td>
                  <td>{stats.count}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: stats.total_value > 0 ? 'var(--emerald-400)' : 'var(--text-muted)' }}>
                    {fmt(stats.total_value)}
                  </td>
                  <td style={{ color: stats.missing_value_count > 0 ? 'var(--amber-400)' : 'var(--text-muted)' }}>
                    {stats.missing_value_count} deals
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
