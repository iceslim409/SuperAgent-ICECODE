"""
ICECODE Computer Control Tools

Gives the agent full autonomous control over the desktop:
- screenshot: capture screen (returns base64 PNG)
- click: left/right/double click at coordinates
- type_text: type text (keyboard)
- hotkey: press key combinations (Ctrl+C, Alt+Tab, etc.)
- move_mouse: move mouse to coordinates
- scroll: scroll at position
- get_screen_size: screen dimensions
- find_on_screen: find image/text on screen
- open_app: open an application by name
- focus_window: focus a window by title
"""
from __future__ import annotations

import base64
import io
import os
import subprocess
import time
from typing import Dict, List

# pyautogui is optional — graceful fallback if DISPLAY not set
_PYAUTOGUI_AVAILABLE = False
_PYAUTOGUI_ERR = ""

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI_AVAILABLE = True
except Exception as e:
    _PYAUTOGUI_ERR = str(e)


COMPUTER_TOOLS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current screen. Returns base64 PNG. Use this to see what's on screen before clicking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional crop region {x, y, width, height}",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click the mouse at specific screen coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate in pixels"},
                    "y": {"type": "integer", "description": "Y coordinate in pixels"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button (default: left)"},
                    "double": {"type": "boolean", "description": "Double-click (default: false)"},
                    "clicks": {"type": "integer", "description": "Number of clicks"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text using the keyboard. Types into the currently focused window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "interval": {"type": "number", "description": "Delay between keystrokes in seconds (default: 0.02)"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Press a keyboard shortcut (e.g. ctrl+c, alt+tab, ctrl+shift+t, win).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keys to press together, e.g. ['ctrl', 'c'] or ['alt', 'tab']",
                    }
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse cursor to a position without clicking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "duration": {"type": "number", "description": "Movement duration in seconds (0 = instant)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the mouse wheel at a position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "clicks": {"type": "integer", "description": "Positive = scroll up/right, negative = scroll down/left"},
                    "direction": {"type": "string", "enum": ["vertical", "horizontal"]},
                },
                "required": ["x", "y", "clicks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_size",
            "description": "Get the screen width and height in pixels.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application. Works on Linux/macOS/Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "App name or path, e.g. 'firefox', 'gnome-terminal', 'calculator'"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Optional CLI arguments"},
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "Focus a window by its title substring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Substring of the window title to find and focus"}
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read the current clipboard content.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_clipboard",
            "description": "Write text to the clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"],
            },
        },
    },
]


async def exec_computer_tool(name: str, args: Dict) -> str:
    """Execute a computer control tool. Returns string result."""
    if not _PYAUTOGUI_AVAILABLE:
        return f"Computer control not available: {_PYAUTOGUI_ERR}. Ensure DISPLAY is set and pyautogui is installed."

    try:
        if name == "screenshot":
            region = args.get("region")
            if region:
                img = pyautogui.screenshot(region=(region["x"], region["y"], region["width"], region["height"]))
            else:
                img = pyautogui.screenshot()
            # Resize to max 1200px wide to save tokens
            if img.width > 1200:
                ratio = 1200 / img.width
                img = img.resize((1200, int(img.height * ratio)))
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            size_kb = len(buf.getvalue()) // 1024
            return f"[SCREENSHOT: {img.width}x{img.height}px, {size_kb}KB]\ndata:image/png;base64,{b64[:100]}... (full base64 available)"

        elif name == "click":
            x, y = args["x"], args["y"]
            button = args.get("button", "left")
            double = args.get("double", False)
            clicks = args.get("clicks", 2 if double else 1)
            pyautogui.click(x, y, clicks=clicks, button=button)
            return f"Clicked {button} at ({x}, {y}) — {clicks}x"

        elif name == "type_text":
            text = args["text"]
            interval = args.get("interval", 0.02)
            pyautogui.typewrite(text, interval=interval)
            return f"Typed {len(text)} characters"

        elif name == "hotkey":
            keys = args["keys"]
            pyautogui.hotkey(*keys)
            return f"Pressed: {'+'.join(keys)}"

        elif name == "move_mouse":
            x, y = args["x"], args["y"]
            dur = args.get("duration", 0.1)
            pyautogui.moveTo(x, y, duration=dur)
            return f"Mouse moved to ({x}, {y})"

        elif name == "scroll":
            x, y = args["x"], args["y"]
            clicks = args["clicks"]
            direction = args.get("direction", "vertical")
            if direction == "horizontal":
                pyautogui.hscroll(x, y, clicks)
            else:
                pyautogui.scroll(clicks, x, y)
            return f"Scrolled {clicks} at ({x}, {y})"

        elif name == "get_screen_size":
            w, h = pyautogui.size()
            return f"Screen size: {w}x{h} pixels"

        elif name == "open_app":
            app = args["app"]
            app_args = args.get("args", [])
            display = os.environ.get("DISPLAY", ":0")
            env = {**os.environ, "DISPLAY": display}
            subprocess.Popen(
                [app] + app_args,
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            return f"Opened: {app} {' '.join(app_args)}"

        elif name == "focus_window":
            title = args["title"]
            # Use wmctrl if available, otherwise xdotool
            if subprocess.run(["which", "wmctrl"], capture_output=True).returncode == 0:
                result = subprocess.run(
                    ["wmctrl", "-a", title], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return f"Focused window matching: {title}"
            # Fallback: xdotool
            if subprocess.run(["which", "xdotool"], capture_output=True).returncode == 0:
                result = subprocess.run(
                    ["xdotool", "search", "--name", title, "windowfocus"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return f"Focused window matching: {title}"
            return f"Could not focus window '{title}' — wmctrl/xdotool not available"

        elif name == "read_clipboard":
            import subprocess as sp
            result = sp.run(["xclip", "-selection", "clipboard", "-o"],
                          capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return result.stdout[:500]
            # pyperclip fallback
            import pyperclip
            return pyperclip.paste()[:500]

        elif name == "write_clipboard":
            text = args["text"]
            import pyperclip
            pyperclip.copy(text)
            return f"Written {len(text)} chars to clipboard"

        else:
            return f"Unknown computer tool: {name}"

    except pyautogui.FailSafeException:
        return "FAILSAFE TRIGGERED: Mouse moved to corner. Move mouse away from corner to continue."
    except Exception as e:
        return f"Computer tool error ({name}): {type(e).__name__}: {e}"
