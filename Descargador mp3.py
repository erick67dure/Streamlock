"""
StreamLock — Reproductor Local de Alta Fidelidad & Gestor de Descargas
Edición: Premium Dark Minimalist (3-Panel Architecture)
========================================================================
• Fondo Primario: Deep Pitch Black (#000000)
• Fondo Secundario: Dark Graphite / Charcoal (#121212)
• Acento: Deep Purple (#7C4DFF) estrictamente para estados activos,
  progreso y llamadas a la acción principales.
• Geometría: Soft Corners controladas (entre 4px y 8px).
• Enfoque Local: Micro-badges "LOCAL", "DESCARGADO", "OFFLINE".
"""
import customtkinter as ctk
import pygame
import os
import random
import re
import threading
import concurrent.futures
import sys

# ══════════════════════════════════════════════════════════════════════
#  SISTEMA DE DISEÑO: BRANDING & PALETA DE COLORES "PREMIUM DARK"
# ══════════════════════════════════════════════════════════════════════
# Fondo Primario: Negro Profundo para las ventanas principales
C_BG_PRIMARY    = "#000000"

# Fondo Secundario: Grafito Oscuro / Carbón para Sidebar y Barra Inferior
C_BG_SECONDARY  = "#121212"

# Superficies y Contenedores Estructurados (Separación tonal sutil)
C_BG_PANEL      = "#161616"
C_BG_PANEL_ALT  = "#1A1A1A"
C_BG_INPUT      = "#181818"
C_HOVER         = "#222222"
C_HOVER_ROW     = "#181818"
C_ACTIVE_ROW    = "#181622"  # Fila activa con tinte grafito/púrpura muy sutil

# Color de Acento: Deep Purple Sofisticado (#7C4DFF)
# Uso estricto: estados activos, barras de progreso, volumen, CTAs primarios
C_ACCENT        = "#7C4DFF"
C_ACCENT_HOVER  = "#6E3EEA"
C_ACCENT_MUTED  = "#3D2B69"

# Tipografía y Jerarquía Textual
C_TEXT_PRIMARY   = "#FFFFFF"  # Blanco puro de alto contraste para encabezados
C_TEXT_SECONDARY = "#A7A7A7"  # Plata/gris apagado para metadatos (artista, álbum, duración)
C_TEXT_MUTED     = "#666666"  # Gris oscuro para numeración y leyendas secundarias
C_TEXT_DISABLED  = "#404040"

# Bordes y Separadores Micro-Diseñados (Ultra-finos de 1px)
C_BORDER_SUBTLE = "#1E1E1E"  # Líneas de 1px entre paneles principales
C_BORDER_CARD   = "#242424"  # Borde fino de tarjetas e inputs
C_BORDER_BADGE  = "#2C2C2C"  # Borde micro para badges ("Downloaded", "Local File")
C_BADGE_BG      = "#141414"

# ══════════════════════════════════════════════════════════════════════
#  GEOMETRÍA CONTROLADA: SOFT CORNERS (4px - 8px)
# ══════════════════════════════════════════════════════════════════════
R_CONTAINER  = 8   # Paneles principales, modales, tarjetas
R_CARD       = 8   # Tarjetas de álbumes / listas
R_COVER      = 6   # Portadas de álbumes / miniaturas
R_BUTTON     = 6   # Botones estándar y de navegación
R_INPUT      = 6   # Campos de búsqueda y entradas de texto
R_BADGE      = 4   # Micro-badges ("LOCAL FILE", "DESCARGADO")
R_PLAYER_CTA = 8   # Botón Play/Pause central
R_SLIDER     = 2   # Barras de progreso y volumen

SIDEBAR_W    = 240
SIDEBAR_MIN  = 64
PLAYER_H     = 88
ROW_H        = 48

SONG_END     = pygame.USEREVENT + 1

if getattr(sys, 'frozen', False):
    _BASE_PATH = os.path.dirname(os.path.realpath(sys.executable))
else:
    _BASE_PATH = os.path.dirname(os.path.realpath(__file__))

PLAYLISTS_DIR = os.path.join(_BASE_PATH, "Playlists")
FFMPEG_PATH   = os.path.join(_BASE_PATH, "ffmpeg.exe")
os.makedirs(PLAYLISTS_DIR, exist_ok=True)


def F(size: int, weight: str = "normal") -> ctk.CTkFont:
    """Retorna fuente optimizada para legibilidad en interfaz oscura."""
    for fam in ("Segoe UI", "Inter", "Roboto", "Helvetica Neue", "Arial"):
        try:
            return ctk.CTkFont(family=fam, size=size, weight=weight)
        except Exception:
            pass
    return ctk.CTkFont(size=size, weight=weight)


def parse_track_meta(filename: str):
    """Extrae artista y título limpio de archivos locales."""
    base = os.path.basename(filename)
    for ext in (".mp3", ".MP3", ".m4a", ".wav", ".opus"):
        if base.endswith(ext):
            base = base[:-len(ext)]
            break
    clean = re.sub(
        r'\s*[\(\[](?:Official\s*(?:Music\s*)?Video|Video\s*Oficial|Lyrics|Letra(?:\s*Español)?|Audio|Official\s*Audio|Extended|Slowed)[\)\]]',
        '', base, flags=re.IGNORECASE
    ).strip()
    if " - " in clean:
        parts = clean.split(" - ", 1)
        artist = parts[0].strip()
        title  = parts[1].strip()
    else:
        artist = "Archivo Local"
        title  = clean
    return artist, title


def make_micro_badge(parent, text: str = "LOCAL", border_color: str = C_BORDER_BADGE, text_color: str = C_TEXT_SECONDARY):
    """Crea un micro-badge compacto con borde fino de 1px."""
    badge = ctk.CTkFrame(
        parent,
        fg_color=C_BADGE_BG,
        border_color=border_color,
        border_width=1,
        corner_radius=R_BADGE,
        height=20
    )
    badge.pack_propagate(False)
    lbl = ctk.CTkLabel(
        badge,
        text=text,
        font=F(9, "bold"),
        text_color=text_color,
        height=18
    )
    lbl.pack(padx=6, pady=0)
    return badge, lbl


