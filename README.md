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
│   ├── resolver_plantillas.py          ← ubica y descarga la plantilla BIAN de cada contrato
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
4. Si el título de un contrato SYNC sigue el formato `API BS <ServiceDomainBian> <DominioFederado> V<n>`, se descarga su plantilla BIAN (ver abajo) y se calculan los endpoints que modificó el PR.
5. Copilot CLI revisa los contratos con las reglas, el glosario y, cuando aplica, la plantilla BIAN, y genera un reporte JSON.
6. `evaluar_reporte.py` publica un comentario con la tabla de hallazgos, anota cada hallazgo en su línea y marca el check:
   - ✅ sin hallazgos al nivel configurado (por defecto, BLOQUEANTE);
   - ❌ con hallazgos;
   - ❌ si no hay reporte válido (*fail-closed*).

## Comparación con la plantilla BIAN

Aplica a los contratos SYNC cuyo `info.title` sigue el formato:

```
API BS <ServiceDomainBian> <DominioFederado> V<n>        p. ej.  API BS CustomerOffer Retail V1
```

| Elemento | Se obtiene así | Ejemplo |
|---|---|---|
| Repositorio de la plantilla | `bcp-api-template-` + Service Domain en kebab-case | `bcp-api-template-customer-offer` |
| Archivo de la plantilla | En la carpeta `api/`, el que cumple `^business-<service-domain>-.+\.(ya?ml|json)$` | `api/business-customer-offer-v13-0-0.yaml` |

El check compara **solo los endpoints que el PR modifica** contra la plantilla (regla 8 de las reglas OpenAPI). El contrato puede implementar un subconjunto de la plantilla, pero lo que implementa debe coincidir con ella.

Las rutas de la plantilla están en kebab-case plural y terminan en el action term, y el contrato las sigue tal cual después de su base path:

| Plantilla | Contrato |
|---|---|
| `POST /customer-offer-procedures/initiate` | `POST /customer-offer/v1/customer-offer-procedures/initiate` |
| `PUT /customer-offer-procedures/{customer-offer-procedure-id}/execute` | `PUT /customer-offer/v1/customer-offer-procedures/{customerOfferProcedureId}/execute` |

Antes de ejecutar Copilot, el check empareja cada endpoint modificado con la plantilla, ignorando el base path (`/<service-domain>/v<n>`) y los nombres de los parámetros de ruta. El resultado puede ser **coincide**, **misma ruta con otro verbo** o **sin operación con la misma ruta** (en este caso, con las más parecidas). Copilot usa ese emparejamiento para revisar ruta, verbo, campos y códigos de respuesta.

En estos contratos el action term en la ruta es correcto: la regla general que lo prohíbe no se aplica.

Hallazgos que se detectan antes de ejecutar Copilot:

| Situación | Severidad |
|---|---|
| El título empieza con `API BS` pero no sigue el formato | MEJORA |
| No existe el repositorio o el archivo de plantilla para el Service Domain del título | BLOQUEANTE |
| Falta el token de plantillas, es inválido o no tiene acceso | BLOQUEANTE (`configuracion-plantilla`: es un problema del check, no del contrato) |

Los contratos cuyo título no empieza con `API BS` no se comparan con plantilla.

## Configuración única en la organización

1. **Acceso al repositorio central.** En este repo: *Settings → Actions → General → Access* → **Accessible from repositories in the organization**. Así los demás repos pueden usar el workflow y la action aunque este repo sea privado o interno.
2. **Cuenta de servicio con licencia de Copilot.** Genera con ella un *fine-grained PAT* con el permiso **Copilot Requests**.
3. **Secret de organización.** *Organization → Settings → Secrets and variables → Actions → New organization secret*:
   - Nombre: `COPILOT_CLI_TOKEN`
   - Acceso: **All repositories** o **Private repositories**, para que los repos nuevos lo hereden.
