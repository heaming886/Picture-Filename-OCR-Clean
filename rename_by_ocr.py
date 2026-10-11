#!/usr/bin/env python3
"""Rename images using text recognized from the upper part of each image.

Install (Windows): use 64-bit Python 3.12, then run
          py -3.12 -m pip install rapidocr-onnxruntime pillow
Preview:  python rename_by_ocr.py "C:\\path\\to\\images"
Rename:   python rename_by_ocr.py "C:\\path\\to\\images" --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")


def clean_filename(text: str, max_length: int = 100) -> str:
    """Convert OCR text to a portable, readable filename stem."""
    text = unicodedata.normalize("NFKC", text)
    text = INVALID_FILENAME_CHARS.sub(" ", text)
    text = WHITESPACE.sub(" ", text).strip(" .\t\n\r")
    # Windows reserves these names even when an extension is added.
    if text.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        text = f"_{text}"
    return text[:max_length].rstrip(" .")


def extract_text(image_path: Path, top_ratio: float) -> str:
    """Recognize text in the top portion with RapidOCR."""
    try:
        from PIL import Image
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "缺少 OCR 套件。Windows 建議使用 64 位元 Python 3.12，並執行："
            "py -3.12 -m pip install rapidocr-onnxruntime pillow"
        ) from exc

    # Keep one OCR engine for the whole run.
    if not hasattr(extract_text, "engine"):
        extract_text.engine = RapidOCR()  # type: ignore[attr-defined]

    with Image.open(image_path) as image:
        image = image.convert("RGB")
        crop = image.crop((0, 0, image.width, max(1, int(image.height * top_ratio))))
        # Upscale small crops to improve recognition of small lettering.
        if crop.width < 1000:
            scale = min(2.0, 1000 / crop.width)
            crop = crop.resize((int(crop.width * scale), int(crop.height * scale)))
        import numpy as np

        results, _ = extract_text.engine(np.asarray(crop))  # type: ignore[attr-defined]

    if not results:
        return ""
    # RapidOCR returns boxes in reading order in most cases; sort explicitly by
    # vertical then horizontal position for predictable filenames.
    results = sorted(results, key=lambda item: (min(p[1] for p in item[0]), min(p[0] for p in item[0])))
    return " ".join(str(item[1]).strip() for item in results if str(item[1]).strip())


def unique_destination(directory: Path, stem: str, suffix: str, reserved: set[str], source: Path) -> Path:
    candidate_stem = stem
    number = 2
    while True:
        candidate = directory / f"{candidate_stem}{suffix}"
        key = candidate.name.casefold()
        if key not in reserved and (not candidate.exists() or candidate.resolve() == source.resolve()):
            reserved.add(key)
            return candidate
        candidate_stem = f"{stem} ({number})"
        number += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="辨識圖片上半部文字，並用辨識結果作為檔名（預設只預覽）。"
    )
    parser.add_argument("directory", nargs="?", default=".", help="圖片目錄，預設為目前目錄")
    parser.add_argument("--apply", action="store_true", help="實際執行改名；未指定時只預覽")
    parser.add_argument("--recursive", action="store_true", help="也處理子目錄")
    parser.add_argument("--top", type=float, default=0.5, help="辨識圖片上方比例，預設 0.5")
    parser.add_argument("--min-chars", type=int, default=2, help="至少需要的文字字元數，預設 2")
    parser.add_argument("--prefix", default="未辨識", help="無可用文字時的檔名，預設 未辨識")
    args = parser.parse_args()

    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        parser.error(f"找不到目錄：{directory}")
    if not 0 < args.top <= 1:
        parser.error("--top 必須大於 0 且不超過 1")
    if args.min_chars < 1:
        parser.error("--min-chars 必須至少為 1")

    images = sorted(
        (p for p in (directory.rglob("*") if args.recursive else directory.iterdir())
         if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: str(p).casefold(),
    )
    if not images:
        print(f"此目錄沒有支援的圖片：{directory}")
        return 0

    reserved: set[str] = set()
    changes: list[tuple[Path, Path]] = []
    for image in images:
        try:
            recognized = extract_text(image, args.top)
            stem = clean_filename(recognized)
            if len(stem) < args.min_chars:
                stem = clean_filename(args.prefix)
            destination = unique_destination(image.parent, stem, image.suffix, reserved, image)
            changes.append((image, destination))
            print(f"{image.name}  ->  {destination.name}")
        except Exception as exc:
            print(f"略過 {image.name}：{exc}", file=sys.stderr)

    if not args.apply:
        print(f"\n預覽完成：{len(changes)} 張。確認結果後加上 --apply 即可改名。")
        return 0

    renamed = 0
    for source, destination in changes:
        try:
            source.rename(destination)
            renamed += 1
        except OSError as exc:
            print(f"改名失敗 {source.name}：{exc}", file=sys.stderr)
    print(f"\n改名完成：{renamed}/{len(changes)} 張。")
    return 0 if renamed == len(changes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
