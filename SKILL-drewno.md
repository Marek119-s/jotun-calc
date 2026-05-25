---
name: drewno
description: "Skill o farbach do drewna Jotun. Używaj przy każdej pracy dotyczącej produktów drewnianych: dane produktów, bazy, kolory, fakturowanie, kalkulator cen zakupu, BOK. Obejmuje wszystkie 3 apki: delta-shop-api, jotun-calc, bok-drewno."
---

# Kontekst

Produkty do ochrony drewna Jotun sprzedawane przez Olicon Delta. Produkty są **barwione (tintowane)** po złożeniu zamówienia — nie są gotowe fabrycznie (wyjątek: Terrassfix, Kraftvask, Tregrunning Klar, Penselrens).

**Trzy apki obsługujące drewno:**
- **delta-shop-api** — generuje rozłożenie faktury na składniki (Baza + Pigment)
- **jotun-calc** — kalkulator ceny zakupu na podstawie formuły pigmentacji i kursu EUR
- **bok-drewno** — asystent BOK (obsługa klienta), baza wiedzy o produktach

---

# Produkty drewniane — pełna lista

| shop_id | product_id | Nazwa produktu | Typ | Rozmiary (L) |
|---------|-----------|----------------|-----|-------------|
| 104 | demidekk-cleantech | Lakier zewnętrzny do drewna klasy premium Jotun Demidekk Cleantech | tintowany | 0.75, 3, 10 |
| 249 | demidekk-terrasslasyr | Jotun Demidekk Terrasslasyr | tintowany | 3, 10 |
| 257 | jotaproff-tackande-utegrund | Jotaproff Täckande Utegrund | tintowany | 3, 10 |
| 256 | jotun-treolje | Jotun Treolie | tintowany | 3 |
| 147 | trebitt-holzlasur | Bejca do drewna klasy premium Jotun Trebitt Oljebeis / Holzlasur | tintowany | 0.75, 3, 10 |
| 185 | jotun-panellakk | Lakier do malowania wewnętrznych paneli drewnianych Jotun Panellakk | gotowy | 0.75, 3 |
| 153 | jotun-tregrunning-klar | Lakier podkładowy zewnętrzny do drewna Jotun Tregrunning Klar | gotowy | 0.9, 2.7, 9 |
| 232 | demidekk-terrassfix | Jotun Terrassfix | gotowy | 4 |
| 111 | jotun-kraftvask | Jotun Kraftvask 1 l | gotowy | 1 |
| 112 | jotun-penselrens | Jotun Penselrens | gotowy | 1 |
| — | demidekk-lasyrolja | Demidekk Lasyrolja | tintowany | 0.75, 3, 10 |

**Demidekk Lasyrolja** — brak w sklepie online (Shoper), dostępna tylko przez BOK. Produkt wycofywany — ostatnie sztuki.

---

# Bazy per produkt

## Demidekk Cleantech (shop_id: 104)
| Baza | Kolory |
|------|--------|
| A | RAL 9003 Signal White, Std 0001 White, Std 1001 Egghvit, RAL 7032 Pebble Grey |
| B | Std 10168 Muted Yellow |
| C | RAL 7016 Antracite Grey, Std 9938 Dempet Sort, RAL 9005 Jed Black, Std 0745 Grann Umbra, RAL 8000 Green Brown |

Nazwy baz w `purchase_prices.json`: `A-BAS`, `B-BAS`, `C-BAS` (oraz `HVIT` dla białego gotowego).

## Demidekk Terrasslasyr (shop_id: 249)
| Baza | Kolory |
|------|--------|
| GUL | STD 90000 Brąz Tarasowy |
| KLAR | STD 10073 Stara Sosna, STD 9074 Nordisk Tre |

## Trebitt Holzlasur (shop_id: 147)
| Baza | Kolory |
|------|--------|
| GELB | Std 10045 Mahagoni, Std 675 palisander, Std 623 birmański tek |
| C | Std 629 naturalny, Std 682 kasztanowy |

## Jotaproff Täckande Utegrund (shop_id: 257)
Jeden kolor w sklepie: Std 0001 White. Baza: HVIT.

## Jotun Treolie (shop_id: 256)
| Baza | Kolory |
|------|--------|
| KLAR | 9001 Gylden, 0500 Grontonet, KLAR |

## Produkty bez tintowania
Panellakk, Tregrunning Klar, Terrassfix, Kraftvask, Penselrens — sprzedawane jako gotowe, bez pigmentacji.

---

# Fakturowanie — struktura faktury (delta-shop-api)