4. **Token de plantillas BIAN.** Crea un *fine-grained PAT* con:
   - *Resource owner*: **la organización** (no la cuenta de servicio).
   - *Repository access*: **All repositories**, para que las plantillas nuevas (`bcp-api-template-*`) queden incluidas sin volver a editar el token. Si tu política lo prohíbe, usa *Only select repositories* y agrega cada repositorio de plantilla.
   - *Permissions → Repository permissions → Contents*: **Read-only**. Ningún otro permiso.

   Guárdalo como secret de organización `BIAN_TEMPLATE_TOKEN`, con el mismo acceso que `COPILOT_CLI_TOKEN`. Es un token distinto porque el de Copilot pertenece a la cuenta de servicio y no puede leer repositorios privados de la organización. Una alternativa sin vencimiento es una GitHub App con permiso *Contents: read*.
5. **Política de Copilot.** Verifica que la organización permita el uso de Copilot CLI.
6. **Nombre de la organización.** Reemplaza `MI-ORG` en:
   - `.github/workflows/verificacion-semantica.yml` (este repo)
   - `.github/workflows/verificacion-semantica.yml` (template)
7. **Check obligatorio.** En el ruleset de la rama principal de los repos de contratos, exige el check **`verificacion-semantica / Verificación semántica`**.

## Publicar una versión

```bash
git tag v2.0.0 && git push origin v2.0.0
git tag -f v2 && git push -f origin v2     # tag mayor móvil: los repos usan @v2
```

- **Parche o menor** (`v1.x.y`): correcciones o reglas que no vuelven más estricto el check. Mueve `v1`.
- **Mayor** (`v2.0.0`): reglas nuevas que pueden bloquear PRs que hoy pasan. Crea `v2` y actualiza en el mismo commit la referencia `@v2` de la action dentro del reusable workflow. Cada equipo migra cambiando `@v1` por `@v2` en su caller.

El reusable workflow referencia la action con el **mismo tag mayor** (`@v2`). Muévelos siempre juntos.

Registra cada cambio de reglas o glosario en `CHANGELOG.md`.

## Parámetros opcionales del reusable workflow

| Input | Por defecto | Uso |
|---|---|---|
| `nivel-fallo` | `BLOQUEANTE` | `MEJORA` hace fallar también por mejoras |
| `patron-contratos` | `^api/[^/]+\.(ya?ml|json)$` | Qué archivos son contratos |
| `patron-async` | `^api/asyncapi[^/]*$` | Qué contratos son asíncronos |
| `modelo` | vacío | Fija el modelo de Copilot CLI para resultados más estables |
| `plantillas-repo-patron` | `bcp-api-template-{service-domain}` | Nombre del repositorio de plantilla |
| `plantillas-archivo-patron` | `^business-{service-domain}-.+\.(ya?ml|json)$` | Archivo de plantilla dentro de `api/` |
| `plantillas-ref` | vacío (rama por defecto) | Rama o tag de las plantillas, p. ej. para fijar una versión aprobada |

Ejemplo en un repo de contratos:

```yaml
jobs:
  verificacion-semantica:
    uses: MI-ORG/gobierno-apis/.github/workflows/verificacion-semantica.yml@v2
    secrets: inherit
    with:
      nivel-fallo: MEJORA
```

## Diagnóstico

| Mensaje | Causa |
|---|---|
| `Falta el token de Copilot…` | No existe el secret de organización, no tiene acceso al repo, falta `secrets: inherit` o el PR viene de un fork |
| `No se obtuvo un reporte válido de Copilot CLI (fail-closed)` | Revisa en el paso *Ejecutar verificación semántica con Copilot CLI* el código de salida y las últimas líneas; o descarga el artefacto `verificacion-semantica` |
| Hallazgo `configuracion-plantilla` | Falta `BIAN_TEMPLATE_TOKEN`, venció o no tiene acceso al repositorio de plantilla. Revisa el paso *Resolver plantillas BIAN* |
| "No hay plantilla BIAN para él" | El Service Domain del título no coincide con ningún repositorio `bcp-api-template-*`, o ese repositorio no tiene un archivo `api/business-<service-domain>-*.yaml` |
| `workflow was not found` o error al resolver la action | Falta el paso 1 de la configuración, `MI-ORG` no fue reemplazado o el tag `v2` no existe |
