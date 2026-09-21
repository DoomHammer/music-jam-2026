Dramatis Personae

- [https://oceaninfo.com/animals/clownfish/](https://oceaninfo.com/animals/clownfish/) (Amphiprion ocellaris)
- [https://oceaninfo.com/animals/giant-squid/](https://oceaninfo.com/animals/giant-squid/) (Architeuthis dux)
- [https://en.wikipedia.org/wiki/Common_starfish](https://en.wikipedia.org/wiki/Common_starfish) (Asterias rubens)
- [https://oceaninfo.com/animals/blue-whale/](https://oceaninfo.com/animals/blue-whale/) (Balaenoptera musculus)
- [https://oceaninfo.com/animals/herring/](https://oceaninfo.com/animals/herring/) (Clupea harengus)
- [https://oceaninfo.com/animals/comb-jelly/](https://oceaninfo.com/animals/comb-jelly/) (Ctenophora)
- [https://oceaninfo.com/animals/bioluminescent-plankton/](https://oceaninfo.com/animals/bioluminescent-plankton/) (Dinoflagellates)
- [https://oceaninfo.com/animals/dugong/](https://oceaninfo.com/animals/dugong/) (Dugong dugon)
- [https://oceaninfo.com/animals/cod-fish/](https://oceaninfo.com/animals/cod-fish/) (Gadus)
- [https://oceaninfo.com/animals/sea-horse/](https://oceaninfo.com/animals/sea-horse/) (Hippocampus histrix)
- [https://oceaninfo.com/animals/american-lobster/](https://oceaninfo.com/animals/american-lobster/) (Homarus americanus)
- [https://oceaninfo.com/animals/atlantic-blue-marlin/](https://oceaninfo.com/animals/atlantic-blue-marlin/) (Makaira nigricans)
- [https://oceaninfo.com/animals/earless-seal/](https://oceaninfo.com/animals/earless-seal/) (Phocidae)
- [https://oceaninfo.com/animals/fugu-pufferfish/](https://oceaninfo.com/animals/fugu-pufferfish/) (Takifugu)
- [https://oceaninfo.com/animals/polar-bear/](https://oceaninfo.com/animals/polar-bear/) (Ursus maritimus)
- [https://oceaninfo.com/animals/vampire-squid/](https://oceaninfo.com/animals/vampire-squid/) (Vampyroteuthis infernalis)

# submarine DNA synthwave arranger

Mini MIDI arranger DAW do hackathonowego projektu muzycznego opartego o sekwencje DNA.

## Glowna aplikacja

```bash
razor_arranger/arranger_daw_app.py
```

Uruchomienie:

```bash
python3 razor_arranger/arranger_daw_app.py
```

Na Windows/PyCharm:

```bash
.\.venv\Scripts\python.exe .\razor_arranger\arranger_daw_app.py
```

## Co robi arranger

`arranger_daw_app.py` to mini DAW / sekwenser / aranzer MIDI:

- timeline ma 96 taktow,
- klik w numer taktu startuje odtwarzanie od tego miejsca,
- clipy maja dlugosc `1`, `2` albo `4` takty,
- klik w pusty slot tworzy clip,
- klik w clip otwiera edycje,
- drag przesuwa clip po timeline,
- prawy klik na clipie daje `Copy beside` i `Rename`,
- `Save` zapisuje projekt do `razor_arranger/arranger_daw.json`,
- `Load` odczytuje projekt z JSON.

## Instrumenty

Domyslne sciezki:

- `Bass`
- `Pad`
- `Arp`
- `Drums`
- `FX`
- `DNA 1`
- `DNA 2`

Mozna dodawac instrumenty przez `Add Instrument` i usuwac sciezki przyciskiem `X`.

Kazda sciezka ma port MIDI, velocity, mute, solo i clipy.

## Edycja clipow

W edytorze clipa:

- `Bars` zmienia dlugosc clipa,
- `Delete` usuwa clip,
- `Bass` pozwala wpisywac nuty,
- `Pad` i `Arp` wybieraja akordy,
- `Drums` wybiera pattern,
- `FX` wybiera efekt,
- `DNA` pozwala wklejac tekst DNA.

`Arp notes` ustawia, czy arpeggio gra `3`, `4` czy `5` dzwiekow z akordu.

`DNA 1 x` spowalnia material DNA 1: `1`, `0.5`, `0.25`, `0.125`.

## DNA na MIDI

DNA jest czyszczone do znakow:

```text
A C G T
```

Nastepnie dzielone na kodony po 3 znaki.

Pierwsze 2 znaki wybieraja wysokosc albo pauze:

```text
AA C3   AC D3   AG E3   AT G3
CA A3   CC C4   CG D4   CT E4
GA G4   GC A4   GG C5   GT D5
TA E5   TC G5   TG A5   TT pauza
```

Trzeci znak wybiera dlugosc:

```text
T = 1/16
C = 1/8
G = 1/4
A = 1/2
```

Jesli tekst DNA jest dluzszy niz pojemnosc clipa, nadmiar jest obcinany.

## FASTA

Lokalne sekwencje DNA sa w:

```bash
fasta_files/
```

Folder zawiera sekwencje roznych organizmow morskich, m.in.:

- `Hippocampus_histrix.fasta`
- `Amphiprion_ocellaris.fasta`
- `Asterias_rubens_COI.fasta`
- `Balaenoptera_musculus.fasta`
- `Homarus_americanus.fasta`
- `Makaira_nigricans.fasta`

## FASTA API

API do pobierania sekwencji DNA z NCBI:

```bash
dna_api/dna_api.py
```

Skrypt pyta o gatunek, gen i liczbe rekordow, pobiera dane przez NCBI E-utilities i zapisuje wynik jako plik `.fasta`.

## Pliki

```text
razor_arranger/arranger_daw_app.py  glowna aplikacja
razor_arranger/arranger_daw.json    zapis projektu
razor_arranger/dna_midi_app.py      prostsza aplikacja DNA MIDI
dna_api/dna_api.py                  pobieranie FASTA z NCBI
fasta_files/                        lokalne pliki FASTA
helpers/                            pomocnicze skrypty
```

## MIDI

Porty MIDI sa pobierane przez `rtmidi2`.

Typowy setup:

```text
arranger -> loopMIDI -> DAW/VST
```

Po zmianie portow kliknij `Ports`.

`Reset` wysyla `All Sound Off`, `All Notes Off` i `noteoff` dla nut `0..127`.
