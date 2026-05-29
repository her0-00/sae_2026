(function() {
    // ── Styles CSS injectés dynamiquement ─────────────────────────
    const style = document.createElement("style");
    style.innerHTML = `
        .immobi-chat-bubble {
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, #7c3aed, #2563eb);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.6rem;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4);
            z-index: 10000;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }
        .immobi-chat-bubble:hover {
            transform: scale(1.1) rotate(5deg);
            box-shadow: 0 8px 24px rgba(124, 58, 237, 0.6);
        }
        .immobi-chat-bubble:active {
            transform: scale(0.95);
        }
        
        .immobi-chat-window {
            position: fixed;
            bottom: 96px;
            right: 24px;
            width: 380px;
            height: 520px;
            border-radius: 16px;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            transform: scale(0.8) translateY(40px);
            opacity: 0;
            pointer-events: none;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        .immobi-chat-window.open {
            transform: scale(1) translateY(0);
            opacity: 1;
            pointer-events: auto;
        }
        
        .immobi-chat-header {
            padding: 1rem 1.25rem;
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(37, 99, 235, 0.2));
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .immobi-chat-title-wrap {
            display: flex;
            flex-direction: column;
        }
        .immobi-chat-title {
            font-weight: 700;
            color: #fff;
            font-size: 0.95rem;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }
        .immobi-chat-title span.pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #22c55e;
            display: inline-block;
            box-shadow: 0 0 8px #22c55e;
            animation: pulse-active 1.8s infinite;
        }
        .immobi-chat-subtitle {
            font-size: 0.72rem;
            color: #94a3b8;
            margin-top: 0.15rem;
        }
        .immobi-chat-close {
            color: #94a3b8;
            font-size: 1.2rem;
            cursor: pointer;
            transition: color 0.15s;
            border: none;
            background: none;
            padding: 4px;
        }
        .immobi-chat-close:hover {
            color: #fff;
        }

        .immobi-chat-messages {
            flex: 1;
            padding: 1.25rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            scroll-behavior: smooth;
        }
        .immobi-chat-messages::-webkit-scrollbar {
            width: 5px;
        }
        .immobi-chat-messages::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 99px;
        }
        
        .immobi-msg {
            max-width: 85%;
            padding: 0.75rem 1rem;
            font-size: 0.85rem;
            line-height: 1.45;
            animation: message-fade 0.25s cubic-bezier(0, 0, 0.2, 1) forwards;
        }
        .immobi-msg-user {
            align-self: flex-end;
            background: #7c3aed;
            color: #fff;
            border-radius: 14px 14px 2px 14px;
            box-shadow: 0 2px 8px rgba(124, 58, 237, 0.2);
        }
        .immobi-msg-assistant {
            align-self: flex-start;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: #f1f5f9;
            border-radius: 14px 14px 14px 2px;
        }
        .immobi-msg p {
            margin: 0 0 0.5rem 0;
        }
        .immobi-msg p:last-child {
            margin: 0;
        }
        .immobi-msg strong {
            color: #fff;
            font-weight: 700;
        }
        .immobi-msg code {
            background: rgba(255, 255, 255, 0.1);
            padding: 1px 4px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.8rem;
            color: #f472b6;
        }
        .immobi-msg pre {
            background: rgba(0, 0, 0, 0.3);
            padding: 0.6rem;
            border-radius: 6px;
            overflow-x: auto;
            margin: 0.4rem 0;
        }
        .immobi-msg pre code {
            background: none;
            padding: 0;
            color: #f8fafc;
        }
        .immobi-msg ul, .immobi-msg ol {
            margin: 0.4rem 0;
            padding-left: 1.2rem;
        }
        .immobi-msg li {
            margin-bottom: 0.25rem;
        }
        
        .immobi-chat-input-panel {
            padding: 0.85rem 1.1rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 0.6rem;
            background: rgba(15, 23, 42, 0.5);
            align-items: center;
        }
        .immobi-chat-input {
            flex: 1;
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 0.55rem 1rem;
            color: #fff;
            font-size: 0.85rem;
            outline: none;
            transition: all 0.15s;
        }
        .immobi-chat-input:focus {
            background: rgba(255, 255, 255, 0.1);
            border-color: #7c3aed;
            box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.25);
        }
        .immobi-chat-send {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: #7c3aed;
            color: #fff;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background 0.15s, transform 0.1s;
        }
        .immobi-chat-send:hover {
            background: #6d28d9;
            transform: scale(1.05);
        }
        .immobi-chat-send:active {
            transform: scale(0.95);
        }
        
        /* Typing indicator animation */
        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 4px 6px;
        }
        .typing-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #94a3b8;
            opacity: 0.4;
            animation: typing-blink 1.4s infinite both;
        }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes pulse-active {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
        @keyframes typing-blink {
            0% { opacity: 0.4; }
            20% { opacity: 1; }
            100% { opacity: 0.4; }
        }
        @keyframes message-fade {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @media(max-width: 480px) {
            .immobi-chat-window {
                width: calc(100% - 32px);
                height: calc(100% - 110px);
                bottom: 80px;
                right: 16px;
            }
        }
    `;
    document.head.appendChild(style);

    // ── Simple Parser Markdown pour le Copilot ───────────────────
    function parseMarkdown(text) {
        if (!text) return "";
        
        let html = text;
        
        // 1. Échapper le HTML brut pour des raisons de sécurité (XSS)
        html = html
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // 2. Extraire et protéger les blocs de code multi-lignes
        const codeBlocks = [];
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const index = codeBlocks.length;
            codeBlocks.push(`<pre><code class="language-${lang}">${code.trim()}</code></pre>`);
            return `__CODE_BLOCK_${index}__`;
        });
        
        // 3. Extraire et protéger les blocs de code en ligne
        const inlineCode = [];
        html = html.replace(/`([^`]+)`/g, (match, code) => {
            const index = inlineCode.length;
            inlineCode.push(`<code>${code}</code>`);
            return `__INLINE_CODE_${index}__`;
        });
        
        // 4. Titres (H1, H2, H3)
        html = html
            .replace(/^### (.*$)/gim, "<h3>$1</h3>")
            .replace(/^## (.*$)/gim, "<h2>$1</h2>")
            .replace(/^# (.*$)/gim, "<h1>$1</h1>");
            
        // 5. Gras & Italique
        html = html
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/\*([^*]+)\*/g, "<em>$1</em>")
            .replace(/__([^_]+)__/g, "<strong>$1</strong>")
            .replace(/_([^_]+)_/g, "<em>$1</em>");
            
        // 6. Liens hypertextes [texte](url)
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        
        // 7. Listes ordonnées et non-ordonnées
        const lines = html.split('\n');
        let inList = false;
        let inNumList = false;
        let processedLines = [];
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            
            // Liste à puces (- ou *)
            if (line.match(/^\s*[-*+]\s+(.*)/)) {
                if (inNumList) {
                    processedLines.push('</ol>');
                    inNumList = false;
                }
                if (!inList) {
                    processedLines.push('<ul>');
                    inList = true;
                }
                line = line.replace(/^\s*[-*+]\s+(.*)/, '<li>$1</li>');
            } 
            // Liste numérotée (1., 2.)
            else if (line.match(/^\s*\d+\.\s+(.*)/)) {
                if (inList) {
                    processedLines.push('</ul>');
                    inList = false;
                }
                if (!inNumList) {
                    processedLines.push('<ol>');
                    inNumList = true;
                }
                line = line.replace(/^\s*\d+\.\s+(.*)/, '<li>$1</li>');
            } 
            // Ligne classique
            else {
                if (inList) {
                    processedLines.push('</ul>');
                    inList = false;
                }
                if (inNumList) {
                    processedLines.push('</ol>');
                    inNumList = false;
                }
            }
            
            processedLines.push(line);
        }
        
        if (inList) processedLines.push('</ul>');
        if (inNumList) processedLines.push('</ol>');
        
        html = processedLines.join('\n');
        
        // 8. Paragraphes & sauts de ligne simples
        const paragraphs = html.split(/\n{2,}/);
        html = paragraphs.map(p => {
            p = p.trim();
            if (!p) return "";
            // Si la ligne commence par une balise block, on ne l'enveloppe pas dans <p>
            if (p.match(/^(<h[1-6]|<ul|<ol|<li|<pre|<blockquote|<div|<p)/i)) {
                return p.replace(/\n/g, "<br>");
            }
            return `<p>${p.replace(/\n/g, "<br>")}</p>`;
        }).filter(Boolean).join("");
        
        // 9. Restaurer le code en ligne et les blocs de code
        inlineCode.forEach((code, idx) => {
            html = html.replace(`__INLINE_CODE_${idx}__`, code);
        });
        
        codeBlocks.forEach((code, idx) => {
            html = html.replace(`__CODE_BLOCK_${idx}__`, code);
        });
        
        return html;
    }

    // ── Construction du DOM du Widget ─────────────────────────────
    const chatBubble = document.createElement("div");
    chatBubble.className = "immobi-chat-bubble";
    chatBubble.innerHTML = "💬";

    const chatWindow = document.createElement("div");
    chatWindow.className = "immobi-chat-window";
    chatWindow.innerHTML = `
        <div class="immobi-chat-header">
            <div class="immobi-chat-title-wrap">
                <h3 class="immobi-chat-title"><span class="pulse-dot"></span> ImmoBI Copilot</h3>
                <div class="immobi-chat-subtitle">Assistant IA connecté à la Base de Données</div>
            </div>
            <button class="immobi-chat-close" title="Fermer">✕</button>
        </div>
        <div class="immobi-chat-messages" id="immobi-chat-messages">
            <div class="immobi-msg immobi-msg-assistant">
                Bonjour ! Je suis **ImmoBI Copilot**. 🏠✨

                Je peux interroger notre base de données pour vous donner des prix réels, des analyses de quartiers, ou rédiger des **arguments de négociation** basés sur les passoires thermiques (DPE) ou le bruit (PEB).

                *Comment puis-je vous aider aujourd'hui ?*
            </div>
        </div>
        <div class="immobi-chat-input-panel">
            <input type="text" class="immobi-chat-input" id="immobi-chat-input" placeholder="Posez une question sur Vannes, Hennebont..." autocomplete="off">
            <button class="immobi-chat-send" id="immobi-chat-send">➔</button>
        </div>
    `;

    document.body.appendChild(chatBubble);
    document.body.appendChild(chatWindow);

    // ── Variables d'état conversationnel ──────────────────────────
    let isWindowOpen = false;
    let messagesHistory = [];
    const chatMessagesEl = document.getElementById("immobi-chat-messages");
    const chatInputEl = document.getElementById("immobi-chat-input");
    const chatSendEl = document.getElementById("immobi-chat-send");

    // Formater le message de bienvenue initial
    const firstMsg = chatMessagesEl.querySelector(".immobi-msg-assistant");
    firstMsg.innerHTML = parseMarkdown(firstMsg.innerHTML);

    // ── Gestionnaires d'évènements ────────────────────────────────
    chatBubble.addEventListener("click", () => {
        isWindowOpen = !isWindowOpen;
        if (isWindowOpen) {
            chatWindow.classList.add("open");
            chatBubble.innerHTML = "✕";
            chatBubble.style.background = "linear-gradient(135deg, #ef4444, #b91c1c)";
            chatBubble.style.boxShadow = "0 4px 16px rgba(239, 68, 68, 0.4)";
            chatInputEl.focus();
        } else {
            closeWindow();
        }
    });

    chatWindow.querySelector(".immobi-chat-close").addEventListener("click", closeWindow);

    function closeWindow() {
        isWindowOpen = false;
        chatWindow.classList.remove("open");
        chatBubble.innerHTML = "💬";
        chatBubble.style.background = "linear-gradient(135deg, #7c3aed, #2563eb)";
        chatBubble.style.boxShadow = "0 4px 16px rgba(124, 58, 237, 0.4)";
    }

    chatInputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMessage();
    });

    chatSendEl.addEventListener("click", sendMessage);

    // ── Envoi du message et appel API ────────────────────────────
    async function sendMessage() {
        const text = chatInputEl.value.trim();
        if (!text) return;

        chatInputEl.value = "";
        
        // Ajouter le message utilisateur dans le volet et l'historique
        appendMessage(text, "user");
        messagesHistory.push({ "role": "user", "content": text });

        // Ajouter l'indicateur de frappe
        const typingEl = appendTypingIndicator();
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: messagesHistory })
            });

            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();
            
            // Retirer l'indicateur de frappe
            typingEl.remove();

            if (data.error) {
                appendMessage("⚠️ *Erreur IA :* " + data.error, "assistant");
            } else if (data.choices && data.choices[0] && data.choices[0].message) {
                const aiMsg = data.choices[0].message;
                appendMessage(aiMsg.content, "assistant");
                messagesHistory.push({ "role": "assistant", "content": aiMsg.content });
            } else {
                appendMessage("Désolé, je rencontre une difficulté pour analyser cette question.", "assistant");
            }
        } catch (err) {
            typingEl.remove();
            appendMessage("⚠️ *Erreur de connexion :* Impossible de contacter l'assistant intelligent. Vérifiez que le serveur Flask est bien démarré.", "assistant");
            console.error(err);
        }

        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }

    function appendMessage(content, role) {
        const msg = document.createElement("div");
        msg.className = `immobi-msg immobi-msg-${role}`;
        msg.innerHTML = parseMarkdown(content);
        chatMessagesEl.appendChild(msg);
        return msg;
    }

    function appendTypingIndicator() {
        const msg = document.createElement("div");
        msg.className = "immobi-msg immobi-msg-assistant";
        msg.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatMessagesEl.appendChild(msg);
        return msg;
    }
})();
