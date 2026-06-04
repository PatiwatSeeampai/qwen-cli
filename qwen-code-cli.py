"""
╔══════════════════════════════════════════════════════════════╗
║          QWEN CODE CLI  —  v2.0  (All Features)             ║
║  Rich UI · Streaming · Diff · Git · Search · Safety Guard   ║
╚══════════════════════════════════════════════════════════════╝

ติดตั้ง dependencies:
    pip install langchain langchain-openai langgraph \
                rich gitpython prompt_toolkit
"""

import os, subprocess, json, re, ast, sys, difflib, time, select
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from pathlib import Path

# ── LangChain / LangGraph ───────────────────────────────────────────────────
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# ── Rich (Terminal UI) ──────────────────────────────────────────────────────
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich import box
from rich.theme import Theme
from rich.prompt import Confirm

# ── Prompt Toolkit (smart input) ────────────────────────────────────────────
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.completion import WordCompleter, PathCompleter, merge_completers

# ── Git ─────────────────────────────────────────────────────────────────────
try:
    import git as gitpython
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

# ════════════════════════════════════════════════════════════════════════════
# CONSOLE SETUP
# ════════════════════════════════════════════════════════════════════════════
custom_theme = Theme({
    "info"     : "bold cyan",
    "success"  : "bold green",
    "warning"  : "bold yellow",
    "danger"   : "bold red",
    "tool"     : "bold magenta",
    "ai"       : "bold bright_white",
    "dim_text" : "grey50",
    "file"     : "bold blue",
})
console = Console(theme=custom_theme, highlight=True)

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTS & CONFIG
# ════════════════════════════════════════════════════════════════════════════
MAX_ITERATIONS   = 20
HISTORY_FILE     = Path.home() / ".qwen_cli_history"
CONTEXT_FILE     = ".qwen-context.md"
MAX_HISTORY_MSGS = 40
SESSIONS_DIR     = Path.home() / ".qwen_cli" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# คำสั่งอันตรายที่ต้องขอ confirm ก่อนรัน
DANGEROUS_PATTERNS = [
    r"\brm\s+-rf?\b", r"\brmdir\b", r"\bdd\b", r"\bmkfs\b",
    r"\bchmod\s+777\b", r"\bsudo\b", r">\s*/dev/",
    r"\bformat\b", r"\bfdisk\b", r"--force",
    r"\btruncate\b", r"\bshred\b",
]

# ════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def is_dangerous_command(command: str) -> bool:
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False

def detect_language(file_path: str) -> str:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "jsx", ".tsx": "tsx", ".json": "json",
        ".sh": "bash", ".yml": "yaml", ".yaml": "yaml",
        ".md": "markdown", ".html": "html", ".css": "css",
        ".sql": "sql", ".go": "go", ".rs": "rust", ".java": "java",
    }
    return ext_map.get(Path(file_path).suffix.lower(), "text")

def show_diff(old_content: str, new_content: str, filename: str) -> None:
    """แสดง colorized diff ก่อนเขียนไฟล์"""
    diff = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm=""
    ))
    if not diff:
        console.print("[dim_text]  (ไม่มีการเปลี่ยนแปลง)[/dim_text]")
        return

    diff_text = Text()
    for line in diff[:80]:
        if line.startswith("+") and not line.startswith("+++"):
            diff_text.append(line + "\n", style="green")
        elif line.startswith("-") and not line.startswith("---"):
            diff_text.append(line + "\n", style="red")
        elif line.startswith("@@"):
            diff_text.append(line + "\n", style="cyan")
        else:
            diff_text.append(line + "\n", style="grey50")

    if len(diff) > 80:
        diff_text.append(f"\n... และอีก {len(diff)-80} บรรทัด\n", style="dim_text")

    console.print(Panel(diff_text, title="[bold]📝 Diff Preview[/bold]",
                        border_style="blue"))

def load_project_context() -> Optional[str]:
    ctx_path = Path(CONTEXT_FILE)
    if ctx_path.exists():
        return ctx_path.read_text(encoding="utf-8")
    return None

def get_test_command() -> Optional[str]:
    ctx = load_project_context()
    if ctx:
        for line in ctx.splitlines():
            if line.strip().startswith("test_command:"):
                return line.split("test_command:", 1)[1].strip()
    return None

