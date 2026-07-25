// ============================================================
// WhisperNet — Background Service Worker (Manifest V3)
// ============================================================
// Responsibilities:
//   1. Listen for START_AUDIO_CAPTURE from the content script
//   2. Execute chrome.tabCapture.getMediaStreamId() for the active tab
//   3. Ensure an offscreen document exists (create if missing)
//   4. Dispatch the stream ID to the offscreen worker
//   5. Handle STOP_AUDIO_CAPTURE to clean up resources
// ============================================================

import { MessageActions, type ExtensionMessage, type AudioStreamStartedPayload } from './types';

const OFFSCREEN_DOCUMENT_PATH = 'src/offscreen/offscreen.html';

// --------------- Offscreen Document Lifecycle ---------------

let creatingOffscreen: Promise<void> | null = null;
let activeTabId: number | null = null;

async function hasOffscreenDocument(): Promise<boolean> {
  // In Manifest V3, we can check existing contexts
  const contexts = await chrome.runtime.getContexts({
    contextTypes: [chrome.runtime.ContextType.OFFSCREEN_DOCUMENT],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH)],
  });
  return contexts.length > 0;
}

async function ensureOffscreenDocument(): Promise<void> {
  if (await hasOffscreenDocument()) {
    return;
  }

  // Prevent race conditions if multiple requests come in simultaneously
  if (creatingOffscreen) {
    await creatingOffscreen;
    return;
  }

  creatingOffscreen = chrome.offscreen.createDocument({
    url: OFFSCREEN_DOCUMENT_PATH,
    reasons: [chrome.offscreen.Reason.USER_MEDIA],
    justification: 'WhisperNet requires an offscreen document to process captured tab audio without interrupting playback.',
  });

  await creatingOffscreen;
  creatingOffscreen = null;
}

// --------------- Tab Audio Capture ---------------

async function startTabCapture(tabId: number): Promise<string> {
  return new Promise((resolve, reject) => {
    chrome.tabCapture.getMediaStreamId(
      { targetTabId: tabId },
      (streamId: string) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(streamId);
      }
    );
  });
}

// --------------- Message Handlers ---------------

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    sender: chrome.runtime.MessageSender,
    sendResponse: (response: unknown) => void
  ) => {
    if (message.action === MessageActions.START_AUDIO_CAPTURE) {
      handleStartCapture(sender)
        .then(() => sendResponse({ success: true }))
        .catch((err) => {
          console.error('[WhisperNet BG] Capture error:', err);
          sendResponse({ success: false, error: err.message });

          // Notify content script of the error
          if (sender.tab?.id) {
            chrome.tabs.sendMessage(sender.tab.id, {
              action: MessageActions.AUDIO_CAPTURE_ERROR,
              payload: { error: err.message },
            });
          }
        });

      // Return true to indicate we'll respond asynchronously
      return true;
    }

    if (message.action === MessageActions.STOP_AUDIO_CAPTURE) {
      handleStopCapture()
        .then(() => sendResponse({ success: true }))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    // Forward chunks from offscreen to the active tab
    if (message.action === MessageActions.AUDIO_CHUNK_EMITTED) {
      if (activeTabId !== null) {
        chrome.tabs.sendMessage(activeTabId, message);
      }
      return false; // Sync response
    }
  }
);

// Allow clicking the extension icon to start capture (grants activeTab)
chrome.action.onClicked.addListener((tab) => {
  if (tab.id) {
    const fakeSender: chrome.runtime.MessageSender = { tab };
    handleStartCapture(fakeSender).catch((err) => {
      console.error('[WhisperNet BG] Capture error from action click:', err);
    });
  }
});

async function handleStartCapture(sender: chrome.runtime.MessageSender): Promise<void> {
  const tabId = sender.tab?.id;
  if (!tabId) {
    throw new Error('No tab ID found in sender context.');
  }
  activeTabId = tabId;

  // Step 1: Ensure offscreen document exists
  await ensureOffscreenDocument();

  // Step 2: Get the media stream ID for the active tab
  const streamId = await startTabCapture(tabId);

  // Step 3: Dispatch stream ID to the offscreen document
  const payload: AudioStreamStartedPayload = { streamId, tabId };
  await chrome.runtime.sendMessage({
    action: MessageActions.AUDIO_STREAM_STARTED,
    payload,
  });

  // Step 4: Notify the content script that capture has started
  chrome.tabs.sendMessage(tabId, {
    action: MessageActions.AUDIO_CAPTURE_STARTED,
  });

  console.log(`[WhisperNet BG] Tab capture started for tab ${tabId}, streamId: ${streamId}`);
}

async function handleStopCapture(): Promise<void> {
  // Close offscreen document if it exists — this stops all audio processing
  if (await hasOffscreenDocument()) {
    await chrome.offscreen.closeDocument();
    console.log('[WhisperNet BG] Offscreen document closed, capture stopped.');
  }
  activeTabId = null;
}
