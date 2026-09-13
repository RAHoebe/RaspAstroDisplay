"""Install a transparent Xcursor theme for a dedicated touchscreen kiosk."""
from pathlib import Path
import struct


def install_theme(home=None):
    home = Path(home) if home else Path.home()
    folder = home / '.icons/AstroInvisible'
    (folder / 'cursors').mkdir(parents=True, exist_ok=True)
    (folder / 'index.theme').write_text('[Icon Theme]\nName=AstroInvisible\nComment=Touchscreen kiosk cursor\n')
    # Xcursor file header, one image table entry, then a transparent 24x24 ARGB image.
    image_type = 0xfffd0002
    data = struct.pack('<7I', 0x72756358, 16, 0x10000, 1, image_type, 24, 28)
    data += struct.pack('<9I', 36, image_type, 24, 1, 24, 24, 0, 0, 0) + bytes(24*24*4)
    for name in ('default','left_ptr','arrow','top_left_arrow','pointer','hand1','hand2','text','xterm',
                 'crosshair','cross','watch','wait','progress','left_ptr_watch','not-allowed'):
        (folder / 'cursors' / name).write_bytes(data)
    return 'AstroInvisible'


if __name__ == '__main__':
    print(install_theme())
