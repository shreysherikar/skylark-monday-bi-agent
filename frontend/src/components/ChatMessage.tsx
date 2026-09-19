import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertTriangle, Wrench, User, Bot, HelpCircle, Copy, Check } from 'lucide-react';
import { ChatMessageItem } from '../types';

interface ChatMessageProps {
  message: ChatMessageItem;
  onOptionClick?: (optionText: string) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onOptionClick }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
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
            title={copied ? "Copied!" : "Copy message"}
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

        {/* Message Content with Markdown rendering */}
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Data Quality Caveat Banners */}
        {!isUser && message.caveats && message.caveats.length > 0 && (
          <div className="caveat-banner">
            <div className="caveat-banner-header">
              <AlertTriangle size={15} />
              <span>Data Quality Caveats & Integrity Flags</span>
            </div>
            {message.caveats.map((c, idx) => (
              <div key={idx} className="caveat-bullet">
                {c}
              </div>
            ))}
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
