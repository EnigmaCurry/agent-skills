#!/usr/bin/env python3
"""Convert an AI agent JSONL session transcript to styled HTML."""

import json
import sys
import re
import html
import os
from datetime import datetime


def strip_system_tags(text):
    """Remove system-reminder, local-command-caveat, and other internal tags."""
    text = re.sub(r'<system-reminder>.*?</system-reminder>', '', text, flags=re.DOTALL)
    text = re.sub(r'<local-command-caveat>.*?</local-command-caveat>', '', text, flags=re.DOTALL)
    text = re.sub(r'<available-deferred-tools>.*?</available-deferred-tools>', '', text, flags=re.DOTALL)
    text = re.sub(r'<command-name>.*?</command-name>', '', text, flags=re.DOTALL)
    text = re.sub(r'<command-message>.*?</command-message>', '', text, flags=re.DOTALL)
    text = re.sub(r'<command-args>.*?</command-args>', '', text, flags=re.DOTALL)
    text = re.sub(r'<local-command-stdout>.*?</local-command-stdout>', '', text, flags=re.DOTALL)
    text = re.sub(r'<functions>.*?</functions>', '', text, flags=re.DOTALL)
    return text.strip()


def inline_format(text):
    """Handle inline markdown formatting."""
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code class="inline-code">\1</code>', text)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text


def md_to_html(text):
    """Simple markdown to HTML conversion."""
    text = strip_system_tags(text)
    if not text:
        return ''

    lines = text.split('\n')
    result = []
    in_code_block = False
    code_lang = ''
    code_lines = []
    in_list = False
    list_type = None

    def close_list():
        nonlocal in_list, list_type
        if in_list:
            result.append(f'</{list_type}>')
            in_list = False
            list_type = None

    def render_code_block():
        lang_label = f'<span class="code-lang">{html.escape(code_lang)}</span>' if code_lang else ''
        if code_lang == 'diff':
            diff_lines = []
            for cl in code_lines:
                escaped = html.escape(cl)
                if cl.startswith('+'):
                    diff_lines.append(f'<span class="diff-add">{escaped}</span>')
                elif cl.startswith('-'):
                    diff_lines.append(f'<span class="diff-del">{escaped}</span>')
                elif cl.startswith('@@'):
                    diff_lines.append(f'<span class="diff-hunk">{escaped}</span>')
                else:
                    diff_lines.append(escaped)
            return f'{lang_label}<pre class="code-block diff"><code>{chr(10).join(diff_lines)}</code></pre>'
        code_content = html.escape('\n'.join(code_lines))
        return f'{lang_label}<pre class="code-block"><code>{code_content}</code></pre>'

    for line in lines:
        if in_code_block:
            if line.startswith('```'):
                result.append(render_code_block())
                in_code_block = False
                code_lines = []
                code_lang = ''
            else:
                code_lines.append(line)
            continue

        if line.startswith('```'):
            close_list()
            in_code_block = True
            code_lang = line[3:].strip()
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            content = inline_format(heading_match.group(2))
            result.append(f'<h{level}>{content}</h{level}>')
            continue

        ul_match = re.match(r'^(\s*)[*\-+]\s+(.*)', line)
        if ul_match:
            content = inline_format(ul_match.group(2))
            if not in_list or list_type != 'ul':
                close_list()
                result.append('<ul>')
                in_list = True
                list_type = 'ul'
            result.append(f'<li>{content}</li>')
            continue

        ol_match = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if ol_match:
            content = inline_format(ol_match.group(2))
            if not in_list or list_type != 'ol':
                close_list()
                result.append('<ol>')
                in_list = True
                list_type = 'ol'
            result.append(f'<li>{content}</li>')
            continue

        if not line.strip():
            close_list()
            result.append('<br>')
            continue

        close_list()
        result.append(f'<p>{inline_format(line)}</p>')

    if in_code_block:
        result.append(render_code_block())
    close_list()

    return '\n'.join(result)


