import os
import json
import re
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from openai import OpenAI

app = Flask(__name__)

DATA_PATH = Path(__file__).parent / "pricing_data" / "purchase_prices.json"
with open(DATA_PATH, encoding="utf-8") as f:
    PRICING = json.load(f)

PRODUCTS    = PRICING["products"]
TINTERS     = PRICING["tinters"]
ML_PER_UNIT = 0.308  # ml per Jotun unit

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

UNITS_MIN = 0.1
UNITS_MAX = 999.0


def fix_ocr_number(s):
    return s.replace('O','0').replace('o','0').replace('I','1').replace('l','1').replace('B','8')


def validate_formula(raw_formula):
    validated, errors = [], []
    for item in raw_formula:
        code      = str(item.get("code", "")).upper().strip()
        units_raw = str(item.get("units", "")).strip()
        units_fixed = fix_ocr_number(units_raw)
        try:
            units = float(units_fixed)
        except ValueError:
            errors.append(f"{code}{units_raw}: nie można odczytać liczby")
            continue
        if not re.match(r'^[A-Z]{2}$', code):
            errors.append(f"Nieprawidłowy kod: '{code}'")
            continue
        if units < UNITS_MIN or units > UNITS_MAX:
            errors.append(f"{code}: wartość {units} poza zakresem {UNITS_MIN}–{UNITS_MAX}")
            continue
        validated.append({"code": code, "units": units})
    return validated, errors


