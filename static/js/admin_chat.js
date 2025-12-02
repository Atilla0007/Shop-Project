// Admin chat polling + send

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('csrftoken');

const box = document.getElementById('admin-chat-box');
const form = document.getElementById('admin-chat-form');
const input = document.getElementById('admin-chat-input');
const quickReplies = document.querySelectorAll('.quick-reply');
const userId = box ? parseInt(box.getAttribute('data-user-id') || '', 10) : null;

let pollTimer = null;
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

function startPolling() {
    loadAdminMessages();
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(loadAdminMessages, 3000);
}

function sendMessage() {
    const text = (input.value || '').trim();
    if (!text || !userId) return;
    const submitBtn = form.querySelector('button[type=\"submit\"]');
    const original = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '...';

    const formData = new FormData();
    formData.append('message', text);

    fetch(`/admin-chat/${userId}/send/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        body: formData,
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.status === 'ok') {
                input.value = '';
                loadAdminMessages();
            } else {
                alert('ارسال پیام انجام نشد.');
            }
        })
        .catch((err) => {
            console.error(err);
            alert('خطا در ارسال پیام.');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = original;
        });
}

if (userId) {
    startPolling();
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
    if (pollTimer) clearInterval(pollTimer);
});
