// ============================================================
// WhisperNet — Offscreen Audio Processing Engine
// ============================================================
// Responsibilities:
//   1. Receive stream ID from the background service worker
//   2. Acquire the media stream via getUserMedia with tabCapture constraint
//   3. Route audio to AudioContext destination (pass-through to speakers)
//   4. Chunk audio into 1-second WebM segments via MediaRecorder
//   5. Emit AUDIO_CHUNK_EMITTED events for Member 4's STT pipeline
// ============================================================

import { MessageActions, type ExtensionMessage, type AudioStreamStartedPayload } from '../types';

// --------------- Audio Engine State ---------------

let audioContext: AudioContext | null = null;
let mediaRecorder: MediaRecorder | null = null;
let mediaStream: MediaStream | null = null;
let sourceNode: MediaStreamAudioSourceNode | null = null;

// --------------- Stream Acquisition & Audio Routing ---------------

async function initializeAudioPipeline(streamId: string): Promise<void> {
  try {
    // Step 1: Acquire the media stream using the tab capture stream ID
    // The mandatory constraint ties getUserMedia to the captured tab audio
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId,
        },
      } as MediaTrackConstraints,
    });

    // Step 2: Create AudioContext for pass-through playback
    // This ensures the user continues to hear the audio uninterrupted
    audioContext = new AudioContext();
    sourceNode = audioContext.createMediaStreamSource(mediaStream);

    // Route directly to speakers — zero disruption to user's listening experience
    sourceNode.connect(audioContext.destination);

    // Step 3: Initialize MediaRecorder for audio chunking
    // Produces 1-second WebM chunks for Member 4's STT transcription pipeline
    const recorderOptions: MediaRecorderOptions = {
      mimeType: getSupportedMimeType(),
    };

    let recordingInterval: ReturnType<typeof setInterval>;
    
    const startRecordingSlice = () => {
      if (!mediaStream || !audioContext) return;
      
      const recorder = new MediaRecorder(mediaStream, recorderOptions);
      
      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          const reader = new FileReader();
          reader.onloadend = () => {
            chrome.runtime.sendMessage({
              action: MessageActions.AUDIO_CHUNK_EMITTED,
              payload: {
                dataUrl: reader.result,
                mimeType: event.data.type,
                timestamp: Date.now(),
              },
            });
          };
          reader.readAsDataURL(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error('[WhisperNet Offscreen] MediaRecorder error:', event);
      };

      recorder.start();
      mediaRecorder = recorder; // keep ref for teardown
      
      // Stop slightly before the next interval to ensure no overlap and valid WebM header
      setTimeout(() => {
        if (recorder.state === 'recording') {
          recorder.stop();
        }
      }, 4900);
    };

    // Kick off the continuous 5-second slices
    startRecordingSlice();
    recordingInterval = setInterval(startRecordingSlice, 5000);

    // Save the interval to clear it on teardown
    (window as any)._recordingInterval = recordingInterval;

    console.log('[WhisperNet Offscreen] Audio pipeline initialized successfully.');
    console.log(`[WhisperNet Offscreen] MIME type: ${recorderOptions.mimeType}`);
    console.log(`[WhisperNet Offscreen] Sample rate: ${audioContext.sampleRate}Hz`);
  } catch (error) {
    console.error('[WhisperNet Offscreen] Failed to initialize audio pipeline:', error);
    throw error;
  }
}

// --------------- MIME Type Detection ---------------

function getSupportedMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];

  for (const mimeType of candidates) {
    if (MediaRecorder.isTypeSupported(mimeType)) {
      return mimeType;
    }
  }

  // Fallback — let the browser decide
  return '';
}

// --------------- Cleanup ---------------

function teardownAudioPipeline(): void {
  if ((window as any)._recordingInterval) {
    clearInterval((window as any)._recordingInterval);
    delete (window as any)._recordingInterval;
  }

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  mediaRecorder = null;

  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }

  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close();
  }
  audioContext = null;

  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }

  console.log('[WhisperNet Offscreen] Audio pipeline torn down.');
}

// --------------- Message Listener ---------------

chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, _sender, sendResponse) => {
    if (message.action === MessageActions.AUDIO_STREAM_STARTED) {
      const payload = message.payload as AudioStreamStartedPayload;

      initializeAudioPipeline(payload.streamId)
        .then(() => sendResponse({ success: true }))
        .catch((err) => sendResponse({ success: false, error: err.message }));

      return true; // async response
    }

    if (message.action === MessageActions.STOP_AUDIO_CAPTURE) {
      teardownAudioPipeline();
      sendResponse({ success: true });
    }
  }
);

// Cleanup on unload (when offscreen document is closed)
window.addEventListener('beforeunload', () => {
  teardownAudioPipeline();
});
