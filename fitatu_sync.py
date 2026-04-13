"""Sync Maczfit meals to Fitatu planner."""

import sys
import json
import os
import uuid
import base64
import requests
from datetime import date, datetime
from getpass import getpass

import maczfit_meals as maczfit

CONFIG_PATH = maczfit.CONFIG_PATH

# Fitatu API config
FITATU_API = "https://fitatu.com/api"
FITATU_HEADERS = {
    "Accept": "application/json; version=v3",
    "Content-Type": "application/json",
}


def _load_fitatu_headers():
    """Load Fitatu API keys from config.json into FITATU_HEADERS."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        api_key = cfg.get("fitatu_api_key", "")
        api_secret = cfg.get("fitatu_api_secret", "")
        if not api_key or not api_secret or "your-" in api_key:
            raise RuntimeError(
                "Missing fitatu_api_key / fitatu_api_secret in config.json.\n"
                "See README for how to obtain them."
            )
        FITATU_HEADERS.update({
            "API-Key": api_key,
            "API-Secret": api_secret,
        })

# Maczfit meal type → Fitatu meal slot
MEAL_SLOT_MAP = {
    1: "breakfast",         # Śniadanie
    2: "second_breakfast",  # II Śniadanie
    3: "lunch",             # Obiad
    4: "snack",             # Podwieczorek
    5: "dinner",            # Kolacja
}

FITATU_SLOTS = ["breakfast", "second_breakfast", "lunch", "dinner", "snack", "supper"]

fitatu_token = None
fitatu_user_id = None


def fitatu_login(email, password):
    global fitatu_token, fitatu_user_id
    _load_fitatu_headers()
    r = requests.post(f"{FITATU_API}/login", headers=FITATU_HEADERS,
                       json={"_username": email, "_password": password})
    r.raise_for_status()
    data = r.json()
    fitatu_token = data["token"]
    payload = fitatu_token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    claims = json.loads(base64.b64decode(payload))
    fitatu_user_id = claims["id"]
    print(f"[Fitatu] Logged in (userId={fitatu_user_id})")


def fitatu_auth_headers():
    return {**FITATU_HEADERS, "Authorization": f"Bearer {fitatu_token}"}


def make_fitatu_item(dish_name, kcal, macros):
    """Create a Fitatu CUSTOM_ITEM for the sync payload."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "planDayDietItemId": str(uuid.uuid1()),
        "foodType": "CUSTOM_ITEM",
        "measureId": 1,
        "measureQuantity": 1,
        "source": "API",
        "updatedAt": now,
        "protein": macros["protein"],
        "fat": macros["fat"],
        "carbohydrate": macros["carbs"],
        "energy": round(kcal),
        "name": dish_name,
    }


def fetch_maczfit_meals(target_date, cfg):
    """Login to Maczfit and return meals list."""
    email = cfg.get("maczfit_email", cfg.get("email"))
    password = cfg.get("maczfit_password", cfg.get("password"))
    if not email or "example.com" in email or email.startswith("<"):
        email = input("Maczfit email: ")
    if not password or "your-" in password or password.startswith("<"):
        password = getpass("Maczfit password: ")

    maczfit.login(email, password)
    if not maczfit.api_token:
        raise RuntimeError("Could not extract Maczfit API token")

    pkg = maczfit.find_package_for_date(maczfit.get_orders(), target_date)
    if not pkg:
        raise RuntimeError("No Maczfit package for this date")

    meals_response = maczfit.get_package_meals(pkg["Id"])
    return meals_response.get("Meals", [])


