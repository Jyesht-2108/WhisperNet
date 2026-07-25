// ============================================================
// WhisperNet — Rolling Transcript Buffer
// ============================================================
// Maintains a 60-90 second rolling window of transcribed story
// dialogue (~150 words). Supports freeze/unfreeze for interaction
// phases and auto-trimming every 5 seconds.
//
// Architectural guardrail: Buffer memory is bounded. Older text
// is constantly trimmed to prevent memory overflow and to keep
// Member 3's prompt payload within optimal token limits.
// ============================================================

import type { RollingBufferState } from '../types';

// --------------- Configuration ---------------

const DEFAULT_MAX_WORDS = 150;
const DEFAULT_TRIM_INTERVAL_MS = 5000;

// --------------- Rolling Buffer Class ---------------

export class RollingBuffer {
  private text: string = '';
  private frozen: boolean = false;
  private maxWords: number;
  private trimIntervalMs: number;
  private trimTimer: ReturnType<typeof setInterval> | null = null;
  private onUpdate: ((context: string) => void) | null = null;

  constructor(maxWords?: number, trimIntervalMs?: number) {
    this.maxWords = maxWords ?? DEFAULT_MAX_WORDS;
    this.trimIntervalMs = trimIntervalMs ?? DEFAULT_TRIM_INTERVAL_MS;
  }

  // --------------- Lifecycle ---------------

  /**
   * Starts the auto-trim timer that fires every `trimIntervalMs`.
   * Must be called to begin buffer management.
   */
  start(): void {
    if (this.trimTimer) return;

    this.trimTimer = setInterval(() => {
      this.trim();
    }, this.trimIntervalMs);

    console.log(
      `[WhisperNet Buffer] Started (maxWords=${this.maxWords}, trimInterval=${this.trimIntervalMs}ms)`
    );
  }

  /**
   * Stops the auto-trim timer and clears the buffer.
   */
  stop(): void {
    if (this.trimTimer) {
      clearInterval(this.trimTimer);
      this.trimTimer = null;
    }
    this.text = '';
    this.frozen = false;
    console.log('[WhisperNet Buffer] Stopped and cleared.');
  }

  // --------------- Core Operations ---------------

  /**
   * Appends new transcript text (STT deltas) to the buffer.
   * No-op if the buffer is frozen during active interaction.
   */
  append(delta: string): void {
    if (this.frozen) {
      return; // Buffer is frozen during active voice interaction
    }

    if (!delta || delta.trim().length === 0) {
      return;
    }

    // Add a space separator if buffer is not empty
    if (this.text.length > 0 && !this.text.endsWith(' ')) {
      this.text += ' ';
    }

    this.text += delta.trim();

    // Notify listeners
    this.notifyUpdate();
  }

  /**
   * Trims the buffer to retain only the most recent `maxWords` words.
   * This prevents memory overflow and keeps the context window tight.
   */
  trim(): void {
    if (this.frozen) return; // Don't trim while frozen

    const words = this.text.split(/\s+/).filter(Boolean);

    if (words.length > this.maxWords) {
      // Keep only the most recent maxWords
      const trimmed = words.slice(words.length - this.maxWords);
      this.text = trimmed.join(' ');

      console.log(
        `[WhisperNet Buffer] Trimmed from ${words.length} to ${trimmed.length} words`
      );
    }
  }

  // --------------- Freeze / Unfreeze ---------------

  /**
   * Freezes the buffer — no new text will be appended until unfrozen.
   * Called when the user clicks "Ask Character" to preserve the
   * current scene context for prompt synthesis.
   */
  freeze(): void {
    this.frozen = true;
    console.log(`[WhisperNet Buffer] Frozen (${this.getWordCount()} words preserved)`);
  }

  /**
   * Unfreezes the buffer — new STT deltas will be appended again.
   * Called when the AI finishes speaking and playback resumes.
   */
  unfreeze(): void {
    this.frozen = false;
    console.log('[WhisperNet Buffer] Unfrozen, resuming accumulation.');
  }

  // --------------- Accessors ---------------

  /**
   * Returns the current buffer contents for prompt synthesis.
   * This is the "rolling context" passed to Member 3's backend.
   */
  getContext(): string {
    return this.text;
  }

  /**
   * Returns the current word count of the buffer.
   */
  getWordCount(): number {
    if (!this.text) return 0;
    return this.text.split(/\s+/).filter(Boolean).length;
  }

  /**
   * Returns whether the buffer is currently frozen.
   */
  isFrozen(): boolean {
    return this.frozen;
  }

  /**
   * Returns a snapshot of the full buffer state.
   */
  getState(): RollingBufferState {
    return {
      text: this.text,
      isFrozen: this.frozen,
      wordCount: this.getWordCount(),
      lastUpdated: Date.now(),
    };
  }

  /**
   * Clears the entire buffer and resets state.
   */
  clear(): void {
    this.text = '';
    this.frozen = false;
    this.notifyUpdate();
    console.log('[WhisperNet Buffer] Cleared.');
  }

  // --------------- Callbacks ---------------

  /**
   * Registers a callback that fires whenever the buffer content changes.
   */
  setOnUpdate(callback: (context: string) => void): void {
    this.onUpdate = callback;
  }

  private notifyUpdate(): void {
    if (this.onUpdate) {
      this.onUpdate(this.text);
    }
  }
}
