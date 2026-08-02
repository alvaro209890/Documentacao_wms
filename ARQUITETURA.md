# Arquitetura

## Visão geral

```
                    Internet
                       │
                       ▼
        ┌──────────────────────────────┐
        │  Cloudflare Tunnel (QUIC)     │
        │  wms.cursar.space             │
        │  geoserver-wms-tunnel.service │
        └──────────────┬───────────────┘
                       │ 127.0.0.1:8082
                       ▼
        ┌──────────────────────────────┐
        │  Proxy Python                 │
        │  geoserver_wms_public_proxy.py│
        │  geoserver-wms-public-proxy.  │
        │  service (porta 8082)         │
        └──────────────┬───────────────┘
                       │ 127.0.0.1:8081
                       ▼
        ┌──────────────────────────────┐
        │  GeoServer (Jetty + JDK 17)  │
        │  geoserver-wms.service       │
        │  porta 8081                  │
        │  data dir: geoserver_data/   │
        └──────┬──────────────┬────────┘
               │              │
      ┌────────▼──────┐  ┌────▼──────────────┐
      │ HD 2TB        │  │ SSD               │
      │ RASTER/       │  │ data/cbers/       │
      │ (520GB rasters│  │ (vetores SIMCAR + │
      │  CBERS/Landsat│  │  Fiscalização)    │
      │  /SPOT)       │  └───────────────────┘
      └───────────────┘
```

## Serviços (systemd user)

| Serviço | Porta | Processo | Função |
|---|---|---|---|
| `geoserver-wms.service` | 8081 | java (Jetty) | GeoServer em si — WMS/WFS/WMTS |
| `geoserver-wms-public-proxy.service` | 8082 | python3 | Proxy público: filtro + reescrita de capabilities |
| `geoserver-wms-tunnel.service` | — | cloudflared | Tunnel `wms.cursar.space` → 127.0.0.1:8082 |

Units em `/home/server/.config/systemd/user/`.

### GeoServer (8081)

- Java: JDK 17 (`/home/server/.local/geoserver-work/jdk-17.0.18+8`)
- Jetty base: `/home/server/.local/geoserver-work`
- Data dir: `-DGEOSERVER_DATA_DIR=/home/server/geoserver_data`
- Memória: `-Xms512m` (sem `-Xmx` explícito — usa default da JVM; pico observado ~4.8GB)
- Headless: `-Djava.awt.headless=true`
- Stop: porta 8079, key `geoserver`

### Proxy Python (8082) — `~/.local/bin/geoserver_wms_public_proxy.py`

Responsabilidades:

1. **Filtro de path**: só aceita `/geoserver/...` terminando em `/ows`, `/wms`, `/wfs`, `/wmts`, ou `/geoserver/schemas/...`. Fora disso → 403.
2. **Reescrita do GetCapabilities do WMS** (só no path `/geoserver/cbers/wms`):
   - Corta a árvore de camadas: expõe **apenas os grupos RASTER e VETOR**
   - Renomeia o grupo "Fiscalização" → "FISCALIZAÇÃO"
   - Adiciona sufixo `-publicproxy2` no `updateSequence`
   - Remove headers de cache (`Cache-Control: no-store, no-cache` etc.)
3. **Força WMS 1.1.1** quando o cliente pede capabilities sem `version` (clientes GIS travam com o XML 1.3.0 default).
4. Encaminha headers `X-Forwarded-For/Proto/Host` para o upstream.

> **Limitação conhecida:** o proxy filtra por path, **não valida nomes de camada** (`layers=`, `typeName=`). Qualquer camada responde por GetMap/GetFeatureInfo/GetFeature direto, e o **WFS GetCapabilities não é reescrito** — lista as 737 camadas completas. Decisão do proprietário: **manter como está** (ver [SEGURANCA.md](SEGURANCA.md)).

### Tunnel Cloudflare — `wms.cursar.space`

- Config: `/home/server/.cloudflared/config.yml` (túnel `geoserver-wms`)
- Protocolo QUIC, edge GRU (São Paulo)
- Hostname público: `https://wms.cursar.space/geoserver/cbers/wms`

## URLs de referência

| Camada | URL |
|---|---|
| Admin local | `http://127.0.0.1:8081/geoserver/cbers/wms` |
| Proxy local | `http://127.0.0.1:8082/geoserver/cbers/wms` |
| Público | `https://wms.cursar.space/geoserver/cbers/wms` |

## Fluxo de uma requisição GetMap pública

1. Cliente GIS → `https://wms.cursar.space/geoserver/cbers/wms?service=WMS&request=GetMap&layers=...`
2. Cloudflare Tunnel reencaminha para `127.0.0.1:8082`
3. Proxy valida path (termina em `/wms`) → encaminha para `127.0.0.1:8081` com `Host` do upstream
4. GeoServer renderiza: raster lê do HD (RASTER/), vetores leem do SSD (data/cbers/)
5. Resposta PNG volta pelo mesmo caminho (proxy não cacheia tiles)
