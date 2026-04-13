"""Sync Maczfit meals to Fitatu planner."""

import sys
import json
import os
import uuid
import requests
from datetime import date, datetime
from getpass import getpass

import maczfit_meals as maczfit

CONFIG_PATH = maczfit.CONFIG_PATH

# Fitatu API config
FITATU_API = "https://fitatu.com/api"
FITATU_HEADERS = {
    "API-Key": "FITATU-MOBILE-APP",
    "API-Secret": "PYRXtfs88UDJMuCCrNpLV",
    "APP-UUID": "64c2d1b0-c8ad-11e8-8956-0242ac120008",
    "APP-Version": "4.5.11",
    "APP-OS": "FITATU-WEB",
    "Accept": "application/json; version=v3",
    "Content-Type": "application/json",
}

# Maczfit meal type → Fitatu meal slot
MEAL_SLOT_MAP = {
    1: "breakfast",         # Śniadanie
    2: "second_breakfast",  # II Śniadanie
    3: "lunch",             # Obiad
    4: "snack",             # Podwieczorek
    5: "dinner",            # Kolacja
}

fitatu_token = None
fitatu_user_id = None


def fitatu_login(email, password):
    global fitatu_token, fitatu_user_id
    r = requests.post(f"{FITATU_API}/login", headers=FITATU_HEADERS,
                       json={"email": email, "password": password})
    r.raise_for_status()
    data = r.json()
    fitatu_token = data.get("token")
    fitatu_user_id = data.get("userId") or data.get("id")
    print(f"[Fitatu] Logged in (userId={fitatu_user_id})")


def fitatu_auth_headers():
    return {**FITATU_HEADERS, "Authorization": f"Bearer {fitatu_token}"}


def fitatu_get_planner_day(target_date):
    url = f"{FITATU_API}/diet-and-activity-plan/{fitatu_user_id}/day/{target_date.isoformat()}"
    r = requests.get(url, headers=fitatu_auth_headers())
    r.raise_for_status()
    return r.json()


def fitatu_save_planner_day(target_date, planner_day):
    url = f"{FITATU_API}/diet-and-activity-plan/{fitatu_user_id}/day/{target_date.isoformat()}"
    r = requests.put(url, headers=fitatu_auth_headers(), json=planner_day)
    r.raise_for_status()
    return r.json()


def make_fitatu_item(dish_name, kcal, macros):
    """Create a Fitatu CUSTOM_ITEM planner entry."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "name": dish_name,
        "energy": round(kcal),
        "protein": macros["protein"],
        "fat": macros["fat"],
        "carbohydrate": macros["carbs"],
        "weight": 100,
        "foodType": "CUSTOM_ITEM",
        "planDayDietItemId": str(uuid.uuid4()),
        "measureId": 1,
        "measureName": "porcja",
        "measureQuantity": 1,
        "source": "API",
        "updatedAt": now,
        "verified": False,
        "containNutritions": True,
    }


def fetch_maczfit_meals(target_date, cfg):
    """Login to Maczfit and return (meals_list, diet_group)."""
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

    diet_group = pkg.get("Product", {}).get("Group",
        pkg.get("Product", {}).get("ChooseMenuDietGroupName", "WYBÓR MENU"))
    meals_response = maczfit.get_package_meals(pkg["Id"])
    return meals_response.get("Meals", []), diet_group


def display_and_select(meals, diet_group):
    """Show meals and let user pick which to sync."""
    fat_pct, carb_pct, protein_pct = maczfit.DIET_MACROS.get(
        diet_group, maczfit.DIET_MACROS["WYBÓR MENU"])

    items = []
    for i, meal in enumerate(meals):
        mi = meal.get("MenuItem", {})
        mt = mi.get("MealTypeId", meal.get("MealTypeId", 0))
        dish = mi.get("DishName", "?")
        kcal = mi.get("KcalSum", 0) or 0
        macros = maczfit.estimate_macros(kcal, fat_pct, carb_pct, protein_pct)
        label = maczfit.MEAL_TYPES.get(mt, f"Meal {mt}")
        slot = MEAL_SLOT_MAP.get(mt, "snack")

        items.append({
            "index": i, "label": label, "dish": dish,
            "kcal": kcal, "macros": macros, "slot": slot, "meal_type_id": mt,
        })
        print(f"  [{i+1}] {label}: {dish}")
        print(f"      {kcal:.0f} kcal | F: {macros['fat']}g | C: {macros['carbs']}g | P: {macros['protein']}g")

    print(f"\n  [A] All meals")
    choice = input("\nSelect meals to sync (e.g. 1,3,5 or A for all): ").strip().upper()

    if choice == "A":
        return items
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
        return [items[i] for i in indices if 0 <= i < len(items)]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return []


def sync_to_fitatu(selected_items, target_date):
    """Push selected meals to Fitatu planner."""
    print(f"\n[Fitatu] Fetching planner for {target_date}...")
    planner_day = fitatu_get_planner_day(target_date)

    diet_plan = planner_day.get("dietPlan", {})

    added = 0
    for item in selected_items:
        slot = item["slot"]
        if slot not in diet_plan:
            diet_plan[slot] = {"items": []}
        if "items" not in diet_plan[slot]:
            diet_plan[slot]["items"] = []

        fitatu_item = make_fitatu_item(item["dish"], item["kcal"], item["macros"])
        diet_plan[slot]["items"].append(fitatu_item)
        added += 1
        print(f"  + [{item['label']}] {item['dish']} → {slot}")

    planner_day["dietPlan"] = diet_plan
    planner_day["pushRequired"] = True

    print(f"\n[Fitatu] Saving {added} item(s)...")
    fitatu_save_planner_day(target_date, planner_day)
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

    # Step 1: Fetch from Maczfit
    print(f"\n{'='*50}")
    print(f"  Maczfit → Fitatu Sync  |  {target_date}")
    print(f"{'='*50}")

    print("\n[Maczfit] Logging in...")
    meals, diet_group = fetch_maczfit_meals(target_date, cfg)
    if not meals:
        print("No meals found.")
        return

    # Step 2: Select meals
    print(f"\nMaczfit meals for {target_date}:\n")
    selected = display_and_select(meals, diet_group)
    if not selected:
        print("Nothing selected, exiting.")
        return

    # Step 3: Login to Fitatu
    print("\n[Fitatu] Logging in...")
    fitatu_email = cfg.get("fitatu_email")
    fitatu_password = cfg.get("fitatu_password")
    if not fitatu_email or "example.com" in fitatu_email or fitatu_email.startswith("<"):
        fitatu_email = input("Fitatu email: ")
    if not fitatu_password or "your-" in fitatu_password or fitatu_password.startswith("<"):
        fitatu_password = getpass("Fitatu password: ")

    fitatu_login(fitatu_email, fitatu_password)

    # Step 4: Push to Fitatu
    sync_to_fitatu(selected, target_date)


if __name__ == "__main__":
    main()
