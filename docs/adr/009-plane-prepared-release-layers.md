# 009. Prepared Plane Release Layers

## Status

Accepted for source preparation only. Runtime compatibility, deployment and the
storage-backend decision are not accepted by this record; ADR 008 is reserved
for tested storage selection.

## Context

Plane maintenance crosses database patches, schema changes, object-storage state
and irreversible RabbitMQ flags. Updating all defaults together would collapse
independent gates. The official v1.4.2 app contract removes secret fallbacks, while
existing deployments need preserved credentials, named volumes and broker identity.

## Decision

Keep exact existing source baseline fallbacks until manager acceptance. Independent
dependency version variables allow later explicit promotion. Prepared root Compose
overrides and a versioned nonsecret release manifest live beside Plane under
`stacks/plane/maintenance/`; each stage changes only its owning services. Operators
retain accepted layers cumulatively, freeze actual resolved config/image identities
privately, and invoke only scoped services with no dependencies or implicit pulls.

One target release variable controls all nine app images, including migrator and
proxy. Target backend credentials/URLs and live secrets are required, never
generated or defaulted. Repository `PLANE_DEBUG`, ports, endpoints and named volumes
are intentionally retained. Migrator is explicitly profiled with no failure retry;
schema success precedes writer startup. Storage image/command is prepared separately
and cannot be considered accepted based on configuration rendering.

Rabbit hostname is optional in baseline and required at the upgrade stage. Absent
means no explicit Docker hostname; it does not guarantee node preservation during
recreation. Set the refreshed observed hostname before any existing-node recreation.
Do not introduce new stable names or default nodenames on existing state.

## Alternatives and Consequences

- Changing default images to candidates would permit unreviewed simultaneous
  schema/storage/broker changes; rejected until independent gates pass.
- Replacing config/env wholesale with official assets would change credentials,
  ports and volume identity; rejected in favor of minimal verified adaptation.
- Separate app version variables could create unsupported mixed releases; rejected.
- Generic update or implicit migrator retries obscure irreversible transitions;
  rejected. Explicit operator sequencing and coherent recovery are required.
- Raw Compose is outside the foundation lock; exclusive operator ownership and
  shared locking remain mandatory. Overlay promotion is a separate accepted change.

## Guardrails

Real Compose regression tests check baseline/example consistency, independent pins,
required nonempty target credentials, lockstep images, explicit migrator selection,
storage command/volume contract, unchanged unrelated services and preserved Rabbit
hostname through both version stops. ADR 010 records exec-based Celery launch and
honest stopped-broker evidence; real checkpoint/restore acceptance remains required.
No automatic rollback/resume after migration failure; no deployment completion
claim until real restored-data/application/queue/storage gates pass.
