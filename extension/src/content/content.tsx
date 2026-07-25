// ============================================================
// WhisperNet — Content Script (Pocket FM DOM Injection)
// ============================================================
// Responsibilities:
//   1. Create a fixed-position container element in document.body
//   2. Attach a Shadow Root for complete CSS isolation
//   3. Mount the React WhisperNetWidget inside the Shadow Root
//   4. Ensure zero style leakage between Pocket FM and the widget
// ============================================================

import React from 'react';
import ReactDOM from 'react-dom/client';
import WhisperNetWidget from './components/WhisperNetWidget';

// --------------- Constants ---------------

const CONTAINER_ID = 'whispernet-root';

// --------------- Shadow DOM Injection ---------------

function injectWhisperNet(): void {
  // Guard: Don't inject twice
  if (document.getElementById(CONTAINER_ID)) {
    console.log('[WhisperNet] Widget already injected, skipping.');
    return;
  }

  // Step 1: Create the host container element
  const hostContainer = document.createElement('div');
  hostContainer.id = CONTAINER_ID;

  // Position it at a high z-index to overlay everything on Pocket FM
  // Using inline styles on the host to guarantee visibility
  hostContainer.style.cssText = `
    position: fixed !important;
    bottom: 0 !important;
    right: 0 !important;
    z-index: 2147483647 !important;
    width: 0 !important;
    height: 0 !important;
    overflow: visible !important;
    pointer-events: none !important;
  `;

  document.body.appendChild(hostContainer);

  // Step 2: Attach Shadow Root for CSS isolation
  // Using 'open' mode so that the extension can inspect/debug if needed.
  // The Shadow boundary still prevents Pocket FM CSS from leaking in.
  const shadowRoot = hostContainer.attachShadow({ mode: 'open' });

  // Step 3: Create an inner mount point inside the Shadow DOM
  const mountPoint = document.createElement('div');
  mountPoint.id = 'whispernet-shadow-mount';
  mountPoint.style.cssText = `
    pointer-events: auto;
  `;
  shadowRoot.appendChild(mountPoint);

  // Step 4: Render the React Widget
  const root = ReactDOM.createRoot(mountPoint);
  root.render(React.createElement(WhisperNetWidget));

  console.log('[WhisperNet] Widget injected into Pocket FM via Shadow DOM.');
}

// --------------- Initialize ---------------

// content_scripts run_at: "document_idle" guarantees DOM is ready
injectWhisperNet();
