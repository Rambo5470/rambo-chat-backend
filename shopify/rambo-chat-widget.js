/**
 * Rambo Bikes Chat Widget
 * Embed in Shopify: Online Store → Themes → Edit Code → theme.liquid → paste before </body>
 * Update CHAT_API_URL below after deploying the backend to Vercel.
 */

(function () {
  'use strict';

  // ── CONFIG ─────────────────────────────────────────────────────────────────
  const CHAT_API_URL   = 'https://rambo-chat.vercel.app/api/chat'; // UPDATE after Vercel deploy
  const BRAND_DARK     = '#1b1b1b';
  const BRAND_RED      = '#cc0000';
  const GREETING_DELAY = 5000;   // ms before greeting appears
  const GREETING_TTL   = 3000;   // ms greeting stays before collapsing to icon

  // ── STATE ──────────────────────────────────────────────────────────────────
  let history       = [];
  let customerName  = '';
  let customerEmail = '';
  let isOpen        = false;
  let hasGreeted    = false;
  let infoCollected = false;

  // ── INJECT CSS ─────────────────────────────────────────────────────────────
  const css = `
    #rb-chat-wrapper * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    #rb-chat-wrapper { position: fixed; bottom: 24px; right: 24px; z-index: 99999; }

    /* Greeting bubble */
    #rb-greeting {
      position: absolute; bottom: 68px; right: 0;
      background: #fff; color: ${BRAND_DARK};
      padding: 10px 16px; border-radius: 20px 20px 4px 20px;
      font-size: 14px; font-weight: 500; white-space: nowrap;
      box-shadow: 0 4px 20px rgba(0,0,0,0.15);
      animation: rb-fadein 0.3s ease;
      cursor: pointer;
    }

    /* Launcher icon */
    #rb-launcher {
      width: 56px; height: 56px; border-radius: 50%;
      background: ${BRAND_DARK}; border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
      transition: transform 0.2s ease, background 0.2s ease;
    }
    #rb-launcher:hover { transform: scale(1.08); background: ${BRAND_RED}; }
    #rb-launcher svg { width: 26px; height: 26px; fill: #fff; }

    /* Chat window */
    #rb-window {
      position: absolute; bottom: 72px; right: 0;
      width: 360px; max-width: calc(100vw - 32px);
      height: 520px; max-height: calc(100vh - 100px);
      background: #fff; border-radius: 16px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.18);
      display: flex; flex-direction: column;
      overflow: hidden; animation: rb-slidein 0.25s ease;
    }
    @media (max-width: 420px) {
      #rb-window { width: calc(100vw - 32px); bottom: 72px; right: 0; }
    }

    /* Header */
    #rb-header {
      background: ${BRAND_DARK}; color: #fff;
      padding: 14px 16px; display: flex; align-items: center; gap: 10px;
      flex-shrink: 0;
    }
    #rb-header-avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: ${BRAND_RED}; display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0;
    }
    #rb-header-text { flex: 1; }
    #rb-header-title { font-size: 15px; font-weight: 600; margin: 0; }
    #rb-header-sub { font-size: 11px; opacity: 0.7; margin: 0; }
    #rb-close-btn {
      background: none; border: none; color: #fff; cursor: pointer;
      font-size: 20px; line-height: 1; padding: 4px; opacity: 0.8;
    }
    #rb-close-btn:hover { opacity: 1; }

    /* Messages */
    #rb-messages {
      flex: 1; overflow-y: auto; padding: 16px;
      display: flex; flex-direction: column; gap: 10px;
    }
    #rb-messages::-webkit-scrollbar { width: 4px; }
    #rb-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }

    .rb-msg { max-width: 82%; word-wrap: break-word; line-height: 1.45; font-size: 14px; }
    .rb-msg.bot {
      align-self: flex-start; background: #f1f1f1; color: ${BRAND_DARK};
      padding: 10px 13px; border-radius: 4px 16px 16px 16px;
    }
    .rb-msg.user {
      align-self: flex-end; background: ${BRAND_DARK}; color: #fff;
      padding: 10px 13px; border-radius: 16px 4px 16px 16px;
    }
    .rb-msg a { color: ${BRAND_RED}; }
    .rb-msg.bot a { color: ${BRAND_RED}; }
    .rb-msg.user a { color: #fff; text-decoration: underline; }

    /* Typing indicator */
    #rb-typing { align-self: flex-start; padding: 10px 14px; background: #f1f1f1; border-radius: 4px 16px 16px 16px; display: none; }
    #rb-typing span { display: inline-block; width: 7px; height: 7px; background: #aaa; border-radius: 50%; margin: 0 2px; animation: rb-bounce 1.2s infinite; }
    #rb-typing span:nth-child(2) { animation-delay: 0.2s; }
    #rb-typing span:nth-child(3) { animation-delay: 0.4s; }

    /* Info form */
    #rb-info-form { padding: 14px 16px; flex-shrink: 0; border-top: 1px solid #eee; background: #fafafa; }
    #rb-info-form p { font-size: 13px; color: #555; margin: 0 0 10px; }
    #rb-info-form input {
      width: 100%; border: 1px solid #ddd; border-radius: 8px;
      padding: 9px 12px; font-size: 14px; margin-bottom: 8px; outline: none;
    }
    #rb-info-form input:focus { border-color: ${BRAND_DARK}; }
    #rb-info-submit {
      width: 100%; background: ${BRAND_DARK}; color: #fff; border: none;
      border-radius: 8px; padding: 10px; font-size: 14px; cursor: pointer;
      transition: background 0.2s;
    }
    #rb-info-submit:hover { background: ${BRAND_RED}; }

    /* Input bar */
    #rb-input-bar {
      display: flex; gap: 8px; padding: 12px 14px;
      border-top: 1px solid #eee; flex-shrink: 0;
    }
    #rb-input {
      flex: 1; border: 1px solid #ddd; border-radius: 20px;
      padding: 9px 14px; font-size: 14px; outline: none; resize: none;
    }
    #rb-input:focus { border-color: ${BRAND_DARK}; }
    #rb-send {
      background: ${BRAND_DARK}; color: #fff; border: none;
      border-radius: 50%; width: 38px; height: 38px; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; transition: background 0.2s;
    }
    #rb-send:hover { background: ${BRAND_RED}; }
    #rb-send svg { width: 18px; height: 18px; fill: #fff; }
    #rb-send:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Powered-by */
    #rb-powered { text-align: center; font-size: 10px; color: #bbb; padding: 4px 0 8px; flex-shrink: 0; }

    /* Animations */
    @keyframes rb-fadein { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes rb-slidein { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes rb-bounce { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-5px); } }
  `;

  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ── BUILD DOM ──────────────────────────────────────────────────────────────
  const wrapper = document.createElement('div');
  wrapper.id = 'rb-chat-wrapper';
  wrapper.innerHTML = `
    <!-- Greeting bubble -->
    <div id="rb-greeting" style="display:none">How can we help? 💬</div>

    <!-- Chat window -->
    <div id="rb-window" style="display:none">
      <div id="rb-header">
        <div id="rb-header-avatar">🚲</div>
        <div id="rb-header-text">
          <p id="rb-header-title">Rambo Bikes Support</p>
          <p id="rb-header-sub">Typically replies instantly</p>
        </div>
        <button id="rb-close-btn" aria-label="Close chat">✕</button>
      </div>

      <div id="rb-messages">
        <!-- welcome message injected on open -->
      </div>
      <div id="rb-typing"><span></span><span></span><span></span></div>

      <!-- Info collection form (shown before first message) -->
      <div id="rb-info-form" style="display:none">
        <p>Before we get started — what's your name and email?</p>
        <input id="rb-name-input"  type="text"  placeholder="First name" />
        <input id="rb-email-input" type="email" placeholder="Email address" />
        <button id="rb-info-submit">Start chat →</button>
      </div>

      <!-- Message input (shown after info collected) -->
      <div id="rb-input-bar" style="display:none">
        <input id="rb-input" type="text" placeholder="Type a message..." autocomplete="off" />
        <button id="rb-send" aria-label="Send">
          <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
        </button>
      </div>

      <div id="rb-powered">Powered by Rambo Bikes AI</div>
    </div>

    <!-- Launcher button -->
    <button id="rb-launcher" aria-label="Open chat">
      <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
    </button>
  `;
  document.body.appendChild(wrapper);

  // ── ELEMENT REFS ───────────────────────────────────────────────────────────
  const greeting   = document.getElementById('rb-greeting');
  const launcher   = document.getElementById('rb-launcher');
  const chatWindow = document.getElementById('rb-window');
  const messages   = document.getElementById('rb-messages');
  const typing     = document.getElementById('rb-typing');
  const infoForm   = document.getElementById('rb-info-form');
  const nameInput  = document.getElementById('rb-name-input');
  const emailInput = document.getElementById('rb-email-input');
  const infoSubmit = document.getElementById('rb-info-submit');
  const inputBar   = document.getElementById('rb-input-bar');
  const textInput  = document.getElementById('rb-input');
  const sendBtn    = document.getElementById('rb-send');
  const closeBtn   = document.getElementById('rb-close-btn');

  // ── HELPERS ────────────────────────────────────────────────────────────────
  function addMessage(text, role) {
    const div = document.createElement('div');
    div.className = `rb-msg ${role}`;
    // linkify URLs
    div.innerHTML = text.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function showTyping() { typing.style.display = 'block'; messages.scrollTop = messages.scrollHeight; }
  function hideTyping() { typing.style.display = 'none'; }

  function openChat() {
    isOpen = true;
    chatWindow.style.display = 'flex';
    greeting.style.display   = 'none';
    launcher.innerHTML = `<svg viewBox="0 0 24 24" fill="white" width="24" height="24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;

    if (messages.children.length === 0) {
      addMessage("👋 Hey there! I'm the Rambo Bikes virtual assistant. I can help with troubleshooting, parts, order status, registration, and more. What can I help you with today?", 'bot');
    }

    if (!infoCollected) {
      infoForm.style.display = 'block';
      inputBar.style.display = 'none';
      setTimeout(() => nameInput.focus(), 100);
    } else {
      infoForm.style.display = 'none';
      inputBar.style.display = 'flex';
      setTimeout(() => textInput.focus(), 100);
    }
  }

  function closeChat() {
    isOpen = false;
    chatWindow.style.display = 'none';
    launcher.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>`;
  }

  async function sendMessage(text) {
    if (!text.trim() || sendBtn.disabled) return;

    addMessage(text, 'user');
    textInput.value = '';
    sendBtn.disabled = true;
    showTyping();

    try {
      const res = await fetch(CHAT_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message:        text,
          history:        history,
          customer_name:  customerName,
          customer_email: customerEmail
        })
      });

      const data = await res.json();
      hideTyping();

      if (data.message) {
        addMessage(data.message, 'bot');
        history = data.history || history;
      }

      // If escalated and case created, show confirmation
      if (data.escalate && data.case_created?.success) {
        addMessage(`✅ I've created a support case for you. Our team will follow up at ${customerEmail}. You can also call (952) 283-0777 Mon-Fri 8:30am-4:30pm CST.`, 'bot');
      }

    } catch (err) {
      hideTyping();
      addMessage("I'm having trouble connecting. Please call (952) 283-0777 or email cs@rambobikes.com.", 'bot');
    }

    sendBtn.disabled = false;
    textInput.focus();
  }

  // ── EVENT LISTENERS ────────────────────────────────────────────────────────
  launcher.addEventListener('click', () => isOpen ? closeChat() : openChat());
  closeBtn.addEventListener('click', closeChat);
  greeting.addEventListener('click', openChat);

  sendBtn.addEventListener('click', () => sendMessage(textInput.value));
  textInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(textInput.value); }
  });

  infoSubmit.addEventListener('click', () => {
    const name  = nameInput.value.trim();
    const email = emailInput.value.trim();
    const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

    if (!name)         { nameInput.style.borderColor  = BRAND_RED; nameInput.focus();  return; }
    if (!emailValid)   { emailInput.style.borderColor = BRAND_RED; emailInput.focus(); return; }

    customerName  = name;
    customerEmail = email;
    infoCollected = true;

    infoForm.style.display = 'none';
    inputBar.style.display = 'flex';

    addMessage(`Thanks, ${name}! What can I help you with today?`, 'bot');
    setTimeout(() => textInput.focus(), 100);
  });

  nameInput.addEventListener('input',  () => nameInput.style.borderColor  = '');
  emailInput.addEventListener('input', () => emailInput.style.borderColor = '');

  // ── GREETING SEQUENCE (5s → show → 3s → hide to icon) ────────────────────
  setTimeout(() => {
    if (!isOpen && !hasGreeted) {
      greeting.style.display = 'block';
      hasGreeted = true;
      setTimeout(() => {
        if (!isOpen) greeting.style.display = 'none';
      }, GREETING_TTL);
    }
  }, GREETING_DELAY);

})();
