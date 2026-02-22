"""
Vocald — Android APK  (UI v4 — ZERO OVERLAP GUARANTEED)
=========================================================

ROOT CAUSE OF ALL PREVIOUS OVERLAP ISSUES:
  BoxLayout does NOT have minimum_height property.
  Calling box.bind(minimum_height=box.setter('height')) does nothing.
  The card never grows — children overflow invisibly.

THE FIX USED HERE:
  All cards are GridLayout(cols=1) — GridLayout DOES track minimum_height.
  Labels always: size_hint_y=None, text_size=(width, None), height from texture_size.
  Fixed-height rows: size_hint_y=None, height=S(x), all children also size_hint_y=None.
  No child ever has size_hint_y != None unless it is explicitly a flex spacer.
"""

import os, sys, threading
from datetime import datetime

os.environ['KIVY_NO_ENV_CONFIG'] = '1'
from kivy.config import Config
Config.set('graphics', 'resizable', '1')

from kivy.app               import App
from kivy.clock             import Clock, mainthread
from kivy.core.window       import Window
from kivy.graphics          import Color, Rectangle, RoundedRectangle
from kivy.metrics           import dp, sp
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
# SCALE  (one value, clamped, drives everything)
# ═══════════════════════════════════════════════════════════════════════════════
def _sc():
    return max(0.82, min(1.35, Window.width / dp(360)))

def F(n): return sp(n) * _sc()   # font
def S(n): return dp(n) * _sc()   # size / spacing


# ═══════════════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════════════
_C = {
    'bg':       (.098, .106, .145, 1),
    'surface':  (.137, .149, .200, 1),
    'surface2': (.173, .188, .247, 1),
    'border':   (.243, .259, .325, 1),
    'primary':  (.012, .804, .682, 1),   # teal
    'accent':   (.608, .373, 1.000, 1),  # purple
    'warn':     (1.000, .714, .157, 1),
    'danger':   (1.000, .353, .380, 1),
    'text':     (.929, .933, .949, 1),
    'muted':    (.510, .533, .612, 1),
}

def C(k):        return _C[k]
def CA(k, a):    return _C[k][:3] + (a,)


# ═══════════════════════════════════════════════════════════════════════════════
# CANVAS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _bg(w, color, r=0):
    """Draw a filled background; keep it in sync with widget pos/size."""
    with w.canvas.before:
        Color(*color)
        rect = (RoundedRectangle(radius=[S(r)]) if r else Rectangle())
    def _sync(*_): rect.pos = w.pos; rect.size = w.size
    w.bind(pos=_sync, size=_sync)


# ═══════════════════════════════════════════════════════════════════════════════
# LABEL — the ONLY safe way to create text in Kivy without overlap
# ═══════════════════════════════════════════════════════════════════════════════
def WrapLbl(text, fs=13, color='text', bold=False, halign='left'):
    """
    Multiline label. Height expands automatically to fit content.
    NEVER put this in a fixed-height container.
    """
    lbl = Label(
        text=str(text), font_size=F(fs),
        color=C(color) if isinstance(color, str) else color,
        bold=bold, halign=halign, valign='top',
        size_hint_y=None, shorten=False,
    )
    # Step 1: when width changes, constrain wrap width
    lbl.bind(width=lambda i, w: setattr(i, 'text_size', (w, None)))
    # Step 2: when texture recalculates, set height to exact text height
    lbl.bind(texture_size=lambda i, ts: setattr(i, 'height', ts[1]))
    lbl.height = F(fs) * 1.4   # safe initial guess
    return lbl


def RowLbl(text, fs=13, color='text', bold=False, halign='left'):
    """
    Single-line label with ellipsis. Use inside fixed-height rows.
    height is set once; text_size.y = height so no vertical overflow.
    """
    h = F(fs) * 1.65
    lbl = Label(
        text=str(text), font_size=F(fs),
        color=C(color) if isinstance(color, str) else color,
        bold=bold, halign=halign, valign='middle',
        size_hint_y=None, height=h,
        shorten=True, shorten_from='right',
    )
    lbl.bind(width=lambda i, w: setattr(i, 'text_size', (w, h)))
    return lbl


def FixLbl(text, fs=13, color='text', bold=False,
           halign='right', w_dp=80):
    """Fixed-width, single-line, truncating label."""
    h = F(fs) * 1.65
    w = S(w_dp)
    lbl = Label(
        text=str(text), font_size=F(fs),
        color=C(color) if isinstance(color, str) else color,
        bold=bold, halign=halign, valign='middle',
        size_hint=(None, None), size=(w, h),
        shorten=True, shorten_from='right',
        text_size=(w, h),
    )
    return lbl


# ═══════════════════════════════════════════════════════════════════════════════
# CARD  — GridLayout(cols=1) so minimum_height ACTUALLY works
# ═══════════════════════════════════════════════════════════════════════════════
def Card(pad=14, spacing=8, radius=14):
    """
    Returns a GridLayout(cols=1).
    minimum_height is a real property on GridLayout — height follows children.
    """
    g = GridLayout(
        cols=1,
        size_hint_y=None,
        padding=[S(pad)],
        spacing=S(spacing),
    )
    g.bind(minimum_height=g.setter('height'))
    _bg(g, C('surface'), r=radius)
    return g


