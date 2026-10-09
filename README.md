# gobierno-apis

Repositorio central de Gobierno de APIs. Contiene la **verificación semántica de contratos** (BIAN + ISO 20022) que se ejecuta en cada Pull Request de los repositorios de contratos creados desde el template.

## Estructura

```
gobierno-apis/
├── .github/workflows/
│   └── verificacion-semantica.yml      ← reusable workflow (on: workflow_call)
├── actions/verificacion-semantica/     ← composite action: toda la lógica
│   ├── action.yml
│   ├── prompt.md                       ← instrucciones para Copilot CLI
│   ├── evaluar_reporte.py              ← valida el JSON, comenta y decide el check
│   ├── glosario.md                     ← vocabulario corporativo BIAN + ISO 20022
│   └── reglas/
│       ├── openapi-semantica.md        ← reglas para contratos síncronos
│       └── asyncapi-semantica.md       ← reglas para contratos asíncronos
├── CHANGELOG.md
└── README.md
```

Las reglas, el glosario y el prompt viajan dentro de la action, así que cada versión publicada es un paquete cerrado y reproducible.

## Cómo funciona

1. Un repositorio de contratos abre un PR. Su workflow (del template) llama a este reusable workflow con `secrets: inherit`.
2. Se detectan los contratos modificados: archivos `.yaml`, `.yml` o `.json` en la raíz de `api/`.
3. Cada contrato se clasifica por nombre: los que empiezan con `asyncapi` son **ASYNC**; el resto, **SYNC**.
4. Copilot CLI revisa los contratos con las reglas y el glosario, y genera un reporte JSON.
5. `evaluar_reporte.py` publica un comentario con la tabla de hallazgos, anota cada hallazgo en su línea y marca el check:
   - ✅ sin hallazgos al nivel configurado (por defecto, BLOQUEANTE);
   - ❌ con hallazgos;
   - ❌ si no hay reporte válido (*fail-closed*).

## Configuración única en la organización

1. **Acceso al repositorio central.** En este repo: *Settings → Actions → General → Access* → **Accessible from repositories in the organization**. Así los demás repos pueden usar el workflow y la action aunque este repo sea privado o interno.
2. **Cuenta de servicio con licencia de Copilot.** Genera con ella un *fine-grained PAT* con el permiso **Copilot Requests**.
3. **Secret de organización.** *Organization → Settings → Secrets and variables → Actions → New organization secret*:
   - Nombre: `COPILOT_CLI_TOKEN`
   - Acceso: **All repositories** o **Private repositories**, para que los repos nuevos lo hereden.
4. **Política de Copilot.** Verifica que la organización permita el uso de Copilot CLI.
5. **Nombre de la organización.** Reemplaza `MI-ORG` en:
   - `.github/workflows/verificacion-semantica.yml` (este repo)
   - `.github/workflows/verificacion-semantica.yml` (template)
6. **Check obligatorio.** En el ruleset de la rama principal de los repos de contratos, exige el check **`verificacion-semantica / Verificación semántica`**.

## Publicar una versión

```bash
git tag v1.0.0 && git push origin v1.0.0
git tag -f v1 && git push -f origin v1     # tag mayor móvil: los repos usan @v1
```

- **Parche o menor** (`v1.x.y`): correcciones o reglas que no vuelven más estricto el check. Mueve `v1`.
- **Mayor** (`v2.0.0`): reglas nuevas que pueden bloquear PRs que hoy pasan. Crea `v2` y actualiza en el mismo commit la referencia `@v2` de la action dentro del reusable workflow. Cada equipo migra cambiando `@v1` por `@v2` en su caller.

El reusable workflow referencia la action con el **mismo tag mayor** (`@v1`). Muévelos siempre juntos.

Registra cada cambio de reglas o glosario en `CHANGELOG.md`.

## Parámetros opcionales del reusable workflow

| Input | Por defecto | Uso |
|---|---|---|
| `nivel-fallo` | `BLOQUEANTE` | `MEJORA` hace fallar también por mejoras |
| `patron-contratos` | `^api/[^/]+\.(ya?ml|json)$` | Qué archivos son contratos |
| `patron-async` | `^api/asyncapi[^/]*$` | Qué contratos son asíncronos |
| `modelo` | vacío | Fija el modelo de Copilot CLI para resultados más estables |

Ejemplo en un repo de contratos:

```yaml
jobs:
  verificacion-semantica:
    uses: MI-ORG/gobierno-apis/.github/workflows/verificacion-semantica.yml@v1
    secrets: inherit
    with:
      nivel-fallo: MEJORA
```

## Diagnóstico

| Mensaje | Causa |
|---|---|
| `Falta el token de Copilot…` | No existe el secret de organización, no tiene acceso al repo, falta `secrets: inherit` o el PR viene de un fork |
| `No se obtuvo un reporte válido de Copilot CLI (fail-closed)` | Revisa en el paso *Ejecutar verificación semántica con Copilot CLI* el código de salida y las últimas líneas; o descarga el artefacto `verificacion-semantica` |
| `workflow was not found` o error al resolver la action | Falta el paso 1 de la configuración, `MI-ORG` no fue reemplazado o el tag `v1` no existe |
