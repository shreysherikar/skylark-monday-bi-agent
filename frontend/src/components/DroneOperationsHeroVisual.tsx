import React from 'react';
import { ThreeDroneOperationsScene } from './ThreeDroneOperationsScene';

interface DroneOperationsHeroVisualProps {
  activeOperationsCount?: number;
}

export const DroneOperationsHeroVisual: React.FC<DroneOperationsHeroVisualProps> = ({
  activeOperationsCount = 127,
}) => {
  return (
    <div className="drone-hero-visual-viewport">
      {/* 1. Real 3D Physical UAV Quadcopter & Earth Operations WebGL Scene */}
      <ThreeDroneOperationsScene />

      {/* 2. Top-Right Real-Time Operations HUD Badge (From Benchmark Reference) */}
      <div className="hud-operations-card">
        <div className="hud-card-header">
          <span className="hud-card-label">REAL-TIME OPERATIONS</span>
          <div className="hud-bars">
            <span className="hud-bar bar-1" />
            <span className="hud-bar bar-2" />
            <span className="hud-bar bar-3" />
            <span className="hud-bar bar-4" />
          </div>
        </div>
        <div className="hud-card-pipeline">
          <span className="hud-step">FLY</span>
          <span className="hud-chevron">&gt;</span>
          <span className="hud-step">COLLECT</span>
          <span className="hud-chevron">&gt;</span>
          <span className="hud-step active">ANALYSE</span>
          <span className="hud-chevron">&gt;</span>
          <span className="hud-step">GROW</span>
        </div>
      </div>

      {/* 3. Floating Active Operations Telemetry Pill (From Benchmark Reference) */}
      <div className="hud-stat-pill">
        <div className="hud-stat-val">{activeOperationsCount}</div>
        <div className="hud-stat-meta">
          <div className="hud-stat-bars">
            <span className="hud-stat-bar" />
            <span className="hud-stat-bar" />
            <span className="hud-stat-bar" />
          </div>
          <span>Active Operations</span>
        </div>
      </div>

      {/* 4. Mumbai, India Location Sync Card (From Benchmark Reference) */}
      <div className="hud-location-pin-card">
        <div className="location-pin-glow" />
        <div className="location-pin-content">
          <div className="location-pin-title">Mumbai, India</div>
          <div className="location-pin-sub">
            <span>Live Data Sync</span>
            <span className="location-live-dot" />
          </div>
        </div>
      </div>
    </div>
  );
};
