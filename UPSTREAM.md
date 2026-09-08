# Procedencia

Este proyecto es una **evolución personal** construida sobre un trabajo ajeno.
Aquí queda registrado, con precisión, de dónde viene cada cosa.

## Base reutilizada

| | |
|---|---|
| Repositorio | https://github.com/moanv2/rlgym |
| Licencia | MIT |
| Copyright | (c) 2026 Diego — `LICENSE` |
| Autor declarado | Diego Alfaro Gomez (`pyproject.toml`) |
| Descripción | *Final Project for Reinforcement Learning @ IE School of Science and Technology* |
| Clonado el | 2026-09-07 |

La licencia MIT permite usar, copiar, modificar y redistribuir **conservando el
aviso de copyright y la licencia**. `LICENSE` se mantiene intacto, con el
copyright original. Nada de este proyecto reclama autoría sobre esa base.

## Versiones exactas de la base

Una rama no es una versión. Estos son los SHAs completos en el momento del clonado:

| Rama | SHA |
|---|---|
| `main` | `0c6965acf3d0405227282a80b1881dbfde3ef56b` |
| `diego` | `ee612541635caa35328a0fa9722cf08b2bb63794` |
| `martin` | `64cca16a6cc2a3f073629e399d884ba40e6220a4` |
| `nachi` | `3dc0a464d55b5eb1ebdfa1349f20a5f9fd2b5a3d` |
| `marco` | `7982beb7441e2702fefddd46bbcb87c0f88932ed` |
| `marian/setup-fixes` | `ef459eb66559fb2944958a075209d692fb17dc16` |

Otras ramas presentes en el remoto y no usadas por ahora: `BotVsReal`,
`feat/tournament-scaffolding`, `martin-imitation`, `presentation`.

## Dependencias obtenidas desde Git

`requirements.txt` de la base las declara apuntando a `main`, que **no es una
versión fija**. SHAs resueltos el 2026-09-07, para fijarlos cuando se instalen:

| Paquete | Repositorio | SHA | Fecha del commit |
|---|---|---|---|
| `rlgym-sim` | AechPro/rocket-league-gym-sim | `a1240530239d6b7671147b4f97e9b5e130d0acce` | 2024-09-09 |
| `rlgym-ppo` | AechPro/rlgym-ppo | `4ffd2e924198bf4b2d59f4bf280b29919d7c07ea` | 2025-01-06 |
| `rlgym-tools` | RLGym/rlgym-tools | `0c63b2a8878233f34869b9ea1e32e19548a0cd16` | 2026-07-10 |

> **Aviso de incompatibilidad.** `rlgym-tools@main` es la API **v2**, pensada
> para RLGym moderno, no para `rlgym_sim`. La propia base ya tropezó con esto:
> `src/rlbot/state_setters/builder.py` dice *"Vendored: rlgym_tools.extra_state_setters
> was removed in rlgym-tools v2"*. Si se instala, hay que fijar una versión
> anterior compatible o prescindir del paquete. **No se mezclan las dos pilas y
> no se migra el proyecto a RLGym moderno.**

## Artefactos usados (checkpoints ajenos)

