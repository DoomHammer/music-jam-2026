import customtkinter as ctk


STEPS = 16
TRACKS = ["Kick", "Snare", "Hat", "Bass", "Lead", "Chord"]
BG = "#070b12"
PANEL = "#111827"
CONTROL = "#1f2b3f"
FIELD = "#050a10"
LINE = "#26344f"
TEXT = "#eaf2ff"
MUTED = "#94a3b8"
ACCENT = "#f4ad22"
GREEN = "#2f9654"


ctk.set_appearance_mode("dark")
app = ctk.CTk(fg_color=BG)
app.title("MusicJam Sequencer")
app.geometry("1180x720")
app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(0, weight=1)

state = {}


def field(parent, label, value):
    ctk.CTkLabel(parent, text=label, text_color=MUTED, anchor="w").pack(fill="x", pady=(12, 3))
    item = ctk.CTkEntry(parent, fg_color=FIELD, border_color=LINE, text_color=TEXT)
    item.pack(fill="x")
    item.insert(0, value)
    return item


def toggle(track, step, button):
    key = (track, step)
    state[key] = not state.get(key, False)
    button.configure(fg_color=ACCENT if state[key] else FIELD)


sidebar = ctk.CTkFrame(app, fg_color=PANEL, corner_radius=0, width=270)
sidebar.grid(row=0, column=1, sticky="nsew")
sidebar.grid_propagate(False)

ctk.CTkLabel(sidebar, text="MusicJam", text_color=ACCENT, font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=22, pady=(34, 28))
field(sidebar, "Mode", "Strudel + MIDI")
field(sidebar, "MIDI Output", "Cubase / Sylenth1")
field(sidebar, "Channel", "1")
field(sidebar, "Velocity", "100")
field(sidebar, "Gate", "0.8")

main = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)
main.grid(row=0, column=0, sticky="nsew", padx=22, pady=18)
main.grid_columnconfigure(0, weight=1)
main.grid_rowconfigure(1, weight=1)

top = ctk.CTkFrame(main, fg_color=BG)
top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
top.grid_columnconfigure(8, weight=1)

ctk.CTkLabel(top, text="Sequencer", text_color=TEXT, font=("Segoe UI", 24, "bold")).grid(row=0, column=0, padx=(0, 26))
ctk.CTkButton(top, text="Play", width=86, fg_color=GREEN, hover_color="#2a874c").grid(row=0, column=1, padx=5)
ctk.CTkButton(top, text="Stop", width=86, fg_color=CONTROL, hover_color="#273956").grid(row=0, column=2, padx=5)
ctk.CTkButton(top, text="Rec", width=74, fg_color="#70333d", hover_color="#87414d").grid(row=0, column=3, padx=5)

for col, (label, value) in enumerate([("BPM", "128"), ("Swing", "0"), ("Steps", "16"), ("Key", "C minor")], start=4):
    box = ctk.CTkFrame(top, fg_color=BG)
    box.grid(row=0, column=col, padx=7)
    ctk.CTkLabel(box, text=label, text_color=MUTED).pack(side="left", padx=(0, 5))
    entry = ctk.CTkEntry(box, width=70, fg_color=FIELD, border_color=LINE, text_color=TEXT)
    entry.pack(side="left")
    entry.insert(0, value)

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
code.insert("1.0", 'note("c eb g bb").sound("sawtooth").midi()')
ctk.CTkButton(strudel, text="Eval", fg_color=ACCENT, hover_color="#d99920", text_color="#111827").pack(fill="x", padx=14, pady=12)
ctk.CTkLabel(strudel, text="Status: UI only", text_color=MUTED).pack(anchor="w", padx=14, pady=(0, 14))

app.mainloop()
