# 🚀 Google Antigravity CLI (`agy`) — Master Commands & Shortcuts Cheat Sheet

> **Saved Location:** `docs/ANTIGRAVITY_COMMANDS_CHEAT_SHEET.md`  
> **Last Updated:** 2026-08-17

---

## ⚡ 1. Ultra-Short Permission Skip Commands (Auto-Approve)

No need to type `--dangerously-skip-permissions` anymore. Use these short aliases:

| Command | Action | Description |
| :--- | :--- | :--- |
| `agyy` | **Start New Chat (Auto-Approve)** | Starts a new agent session with all tool permissions pre-approved. |
| `agyc` | **Continue Last Chat (Auto-Approve)** | Continues your most recent conversation with permissions pre-approved. |
| `agy -y` | **Flag: Auto-Approve** | Replaces `--dangerously-skip-permissions`. Can be combined with other flags. |
| `agy -yc` | **Continue + Auto-Approve** | Equivalent to `agy -c --dangerously-skip-permissions`. |
| `agy -y --conversation <ID>` | **Resume Specific Chat (Auto-Approve)** | Resumes a specific conversation ID with auto-approved permissions. |

---

## 📋 2. Interactive Conversation Explorer (With Keyboard Navigation)

List all your past conversation histories, sorted from newest to oldest, with their **Main Purpose / Topic**:

```powershell
agy --list
```
*(or `agy -l` or `agy-list` in CMD)*

### 🎮 Keyboard Controls Inside the Explorer:
- <kbd>→</kbd> **Right Arrow** *(or `N`)*: Next Page
- <kbd>←</kbd> **Left Arrow** *(or `P`)*: Previous Page
- <kbd>↑</kbd> / <kbd>↓</kbd> **Up / Down Arrow**: Highlight items on the current page
- <kbd>Enter</kbd>: **Resume highlighted conversation immediately** *(with auto-approved permissions)*
- <kbd>1</kbd> – <kbd>9</kbd>: Quick jump and resume item number directly
- <kbd>Esc</kbd> *(or `Q`)*: Exit explorer

---

## 🔄 3. Resume Past Sessions Manually

| Command | Action |
| :--- | :--- |
| `agy -c` | Continue your **most recent** conversation. |
| `agy --continue` | Same as `agy -c`. |
| `agy --conversation <CONVERSATION_ID>` | Resume a specific past conversation by its UUID. |

---

## 🛠️ 4. Useful Antigravity CLI Commands & Flags

| Command / Flag | Description |
| :--- | :--- |
| `agy` | Launch standard interactive agent session. |
| `agy --model <model_name>` | Choose model for session (e.g. `gemini-3.7-flash`, etc.). |
| `agy --effort <low\|medium\|high>` | Set reasoning effort for the session. |
| `agy --mode plan` | Launch in planning mode. |
| `agy models` | List all available AI models. |
| `agy agents` | List available subagents. |
| `agy changelog` | View recent Antigravity updates and changelog. |
| `agy update` | Update Antigravity CLI to the latest version. |

---

## 📁 5. Key System Paths & File Locations

| Resource | Path |
| :--- | :--- |
| **All Conversation Logs & Brain** | `C:\Users\korba\.gemini\antigravity-cli\brain\<CONVERSATION_ID>\` |
| **PowerShell Profile Config** | `C:\Users\korba\OneDrive\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` |
| **CLI Binaries & Shortcuts** | `C:\Users\korba\AppData\Local\agy\bin\` |
| **Global Explorer Script** | `C:\Users\korba\.gemini\antigravity-cli\scripts\list_chats.py` |
