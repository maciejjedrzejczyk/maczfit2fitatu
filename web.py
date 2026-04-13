"""Web UI backend for Maczfit → Fitatu drag-and-drop sync."""

import json
import os
import uuid
import base64
import requests
from datetime import date, datetime
from flask import Flask, jsonify, request, send_file

import maczfit_meals as maczfit
from fitatu_sync import (
    FITATU_API, FITATU_HEADERS, FITATU_SLOTS,
    MEAL_SLOT_MAP, make_fitatu_item,
)

app = Flask(__name__)
CONFIG_PATH = maczfit.CONFIG_PATH

# Session state (single-user tool)
_state = {"maczfit_logged_in": False, "fitatu_token": None, "fitatu_user_id": None, "cfg": {}}


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
def index():
    return send_file("ui.html")


@app.route("/api/maczfit/<date_str>")
def get_maczfit(date_str):
    try:
        target = date.fromisoformat(date_str)
        ensure_maczfit()
        pkg = maczfit.find_package_for_date(maczfit.get_orders(), target)
        if not pkg:
            return jsonify({"meals": [], "error": "No package for this date"})

        diet_group = pkg.get("Product", {}).get("Group",
            pkg.get("Product", {}).get("ChooseMenuDietGroupName", "WYBÓR MENU"))
        fat_pct, carb_pct, protein_pct = maczfit.DIET_MACROS.get(
            diet_group, maczfit.DIET_MACROS["WYBÓR MENU"])

        raw_meals = maczfit.get_package_meals(pkg["Id"]).get("Meals", [])
        meals = []
        for meal in raw_meals:
            mi = meal.get("MenuItem", {})
            mt = mi.get("MealTypeId", meal.get("MealTypeId", 0))
            kcal = mi.get("KcalSum", 0) or 0
            macros = maczfit.estimate_macros(kcal, fat_pct, carb_pct, protein_pct)
            meals.append({
                "dish": mi.get("DishName", "?"),
                "label": maczfit.MEAL_TYPES.get(mt, f"Meal {mt}"),
                "kcal": round(kcal),
                "protein": macros["protein"],
                "fat": macros["fat"],
                "carbs": macros["carbs"],
                "default_slot": MEAL_SLOT_MAP.get(mt, "snack"),
            })
        return jsonify({"meals": meals, "diet_group": diet_group})
    except Exception as e:
        return jsonify({"meals": [], "error": str(e)}), 500


@app.route("/api/fitatu/<date_str>")
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
                {"name": it.get("name", "?"), "energy": it.get("energy", 0),
                 "protein": it.get("protein", 0), "fat": it.get("fat", 0),
                 "carbohydrate": it.get("carbohydrate", 0), "foodType": it.get("foodType", "?")}
                for it in data.get("items", []) if not it.get("deletedAt")
            ]
            slots[slot] = items
        return jsonify({"slots": slots})
    except Exception as e:
        return jsonify({"slots": {}, "error": str(e)}), 500


@app.route("/api/sync", methods=["POST"])
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


if __name__ == "__main__":
    app.run(debug=True, port=5555)
