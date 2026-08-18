"""Interactive Antigravity Conversation Explorer with keyboard navigation (Left/Right arrow paging)."""

import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# On Windows, msvcrt provides instant single-keypress reading
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


def clean_prompt(raw_text: str) -> str:
    """Extract clean user request from raw transcript content."""
    if not raw_text:
        return "(empty)"
    match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        raw_text = match.group(1)
    
    cleaned = re.sub(r"<[^>]+>", "", raw_text)
    cleaned = re.sub(r"^/[a-zA-Z0-9_-]+\s*", "", cleaned.strip())
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 70:
        return cleaned[:67] + "..."
    return cleaned or "(no prompt)"


def get_conversation_purpose(conv_dir: Path) -> tuple[datetime, str]:
    """Read the transcript and find the first user input."""
    log_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
    mtime = datetime.fromtimestamp(conv_dir.stat().st_mtime)
    if not log_file.exists():
        return mtime, "(no logs)"

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "USER_INPUT":
                        content = data.get("content", "")
                        return mtime, clean_prompt(content)
                except Exception:
                    continue
    except Exception:
        pass

    return mtime, "(empty session)"


def load_conversations() -> list[dict]:
    user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    brain_dir = user_home / ".gemini" / "antigravity-cli" / "brain"

    if not brain_dir.exists():
        return []

    conversations = []
    for entry in brain_dir.iterdir():
        if entry.is_dir() and len(entry.name) == 36:
            mtime, purpose = get_conversation_purpose(entry)
            conversations.append({
                "id": entry.name,
                "mtime": mtime,
                "purpose": purpose,
            })

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations


def render_page(conversations: list[dict], page_idx: int, page_size: int, selected_rel_idx: int):
    total_items = len(conversations)
    total_pages = max(1, math.ceil(total_items / page_size))
    page_idx = max(0, min(page_idx, total_pages - 1))

    start_idx = page_idx * page_size
    end_idx = min(start_idx + page_size, total_items)
    page_items = conversations[start_idx:end_idx]

    # Clear screen
    os.system("cls" if os.name == "nt" else "clear")

    print("=" * 115)
    print(f" >>> ANTIGRAVITY CONVERSATION EXPLORER  |  Page {page_idx + 1} of {total_pages}  (Total: {total_items})")
    print("=" * 115)
    print(f" {'#':<3} | {'Last Active':<16} | {'Conversation ID':<36} | {'Main Purpose / Topic'}")
    print("-" * 115)

    for i, conv in enumerate(page_items):
        global_num = start_idx + i + 1
        mtime_str = conv["mtime"].strftime("%Y-%m-%d %H:%M")
        is_selected = (i == selected_rel_idx)
        prefix = ">" if is_selected else " "
        
        row_str = f"{prefix}{global_num:<3} | {mtime_str:<16} | {conv['id']:<36} | {conv['purpose']}"
        if is_selected:
            print(f" [{row_str}]")
        else:
            print(f"  {row_str}")

    print("-" * 115)
    print(" ⌨️  KEYBOARD CONTROLS:")
    print("    [Left Arrow  <--]  : Previous Page     |  [Right Arrow  -->] : Next Page")
    print("    [Up / Down Arrow]  : Select Item       |  [ENTER]            : Resume Selected Chat")
    print("    [Number 1-9]       : Quick Jump Item   |  [Q / ESC]          : Exit Explorer")
    print("=" * 115)


def read_key() -> str:
    """Read a single keypress, returning 'LEFT', 'RIGHT', 'UP', 'DOWN', 'ENTER', 'ESC', 'QUIT', or character."""
    if not HAS_MSVCRT:
        cmd = input().strip().lower()
        if cmd in ("n", "right", ">"):
            return "RIGHT"
        if cmd in ("p", "left", "<"):
            return "LEFT"
        if cmd in ("q", "exit"):
            return "QUIT"
        return cmd

    ch = msvcrt.getch()
    if ch in (b"\x00", b"\xe0"):  # Special prefix for arrow keys
        code = msvcrt.getch()
        if code == b"K":
            return "LEFT"
        elif code == b"M":
            return "RIGHT"
        elif code == b"H":
            return "UP"
        elif code == b"P":
            return "DOWN"
        elif code == b"S":  # Delete
            return "DEL"
    elif ch in (b"\r", b"\n"):
        return "ENTER"
    elif ch == b"\x1b":  # ESC
        return "ESC"
    elif ch in (b"q", b"Q"):
        return "QUIT"
    elif ch in (b"n", b"N"):
        return "RIGHT"
    elif ch in (b"p", b"P"):
        return "LEFT"
    else:
        try:
            return ch.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    return ""


def main():
    conversations = load_conversations()
    if not conversations:
        print("No conversations found in brain directory.")
        return

    # Non-interactive mode fallback
    if "--no-prompt" in sys.argv or "-n" in sys.argv:
        limit = 20
        print(f"{'#':<3} | {'Last Active':<16} | {'Conversation ID':<36} | {'Main Purpose / Topic'}")
        print("-" * 115)
        for idx, conv in enumerate(conversations[:limit], 1):
            mtime_str = conv["mtime"].strftime("%Y-%m-%d %H:%M")
            print(f"{idx:<3} | {mtime_str:<16} | {conv['id']:<36} | {conv['purpose']}")
        return

    page_size = 10
    total_pages = max(1, math.ceil(len(conversations) / page_size))
    current_page = 0
    selected_idx = 0

    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(conversations))
        current_page_count = end_idx - start_idx

        # Clamp selected index
        if selected_idx >= current_page_count:
            selected_idx = max(0, current_page_count - 1)

        render_page(conversations, current_page, page_size, selected_idx)

        key = read_key()

        if key in ("QUIT", "ESC"):
            print("\nExiting.")
            break
        elif key == "RIGHT":
            if current_page < total_pages - 1:
                current_page += 1
                selected_idx = 0
        elif key == "LEFT":
            if current_page > 0:
                current_page -= 1
                selected_idx = 0
        elif key == "UP":
            if selected_idx > 0:
                selected_idx -= 1
            elif current_page > 0:
                current_page -= 1
                selected_idx = page_size - 1
        elif key == "DOWN":
            if selected_idx < current_page_count - 1:
                selected_idx += 1
            elif current_page < total_pages - 1:
                current_page += 1
                selected_idx = 0
        elif key == "ENTER":
            chosen_conv = conversations[start_idx + selected_idx]
            print(f"\n>>> Resuming conversation: {chosen_conv['id']} (Auto-approving permissions) ...\n")
            subprocess.run(["agy", "--conversation", chosen_conv["id"], "--dangerously-skip-permissions"])
            break
        elif key.isdigit() and 1 <= int(key) <= current_page_count:
            chosen_conv = conversations[start_idx + int(key) - 1]
            print(f"\n>>> Resuming conversation: {chosen_conv['id']} (Auto-approving permissions) ...\n")
            subprocess.run(["agy", "--conversation", chosen_conv["id"], "--dangerously-skip-permissions"])
            break


if __name__ == "__main__":
    main()