Extraídos de las ramas indicadas, **sin modificar**. Se guardan fuera de OneDrive
por peso, en `%LOCALAPPDATA%\rlgym-selfplay-pool\artifacts\`.

Todos son obra de sus respectivos autores y se usan al amparo de la licencia MIT
del repositorio que los contiene. **No se reetiquetan ni se presentan como propios.**

| Nombre local | Origen | obs | Arquitectura | Parámetros | Archivos | Uso posible |
|---|---|---|---|---|---|---|
| `diego_1.18B_512` | `diego@ee612541` `diego-bots/checkpoints/MILESTONE_1.18B_nexto_plus_kickoff_512` | 89 | 512×3 | 617.562 | política + book keeping | **solo inferencia / init de pesos** |
| `martin_2.1B_1024` | `martin@64cca16a` `martin-bots/checkpoints/CHAMPION_2.1B_recipeD_advanced1024` | 107 | 1024×3 | 2.302.042 | política + book keeping | **solo inferencia / init de pesos** |
| `marco_2.0B_1024` | `marco@7982beb7` `checkpoints/exp_007_large/1999210400` | 89 | 1024×3 | 2.283.610 | política + crítico + 2 optimizadores + book keeping | **reanudar entrenamiento** |
| `nachi_2.9B` | `nachi@3dc0a464` `checkpoints/shared/2896166208` | 107 | 1024×3 | 2.302.042 | política + crítico + 2 optimizadores + book keeping | **reanudar entrenamiento** |

SHA256 de cada `PPO_POLICY.pt`:

```
59d99272aca334493a8484eee5d6438b4597d8ad97af4584ecd1af31aadaba47  diego_1.18B_512
e959aca4cb171adac7922d00356112518221f94174465a4ac461aebaa484a2e8  martin_2.1B_1024
74f169281224b444de5d4a7be76be73b74c6aabd20710ef6a8b8819f7b66cb76  marco_2.0B_1024
94be42a4f24bf222bb2d400ebe473d4892e3b2a8733f4e2270eada1e8d0558a8  nachi_2.9B
```

Los cuatro se han inspeccionado con **carga restringida** (`torch.load(...,
weights_only=True)`). En ningún momento se ha usado deserialización arbitraria
para hacer cargar un archivo ajeno.

### Corrección al README de la base

El README de `main` describe el bot de Diego como *AdvancedObs 107 / 1024×3*.
El checkpoint que hemos inspeccionado de esa rama —`MILESTONE_1.18B_nexto_plus_kickoff_512`—
es en realidad **obs 89 (DefaultObs) y 512×3**. No es una contradicción: es un
modelo anterior y distinto del `papaya_1024` que describe la tabla. Se anota para
que nadie deduzca la configuración a partir del README en vez de los pesos.

## Mallas de colisión

Obtenidas de la **distribución oficial de RLGym**, no de una instalación del
juego. No hizo falta instalar Rocket League.

| | |
|---|---|
| Paquete | `rlgym-rocket-league` **2.0.1** (sdist de PyPI) |
| SHA256 del sdist | `3be8e9d2f1cfb6514e0e3d455fb33ff95e26eb7c399f819fff0258025cf4d501` (verificado contra PyPI) |
| Licencia del repositorio RLGym | Apache-2.0 |
| Ruta local | `%LOCALAPPDATA%\rlgym-selfplay-pool\collision_meshes\soccar\` |
| Contenido | 16 archivos `.cmf`, 168 KB (modo soccar) |

Descargado con `pip download --no-deps` y extraído a mano: **no se instalaron sus
dependencias ni se instaló RLGym v2**. Solo se usan los datos `.cmf`; la API del
proyecto (`rlgym_sim`) se mantiene sin tocar.

### Compatibilidad comprobada

- `setup_rocket_league.py` de RLGym declara `rocketsim >=2.0.0,<3.0.0`; nuestro
  pin es 2.2.1, dentro del rango.
- `rsim.init(<ruta>)` es API de RocketSim, no de RLGym v2, y existe en 2.2.1.
- Prueba ejecutada: arena creada, 120 ticks, pelota en reposo a z = 93,15 (radio
  ~92,75, luego la colisión está cargada de verdad).
- En Windows un proceso hijo **no hereda** `rsim.init()`: hay que llamarlo en
  cada trabajador. Comprobado con multiprocessing en modo spawn.

### Condiciones de uso

**Uso local sí; redistribución no.** No se copian al repositorio, no se publican
y no salen de LOCALAPPDATA. No hay declaración de procedencia junto a los
archivos, y son geometría derivada de Rocket League: **su presencia en GitHub no
se interpreta como autorización general para redistribuirlas**, ni se asume que
Apache-2.0 conceda derechos sobre esos datos. El README de la base afirma que no
se pueden compartir; la tensión queda anotada, no resuelta.

### Hashes de las mallas (soccar)

```
8764d43b87ba134cacf1be454d59d493630188e79c0d88639258b359bb511c4e  mesh_0.cmf
9d42e5db7cde5c7be0783c256e15e819bd09351fcb2debd3205e3d055073c993  mesh_1.cmf
36cc44e14a0e500aeb6167a4d5fce449b218b3d941df3ca46f398d269b01af3d  mesh_10.cmf
7f4468be0b0835a48996f92d1a2398f1290acbf1152d39e1c53c2701d1fb6ce3  mesh_11.cmf
952a90a0ff27c2733d507e59bdca8600968276eddad9a41b47a689010e805118  mesh_12.cmf
b441f782f07e81c2444ed7a5c4ed618c26ef3e1940ac2c63c362154620631750  mesh_13.cmf
085f7533c53a73da664c129c3b1c93f5ce08ceb302aa5b993ff5fe95af5d6ae8  mesh_14.cmf
21c1d1eb450f9e09ee8d7d55e1d41bf563518f9b2deb2ab5369c47139faa2e4a  mesh_15.cmf
762ec145db3c317d82314ad94af6f8b591e822c26860ed3c0ee106aba5591eee  mesh_2.cmf
0db5c559287bcd255b99e6f5db341b874ec9a5fcf6137247cf16d913e178db5c  mesh_3.cmf
92c3224da44f1a359140647845a44457df35541458b92485e7a3232bb596566a  mesh_4.cmf
776c24b1231b4f7ab5437af68e4cc1cc4d5cd7875b8cb386a67487162c3941a3  mesh_5.cmf
a2262bfa2bfacca3caf3a8334f02b9b52624056853cc33a1340a23c3a33804e6  mesh_6.cmf
c887df022d6a2b33e78a3cf8f5dd65d9cd61f4d72009781d40c32091119a06f3  mesh_7.cmf
3350567082d9a133f59f8471d941fde6cce20eb2b2bc26c2ab0566b7fb7a21e9  mesh_8.cmf
4864911a7f0a3add929f41cc8f676cde416dcc3c07ab08a30742c9893e8a6ce8  mesh_9.cmf
```

## Dependencias instaladas realmente

El entorno reproducible está en `requirements/lock-2026-09-07.txt`.

`torch==2.13.0+cpu`: es la versión CPU más baja que resuelve **todos** los avisos
de seguridad vigentes con corrección publicada. Subir solo a 2.6.0 habría dejado
abierto CVE-2026-24747 (`< 2.10.0`) y GHSA-rrmf-rvhw-rf47 (`<= 2.12.1`).

`rlgym-tools` **no se instaló**: su `main` es la API v2, incompatible con
`rlgym_sim`, tal y como ya advertía el propio código de la base.

`wandb` entra como dependencia de `rlgym-ppo`. **Sin sesión iniciada y sin envío
de datos**; en el entrenamiento irá con `WANDB_MODE=disabled`.

## Qué NO se ha traído

- **Las mallas de colisión al repositorio**: se usan en local (ver la sección de
  arriba) pero **no se copian aquí ni se publican**.
- **Sesiones ni credenciales de W&B**: los `BOOK_KEEPING_VARS.json` mencionan
  el proyecto y la entidad de sus autores. No se reutiliza ninguna cuenta y el
  registro remoto queda desactivado.