Faktura dla farby drewnianej = **dwa wiersze** (jak farby przemysłowe):
1. `[NAZWA PRODUKTU] BASE [X] [Y]L` — baza (Comp A)
2. `MULTICOLOR SOLVENT FREE` z opisem formuły pigmentu — pigment

Przykład z faktury:
```
1 | DEMIDEKK CLEANTECH  BASE A 2,7 L | 2 szt. | 325,24 netto | 800,09 brutto
2 | MULTICOLOR SOLVENT FREE           | RAL 9003 | 0,010 LT | 163,00 | 2,00 brutto
```

## Algorytm kalkulacji (identyczny jak farby przemysłowe)
```
1. total_netto    = round(total_brutto / 1.23, 2)
2. price_per_liter = round(total_netto / total_volume, 2)
3. base_netto     = round(base_vol × price_per_liter, 2)
4. base_brutto    = round(base_netto × 1.23, 2)
5. pigment_brutto = total_brutto − base_brutto   ← KOREKTA z różnicy
6. pigment_netto  = round(pigment_brutto / 1.23, 2)
```

**Farby drewniane są jednoskładnikowe** — brak Comp B. Struktura = Comp A + Pigment.

## Objętości baz (base_vol_l)
Baza to opakowanie komercyjne pomniejszone o objętość pigmentu. Objętości pigmentu (`pigment_volumes`) do uzupełnienia po obliczeniach — na razie `null` lub `0`.

| Produkt | Rozmiar komercyjny | base_vol_l |
|---------|-------------------|------------|
| Cleantech | 0.75L | 0.68 |
| Cleantech | 3L | 2.7 |
| Cleantech | 10L | 9.0 |
| Trebitt | 0.75L | 0.68 |
| Trebitt | 3L | 2.7 |
| Trebitt | 10L | 9.0 |
| Terrasslasyr | 3L | 2.7 |
| Terrasslasyr | 10L | 9.0 |
| Tregrunning | 0.9L | 0.9 |
| Tregrunning | 2.7L | 2.7 |
| Tregrunning | 9L | 9.0 |
| Jotaproff | 3L | ~2.7 |
| Jotaproff | 10L | ~9.0 |
| Treolie | 3L | ~2.7 |

**pigment_volumes do uzupełnienia** — właściciel dostarczy obliczone wartości osobno.

---

# Kalkulator zakupu (jotun-calc)

## Jak działa
- Wczytuje `purchase_prices.json` — ceny zakupu baz w EUR per opakowanie
- Oblicza koszt pigmentów: `units × price_eur_per_ltr × euro_rate × 0.308 / 1000 × commercial_vol_l`
- Liczy cenę sprzedaży: `(koszt_bazy + koszt_pigmentu) / (1 - marża%)`
- Generuje linie faktury

## Stała: `ML_PER_UNIT = 0.308` — ml pigmentu na jednostkę Jotun

## Kluczowe produkty drewniane w `purchase_prices.json`
`DEMIDEKK_CLEANTECH`, `TREBITT_HOLZLASUR`, `TREBITT_MATT_OLJEBEIS`, `TREBITT_WOODCARE`, `DEMIDEKK_TERRASSLASYR`, `TREOLJE_V`, `JOTUN_TREGRUNNING_KLAR`, `JOTAPROFF_TACKANDE_UTEGRUND`, `PANELLAKK`, `KVIST_OG_SPERREGRUNNING`, `JOTUN_KRAFTVASK`, `JOTUN_PENSELRENS`, `DEMIDEKK_TERRASSFIX`

## Aliasy baz (BASE_ALIASES w main.py)
```
OXIDE YELLOW / GELB / YELLOW → GUL
HVIT / VIT / WHITE           → HVIT
KLAR / CLEAR / TRANSPAR.     → KLAR
A / B / C                    → bez zmian
```

## OCR formuły (endpoint /api/ocr)
- Model: `gpt-4o`
- Odczytuje screenshot z programu Jotun do doboru kolorów
- Ekstrakcja: product_name, base, formula (kody pigmentów + jednostki), colour_name, colour_code
- Kody pigmentów (2-literowe): BD, BS, BV, FS, GE, GI, GO, GS, GV, HT, OK, RS, RB, RE, SS, SV, DE, MK, OX

---

# BOK — asystent obsługi klienta (bok-drewno)

## Zasady sprzedaży drewna

**Produkty barwione NIE podlegają zwrotowi** (art. 38 pkt 3 ustawy o prawach konsumenta). Zawsze informować klienta przed potwierdzeniem.

**Kolor na ekranie jest orientacyjny** — zależy od gatunku drewna, przygotowania podłoża, liczby warstw.

**Wilgotność drewna max 18%** przed malowaniem.