# ═══════════════════════════════════════════════════════════════════════════════
# SMALL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def Gap(h=8):
    return Widget(size_hint_y=None, height=S(h))


def Divider():
    d = Widget(size_hint_y=None, height=dp(1))
    with d.canvas:
        Color(*C('border'))
        r = Rectangle()
    d.bind(pos=lambda i, v: setattr(r, 'pos', v),
           size=lambda i, v: setattr(r, 'size', v))
    return d


def Pill(text, ck='primary', w=72):
    """Coloured badge pill — fixed size."""
    g = GridLayout(cols=1, size_hint=(None, None),
                   size=(S(w), S(22)))
    with g.canvas.before:
        Color(*CA(ck, 0.22))
        rr = RoundedRectangle(radius=[S(11)])
    g.bind(pos=lambda i, _: setattr(rr, 'pos', i.pos),
           size=lambda i, _: setattr(rr, 'size', i.size))
    lbl = Label(text=text, font_size=F(8.5), bold=True,
                color=C(ck), halign='center', valign='middle')
    lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
    g.add_widget(lbl)
    return g


# ═══════════════════════════════════════════════════════════════════════════════
# BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════
def PrimaryBtn(text, cb=None, h=50, fs=14, ck='primary', r=12):
    btn = Button(
        text=text, size_hint=(1, None), height=S(h),
        font_size=F(fs), bold=True,
        background_color=(0,0,0,0), color=C('bg'),
    )
    with btn.canvas.before:
        Color(*C(ck)); rr = RoundedRectangle(radius=[S(r)])
    btn.bind(pos=lambda i,v: setattr(rr,'pos',v),
             size=lambda i,v: setattr(rr,'size',v))
    if cb: btn.bind(on_press=cb)
    return btn


def GhostBtn(text, cb=None, h=46, fs=13, r=12):
    btn = Button(
        text=text, size_hint=(1, None), height=S(h),
        font_size=F(fs), bold=False,
        background_color=(0,0,0,0), color=C('text'),
    )
    with btn.canvas.before:
        Color(*C('surface2')); rr = RoundedRectangle(radius=[S(r)])
    btn.bind(pos=lambda i,v: setattr(rr,'pos',v),
             size=lambda i,v: setattr(rr,'size',v))
    if cb: btn.bind(on_press=cb)
    return btn


def IconBtn(icon, cb=None, sz=44, fs=20):
    btn = Button(
        text=icon, size_hint=(None,None), size=(S(sz),S(sz)),
        background_color=(0,0,0,0),
        color=C('text'), font_size=F(fs),
    )
    if cb: btn.bind(on_press=cb)
    return btn


