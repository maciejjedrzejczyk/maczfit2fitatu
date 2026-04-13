"""Fetch daily meal nutritional info from your Maczfit account."""

import sys
import json
import os
import re
import requests
from getpass import getpass
from datetime import date

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
BASE = "https://www.maczfit.pl"
API_URL = "https://gw-prd.maczhub-api.maczfit.pl/api/"
BRAND_ID = 5
MEAL_TYPES = {1: "Śniadanie", 2: "II Śniadanie", 3: "Obiad", 4: "Podwieczorek", 5: "Kolacja"}

# Macro ratios per diet group (from frontend DietsSwiper.js getDietChart)
# Format: {fats%, carbs%, protein%}
DIET_MACROS = {
    "FIT": (35, 45, 20), "SLIM": (35, 45, 20), "COMFORT": (35, 45, 20),
    "VEGE": (35, 47, 18), "DIABETIC": (35, 42, 23), "WEGAN": (35, 50, 15),
    "HYPO HASHIMOTO": (35, 43, 22), "HYPOHASHIMOTO": (35, 43, 22),
    "NO LACTOSE & LOW GLUTEN": (35, 45, 20), "NOLACTOSELOWGLUTEN": (35, 45, 20),
    "VEGE & FISH": (35, 45, 20), "VEGEFISH": (35, 45, 20),
    "FODMAP": (35, 45, 20), "KETO": (75, 5, 20),
    "WYBÓR MENU": (35, 45, 20),  # default for choose-menu diets
}

s = requests.Session()
s.headers.update({"X-Requested-With": "XMLHttpRequest"})
api_token = None
user_id = None


def refresh_csrf():
    token = s.cookies.get("XSRF-TOKEN")
    if token:
        s.headers["X-XSRF-TOKEN"] = requests.utils.unquote(token)


def login(email, password):
    global api_token, user_id
    s.get(f"{BASE}/login").raise_for_status()
    refresh_csrf()
    s.post(f"{BASE}/login", json={"email": email, "password": password, "remember_me": True}).raise_for_status()
    refresh_csrf()
    page = s.get(f"{BASE}/moje-konto").text
    m = re.search(r"token\s*=\s*[\"']([^\"']+)[\"']", page)
    if m:
        api_token = m.group(1)
    m = re.search(r"userId\s*=\s*(\d+)", page)
    if m:
        user_id = int(m.group(1))
    print(f"Logged in. (userId={user_id})")


def api_call(endpoint, params):
    r = requests.post(
        API_URL + endpoint.lstrip("/"),
        json={**params, "BrandId": BRAND_ID, "Market": 2},
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "Authorization": f"Bearer {api_token}"},
    )
    r.raise_for_status()
    return r.json()


def get_orders():
    r = s.post(f"{BASE}/my-account/order/get-all-transactions-without-rating")
    r.raise_for_status()
    return r.json()


def get_package_meals(package_id):
    return api_call("/Transaction/Package/Meals/All", {
        "TransactionPackageId": package_id, "ClientId": user_id,
    })


def find_package_for_date(orders_data, target_date):
    target = target_date.isoformat()
    all_txns = orders_data.get("transactions", [])
    hist = orders_data.get("historyTransactions", {})
    if isinstance(hist, dict):
        all_txns += list(hist.values())
    elif isinstance(hist, list):
        all_txns += hist

    for txn in all_txns:
        for pkg in txn.get("Packages", []):
            if pkg.get("ValidDisplayDeliveryDate") == target:
                return pkg

    dates = sorted(set(
        pkg.get("ValidDisplayDeliveryDate", "?")
        for txn in all_txns for pkg in txn.get("Packages", [])
    ))
    print(f"No package found for {target}.")
    print(f"Available dates: {', '.join(dates)}")
    return None


def estimate_macros(kcal, fat_pct, carb_pct, protein_pct):
    """Estimate grams from kcal using macro ratios (fat=9kcal/g, protein/carbs=4kcal/g)."""
    return {
        "fat": round(kcal * fat_pct / 100 / 9, 1),
        "carbs": round(kcal * carb_pct / 100 / 4, 1),
        "protein": round(kcal * protein_pct / 100 / 4, 1),
    }


def print_meals(meals_response, target_date, diet_name, diet_kcal, diet_group):
    meals = meals_response.get("Meals", [])

    # Resolve macro ratios for this diet
    fat_pct, carb_pct, protein_pct = DIET_MACROS.get(
        diet_group, DIET_MACROS.get("WYBÓR MENU"))

    print(f"\n{'='*64}")
    print(f"  {target_date}  |  {diet_name} ({diet_kcal} kcal)")
    print(f"  Macro split: F {fat_pct}% / C {carb_pct}% / P {protein_pct}%  (estimated)")
    print(f"{'='*64}")

    total = {"kcal": 0, "fat": 0, "carbs": 0, "protein": 0}

    for meal in meals:
        mi = meal.get("MenuItem", {})
        mt = mi.get("MealTypeId", meal.get("MealTypeId", "?"))
        dish = mi.get("DishName", "?")
        kcal = mi.get("KcalSum", 0) or 0
        label = MEAL_TYPES.get(mt, f"Meal {mt}")

        macros = estimate_macros(kcal, fat_pct, carb_pct, protein_pct)
        total["kcal"] += kcal
        for k in ("fat", "carbs", "protein"):
            total[k] += macros[k]

        allergens = ", ".join(a.get("Name", "") for a in mi.get("Allergens", []))
        composition = mi.get("MenuComposition", "")

        print(f"\n  [{label}]  {dish}")
        print(f"    {kcal:.0f} kcal  |  F: {macros['fat']}g  |  C: {macros['carbs']}g  |  P: {macros['protein']}g")
        if allergens:
            print(f"    Alergeny: {allergens}")
        if composition:
            print(f"    Skład: {composition}")

    print(f"\n{'-'*64}")
    print(f"  TOTAL: {total['kcal']:.0f} kcal  |  F: {total['fat']:.1f}g  |  C: {total['carbs']:.1f}g  |  P: {total['protein']:.1f}g")
    print(f"  (macros estimated from diet type ratio, not per-dish)")
    print(f"{'='*64}")


def main():
    target_date = date.today()
    if len(sys.argv) > 1:
        target_date = date.fromisoformat(sys.argv[1])
    else:
        user_date = input(f"Date [YYYY-MM-DD] (Enter for today, {target_date}): ").strip()
        if user_date:
            target_date = date.fromisoformat(user_date)

    email, password = None, None
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        email = cfg.get("maczfit_email", cfg.get("email"))
        password = cfg.get("maczfit_password", cfg.get("password"))
    if not email or "example.com" in email or email.startswith("<"):
        email = input("Email: ")
    if not password or "your-" in password or password.startswith("<"):
        password = getpass("Password: ")

    login(email, password)
    if not api_token:
        print("Error: Could not extract API token.")
        return

    print(f"\nFetching orders for {target_date}...")
    pkg = find_package_for_date(get_orders(), target_date)
    if not pkg:
        return

    pkg_id = pkg["Id"]
    diet_name = pkg.get("Product", {}).get("Name", "?")
    diet_kcal = pkg.get("Product", {}).get("Kcal", "?")
    diet_group = pkg.get("Product", {}).get("Group", pkg.get("Product", {}).get("ChooseMenuDietGroupName", "WYBÓR MENU"))

    print(f"Fetching meals for package #{pkg_id}...")
    print_meals(get_package_meals(pkg_id), target_date, diet_name, diet_kcal, diet_group)


if __name__ == "__main__":
    main()
