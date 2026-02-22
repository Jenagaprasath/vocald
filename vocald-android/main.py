"""
Vocald — Android APK  (UI v3 — zero-overlap, all-device)
=========================================================
Design philosophy:
  • NEVER put wrapping text inside a fixed-height container.
  • Every container that holds text uses size_hint_y=None + minimum_height binding.
  • All font/dp values scale off Window.width with a gentle clamp.
  • Labels use a single helper that auto-resizes via texture_size.
  • Rows that must stay single-line use shorten=True + ellipsis, never wrap.
"""

import os, sys, threading
from datetime import datetime

# ── Kivy must-set-before-import config ────────────────────────────────────────
os.environ['KIVY_NO_ENV_CONFIG'] = '1'
from kivy.config import Config
Config.set('graphics', 'resizable', '1')

from kivy.app               import App
from kivy.clock             import Clock, mainthread
from kivy.core.window       import Window
from kivy.graphics          import Color, Rectangle, RoundedRectangle, Line
from kivy.metrics           import dp, sp
from kivy.properties        import StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout     import BoxLayout
from kivy.uix.button        import Button
from kivy.uix.floatlayout   import FloatLayout
from kivy.uix.gridlayout    import GridLayout
from kivy.uix.label         import Label
from kivy.uix.popup         import Popup
from kivy.uix.progressbar   import ProgressBar
from kivy.uix.screenmanager import (ScreenManager, Screen,
                                    SlideTransition, NoTransition)
from kivy.uix.scrollview    import ScrollView
from kivy.uix.textinput     import TextInput
from kivy.uix.widget        import Widget
from kivy.utils             import platform

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android import mActivity, activity
    from jnius import autoclass


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSIVE SCALE  (base width = 360 dp)
# ═══════════════════════════════════════════════════════════════════════════════
def _scale():
    """A single scale factor clamped to [0.80, 1.40]."""
    return max(0.80, min(1.40, Window.width / dp(360)))

def F(size):   return sp(size) * _scale()   # font size
def S(size):   return dp(size) * _scale()   # spacing / dimension


# ═══════════════════════════════════════════════════════════════════════════════
# COLOUR SYSTEM  — dark navy + electric teal + warm accent
# ═══════════════════════════════════════════════════════════════════════════════
C = dict(
    bg          = (0.094, 0.102, 0.141, 1),   # #181A24
    surface     = (0.133, 0.145, 0.196, 1),   # #222532
    surface2    = (0.169, 0.184, 0.243, 1),   # #2B2F3E
    border      = (0.239, 0.255, 0.322, 1),   # #3D4152
    primary     = (0.008, 0.808, 0.682, 1),   # #02CEAE  teal
    primary_dim = (0.004, 0.490, 0.420, 1),   # #017D6B
    accent      = (0.608, 0.373, 1.000, 1),   # #9B5FFF  purple
    warn        = (1.000, 0.710, 0.157, 1),   # #FFB528
    danger      = (1.000, 0.353, 0.380, 1),   # #FF5A61
    text        = (0.929, 0.933, 0.949, 1),   # #EDEFF2
    muted       = (0.510, 0.533, 0.612, 1),   # #82889C
    white       = (1, 1, 1, 1),
)

def ch(key):       return C[key][:3] + (1,)
def ca(key, a):    return C[key][:3] + (a,)


# ═══════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _bind_rect(widget, attr):
    def _upd(*_):
        r = getattr(widget, attr)
        r.pos  = widget.pos
        r.size = widget.size
    widget.bind(pos=_upd, size=_upd)

def fill(widget, color_key, radius=0):
    with widget.canvas.before:
        Color(*ch(color_key))
        r = RoundedRectangle(radius=[S(radius)]) if radius else Rectangle()
    widget._fill_rect = r
    _bind_rect(widget, '_fill_rect')

def fill_c(widget, color_tuple, radius=0):
    with widget.canvas.before:
        Color(*color_tuple)
        r = RoundedRectangle(radius=[S(radius)]) if radius else Rectangle()
    widget._fill_rect = r
    _bind_rect(widget, '_fill_rect')


# ═══════════════════════════════════════════════════════════════════════════════
# LABEL HELPERS  — the core fix for text overlap
# ═══════════════════════════════════════════════════════════════════════════════

def Lbl(text, size=14, color='text', bold=False, italic=False,
        halign='left', wrap=True):
    """
    wrap=True  → multiline; height auto-expands via texture_size binding.
    wrap=False → single line; fixed height; text truncated with ellipsis.
    """
    lbl = Label(
        text         = str(text),
        font_size    = F(size),
        color        = ch(color) if isinstance(color, str) else color,
        bold         = bold,
        italic       = italic,
        halign       = halign,
        valign       = 'top',
        size_hint_y  = None,
        shorten      = not wrap,
        shorten_from = 'right',
    )
    if wrap:
        lbl.height = F(size) * 1.5   # sane initial height
        lbl.bind(width=lambda i, w: setattr(i, 'text_size', (w, None)))
        lbl.bind(texture_size=lambda i, ts: setattr(i, 'height', ts[1]))
    else:
        h = F(size) * 1.6
        lbl.height     = h
        lbl.valign     = 'middle'
        lbl.text_size  = (None, None)
        lbl.bind(width=lambda i, w: setattr(i, 'text_size', (w, h)))
    return lbl


