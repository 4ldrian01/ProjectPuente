"""Create a secure Django superuser and print credentials.

Usage:
  & 'C:/Users/User''s/ALL FILES - MACHINE LEARNING/ProjectPuente/.venv/Scripts/python.exe' 'C:/Users/User''s/ALL FILES - MACHINE LEARNING/ProjectPuente/backend/scripts/create_superuser.py'

This script does NOT write the password to disk; it only prints it to stdout.
"""
import os
import sys
import secrets
import random
import string

# Ensure backend folder is on path so Django settings can be imported
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()


def gen_username():
    return 'puente_admin_' + secrets.token_hex(4)


def gen_password(length=24):
    # Alphabet with punctuation for strong password
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        # ensure at least one of each required category
        pwd_chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*()-_=+"),
        ]
        pwd_chars += [secrets.choice(alphabet) for _ in range(length - len(pwd_chars))]
        random.SystemRandom().shuffle(pwd_chars)
        pwd = ''.join(pwd_chars)
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*()-_=+" for c in pwd)):
            return pwd


# pick a unique username (try a few times)
for _ in range(6):
    username = gen_username()
    if not User.objects.filter(username=username).exists():
        break
else:
    # fallback to a longer username
    username = 'puente_admin_' + secrets.token_hex(8)

email = f'{username}@local'
password = gen_password(24)

# Create superuser
user = User.objects.create_superuser(username=username, email=email, password=password)

# Print credentials in a parseable form
print('SUPERUSER_CREATED')
print(f'USERNAME:{username}')
print(f'EMAIL:{email}')
print(f'PASSWORD:{password}')
print('NOTE: Please store this password in a secure password manager and change it after first login.')
