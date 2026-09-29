# WMS — tempo de resposta e cache (só medição)

Autor: Hermes-server/wms · card `t_590d9c90` · medido em 29/09/2026 00:06–00:12 BRT (load 1,1; fora de horário de uso).
Nada foi alterado no GeoServer, proxy, túnel, dados ou camadas.

## Resumo

| | Resultado |
|---|---|
| ✅ Camada lenta | **Nenhuma.** As 15 camadas mais pedidas responderam GetMap em 0,17–1,37 s pelo público (mediana ~1,0 s) |
| ✅ Imagem vazia | Nenhuma falha de render. As 13 raster voltaram com 97–100 % de pixel com dado; o `fiscalizacao_area_embargada_siga_poligono` veio 0 % porque **não há feição naquele bbox** (WFS confirmou 0 feições; bbox maior renderiza) |
| ✅ GetCapabilities | 8081 = 3,8 s (montagem do XML de 2,9 MB) · 8082 = 0,01 s (cache do proxy, TTL 60 s) · público = 0,5 s |
| ✅ Custo do túnel | +0,16 s de mediana (0,10–0,35 s) sobre o proxy |
| ✅ Pirâmide | As 13 GeoTIFF têm overviews (5 níveis Landsat, 7 no CBERS de 6,2 GB), `.ovr` externo; o mosaico SPOT tem tiles com overview e `LevelsNum=7` |
| 🟠 Tile cache | **Não existe na prática.** `gwc-cache` no HD tem 12 KB; nenhum cliente pede `tiled=true`, então o `directWMSIntegration` nunca entra |
| 🟠 Cache Cloudflare | **Não há.** `cf-cache-status: DYNAMIC` em GetMap e GetCapabilities; toda requisição vai até o GeoServer |
| 🟠 1ª requisição (fria) | +0,1–2,1 s por camada. Pior caso: `spot_sema_querencia_mosaic` na extensão inteira = **8,2 s** frio / 0,96 s quente |
| 🟠 Tipo de pixel | Não-Byte (Int16/UInt16/Float32 com estilo `_fixo`) = 0,8–1,2 s; Byte = 0,34–0,9 s. É a principal diferença de custo entre camadas |

## Método

- Camadas: journal do `geoserver-wms-public-proxy.service` (09/08 → 29/09, 94.582 linhas). Contei o `LAYERS` de cada GetMap de camada única e usei **o último GetMap real com 200** de cada uma (mesmo CRS, bbox e tamanho que o cliente pediu).
- Para cada camada, 3 rodadas; em cada rodada 8081 → 8082 → público. No público vai um parâmetro `_bench` aleatório para não medir cache de edge.
- Tempo = `time_total` do `curl`. Cada PNG foi decodificado e medido em % de pixel com dado (diferente do fundo `BGCOLOR` e com alfa > 0) — HTTP 200 não prova nada.
- Script: `scripts/bench_wms_getmap.py` (lê um `top15.json` com `layer`/`path`/`query` extraído do journal do proxy).
- Healthcheck antes: 8081 200 (3,9 s) · 8082 200 (4,1 s) · público 200 (4,3 s). Depois: igual (3,8 / 0,01 / 0,5 s com o cache do proxy quente).

## ⚠️ Quem gera esse tráfego

O proxy não loga User-Agent e tudo chega como `127.0.0.1` (túnel), então **não dá para separar cliente por log**. Pela assinatura da URL:

| Assinatura | GetMap | Quem é |
|---|---|---|
| `SERVICE=…&VERSION=1.3.0&…&EXCEPTIONS=XML&BGCOLOR=0xFEFFFF` (maiúsculo) | 1.110 (93 %) | ArcGIS/ArcMap (desktop) |
| minúsculo, 1.3.0 | 35 | cliente web/script |
| minúsculo, 1.1.1, `srs=EPSG:4326` | 27 | inclui o padrão do backend do GeoForest |

O backend do GeoForest valida GetMap direto no **8081** (`GEOSERVER_BASE_URL`) e usa o público só para GetCapabilities; o snapshot do laudo pede ao WMS da SEMA. Ou seja: as "15 mais usadas" abaixo são as mais pedidas **pelo WMS público**, dominado pelo ArcMap do escritório, e não só pelo GeoForest. Chamadas diretas ao 8081 não passam pelo proxy e não aparecem em log nenhum (o Jetty não tem request log ligado).

Volume do período: 53.976 GetCapabilities (quase tudo healthcheck), 1.190 GetMap, 109 GetFeature, 17 GetFeatureInfo. CRS dos GetMap: EPSG:4674 (627), EPSG:31982 (524), EPSG:4326 (26).

## Tabela — GetMap, 3 amostras (segundos)

8081 = 1ª (fria) / mediana. 8082 e público = mediana das 3.

