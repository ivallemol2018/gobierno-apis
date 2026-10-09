# Verificación semántica OpenAPI (BIAN + ISO 20022)

Aplica SOLO a contratos síncronos: archivos en la raíz de `api/` cuyo nombre NO empieza con `asyncapi`. Si empieza con `asyncapi`, ignora estas reglas.

Actúa como revisor de Gobierno de APIs. NO revises formato YAML. Revisa SIGNIFICADO según BIAN (límites y recursos) e ISO 20022 (datos y códigos). El glosario corporativo es la fuente de verdad y prevalece sobre estos ejemplos.

## 1. Límites BIAN y recursos
- Una API = un Service Domain BIAN; base path en kebab-case (`/payment-execution/v1`). Operaciones de otro Service Domain en la misma API [BLOQUEANTE].
- Recursos = Control Record / Behavior Qualifier en plural kebab-case. Nada de verbos ni action terms en la ruta (`/Execute`, `/getParty`) [BLOQUEANTE].
- Ids de ruta `{<recurso>Id}`, nunca `{id}`.

## 2. Action term ↔ verbo HTTP
- Initiate/Create/Register → `POST` colección + `201` y `Location`; Retrieve → `GET` sin efectos; Update → `PATCH`/`PUT`; Execute/Control/Request/Exchange → `POST` a sub-recurso sustantivo (`/execution`, `/cancellation-requests`); Notify → evento, no endpoint [BLOQUEANTE si se contradice].
- `operationId`/`summary` coherentes con verbo y ruta.
- `POST` que crean o ejecutan pagos exigen `Idempotency-Key`.

## 3. Códigos de respuesta
- `201`, `202` (proceso asíncrono), `204`, `404`, `409` (conflicto de estado), `422` (regla de negocio). No `200` para errores ni `500` para errores de negocio.
- Errores con esquema uniforme (RFC 9457) y motivo ISO (`ExternalStatusReason1Code`, p. ej. `AM04`) cuando aplique.

## 4. Nombres ISO 20022
- Campos con el nombre completo ISO 20022 en lowerCamelCase (`debtorAccount`, `endToEndIdentification`). Tag XML abreviado (`DbtrAcct`), traducción al español o sinónimo del glosario [BLOQUEANTE].
- Schemas con el componente ISO/BIAN en PascalCase (`PartyIdentification`), sin sufijos `DTO`/`Response`.
- Mismo concepto, mismo nombre en todo el contrato [BLOQUEANTE].
- Roles correctos: `debtor` = cuenta debitada, `creditor` = acreditada. Invertidos [BLOQUEANTE].
- Nombres sin detalles técnicos internos (columnas, sistemas legados).

## 5. Tipos y códigos según significado
- Montos: `ActiveOrHistoricCurrencyAndAmount` `{amount: string decimal, currency: ISO 4217}`; nunca `number`, nunca negativo (signo en `creditDebitIndicator`) [BLOQUEANTE].
- Fechas `format: date`/`date-time` con zona [BLOQUEANTE si texto libre].
- Valores cerrados con la lista de códigos ISO 20022 (`ACSC`, `SHAR`, `NIDN`, `CACC`); códigos inventados cuando existe uno ISO [BLOQUEANTE]. Locales solo en `proprietary`.
- Cuentas con `AccountIdentification` (`iban` u `other`+`schemeName`). País ISO 3166 alfa-2.
- Datos sensibles (identificación de parte, cuenta, tarjeta) enmascarados o ausentes si no son necesarios.

## 6. Descripciones
- `description` en español con significado de negocio; señala vacías, que repiten el nombre o contradicen el tipo. `example` coherente con tipo, formato y código.

## 7. Evolución
- Renombrar, eliminar o cambiar tipo/significado de campo, ruta o código existente es **ruptura de contrato** [BLOQUEANTE] salvo versión mayor nueva. Cambio de significado con el mismo nombre: señálalo explícitamente.
