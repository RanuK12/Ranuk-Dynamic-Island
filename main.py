"""
Ranuk Dynamic Island — Mini Oficina Pro (Pure Black OLED Edition)
Developed for Emilio Ranucoli / Ranuk IT Solutions (ranuk.dev)
"""
import sys
import os
import json
import threading
import time
import webbrowser
import subprocess
import ctypes
from datetime import datetime
from PIL import Image, ImageDraw
import customtkinter as ctk

from mac_bridge import MacBridge
from weather_bridge import get_weather
from github_bridge import GitHubBridge

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "mac": {"host": "192.168.1.34", "user": "emilioranucoli", "hub_url": "http://192.168.1.34:8788"},
            "weather": {"city": "James Craik, Córdoba", "latitude": -32.16145, "longitude": -63.4679},
            "github": {"username": "RanuK12"},
            "ui": {"collapsed_width": 320, "collapsed_height": 38, "expanded_width": 700, "expanded_height": 520}
        }

def get_rounded_image(path, size, radius=6):
    try:
        if not os.path.exists(path):
            return None
        im = Image.open(path).convert("RGBA")
        im = im.resize(size, Image.Resampling.LANCZOS)
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
        im.putalpha(mask)
        return ctk.CTkImage(light_image=im, dark_image=im, size=size)
    except Exception:
        return None

