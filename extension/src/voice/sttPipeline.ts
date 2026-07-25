// ============================================================
// WhisperNet — OpenAI Whisper STT Pipeline (Chunked)
// ============================================================
// Responsibilities:
//   1. Subscribe to BroadcastChannel('whispernet-audio') for tab audio chunks
//   2. Accumulate raw WebM audio chunks for X seconds
//   3. Send accumulated Blob to the backend for OpenAI Whisper transcription
//   4. Feed resulting transcript into the RollingBuffer
// ============================================================

import { RollingBuffer } from './rollingBuffer';

export class SttPipeline {
  private audioChannel: BroadcastChannel | null = null;
  private buffer: RollingBuffer;
  private backendUrl: string;
  private isRunning: boolean = false;
  
  // Chunk accumulation
  private chunkQueue: Blob[] = [];
  private accumulationTimer: ReturnType<typeof setInterval> | null = null;
  private readonly CHUNK_INTERVAL_MS = 5000; // 5 seconds per chunk
  private isProcessing: boolean = false;

  constructor(
    buffer: RollingBuffer,
    backendUrl: string
  ) {
    this.buffer = buffer;
    this.backendUrl = backendUrl.replace(/\/+$/, ''); // Remove trailing slashes
  }

  // --------------- Lifecycle ---------------

  async start(): Promise<void> {
    if (this.isRunning) {
      console.warn('[WhisperNet STT] Pipeline already running.');
      return;
    }

    this.isRunning = true;
    this.chunkQueue = [];

    // Subscribe to audio chunks from offscreen document
    this.subscribeToAudioChunks();

    // Start accumulation timer
    this.accumulationTimer = setInterval(() => {
      this.processAccumulatedChunks();
    }, this.CHUNK_INTERVAL_MS);

    console.log('[WhisperNet STT] Pipeline started (OpenAI Whisper chunked mode).');
  }

  stop(): void {
    this.isRunning = false;

    if (this.accumulationTimer) {
      clearInterval(this.accumulationTimer);
      this.accumulationTimer = null;
    }

    chrome.runtime.onMessage.removeListener(this.messageListener);

    if (this.audioChannel) {
      this.audioChannel.close();
      this.audioChannel = null;
    }

    this.chunkQueue = [];
    console.log('[WhisperNet STT] Pipeline stopped.');
  }

  private messageListener = (message: any) => {
    if (!this.isRunning) return;

    if (message.action === 'AUDIO_CHUNK_EMITTED' && message.payload?.dataUrl) {
      // Convert base64 dataUrl back to a Blob
      fetch(message.payload.dataUrl)
        .then((res) => res.blob())
        .then((blob) => {
          this.chunkQueue.push(blob);
        })
        .catch((err) => console.error('[WhisperNet STT] Failed to convert dataUrl to Blob:', err));
    }
  };

  private subscribeToAudioChunks(): void {
    chrome.runtime.onMessage.addListener(this.messageListener);
  }

  // --------------- Transcription ---------------

  private async processAccumulatedChunks(): Promise<void> {
    if (this.isProcessing || this.chunkQueue.length === 0 || !this.isRunning) {
      return;
    }

    this.isProcessing = true;
    
    // Dequeue all chunks accumulated so far
    const chunksToProcess = [...this.chunkQueue];
    this.chunkQueue = []; // Reset queue for the next window

    try {
      const combinedBlob = new Blob(chunksToProcess, { type: 'audio/webm' });
      
      const formData = new FormData();
      formData.append('audio', combinedBlob, 'chunk.webm');

      const response = await fetch(`${this.backendUrl}/api/stt/transcribe`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.text && result.text.trim().length > 0) {
        console.log('[WhisperNet STT] Transcribed:', result.text);
        this.buffer.append(result.text.trim());
      }
    } catch (err) {
      console.error('[WhisperNet STT] Chunk transcription failed:', err);
    } finally {
      this.isProcessing = false;
    }
  }
}
