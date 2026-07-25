// ============================================================
// WhisperNet — DOM Media Controller (Pocket FM Interceptor)
// ============================================================
// Responsibilities:
//   1. Dynamically locate <audio> / <video> elements on Pocket FM
//   2. Pause playback when user triggers character interruption
//   3. Resume playback with autoplay restriction error handling
//   4. Report current playback state (currentTime, duration, paused)
// ============================================================

import type { MediaPlayerState } from '../types';

// --------------- Element Discovery ---------------

/**
 * Dynamically locates the active HTML5 media element on the Pocket FM page.
 * Pocket FM dynamically renders its player, so we search broadly and
 * prefer elements that are currently playing or have loaded media.
 */
function findMediaElement(): HTMLMediaElement | null {
  // Search for all audio and video elements
  const mediaElements = [
    ...document.querySelectorAll<HTMLAudioElement>('audio'),
    ...document.querySelectorAll<HTMLVideoElement>('video'),
  ];

  if (mediaElements.length === 0) {
    return null;
  }

  // Prefer a media element that is currently playing
  const playing = mediaElements.find((el) => !el.paused && el.readyState >= 2);
  if (playing) {
    return playing;
  }

  // Fallback: prefer one with a loaded source
  const withSrc = mediaElements.find(
    (el) => el.src || el.querySelector('source')
  );
  if (withSrc) {
    return withSrc;
  }

  // Last resort: return the first found element
  return mediaElements[0];
}

// --------------- Playback Control ---------------

/**
 * Pauses the Pocket FM media player.
 * Returns true if successfully paused, false if no media element was found.
 */
export function pausePlayer(): boolean {
  const media = findMediaElement();
  if (!media) {
    console.warn('[WhisperNet MediaController] No media element found to pause.');
    return false;
  }

  if (!media.paused) {
    media.pause();
    console.log(
      `[WhisperNet MediaController] Paused at ${media.currentTime.toFixed(2)}s`
    );
  }

  return true;
}

/**
 * Resumes the Pocket FM media player from its current position.
 * Handles autoplay restrictions gracefully by catching DOMExceptions.
 * Returns true if resume was initiated, false if no element found.
 */
export async function resumePlayer(): Promise<boolean> {
  const media = findMediaElement();
  if (!media) {
    console.warn('[WhisperNet MediaController] No media element found to resume.');
    return false;
  }

  if (media.paused) {
    try {
      await media.play();
      console.log(
        `[WhisperNet MediaController] Resumed from ${media.currentTime.toFixed(2)}s`
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        console.warn(
          '[WhisperNet MediaController] Autoplay blocked by browser policy. ' +
          'User interaction may be required to resume playback.'
        );
      } else {
        console.error('[WhisperNet MediaController] Resume error:', error);
      }
      return false;
    }
  }

  return true;
}

// --------------- State Reporting ---------------

/**
 * Returns the current state of the Pocket FM media player.
 * Returns null if no media element is found on the page.
 */
export function getPlayerState(): MediaPlayerState | null {
  const media = findMediaElement();
  if (!media) {
    return null;
  }

  return {
    currentTime: media.currentTime,
    duration: isNaN(media.duration) ? 0 : media.duration,
    paused: media.paused,
  };
}

/**
 * Checks if a media player element exists on the current page.
 */
export function hasMediaPlayer(): boolean {
  return findMediaElement() !== null;
}
