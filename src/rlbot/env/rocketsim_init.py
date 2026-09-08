"""Inicializacion de RocketSim, una sola vez por proceso y con ruta explicita.

APORTACION NUEVA de rlgym-selfplay-pool. No forma parte de moanv2/rlgym.
Base: https://github.com/moanv2/rlgym (MIT, (c) 2026 Diego Alfaro Gomez).

POR QUE EXISTE ESTE MODULO
--------------------------
`rlgym_sim` nunca llama a `RocketSim.init()`: va directo a `rsim.Arena(...)`, y
RocketSim busca las mallas en "./collision_meshes/" RELATIVO AL DIRECTORIO DE
TRABAJO. Eso obliga a lanzar todo desde una carpeta concreta, y falla en cuanto
alguien ejecuta el comando desde otro sitio.

Y hay un segundo problema, peor porque es silencioso hasta que revienta: en
Windows multiprocessing arranca con 'spawn', asi que un proceso hijo NO hereda
la inicializacion del padre. Comprobado:

    hijo SIN init  -> RuntimeError: ROCKETSIM FATAL ERROR:
                      No arena meshes found for gamemode soccar
    hijo CON init  -> arena ok

Por eso la inicializacion tiene que ocurrir DENTRO de cada proceso trabajador,
antes de crear su primera arena, y con una ruta absoluta.

TRES REGLAS QUE ESTE MODULO RESPETA
-----------------------------------
1. Una sola vez por proceso: `rsim.init()` lanza "Already inited" en la segunda
   llamada, asi que varias arenas en el mismo proceso comparten inicializacion.
2. Ruta explicita y absoluta: nunca se depende del directorio de trabajo.
3. Los errores reales NO se tragan. Si las mallas faltan o estan corruptas, se
   levanta una excepcion clara. Un try/except que da todo por valido convierte
   un fallo de configuracion en un entrenamiento que no aprende nada.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

# Variable de entorno para no tener que pasar la ruta por todas las capas.
VAR_ENTORNO = "RLBOT_COLLISION_MESHES"

_lock = threading.Lock()
_iniciado_en_pid: int | None = None
_ruta_usada: Path | None = None


class MallasNoEncontradas(RuntimeError):
    """Las mallas de colision no estan donde se dijo, o estan incompletas."""


def resolver_ruta(ruta: str | os.PathLike | None = None) -> Path:
    """Devuelve la ruta absoluta de collision_meshes, o falla diciendo por que."""
    bruta = ruta or os.environ.get(VAR_ENTORNO)
    if not bruta:
        raise MallasNoEncontradas(
            "No se ha indicado la ruta de collision_meshes. Pasala explicitamente "
            f"o define la variable de entorno {VAR_ENTORNO}."
        )
    p = Path(bruta).expanduser().resolve()
    if not p.is_dir():
        raise MallasNoEncontradas(f"No existe la carpeta de mallas: {p}")
    soccar = p / "soccar"
    if not soccar.is_dir():
        raise MallasNoEncontradas(
            f"No hay subcarpeta 'soccar' en {p}. RocketSim la necesita para el modo SOCCAR."
        )
    cmf = list(soccar.glob("*.cmf"))
    if not cmf:
        raise MallasNoEncontradas(f"No hay archivos .cmf en {soccar}")
    return p


def asegurar_init(ruta: str | os.PathLike | None = None) -> Path:
    """Inicializa RocketSim en ESTE proceso si aun no lo esta. Devuelve la ruta.

    Es idempotente dentro del proceso y seguro entre hilos. Tras un fork/spawn
    el PID cambia, asi que el hijo vuelve a inicializar aunque herede el modulo.
    """
    global _iniciado_en_pid, _ruta_usada

    pid = os.getpid()
    with _lock:
        if _iniciado_en_pid == pid:
            return _ruta_usada  # type: ignore[return-value]

        p = resolver_ruta(ruta)
        import RocketSim as rsim

        try:
            rsim.init(str(p))
        except RuntimeError as e:
            # "Already inited" es el unico caso benigno: otro modulo se nos
            # adelanto en este mismo proceso. Cualquier otro error se propaga.
            if "already inited" not in str(e).lower():
                raise
        _iniciado_en_pid = pid
        _ruta_usada = p
        return p


def esta_iniciado() -> bool:
    return _iniciado_en_pid == os.getpid()
