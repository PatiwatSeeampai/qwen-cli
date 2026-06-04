---
name: qwen-code-cli
description: Local AI Coding Agent with Rich UI, streaming, surgical patching, and git automation.
---

# 🤖 Qwen Code CLI — Agent Capabilities & Skills Documentation

เอกสารนี้รวบรวมทักษะการทำงาน (Skills), คำสั่งลัด (Slash Commands) และเครื่องมือ (Tools) ทั้งหมดของระบบ Qwen Code CLI เพื่อเป็นคู่มือโครงสร้างและสถาปัตยกรรมของ Agent ให้เป็นระบบและเป็นระเบียบเรียบร้อย

---

## 🛠️ 1. Agent Bindings & Tools (เครื่องมือที่โมเดลใช้งานได้)

โมเดล LLM ในระบบสามารถเรียกใช้เครื่องมือในรูปแบบ Function Calling ได้ทั้งหมด 9 เครื่องมือหลัก ดังนี้:

| เครื่องมือ (Tool Name) | คำอธิบาย (Description) | พารามิเตอร์หลัก (Key Parameters) |
|---|---|---|
| `execute_bash_command` | รันคำสั่ง Terminal แบบ Async Stream | `command` (str) |
| `view_and_read_file` | อ่านเนื้อหาไฟล์โดยระบุขอบเขตบรรทัดได้ | `file_path`, `start_line`, `end_line` |
| `write_or_edit_file` | เขียนไฟล์ใหม่หรือเขียนทับ (มีระบบตรวจ Diff) | `file_path`, `content` |
| `patch_file` | แก้ไขโค้ดเฉพาะจุดแบบปลอดภัย (Surgical Edit) | `file_path`, `old_snippet`, `new_snippet` |
| `search_in_files` | ค้นหาคีย์เวิร์ดในโปรเจกต์ด้วย Regex/Grep | `pattern`, `directory`, `file_glob` |
| `list_directory_tree` | แสดงแผนผังโครงสร้างของไฟล์และโฟลเดอร์ | `directory`, `max_depth` |
| `get_file_outline` | แสดง Outline คลาส เมธอด และฟังก์ชันของไฟล์ | `file_path` |
| `get_git_info` | ดึงข้อมูลกิ่ง (Branch), สเตตัส และประวัติ Commit | `repo_path` |
| `create_project_context`| สร้างหรืออัปเดตไฟล์คอนเทกซ์ของโปรเจกต์ | `content` |

---

## 📖 2. Slash Commands (คำสั่งลัดที่ผู้ใช้พิมพ์ควบคุม)

คำสั่งระบบที่ถูกประมวลผลภายในตัวเครื่อง (Client-side Commands) โดยไม่ต้องเรียกใช้โมเดลเพื่อประหยัดทรัพยากร:

*   `/help` : แสดงหน้าคู่มือคำสั่งลัดพิเศษ
*   `/clear` : เคลียร์ข้อความบนหน้าต่างแชทเพื่อความเป็นระเบียบ
*   `/reset` : ล้างสถานะ Context/History (จำเป็นมากเมื่อคุยยาวแล้ว LLM เริ่มตอบช้าลง)
*   `/tools` : แสดงรายการและรายละเอียดเครื่องมือทั้งหมดของบอท
*   `/tree` : วาดแผนภาพโฟลเดอร์ปัจจุบันแบบเจาะลึก
*   `/git` : แสดง Git Status และประวัติ Commit ล่าสุด
*   `/diff` : แสดงความต่างของโค้ดล่าสุดแบบใส่สี (Syntax Colored Diff)
*   `/commit` : ให้บอทวิเคราะห์การแก้ไขและช่วย Commit งานพร้อมแต่งข้อความแบบมืออาชีพ
*   `/context` : แสดงภาพรวมโปรเจกต์ในไฟล์ `.qwen-context.md`
*   `exit` / `quit` : ปิดโปรแกรมและบันทึกประวัติการพิมพ์

---

## ⚙️ 3. Agent System Configuration (การตั้งค่าระบบ)

*   **LLM Target**: OpenAI Compatible API (`http://127.0.0.1:8080/v1`)
*   **Model Name**: `qwen2.5-7b-instruct-q4_k_m`
*   **Safety Guard**: ระบบจะแจ้งเตือนและขอคำยืนยัน (Confirmation Gate) ทุกครั้งหากโมเดลพยายามจะรันคำสั่งอันตราย เช่น `rm -rf`, `sudo`, `chmod 777`
*   **Token Optimization**:
    *   จำกัดรอบการคิดสูงสุดที่ `MAX_ITERATIONS = 20` รอบต่อ 1 คำถาม
    *   ทำระบบ **Context Trimming & Summary Auto-compress** เมื่อประวัติแชทเกิน `MAX_HISTORY_MSGS = 40` ข้อความ เพื่อคงความเร็วการตอบกลับให้ไม่ดรอป
