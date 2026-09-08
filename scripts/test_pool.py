"""Pruebas de la mecanica del pool, ANTES de entrenar con el.

APORTACION NUEVA de rlgym-selfplay-pool.

Comprueba, una por una, lo que el experimento dara por supuesto:
  1. una instantanea se guarda y su hash es estable;
  2. una politica congelada no cambia al usarla;
  3. el brazo A (retencion 1) reemplaza su unica instantanea;
  4. el brazo B (retencion N) conserva varias;
  5. el muestreo es reproducible con la misma semilla y distinto con otra;
  6. con UNA sola instantanea, A y B eligen lo mismo (equivalencia);
  7. cargar una instantanea no la modifica;
  8. en el entorno: obs y acciones al coche correcto, solo el aprendiz aporta
     experiencia, reset y fin de episodio siguen funcionando.

Uso:
    python scripts/test_pool.py --meshes RUTA --politica CKPT --tmp DIR
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

FALLOS = 0


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    global FALLOS
    if not ok:
        FALLOS += 1
    print(f"  [{'OK ' if ok else 'MAL'}] {nombre}" + (f": {detalle}" if detalle else ""))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--politica", required=True)
    p.add_argument("--tmp", required=True)
    a = p.parse_args()

    import numpy as np
    import torch
    from rlgym_ppo.ppo import DiscreteFF

    from rlbot.env.frozen_opponent import ConstructorPool, cargar_politica_congelada
    from rlbot.env.opponent_pool import PoolRivales

    tmp = Path(a.tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)

    # Politica de partida (la del artefacto de desarrollo).
    sd = torch.load(Path(a.politica) / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    wk = [k for k in sd if k.endswith("weight")]
    pol = DiscreteFF(89, 90, tuple(int(sd[k].shape[0]) for k in wk[:-1]), "cpu")
    pol.load_state_dict(sd)

    print("== 1-2. Guardado, hash estable y congelacion ==")
    pool_b = PoolRivales(tmp / "pool_b", retencion=5)
    e1 = pool_b.guardar_instantanea(pol, 1000, {"nota": "primera"})
    check("instantanea guardada", (pool_b.ruta_de(e1) / "PPO_POLICY.pt").exists(), e1["id"])
    check("hash registrado y verificable", pool_b.verificar(e1), e1["sha256"][:16])

    cargada = cargar_politica_congelada(pool_b.ruta_de(e1), 89)
    congelada = all(not q.requires_grad for q in cargada.parameters())
    obs = np.zeros((89,), dtype=np.float32)
    with torch.no_grad():
        for _ in range(50):
            cargada.get_action(obs, deterministic=False)
    check("politica congelada, no cambia al usarla",
          congelada and pool_b.verificar(e1), "requires_grad=False y hash intacto")
    check("cargar no modifica el archivo", pool_b.verificar(e1))

    print("\n== 3-4. Retencion: A reemplaza, B conserva ==")
    # Se guardan instantaneas "distintas" perturbando la politica.
    for ts in (2000, 3000, 4000):
        with torch.no_grad():
            for q in pol.parameters():
                q.add_(torch.randn_like(q) * 1e-3)
        pool_b.guardar_instantanea(pol, ts)
    check("B conserva varias", len(pool_b.elegibles()) == 4, f"{len(pool_b.elegibles())} instantaneas")

    pool_a = PoolRivales(tmp / "pool_a", retencion=1)
    for ts in (1000, 2000, 3000):
        pool_a.guardar_instantanea(pol, ts)
    ea = pool_a.elegibles()
    check("A mantiene solo una", len(ea) == 1, f"{len(ea)} instantanea")
    check("A conserva la mas reciente", ea and ea[0]["timestep"] == 3000, f"ts={ea[0]['timestep']}")
    check("A borro las antiguas del disco",
          not (pool_a.carpeta / "snap_000000001000").exists())

    print("\n== 5. Muestreo reproducible ==")
    s1 = [pool_b.elegir(42, i)["id"] for i in range(12)]
    s2 = [pool_b.elegir(42, i)["id"] for i in range(12)]
    s3 = [pool_b.elegir(7, i)["id"] for i in range(12)]
    check("misma semilla, misma secuencia", s1 == s2)
    check("otra semilla, otra secuencia", s1 != s3)
    check("usa mas de una instantanea", len(set(s1)) > 1, f"{len(set(s1))} distintas en 12 episodios")

    print("\n== 6. Con UNA sola instantanea, A y B son equivalentes ==")
    pool_a1 = PoolRivales(tmp / "pool_a1", retencion=1)
    pool_b1 = PoolRivales(tmp / "pool_b1", retencion=5)
    pool_a1.guardar_instantanea(pol, 5000)
    pool_b1.guardar_instantanea(pol, 5000)
    sa = [pool_a1.elegir(42, i)["id"] for i in range(10)]
    sb = [pool_b1.elegir(42, i)["id"] for i in range(10)]
    check("A y B eligen lo mismo con un solo elemento", sa == sb and len(set(sa)) == 1)

    print("\n== 7-8. En el entorno real ==")
    ctor = ConstructorPool(a.meshes, str(tmp / "pool_b"), retencion=5, semilla=42)
    env = ctor()
    o = env.reset()
    check("un solo agente hacia PPO", np.shape(o) == (89,), f"forma {np.shape(o)}")
    check("el aprendiz es el azul", env._i_aprendiz == 0)  # noqa: SLF001

    h_rival = pool_b.verificar(pool_b.elegibles()[0])
    dones, finitos = 0, True
    for _ in range(300):
        o, r, d, _ = env.step(np.array([[np.random.randint(0, 90)]]))
        if not np.isfinite(o).all() or not np.isfinite(r):
            finitos = False
        if d:
            dones += 1
            o = env.reset()
    check("obs y recompensas finitas", finitos, "300 pasos")
    check("reset y fin de episodio funcionan", dones > 0, f"{dones} episodios terminados")
    check("recompensa escalar del aprendiz", np.ndim(r) == 0,
          "solo la experiencia del aprendiz llega a PPO")
    check("las instantaneas siguen intactas tras jugar",
          all(pool_b.verificar(s) for s in pool_b.elegibles()))

    est = env.estadisticas_pool()
    check("el pool sirvio rivales", est["cargas_de_rival"] >= 1, str(est))
    env.close()

    print(f"\nResultado: {'TODO OK' if FALLOS == 0 else str(FALLOS) + ' FALLIDAS'}")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
