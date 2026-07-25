// ============================================================
// WhisperNet — Deepgram Streaming STT Pipeline
// ============================================================
// Responsibilities:
//   1. Establish a persistent WebSocket to Deepgram's streaming STT
//   2. Subscribe to BroadcastChannel('whispernet-audio') for tab audio chunks
//   3. Forward raw WebM/PCM audio directly into the STT WebSocket
//   4. Feed transcript deltas into the RollingBuffer
//   5. Handle reconnection and error recovery
//
// Architectural guardrail (Dual Audio Path Separation):
//   Tab audio → STT ONLY. This audio must NEVER be sent to OpenAI
//   Realtime, as the model would attempt to converse with the narrator.
// ============================================================

import { RollingBuffer } from './rollingBuffer';

// --------------- Configuration ---------------

const DEFAULT_DEEPGRAM_WS_URL = 'wss://api.deepgram.com/v1/listen';
const DEFAULT_MODEL = 'nova-2';
const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

// --------------- STT Pipeline Class ---------------

export class SttPipeline {
  private ws: WebSocket | null = null;
  private audioChannel: BroadcastChannel | null = null;
  private buffer: RollingBuffer;
  private apiKey: string;
  private wsUrl: string;
  private model: string;
  private isRunning: boolean = false;
  private reconnectAttempts: number = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    buffer: RollingBuffer,
    apiKey: string,
    wsUrl?: string,
    model?: string
  ) {
    this.buffer = buffer;
    this.apiKey = apiKey;
    this.wsUrl = wsUrl ?? DEFAULT_DEEPGRAM_WS_URL;
    this.model = model ?? DEFAULT_MODEL;
  }

  // --------------- Lifecycle ---------------

  /**
   * Starts the STT pipeline:
   * 1. Opens WebSocket to Deepgram
   * 2. Subscribes to audio chunks from the offscreen document
   */
  async start(): Promise<void> {
    if (this.isRunning) {
      console.warn('[WhisperNet STT] Pipeline already running.');
      return;
    }

    this.isRunning = true;
    this.reconnectAttempts = 0;

    // Step 1: Connect to Deepgram
    this.connectWebSocket();

    // Step 2: Subscribe to audio chunks from offscreen document
    this.subscribeToAudioChunks();

    console.log('[WhisperNet STT] Pipeline started.');
  }

  /**
   * Stops the STT pipeline and cleans up all resources.
   */
  stop(): void {
    this.isRunning = false;

    // Clear reconnect timer
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    // Close WebSocket
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        // Send close signal to Deepgram to flush any pending transcripts
        try {
          this.ws.send(JSON.stringify({ type: 'CloseStream' }));
        } catch {
          // Ignore send errors during shutdown
        }
      }
      this.ws.close();
      this.ws = null;
    }

    // Close BroadcastChannel
    if (this.audioChannel) {
      this.audioChannel.close();
      this.audioChannel = null;
    }

    console.log('[WhisperNet STT] Pipeline stopped.');
  }

  // --------------- WebSocket Connection ---------------

  private connectWebSocket(): void {
    if (!this.isRunning) return;

    // Build the Deepgram WebSocket URL with query parameters
    const params = new URLSearchParams({
      model: this.model,
      punctuate: 'true',
      interim_results: 'true',
      endpointing: '300',         // 300ms silence endpoint
      vad_events: 'true',
      encoding: 'opus',           // WebM/Opus from MediaRecorder
      sample_rate: '48000',       // Default browser sample rate
      channels: '1',
    });

    const fullUrl = `${this.wsUrl}?${params.toString()}`;

    try {
      this.ws = new WebSocket(fullUrl, ['token', this.apiKey]);
    } catch (err) {
      console.error('[WhisperNet STT] Failed to create WebSocket:', err);
      this.scheduleReconnect();
      return;
    }

    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      console.log('[WhisperNet STT] WebSocket connected to Deepgram.');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleDeepgramMessage(event);
    };

    this.ws.onerror = (event: Event) => {
      console.error('[WhisperNet STT] WebSocket error:', event);
    };

    this.ws.onclose = (event: CloseEvent) => {
      console.log(
        `[WhisperNet STT] WebSocket closed (code=${event.code}, reason="${event.reason}")`
      );

      if (this.isRunning) {
        this.scheduleReconnect();
      }
    };
  }

  // --------------- Deepgram Message Handling ---------------

  private handleDeepgramMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data as string);

      // Process final transcripts only (not interim results)
      // This prevents duplicate text from appearing in the buffer
      if (data.type === 'Results' && data.is_final) {
        const transcript = data.channel?.alternatives?.[0]?.transcript;

        if (transcript && transcript.trim().length > 0) {
          // Feed the transcript delta into the rolling buffer
          this.buffer.append(transcript);

          console.log(
            `[WhisperNet STT] Transcript: "${transcript}" (buffer: ${this.buffer.getWordCount()} words)`
          );
        }
      }

      // Handle speech detection events (optional logging)
      if (data.type === 'SpeechStarted') {
        console.log('[WhisperNet STT] Speech detected in audio stream.');
      }
    } catch (err) {
      console.error('[WhisperNet STT] Failed to parse Deepgram message:', err);
    }
  }

  // --------------- Audio Chunk Subscription ---------------

  /**
   * Subscribes to the BroadcastChannel that receives raw audio chunks
   * from the offscreen document's MediaRecorder.
   * 
   * Path A (Story Audio) → STT ONLY. Never to OpenAI Realtime.
   */
  private subscribeToAudioChunks(): void {
    this.audioChannel = new BroadcastChannel('whispernet-audio');

    this.audioChannel.onmessage = (event: MessageEvent) => {
      const { type, buffer } = event.data;

      if (type === 'audio-chunk' && buffer) {
        this.sendAudioChunk(buffer);
      }
    };

    console.log('[WhisperNet STT] Subscribed to audio chunks via BroadcastChannel.');
  }

  /**
   * Sends a raw audio chunk to the Deepgram WebSocket.
   * Chunks are ArrayBuffers containing WebM/Opus audio data.
   */
  private sendAudioChunk(buffer: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // WebSocket not ready — chunk will be dropped
      // This is acceptable as the rolling buffer handles gaps gracefully
      return;
    }

    try {
      this.ws.send(buffer);
    } catch (err) {
      console.error('[WhisperNet STT] Failed to send audio chunk:', err);
    }
  }

  // --------------- Reconnection Logic ---------------

  private scheduleReconnect(): void {
    if (!this.isRunning) return;

    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error(
        `[WhisperNet STT] Max reconnect attempts (${MAX_RECONNECT_ATTEMPTS}) reached. Stopping pipeline.`
      );
      this.isRunning = false;
      return;
    }

    this.reconnectAttempts++;
    const delay = RECONNECT_DELAY_MS * this.reconnectAttempts;

    console.log(
      `[WhisperNet STT] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`
    );

    this.reconnectTimer = setTimeout(() => {
      this.connectWebSocket();
    }, delay);
  }

  // --------------- Accessors ---------------

  /**
   * Returns whether the STT pipeline is currently active.
   */
  getIsRunning(): boolean {
    return this.isRunning;
  }

  /**
   * Returns whether the WebSocket is currently connected.
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