def FixedLbl(text, size=13, color='text', bold=False,
             halign='right', width_dp=80):
    """Fixed-width, single-line, non-wrapping label."""
    h = F(size) * 1.6
    lbl = Label(
        text         = str(text),
        font_size    = F(size),
        color        = ch(color) if isinstance(color, str) else color,
        bold         = bold,
        halign       = halign,
        valign       = 'middle',
        size_hint    = (None, None),
        size         = (S(width_dp), h),
        shorten      = True,
        shorten_from = 'right',
    )
    lbl.text_size = (S(width_dp), h)
    return lbl


# ═══════════════════════════════════════════════════════════════════════════════
# REUSABLE WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

def Gap(h=8):
    return Widget(size_hint_y=None, height=S(h))


class Card(BoxLayout):
    """
    Dark surface card with rounded corners.
    Height is ALWAYS driven by children (minimum_height binding).
    """
    def __init__(self, pad_dp=14, gap_dp=8, radius=14, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('padding', (S(pad_dp), S(pad_dp)))
        kwargs.setdefault('spacing', S(gap_dp))
        super().__init__(**kwargs)
        self.bind(minimum_height=self.setter('height'))
        with self.canvas.before:
            Color(*ch('surface'))
            self._bg = RoundedRectangle(radius=[S(radius)])
        self.bind(pos=lambda i, _: setattr(i._bg, 'pos',  i.pos),
                  size=lambda i, _: setattr(i._bg, 'size', i.size))


class Pill(BoxLayout):
    """Compact coloured badge pill."""
    def __init__(self, text, color_key='primary', w_dp=72, **kwargs):
        super().__init__(size_hint=(None, None),
                         width=S(w_dp), height=S(22), **kwargs)
        with self.canvas.before:
            Color(*ca(color_key, 0.20))
            self._bg = RoundedRectangle(radius=[S(11)])
        self.bind(pos=lambda i, _: setattr(i._bg, 'pos',  i.pos),
                  size=lambda i, _: setattr(i._bg, 'size', i.size))
        lbl = Label(text=text, font_size=F(9), bold=True,
                    color=ch(color_key), halign='center', valign='middle')
        lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        self.add_widget(lbl)


def IconBtn(icon, on_press=None, size_dp=44, font_size=21):
    btn = Button(text=icon,
                 size_hint=(None, None), size=(S(size_dp), S(size_dp)),
                 background_color=(0, 0, 0, 0),
                 color=ch('text'), font_size=F(font_size))
    if on_press:
        btn.bind(on_press=on_press)
    return btn


def PrimaryBtn(text, on_press=None, h_dp=50, font_size=14,
               color_key='primary', radius=13):
    h = S(h_dp)
    btn = Button(text=text, size_hint=(1, None), height=h,
                 font_size=F(font_size), bold=True,
                 background_color=(0, 0, 0, 0), color=ch('bg'))
    with btn.canvas.before:
        Color(*ch(color_key))
        btn._bg = RoundedRectangle(radius=[S(radius)])
    btn.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
             size=lambda i, v: setattr(i._bg, 'size', v))
    if on_press:
        btn.bind(on_press=on_press)
    return btn


def GhostBtn(text, on_press=None, h_dp=46, font_size=13, radius=12):
    h = S(h_dp)
    btn = Button(text=text, size_hint=(1, None), height=h,
                 font_size=F(font_size), bold=False,
                 background_color=(0, 0, 0, 0), color=ch('text'))
    with btn.canvas.before:
        Color(*ch('surface2'))
        btn._bg = RoundedRectangle(radius=[S(radius)])
    btn.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
             size=lambda i, v: setattr(i._bg, 'size', v))
    if on_press:
        btn.bind(on_press=on_press)
    return btn


def Divider():
    d = Widget(size_hint_y=None, height=dp(1))
    with d.canvas:
        Color(*ch('border'))
        d._r = Rectangle()
    d.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
           size=lambda i, v: setattr(i._r, 'size', v))
    return d


def TopBar(title, back_cb=None, right_widgets=None):
    h = S(56)
    bar = BoxLayout(size_hint_y=None, height=h,
                    padding=(S(6), 0), spacing=S(4))
    with bar.canvas.before:
        Color(*ch('surface'))
        bar._bg = Rectangle()
    bar.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
             size=lambda i, v: setattr(i._bg, 'size', v))

    if back_cb:
        bar.add_widget(IconBtn('←', on_press=lambda _: back_cb(),
                               size_dp=44, font_size=20))

    tl = Label(text=title, font_size=F(16), bold=True,
               color=ch('text'), halign='left', valign='middle')
    tl.bind(size=lambda i, s: setattr(i, 'text_size', s))
    bar.add_widget(tl)

    if right_widgets:
        for w in right_widgets:
            bar.add_widget(w)
    return bar


def StyledInput(hint='', text='', multiline=False):
    ti = TextInput(
        text=text, hint_text=hint,
        size_hint_y=None, height=S(46),
        multiline=multiline, font_size=F(13),
        foreground_color=ch('text'),
        hint_text_color=ch('muted'),
        background_color=ch('surface2'),
        cursor_color=ch('primary'),
        padding=(S(12), S(12)),
    )
    return ti


