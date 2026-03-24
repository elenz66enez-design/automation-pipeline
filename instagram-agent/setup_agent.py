#!/usr/bin/env python3
"""
Rabbi Goldsteyn — n8n Setup Computer Use Agent
Automates the manual setup steps using Claude Opus computer use.

Runs on your local macOS machine. Opens a browser and completes:
  1. upload-post.com account + Instagram connect
  2. Google Sheets tracking sheet creation
  3. n8n workflow import + credential setup

Usage:
    python3 setup_agent.py [--task upload-post|google-sheets|n8n|all]

Requires:
    ANTHROPIC_API_KEY in environment
"""

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import anthropic
import pyautogui
from PIL import Image

# ── Constants ──────────────────────────────────────────────────────────────────

SCREEN_W, SCREEN_H = 1280, 800
MODEL = "claude-opus-4-6"           # Best model for computer use
TOOL_VERSION = "computer_20250124"  # Latest compatible tool version
BETA_FLAG = "computer-use-2025-01-24"
MAX_STEPS = 40
ACTION_DELAY = 0.8                  # Seconds between actions

N8N_WORKFLOW_PATH = Path(__file__).parent / "n8n-workflow.json"

TASKS = {
    "upload-post": """
        Go to https://upload-post.com in the browser.
        1. Click "Sign Up" or "Get Started"
        2. Create an account with email/password
        3. After signing up, navigate to Settings → Integrations or Connect Instagram
        4. Connect the Instagram account (OAuth flow)
        5. After connecting, navigate to Settings → API and generate/copy the API key
        6. Navigate to Posts or Dashboard and find the Post ID for the Rabbi Goldsteyn post
        7. Tell me: what is the API key and what post IDs are available?
        Take your time and proceed step by step.
    """,

    "google-sheets": """
        Go to https://sheets.google.com in the browser.
        1. Create a new spreadsheet
        2. Name it: "Rabbi Goldsteyn — IG DM Tracking"
        3. Rename "Sheet1" tab to: ig_dm_sent
        4. In row 1, enter these headers exactly:
           A1: comment_id
           B1: username
           C1: ts
           D1: step
        5. Bold the header row
        6. Copy the spreadsheet ID from the URL (the long string between /d/ and /edit)
        7. Tell me the Spreadsheet ID so I can configure n8n
    """,

    "n8n": f"""
        Go to https://app.n8n.cloud or http://localhost:5678 in the browser.
        If not logged in, sign up for a free account first.

        1. After login, click "Workflows" in the left sidebar
        2. Click "Add workflow" or the + button
        3. Look for "Import" option (usually in the menu or top-right)
        4. Import the workflow from file — the file path is: {N8N_WORKFLOW_PATH}
        5. After import, open the workflow
        6. Set up credentials:
           a. For "upload-post.com API Key" credential:
              - Type: HTTP Header Auth
              - Header Name: Authorization
              - Header Value: Bearer [enter the API key from upload-post.com]
           b. For "Google Sheets OAuth2" credential:
              - Type: Google Sheets OAuth2 API
              - Complete the OAuth flow
        7. Set up Variables (Settings → Variables):
           - INSTAGRAM_POST_ID: [the post ID from upload-post.com]
           - GOOGLE_SHEET_ID: [the Sheet ID from Google Sheets]
        8. Activate the workflow (toggle at top)
        Tell me when each step is complete.
    """,
}


# ── Screenshot ──────────────────────────────────────────────────────────────────

