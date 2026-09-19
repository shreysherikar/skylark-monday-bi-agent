export interface ChatRequest {
  message: string;
  history?: Array<{
    role: string;
    content: string;
  }>;
}

export interface ChatResponse {
  response: string;
  tools_used: string[];
  caveats: string[];
  needs_clarification: boolean;
  suggested_options: string[];
}

export interface HealthResponse {
  status: string;
  environment: string;
  version: string;
}

export interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  tools_used?: string[];
  caveats?: string[];
  needs_clarification?: boolean;
  suggested_options?: string[];
  isError?: boolean;
}

export type ActiveView = 'chat' | 'overview' | 'funnel' | 'delivery' | 'quality';

export interface QualityCaveatMetrics {
  weighted_pipeline: {
    probability_null_count: number;
    probability_null_pct: number;
    deals_with_probability: number;
    total_deals: number;
    recorded_pipeline_value: number;
    value_with_probability: number;
  };
  deal_values_missing: {
    missing_value_count: number;
    total_deals: number;
    missing_value_pct: number;
  };
  receivables_negative: {
    negative_billing_count: number;
    overbilled_total: number;
    credit_balance_accounts: number;
    credit_balance_total: number;
  };
  cross_board_join: {
    matched_count: number;
    unmatched_work_orders: number;
    unmatched_deals: number;
  };
  unknown_with_billing: {
    count: number;
    billed_value_excl_gst: number;
  };
}

/** Live data-quality telemetry attached to the /api/overview payload. */
export interface OverviewDataQuality {
  caveat_metrics?: Partial<QualityCaveatMetrics>;
  caveats?: Record<string, string>;
  deals_total_rows: number;
  deals_close_date_null_count: number;
  work_orders_total_rows: number;
  work_orders_fully_null_columns: string[];
}

export interface OverviewMetrics {
  pipeline: {
    total_deals: number;
    active_pipeline_count: number;
    won_deals_count: number;
    lost_or_dormant_count: number;
    active_pipeline_unweighted_value: number;
    active_pipeline_weighted_value: number;
    won_deals_total_value: number;
    total_recorded_value: number;
    deals_missing_value_count: number;
    deals_missing_value_pct: number;
    active_deals_missing_prob_count: number;
    stage_breakdown: Record<string, { count: number; total_value: number; missing_value_count: number }>;
    sector_breakdown: Record<string, { total_deals: number; active_deals: number; won_deals: number; active_value: number; won_value: number }>;
    caveats: string[];
  };
  revenue: {
    total_work_orders: number;
    total_order_value_excl_gst: number;
    total_order_value_incl_gst: number;
    total_billed_value_excl_gst: number;
    total_billed_value_incl_gst: number;
    total_collected_value_incl_gst: number;
    net_receivables: number;
    gross_positive_receivables: number;
    credit_balance_total: number;
    credit_balance_accounts_count: number;
    negative_billing_excl_count: number;
    negative_billing_excl_total: number;
    invoice_status_breakdown: Record<string, number>;
    execution_status_breakdown: Record<string, number>;
    sector_breakdown: Record<string, { orders_count: number; total_order_val_excl: number; billed_val_excl: number; collected_val_incl: number; net_receivable: number }>;
    caveats: string[];
  };
  delivery: {
    total_work_orders: number;
    total_deals: number;
    matched_orders_count: number;
    unmatched_orders_count: number;
    link_coverage_percentage: number;
    completed_and_won_count: number;
    completed_with_open_deal_count: number;
    ongoing_or_pending_count: number;
    total_matched_order_value_excl_gst: number;
    total_matched_billed_value_excl_gst: number;
    caveats: string[];
  };
  data_quality?: OverviewDataQuality;
}

export interface QualityMetrics {
  work_orders?: {
    total_rows: number;
    fully_null_columns: string[];
    null_counts: Record<string, number>;
    negative_metrics: {
      amount_to_be_billed_excl_neg_count: number;
      amount_to_be_billed_incl_neg_count: number;
      amount_receivable_neg_count: number;
      balance_in_quantity_neg_count: number;
    };
    invoice_status_metrics: {
      not_billed_count: number;
      unknown_with_billing_count: number;
      other_counts: Record<string, number>;
    };
    unknown_status_counts: Record<string, number>;
  };
  deals?: {
    total_rows: number;
    core_null_rates: {
      closure_probability_null_rate: number;
      deal_value_null_rate: number;
      close_date_null_rate: number;
    };
    null_counts: Record<string, number>;
    unknown_status_counts: Record<string, number>;
  };
  gst_check?: {
    is_valid: boolean;
    checked_rows: number;
    discrepancy_count: number;
    discrepancies: Array<{ serial: string; excl: number; incl: number; expected_incl: number; diff: number }>;
    notes?: string;
    tolerance?: number;
  };
  /** Cross-board narrative caveats computed live by the backend. */
  caveats?: Record<string, string>;
  /** Machine-readable backing counts for every caveat above. */
  caveat_metrics?: Partial<QualityCaveatMetrics>;
}

export interface CommandItem {
  id: string;
  title: string;
  category: 'Navigation' | 'Executive Query' | 'System';
  action: () => void;
  icon?: string;
}
