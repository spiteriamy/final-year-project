
// -----------------------------------------------------------------------------------------------
// session id - persists across reloads and new chats for the whole evaluation

const SESSION_KEY = 'talk2melatin_session_id';

function getOrCreateSessionId() {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
        id = (crypto.randomUUID && crypto.randomUUID()) ||
             // fallback for older browsers
             'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                 const r = Math.random() * 16 | 0;
                 const v = c === 'x' ? r : (r & 0x3 | 0x8);
                 return v.toString(16);
             });
        localStorage.setItem(SESSION_KEY, id);
    }
    return id;
}

const SESSION_ID = getOrCreateSessionId();


// -----------------------------------------------------------------------------------------------
// CHAT SESSION MANAGEMENT

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

// Derive the current chat ID from the URL; create one if absent
const urlParams = new URLSearchParams(window.location.search);
let currentChatId = urlParams.get('chat');

if (!currentChatId) {
  currentChatId = generateId();
  window.history.replaceState({}, '', `?chat=${currentChatId}`);
}

function getAllChats() {
  try { return JSON.parse(localStorage.getItem('chats') || '[]'); }
  catch { return []; }
}

function saveAllChats(chats) {
  localStorage.setItem('chats', JSON.stringify(chats));
}

function ensureChatExists() {
  const chats = getAllChats();
  if (!chats.find(c => c.id === currentChatId)) {
    chats.unshift({ id: currentChatId, title: 'New Chat', createdAt: Date.now() });
    saveAllChats(chats);
    return true; // newly registered
  }
  return false;
}

// Called after the first user message to give the chat a meaningful title
function updateChatTitle(firstMessage) {
  const chats = getAllChats();
  const chat = chats.find(c => c.id === currentChatId);
  if (chat && chat.title === 'New Chat') {
    chat.title = firstMessage.substring(0, 35) + (firstMessage.length > 35 ? '…' : '');
    saveAllChats(chats);
    renderSidebarChats();
  }
}

// Disabled: delete functionality removed.
/*
function deleteChat(chatId) {
  // Remove messages
  localStorage.removeItem(`chat_${chatId}`);

  // Remove from chats list
  const chats = getAllChats().filter(c => c.id !== chatId);
  saveAllChats(chats);

  // If deleting the active chat, navigate to the next available one (or fresh page)
  if (chatId === currentChatId) {
    if (chats.length > 0) {
      window.location.href = `?chat=${chats[0].id}`;
    } else {
      window.location.href = window.location.pathname;
    }
  } else {
    renderSidebarChats();
  }
}
*/

function renderSidebarChats() {
  const listEl = document.getElementById('chat-list');
  if (!listEl) return;

  const chats = getAllChats();

  if (chats.length === 0) {
    listEl.innerHTML = `<p class="px-3 py-2 text-[11px] text-outline italic">No conversations yet.</p>`;
    return;
  }

  listEl.innerHTML = chats.map(chat => {
    const isActive = chat.id === currentChatId;
    return `
      <div class="chat-list-item relative flex items-center rounded-md transition-colors group/item ${isActive
        ? 'text-zinc-100 dark:text-[#c6c6c7] font-semibold bg-zinc-800 dark:bg-[#19191d]'
        : 'text-zinc-500 dark:text-[#47474e] hover:bg-zinc-800/50 dark:hover:bg-[#19191d]/50'
      }">
        <a href="?chat=${chat.id}"
           class="flex items-center gap-3 px-3 py-2 flex-1 min-w-0"
           title="${chat.title}">
          <span class="material-symbols-outlined flex-shrink-0" style="font-size:18px">chat_bubble</span>
          <span class="truncate sidebar-chat-label">${chat.title}</span>
        </a>
        <!-- Disabled: delete functionality removed.
        <button
          class="chat-delete-btn flex-shrink-0 mr-2 p-0.5 rounded opacity-0 group-hover/item:opacity-100 transition-opacity hover:text-error"
          title="Delete chat"
          data-id="${chat.id}">
          <span class="material-symbols-outlined" style="font-size:16px">close</span>
        </button>
        -->
      </div>`;
  }).join('');

  // Disabled: delete functionality removed.
  /*
  // Attach delete listeners
  listEl.querySelectorAll('.chat-delete-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      const id = btn.dataset.id;
      const chat = getAllChats().find(c => c.id === id);
      const label = chat ? `"${chat.title}"` : 'this chat';
      if (confirm(`Delete ${label}? This cannot be undone.`)) {
        deleteChat(id);
      }
    });
  });
  */
}


