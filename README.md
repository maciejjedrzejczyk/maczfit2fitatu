# 🥗 Maczfit Meals + Fitatu Sync

Unofficial tools to fetch meals from [Maczfit](https://www.maczfit.pl/) and sync them to [Fitatu](https://www.fitatu.com/) meal planner.

Nieoficjalne narzędzia do pobierania posiłków z Maczfit i synchronizacji ich z Fitatu.

---

## What does this project do?

Three commands, one goal — get your Maczfit diet data into Fitatu with accurate per-dish macros:

| Command | Description |
|---------|-------------|
| `meals` | Show today's meals with real calories, macros (F/C/P), allergens, and ingredients |
| `sync`  | Interactive CLI — pick which meals to push into Fitatu planner |
| `ui`    | Web UI with drag-and-drop — visually manage Maczfit → Fitatu sync |

Calories and macros are **accurate per dish** — fetched from the Maczfit Nutrient API, not estimated from diet ratios.

---

## Quick start

```bash
git clone https://github.com/<your-username>/maczfit.git
cd maczfit
cp config.json.example config.json
chmod 600 config.json
```

Edit `config.json`:

```json
{
  "maczfit_email": "your-maczfit-email@example.com",
  "maczfit_password": "your-maczfit-password",
  "fitatu_email": "your-fitatu-email@example.com",
  "fitatu_password": "your-fitatu-password"
}
```

The first run creates a virtualenv and installs dependencies automatically.

---

## Usage

### Show meals (CLI)

```bash
./run.sh meals              # today
./run.sh meals 2026-04-13   # specific date
```

Outputs dish names, kcal, fat/carbs/protein, allergens, and composition for each meal.

### Sync to Fitatu (CLI)

```bash
./run.sh sync               # today
./run.sh sync 2026-04-13    # specific date
```

Shows a numbered list of meals, lets you pick which to sync (e.g. `1,3,5` or `A` for all), then pushes them to Fitatu as Custom Items in the correct meal slots.

### Web UI

```bash
./run.sh ui
```

Opens a local web server at **http://localhost:5555** with a drag-and-drop interface:

- Left panel: Maczfit meals for the selected date
- Right panel: Fitatu planner slots (breakfast, second breakfast, lunch, snack, dinner, supper)
- Drag meals from Maczfit into Fitatu slots
- Edit, move, or delete items directly in the Fitatu panel
- Date picker to switch between days

---

## Meal slot mapping

| Maczfit | Fitatu slot |
|---------|-------------|
| Śniadanie | `breakfast` |
| II Śniadanie | `second_breakfast` |
| Obiad | `lunch` |
| Podwieczorek | `snack` |
| Kolacja | `dinner` |

---

## Notes

- Macros are fetched per dish from the Maczfit Nutrient Stats API — not estimated
- Meals appear in Fitatu as "Custom Items"
- `config.json` contains plaintext passwords — restrict permissions with `chmod 600`
- Both APIs are unofficial and may break if the services change
- Fitatu credentials are only needed for `sync` and `ui` commands

## Requirements

- Python 3.8+
- Active Maczfit account with a current diet order
- Fitatu account (for sync/ui)

## License

MIT
