---
name: jotun-calc
description: "Główny skill projektu jotun-calc. Używaj przy każdej pracy z kodem: kalkulator cen zakupu/sprzedaży farb Jotun, OCR formuły pigmentacji, endpointy Flask, pliki danych. Zawiera architekturę, algorytm kalkulacji i znane pułapki."
---

# Kontekst projektu

Aplikacja webowa (Flask) obliczająca cenę zakupu i sprzedaży farby Jotun na podstawie formuły pigmentacji.
BOK lub handlowiec wgrywa screenshot z programu do doboru kolorów Jotun → OCR odczytuje produkt, bazę i formułę → użytkownik wybiera opakowanie, ilość i marżę → aplikacja generuje specyfikację towarową z kosztem zakupu i ceną sprzedaży.

**Platforma:** Railway  
**Język:** Python 3, Flask, OpenAI API (gpt-4o dla OCR)  
**Plik startowy:** `Procfile` (Railway wykrywa automatycznie)

---

# Struktura projektu

```
jotun-calc-main/
├── main.py                          # Flask app — cała logika + endpointy
├── pricing_data/
│   └── purchase_prices.json         # Ceny zakupu baz w EUR + dane pigmentów
├── templates/
│   └── index.html                   # Frontend (Jinja2)
├── generate_prices.py               # Skrypt do generowania JSON z arkusza Excel
├── Procfile                         # Railway: web: python main.py
└── requirements.txt
```

---

