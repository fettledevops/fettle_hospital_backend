#!/bin/sh
set -e

echo ">>> Running database migrations..."
python manage.py migrate --noinput

# Collect static files in production (DEBUG=False)
if [ "$DEBUG" = "False" ] || [ "$DEBUG" = "false" ]; then
  echo ">>> Collecting static files..."
  python manage.py collectstatic --noinput --clear
fi

echo ">>> Starting application..."
exec "$@"
