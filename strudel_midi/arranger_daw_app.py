import copy
import json
import re
import tkinter as tk
import traceback
from pathlib import Path

try:
    import rtmidi2
except ImportError:
    rtmidi2 = None


BG = "#070b12"
PANEL = "#111827"
FIELD = "#050a10"
LINE = "#26344f"
TEXT = "#eaf2ff"
MUTED = "#94a3b8"
ACCENT = "#f4ad22"
GREEN = "#2f9654"
RED = "#70333d"
LOOP = "#0e7490"

PROJECT_FILE = Path(__file__).with_name("arranger_daw.json")
SONG_BARS = 64
STEPS_PER_BAR = 16
CODONS_PER_BAR = 16
CODONS_PER_BEAT = 4
DNA_GATE = 0.8
DNA_DELAY_MS = 5
BAR_WIDTH = 48

NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHORDS = {
    "": [0, 4, 7],
    "m": [0, 3, 7],
    "5": [0, 7],
    "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9],
    "7": [0, 4, 7, 10],
    "m7": [0, 3, 7, 10],
    "maj7": [0, 4, 7, 11],
    "9": [0, 4, 7, 10, 14],
    "m9": [0, 3, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
    "add9": [0, 4, 7, 14],
}
PITCHES = {"AA": 48, "AC": 50, "AG": 52, "AT": 55, "CA": 57, "CC": 60, "CG": 62, "CT": 64, "GA": 67, "GC": 69, "GG": 72, "GT": 74, "TA": 76, "TC": 79, "TG": 81, "TT": None}
DURATIONS = {"T": 0.25, "C": 0.5, "G": 1.0, "A": 2.0}
DRUM_NOTES = {"K": 36, "S": 38}
FX_NOTES = {"NOISE": 84, "RISER": 85, "CYM": 49, "CHOP": 86}

TRACKS = [
    {"id": "bass", "name": "Bass", "kind": "Bass", "channel": 2, "velocity": 88, "gate": 55},
    {"id": "pad", "name": "Pad", "kind": "Pad", "channel": 3, "velocity": 48, "gate": 92},
    {"id": "arp", "name": "Arp", "kind": "Arp", "channel": 4, "velocity": 36, "gate": 35},
    {"id": "drums", "name": "Drums", "kind": "Drums", "channel": 10, "velocity": 96, "gate": 30},
    {"id": "fx", "name": "FX", "kind": "FX", "channel": 5, "velocity": 64, "gate": 75},
    {"id": "voice1", "name": "Voice 1", "kind": "DNA", "channel": 1, "velocity": 75, "gate": 80},
    {"id": "voice2", "name": "Voice 2", "kind": "DNA", "channel": 1, "velocity": 75, "gate": 80},
]

INSTRUMENTS = {
    "Bass": {"kind": "Bass", "channel": 2, "velocity": 88, "gate": 55},
    "Pad": {"kind": "Pad", "channel": 3, "velocity": 48, "gate": 92},
    "Arp": {"kind": "Arp", "channel": 4, "velocity": 36, "gate": 35},
    "Drums": {"kind": "Drums", "channel": 10, "velocity": 96, "gate": 30},
    "FX": {"kind": "FX", "channel": 5, "velocity": 64, "gate": 75},
    "Voice": {"kind": "DNA", "channel": 1, "velocity": 75, "gate": 80},
}

PALETTES = {
    "Pad": ["", "Am9", "Fmaj7", "Cmaj7", "G6", "Em9", "Dm9", "Bbmaj7"],
    "Arp": ["", "Am9", "Fmaj7", "Cmaj7", "G6", "Em9", "Dm9", "Bbmaj7"],
    "Drums": ["", "K", "K+S", "S"],
    "FX": ["", "NOISE", "RISER", "CYM", "CHOP"],
}
COLORS = {
    "Bass": "#1f7a4a",
    "Pad": "#315a9c",
    "Arp": "#a66a21",
    "Drums": "#984052",
    "FX": "#6d5a26",
    "DNA": "#14532d",
}


def clamp(value, low, high):
    return max(low, min(high, value))


def note_number(name, default_octave=4):
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)?", name)
    if not match:
        raise ValueError(f"Bad note: {name}")
    note, accidental, octave = match.groups()
    semitone = NOTE_BASE[note.upper()]
    semitone += 1 if accidental == "#" else -1 if accidental == "b" else 0
    midi = 12 * (int(octave or default_octave) + 1) + semitone
    if not 0 <= midi <= 127:
        raise ValueError(f"Note outside MIDI range: {name}")
    return midi


def normalize_note(name):
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(-?\d+)\s*", name)
    if not match:
        raise ValueError("Note must look like A1, C#2 or Bb3")
    note, accidental, octave = match.groups()
    normalized = f"{note.upper()}{accidental}{octave}"
    note_number(normalized)
    return normalized


