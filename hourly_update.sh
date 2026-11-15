#!/usr/bin/env bash

set -e

REPO_DIR="/home/joaompessoa/karma_track"
PYTHON_EXEC="$REPO_DIR/.venv/bin/python"

echo "Updating repo from $REPO_DIR with Python executable: $PYTHON_EXEC"

cd "$REPO_DIR"

if [[ ! -x "$PYTHON_EXEC" ]]; then
    echo "Missing uv environment. Run: uv sync --locked --no-dev --managed-python" >&2
    exit 1
fi

"$PYTHON_EXEC" entry.py freeze

git add .

if ! git diff-index --quiet HEAD --; then
    COMMIT_MSG="Auto-update: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Committing changes: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
    echo "Pushing changes..."
    git push
else
    echo "No changes to commit."
fi

echo "Script finished."
