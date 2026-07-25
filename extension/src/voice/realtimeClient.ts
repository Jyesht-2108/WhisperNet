// ============================================================
// WhisperNet — OpenAI Realtime WebRTC Client
// ============================================================
// Responsibilities:
//   1. Create RTCPeerConnection and generate local SDP offer
//   2. Exchange SDP with Member 3's backend (ephemeral token auth)
//   3. Attach user microphone track to PeerConnection
//   4. Listen for remote audio track (AI voice) and play it
//   5. Manage RTCDataChannel for session.update / response.done
//   6. Configure server-side VAD (server_vad)
//
// Architectural guardrail (Dual Audio Path Separation):
//   Path B (Microphone Audio) → OpenAI Realtime ONLY.
//   Tab audio must NEVER be sent to the Realtime model.
//
// Security guardrail:
//   Client must NEVER store the OpenAI API key. All auth goes
//   through Member 3's ephemeral token endpoint.
// ============================================================

import type {
  SessionUpdateEvent,
  RealtimeDataChannelEvent,
} from '../types';

// --------------- Configuration ---------------

const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
];

const DATA_CHANNEL_LABEL = 'oai-events';

// --------------- Realtime Client Class ---------------

export class RealtimeClient {
  private peerConnection: RTCPeerConnection | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private remoteAudioEl: HTMLAudioElement | null = null;
  private micStream: MediaStream | null = null;
  private backendUrl: string;
  private isConnected: boolean = false;

  // Callbacks
  private onResponseDone: (() => void) | null = null;
  private onAiTranscript: ((text: string) => void) | null = null;
  private onError: ((error: string) => void) | null = null;

  constructor(backendUrl: string) {
    this.backendUrl = backendUrl;
  }

  // --------------- Lifecycle ---------------

  /**
   * Initializes the WebRTC connection to OpenAI Realtime API:
   * 1. Acquires user microphone
   * 2. Creates RTCPeerConnection
   * 3. Opens DataChannel
   * 4. Generates SDP offer
   * 5. Exchanges with backend for SDP answer (ephemeral auth)
   * 6. Sets remote description to complete the handshake
   */
  async connect(): Promise<void> {
    if (this.isConnected) {
      console.warn('[WhisperNet RTC] Already connected.');
      return;
    }

    try {
      // Step 1: Acquire user microphone (Path B: Mic → OpenAI ONLY)
      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Initially mute the mic track — it gets unmuted when the user clicks "Ask"
      this.setMicEnabled(false);

      // Step 2: Create RTCPeerConnection
      this.peerConnection = new RTCPeerConnection({
        iceServers: ICE_SERVERS,
      });

      // Step 3: Add mic track to PeerConnection
      this.micStream.getAudioTracks().forEach((track) => {
        this.peerConnection!.addTrack(track, this.micStream!);
      });

      // Step 4: Listen for remote audio track (AI's voice)
      this.setupRemoteAudioPlayback();

      // Step 5: Create DataChannel for JSON events
      this.setupDataChannel();

      // Step 6: Generate SDP offer
      const offer = await this.peerConnection.createOffer({
        offerToReceiveAudio: true,
      });
      await this.peerConnection.setLocalDescription(offer);

      // Step 7: Exchange SDP with backend (ephemeral token authentication)
      const sdpAnswer = await this.exchangeSdpWithBackend(offer.sdp!);

      // Step 8: Set remote description to complete WebRTC handshake
      await this.peerConnection.setRemoteDescription({
        type: 'answer',
        sdp: sdpAnswer,
      });

      this.isConnected = true;
      console.log('[WhisperNet RTC] WebRTC connection established.');
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : String(error);
      console.error('[WhisperNet RTC] Connection failed:', errMsg);
      this.onError?.(`WebRTC connection failed: ${errMsg}`);
      this.disconnect();
      throw error;
    }
  }

  /**
   * Disconnects the WebRTC session and cleans up all resources.
   */
  disconnect(): void {
    // Close data channel
    if (this.dataChannel) {
      this.dataChannel.close();
      this.dataChannel = null;
    }

    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }

