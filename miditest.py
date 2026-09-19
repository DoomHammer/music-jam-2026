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
for i in range(1, 10):
    midi.send_noteon(0, 60, 100)
    time.sleep(2)
    midi.send_noteoff(0, 60)
    midi.send_noteon(0, 67, 100)
    time.sleep(2)
    midi.send_noteoff(0, 67)
    pluck(79)

for note in range(128):
    midi.send_noteon(0, note, 0)