def compress_history(history: list, system_msg: SystemMessage) -> list:
    """Intelligently summarize older history when it gets too long, keeping the system prompt and recent messages."""
    # Estimate total tokens by character count (approx. 1 token ~ 3-4 chars)
    # Trigger compression if history length is too long or total characters exceed 24,000 (~6,000-8,000 tokens)
    total_chars = sum(len(getattr(msg, "content", "")) for msg in history)
    
    if len(history) <= MAX_HISTORY_MSGS and total_chars < 24000:
        return history
        
    console.print("[warning]⚠ Context size or message history is too long — summarizing older messages...[/warning]")
    
    # Safely find a split index at a HumanMessage boundary to avoid splitting ToolMessage from AIMessage
    split_idx = len(history) - 8
    while split_idx > 1 and not isinstance(history[split_idx], HumanMessage):
        split_idx -= 1
    if split_idx <= 1:
        split_idx = max(1, len(history) - 8)
        
    to_summarize = history[1:split_idx]
    recent = history[split_idx:]

    formatted_chat = []
    for msg in to_summarize:
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = "Agent"
        elif isinstance(msg, ToolMessage):
            role = f"Tool ({msg.name})"
        else:
            role = "System"
        content = msg.content
        if len(content) > 300:
            content = content[:300] + "... [truncated]"
        formatted_chat.append(f"{role}: {content}")

    chat_text = "\n".join(formatted_chat)
    summary_prompt = (
        "You are an assistant summarizing a coding chat history.\n"
        "Briefly summarize what tasks have been completed, what files were viewed, written, or edited, "
        "and any critical context or decisions made. Keep the summary concise and under 150 words.\n\n"
        f"--- CHAT TO SUMMARIZE ---\n{chat_text}"
    )

    try:
        unbound_llm = llm.bound if hasattr(llm, "bound") else llm
        summary_response = unbound_llm.invoke([
            SystemMessage(content="You are a helpful assistant that summarizes technical conversations in English."),
            HumanMessage(content=summary_prompt)
        ])
        summary_text = summary_response.content.strip()
        console.print(f"[success]✅ History summarized: {summary_text[:100]}...[/success]")
    except Exception as e:
        console.print(f"[warning]⚠ Failed to generate summary: {e}. Falling back to default message.[/warning]")
        summary_text = "The previous conversation history was truncated to save memory."

    compressed = [
        system_msg,
        SystemMessage(content=f"### Summary of previous actions:\n{summary_text}")
    ]
    compressed.extend(recent)
    return compressed

# ════════════════════════════════════════════════════════════════════════════
# TOOLS
# ════════════════════════════════════════════════════════════════════════════

