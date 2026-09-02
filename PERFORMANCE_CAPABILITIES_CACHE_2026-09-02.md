# Cache de GetCapabilities — 2026-09-02

## Mudanca aplicada

O proxy publico `geoserver-wms-public-proxy.service` passou a manter em memoria a
resposta de `GetCapabilities` por 60 segundos. A mudanca esta no host `sd`, em
`/home/server/.local/bin/geoserver_wms_public_proxy.py`; a versao anterior foi
preservada como `geoserver_wms_public_proxy.py.bak-20260902-1415`.

Somente `GetCapabilities` recebe `Cache-Control: public, max-age=60`.
Pedidos
`GetMap`, WFS e demais operacoes continuam dinamicos e nao sao cacheados pelo
proxy.

## Motivo e evidencia

O GeoServer recompunha o XML de capabilities (centenas de camadas publicadas)
a cada requisicao. Antes da correcao, a chamada local levava cerca de 4,3 s e a
publica cerca de 5,9 s. Depois do aquecimento do cache: cerca de 0,002 s no
proxy local e 0,64 s na URL publica.

O `GetMap` da camada de referencia de 2007
`landsat_224_069_2007_lc_5_224_069_20070515_comp543` foi validado apos a
mudanca: HTTP 200 e PNG 1108x631 nao vazio.

## Impacto no GeoForest

O GeoForest usa o acervo IMAP local para analises e a base SIMCAR baixada,
publicada no mesmo GeoServer, para os vetores de recorte. A fonte externa da
SEMA nao e usada como fallback silencioso nessas etapas.
