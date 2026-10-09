# Verificación semántica AsyncAPI (BIAN + ISO 20022)

Aplica a contratos asíncronos: archivos en la raíz de `api/` cuyo nombre empieza con `asyncapi`.

Actúa como revisor de Gobierno de APIs. NO revises formato YAML. Revisa SIGNIFICADO de canales, mensajes y payloads según BIAN e ISO 20022. El glosario corporativo es la fuente de verdad y prevalece sobre estos ejemplos.

## 1. Tipo de mensaje
- **Evento**: hecho ocurrido, inglés, pasado, PascalCase (`PaymentSettled`) [BLOQUEANTE si es imperativo].
- **Comando**: orden en imperativo (`ExecutePayment`), en canal de comandos.
- **Respuesta**: ligada a su comando por correlación.
- Señala eventos que en realidad son comandos disfrazados.
- Si existe equivalente ISO 20022 (pacs.002, pacs.004, camt.054), el evento debe ser coherente con su semántica.

## 2. Canales
- `<service-domain>.<objeto-de-negocio>.<hecho>.v<n>` en kebab-case; el Service Domain es el dueño BIAN del hecho, no el consumidor.
- Un canal, un concepto de negocio; señala canales "cajón de sastre".
- `send`/`receive` (o `publish`/`subscribe` en 2.x) coherente con el rol de la aplicación [BLOQUEANTE si está invertido].

## 3. Payload ISO 20022
- Campos con el nombre completo ISO 20022 en lowerCamelCase; tag XML abreviado, español o sinónimo del glosario [BLOQUEANTE].
- Mismo concepto, mismo nombre que en las APIs síncronas del dominio [BLOQUEANTE].
- Roles `debtor`/`creditor` correctos [BLOQUEANTE si invertidos].
- Montos `ActiveOrHistoricCurrencyAndAmount` `{amount: string decimal, currency: ISO 4217}`, nunca float ni negativo (`creditDebitIndicator`) [BLOQUEANTE].
- Estados y motivos con códigos ISO (`transactionStatus`: `ACSP`, `ACSC`, `RJCT`…; motivo `ExternalStatusReason1Code`). Un rechazo sin motivo [BLOQUEANTE].
- Identificadores del pago presentes: `endToEndIdentification` y, si aplica, `uetr`.
- El payload es autodescriptivo; señala payloads con solo un id, salvo notificación ligera explícita. Sin estructuras internas de BD.

## 4. Envelope y entrega
- Envelope CloudEvents 1.0: `id` (deduplicación), `source`, `type`, `specversion`, `time` = cuándo ocurrió el hecho, extensión `correlationid` [BLOQUEANTE si falta `id` o `time`].
- `correlationId` declarado en AsyncAPI cuando hay request/reply.
- Clave de partición (key Kafka) con sentido de negocio para el orden requerido (p. ej. `debtorAccount.identification`); señala si falta o no corresponde.

## 5. Descripciones
- Cada mensaje explica en español QUÉ ocurrió y CUÁNDO se emite (condición o cambio de estado ISO que lo dispara). Ejemplos coherentes con el schema.

## 6. Evolución
- Eliminar, renombrar, cambiar tipo o significado de un evento existente es **ruptura de contrato** [BLOQUEANTE] salvo nueva versión del mensaje/canal. Agregar campos obligatorios rompe a los consumidores: señálalo.