def display_and_select(meals, target_date):
    """Show meals with real macros, let user pick which to sync."""
    items = []
    for i, meal in enumerate(meals):
        mi = meal.get("MenuItem", {})
        mt = mi.get("MealTypeId", meal.get("MealTypeId", 0))
        dish = mi.get("DishName", "?")
        label = maczfit.MEAL_TYPES.get(mt, f"Meal {mt}")
        slot = MEAL_SLOT_MAP.get(mt, "snack")

        macros = maczfit.get_nutrient_stats(mi["Id"])
        if not macros:
            print(f"  [{i+1}] {label}: {dish}  (nutrient data unavailable)")
            continue

        kcal = macros["kcal"]
        items.append({
            "index": i, "label": label, "dish": dish,
            "kcal": kcal, "macros": macros, "slot": slot, "meal_type_id": mt,
            "date": target_date,
        })
        print(f"  [{i+1}] {label}: {dish}")
        print(f"      {kcal} kcal | F: {macros['fat']}g | C: {macros['carbs']}g | P: {macros['protein']}g")

    print(f"\n  [A] All meals")
    choice = input("\nSelect meals to sync (e.g. 1,3,5 or A for all): ").strip().upper()

    if choice == "A":
        selected = items
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = [items[i] for i in indices if 0 <= i < len(items)]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return []

    if not selected:
        return []

    customize = input("\nCustomize meal slots/date? (y/N): ").strip().lower()
    if customize == "y":
        slot_help = "  " + " | ".join(f"{i+1}={s}" for i, s in enumerate(FITATU_SLOTS))
        print(f"\nFitatu meal slots:\n{slot_help}\n")
        for item in selected:
            prompt = f"  {item['dish'][:50]}\n    Slot [{item['slot']}] (1-6 or Enter to keep): "
            slot_input = input(prompt).strip()
            if slot_input and slot_input.isdigit():
                idx = int(slot_input) - 1
                if 0 <= idx < len(FITATU_SLOTS):
                    item["slot"] = FITATU_SLOTS[idx]

            date_input = input(f"    Date [{item['date']}] (YYYY-MM-DD or Enter to keep): ").strip()
            if date_input:
                try:
                    item["date"] = date.fromisoformat(date_input)
                except ValueError:
                    print("    Invalid date, keeping original.")

    return selected


def sync_to_fitatu(selected_items):
    """Build sync payload and POST to Fitatu."""
    by_date = {}
    for item in selected_items:
        d = item["date"].isoformat()
        slot = item["slot"]
        by_date.setdefault(d, {}).setdefault(slot, [])
        fitatu_item = make_fitatu_item(item["dish"], item["kcal"], item["macros"])
        by_date[d][slot].append(fitatu_item)
        print(f"  + {item['dish'][:50]} → {slot} ({d})")

    payload = {
        d: {"dietPlan": {slot: {"items": items} for slot, items in slots.items()}}
        for d, slots in by_date.items()
    }

    print(f"\n[Fitatu] Syncing {len(selected_items)} item(s)...")
    url = f"{FITATU_API}/diet-plan/{fitatu_user_id}/days?synchronous=true"
    r = requests.post(url, headers=fitatu_auth_headers(), json=payload)
    r.raise_for_status()
    print("[Fitatu] Done! Check your Fitatu planner.")


def main():
    target_date = date.today()
    if len(sys.argv) > 1:
        target_date = date.fromisoformat(sys.argv[1])
    else:
        user_date = input(f"Date [YYYY-MM-DD] (Enter for today, {target_date}): ").strip()
        if user_date:
            target_date = date.fromisoformat(user_date)

    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)

    print(f"\n{'='*50}")
    print(f"  Maczfit → Fitatu Sync  |  {target_date}")
    print(f"{'='*50}")

    print("\n[Maczfit] Logging in...")
    meals = fetch_maczfit_meals(target_date, cfg)
    if not meals:
        print("No meals found.")
        return

    print(f"\nMaczfit meals for {target_date}:\n")
    selected = display_and_select(meals, target_date)
    if not selected:
        print("Nothing selected, exiting.")
        return

    print("\n[Fitatu] Logging in...")
    fitatu_email = cfg.get("fitatu_email")
    fitatu_password = cfg.get("fitatu_password")
    if not fitatu_email or "example.com" in fitatu_email or fitatu_email.startswith("<"):
        fitatu_email = input("Fitatu email: ")
    if not fitatu_password or "your-" in fitatu_password or fitatu_password.startswith("<"):
        fitatu_password = getpass("Fitatu password: ")

    fitatu_login(fitatu_email, fitatu_password)
    sync_to_fitatu(selected)


if __name__ == "__main__":
    main()
