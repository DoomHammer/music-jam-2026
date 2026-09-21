import rtmidi2
import time

def pluck(note):
    midi.send_noteon(0, note, 100);
    time.sleep(0.1);
    midi.send_noteon(0, note, 0)

def clear():
    for note in range(128):
        midi.send_noteon(0, note, 0)

midi = rtmidi2.MidiOut()

ports = rtmidi2.get_out_ports()
print(ports)

midi.open_port(1)  # albo indeks portu Python MIDI

clear()

midi.open_port(2)  # albo indeks portu Python MIDI

clear()