    // Stop microphone
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }

    // Remove remote audio element
    if (this.remoteAudioEl) {
      this.remoteAudioEl.pause();
      this.remoteAudioEl.srcObject = null;
      this.remoteAudioEl.remove();
      this.remoteAudioEl = null;
    }

    this.isConnected = false;
    console.log('[WhisperNet RTC] Disconnected and cleaned up.');
  }

  // --------------- Remote Audio Playback ---------------

  /**
   * Sets up a hidden <audio> element to play the AI's voice response.
   * Listens for the remote track event on the PeerConnection.
   */
  private setupRemoteAudioPlayback(): void {
    if (!this.peerConnection) return;

    this.peerConnection.ontrack = (event: RTCTrackEvent) => {
      console.log('[WhisperNet RTC] Received remote audio track from OpenAI.');

      // Create a hidden audio element for AI voice playback
      if (!this.remoteAudioEl) {
        this.remoteAudioEl = document.createElement('audio');
        this.remoteAudioEl.autoplay = true;
        this.remoteAudioEl.style.display = 'none';
        this.remoteAudioEl.id = 'whispernet-ai-audio';
        document.body.appendChild(this.remoteAudioEl);
      }

      // Attach the remote stream to the audio element
      const [remoteStream] = event.streams;
      if (remoteStream) {
        this.remoteAudioEl.srcObject = remoteStream;
      }
    };
  }

  // --------------- DataChannel Management ---------------

  /**
   * Creates and configures the RTCDataChannel for bidirectional
   * JSON event communication with the OpenAI Realtime API.
   */
  private setupDataChannel(): void {
    if (!this.peerConnection) return;

    this.dataChannel = this.peerConnection.createDataChannel(DATA_CHANNEL_LABEL, {
      ordered: true,
    });

    this.dataChannel.onopen = () => {
      console.log('[WhisperNet RTC] DataChannel opened.');
    };

    this.dataChannel.onclose = () => {
      console.log('[WhisperNet RTC] DataChannel closed.');
    };

    this.dataChannel.onerror = (event) => {
      console.error('[WhisperNet RTC] DataChannel error:', event);
    };

    this.dataChannel.onmessage = (event: MessageEvent) => {
      this.handleDataChannelMessage(event);
    };
  }

  /**
   * Processes incoming JSON events from the OpenAI Realtime API
   * via the DataChannel.
   */
  private handleDataChannelMessage(event: MessageEvent): void {
    try {
      const data: RealtimeDataChannelEvent = JSON.parse(event.data);

      switch (data.type) {
        case 'response.done':
          console.log('[WhisperNet RTC] AI response complete.');
          this.onResponseDone?.();
          break;

        case 'response.audio_transcript.done':
          if ('transcript' in data) {
            const transcript = data.transcript as string;
            console.log(`[WhisperNet RTC] AI transcript: "${transcript}"`);
            this.onAiTranscript?.(transcript);
          }
          break;

        case 'session.created':
          console.log('[WhisperNet RTC] Session created by OpenAI.');
          break;

        case 'session.updated':
          console.log('[WhisperNet RTC] Session updated successfully.');
          break;

        case 'error':
          const errorMsg = (data as { error?: { message?: string } }).error?.message ?? 'Unknown error';
          console.error(`[WhisperNet RTC] OpenAI error: ${errorMsg}`);
          this.onError?.(errorMsg);
          break;

        default:
          // Log unhandled events for debugging
          console.log(`[WhisperNet RTC] Event: ${data.type}`);
      }
    } catch (err) {
      console.error('[WhisperNet RTC] Failed to parse DataChannel message:', err);
    }
  }

  // --------------- Session Update ---------------

  /**
   * Sends a session.update event via the DataChannel to inject
   * Member 3's persona context BEFORE the model processes user voice.
   * 
   * This is the critical integration point — the system instructions
   * contain the fused Databricks lore + rolling buffer + guardrails.
   */
  sendSessionUpdate(instructions: string, voice?: string): void {
    if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
      console.error('[WhisperNet RTC] DataChannel not open, cannot send session.update.');
      return;
    }

    const event: SessionUpdateEvent = {
      type: 'session.update',
      session: {
        instructions,
        turn_detection: {
          type: 'server_vad',
          threshold: 0.5,
          prefix_padding_ms: 300,
          silence_duration_ms: 500,
        },
        voice: voice ?? 'alloy',
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
      },
    };

    this.dataChannel.send(JSON.stringify(event));
    console.log('[WhisperNet RTC] Sent session.update with persona context.');
  }

  // --------------- Microphone Control ---------------

  /**
   * Enables or disables the microphone track.
   * When disabled, audio is not sent to OpenAI.
   */
  setMicEnabled(enabled: boolean): void {
    if (!this.micStream) return;

    this.micStream.getAudioTracks().forEach((track) => {
      track.enabled = enabled;
    });

    console.log(`[WhisperNet RTC] Mic ${enabled ? 'enabled' : 'disabled'}.`);
  }

  // --------------- SDP Exchange ---------------

  /**
   * Exchanges the local SDP offer with Member 3's FastAPI backend.
   * The backend:
   *   1. Receives the SDP offer
   *   2. Uses the master OpenAI API key to create an ephemeral session
   *   3. Negotiates the WebRTC session with OpenAI
   *   4. Returns the remote SDP answer
   * 
   * This ensures the OpenAI API key is NEVER exposed to the client.
   */
  private async exchangeSdpWithBackend(localSdp: string): Promise<string> {
    const endpoint = `${this.backendUrl}/api/realtime/session`;

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sdp_offer: localSdp,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `SDP exchange failed (${response.status}): ${errorText}`
      );
    }

    const data = await response.json();

    if (!data.sdp_answer) {
      throw new Error('Backend response missing sdp_answer field.');
    }

    console.log('[WhisperNet RTC] SDP exchange successful.');
    return data.sdp_answer;
  }

  // --------------- Callback Registration ---------------

  /**
   * Registers a callback for when the AI finishes speaking.
   * This triggers the UI to resume Pocket FM playback.
   */
  setOnResponseDone(callback: () => void): void {
    this.onResponseDone = callback;
  }

  /**
   * Registers a callback for when the AI's transcript is available.
   */
  setOnAiTranscript(callback: (text: string) => void): void {
    this.onAiTranscript = callback;
  }

  /**
   * Registers a callback for error events.
   */
  setOnError(callback: (error: string) => void): void {
    this.onError = callback;
  }

  // --------------- Accessors ---------------

  /**
   * Returns whether the WebRTC connection is active.
   */
  getIsConnected(): boolean {
    return this.isConnected;
  }

  /**
   * Returns whether the DataChannel is open and ready.
   */
  isDataChannelReady(): boolean {
    return this.dataChannel?.readyState === 'open';
  }

  /**
   * Returns the current microphone stream (for external use if needed).
   */
  getMicStream(): MediaStream | null {
    return this.micStream;
  }
}
