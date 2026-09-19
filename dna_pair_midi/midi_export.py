from codon_mapper import gate, velocity


TPB = 480


def _vlq(value):
    data = [value & 0x7F]
    value >>= 7
    while value:
        data.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(data)


def _event(delta, data):
    return _vlq(delta) + bytes(data)


def export_midi(events, path, bpm=120):
    tempo = int(60_000_000 / bpm)
    track = bytearray(_event(0, [0xFF, 0x51, 0x03, tempo >> 16 & 255, tempo >> 8 & 255, tempo & 255]))
    pending = 0

    for event in events:
        ticks = max(1, int(event.duration * TPB))
        if event.event_type == "rest":
            pending += ticks
            continue
        note_ticks = max(1, int(ticks * gate(event.event_type)))
        track += _event(pending, [0x90, event.pitch, velocity(event.event_type)])
        track += _event(note_ticks, [0x80, event.pitch, 0])
        pending = ticks - note_ticks

    track += _event(pending, [0xFF, 0x2F, 0x00])
    with open(path, "wb") as file:
        file.write(b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + TPB.to_bytes(2, "big"))
        file.write(b"MTrk" + len(track).to_bytes(4, "big") + track)
