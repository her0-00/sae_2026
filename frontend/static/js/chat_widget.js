(function () {
    // ── Styles CSS injectés dynamiquement ─────────────────────────
    const style = document.createElement("style");
    style.innerHTML = `
        .realestatebi-chat-bubble {
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
        .realestatebi-chat-bubble:hover {
            transform: scale(1.1) rotate(5deg);
            box-shadow: 0 8px 24px rgba(124, 58, 237, 0.6);
        }
        .realestatebi-chat-bubble:active {
            transform: scale(0.95);
        }
        
        .realestatebi-chat-window {
            position: fixed;
            bottom: 85px;
            right: 24px;
            width: 380px;
            height: 70vh;
            max-height: 620px;
            min-height: 450px;
            border-radius: 16px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
            z-index: 9999;
            display: flex;
            flex-direction: row;
            overflow: hidden;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            transform: scale(0.8) translateY(40px);
            opacity: 0;
            pointer-events: none;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        .realestatebi-chat-window.open {
            transform: scale(1) translateY(0);
            opacity: 1;
            pointer-events: auto;
        }
        .realestatebi-chat-window.with-visualizer {
            width: 850px;
            max-width: 90vw;
        }
        .realestatebi-chat-window.fullscreen {
            width: 100vw !important;
            height: 100vh !important;
            max-width: none !important;
            max-height: none !important;
            bottom: 0 !important;
            right: 0 !important;
            border-radius: 0 !important;
            border: none !important;
        }
        .realestatebi-chat-window.fullscreen .realestatebi-chat-main {
            width: 380px !important;
        }
        .realestatebi-chat-window.fullscreen .realestatebi-chat-visualizer {
            flex: 1 !important;
        }
        .realestatebi-chat-main {
            width: 380px;
            height: 100%;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        .realestatebi-chat-visualizer {
            flex: 1;
            height: 100%;
            display: none;
            flex-direction: column;
            padding: 1.25rem;
            position: relative;
            background: rgba(10, 15, 30, 0.75);
            overflow: hidden;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        .realestatebi-chat-window.with-visualizer .realestatebi-chat-visualizer {
            display: flex;
        }
        .realestatebi-chat-visualizer-close {
            position: absolute;
            top: 12px;
            right: 12px;
            color: #94a3b8;
            border: none;
            background: none;
            font-size: 1rem;
            cursor: pointer;
            z-index: 10;
            transition: color 0.15s;
        }
        .realestatebi-chat-visualizer-close:hover {
            color: #fff;
        }
        .realestatebi-chat-visualizer-content {
            display: flex;
            flex-direction: column;
            height: 100%;
            width: 100%;
        }
        .realestatebi-chat-visualizer-content h4 {
            margin: 0 0 1rem 0;
            color: #fff;
            font-weight: 700;
            font-size: 0.95rem;
            background: linear-gradient(135deg, #22d3ee, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .realestatebi-chat-header {
            padding: 1rem 1.25rem;
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(37, 99, 235, 0.2));
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .realestatebi-chat-title-wrap {
            display: flex;
            flex-direction: column;
        }
        .realestatebi-chat-title {
            font-weight: 700;
            color: #fff;
            font-size: 0.95rem;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }
        .realestatebi-chat-title span.pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #22c55e;
            display: inline-block;
            box-shadow: 0 0 8px #22c55e;
            animation: pulse-active 1.8s infinite;
        }
        .realestatebi-chat-subtitle {
            font-size: 0.72rem;
            color: #94a3b8;
            margin-top: 0.15rem;
        }
        .realestatebi-chat-close {
            color: #94a3b8;
            font-size: 1.2rem;
            cursor: pointer;
            transition: color 0.15s;
            border: none;
            background: none;
            padding: 4px;
        }
        .realestatebi-chat-close:hover {
            color: #fff;
        }

        .realestatebi-chat-messages {
            flex: 1;
            padding: 1.25rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            scroll-behavior: smooth;
        }
        .realestatebi-chat-messages::-webkit-scrollbar {
            width: 5px;
        }
        .realestatebi-chat-messages::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 99px;
        }
        
        .realestatebi-msg {
            max-width: 85%;
            padding: 0.75rem 1rem;
            font-size: 0.85rem;
            line-height: 1.45;
            animation: message-fade 0.25s cubic-bezier(0, 0, 0.2, 1) forwards;
        }
        .realestatebi-msg-user {
            align-self: flex-end;
            background: #7c3aed;
            color: #fff;
            border-radius: 14px 14px 2px 14px;
            box-shadow: 0 2px 8px rgba(124, 58, 237, 0.2);
        }
        .realestatebi-msg-assistant {
            align-self: flex-start;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: #f1f5f9;
            border-radius: 14px 14px 14px 2px;
        }
        .realestatebi-msg p {
            margin: 0 0 0.5rem 0;
        }
        .realestatebi-msg p:last-child {
            margin: 0;
        }
        .realestatebi-msg strong {
            color: #fff;
            font-weight: 700;
        }
        .realestatebi-msg code {
            background: rgba(255, 255, 255, 0.1);
            padding: 1px 4px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.8rem;
            color: #f472b6;
        }
        .realestatebi-msg pre {
            background: rgba(0, 0, 0, 0.3);
            padding: 0.6rem;
            border-radius: 6px;
            overflow-x: auto;
            margin: 0.4rem 0;
        }
        .realestatebi-msg pre code {
            background: none;
            padding: 0;
            color: #f8fafc;
        }
        .realestatebi-msg ul, .realestatebi-msg ol {
            margin: 0.4rem 0;
            padding-left: 1.2rem;
        }
        .realestatebi-msg li {
            margin-bottom: 0.25rem;
        }
        .realestatebi-msg h1, .realestatebi-msg h2, .realestatebi-msg h3 {
            color: #e2e8f0;
            font-weight: 700;
            margin: 0.6rem 0 0.3rem 0;
            line-height: 1.3;
        }
        .realestatebi-msg h1 { font-size: 1rem; }
        .realestatebi-msg h2 { font-size: 0.95rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.2rem; }
        .realestatebi-msg h3 { font-size: 0.88rem; color: #a5b4fc; }
        .realestatebi-msg em { color: #cbd5e1; font-style: italic; }
        .realestatebi-msg a { color: #818cf8; text-decoration: underline; }
        
        .realestatebi-chat-input-panel {
            padding: 0.85rem 1.1rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 0.6rem;
            background: rgba(15, 23, 42, 0.5);
            align-items: center;
        }
        .realestatebi-chat-input {
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
        .realestatebi-chat-input:focus {
            background: rgba(255, 255, 255, 0.1);
            border-color: #7c3aed;
            box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.25);
        }
        .realestatebi-chat-send {
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
        .realestatebi-chat-send:hover {
            background: #6d28d9;
            transform: scale(1.05);
        }
        .realestatebi-chat-send:active {
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
        
        .realestatebi-chat-tabs {
            display: none;
            width: 100%;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(15, 23, 42, 0.6);
            padding: 8px 12px;
            gap: 8px;
            box-sizing: border-box;
            flex-shrink: 0;
        }
        .realestatebi-chat-tab {
            flex: 1;
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            color: #94a3b8;
            font-size: 0.78rem;
            cursor: pointer;
            text-align: center;
            transition: all 0.2s;
            font-weight: 600;
            outline: none;
        }
        .realestatebi-chat-tab.active {
            background: rgba(124, 58, 237, 0.2);
            border-color: #7c3aed;
            color: #fff;
            box-shadow: 0 0 10px rgba(124, 58, 237, 0.2);
        }

        @media(max-width: 768px), (max-height: 680px) {
            .realestatebi-chat-window {
                width: calc(100% - 32px) !important;
                height: calc(100% - 110px) !important;
                bottom: 80px;
                right: 16px;
                min-width: 0 !important;
                max-width: none !important;
                min-height: 0 !important;
                max-height: none !important;
                flex-direction: column !important;
            }
            .realestatebi-chat-main {
                width: 100% !important;
                height: 100% !important;
            }
            .realestatebi-chat-window.with-visualizer .realestatebi-chat-tabs {
                display: flex;
            }
            .realestatebi-chat-window.with-visualizer .realestatebi-chat-main {
                height: calc(100% - 48px) !important;
            }
            .realestatebi-chat-window.with-visualizer .realestatebi-chat-visualizer {
                display: none;
                width: 100% !important;
                height: calc(100% - 48px) !important;
                border-right: none !important;
                border-bottom: none !important;
            }
            .realestatebi-chat-window.with-visualizer.show-visualizer-only .realestatebi-chat-main {
                display: none !important;
            }
            .realestatebi-chat-window.with-visualizer.show-visualizer-only .realestatebi-chat-visualizer {
                display: flex !important;
            }
        }
        
        /* Premium Table & Visual Comparison Styling */
        .realestatebi-table-container {
            width: 100%;
            overflow-x: auto;
            margin: 0.8rem 0;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(15, 23, 42, 0.4);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }
        .realestatebi-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.78rem;
            color: #e2e8f0;
            text-align: left;
        }
        .realestatebi-table th {
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(37, 99, 235, 0.2));
            font-weight: 700;
            color: #fff;
            padding: 0.6rem 0.8rem;
            border-bottom: 2px solid rgba(255, 255, 255, 0.12);
            text-transform: uppercase;
            font-size: 0.68rem;
            letter-spacing: 0.03em;
        }
        .realestatebi-table td {
            padding: 0.6rem 0.8rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            vertical-align: middle;
            background: transparent !important; /* Force transparent cells to override main.css */
        }
        .realestatebi-table tr:last-child td {
            border-bottom: none;
        }
        .realestatebi-table tr:hover {
            background: rgba(255, 255, 255, 0.04) !important;
        }
        .realestatebi-table tr:hover td {
            background: rgba(255, 255, 255, 0.06) !important; /* Force modern hover to override main.css tr:hover td */
        }
        .realestatebi-bar-cell {
            display: flex;
            flex-direction: column;
            gap: 4px;
            min-width: 110px;
        }
        .realestatebi-bar-wrap {
            width: 100%;
            height: 5px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
            overflow: hidden;
        }
        .realestatebi-bar-fill {
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
        .realestatebi-chat-suggestions {
            display: flex;
            gap: 8px;
            padding: 0.5rem 1.1rem;
            border-top: 1px dashed rgba(255, 255, 255, 0.08);
            background: rgba(15, 23, 42, 0.4);
            flex-wrap: wrap;
            align-items: center;
            transition: all 0.3s ease;
        }
        .realestatebi-suggestion-pill {
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
        .realestatebi-suggestion-pill:hover {
            background: rgba(124, 58, 237, 0.3);
            border-color: #a78bfa;
            color: #fff;
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
        }
        .realestatebi-suggestion-pill:active {
            transform: translateY(0);
        }
        
        /* Interactive Visual Filters CSS */
        .realestatebi-visualizer-filters {
            display: none;
            flex-direction: column;
            gap: 10px;
            padding: 12px;
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            margin-bottom: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            flex-shrink: 0;
            box-sizing: border-box;
            animation: message-fade 0.2s ease-out;
        }
        .realestatebi-filters-row {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: stretch;
            width: 100%;
        }
        .realestatebi-filter-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
            flex: 1;
            min-width: 130px;
        }
        .realestatebi-filter-label {
            color: #94a3b8;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .realestatebi-filter-buttons {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        .realestatebi-filter-btn {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #cbd5e1;
            font-size: 0.7rem;
            padding: 4px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
            font-weight: 500;
            outline: none;
            user-select: none;
        }
        .realestatebi-filter-btn:hover {
            background: rgba(255, 255, 255, 0.12);
            color: #fff;
        }
        .realestatebi-filter-btn.active {
            background: rgba(124, 58, 237, 0.25);
            border-color: #7c3aed;
            color: #c084fc;
            box-shadow: 0 0 8px rgba(124, 58, 237, 0.2);
        }
        .realestatebi-filter-dpe-container {
            display: flex;
            gap: 4px;
            justify-content: space-between;
            width: 100%;
        }
        .realestatebi-filter-dpe-badge {
            flex: 1;
            height: 22px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.65rem;
            font-weight: 700;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.15s;
            user-select: none;
            color: #fff;
            text-align: center;
        }
        .realestatebi-filter-dpe-badge.inactive {
            opacity: 0.25;
            filter: grayscale(85%);
            border-color: rgba(255, 255, 255, 0.08);
            color: #cbd5e1 !important;
        }
        
        /* Slider Styling */
        .realestatebi-filter-slider {
            -webkit-appearance: none;
            width: 100%;
            height: 5px;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.1);
            outline: none;
            margin: 8px 0 4px 0;
        }
        .realestatebi-filter-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background: #7c3aed;
            cursor: pointer;
            box-shadow: 0 0 6px rgba(124, 58, 237, 0.5);
            transition: transform 0.1s;
        }
        .realestatebi-filter-slider::-webkit-slider-thumb:hover {
            transform: scale(1.2);
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
        let html = '<div class="realestatebi-table-container"><table class="realestatebi-table">';

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
                            <div class="realestatebi-bar-cell">
                                <div><strong>${cellVal}</strong></div>
                                <div class="realestatebi-bar-wrap">
                                    <div class="realestatebi-bar-fill" style="--fill-width: ${pct}%"></div>
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
    chatBubble.className = "realestatebi-chat-bubble";
    chatBubble.innerHTML = "💬";

    const chatWindow = document.createElement("div");
    chatWindow.className = "realestatebi-chat-window";
    chatWindow.innerHTML = `
        <!-- Tabs (Visible only on mobile with-visualizer) -->
        <div class="realestatebi-chat-tabs" id="realestatebi-chat-tabs">
            <button class="realestatebi-chat-tab active" id="realestatebi-chat-tab-chat">💬 Discussion</button>
            <button class="realestatebi-chat-tab" id="realestatebi-chat-tab-vis">📊 Visuel</button>
        </div>

        <!-- Visualizer Panel -->
        <div class="realestatebi-chat-visualizer" id="realestatebi-chat-visualizer">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-shrink: 0;">
                <h4 id="realestatebi-visualizer-title" style="margin: 0; font-weight: 700; font-size: 0.95rem; background: linear-gradient(135deg, #22d3ee, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Visualisation</h4>
                <div style="display: flex; gap: 8px; align-items: center; z-index: 10;">
                    <button class="realestatebi-chat-visualizer-expand" id="realestatebi-chat-visualizer-expand" title="Plein écran" style="color: #94a3b8; border: none; background: none; font-size: 1.1rem; cursor: pointer; padding: 4px; transition: color 0.15s;">⛶</button>
                    <button class="realestatebi-chat-visualizer-close" id="realestatebi-chat-visualizer-close" title="Fermer" style="color: #94a3b8; border: none; background: none; font-size: 1.1rem; cursor: pointer; padding: 4px; transition: color 0.15s;">✕</button>
                </div>
            </div>
            <div class="realestatebi-chat-visualizer-content" style="flex: 1; height: calc(100% - 30px); display: flex; flex-direction: column; overflow: hidden; width:100%;">
                <!-- Interactive Filters Panel -->
                <div class="realestatebi-visualizer-filters" id="realestatebi-visualizer-filters">
                    <div class="realestatebi-filters-row">
                        <!-- Budget Filter -->
                        <div class="realestatebi-filter-group" id="filter-group-budget">
                            <div class="realestatebi-filter-label">
                                <span>Budget Max</span>
                                <span id="filter-val-budget" style="color: #22d3ee; font-weight:700;">-</span>
                            </div>
                            <input type="range" class="realestatebi-filter-slider" id="filter-input-budget">
                        </div>
                        
                        <!-- Property Type Filter -->
                        <div class="realestatebi-filter-group" id="filter-group-type">
                            <div class="realestatebi-filter-label">Type de bien</div>
                            <div class="realestatebi-filter-buttons" id="filter-container-type"></div>
                        </div>

                        <!-- DPE Filter -->
                        <div class="realestatebi-filter-group" id="filter-group-dpe" style="flex: 1.5; min-width: 180px;">
                            <div class="realestatebi-filter-label">Classe DPE</div>
                            <div class="realestatebi-filter-dpe-container" id="filter-container-dpe"></div>
                        </div>
                    </div>
                </div>

                <div id="realestatebi-visualizer-chart-wrapper" style="display:none; height:100%; width:100%;">
                    <canvas id="realestatebi-visualizer-chart"></canvas>
                </div>
                <div id="realestatebi-visualizer-map-wrapper" style="display:none; height:100%; width:100%;">
                    <div id="realestatebi-visualizer-map" style="height:100%; width:100%; min-height: 250px; border-radius: 8px;"></div>
                </div>
            </div>
        </div>
        
        <!-- Main Chat Panel -->
        <div class="realestatebi-chat-main">
            <div class="realestatebi-chat-header">
                <div class="realestatebi-chat-title-wrap">
                    <h3 class="realestatebi-chat-title"><span class="pulse-dot"></span> RealEstateBI Copilot</h3>
                    <div class="realestatebi-chat-subtitle">Assistant IA connecté à la Base de Données</div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <button class="realestatebi-chat-clear" title="Réinitialiser le chat" style="color: #94a3b8; font-size: 1rem; cursor: pointer; border: none; background: none; padding: 4px; transition: color 0.15s;">🗑️</button>
                    <button class="realestatebi-chat-close" title="Fermer">✕</button>
                </div>
            </div>
            <div class="realestatebi-chat-messages" id="realestatebi-chat-messages">
                <div class="realestatebi-msg realestatebi-msg-assistant" data-markdown="**RealEstateBI Copilot** — outil de négociation immobilière 🏠&#10;&#10;Posez une question précise, obtenez un verdict chiffré :&#10;&#10;- *« Appartement 65m² à 280 000€ à Vannes, c'est négociable ? »*&#10;- *« Quels leviers de négo pour une maison DPE F à Lorient ? »*&#10;- *« Prix du marché appartement proche gare à Hennebont »*"></div>
            </div>
            <div class="realestatebi-chat-suggestions" id="realestatebi-chat-suggestions" style="display: none;"></div>
            <div class="realestatebi-chat-input-panel">
                <input type="text" class="realestatebi-chat-input" id="realestatebi-chat-input" placeholder="Posez une question sur Vannes, Hennebont..." autocomplete="off">
                <button class="realestatebi-chat-send" id="realestatebi-chat-send">➔</button>
            </div>
        </div>
    `;

    document.body.appendChild(chatBubble);
    document.body.appendChild(chatWindow);

    function selectTab(tabName) {
        const tabChat = document.getElementById("realestatebi-chat-tab-chat");
        const tabVis = document.getElementById("realestatebi-chat-tab-vis");
        if (tabName === "chat") {
            chatWindow.classList.remove("show-visualizer-only");
            tabChat.classList.add("active");
            tabVis.classList.remove("active");
        } else {
            chatWindow.classList.add("show-visualizer-only");
            tabVis.classList.add("active");
            tabChat.classList.remove("active");
            if (currentVisualMap) {
                setTimeout(() => {
                    currentVisualMap.invalidateSize();
                }, 200);
            }
        }
    }

    document.getElementById("realestatebi-chat-tab-chat").addEventListener("click", () => selectTab("chat"));
    document.getElementById("realestatebi-chat-tab-vis").addEventListener("click", () => selectTab("vis"));

    document.getElementById("realestatebi-chat-visualizer-close").addEventListener("click", () => {
        chatWindow.classList.remove("with-visualizer");
        chatWindow.classList.remove("fullscreen");
        selectTab("chat");
        const expandBtn = document.getElementById("realestatebi-chat-visualizer-expand");
        if (expandBtn) {
            expandBtn.innerHTML = "⛶";
            expandBtn.title = "Plein écran";
        }
    });

    document.getElementById("realestatebi-chat-visualizer-expand").addEventListener("click", () => {
        chatWindow.classList.toggle("fullscreen");
        const expandBtn = document.getElementById("realestatebi-chat-visualizer-expand");
        if (chatWindow.classList.contains("fullscreen")) {
            expandBtn.innerHTML = "🗗";
            expandBtn.title = "Quitter le plein écran";
        } else {
            expandBtn.innerHTML = "⛶";
            expandBtn.title = "Plein écran";
        }

        if (currentVisualMap) {
            setTimeout(() => {
                currentVisualMap.invalidateSize();
            }, 350);
        }
    });

    // ── Variables d'état conversationnel ──────────────────────────
    let isWindowOpen = localStorage.getItem("realestatebi_chat_open") === "true";
    let messagesHistory = [];
    try {
        const savedHistory = localStorage.getItem("realestatebi_chat_history");
        if (savedHistory) {
            messagesHistory = JSON.parse(savedHistory);
        }
    } catch (e) {
        console.error("Erreur lors de la lecture de l'historique de chat", e);
    }

    const chatMessagesEl = document.getElementById("realestatebi-chat-messages");
    const chatSuggestionsEl = document.getElementById("realestatebi-chat-suggestions");
    const chatInputEl = document.getElementById("realestatebi-chat-input");
    const chatSendEl = document.getElementById("realestatebi-chat-send");

    // Formater le message de bienvenue initial (depuis l'attribut data-markdown)
    const firstMsg = chatMessagesEl.querySelector(".realestatebi-msg-assistant[data-markdown]");
    if (firstMsg) {
        const md = firstMsg.getAttribute("data-markdown")
            .replace(/&#10;/g, "\n");
        firstMsg.innerHTML = parseMarkdown(md);
    }

    // Restaurer l'historique dans le DOM
    if (messagesHistory.length > 0) {
        messagesHistory.forEach(msg => {
            appendMessage(msg.content, msg.role === "assistant" ? "assistant" : "user", msg.widget, msg.sql);
        });

        // Rendre automatiquement le dernier widget disponible de l'historique au chargement
        const lastMsgWithWidget = [...messagesHistory].reverse().find(m => m.role === "assistant" && m.widget && m.widget.type !== "none");
        if (lastMsgWithWidget) {
            setTimeout(() => {
                handleWidgetResponse(lastMsgWithWidget.widget, false);
            }, 500);
        }
    }

    // ── Gestionnaires d'évènements ────────────────────────────────
    chatBubble.addEventListener("click", () => {
        isWindowOpen = !isWindowOpen;
        localStorage.setItem("realestatebi_chat_open", isWindowOpen);
        if (isWindowOpen) {
            openWindow();
        } else {
            closeWindow();
        }
    });

    chatWindow.querySelector(".realestatebi-chat-close").addEventListener("click", () => {
        closeWindow();
    });

    chatWindow.querySelector(".realestatebi-chat-clear").addEventListener("click", () => {
        if (confirm("Voulez-vous réinitialiser l'historique de discussion ?")) {
            messagesHistory = [];
            localStorage.removeItem("realestatebi_chat_history");
            const messages = chatMessagesEl.querySelectorAll(".realestatebi-msg");
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
        localStorage.setItem("realestatebi_chat_open", "false");
        chatWindow.classList.remove("open");
        chatWindow.classList.remove("fullscreen");
        const expandBtn = document.getElementById("realestatebi-chat-visualizer-expand");
        if (expandBtn) {
            expandBtn.innerHTML = "⛶";
            expandBtn.title = "Plein écran";
        }
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
            pill.className = "realestatebi-suggestion-pill";
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
    localStorage.setItem = function (key, value) {
        originalSetItem.apply(this, arguments);
        if (key === "selected_commune_name") {
            window.dispatchEvent(new CustomEvent("realestatebiCommuneChanged", { detail: value }));
        }
    };

    // Écouter les évènements de changement de commune
    window.addEventListener("realestatebiCommuneChanged", (e) => {
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

    // ── Dynamic Library Loader & Rendering Helpers ────────────────
    function loadScript(url) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${url}"]`)) {
                resolve();
                return;
            }
            const script = document.createElement('script');
            script.src = url;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    function loadStylesheet(url) {
        if (document.querySelector(`link[href="${url}"]`)) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        document.head.appendChild(link);
    }

    async function ensureChartJsLoaded() {
        if (window.Chart) return;
        await loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js");
    }

    async function ensureLeafletLoaded() {
        if (!window.L) {
            loadStylesheet("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
            await loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
        }
        if (window.L && !L.markerClusterGroup) {
            loadStylesheet("https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css");
            loadStylesheet("https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css");
            await loadScript("https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js");
        }
    }

    let currentVisualChart = null;
    let currentVisualMap = null;

    async function handleWidgetResponse(widget, autoSwitch = true) {
        if (!widget || widget.type === 'none') {
            chatWindow.classList.remove("with-visualizer");
            return;
        }

        const titleEl = document.getElementById("realestatebi-visualizer-title");
        const chartWrapper = document.getElementById("realestatebi-visualizer-chart-wrapper");
        const mapWrapper = document.getElementById("realestatebi-visualizer-map-wrapper");

        let titleText = widget.title || "Visualisation";
        if (widget.type === 'map' && widget.map_config && widget.map_config.poi_markers && widget.map_config.poi_markers.length > 0) {
            const names = widget.map_config.poi_markers.map(p => p.popup).join(" & ");
            titleText += ` (${names})`;
        }
        titleEl.innerText = titleText;
        chatWindow.classList.add("with-visualizer");

        const filterPanel = document.getElementById("realestatebi-visualizer-filters");

        if (widget.type === 'chart') {
            chartWrapper.style.display = "block";
            mapWrapper.style.display = "none";
            if (filterPanel) filterPanel.style.display = "none";
            try {
                await ensureChartJsLoaded();
                renderVisualChart(widget.chart_config);
            } catch (err) {
                console.error("Erreur de chargement Chart.js:", err);
            }
        } else if (widget.type === 'map') {
            mapWrapper.style.display = "block";
            chartWrapper.style.display = "none";
            if (filterPanel) filterPanel.style.display = "flex";
            
            // Attendre 150ms pour que la div soit dimensionnée par le navigateur (Leaflet a besoin d'une taille non-nulle au chargement)
            setTimeout(async () => {
                try {
                    await ensureLeafletLoaded();
                    renderVisualMap(widget.map_config);
                    if (currentVisualMap) {
                        currentVisualMap.invalidateSize();
                    }
                } catch (err) {
                    console.error("Erreur de chargement Leaflet:", err);
                }
            }, 150);
        }

        // Commutateur d'onglets automatique sur mobile vers le visuel (ou en hauteur réduite de viewport)
        if (autoSwitch && (window.innerWidth <= 768 || window.innerHeight <= 680)) {
            selectTab("vis");
        }
    }

    function renderVisualChart(config) {
        config = config || {};
        if (currentVisualChart) {
            currentVisualChart.destroy();
            currentVisualChart = null;
        }

        const ctx = document.getElementById('realestatebi-visualizer-chart').getContext('2d');

        const dpeColors = {
            'A': '#15803d', 'B': '#16a34a', 'C': '#84cc16', 'D': '#facc15', 'E': '#f97316', 'F': '#dc2626', 'G': '#7f1d1d'
        };

        const datasets = (config.datasets || []).map((ds, index) => {
            const colorPalette = [
                '#0ea5e9', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b', '#ef4444', '#10b981'
            ];

            let bgColors = [];
            let borderColors = [];

            if (config.labels && config.labels.every(l => ['A', 'B', 'C', 'D', 'E', 'F', 'G'].includes(String(l).toUpperCase()))) {
                bgColors = config.labels.map(l => dpeColors[String(l).toUpperCase()] + '66');
                borderColors = config.labels.map(l => dpeColors[String(l).toUpperCase()]);
            } else {
                if (config.type === 'pie' || config.type === 'doughnut' || (config.type === 'bar' && config.datasets.length === 1)) {
                    bgColors = config.labels.map((_, i) => colorPalette[i % colorPalette.length] + '80');
                    borderColors = config.labels.map((_, i) => colorPalette[i % colorPalette.length]);
                } else {
                    const dsColor = colorPalette[index % colorPalette.length];
                    bgColors = config.labels.map(() => dsColor + '80');
                    borderColors = config.labels.map(() => dsColor);
                }
            }

            return {
                ...ds,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 2,
                borderRadius: 6,
                tension: 0.4,
                fill: config.type === 'line' ? true : false
            };
        });

        currentVisualChart = new Chart(ctx, {
            type: config.type || 'bar',
            data: {
                labels: config.labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#cbd5e1' }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.08)' },
                        ticks: { color: '#cbd5e1' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.08)' },
                        ticks: { color: '#cbd5e1' }
                    }
                }
            }
        });
    }

    function renderVisualMap(config) {
        const POI_STYLE = {
            gare: { emoji: '🚂', color: '#7c3aed' },
            ecole: { emoji: '🎓', color: '#2563eb' },
            universite: { emoji: '🏛️', color: '#0d9488' },
            cinema: { emoji: '🎬', color: '#db2777' },
            salle_sport: { emoji: '💪', color: '#ea580c' },
            restaurant: { emoji: '🍽️', color: '#ca8a04' },
            pharmacie: { emoji: '💊', color: '#16a34a' },
            commerce: { emoji: '🛒', color: '#0284c7' },
            transport: { emoji: '🚌', color: '#6366f1' },
            parking: { emoji: '🚗', color: '#64748b' },
            aeroport: { emoji: '🛫', color: '#0ea5e9' },
        };

        config = config || {};
        if (currentVisualMap) {
            currentVisualMap.remove();
            currentVisualMap = null;
        }

        const wrapper = document.getElementById('realestatebi-visualizer-map-wrapper');
        wrapper.innerHTML = '<div id="realestatebi-visualizer-map" style="height:100%; width:100%; min-height: 250px; border-radius: 8px;"></div>';

        const center = config.center || [47.218371, -1.553621];
        currentVisualMap = L.map('realestatebi-visualizer-map').setView(center, config.zoom || 13);

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri'
        }).addTo(currentVisualMap);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; CartoDB'
        }).addTo(currentVisualMap);

        const markersData = config.markers || [];

        // 1. Initialize Budget Filter
        const prices = markersData.map(m => m.valeur_fonciere).filter(p => p !== null && p !== undefined);
        const budgetGroup = document.getElementById("filter-group-budget");
        const budgetSlider = document.getElementById("filter-input-budget");
        const budgetVal = document.getElementById("filter-val-budget");

        let hasBudget = prices.length > 0;
        if (hasBudget) {
            const minPrice = Math.min(...prices);
            const maxPrice = Math.max(...prices);

            budgetSlider.min = minPrice;
            budgetSlider.max = maxPrice;
            budgetSlider.value = maxPrice;

            budgetVal.innerText = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(maxPrice);
            budgetGroup.style.display = "flex";

            budgetSlider.oninput = function () {
                budgetVal.innerText = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(this.value);
                applyFilters();
            };
        } else {
            budgetGroup.style.display = "none";
        }

        // 2. Initialize Property Type Filter
        const types = [...new Set(markersData.map(m => m.type_local).filter(Boolean))];
        const typeGroup = document.getElementById("filter-group-type");
        const typeContainer = document.getElementById("filter-container-type");

        typeContainer.innerHTML = "";
        let hasTypes = types.length > 1;
        if (hasTypes) {
            types.forEach(t => {
                const btn = document.createElement("button");
                btn.className = "realestatebi-filter-btn active";
                btn.innerText = t;
                btn.dataset.type = t;
                btn.onclick = function () {
                    btn.classList.toggle("active");
                    applyFilters();
                };
                typeContainer.appendChild(btn);
            });
            typeGroup.style.display = "flex";
        } else {
            typeGroup.style.display = "none";
        }

        // 3. Initialize DPE Filter
        const dpesInData = [...new Set(markersData.map(m => m.dpe_classe).filter(Boolean).map(d => d.toUpperCase()))];
        const dpeGroup = document.getElementById("filter-group-dpe");
        const dpeContainer = document.getElementById("filter-container-dpe");

        dpeContainer.innerHTML = "";
        const allDpes = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
        const dpeColors = {
            'A': '#15803d', 'B': '#16a34a', 'C': '#84cc16', 'D': '#facc15', 'E': '#f97316', 'F': '#dc2626', 'G': '#7f1d1d'
        };

        let hasDpes = dpesInData.length > 0;
        if (hasDpes) {
            allDpes.forEach(d => {
                const badge = document.createElement("div");
                badge.className = "realestatebi-filter-dpe-badge";
                if (!dpesInData.includes(d)) {
                    badge.className += " inactive";
                }
                badge.innerText = d;
                badge.dataset.dpe = d;
                badge.style.backgroundColor = dpeColors[d];
                badge.onclick = function () {
                    badge.classList.toggle("inactive");
                    applyFilters();
                };
                dpeContainer.appendChild(badge);
            });
            dpeGroup.style.display = "flex";
        } else {
            dpeGroup.style.display = "none";
        }

        const markersGroup = L.markerClusterGroup({
            showCoverageOnHover: false,
            maxClusterRadius: 40
        });
        currentVisualMap.addLayer(markersGroup);

        function applyFilters() {
            markersGroup.clearLayers();

            const maxBudget = hasBudget ? parseFloat(budgetSlider.value) : Infinity;

            const activeTypes = hasTypes
                ? Array.from(typeContainer.querySelectorAll(".realestatebi-filter-btn.active")).map(b => b.dataset.type)
                : types;

            const activeDpes = hasDpes
                ? Array.from(dpeContainer.querySelectorAll(".realestatebi-filter-dpe-badge:not(.inactive)")).map(b => b.dataset.dpe)
                : allDpes;

            const filteredMarkers = markersData.filter(m => {
                if (hasBudget && m.valeur_fonciere !== null && m.valeur_fonciere !== undefined) {
                    if (m.valeur_fonciere > maxBudget) return false;
                }
                if (hasTypes && m.type_local) {
                    if (!activeTypes.includes(m.type_local)) return false;
                }
                if (hasDpes && m.dpe_classe) {
                    if (!activeDpes.includes(m.dpe_classe.toUpperCase())) return false;
                }
                return true;
            });

            filteredMarkers.forEach(m => {
                if (m.lat && m.lng) {
                    let marker;
                    const poi = POI_STYLE[m.type];
                    if (poi) {
                        const icon = L.divIcon({
                            className: '',
                            html: `<div style="background:${poi.color};color:white;font-size:0.95rem;padding:4px;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);">${poi.emoji}</div>`,
                            iconSize: [28, 28],
                            iconAnchor: [14, 14]
                        });
                        marker = L.marker([m.lat, m.lng], { icon });
                    } else if (m.valeur_fonciere) {
                        const prix_k = Math.round(m.valeur_fonciere / 1000) + ' k€';
                        const icon = L.divIcon({
                            className: '',
                            html: `<div style="background:#dc2626;color:white;font-weight:700;font-size:0.8rem;padding:2px 6px;border-radius:12px;border:1.5px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);white-space:nowrap;">${prix_k}</div>`,
                            iconSize: [50, 24],
                            iconAnchor: [25, 12]
                        });
                        marker = L.marker([m.lat, m.lng], { icon });
                    } else {
                        marker = L.marker([m.lat, m.lng]);
                    }
                    marker.bindPopup(`<div style="font-size:0.85rem;line-height:1.4;">${m.popup}</div>`);
                    markersGroup.addLayer(marker);
                }
            });

            try {
                const bounds = markersGroup.getBounds();
                if (bounds.isValid()) {
                    currentVisualMap.fitBounds(bounds, { padding: [25, 25] });
                }
            } catch (e) {
                console.log("Error fitting map bounds:", e);
            }
        }

        if (config.poi_markers && config.poi_markers.length > 0) {
            console.log("POI markers received:", config.poi_markers);
            config.poi_markers.forEach(poi => {
                if (poi.lat && poi.lng) {
                    let marker;
                    const style = POI_STYLE[poi.type];
                    if (style) {
                        const icon = L.divIcon({
                            className: '',
                            html: `<div style="background:${style.color};color:white;font-size:1.1rem;padding:6px;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;border:2.5px solid #dc2626;box-shadow:0 0 12px ${style.color};box-sizing:border-box;">${style.emoji}</div>`,
                            iconSize: [36, 36],
                            iconAnchor: [18, 18]
                        });
                        marker = L.marker([poi.lat, poi.lng], { icon, zIndexOffset: 1000 });
                    } else {
                        const redIcon = new L.Icon({
                            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                            iconSize: [25, 41],
                            iconAnchor: [12, 41],
                            popupAnchor: [1, -34],
                            shadowSize: [41, 41]
                        });
                        marker = L.marker([poi.lat, poi.lng], { icon: redIcon, zIndexOffset: 1000 });
                    }
                    console.log("Rendering POI marker on map:", poi.popup, "at", poi.lat, poi.lng);
                    marker.bindPopup(`<div class="text-red-700 font-bold font-sans text-sm p-1">🎯 ${poi.popup}</div>`)
                        .addTo(currentVisualMap);
                }
            });
        }

        applyFilters();
    }

    // ── Envoi du message avec streaming SSE ─────────────────────
    async function sendMessage() {
        const text = chatInputEl.value.trim();
        if (!text) return;

        chatInputEl.value = "";
        chatInputEl.disabled = true;
        chatSendEl.disabled = true;

        appendMessage(text, "user");
        messagesHistory.push({ role: "user", content: text });
        localStorage.setItem("realestatebi_chat_history", JSON.stringify(messagesHistory));

        let typingEl = appendTypingIndicator();
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

        let assistantEl = null;
        let fullContent = "";
        let receivedWidget = null;
        let receivedSql = null;

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
                    localStorage.setItem("realestatebi_chat_history", JSON.stringify(messagesHistory));
                }
                return;
            }

            // ── Lecture du stream SSE ────────────────────────────
            typingEl.remove();
            assistantEl = document.createElement("div");
            assistantEl.className = "realestatebi-msg realestatebi-msg-assistant";
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
                        if (parsed.widget) {
                            receivedWidget = parsed.widget;
                            handleWidgetResponse(parsed.widget);
                        }
                        if (parsed.sql) {
                            receivedSql = parsed.sql;
                        }
                        if (parsed.c) {
                            fullContent += parsed.c;
                            assistantEl.innerHTML = parseMarkdown(fullContent);
                            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
                        }
                    } catch (_) { }
                }
            }

            if (fullContent) {
                messagesHistory.push({ role: "assistant", content: fullContent, widget: receivedWidget, sql: receivedSql });
                localStorage.setItem("realestatebi_chat_history", JSON.stringify(messagesHistory));
                if (receivedWidget && receivedWidget.type !== "none") {
                    addWidgetBadgeToBubble(assistantEl, receivedWidget);
                }
                if (receivedSql) {
                    addSqlDetailsToBubble(assistantEl, receivedSql);
                }
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

    function addWidgetBadgeToBubble(bubbleEl, widget) {
        if (!widget || widget.type === "none" || !bubbleEl) return;
        const badge = document.createElement("button");
        badge.className = "realestatebi-msg-widget-badge";
        badge.innerHTML = widget.type === "map" ? "🗺️ Voir la carte" : "📊 Voir le graphique";
        badge.style.cssText = `
            display: block;
            margin-top: 8px;
            background: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.25);
            color: #fff;
            font-size: 0.74rem;
            padding: 3px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
            font-weight: 500;
        `;
        badge.addEventListener("mouseenter", () => {
            badge.style.background = "rgba(255, 255, 255, 0.25)";
        });
        badge.addEventListener("mouseleave", () => {
            badge.style.background = "rgba(255, 255, 255, 0.15)";
        });
        badge.addEventListener("click", () => {
            handleWidgetResponse(widget);
        });
        bubbleEl.appendChild(badge);
    }

    function appendMessage(content, role, widget = null, sql = null) {
        const msg = document.createElement("div");
        msg.className = `realestatebi-msg realestatebi-msg-${role}`;
        msg.innerHTML = parseMarkdown(content);
        if (widget && widget.type !== "none") {
            addWidgetBadgeToBubble(msg, widget);
        }
        if (sql) {
            addSqlDetailsToBubble(msg, sql);
        }
        chatMessagesEl.appendChild(msg);
        return msg;
    }

    function addSqlDetailsToBubble(bubbleEl, sql) {
        if (!sql || !bubbleEl) return;
        const details = document.createElement("details");
        details.className = "realestatebi-chat-sql-details";
        details.style.cssText = "margin-top: 8px; font-size: 0.8rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px;";
        details.innerHTML = `
            <summary style="cursor: pointer; color: #38bdf8; font-weight: 600; outline: none; user-select: none;">🔍 Voir la requête SQL générée</summary>
            <pre style="background: #0f172a; padding: 10px; border-radius: 6px; margin-top: 6px; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #a5f3fc; border: 1px solid #1e293b; line-height: 1.4; white-space: pre-wrap; word-break: break-all;"><code class="language-sql">${escapeHtml(sql)}</code></pre>
        `;
        bubbleEl.appendChild(details);
    }

    function escapeHtml(str) {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function appendTypingIndicator() {
        const msg = document.createElement("div");
        msg.className = "realestatebi-msg realestatebi-msg-assistant";
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