// -----------------------------------------------------------------------------------------------
// THEME TOGGLE
// Theme toggle disabled: light theme only.

// const themeToggleBtn = document.getElementById('theme-toggle');
// const themeIcon = document.getElementById('theme-icon');
// const htmlElement = document.documentElement;

// themeToggleBtn.addEventListener('click', () => {
//   if (htmlElement.classList.contains('dark')) {
//     htmlElement.classList.remove('dark');
//     themeIcon.textContent = 'dark_mode';
//     localStorage.setItem('theme', 'light');
//   } else {
//     htmlElement.classList.add('dark');
//     themeIcon.textContent = 'light_mode';
//     localStorage.setItem('theme', 'dark');
//   }
// });


// -----------------------------------------------------------------------------------------------
// SIDEBAR

const sidebar = document.getElementById('sidebar');
const collapseBtn = document.getElementById('collapse-sidebar');
const expandBtn = document.getElementById('expand-sidebar');
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const mobileBackdrop = document.getElementById('mobile-drawer-backdrop');

// Sidebar collapsed-state persistence.
// Default: collapsed on first visit. After that, respect the user's last choice.
const SIDEBAR_STATE_KEY = 'sidebar_collapsed';
const stored = localStorage.getItem(SIDEBAR_STATE_KEY);
const startCollapsed = stored === null ? true : stored === 'true';

if (startCollapsed) {
  sidebar.classList.add('collapsed');
  if (window.innerWidth >= 768) expandBtn.classList.remove('hidden');
} else {
  sidebar.classList.remove('collapsed');
  expandBtn.classList.add('hidden');
}

// Desktop collapse/expand
collapseBtn.addEventListener('click', () => {
  sidebar.classList.add('collapsed');
  expandBtn.classList.remove('hidden');
  localStorage.setItem(SIDEBAR_STATE_KEY, 'true');
});

expandBtn.addEventListener('click', () => {
  sidebar.classList.remove('collapsed');
  expandBtn.classList.add('hidden');
  localStorage.setItem(SIDEBAR_STATE_KEY, 'false');
});

// -----------------------------------------------------------------------------------------------
// MOBILE DRAWER

function openMobileDrawer() {
  sidebar.classList.add('mobile-open');
  mobileBackdrop.classList.add('active');
  document.body.style.overflow = 'hidden';

  // Close the feedback sheet if it's expanded, so the two don't fight
  const panel = document.getElementById('survey-panel');
  if (panel && panel.dataset.state !== 'peek') {
    panel.dataset.state = 'peek';
    document.getElementById('sheet-backdrop')?.classList.remove('active');
  }
}

function closeMobileDrawer() {
  sidebar.classList.remove('mobile-open');
  mobileBackdrop.classList.remove('active');
  document.body.style.overflow = '';
}

if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener('click', openMobileDrawer);
}

if (mobileBackdrop) {
  mobileBackdrop.addEventListener('click', closeMobileDrawer);
  mobileBackdrop.addEventListener('touchstart', closeMobileDrawer, { passive: true });
}

// Close button inside the drawer (mobile only)
const mobileDrawerClose = document.getElementById('mobile-drawer-close');
if (mobileDrawerClose) {
  mobileDrawerClose.addEventListener('click', closeMobileDrawer);
  mobileDrawerClose.addEventListener('touchstart', closeMobileDrawer, { passive: true });
}

// Close drawer when a chat is selected on mobile
document.addEventListener('click', e => {
  const link = e.target.closest('#chat-list a');
  if (link && window.innerWidth < 768) closeMobileDrawer();
});

// New Chat — create a fresh entry and open it
document.getElementById('new-chat-btn').addEventListener('click', () => {
  const newId = generateId();
  window.open(`?chat=${newId}`, '_self');
  // On mobile, also collapse the drawer
  if (window.innerWidth < 768) closeMobileDrawer();
});


// -----------------------------------------------------------------------------------------------
// CHAT FUNCTIONALITY

const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const chatScroll = document.getElementById('chat-scroll');

