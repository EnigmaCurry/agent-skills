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
    text = re.sub(r'<bash-input>(.*?)</bash-input>', r'`\1`', text, flags=re.DOTALL)
    text = re.sub(r'<bash-stdout>.*?</bash-stdout>', '', text, flags=re.DOTALL)
    text = re.sub(r'<bash-stderr>.*?</bash-stderr>', '', text, flags=re.DOTALL)
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
    in_table = False

    def close_list():
        nonlocal in_list, list_type
        if in_list:
            result.append(f'</{list_type}>')
            in_list = False
            list_type = None

    def close_table():
        nonlocal in_table
        if in_table:
            result.append('</tbody></table>')
            in_table = False

    def render_code_block():
        lang_label = f'<span class="code-lang">{html.escape(code_lang)}</span>' if code_lang else ''
        raw = '\n'.join(code_lines)
        data = html.escape(raw, quote=True)
        copy_btn = f'<button class="copy-btn code-copy-btn" data-code="{data}" onclick="copyCode(this)">Copy</button>'
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
            return f'<div class="code-block-wrap">{lang_label}{copy_btn}<pre class="code-block diff"><code>{chr(10).join(diff_lines)}</code></pre></div>'
        code_content = html.escape(raw)
        return f'<div class="code-block-wrap">{lang_label}{copy_btn}<pre class="code-block"><code>{code_content}</code></pre></div>'

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

        # Table rows: lines starting and ending with |
        if re.match(r'^\|.*\|$', line.strip()):
            # Skip separator rows like |---|---|
            if re.match(r'^\|[\s\-:|]+\|$', line.strip()):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if not in_table:
                close_list()
                in_table = True
                header_cells = ''.join(f'<th>{inline_format(c)}</th>' for c in cells)
                result.append(f'<table><thead><tr>{header_cells}</tr></thead><tbody>')
            else:
                row_cells = ''.join(f'<td>{inline_format(c)}</td>' for c in cells)
                result.append(f'<tr>{row_cells}</tr>')
            continue

        close_table()

        if not line.strip():
            close_list()
            result.append('<br>')
            continue

        close_list()
        result.append(f'<p>{inline_format(line)}</p>')

    if in_code_block:
        result.append(render_code_block())
    close_table()
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
    msg_idx = 0
    for msg in messages:
        if msg['role'] == 'user':
            content = md_to_html(msg['text'])
            msg_html.append(f'''<div class="message user-message" id="msg-{msg_idx}">
  <a class="message-label user-label" href="#msg-{msg_idx}" onclick="updateHash(this)">User</a>
  <div class="message-content">{content}</div>
</div>''')
            msg_idx += 1
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
  <div class="tool-bash-header"><span class="tool-bash-label">&#128187; {tool_name}</span>{copy_btn}</div>
  <pre class="tool-input"><code>{cmd_escaped}</code></pre>
</div>''')
                        else:
                            preview = html.escape('\n'.join(cmd_lines[:19]))
                            fade_line = html.escape(cmd_lines[19])
                            parts_html.append(f'''<details class="tool-use tool-bash">
  <summary class="tool-bash-preview">
    <span class="tool-bash-header"><span class="tool-bash-label">&#128187; {tool_name}</span>{copy_btn}</span>
    <pre class="tool-input tool-preview-code"><code>{preview}\n<span class="fade-line">{fade_line}</span></code></pre>
  </summary>
  <pre class="tool-input"><code>{cmd_escaped}</code></pre>
</details>''')
                    elif part['name'] == 'Read' and isinstance(tool_input, dict) and 'file_path' in tool_input:
                        file_path = html.escape(tool_input['file_path'])
                        parts_html.append(f'''<div class="tool-use tool-write">
  <div class="tool-write-summary"><span class="tool-write-icon">&#128065;</span> <span class="tool-write-path">{file_path}</span></div>
