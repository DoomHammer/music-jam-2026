BASES = "ACGT"
CODONS = [a + b + c for a in BASES for b in BASES for c in BASES]
DURATIONS = [0.125, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
EVENT_TYPES = ["normal", "legato", "staccato", "accent", "soft", "loud", "rest", "tie"]
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

PITCH_MAP = {codon: 48 + round(i * 47 / 63) for i, codon in enumerate(CODONS)}
RHYTHM_MAP = {codon: (DURATIONS[i % 8], EVENT_TYPES[i // 8]) for i, codon in enumerate(CODONS)}


def pitch_for(codon):
    return PITCH_MAP[codon]


def rhythm_for(codon):
    return RHYTHM_MAP[codon]


def pitch_name(note):
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"


def velocity(event_type):
    return {"soft": 65, "accent": 120, "loud": 115}.get(event_type, 100)


def gate(event_type):
    return {"staccato": 0.35, "legato": 0.98, "tie": 1.0}.get(event_type, 0.8)