def Toast(msg, dur=2.5):
    box = FloatLayout()
    lbl = Label(text=msg, font_size=F(12), color=ch('text'),
                halign='center', size_hint=(None, None),
                pos_hint={'center_x': 0.5, 'center_y': 0.5})
    lbl.bind(texture_size=lambda i, ts: setattr(i, 'size', ts))
    box.add_widget(lbl)
    popup = Popup(title='', content=box,
                  size_hint=(0.78, None), height=S(52),
                  auto_dismiss=True,
                  background_color=(*ch('surface2')[:3], 0.97),
                  separator_height=0)
    popup.open()
    Clock.schedule_once(lambda _: popup.dismiss(), dur)


def ConfirmPopup(title, body, ok_text, ok_color_key, on_ok):
    box = BoxLayout(orientation='vertical', padding=S(16), spacing=S(12))
    fill_c(box, ch('surface'))
    box.add_widget(Gap(4))
    box.add_widget(Lbl(body, size=12, color='muted'))
    box.add_widget(Gap(8))
    row = BoxLayout(size_hint_y=None, height=S(46), spacing=S(10))
    row.add_widget(GhostBtn('Cancel', on_press=lambda _: popup.dismiss()))
    row.add_widget(PrimaryBtn(ok_text, color_key=ok_color_key,
                              on_press=lambda _: (popup.dismiss(), on_ok())))
    box.add_widget(row)
    box.add_widget(Gap(4))
    popup = Popup(title=title, content=box,
                  size_hint=(0.88, None), height=S(220),
                  background_color=(*ch('surface')[:3], 1),
                  title_color=ch('text'), title_size=F(14),
                  separator_color=ch('border'))
    popup.open()


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL APP STATE
# ═══════════════════════════════════════════════════════════════════════════════
class _State:
    folder_path:        str  = ''
    app_dir:            str  = ''
    engine_ready:       bool = False
    is_analysing:       bool = False
    analysis_cancelled: bool = False

state = _State()


