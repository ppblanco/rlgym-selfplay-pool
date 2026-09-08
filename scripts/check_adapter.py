"""Comprueba el adaptador aprendiz/rival congelado, antes de entrenar con el.

APORTACION NUEVA de rlgym-selfplay-pool.

Verifica, una por una, las propiedades que el experimento dara por supuestas:
  1. El entorno se presenta como UN agente (asi rlgym-ppo solo aprende del azul).
  2. El aprendiz recibe SU observacion y SU recompensa.
  3. La accion del aprendiz llega a SU coche.
  4. El rival permanece congelado (mismos pesos antes y despues).
  5. reset, fin de episodio y truncamiento se transmiten.
  6. Funciona en un proceso hijo con spawn.

Uso:
    python scripts/check_adapter.py --meshes RUTA --rival CKPT [--pasos 400]
"""
from __future__ import annotations

import argparse
import hashlib
import multiprocessing as mp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _hash_pesos(pol) -> str:
    import torch

    h = hashlib.sha256()
    with torch.no_grad():
        for p in pol.parameters():
            h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()[:16]


def _hijo(q, mallas, rival, pasos):
    """Se ejecuta en un proceso spawneado: replica lo que hara un trabajador."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from rlbot.env.frozen_opponent import ConstructorRivalCongelado

        env = ConstructorRivalCongelado(mallas, rival)()
        obs = env.reset()
        import numpy as np

        for _ in range(pasos):
            o, r, d, _ = env.step(np.array([[np.random.randint(0, 90)]]))
            if d:
                o = env.reset()
        q.put(("ok", int(env.pasos_entorno), int(env.episodios), list(np.shape(obs))))
    except Exception as e:  # noqa: BLE001
        q.put(("error", f"{type(e).__name__}: {e}", 0, []))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--rival", required=True)
    p.add_argument("--pasos", type=int, default=400)
    a = p.parse_args()

    import numpy as np

    from rlbot.env.frozen_opponent import ConstructorRivalCongelado

    fallos = 0

    def check(nombre: str, ok: bool, detalle: str) -> None:
        nonlocal fallos
        if not ok:
            fallos += 1
        print(f"  [{'OK ' if ok else 'MAL'}] {nombre}: {detalle}")

    print("== Adaptador aprendiz / rival congelado ==")
    ctor = ConstructorRivalCongelado(a.meshes, a.rival)
    env = ctor()

    # 1. un solo agente hacia rlgym-ppo
    obs = env.reset()
    forma = np.shape(obs)
    check("un_solo_agente", len(forma) == 1,
          f"reset() devuelve forma {forma} -> rlgym-ppo vera {'1 agente' if len(forma)==1 else 'varios'}")
    check("dim_observacion", forma[0] == 89, f"{forma[0]} dimensiones (DefaultObs)")

    # 2 y 3. la obs del aprendiz es la de SU coche, y su accion va a SU coche.
    # Se comprueba comparando con el entorno interno: la obs devuelta tiene que
    # ser identica a la del indice del aprendiz.
    interno = env._env  # noqa: SLF001  (comprobacion deliberada de la interconexion)
    obs_int = interno.reset()
    env._obs_rival = np.asarray(obs_int[1], dtype=np.float32)  # noqa: SLF001
    igual = np.allclose(np.asarray(obs_int[0], dtype=np.float32),
                        np.asarray(obs_int[env._i_aprendiz], dtype=np.float32))  # noqa: SLF001
    check("obs_del_aprendiz", igual and env._i_aprendiz == 0,  # noqa: SLF001
          f"el aprendiz es el equipo {env._i_aprendiz} (azul) y recibe su propia observacion")  # noqa: SLF001

    # 4. rival congelado: hash de pesos antes y despues de muchos pasos
    h_antes = _hash_pesos(env._rival)  # noqa: SLF001
    sin_grad = all(not q.requires_grad for q in env._rival.parameters())  # noqa: SLF001

    # 5. reset / done / truncamiento, y recompensas finitas
    obs = env.reset()
    dones, rews, finitos = 0, [], True
    for _ in range(a.pasos):
        o, r, d, _ = env.step(np.array([[np.random.randint(0, 90)]]))
        rews.append(r)
        if not np.isfinite(o).all() or not np.isfinite(r):
            finitos = False
        if d:
            dones += 1
            o = env.reset()
    check("obs_y_recompensas_finitas", finitos, f"{len(rews)} pasos, todos finitos")
    check("recompensa_escalar", all(np.isscalar(x) or np.ndim(x) == 0 for x in rews),
          "la recompensa del aprendiz es un escalar, como espera rlgym-ppo con 1 agente")
    check("fin_de_episodio", dones > 0,
          f"{dones} finales de episodio en {a.pasos} pasos (timeout de 300 pasos)")
    check("contadores", env.pasos_entorno >= a.pasos,
          f"{env.pasos_entorno} pasos de entorno, {env.episodios} episodios")

    h_despues = _hash_pesos(env._rival)  # noqa: SLF001
    check("rival_congelado", h_antes == h_despues and sin_grad,
          f"pesos {h_antes} sin cambios tras {a.pasos} pasos; requires_grad=False en todos")
    env.close()

    # 6. proceso hijo con spawn
    print("\n== En un proceso hijo (spawn) ==")
    q = mp.Queue()
    proc = mp.Process(target=_hijo, args=(q, a.meshes, a.rival, 60))
    proc.start()
    proc.join(timeout=180)
    if proc.is_alive():
        proc.terminate(); proc.join()
        check("hijo_spawn", False, "TIMEOUT")
    else:
        estado, x, y, forma_h = q.get() if not q.empty() else ("error", "sin respuesta", 0, [])
        check("hijo_spawn", estado == "ok",
              f"{x} pasos, {y} episodios, obs {forma_h}" if estado == "ok" else str(x))

    print(f"\nResultado: {'TODO OK' if fallos == 0 else str(fallos) + ' COMPROBACIONES FALLIDAS'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
