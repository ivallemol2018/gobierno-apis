# Glosario de dominio — BIAN + ISO 20022

Fuente de verdad del vocabulario que deben usar los contratos OpenAPI y AsyncAPI.
La verificación semántica valida recursos, campos, códigos y eventos contra este archivo.

- **Límites y recursos:** BIAN (Service Domains y Business Object Model).
- **Datos y códigos:** diccionario ISO 20022 (componentes de negocio y listas de códigos).
- **Idioma:** nombres en **inglés** según ISO 20022 / BIAN; `description` y documentación en **español**.

> Los nombres de Control Records y las listas de códigos externas cambian entre versiones de BIAN y
> publicaciones de ISO 20022. Verifica contra la versión que adopte la organización antes de activarlo.

---

## 1. Principios de nombrado

| Elemento | Regla | Correcto | Incorrecto |
|---|---|---|---|
| Campo | Nombre completo del elemento ISO 20022 en `lowerCamelCase` | `debtorAccount`, `instructedAmount` | `DbtrAcct` (tag XML), `cuentaOrigen`, `fromAccount` |
| Schema | Componente ISO 20022 / objeto BIAN en `PascalCase` | `PartyIdentification`, `CashAccount` | `ClienteDTO`, `AccountResponse` |
| Código | Valor exacto de la lista de códigos ISO 20022 | `ACSC`, `SHAR`, `NIDN` | `"OK"`, `"1"`, `"PAGADO"`, `"DNI"` |
| Booleano | Prefijo `is` / `has` (ISO casi no usa booleanos: prefiere códigos) | `isPrimary` | `primary`, `flagPrimary` |
| Fecha | Sufijo `Date`, `format: date` | `requestedExecutionDate` | `executionDt`, `fecha` |
| Fecha-hora | Sufijo `DateTime`, `format: date-time` con zona | `creationDateTime` | `timestamp`, `createdAt` |
| Signo de un monto | Nunca con número negativo: usar `creditDebitIndicator` | `amount: "50.00"` + `CRDT` | `amount: "-50.00"` |

**Prohibido:** los tags XML abreviados de ISO 20022 (`Dbtr`, `Cdtr`, `InstdAmt`, `EndToEndId`, `Ccy`) y traducciones al español de elementos que tienen nombre ISO.

**Si un concepto no está en este glosario:** búscalo en el diccionario ISO 20022 o en el BOM de BIAN, úsalo con su nombre oficial y propón agregarlo con un PR al repositorio `gobierno-apis`.

---

## 2. Service Domains BIAN y recursos REST

Cada API corresponde a **un** Service Domain. El base path es el Service Domain en `kebab-case`; los recursos son el Control Record (y sus Behavior Qualifiers como sub-recursos) en plural.

| Service Domain BIAN | Base path | Recurso principal (Control Record) | Uso |
|---|---|---|---|
| Party Reference Data Directory | `/party-reference-data-directory/v1` | `/parties/{partyId}` | Datos de referencia de personas y empresas |
| Current Account | `/current-account/v1` | `/current-account-facilities/{currentAccountFacilityId}` | Cuentas corrientes |
| Savings Account | `/savings-account/v1` | `/savings-account-facilities/{savingsAccountFacilityId}` | Cuentas de ahorro |
| Payment Initiation | `/payment-initiation/v1` | `/payment-initiation-transactions/{paymentInitiationTransactionId}` | Orden de pago del cliente (≈ pain.001) |
| Payment Execution | `/payment-execution/v1` | `/payment-execution-transactions/{paymentExecutionTransactionId}` | Ejecución interbancaria (≈ pacs.008) |

**Identificadores en ruta:** `{<recursoEnSingular>Id}`. Prohibido `{id}`, `{code}`, `{nro}`.

### Action terms BIAN → HTTP

| Action term | Patrón REST | Código esperado |
|---|---|---|
| Initiate / Create / Register | `POST /<recursos>` | `201` + `Location` |
| Retrieve | `GET /<recursos>/{id}` o `GET /<recursos>?…` | `200` |
| Update | `PATCH /<recursos>/{id}` (parcial) · `PUT` (reemplazo total) | `200` / `204` |
| Control (suspend, resume, terminate) | `POST /<recursos>/{id}/<sustantivo-del-control>` (`/suspension`, `/termination`) | `200` / `202` |
| Execute | `POST /<recursos>/{id}/execution` | `200` / `202` |
| Request | `POST /<recursos>/{id}/<sustantivo>-requests` | `201` / `202` |
| Exchange (accept, reject) | `POST /<recursos>/{id}/acceptance` · `/rejection` | `200` |
| Notify | No es endpoint: se publica como **evento** (AsyncAPI) | — |

