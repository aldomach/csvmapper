"""
csv_loader.py - Reads CSV or plain-text files into a list-of-dicts structure.
"""
import csv
import chardet
from pathlib import Path


def detect_encoding(filepath: str) -> str:
    with open(filepath, "rb") as f:
        raw = f.read(50_000)
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def load_file(filepath: str) -> tuple[list[str], list[list[str]]]:
    """
    Returns (headers, rows).
    headers: list of column names
    rows:    list of rows (each row = list of str values)

    Supports CSV and plain .txt (treated as single-column).
    """
    path = Path(filepath)
    encoding = detect_encoding(filepath)
    suffix = path.suffix.lower()

    if suffix in (".csv", ".tsv"):
        delimiter = "\t" if suffix == ".tsv" else ","
        with open(filepath, newline="", encoding=encoding, errors="replace") as f:
            # Sniff delimiter for .csv
            if suffix == ".csv":
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                    delimiter = dialect.delimiter
                except csv.Error:
                    delimiter = ","
            reader = csv.reader(f, delimiter=delimiter)
            all_rows = list(reader)

        if not all_rows:
            return [], []

        headers = all_rows[0]
        rows = all_rows[1:]
        # Normalise row lengths
        n = len(headers)
        rows = [(r + [""] * n)[:n] for r in rows]
        return headers, rows

    else:  # Plain text – one line per row, single column "Line"
        with open(filepath, encoding=encoding, errors="replace") as f:
            lines = [line.rstrip("\n") for line in f]
        headers = ["Line"]
        rows = [[line] for line in lines]
        return headers, rows


def save_csv(filepath: str, headers: list[str], rows: list[list[str]]):
    """Write headers + rows to a CSV file (UTF-8 with BOM for Excel compat)."""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
