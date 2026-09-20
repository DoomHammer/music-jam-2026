import json
import re
import tkinter as tk
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

STEPS_PER_BAR = 16
MAX_BARS = 8
GRID_STEPS = STEPS_PER_BAR * MAX_BARS
SONG_FILE = Path(__file__).with_name("synthwave_daw.json")

TRACK_TYPES = ["Bass", "Pad", "Arp", "Drums", "FX"]
TRACK_DEFAULTS = {
    "Bass": {"channel": 2, "velocity": 88, "gate": 55},
    "Pad": {"channel": 3, "velocity": 48, "gate": 92},
    "Arp": {"channel": 4, "velocity": 36, "gate": 35},
    "Drums": {"channel": 10, "velocity": 96, "gate": 30},
    "FX": {"channel": 5, "velocity": 64, "gate": 75},
}
PALETTES = {
    "Bass": ["", "A2", "C2", "D2", "E2", "F2", "G2", "A3", "C3", "D3", "E3", "F3", "G3"],
    "Pad": ["", "Am9", "Fmaj7", "Cmaj7", "G6", "Em9", "Dm9", "Bbmaj7"],
    "Arp": ["", "Am9", "Fmaj7", "Cmaj7", "G6", "Em9", "Dm9", "Bbmaj7"],
    "Drums": ["", "K", "K+S", "S"],
    "FX": ["", "NOISE", "RISER", "CYM", "CHOP"],
}
TYPE_COLORS = {
    "Bass": "#1f7a4a",
    "Pad": "#315a9c",
    "Arp": "#a66a21",
    "Drums": "#984052",
    "FX": "#6d5a26",
}
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
DRUM_NOTES = {"K": 36, "S": 38}
FX_NOTES = {"NOISE": 84, "RISER": 85, "CYM": 49, "CHOP": 86}


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


def normalize_bass_note(name):
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(-?\d+)\s*", name)
    if not match:
        raise ValueError("Bass note must look like A1, C#2 or Bb3")
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