@tool
def execute_bash_command(command: str) -> str:
    """Run Linux/Bash command in Terminal such as ls, pwd, mkdir, pytest, pip install"""
    console.print(Panel(
        f"[bold yellow]{command}[/bold yellow]",
        title="[tool]🖥  Terminal[/tool]", border_style="yellow", expand=False
    ))

    if is_dangerous_command(command):
        console.print("[danger]⚠ This command is identified as potentially dangerous[/danger]")
        confirmed = Confirm.ask(f"[warning]Confirm execution of: [bold]{command}[/bold] ?[/warning]")
        if not confirmed:
            return "❌ User cancelled command execution"

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            universal_newlines=True
        )
        
        output_chunks = []
        start_time = time.time()
        timeout = 60.0
        timed_out = False
        
        while True:
            if time.time() - start_time > timeout:
                timed_out = True
                process.terminate()
                break
            
            # Use select to wait for data on stdout without modifying the blocking flag of the file descriptor
            r, _, _ = select.select([process.stdout], [], [], 0.02)
            if r:
                line = process.stdout.readline()
                if line == '':
                    if process.poll() is not None:
                        break
                else:
                    output_chunks.append(line)
                    console.print(line, end="")
            else:
                if process.poll() is not None:
                    # Capture any remaining text
                    for remaining_line in process.stdout:
                        output_chunks.append(remaining_line)
                        console.print(remaining_line, end="")
                    break
                
        returncode = process.returncode
        if timed_out:
            returncode = -9
            output = "⏱ Timeout: Exceeded 60 seconds"
            style = "red"
            icon = "❌"
        else:
            output = "".join(output_chunks)
            output = output.strip() if output.strip() else "✅ Command completed successfully (no output)"
            style = "green" if returncode == 0 else "red"
            icon = "✅" if returncode == 0 else "❌"
            
        console.print(Panel(
            Text(output[:2000], style=style),
            title=f"[{style}]{icon} Output (exit={returncode})[/{style}]",
            border_style=style, expand=False
        ))
        return output[:3000]
    except KeyboardInterrupt:
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
        console.print("\n[warning]⚠ Command execution interrupted by user (Ctrl+C)[/warning]")
        raise
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def view_and_read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Read file contents with syntax highlighting preview.
    Optionally provide start_line and end_line (1-indexed, inclusive) to read specific parts of large files to save context window tokens."""
    console.print(f"[file]📄 Reading file: {file_path}[/file]")
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        lang    = detect_language(file_path)
        lines   = content.splitlines()
        
        # Determine ranges
        total_lines = len(lines)
        s = start_line if start_line is not None else 1
        e = end_line if end_line is not None else total_lines
        
        # Clamp and validate ranges
        s = max(1, min(s, total_lines))
        e = max(s, min(e, total_lines))
        
        selected_lines = lines[s-1:e]
        selected_content = "\n".join(selected_lines)
        
        # For terminal preview, show at most 50 lines of the selected content
        preview_lines = selected_lines[:50]
        preview = "\n".join(preview_lines)
        if len(selected_lines) > 50:
            preview += f"\n... (and {len(selected_lines)-50} more lines displayed in terminal)"
            
        panel_title = f"[file]📄 {file_path}[/file]"
        if start_line is not None or end_line is not None:
            panel_title += f" [dim_text](Lines {s}-{e} of {total_lines})[/dim_text]"
        else:
            panel_title += f" [dim_text]({total_lines} lines)[/dim_text]"
            
        console.print(Panel(
            Syntax(preview, lang, theme="monokai", line_numbers=True, start_line=s),
            title=panel_title,
            border_style="blue", expand=False
        ))
        return selected_content
    except Exception as e:
        return f"❌ Unable to read file: {str(e)}"


@tool
def write_or_edit_file(file_path: str, content: str) -> str:
    """Create or overwrite files entirely (diff preview shown before writing)"""
    console.print(f"[file]💾 Writing file: {file_path}[/file]")
    p = Path(file_path)
    old_content = ""
    if p.exists():
        try:
            old_content = p.read_text(encoding="utf-8")
            show_diff(old_content, content, file_path)
        except Exception:
            pass
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(content, encoding="utf-8")
        action = "Updated" if old_content else "Created"
        console.print(f"[success]✅ {action} file {file_path} ({len(content.splitlines())} lines)[/success]")
        
        test_cmd = get_test_command()
        if test_cmd:
            console.print(f"[info]⚡ Running linter/test check: {test_cmd}...[/info]")
            try:
                res = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=30)
                if res.returncode == 0:
                    console.print("[success]✅ Test check passed![/success]")
                    return f"✅ {action} file {file_path} successfully. Test verification passed:\n{res.stdout.strip() or 'OK'}"
                else:
                    console.print("[danger]❌ Test check failed![/danger]")
                    return f"❌ {action} file {file_path} successfully, but Test FAILED!\nError Output:\n{res.stderr.strip() or res.stdout.strip()}"
            except Exception as e:
                return f"✅ {action} file {file_path} successfully, but encountered error running Test: {str(e)}"
                
        return f"✅ {action} file {file_path} successfully"
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def patch_file(file_path: str, old_snippet: str, new_snippet: str) -> str:
    """Surgically edit file — find old_snippet and replace with new_snippet. Use instead of write_or_edit_file when editing parts of files."""
    console.print(f"[file]🔧 Patch: {file_path}[/file]")
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        if old_snippet not in content:
            return "❌ Target snippet not found. Please verify old_snippet."
        count = content.count(old_snippet)
        if count > 1:
            return f"⚠ Target snippet found {count} times. Please make old_snippet more unique."
        new_content = content.replace(old_snippet, new_snippet, 1)
        show_diff(content, new_content, file_path)
        Path(file_path).write_text(new_content, encoding="utf-8")
        console.print(f"[success]✅ Patched {file_path} successfully[/success]")
        
        test_cmd = get_test_command()
        if test_cmd:
            console.print(f"[info]⚡ Running linter/test check: {test_cmd}...[/info]")
            try:
                res = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=30)
                if res.returncode == 0:
                    console.print("[success]✅ Test check passed![/success]")
                    return f"✅ Patch successful. Test verification passed:\n{res.stdout.strip() or 'OK'}"
                else:
                    console.print("[danger]❌ Test check failed![/danger]")
                    return f"❌ Patch successful, but Test FAILED!\nError Output:\n{res.stderr.strip() or res.stdout.strip()}"
            except Exception as e:
                return f"✅ Patch successful, but encountered error running Test: {str(e)}"
                
        return "✅ Patch successful"
    except Exception as e:
        return f"❌ Patch failed: {str(e)}"


@tool
def search_in_files(pattern: str, directory: str = ".", file_glob: str = "*.py") -> str:
    """Search text/regex across multiple files (grep-style)
    pattern: Text or regex | directory: Folder to search | file_glob: Glob pattern like *.py, *.js, *.*"""
    console.print(f"[tool]🔍 Searching for '[bold]{pattern}[/bold]' in {directory}/**/{file_glob}[/tool]")
    skip_dirs = {'.git','__pycache__','node_modules','.venv','venv','dist','build'}
    results = []
    try:
        for fp in Path(directory).rglob(file_glob):
            if any(p in skip_dirs for p in fp.parts):
                continue
            try:
                for i, line in enumerate(fp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        results.append((str(fp), i, line.strip()))
            except Exception:
                pass

        if not results:
            return f"Pattern '{pattern}' not found"

        table = Table(title=f"🔍 '{pattern}' — {len(results)} results", box=box.SIMPLE)
        table.add_column("File:Line", style="cyan", no_wrap=True)
        table.add_column("Content", style="white")
        for fp, ln, line in results[:30]:
            table.add_row(f"{fp}:{ln}", line)
        console.print(table)
        if len(results) > 30:
            console.print(f"[dim_text]... and {len(results)-30} more items[/dim_text]")

        return "\n".join([f"{f}:{l}: {c}" for f,l,c in results[:100]])
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def list_directory_tree(directory: str = ".", max_depth: int = 3) -> str:
    """Show directory tree of the project to understand the structure"""
    skip = {'.git','__pycache__','node_modules','.venv','venv','dist','build','.pytest_cache'}
    lines = []

    def _tree(path: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return
        for i, item in enumerate(items):
            if item.name in skip or item.name.startswith('.'):
                continue
            conn = "└── " if i == len(items)-1 else "├── "
            lines.append(f"{prefix}{conn}{item.name}")
            if item.is_dir():
                ext = "    " if i == len(items)-1 else "│   "
                _tree(item, prefix + ext, depth + 1)

    root = Path(directory)
    lines.append(f"📁 {root.resolve().name}/")
    _tree(root)
    tree_str = "\n".join(lines)
    console.print(Panel(tree_str, title=f"[file]🌳 {directory}[/file]",
                        border_style="blue", expand=False))
    return tree_str


@tool
def get_file_outline(file_path: str) -> str:
    """View Python file outline (classes, functions, imports) without reading the entire file.
    Saves context window when only an overview is needed."""
    console.print(f"[file]🗂 Outline: {file_path}[/file]")
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        tree    = ast.parse(content)
        outline = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    outline.append((node.lineno, "import", a.name))
            elif isinstance(node, ast.ImportFrom):
                outline.append((node.lineno, "from", f"{node.module or ''} import ..."))
            elif isinstance(node, ast.ClassDef):
                outline.append((node.lineno, "class", node.name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                outline.append((node.lineno, kind, node.name))
        outline.sort(key=lambda x: x[0])

        table = Table(title=f"🗂 {file_path}", box=box.SIMPLE)
        table.add_column("Line", style="dim_text", width=6)
        table.add_column("Type", style="cyan", width=12)
        table.add_column("Name", style="bold white")
        style_map = {"class": "bold yellow", "def": "green", "async def": "bright_green"}
        for ln, kind, name in outline:
            table.add_row(str(ln), kind, Text(name, style=style_map.get(kind, "white")))
        console.print(table)
        return "\n".join([f"L{l}: {k} {n}" for l,k,n in outline])
    except SyntaxError as e:
        return f"⚠ Syntax error: {e}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def get_git_info(repo_path: str = ".") -> str:
    """View current git branch, status, diff stat, and last 10 commits"""
    if not GIT_AVAILABLE:
        return "⚠ gitpython is not installed: pip install gitpython"
    console.print(f"[tool]🔀 Git Info: {repo_path}[/tool]")
    try:
        repo   = gitpython.Repo(repo_path, search_parent_directories=True)
        branch = repo.active_branch.name
        status = repo.git.status('--short')
        log    = repo.git.log('--oneline', '-10')
        diff   = repo.git.diff('HEAD', '--stat')
        info   = f"Branch: {branch}\n\nStatus:\n{status or '(clean)'}\n\nRecent commits:\n{log}\n\nDiff stat:\n{diff or '(no changes)'}"
        console.print(Panel(Syntax(info, "text", theme="monokai"),
                            title="[tool]🔀 Git[/tool]", border_style="magenta", expand=False))
        return info
    except gitpython.InvalidGitRepositoryError:
        return "⚠ Not a git repository"
    except Exception as e:
        return f"❌ git error: {str(e)}"


@tool
def create_project_context(content: str) -> str:
    """Create or update .qwen-context.md to save project info for future sessions
    Include: stack, test command, conventions, things the agent should always know"""
    try:
        Path(CONTEXT_FILE).write_text(content, encoding="utf-8")
        console.print(f"[success]✅ Project context saved to {CONTEXT_FILE}[/success]")
        return "✅ Project context saved successfully"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# รวม tools
tools = [
    execute_bash_command, view_and_read_file, write_or_edit_file,
    patch_file, search_in_files, list_directory_tree,
    get_file_outline, get_git_info, create_project_context,
]
tools_by_name = {t.name: t for t in tools}

# ════════════════════════════════════════════════════════════════════════════
# LLM
# ════════════════════════════════════════════════════════════════════════════
api_base = os.environ.get("QWEN_API_BASE", "http://127.0.0.1:8080/v1")
model_name = os.environ.get("QWEN_MODEL", "qwen2.5-7b-instruct-q4_k_m")

llm = ChatOpenAI(
    base_url=api_base,
    api_key="not-needed",
    model=model_name,
    temperature=0,
    max_tokens=2048,
).bind_tools(tools)

# ════════════════════════════════════════════════════════════════════════════
# LANGGRAPH
# ════════════════════════════════════════════════════════════════════════════
class State(TypedDict):
    messages:        Annotated[list, add_messages]
    iteration_count: int

def llm_node(state: State):
    count = state.get("iteration_count", 0)
    if count >= MAX_ITERATIONS:
        console.print(f"[danger]⚠ ถึง MAX_ITERATIONS ({MAX_ITERATIONS})[/danger]")
        return {"messages": [AIMessage(content=f"⚠ หยุดทำงาน ครบ {MAX_ITERATIONS} รอบ")],
                "iteration_count": count}

    # ── เริ่มระบบ Token Streaming ร่วมกับ Rich Live ──
    from rich.live import Live
    
    response = None
    is_tool_call = False
    live = None

    for chunk in llm.stream(state["messages"]):
        if response is None:
            response = chunk
        else:
            response += chunk

        # เช็กว่าโมเดลเริ่มสั่งรัน Tool หรือยัง (ถ้าเป็น Tool จะไม่แสดงบนหน้าจอแชทปกติ)
        if chunk.tool_call_chunks:
            is_tool_call = True

        if not is_tool_call:
            # เช็ก fallback กรณีเป็น XML tool call
            content_so_far = response.content
            if content_so_far.startswith("<tool_call") or content_so_far.strip().startswith("<tool_call"):
                is_tool_call = True
            else:
                # ถ้าเป็นข้อความธรรมดา ให้เริ่มรันกล่องแสดงผลสด (Live Preview)
                if live is None:
                    from rich.markdown import Markdown
                    panel = Panel(Markdown(""), title="[ai]🤖 Qwen[/ai]", border_style="bright_white", expand=False)
                    live = Live(panel, console=console, refresh_per_second=12)
                    live.start()
                
                # อัปเดตข้อความในกล่อง Markdown แบบเรียลไทม์
                live.update(Panel(Markdown(content_so_far), title="[ai]🤖 Qwen[/ai]", border_style="bright_white", expand=False))

    if live:
        live.stop()
    # ── จบระบบ Token Streaming ──

    # Fallback XML parser
    if not response.tool_calls and "<tool_call>" in response.content:
        try:
            match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", response.content, re.DOTALL)
            if match:
                raw = match.group(1).strip()
                if raw.startswith("{{"):
                    raw = raw[1:-1]
                if raw.count('{') > raw.count('}'):
                    if not raw.endswith('"'):
                        raw += '"'
                    raw += "}" * (raw.count('{') - raw.count('}'))
                try:
                    td = ast.literal_eval(raw)
                except Exception:
                    td = json.loads(raw, strict=False)
                response.tool_calls = [{
                    "name": td["name"], "args": td["arguments"],
                    "id": f"call_{count}_{int(time.time())}", "type": "tool_call"
                }]
        except Exception as e:
            console.print(f"[warning]⚠ XML parser error: {e}[/warning]")

    return {"messages": [response], "iteration_count": count + 1}


def tool_node(state: State):
    outputs = []
    for tc in state["messages"][-1].tool_calls:
        fn = tools_by_name.get(tc["name"])
        if not fn:
            result = f"❌ ไม่พบ tool: {tc['name']}"
        else:
            try:
                result = fn.invoke(tc["args"])
            except Exception as e:
                result = f"❌ Tool error: {str(e)}"
        outputs.append(ToolMessage(
            content=json.dumps(result, ensure_ascii=False),
            name=tc["name"], tool_call_id=tc["id"]
        ))
    return {"messages": outputs}


def should_continue(state: State) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "__end__"
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"


builder = StateGraph(State)
builder.add_node("llm", llm_node)
builder.add_node("tools", tool_node)
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", should_continue)
builder.add_edge("tools", "llm")
code_agent_app = builder.compile()

# ════════════════════════════════════════════════════════════════════════════
# BANNER & SPECIAL COMMANDS
# ════════════════════════════════════════════════════════════════════════════
def get_active_model_name() -> str:
    import urllib.request
    try:
        api_base = os.environ.get("QWEN_API_BASE", "http://127.0.0.1:8080/v1")
        req = urllib.request.Request(f"{api_base.rstrip('/')}/models")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            data = json.loads(response.read().decode())
            if "data" in data and len(data["data"]) > 0:
                model_path = data["data"][0]["id"]
                # Extract the basename of the model file
                name = os.path.basename(model_path)
                if len(name) > 30:
                    return name[:27] + "..."
                return name
    except Exception:
        pass
    return os.environ.get("QWEN_MODEL", "qwen2.5-coder")

def print_banner():
    print('New Banner Text')
    console.print(Panel(
        "[bold cyan]QWEN CODE CLI  v2.0[/bold cyan]\n"
        "[dim_text]Rich UI · Diff · Git · Search · Safety Guard · Memory[/dim_text]",
        border_style="cyan", expand=False
    ))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    table.add_column("", style="dim_text", width=3)
    table.add_column("", style="white")
    for icon, desc in [
        ("🖥", "execute_bash_command — Run terminal commands (safety confirm included)"),
        ("📄", "view_and_read_file — Read file contents with syntax highlighting"),
        ("💾", "write_or_edit_file — Create or rewrite file contents with diff preview"),
        ("🔧", "patch_file — Make surgical edits on specific code blocks"),
        ("🔍", "search_in_files — Search text patterns across files (grep-style)"),
        ("🌳", "list_directory_tree — Display project directory structure"),
        ("🗂", "get_file_outline — Overview classes, methods, and imports"),
        ("🔀", "get_git_info — Show branch, diff, and recent commits"),
        ("📋", "create_project_context — Create or update .qwen-context.md"),
    ]:
        table.add_row(icon, desc)
    console.print(Panel(table, title="[bold]🛠  Tools[/bold]", border_style="cyan", expand=False))

    active_model = get_active_model_name()
    info = Columns([
        Panel(f"[cyan]Model[/cyan]\n{active_model}", expand=True),
        Panel(f"[cyan]Max Loop[/cyan]\n{MAX_ITERATIONS}", expand=True),
        Panel(f"[cyan]Context[/cyan]\n{'✅' if load_project_context() else '❌'}", expand=True),
        Panel(f"[cyan]Git[/cyan]\n{'✅' if GIT_AVAILABLE else '❌ pip install gitpython'}", expand=True),
    ])
    console.print(info)
    console.print("[dim_text]Commands: /commit (auto commit msg), /diff (colored diff), /git, /tree, /help | 'exit' to quit[/dim_text]\n")


def auto_save_session(history: list) -> None:
    """Automatically save current session to last_session.json"""
    try:
        serializable_history = []
        for msg in history:
            if isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, HumanMessage):
                role = "human"
            elif isinstance(msg, AIMessage):
                role = "ai"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            else:
                role = "unknown"
                
            msg_dict = {
                "role": role,
                "content": msg.content
            }
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if hasattr(msg, "name") and msg.name:
                msg_dict["name"] = msg.name
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            serializable_history.append(msg_dict)
            
        file_path = SESSIONS_DIR / "last_session.json"
        file_path.write_text(json.dumps(serializable_history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def handle_special_command(cmd: str, history: list, system_msg: SystemMessage) -> tuple[bool, list]:
    """Returns (handled, updated_history)"""
    parts = cmd.strip().split(maxsplit=1)
    if not parts:
        return False, history

    cmd_name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd_name in ("help", "/help"):
        table = Table(title="📖 Special Commands", box=box.SIMPLE)
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        for cm, desc in [
            ("/help", "Show all special commands"),
            ("/clear", "Clear screen"),
            ("/reset", "Reset session chat history"),
            ("/tools", "List all available tools"),
            ("/context", "View .qwen-context.md"),
            ("/tree", "Display directory tree"),
            ("/git", "View git status and info"),
            ("/diff", "Show git diff of pending changes"),
            ("/commit", "Generate commit message and commit staged changes"),
            ("/save <name>", "Save current session history"),
            ("/load <name>", "Load saved session history"),
            ("/sessions", "List all saved sessions"),
            ("exit / quit", "Exit the program (auto-saves session)"),
        ]:
            table.add_row(cm, desc)
        console.print(table)
        return True, history

    if cmd_name in ("/clear", "clear"):
        console.clear(); print_banner()
        return True, history

    if cmd_name == "/reset":
        history = [system_msg]
        console.print("[success]✅ Chat history reset successfully[/success]")
        return True, history

    if cmd_name == "/tools":
        for t in tools:
            console.print(f"[cyan]{t.name}[/cyan]: [dim_text]{t.description[:80]}[/dim_text]")
        return True, history

    if cmd_name == "/tree":
        list_directory_tree.invoke({"directory": ".", "max_depth": 3})
        return True, history

    if cmd_name == "/git":
        get_git_info.invoke({"repo_path": "."})
        return True, history

    if cmd_name == "/diff":
        if not GIT_AVAILABLE:
            console.print("[danger]⚠ gitpython is not installed[/danger]")
            return True, history
        try:
            repo = gitpython.Repo(".", search_parent_directories=True)
            diff = repo.git.diff()
            if not diff.strip():
                console.print("[dim_text]No pending changes (git is clean)[/dim_text]")
            else:
                console.print(Panel(
                    Syntax(diff, "diff", theme="monokai", line_numbers=False),
                    title="[tool]🔀 Git Diff[/tool]", border_style="magenta", expand=False
                ))
        except Exception as e:
            console.print(f"[danger]❌ Git diff error: {str(e)}[/danger]")
        return True, history

    if cmd_name == "/commit":
        if not GIT_AVAILABLE:
            console.print("[danger]⚠ gitpython is not installed[/danger]")
            return True, history
        try:
            repo = gitpython.Repo(".", search_parent_directories=True)
            if not repo.is_dirty(untracked_files=True):
                console.print("[dim_text]Nothing to commit, working tree clean.[/dim_text]")
                return True, history
                
            staged_diff = repo.git.diff("--cached")
            if not staged_diff.strip():
                console.print("[warning]⚠ No changes staged for commit.[/warning]")
                confirm_stage = Confirm.ask("Do you want to stage all changes (git add -A)?")
                if confirm_stage:
                    repo.git.add(A=True)
                    console.print("[success]Staged all changes.[/success]")
                    staged_diff = repo.git.diff("--cached")
                else:
                    console.print("[dim_text]Commit aborted.[/dim_text]")
                    return True, history
            
            if not staged_diff.strip():
                console.print("[dim_text]No changes staged. Commit aborted.[/dim_text]")
                return True, history
                
            console.print("[info]⚡ Generating commit message using LLM...[/info]")
            commit_prompt = (
                "You are an expert software developer. Generate a concise and meaningful git commit message "
                "based on the following diff. Follow conventional commits format (e.g., feat: ..., fix: ..., chore: ...). "
                "Keep the first line under 72 characters. Do not output anything else except the commit message itself.\n\n"
                f"--- GIT DIFF ---\n{staged_diff}"
            )
            
            unbound_llm = llm.bound if hasattr(llm, "bound") else llm
            response = unbound_llm.invoke([
                SystemMessage(content="You are a helper that generates git commit messages. Respond only with the message itself."),
                HumanMessage(content=commit_prompt)
            ])
            commit_msg = response.content.strip()
            
            if commit_msg.startswith("`") and commit_msg.endswith("`"):
                commit_msg = commit_msg.strip("`").strip()
            if commit_msg.startswith('"') and commit_msg.endswith('"'):
                commit_msg = commit_msg.strip('"').strip()
                
            console.print(Panel(
                Text(commit_msg, style="bold green"),
                title="[success]📝 Generated Commit Message[/success]",
                border_style="green", expand=False
            ))
            
            confirm_commit = Confirm.ask("Do you want to execute this commit?")
            if confirm_commit:
                repo.git.commit(m=commit_msg)
                console.print("[success]✅ Commit successful![/success]")
            else:
                console.print("[dim_text]Commit cancelled by user.[/dim_text]")
        except Exception as e:
            console.print(f"[danger]❌ Git commit error: {str(e)}[/danger]")
        return True, history

    if cmd_name == "/context":
        ctx = load_project_context()
        if ctx:
            console.print(Panel(Markdown(ctx), title=f"[file]{CONTEXT_FILE}[/file]", border_style="blue"))
        else:
            console.print(f"[warning]{CONTEXT_FILE} not found[/warning]")
        return True, history

    if cmd_name == "/sessions":
        if not SESSIONS_DIR.exists():
            console.print("[dim_text]No saved sessions found.[/dim_text]")
            return True, history
        files = sorted(SESSIONS_DIR.glob("*.json"))
        if not files:
            console.print("[dim_text]No saved sessions found.[/dim_text]")
            return True, history
        table = Table(title="🗄 Saved Sessions", box=box.SIMPLE)
        table.add_column("Session Name", style="cyan")
        table.add_column("Saved Date/Time", style="white")
        table.add_column("Messages Count", style="dim_text")
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                m_count = len(data)
            except Exception:
                m_count = "?"
            mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f.stat().st_mtime))
            table.add_row(f.stem, mtime, str(m_count))
        console.print(table)
        return True, history

    if cmd_name == "/save":
        if not arg:
            console.print("[danger]Usage: /save <session_name>[/danger]")
            return True, history
        if not re.match(r"^[a-zA-Z0-9_\-]+$", arg):
            console.print("[danger]Error: Session name must be alphanumeric, containing only letters, numbers, underscores, or dashes.[/danger]")
            return True, history
        
        serializable_history = []
        for msg in history:
            if isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, HumanMessage):
                role = "human"
            elif isinstance(msg, AIMessage):
                role = "ai"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            else:
                role = "unknown"
                
            msg_dict = {
                "role": role,
                "content": msg.content
            }
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if hasattr(msg, "name") and msg.name:
                msg_dict["name"] = msg.name
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            serializable_history.append(msg_dict)
            
        try:
            file_path = SESSIONS_DIR / f"{arg}.json"
            file_path.write_text(json.dumps(serializable_history, ensure_ascii=False, indent=2), encoding="utf-8")
            console.print(f"[success]✅ Session saved to {file_path}[/success]")
        except Exception as e:
            console.print(f"[danger]❌ Failed to save session: {e}[/danger]")
        return True, history

    if cmd_name == "/load":
        if not arg:
            console.print("[danger]Usage: /load <session_name>[/danger]")
            return True, history
        if not re.match(r"^[a-zA-Z0-9_\-]+$", arg):
            console.print("[danger]Error: Invalid session name.[/danger]")
            return True, history
            
        file_path = SESSIONS_DIR / f"{arg}.json"
        if not file_path.exists():
            console.print(f"[danger]❌ Session '{arg}' not found.[/danger]")
            return True, history
            
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            new_history = []
            for msg_dict in data:
                role = msg_dict.get("role")
                content = msg_dict.get("content", "")
                if role == "system":
                    new_history.append(SystemMessage(content=content))
                elif role == "human":
                    new_history.append(HumanMessage(content=content))
                elif role == "ai":
                    ai_msg = AIMessage(content=content)
                    if "tool_calls" in msg_dict:
                        ai_msg.tool_calls = msg_dict["tool_calls"]
                    new_history.append(ai_msg)
                elif role == "tool":
                    new_history.append(ToolMessage(
                        content=content,
                        name=msg_dict.get("name", ""),
                        tool_call_id=msg_dict.get("tool_call_id", "")
                    ))
            history = new_history
            console.print(f"[success]✅ Session '{arg}' loaded successfully ({len(history)} messages).[/success]")
        except Exception as e:
            console.print(f"[danger]❌ Failed to load session: {e}[/danger]")
        return True, history

    return False, history


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print_banner()

    ctx = load_project_context()
    ctx_section = f"\n\n## Project Context\n{ctx}" if ctx else ""

    system_prompt = (
        "You are Qwen Code CLI, a senior software engineer AI agent.\n\n"
        "## Core Rules:\n"
        "1. Never ask the user to do the work themselves — handle everything using your available tools.\n"
        "2. Always read the file before editing it. Use `view_and_read_file` with specific `start_line` and `end_line` ranges when reading large files to save context window tokens. Use the `patch_file` tool to make localized changes instead of rewriting the entire file.\n"
        "3. Before writing new code, use `list_directory_tree` to understand the project structure.\n"
        "4. Use `get_file_outline` before reading large files to save context window.\n"
        "5. Respond and summarize entirely in English.\n"
        "6. If you are unsure about dependencies, verify them before installing.\n\n"
        "## Tool Calling fallback structure:\n"
        "You can call tools using standard tool calling. If native tool calling fails, format your response to contain an XML-style block:\n"
        "<tool_call>\n"
        "{\"name\": \"tool_name\", \"arguments\": {\"arg1\": \"value1\"}}\n"
        "</tool_call>"
        f"{ctx_section}"
    )

    system_msg = SystemMessage(content=system_prompt)
    history    = [system_msg]

    # Autocomplete lists
    commands_completer = WordCompleter([
        "/help", "/clear", "/reset", "/tools", "/context", "/tree", "/git", "/diff", "/commit", "/save", "/load", "/sessions", "/exit", "exit", "quit"
    ], ignore_case=True)
    path_completer = PathCompleter(expanduser=True)
    cli_completer = merge_completers([commands_completer, path_completer])

    session = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=cli_completer,
        style=PTStyle.from_dict({"prompt": "bold ansicyan", "": "ansiwhite"}),
    )

    console.print("[dim_text]Ready to accept commands...[/dim_text]\n")

    while True:
        try:
            user_input = session.prompt("\n👤 admin@qwen-cli ❯ ")
        except KeyboardInterrupt:
            console.print("\n[warning]Ctrl+C — Type 'exit' to quit[/warning]")
            continue
        except EOFError:
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "/exit"):
            console.print(Panel("[bold cyan]👋 Closing Qwen CLI — Goodbye![/bold cyan]",
                                border_style="cyan", expand=False))
            break

        handled, history = handle_special_command(user_input, history, system_msg)
        if handled:
            continue

        history = compress_history(history, system_msg)
        history.append(HumanMessage(content=user_input))
        console.print(f"\n[dim_text]{'─'*60}[/dim_text]")

        try:
            for event in code_agent_app.stream(
                {"messages": history, "iteration_count": 0},
                stream_mode="values"
            ):
                if "messages" not in event:
                    continue
                last = event["messages"][-1]

                if isinstance(last, AIMessage) and not last.tool_calls:
                    if last not in history:
                        history.append(last)

                elif isinstance(last, ToolMessage):
                    if last not in history:
                        history.append(last)

        except KeyboardInterrupt:
            console.print("\n[warning]⚠ Execution halted[/warning]")
        except Exception as e:
            console.print(f"[danger]❌ Error: {str(e)}[/danger]")

        console.print(f"[dim_text]{'─'*60}[/dim_text]")
