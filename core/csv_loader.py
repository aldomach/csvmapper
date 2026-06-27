"""
core/csv_loader.py — Lectura y escritura de archivos CSV/TSV/TXT.
Escalabilidad: límite configurable de filas, escritura por chunks.
"""
import csv
from pathlib import Path

import chardet

MAX_ROWS = 200_000


# ── Encoding ──────────────────────────────────────────────────────────────────

def detect_encoding(filepath: str) -> str:
    with open(filepath, "rb") as f:
        raw = f.read(100_000)
    for bom, enc in [
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe",     "utf-16-le"),
        (b"\xfe\xff",     "utf-16-be"),
    ]:
        if raw.startswith(bom):
            return enc
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


# ── Detección de delimitador ──────────────────────────────────────────────────

def detect_delimiter(filepath: str, encoding: str) -> str:
    with open(filepath, encoding=encoding, errors="replace") as f:
        sample = f.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        pass
    # Fallback: contar ocurrencias con penalización por inconsistencia
    candidates = [",", ";", "\t", "|"]
    lines = [l for l in sample.splitlines() if l.strip()][:20]
    best, best_score = ",", -1
    for d in candidates:
        counts = [l.count(d) for l in lines]
        if not counts or max(counts) == 0:
            continue
        avg = sum(counts) / len(counts)
        variance = sum((c - avg) ** 2 for c in counts) / len(counts)
        score = avg - variance * 0.5
        if score > best_score:
            best_score, best = score, d
    return best


def preview_file(filepath: str, n_rows: int = 6) -> tuple[str, list[list[str]]]:
    """Devuelve (detected_delimiter, preview_rows) para el asistente de importación."""
    encoding = detect_encoding(filepath)
    delim = detect_delimiter(filepath, encoding)
    rows = []
    with open(filepath, newline="", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delim)
        for i, row in enumerate(reader):
            if i >= n_rows:
                break
            rows.append(row)
    return delim, rows


# ── Carga principal ───────────────────────────────────────────────────────────

def load_file(filepath: str,
              delimiter: str | None = None,
              has_header: bool = True,
              max_rows: int = MAX_ROWS) -> tuple[list[str], list[list[str]], bool]:
    """
    Devuelve (headers, rows, truncated).
    Si delimiter=None, se autodetecta.
    Si has_header=False, genera encabezados Col1, Col2, …
    """
    path = Path(filepath)
    encoding = detect_encoding(filepath)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return _load_txt(filepath, encoding, max_rows)

    if delimiter is None:
        delimiter = detect_delimiter(filepath, encoding)

    return _load_dsv(filepath, encoding, delimiter, has_header, max_rows)


def _load_dsv(filepath, encoding, delimiter, has_header, max_rows):
    with open(filepath, newline="", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        all_rows_iter = iter(reader)

        try:
            first_row = next(all_rows_iter)
        except StopIteration:
            return [], [], False

        first_row = [c.strip().lstrip("\ufeff") for c in first_row]

        if has_header:
            headers = first_row
            data_rows = []
        else:
            headers = [f"Col{i+1}" for i in range(len(first_row))]
            data_rows = [first_row]

        n = len(headers)
        truncated = False
        for row in all_rows_iter:
            if len(data_rows) >= max_rows:
                truncated = True
                break
            data_rows.append((row + [""] * n)[:n])

    return headers, data_rows, truncated


def _load_txt(filepath, encoding, max_rows):
    rows, truncated = [], False
    with open(filepath, encoding=encoding, errors="replace") as f:
        for line in f:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([line.rstrip("\n\r")])
    return ["Línea"], rows, truncated


# ── Guardado ──────────────────────────────────────────────────────────────────

def save_csv(filepath: str, headers: list[str], rows: list[list[str]],
             delimiter: str = ",", chunk_size: int = 5000):
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(headers)
        for i in range(0, len(rows), chunk_size):
            writer.writerows(rows[i: i + chunk_size])
