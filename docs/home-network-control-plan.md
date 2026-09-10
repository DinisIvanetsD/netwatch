# Home Network Control integration

NetWatch provides live device discovery, TCP service observations, latency history, events,
alerts, scheduled scans, WebSocket refreshes, Technitium DNS query metadata, and optional
router/firewall control through documented provider APIs. It does not decrypt HTTPS traffic.

## Integration boundaries

- DNS visibility and filtering are supplied only by a configured `DNSControlProvider`. The
  shipped provider is Technitium DNS Server with Query Logs and Advanced Blocking.
- Device network controls are supplied only by a configured `NetworkControlProvider` such as
  OpenWrt or OPNsense. NOS/Hitron remains a manual fallback until a supported API is verified.
- The built-in generic provider is read-only. Unsupported actions remain disabled and return a
  capability error if called through the API.
- NetWatch stores network metadata only. It does not intercept TLS, inspect page contents,
  capture credentials, or claim that a DNS observation represents exact usage time.

## Current provider status

- OpenWrt: authenticated ubus control, MAC-based managed rules, Internet block/release, and
  persistent device rule block/release.
- OPNsense: authenticated REST firewall rules, IP-based managed rules, and explicit apply/remove
  confirmation. Standard OPNsense pf rules do not provide MAC matching, so NetWatch validates
  the current IP owner before every control operation.
- Technitium: DNS-only containment; it is not LAN quarantine and can be bypassed by direct IP,
  encrypted DNS, or VPN traffic.
- NOS/Hitron: monitoring and manual Device Filter only; the application never scrapes its UI or
  claims an automatic block succeeded.

## Delivery sequence

1. Add typed provider contracts, capability reporting, and safe unsupported-operation errors.
2. Add encrypted integration configuration and a Technitium provider using its documented API.
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
