"""Preflight: puede esta maquina ejecutar, evaluar o entrenar este proyecto?

APORTACION NUEVA de rlgym-selfplay-pool. No forma parte de moanv2/rlgym.
Base: https://github.com/moanv2/rlgym (MIT, (c) 2026 Diego Alfaro Gomez).

Por defecto SOLO diagnostica: no entrena, no simula, no descarga nada.
El benchmark es opt-in con --benchmark y tiene tope de tiempo por modelo.

    python scripts/preflight.py                 # diagnostico
    python scripts/preflight.py --benchmark     # + medicion de inferencia
    python scripts/preflight.py --json-out FILE # guarda el informe

Cada comprobacion termina en uno de tres estados, y la diferencia importa:
    OK        comprobado y correcto
    FALLO     comprobado y NO cumple
    NO_EJEC   no se ha podido comprobar (falta un recurso) -- NO es un aprobado
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))  # para importar checks_sim

OK, FALLO, NO_EJEC = "OK", "FALLO", "NO_EJEC"


@dataclass
class Check:
    nombre: str
    estado: str
    detalle: str
    datos: dict[str, Any] = field(default_factory=dict)


class Informe:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, nombre: str, estado: str, detalle: str, **datos: Any) -> None:
        self.checks.append(Check(nombre, estado, detalle, datos))
        icono = {OK: "[ OK ]", FALLO: "[FALLO]", NO_EJEC: "[ -- ]"}[estado]
        print(f"  {icono} {nombre}: {detalle}")

    def resumen(self) -> dict[str, int]:
        r = {OK: 0, FALLO: 0, NO_EJEC: 0}
        for c in self.checks:
            r[c.estado] += 1
        return r


# --------------------------------------------------------------------------
# 1. Entorno
# --------------------------------------------------------------------------
def comprobar_entorno(inf: Informe) -> None:
    print("\n== Entorno de ejecucion ==")
    v = sys.version_info
    ok = (3, 10) <= (v.major, v.minor) < (3, 12)
    nota = "compatible" if ok else "la base exige >=3.10,<3.12"
    inf.add(
        "python",
        OK if ok else FALLO,
        f"{platform.python_version()} ({nota})",
        version=platform.python_version(),
        ejecutable=sys.executable,
    )
    inf.add("plataforma", OK, f"{platform.system()} {platform.release()} / {platform.machine()}")

    try:
        import torch

        inf.add(
            "torch",
            OK,
            f"{torch.__version__} | CUDA: {torch.cuda.is_available()} | hilos: {torch.get_num_threads()}",
            version=torch.__version__,
            cuda=torch.cuda.is_available(),
            hilos=torch.get_num_threads(),
        )
    except ImportError as e:
        inf.add("torch", FALLO, f"no instalado ({e})")

    for mod in ("numpy", "yaml"):
        try:
            m = __import__(mod)
            inf.add(mod, OK, getattr(m, "__version__", "?"))
        except ImportError:
            inf.add(mod, FALLO, "no instalado")


# --------------------------------------------------------------------------
# 2. Stack de simulacion y mallas de colision
# --------------------------------------------------------------------------
def comprobar_simulacion(inf: Informe, meshes: Path | None = None) -> bool:
    """Devuelve True si el simulador esta listo para ejecutarse."""
    print("\n== Simulacion ==")
    listo = True

    for mod, etiqueta in (
        ("rlgym_sim", "rlgym_sim"),
        ("rlgym_ppo", "rlgym-ppo"),
        ("RocketSim", "RocketSim (rocketsim)"),
    ):
        try:
            __import__(mod)
            inf.add(etiqueta, OK, "importable")
        except ImportError:
            inf.add(etiqueta, FALLO, "no instalado")
            listo = False

    # Las mallas de colision de Rocket League no se pueden redistribuir: hay que
    # volcarlas de una instalacion local del juego. Sin ellas RocketSim no arranca.
    candidatas = ([meshes] if meshes else []) + [REPO / "collision_meshes", Path.cwd() / "collision_meshes"]
    encontrada = None
    for p in candidatas:
        if p.is_dir() and any(p.iterdir()):
            encontrada = p
            break

    if encontrada:
        inf.add("collision_meshes", OK, str(encontrada), ruta=str(encontrada))
    else:
        inf.add(
            "collision_meshes",
            FALLO,
            "ausente - RocketSim no puede arrancar. Se obtienen de la distribucion "
            "oficial rlgym-rocket-league, o volcandolas de una instalacion local del juego",
            buscado_en=[str(p) for p in candidatas],
        )
        listo = False

    return listo


# --------------------------------------------------------------------------
# 3. Compatibilidad de los artefactos (checkpoints)
# --------------------------------------------------------------------------
def inspeccionar_checkpoint(d: Path) -> dict[str, Any]:
    """Lee un checkpoint SIN deserializacion arbitraria (weights_only=True).

    Que coincidan las dimensiones no basta para dar el comportamiento por
    equivalente, asi que se reporta tambien que piezas faltan.
    """
    import torch

    archivos = sorted(p.name for p in d.iterdir() if p.is_file())
    out: dict[str, Any] = {"ruta": str(d), "archivos": archivos}

    pol = d / "PPO_POLICY.pt"
    if not pol.exists():
        out["error"] = "sin PPO_POLICY.pt"
        return out

    # Carga restringida. Nunca pickle arbitrario para hacer cargar un archivo ajeno.
    sd = torch.load(pol, map_location="cpu", weights_only=True)
    wk = [k for k in sd if k.endswith("weight")]
    if not wk:
        out["error"] = "sin pesos lineales reconocibles"
        return out

    out["obs_dim"] = int(sd[wk[0]].shape[1])
    out["n_acciones"] = int(sd[wk[-1]].shape[0])
    out["capas_ocultas"] = [int(sd[k].shape[0]) for k in wk[:-1]]
    out["parametros"] = int(sum(v.numel() for v in sd.values()))

    tiene = set(archivos)
    out["tiene_critico"] = "PPO_VALUE_NET.pt" in tiene
    out["tiene_optimizadores"] = {
        "PPO_POLICY_OPTIMIZER.pt",
        "PPO_VALUE_NET_OPTIMIZER.pt",
    } <= tiene

    bk = d / "BOOK_KEEPING_VARS.json"
    if bk.exists():
        try:
            book = json.loads(bk.read_text(encoding="utf-8"))
            out["timesteps"] = book.get("cumulative_timesteps")
            cfg = book.get("wandb_config") or {}
            claves = (
                "policy_layer_sizes",
                "critic_layer_sizes",
                "standardize_obs",
                "standardize_returns",
                "gae_gamma",
                "gae_lambda",
                "policy_lr",
                "ppo_ent_coef",
            )
            out["config_entrenamiento"] = {k: cfg.get(k) for k in claves}
            out["tiene_reward_stats"] = "reward_running_stats" in book
        except (ValueError, OSError) as e:
            out["book_keeping_error"] = str(e)

    if out["tiene_critico"] and out["tiene_optimizadores"]:
        out["uso"] = "reanudar_entrenamiento"
    else:
        out["uso"] = "solo_inferencia_o_init_de_pesos"
    return out


def comprobar_artefactos(inf: Informe, raices: list[Path]) -> list[dict[str, Any]]:
    print("\n== Artefactos (checkpoints) ==")
    hallados: list[dict[str, Any]] = []
    for raiz in raices:
        if not raiz.exists():
            continue
        for pol in sorted(raiz.rglob("PPO_POLICY.pt")):
            hallados.append(inspeccionar_checkpoint(pol.parent))

    if not hallados:
        inf.add(
            "checkpoints",
            NO_EJEC,
            "ninguno presente en el arbol de trabajo",
            buscado_en=[str(r) for r in raices],
        )
        return hallados

    for h in hallados:
        etiqueta = f"ckpt {Path(h['ruta']).name}"
        if "error" in h:
            inf.add(etiqueta, FALLO, h["error"])
            continue
        inf.add(
            etiqueta,
            OK,
            f"obs={h['obs_dim']} acciones={h['n_acciones']} capas={h['capas_ocultas']} "
            f"params={h['parametros']:,} uso={h['uso']}",
            **h,
        )
    return hallados


# --------------------------------------------------------------------------
# 4. Benchmark (opt-in, acotado)
# --------------------------------------------------------------------------
def benchmark_inferencia(inf: Informe, ckpts: list[dict[str, Any]], segundos: float) -> None:
    """Mide SOLO el coste de la pasada hacia delante de la politica en CPU.

    Esto NO es velocidad de entrenamiento ni de simulacion: es una cota
    superior de cuantas decisiones por segundo puede tomar la red. El
    simulador y la actualizacion PPO se miden aparte.
    """
    print(f"\n== Benchmark de inferencia (tope {segundos:.0f}s por modelo) ==")
    import numpy as np
    import torch

    utiles = [c for c in ckpts if "error" not in c]
    if not utiles:
        inf.add("bench_inferencia", NO_EJEC, "sin checkpoints que medir")
        return

    vistos: set[tuple] = set()
    for c in utiles:
        firma = (tuple(c["capas_ocultas"]), c["obs_dim"], c["n_acciones"])
        if firma in vistos:
            continue
        vistos.add(firma)

        capas, obs_dim, n_act = c["capas_ocultas"], c["obs_dim"], c["n_acciones"]
        modulos: list[torch.nn.Module] = []
        prev = obs_dim
        for h in capas:
            modulos.append(torch.nn.Linear(prev, h))
            modulos.append(torch.nn.ReLU())
            prev = h
        modulos.append(torch.nn.Linear(prev, n_act))
        red = torch.nn.Sequential(*modulos).eval()

        x = torch.from_numpy(np.zeros((1, obs_dim), dtype=np.float32))
        with torch.no_grad():
            for _ in range(20):
                red(x)
            n = 0
            t0 = time.perf_counter()
            while time.perf_counter() - t0 < segundos:
                for _ in range(100):
                    red(x)
                n += 100
            dt = time.perf_counter() - t0

        ips = n / dt
        inf.add(
            f"bench arch {capas} obs={obs_dim}",
            OK,
            f"{ips:,.0f} inferencias/s (1 coche, lote 1) - cota superior, NO velocidad de entrenamiento",
            inferencias_por_segundo=round(ips, 1),
            capas=capas,
            obs_dim=obs_dim,
            segundos_medidos=round(dt, 2),
        )


def comprobaciones_simulacion(inf, meshes, ckpt, hacer_bench, segundos):
    """Arena, entorno 1v1 y las tres mediciones separadas.

    Se delega en scripts/checks_sim.py, que necesita la pila instalada.
    """
    pendientes = ("env_1v1", "bench_simulacion", "bench_sim_inferencia", "bench_ppo_update")
    if meshes is None:
        inf.add("arena_init", NO_EJEC, "no se ha indicado --meshes")
        for k in pendientes:
            inf.add(k, NO_EJEC, "depende de la arena")
        return

    try:
        from checks_sim import (
            bench_inferencia_integrada,
            bench_ppo,
            bench_simulacion,
            comprobar_arena,
            comprobar_entorno_1v1,
        )
    except ImportError as e:
        inf.add("checks_sim", FALLO, f"no se puede importar: {e}")
        return

    if not comprobar_arena(inf, meshes):
        for k in pendientes:
            inf.add(k, NO_EJEC, "no ejecutado: la arena no arranca")
        return

    env = comprobar_entorno_1v1(inf, meshes)

    if not hacer_bench:
        for k in pendientes[1:]:
            inf.add(k, NO_EJEC, "no solicitado (usa --benchmark)")
        return

    try:
        bench_simulacion(inf, env, segundos)
        if ckpt is not None and (ckpt / "PPO_POLICY.pt").exists():
            bench_inferencia_integrada(inf, env, ckpt, segundos)
            import torch

            sd = torch.load(ckpt / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
            wk = [k for k in sd if k.endswith("weight")]
            bench_ppo(
                inf,
                int(sd[wk[0]].shape[1]),
                int(sd[wk[-1]].shape[0]),
                tuple(int(sd[k].shape[0]) for k in wk[:-1]),
                muestras=50_000,
                segundos=segundos,
            )
        else:
            inf.add("bench_sim_inferencia", NO_EJEC, "sin checkpoint de desarrollo (--dev-ckpt)")
            inf.add("bench_ppo_update", NO_EJEC, "sin checkpoint de desarrollo (--dev-ckpt)")
    finally:
        try:
            if env is not None:
                env.close()
        except Exception:
            pass



# --------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description="Diagnostico de viabilidad del proyecto.")
    p.add_argument("--benchmark", action="store_true", help="Ejecuta tambien las mediciones (opt-in).")
    p.add_argument(
        "--bench-seconds", type=float, default=3.0, help="Segundos de carga por arquitectura (defecto 3)."
    )
    p.add_argument("--json-out", default=None, help="Ruta donde guardar el informe JSON.")
    p.add_argument(
        "--ckpt-root", action="append", default=None, help="Carpeta donde buscar checkpoints (repetible)."
    )
    p.add_argument("--meshes", default=None, help="Carpeta collision_meshes (con soccar/ dentro).")
    p.add_argument(
        "--dev-ckpt",
        default=None,
        help="Checkpoint de DESARROLLO para inferencia. Nunca un rival reservado.",
    )
    args = p.parse_args()

    print("=" * 78)
    print("PREFLIGHT - rlgym-selfplay-pool")
    print("Base: moanv2/rlgym (MIT, (c) 2026 Diego Alfaro Gomez). Este script es aportacion nueva.")
    print("=" * 78)

    inf = Informe()
    comprobar_entorno(inf)
    sim_listo = comprobar_simulacion(inf, Path(args.meshes) if args.meshes else None)

    if args.ckpt_root:
        raices = [Path(r) for r in args.ckpt_root]
    else:
        raices = [
            REPO / "checkpoints",
            REPO / "teammates",
            REPO / "diego-bots",
            REPO / "martin-bots",
        ]
    ckpts = comprobar_artefactos(inf, raices)

    if args.benchmark:
        benchmark_inferencia(inf, ckpts, args.bench_seconds)
    else:
        print("\n== Benchmark de inferencia aislada ==")
        inf.add("bench_inferencia", NO_EJEC, "no solicitado (usa --benchmark)")

    comprobaciones_simulacion(
        inf,
        Path(args.meshes) if args.meshes else None,
        Path(args.dev_ckpt) if args.dev_ckpt else None,
        args.benchmark,
        args.bench_seconds,
    )

    print("\n" + "=" * 78)
    r = inf.resumen()
    print(f"RESUMEN: {r[OK]} OK | {r[FALLO]} FALLO | {r[NO_EJEC]} NO EJECUTADO")
    print("Un NO EJECUTADO no es un aprobado: es una comprobacion que no se ha podido hacer.")
    print("=" * 78)

    if args.json_out:
        destino = Path(args.json_out)
        destino.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "python": platform.python_version(),
            "ejecutable": sys.executable,
            "resumen": r,
            "checks": [asdict(c) for c in inf.checks],
        }
        destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Informe guardado en {destino}")

    return 1 if r[FALLO] else 0


if __name__ == "__main__":
    raise SystemExit(main())
