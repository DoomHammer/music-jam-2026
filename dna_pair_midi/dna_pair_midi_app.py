import customtkinter as ctk
import rtmidi2

from codon_mapper import gate, pitch_name, velocity
from event_generator import generate_events
from midi_export import export_midi


DNA = """TACTCTTTATTTAATATTTGGAGCTTGAGCTGGTATGATTGGAACCGCTATGAGAGTTATAATTCGTACT
GAGCTTGCACAACCAGGGTCTTTACTTCAAGACGATCAAATTTATAAAGTTATAGTAACTGCTCATGCCC
TCGTAATGATATTTTTTATGGTAATGCCTATTATGATAGGAGGATTTGGTAAATGACTAATCCCTCTCAT
GATAGGAGCCCCAGACATGGCATTCCCCCGCATGAAAAAAATGAGGTTTTGACTAATCCCCCCTTCTTTT
TTACTTCTCCTAGCTTCCGCTGGGGTTGAAAGAGGGGCAGGGACTGGGTGAACAATTTACCCCCCTTTAT
CTAGAGGGCTAGCTCACGCAGGAGGATCTGTTGATCTTGCTATCTTTTCCCTACACTTGGCTGGAGCTTC
TTCTATTTTAGCCTCCATAAAATTTATTACAACAATTATAAAAATGCGAACGCCTGGAATGTCTTTTGAT
CGACTTCCTCTTTTCGTTTGATCAGTGTTTGTAACTGCTTTTCTCCTCCTACTTTCTCTCCCCGTTTTAG
CCGGAGCTATTACTATGCTCTTGACAGATCGAAAAATTAATACAACTTTTTTCGACCCCGCTGGAGGAGG
AGACCCTATACTTTTTCAACATTTATTC"""
BG = "#070b12"
PANEL = "#111827"
CONTROL = "#1f2b3f"
FIELD = "#050a10"
LINE = "#26344f"
TEXT = "#eaf2ff"
MUTED = "#94a3b8"
ACCENT = "#f4ad22"
GREEN = "#2f9654"
MIDI_FILE = "dna_pair_output.mid"


ctk.set_appearance_mode("dark")
app = ctk.CTk(fg_color=BG)
app.title("MusicJam DNA Pair MIDI")
app.geometry("1040x680")
app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(1, weight=1)

playing = False
midi = None
events = []
step_i = 0
current_note = None


def status(text):
    status_label.configure(text=f"Status: {text}")


def bpm():
    return int(bpm_entry.get() or 120)


def render_events(items):
    lines = []
    for event in items[:300]:
        label = "REST" if event.event_type == "rest" else pitch_name(event.pitch)
        lines.append(f"{event.index:03}. {event.pitch_codon}+{event.rhythm_codon} -> {label} {event.duration:g} {event.event_type}")
    output.delete("1.0", "end")
    output.insert("1.0", "\n".join(lines))


def build_events():
    global events
    events = generate_events(dna_text.get("1.0", "end"))
    render_events(events)
    export_midi(events, MIDI_FILE, bpm())
    status(f"{len(events)} events, saved {MIDI_FILE}")


def note_off(note):
    if midi:
        midi.send_noteoff(0, note)


def play_step():
    global step_i, current_note
    if not playing:
        return
    event = events[step_i % len(events)]
    step_i += 1
    step_ms = int(60000 / bpm() * event.duration)
    current_note = event.pitch
    if event.event_type != "rest":
        midi.send_noteon(0, event.pitch, velocity(event.event_type))
        app.after(int(step_ms * gate(event.event_type)), lambda note=event.pitch: note_off(note))
    app.after(step_ms, play_step)


def play():
    global midi, playing, step_i
    if playing:
        return
    try:
        build_events()
        if not events:
            return status("no codon pairs")
        midi = rtmidi2.MidiOut()
        midi.open_port(1)
        step_i = 0
        playing = True
        play_step()
    except Exception as err:
        playing = False
        status(str(err))


def stop():
    global midi, playing
    playing = False
    if midi and current_note is not None:
        midi.send_noteoff(0, current_note)
    if midi:
        midi.close_port()
        midi = None
    status("stopped")


top = ctk.CTkFrame(app, fg_color=BG)
top.grid(row=0, column=0, sticky="ew", padx=22, pady=18)
ctk.CTkLabel(top, text="DNA Pair MIDI", text_color=ACCENT, font=("Segoe UI", 26, "bold")).pack(side="left", padx=(0, 24))
ctk.CTkButton(top, text="Play", width=86, fg_color=GREEN, hover_color="#2a874c", command=play).pack(side="left", padx=5)
ctk.CTkButton(top, text="Stop", width=86, fg_color=CONTROL, hover_color="#273956", command=stop).pack(side="left", padx=5)
ctk.CTkButton(top, text="Export MIDI", width=110, fg_color=ACCENT, hover_color="#d99920", text_color="#111827", command=build_events).pack(side="left", padx=5)
ctk.CTkLabel(top, text="BPM", text_color=MUTED).pack(side="left", padx=(18, 5))
bpm_entry = ctk.CTkEntry(top, width=80, fg_color=FIELD, border_color=LINE, text_color=TEXT)
bpm_entry.pack(side="left")
bpm_entry.insert(0, "120")

panel = ctk.CTkFrame(app, fg_color=PANEL, border_color=LINE, border_width=1, corner_radius=8)
panel.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 18))
panel.grid_columnconfigure((0, 1), weight=1)
panel.grid_rowconfigure(1, weight=1)

ctk.CTkLabel(panel, text="Raw DNA", text_color=TEXT, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
ctk.CTkLabel(panel, text="Events", text_color=TEXT, font=("Segoe UI", 18, "bold")).grid(row=0, column=1, sticky="w", padx=16, pady=(16, 8))
dna_text = ctk.CTkTextbox(panel, fg_color=FIELD, border_color=LINE, border_width=1, text_color=TEXT, font=("Consolas", 15))
dna_text.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 16))
dna_text.insert("1.0", DNA)
output = ctk.CTkTextbox(panel, fg_color=FIELD, border_color=LINE, border_width=1, text_color=TEXT, font=("Consolas", 13))
output.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=(0, 16))

status_label = ctk.CTkLabel(app, text="Status: ready", text_color=MUTED)
status_label.grid(row=2, column=0, sticky="w", padx=24, pady=(0, 14))

app.mainloop()