# ═══════════════════════════════════════════════════════════════════════════════
# BASE SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
class BaseScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fill(self, 'bg')


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — ONBOARDING
# ═══════════════════════════════════════════════════════════════════════════════
class OnboardingScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._show_welcome()

    def _scrollable_col(self):
        """Returns a GridLayout inside a ScrollView; mounts to self."""
        self.clear_widgets()
        sv = ScrollView(do_scroll_x=False)
        fill(sv, 'bg')
        col = GridLayout(cols=1, size_hint_y=None,
                         padding=(S(22), S(28)), spacing=S(14))
        col.bind(minimum_height=col.setter('height'))
        sv.add_widget(col)
        self.add_widget(sv)
        return col

    # ── Welcome ───────────────────────────────────────────────────────────────
    def _show_welcome(self):
        col = self._scrollable_col()
        col.add_widget(Gap(20))
        col.add_widget(Lbl('🎙️', size=52, halign='center'))
        col.add_widget(Gap(4))
        col.add_widget(Lbl('Vocald', size=32, bold=True,
                           halign='center'))
        col.add_widget(Lbl('Speaker ID for call recordings',
                           size=13, color='muted', halign='center'))
        col.add_widget(Gap(16))

        c1 = Card()
        c1.add_widget(Lbl('🔒  100% Private', size=13, bold=True,
                          color='primary'))
        c1.add_widget(Gap(4))
        c1.add_widget(Lbl('Everything runs on your phone. No recordings ever '
                          'leave your device. Only voice fingerprints are stored.',
                          size=12, color='muted'))
        col.add_widget(c1)
        col.add_widget(Gap(6))

        c2 = Card()
        for icon, label in [('🔊', 'Automatic speaker identification'),
                             ('📊', 'Local voice profile database'),
                             ('📁', 'No cloud — fully offline')]:
            row = BoxLayout(size_hint_y=None, spacing=S(10))
            row.bind(minimum_height=row.setter('height'))
            icon_l = FixedLbl(icon, size=18, halign='left', width_dp=32)
            row.add_widget(icon_l)
            row.add_widget(Lbl(label, size=12, color='muted'))
            c2.add_widget(row)
        col.add_widget(c2)

        col.add_widget(Gap(20))
        col.add_widget(PrimaryBtn('GET STARTED →',
                                  on_press=self._show_permissions,
                                  h_dp=52, font_size=15))
        col.add_widget(Gap(16))

    # ── Permissions ───────────────────────────────────────────────────────────
    def _show_permissions(self, *_):
        col = self._scrollable_col()
        col.add_widget(Lbl('Permissions', size=26, bold=True))
        col.add_widget(Lbl('Two permissions are needed to use Vocald.',
                           size=12, color='muted'))
        col.add_widget(Gap(10))

        for icon, title, desc in [
            ('📂', 'Storage',  'Read audio files from your recordings folder.'),
            ('📞', 'Call Log', 'Fetch call date, duration, and phone number.'),
        ]:
            card = Card()
            row = BoxLayout(size_hint_y=None, spacing=S(12))
            row.bind(minimum_height=row.setter('height'))

            # icon box
            ibox = BoxLayout(size_hint=(None, None), size=(S(40), S(40)))
            fill_c(ibox, ca('primary', 0.12), radius=10)
            il = Label(text=icon, font_size=F(20),
                       halign='center', valign='middle')
            il.bind(size=lambda i, s: setattr(i, 'text_size', s))
            ibox.add_widget(il)
            row.add_widget(ibox)

            tcol = BoxLayout(orientation='vertical', size_hint_y=None,
                             spacing=S(2))
            tcol.bind(minimum_height=tcol.setter('height'))
            tcol.add_widget(Lbl(title, size=13, bold=True))
            tcol.add_widget(Lbl(desc, size=11, color='muted'))
            row.add_widget(tcol)
            card.add_widget(row)
            col.add_widget(card)

        col.add_widget(Gap(16))
        col.add_widget(PrimaryBtn('GRANT PERMISSIONS',
                                  on_press=self._req_perms, h_dp=52))
        col.add_widget(Gap(16))

    def _req_perms(self, *_):
        if platform == 'android':
            request_permissions(
                [Permission.READ_EXTERNAL_STORAGE,
                 Permission.READ_CALL_LOG,
                 Permission.WRITE_EXTERNAL_STORAGE],
                callback=lambda p, g: Clock.schedule_once(
                    lambda _: self._show_folder(), 0.3))
        else:
            self._show_folder()

    # ── Folder picker ─────────────────────────────────────────────────────────
    def _show_folder(self):
        col = self._scrollable_col()
        col.add_widget(Lbl('Recordings Folder', size=26, bold=True))
        col.add_widget(Lbl('Where does your phone save call recordings?',
                           size=12, color='muted'))
        col.add_widget(Gap(10))

        hint = Card()
        hint.add_widget(Lbl('Common paths:', size=11, bold=True,
                            color='primary'))
        hint.add_widget(Gap(4))
        for p in ['/sdcard/CallRecordings',
                  '/sdcard/MIUI/sound_recorder/call_rec',
                  '/sdcard/Recordings/Call']:
            hint.add_widget(Lbl(f'• {p}', size=10, color='muted'))
        col.add_widget(hint)
        col.add_widget(Gap(8))

        self._folder_display_card = Card()
        self._folder_lbl_ob = Lbl('No folder selected.',
                                   size=12, color='muted', halign='center')
        self._folder_display_card.add_widget(self._folder_lbl_ob)
        col.add_widget(self._folder_display_card)

        col.add_widget(Gap(6))
        col.add_widget(GhostBtn('SELECT FOLDER',
                                on_press=self._open_picker, h_dp=50))
        col.add_widget(Gap(6))
        self._use_btn = PrimaryBtn('USE THIS FOLDER →',
                                   on_press=self._do_setup, h_dp=52)
        self._use_btn.disabled = True
        col.add_widget(self._use_btn)
        col.add_widget(Gap(16))

    def _open_picker(self, *_):
        if platform == 'android':
            Intent = autoclass('android.content.Intent')
            i = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            mActivity.startActivityForResult(i, 1001)
        else:
            self._desktop_path_popup()

    def _desktop_path_popup(self):
        box = BoxLayout(orientation='vertical', padding=S(16), spacing=S(12))
        fill_c(box, ch('surface'))
        box.add_widget(Lbl('Enter folder path:', size=13))
        ti = StyledInput(hint='/path/to/recordings')
        box.add_widget(ti)
        box.add_widget(Gap(4))
        popup = Popup(title='Folder Path', content=box,
                      size_hint=(0.9, None), height=S(210),
                      background_color=(*ch('surface')[:3], 1),
                      title_color=ch('text'), title_size=F(14),
                      separator_color=ch('border'))
        box.add_widget(PrimaryBtn('Confirm', h_dp=46,
                                  on_press=lambda _: self._from_ti(ti, popup)))
        popup.open()

    def _from_ti(self, ti, popup):
        path = ti.text.strip()
        if path and os.path.isdir(path):
            self._set_folder(path); popup.dismiss()
        else:
            Toast('Invalid folder path')

    def set_folder_from_android(self, uri):
        self._set_folder(self._uri_to_path(uri) or uri)

    def _get_resolved_path(self, uri):
        return self._uri_to_path(uri) or uri

    def _uri_to_path(self, uri):
        try:
            if 'primary:' in uri:
                return '/sdcard/' + uri.split('primary:')[-1].rstrip('/')
        except Exception:
            pass
        return uri

    def _set_folder(self, path):
        state.folder_path = path
        self._folder_lbl_ob.text  = f'✅  {path}'
        self._folder_lbl_ob.color = ch('primary')
        self._use_btn.disabled    = False

    # ── Setup scan ────────────────────────────────────────────────────────────
    def _do_setup(self, *_):
        if not state.folder_path:
            Toast('Select a folder first'); return
        col = self._scrollable_col()
        col.add_widget(Gap(32))
        col.add_widget(Lbl('Setting Up…', size=22, bold=True, halign='center'))
        col.add_widget(Gap(8))
        self._setup_lbl = Lbl('Scanning…', size=12, color='muted',
                              halign='center')
        col.add_widget(self._setup_lbl)
        col.add_widget(Gap(12))
        self._setup_pb = ProgressBar(max=100, size_hint_y=None, height=S(8))
        col.add_widget(self._setup_pb)
        threading.Thread(target=self._bg_setup, daemon=True).start()

    def _bg_setup(self):
        from folder_scanner import mark_all_existing_as_seen, count_all_audio_files
        import vocald_engine as engine
        total  = count_all_audio_files(state.folder_path)
        self._upd(f'Found {total} recordings…', 30)
        marked = mark_all_existing_as_seen(
            state.folder_path, lambda fn, ms: engine.mark_file_processed(fn, ms))
        self._upd(f'Marked {marked} files. Done!', 100)
        Clock.schedule_once(self._finish, 1.2)

    @mainthread
    def _upd(self, text, pct):
        self._setup_lbl.text  = text
        self._setup_pb.value  = pct

    @mainthread
    def _finish(self, *_):
        app = App.get_running_app()
        app.store.put('setup_done',  value=True)
        app.store.put('folder_path', value=state.folder_path)
        app.sm.transition = NoTransition()
        app.sm.current    = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — LOGS  (Home)
