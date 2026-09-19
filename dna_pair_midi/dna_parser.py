import re


def codons(raw_dna):
    dna = re.sub(r"[^ACGT]", "", raw_dna.upper())
    return [dna[i:i + 3] for i in range(0, len(dna) - 2, 3)]


def codon_pairs(raw_dna):
    items = codons(raw_dna)
    return list(zip(items, items[1:]))
