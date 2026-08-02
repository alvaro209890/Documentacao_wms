# Dados

## Onde vivem os dados (verificado 2026-08-01)

| Tipo | Onde | Tamanho | Camadas |
|---|---|---|---|
| Raster CBERS/Landsat/SPOT | `/media/server/HD Backup/RASTER/` (HD 2TB) | 520GB | 729 (stores `file:/media/server/HD%20Backup/RASTER/...`) |
| Vetores SIMCAR Digital + Fiscalização | `/media/server/HD Backup/GEOSERVER/data/cbers/` (HD 2TB, via symlink) | ~13GB | 38 (datastores apontam para `geoserver_data/data/cbers/`, resolvido por symlink) |
| Config do GeoServer | `/home/server/geoserver_data/` | — | — |
| Stores CBERS 2026 (via symlink) | `/home/server/.local/geoserver-work/data_dir/external/cbers/` | 2.1MB (links) | 8 |

> **Migração 2026-08-01:** os vetores (~13GB) foram movidos do SSD para o HD (`/media/server/HD Backup/GEOSERVER/data/cbers/`) com symlink em `geoserver_data/data/cbers`. Nenhum datastore foi alterado; o sync mensal segue funcionando pelo mesmo path. Ver [CHANGELOG.md](CHANGELOG.md).

### Estrutura de pastas do data dir

```
/home/server/geoserver_data/
├── data/cbers/            ← vetores ATIVOS (SIMCAR + Fiscalização) — NÃO apagar
├── workspaces/cbers/      ← 737 definições de camadas + 306 layergroups
├── styles/                ← SLD (default_raster, landsat_rgb, ...)
├── gwc/ + gwc-layers/     ← cache/config GeoWebCache (uso mínimo)
├── logs/                  ← geoserver.log (rotaciona em ~20MB)
└── security/, wms.xml, wfs.xml, ...
```

### Estrutura dos rasters no HD

```
/media/server/HD Backup/RASTER/
├── CBERS_4A/{orbita}/{ano}/CBERS_4A_WPM_*.TIF
├── LANDSAT/{orbita}/{ano}/...
└── SPOT/SPOT_SEMA/{municipio}/{tile}/extracted/mosaico_*.tif
```

## Camadas por categoria (workspace `cbers`)

| Categoria | Exemplos | Origem |
|---|---|---|
| CBERS-4A WPM | `213_129_2026_cbers_4a_wpm_...` | INPE, HD |
| Landsat | `landsat_224_069_2023_l9_...` | USGS, HD |
| SPOT SEMA | `spot_sema_canarana_...`, mosaicos por município | SEMA-MT, HD |
| SIMCAR Digital | `car_digital_simcar_d_simcar_d_*` (APP, ARL, AUAS, rios, tipologia vegetal, ...) | sync mensal, SSD |
| Fiscalização | `fiscalizacao_autos_de_infracao*`, `fiscalizacao_areas_embargadas_sema` | sync mensal, SSD |
| Grades | `GRADE_CBERS4`, `GRADE_CBERS_4A_WPM`, `GRADE_LANDSAT` | — |

## Layer groups (306)

Hierarquia principal:

```
RASTER
├── CBERS-4A-Apos_2019 → orbit_{X}_{Y} → orbit_{X}_{Y}_y{AAAA} → layer
└── LANDSAT → landsat_orbit_{X}_{Y} → landsat_orbit_{X}_{Y}_y{AAAA} → layer
VETOR
├── SIMCAR_DIGITAL
├── FISCALIZACAO
└── SPOT_SEMA (grupos por município/tile)
```

Outros: `SPOT`, `SPOT_SEMA`, `GRADES_DE_SATELITE`, `CBERS-4A-Apos_2019`.

## Pontos de atenção

- **SPOT SEMA (reativado 2026-08-01)**: 528 tiles no HD (`SPOT_SEMA_OTIMIZADO`, com overviews) servem as 536 camadas spot — 528 stores de cena + 7 mosaicos por município + `SPOT_MALHA_25`. Todos os mosaicos renderizam (1.7–42s no 1º acesso, ~0.2s repetido). Detalhes em `CHANGELOG.md`.
- **8 camadas CBERS 2026 usam symlinks** em `data_dir/external/cbers/` (criados pelo pipeline de publicação do GeoForest). Em 2026-08-01, **347 de 362 symlinks estavam quebrados** (apontando para `/media/server/HD Backup1/...` inexistente) — render dessas camadas pode falhar; o healthcheck não detecta (só testa GetCapabilities).
- **Limpeza feita em 2026-08-01**: apagados 85 resíduos `.geotiff` (~1MB, sem referência em nenhum store) e `data/spot_sema_mosaics` (220KB, órfão) do SSD.
- `geoserver_data/raster_images/` e `geoserver_data/hd_externo/` estão vazios — estrutura antiga.
- Deslocamento conhecido de imagens CBERS: causa raiz histórica = comparar bbox-center com cena L4 de outra data + zona UTM hardcoded. Publicar com georref nativo.
- `.prj` UTM pode ser SAD69/Córrego Alegre — usar `detectPrjDatum` + towgs84 IBGE; assumir WGS84 desloca 65–80m.
