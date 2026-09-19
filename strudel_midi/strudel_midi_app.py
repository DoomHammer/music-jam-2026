import json
import re
from pathlib import Path

import customtkinter as ctk
import rtmidi2


BG = "#070b12"
PANEL = "#111827"
CONTROL = "#1f2b3f"
FIELD = "#050a10"
LINE = "#26344f"
TEXT = "#eaf2ff"
MUTED = "#94a3b8"
ACCENT = "#f4ad22"
GREEN = "#2f9654"
CODONS_PER_BAR = 16
CODONS_PER_BEAT = 4
DATA_FILE = Path(__file__).with_name("dna_codes.json")
PITCHES = {"AA": 48, "AC": 50, "AG": 52, "AT": 55, "CA": 57, "CC": 60, "CG": 62, "CT": 64, "GA": 67, "GC": 69, "GG": 72, "GT": 74, "TA": 76, "TC": 79, "TG": 81, "TT": None}
DURATIONS = {"T": 0.25, "C": 0.5, "G": 1.0, "A": 2.0}


ctk.set_appearance_mode("dark")
app = ctk.CTk(fg_color=BG)
app.title("MusicJam DNA Poly MIDI")
app.geometry("1120x640")
app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(1, weight=1)

ui = {}
voices = []
playing = False
midi_choices = []


def load_midi_choices():
    ports = rtmidi2.get_out_ports()
    return [f"{index}: {name}" for index, name in enumerate(ports)] or ["no MIDI ports"]


def entry(parent, key, label, value, width=70):
    box = ctk.CTkFrame(parent, fg_color=BG)
    box.pack(side="left", padx=7)
    ctk.CTkLabel(box, text=label, text_color=MUTED).pack(side="left", padx=(0, 5))
    item = ctk.CTkEntry(box, width=width, fg_color=FIELD, border_color=LINE, text_color=TEXT)
    item.pack(side="left")
    item.insert(0, value)
    ui[key] = item
    return item


def set_bpm(value):
    ui["bpm"].delete(0, "end")
    ui["bpm"].insert(0, str(int(float(value))))


def status(text):
    if "status_label" in globals():
        status_label.configure(text=f"Status: {text}")


def refresh_ports():
    global midi_choices
    midi_choices = load_midi_choices()
    for voice in voices:
        voice["port"].configure(values=midi_choices)
        voice["port"].set(midi_choices[min(voice["default_port"], len(midi_choices) - 1)])
    status(f"{len(midi_choices)} MIDI ports")


def selected_port(choice):
    if choice == "no MIDI ports":
        raise RuntimeError("no MIDI ports")
    return int(choice.split(":", 1)[0])


def load_codes():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"Voice A": "", "Voice B": ""}


def save_codes():
    data = {}
    for voice in voices:
        codons = render_voice_text(voice)
        data[voice["name"]] = "".join(codons)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    status(f"saved {DATA_FILE.name}")


def dna_codons(text):
    clean = re.sub(r"[^ACGT]", "", text.upper())
    return [clean[i:i + 3] for i in range(0, len(clean) - 2, 3)]


def render_codons(widget, codons, voice):
    text = widget._textbox
    text.configure(state="normal")
    for tag in text.tag_names():
        if tag.startswith("codon_"):
            text.tag_delete(tag)
    text.delete("1.0", "end")
    for index, codon in enumerate(codons):
        if index and index % CODONS_PER_BAR == 0:
            text.insert("end", "\n")
        elif index and index % CODONS_PER_BEAT == 0:
            text.insert("end", "| ")
        start = text.index("end-1c")
        text.insert("end", codon)
        end = text.index("end-1c")
        tag = f"codon_{index}"
        text.tag_add(tag, start, end)
        text.insert("end", " ")
    if not voice["editing"]:
        text.configure(state="disabled")


def dna_events(codons):
    return [(PITCHES[codon[:2]], DURATIONS[codon[2]]) for codon in codons]


def render_voice_text(voice):
    codons = dna_codons(voice["code"].get("1.0", "end"))
    voice["codons"] = codons
    render_codons(voice["code"], codons, voice)
    if codons:
        set_start(voice, min(voice["start_step"], len(codons) - 1))
    clamp_loop(voice)
    update_loop_highlight(voice)
    return codons


def clear_highlight(voice):
    voice["code"]._textbox.tag_remove("active_codon", "1.0", "end")


def highlight_codon(voice, index):
    clear_highlight(voice)
    ranges = voice["code"]._textbox.tag_ranges(f"codon_{index}")
    if ranges:
        voice["code"]._textbox.tag_add("active_codon", ranges[0], ranges[1])
        voice["code"].see(ranges[0])


