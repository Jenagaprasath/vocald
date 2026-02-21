"""
Vocald — Android APK
Main Kivy application entry point.
Screens: Onboarding → Logs → Details → Profiles → Settings
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

# Conditional Android imports
if platform == 'android':
    from android.permissions import request_permissions, Permission, check_permission
    from android import mActivity, activity
    from jnius import autoclass

# ─── Colour palette ──────────────────────────────────────────────────────────
BRAND      = (0.310, 0.275, 0.506, 1)   # #4F46E5 indigo
BRAND_DARK = (0.192, 0.180, 0.506, 1)   # #312E81
ACCENT     = (0.063, 0.725, 0.506, 1)   # #10B981 emerald
WARN       = (0.961, 0.620, 0.043, 1)   # #F59E0B amber
DANGER     = (0.937, 0.267, 0.267, 1)   # #EF4444 red
BG         = (0.941, 0.949, 1.000, 1)   # #EFF6FF
WHITE      = (1, 1, 1, 1)
LIGHT      = (0.953, 0.957, 0.965, 1)   # #F3F4F6
MUTED      = (0.420, 0.447, 0.502, 1)   # #6B7280
BLACK      = (0.122, 0.161, 0.216, 1)   # #1F2937
CARD_BG    = (1, 1, 1, 1)

BRAND_HEX  = '#4F46E5'
ACCENT_HEX = '#10B981'
WARN_HEX   = '#F59E0B'
DANGER_HEX = '#EF4444'
WHITE_HEX  = '#FFFFFF'
MUTED_HEX  = '#6B7280'
BLACK_HEX  = '#1F2937'
BG_HEX     = '#EFF6FF'
BRAND_DARK_HEX = '#312E81'


# ─── Utility widgets ──────────────────────────────────────────────────────────

class VCard(BoxLayout):
    """White rounded card."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(16)
        self.spacing = dp(8)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._rect = RoundedRectangle(radius=[dp(12)])
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size


def make_label(text, size=14, color=BLACK_HEX, bold=False, halign='left',
               italic=False, markup=False):
    lbl = Label(
        text=text, font_size=sp(size), color=color if isinstance(color, tuple)
             else _hex(color),
        bold=bold, italic=italic, halign=halign, markup=markup,
        size_hint_y=None,
    )
    lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
    lbl.bind(width=lambda i, v: setattr(i, 'text_size', (v, None)))
    return lbl


def make_button(text, bg_color=BRAND, text_color=WHITE_HEX,
                height=dp(48), on_press=None, font_size=14, bold=True,
                radius=dp(10)):
    btn = Button(
        text=text, size_hint=(1, None), height=height,
        font_size=sp(font_size), bold=bold,
        background_color=(0, 0, 0, 0),
        color=text_color if isinstance(text_color, tuple) else _hex(text_color),
    )
    with btn.canvas.before:
        Color(*bg_color)
        btn._bg = RoundedRectangle(radius=[radius])
    btn.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
             size=lambda i, v: setattr(i._bg, 'size', v))
    if on_press:
        btn.bind(on_press=on_press)
    return btn


def _hex(h):
    """Convert '#RRGGBB' to (r,g,b,1) kivy colour tuple."""
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255, g / 255, b / 255, 1


