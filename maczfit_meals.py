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

# Nutrient name mapping (Polish → key)
NUTRIENT_MAP = {"Tłuszcze": "fat", "Węglowodany": "carbs", "Białko": "protein"}

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


def _api_headers():
    return {"Accept": "application/json", "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"}


def api_call(endpoint, params):
    r = requests.post(
        API_URL + endpoint.lstrip("/"),
        json={**params, "BrandId": BRAND_ID, "Market": 2},
        headers=_api_headers(),
    )
    r.raise_for_status()
    return r.json()


def get_nutrient_stats(menu_item_id):
    """Fetch real per-meal macros via GET with JSON body (the app's actual method)."""
    req = requests.Request(
        "GET", API_URL + "Shop/Menu/MenuItem/Nutrient/Stats",
        headers=_api_headers(),
        json={"MenuItemId": menu_item_id, "BrandId": BRAND_ID, "Market": 2},
    )
    r = requests.Session().send(req.prepare())
    if r.status_code != 200:
        return None
    data = r.json()
    macros = {"fat": 0, "carbs": 0, "protein": 0}
    for n in data.get("MenuItemNutrients", []):
        key = NUTRIENT_MAP.get(n["NutrientName"])
        if key:
            macros[key] = round(n["StanG"], 1)
    macros["kcal"] = data.get("SumKcal", 0)
    return macros


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


def print_meals(meals_response, target_date, diet_name, diet_kcal):
    meals = meals_response.get("Meals", [])

    print(f"\n{'='*64}")
    print(f"  {target_date}  |  {diet_name} ({diet_kcal} kcal)")
    print(f"{'='*64}")

    total = {"kcal": 0, "fat": 0, "carbs": 0, "protein": 0}

    for meal in meals:
        mi = meal.get("MenuItem", {})
        mt = mi.get("MealTypeId", meal.get("MealTypeId", "?"))
        dish = mi.get("DishName", "?")
        label = MEAL_TYPES.get(mt, f"Meal {mt}")

        macros = get_nutrient_stats(mi["Id"])
        if not macros:
            print(f"\n  [{label}]  {dish}")
            print(f"    (nutrient data unavailable)")
            continue

        kcal = macros["kcal"]
        total["kcal"] += kcal
        for k in ("fat", "carbs", "protein"):
            total[k] += macros[k]

        allergens = ", ".join(a.get("Name", "") for a in mi.get("Allergens", []))
        composition = mi.get("MenuComposition", "")

        print(f"\n  [{label}]  {dish}")
        print(f"    {kcal} kcal  |  F: {macros['fat']}g  |  C: {macros['carbs']}g  |  P: {macros['protein']}g")
        if allergens:
            print(f"    Alergeny: {allergens}")
        if composition:
            print(f"    Skład: {composition}")

    print(f"\n{'-'*64}")
    print(f"  TOTAL: {total['kcal']} kcal  |  F: {total['fat']:.1f}g  |  C: {total['carbs']:.1f}g  |  P: {total['protein']:.1f}g")
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

    print(f"Fetching meals for package #{pkg_id}...")
    print_meals(get_package_meals(pkg_id), target_date, diet_name, diet_kcal)


if __name__ == "__main__":
    main()