def clear_start(voice):
    voice["code"]._textbox.tag_remove("start_codon", "1.0", "end")


def set_start(voice, index):
    if not voice["codons"]:
        return
    voice["start_step"] = index
    voice["step"] = index
    clear_start(voice)
    ranges = voice["code"]._textbox.tag_ranges(f"codon_{index}")
    if ranges:
        voice["code"]._textbox.tag_add("start_codon", ranges[0], ranges[1])
    status(f"{voice['name']} starts at {index + 1}")


def show_loop_status(voice):
    if voice["loop_start"] is None:
        voice["loop_label"].configure(text="Loop: off")
    else:
        start_bar = voice["loop_start"] // CODONS_PER_BAR + 1
        end_bar = voice["loop_end"] // CODONS_PER_BAR + 1
        voice["loop_label"].configure(text=f"Loop: bars {start_bar}-{end_bar}, steps {voice['loop_start'] + 1}-{voice['loop_end'] + 1}")


def update_loop_highlight(voice):
    text = voice["code"]._textbox
    text.tag_remove("loop_codon", "1.0", "end")
    if voice["loop_start"] is not None:
        for index in range(voice["loop_start"], voice["loop_end"] + 1):
            ranges = text.tag_ranges(f"codon_{index}")
            if ranges:
                text.tag_add("loop_codon", ranges[0], ranges[1])
    text.tag_raise("start_codon")
    text.tag_raise("active_codon")
    show_loop_status(voice)


def clamp_loop(voice):
    if voice["loop_start"] is None or not voice["codons"]:
        voice["loop_start"] = None
        voice["loop_end"] = None
        return
    last = len(voice["codons"]) - 1
    voice["loop_start"] = min(voice["loop_start"], last)
    voice["loop_end"] = min(voice["loop_end"], last)


def set_codon_loop(voice, left, right):
    voice["loop_start"] = min(left, right)
    voice["loop_end"] = max(left, right)
    set_start(voice, voice["loop_start"])
    update_loop_highlight(voice)


def codon_from_event(voice, event):
    index = voice["code"]._textbox.index(f"@{event.x},{event.y}")
    for tag in voice["code"]._textbox.tag_names(index):
        if tag.startswith("codon_"):
            return int(tag.split("_", 1)[1])
    return None


def start_codon_drag(voice, event):
    if voice["editing"]:
        return None
    index = codon_from_event(voice, event)
    if index is None:
        return "break"
    voice["drag_start"] = index
    voice["dragging"] = True
    set_codon_loop(voice, index, index)
    return "break"


def update_codon_drag(voice, event):
    if voice["editing"] or not voice["dragging"]:
        return None
    index = codon_from_event(voice, event)
    if index is not None:
        set_codon_loop(voice, voice["drag_start"], index)
    return "break"


def finish_codon_drag(voice, event):
    if voice["editing"]:
        return None
    index = codon_from_event(voice, event)
    voice["dragging"] = False
    if index is None:
        return "break"
    if voice["drag_start"] == index:
        clear_loop(voice)
        set_start(voice, index)
    else:
        set_codon_loop(voice, voice["drag_start"], index)
    return "break"


def clear_loop(voice):
    voice["loop_start"] = None
    voice["loop_end"] = None
    update_loop_highlight(voice)


def note_off(voice, note):
    if voice["midi"]:
        voice["midi"].send_noteoff(0, note)


def voice_enabled(voice):
    solo_on = any(item["solo"].get() for item in voices)
    return not voice["mute"].get() and (not solo_on or voice["solo"].get())


def silence_voice(voice):
    if voice["midi"] and voice["current_note"] is not None:
        voice["midi"].send_noteoff(0, voice["current_note"])
    voice["current_note"] = None


def toggle_voice(_voice):
    for voice in voices:
        silence_voice(voice)


def close_ports():
    used = set()
    for voice in voices:
        clear_highlight(voice)
        if voice["midi"] and voice["current_note"] is not None:
            voice["midi"].send_noteoff(0, voice["current_note"])
        if voice["midi"] and id(voice["midi"]) not in used:
            used.add(id(voice["midi"]))
            voice["midi"].close_port()
        voice["midi"] = None
        voice["current_note"] = None