Nunca el action term como verbo en la ruta (`/payment-execution-transactions/{id}/Execute`).

**Excepción — contratos con plantilla BIAN** (título `API BS <ServiceDomainBian> <DominioFederado> V<n>`): la ruta sigue a la plantilla del Service Domain, que usa recursos en kebab-case plural y el action term como último segmento en kebab-case (`POST /customer-offer-procedures/{customerOfferProcedureId}/initiate`). En ese caso el verbo HTTP es el de la plantilla y la tabla anterior no se aplica.

---

## 3. Términos de negocio

### Partes

| Concepto | Campo | Tipo ISO 20022 | Definición | No usar |
|---|---|---|---|---|
| Parte | `party` / `partyId` | `PartyIdentification` | Persona natural o jurídica registrada en el banco. | `cliente`, `customer`, `user` |
| Ordenante | `debtor` | `PartyIdentification` | Parte cuya cuenta se debita. | `pagador`, `payer`, `originator` |
| Beneficiario | `creditor` | `PartyIdentification` | Parte cuya cuenta se acredita. | `beneficiario`, `payee` |
| Ordenante / beneficiario final | `ultimateDebtor` / `ultimateCreditor` | `PartyIdentification` | Parte real detrás del ordenante o beneficiario (pagos en nombre de terceros). | `realPayer` |
| Nombre | `name` | `Max140Text` | Nombre o razón social. | `nombre`, `fullName` |
| Dirección | `postalAddress` | `PostalAddress` | Dirección estructurada; `country` en ISO 3166-1 alfa-2 (`PE`). | `direccion`, `address` |
| Documento de identidad | `identification` | `PersonIdentification` / `OrganisationIdentification` | Ver tabla de códigos §4. Dato sensible. | `dni`, `documentNumber` |

### Cuentas y saldos

| Concepto | Campo | Tipo ISO 20022 | Definición | No usar |
|---|---|---|---|---|
| Cuenta | `account` | `CashAccount` | Cuenta de efectivo del cliente. | `cuenta`, `acct` |
| Cuenta del ordenante / beneficiario | `debtorAccount` / `creditorAccount` | `CashAccount` | Cuenta debitada / acreditada. | `fromAccount`, `toAccount`, `cuentaOrigen` |
| Identificación de cuenta | `account.identification` | `AccountIdentification` | `iban` o `other.identification` + `schemeName`. El número local va en `other`. | `accountNumber` suelto |
| CCI | `account.identification.other` | `GenericAccountIdentification` | `identification` = 20 dígitos, `schemeName.proprietary` = `"CCI"` (convención local). | `cci`, `interbankCode` |
| Tipo de cuenta | `account.type.code` | `ExternalCashAccountType1Code` | `CACC` corriente, `SVGS` ahorro. | `tipoCuenta`, `"AHORROS"` |
| Moneda de la cuenta | `account.currency` | `ActiveOrHistoricCurrencyCode` | ISO 4217. | `moneda` |
| Saldo | `balance` | `CashBalance` | Con `type.code`, `amount` y `creditDebitIndicator`. | `saldo` |
| Saldo disponible | `balance` con `type.code = ITAV` | `BalanceType` | Interim available. | `availableBalance` como campo propio |
| Saldo contable | `balance` con `type.code = ITBD` (o `CLBD` al cierre) | `BalanceType` | Interim / closing booked. | `saldoContable`, `ledgerBalance` |
| Movimiento | `entry` | `ReportEntry` | Asiento en la cuenta: `amount`, `creditDebitIndicator`, `status` (`BOOK`/`PDNG`), `bookingDate`, `valueDate`. | `movimiento`, `transaction` |

### Pagos