| # | Camada | Pedidos | Tipo | Requisição | 8081 | 8082 | público |
|---|---|---|---|---|---|---|---|
| 1 | `landsat_224_069_2005_lt05_224069_20051016` | 111 | GeoTIFF Int16 | EPSG:31982 613x839 | 1.10 / 0.90 | 0.90 | 1.06 |
| 2 | `landsat_224_068_2000_landsat5_tm_20000612_224_068_c543` | 89 | GeoTIFF Byte | EPSG:4674 770x542 | 0.67 / 0.52 | 0.52 | 0.62 |
| 3 | `landsat_224_069_2000_l5_224069_20000730_c543` | 81 | GeoTIFF Byte | EPSG:4674 770x711 | 0.91 / 0.78 | 0.79 | 1.06 |
| 4 | `landsat_224_069_2007_lc_5_224_069_20070515_comp543` | 76 | GeoTIFF Float32 | EPSG:31982 613x839 | 1.15 / 0.93 | 0.92 | 1.07 |
| 5 | `landsat_224_069_2008_landsat_5_20080720_224_069_comp5431_geototal` | 68 | GeoTIFF UInt16 (sem compressão) | EPSG:31982 613x839 | 0.66 / 0.54 | 0.53 | 0.68 |
| 6 | `213_129_2026_cbers_4a_wpm_20260720_213_129_l4_c342_pan_j0d292649` | 65 | GeoTIFF Byte, 6,2 GB | EPSG:4674 1107x711 | 0.65 / 0.34 | 0.34 | 0.55 |
| 7 | `spot_sema_querencia_mosaic` | 62 | ImageMosaic (124 tiles) | EPSG:31982 917x839 | 2.56 / 0.44 | 0.43 | 0.79 |
| 8 | `landsat_224_069_2004_l5_tm_224069_20040623_c543` | 36 | GeoTIFF UInt16 | EPSG:4674 770x711 | 1.00 / 0.84 | 0.79 | 1.09 |
| 9 | `ndvi_224_069_2007_ndvi_224_069_20070928_l7_ndfi_j5b33ecad` | 29 | GeoTIFF Byte | EPSG:4674 1108x631 | 0.38 / 0.35 | 0.33 | 0.47 |
| 10 | `landsat_224_069_2006_lc_5_224_069_20060917_comp654` | 25 | GeoTIFF Float32 | EPSG:31982 613x839 | 0.96 / 0.92 | 0.92 | 1.06 |
| 11 | `landsat_224_069_2010_landsat_5_20100726_224_069_geo` | 21 | GeoTIFF UInt16 (sem compressão) | EPSG:31982 1108x631 | 0.88 / 0.83 | 0.80 | 0.98 |
| 12 | `car_digital_simcar_d_simcar_d_area_consolidada` | 21 | Shapefile | EPSG:31982 1564x891 | 0.51 / 0.05 | 0.05 | 0.17 |
| 13 | `landsat_224_069_2011_l5_tm_27062011_224_069_c543` | 19 | GeoTIFF UInt16 | EPSG:31982 1108x631 | 1.32 / 1.23 | 1.20 | 1.37 |
| 14 | `landsat_224_069_2007_landsat_5_tm_20070904_224_069_c543` | 17 | GeoTIFF Byte | EPSG:4674 1108x631 | 0.96 / 0.94 | 0.91 | 1.08 |
| 15 | `fiscalizacao_area_embargada_siga_poligono` | 16 | Shapefile | EPSG:4674 1311x860 | 0.50 / 0.03 | 0.04 | 0.18 |

Pior caso (extensão inteira da camada, 1024x1024, 8081, fria/quente): CBERS 6,2 GB 0,44/0,42 s · Landsat 2008 1,47/1,11 s · Landsat 2011 1,65/1,09 s · Landsat 2007 Float32 1,79/1,30 s · **SPOT Querência 8,20/0,96 s**.

## Causas prováveis do que custa tempo

1. **Sem tile cache e sem cache de edge.** Cada pan/zoom do ArcMap re-renderiza do HD. Não é lento hoje (~1 s), mas é o motivo de nenhum pedido repetido ficar mais barato que ~0,3–1 s. O GWC só serviria se o cliente pedisse `tiled=true` num gridset configurado, o que ArcMap/QGIS em modo WMS simples não fazem.
2. **Pixel não-Byte + estilo `_fixo`.** Int16/UInt16/Float32 passam pela conversão para 8 bits (StretchToMinimumMaximum) a cada pedido. Explica o ~2x das Landsat 16/32 bits contra as Byte. Não é falta de pirâmide.
3. **Leitura fria do HD.** A 1ª leitura de cada camada paga I/O do disco USB (`/media/server/HD Backup`); o mosaico SPOT abre vários tiles e é o que mais sente (8,2 s na extensão inteira). Depois fica no page cache.
4. **GetCapabilities do 8081 = 3,8 s.** Já resolvido para o público pelo cache do proxy (0,01 s). Quem chama o 8081 direto (backend do GeoForest ao validar publicação) ainda paga os 3,8 s.

## O que eu mudaria (não executado — só medição; decisão do Álvaro)

| Opção | Ganho esperado | Custo/risco |
|---|---|---|
| Nada | — | Hoje não há camada lenta |
| Converter as Landsat não-Byte para Byte com o realce do `_fixo` já aplicado | ~0,4 s por pedido nessas 7 camadas | Muda o dado publicado; exige doc + validação de cor |
| Aquecer o mosaico SPOT (1 GetMap após boot) | Elimina os 8 s frios | Trivial; só vale se o 1º acesso do dia incomodar |
| Ligar request log do Jetty ou UA no log do proxy | Saber quem é o GeoForest de verdade | Mexe em config; exige doc |