# ═══════════════════════════════════════════════════════════════════════════════
class LogsScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._recordings = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        fill(root, 'bg')

        # Top bar
        bar = TopBar('🎙️  Vocald', right_widgets=[
            IconBtn('👤', on_press=lambda _: self._go('profiles')),
            IconBtn('⚙️', on_press=lambda _: self._go('settings')),
        ])
        root.add_widget(bar)

        # Action row
        act = BoxLayout(size_hint_y=None, height=S(60),
                        padding=(S(10), S(8)), spacing=S(8))
        fill(act, 'surface')
        self._scan_btn   = PrimaryBtn('🔍  SCAN',   on_press=self._trigger_scan,
                                      h_dp=44, font_size=13)
        self._upload_btn = GhostBtn('📂  UPLOAD', on_press=self._trigger_upload,
                                    h_dp=44, font_size=13)
        act.add_widget(self._scan_btn)
        act.add_widget(self._upload_btn)
        root.add_widget(act)

        # Status strip — single-line, never wraps
        sstrip = BoxLayout(size_hint_y=None, height=S(30),
                           padding=(S(14), 0))
        fill(sstrip, 'surface')
        self._status_lbl = Lbl('', size=10.5, color='muted', wrap=False)
        sstrip.add_widget(self._status_lbl)
        root.add_widget(sstrip)

        # Search
        srow = BoxLayout(size_hint_y=None, height=S(52),
                         padding=(S(10), S(5)))
        self._search = StyledInput(hint='🔎  Search by filename or number…')
        self._search.bind(text=self._on_search)
        srow.add_widget(self._search)
        root.add_widget(srow)

        # Progress panel
        self._prog = BoxLayout(orientation='vertical', size_hint_y=None,
                               height=S(72), padding=(S(12), S(6)),
                               spacing=S(4))
        fill(self._prog, 'surface2')
        self._prog_lbl = Lbl('', size=10.5, color='primary', wrap=False)
        self._prog.add_widget(self._prog_lbl)
        self._prog_bar = ProgressBar(max=100, size_hint_y=None, height=S(8))
        self._prog.add_widget(self._prog_bar)
        crow = BoxLayout(size_hint_y=None, height=S(30))
        crow.add_widget(Widget())
        cb = PrimaryBtn('✕  Cancel', on_press=self._cancel,
                        h_dp=26, font_size=10, color_key='danger')
        cb.size_hint_x = None; cb.width = S(90)
        crow.add_widget(cb)
        self._prog.add_widget(crow)
        self._prog.opacity = 0
        root.add_widget(self._prog)

        # Scroll list
        sv = ScrollView(do_scroll_x=False)
        self._list = GridLayout(cols=1, spacing=S(10),
                                padding=(S(10), S(8)), size_hint_y=None)
        self._list.bind(minimum_height=self._list.setter('height'))
        sv.add_widget(self._list)
        root.add_widget(sv)
        self.add_widget(root)

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        import vocald_engine as engine
        self._recordings = engine.get_all_recordings()
        stats  = engine.get_db_stats()
        folder = os.path.basename(state.folder_path) or '—'
        self._status_lbl.text = (
            f'📁 {folder}  ·  {stats["recordings"]} recordings'
            f'  ·  {stats["voice_profiles"]} voices')
        self._render(self._recordings)

    def _on_search(self, _, text):
        q = text.lower().strip()
        self._render(self._recordings if not q else [
            r for r in self._recordings
            if q in r['filename'].lower() or
               q in (r.get('phone_number') or '').lower()])

    def _render(self, records):
        self._list.clear_widgets()
        if not records:
            self._list.add_widget(Gap(32))
            self._list.add_widget(Lbl(
                'No recordings yet.\nTap SCAN to check for new calls.',
                size=13, color='muted', halign='center'))
            return
        for rec in records:
            self._list.add_widget(self._make_card(rec))

    def _make_card(self, rec):
        """
        Row 1 (fixed h): phone (flex, truncated)  |  badge pill (fixed w)
        Row 2 (auto h) : filename — WRAPS freely
        Row 3 (fixed h): date (flex, truncated)  |  dur (fixed)  |  spk (fixed)
        """
        card = Card(pad_dp=12, gap_dp=6)
        card._rid = rec['id']

        # Row 1
        r1 = BoxLayout(size_hint_y=None, height=S(26), spacing=S(6))
        ph = rec.get('phone_number') or 'Unknown number'
        r1.add_widget(Lbl(f'📞  {ph}', size=13, bold=True, wrap=False))
        status = rec.get('processed', 0)
        pkey   = ('warn', 'primary', 'danger')[status]
        ptxt   = ('⏳ Pending', '✅ Done', '❌ Failed')[status]
        r1.add_widget(Pill(ptxt, color_key=pkey))
        card.add_widget(r1)

        # Row 2 — filename, wrapping, auto height
        card.add_widget(Lbl(rec['filename'], size=10.5, color='muted', wrap=True))

        # Row 3
        r3 = BoxLayout(size_hint_y=None, height=S(20), spacing=S(6))
        try:
            dt = datetime.fromisoformat(rec['call_date'])
            ds = dt.strftime('%d %b %Y  %I:%M %p')
        except Exception:
            ds = rec.get('call_date', '')[:16].replace('T', '  ')
        r3.add_widget(Lbl(f'📅  {ds}', size=9.5, color='muted', wrap=False))

        dur = rec.get('call_duration', 0)
        if dur:
            r3.add_widget(FixedLbl(f'⏱ {dur}s', size=9.5,
                                   color='muted', halign='right', width_dp=50))
        r3.add_widget(FixedLbl(f'👥 {rec.get("total_speakers", 0)}',
                                size=9.5, color='accent',
                                halign='right', width_dp=34))
        card.add_widget(r3)

        card.bind(on_touch_up=lambda i, t:
                  self._open(i._rid) if i.collide_point(*t.pos) else None)
        return card

    def _open(self, rid):
        app = App.get_running_app()
        app.sm.get_screen('detail').load(rid)
        app.sm.transition = SlideTransition(direction='left')
        app.sm.current    = 'detail'

    def _go(self, screen):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='left')
        app.sm.current    = screen

    def _trigger_scan(self, *_):
        if state.is_analysing:
            Toast('Already analysing'); return
        if not state.folder_path:
            Toast('No folder — go to Settings'); return
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _trigger_upload(self, *_):
        if platform == 'android':
            Intent = autoclass('android.content.Intent')
            i = Intent(Intent.ACTION_GET_CONTENT)
            i.setType('audio/*')
            mActivity.startActivityForResult(i, 1002)
        else:
            self._desktop_upload()

    def _desktop_upload(self):
        box = BoxLayout(orientation='vertical', padding=S(16), spacing=S(12))
        fill_c(box, ch('surface'))
        box.add_widget(Lbl('Audio file path:', size=13))
        ti = StyledInput(hint='/path/to/recording.wav')
        box.add_widget(ti)
        box.add_widget(Gap(4))
        popup = Popup(title='Upload File', content=box,
                      size_hint=(0.9, None), height=S(230),
                      background_color=(*ch('surface')[:3], 1),
                      title_color=ch('text'), title_size=F(14),
                      separator_color=ch('border'))
        box.add_widget(PrimaryBtn('Analyse', h_dp=46,
                                  on_press=lambda _: self._from_upload(ti, popup)))
        popup.open()

    def _from_upload(self, ti, popup):
        path = ti.text.strip(); popup.dismiss()
        if path and os.path.isfile(path):
            threading.Thread(target=self._run_file,
                             args=(path,), daemon=True).start()
        else:
            Toast('File not found')

    def upload_file_from_android(self, fp):
        threading.Thread(target=self._run_file, args=(fp,), daemon=True).start()

    def _run_scan(self):
        import vocald_engine as engine
        from folder_scanner import scan_folder
        state.is_analysing = True; state.analysis_cancelled = False
        self._set_ui(True)
        new_files = scan_folder(state.folder_path, engine.is_file_processed)
        if not new_files:
            self._upd_prog('✅  All up to date', 100)
            Clock.schedule_once(lambda _: self._set_ui(False), 1.5)
            state.is_analysing = False
            Clock.schedule_once(lambda _: self._refresh(), 1.6)
            return
        total = len(new_files)
        for idx, fi in enumerate(new_files):
            if state.analysis_cancelled: break
            fname = fi['filename']; fpath = fi['filepath']
            self._upd_prog(f'[{idx+1}/{total}]  {fname}',
                           int((idx / total) * 90))
            rid = engine.create_recording_entry(
                fname, fpath, fi['estimated_call_time'].isoformat())
            try:
                spk = engine.analyse_audio_file(
                    fpath, fname, lambda s: self._upd_prog(s, None))
                engine.update_recording_after_analysis(rid, spk)
                engine.mark_file_processed(fname, fi['modified_ms'])
            except Exception as e:
                engine.mark_recording_failed(rid, str(e))
        self._upd_prog('✅  Scan complete', 100)
        Clock.schedule_once(lambda _: self._set_ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh(), 1.3)
        state.is_analysing = False

    def _run_file(self, filepath):
        import vocald_engine as engine
        state.is_analysing = True; self._set_ui(True)
        fname = os.path.basename(filepath)
        self._upd_prog(f'Analysing: {fname}', 10)
        rid = engine.create_recording_entry(fname, filepath,
                                            datetime.now().isoformat())
        try:
            spk = engine.analyse_audio_file(
                filepath, fname, lambda s: self._upd_prog(s, None))
            engine.update_recording_after_analysis(rid, spk)
            engine.mark_file_processed(
                fname, int(os.path.getmtime(filepath) * 1000))
        except Exception as e:
            engine.mark_recording_failed(rid, str(e))
        self._upd_prog('✅  Done', 100)
        Clock.schedule_once(lambda _: self._set_ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh(), 1.3)
        state.is_analysing = False

    def _cancel(self, *_):
        state.analysis_cancelled = True; Toast('Cancelling…')

    @mainthread
    def _set_ui(self, active):
        self._prog.opacity       = 1 if active else 0
        self._scan_btn.disabled  = active
        self._upload_btn.disabled= active
        if not active: self._prog_bar.value = 0

    @mainthread
    def _upd_prog(self, text, pct=None):
        self._prog_lbl.text = text
        if pct is not None: self._prog_bar.value = pct


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — DETAIL
# ═══════════════════════════════════════════════════════════════════════════════
class DetailScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rec = {}
        root = BoxLayout(orientation='vertical')
        fill(root, 'bg')
        root.add_widget(TopBar('Recording Detail', back_cb=self._back))
        sv = ScrollView(do_scroll_x=False)
        self._col = GridLayout(cols=1, size_hint_y=None,
                               padding=(S(12), S(10)), spacing=S(10))
        self._col.bind(minimum_height=self._col.setter('height'))
        sv.add_widget(self._col)
        root.add_widget(sv)
        self.add_widget(root)

    def load(self, rid):
        import vocald_engine as engine
        self._rec = engine.get_recording_detail(rid)
        self._render()

    def _render(self):
        self._col.clear_widgets()
        rec = self._rec
        if not rec:
            self._col.add_widget(Lbl('Recording not found.', color='danger'))
            return

        meta = Card()
        meta.add_widget(Lbl('Call Details', size=14, bold=True, color='primary'))
        meta.add_widget(Divider())
        meta.add_widget(Gap(4))

        for label, value in [
            ('📞 Phone',    rec.get('phone_number') or 'Unknown'),
            ('📅 Date',     rec.get('call_date', '')[:19].replace('T', '  ')),
            ('⏱ Duration', f'{rec.get("call_duration", 0)} seconds'),
            ('📄 File',     rec.get('filename', '')),
        ]:
            row = BoxLayout(size_hint_y=None, spacing=S(8))
            row.bind(minimum_height=row.setter('height'))
            row.add_widget(FixedLbl(label, size=11, bold=True,
                                    color='muted', halign='left', width_dp=82))
            row.add_widget(Lbl(str(value), size=11, color='text', wrap=True))
            meta.add_widget(row)

        self._col.add_widget(meta)
        self._col.add_widget(Lbl('Identified Speakers', size=14,
                                  bold=True, color='text'))

        speakers = rec.get('speakers', [])
        if not speakers:
            self._col.add_widget(Lbl('No speakers identified.',
                                      size=12, color='muted'))
        else:
            for spk in speakers:
                self._col.add_widget(self._speaker_card(spk))

    def _speaker_card(self, spk):
        card = Card()
        row = BoxLayout(size_hint_y=None, height=S(36), spacing=S(8))
        nl = Label(text=f'👤  {spk["name"]}', font_size=F(13), bold=True,
                   color=ch('text'), halign='left', valign='middle')
        nl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        row.add_widget(nl)
        eb = GhostBtn('✏️ Edit', h_dp=32, font_size=11,
                      on_press=lambda _: self._edit(spk))
        eb.size_hint_x = None; eb.width = S(72)
        row.add_widget(eb)
        card.add_widget(row)

        conf = spk.get('confidence', 0)
        card.add_widget(Lbl(f'Confidence: {conf:.1f}%', size=11, color='muted'))
        if spk.get('voice_profile_id'):
            card.add_widget(Lbl(f'🔗 Profile #{spk["voice_profile_id"]}',
                                size=10, color='accent'))
        card.add_widget(Gap(4))
        pb = ProgressBar(max=100, value=conf, size_hint_y=None, height=S(6))
        card.add_widget(pb)
        return card

    def _edit(self, spk):
        box = BoxLayout(orientation='vertical', padding=S(16), spacing=S(12))
        fill_c(box, ch('surface'))
        box.add_widget(Lbl(f'Rename "{spk["name"]}"', size=13))
        ti = StyledInput(text=spk['name'])
        box.add_widget(ti)
        box.add_widget(Gap(4))
        def _save(_):
            name = ti.text.strip()
            if not name: Toast('Name cannot be empty'); return
            import vocald_engine as engine
            engine.update_speaker_name(
                self._rec['id'], spk['speaker_index'], name)
            popup.dismiss()
            self.load(self._rec['id'])
        box.add_widget(PrimaryBtn('Save', on_press=_save, h_dp=46))
        popup = Popup(title='Edit Speaker', content=box,
                      size_hint=(0.9, None), height=S(240),
                      background_color=(*ch('surface')[:3], 1),
                      title_color=ch('text'), title_size=F(14),
                      separator_color=ch('border'))
        popup.open()

    def _back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current    = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — VOICE PROFILES