class TrackRow:
    def __init__(self, daw, kind, data=None):
        self.daw = daw
        self.kind = kind
        defaults = TRACK_DEFAULTS[kind]
        self.cells = [""] * GRID_STEPS
        self.name_var = tk.StringVar(value=f"{kind} {len(daw.tracks) + 1}")
        self.port_var = tk.StringVar(value=daw.port_choices[0] if daw.port_choices else "no MIDI ports")
        self.channel_var = tk.IntVar(value=defaults["channel"])
        self.velocity_var = tk.IntVar(value=defaults["velocity"])
        self.gate_var = tk.IntVar(value=defaults["gate"])
        self.mute_var = tk.IntVar(value=0)
        self.solo_var = tk.IntVar(value=0)
        self.cell_buttons = []
        self.editor = None
        self.editor_step = None

        if data:
            self.apply_data(data)

        self.left = tk.Frame(daw.inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        self.grid_frame = tk.Frame(daw.inner, bg=BG)
        self.build_left()
        self.build_grid()

    def build_left(self):
        tk.Entry(self.left, textvariable=self.name_var, bg=FIELD, fg=TEXT, insertbackground=ACCENT, relief="flat", width=10).grid(row=0, column=0, sticky="ew", padx=(5, 3), pady=3)
        self.port_menu = tk.OptionMenu(self.left, self.port_var, *(self.daw.port_choices or ["no MIDI ports"]))
        self.port_menu.configure(bg=FIELD, fg=TEXT, activebackground=LINE, activeforeground=TEXT, highlightthickness=0, width=15)
        self.port_menu["menu"].configure(bg=FIELD, fg=TEXT)
        self.port_menu.grid(row=0, column=1, sticky="ew", padx=3, pady=3)
        tk.Label(self.left, text="V", bg=PANEL, fg=MUTED).grid(row=0, column=2, sticky="e", padx=(4, 1), pady=3)
        tk.Spinbox(self.left, from_=1, to=127, textvariable=self.velocity_var, width=4, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").grid(row=0, column=3, sticky="w", padx=2, pady=3)
        tk.Checkbutton(self.left, text="M", variable=self.mute_var, bg=PANEL, fg=TEXT, selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT, command=self.daw.repaint_tracks).grid(row=0, column=4, sticky="w", padx=1, pady=1)
        tk.Checkbutton(self.left, text="S", variable=self.solo_var, bg=PANEL, fg=TEXT, selectcolor=FIELD, activebackground=PANEL, activeforeground=TEXT, command=self.daw.repaint_tracks).grid(row=0, column=5, sticky="w", padx=1, pady=1)
        tk.Button(self.left, text="X", width=2, bg=RED, fg=TEXT, relief="flat", command=lambda: self.daw.remove_track(self)).grid(row=0, column=6, padx=(2, 4), pady=3)
        self.left.grid_columnconfigure(0, weight=1)

    def build_grid(self):
        for step in range(GRID_STEPS):
            button = tk.Button(
                self.grid_frame,
                text="",
                width=4,
                height=1,
                bg=FIELD,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                command=lambda index=step: self.left_click_cell(index),
            )
            button.bind("<Button-3>", lambda _event, index=step: self.clear_cell(index))
            button.bind("<Shift-Button-1>", lambda _event, index=step: self.shift_click_cell(index))
            button.grid(row=0, column=step, padx=(1, 0), pady=1, sticky="nsew")
            self.cell_buttons.append(button)
        self.repaint()

    def grid(self, row):
        self.left.grid(row=row, column=0, sticky="nsew", padx=(0, 4), pady=1)
        self.grid_frame.grid(row=row, column=1, sticky="w", pady=1)

    def destroy(self):
        self.finish_bass_edit(False)
        self.left.destroy()
        self.grid_frame.destroy()

    def set_port_choices(self, choices):
        current = self.port_var.get()
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for choice in choices:
            menu.add_command(label=choice, command=lambda value=choice: self.port_var.set(value))
        if current in choices:
            self.port_var.set(current)
        else:
            self.port_var.set(choices[0])

    def left_click_cell(self, step):
        if self.kind == "Bass":
            self.edit_bass_cell(step)
        else:
            self.cycle_cell(step, 1)

    def shift_click_cell(self, step):
        if self.kind == "Bass":
            self.edit_bass_cell(step)
            return "break"
        self.cycle_cell(step, -1)
        return "break"

    def edit_bass_cell(self, step):
        if self.editor:
            if self.editor_step == step:
                self.editor.focus_set()
                self.editor.select_range(0, "end")
                return
            if not self.finish_bass_edit(True):
                return
        self.cell_buttons[step].grid_remove()
        self.editor_step = step
        self.editor = tk.Entry(self.grid_frame, bg=FIELD, fg=TEXT, insertbackground=ACCENT, relief="flat", width=4, justify="center")
        self.editor.insert(0, self.cells[step])
        self.editor.grid(row=0, column=step, padx=(1, 0), pady=1, sticky="nsew")
        self.editor.focus_set()
        self.editor.select_range(0, "end")
        self.editor.bind("<Return>", lambda _event: (self.finish_bass_edit(True), "break")[1])
        self.editor.bind("<Escape>", lambda _event: (self.finish_bass_edit(False), "break")[1])
        self.editor.bind("<FocusOut>", lambda _event: self.finish_bass_edit(True))

    def finish_bass_edit(self, save):
        if not self.editor:
            return True
        editor = self.editor
        step = self.editor_step
        value = editor.get()
        if save and value.strip():
            try:
                self.cells[step] = normalize_bass_note(value)
            except ValueError as err:
                self.daw.status(str(err))
                editor.focus_set()
                editor.select_range(0, "end")
                return False
        elif save:
            self.cells[step] = ""
        self.editor = None
        self.editor_step = None
        editor.destroy()
        self.cell_buttons[step].grid(row=0, column=step, padx=(1, 0), pady=1, sticky="nsew")
        self.repaint_cell(step)
        if save:
            self.daw.status(f"{self.name_var.get()} step {step + 1}: {self.cells[step] or 'empty'}")
        return True

    def cycle_cell(self, step, direction):
        if self.editor and not self.finish_bass_edit(True):
            return
        palette = PALETTES[self.kind]
        value = self.cells[step]
        index = palette.index(value) if value in palette else 0
        self.cells[step] = palette[(index + direction) % len(palette)]
        self.repaint_cell(step)
        self.daw.status(f"{self.name_var.get()} step {step + 1}: {self.cells[step] or 'empty'}")

    def clear_cell(self, step):
        if self.editor_step == step:
            self.finish_bass_edit(False)
        self.cells[step] = ""
        self.repaint_cell(step)
        self.daw.status(f"{self.name_var.get()} step {step + 1}: empty")
        return "break"

    def repaint(self):
        for step in range(GRID_STEPS):
            self.repaint_cell(step)

    def repaint_cell(self, step):
        value = self.cells[step]
        active = self.daw.playing and step == self.daw.play_step_index
        enabled = self.enabled()
        if active:
            bg, fg = ACCENT, "#111827"
        elif value and enabled:
            bg, fg = TYPE_COLORS[self.kind], TEXT
        elif value:
            bg, fg = "#334155", MUTED
        elif step % STEPS_PER_BAR == 0:
            bg, fg = "#101827", MUTED
        elif step % 4 == 0:
            bg, fg = "#0d1420", MUTED
        else:
            bg, fg = FIELD, MUTED
        self.cell_buttons[step].configure(text=value, bg=bg, fg=fg)

    def enabled(self):
        if self.mute_var.get():
            return False
        solo_on = any(track.solo_var.get() for track in self.daw.tracks)
        return not solo_on or bool(self.solo_var.get())

    def selected_port(self):
        choice = self.port_var.get()
        if choice in ("no MIDI ports", "rtmidi2 missing"):
            return None
        return int(choice.split(":", 1)[0])

    def velocity(self):
        return clamp(int(self.velocity_var.get()), 1, 127)

    def channel(self):
        return clamp(int(self.channel_var.get()), 1, 16) - 1

    def gate(self):
        return clamp(int(self.gate_var.get()), 5, 100) / 100

    def next_filled_step(self, step, total_steps):
        for index in range(step + 1, total_steps):
            if self.cells[index]:
                return index
        return total_steps

    def active_chord(self, step, total_steps):
        filled = [index for index in range(total_steps) if self.cells[index]]
        if not filled:
            return None, 0
        before = [index for index in filled if index <= step]
        source = before[-1] if before else filled[-1]
        return self.cells[source], (step - source) % total_steps

    def to_data(self):
        return {
            "name": self.name_var.get(),
            "kind": self.kind,
            "port": self.selected_port(),
            "channel": self.channel_var.get(),
            "velocity": self.velocity_var.get(),
            "gate": self.gate_var.get(),
            "mute": self.mute_var.get(),
            "solo": self.solo_var.get(),
            "cells": self.cells,
        }

    def apply_data(self, data):
        self.name_var.set(data.get("name", self.name_var.get()))
        self.channel_var.set(data.get("channel", self.channel_var.get()))
        self.velocity_var.set(data.get("velocity", self.velocity_var.get()))
        self.gate_var.set(data.get("gate", self.gate_var.get()))
        self.mute_var.set(data.get("mute", 0))
        self.solo_var.set(data.get("solo", 0))
        cells = data.get("cells", [])
        self.cells = (cells + [""] * GRID_STEPS)[:GRID_STEPS]
        port = data.get("port")
        if port is not None:
            for choice in self.daw.port_choices:
                if choice.startswith(f"{port}:"):
                    self.port_var.set(choice)
                    break


class SynthwaveDaw:
    def __init__(self):
        self.app = tk.Tk()
        self.app.configure(bg=BG)
        self.app.title("Synthwave Grid MIDI DAW")
        self.app.geometry("1280x560")
        self.tracks = []
        self.outputs = {}
        self.active_notes = set()
        self.after_ids = []
        self.playing = False
        self.play_step_index = -1
        self.port_choices = []
        self.add_kind_var = tk.StringVar(value="Bass")
        self.bpm_var = tk.IntVar(value=128)
        self.bars_var = tk.IntVar(value=4)

        self.build_ui()
        self.refresh_ports()
        self.load() if SONG_FILE.exists() else self.load_demo()

    def build_ui(self):
        top = tk.Frame(self.app, bg=BG)
        top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Synthwave Grid", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 10))
        self.button(top, "Play", GREEN, self.play).pack(side="left", padx=4)
        self.button(top, "Stop", "#1f2b3f", self.stop).pack(side="left", padx=4)

        tk.Label(top, text="BPM", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.Spinbox(top, from_=40, to=220, textvariable=self.bpm_var, width=5, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").pack(side="left")
        tk.Label(top, text="Bars", bg=BG, fg=MUTED).pack(side="left", padx=(8, 3))
        tk.Spinbox(top, from_=1, to=MAX_BARS, textvariable=self.bars_var, width=3, bg=FIELD, fg=TEXT, buttonbackground=LINE, relief="flat").pack(side="left")

        tk.OptionMenu(top, self.add_kind_var, *TRACK_TYPES).pack(side="left", padx=(10, 4))
        self.button(top, "Add", ACCENT, self.add_selected_track, fg="#111827", width=5).pack(side="left", padx=3)
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
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.build_header()

        self.status_label = tk.Label(self.app, text="Status: ready", bg=BG, fg=MUTED)
        self.status_label.pack(anchor="w", padx=12, pady=(0, 6))

    def build_header(self):
        tk.Label(self.inner, text="Track", bg=BG, fg=MUTED, width=42, anchor="w").grid(row=0, column=0, sticky="ew", padx=(0, 4))
        grid = tk.Frame(self.inner, bg=BG)
        grid.grid(row=0, column=1, sticky="w", pady=(0, 2))
        self.header_cells = []
        for step in range(GRID_STEPS):
            if step % STEPS_PER_BAR == 0:
                text = f"Bar {step // STEPS_PER_BAR + 1}"
            elif step % 4 == 0:
                text = str(step % STEPS_PER_BAR + 1)
            else:
                text = ""
            label = tk.Label(grid, text=text, width=4, bg="#101827" if step % STEPS_PER_BAR == 0 else FIELD, fg=MUTED, font=("Segoe UI", 7))
            label.grid(row=0, column=step, padx=(1, 0), sticky="ew")
            self.header_cells.append(label)

    def button(self, parent, text, bg, command, fg=TEXT, width=8):
        return tk.Button(parent, text=text, width=width, bg=bg, fg=fg, activebackground=LINE, activeforeground=TEXT, relief="flat", command=command)

    def status(self, text):
        self.status_label.configure(text=f"Status: {text}")

    def refresh_ports(self):
        ports = rtmidi2.get_out_ports() if rtmidi2 else []
        self.port_choices = [f"{index}: {name}" for index, name in enumerate(ports)] or ["rtmidi2 missing" if not rtmidi2 else "no MIDI ports"]
        for track in self.tracks:
            track.set_port_choices(self.port_choices)
        self.status(f"{len(ports)} MIDI ports")

    def add_selected_track(self):
        self.add_track(self.add_kind_var.get())

    def add_track(self, kind, data=None):
        track = TrackRow(self, kind, data)
        self.tracks.append(track)
        self.layout_tracks()
        self.status(f"added {kind}")
        return track

    def remove_track(self, track):
        if self.playing:
            self.stop()
        self.tracks.remove(track)
        track.destroy()
        self.layout_tracks()
        self.status("track removed")

    def layout_tracks(self):
        for row, track in enumerate(self.tracks, start=1):
            track.grid(row)
        self.inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def repaint_tracks(self):
        for track in self.tracks:
            track.repaint()

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

    def load_demo(self):
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
            for offset in range(0, STEPS_PER_BAR, 2):
                drums.cells[start + offset] = "K+S"
        self.repaint_tracks()
        self.status("demo loaded")

    def save(self):
        if not self.commit_edits():
            return
        data = {
            "bpm": self.bpm_var.get(),
            "bars": self.bars_var.get(),
            "tracks": [track.to_data() for track in self.tracks],
        }
        SONG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.status(f"saved {SONG_FILE.name}")

    def load(self):
        if not SONG_FILE.exists():
            return self.status("no saved song")
        if self.playing:
            self.stop()
        data = json.loads(SONG_FILE.read_text(encoding="utf-8"))
        for track in list(self.tracks):
            track.destroy()
        self.tracks.clear()
        self.bpm_var.set(data.get("bpm", 128))
        self.bars_var.set(data.get("bars", 4))
        for track_data in data.get("tracks", []):
            self.add_track(track_data.get("kind", "Bass"), track_data)
        self.repaint_tracks()
        self.status(f"loaded {SONG_FILE.name}")

    def open_outputs(self):
        if not rtmidi2:
            raise RuntimeError("rtmidi2 missing")
        ports = sorted({track.selected_port() for track in self.tracks if track.enabled() and track.selected_port() is not None})
        if not ports:
            raise RuntimeError("no MIDI ports selected")
        for port in ports:
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
            notes = [DRUM_NOTES[token] for token in value.split("+") if token in DRUM_NOTES]
            self.send_notes(track, notes)
        elif track.kind == "FX" and value:
            self.send_notes(track, [FX_NOTES[value]])

    def play_step(self):
        if not self.playing:
            return
        total_steps = self.total_steps()
        previous = self.play_step_index
        self.play_step_index = (self.play_step_index + 1) % total_steps
        self.repaint_playhead(previous, self.play_step_index)
        for track in self.tracks:
            self.play_track_step(track, self.play_step_index, total_steps)
        self.after_ids.append(self.app.after(self.step_ms(), self.play_step))

    def play(self):
        if self.playing:
            return
        try:
            if not self.commit_edits():
                return
            self.stop()
            if not self.tracks:
                return self.status("add a track first")
            self.open_outputs()
            self.playing = True
            self.play_step_index = -1
            self.play_step()
            self.status("playing")
        except Exception as err:
            self.stop()
            self.status(str(err))

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
    SynthwaveDaw().run()
