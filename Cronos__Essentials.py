"""
Always-On-Top Countdown Timer (v2)
------------------------------------
New in this version:
  - Appearance dialog: change font color, font family, font size, background color
  - Window can be shrunk much smaller (minimum ~80x40 px)
  - Below a certain size, the event name and buttons auto-hide so only the
    countdown numbers remain
  - The native Windows title bar is recolored to match your background,
    so it blends in instead of looking like a default white/gray bar
    (requires Windows 10 1809+ or Windows 11; safely does nothing on other OSes)

Run it with:
    python countdown_timer.py

Settings + your event are saved to "countdown_config.json" next to this file.
"""

import json
import os
import sys
import ctypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, colorchooser
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "countdown_config.json")

# Window shrinks below these dimensions -> hide everything except the countdown
COMPACT_WIDTH_THRESHOLD = 180
COMPACT_HEIGHT_THRESHOLD = 95

FONT_SIZE_MIN = 10
FONT_SIZE_AUTO_MIN = 15
# Widest typical countdown string used when probing max font size
FONT_SIZE_PROBE = "999d 23:59:59"

FONT_CHOICES = [
    "Consolas", "Segoe UI", "Arial", "Courier New",
    "Verdana", "Comic Sans MS", "Times New Roman"
]

DEFAULTS = {
    "name": "Your Event",
    "bg_color": "#1e1e1e",
    "font_color": "#4caf50",
    "font_family": "Consolas",
    "font_size": 20,
}


def compute_fit_font_size(root, font_family, max_w, max_h, floor=FONT_SIZE_MIN, ceiling=500):
    """Largest bold digit size that fits inside max_w x max_h."""
    floor = max(FONT_SIZE_MIN, int(floor))
    ceiling = max(floor, int(ceiling))
    lo, hi, best = floor, ceiling, floor
    while lo <= hi:
        mid = (lo + hi) // 2
        probe = tkfont.Font(root=root, family=font_family, size=mid, weight="bold")
        if probe.measure(FONT_SIZE_PROBE) <= max_w and probe.metrics("linespace") <= max_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def compute_max_font_size(root, font_family):
    """Largest bold digit size that still fits comfortably on a maximized window."""
    return compute_fit_font_size(
        root, font_family,
        int(root.winfo_screenwidth() * 0.9),
        int(root.winfo_screenheight() * 0.55),
    )


def clamp_font_size(size, max_size):
    try:
        size = int(size)
    except (TypeError, ValueError, tk.TclError):
        size = DEFAULTS["font_size"]
    return max(FONT_SIZE_MIN, min(size, max_size))


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                if "target" in data:
                    data["target"] = datetime.fromisoformat(data["target"])
                for key, val in DEFAULTS.items():
                    data.setdefault(key, val)
                return data
        except Exception:
            pass
    return None


def save_config(name, target_dt, bg_color, font_color, font_family, font_size):
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "name": name,
            "target": target_dt.isoformat() if target_dt else None,
            "bg_color": bg_color,
            "font_color": font_color,
            "font_family": font_family,
            "font_size": font_size,
        }, f)


def set_title_bar_color(root, hex_color):
    """Recolor the native Windows title bar to match hex_color. No-op on non-Windows
    or on Windows versions that don't support it."""
    if sys.platform != "win32":
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_CAPTION_COLOR = 35

        # Turn on dark-mode title bar (works on Win10 1809+ and Win11)
        dark_value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_value), ctypes.sizeof(dark_value)
        )

        # Set the exact caption color (Windows 11 build 22000+ only)
        hex_clean = hex_color.lstrip("#")
        r, g, b = (int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))
        colorref = r | (g << 8) | (b << 16)  # COLORREF is 0x00BBGGRR
        color_value = ctypes.c_int(colorref)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(color_value), ctypes.sizeof(color_value)
        )
    except Exception:
        pass  # Older Windows without this API - silently skip


