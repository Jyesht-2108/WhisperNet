// ============================================================
// WhisperNet — Interactive Floating Overlay Widget
// ============================================================
// 4-State Machine:
//   idle       → Extension loaded, waiting for activation
//   listening  → Tab audio capture active, STT streaming
//   interrupted → Pocket FM paused, user mic active
//   speaking   → AI response playing, Pocket FM still paused
//
// Now integrates Member 4's Voice Pipeline:
//   • Rolling STT buffer (passive transcription)
//   • OpenAI Realtime WebRTC (active voice interaction)
//   • Auto-resume on response.done
// ============================================================

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { MessageActions, type WidgetState, type ExtensionMessage, type VoicePipelineConfig } from '../../types';
import { pausePlayer, resumePlayer, getPlayerState, hasMediaPlayer } from '../mediaController';
import { VoicePipeline } from '../../voice/voicePipeline';
import widgetStyles from './WhisperNetWidget.css?inline';

// --------------- SVG Icons (Inline) ---------------

const IconWhisper = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <line x1="8" y1="23" x2="16" y2="23" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const IconStream = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M5.636 18.364a9 9 0 0 1 0-12.728" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <path d="M18.364 5.636a9 9 0 0 1 0 12.728" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <path d="M8.464 15.536a5 5 0 0 1 0-7.072" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <path d="M15.536 8.464a5 5 0 0 1 0 7.072" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <circle cx="12" cy="12" r="1.5" fill="currentColor" />
  </svg>
);

const IconStop = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
  </svg>
);

const IconPlay = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <polygon points="6,4 20,12 6,20" fill="currentColor" />
  </svg>
);

const IconMic = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill="currentColor" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const IconMinimize = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const IconWave = () => (
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M2 12h2l3-6 4 12 4-8 3 4h4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

// --------------- Status Label Map ---------------

const STATUS_LABELS: Record<WidgetState, string> = {
  idle: 'Ready',
  listening: 'Capturing Audio',
  interrupted: 'Listening to You',
  speaking: 'Character Speaking',
};

// --------------- Visualizer Constants ---------------

const VISUALIZER_BAR_COUNT = 24;

function getBarStyles(index: number) {
  // Stagger animation speeds and heights for organic look
  const speed = 0.3 + Math.random() * 0.5;
  const height = 10 + Math.random() * 22;
  const delay = index * 0.04;
  return {
    '--bar-speed': `${speed}s`,
    '--bar-height': `${height}px`,
    animationDelay: `${delay}s`,
  } as React.CSSProperties;
}

// --------------- Pipeline Configuration ---------------
// These values will be populated from chrome.storage or environment
// For now, defaults point to local development setup

function getPipelineConfig(): VoicePipelineConfig {
  return {
    backendUrl: 'http://localhost:8000',
    realtimeModel: 'gpt-realtime-2',
    bufferMaxWords: 150,
    bufferTrimInterval: 5000,
  };
}

// --------------- Helper: Truncate Context for Display ---------------

function truncateContext(text: string, maxWords: number = 12): string {
  if (!text) return '';
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length <= maxWords) return text;
  return '…' + words.slice(words.length - maxWords).join(' ');
}

// --------------- Main Widget Component ---------------