def play_voice(voice):
    if not playing:
        return
    if voice["loop_start"] is not None:
        if voice["step"] < voice["loop_start"] or voice["step"] > voice["loop_end"]:
            voice["step"] = voice["loop_start"]
    index = voice["step"] % len(voice["pattern"])
    note, duration = voice["pattern"][index]
    voice["step"] += 1
    voice["current_note"] = None
    highlight_codon(voice, index)
    step_ms = int((60000 / int(ui["bpm"].get() or 120)) * duration)
    if note is not None and voice_enabled(voice):
        note = max(0, min(127, note + int(voice["octave"].get()) * 12))
        voice["current_note"] = note
        volume = int(voice["volume"].get())
        voice["midi"].send_cc(0, 7, volume)
        voice["midi"].send_cc(0, 11, volume)
        voice["midi"].send_noteon(0, note, max(1, volume))
        app.after(int(step_ms * float(ui["gate"].get() or 0.8)), lambda v=voice, n=note: note_off(v, n))
    app.after(step_ms, lambda v=voice: play_voice(v))


def prepare_voice(voice):
    if voice["editing"]:
        voice["editing"] = False
        voice["edit_button"].configure(text="Edit DNA")
    codons = render_voice_text(voice)
    voice["pattern"] = dna_events(codons)
    voice["start_step"] = min(voice["start_step"], max(0, len(voice["pattern"]) - 1))
    voice["step"] = voice["start_step"]
    voice["current_note"] = None
    voice["port_index"] = selected_port(voice["port"].get())


def open_voice_ports():
    opened = {}
    for voice in voices:
        index = voice["port_index"]
        if index not in opened:
            opened[index] = rtmidi2.MidiOut()
            opened[index].open_port(index)
        voice["midi"] = opened[index]


def play():
    global playing
    if playing:
        return
    try:
        close_ports()
        for voice in voices:
            prepare_voice(voice)
            if not voice["pattern"]:
                return status(f"{voice['name']}: no DNA codons")
        open_voice_ports()
        playing = True
        for voice in voices:
            play_voice(voice)
        status("playing 2 voices")
    except Exception as err:
        playing = False
        close_ports()
        status(str(err))


def stop():
    global playing
    playing = False
    close_ports()
    status("stopped")


def reset_midi():
    global playing
    playing = False
    close_ports()
    errors = 0
    for index, _ in enumerate(rtmidi2.get_out_ports()):
        out = rtmidi2.MidiOut()
        opened = False
        try:
            out.open_port(index)
            opened = True
            for channel in range(16):
                out.send_cc(channel, 120, 0)
                out.send_cc(channel, 123, 0)
                for note in range(128):
                    out.send_noteoff(channel, note)
        except Exception:
            errors += 1
        if opened:
            out.close_port()
    status("all MIDI notes off" if not errors else f"reset skipped {errors} busy ports")


def toggle_edit(voice):
    voice["editing"] = not voice["editing"]
    if voice["editing"]:
        clear_highlight(voice)
        voice["code"]._textbox.configure(state="normal")
        voice["edit_button"].configure(text="Done")
        status(f"{voice['name']}: editing DNA")
    else:
        render_voice_text(voice)
        voice["edit_button"].configure(text="Edit DNA")
        status(f"{voice['name']}: sequencer mode")


