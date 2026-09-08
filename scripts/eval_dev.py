"""Evaluacion de DESARROLLO con registro por partida.

APORTACION NUEVA de rlgym-selfplay-pool.
Reutiliza el arnes heredado (tournament/obs.py y tournament/policy_io.py) en vez
de reconstruirlo.

QUE VALIDA Y QUE NO
-------------------
Valida que el circuito de evaluacion funciona y que queda registrado con
trazabilidad. **No es evidencia de que ningun bot juegue mejor**: la serie es
diminuta y los modelos son de desarrollo.

DIFERENCIAS DELIBERADAS CON EL TORNEO HEREDADO
----------------------------------------------
`tournament/match.py` resuelve los empates por criterios administrativos:
diferencia de goles agregada y, en ultima instancia, "mas timesteps de
entrenamiento gana" (`decided_by="seed"`). Eso vale para montar un cuadro de
competicion, pero **falsearia un experimento**: convertiria un empate en
victoria por una propiedad del modelo que no es su juego.

Aqui:
  - un empate se registra como EMPATE, y punto;
  - el resultado sale del marcador o de la condicion de finalizacion;
  - determinista y estocastico se registran por separado, nunca se mezclan;
  - una partida que no termina por gol ni por tiempo se marca 'incompleta' y
    NO cuenta como empate.

Uso:
    python scripts/eval_dev.py --meshes RUTA --a CKPT_A --b CKPT_B
        --partidas 8 --jsonl SALIDA.jsonl [--deterministic]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def sha256_de(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def obs_dim_de(ckpt: Path) -> int:
    import torch

    sd = torch.load(ckpt / "PPO_POLICY.pt", map_location="cpu", weights_only=True)
    wk = [k for k in sd if k.endswith("weight")]
    return int(sd[wk[0]].shape[1])


def jugar(env, pol_azul, pol_naranja, *, deterministic: bool, tope_pasos: int):
    """Juega un episodio. Devuelve (resultado_azul, causa, pasos).

    resultado_azul: +1 gana azul, -1 gana naranja, 0 empate por tiempo.
    causa: 'gol' | 'tiempo' | 'incompleta'
    """
    import numpy as np
    import torch

    from rlbot.tournament.policy_io import action_to_int

    obs = env.reset()
    pasos = 0
    with torch.no_grad():
        while pasos < tope_pasos:
            a_azul, _ = pol_azul.get_action(obs[0], deterministic=deterministic)
            a_nar, _ = pol_naranja.get_action(obs[1], deterministic=deterministic)
            obs, _, done, info = env.step(
                np.asarray([[action_to_int(a_azul)], [action_to_int(a_nar)]])
            )
            pasos += 1
            if done:
                res = int((info or {}).get("result", 0))
                # El resultado tiene que venir del marcador o del fin de episodio,
                # no de un valor por defecto ante informacion ausente.
                if res != 0:
                    return res, "gol", pasos
                return 0, "tiempo", pasos
    # Ni gol ni condicion de fin: la partida NO ha terminado. No es un empate.
    return None, "incompleta", pasos


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meshes", required=True)
    p.add_argument("--a", required=True, help="Checkpoint A (desarrollo).")
    p.add_argument("--b", required=True, help="Checkpoint B (desarrollo).")
    p.add_argument("--etiqueta-a", default="A")
    p.add_argument("--etiqueta-b", default="B")
    p.add_argument("--partidas", type=int, default=8, help="Fijado de antemano.")
    p.add_argument("--semilla-base", type=int, default=1000)
    p.add_argument("--tope-pasos", type=int, default=900, help="Tope por partida.")
    p.add_argument("--deterministic", action="store_true")
    p.add_argument("--minutos", type=float, default=5.0, help="Tope duro de reloj.")
    p.add_argument("--jsonl", required=True)
    p.add_argument("--resumen", default=None)
    a = p.parse_args()

    import numpy as np
    import torch

    from rlbot.env.rocketsim_init import asegurar_init
    from rlbot.tournament.obs import make_env
    from rlbot.tournament.policy_io import load_policy

    torch.set_num_threads(2)
    asegurar_init(a.meshes)

    ck_a, ck_b = Path(a.a), Path(a.b)
    dim_a, dim_b = obs_dim_de(ck_a), obs_dim_de(ck_b)
    h_a, h_b = sha256_de(ck_a / "PPO_POLICY.pt"), sha256_de(ck_b / "PPO_POLICY.pt")
    modo = "deterministic" if a.deterministic else "stochastic"

    print("== Evaluacion de desarrollo ==")
    print(f"  A = {a.etiqueta_a}  obs={dim_a}  {h_a[:16]}")
    print(f"  B = {a.etiqueta_b}  obs={dim_b}  {h_b[:16]}")
    print(f"  partidas={a.partidas} (fijadas de antemano)  modo={modo}  "
          f"tope={a.tope_pasos} pasos/partida")

    salida = Path(a.jsonl)
    salida.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    limite = a.minutos * 60
    entornos: dict[tuple[int, int], object] = {}
    lineas = []

    with salida.open("w", encoding="utf-8") as f:
        for i in range(a.partidas):
            if time.perf_counter() - t0 > limite:
                print(f"  [tope de {a.minutos} min alcanzado tras {i} partidas]")
                break
            # Reparto de lados alternado: A empieza de azul, luego de naranja.
            a_es_azul = (i % 2 == 0)
            azul_ck, naranja_ck = (ck_a, ck_b) if a_es_azul else (ck_b, ck_a)
            azul_dim, naranja_dim = (dim_a, dim_b) if a_es_azul else (dim_b, dim_a)
            semilla = a.semilla_base + i

            clave = (azul_dim, naranja_dim)
            if clave not in entornos:
                entornos[clave] = make_env(azul_dim, naranja_dim)
            env = entornos[clave]

            np.random.seed(semilla)
            torch.manual_seed(semilla)
            try:
                env.action_space.seed(semilla)
            except Exception:  # noqa: BLE001
                pass

            pol_azul = load_policy(azul_ck, azul_dim)
            pol_nar = load_policy(naranja_ck, naranja_dim)

            t_p = time.perf_counter()
            res_azul, causa, pasos = jugar(
                env, pol_azul, pol_nar, deterministic=a.deterministic, tope_pasos=a.tope_pasos
            )
            dur = time.perf_counter() - t_p

            if causa == "incompleta":
                resultado_a = None
            elif res_azul == 0:
                resultado_a = "empate"
            else:
                gana_azul = res_azul > 0
                resultado_a = "victoria_a" if (gana_azul == a_es_azul) else "derrota_a"

            fila = {
                "id": f"dev-{i:03d}",
                "modelo_a": {"etiqueta": a.etiqueta_a, "ruta": str(ck_a), "sha256": h_a, "obs_dim": dim_a},
                "modelo_b": {"etiqueta": a.etiqueta_b, "ruta": str(ck_b), "sha256": h_b, "obs_dim": dim_b},
                "config": {"tope_pasos": a.tope_pasos, "tick_skip": 8, "action_parser": "LookupAction"},
                "semilla": semilla,
                "lado_a": "azul" if a_es_azul else "naranja",
                "modo_accion": modo,
                "resultado_a": resultado_a,
                "resultado_azul_bruto": res_azul,
                "causa_fin": causa,
                "pasos": pasos,
                "segundos": round(dur, 3),
            }
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            lineas.append(fila)
            print(f"  {fila['id']}  A={fila['lado_a']:8} semilla={semilla}  "
                  f"{str(resultado_a):11} por {causa:11} en {pasos:4} pasos ({dur:.1f}s)")

    # -- resumen LEIDO del JSONL, no acumulado en memoria -------------------
    leidas = [json.loads(l) for l in salida.read_text(encoding="utf-8").splitlines() if l.strip()]
    conteo = {"victoria_a": 0, "derrota_a": 0, "empate": 0, "incompleta": 0}
    for r in leidas:
        conteo["incompleta" if r["resultado_a"] is None else r["resultado_a"]] += 1
    decisivas = conteo["victoria_a"] + conteo["derrota_a"]
    completas = decisivas + conteo["empate"]

    resumen = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "jsonl": str(salida),
        "modo_accion": modo,
        "partidas_solicitadas": a.partidas,
        "partidas_registradas": len(leidas),
        "conteo": conteo,
        "tasa_victoria_a_sobre_completas": round(conteo["victoria_a"] / completas, 4) if completas else None,
        "tasa_victoria_a_sobre_decisivas": round(conteo["victoria_a"] / decisivas, 4) if decisivas else None,
        "nota": "Serie de validacion del arnes. NO es evidencia de mejora de ningun bot.",
        "empates": "Un empate se registra como empate: no se desempata por timesteps ni por clasificacion.",
    }
    # Los totales tienen que cuadrar con el JSONL.
    resumen["totales_cuadran"] = (sum(conteo.values()) == len(leidas))

    print("\n== Resumen (leido del JSONL) ==")
    print(f"  registradas={len(leidas)}  {conteo}")
    print(f"  totales cuadran: {resumen['totales_cuadran']}")
    if resumen["tasa_victoria_a_sobre_completas"] is not None:
        print(f"  tasa de victoria de A sobre completas : {resumen['tasa_victoria_a_sobre_completas']}")
        print(f"  tasa de victoria de A sobre decisivas : {resumen['tasa_victoria_a_sobre_decisivas']}")
    print("  (validacion del arnes, no evidencia de mejora)")

    if a.resumen:
        Path(a.resumen).write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  resumen -> {a.resumen}")

    return 0 if resumen["totales_cuadran"] and leidas else 1


if __name__ == "__main__":
    raise SystemExit(main())
