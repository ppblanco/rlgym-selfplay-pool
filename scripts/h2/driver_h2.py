"""Conductor de H2: lanza UNA corrida por proceso limpio y vigila.

APORTACION NUEVA de rlgym-selfplay-pool.

Este proceso padre es deliberadamente tonto: no importa torch, ni rlgym_sim, ni
rlgym_ppo. Solo lanza subprocesos, vigila y decide. Asi no puede heredar ni
contaminar el estado de sockets que colgo H1 entre B1 y A2.

Lo que garantiza:
  - un proceso por corrida, sin excepcion;
  - deteccion de estancamiento: si el log no avanza en N segundos, mata el
    ARBOL entero (padre e hijos) y marca la corrida INCOMPLETA;
  - deteccion de huerfanos: comprueba que no queda ningun descendiente vivo
    antes de pasar a la corrida siguiente;
  - marcador explicito COMPLETA/INCOMPLETA leido de informe.json, no del
    codigo de salida;
  - reanudable: una corrida COMPLETA no se repite; una INCOMPLETA se rehace
    entera desde C0.

Uso:
    python scripts/h2/driver_h2.py --raiz-salida DIR --meshes RUTA
        --linajes sparring,piloto [--presupuesto N --hitos A,B]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESTANCADO_S = 900          # 15 min sin escribir en el log = colgado
INTERVALO_S = 20


def descendientes(pid: int) -> list[int]:
    """PIDs vivos que descienden de pid, via WMIC/tasklist sin dependencias."""
    try:
        salida = subprocess.run(
            ["wmic", "process", "get", "ProcessId,ParentProcessId", "/format:csv"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    hijos: dict[int, list[int]] = {}
    for linea in salida.splitlines():
        partes = linea.strip().split(",")
        if len(partes) < 3:
            continue
        try:
            padre, propio = int(partes[-2]), int(partes[-1])
        except ValueError:
            continue
        hijos.setdefault(padre, []).append(propio)
    fuera, pila = [], [pid]
    while pila:
        actual = pila.pop()
        for h in hijos.get(actual, []):
            if h not in fuera:
                fuera.append(h)
                pila.append(h)
    return fuera


def matar_arbol(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                   capture_output=True, text=True)


def ejecutar_una(linaje: str, raiz: Path, meshes: str, extra: list[str]) -> dict:
    """Lanza una corrida en su propio proceso y la vigila hasta el final."""
    log = raiz / f"{linaje}.log"
    raiz.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(RAIZ / "scripts/h2/train_phase0.py"),
           "--linaje", linaje, "--meshes", meshes, "--raiz-salida", str(raiz)] + extra

    print(f"\n=== {linaje}: proceso nuevo ===", flush=True)
    t0 = time.perf_counter()
    with log.open("w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(RAIZ))
        motivo = None
        while True:
            if p.poll() is not None:
                break
            edad = time.time() - log.stat().st_mtime if log.exists() else 0
            if edad > ESTANCADO_S:
                motivo = f"estancado: {edad:.0f}s sin escribir en el log"
                print(f"  ! {motivo}. Matando el arbol de {p.pid}.", flush=True)
                matar_arbol(p.pid)
                p.wait(timeout=120)
                break
            time.sleep(INTERVALO_S)

    dt = time.perf_counter() - t0
    # -- huerfanos: nada del arbol puede seguir vivo --------------------------
    vivos = descendientes(p.pid)
    if vivos:
        print(f"  ! quedaban {len(vivos)} descendientes vivos: {vivos}. Se matan.", flush=True)
        for h in vivos:
            matar_arbol(h)
        time.sleep(2)
        vivos = descendientes(p.pid)

    # -- el estado se lee del informe, no del codigo de salida ----------------
    inf = raiz / linaje_a_id(raiz, linaje) / "informe.json"
    estado = "SIN_INFORME"
    if inf.exists():
        estado = json.loads(inf.read_text(encoding="utf-8")).get("estado", "SIN_ESTADO")

    r = {"linaje": linaje, "estado": estado, "codigo_salida": p.returncode,
         "segundos": round(dt, 1), "motivo_corte": motivo,
         "huerfanos_restantes": len(vivos), "log": str(log)}
    print(f"  {linaje}: {estado} en {dt:,.0f}s (rc={p.returncode}, "
          f"huerfanos={len(vivos)})", flush=True)
    return r


def linaje_a_id(raiz: Path, linaje: str) -> str:
    cfg = json.loads((RAIZ / "configs/experimento/h2/fase0.json").read_text(encoding="utf-8"))
    return cfg["linajes"][linaje]["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz-salida", required=True)
    ap.add_argument("--meshes", required=True)
    ap.add_argument("--linajes", default="sparring,piloto")
    ap.add_argument("--presupuesto", type=int, default=None)
    ap.add_argument("--hitos", default=None)
    a = ap.parse_args()

    extra: list[str] = []
    if a.presupuesto:
        extra += ["--presupuesto", str(a.presupuesto)]
    if a.hitos:
        extra += ["--hitos", a.hitos]

    raiz = Path(a.raiz_salida)
    resultados = []
    for linaje in [x.strip() for x in a.linajes.split(",") if x.strip()]:
        r = ejecutar_una(linaje, raiz, a.meshes, extra)
        resultados.append(r)
        if r["estado"] != "COMPLETA":
            print(f"\n  ! {linaje} no quedo COMPLETA. El conductor se detiene aqui "
                  f"en vez de arrastrar el fallo.", flush=True)
            break

    (raiz / "conductor.json").write_text(
        json.dumps({"resultados": resultados,
                    "todas_completas": all(r["estado"] == "COMPLETA" for r in resultados)},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  -> {raiz / 'conductor.json'}")
    return 0 if all(r["estado"] == "COMPLETA" for r in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
