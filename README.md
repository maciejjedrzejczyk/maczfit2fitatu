# 🥗 Maczfit Meals

Nieoficjalny skrypt do pobierania informacji o posiłkach i wartościach odżywczych z Twojego konta [Maczfit](https://www.maczfit.pl/).

An unofficial script to fetch meal and nutritional information from your [Maczfit](https://www.maczfit.pl/) catering account.

---

## 🇵🇱 Polski

### Co robi ten skrypt?

Loguje się na Twoje konto Maczfit i pobiera szczegóły posiłków na wybrany dzień:

- **Nazwy dań** dla każdego z 5 posiłków (śniadanie → kolacja)
- **Kalorie** (kcal) na posiłek i sumę dzienną
- **Szacunkowe makroskładniki** (białko, tłuszcze, węglowodany) — obliczane na podstawie proporcji makro dla danego typu diety
- **Alergeny**
- **Skład** z procentowym udziałem składników

### Szybki start

```bash
git clone https://github.com/<your-username>/maczfit.git
cd maczfit
```

Utwórz plik `config.json` z danymi logowania:

```json
{
  "email": "twoj-email@example.com",
  "password": "twoje-haslo"
}
```

Uruchom skrypt:

```bash
# Posiłki na dziś
./run.sh

# Posiłki na konkretny dzień
./run.sh 2026-04-09
```

Przy pierwszym uruchomieniu `run.sh` automatycznie utworzy środowisko wirtualne Pythona i zainstaluje zależności.

### Przykładowy wynik

```
================================================================
  2026-04-09  |  FIT 2500 Diety z Wyborem Dań (2500 kcal)
  Macro split: F 35% / C 45% / P 20%  (estimated)
================================================================

  [Śniadanie]  Truskawkowa muffinka z migdałami i serek waniliowy
    584 kcal  |  F: 22.7g  |  C: 65.7g  |  P: 29.2g
    Alergeny: Gluten, Jaja, Mleko, Orzechy

  [Obiad]  Makaron udon z sezamem i tofu z papryką i marchewką
    744 kcal  |  F: 28.9g  |  C: 83.7g  |  P: 37.2g
    ...

----------------------------------------------------------------
  TOTAL: 2679 kcal  |  F: 104.2g  |  C: 301.4g  |  P: 134.0g
================================================================
```

### Uwagi

- Makroskładniki (B/T/W) są **szacunkowe** — API Maczfit nie udostępnia rozbicia na makro per danie, więc skrypt stosuje proporcje makro zdefiniowane dla danego typu diety (np. FIT = 35% T / 45% W / 20% B)
- Kalorie (`KcalSum`) per posiłek są **dokładne** — pochodzą bezpośrednio z API
- Plik `config.json` zawiera Twoje hasło w postaci jawnej — ogranicz uprawnienia: `chmod 600 config.json`
- Skrypt korzysta z nieoficjalnego API — może przestać działać po zmianach na stronie Maczfit

---

## 🇬🇧 English

### What does this script do?

Logs into your Maczfit account and fetches meal details for a given day:

- **Dish names** for all 5 meals (breakfast → supper)
- **Calories** (kcal) per meal and daily total
- **Estimated macros** (protein, fat, carbs) — calculated from the diet type's macro ratio
- **Allergens**
- **Ingredients** with percentage breakdown

### Quick start

```bash
git clone https://github.com/<your-username>/maczfit.git
cd maczfit
```

Create a `config.json` file with your credentials:

```json
{
  "email": "your-email@example.com",
  "password": "your-password"
}
```

Run the script:

```bash
# Today's meals
./run.sh

# Meals for a specific date
./run.sh 2026-04-09
```

On first run, `run.sh` automatically creates a Python virtual environment and installs dependencies.

### Notes

- Macros (P/F/C) are **estimated** — the Maczfit API does not provide per-dish macro breakdown, so the script applies the macro ratio defined for the diet type (e.g., FIT = 35% F / 45% C / 20% P)
- Calories (`KcalSum`) per meal are **exact** — sourced directly from the API
- `config.json` stores your password in plain text — restrict permissions: `chmod 600 config.json`
- This script uses an unofficial API — it may break if Maczfit changes their website

---

## Supported diet types / Obsługiwane typy diet

| Diet | Fat % | Carbs % | Protein % |
|------|-------|---------|-----------|
| FIT / Slim / Comfort | 35 | 45 | 20 |
| Vege | 35 | 47 | 18 |
| Diabetic & Low Sugar | 35 | 42 | 23 |
| Wegan | 35 | 50 | 15 |
| Hypo Hashimoto | 35 | 43 | 22 |
| No Lactose & Low Gluten | 35 | 45 | 20 |
| Vege & Fish | 35 | 45 | 20 |
| FODMAP | 35 | 45 | 20 |
| Keto IF | 75 | 5 | 20 |

## Requirements / Wymagania

- Python 3.8+
- Active Maczfit account with a current diet order

## License / Licencja

MIT
