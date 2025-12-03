const API_BASE_URL = window.location.origin;

const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

// 发送消息
async function sendMessage() {
    const query = userInput.value.trim();
    if (!query) return;

    // 禁用输入
    userInput.disabled = true;
    sendButton.disabled = true;

    // 显示用户消息
    addMessage(query, 'user');

    // 清空输入
    userInput.value = '';

    // 显示加载动画
    const loadingId = addLoadingMessage();

    try {
        // 发送请求
        const response = await fetch(`${API_BASE_URL}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                stream: false
            })
        });

        // 移除加载动画
        removeMessage(loadingId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            // 构建回复消息
            let reply = '';

            if (data.symbol && data.name) {
                reply += `## ${data.name} (${data.symbol}) 投资分析\n\n`;
            }

            if (data.quant_analysis) {
                reply += `### 📊 量化分析\n\n${data.quant_analysis}\n\n`;
            }

            if (data.news_analysis) {
                reply += `### 📰 新闻政策分析\n\n${data.news_analysis}\n\n`;
            }

            if (data.advice) {
                reply += `### 💡 综合投资建议\n\n${data.advice}`;
            }

            addMessage(reply, 'bot');
        } else {
            addMessage(`❌ ${data.error || '处理失败，请稍后重试'}`, 'bot');
        }
    } catch (error) {
        console.error('Error:', error);
        removeMessage(loadingId);
        addMessage(`❌ 网络错误：${error.message}`, 'bot');
    } finally {
        // 恢复输入
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
    }
}

// 添加消息到聊天界面
function addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // 处理Markdown格式（简单处理）
    const formattedContent = formatMessage(content);
    contentDiv.innerHTML = formattedContent;

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageDiv;
}

// 添加加载消息
function addLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.id = 'loading-message';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = '<div class="loading"></div> 正在分析中，请稍候...';

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    chatMessages.scrollTop = chatMessages.scrollHeight;

    return 'loading-message';
}

// 移除消息
function removeMessage(id) {
    const message = document.getElementById(id);
    if (message) {
        message.remove();
    }
}

// 格式化消息（简单的Markdown处理）
function formatMessage(text) {
    // 转义HTML
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // 标题
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // 粗体
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 列表
    text = text.replace(/^\- (.*$)/gim, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // 换行
    text = text.replace(/\n\n/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');

    // 包装段落
    if (!text.startsWith('<h') && !text.startsWith('<ul')) {
        text = '<p>' + text + '</p>';
    }

    return text;
}

// 事件监听
sendButton.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// 页面加载完成后聚焦输入框
window.addEventListener('load', () => {
    userInput.focus();
});

