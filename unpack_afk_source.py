from pathlib import Path
import base64, gzip
src = Path("afk_screen_source.py.gz.b64")
out = Path("afk_screen.py")
out.write_bytes(gzip.decompress(base64.b64decode(src.read_text().strip())))
print(f"wrote {out} ({out.stat().st_size} bytes)")
