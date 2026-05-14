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
    messages = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = entry.get('type')
            if msg_type == 'user':
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
                        parts.append({
                            'type': 'tool_use',
                            'name': block.get('name', 'unknown'),
                            'input': block.get('input', {})
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
                elif part['type'] == 'tool_use':
                    tool_name = html.escape(part['name'])
                    tool_input = part['input']
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
.diff-add {{ background: rgba(166,227,161,0.2); color: #a6e3a1; display: block; }}
.diff-del {{ background: rgba(243,139,168,0.2); color: #f38ba8; display: block; }}
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
