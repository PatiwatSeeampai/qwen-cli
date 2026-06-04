# 🤖 Qwen Code CLI v2.0 — Claude Code Style

> Local AI Coding Agent ที่รันบนเครื่องตัวเอง พร้อม UI และฟีเจอร์ครบเหมือน Claude Code

---

## ✨ Features ใหม่ทั้งหมด

| Feature | รายละเอียด |
|---|---|
| **Rich Terminal UI** | Syntax highlighting, Panel, Tree, Table สวยงาม |
| **Smart Input** | History ข้ามเซสชัน + Autocomplete จาก `prompt_toolkit` |
| **Patch Mode** | แก้ไขเฉพาะ block ที่ระบุ (`patch_file`) แทน overwrite ทั้งไฟล์ |
| **Git Integration** | `git_operations` tool ครบ: status, diff, commit, push, pull |
| **Approval Gate** | คำสั่งอันตราย (`rm`, `sudo`, `chmod`...) ต้องยืนยันก่อนรันเสมอ |
| **Session Save/Load** | บันทึก/โหลด conversation ได้ข้ามเซสชัน |
| **Auto-save** | บันทึก session อัตโนมัติทุกครั้งที่ออกจากโปรแกรม |
| **Compact** | สรุปและล้าง history เพื่อประหยัด context window |
| **Context Trimming** | ตัด history เก่าอัตโนมัติ ป้องกัน overflow |
| **File Tools ครบ** | list, search, delete, move/rename, read, write, patch |
| **Slash Commands** | `/help /save /load /compact /clear /status /tree /cd /history` |

---

## 🚀 ติดตั้งและรัน

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. เริ่ม Local LLM Server (llama.cpp หรือ LM Studio)
```bash
# ตัวอย่างด้วย llama-server
llama-server -m qwen2.5-7b-instruct-q4_k_m.gguf --port 8080
```

### 3. รัน CLI
```bash
python qwen_cli.py
```

---

## 📖 Slash Commands

```
/help              แสดงคำสั่งทั้งหมด
/save [name]       บันทึก session ปัจจุบัน
/load <name>       โหลด session ที่บันทึกไว้
/sessions          แสดง sessions ทั้งหมด
/compact           สรุปและล้าง history (ประหยัด context)
/clear             ล้าง history ทั้งหมด เริ่มใหม่
/status            แสดง git status
/tree [path]       แสดงโครงสร้างไดเรกทอรี
/cd <path>         เปลี่ยน working directory
/pwd               แสดง working directory ปัจจุบัน
/history           แสดง message history ทั้งหมด
/exit              ออกจากโปรแกรม (auto-save)
```

---

## 🛠️ Tools ที่ Agent ใช้ได้

| Tool | หน้าที่ |
|---|---|
| `execute_bash_command` | รัน bash command (มี approval สำหรับคำสั่งอันตราย) |
| `view_and_read_file` | อ่านไฟล์ + แสดง syntax highlight |
| `write_or_edit_file` | เขียน/overwrite ไฟล์ทั้งหมด |
| `patch_file` | แก้ไขเฉพาะ block ที่ระบุ (surgical edit) |
| `list_directory` | แสดงโครงสร้างไฟล์แบบ tree |
| `search_in_files` | ค้นหา pattern ใน codebase |
| `delete_file` | ลบไฟล์/โฟลเดอร์ (ต้อง confirm) |
| `move_or_rename_file` | ย้ายหรือเปลี่ยนชื่อไฟล์ |
| `git_operations` | Git: status/diff/log/add/commit/push/pull |

---

## 🗂️ Files ที่สร้าง

```
~/.qwen_cli/
├── sessions/          ← session files (.json)
└── input_history      ← prompt_toolkit input history
```

---

## 💡 Tips

- ใช้ **`/compact`** เมื่อ session ยาวมากและ Agent เริ่มตอบช้าหรือหลงประเด็น
- ใช้ **`patch_file`** แทน `write_or_edit_file` เมื่อแก้ไขแค่บางส่วน ปลอดภัยกว่ามาก
- กด **↑/↓** เพื่อดู input history ของเซสชันก่อนหน้า
- **Auto-save** ทำงานทุกครั้งที่กด `/exit` หรือ Ctrl+C