// Helper: get current time
function getTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addMessage(role, text) {
  // create and display a new message in the chat area
  const wrapper = document.createElement('div');

  if (role === 'user') {
    wrapper.className = 'flex justify-end gap-6 group';

    wrapper.innerHTML = `
      <div class="w-fit max-w-[85%] sm:max-w-[70%] ml-auto bg-surface-container-highest p-6 md:p-8 rounded-xl">
        <div class="flex items-center justify-end gap-3 mb-4">
          <span class="text-[10px] text-outline">${getTime()}</span>
          <span class="text-[10px] font-bold uppercase tracking-[0.2em] text-on-surface-variant">User</span>
        </div>
        <div class="text-on-surface leading-relaxed text-lg">${text}</div>
      </div>`;
  } else {
    wrapper.className = 'flex gap-6 group';

    wrapper.innerHTML = `
      <div class="hidden sm:flex flex-shrink-0 w-10 h-10 rounded-lg bg-surface-container-high items-center justify-center mt-1">
        <span class="material-symbols-outlined text-primary text-xl">smart_toy</span>
      </div>
      <div class="flex-1 bg-surface-container-low p-6 md:p-8 rounded-xl">
        <div class="flex items-center gap-3 mb-4">
          <span class="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">Latin Bot</span>
          <span class="text-[10px] text-outline">${getTime()}</span>
        </div>
        <div class="text-on-surface leading-relaxed text-lg">${text}</div>
      </div>`;
  }

  messagesEl.appendChild(wrapper);
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' })

  saveMessages();

  return wrapper;
}

function addTyping() {
  const wrapper = document.createElement('div');
  wrapper.className = 'flex gap-6 group';

  wrapper.innerHTML = `
    <div class="hidden sm:flex flex-shrink-0 w-10 h-10 rounded-lg bg-surface-container-high items-center justify-center mt-1">
      <span class="material-symbols-outlined text-primary text-xl">smart_toy</span>
    </div>
    <div class="flex-1 bg-surface-container-low p-6 md:p-8 rounded-xl">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">Latin Bot</span>
      </div>
      <div class="flex gap-2">
        <div class="w-2 h-2 bg-primary rounded-full animate-bounce"></div>
        <div class="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:0.2s]"></div>
        <div class="w-2 h-2 bg-primary rounded-full animate-bounce [animation-delay:0.4s]"></div>
      </div>
    </div>`;

  messagesEl.appendChild(wrapper);
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' })

  return wrapper;
}

