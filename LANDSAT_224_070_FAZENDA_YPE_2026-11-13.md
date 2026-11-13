# Landsat 224/070 — Fazenda Ypê (Barra do Garças/MT), 2003 a 2009

**Data:** 13/11/2026
**Origem:** pedido do Álvaro — gerar as imagens Landsat da propriedade `Fazenda_Ype` (CAR), folha inteira, sem recorte, e publicar no WMS.

## Propriedade

| Item | Valor |
|---|---|
| Imóvel | Fazenda Ypê — 180,42 ha (`ATP.shp`, 1 polígono) |
| Município | Barra do Garças / MT (IBGE 5101803) |
| Centro | -15,065560 / -52,438809 |
| BBox | -52,4487 a -52,4291 · -15,0761 a -15,0548 |
| Órbita/ponto WRS-2 | **224/070** (célula do imóvel) — 224/071 também cobre por sobreposição lateral |

## Pipeline usado

Executor: `/home/server/.local/bin/landsat_cena.py` (espelha `GeoForest-IA/backend/landsat/`).

1. STAC Planetary Computer (`landsat-c2-l2`), `query` por `landsat:wrs_path` / `landsat:wrs_row` / ano.
2. Escolha da cena: T1 antes de T2, menor `eo:cloud_cover`, sensor preferencial L9 > L8 > L5 > L7.
3. Download das 3 bandas com SAS (`/api/sas/v1/sign`), ~0,55 MB/s do Azure.
4. `gdalbuildvrt -separate` → `gdal_translate -ot Byte -scale 1 30000 1 255 -a_nodata 0 -co TILED=YES -co COMPRESS=LZW -co BIGTIFF=IF_SAFER`.
5. `gdal_edit.py` colorinterp R,G,B → `gdaladdo -ro -r average 2..128` (overview LZW).
6. Gravação em `/media/server/HD Backup/RASTER/LANDSAT/224_070/<ano>/` (folha inteira, **sem recorte**).
7. Publicação REST: coverageStore GeoTIFF → `external.geotiff` → estilo → grupos `RASTER > LANDSAT > 224_070 > ano` → GetMap de validação.

Composição: **falsa-cor C543** (swir16, nir08, red = TM 5/4/3). Todas as 7 cenas são **Landsat 5 TM**, 0% de nuvem.

## Cenas publicadas

| Ano | Data | Item STAC | Camada | TIF |
|---|---|---|---|---|
| 2003 | 2003-07-23 | `LT05_L2SP_224070_20030723_02_T1` | `landsat_224_070_2003_lt05_l2sp_224070_20030723_02_t1_c543` | 91,8 MB |
| 2004 | 2004-06-23 | `LT05_L2SP_224070_20040623_02_T1` | `landsat_224_070_2004_lt05_l2sp_224070_20040623_02_t1_c543` | ~95 MB |
| 2005 | 2005-06-10 | `LT05_L2SP_224070_20050610_02_T1` | `landsat_224_070_2005_lt05_l2sp_224070_20050610_02_t1_c543` | ~96 MB |
| 2006 | 2006-05-12 | `LT05_L2SP_224070_20060512_02_T1` | `landsat_224_070_2006_lt05_l2sp_224070_20060512_02_t1_c543` | ~98 MB |
| 2007 | 2007-05-15 | `LT05_L2SP_224070_20070515_02_T1` | `landsat_224_070_2007_lt05_l2sp_224070_20070515_02_t1_c543` | ~96 MB |
| 2008 | 2008-07-04 | `LT05_L2SP_224070_20080704_02_T1` | `landsat_224_070_2008_lt05_l2sp_224070_20080704_02_t1_c543` | ~98 MB |
| 2009 | 2009-08-08 | `LT05_L2SP_224070_20090808_02_T1` | `landsat_224_070_2009_lt05_l2sp_224070_20090808_02_t1_c543` | 94,1 MB |

Cada camada tem estilo próprio `<camada>_fixo` (`StretchToMinimumMaximum` com p2/p98 reais da cena, medidos no histograma do Byte).

## Correção nos grupos de ano 2008 e 2009

Os grupos `landsat_orbit_224_070_y2008` e `..._y2009` já existiam com uma cena antiga (`..._l2_band5_4_3`) usando o estilo `raster`. Com as duas camadas no grupo, o desenho saía escuro (R/G/B ≈ 88/97/76 em vez de ≈ 150/159/138).

**Decisão:** os grupos 2008 e 2009 ficaram **somente com a cena nova**. As camadas antigas continuam publicadas e acessíveis individualmente (`landsat_224_070_2008_landsat_5_tm_20080720_224_070_l2_band5_4_3` e `landsat_224_070_2009_landsat_5_tm_20090808_224_070_l2_band5_4_3`), apenas não estão mais listadas dentro do grupo do ano.

## Achado registrado (não corrigido)

Os 72 grupos `landsat_orbit_*_y*` usam o estilo **`raster`** (`default_raster.sld`, sem esticamento), o que ignora os estilos `_fixo` das camadas quando o desenho é feito pelo grupo. Medição na mesma área (224_069/2004): camada sozinha R/G/B 145/170/133 contra 58/50/31 pelo grupo do ano. As camadas novas entram no grupo **com o próprio estilo fixo**, então desenham certo pelos dois caminhos; as antigas continuam escuras pelo grupo.

## Verificação

GetMap de cada ano pelo grupo (`EPSG:31982`, bbox 250000,8300000,480000,8505000):

| Ano | R | G | B |
|---|---|---|---|
| 2003 | 155 | 163 | 142 |
| 2004 | 149 | 160 | 141 |
| 2005 | 147 | 157 | 140 |
| 2006 | 142 | 153 | 134 |
| 2007 | 146 | 161 | 136 |
| 2008 | 150 | 159 | 138 |
| 2009 | 158 | 165 | 148 |

Todos os GetMap com `HTTP 200 image/png`. `GetCapabilities` local lista as 7 camadas e os 7 estilos; o `GetCapabilities` público (`wms.cursar.space`) passa a listá-las após expirar o cache do Cloudflare.

## Reversão

Remover as camadas e os grupos de ano criados:

```bash
for y in 2003 2004 2005 2006 2007 2008 2009; do
  curl -u admin:geoserver -X DELETE \
    "http://127.0.0.1:8081/geoserver/rest/workspaces/cbers/coveragestores/landsat_224_070_${y}_*?recurse=true"
done
```

Os GeoTIFFs ficam em `/media/server/HD Backup/RASTER/LANDSAT/224_070/<ano>/`. A remoção dos grupos `y2003` a `y2007` é segura (foram criados agora); nos y2008/y2009 é preciso restaurar a camada antiga na lista do grupo, se for o caso.

## Custo observado

- ~5 min por cena (download ~170 MB a 0,55 MB/s + composição/pirâmides + publicação).
- ~120 MB em disco por cena (TIF + .ovr).
- Lote 2003–2009 executado como unidade transiente `landsat-lote-2003-2009`, log em `/home/server/landsat_224070_2003_2009.log`.
