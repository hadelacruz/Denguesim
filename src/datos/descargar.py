"""Descarga todos los datos crudos de DengueSim GT en ``data/raw/``.

Solo usa la biblioteca estándar de Python (no hace falta instalar nada).

Uso (desde la raíz del repositorio):
    python src/datos/descargar.py              # descarga lo que falte
    python src/datos/descargar.py --solo casos # solo un grupo o un id
    python src/datos/descargar.py --forzar     # vuelve a descargar todo
    python src/datos/descargar.py --listar     # muestra el catálogo

Al terminar escribe ``data/raw/manifest.json`` con URL, tamaño, SHA-256 y
fecha de cada archivo, que es la evidencia de procedencia de los datos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fuentes  # noqa: E402

AGENTE = "DengueSim-GT/1.0 (proyecto academico UVG; Modelacion y Simulacion)"
TIMEOUT = 180
REINTENTOS = 4


def _contexto_ssl() -> ssl.SSLContext:
    """Usa certifi si está instalado (evita fallas de certificados en Windows)."""
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


CTX = _contexto_ssl()


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _bajar(url: str, destino: Path, metodo: str = "GET", datos: bytes | None = None) -> int:
    """Descarga en streaming a un archivo temporal y lo renombra al final."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    if metodo == "POST" and datos is None:
        datos = b""
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        leidos, ultimo = 0, time.time()
        while True:
            bloque = r.read(1 << 20)
            if not bloque:
                break
            f.write(bloque)
            leidos += len(bloque)
            if total > 5_000_000 and time.time() - ultimo > 2:
                print(f"      {leidos / 1e6:7.1f} / {total / 1e6:.1f} MB", flush=True)
                ultimo = time.time()
    if leidos == 0:
        tmp.unlink(missing_ok=True)
        raise IOError("respuesta vacía")
    tmp.replace(destino)
    return leidos


def _validar(destino: Path) -> None:
    """Detecta respuestas HTML de error disfrazadas de archivo."""
    if destino.suffix in {".zip", ".pdf", ".tif", ".pbf"}:
        with open(destino, "rb") as f:
            cabecera = f.read(512).lower()
        if b"<html" in cabecera or b"<!doctype" in cabecera:
            raise IOError("el servidor devolvió una página HTML en lugar del archivo")
    if destino.suffix == ".json":
        with open(destino, encoding="utf-8") as f:
            contenido = json.load(f)
        if isinstance(contenido, dict) and contenido.get("error"):
            raise IOError(f"API respondió con error: {contenido.get('reason') or contenido}")