</div>''')
                    elif part['name'] == 'Grep' and isinstance(tool_input, dict) and 'pattern' in tool_input:
                        pattern = html.escape(tool_input['pattern'])
                        path = html.escape(tool_input.get('path', ''))
                        path_suffix = f' in <span class="tool-write-path">{path}</span>' if path else ''
                        parts_html.append(f'''<div class="tool-use tool-write">
  <div class="tool-write-summary"><span class="tool-write-icon">&#128270;</span> <code class="inline-code">{pattern}</code>{path_suffix}</div>
</div>''')
                    elif part['name'] == 'Glob' and isinstance(tool_input, dict) and 'pattern' in tool_input:
                        pattern = html.escape(tool_input['pattern'])
                        parts_html.append(f'''<div class="tool-use tool-write">
  <div class="tool-write-summary"><span class="tool-write-icon">&#128270;</span> <code class="inline-code">{pattern}</code></div>
</div>''')
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
                        full_content = ''.join(all_lines_html)
                        total = len(all_parts)
                        if total <= 20:
                            preview_lines = []
                            for kind, line in all_parts:
                                cls = 'diff-del' if kind == 'del' else 'diff-add'
                                preview_lines.append(f'<span class="{cls}">{html.escape(line)}</span>')
                            preview_code = f'<pre class="tool-input"><code>{"".join(preview_lines)}</code></pre>'
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
                            preview_code = f'<pre class="tool-input tool-preview-code"><code>{"".join(preview_lines)}</code></pre>'
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
            msg_html.append(f'''<div class="message assistant-message" id="msg-{msg_idx}">
  <a class="message-label assistant-label" href="#msg-{msg_idx}" onclick="updateHash(this)">Assistant</a>
  <div class="message-content">{content}</div>
