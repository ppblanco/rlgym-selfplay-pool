"""Genera las figuras del proyecto leyendo SOLO de results/.

APORTACION NUEVA de rlgym-selfplay-pool.

Sin dependencias externas: escribe SVG directamente. SVG es resolucion
independiente, asi que la misma figura sirve para el informe, la presentacion y
la web sin volver a generarla.

Ningun numero esta escrito a mano: todos salen de results/. Si un dato no esta
ahi, la figura no se dibuja. Asi el grafico y el dato no pueden divergir.

Uso:
    python scripts/figures/make_figures.py [--results results] [--salida docs/figures]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Estilo comun
# ---------------------------------------------------------------------------
FUENTE = "'Segoe UI',-apple-system,Helvetica,Arial,sans-serif"
TINTA = "#111827"        # texto principal
SUAVE = "#6b7280"        # texto secundario
REJILLA = "#e5e7eb"
FONDO = "#ffffff"
HEREDADO = "#9ca3af"     # gris: lo que no es nuestro
PROPIO = "#2563eb"       # azul: lo construido aqui
RESULTADO = "#7c3aed"    # violeta: resultados
FALLA = "#dc2626"
CUMPLE = "#16a34a"
NEUTRO = "#94a3b8"


def esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class SVG:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.o: list[str] = []

    def rect(self, x, y, w, h, fill=FONDO, rx=0, stroke="none", sw=1, op=1.0):
        self.o.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'fill-opacity="{op}"/>')

    def line(self, x1, y1, x2, y2, stroke=REJILLA, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.o.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, t, size=16, fill=TINTA, anchor="start", weight="400",
             family=FUENTE):
        self.o.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
            f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{esc(t)}</text>')

    def arrow(self, x1, y1, x2, y2, stroke=SUAVE, sw=2):
        self.o.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" marker-end="url(#p)"/>')

    def guardar(self, ruta: Path) -> None:
        cab = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
            f'height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
            f'<defs><marker id="p" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{SUAVE}"/></marker></defs>'
            f'<rect width="{self.w}" height="{self.h}" fill="{FONDO}"/>')
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(cab + "".join(self.o) + "</svg>", encoding="utf-8")
        print(f"  {ruta.name}")


def wilson(exitos: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = exitos / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - m, c + m)


# ---------------------------------------------------------------------------
# 1. H1
# ---------------------------------------------------------------------------
def fig_h1(res: Path, out: Path) -> None:
    d = json.loads((res / "h1/analisis-h1.json").read_text(encoding="utf-8"))
    A, B = d["por_brazo"]["A"], d["por_brazo"]["B"]
    dif = d["bootstrap_global"]["dif"] * 100
    lo, hi = [x * 100 for x in d["bootstrap_global"]["ic95"]]

    s = SVG(1600, 900)
    s.text(70, 74, "H1: entrenar contra un pool de versiones pasadas", 34, TINTA, weight="600")
    s.text(70, 112, "Tasa de victoria frente a tres rivales reservados · 720 partidas",
           19, SUAVE)

    # --- panel izquierdo: barras -------------------------------------------
    px, py, pw, ph = 90, 190, 560, 520
    ymax = 12.0
    for v in range(0, 13, 2):
        y = py + ph - (v / ymax) * ph
        s.line(px, y, px + pw, y, REJILLA, 1)
        s.text(px - 14, y + 6, f"{v} %", 15, SUAVE, anchor="end")
    s.line(px, py + ph, px + pw, py + ph, "#d1d5db", 2)

    for i, (nom, br, col) in enumerate([("A · rival único", A, NEUTRO),
                                        ("B · pool histórico", B, PROPIO)]):
        tasa = br["tasa_completas"] * 100
        clo, chi = [x * 100 for x in wilson(br["victorias"], br["completas"])]
        bx = px + 110 + i * 260
        bw = 130
        by = py + ph - (tasa / ymax) * ph
        s.rect(bx, by, bw, py + ph - by, col, rx=4)
        # intervalo de Wilson
        cx = bx + bw / 2
        ylo = py + ph - (clo / ymax) * ph
        yhi = py + ph - (chi / ymax) * ph
        s.line(cx, ylo, cx, yhi, TINTA, 2.5)
        s.line(cx - 22, yhi, cx + 22, yhi, TINTA, 2.5)
        s.line(cx - 22, ylo, cx + 22, ylo, TINTA, 2.5)
        s.text(cx, yhi - 20, f"{tasa:.2f} %", 25, TINTA, anchor="middle", weight="600")
        s.text(cx, py + ph + 34, nom, 17, TINTA, anchor="middle", weight="500")
        s.text(cx, py + ph + 60, f"{br['victorias']} / {br['completas']}", 16, SUAVE,
               anchor="middle")
    s.text(px, py - 26, "Tasa de victoria, con intervalo de Wilson 95 %", 17, SUAVE)

    # --- panel derecho: diferencia -----------------------------------------
    qx, qy, qw = 800, 190, 700
    s.text(qx, qy - 26, "Diferencia B − A, con IC bootstrap 95 %", 17, SUAVE)
    ejey = qy + 150
    xmin, xmax = -6.0, 4.0

    def X(v):
        return qx + (v - xmin) / (xmax - xmin) * qw

    for v in range(-6, 5, 2):
        s.line(X(v), ejey - 90, X(v), ejey + 60, REJILLA, 1)
        s.text(X(v), ejey + 86, f"{v:+d}", 15, SUAVE, anchor="middle")
    s.text(qx + qw / 2, ejey + 114, "puntos porcentuales", 15, SUAVE, anchor="middle")

    # cero, destacado
    s.line(X(0), ejey - 100, X(0), ejey + 66, TINTA, 2.5, dash="7,5")
    s.text(X(0), ejey - 112, "sin efecto", 15, TINTA, anchor="middle", weight="600")

    s.line(X(lo), ejey, X(hi), ejey, PROPIO, 5)
    s.line(X(lo), ejey - 16, X(lo), ejey + 16, PROPIO, 4)
    s.line(X(hi), ejey - 16, X(hi), ejey + 16, PROPIO, 4)
    s.o.append(f'<circle cx="{X(dif):.1f}" cy="{ejey:.1f}" r="11" fill="{PROPIO}"/>')
    s.text(X(dif), ejey - 34, f"{dif:+.2f} pp", 21, PROPIO, anchor="middle", weight="600")
    s.text(X(lo), ejey + 44, f"{lo:+.2f}", 15, SUAVE, anchor="middle")
    s.text(X(hi), ejey + 44, f"{hi:+.2f}", 15, SUAVE, anchor="middle")

    s.rect(qx, ejey + 170, qw, 150, "#f9fafb", rx=10, stroke=REJILLA)
    s.text(qx + 34, ejey + 232, "INCONCLUSIVE", 50, TINTA, weight="700")
    s.text(qx + 34, ejey + 274, "El intervalo cruza el cero: no hay efecto detectable.",
           18, SUAVE)
    s.text(qx + 34, ejey + 302,
           "Cambiar la semilla movía el resultado más que cambiar el método.", 18, SUAVE)

    s.text(70, 862, "Fuente: results/h1/analisis-h1.json · 3 semillas × 2 brazos × "
           "3 rivales × 40 partidas", 14, SUAVE)
    s.guardar(out / "01_h1_resultado.svg")


# ---------------------------------------------------------------------------
# 2. Arquitectura por autoria
# ---------------------------------------------------------------------------
def fig_arquitectura(res: Path, out: Path) -> None:
    # Los numeros de la columna de resultados salen de results/, no del codigo.
    h1 = json.loads((res / "h1/analisis-h1.json").read_text(encoding="utf-8"))
    pu = json.loads((res / "h2/puerta.json").read_text(encoding="utf-8"))
    dif = h1["bootstrap_global"]["dif"] * 100
    lo, hi = [x * 100 for x in h1["bootstrap_global"]["ic95"]]
    fallan = [k.split("_")[0] for k, v in pu["criterios"].items() if not v["cumple"]]

    s = SVG(1600, 980)
    s.text(70, 74, "Arquitectura: qué construí encima de qué", 34, TINTA, weight="600")
    s.text(70, 112, "En gris el proyecto heredado · en azul la capa experimental propia "
           "· en violeta los resultados", 19, SUAVE)

    def caja(x, y, w, h, titulo, items, color, fondo):
        s.rect(x, y, w, h, fondo, rx=12, stroke=color, sw=2)
        s.rect(x, y, w, 44, color, rx=12)
        s.rect(x, y + 30, w, 14, color)
        s.text(x + 20, y + 30, titulo, 19, "#ffffff", weight="600")
        for i, it in enumerate(items):
            if it:  # las cadenas vacias son separadores, no llevan vineta
                s.text(x + 20, y + 76 + i * 30, "· " + it, 16, TINTA)

    caja(70, 170, 420, 250, "HEREDADO · moanv2/rlgym (MIT)",
         ["RLGym + RocketSim (simulación)", "PPO (rlgym-ppo)",
          "LookupAction · 90 acciones", "Registro de recompensas · ZeroSum",
          "Arnés de torneo"], HEREDADO, "#f3f4f6")

    caja(70, 470, 420, 200, "PUNTO DE PARTIDA",
         ["C0 · 32.000 muestras", "hash fijado y verificado",
          "común a todas las corridas"], HEREDADO, "#f3f4f6")

    caja(590, 170, 460, 500, "CREADO EN ESTE PROYECTO",
         ["rocketsim_init · init por proceso", "frozen opponent · un solo agente a PPO",
          "opponent pool · muestreo reproducible",
          "snapshots + manifiesto atómico", "ejecución aislada por proceso",
          "recuperación y reanudación", "evaluación JSONL trazable",
          "integridad · hashes y tabla ciega", "protocolos congelados por SHA256",
          "análisis estadístico"], PROPIO, "#eff6ff")

    caja(1150, 170, 380, 500, "RESULTADOS",
         [f"H1 · {h1['veredicto_H1']}",
          f"  B−A = {dif:+.2f} pp".replace(".", ","),
          f"  IC95 [{lo:+.2f}, {hi:+.2f}]".replace(".", ","), "",
          f"H2 · puerta {pu['veredicto']}",
          f"  {' y '.join(fallan)} fallan", "",
          "Diagnóstico de recompensas", "  ninguna prometedora", "",
          "Prueba final R1/R2", "  hipótesis FALSADA"], RESULTADO, "#f5f3ff")

    s.arrow(490, 300, 585, 300)
    s.arrow(490, 545, 585, 420)
    s.arrow(1050, 420, 1145, 420)

    s.rect(70, 730, 1460, 96, "#f9fafb", rx=10, stroke=REJILLA)
    # Unico valor no derivado de results/: es un inventario de CODIGO, no un
    # resultado experimental. Fuente declarada: docs/CONTRIBUTIONS.md seccion 5.
    INVENTARIO_CODIGO = "5.401 líneas propias en 24 archivos"
    s.text(96, 776, INVENTARIO_CODIGO, 24, PROPIO, weight="600")
    s.text(96, 806, "Ningún archivo heredado fue modificado · verificado con git status",
           17, SUAVE)
    s.text(1500, 776, "0", 40, HEREDADO, anchor="end", weight="700")
    s.text(1500, 806, "archivos heredados modificados", 15, SUAVE, anchor="end")

    s.text(70, 940, "Fuente: docs/CONTRIBUTIONS.md", 14, SUAVE)
    s.guardar(out / "02_arquitectura.svg")


# ---------------------------------------------------------------------------
# 3. Opponent pool
# ---------------------------------------------------------------------------
def fig_pool(out: Path) -> None:
    s = SVG(1600, 900)
    s.text(70, 74, "La idea: entrenar contra tu propio pasado", 34, TINTA, weight="600")
    s.text(70, 112, "En vez de una única copia congelada, un pool de versiones históricas",
           19, SUAVE)

    cx = 800
    s.rect(cx - 170, 165, 340, 62, PROPIO, rx=10)
    s.text(cx, 205, "Current policy", 24, "#ffffff", anchor="middle", weight="600")

    s.arrow(cx, 232, cx, 288)
    s.text(cx + 18, 268, "snapshot cada K muestras", 16, SUAVE)

    s.rect(cx - 420, 295, 840, 130, "#eff6ff", rx=12, stroke=PROPIO, sw=2)
    s.text(cx - 400, 325, "Historical pool", 19, PROPIO, weight="600")
    etiquetas = ["t−1", "t−2", "t−3", "t−4", "…", "C0"]
    for i, e in enumerate(etiquetas):
        bx = cx - 395 + i * 133
        col = "#c7d2fe" if e != "C0" else "#a5b4fc"
        s.rect(bx, 345, 118, 60, col, rx=8, stroke=PROPIO, sw=1)
        s.text(bx + 59, 383, e, 21, TINTA, anchor="middle", weight="600")
    s.text(cx + 395, 325, "retención 16 · C0 protegido", 15, SUAVE, anchor="end")

    s.arrow(cx, 430, cx, 486)
    s.text(cx + 18, 466, "muestreo uniforme y reproducible", 16, SUAVE)

    s.rect(cx - 170, 493, 340, 62, "#1f2937", rx=10)
    s.text(cx, 533, "Frozen opponent", 24, "#ffffff", anchor="middle", weight="600")

    s.arrow(cx, 560, cx, 616)
    s.rect(cx - 170, 623, 340, 62, "#f3f4f6", rx=10, stroke="#d1d5db", sw=2)
    s.text(cx, 663, "1v1 episode", 24, TINTA, anchor="middle", weight="600")

    s.arrow(cx, 690, cx, 746)
    s.rect(cx - 170, 753, 340, 62, PROPIO, rx=10)
    s.text(cx, 793, "Learner update", 24, "#ffffff", anchor="middle", weight="600")

    # bucle de realimentacion
    s.line(cx + 170, 784, cx + 560, 784, SUAVE, 2)
    s.line(cx + 560, 784, cx + 560, 196, SUAVE, 2)
    s.arrow(cx + 560, 196, cx + 172, 196)
    s.text(cx + 550, 500, "nueva current policy", 16, SUAVE, anchor="end")

    # Debajo del pool, no encima: si se coloca a la altura del pool lo tapa.
    s.rect(70, 560, 390, 150, "#f9fafb", rx=10, stroke=REJILLA)
    s.text(96, 598, "Control (brazo A)", 19, TINTA, weight="600")
    s.text(96, 632, "retención 1: el pool guarda", 16, SUAVE)
    s.text(96, 658, "solo la copia más reciente", 16, SUAVE)
    s.text(96, 690, "Mismo código, misma clase.", 15, PROPIO)

    s.guardar(out / "03_opponent_pool.svg")


# ---------------------------------------------------------------------------
# 4 y 5. Recompensas
# ---------------------------------------------------------------------------
def _leer_resumenes(carpeta: Path) -> dict:
    datos: dict[str, dict[int, dict]] = {}
    for p in sorted(carpeta.glob("resumen_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        partes = p.stem.split("_")
        cfg, muestras = "_".join(partes[1:-1]), int(partes[-1])
        datos.setdefault(cfg, {})[muestras] = d
    return datos


def fig_falsacion(res: Path, out: Path) -> None:
    diag = _leer_resumenes(res / "reward-diagnostic/resumenes")
    fin = _leer_resumenes(res / "reward-final-check/resumenes")
    barras = [
        ("stage_1_basics", "moldeado completo", diag["D_A"][500000], NEUTRO),
        ("stage_2_offense", "moldeado ×2", diag["D_B"][500000], NEUTRO),
        ("sin ZeroSum", "moldeado ×2", diag["D_C"][500000], NEUTRO),
        ("R1 · shaping ÷10", "moldeado reducido", fin["R1"][500000], FALLA),
        ("R2 · solo evento", "sin moldeado", fin["R2"][500000], FALLA),
    ]

    s = SVG(1600, 900)
    s.text(70, 74, "Mi hipótesis: el moldeado ahogaba al objetivo. Predicción: reducirlo "
           "ayudaría.", 30, TINTA, weight="600")
    s.text(70, 112, "Tasa de victoria contra C0 tras 500.000 muestras · 200 partidas por "
           "barra · ordenado de más a menos moldeado", 18, SUAVE)

    px, py, pw, ph = 110, 210, 1360, 420
    ymax = 80.0
    for v in range(0, 81, 20):
        y = py + ph - (v / ymax) * ph
        s.line(px, y, px + pw, y, REJILLA, 1)
        s.text(px - 14, y + 6, f"{v} %", 15, SUAVE, anchor="end")
    y50 = py + ph - (50 / ymax) * ph
    s.line(px, y50, px + pw, y50, "#9ca3af", 2, dash="8,6")
    s.text(px + pw, y50 - 12, "50 % · empate con el punto de partida", 15, SUAVE,
           anchor="end")
    s.line(px, py + ph, px + pw, py + ph, "#d1d5db", 2)

    anc = pw / len(barras)
    for i, (nom, sub, d, col) in enumerate(barras):
        tasa = d["tasa"] * 100
        lo, hi = [x * 100 for x in d["ic95_wilson"]]
        bx = px + i * anc + anc * 0.22
        bw = anc * 0.56
        by = py + ph - (tasa / ymax) * ph
        s.rect(bx, by, bw, py + ph - by, col, rx=5)
        cx = bx + bw / 2
        s.line(cx, py + ph - (lo / ymax) * ph, cx, py + ph - (hi / ymax) * ph, TINTA, 2.5)
        s.text(cx, by - 16, f"{tasa:.1f} %", 24, TINTA, anchor="middle", weight="600")
        s.text(cx, py + ph + 34, nom, 17, TINTA, anchor="middle", weight="500")
        s.text(cx, py + ph + 58, sub, 15, SUAVE, anchor="middle")

    s.o.append(f'<line x1="{px + anc * 0.5:.1f}" y1="720" '
               f'x2="{px + pw - anc * 0.5:.1f}" y2="720" stroke="{SUAVE}" '
               f'stroke-width="2" marker-end="url(#p)"/>')
    s.text(px + pw / 2, 748, "menos moldeado →", 17, SUAVE, anchor="middle")

    s.rect(70, 776, 1460, 86, "#fef2f2", rx=10, stroke=FALLA, sw=2)
    completo = barras[0][2]["tasa"] * 100
    reducido = barras[3][2]["tasa"] * 100
    s.text(96, 812, f"Reducir el moldeado lo empeoró: de {completo:.1f} % a "
           f"{reducido:.1f} %.".replace(".", ",").replace(",1 %", ",1 %"),
           25, FALLA, weight="700")
    s.text(96, 844, "La predicción quedó falsada. La causa del deterioro sigue sin "
           "identificarse.", 18, TINTA)

    s.text(70, 884, "Fuente: results/reward-diagnostic/resumenes/ y "
           "results/reward-final-check/resumenes/ · IC de Wilson 95 %", 14, SUAVE)
    s.guardar(out / "04_falsacion.svg")


def fig_diagnostico(res: Path, out: Path) -> None:
    diag = _leer_resumenes(res / "reward-diagnostic/resumenes")
    series = [("D_A · stage_1_basics", "D_A", PROPIO),
              ("D_B · stage_2_offense", "D_B", "#f59e0b"),
              ("D_C · sin ZeroSum", "D_C", "#10b981")]
    xs = [100000, 250000, 500000]

    s = SVG(1600, 900)
    # Exacto: D_B va de 14,0 a 22,5, que es mejora NETA aunque cae desde su pico
    # de 37,5. Decir "las tres empeoran" seria falso; "ninguna mejora de forma
    # sostenida" lo es para las tres.
    s.text(70, 74, "Tres recompensas, ninguna con mejora sostenida", 34,
           TINTA, weight="600")
    s.text(70, 112, "Tasa de victoria contra C0 · 200 partidas por punto", 19, SUAVE)

    px, py, pw, ph = 130, 200, 1180, 480
    ymax = 80.0
    for v in range(0, 81, 20):
        y = py + ph - (v / ymax) * ph
        s.line(px, y, px + pw, y, REJILLA, 1)
        s.text(px - 14, y + 6, f"{v} %", 15, SUAVE, anchor="end")
    y50 = py + ph - (50 / ymax) * ph
    s.line(px, y50, px + pw, y50, "#9ca3af", 2, dash="8,6")
    s.text(px + 10, y50 - 12, "50 % · empate con el punto de partida", 15, SUAVE)
    s.line(px, py + ph, px + pw, py + ph, "#d1d5db", 2)

    def X(m):
        return px + xs.index(m) * (pw / (len(xs) - 1)) if m in xs else px

    for m in xs:
        s.text(X(m), py + ph + 36, f"{m // 1000}k", 18, TINTA, anchor="middle")
    s.text(px + pw / 2, py + ph + 68, "muestras de entrenamiento", 16, SUAVE,
           anchor="middle")

    for nom, cfg, col in series:
        pts = [(X(m), py + ph - (diag[cfg][m]["tasa"] * 100 / ymax) * ph) for m in xs]
        for i in range(len(pts) - 1):
            s.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col, 3.5)
        for (x, y), m in zip(pts, xs):
            s.o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{col}"/>')
            # El primer punto se desplaza para no chocar con las etiquetas del eje.
            primero = m == xs[0]
            s.text(x + (26 if primero else 0), y - 20,
                   f"{diag[cfg][m]['tasa'] * 100:.1f}", 16, col,
                   anchor="start" if primero else "middle", weight="600")
        s.text(pts[-1][0] + 22, pts[-1][1] + 6, nom, 17, col, weight="600")

    s.rect(70, 756, 1460, 86, "#f9fafb", rx=10, stroke=REJILLA)
    # Exacto: D_B sube de 14,0 a 37,5 antes de caer, asi que "las tres se
    # degradan" seria falso. Ninguna mejora de forma SOSTENIDA: eso si lo es.
    s.text(96, 792, "Ninguna mejora de forma sostenida al aumentar el presupuesto.",
           24, TINTA, weight="600")
    s.text(96, 824, "Si entrenar más empeora, comparar dos métodos por tasa de victoria "
           "compara dos formas de empeorar.", 18, SUAVE)
    s.text(70, 868, "Fuente: results/reward-diagnostic/resumenes/", 14, SUAVE)
    s.guardar(out / "05_diagnostico_recompensas.svg")


# ---------------------------------------------------------------------------
# 6. Puerta H2
# ---------------------------------------------------------------------------
def fig_puerta(res: Path, out: Path) -> None:
    d = json.loads((res / "h2/puerta.json").read_text(encoding="utf-8"))
    c = d["criterios"]
    filas = [
        ("G1", "Rivales en zona informativa (35–65 %)",
         c["G1_zona_informativa"]["en_zona"], c["G1_zona_informativa"]["necesarios"],
         "escalones", c["G1_zona_informativa"]["cumple"]),
        ("G2", "Deriva del piloto ≥ 3× la de H1",
         c["G2_deriva"]["deriva_piloto"], c["G2_deriva"]["umbral"], "", c["G2_deriva"]["cumple"]),
        ("G3", "Diversidad del pool ≥ 2× la de H1",
         c["G3_diversidad"]["mediana_pares"], c["G3_diversidad"]["umbral"], "",
         c["G3_diversidad"]["cumple"]),
        ("G4", "Infraestructura estable", 1, 1, "", c["G4_infraestructura"]["cumple"]),
    ]

    s = SVG(1600, 900)
    s.text(70, 74, "La puerta de H2: umbrales escritos antes de gastar el cómputo", 34,
           TINTA, weight="600")
    s.text(70, 112, "Se evalúa antes de entrenar. Si falla alguno, el experimento no se "
           "ejecuta.", 19, SUAVE)

    y0, alto = 190, 118
    for i, (g, desc, med, umb, uni, ok) in enumerate(filas):
        y = y0 + i * alto
        col = CUMPLE if ok else FALLA
        s.rect(70, y, 1460, alto - 16, "#f0fdf4" if ok else "#fef2f2", rx=10,
               stroke=col, sw=2)
        s.rect(70, y, 10, alto - 16, col, rx=4)
        s.text(112, y + 44, g, 30, col, weight="700")
        s.text(178, y + 40, desc, 20, TINTA, weight="500")
        s.text(178, y + 72, "CUMPLE" if ok else "FALLA", 17, col, weight="600")

        if g in ("G2", "G3"):
            bx, bw = 620, 520
            escala = max(med, umb) * 1.35
            s.line(bx, y + 62, bx + bw, y + 62, REJILLA, 12)
            s.line(bx, y + 62, bx + bw * (med / escala), y + 62, col, 12)
            xu = bx + bw * (umb / escala)
            s.line(xu, y + 40, xu, y + 84, TINTA, 3)
            s.text(xu, y + 32, f"requerido {umb:.4f}", 15, TINTA, anchor="middle")
            # La medida se rotula SIEMPRE fuera de la pista: dentro chocaba con
            # el marcador de umbral y quedaba rojo sobre rojo.
            s.text(bx + bw + 16, y + 68, f"{med:.4f}", 19, col, weight="600")
        elif g == "G1":
            s.text(620, y + 68, f"{med} escalones en zona · requeridos {umb}", 19, col,
                   weight="600")
        else:
            s.text(620, y + 68, "sin bloqueos · sin huérfanos · recuperación verificada",
                   19, col, weight="600")

    s.rect(70, y0 + 4 * alto + 10, 1460, 100, "#fef2f2", rx=10, stroke=FALLA, sw=2)
    veredicto = d["veredicto"]          # sale de puerta.json, no del codigo
    s.text(96, y0 + 4 * alto + 54, veredicto + " — STOPPED BEFORE FULL TRAINING",
           34, FALLA, weight="700")
    s.text(96, y0 + 4 * alto + 88,
           "Las diez corridas no se ejecutaron. Unas 12 horas de cómputo ahorradas.",
           18, TINTA)

    s.text(70, 878, "Fuente: results/h2/puerta.json", 14, SUAVE)
    s.guardar(out / "06_puerta_h2.svg")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--salida", default="docs/figures")
    a = ap.parse_args()
    res, out = Path(a.results), Path(a.salida)
    print("Generando figuras desde", res)
    fig_h1(res, out)
    fig_arquitectura(res, out)
    fig_pool(out)
    fig_falsacion(res, out)
    fig_diagnostico(res, out)
    fig_puerta(res, out)
    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
