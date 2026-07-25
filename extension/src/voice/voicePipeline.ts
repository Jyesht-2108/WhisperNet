// ============================================================
// WhisperNet — Voice Pipeline Orchestrator
// ============================================================
// Central coordinator that wires together:
//   • RollingBuffer (passive transcript accumulation)
//   • SttPipeline (Deepgram WebSocket STT)
//   • RealtimeClient (OpenAI WebRTC voice interaction)
//   • Backend API calls (Member 3's prompt synthesis)
//   • UI state transitions
//
// This module implements the full end-to-end interaction loop:
//   Tab Capture → STT → Rolling Buffer → Ask Character →
//   Freeze Buffer → Fetch Context → session.update →
//   User Speaks → AI Responds → response.done → Auto-Resume
// ============================================================

import { RollingBuffer } from './rollingBuffer';
import { SttPipeline } from './sttPipeline';
import { RealtimeClient } from './realtimeClient';
import type {
  VoicePipelineConfig,
  VoicePipelineCallbacks,
  BackendPromptRequest,
  BackendPromptResponse,
} from '../types';

// --------------- Voice Pipeline Class ---------------

export class VoicePipeline {
  private buffer: RollingBuffer;
  private stt: SttPipeline;
  private realtime: RealtimeClient;
  private config: VoicePipelineConfig;
  private callbacks: VoicePipelineCallbacks;
  private isActive: boolean = false;

  constructor(config: VoicePipelineConfig, callbacks: VoicePipelineCallbacks) {
    this.config = config;
    this.callbacks = callbacks;

    // Initialize the rolling buffer
    this.buffer = new RollingBuffer(
      config.bufferMaxWords,
      config.bufferTrimInterval
    );

    // Wire buffer updates to UI
    this.buffer.setOnUpdate((context) => {
      callbacks.onBufferUpdate(context);
    });

    // Initialize the STT pipeline (Chunked OpenAI Whisper via Backend)
    this.stt = new SttPipeline(
      this.buffer,
      config.backendUrl
    );

    // Initialize the WebRTC client
    this.realtime = new RealtimeClient(config.backendUrl, config.realtimeModel || 'gpt-4o-realtime-preview-2024-12-17');

    // Wire WebRTC callbacks
    this.realtime.setOnResponseDone(() => {
      this.handleResponseDone();
    });

    this.realtime.setOnAiTranscript((text) => {
      callbacks.onAiTranscript(text);
    });

    this.realtime.setOnError((error) => {
      callbacks.onError(error);
    });
  }

  // ===============================================================
  // Phase 1: Passive Stream — STT running, buffer accumulating
  // ===============================================================

  /**
   * Starts the passive audio pipeline.
   * Called when the user clicks "Start Stream" and tab capture begins.
   * 
   * Flow: Offscreen Audio Chunks → STT WebSocket → Rolling Buffer
   */
  async startPassiveStream(): Promise<void> {
    try {
      // Start the rolling buffer auto-trim
      this.buffer.start();

      // Start the Deepgram STT WebSocket
      await this.stt.start();

      this.isActive = true;
      console.log('[WhisperNet Pipeline] Passive stream started.');
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : String(error);
      console.error('[WhisperNet Pipeline] Failed to start passive stream:', errMsg);
      this.callbacks.onError(`Failed to start audio pipeline: ${errMsg}`);
    }
  }

  /**
   * Stops the entire pipeline (passive + active).
   * Called when the user clicks "Stop" or the extension unloads.
   */
  stopAll(): void {
    // Stop STT
    this.stt.stop();

    // Stop buffer
    this.buffer.stop();

    // Disconnect WebRTC
    this.realtime.disconnect();

    this.isActive = false;
    console.log('[WhisperNet Pipeline] All streams stopped.');
  }

  // ===============================================================
  // Phase 2: Active Interaction — User "Asks a Character"
  // ===============================================================

