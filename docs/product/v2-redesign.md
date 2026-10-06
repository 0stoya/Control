# Control V2 redesign brief

Status: Existing design targets consolidated on 2026-10-06; connected V2 UI not implemented.

The operator requested a review of the planned Control redesign for V2.
This brief indexes the existing targets and their delivery gates. It does not
declare every prototype or proposed metric accepted or deployed.

## Product direction

Control is the next CRM and operations platform for the business, with Promise/SLA,
Planning, Purchasing, Sales and Operations central. Staff land in their
permissioned operational workspace; shared CRM navigation connects customer,
supplier, contact, product, quotation, order and relationship history.

Use durable domain identities and linked timelines, preserving CSS-owned notes,
tasks, decisions, policy and audit. Source refresh must not erase this knowledge.
Retain the proven Promise Engine semantics and distinguish physical fulfilment,
despatch posting, invoice and finance facts.

## Documented screen changes

| Area | Design target | Evidence/state |
| --- | --- | --- |
| Shared navigation and CRM | Operational workspace entry plus shared records/history; link conversations and tasks to the same identities | Proposed connected shell in the Profit+ replacement map |
| Purchasing home | Purchasing-today actions; summary cards; PO value/history/activity; carriage panel; priority rail; stock/Core health and needs-a-PO shortlist | Explicit V2 target; several connected metrics remain gated |
| Purchasing demand | Core replenishment and customer demand enter supplier review, durable baskets and the ordinary PO editor; clear buying reason, minimum-value gap and duplicate protection | Mixed implementation/prototype status; native assignment and several acceptance gates remain open |
| Products | One family/style with ordered variants; exact SKU price, stock and assembly facts remain attached to each variant | Control ADR 0001 proposed |
| Planning | Useful factual review when decision evidence is unavailable; approved evidence enables the server-ranked decision queue | Existing V1 implementation contract to preserve |
| Order history | Stable identity and timeline across current/archive movement, independent commercial/fulfilment/finance dimensions | V2 architectural goal and proposed first business slice |
| Purchasing email inbox | Read purchasing mail, link a supplier confirmation to the exact sent PO revision, show variant/quantity/price and timing differences, retain staff review | Operator requested; local extraction/comparison core implemented; collection, permissions, API/UI pending |

The Purchasing target specifies four summary cards per row on desktop, a broad
main column and narrow priority rail; two cards and stacked panels on smaller
screens. Its visual conventions are white cards, navy text, pale-blue totals,
navy to-book values and amber above-average bars. Red signals validated stock
exceptions. These are the documented Purchasing conventions, not a final design
system for every V2 screen.

Planned panels display labelled dashes and awaiting states. Real metrics require
an accepted population, currency/unit basis, provenance, freshness, complete
server-side aggregates and matching drilldowns. Page counts are never whole-book
totals; PO-line counts are never relabelled as order counts. Missing history
appears as gaps. Technical source detail belongs in a source-information view;
staff see useful action/status messages.

## Proposed V2 delivery sequence

1. Private native foundation: deployed and locally restored; public staff rollout pending.
2. Authentication continuity and a connected navigation shell, with retained
   workspace entry, record-level Sales scope and explicit V2 permissions.
3. Sales Order Timeline and precisely named warehouse/settled despatch views:
   write the source contract, build evidence translation and projections, then
   authenticated API/UI and reconciliation. No synthetic operational totals.
4. Connect CRM record context around that slice; migrate reviewed durable CSS state.
5. Purchasing target panels independently: reconcile current outstanding value
   before history; stock thresholds before Core health/valuation; shortage review
   before separately accepted creation actions. Reuse verified existing workflows.
6. Product families and further workspace capabilities after source-specific
   identity, freshness and reconciliation acceptance.

This sequence is a proposed practical delivery order. The legacy replacement map
also proposes customer/contact relationship views as its first CRM slice.
Final screen layouts and source contracts are frozen within each implementation
slice; the consolidated brief does not silently resolve unaccepted domain rules.

## Design evidence

CSS design documents were reviewed at local revision
e75b895c27883a4b8572e45dc4c811b73f141c4e. Their historic deployment claims
retain their original scope; local code and live installed revisions can differ.

- [Profit+ replacement map: workspace and shared CRM direction](https://github.com/0stoya/CSS/blob/e75b895c27883a4b8572e45dc4c811b73f141c4e/docs/modernisation/PROFITPLUS_REPLACEMENT_MAP.md)
- [Stand-alone CRM target architecture](https://github.com/0stoya/CSS/blob/e75b895c27883a4b8572e45dc4c811b73f141c4e/docs/modernisation/STANDALONE_CRM_TARGET_ARCHITECTURE.md)
- [Purchasing home: explicit V2 prototype roadmap](https://github.com/0stoya/CSS/blob/e75b895c27883a4b8572e45dc4c811b73f141c4e/docs/purchasing-home-prototype-roadmap.md)
- [Demand, shortages, supplier review and buying rules](https://github.com/0stoya/CSS/blob/e75b895c27883a4b8572e45dc4c811b73f141c4e/docs/raise-orders-from-demand-roadmap.md)
- [Planning review/decision presentation contract](https://github.com/0stoya/CSS/blob/e75b895c27883a4b8572e45dc4c811b73f141c4e/docs/modernisation/STAGE4_PLANNING_REDESIGN.md)
- [Control ADR 0001: exact variants within product families](../architecture/0001-category-backed-product-families.md)
- [Production launch configuration](../runbooks/production-launch.md)
