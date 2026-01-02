/**
 * Customer Care AI - Chat Interface
 * 
 * Frontend logic for the chatbot interface.
 * Communicates with a local Python Flask API or AWS API Gateway.
 */

// Configuration
const CONFIG = {
    // API URL configuration
    // TODO: Replace this with your AWS API Gateway URL from CloudFormation outputs
    // Example: https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/chat
    apiUrl: getApiUrl(),
    tenantId: 'test-tenant',
    customerContext: {
        email: 'test@example.com',
        verified: true
    }
};

/**
 * Get API URL based on environment
 */
function getApiUrl() {
    // Check if running on localhost
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:5001/api/chat';
    }

    // Production - you need to set this after AWS deployment
    // Option 1: Set via URL parameter for testing: ?api_url=https://your-api.com/dev/chat
    const urlParams = new URLSearchParams(window.location.search);
    const apiFromUrl = urlParams.get('api_url');
    if (apiFromUrl) {
        return apiFromUrl;
    }

    // Option 2: Hardcode your AWS API Gateway URL here after deployment
    const AWS_API_URL = 'https://jyiurf3hz3.execute-api.us-east-1.amazonaws.com/dev/chat';

    if (AWS_API_URL === 'PLACEHOLDER_AWS_API_URL') {
        console.error('⚠️ AWS API URL not configured! Please update app.js with your API Gateway endpoint.');
        return null;
    }

    return AWS_API_URL;
}

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const loadingOverlay = document.getElementById('loadingOverlay');

/**
 * Send a message to the chat
 */
async function sendMessage(event) {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input
    messageInput.value = '';

    // Show typing indicator
    const typingIndicator = addTypingIndicator();

    try {
        // Send to API
        const response = await callChatAPI(message);

        // Remove typing indicator
        typingIndicator.remove();

        // Add bot response
        if (response.response) {
            addMessage(response.response, 'bot');
        } else if (response.error) {
            addMessage(`Sorry, I encountered an error: ${response.error}`, 'bot', true);
        }

        // Handle escalation
        if (response.escalate) {
            addMessage('I\'m connecting you with a human agent...', 'bot');
        }

    } catch (error) {
        console.error('Chat error:', error);
        typingIndicator.remove();

        // Check if API URL is configured
        if (!CONFIG.apiUrl) {
            addMessage(
                'The backend API is not configured yet. Please wait for AWS deployment to complete and update the API URL in the code.',
                'bot',
                true
            );
        } else {
            addMessage(
                'Sorry, I\'m having trouble connecting to the backend API. Please check if the AWS Lambda deployment is complete.',
                'bot',
                true
            );
        }
    }
}

/**
 * Send suggestion as message
 */
function sendSuggestion(element) {
    const text = element.textContent;
    messageInput.value = text;
    sendMessage(new Event('submit'));
}

/**
 * Add a message to the chat
 */
function addMessage(text, type, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = type === 'user' ? '👤' : '🤖';

    const content = document.createElement('div');
    content.className = `message-content${isError ? ' error-message' : ''}`;

    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    content.appendChild(paragraph);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * Add typing indicator
 */
function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🤖';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * Scroll chat to bottom
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Call the Chat API
 */
async function callChatAPI(message) {
    const payload = {
        message: message,
        tenant_id: CONFIG.tenantId,
        session_id: getSessionId(),
        customer_context: CONFIG.customerContext
    };

    const response = await fetch(CONFIG.apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();

    // Handle wrapped response (when API Gateway is used)
    if (typeof data.body === 'string') {
        return JSON.parse(data.body);
    }

    return data;
}

/**
 * Get or create session ID
 */
function getSessionId() {
    let sessionId = sessionStorage.getItem('chatSessionId');
    if (!sessionId) {
        sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('chatSessionId', sessionId);
    }
    return sessionId;
}

/**
 * Show loading overlay
 */
function showLoading() {
    loadingOverlay.classList.add('active');
}

/**
 * Hide loading overlay
 */
function hideLoading() {
    loadingOverlay.classList.remove('active');
}

// Initialize
document.addEventListener('DOMContentLoaded', function () {
    // Focus input on load
    messageInput.focus();

    // Handle Enter key
    messageInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            document.getElementById('chatForm').dispatchEvent(new Event('submit'));
        }
    });

    console.log('Customer Care AI Chat initialized');
    console.log('API URL:', CONFIG.apiUrl);
});
