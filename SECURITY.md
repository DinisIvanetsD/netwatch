# Security Policy

## Authorized use

NetWatch is designed only for private networks that you own or are explicitly authorized to administer. Do not use it to scan public targets or bypass network controls.

## Deployment boundary

NetWatch is a single-operator, self-hosted application and does not currently provide user authentication. Keep the API and dashboard on a trusted LAN, loopback interface, VPN, or behind an authenticated reverse proxy. Do not expose the default deployment directly to the public Internet.

For production deployments, use HTTPS, set `NETWATCH_ENV=production`, configure exact `ALLOWED_HOSTS` and `CORS_ORIGINS`, keep the database volume private, and run the scanner with only the operating-system permissions required by the selected discovery adapter.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's private vulnerability reporting feature for this repository. Include affected versions, reproduction steps, impact, and any suggested mitigation. Do not open a public issue for an unpatched vulnerability.