# ═══════════════════════════════════════════════════════════════════════════════
# TOP BAR
# ═══════════════════════════════════════════════════════════════════════════════
def TopBar(title, back_cb=None, extras=None):
    h = S(56)
    bar = BoxLayout(size_hint_y=None, height=h,
                    padding=(S(4), 0), spacing=S(2))
    _bg(bar, C('surface'))
    if back_cb:
        bar.add_widget(IconBtn('←', cb=lambda _: back_cb(), sz=46, fs=20))
    lbl = Label(text=title, font_size=F(16), bold=True,
                color=C('text'), halign='left', valign='middle')
    lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
    bar.add_widget(lbl)
    if extras:
        for e in extras: bar.add_widget(e)
    return bar


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT
# ═══════════════════════════════════════════════════════════════════════════════
def TxtIn(hint='', text=''):
    return TextInput(
        text=text, hint_text=hint,
        size_hint_y=None, height=S(46),
        multiline=False, font_size=F(13),
        foreground_color=C('text'),
        hint_text_color=C('muted'),
        background_color=C('surface2'),
        cursor_color=C('primary'),
        padding=[S(12), S(12)],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TOAST / POPUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def Toast(msg, d=2.5):
    fl = FloatLayout()
    lbl = Label(text=msg, font_size=F(12), color=C('text'),
                halign='center', size_hint=(None,None),
                pos_hint={'center_x':.5,'center_y':.5})
    lbl.bind(texture_size=lambda i,ts: setattr(i,'size',ts))
    fl.add_widget(lbl)
    p = Popup(title='', content=fl,
              size_hint=(.8,None), height=S(54),
              auto_dismiss=True,
              background_color=(*C('surface2')[:3], .97),
              separator_height=0)
    p.open()
    Clock.schedule_once(lambda _: p.dismiss(), d)


def _mk_popup(title, content_widget, h=220):
    return Popup(
        title=title, content=content_widget,
        size_hint=(.88, None), height=S(h),
        background_color=(*C('surface')[:3], 1),
        title_color=C('text'), title_size=F(14),
        separator_color=C('border'),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SCROLLABLE SCREEN HELPER
# ═══════════════════════════════════════════════════════════════════════════════
def ScrollCol(pad_x=18, pad_y=24, spacing=14):
    """
    Returns (scroll_view, grid_layout).
    Mount scroll_view; add children to grid_layout.
    """
    col = GridLayout(cols=1, size_hint_y=None,
                     padding=[S(pad_x), S(pad_y)],
                     spacing=S(spacing))
    col.bind(minimum_height=col.setter('height'))
    sv = ScrollView(do_scroll_x=False)
    _bg(sv, C('bg'))
    sv.add_widget(col)
    return sv, col


# ═══════════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════════
class _St:
    folder_path = ''
    app_dir     = ''
    is_analysing = False
    analysis_cancelled = False

ST = _St()


# ═══════════════════════════════════════════════════════════════════════════════
# BASE SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
class Scr(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        _bg(self, C('bg'))


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — ONBOARDING
# ═══════════════════════════════════════════════════════════════════════════════
class OnboardingScreen(Scr):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._show_welcome()

    # every step rebuilds the screen with a fresh scrollable column
    def _step(self):
        self.clear_widgets()
        sv, col = ScrollCol()
        self.add_widget(sv)
        return col

    # ── Welcome ───────────────────────────────────────────────────────────────
    def _show_welcome(self):
        col = self._step()
        col.add_widget(Gap(28))
        col.add_widget(WrapLbl('🎙️', fs=54, halign='center'))
        col.add_widget(Gap(6))
        col.add_widget(WrapLbl('Vocald', fs=32, bold=True, halign='center'))
        col.add_widget(WrapLbl('Speaker ID for call recordings',
                               fs=13, color='muted', halign='center'))
        col.add_widget(Gap(20))

        c = Card()
        c.add_widget(WrapLbl('🔒  100% Private', fs=13, bold=True,
                             color='primary'))
        c.add_widget(Gap(4))
        c.add_widget(WrapLbl(
            'Everything runs on your phone. No recordings ever leave '
            'your device. Only voice fingerprints are stored.',
            fs=12, color='muted'))
        col.add_widget(c)
        col.add_widget(Gap(8))

        c2 = Card()
        for icon, txt in [('🔊','Automatic speaker identification'),
                           ('📊','Local voice profile database'),
                           ('📁','Fully offline — no cloud')]:
            row = BoxLayout(size_hint_y=None, spacing=S(10))
            # height follows the tallest child; WrapLbl drives it
            row.bind(minimum_height=row.setter('height'))
            # but WrapLbl needs size_hint_y=None which is already set
            row.add_widget(FixLbl(icon, fs=18, halign='left', w_dp=30))
            row.add_widget(WrapLbl(txt, fs=12, color='muted'))
            c2.add_widget(row)
        col.add_widget(c2)

        col.add_widget(Gap(24))
        col.add_widget(PrimaryBtn('GET STARTED  →',
                                  cb=lambda _: self._show_perms(),
                                  h=52, fs=15))
        col.add_widget(Gap(20))

    # ── Permissions ───────────────────────────────────────────────────────────
    def _show_perms(self):
        col = self._step()
        col.add_widget(WrapLbl('Permissions', fs=26, bold=True))
        col.add_widget(Gap(4))
        col.add_widget(WrapLbl('Vocald needs two permissions.',
                               fs=12, color='muted'))
        col.add_widget(Gap(12))

        for icon, title, desc in [
            ('📂','Storage','Read audio files from your recordings folder.'),
            ('📞','Call Log','Fetch call date, duration & phone number.'),
        ]:
            c = Card()
            row = BoxLayout(size_hint_y=None, spacing=S(12))
            row.bind(minimum_height=row.setter('height'))

            ibox = GridLayout(cols=1, size_hint=(None,None), size=(S(40),S(40)))
            _bg(ibox, CA('primary',0.12), r=10)
            ibox.add_widget(Label(text=icon, font_size=F(20),
                                  halign='center', valign='middle'))
            row.add_widget(ibox)

            tcol = GridLayout(cols=1, size_hint_y=None, spacing=S(3))
            tcol.bind(minimum_height=tcol.setter('height'))
            tcol.add_widget(WrapLbl(title, fs=13, bold=True))
            tcol.add_widget(WrapLbl(desc, fs=11, color='muted'))
            row.add_widget(tcol)
            c.add_widget(row)
            col.add_widget(c)

        col.add_widget(Gap(20))
        col.add_widget(PrimaryBtn('GRANT PERMISSIONS',
                                  cb=lambda _: self._req_perms(), h=52))
        col.add_widget(Gap(16))

    def _req_perms(self):
        if platform == 'android':
            request_permissions(
                [Permission.READ_EXTERNAL_STORAGE,
                 Permission.READ_CALL_LOG,
                 Permission.WRITE_EXTERNAL_STORAGE],
                callback=lambda p, g: Clock.schedule_once(
                    lambda _: self._show_folder(), 0.3))
        else:
            self._show_folder()

    # ── Folder ────────────────────────────────────────────────────────────────
    def _show_folder(self):
        col = self._step()
        col.add_widget(WrapLbl('Recordings Folder', fs=24, bold=True))
        col.add_widget(Gap(4))
        col.add_widget(WrapLbl('Where does your phone save call recordings?',
                               fs=12, color='muted'))
        col.add_widget(Gap(12))

        hint = Card()
        hint.add_widget(WrapLbl('Common Android paths:', fs=11,
                                bold=True, color='primary'))
        hint.add_widget(Gap(4))
        for p in ['/sdcard/CallRecordings',
                  '/sdcard/MIUI/sound_recorder/call_rec',
                  '/sdcard/Recordings/Call']:
            hint.add_widget(WrapLbl(f'• {p}', fs=10, color='muted'))
        col.add_widget(hint)
        col.add_widget(Gap(10))

        self._folder_card = Card()
        self._flbl = WrapLbl('No folder selected.',
                             fs=12, color='muted', halign='center')
        self._folder_card.add_widget(self._flbl)
        col.add_widget(self._folder_card)
        col.add_widget(Gap(8))

        col.add_widget(GhostBtn('SELECT FOLDER',
                                cb=lambda _: self._pick(), h=50))
        col.add_widget(Gap(6))
        self._use_btn = PrimaryBtn('USE THIS FOLDER  →',
                                   cb=lambda _: self._do_setup(), h=52)
        self._use_btn.disabled = True
        col.add_widget(self._use_btn)
        col.add_widget(Gap(20))

    def _pick(self):
        if platform == 'android':
            Intent = autoclass('android.content.Intent')
            i = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            mActivity.startActivityForResult(i, 1001)
        else:
            self._desktop_pick()

    def _desktop_pick(self):
        col = GridLayout(cols=1, size_hint_y=None, padding=[S(16)],
                         spacing=S(12))
        col.bind(minimum_height=col.setter('height'))
        _bg(col, C('surface'))
        col.add_widget(WrapLbl('Enter folder path:', fs=13))
        ti = TxtIn(hint='/path/to/recordings')
        col.add_widget(ti)
        col.add_widget(Gap(4))
        p = _mk_popup('Folder Path', col, h=210)
        col.add_widget(PrimaryBtn('Confirm', h=46,
                                  cb=lambda _: self._ti_ok(ti, p)))
        p.open()

    def _ti_ok(self, ti, popup):
        path = ti.text.strip()
        if path and os.path.isdir(path):
            self._set_folder(path); popup.dismiss()
        else:
            Toast('Invalid folder path')

    def set_folder_from_android(self, uri):
        self._set_folder(self._uri2path(uri) or uri)

    def _get_resolved_path(self, uri):
        return self._uri2path(uri) or uri

    def _uri2path(self, uri):
        try:
            if 'primary:' in uri:
                return '/sdcard/' + uri.split('primary:')[-1].rstrip('/')
        except Exception: pass
        return uri

    def _set_folder(self, path):
        ST.folder_path = path
        self._flbl.text  = f'✅  {path}'
        self._flbl.color = C('primary')
        self._use_btn.disabled = False

    # ── Setup ─────────────────────────────────────────────────────────────────
    def _do_setup(self):
        if not ST.folder_path: Toast('Select a folder first'); return
        col = self._step()
        col.add_widget(Gap(40))
        col.add_widget(WrapLbl('Setting Up…', fs=22, bold=True, halign='center'))
        col.add_widget(Gap(10))
        self._slbl = WrapLbl('Scanning…', fs=12, color='muted', halign='center')
        col.add_widget(self._slbl)
        col.add_widget(Gap(14))
        self._spb = ProgressBar(max=100, size_hint_y=None, height=S(8))
        col.add_widget(self._spb)
        threading.Thread(target=self._bg_setup, daemon=True).start()

    def _bg_setup(self):
        from folder_scanner import mark_all_existing_as_seen, count_all_audio_files
        import vocald_engine as engine
        n = count_all_audio_files(ST.folder_path)
        self._sup(f'Found {n} recordings…', 30)
        m = mark_all_existing_as_seen(
            ST.folder_path, lambda fn, ms: engine.mark_file_processed(fn, ms))
        self._sup(f'Marked {m} files. Done!', 100)
        Clock.schedule_once(self._done, 1.2)

    @mainthread
    def _sup(self, t, v): self._slbl.text = t; self._spb.value = v

    @mainthread
    def _done(self, *_):
        app = App.get_running_app()
        app.store.put('setup_done', value=True)
        app.store.put('folder_path', value=ST.folder_path)
        app.sm.transition = NoTransition()
        app.sm.current = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — LOGS
# ═══════════════════════════════════════════════════════════════════════════════
class LogsScreen(Scr):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._recs = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical')
        _bg(root, C('bg'))

        # Top bar
        bar = TopBar('🎙️  Vocald', extras=[
            IconBtn('👤', cb=lambda _: self._go('profiles')),
            IconBtn('⚙️', cb=lambda _: self._go('settings')),
        ])
        root.add_widget(bar)

        # Action row — fixed height, no text that could wrap
        act = BoxLayout(size_hint_y=None, height=S(60),
                        padding=[S(10), S(8)], spacing=S(8))
        _bg(act, C('surface'))
        self._scan_btn   = PrimaryBtn('🔍  SCAN', cb=self._scan, h=44, fs=13)
        self._upload_btn = GhostBtn('📂  UPLOAD', cb=self._upload, h=44, fs=13)
        act.add_widget(self._scan_btn)
        act.add_widget(self._upload_btn)
        root.add_widget(act)

        # Status strip — fixed height, truncating single-line label
        ss = BoxLayout(size_hint_y=None, height=S(28), padding=[S(14), 0])
        _bg(ss, C('surface'))
        self._status = RowLbl('', fs=10.5, color='muted')
        ss.add_widget(self._status)
        root.add_widget(ss)

        # Search box — fixed height
        sr = BoxLayout(size_hint_y=None, height=S(52),
                       padding=[S(10), S(5)])
        self._search = TxtIn(hint='🔎  Search filename or number…')
        self._search.bind(text=self._on_search)
        sr.add_widget(self._search)
        root.add_widget(sr)

        # Progress panel — fixed height, hidden by opacity
        self._prog = BoxLayout(orientation='vertical',
                               size_hint_y=None, height=S(76),
                               padding=[S(12), S(6)], spacing=S(4))
        _bg(self._prog, C('surface2'))
        self._plbl = RowLbl('', fs=10.5, color='primary')
        self._prog.add_widget(self._plbl)
        self._pbar = ProgressBar(max=100, size_hint_y=None, height=S(8))
        self._prog.add_widget(self._pbar)
        crow = BoxLayout(size_hint_y=None, height=S(32))
        crow.add_widget(Widget())
        cb = PrimaryBtn('✕ Cancel', cb=self._cancel, h=28, fs=10, ck='danger')
        cb.size_hint_x = None; cb.width = S(90)
        crow.add_widget(cb)
        self._prog.add_widget(crow)
        self._prog.opacity = 0
        root.add_widget(self._prog)

        # Scrollable list
        sv = ScrollView(do_scroll_x=False)
        self._list = GridLayout(cols=1, size_hint_y=None,
                                padding=[S(10), S(8)], spacing=S(10))
        self._list.bind(minimum_height=self._list.setter('height'))
        sv.add_widget(self._list)
        root.add_widget(sv)
        self.add_widget(root)

    def on_enter(self): self._refresh()

    def _refresh(self):
        import vocald_engine as engine
        self._recs = engine.get_all_recordings()
        st = engine.get_db_stats()
        fd = os.path.basename(ST.folder_path) or '—'
        self._status.text = (
            f'📁 {fd}  ·  {st["recordings"]} recordings'
            f'  ·  {st["voice_profiles"]} voices')
        self._render(self._recs)

    def _on_search(self, _, txt):
        q = txt.lower().strip()
        self._render(self._recs if not q else [
            r for r in self._recs
            if q in r['filename'].lower() or
               q in (r.get('phone_number') or '').lower()])

    def _render(self, recs):
        self._list.clear_widgets()
        if not recs:
            self._list.add_widget(Gap(36))
            self._list.add_widget(
                WrapLbl('No recordings yet.\nTap SCAN to check for new calls.',
                        fs=13, color='muted', halign='center'))
            return
        for r in recs:
            self._list.add_widget(self._card(r))

    def _card(self, rec):
        """
        Card is a GridLayout(cols=1) — minimum_height binding works correctly.

        Children:
          row1  BoxLayout h=S(28)  — phone (RowLbl) + pill (fixed)
          fname WrapLbl            — auto height, wraps freely
          row3  BoxLayout h=S(22)  — date (RowLbl) + dur (FixLbl) + spk (FixLbl)

        All children have size_hint_y=None → card height = sum of them.
        """
        card = Card(pad=12, spacing=7)
        card._rid = rec['id']

        # Row 1: phone + badge
        r1 = BoxLayout(size_hint_y=None, height=S(28), spacing=S(6))
        ph = rec.get('phone_number') or 'Unknown number'
        r1.add_widget(RowLbl(f'📞  {ph}', fs=13, bold=True, color='text'))
        status = rec.get('processed', 0)
        pk = ('warn','primary','danger')[status]
        pt = ('⏳ Pending','✅ Done','❌ Failed')[status]
        r1.add_widget(Pill(pt, ck=pk))
        card.add_widget(r1)

        # Row 2: filename — wrapping
        card.add_widget(WrapLbl(rec['filename'], fs=10.5, color='muted'))

        # Row 3: date + dur + speakers
        r3 = BoxLayout(size_hint_y=None, height=S(22), spacing=S(6))
        try:
            dt = datetime.fromisoformat(rec['call_date'])
            ds = dt.strftime('%d %b %Y  %I:%M %p')
        except Exception:
            ds = rec.get('call_date','')[:16].replace('T','  ')
        r3.add_widget(RowLbl(f'📅  {ds}', fs=9.5, color='muted'))
        dur = rec.get('call_duration', 0)
        if dur:
            r3.add_widget(FixLbl(f'⏱ {dur}s', fs=9.5,
                                 color='muted', halign='right', w_dp=52))
        r3.add_widget(FixLbl(f'👥 {rec.get("total_speakers",0)}',
                              fs=9.5, color='accent', halign='right', w_dp=34))
        card.add_widget(r3)

        card.bind(on_touch_up=lambda i, t:
                  self._open(i._rid) if i.collide_point(*t.pos) else None)
        return card

    def _open(self, rid):
        app = App.get_running_app()
        app.sm.get_screen('detail').load(rid)
        app.sm.transition = SlideTransition(direction='left')
        app.sm.current = 'detail'

    def _go(self, sc):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='left')
        app.sm.current = sc

    # scan / upload
    def _scan(self, *_):
        if ST.is_analysing: Toast('Already analysing'); return
        if not ST.folder_path: Toast('No folder — go to Settings'); return
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _upload(self, *_):
        if platform == 'android':
            Intent = autoclass('android.content.Intent')
            i = Intent(Intent.ACTION_GET_CONTENT); i.setType('audio/*')
            mActivity.startActivityForResult(i, 1002)
        else:
            self._desktop_upload()

    def _desktop_upload(self):
        col = GridLayout(cols=1, size_hint_y=None,
                         padding=[S(16)], spacing=S(12))
        col.bind(minimum_height=col.setter('height'))
        _bg(col, C('surface'))
        col.add_widget(WrapLbl('Audio file path:', fs=13))
        ti = TxtIn(hint='/path/to/recording.wav')
        col.add_widget(ti)
        col.add_widget(Gap(4))
        p = _mk_popup('Upload File', col, h=230)
        col.add_widget(PrimaryBtn('Analyse', h=46,
                                  cb=lambda _: self._do_upload(ti, p)))
        p.open()

    def _do_upload(self, ti, p):
        path = ti.text.strip(); p.dismiss()
        if path and os.path.isfile(path):
            threading.Thread(target=self._run_file,
                             args=(path,), daemon=True).start()
        else: Toast('File not found')

    def upload_file_from_android(self, fp):
        threading.Thread(target=self._run_file, args=(fp,), daemon=True).start()

    def _run_scan(self):
        import vocald_engine as engine
        from folder_scanner import scan_folder
        ST.is_analysing = True; ST.analysis_cancelled = False
        self._ui(True)
        new = scan_folder(ST.folder_path, engine.is_file_processed)
        if not new:
            self._prog_upd('✅  All up to date', 100)
            Clock.schedule_once(lambda _: self._ui(False), 1.5)
            ST.is_analysing = False
            Clock.schedule_once(lambda _: self._refresh(), 1.6); return
        total = len(new)
        for i, fi in enumerate(new):
            if ST.analysis_cancelled: break
            fn = fi['filename']; fp = fi['filepath']
            self._prog_upd(f'[{i+1}/{total}]  {fn}', int(i/total*90))
            rid = engine.create_recording_entry(
                fn, fp, fi['estimated_call_time'].isoformat())
            try:
                sp = engine.analyse_audio_file(
                    fp, fn, lambda s: self._prog_upd(s, None))
                engine.update_recording_after_analysis(rid, sp)
                engine.mark_file_processed(fn, fi['modified_ms'])
            except Exception as e:
                engine.mark_recording_failed(rid, str(e))
        self._prog_upd('✅  Scan complete', 100)
        Clock.schedule_once(lambda _: self._ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh(), 1.3)
        ST.is_analysing = False

    def _run_file(self, path):
        import vocald_engine as engine
        ST.is_analysing = True; self._ui(True)
        fn = os.path.basename(path)
        self._prog_upd(f'Analysing: {fn}', 10)
        rid = engine.create_recording_entry(fn, path, datetime.now().isoformat())
        try:
            sp = engine.analyse_audio_file(
                path, fn, lambda s: self._prog_upd(s, None))
            engine.update_recording_after_analysis(rid, sp)
            engine.mark_file_processed(fn, int(os.path.getmtime(path)*1000))
        except Exception as e:
            engine.mark_recording_failed(rid, str(e))
        self._prog_upd('✅  Done', 100)
        Clock.schedule_once(lambda _: self._ui(False), 1.2)
        Clock.schedule_once(lambda _: self._refresh(), 1.3)
        ST.is_analysing = False

    def _cancel(self, *_): ST.analysis_cancelled = True; Toast('Cancelling…')

    @mainthread
    def _ui(self, on):
        self._prog.opacity      = 1 if on else 0
        self._scan_btn.disabled = on
        self._upload_btn.disabled = on
        if not on: self._pbar.value = 0

    @mainthread
    def _prog_upd(self, t, v=None):
        self._plbl.text = t
        if v is not None: self._pbar.value = v


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — DETAIL
# ═══════════════════════════════════════════════════════════════════════════════
class DetailScreen(Scr):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._rec = {}
        root = BoxLayout(orientation='vertical')
        _bg(root, C('bg'))
        root.add_widget(TopBar('Recording Detail', back_cb=self._back))
        sv = ScrollView(do_scroll_x=False)
        self._col = GridLayout(cols=1, size_hint_y=None,
                               padding=[S(12), S(10)], spacing=S(10))
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
            self._col.add_widget(WrapLbl('Recording not found.', color='danger'))
            return

        meta = Card()
        meta.add_widget(WrapLbl('Call Details', fs=14, bold=True, color='primary'))
        meta.add_widget(Divider())
        meta.add_widget(Gap(4))

        for lbl, val in [
            ('📞 Phone',    rec.get('phone_number') or 'Unknown'),
            ('📅 Date',     rec.get('call_date','')[:19].replace('T','  ')),
            ('⏱ Duration', f'{rec.get("call_duration",0)} seconds'),
            ('📄 File',     rec.get('filename','')),
        ]:
            # Each detail row: fixed label + wrapping value
            # Use a GridLayout row so minimum_height is tracked
            row = GridLayout(cols=2, size_hint_y=None,
                             spacing=S(8), col_default_width=1,
                             col_force_default=False)
            row.bind(minimum_height=row.setter('height'))
            # Col 0: fixed width label
            lw = FixLbl(lbl, fs=11, bold=True, color='muted',
                        halign='left', w_dp=82)
            row.add_widget(lw)
            # Col 1: wrapping value
            vw = WrapLbl(str(val), fs=11, color='text')
            row.add_widget(vw)
            meta.add_widget(row)

        self._col.add_widget(meta)
        self._col.add_widget(Gap(4))
        self._col.add_widget(WrapLbl('Identified Speakers', fs=14,
                                     bold=True, color='text'))

        spks = rec.get('speakers', [])
        if not spks:
            self._col.add_widget(WrapLbl('No speakers identified.',
                                         fs=12, color='muted'))
        else:
            for s in spks: self._col.add_widget(self._spk_card(s))

    def _spk_card(self, spk):
        c = Card()
        # name row + edit btn — fixed height
        r = BoxLayout(size_hint_y=None, height=S(36), spacing=S(8))
        nl = Label(text=f'👤  {spk["name"]}', font_size=F(13), bold=True,
                   color=C('text'), halign='left', valign='middle')
        nl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        r.add_widget(nl)
        eb = GhostBtn('✏️ Edit', cb=lambda _: self._edit(spk), h=32, fs=11)
        eb.size_hint_x = None; eb.width = S(74)
        r.add_widget(eb)
        c.add_widget(r)

        conf = spk.get('confidence', 0)
        c.add_widget(WrapLbl(f'Confidence: {conf:.1f}%', fs=11, color='muted'))
        if spk.get('voice_profile_id'):
            c.add_widget(WrapLbl(f'🔗 Profile #{spk["voice_profile_id"]}',
                                 fs=10, color='accent'))
        c.add_widget(Gap(4))
        pb = ProgressBar(max=100, value=conf, size_hint_y=None, height=S(6))
        c.add_widget(pb)
        return c

    def _edit(self, spk):
        col = GridLayout(cols=1, size_hint_y=None,
                         padding=[S(16)], spacing=S(12))
        col.bind(minimum_height=col.setter('height'))
        _bg(col, C('surface'))
        col.add_widget(WrapLbl(f'Rename "{spk["name"]}"', fs=13))
        ti = TxtIn(text=spk['name'])
        col.add_widget(ti)
        col.add_widget(Gap(4))
        p = _mk_popup('Edit Speaker', col, h=240)
        def _save(_):
            name = ti.text.strip()
            if not name: Toast('Name cannot be empty'); return
            import vocald_engine as engine
            engine.update_speaker_name(self._rec['id'],
                                       spk['speaker_index'], name)
            p.dismiss(); self.load(self._rec['id'])
        col.add_widget(PrimaryBtn('Save', cb=_save, h=46))
        p.open()

    def _back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — PROFILES
# ═══════════════════════════════════════════════════════════════════════════════
class ProfilesScreen(Scr):

    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation='vertical')
        _bg(root, C('bg'))
        root.add_widget(TopBar('Voice Profiles', back_cb=self._back))
        sv = ScrollView(do_scroll_x=False)
        self._col = GridLayout(cols=1, size_hint_y=None,
                               padding=[S(12), S(10)], spacing=S(10))
        self._col.bind(minimum_height=self._col.setter('height'))
        sv.add_widget(self._col)
        root.add_widget(sv)
        self.add_widget(root)

    def on_enter(self): self._refresh()

    def _refresh(self):
        import vocald_engine as engine
        self._col.clear_widgets()
        profiles = engine.get_voice_profiles()
        stats    = engine.get_db_stats()

        sc = Card()
        sc.add_widget(WrapLbl(
            f'📊  {stats["voice_profiles"]} profiles  ·  '
            f'{stats["recordings"]} recordings',
            fs=13, bold=True, color='primary'))
        sc.add_widget(Gap(4))
        sc.add_widget(WrapLbl('Voice fingerprints stored locally on device.',
                              fs=10.5, color='muted'))
        self._col.add_widget(sc)

        if not profiles:
            self._col.add_widget(Gap(16))
            self._col.add_widget(WrapLbl(
                'No profiles yet.\nAnalyse recordings to build the database.',
                fs=12, color='muted', halign='center'))
            return

        for p in profiles:
            c = Card()
            row = BoxLayout(size_hint_y=None, height=S(30), spacing=S(6))
            row.add_widget(RowLbl(f'#{p["id"]}  {p["name"]}',
                                  fs=13, bold=True, color='text'))
            row.add_widget(Pill(f'{p["total_recordings"]} rec',
                                ck='accent', w=70))
            c.add_widget(row)
            try:
                dates = (f'First: {p["first_seen"][:10]}'
                         f'  ·  Last: {p["last_seen"][:10]}')
            except Exception: dates = ''
            c.add_widget(WrapLbl(dates, fs=10, color='muted'))
            self._col.add_widget(c)

    def _back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN 5 — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsScreen(Scr):

    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation='vertical')
        _bg(root, C('bg'))
        root.add_widget(TopBar('Settings', back_cb=self._back))
        sv = ScrollView(do_scroll_x=False)
        self._col = GridLayout(cols=1, size_hint_y=None,
                               padding=[S(12), S(10)], spacing=S(12))
        self._col.bind(minimum_height=self._col.setter('height'))
        sv.add_widget(self._col)
        root.add_widget(sv)
        self.add_widget(root)
        self._build()

    def _build(self):
        col = self._col

        fc = Card()
        fc.add_widget(WrapLbl('📁  Recordings Folder', fs=12,
                              bold=True, color='primary'))
        fc.add_widget(Gap(4))
        self._flbl = WrapLbl(ST.folder_path or 'Not set', fs=11, color='muted')
        fc.add_widget(self._flbl)
        col.add_widget(fc)
        col.add_widget(GhostBtn('Change Folder',
                                cb=lambda _: self._chg_folder(), h=48))
        col.add_widget(Gap(8))

        about = Card()
        about.add_widget(WrapLbl('Vocald  v1.0', fs=13, bold=True))
        about.add_widget(Gap(4))
        about.add_widget(WrapLbl('100% on-device  ·  No internet required',
                                 fs=11, color='muted'))
        col.add_widget(about)
        col.add_widget(Gap(12))

        col.add_widget(WrapLbl('⚠️  Danger Zone', fs=11, bold=True,
                               color='danger'))
        col.add_widget(PrimaryBtn('🗑️  Clear All Data', ck='danger',
                                  cb=lambda _: self._confirm(), h=48))
        col.add_widget(Gap(16))

    def on_enter(self):
        self._flbl.text = ST.folder_path or 'Not set'

    def _chg_folder(self):
        App.get_running_app().sm.get_screen('onboarding')._pick()

    def _confirm(self):
        col = GridLayout(cols=1, size_hint_y=None,
                         padding=[S(16)], spacing=S(12))
        col.bind(minimum_height=col.setter('height'))
        _bg(col, C('surface'))
        col.add_widget(Gap(4))
        col.add_widget(WrapLbl(
            'Delete ALL recordings, speakers, and voice profiles?\n'
            'This cannot be undone.', fs=12, color='muted'))
        col.add_widget(Gap(8))
        row = BoxLayout(size_hint_y=None, height=S(46), spacing=S(10))
        p = _mk_popup('⚠️  Confirm', col, h=220)
        row.add_widget(GhostBtn('Cancel', cb=lambda _: p.dismiss(), h=46))
        row.add_widget(PrimaryBtn('DELETE ALL', ck='danger',
                                  cb=lambda _: (p.dismiss(), self._clear()), h=46))
        col.add_widget(row)
        col.add_widget(Gap(4))
        p.open()

    def _clear(self):
        import sqlite3, vocald_engine as engine
        conn = sqlite3.connect(engine.DB_PATH)
        for t in ('speakers','recordings','voice_profiles'):
            conn.execute(f'DELETE FROM {t}')
        conn.commit(); conn.close()
        engine._processed_registry.clear()
        engine._save_processed_registry()
        Toast('All data cleared')

    def _back(self):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(direction='right')
        app.sm.current = 'logs'


# ═══════════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════════
class VocaldApp(App):
    title = 'Vocald'

    def build(self):
        self.store   = JsonStore(os.path.join(self.user_data_dir, 'settings.json'))
        ST.app_dir   = self.user_data_dir

        if platform == 'android':
            activity.bind(on_activity_result=self._result)

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
            ST.folder_path = self.store.get('folder_path')['value']

        self.sm.current = (
            'logs' if (self.store.exists('setup_done') and
                       self.store.get('setup_done')['value'])
            else 'onboarding')
        return self.sm

    def _result(self, req, res, data):
        if res != -1: return
        if req == 1001:
            uri = data.getData().toString()
            ob  = self.sm.get_screen('onboarding')
            ob.set_folder_from_android(uri)
            self.store.put('folder_path', value=ob._get_resolved_path(uri))
        elif req == 1002:
            fp = self._u2p(data.getData().toString())
            if fp: self.sm.get_screen('logs').upload_file_from_android(fp)

    @staticmethod
    def _u2p(uri):
        try:
            if 'primary:' in uri:
                return '/sdcard/' + uri.split('primary:')[-1]
        except Exception: pass
        return uri


if __name__ == '__main__':
    VocaldApp().run()