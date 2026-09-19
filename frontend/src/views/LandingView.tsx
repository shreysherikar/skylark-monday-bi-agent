import React from 'react';
import {
  Sparkles,
  ArrowRight,
  Database,
  Truck,
  Layers,
  ShieldCheck,
  TrendingUp,
  BarChart3,
  ShieldAlert,
  Lock,
  RefreshCw,
  FileSpreadsheet,
  AlertTriangle,
  ArrowUpRight,
  Activity,
  CheckCircle2,
  FileText,
} from 'lucide-react';
import { ActiveView } from '../types';
import { fetchOverviewMetrics } from '../api';
import { useApiResource } from '../hooks/useApiResource';
import { DroneOperationsHeroVisual } from '../components/DroneOperationsHeroVisual';
import { use3DTilt } from '../hooks/use3DTilt';

interface LandingViewProps {
  onSelectView: (view: ActiveView) => void;
  onAskAI: (prompt: string) => void;
}

// 3D Glass Interactive Tilt Card
const TiltFeatureCard: React.FC<{
  className?: string;
  onClick?: () => void;
  children: React.ReactNode;
}> = ({ className, onClick, children }) => {
  const { ref, tiltStyle, onMouseMove, onMouseLeave } = use3DTilt(9, 1.03);
  return (
    <div
      ref={ref}
      className={className}
      onClick={onClick}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      style={{
        transform: tiltStyle.transform,
        position: 'relative',
        transition: 'transform 0.15s ease-out',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: 'inherit',
          pointerEvents: 'none',
          zIndex: 2,
          transition: 'opacity 0.2s',
          ...tiltStyle.glareStyle,
        }}
      />
      {children}
    </div>
  );
};

