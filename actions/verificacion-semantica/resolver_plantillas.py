#!/usr/bin/env python3
"""Resuelve la plantilla BIAN de cada contrato SYNC del PR.

Un contrato se compara con plantilla cuando su `info.title` sigue el formato
`API BS <ServiceDomainBian> <DominioFederado> V<n>` (p. ej. `API BS CustomerOffer Retail V1`).
Para él:
  1. Deriva el repositorio de la plantilla desde el Service Domain
     (CustomerOffer → bcp-api-template-customer-offer) y busca en su carpeta `api/`
     los archivos que cumplen el patrón (business-customer-offer-<xxxxxx>.yaml).
  2. Descarga la plantilla y genera un índice de sus operaciones.
  3. Calcula qué endpoints (y schemas) cambió el PR comparando base y head.

Salidas en --salida-dir:
  contexto.md            → texto que se inserta en el prompt de Copilot ($PLANTILLAS)
  hallazgos-previos.json → hallazgos deterministas (plantilla inexistente, título mal formado, configuración)
  archivos/<repo>/...    → plantillas descargadas (Copilot las lee con `cat`)

Variables de entorno: PLANTILLAS_TOKEN (lectura de los repos de plantilla), GITHUB_API_URL.
Siempre termina con código 0: los problemas se reportan como hallazgos (fail-closed vía BLOQUEANTE).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import yaml  # PyYAML (preinstalado en los runners ubuntu de GitHub)
except ImportError:  # pragma: no cover - el action intenta instalarlo
    yaml = None

REGLA = "Conformidad con la plantilla BIAN"
FORMATO = re.compile(
    r"^\s*API\s+BS\s+(?P<sd>\S+)\s+(?P<dominio>\S+)\s+V(?P<version>\d+)\s*$", re.IGNORECASE
)
METODOS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
MAX_ARCHIVOS = 3


def anotar(tipo: str, mensaje: str) -> None:
    print(f"::{tipo}::" + mensaje.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"))


def kebab(nombre: str) -> str:
    """CustomerOffer → customer-offer; ATMNetworkOperations → atm-network-operations."""
    s = re.sub(r"[_\s]+", "-", nombre.strip())
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", s)
    return re.sub(r"-+", "-", s).strip("-").lower()


def cargar(texto: str | None):
    if not texto:
        return None
    try:
        doc = json.loads(texto)
        return doc if isinstance(doc, dict) else None
    except ValueError:
        pass
    if yaml is None:
        return None
    try:
        doc = yaml.safe_load(texto)
        return doc if isinstance(doc, dict) else None
    except yaml.YAMLError:
        return None


def leer_titulo(texto: str, doc) -> str | None:
    if doc is not None:
        info = doc.get("info")
        if isinstance(info, dict) and info.get("title") is not None:
            return str(info["title"])
        return None
    # Sin parser: primer `title:` dentro del bloque `info:` (YAML) o "title" (JSON).
    bloque = re.search(r"^info:[ \t]*\n((?:[ \t]+.*(?:\n|$))+)", texto, re.M)
    if bloque:
        t = re.search(r"^[ \t]+title:[ \t]*(['\"]?)(.*?)\1[ \t]*$", bloque.group(1), re.M)
        if t:
            return t.group(2)
    t = re.search(r'"info"\s*:\s*\{[^{}]*?"title"\s*:\s*"([^"]*)"', texto, re.S)
    return t.group(1) if t else None


def linea_titulo(texto: str) -> int | None:
    for i, linea in enumerate(texto.splitlines(), 1):
        if re.match(r'^\s*"?title"?\s*:', linea):
            return i
    return None


def operaciones(doc) -> dict:
    res = {}
    for ruta, item in ((doc or {}).get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for m in METODOS:
            if isinstance(item.get(m), dict):
                res[(m.upper(), str(ruta))] = {"operacion": item[m], "parametros": item.get("parameters")}
    return res


def firma(x) -> str:
    return json.dumps(x, sort_keys=True, default=str)


def cambios(base, head):
    b, h = operaciones(base), operaciones(head)
    ops = []
    for clave in sorted(h, key=lambda k: (k[1], k[0])):
        if clave not in b:
            ops.append((clave[0], clave[1], "nuevo"))
        elif firma(b[clave]) != firma(h[clave]):
            ops.append((clave[0], clave[1], "modificado"))
    bs = ((base or {}).get("components") or {}).get("schemas") or {}
    hs = ((head or {}).get("components") or {}).get("schemas") or {}
    schemas = [n for n in sorted(hs) if n not in bs or firma(bs[n]) != firma(hs[n])]
    return ops, schemas


def segmentos(ruta: str, sd_k: str) -> list[str]:
    """Segmentos comparables de una ruta: sin base path y con parámetros normalizados.

    /customer-offer/v1/customer-offer-procedures/{customerOfferProcedureId}/initiate
    → ['customer-offer-procedures', '{}', 'initiate']
    Se elimina todo hasta el segmento de versión (vN) entre los 3 primeros; si no hay versión,
    se elimina el Service Domain inicial.
    """
    segs = [s for s in ruta.strip("/").lower().split("/") if s]
    for i, s in enumerate(segs[:3]):
        if re.fullmatch(r"v\d+", s):
            segs = segs[i + 1:]
            break
    else:
        if segs and segs[0] == sd_k:
            segs = segs[1:]
    return ["{}" if s.startswith("{") else s for s in segs]


def correspondencia(metodo: str, ruta: str, ops_plantilla: list[tuple[str, str]], sd_k: str):
    """Compara un endpoint del contrato con las operaciones de la plantilla.

    Devuelve (estado, operaciones): estado ∈ coincide | verbo-distinto | sin-coincidencia.
    """
    c = segmentos(ruta, sd_k)
    misma_ruta = [(m, r) for m, r in ops_plantilla if segmentos(r, sd_k) == c]
    exactas = [(m, r) for m, r in misma_ruta if m == metodo]
    if exactas:
        return "coincide", exactas
    if misma_ruta:
        return "verbo-distinto", misma_ruta

    fijos_c = [s for s in c if s != "{}"]

    def puntaje(op):
        m, r = op
        fijos_t = [s for s in segmentos(r, sd_k) if s != "{}"]
        return (2 * len(set(fijos_c) & set(fijos_t))
                + (2 if fijos_c[-1:] == fijos_t[-1:] else 0)
                + (1 if m == metodo else 0))

    parecidas = [op for op in sorted(ops_plantilla, key=puntaje, reverse=True) if puntaje(op) >= 2][:2]
    return "sin-coincidencia", parecidas


def indice(doc) -> list[str]:
    lineas = []
    for (metodo, ruta), datos in sorted(operaciones(doc).items(), key=lambda kv: (kv[0][1], kv[0][0])):
        op = datos["operacion"]
        detalle = " — ".join(
            str(x).strip().replace("\n", " ")[:120] for x in (op.get("operationId"), op.get("summary")) if x
        )
        lineas.append(f"  - `{metodo} {ruta}`" + (f" — {detalle}" if detalle else ""))
    return lineas


class GitHub:
    def __init__(self, url: str, token: str):
        self.url, self.token = url.rstrip("/"), token

    def get(self, ruta: str, raw: bool = False):
        req = urllib.request.Request(
            self.url + ruta,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "verificacion-semantica",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except urllib.error.URLError as e:
            return 0, str(e.reason).encode()
        except Exception as e:  # URL inválida, timeout, error de protocolo…
            return 0, f"{type(e).__name__}: {e}".encode()


def resolver_repo(api: GitHub, org: str, repo: str, carpeta: str, patron: re.Pattern, ref: str, destino: Path):
    """Devuelve (archivos_locales, problema, es_configuracion)."""
    q = f"?ref={urllib.parse.quote(ref)}" if ref else ""
    ruta = f"/repos/{org}/{repo}/contents/{urllib.parse.quote(carpeta)}{q}"
    estado, cuerpo = api.get(ruta)
    if estado == 404:
        return [], (
            f"No se encontró la plantilla BIAN: el repositorio `{org}/{repo}` o su carpeta `{carpeta}/` no existe "
            "o el token de plantillas no tiene acceso a él."
        ), False
    if estado != 200:
        detalle = cuerpo.decode("utf-8", "replace")[:200]
        return [], f"No se pudo leer `{org}/{repo}` (HTTP {estado}): {detalle}", True
    try:
        entradas = json.loads(cuerpo)
    except ValueError:
        return [], f"Respuesta inválida al listar `{org}/{repo}/{carpeta}`.", True
    nombres = sorted(e["name"] for e in entradas if isinstance(e, dict) and e.get("type") == "file"
                     and patron.search(e.get("name", "")))
    if not nombres:
        return [], (
            f"En `{org}/{repo}/{carpeta}/` no hay ningún archivo que cumpla el patrón `{patron.pattern}`."
        ), False
    if len(nombres) > MAX_ARCHIVOS:
        anotar("warning", f"{org}/{repo}: {len(nombres)} plantillas cumplen el patrón; se usan las últimas {MAX_ARCHIVOS}.")
        nombres = nombres[-MAX_ARCHIVOS:]

    locales = []
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        estado, cuerpo = api.get(f"/repos/{org}/{repo}/contents/{urllib.parse.quote(carpeta)}/{urllib.parse.quote(nombre)}{q}", raw=True)
        if estado != 200:
            return [], f"No se pudo descargar `{org}/{repo}/{carpeta}/{nombre}` (HTTP {estado}).", True
        archivo = destino / nombre
        archivo.write_bytes(cuerpo)
        locales.append(archivo)
    return locales, None, False


def procesar(a, api, token, archivo, cache, hallazgo, salida):
    """Resuelve la plantilla de un contrato; devuelve el bloque de contexto o None."""
    try:
        texto = Path(archivo).read_text(encoding="utf-8")
    except OSError:
        return None
    doc = cargar(texto)
    titulo = leer_titulo(texto, doc)
    lt = linea_titulo(texto)
    if not titulo:
        return None

    m = FORMATO.match(titulo)
    if not m:
        if re.match(r"^\s*API\s+BS\b", titulo, re.I):
            hallazgo("MEJORA", archivo, lt,
                     f"El título `{titulo}` empieza con `API BS` pero no sigue el formato "
                     "`API BS <ServiceDomainBian> <DominioFederado> V<n>`, así que no se comparó con la plantilla BIAN.",
                     "Corrige el título, p. ej. `API BS CustomerOffer Retail V1`.")
        return None

    sd, dominio, version = m.group("sd"), m.group("dominio"), m.group("version")
    sd_k = kebab(sd)
    repo = a.repo_patron.replace("{service-domain}", sd_k)
    patron = re.compile(a.archivo_patron.replace("{service-domain}", re.escape(sd_k)), re.IGNORECASE)

    if not token:
        hallazgo("BLOQUEANTE", archivo, lt,
                 f"El contrato debe compararse con la plantilla `{a.org}/{repo}`, pero el check no tiene token "
                 "para leer las plantillas. Es un problema de configuración, no del contrato.",
                 "Gobierno de APIs: crea el secret de organización BIAN_TEMPLATE_TOKEN (ver README de gobierno-apis).",
                 regla="configuracion-plantilla")
        anotar("error", "Falta BIAN_TEMPLATE_TOKEN: no se pueden leer las plantillas BIAN.")
        return None

    if repo not in cache:
        cache[repo] = resolver_repo(api, a.org, repo, a.carpeta, patron, a.ref, salida / "archivos" / repo)
    locales, problema, es_config = cache[repo]
    if problema:
        if es_config:
            anotar("error", problema)
            hallazgo("BLOQUEANTE", archivo, lt, problema + " Es un problema de configuración del check, no del contrato.",
                     "Gobierno de APIs: revisa el token BIAN_TEMPLATE_TOKEN y su acceso a los repositorios de plantillas.",
                     regla="configuracion-plantilla")
        else:
            hallazgo("BLOQUEANTE", archivo, lt,
                     f"El título declara el Service Domain `{sd}`, pero no hay plantilla BIAN para él. {problema}",
                     f"Verifica que `{sd}` sea el nombre exacto del Service Domain BIAN o solicita a Gobierno de APIs "
                     f"publicar la plantilla en `{a.org}/{repo}`.")
        return None

    base_texto = subprocess.run(["git", "show", f"{a.base}:{archivo}"], capture_output=True, text=True).stdout
    base_doc = cargar(base_texto) if base_texto else None
    if doc is not None:
        ops, schemas = cambios(base_doc, doc)
    else:
        ops, schemas = None, []

    bloque = [
        f"### `{archivo}`",
        f"- Título: `{titulo}` → Service Domain BIAN **{sd}**, dominio federado **{dominio}**, versión **{version}**.",
        f"- Plantilla: repositorio `{a.org}/{repo}`. Léela completa con `cat`:",
    ]
    claves_plantilla: list[tuple[str, str]] = []
    for loc in locales:
        bloque.append(f"  - `{loc}`")
        doc_plantilla = cargar(loc.read_text(encoding="utf-8", errors="replace"))
        claves_plantilla += [k for k in operaciones(doc_plantilla) if k not in claves_plantilla]
        ops_plantilla = indice(doc_plantilla)
        if ops_plantilla:
            bloque.append(f"  - Operaciones de `{loc.name}`:")
            bloque += ["  " + x for x in ops_plantilla]
    if ops is None:
        bloque.append("- Endpoints modificados: no se pudieron calcular; dedúcelos del `git diff`.")
    elif ops or schemas:
        bloque.append("- Endpoints modificados en este PR y su correspondencia con la plantilla "
                      "(calculada sin el base path `/<service-domain>/v<n>` y sin nombres de parámetros; "
                      "compara SOLO estos endpoints):")
        for mt, ruta, estado in ops:
            tipo, cand = correspondencia(mt, ruta, claves_plantilla, sd_k)
            lista = ", ".join(f"`{m} {r}`" for m, r in cand)
            if tipo == "coincide":
                detalle = f"coincide con la plantilla {lista}: compara campos, parámetros y respuestas."
            elif tipo == "verbo-distinto":
                detalle = f"⚠ misma ruta que la plantilla {lista}, pero con otro verbo HTTP."
            elif cand:
                detalle = (f"⚠ sin operación con la misma ruta en la plantilla. Más parecidas: {lista}. "
                           "Decide si es la misma operación con otro nombre o si está fuera de la plantilla.")
            else:
                detalle = "⚠ sin operación con la misma ruta en la plantilla ni operaciones parecidas."
            bloque.append(f"  - `{mt} {ruta}` ({estado}) → {detalle}")
        if schemas:
            bloque.append("  - Schemas modificados (compara también los endpoints que los usan): "
                          + ", ".join(f"`{s}`" for s in schemas))
    else:
        bloque.append("- El PR no modifica endpoints ni schemas de este contrato: no compares con la plantilla.")
    return "\n".join(bloque)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--contratos", required=True, help="Lista de contratos clasificados (contratos.txt)")
    p.add_argument("--base", required=True, help="SHA base del PR")
    p.add_argument("--salida-dir", required=True)
    p.add_argument("--org", required=True)
    p.add_argument("--repo-patron", default="bcp-api-template-{service-domain}")
    p.add_argument("--carpeta", default="api")
    p.add_argument("--archivo-patron", default=r"^business-{service-domain}-.+\.(ya?ml|json)$")
    p.add_argument("--ref", default="")
    a = p.parse_args()

    salida = Path(a.salida_dir)
    (salida / "archivos").mkdir(parents=True, exist_ok=True)
    token = os.environ.get("PLANTILLAS_TOKEN", "")
    api = GitHub(os.environ.get("GITHUB_API_URL", "https://api.github.com"), token)

    hallazgos, bloques, cache = [], [], {}

    def hallazgo(sev, archivo, linea, mensaje, sugerencia, regla=REGLA, ubicacion="info.title"):
        hallazgos.append({"severidad": sev, "archivo": archivo, "linea": linea, "ubicacion": ubicacion,
                          "regla": regla, "mensaje": mensaje, "sugerencia": sugerencia})

    for linea in Path(a.contratos).read_text(encoding="utf-8").splitlines():
        if "(SYNC" not in linea:
            continue
        archivo = linea.split(" (", 1)[0].strip()
        try:
            bloque = procesar(a, api, token, archivo, cache, hallazgo, salida)
        except Exception as e:  # fail-closed: nunca se omite la comparación en silencio
            anotar("error", f"{archivo}: error inesperado al resolver la plantilla BIAN: {type(e).__name__}: {e}")
            hallazgo("BLOQUEANTE", archivo, None,
                     f"No se pudo resolver la plantilla BIAN por un error del check ({type(e).__name__}: {e}). "
                     "Es un problema del check, no del contrato.",
                     "Gobierno de APIs: revisa el log del paso *Resolver plantillas BIAN*.",
                     regla="configuracion-plantilla")
            continue
        if bloque:
            bloques.append(bloque)

    if bloques:
        contexto = ("Los siguientes contratos SYNC tienen título `API BS <ServiceDomainBian> <DominioFederado> V<n>` "
                    "y deben compararse con su plantilla BIAN (regla 8 de las REGLAS OPENAPI).\n\n" + "\n\n".join(bloques))
    else:
        contexto = "Ningún contrato SYNC de este PR requiere comparación con plantilla BIAN: no apliques la regla 8."
    (salida / "contexto.md").write_text(contexto + "\n", encoding="utf-8")
    (salida / "hallazgos-previos.json").write_text(
        json.dumps({"hallazgos": hallazgos}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(contexto)
    if hallazgos:
        print(f"Hallazgos deterministas: {len(hallazgos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
