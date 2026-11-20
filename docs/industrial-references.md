# Industrial design references

IPHI uses selected industrial standards as **design references**, as recorded in
[the engineering rules, S-01 to S-05](../rules.md). This page connects those references
to the implemented demonstrator. It is not a conformity assessment, certification,
claim of full standards implementation or proof of suitability for a real plant.
The external links describe the standards' scope; the repository links show what
IPHI actually implements.

## Résumé en français

- **ISA-95 / IEC 62264** : vocabulaire des fonctions et chaîne de données industrielle.
  Les sept composants simulés ne représentent pas sept niveaux ISA-95.
- **ISA-101** : conception d'une IHM lisible, états compréhensibles sans dépendre
  uniquement de la couleur et priorité visuelle aux situations anormales.
- **ISA-18.2 / IEC 62682** : principes de gestion des alarmes repris pour les incidents :
  règles justifiées, temporisation, hystérésis, déduplication, prise en compte et historique.
- **ISA/IEC 62443** : réflexion sur les frontières OT, le moindre privilège et
  l'absence d'action vers les équipements. IPHI reste une démonstration locale sans
  connexion à une usine ni validation de zones et conduits industriels.
- **Sémantique de qualité OPC UA** : mesures `good`, `uncertain`, `bad` ; une mesure
  de mauvaise qualité n'étaye pas un état sain. Cela n'implique pas un connecteur OPC UA.

En entretien : « J'ai utilisé ces références pour guider certains choix de conception,
et je peux montrer leur traduction dans le code et les tests. Je ne présente pas IPHI
comme un produit certifié ou validé sur une installation industrielle réelle. »

## ISA-95 / IEC 62264 — functional vocabulary and data flow

[ISA's description of ISA-95](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard)
defines a functional model and terminology for enterprise/control integration.
IPHI borrows the vocabulary to explain why a source, gateway, collector, historian
and consuming services have different responsibilities and dependencies.

**Implementation evidence:** the [simulated platform](../backend/app/simulation/domain/platform.py)
and [topology model](../backend/app/topology/domain.py) describe seven components and
directed dependencies. [Topology tests](../backend/tests/unit/test_topology_domain.py)
verify the chain, transitive downstream impact and rejection of cycles.

**Boundary:** IPHI does not assign a certified ISA-95 level to each software service,
implement the full ISA-95 information model or exchange MES/ERP transactions. A data
dependency graph is not evidence of industrial network segmentation.

## ISA-101 — human-machine interface design

[ISA-101](https://www.isa.org/standards-and-publications/isa-standards/isa-101-standards)
addresses the design and lifecycle of industrial HMIs. IPHI's written design system
uses a restrained background, abnormal-state emphasis, consistent navigation and
redundant status coding: shape, text and colour together.

**Implementation evidence:** [design system](04-design-system.md),
[ADR 0009](adr/0009-frontend-design-system.md) and
[health badges](../frontend/src/shared/status/HealthBadge.tsx). The real dashboard
and [recorded walkthrough](video-demo.md) show the resulting presentation. Component
tests include accessibility checks; the browser journeys exercise actual screens.

**Boundary:** the particular palette and shapes are IPHI design decisions inspired
by high-performance HMI practice. They are not a claim that an ISA clause prescribes
these exact tokens, or that the full HMI lifecycle has been assessed for conformity.

## ISA-18.2 / IEC 62682 — alarm-management principles

[ISA-18](https://www.isa.org/standards-and-publications/isa-standards/isa-18-series-of-standards)
and [the relationship to IEC 62682](https://www.isa.org/intech-home/2020/march-april/features/alarm-management-questions-that-everyone-asks)
provide the alarm-management context. IPHI reuses selected ideas for its platform
incidents: a rule's rationale and recommended checks, confirmation/recovery windows,
separate clear thresholds, one active incident per fingerprint, downstream impact
grouping, acknowledgement and recorded transitions.

**Implementation evidence:** [hysteresis](../backend/app/health/domain/hysteresis.py),
[incident engine](../backend/app/incidents/domain/engine.py),
[hysteresis tests](../backend/tests/unit/test_health_hysteresis.py) and
[incident-engine tests](../backend/tests/unit/test_incident_engine.py).
The [demo](demo.md) verifies repeated errors without an incident storm and stable
recovery. Acknowledging an incident does not clear its underlying condition.

**Boundary:** an IPHI incident is not a process-safety alarm. The demonstrator does
not implement the entire industrial alarm-management lifecycle, a site's alarm
philosophy, operator training programme or formal alarm-system performance assessment.

## ISA/IEC 62443 — security boundaries and least privilege

[ISA/IEC 62443](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards)
addresses industrial automation/control-system cybersecurity. The
[zones-and-conduits design context](https://www.isa.org/getmedia/661c718f-8e64-446d-acf9-2c6286db1b33/isa-62443-3-2-preview.pdf)
informs IPHI's boundary: no OT writes, commands or automatic remediation, and any
future real connection requires an explicit integration and safety review.

**Implementation evidence:** [local sessions and roles](access.md),
[ADR 0025](adr/0025-identity-sessions-us11.md),
[server authorization tests](../backend/tests/integration/test_identity.py) and
[Compose](../compose.yaml). Viewer/engineer/admin permissions are enforced by the
server; default published ports bind to loopback. The optional MQTT network carries
synthetic observations, as documented in [the MQTT guide](mqtt.md).

**Boundary:** these local controls do not establish IEC 62443 conformity, a security
level or a validated industrial zone/conduit architecture. There is no connected OT
system under assessment and no production-deployment claim.

## OPC UA quality semantics — observation usability

The OPC Foundation distinguishes
[Good, Uncertain and Bad status severities](https://reference.opcfoundation.org/specs/OPC-10000-6/a-2).
IPHI preserves the corresponding three quality labels with observations and excludes
bad samples from rule evidence.

**Implementation evidence:** [observation vocabulary](../backend/app/core/observation.py),
[rule evaluation](../backend/app/health/domain/evaluation.py) and
[bad-quality regression test](../backend/tests/unit/test_health_evaluation.py).
Quality describes whether a measurement can be used; it is separate from component
health. For example, a good-quality observation of `up = 0` can justify `Critical`.

**Boundary:** this is a three-label abstraction, not an OPC UA client, complete
StatusCode implementation or interoperability claim. The implemented optional
transport is MQTT; [ADR 0011](adr/0011-connecteur-mqtt.md) records that choice.

## Supporting software references

The [reference register](../rules.md) also names RFC 3339 / ISO 8601 for UTC timestamps,
RFC 9457 for structured API errors, OpenAPI 3.1 for generated contracts, WCAG 2.2 AA
for accessibility targets and OWASP guidance for application/LLM security. These
support the implementation; they are distinct from the industrial references above.
Automated checks and tested interaction paths are evidence for those paths, not a
blanket certification of the entire product.
