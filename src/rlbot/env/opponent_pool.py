"""Pool de rivales congelados: instantaneas de la politica del aprendiz.

APORTACION NUEVA de rlgym-selfplay-pool.

LA UNICA DIFERENCIA ENTRE LOS DOS BRAZOS
----------------------------------------
Los dos usan ESTA misma maquinaria. Lo unico que cambia es la politica de
retencion del pool:

    Brazo A (control)  retencion = 1   -> siempre hay UNA instantanea, que se
                                          refresca cada K muestras con la
                                          politica actual del aprendiz
    Brazo B (variante) retencion = N   -> se conservan varias instantaneas
                                          historicas y el rival se muestrea
                                          entre ellas

Con una sola instantanea en el pool, A y B se comportan igual. Hay una prueba
que lo comprueba.

MUESTREO
--------
Uniforme entre las instantaneas elegibles. Es la regla mas simple que puede
producir el efecto que estudia H1 (no olvidar versiones pasadas), y no
introduce ningun mecanismo adicional que confunda el experimento. Nada de Elo,
prioridades adaptativas ni curriculos: eso vendria despues, y cada pieza extra
seria una variable mas que aislar.

El muestreo es reproducible: depende de una semilla y del numero de episodio,
no del reloj ni del orden de los procesos.

COORDINACION ENTRE PROCESOS
---------------------------
El proceso principal escribe instantaneas; los trabajadores las leen. La
comunicacion es el sistema de archivos, porque en Windows los trabajadores son
procesos spawneados sin memoria compartida con el padre. Cada trabajador relee
el manifiesto al empezar un episodio y solo carga pesos si la instantanea
elegida cambia respecto a la que ya tiene en cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

MANIFIESTO = "meta.json"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class PoolRivales:
    """Coleccion de instantaneas congeladas, en disco, con manifiesto."""

    def __init__(self, carpeta: str | os.PathLike, retencion: int,
                 proteger: tuple[str, ...] = ()) -> None:
        if retencion < 1:
            raise ValueError("La retencion debe ser >= 1 (A usa 1, B usa varias).")
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.retencion = int(retencion)
        # Instantaneas que NUNCA se expulsan. En el brazo B es C0: el punto del
        # que partieron los dos brazos, y por tanto el ancla de la comparacion.
        # El brazo A no protege nada: conserva solo la version actual.
        self.proteger = tuple(proteger)

    # -- manifiesto --------------------------------------------------------
    @property
    def ruta_manifiesto(self) -> Path:
        return self.carpeta / MANIFIESTO

    def leer_manifiesto(self) -> dict[str, Any]:
        if not self.ruta_manifiesto.exists():
            return {"retencion": self.retencion, "instantaneas": []}
        try:
            return json.loads(self.ruta_manifiesto.read_text(encoding="utf-8"))
        except ValueError:
            # Escritura a medias: se trata como pool vacio en vez de reventar
            # el entrenamiento. No se oculta nada mas que esta carrera concreta.
            return {"retencion": self.retencion, "instantaneas": []}

    def _escribir_manifiesto(self, datos: dict[str, Any]) -> None:
        # Escritura atomica: los trabajadores leen mientras el padre escribe.
        tmp = tempfile.NamedTemporaryFile(
            "w", delete=False, dir=self.carpeta, suffix=".tmp", encoding="utf-8"
        )
        try:
            json.dump(datos, tmp, indent=2, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.replace(tmp.name, self.ruta_manifiesto)

    # -- escritura ---------------------------------------------------------
    def guardar_instantanea(self, politica, timestep: int, config: dict[str, Any] | None = None) -> dict:
        """Congela la politica actual del aprendiz como una instantanea nueva."""
        import torch

        nombre = f"snap_{timestep:012d}"
        destino = self.carpeta / nombre
        destino.mkdir(parents=True, exist_ok=True)
        archivo = destino / "PPO_POLICY.pt"
        torch.save(politica.state_dict(), archivo)

        entrada = {
            "id": nombre,
            "timestep": int(timestep),
            "sha256": _sha256(archivo),
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "config": config or {},
        }

        datos = self.leer_manifiesto()
        datos["retencion"] = self.retencion
        datos["protegidas"] = list(self.proteger)
        datos["instantaneas"] = [s for s in datos.get("instantaneas", []) if s["id"] != nombre]
        datos["instantaneas"].append(entrada)
        datos["instantaneas"].sort(key=lambda s: s["timestep"])

        # REGLA DE RETENCION, determinista y fijada antes del experimento:
        #   1. las instantaneas protegidas (C0 en el brazo B) no se expulsan nunca;
        #   2. si se supera el maximo, se expulsa la MAS ANTIGUA no protegida;
        #   3. se repite hasta caber.
        # El brazo A usa retencion=1 sin protegidas, asi que conserva solo la
        # version actual, exactamente como estaba validado.
        todas = datos["instantaneas"]
        protegidas = [x for x in todas if x["id"] in self.proteger]
        libres = [x for x in todas if x["id"] not in self.proteger]
        hueco = max(0, self.retencion - len(protegidas))
        sobrantes = libres[:-hueco] if hueco else list(libres)
        conservadas = (libres[-hueco:] if hueco else [])
        datos["instantaneas"] = sorted(protegidas + conservadas, key=lambda x: x["timestep"])
        self._escribir_manifiesto(datos)

        for s in sobrantes:
            d = self.carpeta / s["id"]
            for f in d.glob("*"):
                f.unlink(missing_ok=True)
            d.rmdir()
        return entrada

    # -- lectura -----------------------------------------------------------
    def elegibles(self) -> list[dict]:
        return self.leer_manifiesto().get("instantaneas", [])

    def elegir(self, semilla: int, episodio: int) -> dict | None:
        """Muestreo UNIFORME reproducible: depende de (semilla, episodio).

        No depende del reloj ni del orden en que arranquen los trabajadores, asi
        que dos ejecuciones con la misma semilla eligen la misma secuencia.
        """
        import numpy as np

        cands = self.elegibles()
        if not cands:
            return None
        rng = np.random.default_rng((int(semilla) * 1_000_003 + int(episodio)) % (2**63))
        return cands[int(rng.integers(0, len(cands)))]

    def ruta_de(self, entrada: dict) -> Path:
        return self.carpeta / entrada["id"]

    def verificar(self, entrada: dict) -> bool:
        """La instantanea sigue siendo la que dice el manifiesto (no se ha tocado)."""
        f = self.ruta_de(entrada) / "PPO_POLICY.pt"
        return f.exists() and _sha256(f) == entrada["sha256"]
