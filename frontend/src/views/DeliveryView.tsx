import React from 'react';
import {
  Truck,
  DollarSign,
  ArrowUpRight,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Link2,
  AlertOctagon,
  Layers,
  ArrowDownRight,
  Sparkles,
} from 'lucide-react';
import { fetchOverviewMetrics } from '../api';
import { useApiResource } from '../hooks/useApiResource';
import { ErrorState } from '../components/ErrorState';

interface DeliveryViewProps {
  onAskAI: (prompt: string) => void;
}

export const DeliveryView: React.FC<DeliveryViewProps> = ({ onAskAI }) => {
  const { data, isLoading, error, reload } = useApiResource(fetchOverviewMetrics);

  if (isLoading) {
    return (
      <div className="dashboard-view-container">
        <div style={{ height: 28, width: 260 }} className="skeleton-pulse" />
        <div className="kpi-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ height: 130 }} className="skeleton-pulse" />
          ))}
        </div>
        <div style={{ height: 300 }} className="skeleton-pulse" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Unable to Load Delivery Metrics"
        message={error || 'No data returned from the backend.'}
        onRetry={reload}
      />
    );
  }

  const { revenue, delivery } = data;
  const fmt = (n: number | null | undefined) => {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  };

  // Derived live from the quality report — no hardcoded business counts.
  const metrics = data.data_quality?.caveat_metrics;
  const receivables = metrics?.receivables_negative;
  const unknownBilling = metrics?.unknown_with_billing;
  const creditAccounts = receivables?.credit_balance_accounts ?? revenue.credit_balance_accounts_count;
  const negativeBillingCount = receivables?.negative_billing_count ?? revenue.negative_billing_excl_count;

  const risk = delivery.commercial_risk;
  const variance = delivery.value_variance;
  const backlog = delivery.won_deals_backlog;
  const linkedItems = delivery.linked_items || [];

  return (
    <div className="dashboard-view-container">
      {/* Header */}
      <div className="view-header-title">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <h2 className="view-heading" style={{ margin: 0 }}>Cross-Board Fulfillment & Commercial Risk</h2>
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                letterSpacing: '0.04em',
                padding: '3px 8px',
                borderRadius: '4px',
                background: 'rgba(56, 189, 248, 0.15)',
                color: 'var(--sky-400)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}
            >
              LIVE MONDAY CONNECT BOARDS
            </span>
          </div>
          <p className="view-sub">
            Deals (CRM) ↔ Work Orders (Fulfillment) alignment, commercial risk on unclosed deals, and contract value realization ({delivery.matched_orders_count} of {delivery.total_work_orders} linked, {delivery.link_coverage_percentage}% coverage)
          </p>
        </div>
        <button
          className="search-command-btn"
          onClick={() => onAskAI('Which work orders are executing on unclosed deals, and what is our total commercial exposure?')}
        >
          <Sparkles size={14} color="var(--sky-400)" />
          <span>Audit Cross-Board Risks</span>
          <ArrowUpRight size={14} />
        </button>
      </div>

      {/* Cross-Board Strategic KPI Cards */}
      <div className="kpi-grid">
        {/* Monday Linkage Health */}
        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Connect Boards Linkage</span>
            <div className="kpi-icon"><Link2 size={16} color="var(--sky-400)" /></div>
          </div>
          <div className="kpi-value">{delivery.matched_orders_count} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>/ {delivery.total_work_orders} WOs</span></div>
          <div className="kpi-subtext" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Coverage: <strong>{delivery.link_coverage_percentage}%</strong></span>
            <span>Unlinked: <strong>{delivery.unmatched_orders_count}</strong></span>
          </div>
        </div>

        {/* Commercial Risk on Unclosed Deals */}
        <div className="kpi-card" style={{ borderColor: (risk?.unclosed_deal_risk_count ?? 0) > 0 ? 'rgba(239, 68, 68, 0.4)' : undefined }}>
          <div className="kpi-top-row">
            <span className="kpi-label" style={{ color: (risk?.unclosed_deal_risk_count ?? 0) > 0 ? 'var(--rose-400)' : undefined }}>
              Commercial Risk Exposure
            </span>
            <div className="kpi-icon" style={{ color: 'var(--rose-400)' }}><AlertOctagon size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--rose-400)' }}>
            {fmt(risk?.unclosed_deal_risk_value_excl_gst ?? 0)}
          </div>
          <div className="kpi-subtext">
            <strong>{risk?.unclosed_deal_risk_count ?? 0} orders</strong> on unclosed deals ({risk?.high_risk_orders_count ?? 0} Ongoing/Completed)
          </div>
        </div>

        {/* Won Deals Execution Backlog */}
        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Won Deals Without WOs</span>
            <div className="kpi-icon" style={{ color: 'var(--amber-400)' }}><Layers size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--amber-400)' }}>
            {fmt(backlog?.won_deals_without_wo_value ?? 0)}
          </div>
          <div className="kpi-subtext">
            <strong>{backlog?.won_deals_without_wo_count ?? 0} of {backlog?.total_won_deals ?? 0} won deals</strong> lack linked Work Orders
          </div>
        </div>

        {/* Contract Leakage Variance */}
        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Contract Value Leakage</span>
            <div className="kpi-icon" style={{ color: 'var(--indigo-400)' }}><ArrowDownRight size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--indigo-400)' }}>
            {fmt(variance?.contract_leakage_value ?? 0)}
          </div>
          <div className="kpi-subtext">
            <strong>{variance?.contract_leakage_count ?? 0} projects</strong> where Deal contracted &gt; Booked WO
          </div>
        </div>
      </div>

      {/* Commercial Risk Alert Banner */}
      {(risk?.unclosed_deal_risk_count ?? 0) > 0 && (
        <div className="caveat-banner" style={{ borderLeftColor: 'var(--rose-500)', background: 'rgba(239, 68, 68, 0.08)' }}>
          <div className="caveat-banner-header" style={{ color: 'var(--rose-400)' }}>
            <AlertOctagon size={16} />
            <span>Commercial Governance Alert: Active Work Orders on Non-Won Deals</span>
          </div>
          <div className="caveat-bullet">
            <strong>{risk?.unclosed_deal_risk_count} Work Orders totaling {fmt(risk?.unclosed_deal_risk_value_excl_gst)} Excl GST ({fmt(risk?.unclosed_deal_risk_billed_excl_gst)} already billed)</strong> are currently executing or completed while the backing deal on Monday CRM remains unclosed (Open, On Hold, or Dead).
          </div>
          <div className="caveat-bullet" style={{ color: 'var(--text-secondary)' }}>
            Example: <strong>SDPLDEAL-099</strong> ({fmt(14391444)} order value) is marked <strong>Ongoing</strong> in operations, but its linked CRM deal <strong>Goku</strong> is still <strong>Open</strong> at stage <em>E. Proposal/Commercials Sent</em>.
          </div>
        </div>
      )}

      {/* Interactive Linked Deals ↔ Work Orders Alignment Table */}
      <div className="glass-panel" style={{ marginTop: 8 }}>
        <div className="panel-header">
          <div className="panel-title">
            <Link2 size={17} color="var(--sky-400)" />
            <span>Linked Deals ↔ Work Orders Alignment Matrix ({linkedItems.length} Connected Projects)</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Showing live Monday.com Connect Boards relationships
          </span>
        </div>
        <div className="premium-table-wrap">
          <table className="premium-table">
            <thead>
              <tr>
                <th>Work Order</th>
                <th>Deal Name (CRM)</th>
                <th>Deal Status & Stage</th>
                <th>Contract Deal Value</th>
                <th>Booked WO Value (Excl)</th>
                <th>Billed Value (Excl)</th>
                <th>Execution Status</th>
                <th>Commercial Status</th>
              </tr>
            </thead>
            <tbody>
              {linkedItems.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                    No linked deals recorded via Monday Connect Boards.
                  </td>
                </tr>
              ) : (
                linkedItems.map((item) => {
                  const isRisk = item.is_commercial_risk;
                  const isWon = item.deal_status?.toLowerCase() === 'won';

                  return (
                    <tr key={item.wo_serial} style={{ background: isRisk ? 'rgba(239, 68, 68, 0.03)' : undefined }}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#fff' }}>
                        {item.wo_serial}
                      </td>
                      <td style={{ fontWeight: 600, color: 'var(--sky-300)' }}>
                        {item.deal_name || item.wo_deal_name || '—'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                          <span
                            style={{
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              color: isWon ? 'var(--emerald-400)' : 'var(--amber-400)',
                            }}
                          >
                            {item.deal_status || 'UNKNOWN'}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {item.deal_stage || 'No Stage'}
                          </span>
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {fmt(item.deal_value)}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#fff' }}>
                        {fmt(item.wo_amount_excl_gst)}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {fmt(item.wo_billed_excl_gst)}
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            padding: '3px 8px',
                            borderRadius: '4px',
                            background: item.wo_execution_status === 'Completed' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                            color: item.wo_execution_status === 'Completed' ? 'var(--emerald-400)' : 'var(--sky-300)',
                            fontWeight: 600,
                          }}
                        >
                          {item.wo_execution_status || 'UNKNOWN'}
                        </span>
                      </td>
                      <td>
                        {item.risk_severity === 'HIGH' ? (
                          <span
                            style={{
                              fontSize: '0.72rem',
                              padding: '3px 8px',
                              borderRadius: '4px',
                              background: 'rgba(239, 68, 68, 0.2)',
                              color: 'var(--rose-400)',
                              fontWeight: 700,
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                            }}
                          >
                            HIGH RISK
                          </span>
                        ) : item.risk_severity === 'MEDIUM' || item.risk_severity === 'LOW' ? (
                          <span
                            style={{
                              fontSize: '0.72rem',
                              padding: '3px 8px',
                              borderRadius: '4px',
                              background: 'rgba(245, 158, 11, 0.15)',
                              color: 'var(--amber-400)',
                              fontWeight: 600,
                            }}
                          >
                            OPEN DEAL
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: '0.72rem',
                              padding: '3px 8px',
                              borderRadius: '4px',
                              background: 'rgba(16, 185, 129, 0.15)',
                              color: 'var(--emerald-400)',
                              fontWeight: 600,
                            }}
                          >
                            WON & ALIGNED
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Suggested Founder Prompts */}
      <div style={{ marginTop: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button
          className="search-command-btn"
          style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          onClick={() => onAskAI('List all work orders executing on unclosed deals with their order values and current deal stages.')}
        >
          <span>Audit orders on open deals</span>
          <ArrowUpRight size={13} />
        </button>
        <button
          className="search-command-btn"
          style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          onClick={() => onAskAI('What is the contract value variance between deals and work orders, and where do we have revenue leakage?')}
        >
          <span>Analyze contract value variance</span>
          <ArrowUpRight size={13} />
        </button>
        <button
          className="search-command-btn"
          style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          onClick={() => onAskAI('Which won deals have no work orders created yet, and what is the pipeline backlog?')}
        >
          <span>Won deals without work orders</span>
          <ArrowUpRight size={13} />
        </button>
      </div>

      {/* Financial Overview KPIs */}
      <div className="kpi-grid" style={{ marginTop: 24 }}>
        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Total Bookings (Excl. GST)</span>
            <div className="kpi-icon"><Truck size={16} /></div>
          </div>
          <div className="kpi-value">{fmt(revenue.total_order_value_excl_gst)}</div>
          <div className="kpi-subtext">Incl. GST: {fmt(revenue.total_order_value_incl_gst)}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Total Billed (Excl. GST)</span>
            <div className="kpi-icon" style={{ color: 'var(--indigo-400)' }}><DollarSign size={16} /></div>
          </div>
          <div className="kpi-value">{fmt(revenue.total_billed_value_excl_gst)}</div>
          <div className="kpi-subtext">Collected (Incl): {fmt(revenue.total_collected_value_incl_gst)}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Gross Receivables</span>
            <div className="kpi-icon" style={{ color: 'var(--emerald-400)' }}><CheckCircle2 size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--emerald-400)' }}>{fmt(revenue.gross_positive_receivables)}</div>
          <div className="kpi-subtext">Net after credits: <strong>{fmt(revenue.net_receivables)}</strong></div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top-row">
            <span className="kpi-label">Credit Balances ({creditAccounts} {creditAccounts === 1 ? 'Account' : 'Accounts'})</span>
            <div className="kpi-icon" style={{ color: 'var(--amber-400)' }}><ShieldAlert size={16} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--amber-400)' }}>{fmt(Math.abs(revenue.credit_balance_total))}</div>
          <div className="kpi-subtext">Customer overpayments / credit notes</div>
        </div>
      </div>

      {/* Negative Value Accounting Alert */}
      <div className="caveat-banner">
        <div className="caveat-banner-header">
          <AlertTriangle size={16} />
          <span>Legitimate Negative Balances & Bookkeeping Flags</span>
        </div>
        <div className="caveat-bullet">
          <strong>{creditAccounts} Credit {creditAccounts === 1 ? 'Account' : 'Accounts'}:</strong> Negative Amount Receivable rows totaling ₹{Math.abs(revenue.credit_balance_total).toLocaleString('en-IN')} represent legitimate customer credit balances and are preserved without clamping to zero.
        </div>
        <div className="caveat-bullet">
          <strong>{negativeBillingCount} Negative Billing {negativeBillingCount === 1 ? 'Row' : 'Rows'}:</strong> Amount to be billed contains {negativeBillingCount} negative {negativeBillingCount === 1 ? 'entry' : 'entries'} totaling ₹{revenue.negative_billing_excl_total.toLocaleString('en-IN')} Excl GST due to execution volume adjustments.
        </div>
        <div className="caveat-bullet">
          <strong>{unknownBilling?.count ?? '—'} UNKNOWN_WITH_BILLING:</strong> Work orders with billed revenue &gt; 0 but an unset invoice status
          {unknownBilling ? ` (₹${unknownBilling.billed_value_excl_gst.toLocaleString('en-IN')} Excl GST)` : ''}, tracked as a bookkeeping integrity flag.
        </div>
      </div>

      {/* Execution vs Billing Status Panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        {/* Execution Status Panel */}
        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <Truck size={17} color="var(--sky-400)" />
              <span>Execution Status Breakdown</span>
            </div>
          </div>
          <div className="premium-table-wrap">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Execution Status</th>
                  <th>Order Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(revenue.execution_status_breakdown).map(([statusName, count]) => (
                  <tr key={statusName}>
                    <td style={{ fontWeight: 600, color: '#fff' }}>{statusName}</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Invoice Status Panel */}
        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <DollarSign size={17} color="var(--indigo-400)" />
              <span>Invoice Status Breakdown</span>
            </div>
          </div>
          <div className="premium-table-wrap">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Invoice Status</th>
                  <th>Order Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(revenue.invoice_status_breakdown).map(([statusName, count]) => (
                  <tr key={statusName}>
                    <td style={{ fontWeight: 600, color: statusName === 'UNKNOWN_WITH_BILLING' ? 'var(--amber-400)' : '#fff' }}>
                      {statusName}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
