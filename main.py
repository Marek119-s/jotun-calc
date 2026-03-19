import os
import json
import re
import base64
from pathlib import Path
from flask import Flask, request, jsonify, render_template
import anthropic

app = Flask(__name__)

# Load pricing data
DATA_PATH = Path(__file__).parent / "pricing_data" / "purchase_prices.json"
with open(DATA_PATH, encoding="utf-8") as f:
    PRICING = json.load(f)

PRODUCTS = PRICING["products"]
TINTERS  = PRICING["tinters"]
ML_PER_UNIT = PRICING["meta"]["tinting_unit_ml"]  # 0.308 ml per Jotun unit

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── OCR via Claude Vision ─────────────────────────────────────────────────────

def ocr_formula(image_b64: str, media_type: str) -> dict:
    """Extract product, base, and formula from tinting machine screenshot."""
    prompt = """You are reading a screenshot from a Jotun paint tinting machine.
Extract exactly:
1. product_name - e.g. "DEMIDEKK CLEANTECH"
2. base - single letter or short code, e.g. "C", "A", "B", "VIT"
3. formula - list of objects with "code" (e.g. "HT") and "units" (integer), parsed from e.g. "HT088 OK076 RB007 SS054"

Respond ONLY with valid JSON, no markdown, no explanation:
{"product_name": "...", "base": "...", "formula": [{"code": "HT", "units": 88}, ...]}"""

    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r'^```json|```$', '', raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# ── Pricing logic ─────────────────────────────────────────────────────────────

def find_product(product_name: str) -> tuple[str, dict] | tuple[None, None]:
    """Fuzzy match product name to products dict."""
    name_up = product_name.upper().strip()
    for key, prod in PRODUCTS.items():
        if prod["product_name"].upper() in name_up or name_up in prod["product_name"].upper():
            return key, prod
        # key-based match
        key_clean = key.replace('_', ' ')
        if key_clean in name_up or name_up in key_clean:
            return key, prod
    return None, None


def find_base(prod: dict, base_hint: str) -> tuple[str, dict] | tuple[None, None]:
    """Match base letter/code to bases dict."""
    hint = base_hint.upper().strip()
    bases = prod.get("bases", {})

    # Direct match
    for bkey, bdata in bases.items():
        if hint == bkey.replace('_',''):
            return bkey, bdata
        if hint in bkey.upper():
            return bkey, bdata
        # single letter: C → C-BAS, C_BAS, C-BASE
        if re.match(r'^[A-Z]$', hint):
            if bkey.upper().startswith(hint + '-') or bkey.upper().startswith(hint + '_'):
                return bkey, bdata

    return None, None


def calculate_price(product_name: str, base_hint: str, pack_size: str,
                    quantity: int, formula: list[dict], margin_pct: float, vat_pct: float) -> dict:

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

    base_vol_l = pack["base_vol_l"]
    commercial_vol_l = pack["commercial_vol_l"]
    base_price_pln = pack["price_pln_per_pack"]

    # Pigment cost: formula is per 1L base → scale by base_vol_l
    pigment_lines = []
    pigment_total_pln = 0.0
    pigment_total_l = 0.0

    for item in formula:
        code = item["code"].upper()
        units = item["units"]  # Jotun units (1 unit = 0.308 ml)

        # Normalize code: try with and without dash
        tinter = TINTERS.get(code) or TINTERS.get(code.replace('-',''))
        if not tinter:
            # try prefix only match
            for tk, tv in TINTERS.items():
                if '-' in tk and tk.split('-')[0] == code[:2]:
                    tinter = tv
                    break

        if not tinter:
            pigment_lines.append({"code": code, "units": units, "error": f"Nieznany pigment: {code}"})
            continue

        ml_per_1L_base = units * ML_PER_UNIT          # ml of pigment per 1L of base
        vol_l_per_pack = (ml_per_1L_base / 1000) * base_vol_l  # scaled to actual base volume
        cost_pln = vol_l_per_pack * tinter["price_pln_per_ltr"]

        pigment_total_pln += cost_pln
        pigment_total_l   += vol_l_per_pack

        pigment_lines.append({
            "code": tinter["code"],
            "units": units,
            "vol_l": round(vol_l_per_pack, 4),
            "price_pln_per_ltr": tinter["price_pln_per_ltr"],
            "cost_pln": round(cost_pln, 4)
        })

    # Per-pack totals
    total_cost_pln  = base_price_pln + pigment_total_pln
    divisor         = 1 - (margin_pct / 100)
    sell_net_1pack  = total_cost_pln / divisor if divisor > 0 else total_cost_pln
    vat_1pack       = sell_net_1pack * (vat_pct / 100)
    sell_gross_1pack = sell_net_1pack + vat_1pack

    # × quantity
    total_net   = sell_net_1pack * quantity
    total_vat   = vat_1pack * quantity
    total_gross = sell_gross_1pack * quantity

    # Pigment sell price for invoice line (scaled by quantity)
    pigment_sell_net = (pigment_total_pln / divisor) * quantity if pigment_total_pln > 0 else 0

    return {
        "product_name": prod["product_name"],
        "base": base_key,
        "pack_size": pack_size,
        "base_vol_l": base_vol_l,
        "commercial_vol_l": commercial_vol_l,
        "quantity": quantity,
        "margin_pct": margin_pct,
        "vat_pct": vat_pct,

        # Purchase costs (per pack)
        "purchase": {
            "base_pln": round(base_price_pln, 2),
            "pigment_pln": round(pigment_total_pln, 2),
            "total_pln": round(total_cost_pln, 2),
            "pigment_vol_l": round(pigment_total_l, 4),
            "pigment_lines": pigment_lines
        },

        # Invoice lines (like the screenshot)
        "invoice_lines": [
            {
                "lp": 1,
                "name": f"{prod['product_name']} BASE {base_key.replace('_BAS','').replace('_BASE','')} {commercial_vol_l}L",
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

        # Summary
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
    """Accept image, return OCR result."""
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
        bases = {}
        for bkey, bpacks in prod.get("bases", {}).items():
            bases[bkey] = list(bpacks.keys())
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
