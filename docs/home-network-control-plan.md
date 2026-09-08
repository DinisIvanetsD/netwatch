# Home Network Control integration plan

NetWatch currently provides live device discovery, TCP service observations, latency history,
events, alerts, scheduled scans, and WebSocket refreshes. It does not currently ingest DNS
queries or traffic-flow metadata and it has no router/firewall control integration.

## Integration boundaries

- DNS visibility and filtering are supplied only by a configured `DNSControlProvider` such as
  AdGuard Home or Pi-hole.
- Device network controls are supplied only by a configured `NetworkControlProvider` such as
  OpenWrt, OPNsense, or UniFi.
- The built-in generic provider is read-only. Unsupported actions remain disabled and return a
  capability error if called through the API.
- NetWatch stores network metadata only. It does not intercept TLS, inspect page contents,
  capture credentials, or claim that a DNS observation represents exact usage time.

## Delivery sequence

1. Add typed provider contracts, capability reporting, and safe unsupported-operation errors.
2. Add encrypted integration configuration and an AdGuard Home provider using its documented API.
3. Normalize and classify observed domains in one backend service.
4. Persist per-device Internet activity and expose paginated aggregate APIs.
5. Add profiles, assignments, categories, domain rules, schedules, access state, blocked requests,
   control actions, and audit records through migrations.
6. Add policy evaluation with explicit precedence and provider-confirmed mutations.
7. Add parental controls, blocked requests, access control, integrations, and capability UI.
8. Expand demo mode, alerts, WebSocket events, retention, tests, and documentation.

## Policy precedence

Highest to lowest priority:

1. Explicit device block
2. Temporary administrator override
3. Device-specific rule
4. Assigned profile
5. Global policy
6. Default allow

Manual trust and access decisions are persistent and are never overwritten by discovery scans.
