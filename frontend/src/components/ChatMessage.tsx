import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  AlertTriangle,
  Wrench,
  User,
  Bot,
  HelpCircle,
  Copy,
  Check,
  Sparkles,
  ShieldCheck,
  ChevronRight,
} from 'lucide-react';
import { ChatMessageItem } from '../types';

interface ChatMessageProps {
  message: ChatMessageItem;
  onOptionClick?: (optionText: string) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onOptionClick }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const structured = message.structured;

  // Deduplicate caveats from both top-level caveats and structured.caveats
  const allCaveats = Array.from(
    new Set([...(message.caveats || []), ...(structured?.caveats || [])])
  );

  const followUps = structured?.follow_ups || structured?.follow_up || [];

  const handleCopy = () => {
    const textToCopy = structured?.summary
      ? `${structured.summary}\n\n${message.content}`
      : message.content;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`message-container ${message.role}`}>
      <div className={`msg-avatar ${message.role}`}>
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      <div className={`msg-body ${message.role}`} style={{ position: 'relative' }}>
        {!isUser && (
          <button
            onClick={handleCopy}
            title={copied ? 'Copied!' : 'Copy message'}
            style={{
              position: 'absolute',
              top: 10,
              right: 12,
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 6,
              color: copied ? 'var(--emerald-400)' : 'var(--text-muted)',
              padding: '4px 7px',
              fontSize: '0.72rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              transition: 'all 0.2s ease',
              zIndex: 2,
            }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        )}

        {/* Tool Execution Chips */}
        {!isUser && message.tools_used && message.tools_used.length > 0 && (
          <div className="tool-chips-row">
            {message.tools_used.map((tool, idx) => (
              <span key={idx} className="tool-badge" title="Executed deterministic MCP analytics tool">
                <Wrench size={11} />
                {tool}
              </span>
            ))}
          </div>
        )}

        {/* Structured Executive Summary */}
        {!isUser && structured?.summary && (
          <div
            style={{
              background: 'rgba(56, 189, 248, 0.06)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: 12,
              padding: '14px 18px',
              marginBottom: 16,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.74rem',
                fontWeight: 700,
                color: 'var(--cyan-400)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              <Sparkles size={13} />
              <span>Executive Summary</span>
            </div>
            <div
              style={{
                fontSize: '0.92rem',
                color: '#f1f5f9',
                lineHeight: 1.55,
                fontWeight: 500,
              }}
            >
              {structured.summary}
            </div>
          </div>
        )}

        {/* Structured Key KPI Grid */}
        {!isUser && structured?.kpis && structured.kpis.length > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: 10,
              marginBottom: 16,
            }}
          >
            {structured.kpis.map((kpi, idx) => (
              <div
                key={idx}
                style={{
                  background: 'rgba(10, 20, 42, 0.75)',
                  border: '1px solid rgba(56, 189, 248, 0.18)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  backdropFilter: 'blur(12px)',
                }}
              >
                <div
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  {kpi.label}
                </div>
                <div
                  style={{
                    fontSize: '1.2rem',
                    fontWeight: 800,
                    color: '#ffffff',
                    fontFamily: 'var(--font-mono)',
                    letterSpacing: '-0.02em',
                  }}
                >
                  {kpi.value}
                </div>
                {kpi.context && (
                  <div
                    style={{
                      fontSize: '0.72rem',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.3,
                    }}
                  >
                    {kpi.context}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Structured Risk Alerts */}
        {!isUser && structured?.risks && structured.risks.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              marginBottom: 16,
            }}
          >
            {structured.risks.map((risk, idx) => {
              const isHigh = risk.severity === 'high';
              const isLow = risk.severity === 'low';
              const borderColor = isHigh
                ? 'rgba(244, 63, 94, 0.35)'
                : isLow
                ? 'rgba(56, 189, 248, 0.3)'
                : 'rgba(245, 158, 11, 0.3)';
              const bgColor = isHigh
                ? 'rgba(244, 63, 94, 0.08)'
                : isLow
                ? 'rgba(56, 189, 248, 0.06)'
                : 'rgba(245, 158, 11, 0.08)';
              const tagColor = isHigh
                ? 'var(--rose-400)'
                : isLow
                ? 'var(--cyan-400)'
                : 'var(--amber-400)';

              return (
                <div
                  key={idx}
                  style={{
                    background: bgColor,
                    border: `1px solid ${borderColor}`,
                    borderRadius: 10,
                    padding: '10px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff' }}>
                      {risk.title}
                    </span>
                    <span
                      style={{
                        fontSize: '0.66rem',
                        fontWeight: 800,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        color: tagColor,
                        border: `1px solid ${borderColor}`,
                        borderRadius: 4,
                        padding: '2px 6px',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {risk.severity} Risk
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: '0.78rem',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.4,
                    }}
                  >
                    {risk.detail}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Message Content with Markdown rendering */}
        {message.content && (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Structured Evidence / Provenance Footer */}
        {!isUser && structured?.evidence && (
          <div
            style={{
              marginTop: 14,
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 8,
              padding: '10px 14px',
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontWeight: 700,
                color: 'var(--cyan-400)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              <ShieldCheck size={13} />
              <span>Evidence & Provenance</span>
            </div>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px 16px',
                color: 'var(--text-secondary)',
              }}
            >
              <div>
                <strong style={{ color: 'var(--text-muted)' }}>Sources: </strong>
                {structured.evidence.sources.join(', ')}
              </div>
              <div>
                <strong style={{ color: 'var(--text-muted)' }}>Records Analyzed: </strong>
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  {structured.evidence.records_analyzed}
                </span>
              </div>
              {structured.evidence.data_coverage && (
                <div>
                  <strong style={{ color: 'var(--text-muted)' }}>Coverage: </strong>
                  {structured.evidence.data_coverage}
                </div>
              )}
            </div>
            {structured.evidence.calculation && (
              <div
                style={{
                  fontSize: '0.70rem',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  opacity: 0.85,
                }}
              >
                Calculation: {structured.evidence.calculation}
              </div>
            )}
          </div>
        )}

        {/* Data Quality Caveat Banners */}
        {!isUser && allCaveats.length > 0 && (
          <div className="caveat-banner" style={{ marginTop: 12 }}>
            <div className="caveat-banner-header">
              <AlertTriangle size={15} />
              <span>Data Quality Caveats & Integrity Flags</span>
            </div>
            {allCaveats.map((c, idx) => (
              <div key={idx} className="caveat-bullet">
                {c}
              </div>
            ))}
          </div>
        )}

        {/* Follow-up Interactive Inquiries */}
        {!isUser && followUps.length > 0 && (
          <div
            className="clarify-box"
            style={{
              marginTop: 12,
              background: 'rgba(56, 189, 248, 0.04)',
              borderColor: 'rgba(56, 189, 248, 0.2)',
            }}
          >
            <div
              className="clarify-label"
              style={{
                color: 'var(--cyan-400)',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Sparkles size={13} />
              <span>Suggested Follow-up Inquiries:</span>
            </div>
            <div className="clarify-options-wrap">
              {followUps.map((opt, idx) => (
                <button
                  key={idx}
                  className="clarify-btn"
                  onClick={() => onOptionClick && onOptionClick(opt)}
                  style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                >
                  <span>{opt}</span>
                  <ChevronRight size={12} style={{ opacity: 0.6 }} />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Clarification Interactive Chips */}
        {!isUser && message.needs_clarification && message.suggested_options && message.suggested_options.length > 0 && (
          <div className="clarify-box">
            <div className="clarify-label">
              <HelpCircle size={13} style={{ display: 'inline', marginRight: 5, verticalAlign: 'middle' }} />
              Suggested Disambiguation Options:
            </div>
            <div className="clarify-options-wrap">
              {message.suggested_options.map((opt, idx) => (
                <button
                  key={idx}
                  className="clarify-btn"
                  onClick={() => onOptionClick && onOptionClick(opt)}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