// Tracks whether the first user message has been sent in this session
let isFirstMessage = true;

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';
  sendBtn.disabled = true;

  // Always register the chat (idempotent). On first message, also set the title.
  const isNew = ensureChatExists();
  if (isFirstMessage) {
    updateChatTitle(text); // also calls renderSidebarChats internally
    isFirstMessage = false;
  } else if (isNew) {
    // Chat was saved before (e.g. welcome message) but never registered - sync sidebar now
    renderSidebarChats();
  }

  addMessage('user', text);
  const typingRow = addTyping();

  try {
    const res = await fetch(`${window.URL_PREFIX}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: SESSION_ID, chat_id: currentChatId })
    });
    const data = await res.json();
    typingRow.remove();
    addMessage('bot', data.response || data.error || 'No response.');
  } catch (err) {
    typingRow.remove();
    addMessage('bot', 'Connection error.');
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

// Auto-grow textarea
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
});

// Enter to send
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// button click
sendBtn.addEventListener('click', sendMessage);


// -----------------------------------------------------------------------------------------------
// MESSAGE PERSISTENCE (per-chat)

function saveMessages() {
  localStorage.setItem(`chat_${currentChatId}`, messagesEl.innerHTML);
}

function loadMessages() {
  const saved = localStorage.getItem(`chat_${currentChatId}`);
  if (saved) {
    messagesEl.innerHTML = saved;
    return true;
  }
  return false;
}


// -----------------------------------------------------------------------------------------------
// SHARE / EXPORT MODAL

function buildExportData() {
  const chats = getAllChats();
  const meta = chats.find(c => c.id === currentChatId);

  // Parse messages out of the DOM
  const messages = [];
  messagesEl.querySelectorAll('.flex.justify-end.gap-6.group, .flex.gap-6.group').forEach(el => {
    const isUser = el.classList.contains('justify-end');
    const role = isUser ? 'user' : 'assistant';
    const textEl = el.querySelector('.text-on-surface.leading-relaxed');
    const timeEl = el.querySelector('.text-\\[10px\\].text-outline');
    if (textEl) {
      messages.push({
        role,
        content: textEl.textContent.trim(),
        time: timeEl ? timeEl.textContent.trim() : null,
      });
    }
  });

  return {
    id: currentChatId,
    title: meta?.title ?? 'Untitled Chat',
    createdAt: meta?.createdAt ? new Date(meta.createdAt).toISOString() : null,
    exportedAt: new Date().toISOString(),
    messages,
  };
}

function openShareModal() {
  const data = buildExportData();

  // Populate preview fields
  document.getElementById('export-chat-title').textContent = data.title;
  document.getElementById('export-message-count').textContent = `${data.messages.length} message${data.messages.length !== 1 ? 's' : ''}`;
  document.getElementById('export-date').textContent =
    data.createdAt ? new Date(data.createdAt).toLocaleDateString(undefined, { dateStyle: 'medium' }) : 'Unknown date';

  document.getElementById('share-modal').classList.remove('hidden');
}

function closeShareModal() {
  document.getElementById('share-modal').classList.add('hidden');
}

function downloadJSON() {
  const data = buildExportData();
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const filename = data.title.replace(/[^a-z0-9]/gi, '_').toLowerCase().substring(0, 40) + '.json';

  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);

  closeShareModal();
}

// Wire up share button (header)
document.getElementById('share-btn').addEventListener('click', openShareModal);

document.getElementById('share-modal-close').addEventListener('click', closeShareModal);
document.getElementById('share-modal-cancel').addEventListener('click', closeShareModal);
document.getElementById('share-modal-download').addEventListener('click', downloadJSON);
document.getElementById('share-backdrop').addEventListener('click', closeShareModal);


document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeShareModal();
    // Disabled: more menu removed.
    // moreMenu.classList.add('hidden');
  }
});



// -----------------------------------------------------------------------------------------------
// MORE OPTIONS MENU
// Disabled: rename/delete functionality removed.

/*
const moreBtn = document.getElementById('more-btn');
const moreMenu = document.getElementById('more-menu');

moreBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  moreMenu.classList.toggle('hidden');
});

// Close menu when clicking anywhere else
document.addEventListener('click', () => {
  moreMenu.classList.add('hidden');
});

// Prevent clicks inside menu from closing it prematurely
moreMenu.addEventListener('click', (e) => {
  e.stopPropagation();
});

// Rename chat
document.getElementById('menu-rename').addEventListener('click', () => {
  moreMenu.classList.add('hidden');

  const chats = getAllChats();
  const chat = chats.find(c => c.id === currentChatId);
  const currentTitle = chat ? chat.title : 'New Chat';

  const newTitle = prompt('Rename this chat:', currentTitle);
  if (newTitle !== null && newTitle.trim() !== '') {
    chat.title = newTitle.trim();
    saveAllChats(chats);
    renderSidebarChats();
  }
});

// Delete chat
document.getElementById('menu-delete').addEventListener('click', () => {
  moreMenu.classList.add('hidden');

  const chat = getAllChats().find(c => c.id === currentChatId);
  const label = chat ? `"${chat.title}"` : 'this chat';
  if (confirm(`Delete ${label}? This cannot be undone.`)) {
    deleteChat(currentChatId);
  }
});
*/



// -----------------------------------------------------------------------------------------------
// INIT

window.addEventListener('load', () => {
  // Theme toggle disabled: light theme only.
  // // Sync icon to the theme that was applied by the inline script
  // themeIcon.textContent = htmlElement.classList.contains('dark') ? 'light_mode' : 'dark_mode';

  renderSidebarChats();

  const hasMessages = loadMessages();
  if (hasMessages) {
    // Existing chat - first message already sent previously
    isFirstMessage = false;

    // Scroll to bottom to show latest message
    requestAnimationFrame(() => {
      const chatScroll = document.getElementById('chat-scroll');
      chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' })
    });
  } else {
    addMessage('bot', "Welcome. Ask me something about Latin grammar.");
  }
});

