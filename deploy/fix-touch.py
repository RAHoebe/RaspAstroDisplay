"""Bind the detected touchscreen without changing the existing display rotation."""
from display import main

if __name__ == '__main__':
    raise SystemExit(main(['touch-only']))
