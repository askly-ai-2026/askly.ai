document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    const sessionList = document.getElementById('session-list');
    const currentSessionTitle = document.getElementById('current-session-title');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
    const appContainer = document.querySelector('.app-container');

    let currentSessionId = null;

    // Modal system
    const modal = document.getElementById('cyber-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalInputsDiv = document.getElementById('modal-inputs');
    const modalConfirmBtn = document.getElementById('modal-confirm');
    const modalCancelBtn = document.getElementById('modal-cancel');
    const modalClose = document.getElementById('modal-close');
    let modalResolve = null;

    function showModal(options) {
        return new Promise((resolve) => {
            modalResolve = resolve;
            modalTitle.innerText = options.title || 'CONFIRM';
            modalMessage.innerText = options.message || '';
            modalInputsDiv.innerHTML = '';
            if (options.inputs) {
                options.inputs.forEach(input => {
                    const inputEl = document.createElement('input');
                    inputEl.type = input.type || 'text';
                    inputEl.placeholder = input.placeholder || '';
                    inputEl.className = 'modal-input';
                    inputEl.id = input.id || `modal-input-${Date.now()}`;
                    if (input.value) inputEl.value = input.value;
                    modalInputsDiv.appendChild(inputEl);
                });
            }
            modal.style.display = 'flex';
            const onConfirm = () => {
                cleanup();
                if (options.inputs) {
                    const values = {};
                    document.querySelectorAll('.modal-input').forEach((el, idx) => {
                        const inputDef = options.inputs[idx];
                        const key = inputDef.id || inputDef.placeholder || `field${idx}`;
                        values[key] = el.value;
                    });
                    resolve(values);
                } else {
                    resolve(true);
                }
            };
            const onCancel = () => { cleanup(); resolve(false); };
            const cleanup = () => {
                modalConfirmBtn.removeEventListener('click', onConfirm);
                modalCancelBtn.removeEventListener('click', onCancel);
                modalClose.removeEventListener('click', onCancel);
                modal.style.display = 'none';
            };
            modalConfirmBtn.addEventListener('click', onConfirm);
            modalCancelBtn.addEventListener('click', onCancel);
            modalClose.addEventListener('click', onCancel);
        });
    }

    async function confirmDialog(message, title = 'CONFIRM ACTION') {
        const result = await showModal({ title, message });
        return result === true;
    }

    async function promptDialog(message, placeholder = '', title = 'INPUT REQUIRED') {
        const result = await showModal({ title, message, inputs: [{ type: 'text', placeholder, id: 'input0' }] });
        if (result && result.input0 !== undefined) return result.input0;
        return null;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatMessageContent(text) {
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    // Add copy & speak buttons
    function addMessageActions(messageDiv, textContent) {
        const footer = document.createElement('div');
        footer.className = 'message-footer';
        const copyBtn = document.createElement('button');
        copyBtn.className = 'message-action-btn copy-btn';
        copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
        copyBtn.title = 'Copy to clipboard';
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(textContent);
            const original = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
            setTimeout(() => { copyBtn.innerHTML = original; }, 1500);
        });

        const speakBtn = document.createElement('button');
        speakBtn.className = 'message-action-btn speak-btn';
        speakBtn.innerHTML = '<i class="fas fa-volume-up"></i> Speak';
        speakBtn.title = 'Read aloud';
        let utterance = null;
        speakBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (speechSynthesis.speaking) {
                speechSynthesis.cancel();
                speakBtn.innerHTML = '<i class="fas fa-volume-up"></i> Speak';
                speakBtn.classList.remove('speaking');
                return;
            }
            utterance = new SpeechSynthesisUtterance(textContent);
            utterance.lang = 'en-US';
            utterance.onstart = () => {
                speakBtn.innerHTML = '<i class="fas fa-stop"></i> Stop';
                speakBtn.classList.add('speaking');
            };
            utterance.onend = () => {
                speakBtn.innerHTML = '<i class="fas fa-volume-up"></i> Speak';
                speakBtn.classList.remove('speaking');
            };
            speechSynthesis.speak(utterance);
        });
        footer.appendChild(copyBtn);
        footer.appendChild(speakBtn);
        messageDiv.querySelector('.message-content').appendChild(footer);
    }

    // Updated: no timestamp displayed
    function addMessageToChat(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', role);
        const avatarIcon = role === 'user' ? 'fa-user' : 'fa-robot';
        messageDiv.innerHTML = `
            <div class="message-avatar"><i class="fas ${avatarIcon}"></i></div>
            <div class="message-content">
                <div class="message-role">${role.toUpperCase()}</div>
                <div class="message-text">${formatMessageContent(content)}</div>
            </div>
        `;
        addMessageActions(messageDiv, content);
        const emptyState = chatContainer.querySelector('.empty-chat');
        if (emptyState) emptyState.remove();
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    async function sendMessage() {
        if (!navigator.onLine) { await confirmDialog('You are offline.', 'OFFLINE'); return; }
        const message = userInput.value.trim();
        if (!message) return;

        addMessageToChat('user', message);
        userInput.value = '';
        userInput.style.height = '52px';

        const typingDiv = document.createElement('div');
        typingDiv.classList.add('message', 'assistant', 'typing-indicator');
        typingDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">
                <div class="typing-dots"><span></span><span></span><span></span></div>
                <span class="thinking-text">thinking like DeepSeek, ChatGPT, Gemini...</span>
            </div>
        `;
        chatContainer.appendChild(typingDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: currentSessionId, model: 'llama-3.3-70b-versatile' })
            });
            const data = await response.json();
            typingDiv.remove();
            if (data.success) {
                addMessageToChat('assistant', data.response);
                if (!currentSessionId) {
                    currentSessionId = data.session_id;
                    loadSessions();
                    currentSessionTitle.textContent = `CHAT #${currentSessionId}`;
                }
            } else {
                addMessageToChat('assistant', `Error: ${data.error}`);
            }
        } catch (error) {
            typingDiv.remove();
            addMessageToChat('assistant', 'Network error.');
        }
    }

    async function loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            const sessions = await response.json();
            if (sessionList) {
                sessionList.innerHTML = '';
                sessions.forEach((session, index) => {
                    const li = document.createElement('li');
                    li.classList.add('session-item');
                    li.dataset.sessionId = session.id;
                    li.style.setProperty('--index', index);
                    li.innerHTML = `
                        <div class="session-title-wrapper">
                            <span class="session-title">${escapeHtml(session.title)}</span>
                            <button class="rename-session-btn" data-session-id="${session.id}" title="Rename"><i class="fas fa-pencil-alt"></i></button>
                        </div>
                        <button class="delete-session-btn" data-session-id="${session.id}"><i class="fas fa-times"></i></button>
                    `;
                    sessionList.appendChild(li);
                });
                attachSessionClickListeners();
                attachDeleteListeners();
                attachRenameListeners();
            }
        } catch (err) { console.error('Failed to load sessions:', err); }
    }

    async function loadChatHistory(sessionId) {
        try {
            const response = await fetch(`/api/sessions/${sessionId}/messages`);
            const messages = await response.json();
            chatContainer.innerHTML = '';
            if (messages.length === 0) {
                showEmptyState();
            } else {
                messages.forEach(msg => addMessageToChat(msg.role, msg.content));
            }
            const sessionTitle = document.querySelector(`.session-item[data-session-id="${sessionId}"] .session-title`)?.textContent || `CHAT #${sessionId}`;
            currentSessionTitle.textContent = sessionTitle;
        } catch (err) { console.error('Failed to load messages:', err); }
    }

    function showEmptyState() {
        chatContainer.innerHTML = `
            <div class="empty-chat">
                <i class="fas fa-comments"></i>
                <h3>No messages yet</h3>
                <p>Start a conversation with Askly AI</p>
            </div>
        `;
    }

    function attachSessionClickListeners() {
        document.querySelectorAll('.session-item').forEach(item => {
            item.removeEventListener('click', item._clickHandler);
            const handler = (e) => {
                if (e.target.closest('.delete-session-btn') || e.target.closest('.rename-session-btn')) return;
                currentSessionId = item.dataset.sessionId;
                document.querySelectorAll('.session-item').forEach(s => s.classList.remove('active'));
                item.classList.add('active');
                loadChatHistory(currentSessionId);
            };
            item._clickHandler = handler;
            item.addEventListener('click', handler);
        });
    }

    async function attachDeleteListeners() {
        for (const btn of document.querySelectorAll('.delete-session-btn')) {
            btn.removeEventListener('click', btn._listener);
            const handler = async (e) => {
                e.stopPropagation();
                const sessionId = btn.dataset.sessionId;
                if (await confirmDialog('Delete this chat session?')) {
                    await fetch(`/api/sessions?session_id=${sessionId}`, { method: 'DELETE' });
                    await loadSessions();
                    if (currentSessionId == sessionId) {
                        currentSessionId = null;
                        showEmptyState();
                        currentSessionTitle.textContent = 'NEW CHAT';
                    }
                }
            };
            btn._listener = handler;
            btn.addEventListener('click', handler);
        }
    }

    async function attachRenameListeners() {
        for (const btn of document.querySelectorAll('.rename-session-btn')) {
            btn.removeEventListener('click', btn._renameListener);
            const handler = async (e) => {
                e.stopPropagation();
                const sessionId = btn.dataset.sessionId;
                const titleSpan = btn.closest('.session-item').querySelector('.session-title');
                const newTitle = await promptDialog('Enter new chat title:', titleSpan.textContent, 'RENAME CHAT');
                if (newTitle && newTitle.trim() !== titleSpan.textContent) {
                    const response = await fetch(`/api/sessions/${sessionId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: newTitle.trim() })
                    });
                    const data = await response.json();
                    if (data.success) {
                        titleSpan.textContent = newTitle.trim();
                        if (currentSessionId == sessionId) currentSessionTitle.textContent = newTitle.trim();
                    }
                }
            };
            btn._renameListener = handler;
            btn.addEventListener('click', handler);
        }
    }

    async function clearAllHistory() {
        if (!await confirmDialog('Delete ALL chat history?')) return;
        const response = await fetch('/api/history/clear', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            await loadSessions();
            currentSessionId = null;
            showEmptyState();
            currentSessionTitle.textContent = 'NEW CHAT';
        } else {
            await confirmDialog('Failed: ' + (data.error || 'Unknown error'), 'ERROR');
        }
    }

    function toggleSidebar() {
        if (appContainer) {
            appContainer.classList.toggle('sidebar-collapsed');
            const isCollapsed = appContainer.classList.contains('sidebar-collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
            const icon = toggleSidebarBtn?.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-chevron-left', !isCollapsed);
                icon.classList.toggle('fa-chevron-right', isCollapsed);
            }
        }
    }

    function updateOnlineStatus() {
        const isOnline = navigator.onLine;
        if (sendBtn) {
            sendBtn.disabled = !isOnline;
            sendBtn.style.opacity = isOnline ? '1' : '0.5';
            sendBtn.style.cursor = isOnline ? 'pointer' : 'not-allowed';
        }
    }

    // Theme handling
    function applyTheme(theme) {
        document.documentElement.classList.remove('light', 'dark');
        document.documentElement.classList.add(theme);
        localStorage.setItem('theme', theme);
        document.querySelectorAll('.theme-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.theme === theme);
        });
    }

    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);

    window.addEventListener('storage', (e) => {
        if (e.key === 'theme') applyTheme(e.newValue);
    });

    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        appContainer?.classList.add('sidebar-collapsed');
        const icon = toggleSidebarBtn?.querySelector('i');
        if (icon) {
            icon.classList.remove('fa-chevron-left');
            icon.classList.add('fa-chevron-right');
        }
    }

    // Event listeners
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
        userInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }
    if (newChatBtn) newChatBtn.addEventListener('click', () => {
        currentSessionId = null;
        showEmptyState();
        currentSessionTitle.textContent = 'NEW CHAT';
        document.querySelectorAll('.session-item').forEach(s => s.classList.remove('active'));
    });
    if (clearHistoryBtn) clearHistoryBtn.addEventListener('click', clearAllHistory);
    if (toggleSidebarBtn) toggleSidebarBtn.addEventListener('click', toggleSidebar);

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    // Settings page handlers (unchanged)
    const clearAllDataBtn = document.getElementById('clear-all-data');
    if (clearAllDataBtn) {
        clearAllDataBtn.addEventListener('click', async () => {
            if (await confirmDialog('Delete all chat history permanently?')) {
                await fetch('/api/history/clear', { method: 'POST' });
                window.location.href = '/chat';
            }
        });
    }

    const photoInput = document.getElementById('photo-input');
    const profilePreview = document.getElementById('profile-preview');
    if (photoInput) {
        photoInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (file) {
                const formData = new FormData(); formData.append('photo', file);
                await fetch('/api/settings', { method: 'POST', body: formData });
                const reader = new FileReader();
                reader.onload = (e) => { if (profilePreview) profilePreview.src = e.target.result; };
                reader.readAsDataURL(file);
            }
        });
    }

   const resetPhotoBtn = document.getElementById('reset-photo-btn');
if (resetPhotoBtn) {
    resetPhotoBtn.addEventListener('click', async () => {
        if (await confirmDialog('Reset profile photo to default?')) {
            const res = await fetch('/api/settings/reset-photo', { method: 'POST' });
            const data = await res.json();
            if (data.success && profilePreview) profilePreview.src = `/static/uploads/${data.photo}`;
        }
    });
}

    const themeOptions = document.querySelectorAll('.theme-option');
    themeOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const theme = opt.dataset.theme;
            applyTheme(theme);
            fetch('/api/theme', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ theme }) });
        });
    });

    const updateEmailBtn = document.getElementById('update-email-btn');
    if (updateEmailBtn) {
        updateEmailBtn.addEventListener('click', async () => {
            const newEmail = await promptDialog('Enter new email address:', 'user@example.com', 'UPDATE EMAIL');
            if (!newEmail || !newEmail.includes('@')) {
                await confirmDialog('Invalid email address.', 'ERROR');
                return;
            }
            try {
                const res = await fetch('/api/send-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: newEmail })
                });
                const data = await res.json();
                if (data.success) {
                    const otp = await promptDialog('Enter OTP sent to your new email (valid 1 min):', '6-digit code', 'VERIFY OTP');
                    if (!otp) return;
                    const verifyRes = await fetch('/api/verify-update-email', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ otp })
                    });
                    const verifyData = await verifyRes.json();
                    if (verifyData.success) {
                        const emailSpan = document.getElementById('user-email');
                        if (emailSpan) emailSpan.innerText = verifyData.email;
                        await confirmDialog('Email updated successfully!', 'SUCCESS');
                    } else {
                        await confirmDialog('OTP verification failed: ' + (verifyData.error || 'Invalid OTP'), 'ERROR');
                    }
                } else {
                    await confirmDialog(data.error || 'Failed to send OTP', 'ERROR');
                }
            } catch (err) {
                console.error(err);
                await confirmDialog('Network error. Please try again.', 'ERROR');
            }
        });
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (await confirmDialog('Are you sure you want to logout?', 'LOGOUT')) {
                window.location.href = '/logout';
            }
        });
    }

    const deleteAccountBtn = document.getElementById('delete-account-btn');
    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener('click', async () => {
            if (!await confirmDialog('This will permanently delete your account and all chat history. Continue?', 'DELETE ACCOUNT')) return;
            try {
                const otpRes = await fetch('/api/send-delete-otp', { method: 'POST' });
                const otpData = await otpRes.json();
                if (!otpData.success) {
                    await confirmDialog('Failed to send OTP. Try again later.', 'ERROR');
                    return;
                }
                const otp = await promptDialog('Enter OTP sent to your registered email (valid 1 min):', '6-digit code', 'VERIFY OTP');
                if (!otp) return;
                const email = await promptDialog('Confirm your email address to delete account:', 'your@email.com', 'CONFIRM EMAIL');
                if (!email) return;
                const delRes = await fetch('/api/delete-account', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, otp })
                });
                const delData = await delRes.json();
                if (delData.success) {
                    await confirmDialog('Account permanently deleted.', 'SUCCESS');
                    window.location.href = '/login';
                } else {
                    await confirmDialog(delData.error || 'Deletion failed.', 'ERROR');
                }
            } catch (err) {
                console.error(err);
                await confirmDialog('Network error.', 'ERROR');
            }
        });
    }

    // Initial load
    loadSessions();
    showEmptyState();
    updateOnlineStatus();
});