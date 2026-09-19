import React, { useRef, useEffect } from 'react';
import { ChatMessage } from '../components/ChatMessage';
import { QuickPrompts } from '../components/QuickPrompts';
import { ChatInput } from '../components/ChatInput';
import { ChatMessageItem } from '../types';

interface ChatViewProps {
  messages: ChatMessageItem[];
  isLoading: boolean;
  onSendMessage: (message: string) => void;
  onOptionClick: (optionText: string) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  isLoading,
  onSendMessage,
  onOptionClick,
}) => {
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="chat-view-layout">
      <div className="messages-scroll-area">
        {messages.length === 0 ? (
          <QuickPrompts onSelectPrompt={onSendMessage} />
        ) : (
          messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onOptionClick={onOptionClick}
            />
          ))
        )}

        {isLoading && (
          <div className="message-container assistant">
            <div className="msg-avatar assistant">🤖</div>
            <div className="msg-body assistant">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)', fontSize: '0.86rem' }}>
                <div className="pulse-spinner" />
                <span>Executing read-only Monday MCP tools and deterministic calculations...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      <div className="input-dock-wrap">
        <ChatInput onSendMessage={onSendMessage} isLoading={isLoading} />
      </div>
    </div>
  );
};