export const WhisperNetWidget: React.FC = () => {
  const [widgetState, setWidgetState] = useState<WidgetState>('idle');
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasPlayer, setHasPlayer] = useState(false);
  const [rollingContext, setRollingContext] = useState('');
  const [aiTranscript, setAiTranscript] = useState('');
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Voice pipeline instance (persists across re-renders)
  const pipelineRef = useRef<VoicePipeline | null>(null);

  // Initialize voice pipeline once
  useEffect(() => {
    const config = getPipelineConfig();

    const pipeline = new VoicePipeline(config, {
      onStateChange: (state) => {
        setWidgetState(state);
      },
      onBufferUpdate: (context) => {
        setRollingContext(context);
      },
      onAiTranscript: (text) => {
        setAiTranscript(text);
      },
      onError: (error) => {
        console.error('[WhisperNet Widget] Pipeline error:', error);
        setPipelineError(error);
        // Auto-clear error after 5 seconds
        setTimeout(() => setPipelineError(null), 5000);
      },
      onResponseDone: () => {
        // AI finished speaking → auto-resume Pocket FM playback
        handleResume();
      },
    });

    pipelineRef.current = pipeline;

    return () => {
      pipeline.stopAll();
    };
  }, []);

  // Check for media player availability periodically
  useEffect(() => {
    const check = () => setHasPlayer(hasMediaPlayer());
    check();
    const interval = setInterval(check, 3000);
    return () => clearInterval(interval);
  }, []);

  // Listen for external messages (from background / other parts)
  useEffect(() => {
    const handler = (message: ExtensionMessage) => {
      if (message.action === MessageActions.AUDIO_CAPTURE_STARTED) {
        setWidgetState('listening');
        // Start the passive STT stream when tab capture begins
        pipelineRef.current?.startPassiveStream();
      }
      if (message.action === MessageActions.AUDIO_CAPTURE_ERROR) {
        const payload = message.payload as any;
        console.error('[WhisperNet Widget] Capture error received:', payload?.error);
        setPipelineError(`Capture Error: ${payload?.error || 'Unknown error'}`);
        setTimeout(() => setPipelineError(null), 5000);
        setWidgetState('idle');
      }
    };

    chrome.runtime.onMessage.addListener(handler);
    return () => chrome.runtime.onMessage.removeListener(handler);
  }, []);

  // --------------- Action Handlers ---------------

  const handleStartCapture = useCallback(async () => {
    try {
      setPipelineError(null);
      chrome.runtime.sendMessage({
        action: MessageActions.START_AUDIO_CAPTURE,
      });
      // State will be updated via AUDIO_CAPTURE_STARTED message,
      // which also starts the passive STT stream
    } catch (err) {
      console.error('[WhisperNet Widget] Failed to start capture:', err);
    }
  }, []);

  const handleStopCapture = useCallback(async () => {
    try {
      // Stop the voice pipeline (STT + WebRTC)
      pipelineRef.current?.stopAll();

      chrome.runtime.sendMessage({
        action: MessageActions.STOP_AUDIO_CAPTURE,
      });

      setWidgetState('idle');
      setRollingContext('');
      setAiTranscript('');
    } catch (err) {
      console.error('[WhisperNet Widget] Failed to stop capture:', err);
    }
  }, []);

  const handleAskCharacter = useCallback(async () => {
    // Pause Pocket FM playback
    const paused = pausePlayer();
    if (!paused) {
      console.warn('[WhisperNet Widget] Could not pause player');
    }

    // Get current playback state for spoiler control
    const playerState = getPlayerState();
    const episodeIndex = 1; // TODO: Extract from Pocket FM page or user settings
    const timestamp = playerState?.currentTime ?? 0;

    // Delegate to the voice pipeline orchestrator
    // This handles: freeze buffer → fetch context → session.update → enable mic
    try {
      await pipelineRef.current?.handleInterruption(episodeIndex, timestamp);
    } catch (err) {
      console.error('[WhisperNet Widget] Ask character failed:', err);
      // Recover by resuming playback
      await resumePlayer();
      setWidgetState('listening');
    }
  }, []);

  const handleResume = useCallback(async () => {
    // Notify voice pipeline to mute mic and unfreeze buffer
    pipelineRef.current?.handleManualResume();

    // Resume Pocket FM playback
    await resumePlayer();

    // Clear AI transcript
    setAiTranscript('');

    setWidgetState('listening');
  }, []);

  // --------------- Render: Collapsed FAB ---------------

  if (!isExpanded) {
    const isActive = widgetState === 'listening' || widgetState === 'interrupted' || widgetState === 'speaking';
    return (
      <>
        <style>{widgetStyles}</style>
        <button
          className={`wn-fab ${isActive ? 'wn-fab--active' : ''}`}
          onClick={() => setIsExpanded(true)}
          title="Open WhisperNet"
          id="whispernet-fab"
        >
          <IconWave />
        </button>
      </>
    );
  }

  // --------------- Render: Expanded Widget ---------------

  const visualizerClass = widgetState === 'idle'
    ? ''
    : `wn-visualizer--${widgetState === 'listening' ? 'listening' : widgetState === 'interrupted' ? 'interrupted' : 'speaking'}`;

  return (
    <>
      <style>{widgetStyles}</style>
      <div className="wn-widget" id="whispernet-widget">
        {/* --- Header --- */}
        <div className="wn-header">
          <div className="wn-header-left">
            <div className="wn-logo">
              <IconWave />
            </div>
            <span className="wn-title">WhisperNet</span>
          </div>
          <button
            className="wn-collapse-btn"
            onClick={() => setIsExpanded(false)}
            title="Minimize"
            id="whispernet-minimize"
          >
            <IconMinimize />
          </button>
        </div>

        {/* --- Status Pill --- */}
        <div className="wn-status-bar">
          <div className={`wn-status-dot wn-status-dot--${widgetState}`} />
          <span className="wn-status-text">{STATUS_LABELS[widgetState]}</span>
        </div>

        {/* --- Audio Visualizer --- */}
        <div className={`wn-visualizer ${visualizerClass}`}>
          {Array.from({ length: VISUALIZER_BAR_COUNT }).map((_, i) => (
            <div
              key={i}
              className="wn-visualizer-bar"
              style={widgetState !== 'idle' ? getBarStyles(i) : undefined}
            />
          ))}
        </div>

        {/* --- Rolling Context Preview (visible when listening) --- */}
        {widgetState === 'listening' && rollingContext && (
          <div className="wn-context-preview">
            <span className="wn-context-label">Live Context</span>
            <span className="wn-context-text">{truncateContext(rollingContext)}</span>
          </div>
        )}

        {/* --- Mic Active Indicator (Interrupted state) --- */}
        {widgetState === 'interrupted' && (
          <div className="wn-mic-indicator">
            <div className="wn-mic-ring">
              <IconMic />
            </div>
            <span className="wn-mic-label">Speak your question...</span>
          </div>
        )}

        {/* --- Speaking Indicator --- */}
        {widgetState === 'speaking' && (
          <div className="wn-speaking-indicator">
            <span className="wn-speaking-label">✦ Character is responding ✦</span>
            {aiTranscript && (
              <span className="wn-ai-transcript">{aiTranscript}</span>
            )}
          </div>
        )}

        {/* --- Error Banner --- */}
        {pipelineError && (
          <div className="wn-error-banner">
            <span className="wn-error-text">{pipelineError}</span>
          </div>
        )}

        {/* --- Controls --- */}
        <div className="wn-controls">
          {widgetState === 'idle' && (
            <div className="wn-instruction-box" style={{ textAlign: 'center', padding: '10px', fontSize: '13px', color: '#ccc' }}>
              <IconStream />
              <p style={{ marginTop: '8px', marginBottom: 0 }}>
                Click the <strong>WhisperNet icon</strong> in your browser toolbar to start capturing audio.
              </p>
            </div>
          )}

          {widgetState === 'listening' && (
            <>
              <button
                className="wn-btn wn-btn--primary"
                onClick={handleAskCharacter}
                disabled={!hasPlayer}
                title={hasPlayer ? 'Pause story & ask a character' : 'No media player detected'}
                id="whispernet-ask"
              >
                <IconMic />
                Ask Character
              </button>
              <button
                className="wn-btn wn-btn--danger"
                onClick={handleStopCapture}
                id="whispernet-stop-stream"
              >
                <IconStop />
                Stop
              </button>
            </>
          )}

          {widgetState === 'interrupted' && (
            <button
              className="wn-btn wn-btn--success"
              onClick={handleResume}
              id="whispernet-resume"
            >
              <IconPlay />
              Resume Story
            </button>
          )}

          {widgetState === 'speaking' && (
            <button
              className="wn-btn wn-btn--success"
              onClick={handleResume}
              id="whispernet-force-resume"
            >
              <IconPlay />
              Skip & Resume
            </button>
          )}
        </div>

        {/* --- Footer --- */}
        <div className="wn-footer">
          <span className="wn-footer-text">WhisperNet AI Copilot</span>
        </div>
      </div>
    </>
  );
};

export default WhisperNetWidget;
