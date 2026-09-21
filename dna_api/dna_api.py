import urllib.request
import urllib.parse
import json
import re

# ============================================================
# KONFIGURACJA
# ============================================================

EMAIL = "twoj_email@example.com"   # <- wpisz swój email
API_KEY = ""                       # <- opcjonalnie, może zostać pusty
TOOL_NAME = "marine_dna_python"

# ============================================================
# FUNKCJA: WYSZUKIWANIE SEKWENCJI W NCBI
# ============================================================

def search_ncbi(species, gene="", max_results=10):

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    # Szukanie konkretnego organizmu
    query = f'"{species}"[Organism]'

    # Jeżeli podano gen, dodajemy go do zapytania
    if gene.strip():
        query += f' AND "{gene}"[Gene]'

    params = {
        "db": "nuccore",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "tool": TOOL_NAME,
        "email": EMAIL
    }

    if API_KEY:
        params["api_key"] = API_KEY

    url = base_url + "?" + urllib.parse.urlencode(params)

    print("\nSzukam w NCBI...")
    print("Zapytanie:", query)

    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode("utf-8"))

    ids = data["esearchresult"]["idlist"]

    return ids


# ============================================================
# FUNKCJA: POBIERANIE DNA W FORMACIE FASTA
# ============================================================

def download_fasta(ids):

    if not ids:
        return None

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    params = {
        "db": "nuccore",
        "id": ",".join(ids),
        "rettype": "fasta",
        "retmode": "text",
        "tool": TOOL_NAME,
        "email": EMAIL
    }

    if API_KEY:
        params["api_key"] = API_KEY

    url = base_url + "?" + urllib.parse.urlencode(params)

    print("Pobieram sekwencje DNA...")

    with urllib.request.urlopen(url) as response:
        fasta = response.read().decode("utf-8")

    return fasta


# ============================================================
# PROGRAM GŁÓWNY
# ============================================================

print("=" * 60)
print("NCBI DNA DOWNLOADER")
print("=" * 60)

species = input(
    "\nPodaj łacińską nazwę gatunku,\n"
    "np. Asterias rubens: "
).strip()

gene = input(
    "\nPodaj gen, np. COI, 16S, 18S.\n"
    "Jeżeli chcesz dowolną sekwencję, naciśnij ENTER: "
).strip()

while True:
    try:
        max_results = int(
            input("\nIle sekwencji pobrać? np. 5: ")
        )

        if max_results > 0:
            break

    except ValueError:
        pass

    print("Podaj poprawną liczbę.")


try:

    ids = search_ncbi(
        species=species,
        gene=gene,
        max_results=max_results
    )

    if not ids:

        print("\nNie znaleziono żadnych sekwencji.")
        print("Spróbuj bez nazwy genu albo sprawdź nazwę gatunku.")

    else:

        print(f"\nZnaleziono rekordów: {len(ids)}")
        print("NCBI IDs:", ", ".join(ids))

        fasta = download_fasta(ids)

        if fasta:

            print("\n" + "=" * 60)
            print("POBRANE SEKWENCJE")
            print("=" * 60)

            print(fasta)

            # Bezpieczna nazwa pliku
            filename_species = re.sub(
                r"[^A-Za-z0-9_-]",
                "_",
                species
            )

            if gene:
                filename = f"{filename_species}_{gene}.fasta"
            else:
                filename = f"{filename_species}.fasta"

            with open(filename, "w", encoding="utf-8") as file:
                file.write(fasta)

            print("=" * 60)
            print(f"Zapisano do pliku: {filename}")
            print("=" * 60)


except urllib.error.HTTPError as error:

    print("\nBłąd HTTP:")
    print(error)

except urllib.error.URLError as error:

    print("\nNie udało się połączyć z NCBI:")
    print(error)

except Exception as error:

    print("\nWystąpił błąd:")
    print(error)