def voice_panel(parent, name, dna, port):
    panel = ctk.CTkFrame(parent, fg_color=PANEL, border_color=LINE, border_width=1, corner_radius=8)
    panel.pack(side="left", fill="both", expand=True, padx=8)
    head = ctk.CTkFrame(panel, fg_color=PANEL)
    head.pack(fill="x", padx=16, pady=(16, 6))
    ctk.CTkLabel(head, text=name, text_color=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w")
    controls = ctk.CTkFrame(panel, fg_color=PANEL)
    controls.pack(fill="x", padx=16, pady=(0, 8))
    ctk.CTkLabel(controls, text="Port", text_color=MUTED).pack(side="left", padx=(0, 5))
    port_menu = ctk.CTkOptionMenu(controls, width=190, values=midi_choices, fg_color=FIELD, button_color=CONTROL, button_hover_color="#273956", text_color=TEXT)
    port_menu.pack(side="left")
    port_menu.set(midi_choices[min(port, len(midi_choices) - 1)])
    ctk.CTkLabel(controls, text="Vol", text_color=MUTED).pack(side="left", padx=(12, 5))
    volume = ctk.CTkSlider(controls, from_=0, to=127, width=90, button_color=ACCENT, progress_color=ACCENT)
    volume.pack(side="left")
    volume.set(75)
    ctk.CTkLabel(controls, text="Oct", text_color=MUTED).pack(side="left", padx=(12, 5))
    octave = ctk.CTkOptionMenu(controls, width=76, values=["-2", "-1", "0", "+1", "+2"], fg_color=FIELD, button_color=CONTROL, button_hover_color="#273956", text_color=TEXT)
    octave.pack(side="left")
    octave.set("0")
    switches = ctk.CTkFrame(panel, fg_color=PANEL)
    switches.pack(fill="x", padx=16, pady=(0, 8))
    mute = ctk.CTkCheckBox(switches, text="Mute", width=72, fg_color=ACCENT, border_color=LINE)
    mute.pack(side="left", padx=(12, 0))
    solo = ctk.CTkCheckBox(switches, text="Solo", width=72, fg_color=ACCENT, border_color=LINE)
    solo.pack(side="left", padx=(6, 0))
    edit = ctk.CTkButton(switches, text="Edit DNA", width=86, fg_color=CONTROL, hover_color="#273956")
    edit.pack(side="left", padx=(10, 0))
    clear = ctk.CTkButton(switches, text="Clear loop", width=86, fg_color=CONTROL, hover_color="#273956")
    clear.pack(side="left", padx=(6, 0))
    loop_label = ctk.CTkLabel(panel, text="Loop: off", text_color=MUTED)
    loop_label.pack(anchor="w", padx=16, pady=(0, 6))
    code = ctk.CTkTextbox(panel, fg_color=FIELD, border_color=LINE, border_width=1, text_color=TEXT, font=("Consolas", 15))
    code.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    code._textbox.configure(undo=True, maxundo=-1, autoseparators=True)
    code._textbox.tag_configure("loop_codon", background="#14532d", foreground=TEXT)
    code._textbox.tag_configure("active_codon", background=ACCENT, foreground="#111827")
    code._textbox.tag_configure("start_codon", background="#273956", foreground=TEXT)
    voice = {"name": name, "code": code, "edit_button": edit, "loop_label": loop_label, "port": port_menu, "volume": volume, "octave": octave, "mute": mute, "solo": solo, "default_port": port, "port_index": port, "midi": None, "pattern": [], "codons": [], "step": 0, "start_step": 0, "loop_start": None, "loop_end": None, "drag_start": None, "dragging": False, "editing": False, "current_note": None}
    mute.configure(command=lambda v=voice: toggle_voice(v))
    solo.configure(command=lambda v=voice: toggle_voice(v))
    edit.configure(command=lambda v=voice: toggle_edit(v))
    clear.configure(command=lambda v=voice: clear_loop(v))
    voices.append(voice)
    voice["codons"] = dna_codons(dna)
    render_codons(code, voice["codons"], voice)
    update_loop_highlight(voice)
    set_start(voice, 0)
    code._textbox.bind("<ButtonPress-1>", lambda event, v=voice: start_codon_drag(v, event))
    code._textbox.bind("<B1-Motion>", lambda event, v=voice: update_codon_drag(v, event))
    code._textbox.bind("<ButtonRelease-1>", lambda event, v=voice: finish_codon_drag(v, event))
    code._textbox.bind("<<Paste>>", lambda _event, v=voice: app.after(10, lambda: render_voice_text(v)))


top = ctk.CTkFrame(app, fg_color=BG)
top.grid(row=0, column=0, sticky="ew", padx=22, pady=18)

ctk.CTkLabel(top, text="MusicJam DNA Poly MIDI", text_color=ACCENT, font=("Segoe UI", 26, "bold")).pack(side="left", padx=(0, 24))
ctk.CTkButton(top, text="Play", width=86, fg_color=GREEN, hover_color="#2a874c", command=play).pack(side="left", padx=5)
ctk.CTkButton(top, text="Stop", width=86, fg_color=CONTROL, hover_color="#273956", command=stop).pack(side="left", padx=5)
ctk.CTkButton(top, text="Reset MIDI", width=98, fg_color="#70333d", hover_color="#87414d", command=reset_midi).pack(side="left", padx=5)
ctk.CTkButton(top, text="Refresh ports", width=112, fg_color=CONTROL, hover_color="#273956", command=refresh_ports).pack(side="left", padx=5)
ctk.CTkButton(top, text="Save", width=78, fg_color=ACCENT, hover_color="#d99920", text_color="#111827", command=save_codes).pack(side="left", padx=5)
entry(top, "bpm", "BPM", "128")
bpm_slider = ctk.CTkSlider(top, from_=40, to=220, width=130, button_color=ACCENT, progress_color=ACCENT, command=set_bpm)
bpm_slider.pack(side="left", padx=6)
bpm_slider.set(128)
entry(top, "gate", "Gate", "0.8")

body = ctk.CTkFrame(app, fg_color=BG)
body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 18))

midi_choices = load_midi_choices()
codes = load_codes()
voice_panel(body, "Voice A", codes.get("Voice A", ""), 1)
voice_panel(body, "Voice B", codes.get("Voice B", ""), 2)

status_label = ctk.CTkLabel(app, text="Status: ready", text_color=MUTED)
status_label.grid(row=2, column=0, sticky="w", padx=24, pady=(0, 12))

app.mainloop()
