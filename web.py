"""Web UI backend for Maczfit → Fitatu drag-and-drop sync."""

import json
import os
import secrets
import ssl
import subprocess
import uuid
import base64
import requests
from datetime import date, datetime
from functools import wraps
from flask import Flask, jsonify, request, send_file, session, redirect, url_for

import maczfit_meals as maczfit
from fitatu_sync import (
    FITATU_API, FITATU_HEADERS, FITATU_SLOTS,
    MEAL_SLOT_MAP, make_fitatu_item, _load_fitatu_headers,
)

app = Flask(__name__)
CONFIG_PATH = maczfit.CONFIG_PATH

# Session state (single-user tool)
_state = {"maczfit_logged_in": False, "fitatu_token": None, "fitatu_user_id": None, "cfg": {}}


# --- Authentication ---

def _ui_password():
    return cfg().get("ui_password", "")


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if _ui_password() and not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        if request.form.get("password") == _ui_password():
            session["authenticated"] = True
            return redirect(url_for("index"))
        return LOGIN_HTML.replace("<!--ERR-->", '<p style="color:#f44336;margin-top:8px">Wrong password</p>'), 401
    return LOGIN_HTML


LOGIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login — Maczfit → Fitatu</title>
<style>body{font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;background:#f0f2f5;margin:0}
.box{background:#fff;padding:32px;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.1);width:320px;text-align:center}
h2{margin-bottom:20px;font-size:20px}input{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:14px;margin-bottom:12px;box-sizing:border-box}
button{width:100%;padding:10px;border:none;border-radius:6px;background:#4CAF50;color:#fff;font-size:14px;cursor:pointer}button:hover{background:#45a049}</style>
</head><body><div class="box"><h2>🥗 Maczfit → Fitatu</h2>
<form method="POST"><input type="password" name="password" placeholder="Password" autofocus required>
<button type="submit">Log in</button></form><!--ERR--></div></body></html>"""


def cfg():
    if not _state["cfg"] and os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            _state["cfg"] = json.load(f)
    return _state["cfg"]


def ensure_maczfit():
    if not _state["maczfit_logged_in"]:
        c = cfg()
        maczfit.login(c.get("maczfit_email", c.get("email")),
                       c.get("maczfit_password", c.get("password")))
        _state["maczfit_logged_in"] = True


def ensure_fitatu():
    if not _state["fitatu_token"]:
        _load_fitatu_headers()
        c = cfg()
        r = requests.post(f"{FITATU_API}/login", headers=FITATU_HEADERS,
                           json={"_username": c["fitatu_email"], "_password": c["fitatu_password"]})
        r.raise_for_status()
        _state["fitatu_token"] = r.json()["token"]
        payload = _state["fitatu_token"].split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        _state["fitatu_user_id"] = json.loads(base64.b64decode(payload))["id"]


def fitatu_headers():
    return {**FITATU_HEADERS, "Authorization": f"Bearer {_state['fitatu_token']}"}


@app.route("/")
@login_required
def index():
    return send_file("ui.html")


@app.route("/api/maczfit/<date_str>")
@login_required
def get_maczfit(date_str):
    try:
        target = date.fromisoformat(date_str)
        ensure_maczfit()
        pkg = maczfit.find_package_for_date(maczfit.get_orders(), target)
        if not pkg:
            return jsonify({"meals": [], "error": "No package for this date"})

        raw_meals = maczfit.get_package_meals(pkg["Id"]).get("Meals", [])
        meals = []
        for meal in raw_meals:
            mi = meal.get("MenuItem", {})
            mt = mi.get("MealTypeId", meal.get("MealTypeId", 0))
            macros = maczfit.get_nutrient_stats(mi["Id"])
            if not macros:
                continue
            meals.append({
                "dish": mi.get("DishName", "?"),
                "label": maczfit.MEAL_TYPES.get(mt, f"Meal {mt}"),
                "kcal": macros["kcal"],
                "protein": macros["protein"],
                "fat": macros["fat"],
                "carbs": macros["carbs"],
                "default_slot": MEAL_SLOT_MAP.get(mt, "snack"),
            })
        return jsonify({"meals": meals})
    except Exception as e:
        return jsonify({"meals": [], "error": str(e)}), 500


@app.route("/api/fitatu/<date_str>")
@login_required
def get_fitatu(date_str):
    try:
        target = date.fromisoformat(date_str)
        ensure_fitatu()
        url = f"{FITATU_API}/diet-and-activity-plan/{_state['fitatu_user_id']}/day/{date_str}"
        r = requests.get(url, headers=fitatu_headers())
        r.raise_for_status()
        day = r.json()
        slots = {}
        for slot in FITATU_SLOTS:
            data = day.get("dietPlan", {}).get(slot, {})
            items = [
                {"id": it.get("planDayDietItemId"), "name": it.get("name", "?"),
                 "energy": it.get("energy", 0), "protein": it.get("protein", 0),
                 "fat": it.get("fat", 0), "carbohydrate": it.get("carbohydrate", 0),
                 "foodType": it.get("foodType", "?"), "productId": it.get("productId")}
                for it in data.get("items", []) if not it.get("deletedAt")
            ]
            slots[slot] = items
        return jsonify({"slots": slots})
    except Exception as e:
        return jsonify({"slots": {}, "error": str(e)}), 500


@app.route("/api/sync", methods=["POST"])
@login_required
def sync():
    try:
        ensure_fitatu()
        data = request.json  # { date: "2026-04-13", slot: "breakfast", meal: {...} }
        target_date = data["date"]
        slot = data["slot"]
        meal = data["meal"]
        macros = {"protein": meal["protein"], "fat": meal["fat"], "carbs": meal["carbs"]}
        item = make_fitatu_item(meal["dish"], meal["kcal"], macros)
        payload = {target_date: {"dietPlan": {slot: {"items": [item]}}}}
        url = f"{FITATU_API}/diet-plan/{_state['fitatu_user_id']}/days?synchronous=true"
        r = requests.post(url, headers=fitatu_headers(), json=payload)
        r.raise_for_status()
        return jsonify({"ok": True, "response": r.json()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/fitatu/delete", methods=["POST"])
@login_required
def delete_item():
    try:
        ensure_fitatu()
        data = request.json  # { date, slot, item: {id, foodType, name, energy, protein, fat, carbohydrate} }
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item = data["item"]
        sync_item = {
            "planDayDietItemId": item["id"],
            "foodType": item.get("foodType", "CUSTOM_ITEM"),
            "measureId": 1, "measureQuantity": 1,
            "source": "API", "deletedAt": now, "updatedAt": now,
        }
        # CUSTOM_ITEM requires nutritional fields even for deletion
        if item.get("foodType") == "CUSTOM_ITEM":
            sync_item.update({"name": item.get("name", "x"), "energy": item.get("energy", 0),
                              "protein": item.get("protein", 0), "fat": item.get("fat", 0),
                              "carbohydrate": item.get("carbohydrate", 0)})
        else:
            sync_item["productId"] = item.get("productId")
        payload = {data["date"]: {"dietPlan": {data["slot"]: {"items": [sync_item]}}}}
        uid = _state["fitatu_user_id"]
        url = f"{FITATU_API}/diet-plan/{uid}/days?synchronous=true"
        r = requests.post(url, headers=fitatu_headers(), json=payload)
        r.raise_for_status()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/fitatu/move", methods=["POST"])
@login_required
def move_item():
    """Move item between slots/dates: delete from old + add to new in one sync call."""
    try:
        ensure_fitatu()
        data = request.json  # { fromDate, toDate, fromSlot, toSlot, item }
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item = data["item"]
        from_date = data.get("fromDate", data.get("date"))
        to_date = data.get("toDate", from_date)

        # Build delete entry for old slot
        del_item = {
            "planDayDietItemId": item["id"],
            "foodType": item.get("foodType", "CUSTOM_ITEM"),
            "measureId": 1, "measureQuantity": 1,
            "source": "API", "deletedAt": now, "updatedAt": now,
        }
        if item.get("foodType") == "CUSTOM_ITEM":
            del_item.update({"name": item.get("name", "x"), "energy": item.get("energy", 0),
                             "protein": item.get("protein", 0), "fat": item.get("fat", 0),
                             "carbohydrate": item.get("carbohydrate", 0)})
        else:
            del_item["productId"] = item.get("productId")

        # Build add entry for new slot
        macros = {"protein": item.get("protein", 0), "fat": item.get("fat", 0),
                  "carbs": item.get("carbohydrate", 0)}
        add_item = make_fitatu_item(item.get("name", "?"), item.get("energy", 0), macros)

        payload = {}
        if from_date == to_date:
            payload[from_date] = {"dietPlan": {
                data["fromSlot"]: {"items": [del_item]},
                data["toSlot"]: {"items": [add_item]},
            }}
        else:
            payload[from_date] = {"dietPlan": {data["fromSlot"]: {"items": [del_item]}}}
            payload[to_date] = {"dietPlan": {data["toSlot"]: {"items": [add_item]}}}

        uid = _state["fitatu_user_id"]
        url = f"{FITATU_API}/diet-plan/{uid}/days?synchronous=true"
        r = requests.post(url, headers=fitatu_headers(), json=payload)
        r.raise_for_status()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/fitatu/edit", methods=["POST"])
@login_required
def edit_item():
    """Edit item: delete old + add updated in one sync call."""
    try:
        ensure_fitatu()
        data = request.json  # { date, slot, item (original), updated {name,energy,protein,fat,carbohydrate} }
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item = data["item"]
        upd = data["updated"]

        # Delete old
        del_item = {
            "planDayDietItemId": item["id"],
            "foodType": item.get("foodType", "CUSTOM_ITEM"),
            "measureId": 1, "measureQuantity": 1,
            "source": "API", "deletedAt": now, "updatedAt": now,
        }
        if item.get("foodType") == "CUSTOM_ITEM":
            del_item.update({"name": item.get("name", "x"), "energy": item.get("energy", 0),
                             "protein": item.get("protein", 0), "fat": item.get("fat", 0),
                             "carbohydrate": item.get("carbohydrate", 0)})
        else:
            del_item["productId"] = item.get("productId")

        # Add new with updated values
        macros = {"protein": upd["protein"], "fat": upd["fat"], "carbs": upd["carbohydrate"]}
        add_item = make_fitatu_item(upd["name"], upd["energy"], macros)

        payload = {
            data["date"]: {"dietPlan": {data["slot"]: {"items": [del_item, add_item]}}}
        }
        uid = _state["fitatu_user_id"]
        url = f"{FITATU_API}/diet-plan/{uid}/days?synchronous=true"
        r = requests.post(url, headers=fitatu_headers(), json=payload)
        r.raise_for_status()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _ensure_certs(cert_dir=None):
    """Generate self-signed TLS cert if none configured."""
    cert_dir = cert_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
    cert = os.path.join(cert_dir, "cert.pem")
    key = os.path.join(cert_dir, "key.pem")
    if os.path.exists(cert) and os.path.exists(key):
        return cert, key
    os.makedirs(cert_dir, exist_ok=True)
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key, "-out", cert, "-days", "365",
        "-subj", "/CN=maczfit-ui",
    ], check=True, capture_output=True)
    print(f"[TLS] Generated self-signed cert in {cert_dir}/")
    return cert, key


def _run_http_redirect(https_port):
    """Run a tiny HTTP server that redirects everything to HTTPS."""
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    http_port = https_port - 1  # e.g. 5554 → 5555

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "").split(":")[0] or "localhost"
            self.send_response(301)
            self.send_header("Location", f"https://{host}:{https_port}{self.path}")
            self.end_headers()
        do_POST = do_HEAD = do_GET
        def log_message(self, *args):
            pass  # silent

    srv = HTTPServer(("0.0.0.0", http_port), RedirectHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    print(f"[UI] HTTP redirect: http://0.0.0.0:{http_port} → https://…:{https_port}")


if __name__ == "__main__":
    c = cfg()
    app.secret_key = c.get("ui_secret_key", secrets.token_hex(32))
    port = int(c.get("ui_port", 5555))
    use_tls = c.get("ui_tls", True)

    ssl_ctx = None
    if use_tls:
        cert, key = _ensure_certs(c.get("ui_cert_dir"))
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert, key)
        _run_http_redirect(port)

    try:
        import gunicorn  # noqa: F401
        from gunicorn.app.base import BaseApplication

        class GunicornApp(BaseApplication):
            def load_config(self):
                self.cfg.set("bind", f"0.0.0.0:{port}")
                self.cfg.set("workers", 1)
                if ssl_ctx:
                    self.cfg.set("certfile", cert)
                    self.cfg.set("keyfile", key)

            def load(self):
                return app

        print(f"[UI] Starting gunicorn on {'https' if use_tls else 'http'}://0.0.0.0:{port}")
        GunicornApp().run()
    except ImportError:
        proto = "https" if use_tls else "http"
        print(f"[UI] Starting Flask dev server on {proto}://0.0.0.0:{port}")
        print("[UI] Install gunicorn for production use: pip install gunicorn")
        app.run(host="0.0.0.0", port=port, ssl_context=ssl_ctx)
