#!/usr/bin/env python3
"""Clean image filenames, remove selected words, and split concatenated English.

Examples:
  .venv\\Scripts\\python.exe clean-word.py . --remove Taiz Telecom Academy
  .venv\\Scripts\\python.exe clean-word.py . --remove Academy --apply
  .venv\\Scripts\\python.exe clean-word.py . --remove-file remove-words.txt --recursive --apply

Preview is the default. Add --apply to rename files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import wordninja
except ImportError:
    wordninja = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
CAMEL_BOUNDARIES = re.compile(r"(?<=[a-z])(?=[A-Z])")
LETTERS = re.compile(r"[A-Za-z]+")
SPACE = re.compile(r"\s+")
PUNCTUATION_SPACES = re.compile(r"\s+([,.;:!?])")
TECHNICAL_TERMS = sorted({
    "5G", "4G", "3G", "2G", "6G", "5GNR", "4GLTE", "3GPP", "gNodeB", "eNodeB",
    "VoLTE", "VoNR", "NMS", "EMS", "IMS", "SIP", "RAN", "RRC", "LTE", "NR",
    "GSM", "UMTS", "OTN", "DWDM", "CWDM", "MPLS", "CPRI", "RRU", "AAU", "MIMO",
    "SISO", "KPI", "KPIs", "RSRP", "RSRQ", "RSSI", "SINR", "CQI", "PCI", "PRB",
    "PRBs", "SUL", "OTDR", "GPON", "XG-PON", "FTTH", "PON", "OLT", "ONT", "RET",
    "RACH", "PRACH", "HARQ", "RTT", "BTS", "BSC", "MSC", "HSS", "EPC", "PGW",
    "SGW", "MME", "AMF", "SMF", "UPF", "NRF", "UDM", "AUSF", "PCF", "UE", "IP",
    "TCP", "UDP", "DNS", "RF", "TDD", "FDD", "VoIP", "WiFi", "WiFi6", "WiFi7",
}, key=len, reverse=True)
TECHNICAL_TERMS_RE = re.compile(r"5GC(?![a-z]+[A-Z])|" + "|".join(map(re.escape, TECHNICAL_TERMS)))


def segment_run(run: str) -> str:
    """Split long English letter runs while preserving simple capitalization."""
    if wordninja is None or len(run) < 6:
        return run
    parts = wordninja.split(run.lower())
    if len(parts) < 2:
        return run
    if run.isupper():
        return " ".join(part.upper() for part in parts)
    if run.islower():
        return " ".join(parts)
    if run.istitle():
        return " ".join(part.capitalize() for part in parts)
    # Camel/acronym transitions are separated before this point. For unusual
    # mixed-case OCR runs, keep the text readable and avoid inventing capitals.
    return " ".join(parts)


def segment_english(text: str) -> str:
    text = TECHNICAL_TERMS_RE.sub(lambda match: f" {match.group(0)} ", text)
    text = CAMEL_BOUNDARIES.sub(" ", text)
    return LETTERS.sub(lambda match: segment_run(match.group(0)), text)


def remove_phrases(text: str, phrases: list[str]) -> str:
    for phrase in sorted((p.strip() for p in phrases if p.strip()), key=len, reverse=True):
        words = re.split(r"\s+", phrase)
        pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(map(re.escape, words)) + r"(?![A-Za-z0-9])"
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def clean_stem(stem: str, remove_words: list[str], max_length: int) -> str:
    stem = segment_english(stem)
    stem = remove_phrases(stem, remove_words)
    stem = INVALID_FILENAME_CHARS.sub(" ", stem)
    stem = SPACE.sub(" ", stem)
    stem = PUNCTUATION_SPACES.sub(r"\1", stem)
    return stem.strip(" .-_\t")[:max_length].rstrip(" .-_\t")


def find_destination(source: Path, stem: str, reserved: set[str]) -> Path | None:
    if not stem:
        return None
    base = stem
    index = 2
    while True:
        destination = source.with_name(f"{stem}{source.suffix}")
        key = destination.name.casefold()
        if key not in reserved and (not destination.exists() or destination.resolve() == source.resolve()):
            reserved.add(key)
            return destination
        stem = f"{base} ({index})"
        index += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="清理圖片檔名、移除指定詞，並拆開黏在一起的英文字（預設只預覽）。"
    )
    parser.add_argument("directory", nargs="?", default=".", help="圖片目錄，預設為目前目錄")
    parser.add_argument("-r", "--remove", action="append", nargs="+", default=[], metavar="WORD",
                        help="要移除的完整單字或詞組；可在一個 --remove 後列出多個")
    parser.add_argument("--remove-file", type=Path, help="每行一個要移除的單字或詞組")
    parser.add_argument("--recursive", action="store_true", help="包含子目錄")
    parser.add_argument("--apply", action="store_true", help="實際改名；未指定時只預覽")
    parser.add_argument("--max-length", type=int, default=100, help="檔名主體最大字元數，預設 100")
    args = parser.parse_args()

    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        parser.error(f"找不到目錄：{directory}")
    if args.max_length < 1:
        parser.error("--max-length 必須至少為 1")
    if wordninja is None:
        parser.error("缺少 wordninja，請在專案環境安裝：.venv\\Scripts\\python.exe -m pip install wordninja")

    remove_words = [word for group in args.remove for word in group]
    if args.remove_file:
        try:
            remove_words.extend(
                line.strip() for line in args.remove_file.read_text(encoding="utf-8-sig").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )
        except OSError as exc:
            parser.error(f"無法讀取移除詞清單：{exc}")

    files = sorted(
        (p for p in (directory.rglob("*") if args.recursive else directory.iterdir())
         if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: str(p).casefold(),
    )
    if not files:
        print(f"此目錄沒有支援的圖片：{directory}")
        return 0

    reserved: set[str] = set()
    changes: list[tuple[Path, Path]] = []
    skipped = 0
    for source in files:
        stem = clean_stem(source.stem, remove_words, args.max_length)
        destination = find_destination(source, stem, reserved)
        if destination is None:
            print(f"略過（清理後沒有檔名）：{source.name}")
            skipped += 1
        elif destination.name != source.name:
            changes.append((source, destination))
            print(f"{source.name}  ->  {destination.name}")

    if not args.apply:
        print(f"\n預覽完成：預計改名 {len(changes)} 張，略過 {skipped} 張。確認後加上 --apply。")
        return 0

    renamed = 0
    for source, destination in changes:
        try:
            source.rename(destination)
            renamed += 1
        except OSError as exc:
            print(f"改名失敗 {source.name}：{exc}", file=sys.stderr)
    print(f"\n改名完成：{renamed}/{len(changes)} 張；略過 {skipped} 張。")
    return 0 if renamed == len(changes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
