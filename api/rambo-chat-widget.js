/**
 * Rambo Bikes Chat Widget
 * Embed in Shopify: Online Store → Themes → Edit Code → theme.liquid → paste before </body>
 * Update CHAT_API_URL below after deploying the backend to Vercel.
 */

(function () {
  'use strict';

  // ── CONFIG ─────────────────────────────────────────────────────────────────
  const CHAT_API_URL   = 'https://rambo-chat-backend.vercel.app/api/chat';
  const BRAND_DARK     = '#1b1b1b';
  const BRAND_RED      = '#cc0000';
  const GREETING_DELAY = 5000;   // ms before greeting appears
  const GREETING_TTL   = 6000;   // ms greeting stays before collapsing to icon

  // ── STATE ──────────────────────────────────────────────────────────────────
  let history           = [];
  let caseSent          = false;   // one case per session max
  let customerName      = '';
  let customerEmail     = '';
  let pendingEscalation = false;
  let pendingEscalateTo = null;
  let pendingCaseTitle  = null;
  let isOpen        = false;
  let hasGreeted    = false;
  let infoCollected = false;  // show name/email form before chat — required for case creation

  // ── INJECT CSS ─────────────────────────────────────────────────────────────
  const css = `
    #rb-chat-wrapper * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    #rb-chat-wrapper { position: fixed; bottom: 24px; right: 24px; z-index: 99999; }

    /* Greeting bubble */
    #rb-greeting {
      position: absolute; bottom: 68px; right: 0;
      background: #fff; color: ${BRAND_DARK};
      padding: 10px 16px; border-radius: 20px 20px 4px 20px;
      font-size: 13px; font-weight: 600; white-space: normal; width: 280px; max-width: calc(100vw - 76px); line-height: 1.45;
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
      background: #ffffff; display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0; padding: 3px;
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
    .rb-msg a { color: ${BRAND_RED}; pointer-events: auto !important;
                 cursor: pointer !important; text-decoration: underline; }
    .rb-msg.bot a { color: ${BRAND_RED}; pointer-events: auto !important; cursor: pointer !important; }
    .rb-msg.user a { color: #fff; pointer-events: auto !important; cursor: pointer !important; }
    .rb-msg.bot a { color: ${BRAND_RED}; }
    .rb-msg.user a { color: #fff; text-decoration: underline; }

    /* Typing indicator */
    #rb-typing { align-self: flex-start; padding: 10px 14px; background: #f1f1f1; border-radius: 4px 16px 16px 16px; display: none; }
    #rb-typing span { display: inline-block; width: 7px; height: 7px; background: #aaa; border-radius: 50%; margin: 0 2px; animation: rb-bounce 1.2s infinite; }
    #rb-typing span:nth-child(2) { animation-delay: 0.2s; }
    #rb-typing span:nth-child(3) { animation-delay: 0.4s; }

    /* Info form — hidden, info collected conversationally */
    #rb-info-form { display: none !important; }

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

  // === BLOCK CONTIVIO CHAT COMPLETELY ===
  // Override Contivio's startup functions so their chat never initializes
  window.ContivioInitChatTimer = function() {};
  window.ContivioSlidePopup    = function() {};
  window.ContivioStartChat     = function() {};
  window.ContivioInit          = function() {};

  // Also nuke any existing elements immediately and via interval
  const killContivio = () => {
    ['livechatbutton','ContivioCustomData','ContivioForm'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.remove();
    });
    document.querySelectorAll('iframe, div').forEach(el => {
      const src  = el.src || '';
      const id   = el.id  || '';
      if (src.includes('contivio') || src.includes('uschat4') ||
          id.includes('Contivio')  || id.includes('livechat')) {
        el.remove();
      }
    });
  };
  killContivio();
  // Run for 30 seconds every 500ms — catches any delayed Contivio load
  let _ck = 0;
  const _ci = setInterval(() => {
    killContivio();
    if (++_ck > 60) clearInterval(_ci);
  }, 500);
  new MutationObserver(killContivio).observe(document.documentElement,
    {childList: true, subtree: true});

  // Suppress existing Contivio chat widget
  const contivioSuppressor = document.createElement('style');
  contivioSuppressor.textContent = `/* Hide Contivio chat widget when Rambo AI chat is active */
    #ContivioChatWidget, .contivio-chat-widget, 
    iframe[src*="contivio"], div[class*="contivio"],
    #contivio-chat-container { display: none !important; }`;
  document.head.appendChild(contivioSuppressor);

  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ── BUILD DOM ──────────────────────────────────────────────────────────────
  const wrapper = document.createElement('div');
  wrapper.id = 'rb-chat-wrapper';
  wrapper.innerHTML = `
    <!-- Greeting bubble -->
    <div id="rb-greeting" style="display:none">I'm your personal Rambo assistant! Click on me for instant chat support.</div>

    <!-- Chat window -->
    <div id="rb-window" style="display:none">
      <div id="rb-header">
        <div id="rb-header-avatar"><img src="data:image/png;base64,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" style="width:34px;height:34px;object-fit:contain;display:block;" alt="Rambo" /></div>
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
    // Linkify URLs — simple, works on all browsers including iOS Safari
    // Only match full URLs with https:// to avoid regex compatibility issues
    var linkified = text.replace(/(https?:\/\/[^\s<)"']+)/g, function(url) {
      return '<a href="' + url + '" target="_blank" rel="noopener" ' +
             'style="color:#cc0000;text-decoration:underline;cursor:pointer;">' + url + '</a>';
    });
    div.innerHTML = linkified;
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
      addMessage("👋 Hey there! I'm your personal Rambo Bikes assistant. I can help with troubleshooting, parts, order status, registration, and more. What can I help you with today?", 'bot');
    }

    if (infoCollected) {
      infoForm.style.display = 'none';
      inputBar.style.display = 'flex';
      setTimeout(() => textInput.focus(), 100);
    } else {
      infoForm.style.display = 'block';
      inputBar.style.display = 'none';
      setTimeout(() => nameInput.focus(), 100);
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
          message:              text,
          history:              history,
          customer_name:        customerName,
          customer_email:       customerEmail,
          case_already_created: caseSent,
          pending_escalation:   pendingEscalation,
          pending_escalate_to:  pendingEscalateTo,
          pending_case_title:   pendingCaseTitle
        })
      });

      const data = await res.json();
      hideTyping();

      if (data.message) {
        addMessage(data.message, 'bot');
        history = data.history || history;
      }

      // Track pending escalation for retry next turn
      if (data.pending_escalation) {
        pendingEscalation = true;
        pendingEscalateTo = data.pending_escalate_to || null;
        pendingCaseTitle  = data.pending_case_title  || null;
      }

      // Show case confirmation only once per session
      if (data.case_created?.success && !caseSent) {
        caseSent = true;
        pendingEscalation = false;
        pendingEscalateTo = null;
        pendingCaseTitle  = null;
        const followUp = customerEmail ? ` Our team will follow up at ${customerEmail}.` : "";
        addMessage(`✅ I've created a support case for you.${followUp} You can also call (952) 283-0777 Mon-Fri 8:30am-4:30pm CST.`, 'bot');
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

  // Contivio removal handled below

  // ── PAGE-AWARE GREETING — different message per page ───────────────────────
  function getPageGreeting() {
    const path = window.location.pathname.toLowerCase();
    const search = window.location.search.toLowerCase();
    if (path.includes('/products/') && !path.includes('replacement') && !path.includes('charger') && !path.includes('tube') && !path.includes('chain')) {
      return "Questions about this bike? I can help! 🚵";
    } else if (path.includes('/cart') || path.includes('checkout')) {
      return "Questions before you buy? I\'m here to help!";
    } else if (path.includes('/pages/support') || path.includes('/pages/contact') || path.includes('/pages/faq')) {
      return "Need help? I can answer most questions instantly!";
    } else if (path.includes('/collections/') || path.includes('/products/')) {
      return "Need help finding the right part? Ask me!";
    } else {
      return "I\'m your personal Rambo assistant! Click on me for instant chat support.";
    }
  }

  setTimeout(() => {
    if (!isOpen && !hasGreeted) {
      greeting.textContent = getPageGreeting();
      greeting.style.display = 'block';
      hasGreeted = true;
      setTimeout(() => {
        if (!isOpen) greeting.style.display = 'none';
      }, GREETING_TTL);
    }
  }, GREETING_DELAY);

})();
