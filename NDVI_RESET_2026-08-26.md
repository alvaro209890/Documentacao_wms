# Reset do acervo NDVI do GeoForest — 2026-08-26

Operação executada no `server-desktop` por solicitação do responsável pelo
GeoForest-IA.

## Motivo

Um job de cena completa foi interrompido por um restart do auto-deploy e ficou
visível no painel em 15%. A correção da recuperação de jobs entrou no
GeoForest-IA no commit `ddbfdb2c`.

## Estado antes

- 8 coveragestores/camadas com prefixo `ndvi_` no workspace `cbers`;
- grupos `NDVI`, `ndvi_orbit_224_069`, `ndvi_orbit_229_069` e seus grupos de ano;
- 8 GeoTIFFs em `/media/server/HD Backup/RASTER/NDVI`;
- `cbers:NDVI` referenciado pelo grupo `cbers:RASTER`.

## Operação

1. Removida somente a referência `cbers:NDVI` de `cbers:RASTER`.
2. Removidos os grupos da hierarquia NDVI.
3. Removidos os 8 coveragestores com `recurse=true`.
4. Apagados os GeoTIFFs, índices e temporários NDVI do GeoForest.
5. Zerado o histórico específico da aba NDVI.

As definições dos estilos continuam versionadas no GeoForest. O `ndvi_ramp`
permanece no catálogo; `ndfi_ramp` e `savi_ramp` serão criados de forma
idempotente quando uma nova publicação exigir cada um deles. Estilos não são
imagens. Nenhuma camada CBERS, LANDSAT, SPOT ou vetorial foi removida.

## Verificação depois

- GetCapabilities público: 0 nomes de camada/grupo NDVI;
- REST: 0 coveragestores NDVI e 0 grupos NDVI;
- filhos de `RASTER`: `CBERS-4A-Apos_2019`, `LANDSAT` e `SPOT`;
- `/media/server/HD Backup/RASTER/NDVI`: ausente;
- índices `ndvi_archive`/`ndvi_scene_archive`: ausentes;
- documentos `ndvi_scene_jobs` e `processing_jobs` NDVI: 0;
- GeoForest API: saudável; backend ativo no commit `ddbfdb2c`.

A próxima execução bem-sucedida da aba NDVI recriará o diretório, os stores e a
hierarquia, tornando-se a primeira imagem do novo acervo.