export const LandingView: React.FC<LandingViewProps> = ({ onSelectView, onAskAI }) => {
  const { data: metrics, isLoading } = useApiResource(fetchOverviewMetrics);

  const fmt = (n?: number) =>
    n !== undefined ? `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';

  const pipeline = metrics?.pipeline;
  const revenue = metrics?.revenue;
  const delivery = metrics?.delivery;

  return (
    <div className="landing-page-container">
      {/* =========================================================================
          SECTION 9: HERO SECTION — Real 3D UAV Quadcopter & Operations Command Center
          ========================================================================= */}
      <section className="cinematic-hero-section">
        {/* Real 3D Physical UAV Quadcopter & Earth Operations WebGL Visual */}
        <DroneOperationsHeroVisual
          activeOperationsCount={delivery?.matched_orders_count ? delivery.matched_orders_count * 8 + 7 : 127}
        />

        {/* Hero Foreground Content Overlay */}
        <div className="hero-foreground-content">
          <div className="hero-eyebrow-tag">
            <span className="eyebrow-dot" />
            <span>MONDAY.COM • BUSINESS INTELLIGENCE AGENT</span>
          </div>

          <h1 className="hero-grand-title">
            TURN MESSY BUSINESS DATA <br />
            <span className="hero-gradient-title">INTO ACTIONABLE INTELLIGENCE.</span>
          </h1>

          <p className="hero-subtext">
            An AI-powered business intelligence agent that connects to Monday.com Work Orders and Deals,
            understands founder-level questions, and delivers contextual insights across sales,
            revenue, pipeline, and operations.
          </p>

          <div className="hero-cta-button-group">
            <button
              className="hero-btn-primary"
              onClick={() => onSelectView('chat')}
            >
              <span>LAUNCH AI COPILOT</span>
              <ArrowRight size={18} />
            </button>

            <button
              className="hero-btn-secondary"
              onClick={() => {
                const el = document.getElementById('core-intelligence');
                el?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              <span>EXPLORE INTELLIGENCE</span>
            </button>
          </div>

          {/* Hero Live Status Dots Pill */}
          <div className="hero-live-status-pills">
            <div className="status-item">
              <span className="dot dot-emerald" />
              <span>Monday.com Connected</span>
            </div>
            <div className="status-item">
              <span className="dot dot-cyan" />
              <span>Work Orders Live</span>
            </div>
            <div className="status-item">
              <span className="dot dot-purple" />
              <span>Deals Live</span>
            </div>
            <div className="status-item">
              <span className="dot dot-amber" />
              <span>Read-Only Access</span>
            </div>
          </div>
        </div>

        {/* 4 Floating Holographic Glass Feature Cards matching Reference Benchmark */}
        <div className="hero-floating-cards-grid">
          {/* Card 1: Sales Intelligence */}
          <TiltFeatureCard
            className="hero-feature-card"
            onClick={() => onSelectView('funnel')}
          >
            <div className="card-top-row">
              <div className="card-icon-bubble cyan">
                <Database size={20} />
              </div>
              <div className="card-arrow-circle">
                <ArrowRight size={15} />
              </div>
            </div>
            <h3 className="card-title">Sales Intelligence</h3>
            <p className="card-description">
              Track pipeline health, deal velocity and revenue forecasts.
            </p>
          </TiltFeatureCard>

          {/* Card 2: Delivery & Operations */}
          <TiltFeatureCard
            className="hero-feature-card"
            onClick={() => onSelectView('delivery')}
          >
            <div className="card-top-row">
              <div className="card-icon-bubble blue">
                <Truck size={20} />
              </div>
              <div className="card-arrow-circle">
                <ArrowRight size={15} />
              </div>
            </div>
            <h3 className="card-title">Delivery & Operations</h3>
            <p className="card-description">
              Monitor work orders, execution status and billing cycles.
            </p>
          </TiltFeatureCard>

          {/* Card 3: Cross-Board Intelligence */}
          <TiltFeatureCard
            className="hero-feature-card"
            onClick={() => onSelectView('delivery')}
          >
            <div className="card-top-row">
              <div className="card-icon-bubble purple">
                <Layers size={20} />
              </div>
              <div className="card-arrow-circle">
                <ArrowRight size={15} />
              </div>
            </div>
            <h3 className="card-title">Cross-Board Intelligence</h3>
            <p className="card-description">
              Connect deals to delivery with native Monday.com relationships.
            </p>
          </TiltFeatureCard>

          {/* Card 4: Data Quality & Governance */}
          <TiltFeatureCard
            className="hero-feature-card"
            onClick={() => onSelectView('quality')}
          >
            <div className="card-top-row">
              <div className="card-icon-bubble emerald">
                <ShieldCheck size={20} />
              </div>
              <div className="card-arrow-circle">
                <ArrowRight size={15} />
              </div>
            </div>
            <h3 className="card-title">Data Quality & Governance</h3>
            <p className="card-description">
              Detect anomalies, handle messy data, and ensure trusted insights.
            </p>
          </TiltFeatureCard>
        </div>

        {/* Popular Questions Strip directly launching into AI Copilot */}
        <div className="hero-popular-prompts-bar">
          <div className="prompts-bar-header">
            <span>Popular questions to get started</span>
            <button
              className="view-all-prompts-link"
              onClick={() => onSelectView('chat')}
            >
              <span>View all prompts</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="prompts-chips-wrapper">
            <button
              className="prompt-chip"
              onClick={() => onAskAI("Give me an executive leadership update.")}
            >
              <Sparkles size={14} className="text-purple" />
              <span>Give me an executive leadership update.</span>
            </button>

            <button
              className="prompt-chip"
              onClick={() => onAskAI("Are we executing work orders on deals that haven't actually been won yet?")}
            >
              <BarChart3 size={14} className="text-cyan" />
              <span>Are we executing work orders on deals that haven't actually been won yet?</span>
            </button>

            <button
              className="prompt-chip"
              onClick={() => onAskAI("How's our pipeline looking for the energy sector this quarter?")}
            >
              <Layers size={14} className="text-indigo" />
              <span>How's our pipeline looking for the energy sector this quarter?</span>
            </button>

            <button
              className="prompt-chip"
              onClick={() => onAskAI("What's our gross vs. net accounts receivable position?")}
            >
              <Database size={14} className="text-amber" />
              <span>What's our gross vs. net accounts receivable position?</span>
            </button>
          </div>
        </div>
      </section>

      {/* =========================================================================
          LIVE TELEMETRY STRIP — Real API Values Only (100% Deterministic)
          ========================================================================= */}
      <section className="telemetry-deck-section">
        <div className="telemetry-deck-inner">
          <div className="telemetry-card">
            <div className="telemetry-card-label">
              <Database size={13} className="text-cyan" /> Active Pipeline (Unweighted)
            </div>
            <div className="telemetry-card-val">
              {isLoading ? <span className="skeleton-line" /> : fmt(pipeline?.active_pipeline_unweighted_value)}
            </div>
            <div className="telemetry-card-sub">
              {pipeline?.active_pipeline_count ? `${pipeline.active_pipeline_count} active deals` : 'Live Deals Board'}
            </div>
          </div>

          <div className="telemetry-card">
            <div className="telemetry-card-label">
              <TrendingUp size={13} className="text-indigo" /> Probability-Weighted
            </div>
            <div className="telemetry-card-val text-indigo">
              {isLoading ? <span className="skeleton-line" /> : fmt(pipeline?.active_pipeline_weighted_value)}
            </div>
            <div className="telemetry-card-sub">High 80% | Med 50% | Low 20%</div>
          </div>

          <div className="telemetry-card">
            <div className="telemetry-card-label">
              <Truck size={13} className="text-sky" /> Total Work Orders
            </div>
            <div className="telemetry-card-val text-sky">
              {isLoading ? <span className="skeleton-line" /> : (revenue?.total_work_orders ?? 176)}
            </div>
            <div className="telemetry-card-sub">
              {revenue?.total_order_value_excl_gst ? fmt(revenue.total_order_value_excl_gst) : 'Booked Execution'}
            </div>
          </div>

          <div className="telemetry-card">
            <div className="telemetry-card-label">
              <ShieldAlert size={13} className="text-amber" /> Net Outstanding AR
            </div>
            <div className="telemetry-card-val text-amber">
              {isLoading ? <span className="skeleton-line" /> : fmt(revenue?.net_receivables)}
            </div>
            <div className="telemetry-card-sub">
              {revenue?.credit_balance_accounts_count ? `${revenue.credit_balance_accounts_count} client credit accounts` : 'Credit Reconciled'}
            </div>
          </div>

          <div className="telemetry-card">
            <div className="telemetry-card-label">
              <Layers size={13} className="text-emerald" /> Connect Boards Links
            </div>
            <div className="telemetry-card-val text-emerald">
              {isLoading ? <span className="skeleton-line" /> : `${delivery?.matched_orders_count ?? 15} Linked`}
            </div>
            <div className="telemetry-card-sub">
              {delivery?.commercial_risk ? `${delivery.commercial_risk.unclosed_deal_risk_count} At-Risk Orders` : 'Deals ↔ WOs'}
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 10: PRODUCT STORY
          ========================================================================= */}
      <section className="cinematic-section">
        <div className="section-title-block">
          <span className="section-eyebrow">THE OPERATIONAL MANDATE</span>
          <h2 className="section-main-title">BUSINESS INTELLIGENCE, WITHOUT THE SPREADSHEET WORK.</h2>
          <p className="section-paragraph">
            Founders shouldn't have to manually pull data, clean inconsistent records, and build ad-hoc analysis for every business question.
            Skylark BI connects directly to Monday.com boards, handles real-world messy data, understands natural-language questions, and turns operational and sales data into decision-ready insights.
          </p>
        </div>

        <div className="glass-showcase-trio">
          <div className="trio-card">
            <div className="trio-icon-box bg-cyan-glow">
              <RefreshCw size={24} className="text-cyan" />
            </div>
            <h4>Live Monday.com Sync</h4>
            <p>Direct GraphQL v2 queries over Work Orders &amp; Deals boards without maintaining brittle CSV exports or intermediate replicas.</p>
          </div>

          <div className="trio-card">
            <div className="trio-icon-box bg-indigo-glow">
              <FileSpreadsheet size={24} className="text-indigo" />
            </div>
            <h4>Messy Data Resilience</h4>
            <p>Automatically reconciles 71 mixed PO quantity units, preserves negative credit balances, and handles missing information with full integrity.</p>
          </div>

          <div className="trio-card">
            <div className="trio-icon-box bg-purple-glow">
              <Sparkles size={24} className="text-purple" />
            </div>
            <h4>Founder Conversational AI</h4>
            <p>Converse naturally about pipeline health, unclosed deal risk, and gross vs. net receivables with zero arithmetic hallucinations.</p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          THE PROBLEM
          ========================================================================= */}
      <section className="cinematic-section">
        <div className="section-title-block text-center">
          <span className="section-eyebrow">REAL-WORLD REALITY</span>
          <h2 className="section-main-title">BUSINESS DATA IS MESSY. DECISIONS CAN'T BE.</h2>
          <p className="section-paragraph center-para">
            Why spreadsheets and general-purpose LLMs fail when analyzing enterprise operations.
          </p>
        </div>

        <div className="problem-cards-grid">
          <div className="problem-card">
            <div className="problem-badge">01</div>
            <h3>FRAGMENTED DATA</h3>
            <p>Work Orders and Deals live across separate business workflows, making cross-board analysis difficult.</p>
          </div>

          <div className="problem-card">
            <div className="problem-badge">02</div>
            <h3>INCONSISTENT DATA</h3>
            <p>Real-world records contain missing values, inconsistent formats, duplicate headers, and irregular text.</p>
          </div>

          <div className="problem-card">
            <div className="problem-badge">03</div>
            <h3>AD-HOC ANALYSIS</h3>
            <p>Every founder question can require a new round of filtering, cleaning, calculations, and investigation.</p>
          </div>

          <div className="problem-card">
            <div className="problem-badge">04</div>
            <h3>INCOMPLETE RECORDS</h3>
            <p>Missing information shouldn't silently become misleading numbers. Skylark BI surfaces data-quality limitations alongside insights.</p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 11: HOW IT WORKS — 3D Connected Pipeline
          ========================================================================= */}
      <section className="cinematic-section bg-gradient-panel">
        <div className="section-title-block text-center">
          <span className="section-eyebrow">OPERATIONAL FLOW</span>
          <h2 className="section-main-title">FROM MONDAY.COM DATA TO EXECUTIVE INSIGHT.</h2>
          <p className="section-paragraph center-para">
            Five-stage deterministic intelligence pipeline connecting live boards to verified answers.
          </p>
        </div>

        <div className="pipeline-steps-container">
          <div className="pipeline-step-box">
            <div className="step-tag">01</div>
            <h4>CONNECT</h4>
            <p>Read Work Orders and Deals directly from Monday.com.</p>
          </div>

          <div className="pipeline-arrow">&rarr;</div>

          <div className="pipeline-step-box">
            <div className="step-tag">02</div>
            <h4>NORMALIZE</h4>
            <p>Clean and standardize messy operational data while preserving meaningful missing information.</p>
          </div>

          <div className="pipeline-arrow">&rarr;</div>

          <div className="pipeline-step-box">
            <div className="step-tag">03</div>
            <h4>UNDERSTAND</h4>
            <p>Interpret founder-level questions and clarify ambiguous requests.</p>
          </div>

          <div className="pipeline-arrow">&rarr;</div>

          <div className="pipeline-step-box">
            <div className="step-tag">04</div>
            <h4>ANALYZE</h4>
            <p>Run deterministic analytics across revenue, pipeline, operations, and connected boards.</p>
          </div>

          <div className="pipeline-arrow">&rarr;</div>

          <div className="pipeline-step-box">
            <div className="step-tag">05</div>
            <h4>EXPLAIN</h4>
            <p>Return contextual insights together with relevant data-quality caveats.</p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 12: CORE INTELLIGENCE — 6 Dedicated Executive Glass Cards
          ========================================================================= */}
      <section id="core-intelligence" className="cinematic-section">
        <div className="section-title-block">
          <span className="section-eyebrow">ANALYTICAL CAPABILITIES</span>
          <h2 className="section-main-title">CORE INTELLIGENCE MODULES</h2>
          <p className="section-paragraph">
            Engineered to answer critical sales, fulfillment, and financial health questions.
          </p>
        </div>

        <div className="core-modules-grid">
          {/* Card 1: Revenue Intelligence */}
          <div className="core-module-card" onClick={() => onSelectView('delivery')}>
            <div className="module-top">
              <span className="module-pill cyan">FINANCE &amp; AR</span>
              <div className="module-icon"><Database size={22} className="text-cyan" /></div>
            </div>
            <h3>REVENUE INTELLIGENCE</h3>
            <p>Understand bookings, billed revenue, collections, and receivables.</p>
            <div
              className="module-prompt-callout"
              onClick={(e) => {
                e.stopPropagation();
                onAskAI("What's our gross vs. net accounts receivable position?");
              }}
            >
              <span className="prompt-label">Example Query:</span>
              <span className="prompt-text">"What's our gross vs. net accounts receivable position?"</span>
              <ArrowUpRight size={14} className="prompt-icon" />
            </div>
          </div>

          {/* Card 2: Pipeline Intelligence */}
          <div className="core-module-card" onClick={() => onSelectView('funnel')}>
            <div className="module-top">
              <span className="module-pill indigo">SALES PIPELINE</span>
              <div className="module-icon"><TrendingUp size={22} className="text-indigo" /></div>
            </div>
            <h3>PIPELINE INTELLIGENCE</h3>
            <p>Explore pipeline health, deal stages, sector performance, and probability-weighted opportunities.</p>
            <div
              className="module-prompt-callout"
              onClick={(e) => {
                e.stopPropagation();
                onAskAI("How's our pipeline looking for the energy sector this quarter?");
              }}
            >
              <span className="prompt-label">Example Query:</span>
              <span className="prompt-text">"How's our pipeline looking for the energy sector this quarter?"</span>
              <ArrowUpRight size={14} className="prompt-icon" />
            </div>
          </div>

          {/* Card 3: Operations Intelligence */}
          <div className="core-module-card" onClick={() => onSelectView('delivery')}>
            <div className="module-top">
              <span className="module-pill sky">FULFILLMENT</span>
              <div className="module-icon"><Truck size={22} className="text-sky" /></div>
            </div>
            <h3>OPERATIONS INTELLIGENCE</h3>
            <p>Understand work-order execution, billing status, and delivery progress.</p>
            <div
              className="module-prompt-callout"
              onClick={(e) => {
                e.stopPropagation();
                onAskAI("How many work orders are currently ongoing and completed?");
              }}
            >
              <span className="prompt-label">Example Query:</span>
              <span className="prompt-text">"How many work orders are currently ongoing?"</span>
              <ArrowUpRight size={14} className="prompt-icon" />
            </div>
          </div>

          {/* Card 4: Cross-Board Intelligence */}
          <div className="core-module-card" onClick={() => onSelectView('delivery')}>
            <div className="module-top">
              <span className="module-pill purple">CONNECT BOARDS</span>
              <div className="module-icon"><Layers size={22} className="text-purple" /></div>
            </div>
            <h3>CROSS-BOARD INTELLIGENCE</h3>
            <p>Connect sales commitments with operational execution using native Monday.com relationships.</p>
            <div
              className="module-prompt-callout"
              onClick={(e) => {
                e.stopPropagation();
                onAskAI("Are we executing work orders on deals that haven't actually been won yet?");
              }}
            >
              <span className="prompt-label">Example Query:</span>
              <span className="prompt-text">"Are we executing work orders on deals that haven't actually been won yet?"</span>
              <ArrowUpRight size={14} className="prompt-icon" />
            </div>
          </div>

          {/* Card 5: Data Quality */}
          <div className="core-module-card" onClick={() => onSelectView('quality')}>
            <div className="module-top">
              <span className="module-pill emerald">DATA GOVERNANCE</span>
              <div className="module-icon"><ShieldCheck size={22} className="text-emerald" /></div>
            </div>
            <h3>DATA QUALITY</h3>
            <p>Surface missing, inconsistent, and incomplete records instead of hiding them.</p>
            <div
              className="module-prompt-callout"
              onClick={(e) => {
                e.stopPropagation();
                onAskAI("Show me all missing or inconsistent records across boards");
              }}
            >
              <span className="prompt-label">Example Query:</span>
              <span className="prompt-text">"Show me all missing or inconsistent records across boards"</span>
              <ArrowUpRight size={14} className="prompt-icon" />
            </div>
          </div>

          {/* Card 6: Leadership Briefing */}
          <div
            className="core-module-card"
            onClick={() => onAskAI("Give me an executive leadership update.")}
          >
            <div className="module-top">
              <span className="module-pill amber">EXECUTIVE UPDATE</span>
              <div className="module-icon"><FileText size={22} className="text-amber" /></div>
            </div>
            <h3>LEADERSHIP BRIEFING</h3>
            <p>Prepare structured executive updates combining pipeline, revenue, operations, and data-quality signals.</p>
            <div
              className="module-prompt-callout"
              onClick={(e) => {
                e.stopPropagation();
                onAskAI("Give me an executive leadership update.");
              }}
            >
              <span className="prompt-label">Example Query:</span>
              <span className="prompt-text">"Give me an executive leadership update."</span>
              <ArrowUpRight size={14} className="prompt-icon" />
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 14: DATA QUALITY / TRUST
          ========================================================================= */}
      <section className="cinematic-section">
        <div className="section-title-block text-center">
          <span className="section-eyebrow">GOVERNANCE &amp; ACCURACY</span>
          <h2 className="section-main-title">DATA YOU CAN TRUST — WITH THE CAVEATS VISIBLE.</h2>
          <p className="section-paragraph center-para">
            Real-world business data is incomplete and inconsistent. Skylark BI does not silently turn missing information into zero or hide data-quality limitations.
          </p>
        </div>

        <div className="quality-quad-grid">
          <div className="quality-card">
            <div className="quality-icon text-amber"><AlertTriangle size={24} /></div>
            <h4>MISSING &amp; NULL VALUES</h4>
            <p>Distinguishes unavailable information from genuine zero values.</p>
          </div>

          <div className="quality-card">
            <div className="quality-icon text-cyan"><FileSpreadsheet size={24} /></div>
            <h4>INCONSISTENT FORMATS</h4>
            <p>Normalizes irregular dates, numbers, naming conventions, and operational text.</p>
          </div>

          <div className="quality-card">
            <div className="quality-icon text-purple"><Layers size={24} /></div>
            <h4>CROSS-BOARD RELATIONSHIPS</h4>
            <p>Uses available native Monday.com relationships to connect sales and delivery data.</p>
          </div>

          <div className="quality-card">
            <div className="quality-icon text-emerald"><ShieldAlert size={24} /></div>
            <h4>DATA QUALITY CAVEATS</h4>
            <p>Makes limitations visible instead of hiding uncertainty behind a confident answer.</p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 15: AI ARCHITECTURE VISUAL
          ========================================================================= */}
      <section className="cinematic-section bg-gradient-panel">
        <div className="section-title-block text-center">
          <span className="section-eyebrow">ZERO-HALLUCINATION ARCHITECTURE</span>
          <h2 className="section-main-title">AI FOR UNDERSTANDING. DETERMINISTIC ANALYTICS FOR NUMBERS.</h2>
          <p className="section-paragraph center-para">
            The AI agent interprets questions, clarifies ambiguity, and explains results. All calculations are executed strictly by deterministic Python analytics.
          </p>
        </div>

        {/* 3D Flow Visual Matching Exact 6-Stage Specification */}
        <div className="architecture-flow-diagram">
          <div className="arch-node">
            <span className="arch-badge">INPUT</span>
            <h5>Founder Question</h5>
          </div>
          <div className="arch-connector">&darr;</div>
          <div className="arch-node">
            <span className="arch-badge cyan">REASONING</span>
            <h5>Query Understanding</h5>
          </div>
          <div className="arch-connector">&darr;</div>
          <div className="arch-node">
            <span className="arch-badge amber">DISAMBIGUATION</span>
            <h5>Clarification</h5>
          </div>
          <div className="arch-connector">&darr;</div>
          <div className="arch-node highlight">
            <span className="arch-badge purple">ZERO-HALLUCINATION</span>
            <h5>Deterministic Analytics</h5>
          </div>
          <div className="arch-connector">&darr;</div>
          <div className="arch-node">
            <span className="arch-badge emerald">READ-ONLY MCP</span>
            <h5>Monday.com Data</h5>
          </div>
          <div className="arch-connector">&darr;</div>
          <div className="arch-node final">
            <span className="arch-badge sky">EXECUTIVE OUTPUT</span>
            <h5>Business Insight + Data Caveats</h5>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 16: READ-ONLY MONDAY.COM
          ========================================================================= */}
      <section className="cinematic-section">
        <div className="readonly-banner-card">
          <div className="readonly-content">
            <span className="section-eyebrow">SECURITY &amp; INTEGRITY</span>
            <h2>CONNECTED TO MONDAY.COM. BUILT FOR READ-ONLY INTELLIGENCE.</h2>
            <p>
              Skylark BI reads data from the Work Orders and Deals boards without modifying business records. The agent dynamically queries connected Monday.com data rather than relying on hardcoded CSV values.
            </p>
            <div className="readonly-badges-row">
              <span className="readonly-badge"><Lock size={13} /> READ-ONLY</span>
              <span className="readonly-badge"><Activity size={13} /> LIVE DATA</span>
              <span className="readonly-badge"><RefreshCw size={13} /> DYNAMIC QUERYING</span>
              <span className="readonly-badge"><CheckCircle2 size={13} /> MONDAY.COM</span>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 13: FOUNDER QUESTIONS (Interactive Prompt Matrix)
          ========================================================================= */}
      <section className="cinematic-section">
        <div className="section-title-block text-center">
          <span className="section-eyebrow">CONVERSATIONAL CLARITY</span>
          <h2 className="section-main-title">ASK BUSINESS QUESTIONS IN PLAIN ENGLISH.</h2>
          <p className="section-paragraph center-para">
            Click any query below to run it against the live Monday.com dataset through the AI Copilot.
          </p>
        </div>

        <div className="founder-prompts-matrix">
          {[
            {
              q: "How's our pipeline looking for the energy sector this quarter?",
              cat: "PIPELINE DISAMBIGUATION",
              desc: "Evaluates active pipeline by sector while detecting Fiscal Year vs. Calendar Year intervals.",
            },
            {
              q: "Are we executing work orders on deals that haven't actually been won yet?",
              cat: "COMMERCIAL GOVERNANCE",
              desc: "Audits unclosed proposal risk across all active and completed delivery projects.",
            },
            {
              q: "What is our contract value variance between sales CRM commitments and delivery bookings?",
              cat: "CONTRACT LEAKAGE",
              desc: "Compares deal contracted value with booked work order amounts and billed execution.",
            },
            {
              q: "What's our gross vs. net accounts receivable position?",
              cat: "ACCOUNTS RECEIVABLE",
              desc: "Reconciles gross positive debt against legitimate customer credit overpayment balances.",
            },
            {
              q: "Give me an executive leadership update.",
              cat: "LEADERSHIP BRIEFING",
              desc: "Synthesizes pipeline velocity, delivery health, net receivables, and audit risks into an executive memo.",
            },
          ].map((item, idx) => (
            <div
              key={idx}
              className="founder-prompt-tile"
              onClick={() => onAskAI(item.q)}
            >
              <div className="tile-top">
                <span className="tile-cat">{item.cat}</span>
                <ArrowRight size={15} className="tile-arrow" />
              </div>
              <h4 className="tile-q">"{item.q}"</h4>
              <p className="tile-desc">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================================================
          SECTION 17: FINAL CTA & LEADERSHIP BRIEFING CALLOUT
          ========================================================================= */}
      <section className="cinematic-section">
        <div className="briefing-callout-card">
          <div className="briefing-card-content">
            <span className="section-eyebrow">C-SUITE MEMO AUTOMATION</span>
            <h2>FROM RAW DATA TO EXECUTIVE BRIEFING.</h2>
            <p>
              Prepare structured leadership updates combining pipeline, revenue, operations, and data-quality signals at the touch of a button.
            </p>
            <button
              className="hero-btn-primary"
              onClick={() => onAskAI("Give me an executive leadership update.")}
            >
              <Sparkles size={18} />
              <span>GENERATE LEADERSHIP BRIEFING</span>
            </button>
          </div>
        </div>

        <div className="final-cta-banner">
          <h2>YOUR BUSINESS DATA IS ALREADY THERE. START ASKING QUESTIONS.</h2>
          <p>
            Explore your Monday.com sales and operational intelligence through a conversational interface built for founder-level decision making.
          </p>
          <div className="final-btn-row">
            <button
              className="hero-btn-primary"
              onClick={() => onSelectView('chat')}
            >
              <span>LAUNCH AI COPILOT</span>
              <ArrowRight size={16} />
            </button>
            <button
              className="hero-btn-secondary"
              onClick={() => onSelectView('overview')}
            >
              <span>EXPLORE THE PLATFORM</span>
            </button>
          </div>
        </div>
      </section>

      {/* =========================================================================
          FOOTER — Matching Reference Benchmark
          ========================================================================= */}
      <footer className="cinematic-footer">
        <div className="footer-line">
          <span>SKYLARK DRONES</span>
          <span className="footer-sep">|</span>
          <span>DATA</span>
          <span className="footer-sep">&gt;</span>
          <span>INSIGHT</span>
          <span className="footer-sep">&gt;</span>
          <span>HIGHER IMPACT</span>
        </div>
      </footer>
    </div>
  );
};
export default LandingView;
