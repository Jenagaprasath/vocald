"""
Vocald — Android APK
Main Kivy application entry point.
Screens: Onboarding → Logs → Details → Profiles → Settings
Fixed UI — no text overlap, clean card layout, dynamic heights.
"""

import os
import sys
import threading
from datetime import datetime

# ─── Kivy config (must be before any kivy imports) ───────────────────────────
os.environ['KIVY_NO_ENV_CONFIG'] = '1'
from kivy.config import Config
Config.set('graphics', 'resizable', '1')

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock, mainthread
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.storage.jsonstore import JsonStore
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.core.window import Window

# Conditional Android imports
if platform == 'android':
    from android.permissions import request_permissions, Permission, check_permission
    from android import mActivity, activity
    from jnius import autoclass


# ─── Responsive helpers ───────────────────────────────────────────────────────
def sw(pct):
    return Window.width * pct / 100

def sh(pct):
    return Window.height * pct / 100

def rsp(size):
    """Responsive font size. Clamps between 0.85x and 1.3x."""
    scale = max(0.85, min(1.3, Window.width / 400))
    return sp(size * scale)

def rdp(size):
    """Responsive dp. Clamps between 0.85x and 1.25x."""
    scale = max(0.85, min(1.25, Window.width / 400))
    return dp(size * scale)


# ─── Colour palette ──────────────────────────────────────────────────────────
BRAND        = (0.216, 0.196, 0.553, 1)
BRAND_DARK   = (0.149, 0.137, 0.420, 1)
BRAND_LIGHT  = (0.580, 0.561, 0.902, 1)
ACCENT       = (0.055, 0.698, 0.506, 1)
WARN         = (0.953, 0.612, 0.071, 1)
DANGER       = (0.918, 0.263, 0.263, 1)
BG           = (0.953, 0.957, 0.976, 1)
WHITE        = (1, 1, 1, 1)
MUTED        = (0.435, 0.459, 0.514, 1)
BLACK        = (0.110, 0.145, 0.208, 1)
CARD_BG      = (1, 1, 1, 1)
DIVIDER      = (0.906, 0.910, 0.925, 1)

BRAND_HEX      = '#3732A3'
BRAND_DARK_HEX = '#261F6B'
ACCENT_HEX     = '#0EB281'
WARN_HEX       = '#F39C12'
DANGER_HEX     = '#EA4343'
WHITE_HEX      = '#FFFFFF'
MUTED_HEX      = '#6F75A3'
BLACK_HEX      = '#1C2535'
BG_HEX         = '#F3F4F9'


# ─── Helper: hex colour ───────────────────────────────────────────────────────
def _hex(h):
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255, g / 255, b / 255, 1


# ─── Background rect helper ───────────────────────────────────────────────────
def bg_rect(widget, color=BG):
    with widget.canvas.before:
        Color(*color)
        widget._bg = Rectangle()
    widget.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                size=lambda i, v: setattr(i._bg, 'size', v))


# ─── Label factory ────────────────────────────────────────────────────────────
def make_label(text, size=14, color=BLACK_HEX, bold=False, halign='left',
               italic=False, markup=False, wrap=True):
    """
    Creates a label that auto-sizes its height to fit text.
    wrap=True  → text_size follows width (word-wrap, dynamic height)
    wrap=False → single line, no wrapping
    """
    lbl = Label(
        text=text,
        font_size=rsp(size),
        color=color if isinstance(color, tuple) else _hex(color),
        bold=bold,
        italic=italic,
        halign=halign,
        valign='top',
        markup=markup,
        size_hint_y=None,
        shorten=False,
    )
    if wrap:
        lbl.bind(width=lambda i, w: setattr(i, 'text_size', (w, None)))
        lbl.bind(texture_size=lambda i, ts: setattr(i, 'height', ts[1]))
    else:
        lbl.text_size = (None, None)
        lbl.height = rsp(size) * 1.6
    return lbl


# ─── Button factory ───────────────────────────────────────────────────────────
def make_button(text, bg_color=BRAND, text_color=WHITE_HEX,
                height=None, on_press=None, font_size=14, bold=True, radius=None):
    h = height if height is not None else rdp(48)
    r = radius if radius is not None else rdp(10)
    btn = Button(
        text=text,
        size_hint=(1, None),
        height=h,
        font_size=rsp(font_size),
        bold=bold,
        background_color=(0, 0, 0, 0),
        color=text_color if isinstance(text_color, tuple) else _hex(text_color),
    )
    with btn.canvas.before:
        Color(*bg_color)
        btn._bg = RoundedRectangle(radius=[r])
    btn.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
             size=lambda i, v: setattr(i._bg, 'size', v))
    if on_press:
        btn.bind(on_press=on_press)
    return btn


