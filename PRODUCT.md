# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

O utilizador principal é um administrador de uma rede própria ou autorizada, que precisa de perceber o estado da rede local, investigar alterações e aplicar políticas de acesso quando a infraestrutura suporta essa operação. O produto também é apresentado como um projeto de portfólio técnico.

## Product Purpose

NetWatch é uma plataforma self-hosted de monitorização e inteligência de redes locais. Descobre dispositivos numa rede autorizada, acompanha disponibilidade e latência, identifica serviços expostos, regista alterações, apresenta atividade DNS disponível e organiza alertas e relatórios num dashboard operacional. Sucesso significa transformar sinais técnicos dispersos numa visão clara e acionável da rede, sem fingir que dados indisponíveis foram observados.

## Positioning

NetWatch combina inventário de dispositivos, monitorização contínua, diagnóstico de atividade e preparação para controlo de acesso numa única ferramenta local, com explicações honestas sobre o que o sensor, o DNS e o router conseguem realmente fornecer. O seu mecanismo distintivo é manter a atribuição histórica de endereços e separar explicitamente observação, inferência e capacidade de enforcement.

## Operating Context

O produto é executado localmente, através de uma interface web e de uma aplicação desktop empacotada, com um backend FastAPI e um sensor de rede no mesmo ambiente operacional. É utilizado em redes privadas autorizadas, incluindo redes domésticas, hotspots ou redes administradas pelo utilizador. O administrador configura a rede monitorizada, inicia scans, acompanha dispositivos e eventos, consulta relatórios e, quando aplicável, liga um fornecedor de DNS ou router/firewall compatível.

## Capabilities and Constraints

- Descoberta de dispositivos em sub-redes privadas explicitamente configuradas.
- Monitorização de estado online/offline, latência, histórico, nomes atribuídos pelo utilizador, hostname e dados de fabricante quando disponíveis.
- Verificação conservadora de serviços TCP aprovados e geração de eventos e alertas para alterações relevantes.
- Atividade DNS apenas quando o tráfego passa por um fornecedor compatível e contém metadados disponíveis; o produto não revela pesquisas exatas, mensagens, passwords ou conteúdo de páginas HTTPS.
- Reatribuição manual de dispositivos a nomes definidos pelo utilizador para que o administrador não dependa de adivinhar a identidade de uma pessoa a partir de um IP.
- Relatórios e exportação de dados para apoiar investigação e documentação.
- Integração de controlo depende de um router/firewall com API ou mecanismo suportado. Sem essa capacidade, NetWatch pode preparar, explicar ou registar uma política, mas não promete bloquear ou colocar dispositivos em quarentena.
- O produto deve operar apenas em redes que o utilizador possui ou está autorizado a administrar. Deve rejeitar alvos públicos e não inclui exploração, ataques a credenciais, evasão ou scanning da Internet.
- As limitações de ARP, ICMP, permissões e redes em bridge Docker variam por sistema operativo e devem ser apresentadas de forma explícita.

## Brand Commitments

- Nome: NetWatch.
- Tagline: “Know what's on your network.”
- Personalidade: profissional, clara, técnica e útil, sem estética hacker estereotipada.
- A interface deve funcionar como produto de monitorização/SaaS de segurança, com linguagem direta e explicações compreensíveis para decisões operacionais.

## Evidence on Hand

- Aplicação existente com frontend Next.js/React/TypeScript, backend FastAPI/Python, persistência SQLAlchemy/SQLite, WebSockets, modo demo e aplicação desktop empacotada.
- Rotas e fluxos existentes para dashboard, dispositivos, rede, serviços, alertas, atividade, histórico, internet/DNS, controlos parentais, relatórios e settings.
- Repositório privado GitHub: `DinisIvanetsD/netwatch`.
- A aplicação já dispõe de verificações de readiness, relatórios e exportação CSV, bem como documentação sobre limitações de DNS/HTTPS e integrações de router.
- Não existe evidência autorizada de uma API local documentada para controlo automático do router NOS/CHITA atualmente utilizado; essa integração não deve ser fabricada.
- Não devem ser inventados nomes de pessoas, pesquisas exatas, relações físicas de topologia, clientes, métricas de mercado ou integrações que não tenham sido verificadas.

## Product Principles

1. Mostrar a verdade operacional: distinguir dados observados, inferências e capacidades indisponíveis.
2. Dar ao administrador contexto acionável, não apenas listas de IPs e portas.
3. Proteger a rede e os seus utilizadores através de escopo privado, validação rigorosa e enforcement explícito.
4. Manter histórico suficiente para explicar mudanças de endereço, estado, serviços e atividade.
5. Tornar os fluxos de scan, investigação, política e recuperação claros e verificáveis.

## Accessibility & Inclusion

A interface deve permanecer legível em desktop, laptop, tablet e acesso móvel básico; suportar teclado, foco visível, semântica adequada, estados de carregamento/erro compreensíveis e não depender apenas de cor para comunicar estado ou severidade. A linguagem deve explicar termos técnicos sem presumir que o administrador sabe a que utilizador pertence cada IP.
