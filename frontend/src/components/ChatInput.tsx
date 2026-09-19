import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, isLoading }) => {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (text.trim() && !isLoading) {
      onSendMessage(text.trim());
      setText('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [text]);

  return (
    <div>
      <div className="input-dock">
        <textarea
          ref={textareaRef}
          rows={1}
          className="dock-textarea"
          placeholder="Ask a commercial question (e.g. pipeline, receivables, leadership update)..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button
          className="dock-send-btn"
          onClick={handleSend}
          disabled={!text.trim() || isLoading}
          title="Send query (Enter)"
        >
          {isLoading ? <Loader2 size={18} className="pulse-spinner" /> : <Send size={18} />}
        </button>
      </div>
      <div className="dock-hint">
        Press <kbd className="kbd-shortcut">Enter</kbd> to submit, <kbd className="kbd-shortcut">Shift + Enter</kbd> for newline.
      </div>
    </div>
  );
};
