#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

VENV=".venv"

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet -r requirements.txt
    echo "Setup complete."
fi

SCRIPT="${1:-}"
shift 2>/dev/null || true

case "$SCRIPT" in
    sync)  exec "$VENV/bin/python" fitatu_sync.py "$@" ;;
    meals) exec "$VENV/bin/python" maczfit_meals.py "$@" ;;
    *)
        echo "Usage: ./run.sh <command> [date]"
        echo ""
        echo "Commands:"
        echo "  meals [YYYY-MM-DD]  Show Maczfit meals for a date"
        echo "  sync  [YYYY-MM-DD]  Sync Maczfit meals → Fitatu planner"
        echo ""
        echo "Examples:"
        echo "  ./run.sh meals              # today's meals"
        echo "  ./run.sh meals 2026-04-09   # specific date"
        echo "  ./run.sh sync               # sync today to Fitatu"
        echo "  ./run.sh sync 2026-04-09    # sync specific date"
        exit 1
        ;;
esac
