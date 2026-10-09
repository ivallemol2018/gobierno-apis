#!/usr/bin/env python3
"""Evalúa el reporte de verificación semántica generado por Copilot CLI.

Uso: evaluar_reporte.py <reporte.json> <resumen.md> [BLOQUEANTE|MEJORA] [salida-copilot.log]

Si <reporte.json> no existe o no es válido, intenta recuperar el JSON
desde la salida de Copilot CLI (último objeto con la clave `hallazgos`).

Códigos de salida:
  0  sin hallazgos al nivel de fallo
  1  hay hallazgos al nivel de fallo (el check debe fallar)
  2  reporte ausente o inválido (fail-closed)

Los conteos se calculan aquí a partir de los hallazgos; no se confía en
ningún resumen que el modelo pudiera escribir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SEVERIDADES = ("BLOQUEANTE", "MEJORA")
RANGO = {"BLOQUEANTE": 2, "MEJORA": 1}


def escapar_anotacion(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escapar_propiedad(texto: str) -> str:
    return escapar_anotacion(texto).replace(":", "%3A").replace(",", "%2C")


def celda(texto) -> str:
    return str(texto or "").replace("|", "\\|").replace("\n", " ").strip()


def extraer_json(texto: str):
    """Devuelve el último objeto JSON con clave `hallazgos` presente en el texto.

    Tolera bloques ```json, texto antes/después y salida con otros mensajes."""
    decodificador = json.JSONDecoder()
    encontrado = None
    i = texto.find("{")
    while i != -1:
        try:
            obj, fin = decodificador.raw_decode(texto, i)
        except json.JSONDecodeError:
            i = texto.find("{", i + 1)
            continue
        if isinstance(obj, dict) and "hallazgos" in obj:
            encontrado = obj
        i = texto.find("{", fin)
    return encontrado


def leer(ruta: Path):
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def cargar(ruta: Path, salida: Path | None):
    datos, origen, problemas = None, None, []

    texto = leer(ruta) if ruta.is_file() else None
    if texto is None:
        problemas.append(f"Copilot CLI no escribió `{ruta}`.")
    elif not texto.strip():
        problemas.append(f"`{ruta}` está vacío.")
    else:
        datos = extraer_json(texto)
        if datos is None:
            problemas.append(f"`{ruta}` no contiene un JSON con la clave `hallazgos`.")
        else:
            origen = str(ruta)

    if datos is None and salida is not None and salida.is_file():
        datos = extraer_json(leer(salida) or "")
        if datos is not None:
            origen = f"respuesta de Copilot CLI ({salida})"
            print(f"::warning::Copilot no escribió un reporte válido en {ruta}; se usó el JSON de su respuesta.")
        else:
            problemas.append(f"La respuesta de Copilot CLI (`{salida}`) tampoco contiene el JSON del reporte.")

    if datos is None:
        return None, " ".join(problemas), None
    if not isinstance(datos.get("hallazgos"), list):
        return None, "El reporte no tiene la clave `hallazgos` como lista.", None

    validos = []
    for i, h in enumerate(datos["hallazgos"]):
        if not isinstance(h, dict):
            return None, f"El hallazgo #{i + 1} no es un objeto.", None
        sev = str(h.get("severidad", "")).strip().upper()
        if sev not in SEVERIDADES:
            return None, f"El hallazgo #{i + 1} tiene severidad inválida: {h.get('severidad')!r}.", None
        if not h.get("archivo") or not h.get("mensaje"):
            return None, f"El hallazgo #{i + 1} no indica `archivo` o `mensaje`.", None
        h["severidad"] = sev
        validos.append(h)
    return validos, None, origen


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    reporte, resumen = Path(sys.argv[1]), Path(sys.argv[2])
    nivel = (sys.argv[3] if len(sys.argv) > 3 else "BLOQUEANTE").upper()
    salida = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    if nivel not in RANGO:
        print(f"::error::NIVEL_FALLO inválido: {nivel}")
        return 2

    hallazgos, error, origen = cargar(reporte, salida)
    if error:
        print(f"::error::{escapar_anotacion(error)}")
        resumen.write_text(
            "## ❌ Verificación semántica: sin reporte válido\n\n"
            f"{error}\n\nEl check falla por seguridad (fail-closed). "
            "Revisa en el log del paso *Ejecutar verificación semántica con Copilot CLI* el código de salida "
            "y las últimas líneas de la respuesta, o descarga el artefacto `verificacion-semantica` "
            "(`copilot-salida.log`, `copilot-sesion.md`).\n",
            encoding="utf-8",
        )
        return 2

    hallazgos.sort(key=lambda h: (-RANGO[h["severidad"]], str(h["archivo"]), h.get("linea") or 0))
    n_bloq = sum(h["severidad"] == "BLOQUEANTE" for h in hallazgos)
    n_mej = len(hallazgos) - n_bloq
    falla = any(RANGO[h["severidad"]] >= RANGO[nivel] for h in hallazgos)

    # Anotaciones en la pestaña "Files changed" del PR
    for h in hallazgos:
        tipo = "error" if h["severidad"] == "BLOQUEANTE" else "warning"
        props = f"file={escapar_propiedad(str(h['archivo']))}"
        if isinstance(h.get("linea"), int) and h["linea"] > 0:
            props += f",line={h['linea']}"
        props += f",title={escapar_propiedad('Semántica: ' + str(h.get('regla') or h['severidad']))}"
        cuerpo = str(h["mensaje"])
        if h.get("sugerencia"):
            cuerpo += f"\nSugerencia: {h['sugerencia']}"
        print(f"::{tipo} {props}::{escapar_anotacion(cuerpo)}")

    icono = "❌" if falla else ("⚠️" if hallazgos else "✅")
    estado = "no aprobada" if falla else "aprobada"
    lineas = [
        f"## {icono} Verificación semántica {estado}",
        "",
        f"**{len(hallazgos)} hallazgos** (bloqueantes: {n_bloq}, mejoras: {n_mej}). "
        f"El check falla con severidad **{nivel}** o superior.",
        "",
    ]
    if hallazgos:
        lineas += [
            "| Severidad | Archivo | Ubicación | Regla | Hallazgo | Sugerencia |",
            "|---|---|---|---|---|---|",
        ]
        for h in hallazgos:
            archivo = celda(h["archivo"]) + (f":{h['linea']}" if isinstance(h.get("linea"), int) else "")
            lineas.append(
                f"| {'🔴' if h['severidad'] == 'BLOQUEANTE' else '🟡'} {h['severidad']} "
                f"| `{archivo}` | `{celda(h.get('ubicacion'))}` | {celda(h.get('regla'))} "
                f"| {celda(h['mensaje'])} | {celda(h.get('sugerencia'))} |"
            )
    else:
        lineas.append("Los contratos modificados cumplen las reglas semánticas.")
    lineas += ["", "<sub>Generado por Copilot CLI con las reglas y el glosario corporativo del repositorio `gobierno-apis`.</sub>"]
    resumen.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    return 1 if falla else 0


if __name__ == "__main__":
    sys.exit(main())
