const widgetToggleBtn = document.getElementById('global-chat-toggle');
const widgetContainer = document.getElementById('global-chat-widget');
const widgetCloseBtn = document.getElementById('global-chat-close');
const widgetForm = document.getElementById('global-chat-form');
const widgetInput = document.getElementById('global-chat-input');
const widgetMessagesBox = document.getElementById('global-chat-messages');

const pageChatBox = document.getElementById('chat-box');
const pageChatForm = document.getElementById('chat-form');
const pageChatInput = document.getElementById('chat-input');

const isAuth = document.body.dataset.userAuthenticated === 'true';
const currentUserId = Number(document.body.dataset.userId || '0');

let socket = null;
let messagesCache = [];

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMessages(boxElement, messages) {
    if (!boxElement) return;

    boxElement.innerHTML = '';
    if (!messages.length) {
        boxElement.innerHTML = '<div class="chat-empty">هنوز پیامی وجود ندارد. سلام کنید! 👋</div>';
        return;
    }

    messages.forEach((msg) => {
        const div = document.createElement('div');
        div.className = 'chat-message ' + (msg.is_admin ? 'from-admin' : 'from-user');
        div.innerHTML = `
            <div class="chat-message-meta">
                <span class="chat-sender">${msg.sender}</span>
                <span class="chat-time">${msg.created_at}</span>
            </div>
            <div class="chat-message-text">${escapeHtml(msg.text)}</div>
        `;
        boxElement.appendChild(div);
    });

    boxElement.scrollTop = boxElement.scrollHeight;
}

function renderAllMessages(messages) {
    renderMessages(widgetMessagesBox, messages);
    renderMessages(pageChatBox, messages);
}

function setMessages(messages) {
    messagesCache = Array.isArray(messages) ? [...messages] : [];
    renderAllMessages(messagesCache);
}

function upsertMessage(message) {
    if (!message || !message.id) return;
    if (!Array.isArray(messagesCache)) {
        messagesCache = [];
    }
    const exists = messagesCache.some((m) => m.id === message.id);
    if (!exists) {
        messagesCache.push(message);
        messagesCache.sort((a, b) => a.id - b.id);
    } else {
        messagesCache = messagesCache.map((m) => (m.id === message.id ? message : m));
    }
    renderAllMessages(messagesCache);
}

function loadMessages() {
    if (!isAuth) return;
    fetch('/chat/messages/')
        .then((res) => res.json())
        .then((data) => {
            if (data.messages) {
                setMessages(data.messages);
            }
        })
        .catch((err) => console.error('خطا در دریافت پیام‌ها:', err));
}

function handleIncomingMessage(msg) {
    upsertMessage(msg);
    if (msg && msg.is_admin) {
        const widgetHidden = widgetContainer && widgetContainer.classList.contains('hidden');
        const notOnPage = !pageChatBox;
        if (widgetHidden && notOnPage) {
            showNotification('پیام جدید پشتیبانی دریافت شد');
        }
        loadMessages(); // mark admin messages as read on the server
    }
}

function initSocket() {
    if (!isAuth || socket) return;
    if (typeof io === 'undefined') {
        console.error('Socket.IO script not loaded');
        return;
    }

    socket = io({ withCredentials: true });

    socket.on('connect', () => {
        loadMessages();
    });

    socket.on('chat_message', (msg) => {
        handleIncomingMessage(msg);
    });

    socket.on('connect_error', (err) => {
        console.error('Socket.IO connection error:', err);
    });

    socket.connect();
}

function sendMessage(text, btnElement, inputElement) {
    if (!text) return;
    if (!socket || !socket.connected) {
        alert('اتصال به سرور چت برقرار نیست. لطفا دوباره تلاش کنید.');
        return;
    }

    const originalText = btnElement.textContent;
    btnElement.disabled = true;
    btnElement.textContent = '...';

    const emitter = socket.timeout ? socket.timeout(5000) : socket;
    emitter.emit('send_message', { room_user_id: currentUserId, message: text }, (err, res) => {
        if (err || !res || res.status !== 'ok') {
            alert('ارسال پیام انجام نشد. لطفا دوباره تلاش کنید.');
        } else {
            inputElement.value = '';
            inputElement.focus();
        }
        btnElement.disabled = false;
        btnElement.textContent = originalText;
    });
}

function showNotification(msg) {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'granted') {
        new Notification('پیام جدید پشتیبانی', { body: msg });
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then((p) => {
            if (p === 'granted') {
                new Notification('پیام جدید پشتیبانی', { body: msg });
            }
        });
    }
}

function alertAuth() {
    alert('برای استفاده از چت باید وارد حساب خود شوید.');
    window.location.href = '/login/';
}

if (widgetForm) {
    widgetForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!isAuth) return alertAuth();
        const text = (widgetInput.value || '').trim();
        const btn = widgetForm.querySelector('button');
        sendMessage(text, btn, widgetInput);
    });
}

if (pageChatForm) {
    pageChatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!isAuth) return alertAuth();
        const text = (pageChatInput.value || '').trim();
        const btn = pageChatForm.querySelector('button');
        sendMessage(text, btn, pageChatInput);
    });
}

if (widgetToggleBtn) {
    widgetToggleBtn.addEventListener('click', () => {
        if (!isAuth) return alertAuth();
        widgetContainer.classList.remove('hidden');
        widgetToggleBtn.classList.add('hidden');
        loadMessages();
        if (widgetInput) widgetInput.focus();
    });
}

if (widgetCloseBtn) {
    widgetCloseBtn.addEventListener('click', () => {
        widgetContainer.classList.add('hidden');
        widgetToggleBtn.classList.remove('hidden');
    });
}

if (isAuth) {
    initSocket();
}

window.addEventListener('beforeunload', () => {
    if (socket) {
        socket.close();
    }
});
