#!/bin/sh
set -e

echo ">>> Running database migrations..."
python manage.py migrate --noinput

# Collect static files in production (DEBUG=False)
DEBUG_NORMALIZED=$(printf '%s' "$DEBUG" | tr '[:upper:]' '[:lower:]')
if [ "$DEBUG_NORMALIZED" != "true" ]; then
  echo ">>> Collecting static files..."
  python manage.py collectstatic --noinput --clear
fi

echo ">>> Starting application..."
exec "$@"