**Drewna egzotyczne** (teak, bangkirai, ipe, merbau) — Terrassfix wykluczone przez TDS. Treolie/Terrasslasyr — próba obowiązkowa.

## Kiedy jaki produkt

| Sytuacja klienta | Produkt |
|-----------------|---------|
| Kryjący kolor elewacji, trwałość ~10–12 lat | Demidekk Cleantech |
| Lazura elewacja, widoczna struktura drewna, ~6–8 lat | Trebitt Holzlasur |
| Naturalny efekt olejowany | Demidekk Lasyrolja (tylko BOK) |
| Taras — ochrona + kolor | Demidekk Terrasslasyr |
| Taras — odświeżenie, pielęgnacja | Jotun Treolie / Terrassfix |
| Wnętrza, panele drewniane | Jotun Panellakk |
| Podkład nowe drewno elewacyjne | Jotun Tregrunning Klar |
| Podkład renowacja + Cleantech | Jotaproff Täckande Utegrund |
| Mycie/czyszczenie drewna | Jotun Kraftvask |
| Czyszczenie pędzli (Trebitt) | Jotun Penselrens |

## Systemy powłokowe

| Zastosowanie | System |
|---|---|
| Nowe drewno elewacyjne + Trebitt/Cleantech | Tregrunning Klar → 2× Trebitt/Cleantech |
| Renowacja + Cleantech (odsłonięte drewno) | Jotaproff Täckande Utegrund → Cleantech |
| Drewno z sękami/żywicą + Panellakk | Kvist og Sperregrunning → Panellakk |
| Nowy taras | Terrasslasyr lub Treolie (bez podkładu) |

## Struktury danych BOK (bok-drewno)

### products_config.json
- `id` — klucz produktu (np. `demidekk-cleantech`)
- `shop_id` — ID w Shoperze (null jeśli brak w sklepie)
- `package_sizes` — rozmiary w litrach (0.68 = opakowanie 0.75L)
- `stock_symbols` — symbole magazynowe
- `areas` — obszary zastosowań: `elewacja`, `plot_altana`, `taras`, `meble`, `wnetrze`, `czyszczenie`
- `yield_m2_per_l` — wydajność m²/L
- `related` — powiązane produkty

### color_bases.json
Mapowanie kolor → baza per produkt. Klucz: `product_id`, struktura:
```json
{ "bases": { "A": ["RAL 9003 Signal White", ...], "C": [...] } }
```

### shop_products.json
Dane ze sklepu (ceny, stany, warianty, atrybuty). Struktura wariantu:
```json
{ "variant_id": 974, "attributes": {"pojemnosc": "10 litrów", "kolor": "Std 0001 White"}, "price_pln": 1181.34 }
```

### areas_config.json
Konfiguracja obszarów zastosowań — używana do rekomendacji produktów wg zastosowania.

---

# Nazewnictwo plików produktów (delta-shop-api)

Konwencja identyczna jak farby przemysłowe:
- ID: myślniki (`demidekk-cleantech`)
- Plik: podkreślniki (`demidekk_cleantech.json`)
- Konwersja: `product_id.replace('-', '_') + ".json"`

---

# Ceny sklepowe — produkty drewniane

Ceny brutto z aktywnych wariantów (toggle ON w Shoperze):

## Demidekk Cleantech (104)
| Rozmiar | Kolor | Cena brutto |
|---------|-------|-------------|
| 0.75L | RAL 9005 Jed Black | 143,94 zł |
| 0.75L | Std 9938 Dempet Sort | 144,00 zł |
| 0.75L | RAL 7016 Antracite Grey | 140,58 zł |
| 0.75L | RAL 7032 Pebble Grey | 135,94 zł |
| 0.75L | Std 0745 Grann Umbra | 149,82 zł |
| 0.75L | RAL 8000 Green Brown | 144,18 zł |
| 0.75L | Std 10168 Muted Yellow | 139,71 zł |
| 0.75L | RAL 9003 Signal White | 131,85 zł |
| 0.75L | Std 0001 White | 143,75 zł |
| 0.75L | Std 1001 Egghvit | 136,38 zł |
| 3L | RAL 9005 Jed Black | 488,48 zł |
| 3L | Std 9938 Dempet Sort | 488,74 zł |
| 3L | RAL 7016 Antracite Grey | 475,05 zł |
| 3L | RAL 7032 Pebble Grey | 456,47 zł |
| 3L | Std 0745 Grann Umbra | 511,98 zł |
| 3L | RAL 8000 Green Brown | 489,44 zł |
| 3L | Std 10168 Muted Yellow | 471,57 zł |
| 3L | RAL 9003 Signal White | 440,12 zł |
| 3L | Std 0001 White | 487,72 zł |
| 3L | Std 1001 Egghvit | 470,72 zł |
| 10L | RAL 9005 Jed Black | 1 422,64 zł |
| 10L | Std 9938 Dempet Sort | 1 423,49 zł |
| 10L | RAL 7016 Antracite Grey | 1 377,87 zł |
| 10L | RAL 7032 Pebble Grey | 1 315,94 zł |
| 10L | Std 0745 Grann Umbra | 1 500,97 zł |
| 10L | RAL 8000 Green Brown | 1 425,83 zł |
| 10L | Std 10168 Muted Yellow | 1 366,27 zł |
| 10L | RAL 9003 Signal White | 1 263,48 zł |
| 10L | Std 0001 White | 1 420,08 zł |
| 10L | Std 1001 Egghvit | 1 404,58 zł |