</div>''')
            msg_idx += 1

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
:root {{
  --bg: #ffffff;
  --fg: #111827;
  --fg-muted: #4b5563;
  --fg-faint: #9ca3af;
  --border: #d1d5db;
  --border-light: #e5e7eb;
  --card-bg: #f9fafb;
  --msg-bg: #ffffff;
  --msg-shadow: rgba(0,0,0,0.08);
  --code-bg: #1e1e2e;
  --code-fg: #cdd6f4;
  --inline-code-bg: #e5e7eb;
  --inline-code-fg: #be185d;
  --link: #2563eb;
  --user-accent: #2563eb;
  --assistant-accent: #059669;
  --table-header-bg: #f3f4f6;
  --table-stripe-bg: #f9fafb;
  --ask-bg: #f9fafb;
  --ask-selected-bg: #eff6ff;
  --copy-btn-hover: #111827;
  --diff-add-bg: rgba(166,227,161,0.2);
  --diff-add-fg: #166534;
  --diff-del-bg: rgba(243,139,168,0.2);
  --diff-del-fg: #991b1b;
}}
body.dark {{
  --bg: #0f172a;
  --fg: #e2e8f0;
  --fg-muted: #94a3b8;
  --fg-faint: #64748b;
  --border: #334155;
  --border-light: #1e293b;
  --card-bg: #1e293b;
  --msg-bg: #1e293b;
  --msg-shadow: rgba(0,0,0,0.3);
  --code-bg: #0f172a;
  --code-fg: #cdd6f4;
  --inline-code-bg: #334155;
  --inline-code-fg: #f472b6;
  --link: #60a5fa;
  --user-accent: #3b82f6;
  --assistant-accent: #10b981;
  --table-header-bg: #1e293b;
  --table-stripe-bg: #162032;
  --ask-bg: #1e293b;
  --ask-selected-bg: #1e3a5f;
  --copy-btn-hover: #e2e8f0;
  --diff-add-bg: rgba(166,227,161,0.15);
  --diff-add-fg: #a6e3a1;
  --diff-del-bg: rgba(243,139,168,0.15);
  --diff-del-fg: #f38ba8;
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
}}
.accent-bar {{ height: 4px; background: linear-gradient(90deg, #2563eb, #059669); }}
.container {{ max-width: 1350px; margin: 0 auto; padding: 2rem 1.5rem; margin-right: 180px; }}
body.no-minimap .container {{ margin-right: auto; }}
body.no-minimap .minimap {{ display: none; }}
header {{ margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: flex-start; }}
header h1 {{ font-size: 1.75rem; font-weight: 700; color: var(--fg); }}
header .subtitle {{ font-size: 0.9rem; color: var(--fg-muted); margin-top: 0.25rem; }}
.settings-btn {{
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 0.2s;
  padding: 0.25rem;
  line-height: 1;
}}
.settings-btn:hover {{ opacity: 1; }}
.modal-overlay {{
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 200;
  justify-content: center;
  align-items: center;
}}
.modal-overlay.open {{ display: flex; }}
.modal {{
  background: var(--msg-bg);
  border-radius: 12px;
  padding: 1.5rem;
  min-width: 320px;
  max-width: 400px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.3);
  color: var(--fg);
}}
.modal-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}}
.modal-header h2 {{ font-size: 1.1rem; font-weight: 700; }}
.modal-close {{
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--fg-muted);
  line-height: 1;
}}
.modal-close:hover {{ color: var(--fg); }}
.setting-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-light);
}}
.setting-label {{
  font-weight: 600;
  font-size: 0.85rem;
}}
.setting-control {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--fg-muted);
}}
.keybinds {{
  margin-top: 1rem;
}}
.keybinds h3 {{
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--fg-muted);
  margin-bottom: 0.5rem;
}}
.keybind {{
  font-size: 0.8rem;
  color: var(--fg-muted);
  padding: 0.25rem 0;
}}
.keybind kbd {{
  display: inline-block;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--fg);
  margin-right: 0.4rem;
  min-width: 1.5rem;
  text-align: center;
}}
.toggle-switch {{
  position: relative;
  width: 2.5rem;
  height: 1.4rem;
  background: var(--border);
  border-radius: 0.7rem;
  cursor: pointer;
  transition: background 0.2s;
}}
.toggle-switch.active {{ background: #2563eb; }}
.toggle-switch::after {{
  content: '';
  position: absolute;
  top: 0.15rem;
  left: 0.15rem;
  width: 1.1rem;
  height: 1.1rem;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}}
.toggle-switch.active::after {{ transform: translateX(1.1rem); }}
.message {{
  background: var(--msg-bg);
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px var(--msg-shadow);
  border-left: 4px solid transparent;
}}
.user-message {{ border-left-color: var(--user-accent); }}
.assistant-message {{ border-left-color: var(--assistant-accent); }}
body.chat-mode .container {{ max-width: 100%; padding: 2rem 3rem; margin-right: 180px; }}
body.chat-mode.no-minimap .container {{ margin-right: 0; }}
body.chat-mode .message {{ max-width: 75%; }}
body.chat-mode .user-message {{
  margin-left: auto;
  border-left: none;
  border-right: 4px solid var(--user-accent);
}}
body.chat-mode .assistant-message {{
  margin-right: auto;
}}
.message-label {{
  display: block;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
  text-decoration: none;
  cursor: pointer;
}}
.message-label:hover {{ opacity: 0.7; }}
.message.active {{
  box-shadow: 0 0 0 2px var(--user-accent), 0 1px 3px var(--msg-shadow);
}}
.user-label {{ color: var(--user-accent); }}
.assistant-label {{ color: var(--assistant-accent); }}
.message-content p {{ margin-bottom: 0.5rem; }}
.message-content h1 {{ font-size: 1.4rem; margin: 1rem 0 0.5rem; }}
.message-content h2 {{ font-size: 1.2rem; margin: 0.8rem 0 0.4rem; }}
.message-content h3 {{ font-size: 1.05rem; margin: 0.6rem 0 0.3rem; }}
.message-content ul, .message-content ol {{ padding-left: 1.5rem; margin-bottom: 0.5rem; }}
.message-content li {{ margin-bottom: 0.25rem; }}
.message-content a {{ color: var(--link); text-decoration: none; }}
.message-content a:hover {{ text-decoration: underline; }}
.message-content table {{
  border-collapse: collapse;
  width: 100%;
  margin: 0.75rem 0;
  font-size: 0.85rem;
}}
.message-content th, .message-content td {{
  border: 1px solid var(--border);
  padding: 0.4rem 0.75rem;
  text-align: left;
}}
.message-content th {{
  background: var(--table-header-bg);
  font-weight: 600;
}}
.message-content tr:nth-child(even) {{
  background: var(--table-stripe-bg);
}}
.code-block-wrap {{
  position: relative;
}}
.code-copy-btn {{
  position: absolute;
  top: 0.4rem;
  right: 0.4rem;
  z-index: 1;
}}
.code-block {{
  background: var(--code-bg);
  color: var(--code-fg);
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
  color: var(--fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}}
.inline-code {{
  background: var(--inline-code-bg);
  color: var(--inline-code-fg);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
  font-size: 0.85em;
}}
.diff-add {{ background: var(--diff-add-bg); color: var(--diff-add-fg); display: block; line-height: 1.4; }}
.diff-del {{ background: var(--diff-del-bg); color: var(--diff-del-fg); display: block; line-height: 1.4; }}
.diff-hunk {{ color: #cba6f7; display: block; }}
.tool-use {{
  border: 1px solid var(--border);
  border-radius: 6px;
  margin: 0.75rem 0;
  font-size: 0.85rem;
}}
.tool-use summary {{
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  color: var(--fg-muted);
  font-weight: 500;
  background: var(--card-bg);
  border-radius: 6px;
}}
.tool-use[open] summary {{ border-radius: 6px 6px 0 0; border-bottom: 1px solid var(--border); }}
.tool-input {{
  background: var(--code-bg);
  color: var(--code-fg);
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
  color: var(--fg-muted);
  font-weight: 500;
}}
.copy-btn {{
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--fg-muted);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}}
.copy-btn:hover {{ color: var(--copy-btn-hover); border-color: var(--fg-faint); }}
.copy-btn.copied {{
  color: var(--assistant-accent);
  border-color: var(--assistant-accent);
  animation: copy-flash 1.5s ease forwards;
}}
@keyframes copy-flash {{
  0% {{ color: var(--assistant-accent); border-color: var(--assistant-accent); }}
  70% {{ color: var(--assistant-accent); border-color: var(--assistant-accent); }}
  100% {{ color: var(--fg-muted); border-color: var(--border); }}
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
  background: var(--card-bg);
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
  color: var(--fg-faint);
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
  border-bottom: 1px solid var(--border);
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
  color: var(--link);
  word-break: break-all;
}}
.ask-question {{
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 0.75rem 0;
  overflow: hidden;
  background: var(--ask-bg);
}}
.ask-header {{
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--fg-muted);
  padding: 0.6rem 0.85rem 0;
}}
.ask-text {{
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--fg);
  padding: 0.25rem 0.85rem 0.5rem;
}}
.ask-options {{
  border-top: 1px solid var(--border-light);
}}
.ask-option {{
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.5rem 0.85rem;
  border-bottom: 1px solid var(--border-light);
  color: var(--fg-muted);
  font-size: 0.8rem;
}}
.ask-option:last-child {{ border-bottom: none; }}
.ask-option-selected {{
  background: var(--ask-selected-bg);
  color: var(--fg);
}}
.ask-radio {{
  font-size: 0.7rem;
  color: var(--border);
  flex-shrink: 0;
}}
.ask-radio-selected {{
  color: var(--user-accent);
}}
.ask-option-label {{
  font-weight: 600;
  white-space: nowrap;
}}
.ask-option-desc {{
  color: var(--fg-muted);
  font-size: 0.75rem;
}}
footer {{
  text-align: center;
  color: var(--fg-faint);
  font-size: 0.8rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}}
.minimap {{
  position: fixed;
  right: 0;
  top: 0;
  width: 180px;
  height: 100vh;
  background: var(--bg);
  border-left: 1px solid var(--border);
  overflow: hidden;
  cursor: pointer;
  z-index: 100;
  opacity: 0.7;
  transition: opacity 0.2s;
}}
.minimap:hover {{ opacity: 1; }}
.minimap-content {{
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: top left;
  pointer-events: none;
  width: var(--minimap-source-width, 1350px);
}}
.minimap-content .container {{
  max-width: none;
  padding: 0.5rem;
}}
.minimap-content .minimap,
.minimap-content .header-controls,
.minimap-content .copy-btn,
.minimap-content .code-copy-btn {{
  display: none !important;
}}
.minimap-jump {{
  position: absolute;
  left: 0;
  right: 0;
  height: 20px;
  background: var(--card-bg);
  border: none;
  color: var(--fg-faint);
  font-size: 0.5rem;
  cursor: pointer;
  z-index: 2;
  opacity: 0.6;
  transition: opacity 0.2s;
}}
.minimap-jump:hover {{ opacity: 1; color: var(--fg); }}
.minimap-jump-top {{ top: 0; border-bottom: 1px solid var(--border); }}
.minimap-jump-bottom {{ bottom: 0; border-top: 1px solid var(--border); }}
.minimap-viewport {{
  position: absolute;
  left: 0;
  right: 0;
  background: var(--user-accent);
  opacity: 0.1;
  border-top: 2px solid var(--user-accent);
  border-bottom: 2px solid var(--user-accent);
  pointer-events: none;
}}
</style>
</head>
<body class="dark">
<div class="accent-bar"></div>
<div class="container">
<header>
  <div>
    <h1>{html.escape(title)}</h1>
    <div class="subtitle">{today} &middot; {html.escape(project_dir)}</div>
  </div>
  <button class="settings-btn" onclick="document.getElementById('settingsModal').classList.add('open')" title="Settings">&#9881;&#65039;</button>
</header>
<div class="modal-overlay" id="settingsModal" onclick="if(event.target===this)this.classList.remove('open')">
  <div class="modal">
    <div class="modal-header">
      <h2>Settings</h2>
      <button class="modal-close" onclick="document.getElementById('settingsModal').classList.remove('open')">&times;</button>
    </div>
    <div class="modal-body">
      <div class="setting-row">
        <span class="setting-label">Layout</span>
        <div class="setting-control">
          <span>Linear</span>
          <div class="toggle-switch" id="viewToggle" onclick="toggleView()"></div>
          <span>Chat</span>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Theme</span>
        <div class="setting-control">
          <span>&#9728;&#65039;</span>
          <div class="toggle-switch" id="themeToggle" onclick="toggleTheme()"></div>
          <span>&#127769;</span>
        </div>
      </div>
      <div class="setting-row">
        <span class="setting-label">Minimap</span>
        <div class="setting-control">
          <span>Off</span>
          <div class="toggle-switch active" id="minimapToggle" onclick="toggleMinimap()"></div>
          <span>On</span>
        </div>
      </div>
      <div class="keybinds">
        <h3>Keyboard Shortcuts</h3>
        <div class="keybind"><kbd>j</kbd> Next message</div>
        <div class="keybind"><kbd>k</kbd> Previous message</div>
        <div class="keybind"><kbd>m</kbd> Toggle minimap</div>
        <div class="keybind"><kbd>Esc</kbd> Close settings</div>
      </div>
    </div>
  </div>
</div>
{body}
<footer>Exported &middot; {now}</footer>
</div>
<div class="minimap" id="minimap">
  <button class="minimap-jump minimap-jump-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="Scroll to top">&#9650;</button>
  <div class="minimap-content" id="minimapContent">
  </div>
  <div class="minimap-viewport" id="minimapViewport"></div>
  <button class="minimap-jump minimap-jump-bottom" onclick="window.scrollTo({{top:document.documentElement.scrollHeight,behavior:'smooth'}})" title="Scroll to bottom">&#9660;</button>
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
function toggleView() {{
  var toggle = document.getElementById('viewToggle');
  var isChat = document.body.classList.toggle('chat-mode');
  toggle.classList.toggle('active', isChat);
  localStorage.setItem('viewMode', isChat ? 'chat' : 'linear');
}}
function toggleMinimap() {{
  var toggle = document.getElementById('minimapToggle');
  var hidden = document.body.classList.toggle('no-minimap');
  toggle.classList.toggle('active', !hidden);
  localStorage.setItem('minimap', hidden ? 'off' : 'on');
  if (!hidden && window.minimapRelayout) setTimeout(window.minimapRelayout, 50);
}}
function toggleTheme() {{
  var toggle = document.getElementById('themeToggle');
  var isDark = document.body.classList.toggle('dark');
  toggle.classList.toggle('active', isDark);
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}}
(function() {{
  var savedTheme = localStorage.getItem('theme');
  var wantLight = savedTheme === 'light' || (!savedTheme && window.matchMedia('(prefers-color-scheme: light)').matches);
  if (wantLight) {{
    document.body.classList.remove('dark');
  }} else {{
    document.getElementById('themeToggle').classList.add('active');
  }}
  if (localStorage.getItem('viewMode') === 'chat') {{
    document.body.classList.add('chat-mode');
    document.getElementById('viewToggle').classList.add('active');
  }}
  if (localStorage.getItem('minimap') === 'off') {{
    document.body.classList.add('no-minimap');
    document.getElementById('minimapToggle').classList.remove('active');
  }}
}})();
document.querySelectorAll('details.tool-use').forEach(function(el) {{
  el.addEventListener('toggle', function() {{
    var open = el.open;
    document.querySelectorAll('details.tool-use').forEach(function(d) {{
      d.open = open;
    }});
  }});
}});
// Hash and navigation
function updateHash(el) {{
  history.replaceState(null, '', el.getAttribute('href'));
}}
var allMessages = document.querySelectorAll('.message');
var currentIdx = -1;
function navigateMsg(dir) {{
  var next = currentIdx + dir;
  if (next < 0) next = 0;
  if (next >= allMessages.length) next = allMessages.length - 1;
  currentIdx = next;
  var msg = allMessages[currentIdx];
  msg.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  history.replaceState(null, '', '#' + msg.id);
  allMessages.forEach(function(m) {{ m.classList.remove('active'); }});
  msg.classList.add('active');
}}
// Find current message based on scroll position
function findCurrentMsg() {{
  var scrollTop = window.scrollY + 100;
  for (var i = allMessages.length - 1; i >= 0; i--) {{
    if (allMessages[i].offsetTop <= scrollTop) {{
      currentIdx = i;
      return;
    }}
  }}
  currentIdx = 0;
}}
document.addEventListener('keydown', function(e) {{
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'Escape') {{ document.getElementById('settingsModal').classList.remove('open'); }}
  if (e.key === 'j') {{ if (currentIdx < 0) findCurrentMsg(); navigateMsg(1); e.preventDefault(); }}
  if (e.key === 'k') {{ if (currentIdx < 0) findCurrentMsg(); navigateMsg(-1); e.preventDefault(); }}
  if (e.key === 'm') {{ toggleMinimap(); }}
}});
// Load anchor on page load
(function() {{
  var hash = window.location.hash;
  if (hash) {{
    var el = document.querySelector(hash);
    if (el) {{
      el.scrollIntoView({{ block: 'start' }});
      el.classList.add('active');
      var m = hash.match(/msg-(\\d+)/);
      if (m) currentIdx = parseInt(m[1]);
    }}
  }}
}})();
// Minimap
(function() {{
  var minimap = document.getElementById('minimap');
  var content = document.getElementById('minimapContent');
  var viewport = document.getElementById('minimapViewport');
  var container = document.querySelector('.container');
  var mapW = 180;

  // Clone page content into minimap
  var clone = container.cloneNode(true);
  content.appendChild(clone);

  var sourceW, scale, cloneH, maxScroll;

  var sc, mapH, contentH, maxScroll, contentPan;

  function layout() {{
    mapH = minimap.clientHeight;
    sc = mapW / container.offsetWidth;
    content.style.width = container.offsetWidth + 'px';
    content.style.transform = 'scale(' + sc + ')';
    contentH = clone.offsetHeight * sc;
    maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    contentPan = 0;
  }}

  function frac() {{
    return maxScroll > 0 ? window.scrollY / maxScroll : 0;
  }}

  function update() {{
    maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    var f = frac();
    var vpH = (window.innerHeight / document.documentElement.scrollHeight) * contentH;
    var vpPos = f * (contentH - vpH); // position in content space

    // Pan content so viewport stays visible and centered when possible
    var idealPan = vpPos + vpH / 2 - mapH / 2;
    contentPan = Math.max(0, Math.min(contentH - mapH, idealPan));

    viewport.style.top = (vpPos - contentPan) + 'px';
    viewport.style.height = vpH + 'px';
    content.style.transform = 'scale(' + sc + ') translateY(' + (-contentPan / sc) + 'px)';
  }}

  function minimapYToFrac(y) {{
    // Convert minimap Y to document fraction
    var vpH = (window.innerHeight / document.documentElement.scrollHeight) * contentH;
    var contentY = y + contentPan; // position in content space
    var f = contentY / (contentH - vpH);
    return Math.max(0, Math.min(1, f));
  }}

  layout();
  update();
  window.addEventListener('scroll', update);
  window.addEventListener('resize', function() {{ layout(); update(); }});
  window.minimapRelayout = function() {{ layout(); update(); }};

  // Interaction
  var dragging = false;
  var didDrag = false;
  var dragStartY = 0;
  var dragStartFrac = 0;

  minimap.addEventListener('mousedown', function(e) {{
    dragging = true;
    didDrag = false;
    dragStartY = e.clientY;
    dragStartFrac = frac();
    e.preventDefault();
  }});
  window.addEventListener('mousemove', function(e) {{
    if (!dragging) return;
    if (Math.abs(e.clientY - dragStartY) > 3) didDrag = true;
    if (!didDrag) return;
    var dy = e.clientY - dragStartY;
    // Scale so available drag distance reaches full range
    // Dragging down: remaining frac = 1 - startFrac, available pixels = screenH - startY
    // Dragging up: remaining frac = startFrac, available pixels = startY
    var pixelsAvail, fracRange;
    if (dy > 0) {{
      pixelsAvail = window.innerHeight - dragStartY;
      fracRange = 1 - dragStartFrac;
    }} else {{
      pixelsAvail = dragStartY;
      fracRange = dragStartFrac;
    }}
    var scale = pixelsAvail > 0 ? fracRange / pixelsAvail : 0;
    var newFrac = dragStartFrac + dy * scale;
    newFrac = Math.max(0, Math.min(1, newFrac));
    window.scrollTo({{ top: newFrac * maxScroll }});
  }});
  window.addEventListener('mouseup', function(e) {{
    if (dragging && !didDrag) {{
      // Click: map minimap Y to document position
      var mapRect = minimap.getBoundingClientRect();
      var y = e.clientY - mapRect.top;
      var vpH = parseFloat(viewport.style.height) || 0;
      window.scrollTo({{ top: minimapYToFrac(y - vpH / 2) * maxScroll, behavior: 'smooth' }});
    }}
    dragging = false;
    didDrag = false;
  }});
}})();
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
