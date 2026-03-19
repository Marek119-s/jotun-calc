"""
Regeneruje pricing_data/purchase_prices.json z arkusza Excel.
Użycie: python generate_prices.py Ceny_zakupu.xlsx
"""
import sys
import pandas as pd
import json
import re
from pathlib import Path

PACK_MAP = {0.68: 0.75, 0.9: 1.0, 2.7: 3.0, 9.0: 10.0}
ML_PER_UNIT = 0.308
EURO_RATE = 4.3

def to_float(val):
    try:
        return float(str(val).replace('€','').replace(',','.').strip())
    except:
        return None

def generate(xlsx_path: str):
    df = pd.read_excel(xlsx_path, sheet_name=0, header=None)

    # Tinters
    tinters = {}
    for _, row in df[df[0].astype(str).str.contains('MC TINTER', na=False)].iterrows():
        m = re.search(r'MC TINTER ([A-Z]{2})-?(\d+)', str(row[0]))
        if m:
            cd = f"{m.group(1)}-{m.group(2)}"
            cp = f"{m.group(1)}{m.group(2)}"
            e = {"name": str(row[0]).strip(), "code": cd, "price_pln_per_ltr": to_float(row[9])}
            tinters[cd] = e
            tinters[cp] = e

    # Products (STD bases only)
    skip = re.compile(r'MC TINTER|Nazwa|[Gg]et.nt', re.IGNORECASE)
    products = {}

    for _, row in df.iterrows():
        rn = str(row[0]).strip()
        if skip.search(rn):
            continue
        vol = to_float(row[1])
        pt = str(row[2]).strip() if str(row[2]) != 'nan' else 'STD'
        pln = to_float(row[10])
        if not vol or not pln or pt == 'MC':
            continue

        bm = re.search(
            r'(A-BAS|B-BAS|C-BAS|VIT\s*BAS|A-BASE|B-BASE|C-BASE|HV-BASE|Y\s*BASE|C\s*BASE|GUL\s*BASE|KLAR\s*BASE|HVIT)',
            rn, re.IGNORECASE)
        base = bm.group(1).strip().upper().replace(' ', '_') if bm else 'STANDARD'
        family = rn[:bm.start()].strip() if bm else re.sub(r'\s+[\d,.]+\s*L.*$', '', rn).strip()
        fkey = re.sub(r'\s+', '_', re.sub(r'[^A-Z0-9 ]', '', family.upper()).strip())

        cv = PACK_MAP.get(round(vol, 2), vol)
        pk = f"{cv}L".replace('.0L', 'L')

        if fkey not in products:
            products[fkey] = {"product_name": family, "bases": {}}
        if base not in products[fkey]["bases"]:
            products[fkey]["bases"][base] = {}

        products[fkey]["bases"][base][pk] = {
            "base_vol_l": vol,
            "commercial_vol_l": cv,
            "price_pln_per_pack": round(pln, 3),
            "unit": "szt."
        }

    out = {
        "meta": {
            "euro_rate": EURO_RATE,
            "tinting_unit_ml": ML_PER_UNIT,
            "pack_map": {"0.68": "0.75L", "0.9": "1L", "2.7": "3L", "9.0": "10L"},
            "formula_basis": "per_1L_base"
        },
        "products": products,
        "tinters": tinters
    }

    out_path = Path(__file__).parent / "pricing_data" / "purchase_prices.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"✓ Zapisano {out_path}")
    print(f"  Produkty: {len(products)}, Pigmenty: {len([k for k in tinters if '-' in k])}")

if __name__ == "__main__":
    xlsx = sys.argv[1] if len(sys.argv) > 1 else "Ceny_zakupu_lakiery.xlsx"
    generate(xlsx)