| Concepto | Campo | Tipo ISO 20022 | Definición | No usar |
|---|---|---|---|---|
| Id. de la instrucción | `instructionIdentification` | `Max35Text` | Asignado por quien instruye, único en su ámbito. | `instructionId`, `nroOperacion` |
| Id. extremo a extremo | `endToEndIdentification` | `Max35Text` | Asignado por el ordenante; viaja sin cambios hasta el beneficiario. | `e2eId`, `referencia` |
| UETR | `uetr` | `UUIDv4Identifier` | Identificador único universal de la transacción. | `trackingId` |
| Id. de la transacción | `transactionIdentification` | `Max35Text` | Asignado por el primer agente. | `txId`, `trxId` |
| Monto instruido | `instructedAmount` | `ActiveOrHistoricCurrencyAndAmount` | Monto que ordena el ordenante (ver §5). | `monto`, `amount` suelto |
| Fecha de ejecución solicitada | `requestedExecutionDate` | `DateAndDateTime2Choice` | Cuándo debe ejecutarse. | `fechaPago`, `paymentDate` |
| Asunción de gastos | `chargeBearer` | `ChargeBearerType1Code` | `DEBT`, `CRED`, `SHAR`, `SLEV`. | `quienPaga`, `feeType` |
| Gastos | `charges` | `Charges` | Comisiones aplicadas, con `amount` y `agent`. | `comision`, `fee` |
| Concepto | `remittanceInformation` | `RemittanceInformation` | `unstructured` (texto) o `structured` (referencias de documento). | `glosa`, `concept`, `memo` |
| Propósito | `purpose.code` / `categoryPurpose.code` | `ExternalPurpose1Code` / `ExternalCategoryPurpose1Code` | Motivo económico del pago (`SALA` sueldos, `SUPP` proveedores…). | `motivo`, `paymentType` libre |
| Agente del ordenante / beneficiario | `debtorAgent` / `creditorAgent` | `BranchAndFinancialInstitutionIdentification` | Entidad financiera; `BICFI` o miembro del sistema de compensación. | `banco`, `bankCode` |
| Estado de la transacción | `transactionStatus` | `ExternalPaymentTransactionStatus1Code` | Ver §4. | `estado`, `status` libre |
| Motivo del estado | `statusReasonInformation.reason.code` | `ExternalStatusReason1Code` | Ver §4. | `errorCode`, `motivoRechazo` |

### Reversiones (sustituyen a "anulación" y "extorno")

| Concepto | Recurso / evento | Mensaje ISO 20022 | Cuándo |
|---|---|---|---|
| Solicitud de cancelación | `POST …/{id}/cancellation-requests` | camt.055 (cliente) / camt.056 (interbancario) | Se pide anular antes de la liquidación o al beneficiario después. |
| Devolución | `PaymentReturned` | pacs.004 | El agente del beneficiario devuelve fondos ya liquidados. |
| Reversión | `PaymentReversed` | pacs.007 | El agente que envió revierte por error propio. |

### Cabeceras técnicas (no ISO 20022)

| Cabecera | Formato | Uso |
|---|---|---|
| `Idempotency-Key` | UUID | Obligatoria en `POST` que crean o ejecutan pagos. |
| `X-Correlation-Id` | UUID | Trazabilidad entre servicios; se propaga a los eventos como `correlationid`. |

---

## 4. Listas de códigos

### Identificación de personas — `ExternalPersonIdentification1Code`
| Documento local | Código ISO | Ubicación |
|---|---|---|
| DNI | `NIDN` | `privateIdentification.other.schemeName.code` |
| Carné de Extranjería | `ARNU` | `privateIdentification.other.schemeName.code` |
| Pasaporte | `CCPT` | `privateIdentification.other.schemeName.code` |
| RUC (empresas) | `TXID` (`ExternalOrganisationIdentification1Code`) | `organisationIdentification.other.schemeName.code` |

### Estado de la transacción — `ExternalPaymentTransactionStatus1Code`
| Código | Significado | Sigue a |
|---|---|---|
| `RCVD` | Recibida | — |
| `ACTC` | Validación técnica aceptada | `RCVD` |
| `ACCP` | Aceptada tras validar perfil del cliente | `ACTC` |
| `PDNG` | Pendiente (revisión, fondos, horario) | `ACTC`, `ACCP` |
| `ACSP` | Aceptada, liquidación en proceso | `ACCP`, `PDNG` |
| `ACSC` | Liquidación completada en cuenta del ordenante | `ACSP` |
| `ACCC` | Liquidación completada en cuenta del beneficiario | `ACSC` |
| `RJCT` | Rechazada (estado final; requiere motivo) | cualquiera no final |

