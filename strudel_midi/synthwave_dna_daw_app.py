import json
import re
import tkinter as tk
import traceback
from pathlib import Path

try:
    from .synthwave_daw_app import (
        ACCENT,
        BG,
        FIELD,
        GRID_STEPS,
        GREEN,
        LINE,
        MAX_BARS,
        MUTED,
        PANEL,
        RED,
        STEPS_PER_BAR,
        TEXT,
        TrackRow,
        clamp,
        chord_notes,
        note_number,
        rtmidi2,
    )
except ImportError:
    from synthwave_daw_app import (
        ACCENT,
        BG,
        FIELD,
        GRID_STEPS,
        GREEN,
        LINE,
        MAX_BARS,
        MUTED,
        PANEL,
        RED,
        STEPS_PER_BAR,
        TEXT,
        TrackRow,
        clamp,
        chord_notes,
        note_number,
        rtmidi2,
    )


APP_FILE = Path(__file__).with_name("synthwave_dna_daw.json")
DNA_FILE = Path(__file__).with_name("dna_codes.json")
DNA_GATE = 0.8
CODONS_PER_BAR = 16
CODONS_PER_BEAT = 4
PITCHES = {"AA": 48, "AC": 50, "AG": 52, "AT": 55, "CA": 57, "CC": 60, "CG": 62, "CT": 64, "GA": 67, "GC": 69, "GG": 72, "GT": 74, "TA": 76, "TC": 79, "TG": 81, "TT": None}
DURATIONS = {"T": 0.25, "C": 0.5, "G": 1.0, "A": 2.0}
TRACK_TYPES = ["Bass", "Pad", "Arp", "Drums", "FX"]
LOOP = "#0e7490"


def dna_codons(text):
    clean = re.sub(r"[^ACGT]", "", text.upper())
    return [clean[i:i + 3] for i in range(0, len(clean) - 2, 3)]


def dna_events(codons):
    return [(PITCHES[codon[:2]], DURATIONS[codon[2]]) for codon in codons]


def load_dna_codes():
    if DNA_FILE.exists():
        return json.loads(DNA_FILE.read_text(encoding="utf-8"))
    return {"Voice A": "", "Voice B": ""}


def format_dna(text):
    parts = []
    for index, codon in enumerate(dna_codons(text)):
        if index and index % CODONS_PER_BAR == 0:
            parts.append("\n")
        elif index and index % CODONS_PER_BEAT == 0:
            parts.append("| ")
        parts.append(f"{codon} ")
    return "".join(parts).strip()


class GridTrackRow(TrackRow):
    def enabled(self):
        if self.mute_var.get():
            return False
        solo_on = any(track.solo_var.get() for track in self.daw.tracks)
        solo_on = solo_on or any(voice.solo_var.get() for voice in self.daw.dna_voices)
        return not solo_on or bool(self.solo_var.get())