def show_toast(message, duration=2.5):
    """Simple popup that auto-dismisses."""
    box = BoxLayout(orientation='vertical', padding=dp(16))
    box.add_widget(make_label(message, size=13, halign='center'))
    popup = Popup(title='', content=box, size_hint=(0.8, None), height=dp(100),
                  auto_dismiss=True, background_color=(*BRAND[:3], 0.95))
    popup.open()
    Clock.schedule_once(lambda _: popup.dismiss(), duration)


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
    """Multi-step first-launch setup wizard."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.step = 0
        self._build_step_0()

    def _clear(self):
        self.clear_widgets()

    def _build_step_0(self):
        """Welcome screen."""
        self._clear()
        root = BoxLayout(orientation='vertical', padding=dp(32), spacing=dp(24))
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        root.add_widget(Widget(size_hint_y=None, height=dp(60)))
        root.add_widget(make_label('🎙️', size=64, halign='center'))
        root.add_widget(make_label('Vocald', size=36, bold=True,
                                   color=BRAND_DARK_HEX, halign='center'))
        root.add_widget(make_label('Call Recording Speaker ID',
                                   size=16, color=MUTED_HEX, halign='center'))
        root.add_widget(Widget(size_hint_y=None, height=dp(40)))

        card = VCard(size_hint_y=None, height=dp(160))
        card.add_widget(make_label('🔒  100% Private', size=15, bold=True,
                                   color=BRAND_DARK_HEX))
        card.add_widget(make_label(
            'Everything runs on your phone. No recordings ever leave your device. '
            'Audio is deleted after analysis — only voice fingerprints are stored.',
            size=13, color=MUTED_HEX))
        root.add_widget(card)

        root.add_widget(Widget())
        root.add_widget(make_button('GET STARTED', on_press=self._step1))
        self.add_widget(root)

    def _step1(self, *_):
        """Request permissions."""
        self._clear()
        root = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(16))
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        root.add_widget(make_label('Permissions Needed', size=26, bold=True,
                                   color=BRAND_DARK_HEX))
        root.add_widget(make_label('Vocald needs these to work:', size=14,
                                   color=MUTED_HEX))

        for icon, title, desc in [
            ('📂', 'Storage Access',
             'Read call recording files from your chosen folder'),
            ('📞', 'Call Log',
             'Get the real call time, phone number & duration from Android'),
        ]:
            c = VCard(size_hint_y=None, height=dp(90))
            row = BoxLayout(spacing=dp(12))
            icon_lbl = make_label(icon, size=28)
            icon_lbl.size_hint_x = None
            icon_lbl.width = dp(40)
            row.add_widget(icon_lbl)
            col = BoxLayout(orientation='vertical')
            col.add_widget(make_label(title, size=14, bold=True))
            col.add_widget(make_label(desc, size=12, color=MUTED_HEX))
            row.add_widget(col)
            c.add_widget(row)
            root.add_widget(c)

        root.add_widget(Widget())
        root.add_widget(make_button('GRANT PERMISSIONS',
                                    on_press=self._request_permissions))
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
            # Desktop testing — skip
            self._step2()

    def _on_permissions(self, permissions, grants):
        Clock.schedule_once(lambda _: self._step2(), 0.3)

    def _step2(self, *_):
        """Folder selection."""
        self._clear()
        root = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(16))
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        root.add_widget(make_label('Select Call Recordings Folder',
                                   size=24, bold=True, color=BRAND_DARK_HEX))
        root.add_widget(make_label(
            'Choose the folder where your phone saves call recordings.\n'
            'Common locations: "CallRecordings", "PhoneRecord", "Recordings"',
            size=13, color=MUTED_HEX))

        card = VCard(size_hint_y=None, height=dp(120))
        card.add_widget(make_label('📁  Common folder paths on Android:',
                                   size=13, bold=True))
        for path in ['/sdcard/CallRecordings',
                     '/sdcard/MIUI/sound_recorder/call_rec',
                     '/sdcard/Recordings/Call']:
            card.add_widget(make_label(f'  • {path}', size=11,
                                       color=MUTED_HEX))
        root.add_widget(card)

        self._folder_label = make_label('No folder selected', size=13,
                                        color=MUTED_HEX, halign='center')
        root.add_widget(self._folder_label)
        root.add_widget(Widget())
        root.add_widget(make_button('SELECT FOLDER',
                                    on_press=self._open_folder_picker,
                                    bg_color=(0.53, 0.53, 0.93, 1)))
        self._use_btn = make_button('USE THIS FOLDER',
                                    on_press=self._step3,
                                    bg_color=ACCENT)
        self._use_btn.disabled = True
        root.add_widget(self._use_btn)
        self.add_widget(root)

    def _open_folder_picker(self, *_):
        if platform == 'android':
            self._android_folder_picker()
        else:
            self._desktop_folder_input()

    def _android_folder_picker(self):
        """Launch SAF folder picker via Android Intent."""
        Intent = autoclass('android.content.Intent')
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
        mActivity.startActivityForResult(intent, 1001)
        # Result handled in on_activity_result (see app class below)

    def _desktop_folder_input(self):
        """Desktop fallback — type path manually."""
        box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        box.add_widget(make_label('Enter folder path (desktop testing):', size=13))
        ti = TextInput(size_hint_y=None, height=dp(44), hint_text='/path/to/recordings',
                       multiline=False)
        box.add_widget(ti)
        btn = make_button('OK', height=dp(44))
        box.add_widget(btn)
        popup = Popup(title='Folder Path', content=box,
                      size_hint=(0.9, None), height=dp(200))

        def _ok(*_):
            path = ti.text.strip()
            if path and os.path.isdir(path):
                self._set_folder(path)
            else:
                show_toast('Invalid path — folder does not exist')
            popup.dismiss()

        btn.bind(on_press=_ok)
        popup.open()

    def set_folder_from_android(self, uri_string: str):
        """Called back by the app after Android SAF result."""
        # Convert URI to real path for Resemblyzer (needs file path)
        # For Android 10+ we store the URI and resolve files via DocumentFile
        path = self._uri_to_path(uri_string)
        self._set_folder(path or uri_string)

    def _uri_to_path(self, uri_string: str) -> str:
        """Try to resolve SAF URI to a real filesystem path."""
        try:
            # Most common: content://com.android.externalstorage.documents/tree/...
            if 'primary:' in uri_string:
                rel = uri_string.split('primary:')[-1]
                rel = rel.rstrip('/')
                return f'/sdcard/{rel}'
        except Exception:
            pass
        return uri_string

    def _set_folder(self, path: str):
        state.folder_path = path
        self._folder_label.text = f'✅  {path}'
        self._folder_label.color = _hex(ACCENT_HEX)
        self._use_btn.disabled = False

    def _step3(self, *_):
        """Initial scan — mark all existing files as seen."""
        if not state.folder_path:
            show_toast('Please select a folder first')
            return

        self._clear()
        root = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(16))
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        root.add_widget(make_label('Setting Up...', size=24, bold=True,
                                   color=BRAND_DARK_HEX))
        self._status_label = make_label('Scanning folder...', size=14,
                                        color=MUTED_HEX)
        root.add_widget(self._status_label)
        self._pb = ProgressBar(max=100, size_hint_y=None, height=dp(12))
        root.add_widget(self._pb)
        self.add_widget(root)

        threading.Thread(target=self._do_initial_scan, daemon=True).start()

    def _do_initial_scan(self):
        from folder_scanner import mark_all_existing_as_seen, count_all_audio_files
        import vocald_engine as engine

        total = count_all_audio_files(state.folder_path)
        self._update_status(f'Found {total} existing recordings — marking as seen...')
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
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(16), 0),
                           spacing=dp(8))
        with topbar.canvas.before:
            Color(*BRAND)
            topbar._bg = Rectangle()
        topbar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                    size=lambda i, v: setattr(i._bg, 'size', v))
        topbar.add_widget(make_label('🎙️ Vocald', size=18, bold=True,
                                     color=WHITE_HEX))
        topbar.add_widget(Widget())
        btn_db = Button(text='👤', size_hint=(None, None), size=(dp(44), dp(44)),
                        background_color=(0, 0, 0, 0), color=_hex(WHITE_HEX),
                        font_size=sp(20))
        btn_db.bind(on_press=lambda _: self._go('profiles'))
        topbar.add_widget(btn_db)
        btn_set = Button(text='⚙️', size_hint=(None, None), size=(dp(44), dp(44)),
                         background_color=(0, 0, 0, 0), color=_hex(WHITE_HEX),
                         font_size=sp(20))
        btn_set.bind(on_press=lambda _: self._go('settings'))
        topbar.add_widget(btn_set)
        root.add_widget(topbar)

        # ── Action bar ───────────────────────────────────────────────────────
        actbar = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=(dp(12), dp(8)), spacing=dp(8))
        self._scan_btn = make_button('🔍 SCAN NOW', height=dp(40),
                                     on_press=self._trigger_scan,
                                     font_size=12)
        actbar.add_widget(self._scan_btn)
        self._upload_btn = make_button('📂 UPLOAD FILE', height=dp(40),
                                       on_press=self._trigger_upload,
                                       bg_color=(0.53, 0.53, 0.93, 1),
                                       font_size=12)
        actbar.add_widget(self._upload_btn)
        root.add_widget(actbar)

        # ── Status chip ──────────────────────────────────────────────────────
        self._status_bar = BoxLayout(size_hint_y=None, height=dp(36),
                                     padding=(dp(16), 0))
        self._status_lbl = make_label('', size=12, color=MUTED_HEX)
        self._status_bar.add_widget(self._status_lbl)
        root.add_widget(self._status_bar)

        # ── Search ───────────────────────────────────────────────────────────
        search_row = BoxLayout(size_hint_y=None, height=dp(44),
                               padding=(dp(12), 0))
        self._search_input = TextInput(
            hint_text='🔎  Search by filename or phone number...',
            size_hint_y=None, height=dp(40), multiline=False,
            font_size=sp(13), background_color=_hex(WHITE_HEX),
        )
        self._search_input.bind(text=self._on_search)
        search_row.add_widget(self._search_input)
        root.add_widget(search_row)

        # ── Analysis progress bar (hidden by default) ─────────────────────
        self._progress_box = BoxLayout(orientation='vertical',
                                       size_hint_y=None, height=dp(60),
                                       padding=(dp(12), dp(4)))
        self._progress_lbl = make_label('', size=12, color=BRAND_DARK_HEX)
        self._progress_box.add_widget(self._progress_lbl)
        self._progress_bar = ProgressBar(max=100, size_hint_y=None, height=dp(8))
        self._progress_box.add_widget(self._progress_bar)
        cancel_btn = make_button('Cancel', height=dp(28), font_size=11,
                                 bg_color=DANGER, on_press=self._cancel_analysis)
        self._progress_box.add_widget(cancel_btn)
        self._progress_box.opacity = 0
        root.add_widget(self._progress_box)

        # ── Scrollable recordings list ────────────────────────────────────
        self._scroll = ScrollView()
        self._list = GridLayout(cols=1, spacing=dp(10), padding=dp(12),
                                size_hint_y=None)
        self._list.bind(minimum_height=self._list.setter('height'))
        self._scroll.add_widget(self._list)
        root.add_widget(self._scroll)

        self.add_widget(root)

    def on_enter(self):
        """Called every time this screen becomes active."""
        self._refresh_list()

    def _refresh_list(self):
        import vocald_engine as engine
        self._recordings = engine.get_all_recordings()
        stats = engine.get_db_stats()
        folder_name = os.path.basename(state.folder_path) or 'No folder'
        self._status_lbl.text = (
            f'📁 {folder_name}  •  {stats["recordings"]} recordings  '
            f'•  {stats["voice_profiles"]} known voices'
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
            self._list.add_widget(
                make_label('No recordings yet.\nTap SCAN NOW to check for new calls.',
                           size=14, color=MUTED_HEX, halign='center'))
            return

        for rec in records:
            self._list.add_widget(self._make_card(rec))

    def _make_card(self, rec):
        card = VCard(size_hint_y=None, height=dp(110))
        card._rid = rec['id']

        # Top row: phone number + status badge
        top = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
        phone = rec.get('phone_number') or 'Unknown number'
        top.add_widget(make_label(f'📞  {phone}', size=14, bold=True,
                                  color=BRAND_DARK_HEX))
        top.add_widget(Widget())
        status = rec.get('processed', 0)
        badge_text = ['⏳ Pending', '✅ Done', '❌ Failed'][status]
        badge_color = [WARN_HEX, ACCENT_HEX, DANGER_HEX][status]
        top.add_widget(make_label(badge_text, size=11, bold=True,
                                  color=badge_color))
        card.add_widget(top)

        # Middle row: filename
        card.add_widget(make_label(rec['filename'], size=12, color=MUTED_HEX))

        # Bottom row: date + speakers
        bot = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(16))
        try:
            dt = datetime.fromisoformat(rec['call_date'])
            date_str = dt.strftime('%d %b %Y  %I:%M %p')
        except Exception:
            date_str = rec.get('call_date', '')
        bot.add_widget(make_label(f'📅  {date_str}', size=12, color=MUTED_HEX))
        dur = rec.get('call_duration', 0)
        if dur:
            bot.add_widget(make_label(f'⏱  {dur}s', size=12, color=MUTED_HEX))
        bot.add_widget(Widget())
        spk_n = rec.get('total_speakers', 0)
        bot.add_widget(make_label(f'👥  {spk_n}', size=12, color=BRAND_DARK_HEX))
        card.add_widget(bot)

        # Tap to open detail
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

    # ── Scan trigger ─────────────────────────────────────────────────────────
    def _trigger_scan(self, *_):
        if state.is_analysing:
            show_toast('Analysis already running')
            return
        if not state.folder_path:
            show_toast('No folder selected — go to Settings')
            return
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _trigger_upload(self, *_):
        """Manual single-file upload — open file picker."""
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
        box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        box.add_widget(make_label('Enter audio file path:', size=13))
        ti = TextInput(size_hint_y=None, height=dp(44),
                       hint_text='/path/to/recording.wav', multiline=False)
        box.add_widget(ti)
        btn = make_button('Analyse', height=dp(44))
        box.add_widget(btn)
        popup = Popup(title='Upload File', content=box,
                      size_hint=(0.9, None), height=dp(220))

        def _ok(*_):
            path = ti.text.strip()
            popup.dismiss()
            if path and os.path.isfile(path):
                threading.Thread(
                    target=self._run_single_file,
                    args=(path,), daemon=True
                ).start()
            else:
                show_toast('File not found')

        btn.bind(on_press=_ok)
        popup.open()

    def upload_file_from_android(self, filepath: str):
        threading.Thread(target=self._run_single_file,
                         args=(filepath,), daemon=True).start()

    # ── Analysis runner ───────────────────────────────────────────────────────
    def _run_scan(self):
        """Scan folder and analyse all new files FIFO."""
        import vocald_engine as engine
        from folder_scanner import scan_folder

        state.is_analysing = True
        state.analysis_cancelled = False
        self._set_scanning_ui(True)

        new_files = scan_folder(state.folder_path, engine.is_file_processed)

        if not new_files:
            self._update_progress('✅  All up to date — no new recordings', 100)
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
                f'Analysing {idx+1}/{total}: {fname}', int((idx / total) * 90)
            )

            # Create DB entry with call timestamp immediately
            call_date = file_info['estimated_call_time'].isoformat()
            rid = engine.create_recording_entry(
                filename=fname, filepath=fpath,
                call_date=call_date,
            )

            # Analyse
            def _cb(step): self._update_progress(f'{fname}: {step}', None)
            try:
                speakers = engine.analyse_audio_file(fpath, fname, _cb)
                engine.update_recording_after_analysis(rid, speakers)
                engine.mark_file_processed(fname, file_info['modified_ms'])
            except Exception as e:
                engine.mark_recording_failed(rid, str(e))
                print(f'❌ Failed: {fname}: {e}')

        self._update_progress('✅  Scan complete', 100)
        Clock.schedule_once(lambda _: self._set_scanning_ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh_list(), 1.3)
        state.is_analysing = False

    def _run_single_file(self, filepath: str):
        """Manually uploaded file — analyse immediately."""
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
            engine.mark_file_processed(fname, int(os.path.getmtime(filepath) * 1000))
        except Exception as e:
            engine.mark_recording_failed(rid, str(e))

        self._update_progress('✅  Done', 100)
        Clock.schedule_once(lambda _: self._set_scanning_ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh_list(), 1.3)
        state.is_analysing = False

    def _cancel_analysis(self, *_):
        state.analysis_cancelled = True
        show_toast('Cancelling after current file...')

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
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        # Top bar
        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(8), 0),
                           spacing=dp(4))
        with topbar.canvas.before:
            Color(*BRAND)
            topbar._bg = Rectangle()
        topbar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                    size=lambda i, v: setattr(i._bg, 'size', v))
        back = Button(text='← Back', size_hint=(None, None),
                      size=(dp(80), dp(44)), background_color=(0, 0, 0, 0),
                      color=_hex(WHITE_HEX), font_size=sp(13))
        back.bind(on_press=lambda _: self._go_back())
        topbar.add_widget(back)
        self._title_lbl = make_label('Recording', size=16, bold=True,
                                     color=WHITE_HEX)
        topbar.add_widget(self._title_lbl)
        root.add_widget(topbar)

        scroll = ScrollView()
        self._content = GridLayout(cols=1, spacing=dp(10), padding=dp(12),
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
            self._content.add_widget(make_label('Recording not found', size=14))
            return

        self._title_lbl.text = rec.get('filename', 'Detail')

        # Meta card
        meta = VCard(size_hint_y=None, height=dp(160))
        meta.add_widget(make_label('Call Details', size=16, bold=True,
                                   color=BRAND_DARK_HEX))

        for label, value in [
            ('📞 Phone', rec.get('phone_number') or 'Unknown'),
            ('📅 Date', rec.get('call_date', '')[:19].replace('T', '  ')),
            ('⏱ Duration', f'{rec.get("call_duration", 0)} seconds'),
            ('📄 File', rec.get('filename', '')),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
            row.add_widget(make_label(label, size=12, bold=True))
            row.add_widget(make_label(str(value), size=12, color=MUTED_HEX))
            meta.add_widget(row)
        self._content.add_widget(meta)

        # Speakers
        self._content.add_widget(make_label('Identified Speakers', size=16,
                                             bold=True, color=BRAND_DARK_HEX))
        speakers = rec.get('speakers', [])
        if not speakers:
            self._content.add_widget(make_label('No speakers identified.',
                                                 size=13, color=MUTED_HEX))
        else:
            for spk in speakers:
                self._content.add_widget(self._make_speaker_card(spk))

    def _make_speaker_card(self, spk):
        card = VCard(size_hint_y=None, height=dp(120))
        top = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        top.add_widget(make_label(f'👤  {spk["name"]}', size=15, bold=True,
                                  color=BRAND_DARK_HEX))
        top.add_widget(Widget())
        edit_btn = make_button('✏️ Edit', height=dp(30), font_size=11,
                               bg_color=(0.53, 0.53, 0.93, 1))
        edit_btn.size_hint_x = None
        edit_btn.width = dp(70)
        top.add_widget(edit_btn)
        card.add_widget(top)

        conf = spk.get('confidence', 0)
        card.add_widget(make_label(f'Confidence: {conf:.1f}%', size=12,
                                   color=MUTED_HEX))
        if spk.get('voice_profile_id'):
            card.add_widget(make_label(
                f'🔗 Voice Profile #{spk["voice_profile_id"]}',
                size=11, color=BRAND_DARK_HEX))

        # Confidence bar
        pb = ProgressBar(max=100, value=conf, size_hint_y=None, height=dp(8))
        card.add_widget(pb)

        def _edit(*_):
            self._edit_speaker_name(spk)
        edit_btn.bind(on_press=_edit)
        return card

    def _edit_speaker_name(self, spk):
        box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        box.add_widget(make_label(f'Rename speaker: {spk["name"]}', size=13))
        ti = TextInput(text=spk['name'], size_hint_y=None, height=dp(44),
                       multiline=False)
        box.add_widget(ti)
        btn = make_button('Save', height=dp(44))
        box.add_widget(btn)
        popup = Popup(title='Edit Speaker', content=box,
                      size_hint=(0.9, None), height=dp(220))

        def _save(*_):
            new_name = ti.text.strip()
            if new_name:
                import vocald_engine as engine
                engine.update_speaker_name(
                    self._recording['id'], spk['speaker_index'], new_name
                )
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
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        topbar = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=(dp(8), 0), spacing=dp(4))
        with topbar.canvas.before:
            Color(*BRAND)
            topbar._bg = Rectangle()
        topbar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                    size=lambda i, v: setattr(i._bg, 'size', v))
        back = Button(text='← Back', size_hint=(None, None),
                      size=(dp(80), dp(44)), background_color=(0, 0, 0, 0),
                      color=_hex(WHITE_HEX), font_size=sp(13))
        back.bind(on_press=lambda _: self._go_back())
        topbar.add_widget(back)
        topbar.add_widget(make_label('Voice Profiles', size=16, bold=True,
                                     color=WHITE_HEX))
        root.add_widget(topbar)

        scroll = ScrollView()
        self._content = GridLayout(cols=1, spacing=dp(10), padding=dp(12),
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

        # Stats card
        sc = VCard(size_hint_y=None, height=dp(80))
        sc.add_widget(make_label(
            f'📊  {stats["voice_profiles"]} voice profiles  •  '
            f'{stats["recordings"]} recordings', size=13, bold=True,
            color=BRAND_DARK_HEX))
        sc.add_widget(make_label(
            'Embeddings are 256-dimensional voice fingerprints stored locally.',
            size=11, color=MUTED_HEX))
        self._content.add_widget(sc)

        if not profiles:
            self._content.add_widget(make_label(
                'No voice profiles yet.\nAnalyse some recordings to build the database.',
                size=13, color=MUTED_HEX, halign='center'))
            return

        for p in profiles:
            card = VCard(size_hint_y=None, height=dp(100))
            row1 = BoxLayout(size_hint_y=None, height=dp(30))
            row1.add_widget(make_label(f'#{p["id"]}  {p["name"]}', size=15,
                                        bold=True, color=BRAND_DARK_HEX))
            row1.add_widget(Widget())
            row1.add_widget(make_label(f'{p["total_recordings"]} recordings',
                                        size=11, color=ACCENT_HEX))
            card.add_widget(row1)
            try:
                first = p['first_seen'][:10]
                last = p['last_seen'][:10]
            except Exception:
                first = last = ''
            card.add_widget(make_label(f'First: {first}  •  Last seen: {last}',
                                        size=11, color=MUTED_HEX))
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
        with root.canvas.before:
            Color(*BG)
            root._bg = Rectangle()
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        topbar = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=(dp(8), 0), spacing=dp(4))
        with topbar.canvas.before:
            Color(*BRAND)
            topbar._bg = Rectangle()
        topbar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                    size=lambda i, v: setattr(i._bg, 'size', v))
        back = Button(text='← Back', size_hint=(None, None),
                      size=(dp(80), dp(44)), background_color=(0, 0, 0, 0),
                      color=_hex(WHITE_HEX), font_size=sp(13))
        back.bind(on_press=lambda _: self._go_back())
        topbar.add_widget(back)
        topbar.add_widget(make_label('Settings', size=16, bold=True,
                                     color=WHITE_HEX))
        root.add_widget(topbar)

        scroll = ScrollView()
        content = GridLayout(cols=1, spacing=dp(10), padding=dp(12),
                             size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        # Current folder
        fc = VCard(size_hint_y=None, height=dp(90))
        fc.add_widget(make_label('📁  Call Recordings Folder', size=14,
                                  bold=True, color=BRAND_DARK_HEX))
        self._folder_lbl = make_label(state.folder_path or 'Not set',
                                       size=12, color=MUTED_HEX)
        fc.add_widget(self._folder_lbl)
        content.add_widget(fc)

        content.add_widget(make_button('Change Folder', bg_color=(0.53, 0.53, 0.93, 1),
                                       height=dp(44),
                                       on_press=self._change_folder))

        content.add_widget(make_label('Danger Zone', size=14, bold=True,
                                       color=DANGER_HEX))
        content.add_widget(make_button('🗑️  Clear All Data', bg_color=DANGER,
                                       height=dp(44),
                                       on_press=self._confirm_clear))

        # Version info
        vc = VCard(size_hint_y=None, height=dp(70))
        vc.add_widget(make_label('Vocald v1.0', size=14, bold=True,
                                  color=BRAND_DARK_HEX))
        vc.add_widget(make_label('100% on-device • No internet required',
                                  size=11, color=MUTED_HEX))
        content.add_widget(vc)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self):
        self._folder_lbl.text = state.folder_path or 'Not set'

    def _change_folder(self, *_):
        """Re-open folder picker."""
        app = App.get_running_app()
        ob = app.sm.get_screen('onboarding')
        ob._desktop_folder_input() if platform != 'android' else ob._android_folder_picker()

    def _confirm_clear(self, *_):
        box = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        box.add_widget(make_label('This will delete ALL recordings, speakers,\n'
                                  'and voice profiles. Cannot be undone.',
                                  size=13, color=DANGER_HEX))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        row.add_widget(make_button('Cancel', bg_color=MUTED, height=dp(44)))
        row.add_widget(make_button('DELETE ALL', bg_color=DANGER, height=dp(44)))
        box.add_widget(row)
        popup = Popup(title='⚠️ Confirm Delete', content=box,
                      size_hint=(0.9, None), height=dp(220))

        row.children[1].bind(on_press=lambda _: popup.dismiss())
        def _do_clear(*_):
            self._clear_all_data()
            popup.dismiss()
        row.children[0].bind(on_press=_do_clear)
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
        # Clear processed registry
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

        # Register Android activity result callback
        if platform == 'android':
            activity.bind(on_activity_result=self.on_activity_result)

        # Initialise engine (set DB path etc.)
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        import vocald_engine as engine
        engine.init_engine(self.user_data_dir)

        # Build screen manager
        self.sm = ScreenManager()
        self.sm.add_widget(OnboardingScreen(name='onboarding'))
        self.sm.add_widget(LogsScreen(name='logs'))
        self.sm.add_widget(DetailScreen(name='detail'))
        self.sm.add_widget(ProfilesScreen(name='profiles'))
        self.sm.add_widget(SettingsScreen(name='settings'))

        # Restore saved folder
        if self.store.exists('folder_path'):
            state.folder_path = self.store.get('folder_path')['value']

        # Decide start screen
        if self.store.exists('setup_done') and self.store.get('setup_done')['value']:
            self.sm.current = 'logs'
        else:
            self.sm.current = 'onboarding'

        return self.sm

    def on_activity_result(self, request_code, result_code, data):
        """Handle Android Intent results (folder picker + file picker)."""
        RESULT_OK = -1
        if result_code != RESULT_OK:
            return

        if request_code == 1001:
            # Folder picker result
            uri = data.getData().toString()
            ob = self.sm.get_screen('onboarding')
            ob.set_folder_from_android(uri)
            self.store.put('folder_path', value=ob._get_resolved_path(uri))

        elif request_code == 1002:
            # File picker result
            uri = data.getData().toString()
            filepath = self._resolve_uri_to_path(uri)
            if filepath:
                logs_screen = self.sm.get_screen('logs')
                logs_screen.upload_file_from_android(filepath)

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
