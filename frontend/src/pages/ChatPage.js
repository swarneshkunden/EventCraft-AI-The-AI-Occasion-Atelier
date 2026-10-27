/**
 * AI Event Co-Pilot Chat and Personalized Idea Generator Page.
 */
import { getCurrentEvent } from '../services/events.js';
import {
  getChatHistory,
  sendChatMessage,
  getEventIdeas,
} from '../services/events.js';
import { showToast, escapeHtml } from '../utils/toast.js';

let chatHistory = [];
let generatedIdeas = null;

export async function renderChatPage() {
  const event = getCurrentEvent();

  if (!event) {
    return `
      <div class="page-body">
        <div class="empty-state card">
          <p>Please select or create an event to talk with your AI Co-Pilot.</p>
        </div>
      </div>
    `;
  }

  try {
    chatHistory = (await getChatHistory(event.id)) || [];
  } catch (err) {
    console.error('Failed to load chat history', err);
    chatHistory = [];
  }

  const promptSuggestions = [
    'Draft a polite RSVP reminder message for pending guests',
    'Write a minute-by-minute run-of-show schedule for our event',
    'What are unique, memorable entertainment ideas on our budget?',
    'How can we negotiate or lower costs on our venue and catering?',
  ];

  return `
    <div class="chat-layout">

      <!-- Top Bar with Ideas Generator Trigger -->
      <div style="padding: 14px 24px; border-bottom: 1px solid var(--clr-border); background: var(--clr-surface); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div>
          <h2 style="font-size: 1.2rem; font-weight: 800; display: flex; align-items: center; gap: 8px;">
            <span>✨</span> AI Event Co-Pilot
          </h2>
          <p style="font-size: 0.8rem; color: var(--clr-text-muted);">
            Context-aware execution assistant with access to your budget, tasks, and vendors.
          </p>
        </div>

        <button id="btn-generate-ideas" class="btn btn-primary btn-sm" title="Get theme, decor, menu, and activity recommendations">
          💡 Generate Creative Ideas
        </button>
      </div>

      <!-- Personalized Ideas Container (if opened) -->
      <div id="ideas-modal-container" style="display: none; padding: 16px 24px; background: var(--clr-surface-2); border-bottom: 1px solid var(--clr-border); max-height: 280px; overflow-y: auto;">
        <!-- Filled dynamically -->
      </div>

      <!-- Chat Messages Scroll Area -->
      <div class="chat-messages" id="chat-messages-container">
        ${
          chatHistory.length === 0
            ? `
          <div style="text-align: center; margin: auto; max-width: 500px; color: var(--clr-text-muted);">
            <div style="font-size: 40px; margin-bottom: 12px;">🤖</div>
            <h3 style="font-size: 1.1rem; font-weight: 700; color: var(--clr-text); margin-bottom: 6px;">
              Your Event Execution Co-Pilot
            </h3>
            <p style="font-size: 0.85rem; line-height: 1.6; margin-bottom: 20px;">
              Ask anything about scheduling, run-of-show timings, budget optimization, guest communication, or contingency plans.
            </p>

            <div style="display: flex; flex-direction: column; gap: 8px;">
              <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--clr-primary-light);">
                Try Asking:
              </div>
              ${promptSuggestions
                .map(
                  (p) => `
                <button class="chip prompt-chip" style="text-align: left; padding: 8px 14px;">
                  💬 ${escapeHtml(p)}
                </button>
              `
                )
                .join('')}
            </div>
          </div>
        `
            : renderChatMessages(chatHistory)
        }
      </div>

      <!-- Chat Input Area -->
      <div class="chat-input-area">
        <div class="chat-input-row">
          <textarea
            id="chat-textarea"
            rows="2"
            placeholder="Ask your AI Co-Pilot anything about ${escapeHtml(event.title || event.name)}... (Shift+Enter for new line)"
          ></textarea>
          <button id="btn-send-chat" class="btn btn-primary" style="height: 48px; padding: 0 20px; font-weight: 700;">
            Send
          </button>
        </div>
      </div>

    </div>
  `;
}

