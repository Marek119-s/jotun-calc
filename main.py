import os
import json
import re
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from openai import OpenAI

app = Flask(__name__)

# Load pricing data
DATA_PATH = Path(__file__).parent / "pricing_data" / "purchase_prices.json"
with open(DATA_PATH, encoding="utf-8") as f:
    PRICING = json.load(f)

PRODUCTS = PRICING["products"]
TINTERS  = PRICING["tinters"]
ML_PER_UNIT = PRICING["meta"]["tinting_unit_ml"]

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# ── OCR via GPT-4o Vision ─────────────────────────────────────────────────────

def ocr_formula(image_b64: str, media_type: str) -> dict:
    prompt = """You are reading a screenshot from a Jotun paint tinting machine.
Extract exactly:
1. product_name - e.g. "DEMIDEKK CLEANTECH"
2. base - single letter or short code, e.g. "C", "A", "B", "VIT"
3. formula - list of objects with "code" (e.g. "HT") and "units" (integer), parsed from e.g. "HT088 OK076 RB007 SS054"

Respond ONLY with valid JSON, no markdown, no explanation:
{"product_name": "...", "base": "...", "formula": [{"code": "HT", "units": 88}, ...]}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r'^```json|```$', '', raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ── Pricing logic ─────────────────────────────────────────────────────────────

def normalize(s):
    """Normalize string: uppercase, replace -/_ with space, strip."""
    return re.sub(r'[-_]', ' ', s.upper().strip())

def find_product(product_name: str):
    name_up = product_name.upper().strip()
    name_norm = normalize(product_name)
    for key, prod in PRODUCTS.items():
        prod_norm = normalize(prod["product_name"])
        if prod_norm in name_norm or name_norm in prod_norm:
            return key, prod
        if prod["product_name"].upper() in name_up or name_up in prod["product_name"].upper():
            return key, prod
    return None, None


def find_base(prod: dict, base_hint: str):
    hint_norm = normalize(base_hint)
    hint_up   = base_hint.upper().strip()
    bases = prod.get("bases", {})
    for bkey, bdata in bases.items():
        bkey_norm = normalize(bkey)
        # exact normalized match
        if hint_norm == bkey_norm:
            return bkey, bdata
        # hint contained in key
        if hint_norm in bkey_norm:
            return bkey, bdata
        # single letter: C → C-BAS, C_BAS, C BASE
        if re.match(r'^[A-Z]$', hint_up):
            if bkey_norm.startswith(hint_up + ' '):
                return bkey, bdata
    return None, None


def calculate_price(product_name, base_hint, pack_size, quantity, formula, margin_pct, vat_pct):
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

    base_vol_l      = pack["base_vol_l"]
    commercial_vol_l = pack["commercial_vol_l"]
    base_price_pln  = pack["price_pln_per_pack"]

    # Pigments: formula per 1L base → scale by base_vol_l
    pigment_lines     = []
    pigment_total_pln = 0.0
    pigment_total_l   = 0.0

    for item in formula:
        code  = item["code"].upper()
        units = item["units"]

        tinter = TINTERS.get(code) or TINTERS.get(code.replace('-',''))
        if not tinter:
            for tk, tv in TINTERS.items():
                if '-' in tk and tk.split('-')[0] == code[:2]:
                    tinter = tv; break

        if not tinter:
            pigment_lines.append({"code": code, "units": units, "error": f"Nieznany pigment: {code}"})
            continue

        ml_per_1L   = units * ML_PER_UNIT
        vol_l       = (ml_per_1L / 1000) * base_vol_l
        cost_pln    = vol_l * tinter["price_pln_per_ltr"]

        pigment_total_pln += cost_pln
        pigment_total_l   += vol_l

        pigment_lines.append({
            "code": tinter["code"], "units": units,
            "vol_l": round(vol_l, 4),
            "price_pln_per_ltr": tinter["price_pln_per_ltr"],
            "cost_pln": round(cost_pln, 4)
        })

    total_cost_pln   = base_price_pln + pigment_total_pln
    divisor          = 1 - (margin_pct / 100)
    sell_net_1pack   = total_cost_pln / divisor if divisor > 0 else total_cost_pln
    vat_1pack        = sell_net_1pack * (vat_pct / 100)
    sell_gross_1pack = sell_net_1pack + vat_1pack

    total_net   = sell_net_1pack * quantity
    total_vat   = vat_1pack * quantity
    total_gross = sell_gross_1pack * quantity

    pigment_sell_net = (pigment_total_pln / divisor) * quantity if pigment_total_pln > 0 else 0

    base_label = base_key.replace('_BAS','').replace('_BASE','')

    return {
        "product_name": prod["product_name"],
        "base": base_key,
        "pack_size": pack_size,
        "base_vol_l": base_vol_l,
        "commercial_vol_l": commercial_vol_l,
        "quantity": quantity,
        "margin_pct": margin_pct,
        "vat_pct": vat_pct,

        "purchase": {
            "base_pln": round(base_price_pln, 2),
            "pigment_pln": round(pigment_total_pln, 2),
            "total_pln": round(total_cost_pln, 2),
            "pigment_vol_l": round(pigment_total_l, 4),
            "pigment_lines": pigment_lines
        },

        "invoice_lines": [
            {
                "lp": 1,
                "name": f"{prod['product_name']} BASE {base_label} {commercial_vol_l}L",
                "desc": "",
                "qty": quantity,
                "unit": "szt.",
                "unit_price_net": round(base_price_pln / divisor, 2),
                "value_net": round((base_price_pln / divisor) * quantity, 2),
                "value_gross": round((base_price_pln / divisor) * (1 + vat_pct/100) * quantity, 2),
                "vat_pct": vat_pct
            },
            *([] if pigment_total_l == 0 else [{
                "lp": 2,
                "name": "MULTICOLOR SOLVENT FREE",
                "desc": "  ".join(f"{p['code']} {p['units']}" for p in pigment_lines if 'error' not in p),
                "qty": round(pigment_total_l * quantity, 4),
                "unit": "LT",
                "unit_price_net": round(pigment_total_pln / pigment_total_l, 2) if pigment_total_l > 0 else 0,
                "value_net": round(pigment_sell_net, 2),
                "value_gross": round(pigment_sell_net * (1 + vat_pct/100), 2),
                "vat_pct": vat_pct
            }])
        ],

        "summary": {
            "total_net": round(total_net, 2),
            "total_vat": round(total_vat, 2),
            "total_gross": round(total_gross, 2),
            "margin_amount": round((sell_net_1pack - total_cost_pln) * quantity, 2)
        }
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ocr", methods=["POST"])
def api_ocr():
    data = request.json
    image_b64  = data.get("image_b64")
    media_type = data.get("media_type", "image/png")
    if not image_b64:
        return jsonify({"error": "Brak obrazu"}), 400
    try:
        result = ocr_formula(image_b64, media_type)
        return jsonify(result)
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
    body = request.json
    result = calculate_price(
        product_name = body.get("product_name", ""),
        base_hint    = body.get("base", ""),
        pack_size    = body.get("pack_size", ""),
        quantity     = int(body.get("quantity", 1)),
        formula      = body.get("formula", []),
        margin_pct   = float(body.get("margin_pct", 30)),
        vat_pct      = float(body.get("vat_pct", 23))
    )
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