def capture_screenshot() -> str:
    """Capture macOS screen, return base64 PNG."""
    # Use macOS screencapture (no display server needed)
    subprocess.run(
        ["screencapture", "-x", "-t", "png", "/tmp/agent_screenshot.png"],
        check=True,
        capture_output=True,
    )
    img = Image.open("/tmp/agent_screenshot.png")
    img = img.resize((SCREEN_W, SCREEN_H), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Action Executor ─────────────────────────────────────────────────────────────

def execute_action(action: dict) -> dict:
    """Execute a computer use action via pyautogui."""
    atype = action.get("action") or action.get("type")

    # Scale coordinates from model's 1280x800 space to actual screen
    actual_w, actual_h = pyautogui.size()
    scale_x = actual_w / SCREEN_W
    scale_y = actual_h / SCREEN_H

    def scale(x, y):
        return int(x * scale_x), int(y * scale_y)

    if atype == "screenshot":
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": capture_screenshot()}}

    elif atype == "left_click" or atype == "click":
        x, y = scale(action["coordinate"][0], action["coordinate"][1])
        pyautogui.click(x, y)
        time.sleep(ACTION_DELAY)
        return {"output": f"Clicked ({x}, {y})"}

    elif atype == "right_click":
        x, y = scale(action["coordinate"][0], action["coordinate"][1])
        pyautogui.rightClick(x, y)
        time.sleep(ACTION_DELAY)
        return {"output": f"Right-clicked ({x}, {y})"}

    elif atype == "double_click":
        x, y = scale(action["coordinate"][0], action["coordinate"][1])
        pyautogui.doubleClick(x, y)
        time.sleep(ACTION_DELAY)
        return {"output": f"Double-clicked ({x}, {y})"}

    elif atype == "type":
        text = action.get("text", "")
        pyautogui.typewrite(text, interval=0.04)
        time.sleep(0.3)
        return {"output": f"Typed {len(text)} chars"}

    elif atype == "key":
        key = action.get("text", "")
        # Map common keys
        key_map = {
            "Return": "enter", "Tab": "tab", "Escape": "escape",
            "BackSpace": "backspace", "ctrl+a": "ctrl+a", "ctrl+c": "ctrl+c",
            "ctrl+v": "ctrl+v", "cmd+a": "command+a", "cmd+c": "command+c",
            "cmd+v": "command+v",
        }
        mapped = key_map.get(key, key)
        if "+" in mapped:
            parts = mapped.split("+")
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(mapped)
        time.sleep(0.3)
        return {"output": f"Pressed key: {key}"}

    elif atype == "scroll":
        x, y = scale(action["coordinate"][0], action["coordinate"][1])
        direction = action.get("direction", "down")
        amount = action.get("amount", 3)
        scroll = -amount if direction == "down" else amount
        pyautogui.scroll(scroll, x=x, y=y)
        time.sleep(0.3)
        return {"output": f"Scrolled {direction} at ({x}, {y})"}

    elif atype == "mouse_move":
        x, y = scale(action["coordinate"][0], action["coordinate"][1])
        pyautogui.moveTo(x, y)
        return {"output": f"Moved mouse to ({x}, {y})"}

    elif atype == "left_click_drag":
        sx, sy = scale(action["start_coordinate"][0], action["start_coordinate"][1])
        ex, ey = scale(action["coordinate"][0], action["coordinate"][1])
        pyautogui.drag(sx, sy, ex, ey, duration=0.5)
        time.sleep(0.3)
        return {"output": f"Dragged from ({sx},{sy}) to ({ex},{ey})"}

    elif atype == "zoom":
        # Opus 4.5+ zoom action — capture zoomed region
        x, y = scale(action["coordinate"][0], action["coordinate"][1])
        img = pyautogui.screenshot(region=(x - 100, y - 100, 200, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}

    elif atype == "cursor_position":
        x, y = pyautogui.position()
        return {"output": f"Cursor at ({x}, {y})"}

    else:
        return {"error": f"Unknown action: {atype}"}


# ── Agent Loop ──────────────────────────────────────────────────────────────────

def run_agent(task: str, task_name: str):
    """Run the computer use agent for a given task."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    tools = [
        {
            "type": TOOL_VERSION,
            "name": "computer",
            "display_width_px": SCREEN_W,
            "display_height_px": SCREEN_H,
        }
    ]

    # Initial screenshot
    print(f"\n[Agent] Starting task: {task_name}")
    print("[Agent] Taking initial screenshot...")
    initial_screenshot = capture_screenshot()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": initial_screenshot,
                    },
                },
                {
                    "type": "text",
                    "text": f"Here is the current screen. Please complete this task:\n\n{task}\n\nProceed step by step. Use the computer tool to interact with the screen.",
                },
            ],
        }
    ]

    step = 0
    while step < MAX_STEPS:
        step += 1
        print(f"\n[Agent] Step {step}/{MAX_STEPS}")

        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=tools,
            messages=messages,
            betas=[BETA_FLAG],
        )

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        # Process tool uses
        tool_results = []
        has_tool_use = False

        for block in response.content:
            if block.type == "text":
                print(f"[Claude] {block.text[:300]}")
            elif block.type == "tool_use" and block.name == "computer":
                has_tool_use = True
                action = block.input
                action_type = action.get("action", "?")
                print(f"[Action] {action_type}: {json.dumps(action, default=str)[:120]}")

                result = execute_action(action)

                # Build tool result content
                if result.get("type") == "image":
                    content = [result]
                elif "error" in result:
                    content = [{"type": "text", "text": f"Error: {result['error']}"}]
                else:
                    # Take new screenshot after action (unless it was a screenshot request)
                    if action_type != "screenshot":
                        time.sleep(0.5)
                        new_screenshot = capture_screenshot()
                        content = [
                            {"type": "text", "text": result.get("output", "Action completed")},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": new_screenshot,
                                },
                            },
                        ]
                    else:
                        content = [result]

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })

        # If no tool use and stop reason is end_turn, we're done
        if not has_tool_use:
            if response.stop_reason == "end_turn":
                print("\n[Agent] Task complete!")
                # Print final message
                for block in response.content:
                    if block.type == "text":
                        print(f"\n[Result]\n{block.text}")
                break
        else:
            # Add tool results and continue
            messages.append({"role": "user", "content": tool_results})

    else:
        print(f"\n[Agent] Reached max steps ({MAX_STEPS}). Stopping.")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Rabbi Goldsteyn n8n Setup Agent")
    parser.add_argument(
        "--task",
        choices=["upload-post", "google-sheets", "n8n", "all"],
        default="all",
        help="Which setup task to run (default: all)",
    )
    args = parser.parse_args()

    # Safety check
    print("=" * 60)
    print("Rabbi Goldsteyn — Computer Use Setup Agent")
    print("=" * 60)
    print("This agent will control your browser to complete the n8n setup.")
    print(f"Task: {args.task}")
    print()

    if args.task == "all":
        task_order = ["upload-post", "google-sheets", "n8n"]
    else:
        task_order = [args.task]

    for task_name in task_order:
        input(f"Press Enter to start task: {task_name} (Ctrl+C to cancel)")
        run_agent(TASKS[task_name], task_name)
        print(f"\n✓ Task '{task_name}' finished.\n")
        if len(task_order) > 1:
            time.sleep(2)

    print("\nAll tasks complete.")


if __name__ == "__main__":
    main()
