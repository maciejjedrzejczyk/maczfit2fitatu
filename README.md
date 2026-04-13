# 🥗 Maczfit Meals + Fitatu Sync

Nieoficjalne narzędzia do pobierania posiłków z [Maczfit](https://www.maczfit.pl/) i synchronizacji ich z [Fitatu](https://www.fitatu.com/).

Unofficial tools to fetch meals from [Maczfit](https://www.maczfit.pl/) and sync them to [Fitatu](https://www.fitatu.com/) meal planner.

---

## 🇵🇱 Polski

### Co robi ten projekt?

1. **`meals`** — Loguje się na konto Maczfit i wyświetla posiłki na wybrany dzień (nazwy dań, kalorie, szacunkowe makro, alergeny, skład)
2. **`sync`** — Pobiera posiłki z Maczfit, pozwala wybrać które zsynchronizować, a następnie wstawia je do planera Fitatu

### Szybki start

```bash
git clone https://github.com/<your-username>/maczfit.git
cd maczfit
cp config.json.example config.json
chmod 600 config.json
```

Edytuj `config.json`:

```json
{
  "maczfit_email": "twoj-email@example.com",
  "maczfit_password": "twoje-haslo",
  "fitatu_email": "twoj-fitatu@example.com",
  "fitatu_password": "twoje-fitatu-haslo"
}
```

Użycie:

```bash
# Pokaż posiłki Maczfit na dziś
./run.sh meals

# Pokaż posiłki na konkretny dzień
./run.sh meals 2026-04-09

# Synchronizuj posiłki Maczfit → Fitatu
./run.sh sync

# Synchronizuj konkretny dzień
./run.sh sync 2026-04-09
```

### Przykład synchronizacji

```
==================================================
  Maczfit → Fitatu Sync  |  2026-04-09
==================================================

[Maczfit] Logging in...
Logged in. (userId=295623)

Maczfit meals for 2026-04-09:

  [1] Śniadanie: Truskawkowa muffinka z migdałami
      584 kcal | F: 22.7g | C: 65.7g | P: 29.2g
  [2] II Śniadanie: Baton kajmakowy z płatków
      380 kcal | F: 14.8g | C: 42.7g | P: 19.0g
  [3] Obiad: Makaron udon z sezamem i tofu
      744 kcal | F: 28.9g | C: 83.7g | P: 37.2g
  [4] Podwieczorek: Zupa curry z dynią
      301 kcal | F: 11.7g | C: 33.9g | P: 15.1g
  [5] Kolacja: Zupa krem z ogórka kiszonego
      670 kcal | F: 26.1g | C: 75.4g | P: 33.5g

  [A] All meals

Select meals to sync (e.g. 1,3,5 or A for all): A

[Fitatu] Logging in...
[Fitatu] Logged in (userId=abc123)
[Fitatu] Fetching planner for 2026-04-09...
  + [Śniadanie] Truskawkowa muffinka → breakfast
  + [II Śniadanie] Baton kajmakowy → second_breakfast
  + [Obiad] Makaron udon → lunch
  + [Podwieczorek] Zupa curry → snack
  + [Kolacja] Zupa krem → dinner

[Fitatu] Saving 5 item(s)...
[Fitatu] Done! Check your Fitatu planner.
```

### Uwagi

- Makroskładniki (B/T/W) są **szacunkowe** — API Maczfit nie udostępnia rozbicia per danie
- Kalorie per posiłek są **dokładne** z API Maczfit
- Posiłki trafiają do Fitatu jako "Custom Items"
- `config.json` zawiera hasła w postaci jawnej — ogranicz uprawnienia: `chmod 600 config.json`
- Oba skrypty korzystają z nieoficjalnych API

---

## 🇬🇧 English

### What does this project do?

1. **`meals`** — Logs into Maczfit and displays meals for a given day (dish names, calories, estimated macros, allergens, ingredients)
2. **`sync`** — Fetches meals from Maczfit, lets you pick which ones to sync, then inserts them into Fitatu planner

### Quick start

```bash
git clone https://github.com/<your-username>/maczfit.git
cd maczfit
cp config.json.example config.json
chmod 600 config.json
```

Edit `config.json` with your credentials, then:

```bash
# Show today's Maczfit meals
./run.sh meals

# Sync Maczfit meals → Fitatu planner
./run.sh sync

# Specific date
./run.sh sync 2026-04-09
```

### Notes

- Macros are **estimated** from the diet type ratio (Maczfit API only provides per-meal kcal)
- Meals are inserted into Fitatu as "Custom Items"
- Both scripts use unofficial APIs — may break if the services change

---

## Meal slot mapping / Mapowanie posiłków

| Maczfit | Fitatu slot |
|---------|-------------|
| Śniadanie | `breakfast` |
| II Śniadanie | `second_breakfast` |
| Obiad | `lunch` |
| Podwieczorek | `snack` |
| Kolacja | `dinner` |

## Diet macro ratios / Proporcje makro

| Diet | Fat % | Carbs % | Protein % |
|------|-------|---------|-----------|
| FIT / Slim / Comfort | 35 | 45 | 20 |
| Vege | 35 | 47 | 18 |
| Diabetic | 35 | 42 | 23 |
| Wegan | 35 | 50 | 15 |
| Hypo Hashimoto | 35 | 43 | 22 |
| Keto IF | 75 | 5 | 20 |

## Requirements / Wymagania

- Python 3.8+
- Active Maczfit account with a current diet order
- Fitatu account (for sync feature)

## License / Licencja

MIT
