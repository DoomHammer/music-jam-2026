import re

import customtkinter as ctk
import rtmidi2


STEPS = 16
TRACKS = ["MIDI 1", "MIDI 2", "MIDI 3", "MIDI 4", "MIDI 5", "MIDI 6"]
BG = "#070b12"
PANEL = "#111827"
CONTROL = "#1f2b3f"
FIELD = "#050a10"
LINE = "#26344f"
TEXT = "#eaf2ff"
MUTED = "#94a3b8"
ACCENT = "#f4ad22"
GREEN = "#2f9654"

NOTES = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11}


ctk.set_appearance_mode("dark")
app = ctk.CTk(fg_color=BG)
app.title("MusicJam Strudel MIDI")
app.geometry("1180x720")
app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(0, weight=1)

state = {}
playing = False
midi = None
ui = {}
pattern = []
step_i = 0
current_note = None
channel = 0
velocity = 100
gate_ms = 300
step_ms = 375


def field(parent, key, label, value):
    ctk.CTkLabel(parent, text=label, text_color=MUTED, anchor="w").pack(fill="x", pady=(12, 3))
    item = ctk.CTkEntry(parent, fg_color=FIELD, border_color=LINE, text_color=TEXT)
    item.pack(fill="x")
    item.insert(0, value)
    ui[key] = item


def toggle(track, step, button):
    key = (track, step)
    state[key] = not state.get(key, False)
    button.configure(fg_color=ACCENT if state[key] else FIELD)


def status(text):
    app.after(0, lambda: status_label.configure(text=f"Status: {text}"))


def midi_note(token, octave):
    match = re.fullmatch(r"([a-gA-G][#b]?)(-?\d*)", token)
    if not match:
        return None
    name, oct_text = match.groups()
    oct_num = int(oct_text) if oct_text else octave
    return 12 * (oct_num + 1) + NOTES[name.lower()]


def strudel_notes(text):
    match = re.search(r"""note\(\s*["']([^"']+)["']\s*\)""", text)
    if not match:
        return []
    octave = int(ui["octave"].get() or 4)
    return [midi_note(token, octave) for token in re.split(r"[\s,]+", match.group(1)) if token and token != "~"]


def open_midi():
    out = rtmidi2.MidiOut()
    port = ui["port"].get().strip()
    out.open_port(int(port) if port.isdigit() else rtmidi2.get_out_ports().index(port))
    return out


def note_off(note):
    if midi:
        midi.send_noteoff(channel, note)


def play_step():
    global step_i, current_note
    if not playing:
        return
    current_note = pattern[step_i % len(pattern)]
    step_i += 1
    midi.send_noteon(channel, current_note, velocity)
    app.after(gate_ms, lambda note=current_note: note_off(note))
    app.after(step_ms, play_step)


def play():
    global midi, playing, pattern, step_i, channel, velocity, gate_ms, step_ms
    if playing:
        return
    try:
        pattern = [note for note in strudel_notes(code.get("1.0", "end")) if note is not None]
        if not pattern:
            return status("no note(...)")
        midi = open_midi()
        bpm = int(ui["bpm"].get() or 120)
        channel = int(ui["channel"].get() or 1) - 1
        velocity = int(ui["velocity"].get() or 100)
        step_ms = int(60000 / bpm)
        gate_ms = int(step_ms * float(ui["gate"].get() or 0.8))
        step_i = 0
        playing = True
        status(f"playing {len(pattern)} notes")
        play_step()
    except Exception as err:
        playing = False
        status(str(err))


def stop():
    global playing
    playing = False
    if midi and current_note is not None:
        midi.send_noteoff(channel, current_note)
    status("stopped")


sidebar = ctk.CTkFrame(app, fg_color=PANEL, corner_radius=0, width=270)
sidebar.grid(row=0, column=1, sticky="nsew")
sidebar.grid_propagate(False)

ctk.CTkLabel(sidebar, text="MusicJam", text_color=ACCENT, font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=22, pady=(34, 28))
field(sidebar, "mode", "Mode", "Strudel MIDI")
field(sidebar, "port", "MIDI Output", "1")
field(sidebar, "channel", "Channel", "1")
field(sidebar, "velocity", "Velocity", "100")
field(sidebar, "gate", "Gate", "0.8")
field(sidebar, "octave", "Octave", "4")

main = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)
main.grid(row=0, column=0, sticky="nsew", padx=22, pady=18)
main.grid_columnconfigure(0, weight=1)
main.grid_rowconfigure(1, weight=1)

top = ctk.CTkFrame(main, fg_color=BG)
top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
top.grid_columnconfigure(8, weight=1)

ctk.CTkLabel(top, text="Sequencer", text_color=TEXT, font=("Segoe UI", 24, "bold")).grid(row=0, column=0, padx=(0, 26))
ctk.CTkButton(top, text="Play", width=86, fg_color=GREEN, hover_color="#2a874c", command=play).grid(row=0, column=1, padx=5)
ctk.CTkButton(top, text="Stop", width=86, fg_color=CONTROL, hover_color="#273956", command=stop).grid(row=0, column=2, padx=5)
ctk.CTkButton(top, text="Rec", width=74, fg_color="#70333d", hover_color="#87414d").grid(row=0, column=3, padx=5)

for col, (key, label, value) in enumerate([("bpm", "BPM", "128"), ("swing", "Swing", "0"), ("steps", "Steps", "16"), ("key", "Key", "C minor")], start=4):
    box = ctk.CTkFrame(top, fg_color=BG)
    box.grid(row=0, column=col, padx=7)
    ctk.CTkLabel(box, text=label, text_color=MUTED).pack(side="left", padx=(0, 5))
    entry = ctk.CTkEntry(box, width=70, fg_color=FIELD, border_color=LINE, text_color=TEXT)
    entry.pack(side="left")
    entry.insert(0, value)
    ui[key] = entry

ctk.CTkButton(top, text="Save", width=80, fg_color=CONTROL, hover_color="#273956", text_color=ACCENT).grid(row=0, column=9, sticky="e")

work = ctk.CTkFrame(main, fg_color=PANEL, border_color=LINE, border_width=1, corner_radius=8)
work.grid(row=1, column=0, sticky="nsew")
work.grid_columnconfigure(0, weight=1)
work.grid_rowconfigure(0, weight=1)
work.grid_rowconfigure(1, weight=1)

grid = ctk.CTkFrame(work, fg_color=PANEL)
grid.grid(row=0, column=0, sticky="nsew", padx=18, pady=(18, 8))

for step in range(STEPS):
    ctk.CTkLabel(grid, text=f"{step + 1:02}", width=38, text_color=MUTED).grid(row=0, column=step + 4, padx=3)

for row, track in enumerate(TRACKS, start=1):
    ctk.CTkLabel(grid, text=track, width=76, text_color=TEXT, anchor="w").grid(row=row, column=0, sticky="w", pady=5)
    ctk.CTkCheckBox(grid, text="M", width=34, fg_color=ACCENT, border_color=LINE).grid(row=row, column=1)
    ctk.CTkCheckBox(grid, text="S", width=34, fg_color=ACCENT, border_color=LINE).grid(row=row, column=2)
    ctk.CTkEntry(grid, width=56, fg_color=FIELD, border_color=LINE, text_color=TEXT).grid(row=row, column=3, padx=(0, 8))
    grid.grid_slaves(row=row, column=3)[0].insert(0, "ch1")

    for step in range(STEPS):
        button = ctk.CTkButton(grid, text="", width=38, height=30, corner_radius=5, fg_color=FIELD, hover_color="#283754")
        button.configure(command=lambda t=track, s=step, b=button: toggle(t, s, b))
        button.grid(row=row, column=step + 4, padx=3, pady=5)

strudel = ctk.CTkFrame(work, fg_color=BG, border_color=LINE, border_width=1, corner_radius=8)
strudel.grid(row=1, column=0, sticky="nsew", padx=18, pady=(8, 18))

ctk.CTkLabel(strudel, text="Strudel", text_color=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=14, pady=(14, 8))
code = ctk.CTkTextbox(strudel, height=130, fg_color=FIELD, border_color=LINE, border_width=1, text_color=TEXT, font=("Consolas", 15))
code.pack(fill="both", expand=True, padx=14)
code.insert("1.0", 'note("c eb g bb").midi()')
ctk.CTkButton(strudel, text="Eval", fg_color=ACCENT, hover_color="#d99920", text_color="#111827", command=play).pack(fill="x", padx=14, pady=12)
status_label = ctk.CTkLabel(strudel, text="Status: ready", text_color=MUTED)
status_label.pack(anchor="w", padx=14, pady=(0, 14))

app.mainloop()