### Motivos frecuentes — `ExternalStatusReason1Code`
| Código | Significado |
|---|---|
| `AM04` | Fondos insuficientes |
| `AM05` | Duplicado |
| `AC01` | Número de cuenta incorrecto |
| `AC04` | Cuenta cerrada |
| `AC06` | Cuenta bloqueada |

### Otras
- **Moneda:** ISO 4217 (`PEN`, `USD`).
- **País:** ISO 3166-1 alfa-2 (`PE`).
- **Indicador crédito/débito:** `CRDT`, `DBIT`.
- **Estado del movimiento:** `BOOK` (contabilizado), `PDNG` (pendiente), `INFO` (informativo).

Prohibido inventar códigos propios cuando existe uno ISO. Si se necesita uno local, usar el campo `proprietary` del elemento y documentarlo aquí.

---

## 5. Tipos de dato comunes

### `ActiveOrHistoricCurrencyAndAmount`
```yaml
ActiveOrHistoricCurrencyAndAmount:
  type: object
  description: Monto con su moneda (ISO 20022). El signo nunca va en el monto.
  required: [amount, currency]
  properties:
    amount:
      type: string
      pattern: '^\d{1,18}(\.\d{1,5})?$'
      description: Monto decimal no negativo; máximo 18 dígitos y 5 decimales.
      example: "1250.50"
    currency:
      type: string
      pattern: '^[A-Z]{3}$'
      description: Código de moneda ISO 4217.
      example: PEN
```

### `AccountIdentification`
```yaml
AccountIdentification:
  type: object
  description: Identificación de la cuenta. Exactamente una de las dos opciones.
  oneOf:
    - required: [iban]
    - required: [other]
  properties:
    iban:
      type: string
      pattern: '^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$'
    other:
      type: object
      required: [identification, schemeName]
      properties:
        identification: { type: string, maxLength: 34 }
        schemeName:
          type: object
          properties:
            code: { type: string, description: ExternalAccountIdentification1Code }
            proprietary: { type: string, description: 'Esquema local, p. ej. "CCI"' }
```

### Datos sensibles
Se devuelven enmascarados salvo autorización explícita de la operación:
`identification` (documento de la parte), `account.identification`, número de tarjeta (nunca completo).

---

## 6. Eventos (AsyncAPI)

**Formato del envelope:** CloudEvents 1.0 — `id` (UUID, para deduplicar), `source`, `type`, `specversion`, `time` (cuándo ocurrió el hecho), `datacontenttype`, extensión `correlationid`.
**Canal:** `<service-domain>.<objeto-de-negocio>.<hecho>.v<n>` en minúsculas y `kebab-case`.
**`type`:** `pe.<organizacion>.<service-domain>.<Evento>.v<n>`.

| Evento | Canal | Clave de partición | Se emite cuando | Equivalente ISO |
|---|---|---|---|---|
| `PaymentAccepted` | `payment-execution.payment.accepted.v1` | `debtorAccount.identification` | `transactionStatus` pasa a `ACSP` | pacs.002 |
| `PaymentSettled` | `payment-execution.payment.settled.v1` | `debtorAccount.identification` | `transactionStatus` pasa a `ACSC` | pacs.002 |
| `PaymentRejected` | `payment-execution.payment.rejected.v1` | `debtorAccount.identification` | `transactionStatus` pasa a `RJCT` | pacs.002 |
| `PaymentReturned` | `payment-execution.payment.returned.v1` | `creditorAccount.identification` | Se devuelven fondos liquidados | pacs.004 |
| `AccountEntryBooked` | `current-account.account-entry.booked.v1` | `account.identification` | Un movimiento pasa a `BOOK` | camt.054 |
| `PartyUpdated` | `party-reference-data-directory.party.updated.v1` | `partyId` | Cambian datos de referencia de la parte | — |

Eventos en inglés, en pasado y en `PascalCase`. Un evento que ordena hacer algo es un comando (`ExecutePayment`) y va en un canal de comandos, no de eventos.