# ─── Card widget ──────────────────────────────────────────────────────────────
class VCard(BoxLayout):
    """
    White rounded card. Height is dynamic by default (size_hint_y=None + auto).
    Pass fixed_height=X to lock the height.
    """
    def __init__(self, fixed_height=None, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('padding', (rdp(14), rdp(12)))
        kwargs.setdefault('spacing', rdp(8))
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._rect = RoundedRectangle(radius=[rdp(12)])
        self.bind(pos=self._upd, size=self._upd)

        if fixed_height is not None:
            self.height = fixed_height
        else:
            # auto-height: expand to contain children
            self.bind(minimum_height=self.setter('height'))

    def _upd(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size


# ─── Top bar ──────────────────────────────────────────────────────────────────
def make_topbar(title, back_cb=None):
    h = rdp(56)
    topbar = BoxLayout(size_hint_y=None, height=h,
                       padding=(rdp(8), 0), spacing=rdp(4))
    with topbar.canvas.before:
        Color(*BRAND)
        topbar._bg = Rectangle()
    topbar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                size=lambda i, v: setattr(i._bg, 'size', v))

    if back_cb:
        back = Button(
            text='←', size_hint=(None, None), size=(rdp(44), rdp(44)),
            background_color=(0, 0, 0, 0),
            color=_hex(WHITE_HEX), font_size=rsp(20),
        )
        back.bind(on_press=lambda _: back_cb())
        topbar.add_widget(back)

    lbl = Label(
        text=title, font_size=rsp(17), bold=True,
        color=_hex(WHITE_HEX), halign='left', valign='middle',
    )
    lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
    topbar.add_widget(lbl)
    return topbar


# ─── Toast ────────────────────────────────────────────────────────────────────
def show_toast(message, duration=2.5):
    box = BoxLayout(orientation='vertical', padding=rdp(16))
    lbl = make_label(message, size=12, halign='center', color=WHITE_HEX)
    box.add_widget(lbl)
    popup = Popup(
        title='', content=box,
        size_hint=(0.85, None), height=rdp(80),
        auto_dismiss=True,
        background_color=(*BRAND_DARK[:3], 0.95),
        separator_height=0,
    )
    popup.open()
    Clock.schedule_once(lambda _: popup.dismiss(), duration)


# ─── Divider ──────────────────────────────────────────────────────────────────
def make_divider():
    d = Widget(size_hint_y=None, height=dp(1))
    with d.canvas:
        Color(*DIVIDER)
        d._rect = Rectangle()
    d.bind(pos=lambda i, v: setattr(i._rect, 'pos', v),
           size=lambda i, v: setattr(i._rect, 'size', v))
    return d


# ─── Spacer ───────────────────────────────────────────────────────────────────
def spacer(h=8):
    return Widget(size_hint_y=None, height=rdp(h))


# ─── Global app state ─────────────────────────────────────────────────────────
class VocaldState:
    folder_path: str = ''
    app_dir: str = ''
    engine_ready: bool = False
    is_analysing: bool = False
    analysis_cancelled: bool = False

state = VocaldState()


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 1: ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════
class OnboardingScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.step = 0
        self._build_step_0()

    def _clear(self):
        self.clear_widgets()

    # ── Step 0: Welcome ───────────────────────────────────────────────────────
    def _build_step_0(self):
        self._clear()
        root = BoxLayout(orientation='vertical',
                         padding=(rdp(24), rdp(40)),
                         spacing=rdp(20))
        bg_rect(root)

        # Logo + title block
        root.add_widget(spacer(20))
        root.add_widget(make_label('🎙️', size=52, halign='center'))
        root.add_widget(spacer(4))
        root.add_widget(make_label('Vocald', size=30, bold=True,
                                   color=BRAND_DARK_HEX, halign='center'))
        root.add_widget(make_label('Call Recording Speaker ID',
                                   size=14, color=MUTED_HEX, halign='center'))
        root.add_widget(spacer(16))

        # Privacy card
        card = VCard()
        card.add_widget(make_label('🔒  100% Private', size=14, bold=True,
                                   color=BRAND_DARK_HEX))
        card.add_widget(spacer(4))
        card.add_widget(make_label(
            'Everything runs on your phone. No recordings ever leave your '
            'device. Audio is deleted after analysis — only voice '
            'fingerprints are stored.',
            size=12, color=MUTED_HEX))
        root.add_widget(card)

        root.add_widget(Widget())  # flex spacer
        root.add_widget(make_button('GET STARTED', on_press=self._step1,
                                    height=rdp(52), font_size=15))
        root.add_widget(spacer(8))
        self.add_widget(root)

    # ── Step 1: Permissions ───────────────────────────────────────────────────
    def _step1(self, *_):
        self._clear()
        root = BoxLayout(orientation='vertical',
                         padding=(rdp(20), rdp(30)),
                         spacing=rdp(14))
        bg_rect(root)

        root.add_widget(make_label('Permissions Needed', size=22, bold=True,
                                   color=BRAND_DARK_HEX))
        root.add_widget(spacer(2))
        root.add_widget(make_label('Vocald needs these to work:', size=13,
                                   color=MUTED_HEX))
        root.add_widget(spacer(6))

        for icon, title, desc in [
            ('📂', 'Storage Access',
             'Read call recording files from your chosen folder'),
            ('📞', 'Call Log',
             'Get real call time, phone number & duration from Android'),
        ]:
            card = VCard()
            row = BoxLayout(spacing=rdp(12), size_hint_y=None)
            row.bind(minimum_height=row.setter('height'))

            icon_lbl = Label(text=icon, font_size=rsp(26),
                             size_hint=(None, None), size=(rdp(40), rdp(40)))
            row.add_widget(icon_lbl)

            col = BoxLayout(orientation='vertical', spacing=rdp(4))
            col.bind(minimum_height=col.setter('height'))
            t = make_label(title, size=13, bold=True)
            d = make_label(desc, size=11, color=MUTED_HEX)
            col.add_widget(t)
            col.add_widget(d)
            col.size_hint_y = None
            col.bind(minimum_height=col.setter('height'))
            row.add_widget(col)
            row.size_hint_y = None
            row.bind(minimum_height=row.setter('height'))
            card.add_widget(row)
            root.add_widget(card)

        root.add_widget(Widget())
        root.add_widget(make_button('GRANT PERMISSIONS',
                                    on_press=self._request_permissions,
                                    height=rdp(52), font_size=14))
        root.add_widget(spacer(8))
        self.add_widget(root)

    def _request_permissions(self, *_):
        if platform == 'android':
            request_permissions(
                [Permission.READ_EXTERNAL_STORAGE,
                 Permission.READ_CALL_LOG,
                 Permission.WRITE_EXTERNAL_STORAGE],
                callback=self._on_permissions
            )
        else:
            self._step2()

    def _on_permissions(self, permissions, grants):
        Clock.schedule_once(lambda _: self._step2(), 0.3)

    # ── Step 2: Folder selection ──────────────────────────────────────────────
    def _step2(self, *_):
        self._clear()
        root = BoxLayout(orientation='vertical',
                         padding=(rdp(20), rdp(30)),
                         spacing=rdp(14))
        bg_rect(root)

        root.add_widget(make_label('Select Recordings Folder', size=22,
                                   bold=True, color=BRAND_DARK_HEX))
        root.add_widget(spacer(2))
        root.add_widget(make_label(
            'Choose the folder where your phone saves call recordings.',
            size=12, color=MUTED_HEX))
        root.add_widget(spacer(4))

        # Common paths hint card
        card = VCard()
        card.add_widget(make_label('📁  Common folder paths:', size=12, bold=True))
        card.add_widget(spacer(4))
        for path in ['/sdcard/CallRecordings',
                     '/sdcard/MIUI/sound_recorder/call_rec',
                     '/sdcard/Recordings/Call']:
            card.add_widget(make_label(f'• {path}', size=11, color=MUTED_HEX))
        root.add_widget(card)
        root.add_widget(spacer(4))

        self._folder_label = make_label('No folder selected yet.',
                                        size=12, color=MUTED_HEX,
                                        halign='center')
        root.add_widget(self._folder_label)

        root.add_widget(Widget())
        root.add_widget(make_button('SELECT FOLDER',
                                    on_press=self._open_folder_picker,
                                    bg_color=BRAND_LIGHT,
                                    height=rdp(50), font_size=14))
        root.add_widget(spacer(6))
        self._use_btn = make_button('USE THIS FOLDER',
                                    on_press=self._step3,
                                    bg_color=ACCENT,
                                    height=rdp(50), font_size=14)
        self._use_btn.disabled = True
        root.add_widget(self._use_btn)
        root.add_widget(spacer(8))
        self.add_widget(root)

    def _open_folder_picker(self, *_):
        if platform == 'android':
            self._android_folder_picker()
        else:
            self._desktop_folder_input()

    def _android_folder_picker(self):
        Intent = autoclass('android.content.Intent')
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
        mActivity.startActivityForResult(intent, 1001)

    def _desktop_folder_input(self):
        box = BoxLayout(orientation='vertical', padding=rdp(16), spacing=rdp(12))
        box.add_widget(make_label('Enter folder path:', size=13))
        ti = TextInput(size_hint_y=None, height=rdp(44),
                       hint_text='/path/to/recordings', multiline=False,
                       font_size=rsp(13))
        box.add_widget(ti)
        btn = make_button('OK', height=rdp(44))
        box.add_widget(btn)
        popup = Popup(title='Folder Path', content=box,
                      size_hint=(0.9, None), height=rdp(220))
        def _ok(*_):
            path = ti.text.strip()
            if path and os.path.isdir(path):
                self._set_folder(path)
            else:
                show_toast('Invalid path')
            popup.dismiss()
        btn.bind(on_press=_ok)
        popup.open()

    def set_folder_from_android(self, uri_string: str):
        path = self._uri_to_path(uri_string)
        self._set_folder(path or uri_string)

    def _get_resolved_path(self, uri_string: str) -> str:
        return self._uri_to_path(uri_string) or uri_string

    def _uri_to_path(self, uri_string: str) -> str:
        try:
            if 'primary:' in uri_string:
                rel = uri_string.split('primary:')[-1].rstrip('/')
                return f'/sdcard/{rel}'
        except Exception:
            pass
        return uri_string

    def _set_folder(self, path: str):
        state.folder_path = path
        self._folder_label.text = f'✅  {path}'
        self._folder_label.color = _hex(ACCENT_HEX)
        self._use_btn.disabled = False

    # ── Step 3: Initial scan ──────────────────────────────────────────────────
    def _step3(self, *_):
        if not state.folder_path:
            show_toast('Please select a folder first')
            return
        self._clear()
        root = BoxLayout(orientation='vertical',
                         padding=(rdp(20), rdp(30)),
                         spacing=rdp(16))
        bg_rect(root)

        root.add_widget(make_label('Setting Up…', size=22, bold=True,
                                   color=BRAND_DARK_HEX))
        root.add_widget(spacer(4))
        self._status_label = make_label('Scanning folder…', size=13,
                                        color=MUTED_HEX)
        root.add_widget(self._status_label)
        root.add_widget(spacer(8))
        self._pb = ProgressBar(max=100, size_hint_y=None, height=rdp(10))
        root.add_widget(self._pb)
        self.add_widget(root)
        threading.Thread(target=self._do_initial_scan, daemon=True).start()

    def _do_initial_scan(self):
        from folder_scanner import mark_all_existing_as_seen, count_all_audio_files
        import vocald_engine as engine
        total = count_all_audio_files(state.folder_path)
        self._update_status(f'Found {total} recordings — marking as seen…')
        self._update_pb(30)
        marked = mark_all_existing_as_seen(
            state.folder_path,
            lambda fn, ms: engine.mark_file_processed(fn, ms)
        )
        self._update_pb(90)
        self._update_status(f'Marked {marked} files — setup complete!')
        self._update_pb(100)
        Clock.schedule_once(self._finish_onboarding, 1.2)

    @mainthread
    def _update_status(self, text):
        self._status_label.text = text

    @mainthread
    def _update_pb(self, val):
        self._pb.value = val

    @mainthread
    def _finish_onboarding(self, *_):
        app = App.get_running_app()
        app.store.put('setup_done', value=True)
        app.store.put('folder_path', value=state.folder_path)
        app.sm.transition = NoTransition()
        app.sm.current = 'logs'


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 2: LOGS (Home)
# ══════════════════════════════════════════════════════════════════════════════
class LogsScreen(Screen):
    search_text = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._recordings = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        bg_rect(root)

        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = BoxLayout(size_hint_y=None, height=rdp(56),
                           padding=(rdp(16), 0), spacing=rdp(8))
        with topbar.canvas.before:
            Color(*BRAND)
            topbar._bg = Rectangle()
        topbar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                    size=lambda i, v: setattr(i._bg, 'size', v))

        title_lbl = Label(
            text='🎙️  Vocald', font_size=rsp(17), bold=True,
            color=_hex(WHITE_HEX), halign='left', valign='middle',
        )
        title_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        topbar.add_widget(title_lbl)
        topbar.add_widget(Widget())

        for icon, screen in [('👤', 'profiles'), ('⚙️', 'settings')]:
            btn = Button(text=icon, size_hint=(None, None),
                         size=(rdp(44), rdp(44)),
                         background_color=(0, 0, 0, 0),
                         color=_hex(WHITE_HEX), font_size=rsp(20))
            btn.bind(on_press=lambda _, s=screen: self._go(s))
            topbar.add_widget(btn)
        root.add_widget(topbar)

        # ── Action bar ───────────────────────────────────────────────────────
        actbar = BoxLayout(size_hint_y=None, height=rdp(60),
                           padding=(rdp(10), rdp(8)), spacing=rdp(8))
        self._scan_btn = make_button('🔍  SCAN NOW', height=rdp(44),
                                     on_press=self._trigger_scan, font_size=13)
        actbar.add_widget(self._scan_btn)
        self._upload_btn = make_button('📂  UPLOAD', height=rdp(44),
                                       on_press=self._trigger_upload,
                                       bg_color=BRAND_LIGHT, font_size=13)
        actbar.add_widget(self._upload_btn)
        root.add_widget(actbar)

        # ── Status bar ───────────────────────────────────────────────────────
        sbar = BoxLayout(size_hint_y=None, height=rdp(28),
                         padding=(rdp(14), 0))
        self._status_lbl = Label(text='', font_size=rsp(11),
                                 color=_hex(MUTED_HEX),
                                 halign='left', valign='middle')
        self._status_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        sbar.add_widget(self._status_lbl)
        root.add_widget(sbar)

        # ── Search ───────────────────────────────────────────────────────────
        search_row = BoxLayout(size_hint_y=None, height=rdp(50),
                               padding=(rdp(10), rdp(4)))
        self._search_input = TextInput(
            hint_text='🔎  Search by filename or phone…',
            size_hint_y=None, height=rdp(42), multiline=False,
            font_size=rsp(12), background_color=_hex(WHITE_HEX),
            foreground_color=_hex(BLACK_HEX),
            padding=(rdp(10), rdp(10)),
        )
        self._search_input.bind(text=self._on_search)
        search_row.add_widget(self._search_input)
        root.add_widget(search_row)

        # ── Progress block ───────────────────────────────────────────────────
        self._progress_box = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=rdp(80),
            padding=(rdp(12), rdp(6)), spacing=rdp(4),
        )
        with self._progress_box.canvas.before:
            Color(0.937, 0.941, 0.976, 1)
            self._progress_box._bg = Rectangle()
        self._progress_box.bind(
            pos=lambda i, v: setattr(i._bg, 'pos', v),
            size=lambda i, v: setattr(i._bg, 'size', v),
        )
        self._progress_lbl = Label(
            text='', font_size=rsp(11),
            color=_hex(BRAND_DARK_HEX),
            halign='left', valign='middle',
            size_hint_y=None, height=rdp(20),
        )
        self._progress_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        self._progress_box.add_widget(self._progress_lbl)
        self._progress_bar = ProgressBar(max=100, size_hint_y=None, height=rdp(10))
        self._progress_box.add_widget(self._progress_bar)
        cancel_row = BoxLayout(size_hint_y=None, height=rdp(30), spacing=rdp(8))
        cancel_row.add_widget(Widget())
        cancel_btn = make_button('✕  Cancel', height=rdp(28), font_size=11,
                                 bg_color=DANGER,
                                 on_press=self._cancel_analysis)
        cancel_btn.size_hint_x = None
        cancel_btn.width = rdp(100)
        cancel_row.add_widget(cancel_btn)
        self._progress_box.add_widget(cancel_row)
        self._progress_box.opacity = 0
        root.add_widget(self._progress_box)

        # ── Scrollable list ───────────────────────────────────────────────────
        self._scroll = ScrollView()
        self._list = GridLayout(cols=1, spacing=rdp(10),
                                padding=(rdp(10), rdp(6)),
                                size_hint_y=None)
        self._list.bind(minimum_height=self._list.setter('height'))
        self._scroll.add_widget(self._list)
        root.add_widget(self._scroll)
        self.add_widget(root)

    def on_enter(self):
        self._refresh_list()

    def _refresh_list(self):
        import vocald_engine as engine
        self._recordings = engine.get_all_recordings()
        stats = engine.get_db_stats()
        folder_name = os.path.basename(state.folder_path) or 'No folder'
        self._status_lbl.text = (
            f'📁 {folder_name}  •  {stats["recordings"]} recordings'
            f'  •  {stats["voice_profiles"]} voices'
        )
        self._render_list(self._recordings)

    def _on_search(self, instance, text):
        q = text.lower().strip()
        if not q:
            self._render_list(self._recordings)
            return
        filtered = [r for r in self._recordings
                    if q in r['filename'].lower() or
                       q in (r.get('phone_number') or '').lower()]
        self._render_list(filtered)

    def _render_list(self, records):
        self._list.clear_widgets()
        if not records:
            lbl = make_label(
                'No recordings yet.\nTap SCAN NOW to check for new calls.',
                size=13, color=MUTED_HEX, halign='center')
            lbl.size_hint_y = None
            self._list.add_widget(spacer(20))
            self._list.add_widget(lbl)
            return
        for rec in records:
            self._list.add_widget(self._make_card(rec))

    def _make_card(self, rec):
        """
        Card layout (all rows explicitly sized to prevent overlap):
          Row 1: phone number  |  status badge
          Row 2: filename (wraps)
          Row 3: date  |  duration  |  speakers
        """
        card = VCard()
        card._rid = rec['id']

        # Row 1: phone + badge
        row1 = BoxLayout(size_hint_y=None, height=rdp(28), spacing=rdp(6))
        phone = rec.get('phone_number') or 'Unknown number'
        phone_lbl = Label(
            text=f'📞  {phone}', font_size=rsp(13), bold=True,
            color=_hex(BRAND_DARK_HEX), halign='left', valign='middle',
        )
        phone_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        row1.add_widget(phone_lbl)

        status = rec.get('processed', 0)
        badge_text  = ('⏳ Pending', '✅ Done', '❌ Failed')[status]
        badge_color = (WARN_HEX, ACCENT_HEX, DANGER_HEX)[status]
        badge = Label(
            text=badge_text, font_size=rsp(10), bold=True,
            color=_hex(badge_color), halign='right', valign='middle',
            size_hint=(None, None), size=(rdp(72), rdp(28)),
        )
        badge.text_size = (rdp(72), rdp(28))
        row1.add_widget(badge)
        card.add_widget(row1)

        # Row 2: filename
        fname_lbl = make_label(rec['filename'], size=11, color=MUTED_HEX)
        card.add_widget(fname_lbl)
        card.add_widget(spacer(2))

        # Row 3: date | duration | speakers
        row3 = BoxLayout(size_hint_y=None, height=rdp(22), spacing=rdp(8))
        try:
            dt = datetime.fromisoformat(rec['call_date'])
            date_str = dt.strftime('%d %b %Y  %I:%M %p')
        except Exception:
            date_str = rec.get('call_date', '')[:16].replace('T', '  ')

        date_lbl = Label(
            text=f'📅  {date_str}', font_size=rsp(10),
            color=_hex(MUTED_HEX), halign='left', valign='middle',
        )
        date_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        row3.add_widget(date_lbl)

        dur = rec.get('call_duration', 0)
        if dur:
            dur_lbl = Label(
                text=f'⏱ {dur}s', font_size=rsp(10),
                color=_hex(MUTED_HEX), halign='right', valign='middle',
                size_hint=(None, None), size=(rdp(60), rdp(22)),
            )
            dur_lbl.text_size = (rdp(60), rdp(22))
            row3.add_widget(dur_lbl)

        spk_n = rec.get('total_speakers', 0)
        spk_lbl = Label(
            text=f'👥 {spk_n}', font_size=rsp(10),
            color=_hex(BRAND_DARK_HEX), halign='right', valign='middle',
            size_hint=(None, None), size=(rdp(44), rdp(22)),
        )
        spk_lbl.text_size = (rdp(44), rdp(22))
        row3.add_widget(spk_lbl)
        card.add_widget(row3)

        card.bind(on_touch_up=lambda inst, touch:
                  self._open_detail(inst._rid)
                  if inst.collide_point(*touch.pos) else None)
        return card

    def _open_detail(self, rid):
        app = App.get_running_app()
        app.sm.get_screen('detail').load(rid)
        app.sm.transition = SlideTransition(direction='left')
        app.sm.current = 'detail'

    def _go(self, screen):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='left')
        app.sm.current = screen

    def _trigger_scan(self, *_):
        if state.is_analysing:
            show_toast('Analysis already running')
            return
        if not state.folder_path:
            show_toast('No folder selected — go to Settings')
            return
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _trigger_upload(self, *_):
        if platform == 'android':
            self._android_file_picker()
        else:
            self._desktop_file_input()

    def _android_file_picker(self):
        Intent = autoclass('android.content.Intent')
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType('audio/*')
        mActivity.startActivityForResult(intent, 1002)

    def _desktop_file_input(self):
        box = BoxLayout(orientation='vertical', padding=rdp(16), spacing=rdp(12))
        box.add_widget(make_label('Enter audio file path:', size=13))
        ti = TextInput(size_hint_y=None, height=rdp(44),
                       hint_text='/path/to/recording.wav', multiline=False,
                       font_size=rsp(13))
        box.add_widget(ti)
        btn = make_button('Analyse', height=rdp(44))
        box.add_widget(btn)
        popup = Popup(title='Upload File', content=box,
                      size_hint=(0.9, None), height=rdp(240))
        def _ok(*_):
            path = ti.text.strip()
            popup.dismiss()
            if path and os.path.isfile(path):
                threading.Thread(target=self._run_single_file,
                                 args=(path,), daemon=True).start()
            else:
                show_toast('File not found')
        btn.bind(on_press=_ok)
        popup.open()

    def upload_file_from_android(self, filepath: str):
        threading.Thread(target=self._run_single_file,
                         args=(filepath,), daemon=True).start()

    def _run_scan(self):
        import vocald_engine as engine
        from folder_scanner import scan_folder
        state.is_analysing = True
        state.analysis_cancelled = False
        self._set_scanning_ui(True)
        new_files = scan_folder(state.folder_path, engine.is_file_processed)
        if not new_files:
            self._update_progress('✅  All up to date', 100)
            Clock.schedule_once(lambda _: self._set_scanning_ui(False), 1.5)
            state.is_analysing = False
            Clock.schedule_once(lambda _: self._refresh_list(), 1.6)
            return
        total = len(new_files)
        for idx, file_info in enumerate(new_files):
            if state.analysis_cancelled:
                break
            fname = file_info['filename']
            fpath = file_info['filepath']
            self._update_progress(
                f'Analysing {idx + 1}/{total}: {fname}',
                int((idx / total) * 90)
            )
            call_date = file_info['estimated_call_time'].isoformat()
            rid = engine.create_recording_entry(fname, fpath, call_date)
            def _cb(step): self._update_progress(f'{fname}: {step}', None)
            try:
                speakers = engine.analyse_audio_file(fpath, fname, _cb)
                engine.update_recording_after_analysis(rid, speakers)
                engine.mark_file_processed(fname, file_info['modified_ms'])
            except Exception as e:
                engine.mark_recording_failed(rid, str(e))
        self._update_progress('✅  Scan complete', 100)
        Clock.schedule_once(lambda _: self._set_scanning_ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh_list(), 1.3)
        state.is_analysing = False

    def _run_single_file(self, filepath: str):
        import vocald_engine as engine
        state.is_analysing = True
        self._set_scanning_ui(True)
        fname = os.path.basename(filepath)
        self._update_progress(f'Analysing: {fname}', 10)
        call_date = datetime.now().isoformat()
        rid = engine.create_recording_entry(fname, filepath, call_date)
        def _cb(step): self._update_progress(f'{step}', None)
        try:
            speakers = engine.analyse_audio_file(filepath, fname, _cb)
            engine.update_recording_after_analysis(rid, speakers)
            engine.mark_file_processed(
                fname, int(os.path.getmtime(filepath) * 1000))
        except Exception as e:
            engine.mark_recording_failed(rid, str(e))
        self._update_progress('✅  Done', 100)
        Clock.schedule_once(lambda _: self._set_scanning_ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh_list(), 1.3)
        state.is_analysing = False

    def _cancel_analysis(self, *_):
        state.analysis_cancelled = True
        show_toast('Cancelling after current file…')

    @mainthread
    def _set_scanning_ui(self, active: bool):
        self._progress_box.opacity = 1 if active else 0
        self._scan_btn.disabled = active
        self._upload_btn.disabled = active
        if not active:
            self._progress_bar.value = 0

    @mainthread
    def _update_progress(self, text: str, pct=None):
        self._progress_lbl.text = text
        if pct is not None:
            self._progress_bar.value = pct


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 3: RECORDING DETAIL
# ══════════════════════════════════════════════════════════════════════════════
class DetailScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._recording = {}
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        bg_rect(root)
        root.add_widget(make_topbar('Recording Detail', back_cb=self._go_back))
        scroll = ScrollView()
        self._content = GridLayout(cols=1, spacing=rdp(10),
                                   padding=(rdp(12), rdp(10)),
                                   size_hint_y=None)
        self._content.bind(minimum_height=self._content.setter('height'))
        scroll.add_widget(self._content)
        root.add_widget(scroll)
        self.add_widget(root)

    def load(self, recording_id: int):
        import vocald_engine as engine
        self._recording = engine.get_recording_detail(recording_id)
        self._render()

    def _render(self):
        self._content.clear_widgets()
        rec = self._recording
        if not rec:
            self._content.add_widget(
                make_label('Recording not found.', size=14, color=DANGER_HEX))
            return

        # Meta card
        meta = VCard()
        meta.add_widget(make_label('Call Details', size=15, bold=True,
                                   color=BRAND_DARK_HEX))
        meta.add_widget(make_divider())
        meta.add_widget(spacer(4))

        rows = [
            ('📞 Phone',     rec.get('phone_number') or 'Unknown'),
            ('📅 Date',      rec.get('call_date', '')[:19].replace('T', '  ')),
            ('⏱ Duration',  f'{rec.get("call_duration", 0)} seconds'),
            ('📄 File',      rec.get('filename', '')),
        ]
        for label, value in rows:
            row = BoxLayout(size_hint_y=None, height=rdp(26), spacing=rdp(10))
            l = Label(text=label, font_size=rsp(11), bold=True,
                      color=_hex(BLACK_HEX), halign='left', valign='middle',
                      size_hint=(None, None), size=(rdp(85), rdp(26)))
            l.text_size = (rdp(85), rdp(26))
            row.add_widget(l)
            v = Label(text=str(value), font_size=rsp(11),
                      color=_hex(MUTED_HEX), halign='left', valign='middle')
            v.bind(size=lambda i, s: setattr(i, 'text_size', s))
            row.add_widget(v)
            meta.add_widget(row)

        self._content.add_widget(meta)
        self._content.add_widget(spacer(4))
        self._content.add_widget(make_label('Identified Speakers', size=15,
                                            bold=True, color=BRAND_DARK_HEX))

        speakers = rec.get('speakers', [])
        if not speakers:
            self._content.add_widget(
                make_label('No speakers identified.', size=12, color=MUTED_HEX))
        else:
            for spk in speakers:
                self._content.add_widget(self._make_speaker_card(spk))

    def _make_speaker_card(self, spk):
        card = VCard()

        # Speaker name row + edit button
        top = BoxLayout(size_hint_y=None, height=rdp(34), spacing=rdp(8))
        name_lbl = Label(
            text=f'👤  {spk["name"]}', font_size=rsp(14), bold=True,
            color=_hex(BRAND_DARK_HEX), halign='left', valign='middle',
        )
        name_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        top.add_widget(name_lbl)

        edit_btn = make_button('✏️ Edit', height=rdp(30), font_size=11,
                               bg_color=BRAND_LIGHT)
        edit_btn.size_hint_x = None
        edit_btn.width = rdp(72)
        top.add_widget(edit_btn)
        card.add_widget(top)

        # Confidence text
        conf = spk.get('confidence', 0)
        card.add_widget(make_label(f'Confidence: {conf:.1f}%', size=11,
                                   color=MUTED_HEX))

        # Voice profile link
        if spk.get('voice_profile_id'):
            card.add_widget(make_label(
                f'🔗 Voice Profile #{spk["voice_profile_id"]}',
                size=10, color=BRAND_HEX))

        card.add_widget(spacer(4))

        # Progress bar
        pb = ProgressBar(max=100, value=conf, size_hint_y=None, height=rdp(8))
        card.add_widget(pb)

        edit_btn.bind(on_press=lambda _: self._edit_speaker_name(spk))
        return card

    def _edit_speaker_name(self, spk):
        box = BoxLayout(orientation='vertical', padding=rdp(16), spacing=rdp(12))
        box.add_widget(make_label(f'Rename: {spk["name"]}', size=13))
        ti = TextInput(text=spk['name'], size_hint_y=None, height=rdp(44),
                       multiline=False, font_size=rsp(13))
        box.add_widget(ti)
        btn = make_button('Save', height=rdp(44))
        box.add_widget(btn)
        popup = Popup(title='Edit Speaker', content=box,
                      size_hint=(0.9, None), height=rdp(240))
        def _save(*_):
            new_name = ti.text.strip()
            if new_name:
                import vocald_engine as engine
                engine.update_speaker_name(
                    self._recording['id'], spk['speaker_index'], new_name)
                popup.dismiss()
                self.load(self._recording['id'])
            else:
                show_toast('Name cannot be empty')
        btn.bind(on_press=_save)
        popup.open()

    def _go_back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current = 'logs'


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 4: VOICE PROFILES
# ══════════════════════════════════════════════════════════════════════════════
class ProfilesScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        bg_rect(root)
        root.add_widget(make_topbar('Voice Profiles', back_cb=self._go_back))
        scroll = ScrollView()
        self._content = GridLayout(cols=1, spacing=rdp(10),
                                   padding=(rdp(12), rdp(10)),
                                   size_hint_y=None)
        self._content.bind(minimum_height=self._content.setter('height'))
        scroll.add_widget(self._content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        import vocald_engine as engine
        self._content.clear_widgets()
        profiles = engine.get_voice_profiles()
        stats = engine.get_db_stats()

        # Stats summary card
        sc = VCard()
        sc.add_widget(make_label(
            f'📊  {stats["voice_profiles"]} voice profiles  •  '
            f'{stats["recordings"]} recordings',
            size=13, bold=True, color=BRAND_DARK_HEX))
        sc.add_widget(spacer(4))
        sc.add_widget(make_label(
            'Voice fingerprints are stored locally on your device.',
            size=11, color=MUTED_HEX))
        self._content.add_widget(sc)

        if not profiles:
            self._content.add_widget(spacer(10))
            self._content.add_widget(make_label(
                'No voice profiles yet.\n'
                'Analyse some recordings to build the database.',
                size=12, color=MUTED_HEX, halign='center'))
            return

        for p in profiles:
            card = VCard()

            # Name + recording count row
            row1 = BoxLayout(size_hint_y=None, height=rdp(30), spacing=rdp(6))
            name_lbl = Label(
                text=f'#{p["id"]}  {p["name"]}', font_size=rsp(14), bold=True,
                color=_hex(BRAND_DARK_HEX), halign='left', valign='middle',
            )
            name_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
            row1.add_widget(name_lbl)

            rec_lbl = Label(
                text=f'{p["total_recordings"]} recordings',
                font_size=rsp(10), color=_hex(ACCENT_HEX),
                halign='right', valign='middle',
                size_hint=(None, None), size=(rdp(100), rdp(30)),
            )
            rec_lbl.text_size = (rdp(100), rdp(30))
            row1.add_widget(rec_lbl)
            card.add_widget(row1)

            # Date row
            try:
                first = p['first_seen'][:10]
                last  = p['last_seen'][:10]
            except Exception:
                first = last = 'N/A'
            card.add_widget(make_label(
                f'First seen: {first}  •  Last seen: {last}',
                size=10, color=MUTED_HEX))

            self._content.add_widget(card)

    def _go_back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current = 'logs'


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 5: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
class SettingsScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        bg_rect(root)
        root.add_widget(make_topbar('Settings', back_cb=self._go_back))

        scroll = ScrollView()
        content = GridLayout(cols=1, spacing=rdp(12),
                             padding=(rdp(12), rdp(10)),
                             size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        # Folder card
        fc = VCard()
        fc.add_widget(make_label('📁  Call Recordings Folder', size=13,
                                 bold=True, color=BRAND_DARK_HEX))
        fc.add_widget(spacer(4))
        self._folder_lbl = make_label(state.folder_path or 'Not set',
                                      size=11, color=MUTED_HEX)
        fc.add_widget(self._folder_lbl)
        content.add_widget(fc)

        content.add_widget(make_button(
            'Change Folder', bg_color=BRAND_LIGHT, height=rdp(46),
            on_press=self._change_folder, font_size=13))

        content.add_widget(spacer(8))
        content.add_widget(make_label('Danger Zone', size=12, bold=True,
                                      color=DANGER_HEX))
        content.add_widget(make_button(
            '🗑️  Clear All Data', bg_color=DANGER, height=rdp(46),
            on_press=self._confirm_clear, font_size=13))

        content.add_widget(spacer(8))

        # About card
        vc = VCard()
        vc.add_widget(make_label('Vocald  v1.0', size=13, bold=True,
                                 color=BRAND_DARK_HEX))
        vc.add_widget(spacer(4))
        vc.add_widget(make_label('100% on-device  •  No internet required',
                                 size=11, color=MUTED_HEX))
        content.add_widget(vc)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self):
        self._folder_lbl.text = state.folder_path or 'Not set'

    def _change_folder(self, *_):
        app = App.get_running_app()
        ob = app.sm.get_screen('onboarding')
        if platform != 'android':
            ob._desktop_folder_input()
        else:
            ob._android_folder_picker()

    def _confirm_clear(self, *_):
        box = BoxLayout(orientation='vertical', padding=rdp(16), spacing=rdp(12))
        box.add_widget(make_label(
            'This will delete ALL recordings, speakers,\n'
            'and voice profiles. This cannot be undone.',
            size=12, color=DANGER_HEX))
        box.add_widget(spacer(4))
        row = BoxLayout(size_hint_y=None, height=rdp(46), spacing=rdp(10))
        cancel_btn = make_button('Cancel', bg_color=MUTED, height=rdp(46),
                                 font_size=13)
        delete_btn = make_button('DELETE ALL', bg_color=DANGER,
                                 height=rdp(46), font_size=13)
        row.add_widget(cancel_btn)
        row.add_widget(delete_btn)
        box.add_widget(row)
        popup = Popup(title='⚠️  Confirm Delete', content=box,
                      size_hint=(0.9, None), height=rdp(240))
        cancel_btn.bind(on_press=lambda _: popup.dismiss())
        def _do_clear(*_):
            self._clear_all_data()
            popup.dismiss()
        delete_btn.bind(on_press=_do_clear)
        popup.open()

    def _clear_all_data(self):
        import sqlite3
        import vocald_engine as engine
        conn = sqlite3.connect(engine.DB_PATH)
        conn.execute('DELETE FROM speakers')
        conn.execute('DELETE FROM recordings')
        conn.execute('DELETE FROM voice_profiles')
        conn.commit()
        conn.close()
        engine._processed_registry.clear()
        engine._save_processed_registry()
        show_toast('All data cleared')

    def _go_back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current = 'logs'


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
class VocaldApp(App):
    title = 'Vocald'

    def build(self):
        self.store = JsonStore(os.path.join(self.user_data_dir, 'settings.json'))
        state.app_dir = self.user_data_dir

        if platform == 'android':
            activity.bind(on_activity_result=self.on_activity_result)

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        import vocald_engine as engine
        engine.init_engine(self.user_data_dir)

        self.sm = ScreenManager()
        self.sm.add_widget(OnboardingScreen(name='onboarding'))
        self.sm.add_widget(LogsScreen(name='logs'))
        self.sm.add_widget(DetailScreen(name='detail'))
        self.sm.add_widget(ProfilesScreen(name='profiles'))
        self.sm.add_widget(SettingsScreen(name='settings'))

        if self.store.exists('folder_path'):
            state.folder_path = self.store.get('folder_path')['value']

        if (self.store.exists('setup_done')
                and self.store.get('setup_done')['value']):
            self.sm.current = 'logs'
        else:
            self.sm.current = 'onboarding'

        return self.sm

    def on_activity_result(self, request_code, result_code, data):
        RESULT_OK = -1
        if result_code != RESULT_OK:
            return
        if request_code == 1001:
            uri = data.getData().toString()
            ob = self.sm.get_screen('onboarding')
            ob.set_folder_from_android(uri)
            self.store.put('folder_path', value=ob._get_resolved_path(uri))
        elif request_code == 1002:
            uri = data.getData().toString()
            filepath = self._resolve_uri_to_path(uri)
            if filepath:
                self.sm.get_screen('logs').upload_file_from_android(filepath)

    def _resolve_uri_to_path(self, uri_string: str) -> str:
        try:
            if 'primary:' in uri_string:
                rel = uri_string.split('primary:')[-1]
                return f'/sdcard/{rel}'
        except Exception:
            pass
        return uri_string


if __name__ == '__main__':
    VocaldApp().run()