function renderChatMessages(messages) {
  return messages
    .map((msg) => {
      const isUser = msg.role === 'user';
      return `
      <div class="chat-bubble ${isUser ? 'user' : 'assistant'}" style="position: relative;">
        <div style="font-size: 0.7rem; font-weight: 700; color: var(--clr-text-dim); margin-bottom: 4px; text-transform: uppercase;">
          ${isUser ? 'You' : 'EventCraft Co-Pilot'}
        </div>
        <div class="chat-bubble-text" style="white-space: pre-wrap; word-break: break-word;">${escapeHtml(msg.content)}</div>
      </div>
    `;
    })
    .join('');
}

export function initChatPageEvents() {
  const event = getCurrentEvent();
  if (!event) return;

  const msgContainer = document.getElementById('chat-messages-container');
  if (msgContainer) {
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  const textarea = document.getElementById('chat-textarea');
  const sendBtn = document.getElementById('btn-send-chat');

  async function handleSend() {
    const text = textarea?.value.trim();
    if (!text) return;

    textarea.value = '';
    sendBtn.disabled = true;

    // Append user message optimistically
    chatHistory.push({ role: 'user', content: text });
    if (msgContainer) {
      msgContainer.innerHTML = renderChatMessages(chatHistory);
      msgContainer.scrollTop = msgContainer.scrollHeight;
    }

    // Loading indicator
    const loadingBubble = document.createElement('div');
    loadingBubble.className = 'chat-bubble assistant';
    loadingBubble.id = 'ai-chat-loading';
    loadingBubble.innerHTML = `
      <div class="ai-loading">
        <span class="spinner spinner-sm"></span>
        <span>Co-Pilot is thinking...</span>
      </div>
    `;
    msgContainer?.appendChild(loadingBubble);
    if (msgContainer) msgContainer.scrollTop = msgContainer.scrollHeight;

    try {
      const response = await sendChatMessage(event.id, text);
      document.getElementById('ai-chat-loading')?.remove();
      chatHistory.push({ role: 'assistant', content: response.content });
      if (msgContainer) {
        msgContainer.innerHTML = renderChatMessages(chatHistory);
        msgContainer.scrollTop = msgContainer.scrollHeight;
      }
    } catch (err) {
      document.getElementById('ai-chat-loading')?.remove();
      showToast(err.message || 'Chat error. Please try again.', 'error');
    } finally {
      sendBtn.disabled = false;
      textarea?.focus();
    }
  }

  sendBtn?.addEventListener('click', handleSend);

  textarea?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Prompt chips
  document.querySelectorAll('.prompt-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      if (textarea) {
        textarea.value = chip.textContent.replace('💬', '').trim();
        handleSend();
      }
    });
  });

  // Generate Ideas
  document.getElementById('btn-generate-ideas')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-generate-ideas');
    const ideasBox = document.getElementById('ideas-modal-container');
    if (!ideasBox) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Generating Ideas...';

    try {
      const ideas = await getEventIdeas(event.id);
      btn.disabled = false;
      btn.textContent = '💡 Refresh Ideas';

      ideasBox.style.display = 'block';

      // Render ideas
      const rawText = ideas.raw || JSON.stringify(ideas, null, 2);
      ideasBox.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h4 style="font-weight: 700; color: var(--clr-primary-light);">
            🎨 Personalized Themes, Decor & Menu Inspiration
          </h4>
          <button id="btn-close-ideas" class="btn btn-ghost btn-sm" style="font-size: 0.8rem;">✕ Close</button>
        </div>
        <div style="font-size: 0.85rem; line-height: 1.6; color: var(--clr-text); white-space: pre-wrap;">
          ${escapeHtml(rawText)}
        </div>
      `;

      document.getElementById('btn-close-ideas')?.addEventListener('click', () => {
        ideasBox.style.display = 'none';
      });

      showToast('Ideas generated based on your profile & budget!', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to generate ideas', 'error');
      btn.disabled = false;
      btn.textContent = '💡 Generate Creative Ideas';
    }
  });
}
