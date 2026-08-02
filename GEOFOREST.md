# Vinculação com o GeoForest-IA

O **GeoForest-IA** (plataforma de geoprocessamento florestal) é o principal consumidor e o publicador de camadas deste WMS.

- Repo: `github.com/alvaro209890/GeoForest-IA`
- Backend: Node/Express, porta 3001 (`geoforest-backend.service`)
- App: `ia-florestal.web.app` | API: `geoforest-api.cursar.space`

## Publicação de camadas (GeoServer → dados)

O backend publica imagens no GeoServer via **REST local** (`http://127.0.0.1:8081/geoserver`) com credenciais de admin do GeoServer definidas em env (`GEOSERVER_USER`/`GEOSERVER_PASSWORD` no backend — **não versionar**).

| Módulo | Função | Detalhes |
|---|---|---|
| `backend/cbers-archive.ts` | `publishCbersPanToArchive()` → `publishGeoTiff()` | Publica cenas CBERS: cria coveragestore → publica layer → adiciona ao layer group → verifica via WMS GetMap |
| `backend/landsat.ts` | `publishLandsatGeoTiff()` | Mesmo pipeline para Landsat |
| `backend/lib/map-utils.ts` | Capabilities + snapshot cache | Usa o WMS **externo** da SEMA (`geo.sema.mt.gov.br/geoserver/ows`), não o local |

Pipeline de publicação:

1. Baixa/processa a cena → TIF em `/media/server/HD Backup/RASTER/CBERS_4A/{orbita}/{ano}/`
2. Cria symlink em `/home/server/.local/geoserver-work/data_dir/external/cbers/{orbita}/{ano}/{cena}/` — **é daqui que vêm os symlinks de external/**
3. `POST` REST: cria coveragestore (tipo GeoTIFF) apontando para o symlink
4. Publica a layer + adiciona nos layer groups (`orbit_{X}_{Y}_y{AAAA}` → `orbit_{X}_{Y}` → `CBERS-4A-Apos_2019` → `RASTER`)
5. Verifica com `GetMap` na URL pública `https://wms.cursar.space/geoserver/cbers/wms`
6. Retry com backoff curto; aguarda o GeoServer subir (útil após restart)

## Consumo do WMS público

| Módulo | Uso | URL base |
|---|---|---|
| `backend/cbers-wpm.ts` | Análise de imagens CBERS 4A WPM (jobs, bbox) | `GEOSERVER_PUBLIC_WMS_BASE` → `https://wms.cursar.space/geoserver/cbers/wms` |
| `backend/landsat.ts` | Análise de imagens Landsat (jobs, bbox) | idem (`GEOSERVER_PUBLIC_WMS_BASE`) |
| `backend/cbers-archive.ts` | Verificação pós-publicação (GetMap) | idem |
| `backend/lib/map-utils.ts` | Capabilities/snapshot do mapa | SEMA externa (não é este WMS) |

Variáveis de ambiente do backend relacionadas:

- `GEOSERVER_PUBLIC_WMS_BASE` — override da URL pública do WMS (default `https://wms.cursar.space/geoserver/cbers/wms`)
- `GEOSERVER_BASE_URL` — REST local (default `http://127.0.0.1:8081/geoserver`)
- `GEOSERVER_USER` / `GEOSERVER_PASSWORD` — admin REST (defaults locais)
- `SEMA_WMS_BASE_URL` / `SEMA_WMS_AUTHKEY` — WMS da SEMA (externo)

## Fluxo de dados completo

```
INPE/USGS ──► GeoForest backend ──► RASTER/ (HD)
                    │                     │
                    │  REST 8081          │ symlink
                    ▼                     ▼
              GeoServer ◄──── external/cbers (symlinks)
                    │
                    │ WMS público (wms.cursar.space)
                    ▼
        Análises CBERS/Landsat do GeoForest
        (jobs de imagem por bbox + recorte)
```

## Dependência operacional

- Se o GeoServer cair, o **healthcheck** (`geoserver-wms-healthcheck.timer`, a cada 2 min) reinicia os serviços em cascata (ver [SERVICOS.md](SERVICOS.md)).
- O pipeline de publicação do GeoForest tem retry com backoff e espera o GeoServer responder antes de publicar.
- O sync mensal `car-digital-sync` (SIMCAR + Fiscalização) roda depois do `geoserver-wms.service` (`After=`) e atualiza os vetores que o WMS serve.
