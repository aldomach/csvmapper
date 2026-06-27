"""
csv_loader.py — Lectura y escritura de archivos CSV/TSV/TXT.

Escalabilidad:
  - detect_encoding lee solo los primeros 100 KB (suficiente para chardet).
  - load_file tiene límite configurable de filas (MAX_ROWS) para proteger RAM.
    Si el archivo supera el límite, devuelve las primeras MAX_ROWS filas y
    el flag truncated=True.
  - save_csv escribe por chunks para no acumular todo en memoria.
  - Detección de delimitador robusta: prueba varios candidatos y elige el
    que produce más columnas consistentes.
"""

import csv
import io
from pathlib import Path

import chardet

MAX_ROWS = 200_000   # límite de filas para proteger RAM (~50 MB típico)


# ── Encoding ──────────────────────────────────────────────────────────────────

def detect_encoding(filepath: str) -> str:
    with open(filepath, "rb") as f:
        raw = f.read(100_000)
    # BOM explícito tiene prioridad
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

def _detect_delimiter(sample: str) -> str:
    """
    Usa csv.Sniffer; si falla, cuenta ocurrencias de cada candidato
    y elige el que produce el conteo más alto y consistente.
    """
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        pass

    candidates = [",", ";", "\t", "|"]
    best_delim = ","
    best_score = -1
    lines = [l for l in sample.splitlines() if l.strip()][:20]

    for delim in candidates:
        counts = [line.count(delim) for line in lines]
        if not counts:
            continue
        avg = sum(counts) / len(counts)
        # Consistencia: stddev baja + promedio alto = buen delimitador
        variance = sum((c - avg) ** 2 for c in counts) / len(counts)
        score = avg - variance * 0.5
        if score > best_score:
            best_score = score
            best_delim = delim

    return best_delim


# ── Carga ─────────────────────────────────────────────────────────────────────

def load_file(filepath: str, max_rows: int = MAX_ROWS
              ) -> tuple[list[str], list[list[str]], bool]:
    """
    Devuelve (headers, rows, truncated).
    truncated=True si el archivo tenía más filas que max_rows.
    """
    path     = Path(filepath)
    encoding = detect_encoding(filepath)
    suffix   = path.suffix.lower()

    if suffix in (".csv", ".tsv", ".txt") and suffix != ".txt":
        return _load_dsv(filepath, encoding, suffix, max_rows)
    elif suffix == ".txt":
        return _load_txt(filepath, encoding, max_rows)
    else:
        # Intentar como CSV genérico
        return _load_dsv(filepath, encoding, ".csv", max_rows)


def _load_dsv(filepath, encoding, suffix, max_rows):
    """Carga archivos delimitados (CSV / TSV)."""
    with open(filepath, newline="", encoding=encoding, errors="replace") as f:
        sample = f.read(8192)
        f.seek(0)

        if suffix == ".tsv":
            delimiter = "\t"
        else:
            delimiter = _detect_delimiter(sample)

        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            return [], [], False

        # Limpiar encabezados (quitar espacios, BOM residual)
        headers = [h.strip().lstrip("\ufeff") for h in headers]
        n = len(headers)

        rows      = []
        truncated = False
        for row in reader:
            if len(rows) >= max_rows:
                truncated = True
                break
            # Normalizar largo de fila
            normalized = (row + [""] * n)[:n]
            rows.append(normalized)

    return headers, rows, truncated


def _load_txt(filepath, encoding, max_rows):
    """Carga texto plano: una línea = una fila, columna única 'Línea'."""
    rows      = []
    truncated = False
    with open(filepath, encoding=encoding, errors="replace") as f:
        for line in f:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([line.rstrip("\n\r")])
    return ["Línea"], rows, truncated


# ── Guardado ──────────────────────────────────────────────────────────────────

def save_csv(filepath: str, headers: list[str], rows: list[list[str]],
             chunk_size: int = 5000):
    """
    Escribe el CSV en chunks para no acumular todo en memoria.
    UTF-8 con BOM para compatibilidad con Excel.
    """
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i in range(0, len(rows), chunk_size):
            writer.writerows(rows[i : i + chunk_size])
