#!/bin/bash
# Maktab CRM ni ishga tushirish
set -e
cd "$(dirname "$0")"

./venv/bin/python manage.py migrate
echo "=========================================="
echo "  Maktab CRM ishga tushdi!"
echo "  Sayt:        http://127.0.0.1:8000"
echo "  Admin panel: http://127.0.0.1:8000/admin"
echo "------------------------------------------"
echo "  Demo ma'lumot uchun: ./venv/bin/python manage.py seed_demo"
echo "  Admin:      admin / admin123"
echo "  O'qituvchi: teacher1 / teacher123"
echo "  O'quvchi:   student1 / student123"
echo "  Ota-ona:    parent1 / parent123"
echo "  To'xtatish: Ctrl+C"
echo "=========================================="
./venv/bin/python manage.py runserver 0.0.0.0:8000