def apply_taskbar_hide(hwnd):
    """Hides the window from Windows Taskbar and Alt+Tab cleanly without creating backdrop artifacts."""
    try:
        top_hwnd = ctypes.windll.user32.GetParent(hwnd) or hwnd
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        style = ctypes.windll.user32.GetWindowLongW(top_hwnd, GWL_EXSTYLE)
        style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(top_hwnd, GWL_EXSTYLE, style)
        
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        ctypes.windll.user32.SetWindowPos(top_hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass

class DynamicIsland(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.mac_bridge = MacBridge(
            host=self.config.get("mac", {}).get("host", "192.168.1.34"),
            user=self.config.get("mac", {}).get("user", "emilioranucoli"),
            hub_url=self.config.get("mac", {}).get("hub_url", "http://192.168.1.34:8788")
        )
        self.gh_bridge = GitHubBridge(
            username=self.config.get("github", {}).get("username", "RanuK12"),
            token=self.config.get("github", {}).get("token", "")
        )

        # Dimensions
        self.collapsed_w = self.config["ui"].get("collapsed_width", 320)
        self.collapsed_h = self.config["ui"].get("collapsed_height", 38)
        self.expanded_w = self.config["ui"].get("expanded_width", 700)
        self.expanded_h = self.config["ui"].get("expanded_height", 520)

        self.is_expanded = False

        # States
        self.mac_data = {"connected": False, "bot_running": False, "services": [], "slack_messages": [], "crons": [], "hub": {}}
        self.weather_data = {"temp": "--", "icon": "⛅", "desc": "Cargando...", "forecast": []}
        self.github_data = {"repos": []}
        self.pomodoro_seconds = 25 * 60
        self.pomodoro_running = False

        # Window styling: Frameless, Topmost, transparent margin (No alpha to avoid gray border!)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#000001")
        self.wm_attributes("-transparentcolor", "#000001")

        try:
            ico_file = os.path.join(ASSETS_DIR, "icon.ico")
            if os.path.exists(ico_file):
                self.iconbitmap(ico_file)
        except Exception:
            pass

        self.screen_w = self.winfo_screenwidth()
        self.update_geometry(self.collapsed_w, self.collapsed_h)

        # Assets
        logo_path = os.path.join(ASSETS_DIR, "logo.png")
        banner_path = os.path.join(ASSETS_DIR, "banner.jpeg")
        self.img_logo_pill = get_rounded_image(logo_path, (20, 20), radius=5)
        self.img_banner = get_rounded_image(banner_path, (640, 115), radius=10)

        # Dragging states
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._win_x = 0
        self._win_y = 0

        self.setup_ui()
        self.start_background_sync()
        self.start_clock_timer()

        # Hide from taskbar and bring front
        self.after(20, lambda: apply_taskbar_hide(self.winfo_id()))
        self.after(50, self.lift)
        self.focus_force()

    def update_geometry(self, w, h):
        x = (self.screen_w - w) // 2
        y = 6
        self.geometry(f"{w}x{h}+{x}+{y}")

    def setup_ui(self):
        # Master Island Frame — Pure OLED Black, NO gray border, seamless edges
        self.island_frame = ctk.CTkFrame(
            self,
            fg_color="#000000",
            border_width=0,
            corner_radius=19
        )
        self.island_frame.pack(fill="both", expand=True)

        # --- PILL BAR ---
        self.pill_bar = ctk.CTkFrame(self.island_frame, fg_color="transparent", height=38)
        self.pill_bar.pack(fill="x", padx=12, pady=0)
        
        self.pill_bar.bind("<ButtonPress-1>", self.start_drag)
        self.pill_bar.bind("<B1-Motion>", self.do_drag)
        self.pill_bar.bind("<ButtonRelease-1>", self.end_drag)

        # Left Group
        left_grp = ctk.CTkFrame(self.pill_bar, fg_color="transparent")
        left_grp.pack(side="left")
        left_grp.bind("<ButtonPress-1>", self.start_drag)
        left_grp.bind("<B1-Motion>", self.do_drag)
        left_grp.bind("<ButtonRelease-1>", self.end_drag)

        if self.img_logo_pill:
            self.lbl_pill_logo = ctk.CTkLabel(left_grp, image=self.img_logo_pill, text="")
            self.lbl_pill_logo.pack(side="left", padx=(0, 6))
            self.lbl_pill_logo.bind("<ButtonPress-1>", self.start_drag)
            self.lbl_pill_logo.bind("<B1-Motion>", self.do_drag)
            self.lbl_pill_logo.bind("<ButtonRelease-1>", self.end_drag)

        self.dot_label = ctk.CTkLabel(
            left_grp,
            text="●",
            text_color="#00e676",
            font=("Segoe UI", 15, "bold"),
            width=14
        )
        self.dot_label.pack(side="left", padx=(0, 6))
        self.dot_label.bind("<ButtonPress-1>", self.start_drag)
        self.dot_label.bind("<B1-Motion>", self.do_drag)
        self.dot_label.bind("<ButtonRelease-1>", self.end_drag)

        self.pill_title = ctk.CTkLabel(
            left_grp,
            text="Ranuk Hub",
            text_color="#ffffff",
            font=("Segoe UI Variable Display", 12, "bold")
        )
        self.pill_title.pack(side="left")
        self.pill_title.bind("<ButtonPress-1>", self.start_drag)
        self.pill_title.bind("<B1-Motion>", self.do_drag)
        self.pill_title.bind("<ButtonRelease-1>", self.end_drag)

        self.pill_badge = ctk.CTkLabel(
            left_grp,
            text="11 svcs",
            font=("Segoe UI", 10, "bold"),
            text_color="#58a6ff",
            fg_color="#121824",
            corner_radius=4,
            padx=6,
            pady=1
        )
        self.pill_badge.pack(side="left", padx=(6, 0))
        self.pill_badge.bind("<ButtonPress-1>", self.start_drag)
        self.pill_badge.bind("<B1-Motion>", self.do_drag)
        self.pill_badge.bind("<ButtonRelease-1>", self.end_drag)

        # Right Group (Always visible, clean, never overflowing)
        right_grp = ctk.CTkFrame(self.pill_bar, fg_color="transparent")
        right_grp.pack(side="right")
        right_grp.bind("<ButtonPress-1>", self.start_drag)
        right_grp.bind("<B1-Motion>", self.do_drag)
        right_grp.bind("<ButtonRelease-1>", self.end_drag)

        self.pill_clock = ctk.CTkLabel(
            right_grp,
            text=datetime.now().strftime("%H:%M"),
            text_color="#8b949e",
            font=("Segoe UI Variable Display", 12, "bold")
        )
        self.pill_clock.pack(side="right", padx=(6, 0))
        self.pill_clock.bind("<ButtonPress-1>", self.start_drag)
        self.pill_clock.bind("<B1-Motion>", self.do_drag)
        self.pill_clock.bind("<ButtonRelease-1>", self.end_drag)

        self.pill_weather = ctk.CTkLabel(
            right_grp,
            text="⛅ 19°",
            text_color="#ffffff",
            font=("Segoe UI", 12, "bold")
        )
        self.pill_weather.pack(side="right", padx=(0, 6))
        self.pill_weather.bind("<ButtonPress-1>", self.start_drag)
        self.pill_weather.bind("<B1-Motion>", self.do_drag)
        self.pill_weather.bind("<ButtonRelease-1>", self.end_drag)

        # --- EXPANDED DASHBOARD CONTAINER ---
        self.dashboard_frame = ctk.CTkFrame(self.island_frame, fg_color="transparent")

        # Tab Selector Bar + Close button
        self.nav_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=6, pady=(0, 8))

        self.tab_buttons = {}
        tabs = [
            ("slack", "💬 Slack Agentes"),
            ("hub", "🤖 Hub & Mac"),
            ("agenda", "⏰ Crons del Día"),
            ("github", "🐙 GitHub"),
            ("weather", "🌤️ Clima"),
            ("focus", "⏱️ Focus")
        ]

        for key, label in tabs:
            btn = ctk.CTkButton(
                self.nav_frame,
                text=label,
                font=("Segoe UI Variable Display", 11, "bold"),
                fg_color="#121824" if key != "slack" else "#1f6feb",
                hover_color="#1d2638",
                text_color="#f0f6fc",
                height=28,
                corner_radius=8,
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(side="left", expand=True, fill="x", padx=2)
            self.tab_buttons[key] = btn

        btn_close = ctk.CTkButton(
            self.nav_frame,
            text="✕",
            font=("Segoe UI", 11, "bold"),
            fg_color="#2b1414",
            hover_color="#541b1b",
            text_color="#ff7b72",
            width=28,
            height=28,
            corner_radius=8,
            command=self.toggle_expand
        )
        btn_close.pack(side="right", padx=(4, 0))

        # Content Card Holder (Dark Glass)
        self.content_holder = ctk.CTkFrame(
            self.dashboard_frame,
            fg_color="#0d111a",
            corner_radius=14,
            border_color="#1a2332",
            border_width=1
        )
        self.content_holder.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Build individual tab views
        self.tab_views = {
            "slack": self.build_slack_view(),
            "hub": self.build_hub_view(),
            "agenda": self.build_agenda_view(),
            "github": self.build_github_view(),
            "weather": self.build_weather_view(),
            "focus": self.build_focus_view()
        }
        self.current_tab = "slack"
        self.tab_views["slack"].pack(fill="both", expand=True, padx=12, pady=12)

    # --- DRAG & CLICK LOGIC ---
    def start_drag(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_x = self.winfo_x()
        self._win_y = self.winfo_y()
        self._is_dragging = False

    def do_drag(self, event):
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        if abs(dx) > 4 or abs(dy) > 4:
            self._is_dragging = True
            self.geometry(f"+{self._win_x + dx}+{self._win_y + dy}")

    def end_drag(self, event):
        if not self._is_dragging:
            self.toggle_expand()
        self._is_dragging = False

    # --- FAST SNAPPY EXPAND / COLLAPSE (Zero Lag) ---
    def toggle_expand(self):
        curr_x = self.winfo_x()
        curr_y = self.winfo_y()

        if not self.is_expanded:
            # Expand Snappily
            self.geometry(f"{self.expanded_w}x{self.expanded_h}+{curr_x}+{curr_y}")
            self.dashboard_frame.pack(fill="both", expand=True, padx=6, pady=(4, 6))
            self.is_expanded = True
        else:
            # Collapse Snappily
            self.dashboard_frame.pack_forget()
            self.geometry(f"{self.collapsed_w}x{self.collapsed_h}+{curr_x}+{curr_y}")
            self.is_expanded = False

    # --- TAB BUILDERS ---
    def build_slack_view(self):
        f = ctk.CTkFrame(self.content_holder, fg_color="transparent")

        top_row = ctk.CTkFrame(f, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 6))

        lbl_head = ctk.CTkLabel(top_row, text="💬 Canal de Empleados Agentes (Slack Feed)", font=("Segoe UI Variable Display", 13, "bold"), text_color="#58a6ff")
        lbl_head.pack(side="left")

        self.lbl_slack_count = ctk.CTkLabel(top_row, text="Sincronizando...", font=("Segoe UI", 11), text_color="#8b949e")
        self.lbl_slack_count.pack(side="right")

        self.slack_scroll = ctk.CTkScrollableFrame(f, fg_color="#070a0f", corner_radius=10, height=310)
        self.slack_scroll.pack(fill="both", expand=True, pady=(0, 8))

        # Input Row to send directives
        input_row = ctk.CTkFrame(f, fg_color="transparent")
        input_row.pack(fill="x")

        self.entry_slack = ctk.CTkEntry(
            input_row,
            placeholder_text="Enviar directiva o mensaje al equipo como CEO (Emilio)...",
            font=("Segoe UI", 11),
            fg_color="#121824",
            border_color="#1f2c40",
            height=32
        )
        self.entry_slack.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_slack.bind("<Return>", lambda e: self.send_agent_directive())

        btn_send = ctk.CTkButton(
            input_row,
            text="Enviar 👑",
            font=("Segoe UI Variable Display", 11, "bold"),
            fg_color="#1f6feb",
            hover_color="#388bfd",
            width=90,
            height=32,
            corner_radius=8,
            command=self.send_agent_directive
        )
        btn_send.pack(side="right")

        return f

    def build_hub_view(self):
        f = ctk.CTkFrame(self.content_holder, fg_color="transparent")

        # Top Banner Image
        if self.img_banner:
            self.lbl_banner = ctk.CTkLabel(f, image=self.img_banner, text="")
            self.lbl_banner.pack(fill="x", pady=(0, 8))

        # Header Row
        hr = ctk.CTkFrame(f, fg_color="transparent")
        hr.pack(fill="x", pady=(0, 6))
        
        lbl_host = ctk.CTkLabel(hr, text="🏢 Ranuk Hub — MacBook Pro (192.168.1.34)", font=("Segoe UI Variable Display", 13, "bold"), text_color="#58a6ff")
        lbl_host.pack(side="left")

        btn_open_hub = ctk.CTkButton(
            hr,
            text="Abrir Hub Web ↗",
            font=("Segoe UI Variable Display", 11, "bold"),
            fg_color="#238636",
            hover_color="#2ea043",
            width=115,
            height=26,
            corner_radius=6,
            command=lambda: webbrowser.open(self.config.get("mac", {}).get("hub_url", "http://192.168.1.34:8788/"))
        )
        btn_open_hub.pack(side="right")

        # Telemetry Card
        card = ctk.CTkFrame(f, fg_color="#121824", corner_radius=10, border_color="#1d283a", border_width=1)
        card.pack(fill="x", pady=(0, 8))

        cl = ctk.CTkFrame(card, fg_color="transparent")
        cl.pack(fill="x", padx=10, pady=8)

        self.lbl_hub_telemetry = ctk.CTkLabel(
            cl,
            text="Empresa: Ranuk IT Solutions | CEO: Emilio Ranucoli\nBatería Mac: 100% | Uptime: Calculando...",
            font=("Segoe UI", 11),
            text_color="#e6edf3",
            justify="left"
        )
        self.lbl_hub_telemetry.pack(anchor="w")

        # Microservices List
        lbl_svcs_head = ctk.CTkLabel(f, text="🤖 Microservicios Activos en Mac:", font=("Segoe UI Variable Display", 12, "bold"), text_color="#e6edf3", anchor="w")
        lbl_svcs_head.pack(fill="x", pady=(2, 2))

        self.lbl_svcs_list = ctk.CTkLabel(
            f,
            text="• rk-agent-loop.py\n• rk-scan-server.py\n• rk-ollama-loop.py\n• rk-mini-watch-loop.py\n• rk_bridge.py",
            font=("Segoe UI", 11),
            text_color="#3fb950",
            justify="left",
            anchor="w"
        )
        self.lbl_svcs_list.pack(fill="x")

        # Bottom SSH trigger
        bottom_row = ctk.CTkFrame(f, fg_color="transparent")
        bottom_row.pack(fill="x", pady=(6, 0))

        btn_ssh = ctk.CTkButton(
            bottom_row,
            text="💻 Consola SSH al Mac",
            font=("Segoe UI Variable Display", 11, "bold"),
            fg_color="#1f2c40",
            hover_color="#2d3f5c",
            height=28,
            corner_radius=6,
            command=self.open_mac_ssh
        )
        btn_ssh.pack(side="left")

        return f

    def build_agenda_view(self):
        f = ctk.CTkFrame(self.content_holder, fg_color="transparent")

        top_row = ctk.CTkFrame(f, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 6))

        lbl_head = ctk.CTkLabel(top_row, text="⏰ Crons y Tareas Diarias de Mac (48 Programados)", font=("Segoe UI Variable Display", 13, "bold"), text_color="#58a6ff")
        lbl_head.pack(side="left")

        self.lbl_crons_summary = ctk.CTkLabel(top_row, text="Cargando crons...", font=("Segoe UI", 11), text_color="#8b949e")
        self.lbl_crons_summary.pack(side="right")

        self.crons_scroll = ctk.CTkScrollableFrame(f, fg_color="#070a0f", corner_radius=10, height=350)
        self.crons_scroll.pack(fill="both", expand=True)

        return f

    def build_github_view(self):
        f = ctk.CTkFrame(self.content_holder, fg_color="transparent")

        top_row = ctk.CTkFrame(f, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 6))

        lbl_head = ctk.CTkLabel(top_row, text="🐙 GitHub — RanuK12 (158 repositorios)", font=("Segoe UI Variable Display", 13, "bold"), text_color="#58a6ff")
        lbl_head.pack(side="left")

        btn_web = ctk.CTkButton(
            top_row,
            text="Ver Perfil ↗",
            font=("Segoe UI Variable Display", 11, "bold"),
            fg_color="#238636",
            hover_color="#2ea043",
            width=95,
            height=24,
            corner_radius=6,
            command=lambda: webbrowser.open("https://github.com/RanuK12")
        )
        btn_web.pack(side="right")

        self.lbl_gh_bio = ctk.CTkLabel(
            f,
            text="Systems & ML Engineer | Python/Web | Ranuk IT",
            font=("Segoe UI", 11, "italic"),
            text_color="#8b949e",
            anchor="w"
        )
        self.lbl_gh_bio.pack(fill="x", pady=(0, 8))

        self.gh_repos_box = ctk.CTkScrollableFrame(f, fg_color="#070a0f", corner_radius=10, height=310)
        self.gh_repos_box.pack(fill="both", expand=True)

        return f

    def build_weather_view(self):
        f = ctk.CTkFrame(self.content_holder, fg_color="transparent")
        
        # Location header — Shows exact location
        loc_row = ctk.CTkFrame(f, fg_color="transparent")
        loc_row.pack(fill="x", pady=(0, 6))

        self.lbl_w_city = ctk.CTkLabel(loc_row, text="📍 James Craik, Córdoba", font=("Segoe UI Variable Display", 13, "bold"), text_color="#ffd166")
        self.lbl_w_city.pack(side="left")

        # Current weather card
        curr_card = ctk.CTkFrame(f, fg_color="#121824", corner_radius=12, border_color="#1d283a", border_width=1)
        curr_card.pack(fill="x", pady=(0, 10))

        c_layout = ctk.CTkFrame(curr_card, fg_color="transparent")
        c_layout.pack(fill="x", padx=16, pady=12)

        left_c = ctk.CTkFrame(c_layout, fg_color="transparent")
        left_c.pack(side="left")

        self.lbl_w_big = ctk.CTkLabel(left_c, text="⛅ 19°C", font=("Segoe UI Variable Display", 36, "bold"), text_color="#ffd166")
        self.lbl_w_big.pack(anchor="w")

        self.lbl_w_desc = ctk.CTkLabel(left_c, text="Mayormente despejado", font=("Segoe UI Variable Display", 13, "bold"), text_color="#f0f6fc")
        self.lbl_w_desc.pack(anchor="w")

        right_c = ctk.CTkFrame(c_layout, fg_color="transparent")
        right_c.pack(side="right")

        self.lbl_w_detail = ctk.CTkLabel(
            right_c,
            text="Sensación: 19° | Humedad: 48%\nViento: 15 km/h | Índice UV: 7",
            font=("Segoe UI", 11),
            text_color="#8b949e",
            justify="right"
        )
        self.lbl_w_detail.pack(anchor="e")

        # 5-Day Forecast Header
        lbl_fc_head = ctk.CTkLabel(f, text="📅 Pronóstico para los Próximos 5 Días:", font=("Segoe UI Variable Display", 12, "bold"), text_color="#e6edf3", anchor="w")
        lbl_fc_head.pack(fill="x", pady=(4, 6))

        # Uniform 5-Card Container (NO scrollbar, perfectly symmetrical and aligned)
        self.forecast_grid = ctk.CTkFrame(f, fg_color="transparent")
        self.forecast_grid.pack(fill="x", expand=False)
        for col_idx in range(5):
            self.forecast_grid.columnconfigure(col_idx, weight=1, uniform="forecast_col")

        return f

    def build_focus_view(self):
        f = ctk.CTkFrame(self.content_holder, fg_color="transparent")

        self.lbl_pomo = ctk.CTkLabel(f, text="25:00", font=("Segoe UI Variable Display", 48, "bold"), text_color="#00d2ff")
        self.lbl_pomo.pack(pady=(24, 16))

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack()

        self.btn_pomo_action = ctk.CTkButton(
            btn_row,
            text="▶ Iniciar Focus",
            font=("Segoe UI Variable Display", 12, "bold"),
            fg_color="#238636",
            hover_color="#2ea043",
            width=140,
            height=34,
            corner_radius=8,
            command=self.toggle_pomodoro
        )
        self.btn_pomo_action.pack(side="left", padx=6)

        btn_reset = ctk.CTkButton(
            btn_row,
            text="↺ Reiniciar",
            font=("Segoe UI Variable Display", 12, "bold"),
            fg_color="#21262d",
            hover_color="#30363d",
            width=90,
            height=34,
            corner_radius=8,
            command=self.reset_pomodoro
        )
        btn_reset.pack(side="left", padx=6)

        return f

    # --- TAB NAVIGATION ---
    def switch_tab(self, key):
        if key == self.current_tab:
            return
        self.tab_views[self.current_tab].pack_forget()
        self.tab_buttons[self.current_tab].configure(fg_color="#121824")
        
        self.tab_views[key].pack(fill="both", expand=True, padx=12, pady=12)
        self.tab_buttons[key].configure(fg_color="#1f6feb")
        self.current_tab = key

    # --- BACKGROUND SYNC ---
    def start_background_sync(self):
        def worker():
            tick = 0
            while True:
                # 1. Full Mac state (Services, Hub, Slack, Crons) every 8s
                mac = self.mac_bridge.fetch_full_status()
                self.after(0, lambda m=mac: self.apply_mac_update(m))

                # 2. Weather (Auto-detects location wherever you are)
                if tick % 90 == 0:
                    w = get_weather(
                        city_name=self.config.get("weather", {}).get("city", "Auto")
                    )
                    self.after(0, lambda weather=w: self.apply_weather_update(weather))

                # 3. GitHub every 5 mins (30 ticks)
                if tick % 30 == 0:
                    gh = self.gh_bridge.fetch_summary()
                    self.after(0, lambda g=gh: self.apply_github_update(g))

                tick += 1
                time.sleep(8)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def start_clock_timer(self):
        def tick():
            self.pill_clock.configure(text=datetime.now().strftime("%H:%M"))
            if self.pomodoro_running:
                if self.pomodoro_seconds > 0:
                    self.pomodoro_seconds -= 1
                    m = self.pomodoro_seconds // 60
                    s = self.pomodoro_seconds % 60
                    self.lbl_pomo.configure(text=f"{m:02d}:{s:02d}")
                else:
                    self.pomodoro_running = False
                    self.lbl_pomo.configure(text="¡Completado!")
                    self.btn_pomo_action.configure(text="▶ Iniciar Focus")
            self.after(1000, tick)

        self.after(1000, tick)

    # --- UI UPDATE CALLBACKS ---
    def apply_mac_update(self, data):
        self.mac_data = data
        if data.get("connected"):
            self.dot_label.configure(text_color="#00e676")
            
            # Hub Telemetry
            hub = data.get("hub", {})
            empresa = hub.get("empresa", "Ranuk IT Solutions")
            ceo = hub.get("ceo", "Emilio Ranucoli")
            batt = data.get("battery", "--")
            uptime = data.get("uptime", "--")
            self.lbl_hub_telemetry.configure(
                text=f"🏢 {empresa} | CEO: {ceo}\n🔋 Batería Mac: {batt} | ⏱️ Uptime: {uptime}"
            )

            # Services
            services = data.get("services", [])
            svc_count = len(services)
            self.pill_badge.configure(text=f"{svc_count} svcs" if svc_count > 0 else "activo")
            if services:
                self.lbl_svcs_list.configure(text="\n".join([f"🟢 {s}" for s in services[:8]]))
            else:
                self.lbl_svcs_list.configure(text="• Sin microservicios detectados")

            # Slack Messages
            slack_msgs = data.get("slack_messages", [])
            self.lbl_slack_count.configure(text=f"{len(slack_msgs)} directivas recientes")
            self.render_slack_messages(slack_msgs)

            # Crons & Agenda
            crons = data.get("crons", [])
            self.render_crons_agenda(crons)

        else:
            self.dot_label.configure(text_color="#f85149")
            self.pill_badge.configure(text="offline")

    def render_slack_messages(self, messages):
        for child in self.slack_scroll.winfo_children():
            child.destroy()

        if not messages:
            lbl_empty = ctk.CTkLabel(self.slack_scroll, text="No hay mensajes recientes en el canal de agentes.", text_color="#8b949e", font=("Segoe UI", 11))
            lbl_empty.pack(pady=10)
            return

        for m in messages:
            row = ctk.CTkFrame(self.slack_scroll, fg_color="#101520", corner_radius=8, border_color="#1a2332", border_width=1)
            row.pack(fill="x", pady=3, padx=2)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(6, 2))

            sender_txt = f"{m.get('icon', '🤖')} {m.get('sender', 'agente')} ➔ {m.get('dest', 'equipo')}"
            lbl_sender = ctk.CTkLabel(top, text=sender_txt, font=("Segoe UI Variable Display", 11, "bold"), text_color="#58a6ff")
            lbl_sender.pack(side="left")

            lbl_time = ctk.CTkLabel(top, text=m.get("time", ""), font=("Segoe UI", 10), text_color="#8b949e")
            lbl_time.pack(side="right")

            lbl_msg = ctk.CTkLabel(row, text=m.get("text", ""), font=("Segoe UI", 11), text_color="#f0f6fc", justify="left", wraplength=600)
            lbl_msg.pack(fill="x", padx=10, pady=(0, 8), anchor="w")

    def render_crons_agenda(self, crons):
        for child in self.crons_scroll.winfo_children():
            child.destroy()

        if not crons:
            lbl_empty = ctk.CTkLabel(self.crons_scroll, text="Cargando crons de LaunchAgents...", text_color="#8b949e", font=("Segoe UI", 11))
            lbl_empty.pack(pady=10)
            return

        done_count = sum(1 for c in crons if c.get("done"))
        pending_count = len(crons) - done_count
        self.lbl_crons_summary.configure(text=f"{done_count} ejecutados | {pending_count} pendientes hoy")

        # Find next pending
        next_cron = None
        for c in crons:
            if not c.get("done"):
                next_cron = c
                break

        for c in crons:
            row = ctk.CTkFrame(self.crons_scroll, fg_color="#101520" if c != next_cron else "#16281e", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            is_done = c.get("done")
            status_txt = "✔" if is_done else ("⭐ PRÓXIMO" if c == next_cron else "⏳")
            t_color = "#3fb950" if is_done else ("#ffd166" if c == next_cron else "#58a6ff")

            lbl_stat = ctk.CTkLabel(row, text=f"{c.get('time')}  [{status_txt}]", font=("Segoe UI", 11, "bold"), text_color=t_color, width=110, anchor="w")
            lbl_stat.pack(side="left", padx=(8, 4), pady=4)

            name_color = "#8b949e" if is_done else "#f0f6fc"
            lbl_name = ctk.CTkLabel(row, text=c.get("title", ""), font=("Segoe UI", 11), text_color=name_color, anchor="w")
            lbl_name.pack(side="left", fill="x", expand=True)

    def send_agent_directive(self):
        text = self.entry_slack.get().strip()
        if not text:
            return
        self.entry_slack.delete(0, "end")
        threading.Thread(target=lambda: self.mac_bridge.send_slack_message(text, sender="emilio"), daemon=True).start()

    def apply_github_update(self, data):
        self.github_data = data
        for child in self.gh_repos_box.winfo_children():
            child.destroy()

        repos = data.get("repos", [])
        if repos:
            for r in repos:
                card = ctk.CTkFrame(self.gh_repos_box, fg_color="#101520", corner_radius=8, border_color="#1a2332", border_width=1)
                card.pack(fill="x", pady=3, padx=2)

                top = ctk.CTkFrame(card, fg_color="transparent")
                top.pack(fill="x", padx=10, pady=4)

                lbl_n = ctk.CTkLabel(top, text=f"📦 {r['name']}", font=("Segoe UI Variable Display", 12, "bold"), text_color="#58a6ff")
                lbl_n.pack(side="left")

                lbl_l = ctk.CTkLabel(top, text=f"{r['language']} · ⭐ {r['stars']}", font=("Segoe UI", 10), text_color="#8b949e")
                lbl_l.pack(side="right")

                btn_visit = ctk.CTkButton(
                    card,
                    text="Abrir Repositorio ↗",
                    font=("Segoe UI Variable Display", 10, "bold"),
                    fg_color="#1a2332",
                    hover_color="#253247",
                    height=22,
                    corner_radius=4,
                    command=lambda u=r.get("url", "https://github.com/RanuK12"): webbrowser.open(u)
                )
                btn_visit.pack(anchor="e", padx=10, pady=(0, 4))
        else:
            lbl = ctk.CTkLabel(self.gh_repos_box, text="No se pudieron cargar repositorios.", text_color="#8b949e")
            lbl.pack(pady=10)

    def apply_weather_update(self, data):
        self.weather_data = data
        city = data.get("city", "James Craik, Córdoba")
        self.lbl_w_city.configure(text=f"📍 {city}")

        icon = data.get("icon", "⛅")
        temp = data.get("temp", "--")
        desc = data.get("desc", "")
        self.pill_weather.configure(text=f"{icon} {temp}°")
        self.lbl_w_big.configure(text=f"{icon} {temp}°C")
        self.lbl_w_desc.configure(text=desc)
        self.lbl_w_detail.configure(
            text=f"Sensación: {data.get('feels_like', '--')}° | Humedad: {data.get('humidity', '--')}%\n"
                 f"Viento: {data.get('wind', '--')} km/h | Índice UV: {data.get('uv', '--')}"
        )

        # Clear and build perfectly uniform 5-column forecast cards
        for child in self.forecast_grid.winfo_children():
            child.destroy()

        for idx, day in enumerate(data.get("forecast", [])[:5]):
            card = ctk.CTkFrame(
                self.forecast_grid,
                fg_color="#101520",
                corner_radius=10,
                border_color="#1a2332",
                border_width=1,
                height=130
            )
            card.grid(row=0, column=idx, padx=4, sticky="nsew")

            # Day label (Fixed height for uniform vertical layout)
            lbl_day = ctk.CTkLabel(
                card,
                text=day.get("day", ""),
                font=("Segoe UI Variable Display", 11, "bold"),
                text_color="#58a6ff",
                height=22
            )
            lbl_day.pack(fill="x", pady=(8, 2))

            # Icon label (Fixed height = 36 to ensure equal vertical level)
            lbl_ico = ctk.CTkLabel(
                card,
                text=day.get("icon", "⛅"),
                font=("Segoe UI", 24),
                height=36
            )
            lbl_ico.pack(fill="x", pady=2)

            # Temp label (Fixed height)
            lbl_temps = ctk.CTkLabel(
                card,
                text=f"{day.get('max')}° / {day.get('min')}°",
                font=("Segoe UI", 11, "bold"),
                text_color="#f0f6fc",
                height=20
            )
            lbl_temps.pack(fill="x", pady=(0, 4))

            # Rain badge (Fixed height)
            rain_p = day.get("rain_prob", 0)
            rain_bg = "#162334" if rain_p > 20 else "#0f1622"
            rain_col = "#58a6ff" if rain_p > 20 else "#8b949e"
            
            lbl_rain = ctk.CTkLabel(
                card,
                text=f"💧 {rain_p}%",
                font=("Segoe UI", 10, "bold"),
                text_color=rain_col,
                fg_color=rain_bg,
                corner_radius=6,
                height=20,
                padx=6
            )
            lbl_rain.pack(pady=(0, 8))

    # --- FOCUS ACTIONS ---
    def toggle_pomodoro(self):
        self.pomodoro_running = not self.pomodoro_running
        self.btn_pomo_action.configure(
            text="⏸ Pausar" if self.pomodoro_running else "▶ Reanudar Focus",
            fg_color="#d29922" if self.pomodoro_running else "#238636"
        )

    def reset_pomodoro(self):
        self.pomodoro_running = False
        self.pomodoro_seconds = 25 * 60
        self.lbl_pomo.configure(text="25:00")
        self.btn_pomo_action.configure(text="▶ Iniciar Focus", fg_color="#238636")

    # --- MAC SSH TERMINAL ---
    def open_mac_ssh(self):
        user = self.config.get("mac", {}).get("user", "emilioranucoli")
        host = self.config.get("mac", {}).get("host", "192.168.1.34")
        subprocess.Popen(["powershell", "-NoExit", "-Command", f"ssh {user}@{host}"])


if __name__ == "__main__":
    app = DynamicIsland()
    app.mainloop()
