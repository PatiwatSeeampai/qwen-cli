---
name: qwen-code-cli
description: Local AI Coding Agent with Rich UI, streaming, surgical patching, and git automation.
---

# 🤖 Qwen Code CLI — Agent Capabilities & Skills Documentation

This document summarizes the core capabilities, slash commands, and tool bindings of the Qwen Code CLI system to provide a clean overview of the Agent's architecture and operation guidelines.

---

## 🛠️ 1. Agent Bindings & Tools

The LLM Agent in this system can invoke 9 primary tools through function calling:

| Tool Name | Description | Key Parameters |
|---|---|---|
| `execute_bash_command` | Executes terminal commands as an asynchronous output stream | `command` (str) |
| `view_and_read_file` | Reads file content with precise line-range selection | `file_path`, `start_line`, `end_line` |
| `write_or_edit_file` | Writes a new file or overwrites an existing one (includes diff review) | `file_path`, `content` |
| `patch_file` | Edits specific code sections safely (Surgical Edit) | `file_path`, `old_snippet`, `new_snippet` |
| `search_in_files` | Searches for text/regex patterns in the workspace (grep-like) | `pattern`, `directory`, `file_glob` |
| `list_directory_tree` | Generates a structural directory tree of the workspace | `directory`, `max_depth` |
| `get_file_outline` | Displays the structural outline (classes, methods, functions) of a file | `file_path` |
| `get_git_info` | Retrieves git repository status, branch info, and commit logs | `repo_path` |
| `create_project_context`| Creates or updates the project context profile | `content` |

---

## 📖 2. Slash Commands

Client-side commands processed locally inside the terminal without calling the LLM (saving tokens and latency):

*   `/help` : Displays the guide for all available slash commands
*   `/clear` : Clears the terminal screen layout
*   `/reset` : Resets chat history and context (crucial when chat history grows long and LLM becomes slower)
*   `/tools` : Shows names and descriptions of all tools the agent can use
*   `/tree` : Draws the folder structure starting from the current directory
*   `/git` : Displays current Git status and the last 10 commit logs
*   `/diff` : Displays color-coded syntax diff of changes
*   `/commit` : Instructs LLM to analyze git diff, write a commit message, and perform the Git commit
*   `/context` : Shows the current project context saved in `.qwen-context.md`
*   `exit` / `quit` : Safely terminates the CLI and saves input command history

---

## ⚙️ 3. Agent System Configuration

*   **LLM Target**: OpenAI-compatible API (`http://127.0.0.1:8080/v1`)
*   **Model Name**: `qwen2.5-7b-instruct-q4_k_m`
*   **Safety Guard**: Displays warning and prompts for user confirmation (Confirmation Gate) if the agent attempts to run potentially harmful commands (e.g. `rm -rf`, `sudo`, `chmod 777`).
*   **Token Optimization**:
    *   Caps execution steps at `MAX_ITERATIONS = 20` per query loop.
    *   Triggers **Context Trimming & Summary Auto-compress** when chat history exceeds `MAX_HISTORY_MSGS = 40` messages to keep response times high.