def parse_jsonl(filepath):
    """Parse JSONL and extract conversation messages."""
    # First pass: collect AskUserQuestion answers keyed by tool_use_id
    answers_by_id = {}
    entries = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entries.append(entry)
            if entry.get('type') == 'user':
                tool_result = entry.get('toolUseResult', {})
                if isinstance(tool_result, dict) and 'answers' in tool_result:
                    content = entry.get('message', {}).get('content', [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'tool_result':
                                answers_by_id[block.get('tool_use_id')] = tool_result['answers']

    # Second pass: build messages
    messages = []
    for entry in entries:
        msg_type = entry.get('type')
        if msg_type == 'user':
            # Skip tool_result-only messages (answers rendered on assistant side)
            tool_result = entry.get('toolUseResult', {})
            if isinstance(tool_result, dict) and 'answers' in tool_result:
                continue

            content = entry.get('message', {}).get('content', '')
            if isinstance(content, str):
                text = strip_system_tags(content)
                if text:
                    messages.append({'role': 'user', 'text': text,
                                     'timestamp': entry.get('timestamp')})
            elif isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        t = strip_system_tags(block.get('text', ''))
                        if t:
                            texts.append(t)
                    elif isinstance(block, str):
                        t = strip_system_tags(block)
                        if t:
                            texts.append(t)
                if texts:
                    messages.append({'role': 'user', 'text': '\n'.join(texts),
                                     'timestamp': entry.get('timestamp')})

        elif msg_type == 'assistant':
            content = entry.get('message', {}).get('content', [])
            parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get('type')
                if btype == 'text':
                    text = strip_system_tags(block.get('text', ''))
                    if text:
                        parts.append({'type': 'text', 'content': text})
                elif btype == 'tool_use':
                    tool_id = block.get('id', '')
                    name = block.get('name', 'unknown')
                    inp = block.get('input', {})
                    if name == 'AskUserQuestion' and tool_id in answers_by_id:
                        parts.append({
                            'type': 'ask_user',
                            'input': inp,
                            'answers': answers_by_id[tool_id]
                        })
                    else:
                        parts.append({
                            'type': 'tool_use',
                            'name': name,
                            'input': inp
                        })
            if parts:
                messages.append({'role': 'assistant', 'parts': parts,
                                 'timestamp': entry.get('timestamp')})

    return messages


def generate_html(messages, project_dir, title='Conversation'):
    """Generate styled HTML from messages."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    today = datetime.now().strftime('%Y-%m-%d')

    msg_html = []
    for msg in messages:
        if msg['role'] == 'user':
            content = md_to_html(msg['text'])
            msg_html.append(f'''<div class="message user-message">
  <div class="message-label user-label">User</div>
  <div class="message-content">{content}</div>
</div>''')
        elif msg['role'] == 'assistant':
            parts_html = []
            for part in msg['parts']:
                if part['type'] == 'text':
                    parts_html.append(md_to_html(part['content']))
                elif part['type'] == 'ask_user':
                    inp = part['input']
                    answers = part['answers']
                    questions = inp.get('questions', [])
                    for q in questions:
                        question_text = html.escape(q.get('question', ''))
                        header = html.escape(q.get('header', ''))
                        options = q.get('options', [])
                        selected = answers.get(q.get('question', ''), '')
                        options_html = []
                        for opt in options:
                            label = opt.get('label', '')
                            desc = opt.get('description', '')
                            is_selected = (label == selected)
                            sel_class = ' ask-option-selected' if is_selected else ''
                            radio = '&#9679;' if is_selected else '&#9675;'
                            radio_class = ' ask-radio-selected' if is_selected else ''
                            options_html.append(
                                f'<div class="ask-option{sel_class}">'
                                f'<span class="ask-radio{radio_class}">{radio}</span>'
                                f'<span class="ask-option-label">{html.escape(label)}</span>'
                                f'<span class="ask-option-desc">{html.escape(desc)}</span>'
                                f'</div>'
                            )
                        parts_html.append(
                            f'<div class="ask-question">'
                            f'<div class="ask-header">{header}</div>'
                            f'<div class="ask-text">{question_text}</div>'
                            f'<div class="ask-options">{"".join(options_html)}</div>'
                            f'</div>'
                        )
                elif part['type'] == 'tool_use':
                    tool_name = html.escape(part['name'])
                    tool_input = part['input']
                    # Bash tools: show the command as shell code
                    if part['name'] == 'Bash' and isinstance(tool_input, dict) and 'command' in tool_input:
                        cmd = tool_input['command']
                        cmd_lines = cmd.split('\n')
                        cmd_escaped = html.escape(cmd)
                        # Encode for data attribute (double-escape quotes)
                        cmd_data = html.escape(cmd, quote=True)
                        copy_btn = f'<button class="copy-btn" data-code="{cmd_data}" onclick="copyCode(this)">Copy</button>'
                        if len(cmd_lines) <= 20:
                            parts_html.append(f'''<div class="tool-use tool-bash">
  <div class="tool-bash-header"><span class="tool-bash-label">&#128295; {tool_name}</span>{copy_btn}</div>
  <pre class="tool-input"><code>{cmd_escaped}</code></pre>
</div>''')
                        else:
                            preview = html.escape('\n'.join(cmd_lines[:19]))
                            fade_line = html.escape(cmd_lines[19])
                            parts_html.append(f'''<details class="tool-use tool-bash">
  <summary class="tool-bash-preview">
    <span class="tool-bash-header"><span class="tool-bash-label">&#128295; {tool_name}</span>{copy_btn}</span>
    <pre class="tool-input tool-preview-code"><code>{preview}\n<span class="fade-line">{fade_line}</span></code></pre>
  </summary>
  <pre class="tool-input"><code>{cmd_escaped}</code></pre>
</details>''')
                    elif part['name'] == 'Write' and isinstance(tool_input, dict) and 'file_path' in tool_input:
                        file_path = html.escape(tool_input['file_path'])
                        raw = tool_input.get('content', '')
                        file_content = html.escape(raw)
                        lines = raw.split('\n')
                        if len(lines) <= 20:
                            preview_code = f'<pre class="tool-input"><code>{file_content}</code></pre>'
                            parts_html.append(f'''<div class="tool-use tool-write">
  <div class="tool-write-summary"><span class="tool-write-icon">&#128196;</span> <span class="tool-write-path">{file_path}</span></div>
  {preview_code}
</div>''')
                        else:
                            preview = html.escape('\n'.join(lines[:19]))
                            fade_line = html.escape(lines[19])
                            parts_html.append(f'''<details class="tool-use tool-write">
  <summary class="tool-bash-preview">
    <span class="tool-write-summary"><span class="tool-write-icon">&#128196;</span> <span class="tool-write-path">{file_path}</span></span>
    <pre class="tool-input tool-preview-code"><code>{preview}\n<span class="fade-line">{fade_line}</span></code></pre>
  </summary>
  <pre class="tool-input"><code>{file_content}</code></pre>
</details>''')
                    elif part['name'] == 'Edit' and isinstance(tool_input, dict) and 'file_path' in tool_input:
                        file_path = html.escape(tool_input['file_path'])
                        old_raw = tool_input.get('old_string', '')
                        new_raw = tool_input.get('new_string', '')
                        # Build per-line diff for both preview and full content
                        old_lines = old_raw.split('\n')
                        new_lines = new_raw.split('\n')
                        all_parts = []
                        for ol in old_lines:
                            all_parts.append(('del', ol))
                        for nl in new_lines:
                            all_parts.append(('add', nl))
                        all_lines_html = []
                        for kind, line in all_parts:
                            cls = 'diff-del' if kind == 'del' else 'diff-add'
                            all_lines_html.append(f'<span class="{cls}">{html.escape(line)}</span>')
                        full_content = chr(10).join(all_lines_html)
                        total = len(all_parts)
                        if total <= 20:
                            preview_lines = []
                            for kind, line in all_parts:
                                cls = 'diff-del' if kind == 'del' else 'diff-add'
                                preview_lines.append(f'<span class="{cls}">{html.escape(line)}</span>')
                            preview_code = f'<pre class="tool-input"><code>{chr(10).join(preview_lines)}</code></pre>'
                            parts_html.append(f'''<div class="tool-use tool-write">
  <div class="tool-write-summary"><span class="tool-write-icon">&#9998;</span> <span class="tool-write-path">{file_path}</span></div>
  {preview_code}
</div>''')
                        else:
                            preview_lines = []
                            for kind, line in all_parts[:19]:
                                cls = 'diff-del' if kind == 'del' else 'diff-add'
                                preview_lines.append(f'<span class="{cls}">{html.escape(line)}</span>')
                            fade_kind, fade_text = all_parts[19]
                            fade_cls = 'diff-del' if fade_kind == 'del' else 'diff-add'
                            preview_lines.append(f'<span class="{fade_cls} fade-line">{html.escape(fade_text)}</span>')
                            preview_code = f'<pre class="tool-input tool-preview-code"><code>{chr(10).join(preview_lines)}</code></pre>'
                            parts_html.append(f'''<details class="tool-use tool-write">
  <summary class="tool-bash-preview">
    <span class="tool-write-summary"><span class="tool-write-icon">&#9998;</span> <span class="tool-write-path">{file_path}</span></span>
    {preview_code}
  </summary>
  <pre class="tool-input"><code>{full_content}</code></pre>
</details>''')
                    else:
                        if isinstance(tool_input, dict):
                            input_display = json.dumps(tool_input, indent=2)
                        else:
                            input_display = str(tool_input)
                        input_escaped = html.escape(input_display)
                        parts_html.append(f'''<details class="tool-use">
  <summary>&#128295; {tool_name}</summary>
  <pre class="tool-input"><code>{input_escaped}</code></pre>
</details>''')
            content = '\n'.join(parts_html)
            msg_html.append(f'''<div class="message assistant-message">
  <div class="message-label assistant-label">Assistant</div>
  <div class="message-content">{content}</div>
</div>''')

    body = '\n'.join(msg_html)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ font-size: 1.5em; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #f8f9fa;
  color: #1a1a2e;
  line-height: 1.6;
}}
.accent-bar {{ height: 4px; background: linear-gradient(90deg, #2563eb, #059669); }}
.container {{ max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }}
header {{ margin-bottom: 2rem; }}
header h1 {{ font-size: 1.75rem; font-weight: 700; color: #1a1a2e; }}
header .subtitle {{ font-size: 0.9rem; color: #6b7280; margin-top: 0.25rem; }}
.message {{
  background: #fff;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border-left: 4px solid transparent;
}}
.user-message {{ border-left-color: #2563eb; }}
.assistant-message {{ border-left-color: #059669; }}
.message-label {{
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}}
.user-label {{ color: #2563eb; }}
.assistant-label {{ color: #059669; }}
.message-content p {{ margin-bottom: 0.5rem; }}
.message-content h1 {{ font-size: 1.4rem; margin: 1rem 0 0.5rem; }}
.message-content h2 {{ font-size: 1.2rem; margin: 0.8rem 0 0.4rem; }}
.message-content h3 {{ font-size: 1.05rem; margin: 0.6rem 0 0.3rem; }}
.message-content ul, .message-content ol {{ padding-left: 1.5rem; margin-bottom: 0.5rem; }}
.message-content li {{ margin-bottom: 0.25rem; }}
.message-content a {{ color: #2563eb; text-decoration: none; }}
.message-content a:hover {{ text-decoration: underline; }}
.code-block {{
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", Menlo, Consolas, monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  margin: 0.75rem 0;
}}
.code-lang {{
  display: inline-block;
  font-size: 0.7rem;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}}
.inline-code {{
  background: #e5e7eb;
  color: #d63384;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
  font-size: 0.85em;
}}
.diff-add {{ background: rgba(166,227,161,0.2); color: #a6e3a1; display: block; line-height: 1.4; }}
.diff-del {{ background: rgba(243,139,168,0.2); color: #f38ba8; display: block; line-height: 1.4; }}
.diff-hunk {{ color: #cba6f7; display: block; }}
.tool-use {{
  border: 1px solid #d1d5db;
  border-radius: 6px;
  margin: 0.75rem 0;
  font-size: 0.85rem;
}}
.tool-use summary {{
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  color: #6b7280;
  font-weight: 500;
  background: #f9fafb;
  border-radius: 6px;
}}
.tool-use[open] summary {{ border-radius: 6px 6px 0 0; border-bottom: 1px solid #d1d5db; }}
.tool-input {{
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 0.75rem;
  margin: 0;
  border-radius: 0 0 6px 6px;
  overflow-x: auto;
  font-family: "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.4;
}}
.tool-bash-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem 0;
}}
.tool-bash-label {{
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}}
.copy-btn {{
  font-size: 0.65rem;
  font-weight: 600;
  color: #6b7280;
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}}
.copy-btn:hover {{ color: #1a1a2e; border-color: #9ca3af; }}
.copy-btn.copied {{
  color: #059669;
  border-color: #059669;
  animation: copy-flash 1.5s ease forwards;
}}
@keyframes copy-flash {{
  0% {{ color: #059669; border-color: #059669; }}
  70% {{ color: #059669; border-color: #059669; }}
  100% {{ color: #6b7280; border-color: #d1d5db; }}
}}
.tool-bash > .tool-input {{
  border-radius: 0 0 6px 6px;
}}
.tool-bash:not(details) > .tool-input {{
  border-radius: 0 0 6px 6px;
}}
.tool-bash-preview {{
  list-style: none;
  padding: 0;
  background: #f9fafb;
  border-radius: 6px;
  position: relative;
}}
.tool-bash-preview::-webkit-details-marker {{ display: none; }}
.tool-bash-preview::after {{
  content: '\\25BC';
  position: absolute;
  right: 0.75rem;
  bottom: 0.5rem;
  font-size: 0.6rem;
  color: #9ca3af;
  transition: transform 0.2s ease;
}}
details[open] > .tool-bash-preview::after {{
  content: '\\25B2';
}}
.tool-preview-code {{
  border-radius: 0 0 6px 6px;
  margin: 0;
  cursor: pointer;
}}
details[open] .tool-preview-code {{
  display: none;
}}
details.tool-use[open] > .tool-bash-preview {{
  border-radius: 6px 6px 0 0;
  border-bottom: 1px solid #d1d5db;
}}
.fade-line {{ opacity: 0.35; }}
.tool-write summary {{
  display: block;
}}
.tool-write-summary {{
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
}}
.tool-write-icon {{
  font-size: 0.85rem;
  flex-shrink: 0;
}}
.tool-write-path {{
  font-family: "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
  font-size: 0.8rem;
  color: #2563eb;
  word-break: break-all;
}}
.ask-question {{
  border: 1px solid #d1d5db;
  border-radius: 8px;
  margin: 0.75rem 0;
  overflow: hidden;
  background: #f9fafb;
}}
.ask-header {{
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6b7280;
  padding: 0.6rem 0.85rem 0;
}}
.ask-text {{
  font-size: 0.85rem;
  font-weight: 600;
  color: #1a1a2e;
  padding: 0.25rem 0.85rem 0.5rem;
}}
.ask-options {{
  border-top: 1px solid #e5e7eb;
}}
.ask-option {{
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.5rem 0.85rem;
  border-bottom: 1px solid #e5e7eb;
  color: #6b7280;
  font-size: 0.8rem;
}}
.ask-option:last-child {{ border-bottom: none; }}
.ask-option-selected {{
  background: #eff6ff;
  color: #1a1a2e;
}}
.ask-radio {{
  font-size: 0.7rem;
  color: #d1d5db;
  flex-shrink: 0;
}}
.ask-radio-selected {{
  color: #2563eb;
}}
.ask-option-label {{
  font-weight: 600;
  white-space: nowrap;
}}
.ask-option-desc {{
  color: #6b7280;
  font-size: 0.75rem;
}}
footer {{
  text-align: center;
  color: #9ca3af;
  font-size: 0.8rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
}}
</style>
</head>
<body>
<div class="accent-bar"></div>
<div class="container">
<header>
  <h1>{html.escape(title)}</h1>
  <div class="subtitle">{today} &middot; {html.escape(project_dir)}</div>
</header>
{body}
<footer>Exported &middot; {now}</footer>
</div>
<script>
function copyCode(btn) {{
  var code = btn.getAttribute('data-code');
  // Decode HTML entities
  var ta = document.createElement('textarea');
  ta.innerHTML = code;
  navigator.clipboard.writeText(ta.value).then(function() {{
    var orig = btn.textContent;
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() {{
      btn.textContent = orig;
      btn.classList.remove('copied');
    }}, 1500);
  }});
  // Prevent details toggle when clicking copy
  event.stopPropagation();
  event.preventDefault();
}}
document.querySelectorAll('details.tool-use').forEach(function(el) {{
  el.addEventListener('toggle', function() {{
    var open = el.open;
    document.querySelectorAll('details.tool-use').forEach(function(d) {{
      d.open = open;
    }});
  }});
}});
</script>
</body>
</html>'''


def find_session(cwd=None):
    """Find the current session JSONL file."""
    if cwd is None:
        cwd = os.getcwd()
    slug = '-' + cwd.replace('/', '-').lstrip('-')
    projects_dir = os.path.expanduser(f'~/.claude/projects/{slug}')
    if not os.path.isdir(projects_dir):
        print(f"Error: project directory not found: {projects_dir}", file=sys.stderr)
        sys.exit(1)
    jsonl_files = [f for f in os.listdir(projects_dir) if f.endswith('.jsonl')]
    if not jsonl_files:
        print(f"Error: no session files in {projects_dir}", file=sys.stderr)
        sys.exit(1)
    jsonl_files.sort(key=lambda f: os.path.getmtime(os.path.join(projects_dir, f)), reverse=True)
    return os.path.join(projects_dir, jsonl_files[0])


def first_user_message(filepath):
    """Extract the first user message for filename generation."""
    with open(filepath, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except (json.JSONDecodeError, ValueError):
                continue
            if entry.get('type') == 'user':
                content = entry.get('message', {}).get('content', '')
                if isinstance(content, str):
                    return strip_system_tags(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            t = strip_system_tags(block.get('text', ''))
                            if t:
                                return t
    return ''


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Export conversation to HTML')
    parser.add_argument('--jsonl', help='Path to JSONL file (auto-detected if omitted)')
    parser.add_argument('--output', '-o', default='/tmp/claude-export.html',
                        help='Output HTML path (default: /tmp/claude-export.html)')
    parser.add_argument('--title', default=None,
                        help='Page title (derived from output filename if omitted)')
    parser.add_argument('--cwd', help='Working directory for session detection')
    parser.add_argument('--first-message', action='store_true',
                        help='Print first user message and exit')
    args = parser.parse_args()

    jsonl_path = args.jsonl or find_session(args.cwd)

    if args.first_message:
        print(first_user_message(jsonl_path))
        return

    project_dir = args.cwd or os.getcwd()

    title = args.title
    if not title:
        basename = os.path.splitext(os.path.basename(args.output))[0]
        title = basename.replace('-', ' ').replace('_', ' ').title()

    messages = parse_jsonl(jsonl_path)
    html_content = generate_html(messages, project_dir, title)

    with open(args.output, 'w') as f:
        f.write(html_content)

    print(f"Generated {args.output} with {len(messages)} messages")


if __name__ == '__main__':
    main()