# Endpointy API

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/` | Strona główna (formularz) |
| GET | `/api/products` | Lista produktów z bazami i rozmiarami |
| POST | `/api/ocr` | OCR screenshota → produkt, baza, formuła |
| POST | `/api/calculate` | Kalkulacja ceny zakupu i sprzedaży |

### `/api/ocr` — żądanie
```json
{
  "image_b64": "<base64>",
  "media_type": "image/png"
}
```

### `/api/ocr` — odpowiedź
```json
{
  "product_name": "DEMIDEKK CLEANTECH",
  "base": "A",
  "colour_name": "SIGNAL WHITE",
  "colour_code": "9003",
  "formula": [{"code": "SV", "units": 12.0}, {"code": "HT", "units": 3.5}],
  "ocr_errors": []
}
```

### `/api/calculate` — żądanie
```json
{
  "product_name": "DEMIDEKK CLEANTECH",
  "base": "A",
  "pack_size": "3L",
  "quantity": 2,
  "formula": [{"code": "SV", "units": 12.0}],
  "margin_pct": 30,
  "vat_pct": 23,
  "euro_rate": 4.3
}
```

### `/api/calculate` — odpowiedź (kluczowe pola)
```json
{
  "product_name": "DEMIDEKK CLEANTECH",
  "base": "A-BAS",
  "pack_size": "3L",
  "base_vol_l": 2.7,
  "commercial_vol_l": 3.0,
  "purchase": {
    "base_pln": 250.48,
    "pigment_pln": 1.23,
    "total_pln": 251.71,
    "pigment_vol_l": 0.009
  },
  "invoice_lines": [
    {"lp": 1, "name": "DEMIDEKK CLEANTECH BASE A 3L", "qty": 2, "unit": "szt.", "value_gross": 714.80},
    {"lp": 2, "name": "MULTICOLOR SOLVENT FREE", "qty": 0.018, "unit": "LT", "value_gross": 3.50}
  ],
  "summary": {
    "total_net": 582.76,
    "total_vat": 134.03,
    "total_gross": 716.79
  }
}
```

---

# Algorytm kalkulacji

## Logika opakowań
Baza (rzeczywista) ≠ opakowanie handlowe:

| base_vol_l | commercial_vol_l (rozmiar handlowy) |
|------------|-------------------------------------|
| 0.68 L | 0.75 L |
| 0.9 L | 1 L |
| 2.7 L | 3 L |
| 9.0 L | 10 L |

## Koszt pigmentów
Formuła podana jest **per 1L bazy** → skalowana × `base_vol_l` dla wybranego opakowania.

```
koszt_pigmentu_pln = units × price_eur_per_ltr × euro_rate × ML_PER_UNIT / 1000 × commercial_vol_l
```

**Stała: `ML_PER_UNIT = 0.308`** — ml pigmentu Jotun na jednostkę formuły.

## Objętość pigmentu
```
pigment_vol_l = round(sum_units × 0.308 × commercial_vol_l / 1000, 2)
```

## Cena sprzedaży
```
total_cost_pln = base_price_pln + pigment_total_pln
sell_net_1pack = total_cost_pln / (1 - margin_pct/100)
sell_gross_1pack = sell_net_1pack × (1 + vat_pct/100)
```

## Linie faktury
- **Linia 1:** `[PRODUKT] BASE [X] [Y]L` — baza, ilość w szt., cena netto per szt.
- **Linia 2:** `MULTICOLOR SOLVENT FREE` — pigmenty, ilość w LT (łączna objętość pigmentu × quantity)

Linia 2 pojawia się tylko gdy `pigment_vol_l > 0`.

---

# Struktura `purchase_prices.json`

```json
{
  "meta": {
    "euro_rate": 4.3,
    "tinting_unit_ml": 0.308,
    "pack_map": {"0.68": "0.75L", "2.7": "3L", "9.0": "10L"},
    "formula_basis": "per_1L_base"
  },
  "products": {
    "DEMIDEKK_CLEANTECH": {
      "product_name": "DEMIDEKK CLEANTECH",
      "bases": {
        "A-BAS": {
          "0.75L": {"base_vol_l": 0.68, "commercial_vol_l": 0.75, "price_eur_per_pack": 17.45},
          "3L":    {"base_vol_l": 2.7,  "commercial_vol_l": 3.0,  "price_eur_per_pack": 58.25},
          "10L":   {"base_vol_l": 9.0,  "commercial_vol_l": 10.0, "price_eur_per_pack": 166.95}
        },
        "B-BAS": { ... },
        "C-BAS": { ... }
      }
    }
  },
  "tinters": {
    "SV": {"code": "SV", "price_eur_per_ltr": 12.50},
    "HT": {"code": "HT", "price_eur_per_ltr": 18.30}
  }
}
```

---

# OCR formuły (`/api/ocr`)

- Model: `gpt-4o` (nie mini — wymagana precyzja odczytu)
- Odczytuje screenshot z programu Jotun do doboru kolorów (nie z maszyny mieszającej)
- Ekstrakcja: `product_name`, `base`, `formula` (kody + jednostki), `colour_name`, `colour_code`

## Kody pigmentów (tylko te 19 są poprawne)
`BD, BS, BV, FS, GE, GI, GO, GS, GV, HT, OK, RS, RB, RE, SS, SV, DE, MK, OX`

## Format jednostek
- Program Jotun: całkowite — `RB012` = kod RB, 12 jednostek
- Maszyna mieszająca: dziesiętne — `RB040.3` = kod RB, 40.3 jednostek

## Aliasy baz (BASE_ALIASES w main.py)
```python
BASE_ALIASES = {
    "OXIDE YELLOW": "GUL", "OXIDEYELLOW": "GUL", "GELB": "GUL", "YELLOW": "GUL",
    "HVIT": "HVIT", "VIT": "HVIT", "WHITE": "HVIT",
    "KLAR": "KLAR", "CLEAR": "KLAR", "TRANSPAR.": "KLAR", "TRANSPARENT": "KLAR",
    "A": "A", "B": "B", "C": "C",
}
```

## Walidacja RAL po OCR
Każdy zwrócony kod pigmentu jest walidowany:
- Format: dokładnie 2 litery A-Z
- Zakres jednostek: `0.1 – 999.0`
- Kod musi być w liście 19 dopuszczalnych kodów

---

# Wyszukiwanie produktu i bazy w kodzie

## `find_product(product_name)`
Normalizuje nazwę (uppercase, zamiana znaków skandynawskich, myślniki → spacje) i porównuje z `product_name` w JSON. Zwraca klucz i dict produktu.

## `find_base(prod, base_hint)`
Najpierw stosuje `BASE_ALIASES`, potem szuka po kluczu w `prod["bases"]`. Obsługuje częściowe dopasowania.

## `normalize(s)`
```python
s.upper().strip()
# Ä→A, Ö→O, Å→A, Ø→O, Æ→AE
# myślniki i podkreślniki → spacje
```

---

# Aktualizacja cen zakupu

```bash
python generate_prices.py Nowy_arkusz.xlsx
```

Skrypt generuje nowy `pricing_data/purchase_prices.json` z arkusza Excel dostarczonego przez Jotun.
Po wygenerowaniu sprawdź czy struktura baz i rozmiarów jest spójna z poprzednią wersją.

---

# Zmienne środowiskowe

| Zmienna | Opis |
|---------|------|
| `OPENAI_API_KEY` | Klucz API OpenAI (wymagany) |
| `PORT` | Port serwera (Railway ustawia automatycznie) |

---

# Znane pułapki

- `commercial_vol_l` ≠ `base_vol_l` — w nazwie faktury używaj `commercial_vol_l` (np. 3L), nie `base_vol_l` (2.7)
- Formuła pigmentu podana **per 1L bazy** — nie zapominaj skalować przez `base_vol_l`, nie przez `commercial_vol_l`
- `HVIT` i `A-BAS` to różne bazy dla Cleantech — HVIT = gotowy biały (bez tintowania), A-BAS = baza do tintowania
- Aliasy baz: `GELB` → `GUL` (nie `GELB`) — sprawdź aliasy przed szukaniem w JSON
- Błędy OCR cyfr: O→0, I→1, l→1, B→8 — funkcja `fix_ocr_number()` obsługuje to automatycznie
- Jeśli `formula` jest pusta i `pigment_vol_l == 0` → linia 2 faktury nie jest generowana (produkt bez pigmentu)
- `base_only_warning: true` w odpowiedzi = formuła była niepusta ale żaden pigment nie przeszedł walidacji — zgłoś błąd
