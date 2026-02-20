# imghdr compatibility shim for Python 3.13+
# This module was removed but Kivy 2.3.0 still uses it

import struct

def what(file, h=None):
    if h is None:
        if isinstance(file, str):
            with open(file, 'rb') as f:
                h = f.read(32)
        else:
            location = file.tell()
            h = file.read(32)
            file.seek(location)
    
    if h[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if h[:3] == b'GIF': return 'gif'
    if h[:2] in (b'MM', b'II'): return 'tiff'
    if h[:2] == b'\xff\xd8': return 'jpeg'
    if h[:4] == b'RIFF' and h[8:12] == b'WEBP': return 'webp'
    if h[:2] == b'BM': return 'bmp'
    return None
