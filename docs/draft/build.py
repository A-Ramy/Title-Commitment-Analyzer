"""Builds docs/draft/index.html from index.template.html with the brand logos inlined (one self-contained file).

    python3 docs/draft/build.py
"""

import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent.parent / "assets"
LOGOS = {"__LOGO_LIGHT__": "logo-full.png", "__LOGO_DARK__": "logo-full-white.png", "__LOGO_MARK__": "logo-mark.png"}

html = (HERE / "index.template.html").read_text(encoding="utf-8")
for key, name in LOGOS.items():
    html = html.replace(key, base64.b64encode((ASSETS / name).read_bytes()).decode())
(HERE / "index.html").write_text(html, encoding="utf-8")
