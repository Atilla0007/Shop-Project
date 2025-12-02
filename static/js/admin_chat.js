const box = document.getElementById('admin-chat-box');
const form = document.getElementById('admin-chat-form');
const input = document.getElementById('admin-chat-input');
const quickReplies = document.querySelectorAll('.quick-reply');

const userId = box ? parseInt(box.getAttribute('data-user-id') || '', 10) : null;

let socket = null;
let messagesCache = [];

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMessages(messages) {
    if (!box) return;

    box.innerHTML = '';
    if (!messages.length) {
        box.innerHTML = '<div class="chat-empty">هنوز پیامی وجود ندارد.</div>';
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
        box.appendChild(div);
    });

    box.scrollTop = box.scrollHeight;
}

function setMessages(messages) {
    messagesCache = Array.isArray(messages) ? [...messages] : [];
    renderMessages(messagesCache);
}

function upsertMessage(message) {
    if (!message || !message.id) return;
    const exists = messagesCache.some((m) => m.id === message.id);
    if (!exists) {
        messagesCache.push(message);
        messagesCache.sort((a, b) => a.id - b.id);
    } else {
        messagesCache = messagesCache.map((m) => (m.id === message.id ? message : m));
    }
    renderMessages(messagesCache);
}

function loadAdminMessages() {
    if (!userId) return;
    fetch(`/admin-chat/${userId}/messages/`)
        .then((res) => res.json())
        .then((data) => {
            if (data.messages) {
                setMessages(data.messages);
            }
        })
        .catch((err) => console.error('خطا در دریافت پیام‌ها:', err));
}

function initSocket() {
    if (!userId || socket) return;
    if (typeof io === 'undefined') {
        console.error('Socket.IO script not loaded');
        return;
    }

    socket = io({ withCredentials: true });

    socket.on('connect', () => {
        socket.emit('join_room', { room_user_id: userId }, (res) => {
            if (res && res.status === 'error') {
                console.error('عدم دسترسی به اتاق چت کاربر', res);
            }
        });
        loadAdminMessages();
    });

    socket.on('chat_message', (msg) => {
        upsertMessage(msg);
        if (msg && !msg.is_admin) {
            loadAdminMessages(); // marks user messages as read_by_admin
        }
    });

    socket.on('connect_error', (err) => {
        console.error('Socket.IO connection error:', err);
    });

    socket.connect();
}

function sendMessage() {
    const text = (input.value || '').trim();
    if (!text || !socket || !socket.connected) return;

    const submitBtn = form.querySelector('button[type="submit"]');
    const original = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '...';

    const emitter = socket.timeout ? socket.timeout(5000) : socket;
    emitter.emit('send_message', { room_user_id: userId, message: text }, (err, res) => {
        if (err || !res || res.status !== 'ok') {
            alert('ارسال پیام انجام نشد. دوباره تلاش کنید.');
        } else {
            input.value = '';
            input.focus();
        }
        submitBtn.disabled = false;
        submitBtn.textContent = original;
    });
}

if (userId) {
    loadAdminMessages();
    initSocket();

    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            sendMessage();
        });
    }

    quickReplies.forEach((btn) => {
        btn.addEventListener('click', function () {
            input.value = this.textContent;
            input.focus();
        });
    });
}

window.addEventListener('beforeunload', () => {
    if (socket) socket.close();
});
