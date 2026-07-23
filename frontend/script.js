/* ==========================================================================
   AURA Client Script - Clean, Simplified API Fetch & DOM Rendering
   ========================================================================== */

// Global App State
let activeArticleId = null;
let activeArticleData = null;
let chatHistory = []; // format: [{role: 'user', content: '...'}, {role: 'model', content: '...'}]

// Self-healing API Base config for routing to port 8000 even if page is loaded via file:// or another dev server port
const API_BASE = window.location.port === "8000" ? "" : "http://127.0.0.1:8000";

// Initialize App on DOM Load
document.addEventListener("DOMContentLoaded", () => {
    // 1. Render Lucide Icons safely
    if (window.lucide) {
        try {
            lucide.createIcons();
        } catch (e) {
            console.error("Lucide failed to render icons:", e);
        }
    }
    
    // 2. Setup Event Listeners
    setupEventListeners();
    
    // 3. Load Saved Theme
    const savedTheme = localStorage.getItem("aura-theme") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);
});

// Event Listeners Configuration
function setupEventListeners() {
    // URL Analysis Form
    document.getElementById("analyzeForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const urlInput = document.getElementById("articleUrlInput");
        const url = urlInput.value.trim();
        if (url) {
            await analyzeArticle(url);
        }
    });

    // Theme Toggle Button
    document.getElementById("themeToggle").addEventListener("click", () => {
        const html = document.documentElement;
        const currentTheme = html.getAttribute("data-theme");
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        html.setAttribute("data-theme", newTheme);
        localStorage.setItem("aura-theme", newTheme);
    });

    // Chat Message Form Submission
    document.getElementById("chatForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const input = document.getElementById("chatInput");
        const question = input.value.trim();
        if (question && activeArticleId) {
            input.value = "";
            document.getElementById("chatSendBtn").disabled = true;
            await sendChatMessage(question);
        }
    });

    // Handle Input change for Send Button state
    document.getElementById("chatInput").addEventListener("input", (e) => {
        const value = e.target.value.trim();
        document.getElementById("chatSendBtn").disabled = (value.length === 0 || !activeArticleId);
    });

    // Suggestion Chips Click
    document.querySelectorAll(".suggestion-chips .chip").forEach(chip => {
        chip.addEventListener("click", async (e) => {
            const question = e.target.textContent;
            if (activeArticleId) {
                await sendChatMessage(question);
            } else {
                showToast("Please analyze a webpage URL first.");
            }
        });
    });

    // Export Button Click
    document.getElementById("exportBtn").addEventListener("click", () => {
        if (activeArticleId) {
            window.location.href = `${API_BASE}/api/export/${activeArticleId}`;
        }
    });
}