class CountdownApp:
    def __init__(self, root):
        self.root = root
        self.root.title("")
        self.root.attributes("-topmost", True)
        if sys.platform == "win32":
            # Tool-window style keeps it out of the Alt+Tab list and the taskbar
            self.root.attributes("-toolwindow", True)
        self.root.minsize(80, 40)
        self.root.geometry("280x140+40+40")

        config = load_config() or {}
        self.event_name = tk.StringVar(value=config.get("name", DEFAULTS["name"]))
        self.target_dt = config.get("target")
        self.bg_color = config.get("bg_color", DEFAULTS["bg_color"])
        self.font_color = config.get("font_color", DEFAULTS["font_color"])
        self.font_family = config.get("font_family", DEFAULTS["font_family"])
        self.max_font_size = compute_max_font_size(self.root, self.font_family)
        self.font_size = clamp_font_size(
            config.get("font_size", DEFAULTS["font_size"]), self.max_font_size
        )

        self.root.configure(bg=self.bg_color)

        # --- Widgets ---
        self.name_label = tk.Label(
            root, textvariable=self.event_name, font=("Segoe UI", 13, "bold"),
            bg=self.bg_color, fg="#ffffff"
        )
        self.name_label.pack(pady=(12, 2))

        self.time_label = tk.Label(
            root, text="--:--:--:--",
            font=(self.font_family, self.font_size, "bold"),
            bg=self.bg_color, fg=self.font_color
        )
        self.time_label.pack(pady=(0, 8), expand=True, fill="both")

        self.controls_frame = tk.Frame(root, bg=self.bg_color)
        self.controls_frame.pack(pady=(0, 10))

        self.edit_button = tk.Button(
            self.controls_frame, text="Set Event", command=self.open_edit_dialog,
            bg="#2d2d2d", fg="white", relief="flat", padx=8, pady=2
        )
        self.edit_button.pack(side="left", padx=4)

        self.appearance_button = tk.Button(
            self.controls_frame, text="Appearance", command=self.open_appearance_dialog,
            bg="#2d2d2d", fg="white", relief="flat", padx=8, pady=2
        )
        self.appearance_button.pack(side="left", padx=4)

        self._auto_sync = False
        self.sync_button = tk.Button(
            self.controls_frame, text="Auto Sync", command=self.toggle_auto_sync,
            bg="#2d2d2d", fg="white", relief="flat", padx=8, pady=2
        )
        self.sync_button.pack(side="left", padx=4)

        # Recolor the title bar once the window actually exists
        self.root.after(50, lambda: set_title_bar_color(self.root, self.bg_color))

        # Watch for resizing to trigger compact mode
        self._is_compact = False
        self.root.bind("<Configure>", self.on_resize)

        if not self.target_dt:
            self.root.after(300, self.open_edit_dialog)

        self.update_countdown()

    # ---------- Compact mode ----------
    def on_resize(self, event):
        if event.widget != self.root:
            return
        w, h = self.root.winfo_width(), self.root.winfo_height()
        should_be_compact = w < COMPACT_WIDTH_THRESHOLD or h < COMPACT_HEIGHT_THRESHOLD

        if should_be_compact and not self._is_compact:
            self.name_label.pack_forget()
            self.controls_frame.pack_forget()
            self._is_compact = True
        elif not should_be_compact and self._is_compact:
            self.name_label.pack(pady=(12, 2), before=self.time_label)
            self.controls_frame.pack(pady=(0, 10))
            self._is_compact = False

        if self._auto_sync:
            self.sync_font_to_window()

    def toggle_auto_sync(self):
        self._auto_sync = not self._auto_sync
        self.sync_button.configure(
            text="Auto Sync ON" if self._auto_sync else "Auto Sync",
            bg="#3d6b3d" if self._auto_sync else "#2d2d2d",
        )
        if self._auto_sync:
            self.sync_font_to_window()
        else:
            self._save()

    def sync_font_to_window(self):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        max_w = max(1, int(w * 0.92))
        max_h = max(1, int(h * (0.85 if self._is_compact else 0.5)))
        size = compute_fit_font_size(
            self.root, self.font_family, max_w, max_h,
            floor=FONT_SIZE_AUTO_MIN, ceiling=self.max_font_size,
        )
        if size != self.font_size:
            self.font_size = size
            self.time_label.configure(font=(self.font_family, self.font_size, "bold"))

    # ---------- Set Event dialog ----------
    def open_edit_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Event")
        dialog.attributes("-topmost", True)
        dialog.geometry("300x220")
        dialog.resizable(False, False)

        tk.Label(dialog, text="Event name:").pack(pady=(10, 0))
        name_entry = tk.Entry(dialog, width=30)
        name_entry.insert(0, self.event_name.get())
        name_entry.pack()

        tk.Label(dialog, text="Date (YYYY-MM-DD):").pack(pady=(10, 0))
        date_entry = tk.Entry(dialog, width=30)
        if self.target_dt:
            date_entry.insert(0, self.target_dt.strftime("%Y-%m-%d"))
        date_entry.pack()

        tk.Label(dialog, text="Time (HH:MM, 24h):").pack(pady=(10, 0))
        time_entry = tk.Entry(dialog, width=30)
        time_entry.insert(0, self.target_dt.strftime("%H:%M") if self.target_dt else "09:00")
        time_entry.pack()

        def save_and_close():
            try:
                target = datetime.strptime(
                    f"{date_entry.get().strip()} {time_entry.get().strip()}",
                    "%Y-%m-%d %H:%M"
                )
            except ValueError:
                messagebox.showerror(
                    "Invalid input",
                    "Please enter date as YYYY-MM-DD and time as HH:MM (24-hour)."
                )
                return

            self.event_name.set(name_entry.get().strip() or "Your Event")
            self.target_dt = target
            self._save()
            dialog.destroy()

        tk.Button(dialog, text="Save", command=save_and_close).pack(pady=15)

    # ---------- Appearance dialog ----------
    def open_appearance_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Appearance")
        dialog.attributes("-topmost", True)
        dialog.geometry("300x300")
        dialog.resizable(False, False)

        # Font family
        tk.Label(dialog, text="Font:").pack(pady=(10, 0))
        font_var = tk.StringVar(value=self.font_family)
        font_menu = ttk.Combobox(dialog, textvariable=font_var, values=FONT_CHOICES, state="readonly")
        font_menu.pack()

        # Font size (capped so digits still fit when the window is maximized)
        tk.Label(dialog, text="Font size:").pack(pady=(10, 0))
        size_var = tk.IntVar(value=self.font_size)
        tk.Spinbox(
            dialog, from_=FONT_SIZE_MIN, to=self.max_font_size,
            textvariable=size_var, width=10
        ).pack()

        # Font color
        tk.Label(dialog, text="Digit color:").pack(pady=(10, 0))
        font_color_preview = tk.Label(dialog, text="       ", bg=self.font_color, relief="solid", bd=1)
        font_color_preview.pack()
        chosen_font_color = {"value": self.font_color}

        def pick_font_color():
            color = colorchooser.askcolor(color=chosen_font_color["value"], title="Choose digit color")
            if color[1]:
                chosen_font_color["value"] = color[1]
                font_color_preview.configure(bg=color[1])

        tk.Button(dialog, text="Choose color", command=pick_font_color).pack(pady=(2, 0))

        # Background color
        tk.Label(dialog, text="Background color:").pack(pady=(10, 0))
        bg_color_preview = tk.Label(dialog, text="       ", bg=self.bg_color, relief="solid", bd=1)
        bg_color_preview.pack()
        chosen_bg_color = {"value": self.bg_color}

        def pick_bg_color():
            color = colorchooser.askcolor(color=chosen_bg_color["value"], title="Choose background color")
            if color[1]:
                chosen_bg_color["value"] = color[1]
                bg_color_preview.configure(bg=color[1])

        tk.Button(dialog, text="Choose color", command=pick_bg_color).pack(pady=(2, 0))

        def save_and_close():
            if self._auto_sync:
                self.toggle_auto_sync()
            self.font_family = font_var.get()
            self.max_font_size = compute_max_font_size(self.root, self.font_family)
            self.font_size = clamp_font_size(size_var.get(), self.max_font_size)
            self.font_color = chosen_font_color["value"]
            self.bg_color = chosen_bg_color["value"]
            self.apply_appearance()
            self._save()
            dialog.destroy()

        tk.Button(dialog, text="Save", command=save_and_close).pack(pady=15)

    def apply_appearance(self):
        self.root.configure(bg=self.bg_color)
        self.name_label.configure(bg=self.bg_color)
        self.time_label.configure(bg=self.bg_color, fg=self.font_color, font=(self.font_family, self.font_size, "bold"))
        self.controls_frame.configure(bg=self.bg_color)
        set_title_bar_color(self.root, self.bg_color)

    def _save(self):
        save_config(
            self.event_name.get(), self.target_dt,
            self.bg_color, self.font_color, self.font_family, self.font_size
        )

    # ---------- Countdown loop ----------
    def update_countdown(self):
        if self.target_dt:
            remaining = self.target_dt - datetime.now()
            total_seconds = int(remaining.total_seconds())

            if total_seconds <= 0:
                self.time_label.config(text="TIME'S UP!")
            else:
                days, rem = divmod(total_seconds, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, seconds = divmod(rem, 60)
                self.time_label.config(text=f"{days}d {hours:02}:{minutes:02}:{seconds:02}")
        else:
            self.time_label.config(text="No event set")

        self.root.after(1000, self.update_countdown)


if __name__ == "__main__":
    root = tk.Tk()
    app = CountdownApp(root)
    root.mainloop()