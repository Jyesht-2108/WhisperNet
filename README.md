# 🎙️ WhisperNet — Browser-Native AI Copilot for Audio Storytelling

> **Turn passive listening into an interactive, infinite story universe.**  
> WhisperNet is a Chrome Extension that injects an in-context AI voice copilot directly over audio storytelling platforms like Pocket FM. Interrupt any story live, ask a character a question, and receive low-latency, in-persona voice responses anchored strictly to your current timestamp—**zero spoilers guaranteed.**

---

## 🌟 Key Features

* **🌐 Browser-Native Overlay:** Seamlessly injects an isolated Shadow DOM UI floating widget into Pocket FM without altering site styles or breaking navigation.
  <br>
* **⚡ Sub-500ms Voice Interactivity:** Powered by OpenAI’s Realtime API (`gpt-4o-realtime-preview`) over WebRTC for instant, natural, in-persona dialogue.
* **🛡️ Temporal Anti-Spoiler RAG:** Combines Databricks Vector Search and Databricks Genie AI with strict metadata filtering (`WHERE episode_index <= current_position`). Future plot points remain mathematically inaccessible to the AI.
* **🎙️ Live Tab Capture & Rolling Memory:** Utilizes `chrome.tabCapture` in an offscreen worker to continuously transcribe live tab audio into a 90-second rolling context buffer without muting the audio for the listener.
* **⏯️ Smart Player Interruption:** Automatically pauses the HTML5 audio player when the user speaks and seamlessly resumes playback as soon as the character finishes answering.

---

## 🏗️ Architecture Overview

WhisperNet connects Edge Browser Execution, Asynchronous Python Orchestration, and Databricks Intelligence Layers:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        POCKET FM TAB (Chrome Browser)                       │
│                                                                             │
│  [HTML5 Audio Player] ──(tabCapture)──> [Offscreen Worker] ──> [STT Buffer] │
│           │                                                          │      │
│      (Pause/Resume)                                                  │      │
│           ▲                                                          │      │
│   [Injected React UI] <───────(WebRTC Voice Stream)────────> [OpenAI]       │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ (JSON State & Query)
                                    ▼
                     ┌──────────────────────────────┐
                     │   FastAPI Backend Server     │
                     │  (Prompt Synthesis & Auth)   │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │   Databricks Knowledge Core  │
                     │  • Unity Catalog (Delta)     │
                     │  • Vector Search Index       │
                     │  • Genie AI Reasoning Space  │
                     └──────────────────────────────┘