## Trebitt Holzlasur (147)
| Rozmiar | Kolor | Cena brutto |
|---------|-------|-------------|
| 0.75L | Std 10045 Mahagoni | 105,89 zł |
| 0.75L | Std 682 kasztanowy | 104,12 zł |
| 0.75L | Std 675 palisander | 108,99 zł |
| 0.75L | Std 629 naturalny | 106,09 zł |
| 0.75L | Std 623 birmański tek | 102,79 zł |
| 3L | Std 10045 Mahagoni | 382,38 zł |
| 3L | Std 682 kasztanowy | 375,30 zł |
| 3L | Std 675 palisander | 394,77 zł |
| 3L | Std 629 naturalny | 383,16 zł |
| 3L | Std 623 birmański tek | 369,97 zł |
| 10L | Std 10045 Mahagoni | 1 057,17 zł |
| 10L | Std 629 naturalny | 1 101,15 zł |
| 10L | Std 682 kasztanowy | 1 074,95 zł |
| 10L | Std 675 palisander | 1 139,84 zł |
| 10L | Std 623 birmański tek | 1 057,17 zł |

## Demidekk Terrasslasyr (249)
| Rozmiar | Kolor | Cena brutto |
|---------|-------|-------------|
| 3L | STD 90000 Brąz Tarasowy | 312,50 zł |
| 3L | STD 10073 Stara Sosna | 356,04 zł |
| 3L | STD 9074 Nordisk Tre | 334,33 zł |
| 10L | STD 90000 Brąz Tarasowy | 899,82 zł |
| 10L | STD 10073 Stara Sosna | 1 044,96 zł |
| 10L | STD 9074 Nordisk Tre | 972,59 zł |

## Pozostałe produkty
| shop_id | Rozmiar | Kolor | Cena brutto |
|---------|---------|-------|-------------|
| 257 | 3L | Std 0001 White | 387,99 zł |
| 257 | 10L | Std 0001 White | 1 181,34 zł |
| 256 | 3L | 9001 Gylden | 186,93 zł |
| 256 | 3L | 0500 Grontonet | 168,34 zł |
| 256 | 3L | KLAR | 163,58 zł |
| 185 | 0.75L | — | 78,65 zł |
| 185 | 3L | — | 252,77 zł |
| 153 | 0.9L | — | 123,16 zł |
| 153 | 2.7L | — | 358,14 zł |
| 153 | 9L | — | 1 097,09 zł |
| 232 | 4L | — | 205,14 zł |
| 111 | 1L | — | 100,86 zł |

---

# Do uzupełnienia w przyszłości

- **pigment_volumes** dla wszystkich produktów tintowanych — właściciel dostarczy wyliczone wartości (objętość pigmentu w litrach per rozmiar opakowania per kolor)
- Po otrzymaniu pigment_volumes: uzupełnić pliki `products/*.json` w delta-shop-api i uruchomić kalkulator faktury dla farb drewnianych

---

# Znane pułapki

- Rozmiar opakowania komercyjnego (np. 3L) ≠ objętość bazy (np. 2.7L) — różnica to pigment
- `package_sizes` w `products_config.json` podane jako fizyczna objętość bazy (0.68, 2.7, 9), nie rozmiar handlowy (0.75, 3, 10)
- Demidekk Cleantech dawniej nazywała się "Ultimate Täckfärg" — w systemie magazynowym mogą być obie nazwy
- Treolie ma 11 szt. zarezerwowanych wg danych BOK — zawsze sprawdzić aktualny stan przed potwierdzeniem
- Terrassfix — nie stosować na drewno egzotyczne (wprost wykluczone przez TDS)
- Produkty barwione NIE podlegają zwrotowi — zawsze informować klienta przed potwierdzeniem zamówienia