// --------------------------------------------------------------------------
// 1. ARTICLE ANALYSIS (API /api/analyze)
// --------------------------------------------------------------------------
async function analyzeArticle(url) {
    const loader = document.getElementById("loaderWrapper");
    const progressFill = document.getElementById("progressBarFill");
    const loaderText = document.getElementById("loaderStatusText");
    const submitBtn = document.getElementById("analyzeSubmitBtn");

    // Show loader UI
    loader.style.display = "flex";
    submitBtn.disabled = true;
    
    // Reset loader state
    progressFill.style.width = "0%";
    loaderText.textContent = "Connecting to URL...";

    // Simulate stepping progress
    let progress = 5;
    const progressInterval = setInterval(() => {
        if (progress < 90) {
            progress += Math.floor(Math.random() * 8) + 2;
            progressFill.style.width = `${progress}%`;
            
            if (progress < 25) loaderText.textContent = "Scraping webpage text content...";
            else if (progress < 50) loaderText.textContent = "Generating summaries using AI models...";
            else if (progress < 75) loaderText.textContent = "Processing semantic chunks and building FAISS RAG index...";
            else loaderText.textContent = "Finalizing article database save...";
        }
    }, 400);

    try {
        const res = await fetch(`${API_BASE}/api/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url })
        });

        clearInterval(progressInterval);

        if (res.ok) {
            progressFill.style.width = "100%";
            loaderText.textContent = "Analysis completed!";
            
            const data = await res.json();
            activeArticleId = data.id;
            activeArticleData = data;
            chatHistory = [];

            // Display Results
            setTimeout(() => {
                loader.style.display = "none";
                submitBtn.disabled = false;
                renderDashboard(data);
                showToast("Webpage analyzed successfully!", false);
            }, 500);

        } else {
            const textResponse = await res.text();
            let errorMessage = "Analysis failed.";
            try {
                const errJson = JSON.parse(textResponse);
                errorMessage = errJson.detail || errorMessage;
            } catch (jsonErr) {
                errorMessage = textResponse || errorMessage;
            }
            throw new Error(errorMessage);
        }

    } catch (e) {
        clearInterval(progressInterval);
        loader.style.display = "none";
        submitBtn.disabled = false;
        showToast(e.message || "Error communicating with server.");
    }
}

// Render Dashboard Data on Successful Analysis
function renderDashboard(data) {
    // 1. Show Metadata Card
    const infoCard = document.getElementById("articleInfoCard");
    if (infoCard) infoCard.style.display = "block";
    
    const displayTitle = document.getElementById("displayTitle");
    if (displayTitle) displayTitle.textContent = data.title;
    
    const displayUrl = document.getElementById("displayUrl");
    if (displayUrl) displayUrl.href = data.source_url;

    // 2. Render Abstractive Summary
    const absContent = document.getElementById("abstractiveContent");
    if (absContent) {
        absContent.innerHTML = "";
        if (data.abstractive_summary) {
            const paragraphs = data.abstractive_summary.split("\n\n");
            paragraphs.forEach(pText => {
                if (pText.trim()) {
                    const p = document.createElement("p");
                    p.textContent = pText.trim();
                    absContent.appendChild(p);
                }
            });
        }
    }

    // 3. Render Extractive Summary
    const extContent = document.getElementById("extractiveContent");
    if (extContent) {
        extContent.innerHTML = "";
        if (data.extractive_summary) {
            data.extractive_summary.forEach(sent => {
                const li = document.createElement("li");
                li.textContent = sent;
                extContent.appendChild(li);
            });
        }
    }

    // 4. Show Suggestion Chips & Enable Chat Input
    const suggestionChips = document.getElementById("suggestionChips");
    if (suggestionChips) suggestionChips.style.display = "flex";
    
    const chatInput = document.getElementById("chatInput");
    if (chatInput) chatInput.placeholder = "Ask any question about the article...";
    
    // Reset Chat messages view
    const messages = document.getElementById("chatMessages");
    if (messages) {
        messages.innerHTML = `
            <div class="system-message message">
                <div class="avatar"><i data-lucide="bot"></i></div>
                <div class="msg-content">
                    <p>Welcome! Ask me anything about the article <strong>"${data.title}"</strong>. The chatbot is grounded strictly in its context.</p>
                </div>
            </div>
        `;
    }
    if (window.lucide) lucide.createIcons();
}

// --------------------------------------------------------------------------
// 2. CHATBOT RAG INTERACTION (API /api/chat)
// --------------------------------------------------------------------------
async function sendChatMessage(question) {
    const messages = document.getElementById("chatMessages");
    const typing = document.getElementById("typingIndicator");

    // Append User Message bubble
    appendMessage("user", question);
    
    // Show typing status
    typing.style.display = "flex";
    messages.scrollTop = messages.scrollHeight;

    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                article_id: activeArticleId,
                question: question,
                chat_history: chatHistory
            })
        });

        typing.style.display = "none";

        if (res.ok) {
            const data = await res.json();
            
            // Append Bot Message bubble
            appendMessage("bot", data.response);
            
            // Save to Local chat history
            chatHistory.push({ role: "user", content: question });
            chatHistory.push({ role: "model", content: data.response });

        } else {
            const textResponse = await res.text();
            let errorMessage = "Failed to query chat.";
            try {
                const errJson = JSON.parse(textResponse);
                errorMessage = errJson.detail || errorMessage;
            } catch (jsonErr) {
                errorMessage = textResponse || errorMessage;
            }
            throw new Error(errorMessage);
        }

    } catch (e) {
        typing.style.display = "none";
        showToast(e.message || "Error getting response.");
    }

    document.getElementById("chatSendBtn").disabled = false;
    messages.scrollTop = messages.scrollHeight;
}

// Helper to construct and append message bubble elements
function appendMessage(role, text) {
    const messages = document.getElementById("chatMessages");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}`;

    const icon = role === "user" ? "user" : "bot";
    msgDiv.innerHTML = `
        <div class="avatar"><i data-lucide="${icon}"></i></div>
        <div class="msg-content">
            <p>${escapeHtml(text)}</p>
        </div>
    `;
    messages.appendChild(msgDiv);
    if (window.lucide) {
        try {
            lucide.createIcons();
        } catch (e) {
            console.error(e);
        }
    }
    messages.scrollTop = messages.scrollHeight;
}

// --------------------------------------------------------------------------
// UTILITY FUNCTIONS
// --------------------------------------------------------------------------
function showToast(message, isError = true) {
    let toast = document.getElementById("alertToast") || document.getElementById("toastNotification");
    
    // Dynamic fallback if toast element is missing in the page
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "alertToast";
        toast.style.position = "fixed";
        toast.style.bottom = "20px";
        toast.style.right = "20px";
        toast.style.padding = "16px 24px";
        toast.style.borderRadius = "8px";
        toast.style.background = "#1e2538";
        toast.style.color = "#ffffff";
        toast.style.borderLeft = "4px solid var(--danger-color, #ef4444)";
        toast.style.boxShadow = "0 10px 15px -3px rgba(0, 0, 0, 0.3)";
        toast.style.zIndex = "99999";
        toast.style.display = "flex";
        toast.style.alignItems = "center";
        toast.style.gap = "12px";
        toast.style.fontSize = "0.95rem";
        toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        toast.style.opacity = "0";
        toast.style.transform = "translateY(10px)";
        toast.innerHTML = `<i class="alert-icon" data-lucide="alert-circle" style="color: #ef4444;"></i><span id="alertMessage"></span>`;
        document.body.appendChild(toast);
    }
    
    const msgSpan = document.getElementById("alertMessage") || toast.querySelector("span") || toast;
    msgSpan.textContent = message;
    
    const existingIcon = toast.querySelector(".alert-icon");
    if (existingIcon) existingIcon.remove();
    
    const newIcon = document.createElement("i");
    newIcon.className = "alert-icon";
    newIcon.setAttribute("data-lucide", isError ? "alert-circle" : "check-circle");
    
    if (isError) {
        toast.style.borderLeftColor = "var(--danger-color, #ef4444)";
        newIcon.style.color = "var(--danger-color, #ef4444)";
    } else {
        toast.style.borderLeftColor = "var(--success-color, #10b981)";
        newIcon.style.color = "var(--success-color, #10b981)";
    }
    
    toast.insertBefore(newIcon, msgSpan);
    if (window.lucide) {
        try {
            lucide.createIcons();
        } catch (e) {
            console.error(e);
        }
    }
    
    toast.classList.add("show");
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
    
    setTimeout(() => {
        toast.classList.remove("show");
        toast.style.opacity = "0";
        toast.style.transform = "translateY(10px)";
    }, 4500);
}

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
