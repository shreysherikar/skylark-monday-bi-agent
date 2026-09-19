import React, { useState, useEffect, useRef } from 'react';
import { Search, Sparkles, LayoutDashboard } from 'lucide-react';
import { ActiveView, CommandItem } from '../types';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectView: (view: ActiveView) => void;
  onRunPrompt: (prompt: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectView,
  onRunPrompt,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    {
      id: 'nav-chat',
      title: 'Go to AI Copilot Chat',
      category: 'Navigation',
      action: () => onSelectView('chat'),
    },
    {
      id: 'nav-overview',
      title: 'Go to Executive Overview KPIs',
      category: 'Navigation',
      action: () => onSelectView('overview'),
    },
    {
      id: 'nav-funnel',
      title: 'Go to Deal Funnel Pipeline',
      category: 'Navigation',
      action: () => onSelectView('funnel'),
    },
    {
      id: 'nav-delivery',
      title: 'Go to Work Orders & Delivery',
      category: 'Navigation',
      action: () => onSelectView('delivery'),
    },
    {
      id: 'nav-quality',
      title: 'Go to Data Quality Audit Inspector',
      category: 'Navigation',
      action: () => onSelectView('quality'),
    },
    {
      id: 'query-leadership',
      title: "Query: Give me this week's leadership update",
      category: 'Executive Query',
      action: () => {
        onSelectView('chat');
        onRunPrompt("Give me this week's leadership update");
      },
    },
    {
      id: 'query-renewables',
      title: 'Query: How is the deal pipeline looking in Renewables?',
      category: 'Executive Query',
      action: () => {
        onSelectView('chat');
        onRunPrompt('How is the deal pipeline looking in Renewables?');
      },
    },
    {
      id: 'query-receivables',
      title: 'Query: What are our total outstanding receivables and credit balances?',
      category: 'Executive Query',
      action: () => {
        onSelectView('chat');
        onRunPrompt('What are our total outstanding receivables and credit balances?');
      },
    },
    {
      id: 'query-delivery',
      title: 'Query: Compare delivery fulfillment vs tracked deal pipeline',
      category: 'Executive Query',
      action: () => {
        onSelectView('chat');
        onRunPrompt('Compare delivery fulfillment vs tracked deal pipeline');
      },
    },
  ];

  const filtered = commands.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase()) ||
    c.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // Open
          inputRef.current?.focus();
        }
      }
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [isOpen, onClose]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action();
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="cmd-modal-backdrop" onClick={onClose}>
      <div className="cmd-modal-box" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', padding: '0 16px', gap: 10 }}>
          <Search size={18} color="var(--text-muted)" />
          <input
            ref={inputRef}
            type="text"
            className="cmd-search-input"
            placeholder="Type a command or executive query..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
          />
          <kbd className="kbd-shortcut" style={{ fontSize: '0.7rem' }}>ESC</kbd>
        </div>

        <div className="cmd-list">
          {filtered.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No commands found matching "{query}"
            </div>
          ) : (
            filtered.map((item, idx) => (
              <div
                key={item.id}
                className={`cmd-item ${idx === selectedIndex ? 'selected' : ''}`}
                onClick={() => {
                  item.action();
                  onClose();
                }}
                onMouseEnter={() => setSelectedIndex(idx)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {item.category === 'Navigation' ? (
                    <LayoutDashboard size={16} color="var(--sky-400)" />
                  ) : (
                    <Sparkles size={16} color="var(--amber-400)" />
                  )}
                  <span>{item.title}</span>
                </div>
                <span className="cmd-category-tag">{item.category}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