  /**
   * Handles the user clicking "Ask Character":
   * 1. Freezes the rolling buffer (preserves current scene context)
   * 2. Fetches enriched persona prompt from Member 3's backend
   * 3. Initializes WebRTC connection if not already active
   * 4. Sends session.update via DataChannel with context
   * 5. Enables mic track → user speaks → AI responds
   * 
   * @param episodeIndex - Current episode index for spoiler control
   * @param timestamp - Current playback timestamp
   */
  async handleInterruption(episodeIndex: number, timestamp: number): Promise<void> {
    try {
      // Step 1: Freeze the rolling buffer and pause passive STT
      this.buffer.freeze();
      this.stt.pause();
      const frozenContext = this.buffer.getContext();

      console.log(
        `[WhisperNet Pipeline] Buffer frozen with ${this.buffer.getWordCount()} words.`
      );

      // Step 2: Fetch enriched persona prompt from backend
      this.callbacks.onStateChange('interrupted');

      const promptResponse = await this.fetchPersonaPrompt(
        '', // User query will be spoken via WebRTC, not typed
        frozenContext,
        episodeIndex,
        timestamp
      );

      // Step 3: Initialize WebRTC if not already connected
      if (!this.realtime.getIsConnected()) {
        console.log('[WhisperNet Pipeline] Initializing WebRTC connection...');
        await this.realtime.connect();
      }

      // Step 4: Wait for DataChannel to be ready, then send session.update
      await this.waitForDataChannel();

      this.realtime.sendSessionUpdate(
        promptResponse.system_instructions,
        promptResponse.voice_settings?.voice
      );

      // Step 5: Enable microphone — user can now speak
      this.realtime.setMicEnabled(true);

      console.log('[WhisperNet Pipeline] Interaction active — user can speak.');
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : String(error);
      console.error('[WhisperNet Pipeline] Interruption failed:', errMsg);
      this.callbacks.onError(`Failed to start interaction: ${errMsg}`);

      // Attempt to recover — unfreeze buffer and let the user resume
      this.buffer.unfreeze();
      this.stt.resume();
      this.callbacks.onStateChange('listening');
    }
  }

  // ===============================================================
  // Phase 3: Resolution — AI finished speaking, resume playback
  // ===============================================================

  /**
   * Called internally when OpenAI's response.done event fires.
   * This signals that the AI has finished speaking.
   * 
   * Flow:
   * 1. Mute mic track
   * 2. Signal UI to resume Pocket FM (onResponseDone callback)
   * 3. Unfreeze the rolling buffer
   */
  private handleResponseDone(): void {
    console.log('[WhisperNet Pipeline] AI finished generating response.');
    
    // 1. Mute the mic
    this.realtime.setMicEnabled(false);

    // Note: We deliberately do NOT call this.callbacks.onResponseDone() here!
    // The user must manually click "Resume Story" to prevent the story audio
    // from overlapping with the AI's WebRTC audio buffer.
  }

  /**
   * Manual resolution — called when the user clicks "Resume Story"
   * or "Skip & Resume" before the AI finishes speaking.
   */
  handleManualResume(): void {
    console.log('[WhisperNet Pipeline] Manual resume triggered.');

    // Mute mic
    this.realtime.setMicEnabled(false);

    // Unfreeze buffer
    this.buffer.unfreeze();
  }

  // ===============================================================
  // Backend Communication
  // ===============================================================

  /**
   * Fetches the enriched persona prompt from Member 3's FastAPI backend.
   * The backend:
   *   1. Receives the rolling context + episode boundary
   *   2. Queries Databricks for relevant lore (with spoiler filtering)
   *   3. Synthesizes a guarded persona system prompt
   *   4. Returns the complete instruction set for OpenAI
   */
  private async fetchPersonaPrompt(
    userQuery: string,
    rollingContext: string,
    episodeIndex: number,
    timestamp: number
  ): Promise<BackendPromptResponse> {
    const endpoint = `${this.config.backendUrl}/api/generate-prompt`;

    const requestBody: BackendPromptRequest = {
      user_query: userQuery,
      rolling_context: rollingContext,
      playback_state: {
        episode_index: episodeIndex,
        timestamp,
      },
    };

    console.log('[WhisperNet Pipeline] Fetching persona prompt from backend...');

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Backend prompt fetch failed (${response.status}): ${errorText}`
      );
    }

    const data: BackendPromptResponse = await response.json();
    console.log('[WhisperNet Pipeline] Persona prompt received.');
    return data;
  }

  // ===============================================================
  // Utilities
  // ===============================================================

  /**
   * Waits for the DataChannel to be open before sending events.
   * Times out after 5 seconds to prevent indefinite blocking.
   */
  private waitForDataChannel(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.realtime.isDataChannelReady()) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        reject(new Error('DataChannel open timeout (5s)'));
      }, 5000);

      const checkInterval = setInterval(() => {
        if (this.realtime.isDataChannelReady()) {
          clearInterval(checkInterval);
          clearTimeout(timeout);
          resolve();
        }
      }, 100);
    });
  }

  // ===============================================================
  // Accessors
  // ===============================================================

  /** Returns the current rolling context text */
  getRollingContext(): string {
    return this.buffer.getContext();
  }

  /** Returns the rolling buffer word count */
  getBufferWordCount(): number {
    return this.buffer.getWordCount();
  }

  /** Returns whether the pipeline is active */
  getIsActive(): boolean {
    return this.isActive;
  }

  /** Returns whether the WebRTC connection is established */
  isRealtimeConnected(): boolean {
    return this.realtime.getIsConnected();
  }

  /** Returns the underlying microphone stream */
  getMicStream(): MediaStream | null {
    return this.realtime.getMicStream();
  }
}
