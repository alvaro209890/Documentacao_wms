# WMS — Documentação Técnica

Documentação do serviço **GeoServer WMS** rodando no PC `server-desktop` do Álvaro, incluindo arquitetura, dados, operação e vinculações com o GeoForest-IA.

> ⚠️ Este repositório é **público**. Não incluir senhas, tokens ou chaves — só referências a onde vivem.

---

## Índice

| Arquivo | Conteúdo |
|---|---|
| [ARQUITETURA.md](ARQUITETURA.md) | Os 3 serviços (GeoServer, proxy, tunnel), fluxo de requisição e diagrama |
| [DADOS.md](DADOS.md) | Onde vivem os dados, camadas, grupos, discos e limpeza |
| [GEOFOREST.md](GEOFOREST.md) | Vinculação com o GeoForest-IA (publicação + consumo) |
| [SERVICOS.md](SERVICOS.md) | Systemd, timers, healthcheck e sync automático |
| [OPERACAO.md](OPERACAO.md) | Comandos de diagnóstico, testes e troubleshooting |
| [SEGURANCA.md](SEGURANCA.md) | Proxy público, exposição de camadas e decisões |

## Resumo executivo

- **GeoServer** (Jetty + JDK 17) na porta **8081**, data dir em `/home/server/geoserver_data` (~13GB de configuração + vetores)
- **Proxy Python** na porta **8082** — filtra requests públicos, reescreve GetCapabilities (expõe só RASTER/VETOR)
- **Tunnel Cloudflare** — `https://wms.cursar.space` → 8082
- **737 camadas** no workspace `cbers`: CBERS-4A WPM, Landsat, SPOT SEMA, SIMCAR Digital e Fiscalização
- **Raster (729 camadas)** leem direto do HD de 2TB (`/media/server/HD Backup/RASTER`, 520GB)
- **Vetores (38 camadas SIMCAR/Fiscalização)** também no HD de 2TB (`/media/server/HD Backup/GEOSERVER/data/cbers`, via symlink — migrados do SSD em 2026-08-01)
- **Principal integração:** GeoForest-IA publica camadas CBERS/Landsat via REST local e consome o WMS público para análise de imagens

*Documentado em 2026-08-01. Operações registradas em [CHANGELOG.md](CHANGELOG.md).*
