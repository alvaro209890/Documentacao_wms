# NDVI: correção de GeoTIFF RGBA e limpeza do WMS — 2026-08-26

## Incidente

O job `5f430ae2-086e-4a2f-9f35-927401a58338`, da cena Landsat 7 `LE07_L2SP_224069_20070928_02_T1`, falhou na validação da composição NDVI. A camada chegou a ser criada, mas o `GetMap` devolvia exceção e clientes como o ArcMap não conseguiam consumi-la.

## Causa

As composições NDVI, NDFI e SAVI são coloridas pelo GDAL antes da publicação e chegam ao GeoServer como GeoTIFF RGBA de 8 bits. O pipeline aplicava novamente estilos SLD monobanda, causando `Source and Destination image must have the same Bands`.

## Correção publicada

- NDVI, NDFI, SAVI, RGB e SWIR da cena completa agora usam o estilo neutro `raster` no GeoServer.
- As rampas de cor continuam incorporadas pelo GDAL durante a geração do arquivo.
- Em qualquer falha, o pipeline remove índice, TIFF, overview, coveragestore e apenas os grupos NDVI que ficarem vazios.
- O rollback desprende primeiro a árvore dos grupos pais porque o GeoServer rejeita `PUT` de layer group vazio.
- As bibliotecas CBERS, Landsat e SPOT não são alteradas.

Código de produção: `b93c1e9a9c158a379bff938fe21fc0f77e7a12ac` no `main` de `alvaro209890/GeoForest-IA`.

## Validação real

Antes da limpeza, a camada órfã foi atualizada de forma controlada para o estilo `raster`:

- `GetCapabilities` público: camada presente;
- `GetMap` privado: aprovado pela validação do backend;
- `GetMap` público: `image/png`, RGBA, 256 x 256, 80.069 bytes.

Depois da prova, a camada defeituosa e seus artefatos foram excluídos conforme solicitado:

- coveragestore e grupos `NDVI`, `ndvi_orbit_224_069` e `ndvi_orbit_224_069_y2007`: HTTP 404;
- coveragestores NDVI no workspace `cbers`: 0;
- arquivos no acervo NDVI: 0;
- camada ausente do `GetCapabilities` público;
