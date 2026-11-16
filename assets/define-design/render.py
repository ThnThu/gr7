#!/usr/bin/env python3
"""Render các sơ đồ Mermaid trong thư mục này: .mmd → .svg → .png.

Xử lý hai lỗi thường gặp khi dùng Kroki + rsvg-convert:

1. Nhãn bị mất chữ hoàn toàn: Mermaid mặc định vẽ nhãn bằng ``<foreignObject>``
   (HTML) và ``rsvg-convert`` bỏ qua thẻ này. Mỗi khối ``.mmd`` đã có dòng
   ``%%{init: {"htmlLabels": false}}%%`` để nhãn thành ``<text>`` thật.
2. Chữ dính nhau ("Ngườidùng"): ``rsvg-convert`` bỏ dấu cách ở đầu mỗi
   ``<tspan>``. Script thêm ``xml:space="preserve"`` vào mọi thẻ ``<text>``
   trước khi ghi SVG.

Cách dùng::

    python3 assets/define-design/render.py            # tất cả .mmd
    python3 assets/define-design/render.py 04_...mmd  # một tệp

Yêu cầu: mạng tới kroki.io và ``rsvg-convert`` (gói librsvg2-bin).
"""

import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ENDPOINT = "https://kroki.io/mermaid/svg"
PNG_WIDTH = 2200


def fetch_svg(source: str, retries: int = 3) -> str:
    data = source.encode("utf-8")
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                ENDPOINT,
                data=data,
                headers={
                    "Content-Type": "text/plain",
                    # Kroki/Cloudflare chặn User-Agent mặc định của urllib (403).
                    "User-Agent": "curl/8.5.0",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                svg = resp.read().decode("utf-8")
            if svg.lstrip().startswith("<svg"):
                return svg
            last = RuntimeError("Kroki không trả về SVG")
        except Exception as exc:  # noqa: BLE001 - cần thử lại mọi lỗi mạng
            last = exc
        if attempt < retries:
            time.sleep(2 * attempt)
    raise RuntimeError(f"Không tải được SVG sau {retries} lần: {last}")


def preserve_spaces(svg: str) -> str:
    """Thêm xml:space='preserve' để rsvg-convert giữ dấu cách giữa các tspan."""

    def patch(match: re.Match) -> str:
        tag = match.group(0)
        if "xml:space" in tag:
            return tag
        return tag[:-1] + ' xml:space="preserve">'

    return re.sub(r"<text\b[^>]*>", patch, svg)


def check(svg: str) -> tuple[int, int]:
    foreign = svg.count("<foreignObject")
    texts = len(re.findall(r"<text\b", svg))
    return foreign, texts


def main(argv: list[str]) -> int:
    base = Path(__file__).resolve().parent
    targets = [Path(a) for a in argv[1:]] or sorted(base.glob("*.mmd"))
    failed = 0
    for mmd in targets:
        mmd = mmd if mmd.is_absolute() else base / mmd
        if not mmd.exists():
            print(f"Bỏ qua (không có tệp): {mmd.name}")
            failed += 1
            continue
        print(f"== {mmd.name} ==")
        svg_text = preserve_spaces(fetch_svg(mmd.read_text(encoding="utf-8")))
        foreign, texts = check(svg_text)
        if foreign or not texts:
            print(f"  LỖI: foreignObject={foreign}, text={texts}")
            failed += 1
            continue
        svg_path = mmd.with_suffix(".svg")
        png_path = mmd.with_suffix(".png")
        svg_path.write_text(svg_text, encoding="utf-8")
        subprocess.run(
            ["rsvg-convert", "-w", str(PNG_WIDTH), str(svg_path), "-o", str(png_path)],
            check=True,
        )
        size = subprocess.run(
            ["identify", "-format", "%wx%h", str(png_path)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        print(f"  OK: text={texts}, png={size}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
