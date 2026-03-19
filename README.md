# Jotun Kalkulator Cen

Aplikacja do obliczania cen zakupu/sprzedaży farb Jotun na podstawie screenshota z programu do mieszania.

## Flow

1. Wgraj screenshot z programu do mieszania (OCR odczytuje: produkt, bazę, formułę)
2. Wybierz opakowanie + ilość + marżę
3. Otrzymujesz specyfikację towarową (baza szt. + pigmenty LT) z kosztem zakupu i ceną sprzedaży

## Logika opakowań

| Baza (rzeczywista) | Opakowanie handlowe |
|--------------------|---------------------|
| 0.68 L             | 0.75 L              |
| 0.9 L              | 1 L                 |
| 2.7 L              | 3 L                 |
| 9.0 L              | 10 L                |

Formuła pigmentów podana jest **na 1L bazy** → skalowana × `base_vol_l` dla wybranego opakowania.
Pigmenty: 1 jednostka Jotun = 0.308 ml.

## Deploy na Railway

1. Wgraj repozytorium na GitHub
2. Nowy projekt w Railway → Deploy from GitHub
3. Dodaj zmienną środowiskową:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
4. Railway automatycznie wykryje `Procfile` i uruchomi aplikację

## Lokalne uruchomienie

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python main.py
```

## Struktura

```
jotun-calc/
├── main.py                     # Flask app + logika kalkulacji
├── pricing_data/
│   └── purchase_prices.json    # Ceny zakupu z arkusza Excel
├── templates/
│   └── index.html              # Frontend
├── requirements.txt
└── Procfile
```

## Aktualizacja cen

Aby zaktualizować ceny zakupu, uruchom skrypt generujący JSON z nowego arkusza Excel:

```bash
python generate_prices.py Nowy_arkusz.xlsx
```
