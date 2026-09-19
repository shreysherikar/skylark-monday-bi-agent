import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { TopNav } from './components/TopNav';
import { CommandPalette } from './components/CommandPalette';
import { LandingView } from './views/LandingView';
import { ChatView } from './views/ChatView';
import { OverviewView } from './views/OverviewView';
import { FunnelView } from './views/FunnelView';
import { DeliveryView } from './views/DeliveryView';
import { QualityView } from './views/QualityView';
import { ActiveView, ChatMessageItem } from './types';
import { sendChatMessage } from './api';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<ActiveView>('home');
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState<boolean>(false);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    // Ensure we are on chat view when sending a message
    setActiveView('chat');

    const userMsg: ChatMessageItem = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      const history = newMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const result = await sendChatMessage(text, history.slice(0, -1));

      const assistantMsg: ChatMessageItem = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: result.response,
        timestamp: new Date().toISOString(),
        tools_used: result.tools_used,
        caveats: result.caveats,
        needs_clarification: result.needs_clarification,
        suggested_options: result.suggested_options,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessageItem = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ **Error communicating with BI Agent**: ${err.message || 'Unknown network error'}. Please ensure the backend server is running.`,
        timestamp: new Date().toISOString(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOptionClick = (optionText: string) => {
    handleSendMessage(optionText);
  };

  const handleTriggerLeadershipBriefing = () => {
    handleSendMessage("Give me this week's leadership update");
  };

  const handleRefreshData = async () => {
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="enterprise-app">
      {/* Collapsible Enterprise Sidebar */}
      <Sidebar
        activeView={activeView}
        onSelectView={setActiveView}
        isOpenMobile={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        onTriggerLeadershipBriefing={handleTriggerLeadershipBriefing}
      />

      {/* Main App Canvas */}
      <div className="main-canvas">
        <TopNav
          activeView={activeView}
          onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          onRefreshData={handleRefreshData}
          onLaunchCopilot={() => setActiveView('chat')}
        />

        <div className={`view-content-area ${activeView === 'chat' ? 'chat-mode' : 'scrollable-mode'}`} key={refreshKey}>
          {activeView === 'home' && (
            <LandingView
              onSelectView={setActiveView}
              onAskAI={handleSendMessage}
            />
          )}

          {activeView === 'chat' && (
            <ChatView
              messages={messages}
              isLoading={isLoading}
              onSendMessage={handleSendMessage}
              onOptionClick={handleOptionClick}
            />
          )}

          {activeView === 'overview' && (
            <OverviewView onAskAI={handleSendMessage} />
          )}

          {activeView === 'funnel' && (
            <FunnelView onAskAI={handleSendMessage} />
          )}

          {activeView === 'delivery' && (
            <DeliveryView onAskAI={handleSendMessage} />
          )}

          {activeView === 'quality' && (
            <QualityView onAskAI={handleSendMessage} />
          )}
        </div>
      </div>

      {/* Global Command Palette (⌘K / Ctrl+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectView={setActiveView}
        onRunPrompt={handleSendMessage}
      />
    </div>
  );
};

export default App;
