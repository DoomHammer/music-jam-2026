from dataclasses import dataclass

from codon_mapper import pitch_for, rhythm_for
from dna_parser import codon_pairs


@dataclass(frozen=True)
class MusicEvent:
    index: int
    pitch_codon: str
    rhythm_codon: str
    pitch: int
    duration: float
    event_type: str


def generate_events(raw_dna):
    events = []
    for index, (left, right) in enumerate(codon_pairs(raw_dna), start=1):
        duration, event_type = rhythm_for(right)
        events.append(MusicEvent(index, left, right, pitch_for(left), duration, event_type))
    return events
