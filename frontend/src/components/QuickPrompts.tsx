import React from 'react';
import { ArrowUpRight, Sparkles, TrendingUp, DollarSign, Layers, ShieldAlert } from 'lucide-react';

interface QuickPromptsProps {
  onSelectPrompt: (promptText: string) => void;
}

const STARTER_PROMPTS = [
  {
    icon: Sparkles,
    label: "Give me this week's leadership update",
    category: "Executive Briefing",
  },
  {
    icon: TrendingUp,
    label: "How is the deal pipeline looking in Renewables?",
    category: "Pipeline Health",
  },
  {
    icon: DollarSign,
    label: "What are our total outstanding receivables and credit balances?",
    category: "Financials & AR",
  },
  {
    icon: Layers,
    label: "Are we executing any work orders on deals that haven't been won yet?",
    category: "Commercial Risk",
  },
  {
    icon: Layers,
    label: "Show me any contract value variance between sales CRM commitments and work orders",
    category: "Scope Leakage",
  },
  {
    icon: ShieldAlert,
    label: "Inspect data quality health and severe null rates",
    category: "Governance Audit",
  },
];

export const QuickPrompts: React.FC<QuickPromptsProps> = ({ onSelectPrompt }) => {
  return (
    <div className="welcome-hero">
      <div className="hero-pill">
        <Sparkles size={13} />
        Executive Business Intelligence
      </div>
      <h2 className="hero-heading">Skylark Commercial Intelligence</h2>
      <p className="hero-subheading">
        Ask natural language questions across live Monday.com Work Orders & Deals.
        Every calculation is deterministic; all data quality limitations are transparently surfaced.
      </p>

      <div className="prompts-deck">
        {STARTER_PROMPTS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="deck-card"
              onClick={() => onSelectPrompt(item.label)}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{
                  padding: 8,
                  borderRadius: 8,
                  background: 'rgba(14, 165, 233, 0.1)',
                  color: 'var(--sky-400)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: 2
                }}>
                  <Icon size={16} />
                </div>
                <div>
                  <div className="deck-card-tag">{item.category}</div>
                  <div className="deck-card-prompt">{item.label}</div>
                </div>
              </div>
              <ArrowUpRight size={16} color="var(--text-muted)" style={{ flexShrink: 0 }} />
            </div>
          );
        })}
      </div>
    </div>
  );
};
