import re

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
CODONS_PER_LINE = 18
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
PITCHES = {"AA": 48, "AC": 50, "AG": 52, "AT": 55, "CA": 57, "CC": 60, "CG": 62, "CT": 64, "GA": 67, "GC": 69, "GG": 72, "GT": 74, "TA": 76, "TC": 79, "TG": 81, "TT": None}
DURATIONS = {"T": 0.25, "C": 0.5, "G": 1.0, "A": 2.0}


ctk.set_appearance_mode("dark")
app = ctk.CTk(fg_color=BG)
app.title("MusicJam Strudel MIDI")
app.geometry("940x560")
app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(1, weight=1)

ui = {}
playing = False
midi = None
pattern = []
step_i = 0
current_note = None


def entry(parent, key, label, value, width=80):
    box = ctk.CTkFrame(parent, fg_color=BG)
    box.pack(side="left", padx=7)
    ctk.CTkLabel(box, text=label, text_color=MUTED).pack(side="left", padx=(0, 5))
    item = ctk.CTkEntry(box, width=width, fg_color=FIELD, border_color=LINE, text_color=TEXT)
    item.pack(side="left")
    item.insert(0, value)
    ui[key] = item


def status(text):
    status_label.configure(text=f"Status: {text}")


def dna_codons(text):
    clean = re.sub(r"[^ACGT]", "", text.upper())
    return [clean[i:i + 3] for i in range(0, len(clean) - 2, 3)]


def format_codons(codons):
    return "\n".join(" ".join(codons[i:i + CODONS_PER_LINE]) for i in range(0, len(codons), CODONS_PER_LINE))


def dna_events(codons):
    return [(PITCHES[codon[:2]], DURATIONS[codon[2]]) for codon in codons]


def codon_pos(index):
    return f"{index // CODONS_PER_LINE + 1}.{index % CODONS_PER_LINE * 4}"


def clear_highlight():
    code._textbox.tag_remove("active_codon", "1.0", "end")


def highlight_codon(index):
    clear_highlight()
    start = codon_pos(index)
    code._textbox.tag_add("active_codon", start, f"{start}+3c")
    code.see(start)


def note_off(note):
    if midi:
        midi.send_noteoff(0, note)


def play_step():
    global step_i, current_note
    if not playing:
        return
    index = step_i % len(pattern)
    highlight_codon(index)
    current_note, duration = pattern[index]
    step_i += 1
    step_ms = int((60000 / int(ui["bpm"].get() or 120)) * duration)
    if current_note is not None:
        midi.send_noteon(0, current_note, 100)
        app.after(int(step_ms * float(ui["gate"].get() or 0.8)), lambda note=current_note: note_off(note))
    app.after(step_ms, play_step)


def play():
    global midi, playing, pattern, step_i
    if playing:
        return
    try:
        codons = dna_codons(code.get("1.0", "end"))
        pattern = dna_events(codons)
        if not pattern:
            return status("no DNA codons")
        code.delete("1.0", "end")
        code.insert("1.0", format_codons(codons))
        midi = rtmidi2.MidiOut()
        midi.open_port(1)
        step_i = 0
        playing = True
        status(f"playing {len(pattern)} codons")
        play_step()
    except Exception as err:
        playing = False
        status(str(err))


def stop():
    global midi, playing
    playing = False
    clear_highlight()
    if midi and current_note is not None:
        midi.send_noteoff(0, current_note)
    if midi:
        midi.close_port()
        midi = None
    status("stopped")


top = ctk.CTkFrame(app, fg_color=BG)
top.grid(row=0, column=0, sticky="ew", padx=22, pady=18)

ctk.CTkLabel(top, text="MusicJam DNA MIDI", text_color=ACCENT, font=("Segoe UI", 26, "bold")).pack(side="left", padx=(0, 24))
ctk.CTkButton(top, text="Play", width=86, fg_color=GREEN, hover_color="#2a874c", command=play).pack(side="left", padx=5)
ctk.CTkButton(top, text="Stop", width=86, fg_color=CONTROL, hover_color="#273956", command=stop).pack(side="left", padx=5)
entry(top, "bpm", "BPM", "128")
entry(top, "gate", "Gate", "0.8")

panel = ctk.CTkFrame(app, fg_color=PANEL, border_color=LINE, border_width=1, corner_radius=8)
panel.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 18))

ctk.CTkLabel(panel, text="DNA", text_color=TEXT, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
code = ctk.CTkTextbox(panel, fg_color=FIELD, border_color=LINE, border_width=1, text_color=TEXT, font=("Consolas", 16))
code.pack(fill="both", expand=True, padx=16)
code._textbox.tag_configure("active_codon", background=ACCENT, foreground="#111827")
code.insert("1.0", format_codons(dna_codons(DNA)))

bottom = ctk.CTkFrame(panel, fg_color=PANEL)
bottom.pack(fill="x", padx=16, pady=14)
ctk.CTkButton(bottom, text="Parse / Play", fg_color=ACCENT, hover_color="#d99920", text_color="#111827", command=play).pack(side="left")
status_label = ctk.CTkLabel(bottom, text="Status: ready", text_color=MUTED)
status_label.pack(side="left", padx=14)

app.mainloop()
