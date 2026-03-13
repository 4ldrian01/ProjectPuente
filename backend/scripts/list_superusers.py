"""List Django superusers and basic info (no passwords).

Run with: "C:/Users/User's/ALL FILES - MACHINE LEARNING/ProjectPuente/.venv/Scripts/python.exe" scripts\\list_superusers.py
"""
import os
import sys

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

supers = list(User.objects.filter(is_superuser=True).values('username', 'email', 'is_active', 'date_joined'))
if not supers:
    print('NO_SUPERUSERS_FOUND')
else:
    for u in supers:
        print(f"USERNAME: {u['username']}, EMAIL: {u['email']}, ACTIVE: {u['is_active']}, JOINED: {u['date_joined']}")
