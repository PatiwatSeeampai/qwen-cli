# 🤖 Qwen Code CLI v2.0 — Claude Code Style

> Local AI Coding Agent running 100% locally on your machine with Rich UI and full features matching Claude Code.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Rich Terminal UI** | Beautiful Syntax highlighting, Panels, Trees, and Tables |
| **Smart Input** | Multi-session persistent command history + autocomplete powered by `prompt_toolkit` |
| **Patch Mode** | Surgical block editing (`patch_file`) instead of overwriting entire files |
| **Git Integration** | Comprehensive Git tools: status, diff, commit, push, pull |
| **Approval Gate** | Prompts for confirmation before executing dangerous commands (`rm`, `sudo`, `chmod`...) |
| **Session Save/Load** | Save and resume chat conversations across sessions |
| **Auto-save** | Automatically saves session states upon exiting the program |
| **Compact** | Summarizes and clears older history to optimize context window utilization |
| **Context Trimming** | Automatically trims history prefix to prevent context overflow |
| **File Tools** | Full set of file tools: list, search, delete, move/rename, read, write, and patch |
| **Slash Commands** | `/help /save /load /compact /clear /status /tree /cd /history` and more |

---

## 🚀 Installation & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Local LLM Server (llama.cpp or LM Studio)
```bash
# Example using llama-server
llama-server -m qwen2.5-7b-instruct-q4_k_m.gguf --port 8080
```

### 3. Run CLI
```bash
python qwen_cli.py
```

---

## 📖 Slash Commands

```
/help              Display all commands and help guide
/save [name]       Save current session state
/load <name>       Load a saved session
/sessions          List all saved sessions
/compact           Summarize and clean up conversation history (save context)
/clear             Clear all chat history and start fresh
/status            Display git status
/tree [path]       Display directory structure as a tree
/cd <path>         Change the current working directory
/pwd               Display the current working directory path
/history           Display full message history
/exit              Exit the application (auto-saves session)
```

---

## 🛠️ Agent Tools

| Tool | Purpose |
|---|---|
| `execute_bash_command` | Execute bash commands (includes confirmation gate for dangerous commands) |
| `view_and_read_file` | Read files with line-range selection and syntax highlighting |
| `write_or_edit_file` | Write or overwrite entire file content |
| `patch_file` | Edit specific parts of a file (surgical edit) |
| `list_directory` | Display folder structure in tree view |
| `search_in_files` | Search for regex/text patterns inside codebase |
| `delete_file` | Delete files/directories (requires confirmation) |
| `move_or_rename_file` | Move or rename files |
| `git_operations` | Perform Git operations (status, diff, log, commit, push, pull) |

---

## 🗂️ Created Directories & Files

```
~/.qwen_cli/
├── sessions/          ← Saved session files (.json)
└── input_history      ← prompt_toolkit command history
```

---

## 💡 Tips

- Use **`/compact`** when your session runs long and the Agent starts responding slowly or losing focus.
- Use **`patch_file`** instead of `write_or_edit_file` when editing specific segments of a file. It is much faster and safer.
- Press **↑/↓** arrows in the prompt to navigate your command history across sessions.
- **Auto-save** executes automatically whenever you exit with `/exit` or hit `Ctrl+C`.
