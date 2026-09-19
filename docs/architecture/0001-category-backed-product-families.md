# ADR 0001: Category-backed product families

Status: Proposed

Date: 2026-09-19

## Context

Control V2 needs a product-family model that can present one style with selectable
variants while preserving the exact stock identities used by Profit+ for price,
stock, orders and assembly recipes.

Read-only research of the legacy OGL web catalogue found an explicit grouping
relationship. A `WebCategories` row with `grpproducts = 'Y'` represents a
displayable product group, and `WebCategoryProducts` assigns exact stock codes to
that group with a display order. Variant attributes such as size are held in
`WebProductAttributes`.

The reviewed BioMarsh example provides concrete evidence:

- category `002c0004000d0018` is titled "HV938 Orange Hi Vis Stormcoat cw Bio
  Marsh Logo" and has `grpproducts = 'Y'`;
- it contains nine exact variants, ordered from XSmall through 5XLarge;
- the customer-facing mirror category `000100180574000d0018` contains the same
  nine variants;
- there is no stock item named `BIOM/HV938/HO/T5192`;
- each exact variant, such as `BIOM/HV938/HO/S/T5192`, is a separate Q24
  assembly;
- that Small assembly has exact components `CHV938/HO/S`, `TMP5192` and
  `TMP5192BACK`, each with quantity one.

At the wider catalogue level, the two reviewed BioMarsh personalised-category
trees contained identical sets of 442 exact SKUs. This establishes useful
legacy grouping evidence, but OGL remains historical and reconciliation
evidence. It does not become V2's current product authority through this ADR.

## Decision

V2 will model a product family separately from its sellable product variants.

The family will have a durable V2 identifier. Every source category used to
establish or place that family will be retained as a source identifier with its
observation and translation provenance. An operator-friendly key such as
`BIOM/HV938/HO/T5192` may be exposed as an alias after validation, but it is not
an ERP stock code and must never be sent to Profit+ as one.

Each family member remains an exact product identity. Price, stock, order-line
membership and Q24 recipe evidence attach to that exact variant, not to the
family. A family can offer a shared presentation and size selector without
collapsing operational facts across its members.

Initial legacy translation will use these relationships:

| V2 concept | Legacy evidence |
| --- | --- |
| Family source identity | `WebCategories.category` where `grpproducts = 'Y'` |
| Family title | `WebCategories.ctitle` |
| Variant membership | `WebCategoryProducts.category + stockcode` |
| Variant display order | `WebCategoryProducts.lstorder` |
| Variant label/size | `WebProductAttributes` with its retained attribute identity |
| Exact sellable product | `WebProducts.stockcode` resolved to the canonical V2 product |
| Customer catalogue placement | the retained category path and catalogue scope |
| Customer price | exact variant price evidence for the accepted customer price source |
| Manufacturing recipe | exact Q24 `assemcode` and component rows for the variant |

Family membership must come from accepted relationship evidence. SKU parsing
may propose or validate a friendly alias, but it cannot create membership,
recipes or operational product identities.

Mirrored category placements must not create duplicate families. A translator
may merge two source categories only under a versioned, reviewed rule that
proves the relationship, including exact member-set parity for the observation
being translated. Matching titles alone are insufficient. Both source category
identities remain attached to the resulting family as catalogue placements.

Q24 recipes remain variant-specific. V2 may later project a family-level recipe
template for comparison or presentation, but that projection cannot replace the
exact recipe used for availability, assembly or fulfilment decisions.

## Proposed relational shape

The final migration names may change, but the domain needs these distinct
grains:

```text
inventory.product_family
  family_id
  display_name
  friendly_key

inventory.product_family_source
  family_id
  source_system
  source_dataset
  source_category_key
  source_observed_at
  translator_version

inventory.product_family_member
  family_id
  product_id
  variant_label
  display_order
  effective_at
  source_observation_id

inventory.product_family_placement
  family_id
  catalogue_scope_id
  source_category_key
  source_observation_id
```

Uniqueness and temporal rules must prevent duplicate current membership for the
same family and exact product while retaining changes as evidence rather than
overwriting history.

## Consequences

- The portal can show one style card with an ordered size selector.
- Stock, prices, recipes and order lines remain exact and reconcilable.
- Customer-specific catalogue membership is explicit instead of inferred from
  prefixes such as `BIOM/`.
- Mirrored navigation trees become placements of one family rather than
  duplicate products.
- A missing or stale category observation cannot silently remove a variant;
  lifecycle and absence rules require a separate accepted contract.
- V2 needs a versioned family translator and reconciliation report before this
  model can become authoritative.

## Acceptance work

Before implementation or cutover:

1. Define the source observation contract for categories, category membership
   and variant attributes.
2. Prove stable category and membership keys across repeated captures.
3. Classify mirrored-category relationships beyond the reviewed example.
4. Define freshness, revisit and deletion semantics for category membership.
5. Reconcile translated family, placement and member counts against reviewed
   legacy catalogues.
6. Confirm every operational member resolves to one canonical exact product.
7. Keep recipe authority on exact Q24 assemblies and report missing or partial
   recipes explicitly.

