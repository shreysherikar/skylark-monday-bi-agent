import React from 'react';
import { Truck, DollarSign, ArrowUpRight, AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react';
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
  const fmt = (n: number) => `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  // Derived live from the quality report — no hardcoded business counts.
  const metrics = data.data_quality?.caveat_metrics;
  const receivables = metrics?.receivables_negative;
  const unknownBilling = metrics?.unknown_with_billing;
  const creditAccounts = receivables?.credit_balance_accounts ?? revenue.credit_balance_accounts_count;
  const negativeBillingCount = receivables?.negative_billing_count ?? revenue.negative_billing_excl_count;

  return (
    <div className="dashboard-view-container">
      <div className="view-header-title">
        <div>
          <h2 className="view-heading">Work Orders, Fulfillment & Billing</h2>
          <p className="view-sub">
            Execution status, invoice tracking, and credit balance accounting ({delivery.matched_orders_count} of {delivery.total_work_orders} linked, {delivery.link_coverage_percentage}% coverage)
          </p>
        </div>
        <button
          className="search-command-btn"
          onClick={() => onAskAI('What is the billing and collection status across work orders?')}
        >
          <span>Analyze Delivery with AI</span>
          <ArrowUpRight size={14} />
        </button>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
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
