"""Repara el marcador COMPLETA/INCOMPLETA de una corrida de la fase 0 de H2.

APORTACION NUEVA de rlgym-selfplay-pool.

Existe por un defecto concreto y ya corregido: `train_phase0.py` buscaba el
checkpoint final DENTRO de la carpeta `checkpoints/`, pero rlgym-ppo escribe en
una carpeta hermana con sufijo (`checkpoints-<id>/<ts>/`). Una corrida que habia
terminado perfectamente quedaba marcada INCOMPLETA por esa busqueda vacia.

Este script NO reentrena, NO altera pesos y NO inventa nada. Solo vuelve a
derivar del disco los campos que el defecto dejo mal, y unicamente asciende a
COMPLETA si TODO se verifica de nuevo:

  - no hubo error durante el entrenamiento;
  - las muestras alcanzan el presupuesto;
  - los parametros son finitos;
  - existe un checkpoint final que se RECUPERA en un proceso nuevo;
  - C0 sigue intacto.

Si algo de eso falla, deja la corrida como esta. La reparacion queda escrita en
el propio informe, con la fecha y el motivo, para que nadie la confunda con un
resultado original.

Uso:
    python scripts/h2/repair_informe.py --run DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))


def sha256_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="Carpeta de la corrida (con informe.json).")
    a = ap.parse_args()

    from integrity_table import recuperar

    dir_run = Path(a.run)
    p_inf = dir_run / "informe.json"
    d = json.loads(p_inf.read_text(encoding="utf-8"))

    if d.get("estado") == "COMPLETA":
        print("  ya estaba COMPLETA; no se toca nada.")
        return 0
    if d.get("reparado_por"):
        print("  ya fue reparada antes; no se repara dos veces.")
        return 1

    r = d["resultado"]
    presupuesto = int(d["configuracion_resuelta"]["presupuesto"])

    dir_ckpt = dir_run / "checkpoints"
    ckpts = sorted(dir_ckpt.parent.glob(dir_ckpt.name + "*/*/PPO_POLICY.pt"),
                   key=lambda p: int(p.parent.name))
    ckpt_final = ckpts[-1].parent if ckpts else None

    comprobaciones = {
        "sin_error": r["error"] is None,
        "presupuesto_alcanzado": int(r["muestras"]) >= presupuesto,
        "parametros_finitos": bool(d["integridad"]["parametros_finitos"]),
        "c0_intacto": bool(d["integridad"]["c0_intacto"]),
        "checkpoint_final_existe": ckpt_final is not None,
    }
    if ckpt_final is not None:
        rec = recuperar(ckpt_final)
        comprobaciones["checkpoint_final_se_recupera"] = bool(rec.get("ok"))
    else:
        rec = {"ok": False, "error": "sin checkpoint"}
        comprobaciones["checkpoint_final_se_recupera"] = False

    for k, v in comprobaciones.items():
        print(f"  {'OK   ' if v else 'FALLA'}  {k}")

    if not all(comprobaciones.values()):
        print("\n  No se asciende a COMPLETA: alguna comprobacion falla.")
        return 1

    d["integridad"]["checkpoint_final"] = str(ckpt_final)
    d["integridad"]["hash_checkpoint_final"] = sha256_archivo(ckpt_final / "PPO_POLICY.pt")
    d["integridad"]["recuperacion_verificada"] = rec
    d["estado"] = "COMPLETA"
    d["reparado_por"] = {
        "script": "scripts/h2/repair_informe.py",
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "motivo": ("El marcador decia INCOMPLETA por un defecto de train_phase0.py: "
                   "buscaba el checkpoint final dentro de 'checkpoints/', pero "
                   "rlgym-ppo escribe en la hermana 'checkpoints-<id>/<ts>/'. "
                   "El entrenamiento habia terminado correctamente."),
        "no_se_reentreno": True,
        "comprobaciones": comprobaciones,
    }
    p_inf.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  {dir_run.name}: ascendida a COMPLETA y reparacion registrada en el informe.")
    print(f"  checkpoint final: {ckpt_final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
