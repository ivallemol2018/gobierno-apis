# Changelog

Cambios en reglas, glosario y comportamiento de la verificación semántica.
Formato: [versión] — fecha — cambio. Un cambio que puede bloquear PRs que antes pasaban es versión mayor.

## [2.0.0] — 2026-10-11
- **Nueva regla 8 (OpenAPI): conformidad con la plantilla BIAN.** Los contratos SYNC con título `API BS <ServiceDomainBian> <DominioFederado> V<n>` se comparan con la plantilla del Service Domain (`bcp-api-template-<service-domain>/api/business-<service-domain>-*.yaml`). Se revisan solo los endpoints modificados en el PR; el contrato puede implementar un subconjunto de la plantilla.
- Las rutas de la plantilla están en kebab-case plural con el action term como último segmento; el contrato debe seguirlas tal cual después de su base path. Emparejamiento determinista de cada endpoint modificado con la plantilla (coincide / otro verbo / sin coincidencia y las más parecidas).
- Excepción en la regla 1 y en el glosario: en contratos con plantilla BIAN, el action term en la ruta es correcto y el verbo HTTP es el de la plantilla.
- Hallazgos deterministas previos a Copilot: título mal formado (MEJORA), plantilla inexistente (BLOQUEANTE), token de plantillas ausente o inválido (BLOQUEANTE, `configuracion-plantilla`).
- Nuevo secret de organización `BIAN_TEMPLATE_TOKEN` (lectura de los repositorios de plantilla).
- Versión mayor porque puede bloquear PRs que en v1 pasaban. Los repos migran cambiando `@v1` por `@v2` en su workflow.

## [1.0.0] — 2026-10-08
- Primera versión centralizada (opción A: el check es la única fuente de las reglas).
- Reglas OpenAPI y AsyncAPI alineadas a BIAN (límites y recursos) e ISO 20022 (datos y códigos).
- Glosario corporativo: Service Domains, action terms → HTTP, términos de negocio, listas de códigos ISO, tipos comunes y catálogo de eventos (CloudEvents).
- Detección: contratos en la raíz de `api/`; ASYNC si el nombre empieza con `asyncapi`, SYNC el resto.
- Recuperación del reporte desde la respuesta de Copilot CLI y modo *fail-closed*.