# ══════════════════════════════════════════════════════════════════════
#  APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════
class ReproductorApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("StreamLock — Local Audio Vault")
        self.geometry("1120x720")
        try:
            self.iconbitmap(os.path.join(_BASE_PATH, "logo.ico"))
        except Exception:
            pass

        self.minsize(880, 600)
        self.configure(fg_color=C_BG_PRIMARY)

        pygame.init()
        pygame.mixer.init()
        pygame.mixer.music.set_endevent(SONG_END)

        # Estados de reproducción
        self._playing              = False
        self._loop                 = False
        self._shuffle              = False
        self._cur_idx              = -1
        self._playlist             = []
        self._duration             = 0.0
        self._pos                  = 0.0
        self._seeking              = False
        self.inicio_tiempo_actual  = 0.0

        # Estados de navegación e interfaz
        self._sidebar_open         = True
        self._transitioning        = False
        self._cur_view             = None
        self._active_nav_btn       = None
        self._row_refs             = []
        self._all_songs            = []
        self._current_playlist_name = ""
        self._lbl_meta             = None

        self.cookies_file = os.path.join(_BASE_PATH, "cookies.txt")
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        # Construcción de la arquitectura de 3 paneles
        self._build_ui()
        self.playlists = {}
        self._show_selection(animated=False)

        self.after(60, self._enforce_z)
        self._tick_bars()
        self._pygame_loop()
        self.actualizar_barra()
        self.after(100, self.cargar_playlists)

    # ══════════════════════════════════════════════════════════════════
    #  ARQUITECTURA DE 3 PANELES: SIDEBAR, CONTENIDO & PLAYER BAR
    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # 1. Contenedor Superior (Sidebar + Separador 1px + Área Central)
        self._top = ctk.CTkFrame(self, fg_color=C_BG_PRIMARY, corner_radius=0)
        self._top.pack(fill="both", expand=True)

        self._build_sidebar()

        # Separador vertical de 1px entre Sidebar y Contenido
        self._sidebar_sep = ctk.CTkFrame(self._top, width=1, fg_color=C_BORDER_SUBTLE, corner_radius=0)
        self._sidebar_sep.pack(side="left", fill="y")

        self._build_content()

        # Separador horizontal de 1px entre Contenido y Player Bar
        self._player_sep = ctk.CTkFrame(self, height=1, fg_color=C_BORDER_SUBTLE, corner_radius=0)
        self._player_sep.pack(side="bottom", fill="x")

        # 2. Barra Inferior Persistente (Dark Graphite #121212)
        self._build_player()
        self._build_refresh_btn()

    # ──────────────────────────────────────────────────────────────────
    #  PANEL 1: BARRA LATERAL (SIDEBAR)
    # ──────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self._top,
            width=SIDEBAR_W,
            fg_color=C_BG_SECONDARY,
            corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Cabecera de Marca (Branding sofisticado)
        row_brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        row_brand.pack(fill="x", padx=16, pady=(20, 10))

        self.btn_menu = ctk.CTkButton(
            row_brand, text="☰", width=34, height=34,
            fg_color="transparent", hover_color=C_HOVER, font=F(16),
            text_color=C_TEXT_SECONDARY, corner_radius=R_BUTTON,
            command=self._toggle_sidebar
        )
        self.btn_menu.pack(side="left")

        self.brand_box = ctk.CTkFrame(row_brand, fg_color="transparent")
        self.brand_box.pack(side="left", padx=(8, 0))

        brand_line = ctk.CTkFrame(self.brand_box, fg_color="transparent")
        brand_line.pack(anchor="w")

        self.lbl_logo_icon = ctk.CTkLabel(
            brand_line, text="◈", font=F(16, "bold"), text_color=C_ACCENT
        )
        self.lbl_logo_icon.pack(side="left", padx=(0, 4))

        self.lbl_logo = ctk.CTkLabel(
            brand_line, text="StreamLock", font=F(15, "bold"), text_color=C_TEXT_PRIMARY
        )
        self.lbl_logo.pack(side="left")

        self.lbl_subtitle = ctk.CTkLabel(
            self.brand_box, text="OFFLINE AUDIO VAULT", font=F(8, "bold"), text_color=C_TEXT_MUTED
        )
        self.lbl_subtitle.pack(anchor="w", pady=(1, 0))

        # Navegación Principal
        self._nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self._nav.pack(fill="x", padx=12, pady=(16, 0))

        self.lbl_sec_lib = ctk.CTkLabel(
            self._nav, text="EXPLORAR", font=F(10, "bold"),
            text_color=C_TEXT_MUTED, anchor="w"
        )
        self.lbl_sec_lib.pack(fill="x", padx=6, pady=(0, 6))

        self.btn_playlists = self._nav_btn("♫   Mis Playlists", self._goto_selection)
        self.btn_download  = self._nav_btn("↓   Descargar Audio", self._goto_download)

        # Sección Playlists Locales (Acceso directo desde Sidebar)
        self._pl_header_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self._pl_header_row.pack(fill="x", padx=18, pady=(20, 6))

        self.lbl_sec_pl = ctk.CTkLabel(
            self._pl_header_row, text="LISTAS LOCALES", font=F(10, "bold"),
            text_color=C_TEXT_MUTED, anchor="w"
        )
        self.lbl_sec_pl.pack(side="left")

        self.btn_quick_new = ctk.CTkButton(
            self._pl_header_row, text="+", width=22, height=22,
            fg_color=C_BG_PANEL, hover_color=C_HOVER, text_color=C_TEXT_PRIMARY,
            border_color=C_BORDER_CARD, border_width=1, corner_radius=4,
            font=F(12, "bold"), command=self._create_playlist
        )
        self.btn_quick_new.pack(side="right")

        self._sidebar_pl_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent",
            scrollbar_button_color=C_BG_PANEL,
            scrollbar_button_hover_color=C_HOVER
        )
        self._sidebar_pl_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Pie de Sidebar: Indicador de Almacenamiento Local Offline
        self.storage_box = ctk.CTkFrame(
            self.sidebar, fg_color=C_BG_PANEL, border_color=C_BORDER_CARD,
            border_width=1, corner_radius=R_CONTAINER
        )
        self.storage_box.pack(fill="x", padx=12, pady=12, side="bottom")

        row_stat = ctk.CTkFrame(self.storage_box, fg_color="transparent")
        row_stat.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            row_stat, text="●", font=F(8), text_color="#66BB6A"
        ).pack(side="left", padx=(0, 6))

        self.lbl_stat_mode = ctk.CTkLabel(
            row_stat, text="MODO LOCAL ACTIVO", font=F(9, "bold"), text_color=C_TEXT_SECONDARY
        )
        self.lbl_stat_mode.pack(side="left")

        self.lbl_storage_info = ctk.CTkLabel(
            self.storage_box, text="0 listas · 0 MB en disco", font=F(10), text_color=C_TEXT_MUTED
        )
        self.lbl_storage_info.pack(anchor="w", padx=10, pady=(0, 8))

    def _nav_btn(self, text, cmd):
        b = ctk.CTkButton(
            self._nav, text=text, anchor="w", height=38,
            corner_radius=R_BUTTON, fg_color="transparent",
            hover_color=C_HOVER, text_color=C_TEXT_SECONDARY,
            font=F(13, "bold"), command=cmd
        )
        b.pack(fill="x", pady=2)
        return b

    def _toggle_sidebar(self):
        if self._sidebar_open:
            self.brand_box.pack_forget()
            self.lbl_sec_lib.pack_forget()
            self._pl_header_row.pack_forget()
            self._sidebar_pl_frame.pack_forget()
            self.storage_box.pack_forget()
            for b, ico in [(self.btn_playlists, "♫"), (self.btn_download, "↓")]:
                b.configure(text=ico, anchor="center")
            self.sidebar.configure(width=SIDEBAR_MIN)
            self._sidebar_open = False
        else:
            self.sidebar.configure(width=SIDEBAR_W)
            self.brand_box.pack(side="left", padx=(8, 0))
            self.lbl_sec_lib.pack(fill="x", padx=6, pady=(0, 6))
            self._pl_header_row.pack(fill="x", padx=18, pady=(20, 6))
            self._sidebar_pl_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
            self.storage_box.pack(fill="x", padx=12, pady=12, side="bottom")
            for b, t in [(self.btn_playlists, "♫   Mis Playlists"), (self.btn_download, "↓   Descargar Audio")]:
                b.configure(text=t, anchor="w")
            self._sidebar_open = True
        self._enforce_z()

    def _update_sidebar_playlists(self):
        """Actualiza la lista rápida de playlists en el sidebar."""
        for w in self._sidebar_pl_frame.winfo_children():
            w.destroy()

        if not self.playlists:
            lbl_empty = ctk.CTkLabel(
                self._sidebar_pl_frame, text="Sin playlists",
                font=F(11), text_color=C_TEXT_MUTED
            )
            lbl_empty.pack(anchor="w", padx=10, pady=4)
            return

        for name, songs in self.playlists.items():
            btn = ctk.CTkButton(
                self._sidebar_pl_frame,
                text=f"•  {name}",
                anchor="w",
                height=30,
                corner_radius=R_BUTTON,
                fg_color="transparent",
                hover_color=C_HOVER,
                text_color=C_TEXT_SECONDARY,
                font=F(12),
                command=lambda n=name: self._show_playlist(n)
            )
            btn.pack(fill="x", pady=1)

        # Actualiza el pie de almacenamiento
        total_songs = sum(len(s) for s in self.playlists.values())
        total_bytes = 0
        for s in self.playlists.values():
            total_bytes += sum(os.path.getsize(p) for p in s if os.path.exists(p))
        mb_str = f"{total_bytes / (1024 * 1024):.1f} MB" if total_bytes > 0 else "0 MB"
        self.lbl_storage_info.configure(
            text=f"{len(self.playlists)} listas · {total_songs} pistas · {mb_str}"
        )

    # ──────────────────────────────────────────────────────────────────
    #  PANEL 2: CONTENEDOR CENTRAL DE VISTAS (PITCH BLACK #000000)
    # ──────────────────────────────────────────────────────────────────
    def _build_content(self):
        self.content = ctk.CTkFrame(
            self._top,
            fg_color=C_BG_PRIMARY,
            corner_radius=0
        )
        self.content.pack(side="left", fill="both", expand=True)

    # ──────────────────────────────────────────────────────────────────
    #  PANEL 3: REPRODUCTOR INFERIOR PERSISTENTE (CHARCOAL #121212)
    # ──────────────────────────────────────────────────────────────────
    def _build_player(self):
        self.player = ctk.CTkFrame(
            self,
            fg_color=C_BG_SECONDARY,
            corner_radius=0,
            height=PLAYER_H
        )
        self.player.pack(fill="x", side="bottom")
        self.player.pack_propagate(False)

        grid = ctk.CTkFrame(self.player, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=20, pady=8)

        # ── SECCIÓN IZQUIERDA: Metadatos de la Pista Actual ──
        left_col = ctk.CTkFrame(grid, fg_color="transparent", width=280)
        left_col.pack(side="left", fill="y", expand=False)
        left_col.pack_propagate(False)

        cover_box = ctk.CTkFrame(
            left_col,
            width=46,
            height=46,
            fg_color=C_BG_PANEL_ALT,
            border_color=C_BORDER_CARD,
            border_width=1,
            corner_radius=R_COVER
        )
        cover_box.pack(side="left", pady=12, padx=(0, 12))
        cover_box.pack_propagate(False)

        self.lbl_player_ico = ctk.CTkLabel(
            cover_box, text="♫", font=F(16), text_color=C_ACCENT
        )
        self.lbl_player_ico.place(relx=0.5, rely=0.5, anchor="center")

        meta_stack = ctk.CTkFrame(left_col, fg_color="transparent")
        meta_stack.pack(side="left", fill="both", expand=True, pady=12)

        self.lbl_song = ctk.CTkLabel(
            meta_stack,
            text="Sin reproducción",
            font=F(13, "bold"),
            text_color=C_TEXT_PRIMARY,
            anchor="w"
        )
        self.lbl_song.pack(anchor="w", fill="x")

        row_submeta = ctk.CTkFrame(meta_stack, fg_color="transparent")
        row_submeta.pack(anchor="w", fill="x", pady=(2, 0))

        self.lbl_artist = ctk.CTkLabel(
            row_submeta,
            text="Biblioteca local",
            font=F(11),
            text_color=C_TEXT_SECONDARY,
            anchor="w"
        )
        self.lbl_artist.pack(side="left")

        # ── SECCIÓN CENTRAL: Controles Fluidos + Barra de Línea de Tiempo ──
        center_col = ctk.CTkFrame(grid, fg_color="transparent")
        center_col.pack(side="left", fill="both", expand=True, padx=16)

        ctrl_row = ctk.CTkFrame(center_col, fg_color="transparent")
        ctrl_row.pack(side="top", pady=(2, 4))

        self.btn_shuf = self._tog(ctrl_row, "⇄", self._toggle_shuffle)
        self._ctrl(ctrl_row, "⏮", self._prev, 16)

        # Botón Play/Pause central con geometría controlada (8px)
        self.btn_play = ctk.CTkButton(
            ctrl_row,
            text="▶",
            width=38,
            height=38,
            corner_radius=R_PLAYER_CTA,
            fg_color=C_TEXT_PRIMARY,
            hover_color="#E0E0E0",
            text_color=C_BG_SECONDARY,
            font=F(16, "bold"),
            border_width=0,
            command=self._toggle_play
        )
        self.btn_play.pack(side="left", padx=12)

        self._ctrl(ctrl_row, "⏭", self._next, 16)
        self.btn_loop = self._tog(ctrl_row, "↻", self._toggle_loop)

        # Línea de Progreso
        prog_row = ctk.CTkFrame(center_col, fg_color="transparent")
        prog_row.pack(side="top", fill="x")

        self.lbl_cur = ctk.CTkLabel(
            prog_row, text="0:00", font=F(11), text_color=C_TEXT_SECONDARY
        )
        self.lbl_cur.pack(side="left", padx=(0, 8))

        # Slider Flat con acento Deep Purple (#7C4DFF)
        self.prog = ctk.CTkSlider(
            prog_row,
            from_=0.0,
            to=1.0,
            height=4,
            corner_radius=R_SLIDER,
            fg_color="#242424",
            progress_color=C_ACCENT,
            button_color=C_TEXT_PRIMARY,
            button_hover_color=C_TEXT_PRIMARY,
            button_length=0,
            command=self._on_seek
        )
        self.prog.set(0)
        self.prog.pack(side="left", fill="x", expand=True)
        self.prog.bind("<ButtonPress-1>",   lambda e: setattr(self, "_seeking", True))
        self.prog.bind("<ButtonRelease-1>", self._on_seek_release)

        self.lbl_tot = ctk.CTkLabel(
            prog_row, text="--:--", font=F(11), text_color=C_TEXT_SECONDARY
        )
        self.lbl_tot.pack(side="right", padx=(8, 0))

        # ── SECCIÓN DERECHA: Control de Volumen & Badge Offline ──
        right_col = ctk.CTkFrame(grid, fg_color="transparent", width=220)
        right_col.pack(side="right", fill="y", expand=False)
        right_col.pack_propagate(False)

        vol_row = ctk.CTkFrame(right_col, fg_color="transparent")
        vol_row.pack(side="right", pady=(24, 0))

        ctk.CTkLabel(
            vol_row, text="🔈", font=F(13), text_color=C_TEXT_SECONDARY
        ).pack(side="left", padx=(0, 8))

        self.vol_slider = ctk.CTkSlider(
            vol_row,
            from_=0.0,
            to=1.0,
            width=88,
            height=4,
            corner_radius=R_SLIDER,
            fg_color="#242424",
            progress_color=C_ACCENT,
            button_length=0,
            command=self._set_volume
        )
        self.vol_slider.set(0.8)
        pygame.mixer.music.set_volume(0.8)
        self.vol_slider.pack(side="left", padx=(0, 10))

        make_micro_badge(vol_row, "OFFLINE", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

        self._row_bars    = []
        self._row_bar_spd = []

    def _ctrl(self, p, t, c, sz=15):
        b = ctk.CTkButton(
            p, text=t, width=32, height=32, corner_radius=R_BUTTON,
            fg_color="transparent", hover_color=C_HOVER, text_color=C_TEXT_SECONDARY,
            font=F(sz), border_width=0, command=c
        )
        b.pack(side="left", padx=2)
        return b

    def _tog(self, p, t, c):
        b = ctk.CTkButton(
            p, text=t, width=32, height=32, corner_radius=R_BUTTON,
            fg_color="transparent", hover_color=C_HOVER, text_color=C_TEXT_MUTED,
            font=F(14), border_width=0, command=c
        )
        b.pack(side="left", padx=2)
        return b

    def _build_refresh_btn(self):
        self.btn_ref = ctk.CTkButton(
            self, text="↺", width=32, height=32, corner_radius=R_BUTTON,
            fg_color=C_BG_PANEL, hover_color=C_HOVER, text_color=C_TEXT_MUTED,
            border_color=C_BORDER_CARD, border_width=1,
            font=F(14), command=self._force_refresh
        )
        self.btn_ref.place(relx=1.0, rely=0.0, x=-16, y=14, anchor="ne")

    def _force_refresh(self):
        self._enforce_z()
        self.update_idletasks()
        self.update()
        if self._cur_view:
            try:
                self._cur_view.lift()
            except Exception:
                pass
        self.sidebar.lift()

    def _enforce_z(self):
        try:
            self.sidebar.lift()
            self._sidebar_sep.lift()
            self.btn_ref.lift()
        except Exception:
            pass

    def _switch(self, builder_fn, nav_btn=None):
        if self._transitioning:
            return
        self._transitioning = True
        if nav_btn:
            self._set_nav(nav_btn)
        nuevo = ctk.CTkFrame(self.content, fg_color=C_BG_PRIMARY, corner_radius=0)
        builder_fn(nuevo)
        nuevo.update_idletasks()
        nuevo.place(relx=0, rely=0, relwidth=1, relheight=1)
        nuevo.lift()
        viejo = self._cur_view
        self._cur_view = nuevo
        self._enforce_z()

        def _cleanup():
            if viejo:
                try:
                    viejo.destroy()
                except Exception:
                    pass
            self._transitioning = False
            self._enforce_z()

        self.after(5, _cleanup)

    def _switch_direct(self, builder_fn, nav_btn=None):
        if nav_btn:
            self._set_nav(nav_btn)
        nuevo = ctk.CTkFrame(self.content, fg_color=C_BG_PRIMARY, corner_radius=0)
        builder_fn(nuevo)
        nuevo.update_idletasks()
        nuevo.place(relx=0, rely=0, relwidth=1, relheight=1)
        nuevo.lift()
        viejo = self._cur_view
        self._cur_view = nuevo
        self._enforce_z()
        if viejo:
            try:
                viejo.destroy()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    #  VISUALIZADOR Y CICLO PYGAME
    # ══════════════════════════════════════════════════════════════════
    def _tick_bars(self):
        self._animate_row_bars()

    def _animate_row_bars(self):
        if not self._playing or self._cur_idx < 0:
            self.after(200, self._animate_row_bars)
            return
        for row_idx, bars in enumerate(self._row_bars):
            if row_idx == self._cur_idx:
                for b in bars:
                    try:
                        b.configure(height=random.randint(4, 20), fg_color=C_ACCENT)
                    except Exception:
                        pass
        self.after(80, self._animate_row_bars)

    def _pygame_loop(self):
        for ev in pygame.event.get():
            if ev.type == SONG_END:
                self._on_end()
        self.after(200, self._pygame_loop)

    def actualizar_barra(self):
        if self._playing and self._duration > 0 and not self._seeking:
            ms = pygame.mixer.music.get_pos()
            if ms >= 0:
                pos_real = min((ms / 1000.0) + self.inicio_tiempo_actual, self._duration)
                progreso = pos_real / self._duration
                try:
                    self.prog.set(progreso)
                    self.lbl_cur.configure(text=self._fmt(pos_real))
                except Exception:
                    pass
        self.after(500, self.actualizar_barra)

    def _on_seek(self, value: float):
        self._seeking = True
        if self._duration > 0:
            try:
                self.lbl_cur.configure(text=self._fmt(value * self._duration))
            except Exception:
                pass

    def _on_seek_release(self, event):
        if not self._playlist or self._cur_idx < 0 or self._duration <= 0:
            self._seeking = False
            return
        valor        = self.prog.get()
        nuevo_tiempo = valor * self._duration
        try:
            path = self._playlist[self._cur_idx]
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(start=nuevo_tiempo)
            self.inicio_tiempo_actual = nuevo_tiempo
            self._playing = True
            self.btn_play.configure(text="⏸")
            self.lbl_cur.configure(text=self._fmt(nuevo_tiempo))
        except Exception as e:
            self.lbl_song.configure(text=f"✕ Error: {str(e)[:35]}")
        finally:
            self._seeking = False

    @staticmethod
    def _fmt(s: float) -> str:
        s = int(s)
        return f"{s//60}:{s%60:02d}"

    def _play_idx(self, idx: int):
        if not self._playlist or not (0 <= idx < len(self._playlist)):
            return
        self._cur_idx = idx
        path = self._playlist[idx]
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self._playing             = True
            self.inicio_tiempo_actual = 0.0
            self._duration = self._get_duration(path)

            artist, title = parse_track_meta(path)
            self.lbl_song.configure(text=title)
            self.lbl_artist.configure(text=artist)

            self.btn_play.configure(text="⏸")
            self.prog.set(0)
            self.lbl_cur.configure(text="0:00")
            self.lbl_tot.configure(text=self._fmt(self._duration) if self._duration else "--:--")
            self._highlight(idx)
        except Exception:
            pass

    @staticmethod
    def _get_duration(path: str) -> float:
        try:
            from mutagen.mp3 import MP3
            return MP3(path).info.length
        except Exception:
            pass
        try:
            snd = pygame.mixer.Sound(path)
            dur = snd.get_length()
            del snd
            return dur
        except Exception:
            return 0.0

    def _toggle_play(self):
        if not self._playlist:
            return
        if self._playing:
            pygame.mixer.music.pause()
            self._playing = False
            self.btn_play.configure(text="▶")
        else:
            if self._cur_idx == -1:
                self._play_idx(0)
            else:
                pygame.mixer.music.unpause()
                self._playing = True
                self.btn_play.configure(text="⏸")

    def _next(self):
        if not self._playlist:
            return
        idx = random.randint(0, len(self._playlist) - 1) if self._shuffle else (self._cur_idx + 1) % len(self._playlist)
        self._play_idx(idx)

    def _prev(self):
        if not self._playlist:
            return
        self._play_idx((self._cur_idx - 1) % len(self._playlist))

    def _on_end(self):
        if self._loop:
            self._play_idx(self._cur_idx)
        else:
            self._next()

    def _toggle_loop(self):
        self._loop = not self._loop
        self.btn_loop.configure(text_color=C_ACCENT if self._loop else C_TEXT_MUTED)

    def _toggle_shuffle(self):
        self._shuffle = not self._shuffle
        self.btn_shuf.configure(text_color=C_ACCENT if self._shuffle else C_TEXT_MUTED)

    def _set_volume(self, value: float):
        pygame.mixer.music.set_volume(float(value))

    def _highlight(self, idx: int):
        for i, (card, lbl_t, lbl_a) in enumerate(self._row_refs):
            try:
                if i == idx:
                    card.configure(fg_color=C_ACTIVE_ROW, border_color=C_ACCENT_MUTED, border_width=1)
                    lbl_t.configure(text_color=C_ACCENT)
                else:
                    card.configure(fg_color="transparent", border_color="transparent", border_width=0)
                    lbl_t.configure(text_color=C_TEXT_PRIMARY)
                    if i < len(self._row_bars):
                        for b in self._row_bars[i]:
                            b.configure(height=3, fg_color=C_TEXT_MUTED)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    #  DATOS DE PLAYLISTS LOCALES
    # ══════════════════════════════════════════════════════════════════
    def cargar_playlists(self):
        self.playlists = self._load_playlists()
        self._update_sidebar_playlists()
        self._show_selection(animated=False)

    def _load_playlists(self) -> dict:
        result = {}
        if os.path.isdir(PLAYLISTS_DIR):
            for folder in sorted(os.listdir(PLAYLISTS_DIR)):
                fp = os.path.join(PLAYLISTS_DIR, folder)
                if os.path.isdir(fp):
                    files = sorted([os.path.join(fp, f) for f in os.listdir(fp) if f.lower().endswith(".mp3")])
                    result[folder] = files
        return result

    def _create_playlist(self):
        """Modal refinado para crear nueva lista local."""
        modal = ctk.CTkToplevel(self)
        modal.title("Nueva Playlist Local")
        modal.geometry("340x200")
        modal.resizable(False, False)
        modal.configure(fg_color=C_BG_PANEL)
        modal.grab_set()
        modal.lift()
        self.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - 340) // 2
        py = self.winfo_y() + (self.winfo_height() - 200) // 2
        modal.geometry(f"340x200+{px}+{py}")

        header = ctk.CTkFrame(modal, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))
        ctk.CTkLabel(header, text="Nueva Playlist Local", font=F(14, "bold"), text_color=C_TEXT_PRIMARY).pack(side="left")
        make_micro_badge(header, "CARPETA LOCAL", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

        entry = ctk.CTkEntry(
            modal, placeholder_text="Nombre de la playlist...",
            height=38, corner_radius=R_INPUT, fg_color=C_BG_INPUT,
            border_color=C_BORDER_CARD, border_width=1,
            text_color=C_TEXT_PRIMARY, font=F(13)
        )
        entry.pack(fill="x", padx=24, pady=(0, 16))
        entry.focus()

        def submit():
            name = entry.get().strip()
            if name:
                os.makedirs(os.path.join(PLAYLISTS_DIR, name), exist_ok=True)
                self.playlists = self._load_playlists()
                self._update_sidebar_playlists()
                self._show_selection(animated=True)
            modal.destroy()

        entry.bind("<Return>", lambda e: submit())

        btn_row = ctk.CTkFrame(modal, fg_color="transparent")
        btn_row.pack(fill="x", padx=24)

        ctk.CTkButton(
            btn_row, text="Crear Playlist", height=36, corner_radius=R_BUTTON,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color=C_TEXT_PRIMARY,
            font=F(13, "bold"), command=submit
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Cancelar", height=36, corner_radius=R_BUTTON,
            fg_color=C_BG_PANEL_ALT, hover_color=C_HOVER, text_color=C_TEXT_SECONDARY,
            border_color=C_BORDER_CARD, border_width=1, font=F(12),
            command=modal.destroy
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    # ══════════════════════════════════════════════════════════════════
    #  VISTA 1 — BIBLIOTECA (GRID DE PLAYLISTS & ÁLBUMES)
    # ══════════════════════════════════════════════════════════════════
    def _show_selection(self, animated: bool = True):
        def build(frame):
            top = ctk.CTkFrame(frame, fg_color="transparent")
            top.pack(fill="x", padx=36, pady=(32, 6))

            title_row = ctk.CTkFrame(top, fg_color="transparent")
            title_row.pack(side="left")

            ctk.CTkLabel(
                title_row, text="Mi Biblioteca", font=F(26, "bold"), text_color=C_TEXT_PRIMARY
            ).pack(side="left")

            badge_box = ctk.CTkFrame(title_row, fg_color="transparent")
            badge_box.pack(side="left", padx=(12, 0))
            make_micro_badge(badge_box, "ALMACENAMIENTO LOCAL", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

            ctk.CTkButton(
                top, text="+ Nueva Playlist", width=128, height=36,
                corner_radius=R_BUTTON, border_width=0,
                fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
                text_color=C_TEXT_PRIMARY, font=F(13, "bold"),
                command=self._create_playlist
            ).pack(side="right")

            pl_count = len(self.playlists)
            total_songs = sum(len(s) for s in self.playlists.values())
            msg = f"{pl_count} listas de reproducción locales · {total_songs} pistas disponibles sin conexión" if pl_count else "No hay música almacenada localmente todavía"
            ctk.CTkLabel(
                frame, text=msg, font=F(12), text_color=C_TEXT_SECONDARY
            ).pack(anchor="w", padx=36, pady=(0, 20))

            grid = ctk.CTkScrollableFrame(
                frame, fg_color="transparent",
                scrollbar_button_color=C_BG_PANEL,
                scrollbar_button_hover_color=C_HOVER
            )
            grid.pack(fill="both", expand=True, padx=24, pady=(0, 16))

            cols = 4
            for i, (name, songs) in enumerate(self.playlists.items()):
                self._playlist_card(grid, name, songs, i // cols, i % cols)
            for c in range(cols):
                grid.columnconfigure(c, weight=1)

        if animated:
            self._switch(build, nav_btn=self.btn_playlists)
        else:
            self._switch_direct(build, nav_btn=self.btn_playlists)

    def _playlist_card(self, parent, name, songs, row, col):
        """Tarjeta de álbum/playlist con bordes finos de 1px y geometría controlada."""
        card = ctk.CTkFrame(
            parent,
            fg_color=C_BG_PANEL,
            border_color=C_BORDER_CARD,
            border_width=1,
            corner_radius=R_CARD,
            cursor="hand2"
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # Contenedor de "Portada de Álbum" (Soft Corners: 6px)
        cover = ctk.CTkFrame(
            card,
            fg_color=C_BG_PANEL_ALT,
            border_color=C_BORDER_CARD,
            border_width=1,
            corner_radius=R_COVER,
            width=132,
            height=132
        )
        cover.pack(pady=(14, 10), padx=14)
        cover.pack_propagate(False)

        ico = ctk.CTkLabel(cover, text="♫", font=F(42), text_color=C_TEXT_MUTED)
        ico.place(relx=0.5, rely=0.45, anchor="center")

        cover_badge = ctk.CTkFrame(
            cover, fg_color=C_BADGE_BG, border_color=C_BORDER_BADGE,
            border_width=1, corner_radius=3, height=16
        )
        cover_badge.place(relx=0.5, rely=0.85, anchor="center")
        ctk.CTkLabel(
            cover_badge, text="LOCAL", font=F(8, "bold"), text_color=C_TEXT_SECONDARY
        ).pack(padx=5, pady=0)

        lbl = ctk.CTkLabel(
            card, text=name, font=F(14, "bold"),
            text_color=C_TEXT_PRIMARY, wraplength=140, anchor="w"
        )
        lbl.pack(padx=14, anchor="w")

        size_str = self._playlist_size(songs)
        sub = ctk.CTkLabel(
            card, text=f"{len(songs)} pistas · {size_str}",
            font=F(11), text_color=C_TEXT_SECONDARY, anchor="w"
        )
        sub.pack(pady=(2, 14), padx=14, anchor="w")

        def enter(e, c=card, cv=cover):
            c.configure(fg_color=C_HOVER, border_color="#303030")
            cv.configure(fg_color="#202020")

        def leave(e, c=card, cv=cover):
            c.configure(fg_color=C_BG_PANEL, border_color=C_BORDER_CARD)
            cv.configure(fg_color=C_BG_PANEL_ALT)

        for w in [card, cover, ico, lbl, sub, cover_badge]:
            w.bind("<Button-1>", lambda e, n=name: self._show_playlist(n))
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)

    # ══════════════════════════════════════════════════════════════════
    #  VISTA 2 — PLAYLIST (TABLA ESTRUCTURADA & MINIMALISTA)
    # ══════════════════════════════════════════════════════════════════
    def _show_playlist(self, name: str, animated: bool = True):
        songs = self.playlists.get(name, [])
        self._playlist              = songs
        self._all_songs             = songs
        self._current_playlist_name = name

        def build(frame):
            self._row_refs = []

            # Barra Superior de Encabezado
            top = ctk.CTkFrame(frame, fg_color="transparent")
            top.pack(fill="x", padx=36, pady=(28, 6))

            back_btn = ctk.CTkButton(
                top, text="← Volver", width=76, height=32, corner_radius=R_BUTTON,
                fg_color=C_BG_PANEL, hover_color=C_HOVER, text_color=C_TEXT_SECONDARY,
                border_color=C_BORDER_CARD, border_width=1, font=F(12),
                command=lambda: self._show_selection(animated=True)
            )
            back_btn.pack(side="left")

            title_group = ctk.CTkFrame(top, fg_color="transparent")
            title_group.pack(side="left", padx=16)

            ctk.CTkLabel(
                title_group, text=name, font=F(26, "bold"), text_color=C_TEXT_PRIMARY
            ).pack(side="left")

            make_micro_badge(title_group, "DESCARGADO", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

            # Metadata Strip
            self._lbl_meta = ctk.CTkLabel(
                frame,
                text=f"{len(songs)} canciones · {self._playlist_size(songs)} en disco · Formato MP3 local",
                font=F(12), text_color=C_TEXT_SECONDARY
            )
            self._lbl_meta.pack(anchor="w", padx=36, pady=(0, 16))

            # Barra de Búsqueda / Filtro en Playlist
            search_frame = ctk.CTkFrame(frame, fg_color="transparent")
            search_frame.pack(fill="x", padx=36, pady=(0, 8))

            self._search_var = ctk.StringVar()
            self._search_var.trace_add("write", lambda *_: self._filter_songs())

            self._search_entry = ctk.CTkEntry(
                search_frame, placeholder_text="Filtrar pistas de esta lista...",
                textvariable=self._search_var, height=34, corner_radius=R_INPUT,
                width=280, fg_color=C_BG_INPUT, border_color=C_BORDER_CARD,
                border_width=1, text_color=C_TEXT_PRIMARY,
                placeholder_text_color=C_TEXT_MUTED, font=F(12)
            )
            self._search_entry.pack(side="left")

            # Cabecera de Columnas (Estilo DAW / Reproductor Profesional)
            col_header = ctk.CTkFrame(frame, fg_color="transparent", height=28)
            col_header.pack(fill="x", padx=36, pady=(8, 2))
            col_header.pack_propagate(False)

            ctk.CTkLabel(
                col_header, text="#", width=36, font=F(10, "bold"),
                text_color=C_TEXT_MUTED, anchor="center"
            ).pack(side="left")

            ctk.CTkLabel(
                col_header, text="TÍTULO Y ARTISTA", font=F(10, "bold"),
                text_color=C_TEXT_MUTED, anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=(12, 10))

            ctk.CTkLabel(
                col_header, text="ESTADO", width=70, font=F(10, "bold"),
                text_color=C_TEXT_MUTED, anchor="center"
            ).pack(side="right", padx=(0, 100))

            ctk.CTkLabel(
                col_header, text="DURACIÓN", width=50, font=F(10, "bold"),
                text_color=C_TEXT_MUTED, anchor="e"
            ).pack(side="right", padx=(0, 48))

            # Separador sutil de 1px bajo las columnas
            ctk.CTkFrame(frame, height=1, fg_color=C_BORDER_SUBTLE).pack(fill="x", padx=36, pady=(0, 4))

            # Lista desplazable de canciones
            self._scroll_list = ctk.CTkScrollableFrame(
                frame, fg_color="transparent",
                scrollbar_button_color=C_BG_PANEL,
                scrollbar_button_hover_color=C_HOVER
            )
            self._scroll_list.pack(fill="both", expand=True, padx=26, pady=(4, 12))

            self._build_song_rows(songs)
            self._highlight(self._cur_idx)

        if animated:
            self._switch(build, nav_btn=self.btn_playlists)
        else:
            self._switch_direct(build, nav_btn=self.btn_playlists)

    def _build_song_rows(self, songs: list):
        self._row_refs    = []
        self._row_bars    = []
        self._row_bar_spd = []
        for w in self._scroll_list.winfo_children():
            w.destroy()

        for i, path in enumerate(songs):
            row, lbl_t, lbl_a = self._skeleton_row(self._scroll_list, i, path)
            self._row_refs.append((row, lbl_t, lbl_a))

    def _filter_songs(self):
        query = self._search_var.get().strip().lower()
        filtered = [p for p in self._all_songs if query in os.path.basename(p).lower()] if query else self._all_songs
        self._playlist = filtered
        self._build_song_rows(filtered)
        self._highlight(self._cur_idx)

    def _skeleton_row(self, parent, idx: int, path: str):
        artist, title = parse_track_meta(path)

        # Fila con geometría suave (6px) y fondo transparente por defecto
        card = ctk.CTkFrame(
            parent, fg_color="transparent", corner_radius=R_BUTTON,
            cursor="hand2", height=ROW_H
        )
        card.pack(fill="x", pady=1, padx=6)
        card.pack_propagate(False)

        # Columna #: Número de pista
        ctk.CTkLabel(
            card, text=f"{idx + 1:02d}", width=36, font=F(11),
            text_color=C_TEXT_MUTED, anchor="center"
        ).pack(side="left")

        # Columna: Título y Artista
        info_box = ctk.CTkFrame(card, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True, padx=(12, 10), pady=4)

        lbl_title = ctk.CTkLabel(
            info_box, text=title, font=F(13, "bold"),
            text_color=C_TEXT_PRIMARY, anchor="w"
        )
        lbl_title.pack(anchor="w", fill="x")

        lbl_artist = ctk.CTkLabel(
            info_box, text=artist, font=F(11),
            text_color=C_TEXT_SECONDARY, anchor="w"
        )
        lbl_artist.pack(anchor="w", fill="x")

        # Columna: Micro-Badge "LOCAL"
        badge_frame = ctk.CTkFrame(card, fg_color="transparent", width=80)
        badge_frame.pack(side="right", padx=(0, 20))
        badge_frame.pack_propagate(False)
        make_micro_badge(badge_frame, "LOCAL MP3", border_color=C_BORDER_BADGE, text_color=C_TEXT_SECONDARY)

        # Menú contextual ⋮
        btn_opts = ctk.CTkButton(
            card, text="⋮", width=28, height=28, corner_radius=R_BUTTON,
            fg_color="transparent", hover_color=C_HOVER, text_color=C_TEXT_MUTED,
            font=F(14), command=lambda i=idx, p=path: self._show_song_menu(i, p)
        )
        btn_opts.pack(side="right", padx=(0, 8))

        # Duración
        lbl_dur = ctk.CTkLabel(
            card, text="--:--", font=F(12), text_color=C_TEXT_SECONDARY, width=45, anchor="e"
        )
        lbl_dur.pack(side="right", padx=(0, 16))

        # Barras de ecualizador animadas (Deep Purple #7C4DFF)
        viz = ctk.CTkFrame(card, fg_color="transparent", width=30, height=ROW_H)
        viz.pack(side="right", padx=(0, 12))
        viz.pack_propagate(False)

        bars_this_row = []
        for _ in range(4):
            b = ctk.CTkFrame(
                viz, width=3, height=3, fg_color=C_ACCENT, corner_radius=1
            )
            b.pack(side="left", padx=1, anchor="center")
            bars_this_row.append(b)

        while len(self._row_bars) <= idx:
            self._row_bars.append([])
            self._row_bar_spd.append(80)

        self._row_bars[idx] = bars_this_row

        # Comportamiento de Hover y Selección
        def on_enter(e, c=card, i=idx):
            if i != self._cur_idx:
                c.configure(fg_color=C_HOVER_ROW)

        def on_leave(e, c=card, i=idx):
            if i != self._cur_idx:
                c.configure(fg_color="transparent")

        def on_click(e, i=idx):
            self._play_idx(i)

        no_click = {btn_opts}
        for w in [card, lbl_title, lbl_artist, info_box, viz] + [ch for ch in card.winfo_children() if ch not in no_click]:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)

        def _cargar_duracion():
            dur = self._get_duration(path)
            self.after(0, lambda: lbl_dur.configure(text=self._fmt(dur)))

        self._thread_pool.submit(_cargar_duracion)

        return card, lbl_title, lbl_artist

    def _show_song_menu(self, idx, path):
        artist, title = parse_track_meta(path)
        popup = ctk.CTkToplevel(self)
        popup.title("Opciones de Archivo")
        popup.geometry("320x190")
        popup.resizable(False, False)
        popup.configure(fg_color=C_BG_PANEL)
        popup.grab_set()
        popup.lift()
        self.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - 320) // 2
        py = self.winfo_y() + (self.winfo_height() - 190) // 2
        popup.geometry(f"320x190+{px}+{py}")

        header = ctk.CTkFrame(popup, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 4))
        ctk.CTkLabel(header, text="Gestión de Archivo Local", font=F(12, "bold"), text_color=C_TEXT_MUTED).pack(side="left")
        make_micro_badge(header, "LOCAL", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

        ctk.CTkLabel(
            popup, text=title, font=F(13, "bold"), text_color=C_TEXT_PRIMARY, wraplength=280
        ).pack(pady=(4, 1), padx=20)
        ctk.CTkLabel(
            popup, text=artist, font=F(11), text_color=C_TEXT_SECONDARY
        ).pack(pady=(0, 16), padx=20)

        ctk.CTkButton(
            popup, text="🗑  Eliminar archivo local", height=36, corner_radius=R_BUTTON,
            fg_color="#8A2323", hover_color="#A82E2E", text_color=C_TEXT_PRIMARY,
            font=F(12, "bold"), command=lambda: self._delete_song(idx, path, popup)
        ).pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkButton(
            popup, text="Cancelar", height=32, corner_radius=R_BUTTON,
            fg_color=C_BG_PANEL_ALT, hover_color=C_HOVER, text_color=C_TEXT_SECONDARY,
            border_color=C_BORDER_CARD, border_width=1, font=F(12),
            command=popup.destroy
        ).pack(fill="x", padx=20)

    def _delete_song(self, idx, path, popup):
        popup.destroy()
        if self._cur_idx == idx and self._playing:
            pygame.mixer.music.stop()
            self._playing = False
            self._cur_idx = -1
            self._duration = 0.0
            self._seeking = False
            self.btn_play.configure(text="▶")
            self.prog.set(0)
            self.lbl_cur.configure(text="0:00")
            self.lbl_tot.configure(text="--:--")
            self.lbl_song.configure(text="Sin reproducción")
            self.lbl_artist.configure(text="Biblioteca local")

        try:
            os.remove(path)
        except Exception:
            return

        self.playlists = self._load_playlists()
        self._update_sidebar_playlists()

        current = self._current_playlist_name
        if current and current in self.playlists:
            songs = self.playlists[current]
            self._playlist = songs
            self._all_songs = songs
            self._build_song_rows(songs)
            self._update_playlist_meta(songs)
        else:
            self._show_selection(animated=False)

    @staticmethod
    def _playlist_size(songs):
        total = sum(os.path.getsize(p) for p in songs if os.path.exists(p))
        if total == 0:
            return "0 MB"
        if total < 1024 * 1024:
            return f"{total / 1024:.1f} KB"
        return f"{total / (1024 * 1024):.1f} MB"

    def _update_playlist_meta(self, songs):
        try:
            self._lbl_meta.configure(
                text=f"{len(songs)} canciones · {self._playlist_size(songs)} en disco · Formato MP3 local"
            )
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    #  VISTA 3 — DESCARGA Y BUSCADOR (ESTRUCTURA CLARA & MODERNA)
    # ══════════════════════════════════════════════════════════════════
    def _goto_download(self):
        def build(frame):
            top = ctk.CTkFrame(frame, fg_color="transparent")
            top.pack(fill="x", padx=36, pady=(32, 4))

            title_row = ctk.CTkFrame(top, fg_color="transparent")
            title_row.pack(anchor="w")

            ctk.CTkLabel(
                title_row, text="Descubrir y Descargar", font=F(26, "bold"), text_color=C_TEXT_PRIMARY
            ).pack(side="left")

            badge_box = ctk.CTkFrame(title_row, fg_color="transparent")
            badge_box.pack(side="left", padx=(12, 0))
            make_micro_badge(badge_box, "GESTOR OFFLINE", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

            ctk.CTkLabel(
                frame, text="Buscá en el catálogo online o importá pistas directas a tu almacenamiento local.",
                font=F(12), text_color=C_TEXT_SECONDARY
            ).pack(anchor="w", padx=36, pady=(0, 20))

            sc = ctk.CTkScrollableFrame(
                frame, fg_color="transparent",
                scrollbar_button_color=C_BG_PANEL,
                scrollbar_button_hover_color=C_HOVER
            )
            sc.pack(fill="both", expand=True, padx=26, pady=(0, 16))

            # ── PANEL 1: BUSCADOR ONLINE INTEGRADO ──
            card_search = ctk.CTkFrame(
                sc, fg_color=C_BG_PANEL, border_color=C_BORDER_CARD,
                border_width=1, corner_radius=R_CONTAINER
            )
            card_search.pack(fill="x", padx=10, pady=(0, 18))

            head_search = ctk.CTkFrame(card_search, fg_color="transparent")
            head_search.pack(fill="x", padx=20, pady=(18, 12))

            ctk.CTkLabel(
                head_search, text="Búsqueda en Catálogo Online",
                font=F(14, "bold"), text_color=C_TEXT_PRIMARY
            ).pack(side="left")

            make_micro_badge(head_search, "YOUTUBE STREAM", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

            row_search = ctk.CTkFrame(card_search, fg_color="transparent")
            row_search.pack(fill="x", padx=20, pady=(0, 12))

            self._yt_query_entry = ctk.CTkEntry(
                row_search, placeholder_text="Escribí artista, canción o tema...",
                height=38, corner_radius=R_INPUT, fg_color=C_BG_INPUT,
                border_color=C_BORDER_CARD, border_width=1,
                text_color=C_TEXT_PRIMARY, placeholder_text_color=C_TEXT_MUTED, font=F(13)
            )
            self._yt_query_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self._yt_query_entry.bind("<Return>", lambda e: self._iniciar_busqueda())

            self._btn_buscar = ctk.CTkButton(
                row_search, text="Buscar", width=96, height=38,
                corner_radius=R_BUTTON, border_width=0,
                fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
                text_color=C_TEXT_PRIMARY, font=F(13, "bold"),
                command=self._iniciar_busqueda
            )
            self._btn_buscar.pack(side="right")

            self._lbl_search_status = ctk.CTkLabel(
                card_search, text="", font=F(11), text_color=C_TEXT_MUTED
            )
            self._lbl_search_status.pack(anchor="w", padx=20, pady=(0, 8))

            self._search_results_frame = ctk.CTkScrollableFrame(
                card_search, fg_color="transparent", height=190,
                scrollbar_button_color=C_BG_PANEL_ALT, scrollbar_button_hover_color=C_HOVER
            )
            self._search_results_frame.pack(fill="x", padx=14, pady=(0, 14))

            # ── PANEL 2: DESCARGA DIRECTA A PLAYLIST LOCAL ──
            card_dl = ctk.CTkFrame(
                sc, fg_color=C_BG_PANEL, border_color=C_BORDER_CARD,
                border_width=1, corner_radius=R_CONTAINER
            )
            card_dl.pack(fill="x", padx=10, pady=(0, 18))

            head_dl = ctk.CTkFrame(card_dl, fg_color="transparent")
            head_dl.pack(fill="x", padx=20, pady=(18, 12))

            ctk.CTkLabel(
                head_dl, text="Importación Directa a Biblioteca Local",
                font=F(14, "bold"), text_color=C_TEXT_PRIMARY
            ).pack(side="left")

            make_micro_badge(head_dl, "CONVERSIÓN MP3", border_color=C_BORDER_BADGE, text_color=C_TEXT_MUTED)

            self._url_entry = ctk.CTkEntry(
                card_dl, placeholder_text="Pegá el enlace directo de YouTube o audio aquí...",
                height=38, corner_radius=R_INPUT, fg_color=C_BG_INPUT,
                border_color=C_BORDER_CARD, border_width=1,
                text_color=C_TEXT_PRIMARY, placeholder_text_color=C_TEXT_MUTED, font=F(12)
            )
            self._url_entry.pack(fill="x", padx=20, pady=(0, 14))

            row_dest = ctk.CTkFrame(card_dl, fg_color="transparent")
            row_dest.pack(fill="x", padx=20, pady=(0, 14))

            ctk.CTkLabel(
                row_dest, text="Guardar en Playlist Local:",
                font=F(12), text_color=C_TEXT_SECONDARY
            ).pack(side="left")

            pl_names = list(self.playlists.keys()) if self.playlists else ["(sin playlists)"]
            self._dest_var = ctk.StringVar(value=pl_names[0])
            self._menu_dest = ctk.CTkOptionMenu(
                row_dest, values=pl_names, variable=self._dest_var,
                height=34, corner_radius=R_INPUT, fg_color=C_BG_INPUT,
                button_color=C_BG_PANEL_ALT, button_hover_color=C_HOVER,
                dropdown_fg_color=C_BG_PANEL, text_color=C_TEXT_PRIMARY,
                font=F(12)
            )
            self._menu_dest.pack(side="right")

            # Botón Primario de Descarga (Acento Deep Purple #7C4DFF)
            self._btn_dl = ctk.CTkButton(
                card_dl, text="Descargar e Importar a Biblioteca",
                height=42, corner_radius=R_BUTTON, border_width=0,
                fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
                text_color=C_TEXT_PRIMARY, font=F(13, "bold"),
                command=self._start_download
            )
            self._btn_dl.pack(fill="x", padx=20, pady=(6, 12))

            self._dl_prog = ctk.CTkProgressBar(
                card_dl, height=4, corner_radius=R_SLIDER,
                fg_color=C_BG_PANEL_ALT, progress_color=C_ACCENT
            )
            self._dl_prog.set(0)
            self._dl_prog.pack(fill="x", padx=20, pady=(0, 8))

            self._dl_status = ctk.CTkLabel(
                card_dl, text="Listo para procesar", font=F(11), text_color=C_TEXT_MUTED
            )
            self._dl_status.pack(pady=(0, 16))

        self._switch(build, nav_btn=self.btn_download)

    def _iniciar_busqueda(self):
        query = self._yt_query_entry.get().strip()
        if not query:
            return
        self._btn_buscar.configure(state="disabled", text="...")
        self._lbl_search_status.configure(text="Buscando en catálogo online...", text_color=C_TEXT_MUTED)
        for w in self._search_results_frame.winfo_children():
            w.destroy()
        threading.Thread(target=self.ejecutar_busqueda, args=(query,), daemon=True).start()

    def ejecutar_busqueda(self, query: str):
        try:
            import yt_dlp
        except ImportError:
            self.after(0, lambda: self._btn_buscar.configure(state="normal", text="Buscar"))
            return

        opts = {
            "extract_flat": True, "quiet": True, "no_warnings": True,
            "ignoreerrors": True, "nocheckcertificate": True
        }
        if os.path.isfile(self.cookies_file):
            opts["cookiefile"] = self.cookies_file

        resultados = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if info and "entries" in info:
                for entry in info["entries"]:
                    if entry:
                        resultados.append({
                            "titulo": entry.get("title", "Sin título"),
                            "canal": entry.get("uploader", ""),
                            "duracion": entry.get("duration") or 0,
                            "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                        })
            if resultados:
                self.after(0, lambda r=resultados: self._mostrar_resultados(r))
            else:
                self.after(0, lambda: self._lbl_search_status.configure(text="Sin resultados.", text_color="#FFA726"))
        except Exception:
            pass
        finally:
            self.after(0, lambda: self._btn_buscar.configure(state="normal", text="Buscar"))

    def _mostrar_resultados(self, resultados: list):
        for w in self._search_results_frame.winfo_children():
            w.destroy()
        self._lbl_search_status.configure(text=f"{len(resultados)} resultados obtenidos", text_color=C_TEXT_SECONDARY)
        for res in resultados:
            dur_str = self._fmt(res["duracion"]) if res["duracion"] else "--:--"
            card = ctk.CTkFrame(
                self._search_results_frame, fg_color=C_BG_PANEL_ALT,
                border_color=C_BORDER_CARD, border_width=1, corner_radius=R_BUTTON
            )
            card.pack(fill="x", pady=3, padx=4)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=8)

            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                col, text=res["titulo"], font=F(12, "bold"), text_color=C_TEXT_PRIMARY, anchor="w"
            ).pack(anchor="w")

            ctk.CTkLabel(
                col, text=res["canal"], font=F(11), text_color=C_TEXT_MUTED, anchor="w"
            ).pack(anchor="w")

            ctk.CTkLabel(
                row, text=dur_str, font=F(11), text_color=C_TEXT_MUTED
            ).pack(side="right", padx=(0, 14))

            ctk.CTkButton(
                row, text="Preparar", width=76, height=28, corner_radius=R_BUTTON,
                fg_color=C_BG_PANEL, hover_color=C_HOVER, border_color=C_BORDER_CARD,
                border_width=1, text_color=C_TEXT_PRIMARY, font=F(11, "bold"),
                command=lambda u=res["url"]: self._preparar_descarga(u)
            ).pack(side="right")

    def _preparar_descarga(self, url: str):
        try:
            self._url_entry.delete(0, "end")
            self._url_entry.insert(0, url)
            self._lbl_search_status.configure(
                text="URL cargada en panel de descarga. Presioná 'Descargar e Importar'.",
                text_color=C_ACCENT
            )
        except Exception:
            pass

    def _start_download(self):
        url = self._url_entry.get().strip()
        if not url:
            return
        dest_name = self._dest_var.get()
        if dest_name == "(sin playlists)":
            return
        dest_path = os.path.join(PLAYLISTS_DIR, dest_name)
        os.makedirs(dest_path, exist_ok=True)
        self._btn_dl.configure(state="disabled")
        self._dl_prog.set(0)
        self._dl_status.configure(text="Iniciando descarga...", text_color=C_TEXT_MUTED)
        threading.Thread(target=self._download_worker, args=(url, dest_path), daemon=True).start()

    def _download_worker(self, url: str, dest_path: str):
        try:
            import yt_dlp
        except ImportError:
            self.after(0, lambda: self._btn_dl.configure(state="normal"))
            return

        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done  = d.get("downloaded_bytes", 0)
                if total:
                    self.after(0, lambda p=done/total: self._dl_prog.set(p))
                self.after(0, lambda: self._dl_status.configure(text="Descargando audio..."))
            elif d.get("status") == "finished":
                self.after(0, lambda: self._dl_prog.set(0.95))
                self.after(0, lambda: self._dl_status.configure(text="Procesando formato MP3..."))

        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(dest_path, "%(title)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "progress_hooks": [hook], "ignoreerrors": True, "nocheckcertificate": True, "quiet": True,
            "sleep_interval": 3, "max_sleep_interval": 7,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}
        }
        if os.path.isfile(self.cookies_file):
            opts["cookiefile"] = self.cookies_file
        if os.path.isfile(FFMPEG_PATH):
            opts["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.playlists = self._load_playlists()
            self._update_sidebar_playlists()
            self.after(0, lambda: self._dl_prog.set(1.0))
            self.after(0, lambda: self._dl_status.configure(text="¡Descarga completada en biblioteca local!", text_color="#66BB6A"))
            self._url_entry.delete(0, "end")
        except Exception:
            self.after(0, lambda: self._dl_status.configure(text="Falló la descarga.", text_color="#E53935"))
        finally:
            self.after(0, lambda: self._btn_dl.configure(state="normal"))

    # ══════════════════════════════════════════════════════════════════
    def _goto_selection(self):
        self._show_selection(animated=True)

    def _set_nav(self, active):
        for b in [self.btn_playlists, self.btn_download]:
            b.configure(fg_color="transparent", text_color=C_TEXT_SECONDARY)
        active.configure(fg_color=C_HOVER, text_color=C_TEXT_PRIMARY)

    def destroy(self):
        try:
            pygame.mixer.music.stop()
            pygame.quit()
        except Exception:
            pass
        super().destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ReproductorApp()
    app.mainloop()