# ═══════════════════════════════════════════════════════════════════════════════
class ProfilesScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation='vertical')
        fill(root, 'bg')
        root.add_widget(TopBar('Voice Profiles', back_cb=self._back))
        sv = ScrollView(do_scroll_x=False)
        self._col = GridLayout(cols=1, size_hint_y=None,
                               padding=(S(12), S(10)), spacing=S(10))
        self._col.bind(minimum_height=self._col.setter('height'))
        sv.add_widget(self._col)
        root.add_widget(sv)
        self.add_widget(root)

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        import vocald_engine as engine
        self._col.clear_widgets()
        profiles = engine.get_voice_profiles()
        stats    = engine.get_db_stats()

        sc = Card()
        sc.add_widget(Lbl(
            f'📊  {stats["voice_profiles"]} profiles  ·  '
            f'{stats["recordings"]} recordings',
            size=13, bold=True, color='primary'))
        sc.add_widget(Gap(4))
        sc.add_widget(Lbl('Voice fingerprints stored locally on device.',
                          size=10.5, color='muted'))
        self._col.add_widget(sc)

        if not profiles:
            self._col.add_widget(Gap(16))
            self._col.add_widget(Lbl(
                'No profiles yet.\nAnalyse recordings to build the database.',
                size=12, color='muted', halign='center'))
            return

        for p in profiles:
            card = Card()
            row = BoxLayout(size_hint_y=None, height=S(28), spacing=S(6))
            row.add_widget(Lbl(f'#{p["id"]}  {p["name"]}',
                               size=13, bold=True, wrap=False))
            rp = Pill(f'{p["total_recordings"]} rec', color_key='accent', w_dp=70)
            row.add_widget(rp)
            card.add_widget(row)
            try:
                dates = (f'First: {p["first_seen"][:10]}'
                         f'  ·  Last: {p["last_seen"][:10]}')
            except Exception:
                dates = ''
            card.add_widget(Lbl(dates, size=10, color='muted', wrap=False))
            self._col.add_widget(card)

    def _back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current    = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 5 — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation='vertical')
        fill(root, 'bg')
        root.add_widget(TopBar('Settings', back_cb=self._back))
        sv = ScrollView(do_scroll_x=False)
        self._col = GridLayout(cols=1, size_hint_y=None,
                               padding=(S(12), S(10)), spacing=S(12))
        self._col.bind(minimum_height=self._col.setter('height'))
        sv.add_widget(self._col)
        root.add_widget(sv)
        self.add_widget(root)
        self._build()

    def _build(self):
        col = self._col
        fc = Card()
        fc.add_widget(Lbl('📁  Recordings Folder', size=12, bold=True,
                          color='primary'))
        fc.add_widget(Gap(4))
        self._flbl = Lbl(state.folder_path or 'Not set',
                         size=11, color='muted', wrap=True)
        fc.add_widget(self._flbl)
        col.add_widget(fc)
        col.add_widget(GhostBtn('Change Folder',
                                on_press=self._change_folder, h_dp=48))
        col.add_widget(Gap(8))

        about = Card()
        about.add_widget(Lbl('Vocald  v1.0', size=13, bold=True))
        about.add_widget(Gap(4))
        about.add_widget(Lbl('100% on-device  ·  No internet required',
                             size=11, color='muted'))
        col.add_widget(about)
        col.add_widget(Gap(12))

        col.add_widget(Lbl('⚠️  Danger Zone', size=11, bold=True,
                           color='danger'))
        col.add_widget(PrimaryBtn('🗑️  Clear All Data', color_key='danger',
                                  on_press=self._confirm_clear, h_dp=48))
        col.add_widget(Gap(12))

    def on_enter(self):
        self._flbl.text = state.folder_path or 'Not set'

    def _change_folder(self, *_):
        App.get_running_app().sm.get_screen('onboarding')._open_picker()

    def _confirm_clear(self, *_):
        ConfirmPopup(
            title       = '⚠️  Confirm',
            body        = ('Delete ALL recordings, speakers, and voice profiles?\n'
                           'This cannot be undone.'),
            ok_text     = 'DELETE ALL',
            ok_color_key= 'danger',
            on_ok       = self._clear_all,
        )

    def _clear_all(self):
        import sqlite3, vocald_engine as engine
        conn = sqlite3.connect(engine.DB_PATH)
        for t in ('speakers', 'recordings', 'voice_profiles'):
            conn.execute(f'DELETE FROM {t}')
        conn.commit(); conn.close()
        engine._processed_registry.clear()
        engine._save_processed_registry()
        Toast('All data cleared')

    def _back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current    = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════
