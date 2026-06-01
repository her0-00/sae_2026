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
            bottom: 85px;
            right: 24px;
            width: 50vw;
            max-width: 700px;
            min-width: 380px;
            height: 70vh;
            max-height: 620px;
            min-height: 450px;
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
        .immobi-msg h1, .immobi-msg h2, .immobi-msg h3 {
            color: #e2e8f0;
            font-weight: 700;
            margin: 0.6rem 0 0.3rem 0;
            line-height: 1.3;
        }
        .immobi-msg h1 { font-size: 1rem; }
        .immobi-msg h2 { font-size: 0.95rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.2rem; }
        .immobi-msg h3 { font-size: 0.88rem; color: #a5b4fc; }
        .immobi-msg em { color: #cbd5e1; font-style: italic; }
        .immobi-msg a { color: #818cf8; text-decoration: underline; }
        
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
        
        @media(max-width: 768px), (max-height: 680px) {
            .immobi-chat-window {
                width: calc(100% - 32px) !important;
                height: calc(100% - 110px) !important;
                bottom: 80px;
                right: 16px;
                min-width: 0 !important;
                max-width: none !important;
                min-height: 0 !important;
                max-height: none !important;
            }
        }
        
        /* Premium Table & Visual Comparison Styling */
        .immobi-table-container {
            width: 100%;
            overflow-x: auto;
            margin: 0.8rem 0;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(15, 23, 42, 0.4);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }
        .immobi-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.78rem;
            color: #e2e8f0;
            text-align: left;
        }
        .immobi-table th {
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(37, 99, 235, 0.2));
            font-weight: 700;
            color: #fff;
            padding: 0.6rem 0.8rem;
            border-bottom: 2px solid rgba(255, 255, 255, 0.12);
            text-transform: uppercase;
            font-size: 0.68rem;
            letter-spacing: 0.03em;
        }
        .immobi-table td {
            padding: 0.6rem 0.8rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            vertical-align: middle;
            background: transparent !important; /* Force transparent cells to override main.css */
        }
        .immobi-table tr:last-child td {
            border-bottom: none;
        }
        .immobi-table tr:hover {
            background: rgba(255, 255, 255, 0.04) !important;
        }
        .immobi-table tr:hover td {
            background: rgba(255, 255, 255, 0.06) !important; /* Force modern hover to override main.css tr:hover td */
        }
        .immobi-bar-cell {
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 110px;
        }
        .immobi-bar-wrap {
            width: 100%;
            height: 5px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
            overflow: hidden;
        }
        .immobi-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #a78bfa, #60a5fa);
            border-radius: 2px;
            width: 0;
            animation: bar-grow 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }
        @keyframes bar-grow {
            to { width: var(--fill-width); }
        }
        
        /* Premium Copilot Suggestion Pills */
        .immobi-chat-suggestions {
            display: flex;
            gap: 8px;
            padding: 0.5rem 1.1rem;
            border-top: 1px dashed rgba(255, 255, 255, 0.08);
            background: rgba(15, 23, 42, 0.4);
            flex-wrap: wrap;
            align-items: center;
            transition: all 0.3s ease;
        }
        .immobi-suggestion-pill {
            background: rgba(124, 58, 237, 0.15);
            border: 1px solid rgba(124, 58, 237, 0.3);
            color: #c084fc;
            font-size: 0.74rem;
            padding: 4px 10px;
            border-radius: 99px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.2s ease;
            user-select: none;
        }
        .immobi-suggestion-pill:hover {
            background: rgba(124, 58, 237, 0.3);
            border-color: #a78bfa;
            color: #fff;
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
        }
        .immobi-suggestion-pill:active {
            transform: translateY(0);
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
        
        // 6.5 Tables Markdown
        html = parseMarkdownTables(html);
        
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

    // ── Tableaux & Barres de Comparaison Visuelle ─────────────────
    function parseMarkdownTables(text) {
        if (!text) return "";
        const lines = text.split('\n');
        let inTable = false;
        let tableRows = [];
        let outputLines = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line.startsWith('|') && line.endsWith('|')) {
                if (!inTable) {
                    inTable = true;
                    tableRows = [];
                }
                tableRows.push(line);
            } else {
                if (inTable) {
                    outputLines.push(renderStyledTable(tableRows));
                    inTable = false;
                }
                outputLines.push(lines[i]);
            }
        }
        if (inTable) {
            outputLines.push(renderStyledTable(tableRows));
        }
        return outputLines.join('\n');
    }

    function renderStyledTable(rows) {
        if (rows.length < 2) return rows.join('\n');
        
        // Parse headers
        const headers = rows[0]
            .split('|')
            .map(x => x.trim())
            .filter((x, idx, arr) => idx > 0 && idx < arr.length - 1);
            
        let dataStartIndex = 1;
        if (rows[1] && rows[1].replace(/[\s|:-]/g, '') === '') {
            dataStartIndex = 2;
        }
        
        // Parse data rows
        const data = [];
        for (let i = dataStartIndex; i < rows.length; i++) {
            const cells = rows[i]
                .split('|')
                .map(x => x.trim())
                .filter((x, idx, arr) => idx > 0 && idx < arr.length - 1);
            if (cells.length > 0) {
                data.push(cells);
            }
        }
        
        if (data.length === 0) return rows.join('\n');
        
        // Analyse des colonnes pour trouver des métriques numériques à comparer
        const maxValues = {};
        const colIsNumeric = {};
        
        headers.forEach((header, colIdx) => {
            const lowerHeader = header.toLowerCase();
            if (
                lowerHeader.includes('m²') ||
                lowerHeader.includes('m2') ||
                lowerHeader.includes('prix') ||
                lowerHeader.includes('médiane') ||
                lowerHeader.includes('budget') ||
                lowerHeader.includes('valeur') ||
                lowerHeader.includes('€') ||
                lowerHeader.includes('ventes')
            ) {
                let numbers = data.map(row => {
                    const cell = row[colIdx] || '';
                    const cleanCell = cell.replace(/\s(?=\d)/g, '').replace(/&nbsp;/g, '');
                    const match = cleanCell.match(/\d+/);
                    return match ? parseInt(match[0], 10) : null;
                }).filter(x => x !== null);
                
                if (numbers.length > 0) {
                    colIsNumeric[colIdx] = true;
                    maxValues[colIdx] = Math.max(...numbers);
                }
            }
        });
        
        // Génération du tableau HTML stylisé
        let html = '<div class="immobi-table-container"><table class="immobi-table">';
        
        // En-tête
        html += '<thead><tr>';
        headers.forEach(h => {
            html += `<th>${h}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        // Données
        data.forEach(row => {
            html += '<tr>';
            headers.forEach((_, colIdx) => {
                const cellVal = row[colIdx] || '';
                if (colIsNumeric[colIdx] && maxValues[colIdx] > 0) {
                    const cleanCell = cellVal.replace(/\s(?=\d)/g, '').replace(/&nbsp;/g, '');
                    const match = cleanCell.match(/\d+/);
                    const numVal = match ? parseInt(match[0], 10) : null;
                    if (numVal !== null) {
                        const pct = Math.min(100, Math.round((numVal / maxValues[colIdx]) * 100));
                        html += `<td>
                            <div class="immobi-bar-cell">
                                <div><strong>${cellVal}</strong></div>
                                <div class="immobi-bar-wrap">
                                    <div class="immobi-bar-fill" style="--fill-width: ${pct}%"></div>
                                </div>
                            </div>
                        </td>`;
                        return;
                    }
                }
                html += `<td>${cellVal}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table></div>';
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
            <div style="display: flex; gap: 8px; align-items: center;">
                <button class="immobi-chat-clear" title="Réinitialiser le chat" style="color: #94a3b8; font-size: 1rem; cursor: pointer; border: none; background: none; padding: 4px; transition: color 0.15s;">🗑️</button>
                <button class="immobi-chat-close" title="Fermer">✕</button>
            </div>
        </div>
        <div class="immobi-chat-messages" id="immobi-chat-messages">
            <div class="immobi-msg immobi-msg-assistant" data-markdown="**ImmoBI Copilot** — outil de négociation immobilière 🏠&#10;&#10;Posez une question précise, obtenez un verdict chiffré :&#10;&#10;- *« Appartement 65m² à 280 000€ à Vannes, c'est négociable ? »*&#10;- *« Quels leviers de négo pour une maison DPE F à Lorient ? »*&#10;- *« Prix du marché appartement proche gare à Hennebont »*"></div>
        </div>
        <div class="immobi-chat-suggestions" id="immobi-chat-suggestions" style="display: none;"></div>
        <div class="immobi-chat-input-panel">
            <input type="text" class="immobi-chat-input" id="immobi-chat-input" placeholder="Posez une question sur Vannes, Hennebont..." autocomplete="off">
            <button class="immobi-chat-send" id="immobi-chat-send">➔</button>
        </div>
    `;

    document.body.appendChild(chatBubble);
    document.body.appendChild(chatWindow);

    // ── Variables d'état conversationnel ──────────────────────────
    let isWindowOpen = localStorage.getItem("immobi_chat_open") === "true";
    let messagesHistory = [];
    try {
        const savedHistory = localStorage.getItem("immobi_chat_history");
        if (savedHistory) {
            messagesHistory = JSON.parse(savedHistory);
        }
    } catch (e) {
        console.error("Erreur lors de la lecture de l'historique de chat", e);
    }

    const chatMessagesEl = document.getElementById("immobi-chat-messages");
    const chatSuggestionsEl = document.getElementById("immobi-chat-suggestions");
    const chatInputEl = document.getElementById("immobi-chat-input");
    const chatSendEl = document.getElementById("immobi-chat-send");

    // Formater le message de bienvenue initial (depuis l'attribut data-markdown)
    const firstMsg = chatMessagesEl.querySelector(".immobi-msg-assistant[data-markdown]");
    if (firstMsg) {
        const md = firstMsg.getAttribute("data-markdown")
            .replace(/&#10;/g, "\n");
        firstMsg.innerHTML = parseMarkdown(md);
    }

    // Restaurer l'historique dans le DOM
    if (messagesHistory.length > 0) {
        messagesHistory.forEach(msg => {
            appendMessage(msg.content, msg.role === "assistant" ? "assistant" : "user");
        });
    }

    // ── Gestionnaires d'évènements ────────────────────────────────
    chatBubble.addEventListener("click", () => {
        isWindowOpen = !isWindowOpen;
        localStorage.setItem("immobi_chat_open", isWindowOpen);
        if (isWindowOpen) {
            openWindow();
        } else {
            closeWindow();
        }
    });

    chatWindow.querySelector(".immobi-chat-close").addEventListener("click", () => {
        closeWindow();
    });

    chatWindow.querySelector(".immobi-chat-clear").addEventListener("click", () => {
        if (confirm("Voulez-vous réinitialiser l'historique de discussion ?")) {
            messagesHistory = [];
            localStorage.removeItem("immobi_chat_history");
            const messages = chatMessagesEl.querySelectorAll(".immobi-msg");
            messages.forEach((msg, idx) => {
                if (idx > 0) msg.remove(); // Garde seulement le message de bienvenue initial
            });
            chatMessagesEl.scrollTop = 0;
        }
    });

    function openWindow() {
        chatWindow.classList.add("open");
        chatBubble.innerHTML = "✕";
        chatBubble.style.background = "linear-gradient(135deg, #ef4444, #b91c1c)";
        chatBubble.style.boxShadow = "0 4px 16px rgba(239, 68, 68, 0.4)";
        chatInputEl.focus();
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }

    function closeWindow() {
        isWindowOpen = false;
        localStorage.setItem("immobi_chat_open", "false");
        chatWindow.classList.remove("open");
        chatBubble.innerHTML = "💬";
        chatBubble.style.background = "linear-gradient(135deg, #7c3aed, #2563eb)";
        chatBubble.style.boxShadow = "0 4px 16px rgba(124, 58, 237, 0.4)";
    }

    // Ouverture automatique lors du rechargement de la page si l'état était ouvert
    if (isWindowOpen) {
        openWindow();
    }

    // ── Connexion intelligente avec la carte (localStorage) ───
    let currentCommune = localStorage.getItem("selected_commune_name") || "";
    let previousCommune = "";

    function updatePills(communeName) {
        if (!communeName) {
            chatSuggestionsEl.style.display = "none";
            chatInputEl.placeholder = "Posez une question sur Vannes, Hennebont...";
            return;
        }

        communeName = communeName.toUpperCase();
        chatInputEl.placeholder = `Poser une question sur ${communeName}...`;

        if (currentCommune && currentCommune.toUpperCase() !== communeName) {
            previousCommune = currentCommune.toUpperCase();
        }
        currentCommune = communeName;

        chatSuggestionsEl.innerHTML = "";
        
        const pills = [
            { text: `📍 Analyser ${communeName}`, prompt: `Analyser le marché à ${communeName}` }
        ];

        if (previousCommune && previousCommune !== currentCommune) {
            pills.push({ 
                text: `⚖️ Comparer avec ${previousCommune}`, 
                prompt: `Je veux acheter un bien à ${communeName} ou à ${previousCommune}, fais-moi une comparaison complète.` 
            });
        }

        pills.forEach(p => {
            const pill = document.createElement("div");
            pill.className = "immobi-suggestion-pill";
            pill.innerHTML = p.text;
            pill.addEventListener("click", () => {
                chatInputEl.value = p.prompt;
                sendMessage();
            });
            chatSuggestionsEl.appendChild(pill);
        });

        chatSuggestionsEl.style.display = "flex";
        
        // Ajuster le défilement si nécessaire
        setTimeout(() => {
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
        }, 100);
    }

    // Intercepter setItem pour détecter les clics sur la carte en temps réel
    const originalSetItem = localStorage.setItem;
    localStorage.setItem = function(key, value) {
        originalSetItem.apply(this, arguments);
        if (key === "selected_commune_name") {
            window.dispatchEvent(new CustomEvent("immobiCommuneChanged", { detail: value }));
        }
    };

    // Écouter les évènements de changement de commune
    window.addEventListener("immobiCommuneChanged", (e) => {
        updatePills(e.detail);
    });

    // Écouter les changements inter-pages
    window.addEventListener("storage", (e) => {
        if (e.key === "selected_commune_name") {
            updatePills(e.newValue);
        }
    });

    // Initialisation
    if (currentCommune) {
        updatePills(currentCommune);
    }

    chatInputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMessage();
    });

    chatSendEl.addEventListener("click", sendMessage);

    // ── Envoi du message avec streaming SSE ─────────────────────
    async function sendMessage() {
        const text = chatInputEl.value.trim();
        if (!text) return;

        chatInputEl.value = "";
        chatInputEl.disabled = true;
        chatSendEl.disabled = true;

        appendMessage(text, "user");
        messagesHistory.push({ role: "user", content: text });
        localStorage.setItem("immobi_chat_history", JSON.stringify(messagesHistory));

        const typingEl = appendTypingIndicator();
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

        let assistantEl = null;
        let fullContent = "";

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: messagesHistory })
            });

            if (!res.ok) throw new Error("HTTP " + res.status);

            // Réponse non-streamée (mode dev sans clés)
            const contentType = res.headers.get("content-type") || "";
            if (contentType.includes("application/json")) {
                typingEl.remove();
                const data = await res.json();
                if (data.choices?.[0]?.message) {
                    const msg = data.choices[0].message.content;
                    appendMessage(msg, "assistant");
                    messagesHistory.push({ role: "assistant", content: msg });
                    localStorage.setItem("immobi_chat_history", JSON.stringify(messagesHistory));
                }
                return;
            }

            // ── Lecture du stream SSE ────────────────────────────
            typingEl.remove();
            assistantEl = document.createElement("div");
            assistantEl.className = "immobi-msg immobi-msg-assistant";
            chatMessagesEl.appendChild(assistantEl);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop(); // Ligne incomplète → garde pour le prochain chunk

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const raw = line.slice(6).trim();
                    if (raw === "[DONE]") break;
                    try {
                        const parsed = JSON.parse(raw);
                        if (parsed.error) {
                            assistantEl.innerHTML = parseMarkdown("⚠️ " + parsed.error);
                            break;
                        }
                        if (parsed.c) {
                            fullContent += parsed.c;
                            assistantEl.innerHTML = parseMarkdown(fullContent);
                            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
                        }
                    } catch (_) {}
                }
            }

            if (fullContent) {
                messagesHistory.push({ role: "assistant", content: fullContent });
                localStorage.setItem("immobi_chat_history", JSON.stringify(messagesHistory));
            }

        } catch (err) {
            typingEl?.remove();
            if (assistantEl) assistantEl.remove();
            appendMessage("⚠️ *Erreur de connexion.* Vérifiez que le serveur est démarré.", "assistant");
            console.error(err);
        } finally {
            chatInputEl.disabled = false;
            chatSendEl.disabled = false;
            chatInputEl.focus();
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
        }
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