def ocr_formula(image_b64, media_type):
    prompt = """You are reading a screenshot from a Jotun colour selection software (not a mixing machine).

The screen shows a product list with columns in this order:
  [BASE NAME] | [PRODUCT NAME] | [FORMULA] | [APPLICATION]

Example row:
  OXIDE YELLOW | DEMIDEKK TERRASSLASYR | RB012 SS028 | Exterior

BASE NAME is the tinting base — it can be a colour name like "OXIDE YELLOW", "HVIT", "KLAR" etc.
PRODUCT NAME is the paint product name.
FORMULA is a list of pigment codes with amounts.

Formula format — whole numbers, 2-letter code + 3 digits:
  RB012 = code RB, units 12
  SS028 = code SS, units 28
  OX005 = code OX, units 5

ALSO handle mixing machine format with decimals if present:
  HT003.7 = code HT, units 3.7
  RB040.3 = code RB, units 40.3

VALID pigment codes — ONLY these 2-letter codes:
BD, BS, BV, FS, GE, GI, GO, GS, GV, HT, OK, RS, RB, RE, SS, SV, DE, MK, OX

BASE mapping — translate base name to short code:
  OXIDE YELLOW / OXIDEYELLOW → GUL
  HVIT / WHITE / WIT → HVIT
  KLAR / CLEAR → KLAR
  A / B / C → use as-is

Extract:
1. product_name - full product name (e.g. "DEMIDEKK TERRASSLASYR")
2. base - translated base code (e.g. "GUL", "HVIT", "A", "B", "C")
3. formula - every pigment code with its numeric amount

JSON only, no explanation:
{"product_name":"DEMIDEKK TERRASSLASYR","base":"GUL","formula":[{"code":"RB","units":12},{"code":"SS","units":28}]}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=400,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
            {"type": "text", "text": prompt}
        ]}]
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r'^```json|```$', '', raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def normalize(s):
    return re.sub(r'[-_]', ' ', s.upper().strip())


def find_product(product_name):
    name_norm = normalize(product_name)
    for key, prod in PRODUCTS.items():
        if normalize(prod["product_name"]) in name_norm or name_norm in normalize(prod["product_name"]):
            return key, prod
    return None, None


# Aliasy baz: różne nazwy z różnych wersji oprogramowania Jotuna → klucz w JSON
BASE_ALIASES = {
    "OXIDE YELLOW": "GUL", "OXIDEYELLOW": "GUL", "OX": "GUL",
    "HVIT":         "HVIT", "VIT": "HVIT", "WHITE": "HVIT",
    "KLAR":         "STANDARD", "CLEAR": "STANDARD",
}

def find_base(prod, base_hint):
    # Zastosuj alias jeśli istnieje
    hint_up = base_hint.upper().strip()
    hint_up = BASE_ALIASES.get(hint_up, hint_up)

    hint_norm = normalize(hint_up)
    for bkey, bdata in prod.get("bases", {}).items():
        bkey_norm = normalize(bkey)
        if hint_norm == bkey_norm or hint_norm in bkey_norm:
            return bkey, bdata
        if re.match(r'^[A-Z]$', hint_up) and bkey_norm.startswith(hint_up + ' '):
            return bkey, bdata
    return None, None


def calculate_price(product_name, base_hint, pack_size, quantity,
                    formula, margin_pct, vat_pct, euro_rate=4.3):

    prod_key, prod = find_product(product_name)
    if not prod:
        return {"error": f"Nie znaleziono produktu: {product_name}"}

    base_key, base_packs = find_base(prod, base_hint)
    if not base_packs:
        available = list(prod.get("bases", {}).keys())
        return {"error": f"Nie znaleziono bazy '{base_hint}'. Dostępne: {available}"}

    pack = base_packs.get(pack_size)
    if not pack:
        available = list(base_packs.keys())
        return {"error": f"Brak opakowania {pack_size}. Dostępne: {available}"}

    base_vol_l       = pack["base_vol_l"]
    commercial_vol_l = pack["commercial_vol_l"]
    base_price_pln   = pack["price_eur_per_pack"] * euro_rate

    # Pigments
    # Excel formula: SUMA(jednostki × cena_EUR × kurs) × 0.308 / 1000 × commercial_vol
    pigment_lines     = []
    pigment_total_pln = 0.0
    total_units_sum   = 0.0

    # Aliasy dla pełnych nazw pigmentów jakie może zwrócić OCR
    PIGMENT_ALIASES = {
        "OXIDEYELLOW": "OX", "OXIDE YELLOW": "OX", "OXIDGELB": "OX",
        "OXIDERED": "RE", "OXIDE RED": "RE",
        "BLACK": "SS", "SCHWARZ": "SS",
        "WHITE": "SV", "WEISS": "SV",
        "CARBON": "SS",
    }

    for item in formula:
        code  = item["code"].upper().strip()
        units = float(item["units"])

        # Sprawdź alias (pełna nazwa → 2-literowy kod)
        code = PIGMENT_ALIASES.get(code, code)
        # Weź tylko pierwsze 2 litery jeśli kod jest dłuższy (np. OX12 → OX)
        if len(code) > 2 and not TINTERS.get(code):
            code = code[:2]

        tinter = TINTERS.get(code) or TINTERS.get(code.replace('-', ''))
        if not tinter:
            for tk, tv in TINTERS.items():
                if '-' in tk and tk.split('-')[0] == code[:2]:
                    tinter = tv
                    break

        if not tinter:
            pigment_lines.append({"code": code, "units": units, "error": f"Nieznany pigment: {code}"})
            continue

        total_units_sum += units
        cost_pln = units * tinter["price_eur_per_ltr"] * euro_rate * ML_PER_UNIT / 1000 * commercial_vol_l
        pigment_total_pln += cost_pln

        pigment_lines.append({
            "code": tinter["code"],
            "units": units,
            "price_eur_per_ltr": tinter["price_eur_per_ltr"],
            "cost_pln": round(cost_pln, 4)
        })

    # Volume: Excel ZAOKR(sum_units × 0.308 × commercial_vol / 1000, 2)
    pigment_total_l = round(total_units_sum * ML_PER_UNIT * commercial_vol_l / 1000, 2)

    # Jesli formula byla podana ale zaden pigment nie przeszedl walidacji -> ostrzezenie
    base_only_warning = len(formula) > 0 and pigment_total_pln == 0.0


    # Margin on base + pigments together
    total_cost_pln   = base_price_pln + pigment_total_pln
    divisor          = 1 - (margin_pct / 100)
    sell_net_1pack   = total_cost_pln / divisor if divisor > 0 else total_cost_pln
    vat_1pack        = sell_net_1pack * (vat_pct / 100)
    sell_gross_1pack = sell_net_1pack + vat_1pack

    total_net   = sell_net_1pack * quantity
    total_vat   = vat_1pack * quantity
    total_gross = sell_gross_1pack * quantity

    base_label = base_key.replace('_BAS','').replace('_BASE','').replace('-BAS','').replace('-BASE','')

    invoice_lines = [{
        "lp": 1,
        "name": f"{prod['product_name']} BASE {base_label} {commercial_vol_l}L",
        "desc": "",
        "qty": quantity,
        "unit": "szt.",
        "unit_price_net": round(base_price_pln / divisor, 2),
        "value_net": round((base_price_pln / divisor) * quantity, 2),
        "value_gross": round((base_price_pln / divisor) * (1 + vat_pct/100) * quantity, 2),
        "vat_pct": vat_pct
    }]

    if pigment_total_l > 0:
        pig_sell_net = (pigment_total_pln / divisor) * quantity
        invoice_lines.append({
            "lp": 2,
            "name": "MULTICOLOR SOLVENT FREE",
            "desc": "  ".join(f"{p['code']} {p['units']}" for p in pigment_lines if 'error' not in p),
            "qty": round(pigment_total_l * quantity, 4),
            "unit": "LT",
            "unit_price_net": round((pigment_total_pln / divisor) / pigment_total_l, 2) if pigment_total_l > 0 else 0,
            "value_net": round(pig_sell_net, 2),
            "value_gross": round(pig_sell_net * (1 + vat_pct/100), 2),
            "vat_pct": vat_pct
        })

    return {
        "base_only_warning": base_only_warning,
        "product_name": prod["product_name"],
        "base": base_key,
        "pack_size": pack_size,
        "base_vol_l": base_vol_l,
        "commercial_vol_l": commercial_vol_l,
        "quantity": quantity,
        "margin_pct": margin_pct,
        "vat_pct": vat_pct,
        "euro_rate": euro_rate,
        "purchase": {
            "base_pln": round(base_price_pln, 2),
            "pigment_pln": round(pigment_total_pln, 2),
            "total_pln": round(total_cost_pln, 2),
            "pigment_vol_l": pigment_total_l,
            "pigment_lines": pigment_lines
        },
        "invoice_lines": invoice_lines,
        "summary": {
            "total_net": round(total_net, 2),
            "total_vat": round(total_vat, 2),
            "total_gross": round(total_gross, 2),
            "margin_amount": round((sell_net_1pack - total_cost_pln) * quantity, 2)
        }
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    data       = request.json
    image_b64  = data.get("image_b64")
    media_type = data.get("media_type", "image/png")
    if not image_b64:
        return jsonify({"error": "Brak obrazu"}), 400
    try:
        raw = ocr_formula(image_b64, media_type)
        validated, errors = validate_formula(raw.get("formula", []))
        raw["formula"]    = validated
        raw["ocr_errors"] = errors
        return jsonify(raw)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products", methods=["GET"])
def api_products():
    out = []
    for key, prod in PRODUCTS.items():
        bases = {bkey: list(bpacks.keys()) for bkey, bpacks in prod.get("bases", {}).items()}
        out.append({"key": key, "name": prod["product_name"], "bases": bases})
    return jsonify(out)


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    body   = request.json
    result = calculate_price(
        product_name = body.get("product_name", ""),
        base_hint    = body.get("base", ""),
        pack_size    = body.get("pack_size", ""),
        quantity     = int(body.get("quantity", 1)),
        formula      = body.get("formula", []),
        margin_pct   = float(body.get("margin_pct", 30)),
        vat_pct      = float(body.get("vat_pct", 23)),
        euro_rate    = float(body.get("euro_rate", 4.3))
    )
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