class VocaldApp(App):
    title = 'Vocald'

    def build(self):
        self.store    = JsonStore(os.path.join(self.user_data_dir, 'settings.json'))
        state.app_dir = self.user_data_dir

        if platform == 'android':
            activity.bind(on_activity_result=self._on_result)

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        import vocald_engine as engine
        engine.init_engine(self.user_data_dir)

        self.sm = ScreenManager()
        for name, cls in [('onboarding', OnboardingScreen),
                          ('logs',       LogsScreen),
                          ('detail',     DetailScreen),
                          ('profiles',   ProfilesScreen),
                          ('settings',   SettingsScreen)]:
            self.sm.add_widget(cls(name=name))

        if self.store.exists('folder_path'):
            state.folder_path = self.store.get('folder_path')['value']

        self.sm.current = (
            'logs' if (self.store.exists('setup_done') and
                       self.store.get('setup_done')['value'])
            else 'onboarding')
        return self.sm

    def _on_result(self, req, result, data):
        if result != -1: return
        if req == 1001:
            uri = data.getData().toString()
            ob  = self.sm.get_screen('onboarding')
            ob.set_folder_from_android(uri)
            self.store.put('folder_path', value=ob._get_resolved_path(uri))
        elif req == 1002:
            uri = data.getData().toString()
            fp  = self._uri_path(uri)
            if fp: self.sm.get_screen('logs').upload_file_from_android(fp)

    @staticmethod
    def _uri_path(uri):
        try:
            if 'primary:' in uri:
                return '/sdcard/' + uri.split('primary:')[-1]
        except Exception:
            pass
        return uri


if __name__ == '__main__':
    VocaldApp().run()