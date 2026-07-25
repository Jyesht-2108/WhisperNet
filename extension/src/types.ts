// ============================================================
// WhisperNet — Shared Types & Messaging Contracts
// ============================================================

// --------------- Extension State Interface ---------------
// Matches the interface contract from doc.md for team integration

export interface ExtensionState {
  isPlaying: boolean;
  isMicActive: boolean;
  isCapturing: boolean;
  currentRollingContext: string;
  triggerPause: () => void;
  triggerResume: () => void;
}

// --------------- Widget UI State Machine ---------------

export type WidgetState = 'idle' | 'listening' | 'interrupted' | 'speaking';

// --------------- Message Action Types ---------------

export const MessageActions = {
  /** Content Script → Background: request tab audio capture */
  START_AUDIO_CAPTURE: 'START_AUDIO_CAPTURE',
  /** Background → Content Script: acknowledge capture started */
  AUDIO_CAPTURE_STARTED: 'AUDIO_CAPTURE_STARTED',
  /** Background → Offscreen: pass stream ID for capture */
  AUDIO_STREAM_STARTED: 'AUDIO_STREAM_STARTED',
  /** UI Component → Media Controller: pause DOM audio/video */
  PAUSE_MEDIA_PLAYER: 'PAUSE_MEDIA_PLAYER',
  /** UI Component → Media Controller: resume DOM audio/video */
  RESUME_MEDIA_PLAYER: 'RESUME_MEDIA_PLAYER',
  /** Offscreen → Bridge / Member 4: raw audio blob chunk */
  AUDIO_CHUNK_EMITTED: 'AUDIO_CHUNK_EMITTED',
  /** Background → Content Script: capture error occurred */
  AUDIO_CAPTURE_ERROR: 'AUDIO_CAPTURE_ERROR',
  /** Member 4 / Realtime API → UI: AI finished speaking */
  AI_RESPONSE_COMPLETE: 'AI_RESPONSE_COMPLETE',
  /** Content Script → Background: stop audio capture */
  STOP_AUDIO_CAPTURE: 'STOP_AUDIO_CAPTURE',
} as const;

export type MessageAction = (typeof MessageActions)[keyof typeof MessageActions];

// --------------- Message Payloads ---------------

export interface AudioStreamStartedPayload {
  streamId: string;
  tabId: number;
}

export interface AudioCaptureErrorPayload {
  error: string;
}

export interface AudioChunkPayload {
  chunk: Blob;
  timestamp: number;
}

// --------------- Generic Extension Message ---------------

export interface ExtensionMessage<T = unknown> {
  action: MessageAction;
  payload?: T;
}

// --------------- Media Player State ---------------

export interface MediaPlayerState {
  currentTime: number;
  duration: number;
  paused: boolean;
}

// ============================================================
// Voice Pipeline Types (Member 4 Integration)
// ============================================================

// --------------- Voice Pipeline Configuration ---------------

export interface VoicePipelineConfig {
  /** Base URL for Member 3's FastAPI backend (e.g., http://localhost:8000) */
  backendUrl: string;
  /** OpenAI Realtime model ID */
  realtimeModel?: string;
  /** Rolling buffer max word count (default: 150) */
  bufferMaxWords?: number;
  /** Rolling buffer trim interval in ms (default: 5000) */
  bufferTrimInterval?: number;
}

// --------------- WebRTC Session Exchange ---------------
// Payload sent to Member 3's backend for SDP negotiation

export interface RealtimeSessionRequest {
  /** The local WebRTC session description offer (SDP) */
  sdp_offer: string;
}

export interface RealtimeSessionResponse {
  /** The remote SDP answer from OpenAI (via backend) */
  sdp_answer: string;
  /** Ephemeral session token (embedded in SDP, but may also be returned explicitly) */
  ephemeral_token?: string;
}

// --------------- Backend Prompt Response ---------------
// Response from Member 3's /api/generate-prompt endpoint

export interface BackendPromptRequest {
  /** The transcribed user question */
  user_query: string;
  /** The last 60-90 seconds of transcribed story audio */
  rolling_context: string;
  /** Current playback state for spoiler control */
  playback_state: {
    episode_index: number;
    timestamp: number;
  };
}

export interface BackendPromptResponse {
  /** Fully synthesized persona prompt with guardrails */
  system_instructions: string;
  /** Voice settings for OpenAI Realtime */
  voice_settings: {
    voice: string;
    speed?: number;
    tone?: string;
  };
  /** Sanitized user question */
  user_input: string;
}

// --------------- OpenAI Realtime DataChannel Events ---------------
// Matches the session.update contract from member4.md

export interface SessionUpdateEvent {
  type: 'session.update';
  session: {
    type?: string;
    instructions?: string;
    tools?: any[];
    modalities?: string[];
    audio?: {
      input?: {
        format?: { type: string; rate?: number };
        turn_detection?: {
          type: 'server_vad';
          threshold?: number;
          prefix_padding_ms?: number;
          silence_duration_ms?: number;
        };
      };
      output?: {
        format?: { type: string; rate?: number };
        voice?: string;
      };
    };
  };
}

/** Response event fired when AI finishes its turn */
export interface ResponseDoneEvent {
  type: 'response.done';
  response: {
    id: string;
    status: string;
    output: Array<{
      type: string;
      content?: Array<{
        type: string;
        text?: string;
        transcript?: string;
      }>;
    }>;
  };
}

/** Audio transcript completion event */
export interface ResponseAudioTranscriptDoneEvent {
  type: 'response.audio_transcript.done';
  transcript: string;
}

/** Union of all DataChannel events we listen for */
export type RealtimeDataChannelEvent =
  | SessionUpdateEvent
  | ResponseDoneEvent
  | ResponseAudioTranscriptDoneEvent
  | { type: string; [key: string]: unknown };

// --------------- Rolling Buffer State ---------------

export interface RollingBufferState {
  /** Current transcript text */
  text: string;
  /** Whether the buffer is frozen (during active interaction) */
  isFrozen: boolean;
  /** Word count of current buffer */
  wordCount: number;
  /** Timestamp of last update */
  lastUpdated: number;
}

// --------------- Voice Pipeline State ---------------

export type VoicePipelineState =
  | 'inactive'        // Pipeline not started
  | 'passive'         // STT running, buffer accumulating
  | 'freezing'        // Buffer frozen, preparing context
  | 'context_loading' // Fetching prompt from backend
  | 'active'          // WebRTC session active, user speaking
  | 'responding'      // AI is speaking
  | 'resuming';       // Transitioning back to passive

// --------------- Voice Pipeline Event Callbacks ---------------

export interface VoicePipelineCallbacks {
  /** Called when widget state should change */
  onStateChange: (state: WidgetState) => void;
  /** Called when rolling buffer updates */
  onBufferUpdate: (context: string) => void;
  /** Called when AI transcript is received */
  onAiTranscript: (text: string) => void;
  /** Called when an error occurs in the pipeline */
  onError: (error: string) => void;
  /** Called when AI finishes speaking — UI should resume Pocket FM */
  onResponseDone: () => void;
}