def chord_notes(name, default_octave=4):
    match = re.fullmatch(r"([A-Ga-g][#b]?)(.*)", name)
    if not match:
        raise ValueError(f"Bad chord: {name}")
    root, quality = match.groups()
    if quality not in CHORDS:
        raise ValueError(f"Unknown chord: {name}")
    base = note_number(root, default_octave)
    return [base + interval for interval in CHORDS[quality]]


def dna_codons(text):
    clean = re.sub(r"[^ACGT]", "", text.upper())
    return [clean[i:i + 3] for i in range(0, len(clean) - 2, 3)]


def dna_events(codons):
    return [(PITCHES[codon[:2]], DURATIONS[codon[2]]) for codon in codons if len(codon) == 3]


def default_clip(track, start_bar, bars):
    clip = {"start": start_bar, "bars": bars, "name": f"{track['name']} {start_bar + 1}", "cells": [""] * (bars * STEPS_PER_BAR)}
    if track["kind"] == "DNA":
        clip["codons"] = []
        clip["dna_step"] = 0
        clip["dna_wait"] = 0
        clip["active_codon"] = None
    return clip


class ArrangerDaw:
    def __init__(self):
        self.app = tk.Tk()
        self.app.configure(bg=BG)
        self.app.report_callback_exception = self.report_callback_exception
        self.app.title("Synthwave Arranger MIDI DAW")
        self.app.geometry("1320x720")
        self.bpm_var = tk.IntVar(value=128)
        self.start_bar_var = tk.IntVar(value=1)
        self.clip_bars_var = tk.StringVar(value="1")
        self.tracks = []
        self.port_choices = []
        self.outputs = {}
        self.active_notes = set()
        self.after_ids = []
        self.playing = False
        self.play_step_index = -1
        self.editor = None
        self.track_rows = {}
        self.header_cells = []
        self.drag_clip = None
        self.build_ui()
        self.refresh_ports()
        self.load()

    def build_ui(self):
        top = tk.Frame(self.app, bg=BG)
        top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Synthwave Arranger", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 10))
        self.button(top, "Play", GREEN, self.play).pack(side="left", padx=4)
        self.button(top, "Stop", "#1f2b3f", self.stop).pack(side="left", padx=4)
        tk.Label(top, text="BPM", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.Spinbox(top, from_=40, to=220, textvariable=self.bpm_var, width=5, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").pack(side="left")
        tk.Label(top, text="Clip", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.OptionMenu(top, self.clip_bars_var, "1", "2", "4").pack(side="left")
        self.button(top, "Add Instrument", "#1f2b3f", self.open_add_instrument, width=13).pack(side="left", padx=(10, 3))
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

        self.status_box = tk.Text(self.app, height=4, bg=FIELD, fg=MUTED, insertbackground=ACCENT, selectbackground="#273956", relief="flat", font=("Consolas", 9), wrap="word")
        self.status_box.pack(fill="x", padx=12, pady=(0, 6))
        self.status_box.bind("<Control-c>", self.copy_status)
        self.status_box.bind("<Control-C>", self.copy_status)
        self.status("ready")

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
        for track in self.tracks:
            if "port_var" in track:
                self.set_port_choices(track)
        self.status(f"{len(ports)} MIDI ports")

    def set_port_choices(self, track):
        current = track["port_var"].get()
        menu = track["port_menu"]["menu"]
        menu.delete(0, "end")
        for choice in self.port_choices:
            menu.add_command(label=choice, command=lambda value=choice, t=track: t["port_var"].set(value))
        track["port_var"].set(current if current in self.port_choices else self.port_choices[0])

    def selected_port(self, track):
        choice = track["port_var"].get()
        if choice in ("no MIDI ports", "rtmidi2 missing"):
            return None
        return int(choice.split(":", 1)[0])

    def load_default_tracks(self):
        self.tracks = []
        for spec in TRACKS:
            track = dict(spec)
            track["clips"] = []
            self.tracks.append(track)

    def new_track(self, instrument):
        spec = dict(INSTRUMENTS[instrument])
        base = "Voice" if spec["kind"] == "DNA" else instrument
        number = sum(1 for track in self.tracks if track["kind"] == spec["kind"] and track["name"].startswith(base)) + 1
        track_id = f"{base.lower()}{number}"
        used_ids = {track["id"] for track in self.tracks}
        while track_id in used_ids:
            number += 1
            track_id = f"{base.lower()}{number}"
        spec.update({"id": track_id, "name": f"{base} {number}", "clips": []})
        return spec

    def open_add_instrument(self):
        window = tk.Toplevel(self.app)
        window.configure(bg=BG)
        window.title("Add instrument")
        window.geometry("260x110")
        instrument_var = tk.StringVar(value="Bass")
        tk.Label(window, text="Instrument", bg=BG, fg=MUTED).pack(anchor="w", padx=10, pady=(10, 3))
        tk.OptionMenu(window, instrument_var, *INSTRUMENTS.keys()).pack(fill="x", padx=10)
        self.button(window, "Add", ACCENT, lambda: self.add_instrument(window, instrument_var.get()), fg="#111827", width=8).pack(anchor="e", padx=10, pady=10)

    def add_instrument(self, window, instrument):
        self.sync_track_controls()
        self.tracks.append(self.new_track(instrument))
        self.build_arranger()
        window.destroy()
        self.status(f"added {instrument}")

    def sync_track_controls(self):
        for track in self.tracks:
            if "velocity_var" in track:
                track["velocity"] = track["velocity_var"].get()
                track["mute"] = track["mute_var"].get()
                track["solo"] = track["solo_var"].get()
                track["saved_port"] = self.selected_port(track)

    def build_arranger(self):
        for widget in self.inner.winfo_children():
            widget.destroy()
        self.track_rows.clear()
        tk.Label(self.inner, text="Track", bg=BG, fg=MUTED, width=35, anchor="w").grid(row=0, column=0, sticky="ew", padx=(0, 4))
        header = tk.Frame(self.inner, bg=BG)
        header.grid(row=0, column=1, sticky="w", pady=(0, 2))
        self.header_cells = []
        for bar in range(SONG_BARS):
            header.grid_columnconfigure(bar, minsize=BAR_WIDTH)
            label = tk.Label(header, text=str(bar + 1), width=1, bg="#101827" if bar % 4 == 0 else FIELD, fg=MUTED, font=("Segoe UI", 8), cursor="hand2")
            label.bind("<Button-1>", lambda _event, b=bar: self.play_from_bar(b + 1))
            label.grid(row=0, column=bar, padx=(1, 0), sticky="ew")
            self.header_cells.append(label)
        for row, track in enumerate(self.tracks, start=1):
            self.build_track_row(row, track)
        self.inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def build_track_row(self, row, track):
        left = tk.Frame(self.inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        left.grid(row=row, column=0, sticky="nsew", padx=(0, 4), pady=1)
        tk.Label(left, text=track["name"], bg=PANEL, fg=ACCENT, width=10, anchor="w").grid(row=0, column=0, sticky="ew", padx=(5, 3), pady=3)
        port_var = tk.StringVar(value=self.port_choices[0] if self.port_choices else "no MIDI ports")
        port_menu = tk.OptionMenu(left, port_var, *(self.port_choices or ["no MIDI ports"]))
        port_menu.configure(bg=FIELD, fg=TEXT, activebackground=LINE, activeforeground=TEXT, highlightthickness=0, width=15)
        port_menu["menu"].configure(bg=FIELD, fg=TEXT)
        port_menu.grid(row=0, column=1, sticky="ew", padx=3, pady=3)
        if track.get("saved_port") is not None:
            for choice in self.port_choices:
                if choice.startswith(f"{track['saved_port']}:"):
                    port_var.set(choice)
                    break
        velocity_var = tk.IntVar(value=track.get("velocity", 75))
        tk.Label(left, text="V", bg=PANEL, fg=MUTED).grid(row=0, column=2, sticky="e", padx=(4, 1), pady=3)
        tk.Spinbox(left, from_=1, to=127, textvariable=velocity_var, width=4, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").grid(row=0, column=3, sticky="w", padx=2, pady=3)
        mute_var = tk.IntVar(value=track.get("mute", 0))
        solo_var = tk.IntVar(value=track.get("solo", 0))
        tk.Checkbutton(left, text="M", variable=mute_var, bg=PANEL, fg=TEXT, selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT, command=self.repaint_arranger).grid(row=0, column=4, sticky="w", padx=1, pady=1)
        tk.Checkbutton(left, text="S", variable=solo_var, bg=PANEL, fg=TEXT, selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT, command=self.repaint_arranger).grid(row=0, column=5, sticky="w", padx=1, pady=1)
        track.update({"port_var": port_var, "port_menu": port_menu, "velocity_var": velocity_var, "mute_var": mute_var, "solo_var": solo_var})

        timeline = tk.Frame(self.inner, bg=BG)
        timeline.grid(row=row, column=1, sticky="w", pady=1)
        for bar in range(SONG_BARS):
            timeline.grid_columnconfigure(bar, minsize=BAR_WIDTH)
        self.track_rows[track["id"]] = timeline
        self.render_track_timeline(track)

    def render_track_timeline(self, track):
        timeline = self.track_rows[track["id"]]
        for widget in timeline.winfo_children():
            widget.destroy()
        clips_by_start = {clip["start"]: clip for clip in track["clips"]}
        covered = set()
        bar = 0
        while bar < SONG_BARS:
            if bar in clips_by_start:
                clip = clips_by_start[bar]
                bars = clamp(int(clip.get("bars", 1)), 1, 4)
                color = COLORS[track["kind"]]
                button = tk.Button(timeline, text=f"{clip.get('name', track['name'])}\n{bars}b", width=1, height=2, bg=color, fg=TEXT, activebackground=LINE, activeforeground=TEXT, relief="flat")
                button.bind("<ButtonPress-1>", lambda event, t=track, c=clip: self.start_clip_drag(event, t, c))
                button.bind("<B1-Motion>", self.update_clip_drag)
                button.bind("<ButtonRelease-1>", lambda event, t=track, c=clip: self.finish_clip_drag(event, t, c))
                button.bind("<Button-3>", lambda event, t=track, c=clip: self.show_clip_menu(event, t, c))
                button.grid(row=0, column=bar, columnspan=bars, padx=(1, 0), pady=1, sticky="nsew")
                covered.update(range(bar, min(SONG_BARS, bar + bars)))
                bar += bars
                continue
            if bar in covered:
                bar += 1
                continue
            button = tk.Button(timeline, text="", width=1, height=2, bg="#101827" if bar % 4 == 0 else FIELD, fg=MUTED, activebackground=LINE, activeforeground=TEXT, relief="flat", command=lambda t=track, b=bar: self.add_clip(t, b))
            button.grid(row=0, column=bar, padx=(1, 0), pady=1, sticky="nsew")
            bar += 1

    def repaint_arranger(self):
        for track in self.tracks:
            self.render_track_timeline(track)

    def add_clip(self, track, bar):
        bars = clamp(int(self.clip_bars_var.get()), 1, 4)
        if bar + bars > SONG_BARS:
            bars = SONG_BARS - bar
        if self.clip_overlaps(track, bar, bars):
            return self.status("clip overlaps another clip")
        clip = default_clip(track, bar, bars)
        track["clips"].append(clip)
        track["clips"].sort(key=lambda item: item["start"])
        self.render_track_timeline(track)
        self.open_clip_editor(track, clip)

    def clip_overlaps(self, track, start, bars, ignore=None):
        return any(other is not ignore and max(start, other["start"]) < min(start + bars, other["start"] + other["bars"]) for other in track["clips"])

    def show_clip_menu(self, event, track, clip):
        menu = tk.Menu(self.app, tearoff=0, bg=FIELD, fg=TEXT, activebackground=LINE, activeforeground=TEXT)
        menu.add_command(label="Copy beside", command=lambda: self.copy_clip_beside(track, clip))
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def copy_clip_beside(self, track, clip):
        bars = clamp(int(clip.get("bars", 1)), 1, 4)
        start = clip["start"] + bars
        if start + bars > SONG_BARS:
            return self.status("no room to copy clip")
        if self.clip_overlaps(track, start, bars):
            return self.status("copy overlaps another clip")
        new_clip = copy.deepcopy(clip)
        new_clip["start"] = start
        new_clip["name"] = f"{clip.get('name', track['name'])} copy"
        new_clip["dna_step"] = 0
        new_clip["dna_wait"] = 0
        new_clip["active_codon"] = None
        track["clips"].append(new_clip)
        track["clips"].sort(key=lambda item: item["start"])
        self.render_track_timeline(track)
        self.status("clip copied")

    def start_clip_drag(self, event, track, clip):
        self.drag_clip = {"track": track, "clip": clip, "x": event.x_root, "y": event.y_root, "moved": False}
        return "break"

    def update_clip_drag(self, event):
        if self.drag_clip and (abs(event.x_root - self.drag_clip["x"]) > 4 or abs(event.y_root - self.drag_clip["y"]) > 4):
            self.drag_clip["moved"] = True
            event.widget.configure(cursor="fleur")
        return "break"

    def finish_clip_drag(self, event, track, clip):
        drag = self.drag_clip
        self.drag_clip = None
        event.widget.configure(cursor="")
        if not drag or drag["track"] is not track or drag["clip"] is not clip:
            return "break"
        if not drag["moved"]:
            self.open_clip_editor(track, clip)
            return "break"
        bars = clamp(int(clip.get("bars", 1)), 1, 4)
        timeline = self.track_rows[track["id"]]
        target = clamp((event.x_root - timeline.winfo_rootx()) // BAR_WIDTH, 0, SONG_BARS - bars)
        self.move_clip(track, clip, target)
        return "break"

    def move_clip(self, track, clip, start):
        bars = clamp(int(clip.get("bars", 1)), 1, 4)
        if self.clip_overlaps(track, start, bars, ignore=clip):
            return self.status("move overlaps another clip")
        clip["start"] = start
        track["clips"].sort(key=lambda item: item["start"])
        self.render_track_timeline(track)
        self.status(f"clip moved to bar {start + 1}")

    def delete_clip(self, track, clip):
        track["clips"].remove(clip)
        self.render_track_timeline(track)
        self.status("clip removed")
        return "break"

    def open_clip_editor(self, track, clip):
        if self.editor and self.editor.window.winfo_exists():
            self.editor.close()
        self.editor = ClipEditor(self, track, clip)

    def resize_clip(self, track, clip, bars):
        bars = clamp(int(bars), 1, 4)
        if clip["start"] + bars > SONG_BARS:
            bars = SONG_BARS - clip["start"]
        if self.clip_overlaps(track, clip["start"], bars, ignore=clip):
            return self.status("clip resize overlaps another clip")
        old_steps = clip["bars"] * STEPS_PER_BAR
        clip["bars"] = bars
        new_steps = bars * STEPS_PER_BAR
        if track["kind"] == "DNA":
            codons = [codon for codon in clip.get("codons", []) if codon]
            clip["codons"] = codons[:bars * CODONS_PER_BAR]
        else:
            clip["cells"] = (clip.get("cells", [""] * old_steps) + [""] * new_steps)[:new_steps]
        self.render_track_timeline(track)
        if self.editor:
            self.editor.rebuild()
        self.status(f"clip length {bars} bars")

    def total_steps(self):
        return SONG_BARS * STEPS_PER_BAR

    def step_ms(self):
        return int((60000 / clamp(int(self.bpm_var.get()), 40, 220)) / 4)

    def clip_at_step(self, track, step):
        bar = step // STEPS_PER_BAR
        for clip in track["clips"]:
            if clip["start"] <= bar < clip["start"] + clip["bars"]:
                return clip
        return None

    def enabled(self, track):
        if track["mute_var"].get():
            return False
        solo_on = any(item["solo_var"].get() for item in self.tracks)
        return not solo_on or bool(track["solo_var"].get())

    def open_outputs(self):
        if not rtmidi2:
            raise RuntimeError("rtmidi2 missing")
        ports = {self.selected_port(track) for track in self.tracks if self.enabled(track) and self.selected_port(track) is not None}
        if not ports:
            raise RuntimeError("no MIDI ports selected")
        for port in sorted(ports):
            output = rtmidi2.MidiOut()
            output.open_port(port)
            self.outputs[port] = output

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

    def send_notes(self, track, notes, duration_steps=1, gate=None):
        port = self.selected_port(track)
        if port not in self.outputs:
            return
        gate = (track.get("gate", 80) / 100) if gate is None else gate
        duration_ms = max(20, int(self.step_ms() * duration_steps * gate))
        channel = clamp(int(track["channel"]), 1, 16) - 1
        velocity = clamp(int(track["velocity_var"].get()), 1, 127)
        for note in notes:
            self.send_note(port, channel, note, velocity, duration_ms)

    def next_filled_step(self, clip, local_step):
        cells = clip.get("cells", [])
        for index in range(local_step + 1, len(cells)):
            if cells[index]:
                return index
        return len(cells)

    def active_chord(self, clip, local_step):
        cells = clip.get("cells", [])
        filled = [index for index, value in enumerate(cells) if value and index <= local_step]
        if not filled:
            return None, 0
        source = filled[-1]
        return cells[source], local_step - source

    def play_clip_step(self, track, clip, local_step):
        if not self.enabled(track):
            return
        value = clip.get("cells", [""])[local_step]
        kind = track["kind"]
        if kind == "Bass" and value:
            self.send_notes(track, [note_number(value, 2)], self.next_filled_step(clip, local_step) - local_step, gate=1.0)
        elif kind == "Pad" and value:
            self.send_notes(track, chord_notes(value, 4), self.next_filled_step(clip, local_step) - local_step)
        elif kind == "Arp":
            chord, offset = self.active_chord(clip, local_step)
            if chord:
                notes = chord_notes(chord, 4)
                self.send_notes(track, [notes[offset % len(notes)]])
        elif kind == "Drums" and value:
            notes = [DRUM_NOTES[token] for token in value.split("+") if token in DRUM_NOTES]
            self.send_notes(track, notes)
        elif kind == "FX" and value:
            self.send_notes(track, [FX_NOTES[value]])

    def play_dna_clip_step(self, track, clip, local_step):
        if not self.enabled(track):
            return
        if local_step == 0:
            clip["active_codon"] = None
        codons = [codon for codon in clip.get("codons", []) if codon]
        events = dna_events(codons)
        if not events:
            return
        total_steps = clip["bars"] * STEPS_PER_BAR
        if track["id"] == "voice1" and clip.get("dna_factor", "1") != "1":
            factor = float(clip.get("dna_factor", "1"))
            events = events[:max(1, int(total_steps * factor))]
            for index, (note, _duration) in enumerate(events):
                start = index * total_steps // len(events)
                if start != local_step:
                    continue
                end = (index + 1) * total_steps // len(events)
                clip["active_codon"] = index
                if note is not None:
                    port = self.selected_port(track)
                    self.send_note(port, 0, note, clamp(int(track["velocity_var"].get()), 1, 127), max(20, int(self.step_ms() * max(1, end - start) * DNA_GATE + DNA_DELAY_MS)))
                if self.editor and self.editor.clip is clip:
                    self.editor.repaint_playhead(local_step)
                return
            clip["active_codon"] = None
            if self.editor and self.editor.clip is clip:
                self.editor.repaint_playhead(local_step)
            return
        duration_steps_by_event = [max(1, int(round(duration * 4))) for _note, duration in events]
        if sum(duration_steps_by_event) > total_steps:
            index = local_step % len(events)
            note, _duration = events[index]
            clip["active_codon"] = index
            if note is not None:
                port = self.selected_port(track)
                self.send_note(port, 0, note, clamp(int(track["velocity_var"].get()), 1, 127), max(20, int(self.step_ms() * DNA_GATE + DNA_DELAY_MS)))
            if self.editor and self.editor.clip is clip:
                self.editor.repaint_playhead(local_step)
            return
        step = 0
        while step <= local_step:
            for index, (note, _duration) in enumerate(events):
                duration_steps = duration_steps_by_event[index]
                if step == local_step:
                    clip["active_codon"] = index
                    if note is not None:
                        port = self.selected_port(track)
                        self.send_note(port, 0, note, clamp(int(track["velocity_var"].get()), 1, 127), max(20, int(self.step_ms() * duration_steps * DNA_GATE + DNA_DELAY_MS)))
                    if self.editor and self.editor.clip is clip:
                        self.editor.repaint_playhead(local_step)
                    return
                step += duration_steps
                if step > local_step:
                    break
        clip["active_codon"] = None
        if self.editor and self.editor.clip is clip:
            self.editor.repaint_playhead(local_step)

    def repaint_playhead(self, previous, current):
        for step in (previous, current):
            if step < 0:
                continue
            bar = step // STEPS_PER_BAR
            if 0 <= bar < len(self.header_cells):
                active = self.playing and bar == current // STEPS_PER_BAR
                self.header_cells[bar].configure(bg=ACCENT if active else "#101827" if bar % 4 == 0 else FIELD, fg="#111827" if active else MUTED)

    def play_step(self):
        if not self.playing:
            return
        previous = self.play_step_index
        self.play_step_index = (self.play_step_index + 1) % self.total_steps()
        self.repaint_playhead(previous, self.play_step_index)
        for track in self.tracks:
            clip = self.clip_at_step(track, self.play_step_index)
            if not clip:
                continue
            local_step = self.play_step_index - clip["start"] * STEPS_PER_BAR
            if track["kind"] == "DNA":
                self.play_dna_clip_step(track, clip, local_step)
            else:
                self.play_clip_step(track, clip, local_step)
            if self.editor and self.editor.clip is clip:
                self.editor.repaint_playhead(local_step)
        self.after_ids.append(self.app.after(self.step_ms(), self.play_step))

    def play(self):
        if self.playing:
            return
        try:
            self.stop()
            self.open_outputs()
            self.playing = True
            start_bar = clamp(self.start_bar_var.get(), 1, SONG_BARS)
            self.play_step_index = (start_bar - 1) * STEPS_PER_BAR - 1
            for track in self.tracks:
                for clip in track["clips"]:
                    clip["dna_step"] = 0
                    clip["dna_wait"] = 0
                    clip["active_codon"] = None
            self.play_step()
            self.status(f"playing from bar {start_bar}")
        except Exception:
            self.stop()
            self.report_exception("play failed")

    def play_from_bar(self, bar):
        self.start_bar_var.set(clamp(int(bar), 1, SONG_BARS))
        if self.playing:
            self.stop()
        self.play()

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
        if self.editor:
            self.editor.repaint_playhead(None)

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

    def to_data(self):
        tracks = []
        for track in self.tracks:
            item = {key: track[key] for key in ("id", "name", "kind", "channel", "gate") if key in track}
            item["velocity"] = track["velocity_var"].get() if "velocity_var" in track else track.get("velocity", 75)
            item["port"] = self.selected_port(track) if "port_var" in track else None
            item["mute"] = track["mute_var"].get() if "mute_var" in track else 0
            item["solo"] = track["solo_var"].get() if "solo_var" in track else 0
            item["clips"] = track["clips"]
            tracks.append(item)
        return {"bpm": self.bpm_var.get(), "start_bar": clamp(self.start_bar_var.get(), 1, SONG_BARS), "tracks": tracks}

    def apply_track_data(self, track, data):
        track["clips"] = data.get("clips", [])
        track["velocity"] = data.get("velocity", track.get("velocity", 75))
        track["mute"] = data.get("mute", 0)
        track["solo"] = data.get("solo", 0)
        track["saved_port"] = data.get("port")

    def save(self):
        if self.editor:
            self.editor.commit_dna()
        PROJECT_FILE.write_text(json.dumps(self.to_data(), indent=2), encoding="utf-8")
        self.status(f"saved {PROJECT_FILE.name}")

    def load(self):
        if self.playing:
            self.stop()
        self.load_default_tracks()
        if PROJECT_FILE.exists():
            data = json.loads(PROJECT_FILE.read_text(encoding="utf-8"))
            self.bpm_var.set(data.get("bpm", 128))
            self.start_bar_var.set(clamp(int(data.get("start_bar", 1)), 1, SONG_BARS))
            by_id = {track["id"]: track for track in data.get("tracks", [])}
            for track in self.tracks:
                if track["id"] in by_id:
                    self.apply_track_data(track, by_id[track["id"]])
            default_ids = {track["id"] for track in self.tracks}
            for saved_track in data.get("tracks", []):
                if saved_track.get("id") in default_ids:
                    continue
                track = {key: saved_track[key] for key in ("id", "name", "kind", "channel", "gate") if key in saved_track}
                track["clips"] = []
                self.apply_track_data(track, saved_track)
                self.tracks.append(track)
        self.build_arranger()
        for track in self.tracks:
            if "saved_port" in track and track["saved_port"] is not None:
                for choice in self.port_choices:
                    if choice.startswith(f"{track['saved_port']}:"):
                        track["port_var"].set(choice)
                        break
            track["velocity_var"].set(track.get("velocity", 75))
            track["mute_var"].set(track.get("mute", 0))
            track["solo_var"].set(track.get("solo", 0))
        self.status(f"loaded {PROJECT_FILE.name if PROJECT_FILE.exists() else 'default project'}")

    def run(self):
        self.app.protocol("WM_DELETE_WINDOW", lambda: (self.stop(), self.app.destroy()))
        self.app.mainloop()


class ClipEditor:
    def __init__(self, daw, track, clip):
        self.daw = daw
        self.track = track
        self.clip = clip
        self.kind = track["kind"]
        self.window = tk.Toplevel(daw.app)
        self.window.configure(bg=BG)
        self.window.title(f"{track['name']} clip @ bar {clip['start'] + 1}")
        self.window.geometry("920x360")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.bar_var = tk.StringVar(value=str(clip["bars"]))
        self.dna_factor_var = tk.StringVar(value=str(clip.get("dna_factor", "1")))
        self.buttons = []
        self.text = None
        self.build()

    def build(self):
        top = tk.Frame(self.window, bg=BG)
        top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text=f"{self.track['name']} clip", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 10))
        tk.Label(top, text="Bars", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.OptionMenu(top, self.bar_var, "1", "2", "4", command=lambda value: self.daw.resize_clip(self.track, self.clip, value)).pack(side="left")
        if self.track["id"] == "voice1":
            tk.Label(top, text="Voice 1 x", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
            tk.OptionMenu(top, self.dna_factor_var, "1", "0.5", "0.25", "0.125", command=self.set_dna_factor).pack(side="left")
        self.daw.button(top, "Delete", RED, self.delete, width=7).pack(side="right", padx=3)
        self.body = tk.Frame(self.window, bg=BG)
        self.body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.rebuild()

    def rebuild(self):
        for widget in self.body.winfo_children():
            widget.destroy()
        self.buttons = []
        if self.kind == "DNA":
            self.build_dna()
        else:
            self.build_grid()

    def set_dna_factor(self, value):
        self.clip["dna_factor"] = value

    def build_grid(self):
        steps = self.clip["bars"] * STEPS_PER_BAR
        cells = self.clip.setdefault("cells", [""] * steps)
        self.clip["cells"] = (cells + [""] * steps)[:steps]
        for step in range(steps):
            button = tk.Button(self.body, text=self.clip["cells"][step], width=5, height=2, bg=FIELD, fg=TEXT, activebackground=LINE, activeforeground=TEXT, relief="flat", command=lambda index=step: self.left_click(index))
            button.bind("<Button-3>", lambda _event, index=step: self.clear_cell(index))
            button.grid(row=step // STEPS_PER_BAR, column=step % STEPS_PER_BAR, padx=1, pady=1, sticky="nsew")
            self.buttons.append(button)
        self.repaint()

    def build_dna(self):
        max_codons = self.clip["bars"] * CODONS_PER_BAR
        codons = [codon for codon in self.clip.setdefault("codons", []) if codon]
        self.clip["codons"] = codons[:max_codons]
        self.text = tk.Text(self.body, bg=FIELD, fg=TEXT, insertbackground=ACCENT, selectbackground="#273956", relief="flat", font=("Consolas", 15), undo=True, wrap="word")
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("active_codon", background=ACCENT, foreground="#111827")
        self.text.bind("<FocusOut>", lambda _event: self.commit_dna())
        self.text.bind("<Control-c>", lambda event: (event.widget.event_generate("<<Copy>>"), "break")[1])
        self.text.bind("<Control-C>", lambda event: (event.widget.event_generate("<<Copy>>"), "break")[1])
        self.render_dna()

    def render_dna(self):
        self.text.delete("1.0", "end")
        for index, codon in enumerate(self.clip.get("codons", [])):
            if index and index % CODONS_PER_BAR == 0:
                self.text.insert("end", "\n")
            elif index and index % CODONS_PER_BEAT == 0:
                self.text.insert("end", "| ")
            start = self.text.index("end-1c")
            self.text.insert("end", codon)
            end = self.text.index("end-1c")
            self.text.tag_add(f"codon_{index}", start, end)
            self.text.insert("end", " ")

    def commit_dna(self):
        if self.text:
            self.clip["codons"] = dna_codons(self.text.get("1.0", "end"))[:self.clip["bars"] * CODONS_PER_BAR]

    def left_click(self, step):
        if self.kind == "Bass":
            self.edit_note(step)
            return
        palette = PALETTES[self.kind]
        value = self.clip["cells"][step]
        index = palette.index(value) if value in palette else 0
        self.clip["cells"][step] = palette[(index + 1) % len(palette)]
        self.repaint_cell(step)

    def edit_note(self, step):
        button = self.buttons[step]
        button.grid_remove()
        editor = tk.Entry(self.body, bg=FIELD, fg=TEXT, insertbackground=ACCENT, relief="flat", width=5, justify="center")
        editor.insert(0, self.clip["cells"][step])
        editor.grid(row=step // STEPS_PER_BAR, column=step % STEPS_PER_BAR, padx=1, pady=1, sticky="nsew")
        editor.focus_set()
        editor.select_range(0, "end")

        def finish(save):
            if save:
                value = editor.get().strip()
                if value:
                    try:
                        self.clip["cells"][step] = normalize_note(value)
                    except ValueError as err:
                        self.daw.status(str(err))
                        editor.focus_set()
                        editor.select_range(0, "end")
                        return
                else:
                    self.clip["cells"][step] = ""
            editor.destroy()
            button.grid(row=step // STEPS_PER_BAR, column=step % STEPS_PER_BAR, padx=1, pady=1, sticky="nsew")
            self.repaint_cell(step)

        editor.bind("<Return>", lambda _event: (finish(True), "break")[1])
        editor.bind("<Escape>", lambda _event: (finish(False), "break")[1])
        editor.bind("<FocusOut>", lambda _event: finish(True))

    def clear_cell(self, step):
        self.clip["cells"][step] = ""
        self.repaint_cell(step)
        return "break"

    def repaint(self):
        for step in range(len(self.buttons)):
            self.repaint_cell(step)

    def repaint_cell(self, step):
        value = self.clip["cells"][step]
        active = self.daw.playing and self.daw.clip_at_step(self.track, self.daw.play_step_index) is self.clip and self.daw.play_step_index - self.clip["start"] * STEPS_PER_BAR == step
        if active:
            bg, fg = ACCENT, "#111827"
        elif value:
            bg, fg = COLORS[self.kind], TEXT
        elif step % STEPS_PER_BAR == 0:
            bg, fg = "#101827", MUTED
        elif step % 4 == 0:
            bg, fg = "#0d1420", MUTED
        else:
            bg, fg = FIELD, MUTED
        self.buttons[step].configure(text=value, bg=bg, fg=fg)

    def repaint_playhead(self, local_step):
        if self.kind == "DNA":
            if not self.text:
                return
            self.text.tag_remove("active_codon", "1.0", "end")
            index = self.clip.get("active_codon")
            if index is not None:
                ranges = self.text.tag_ranges(f"codon_{index}")
                if ranges:
                    self.text.tag_add("active_codon", ranges[0], ranges[1])
                    self.text.see(ranges[0])
            return
        self.repaint()

    def delete(self):
        self.close()
        self.daw.delete_clip(self.track, self.clip)

    def close(self):
        self.commit_dna()
        self.daw.editor = None
        self.window.destroy()


if __name__ == "__main__":
    ArrangerDaw().run()
