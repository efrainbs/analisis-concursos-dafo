#!/bin/bash
# Launches the Flask DAFO Explorer (server.py) with FTS5 search.
# Streamlit app.py is deprecated; server.py is the active web app.
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo "Creando virtualenv en $VENV..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -r "$DIR/requirements.txt"
fi
exec "$VENV/bin/python3" "$DIR/server.py" "$@"