class DnaVoiceRow:
    def __init__(self, daw, name, dna, default_port, data=None):
        self.daw = daw
        self.name = name
        self.codons = dna_codons(dna)
        self.pattern = dna_events(self.codons)
        self.step = 0
        self.start_step = 0
        self.loop_start = None
        self.loop_end = None
        self.active_step = None
        self.current_note = None
        self.name_var = tk.StringVar(value=name)
        self.port_var = tk.StringVar(value=daw.port_choices[min(default_port, len(daw.port_choices) - 1)] if daw.port_choices else "no MIDI ports")
        self.velocity_var = tk.IntVar(value=75)
        self.octave_var = tk.IntVar(value=0)
        self.mute_var = tk.IntVar(value=0)
        self.solo_var = tk.IntVar(value=0)
        self.cells = []

        if data:
            self.apply_data(data)

        self.left = tk.Frame(daw.inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        self.grid_frame = tk.Frame(daw.inner, bg=BG)
        self.build_left()
        self.build_grid()

    def build_left(self):
        tk.Button(self.left, textvariable=self.name_var, bg=PANEL, fg=ACCENT, activebackground=LINE, activeforeground=TEXT, relief="flat", width=10, anchor="w", command=self.daw.open_dna_editor).grid(row=0, column=0, sticky="ew", padx=(5, 3), pady=3)
        self.port_menu = tk.OptionMenu(self.left, self.port_var, *(self.daw.port_choices or ["no MIDI ports"]))
        self.port_menu.configure(bg=FIELD, fg=TEXT, activebackground=LINE, activeforeground=TEXT, highlightthickness=0, width=15)
        self.port_menu["menu"].configure(bg=FIELD, fg=TEXT)
        self.port_menu.grid(row=0, column=1, sticky="ew", padx=3, pady=3)
        tk.Label(self.left, text="V", bg=PANEL, fg=MUTED).grid(row=0, column=2, sticky="e", padx=(4, 1), pady=3)
        tk.Spinbox(self.left, from_=1, to=127, textvariable=self.velocity_var, width=4, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").grid(row=0, column=3, sticky="w", padx=2, pady=3)
        tk.Label(self.left, text="O", bg=PANEL, fg=MUTED).grid(row=0, column=4, sticky="e", padx=(4, 1), pady=3)
        tk.Spinbox(self.left, from_=-2, to=2, textvariable=self.octave_var, width=3, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").grid(row=0, column=5, sticky="w", padx=2, pady=3)
        tk.Checkbutton(self.left, text="M", variable=self.mute_var, bg=PANEL, fg=TEXT, selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT, command=self.daw.repaint_all).grid(row=0, column=6, sticky="w", padx=1, pady=1)
        tk.Checkbutton(self.left, text="S", variable=self.solo_var, bg=PANEL, fg=TEXT, selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT, command=self.daw.repaint_all).grid(row=0, column=7, sticky="w", padx=1, pady=1)
        self.left.grid_columnconfigure(0, weight=1)

    def build_grid(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.cells.clear()
        for index, codon in enumerate(self.codons):
            button = tk.Button(
                self.grid_frame,
                text=codon,
                width=4,
                height=1,
                bg=FIELD,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                command=lambda step=index: self.set_start(step),
            )
            button.bind("<Button-3>", lambda _event, step=index: self.set_loop(step))
            button.grid(row=0, column=index, padx=(1, 0), pady=1, sticky="nsew")
            self.cells.append(button)
        self.repaint()

    def set_dna(self, dna):
        self.codons = dna_codons(dna)
        self.pattern = dna_events(self.codons)
        self.start_step = min(self.start_step, max(0, len(self.pattern) - 1))
        if self.loop_start is not None and self.loop_end is not None:
            last = max(0, len(self.pattern) - 1)
            self.loop_start = min(self.loop_start, last)
            self.loop_end = min(self.loop_end, last)
        else:
            self.loop_start = None
            self.loop_end = None
        self.step = self.start_step
        self.build_grid()

    def grid(self, row):
        self.left.grid(row=row, column=0, sticky="nsew", padx=(0, 4), pady=1)
        self.grid_frame.grid(row=row, column=1, sticky="w", pady=1)

    def destroy(self):
        self.left.destroy()
        self.grid_frame.destroy()

    def set_port_choices(self, choices):
        current = self.port_var.get()
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for choice in choices:
            menu.add_command(label=choice, command=lambda value=choice: self.port_var.set(value))
        self.port_var.set(current if current in choices else choices[0])

    def set_start(self, step):
        self.start_step = step
        self.step = step
        self.repaint()
        self.daw.status(f"{self.name_var.get()} starts at {step + 1}")
        if self.daw.dna_editor:
            self.daw.dna_editor.repaint_blocks()

    def set_loop(self, step):
        self.loop_start = min(self.start_step, step)
        self.loop_end = max(self.start_step, step)
        self.step = self.loop_start
        self.repaint()
        self.daw.status(f"{self.name_var.get()} loop {self.loop_start + 1}-{self.loop_end + 1}")
        if self.daw.dna_editor:
            self.daw.dna_editor.repaint_blocks()
        return "break"

    def highlight(self, step):
        previous = self.active_step
        self.active_step = step
        for index in (previous, step, self.start_step):
            if index is not None and 0 <= index < len(self.cells):
                self.repaint_cell(index)
        if 0 <= step < len(self.cells):
            self.cells[step].configure(bg=ACCENT, fg="#111827")
        if self.daw.dna_editor:
            self.daw.dna_editor.repaint_blocks()

    def repaint(self):
        for index in range(len(self.cells)):
            self.repaint_cell(index)

    def repaint_cell(self, index):
        if index == self.active_step and self.daw.playing:
            bg, fg = ACCENT, "#111827"
        elif index == self.start_step:
            bg, fg = "#273956", TEXT
        elif self.loop_start is not None and self.loop_end is not None and self.loop_start <= index <= self.loop_end:
            bg, fg = LOOP, TEXT
        elif self.enabled() and self.codons[index][:2] != "TT":
            bg, fg = "#14532d", TEXT
        else:
            bg, fg = FIELD, MUTED
        self.cells[index].configure(bg=bg, fg=fg)

    def selected_port(self):
        choice = self.port_var.get()
        if choice in ("no MIDI ports", "rtmidi2 missing"):
            return None
        return int(choice.split(":", 1)[0])

    def enabled(self):
        if self.mute_var.get():
            return False
        solo_on = any(track.solo_var.get() for track in self.daw.tracks)
        solo_on = solo_on or any(voice.solo_var.get() for voice in self.daw.dna_voices)
        return not solo_on or bool(self.solo_var.get())

    def velocity(self):
        return clamp(int(self.velocity_var.get()), 1, 127)

    def octave(self):
        return clamp(int(self.octave_var.get()), -2, 2)

    def to_data(self):
        return {
            "name": self.name_var.get(),
            "port": self.selected_port(),
            "velocity": self.velocity_var.get(),
            "octave": self.octave_var.get(),
            "mute": self.mute_var.get(),
            "solo": self.solo_var.get(),
            "start_step": self.start_step,
            "loop_start": self.loop_start,
            "loop_end": self.loop_end,
        }

    def apply_data(self, data):
        self.name_var.set(data.get("name", self.name_var.get()))
        self.velocity_var.set(data.get("velocity", self.velocity_var.get()))
        self.octave_var.set(data.get("octave", self.octave_var.get()))
        self.mute_var.set(data.get("mute", 0))
        self.solo_var.set(data.get("solo", 0))
        self.start_step = min(data.get("start_step", 0), max(0, len(self.pattern) - 1))
        self.loop_start = data.get("loop_start")
        self.loop_end = data.get("loop_end")
        if self.loop_start is not None and self.loop_end is not None and self.pattern:
            last = len(self.pattern) - 1
            self.loop_start = min(self.loop_start, last)
            self.loop_end = min(self.loop_end, last)
        else:
            self.loop_start = None
            self.loop_end = None
        self.step = self.start_step
        port = data.get("port")
        if port is not None:
            for choice in self.daw.port_choices:
                if choice.startswith(f"{port}:"):
                    self.port_var.set(choice)
                    break


class DnaEditorWindow:
    def __init__(self, daw):
        self.daw = daw
        self.window = tk.Toplevel(daw.app)
        self.window.configure(bg=BG)
        self.window.title("DNA Voices")
        self.window.geometry("1120x640")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.panels = {}
        self.build_ui()
        self.load_from_app()

    def build_ui(self):
        top = tk.Frame(self.window, bg=BG)
        top.pack(fill="x", padx=16, pady=12)
        tk.Label(top, text="DNA Voices", bg=BG, fg=ACCENT, font=("Segoe UI", 20, "bold")).pack(side="left", padx=(0, 14))
        self.button(top, "Apply", ACCENT, self.apply, fg="#111827").pack(side="left", padx=4)
        self.button(top, "Save DNA", GREEN, self.save, width=10).pack(side="left", padx=4)
        self.button(top, "Reload File", "#1f2b3f", self.load_from_file, width=10).pack(side="left", padx=4)

        body = tk.Frame(self.window, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.voice_panel(body, "Voice 1", "Voice A", 0)
        self.voice_panel(body, "Voice 2", "Voice B", 1)

    def button(self, parent, text, bg, command, fg=TEXT, width=8):
        return tk.Button(parent, text=text, width=width, bg=bg, fg=fg, activebackground=LINE, activeforeground=TEXT, relief="flat", command=command)

    def voice_panel(self, parent, title, key, column):
        panel = tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        panel.grid(row=0, column=column, sticky="nsew", padx=6)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)
        head = tk.Frame(panel, bg=PANEL)
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        tk.Label(head, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(side="left")
        edit_button = self.button(head, "Edytuj", "#1f2b3f", lambda k=key: self.toggle_edit(k), width=8)
        edit_button.pack(side="right", padx=3)
        self.button(head, "Save DNA", GREEN, self.save, width=10).pack(side="right", padx=3)
        text = tk.Text(panel, bg=FIELD, fg=TEXT, insertbackground=ACCENT, selectbackground="#273956", relief="flat", font=("Consolas", 15), undo=True, wrap="word")
        text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        text.tag_configure("loop_codon", background=LOOP, foreground=TEXT)
        text.tag_configure("start_codon", background="#273956", foreground=TEXT)
        text.tag_configure("active_codon", background=ACCENT, foreground="#111827")
        text.bind("<Key>", lambda event, k=key: self.block_readonly_key(event, k))
        text.bind("<<Paste>>", lambda event, k=key: self.block_readonly_paste(event, k))
        text.bind("<Control-c>", lambda event: (event.widget.event_generate("<<Copy>>"), "break")[1])
        text.bind("<Control-C>", lambda event: (event.widget.event_generate("<<Copy>>"), "break")[1])
        self.panels[key] = {"title": title, "codons": [], "text": text, "editing": False, "edit_button": edit_button}

    def load_from_app(self):
        codes = {
            "Voice A": "".join(self.daw.dna_voices[0].codons) if len(self.daw.dna_voices) > 0 else "",
            "Voice B": "".join(self.daw.dna_voices[1].codons) if len(self.daw.dna_voices) > 1 else "",
        }
        self.set_codes(codes)
        self.daw.status("DNA loaded from app")

    def load_from_file(self):
        self.set_codes(load_dna_codes())
        self.daw.status(f"DNA loaded from {DNA_FILE.name}")

    def voice_for(self, key):
        index = 0 if key == "Voice A" else 1
        return self.daw.dna_voices[index] if len(self.daw.dna_voices) > index else None

    def set_codes(self, codes):
        for key, panel in self.panels.items():
            panel["editing"] = False
            panel["edit_button"].configure(text="Edytuj")
            panel["codons"] = dna_codons(codes.get(key, ""))
            self.render_text(key)

    def toggle_edit(self, key):
        panel = self.panels[key]
        if panel["editing"]:
            panel["codons"] = dna_codons(panel["text"].get("1.0", "end"))
            panel["editing"] = False
            panel["edit_button"].configure(text="Edytuj")
            self.render_text(key)
            return
        panel["editing"] = True
        panel["edit_button"].configure(text="Done")
        panel["text"].focus_set()

    def block_readonly_key(self, event, key):
        if self.panels[key]["editing"]:
            return None
        if event.state & 0x4 and event.keysym.lower() in {"a", "c"}:
            return None
        if event.keysym in {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Shift_L", "Shift_R", "Control_L", "Control_R"}:
            return None
        return "break"

    def block_readonly_paste(self, event, key):
        if not self.panels[key]["editing"]:
            return "break"
        return None

    def render_text(self, key):
        panel = self.panels[key]
        text = panel["text"]
        text.delete("1.0", "end")
        for index, codon in enumerate(panel["codons"]):
            if index and index % CODONS_PER_BAR == 0:
                text.insert("end", "\n")
            elif index and index % CODONS_PER_BEAT == 0:
                text.insert("end", "| ")
            start = text.index("end-1c")
            text.insert("end", codon)
            end = text.index("end-1c")
            text.tag_add(f"codon_{index}", start, end)
            text.insert("end", " ")
        self.repaint_text(key)

    def repaint_text(self, key):
        voice = self.voice_for(key)
        panel = self.panels[key]
        text = panel["text"]
        if not voice:
            return
        text.tag_remove("active_codon", "1.0", "end")
        text.tag_remove("start_codon", "1.0", "end")
        text.tag_remove("loop_codon", "1.0", "end")
        if voice.loop_start is not None and voice.loop_end is not None:
            for index in range(voice.loop_start, min(voice.loop_end + 1, len(panel["codons"]))):
                ranges = text.tag_ranges(f"codon_{index}")
                if ranges:
                    text.tag_add("loop_codon", ranges[0], ranges[1])
        for tag, index in (("start_codon", voice.start_step), ("active_codon", voice.active_step)):
            if index is not None and 0 <= index < len(panel["codons"]):
                ranges = text.tag_ranges(f"codon_{index}")
                if ranges:
                    text.tag_add(tag, ranges[0], ranges[1])
                    if tag == "active_codon":
                        text.see(ranges[0])
        text.tag_raise("start_codon")
        text.tag_raise("active_codon")

    def repaint_blocks(self):
        for key in self.panels:
            self.repaint_text(key)

    def codes(self):
        result = {}
        for key, panel in self.panels.items():
            panel["codons"] = dna_codons(panel["text"].get("1.0", "end"))
            result[key] = "".join(panel["codons"])
        return result

    def apply(self):
        self.daw.apply_dna_codes(self.codes())
        for key, panel in self.panels.items():
            panel["codons"] = dna_codons(panel["text"].get("1.0", "end"))
            if panel["editing"]:
                self.repaint_text(key)
            else:
                self.render_text(key)
        self.daw.status("DNA applied")

    def save(self):
        codes = self.codes()
        DNA_FILE.write_text(json.dumps(codes, indent=2), encoding="utf-8")
        self.daw.apply_dna_codes(codes)
        for key, panel in self.panels.items():
            panel["codons"] = dna_codons(panel["text"].get("1.0", "end"))
            if panel["editing"]:
                self.repaint_text(key)
            else:
                self.render_text(key)
        self.daw.status(f"saved {DNA_FILE.name}")

    def close(self):
        self.daw.dna_editor = None
        self.window.destroy()


class SynthwaveDnaDaw:
    def __init__(self):
        self.app = tk.Tk()
        self.app.configure(bg=BG)
        self.app.report_callback_exception = self.report_callback_exception
        self.app.title("Synthwave DNA Grid MIDI DAW")
        self.app.geometry("1280x620")
        self.tracks = []
        self.dna_voices = []
        self.outputs = {}
        self.active_notes = set()
        self.after_ids = []
        self.playing = False
        self.play_step_index = -1
        self.port_choices = []
        self.dna_editor = None
        self.add_kind_var = tk.StringVar(value="Bass")
        self.bpm_var = tk.IntVar(value=128)
        self.bars_var = tk.IntVar(value=4)

        self.build_ui()
        self.refresh_ports()
        self.load()

    def build_ui(self):
        top = tk.Frame(self.app, bg=BG)
        top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Synthwave DNA Grid", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 10))
        self.button(top, "Play", GREEN, self.play).pack(side="left", padx=4)
        self.button(top, "Stop", "#1f2b3f", self.stop).pack(side="left", padx=4)
        tk.Label(top, text="BPM", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.Spinbox(top, from_=40, to=220, textvariable=self.bpm_var, width=5, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").pack(side="left")
        tk.Label(top, text="Bars", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.Spinbox(top, from_=1, to=MAX_BARS, textvariable=self.bars_var, width=3, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").pack(side="left")
        tk.OptionMenu(top, self.add_kind_var, *TRACK_TYPES).pack(side="left", padx=(10, 4))
        self.button(top, "Add", ACCENT, self.add_selected_track, fg="#111827", width=5).pack(side="left", padx=3)
        self.button(top, "DNA", "#1f2b3f", self.open_dna_editor, width=5).pack(side="left", padx=3)
        self.button(top, "Save", ACCENT, self.save, fg="#111827", width=5).pack(side="left", padx=(10, 3))
        self.button(top, "Load", "#1f2b3f", self.load).pack(side="left", padx=4)
        self.button(top, "Ports", "#1f2b3f", self.refresh_ports, width=6).pack(side="left", padx=3)
        self.button(top, "Reset", RED, self.reset_midi, width=6).pack(side="left", padx=3)

        body = tk.Frame(self.app, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        xscroll = tk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        yscroll = tk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.build_header()
        self.status_box = tk.Text(self.app, height=4, bg=FIELD, fg=MUTED, insertbackground=ACCENT, selectbackground="#273956", relief="flat", font=("Consolas", 9), wrap="word")
        self.status_box.pack(fill="x", padx=12, pady=(0, 6))
        self.status_box.bind("<Control-c>", self.copy_status)
        self.status_box.bind("<Control-C>", self.copy_status)
        self.status("ready")

    def build_header(self):
        tk.Label(self.inner, text="Track", bg=BG, fg=MUTED, width=46, anchor="w").grid(row=0, column=0, sticky="ew", padx=(0, 4))
        grid = tk.Frame(self.inner, bg=BG)
        grid.grid(row=0, column=1, sticky="w", pady=(0, 2))
        self.header_cells = []
        for step in range(GRID_STEPS):
            text = f"Bar {step // STEPS_PER_BAR + 1}" if step % STEPS_PER_BAR == 0 else str(step % STEPS_PER_BAR + 1) if step % 4 == 0 else ""
            label = tk.Label(grid, text=text, width=4, bg="#101827" if step % STEPS_PER_BAR == 0 else FIELD, fg=MUTED, font=("Segoe UI", 7))
            label.grid(row=0, column=step, padx=(1, 0), sticky="ew")
            self.header_cells.append(label)

    def button(self, parent, text, bg, command, fg=TEXT, width=8):
        return tk.Button(parent, text=text, width=width, bg=bg, fg=fg, activebackground=LINE, activeforeground=TEXT, relief="flat", command=command)

    def status(self, text):
        self.status_box.configure(state="normal")
        self.status_box.delete("1.0", "end")
        self.status_box.insert("1.0", f"Status: {text}")
        self.status_box.configure(state="disabled")

    def report_callback_exception(self, exc_type, exc, tb):
        report = "".join(traceback.format_exception(exc_type, exc, tb))
        print(report, flush=True)
        self.status(report)

    def report_exception(self, label):
        report = f"{label}\n{traceback.format_exc()}"
        print(report, flush=True)
        self.status(report)

    def copy_status(self, _event=None):
        try:
            text = self.status_box.selection_get()
        except tk.TclError:
            text = self.status_box.get("1.0", "end").strip()
        self.app.clipboard_clear()
        self.app.clipboard_append(text)
        return "break"

    def refresh_ports(self):
        ports = rtmidi2.get_out_ports() if rtmidi2 else []
        self.port_choices = [f"{index}: {name}" for index, name in enumerate(ports)] or ["rtmidi2 missing" if not rtmidi2 else "no MIDI ports"]
        for row in self.tracks + self.dna_voices:
            row.set_port_choices(self.port_choices)
        self.status(f"{len(ports)} MIDI ports")

    def add_selected_track(self):
        self.add_track(self.add_kind_var.get())

    def add_track(self, kind, data=None):
        track = GridTrackRow(self, kind, data)
        self.tracks.append(track)
        self.layout_rows()
        return track

    def add_dna_voice(self, name, dna, default_port, data=None):
        voice = DnaVoiceRow(self, name, dna, default_port, data)
        self.dna_voices.append(voice)
        self.layout_rows()
        return voice

    def open_dna_editor(self):
        if self.dna_editor and self.dna_editor.window.winfo_exists():
            self.dna_editor.window.lift()
            return
        self.dna_editor = DnaEditorWindow(self)

    def apply_dna_codes(self, codes):
        if self.playing:
            self.stop()
        if len(self.dna_voices) >= 1:
            self.dna_voices[0].set_dna(codes.get("Voice A", ""))
        if len(self.dna_voices) >= 2:
            self.dna_voices[1].set_dna(codes.get("Voice B", ""))
        self.layout_rows()
        self.repaint_all()

    def remove_track(self, track):
        if self.playing:
            self.stop()
        self.tracks.remove(track)
        track.destroy()
        self.layout_rows()
        self.status("track removed")

    def layout_rows(self):
        row = 1
        for track in self.tracks:
            track.grid(row)
            row += 1
        for voice in self.dna_voices:
            voice.grid(row)
            row += 1
        self.inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def repaint_tracks(self):
        for track in self.tracks:
            track.repaint()

    def repaint_all(self):
        self.repaint_tracks()
        for voice in self.dna_voices:
            voice.repaint()

    def commit_edits(self):
        return all(track.finish_bass_edit(True) for track in self.tracks)

    def repaint_playhead(self, previous, current):
        for step in (previous, current):
            if 0 <= step < GRID_STEPS:
                active = self.playing and step == current
                self.header_cells[step].configure(bg=ACCENT if active else "#101827" if step % STEPS_PER_BAR == 0 else FIELD, fg="#111827" if active else MUTED)
                for track in self.tracks:
                    track.repaint_cell(step)

    def total_steps(self):
        return clamp(int(self.bars_var.get()), 1, MAX_BARS) * STEPS_PER_BAR

    def step_ms(self):
        return int((60000 / clamp(int(self.bpm_var.get()), 40, 220)) / 4)

    def load_demo_tracks(self):
        bass = self.add_track("Bass")
        pad = self.add_track("Pad")
        arp = self.add_track("Arp")
        drums = self.add_track("Drums")
        chords = [("Am9", "A2"), ("Fmaj7", "F2"), ("Cmaj7", "C2"), ("G6", "G2")]
        for bar, (chord, root) in enumerate(chords):
            start = bar * STEPS_PER_BAR
            pad.cells[start] = chord
            arp.cells[start] = chord
            for offset in range(0, STEPS_PER_BAR, 2):
                bass.cells[start + offset] = root if offset != 4 else root[0] + "3"
                drums.cells[start + offset] = "K+S"
        self.repaint_tracks()

    def save(self):
        if not self.commit_edits():
            return
        data = {
            "bpm": self.bpm_var.get(),
            "bars": self.bars_var.get(),
            "tracks": [track.to_data() for track in self.tracks],
            "dna_voices": [voice.to_data() for voice in self.dna_voices],
        }
        APP_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.status(f"saved {APP_FILE.name}")

    def load(self):
        if self.playing:
            self.stop()
        data = json.loads(APP_FILE.read_text(encoding="utf-8")) if APP_FILE.exists() else {}
        for row in list(self.tracks) + list(self.dna_voices):
            row.destroy()
        self.tracks.clear()
        self.dna_voices.clear()
        self.bpm_var.set(data.get("bpm", 128))
        self.bars_var.set(data.get("bars", 4))
        if data.get("tracks"):
            for track_data in data["tracks"]:
                self.add_track(track_data.get("kind", "Bass"), track_data)
        else:
            self.load_demo_tracks()
        codes = load_dna_codes()
        dna_settings = data.get("dna_voices", [{}, {}])
        self.add_dna_voice("Voice 1", codes.get("Voice A", ""), 1, dna_settings[0] if len(dna_settings) > 0 else None)
        self.add_dna_voice("Voice 2", codes.get("Voice B", ""), 2, dna_settings[1] if len(dna_settings) > 1 else None)
        self.repaint_all()
        self.status(f"loaded {APP_FILE.name if APP_FILE.exists() else 'demo + dna_codes.json'}")

    def open_outputs(self):
        if not rtmidi2:
            raise RuntimeError("rtmidi2 missing")
        ports = {track.selected_port() for track in self.tracks if track.enabled() and track.selected_port() is not None}
        ports |= {voice.selected_port() for voice in self.dna_voices if voice.enabled() and voice.pattern and voice.selected_port() is not None}
        if not ports:
            raise RuntimeError("no MIDI ports selected")
        for port in sorted(ports):
            output = rtmidi2.MidiOut()
            output.open_port(port)
            self.outputs[port] = output

    def send_notes(self, track, notes, duration_steps=1):
        port = track.selected_port()
        output = self.outputs.get(port)
        if not output:
            return
        channel = track.channel()
        velocity = track.velocity()
        duration_ms = max(20, int(self.step_ms() * duration_steps * track.gate()))
        for note in notes:
            self.send_note(port, channel, note, velocity, duration_ms)

    def send_note(self, port, channel, note, velocity, duration_ms):
        output = self.outputs.get(port)
        if not output:
            return
        note = clamp(note, 0, 127)
        output.send_noteon(channel, note, velocity)
        self.active_notes.add((port, channel, note))
        after_id = self.app.after(duration_ms, lambda p=port, ch=channel, n=note: self.send_note_off(p, ch, n))
        self.after_ids.append(after_id)

    def send_note_off(self, port, channel, note):
        output = self.outputs.get(port)
        if output:
            output.send_noteoff(channel, note)
        self.active_notes.discard((port, channel, note))

    def play_track_step(self, track, step, total_steps):
        if not track.enabled():
            return
        value = track.cells[step]
        if track.kind == "Bass" and value:
            self.send_notes(track, [note_number(value, 2)])
        elif track.kind == "Pad" and value:
            self.send_notes(track, chord_notes(value, 4), track.next_filled_step(step, total_steps) - step)
        elif track.kind == "Arp":
            chord, offset = track.active_chord(step, total_steps)
            if chord:
                notes = chord_notes(chord, 4)
                self.send_notes(track, [notes[offset % len(notes)]])
        elif track.kind == "Drums" and value:
            notes = [36 if token == "K" else 38 for token in value.split("+") if token in ("K", "S")]
            self.send_notes(track, notes)
        elif track.kind == "FX" and value:
            fx_notes = {"NOISE": 84, "RISER": 85, "CYM": 49, "CHOP": 86}
            self.send_notes(track, [fx_notes[value]])

    def play_grid_step(self):
        if not self.playing:
            return
        total_steps = self.total_steps()
        previous = self.play_step_index
        self.play_step_index = (self.play_step_index + 1) % total_steps
        self.repaint_playhead(previous, self.play_step_index)
        for track in self.tracks:
            self.play_track_step(track, self.play_step_index, total_steps)
        self.after_ids.append(self.app.after(self.step_ms(), self.play_grid_step))

    def play_dna_voice(self, voice):
        if not self.playing or not voice.pattern:
            return
        loop_on = voice.loop_start is not None and voice.loop_end is not None
        if loop_on and (voice.step < voice.loop_start or voice.step > voice.loop_end):
            voice.step = voice.loop_start
        index = voice.step % len(voice.pattern)
        note, duration = voice.pattern[index]
        voice.step += 1
        if loop_on and voice.step > voice.loop_end:
            voice.step = voice.loop_start
        voice.highlight(index)
        duration_ms = int((60000 / clamp(int(self.bpm_var.get()), 40, 220)) * duration)
        if note is not None and voice.enabled():
            port = voice.selected_port()
            note += voice.octave() * 12
            self.send_note(port, 0, note, voice.velocity(), max(20, int(duration_ms * DNA_GATE)))
        self.after_ids.append(self.app.after(duration_ms, lambda v=voice: self.play_dna_voice(v)))

    def play(self):
        if self.playing:
            return
        try:
            if not self.commit_edits():
                return
            self.stop()
            self.open_outputs()
            self.playing = True
            self.play_step_index = -1
            for voice in self.dna_voices:
                voice.step = voice.start_step
            self.play_grid_step()
            for voice in self.dna_voices:
                self.play_dna_voice(voice)
            self.status("playing grid + DNA")
        except Exception as err:
            self.stop()
            self.report_exception("play failed")

    def stop(self):
        self.playing = False
        for after_id in self.after_ids:
            try:
                self.app.after_cancel(after_id)
            except Exception:
                pass
        self.after_ids.clear()
        self.all_notes_off()
        for output in self.outputs.values():
            output.close_port()
        self.outputs.clear()
        previous = self.play_step_index
        self.play_step_index = -1
        self.repaint_playhead(previous, -1)
        for voice in self.dna_voices:
            voice.active_step = None
            voice.repaint()
        if self.dna_editor:
            self.dna_editor.repaint_blocks()

    def all_notes_off(self):
        for port, channel, note in list(self.active_notes):
            output = self.outputs.get(port)
            if output:
                output.send_noteoff(channel, note)
        self.active_notes.clear()
        for output in self.outputs.values():
            for channel in range(16):
                output.send_cc(channel, 120, 0)
                output.send_cc(channel, 123, 0)

    def reset_midi(self):
        self.stop()
        if not rtmidi2:
            return self.status("rtmidi2 missing")
        errors = 0
        for index, _ in enumerate(rtmidi2.get_out_ports()):
            output = rtmidi2.MidiOut()
            opened = False
            try:
                output.open_port(index)
                opened = True
                for channel in range(16):
                    output.send_cc(channel, 120, 0)
                    output.send_cc(channel, 123, 0)
                    for note in range(128):
                        output.send_noteoff(channel, note)
            except Exception:
                errors += 1
            if opened:
                output.close_port()
        self.status("all MIDI notes off" if not errors else f"reset skipped {errors} busy ports")

    def run(self):
        self.app.protocol("WM_DELETE_WINDOW", lambda: (self.stop(), self.app.destroy()))
        self.app.mainloop()


if __name__ == "__main__":
    SynthwaveDnaDaw().run()
