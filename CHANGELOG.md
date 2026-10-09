# Changelog

Cambios en reglas, glosario y comportamiento de la verificación semántica.
Formato: [versión] — fecha — cambio. Un cambio que puede bloquear PRs que antes pasaban es versión mayor.

## [1.0.0] — 2026-10-08
- Primera versión centralizada (opción A: el check es la única fuente de las reglas).
- Reglas OpenAPI y AsyncAPI alineadas a BIAN (límites y recursos) e ISO 20022 (datos y códigos).
- Glosario corporativo: Service Domains, action terms → HTTP, términos de negocio, listas de códigos ISO, tipos comunes y catálogo de eventos (CloudEvents).
- Detección: contratos en la raíz de `api/`; ASYNC si el nombre empieza con `asyncapi`, SYNC el resto.
- Recuperación del reporte desde la respuesta de Copilot CLI y modo *fail-closed*.