def descargar_fuente(fuente: dict, forzar: bool) -> dict:
    destino = fuentes.RAW / fuente["destino"]
    registro = {k: fuente.get(k) for k in ("id", "grupo", "url", "nota")}
    registro["archivo"] = str(Path("data/raw") / fuente["destino"]).replace("\\", "/")
    if destino.exists() and not forzar:
        registro.update(estado="existente", bytes=destino.stat().st_size, sha256=_sha256(destino))
        print(f"  = {fuente['id']:<32} ya existe ({destino.stat().st_size / 1e6:.2f} MB)")
        return registro

    print(f"  > {fuente['id']:<32} descargando...", flush=True)
    error = None
    for intento in range(1, REINTENTOS + 1):
        try:
            n = _bajar(fuente["url"], destino, fuente.get("metodo", "GET"), fuente.get("datos"))
            _validar(destino)
            registro.update(
                estado="ok",
                bytes=n,
                sha256=_sha256(destino),
                fecha_descarga=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            print(f"    ok ({n / 1e6:.2f} MB)")
            if fuente.get("pausa"):
                time.sleep(fuente["pausa"])
            return registro
        except urllib.error.HTTPError as e:
            error = f"HTTP {e.code}"
            espera = 65 if e.code == 429 else 5 * intento
        except Exception as e:  # red, SSL, archivo inválido
            error = f"{type(e).__name__}: {e}"
            espera = 5 * intento
        destino.unlink(missing_ok=True)
        if intento < REINTENTOS:
            print(f"    intento {intento} falló ({error}); reintento en {espera}s")
            time.sleep(espera)
    registro.update(estado="error", error=error)
    print(f"    ERROR: {error}")
    return registro


def descargar_csv_insivumeh(forzar: bool) -> list[dict]:
    """Las páginas de estación de INSIVUMEH cargan un CSV por JavaScript; se
    extrae su URL del HTML ya descargado y se baja el CSV directamente."""
    import re

    registros = []
    for html in sorted((fuentes.RAW / "clima" / "insivumeh").glob("*.html")):
        m = re.search(r'csvUrl\s*=\s*"([^"?]+)', html.read_text(encoding="utf-8", errors="ignore"))
        if not m:
            continue
        url = urllib.parse.quote(m.group(1), safe=":/")
        registros.append(descargar_fuente({
            "id": f"insivumeh_csv_{html.stem}", "grupo": "clima", "url": url,
            "destino": f"clima/insivumeh/{html.stem}.csv",
            "nota": "INSIVUMEH. CSV de datos diarios recientes de la estación (el que carga la página).", "pausa": 2,
        }, forzar))
    return registros


def descargar_overpass(forzar: bool) -> list[dict]:
    registros = []
    for destino_rel, consulta in fuentes.OVERPASS_CONSULTAS.items():
        fuente = {
            "id": "osm_" + Path(destino_rel).stem,
            "grupo": "geo",
            "url": fuentes.OVERPASS_URL,
            "metodo": "POST",
            "datos": urllib.parse.urlencode({"data": consulta}).encode(),
            "destino": destino_rel,
            "nota": "OpenStreetMap vía Overpass API (ODbL). Consulta: " + " ".join(consulta.split()),
            "pausa": 5,
        }
        registros.append(descargar_fuente(fuente, forzar))
    return registros


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--solo", nargs="*", help="grupos o ids a descargar (casos, boletines, censo, geo, clima, osm)")
    p.add_argument("--forzar", action="store_true", help="vuelve a descargar aunque el archivo exista")
    p.add_argument("--listar", action="store_true", help="solo lista las fuentes")
    a = p.parse_args()

    catalogo = fuentes.todas()
    if a.listar:
        for f in catalogo:
            print(f"{f['grupo']:<10} {f['id']:<32} {f['destino']}")
        return 0

    def elegida(f: dict) -> bool:
        return not a.solo or f["grupo"] in a.solo or f["id"] in a.solo

    fuentes.RAW.mkdir(parents=True, exist_ok=True)
    print(f"Destino: {fuentes.RAW}")
    registros = []
    for grupo in ["casos", "boletines", "censo", "geo", "clima"]:
        sel = [f for f in catalogo if f["grupo"] == grupo and elegida(f)]
        if sel:
            print(f"\n[{grupo}]")
        registros += [descargar_fuente(f, a.forzar) for f in sel]
    if not a.solo or "clima" in a.solo:
        registros += descargar_csv_insivumeh(a.forzar)
    if not a.solo or "osm" in a.solo or "geo" in a.solo:
        print("\n[osm]")
        registros += descargar_overpass(a.forzar)

    manifest_path = fuentes.RAW / "manifest.json"
    previo = {}
    if manifest_path.exists():
        previo = {r["id"]: r for r in json.loads(manifest_path.read_text(encoding="utf-8"))}
    for r in registros:
        anterior = previo.get(r["id"], {})
        if r["estado"] == "existente" and anterior.get("fecha_descarga"):
            r["fecha_descarga"] = anterior["fecha_descarga"]
        previo[r["id"]] = r
    manifest_path.write_text(json.dumps(list(previo.values()), indent=2, ensure_ascii=False), encoding="utf-8")

    errores = [r for r in registros if r["estado"] == "error"]
    print(f"\nListo: {len(registros) - len(errores)} archivos disponibles, {len(errores)} con error.")
    for r in errores:
        print(f"  - {r['id']}: {r['error']}")
    print(f"Manifiesto: {manifest_path}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
