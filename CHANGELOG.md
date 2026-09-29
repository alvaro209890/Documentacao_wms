# Changelog — Documentação WMS

Registro de operações e mudanças no serviço WMS.

## 2026-09-28 — Auditoria read-only do catálogo `cbers` (sem alteração) *(autor: Hermes-server/wms)*

Nada foi alterado no GeoServer, proxy, túnel ou dados. Medido direto dos XML do data dir,
dos 3 GetCapabilities e de GetMap reais:

| Item | Resultado |
|---|---|
| Camadas | **813** (750 raster + 63 vetor), 700 layergroups (159 NAMED, 541 CONTAINER) |
| Stores com arquivo ausente | **0** (528 WorldImage, 215 GeoTIFF, 7 ImageMosaic, 63 Shapefile) |
| Camada sem estilo / SLD ausente | **0** (185 estilos) |
| Raster não-Byte sem `_fixo` | **1**: `213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan` (Int16) |
| GetCapabilities 1.3.0 | XML válido: local 3,9 s · proxy 4,1 s · público 1,5 s; 972 `<Layer>` com nome |
| GetMap (1.3.0, EPSG:4674, bbox lat,lon) | **20/20 PNG com dado**, local e público (CBERS, Landsat, NDVI, SPOT, mosaico, SIMCAR, Fiscalização, Base) |
| Tamanho | SSD 101 MB (config+logs) · vetores no HD 20 GB · rasters dos stores 446 GiB |

Achados:
- 🔴 **`AREAS_USO_RESTRITO` não renderiza** (falha silenciosa): o shapefile do store
  `base_referencia` está em `SIRGAS_2000_Lambert_Conformal_Conic_MT` (metros), mas a camada declara
  `EPSG:4674` com `projectionPolicy=FORCE_DECLARED`. Os metros são lidos como graus, o
  `latLonBoundingBox` ficou `-180,-90,180,90`, e o GetMap de MT volta PNG 100% transparente com
  HTTP 200. É a única das 63 camadas vetoriais assim. Correção sugerida (não aplicada):
  `REPROJECT_TO_DECLARED` + recalcular bbox, ou reprojetar o shapefile para EPSG:4674.
- Os **347 symlinks quebrados** de `data_dir/external/cbers/` **não são usados por nenhum store**:
  os 11 stores que apontam para `external/` resolvem. Não há impacto em render (corrige a nota de
  01/08). `/media/server/HD Backup1` hoje é symlink para `HD Backup`, mas os arquivos estão em
  `RASTER/CBERS_4A/...`, por isso o alvo continua não existindo.
- O proxy mostra só as árvores RASTER/VETOR: `AREAS_USO_RESTRITO`, a cena
  `211_129_2022_cbers_4a_wpm_20220803_211_129_c342` e o grupo `orbit_211_129_y2022` estão na raiz
  e **não aparecem no capabilities público** (continuam respondendo por GetMap).
- `car_digital_simcar_d_simcar_d_app` na extensão de MT leva ~31 s local (zoom de imóvel é rápido).
- WFS público lista 64 FeatureTypes (os vetores), não todas as camadas.

Pendências (decisão do Álvaro, nada feito): CRS de `AREAS_USO_RESTRITO`; `_fixo` da cena Int16 acima; incluir os 3 nomes da raiz
nas árvores; limpar os 347 links órfãos.

## 2026-09-02 — WMS lento / espiral de restarts do túnel *(autor: Claude)*

**Sintoma:** WMS "lento", healthcheck em loop de falha desde 13:28 (45 restarts do túnel no dia).

**Causa raiz (dupla):**
1. **Buffer UDP do kernel minúsculo.** `net.core.rmem_max/wmem_max` = 208 KiB; o QUIC do
   cloudflared quer 7 MiB (o log reclamava `failed to sufficiently increase receive buffer`).
   Servir o GetCapabilities do `cbers` (~2,9 MB, 1507 camadas) pelo túnel beirava/passava os
   `--max-time 20` do healthcheck.
2. **Healthcheck destrutivo.** Ao falhar o teste público, o script reiniciava o
   `geoserver-wms-tunnel.service` — que é **multisserviço** (derruba junto geoforest-api,
   ecogestor-api, modelos). Reconexão QUIC leva ~10-30 s; no tick seguinte (2 min) o público
   caía no meio do restart → outro restart. Espiral auto-infligida. GeoServer local e proxy
   respondiam 200 em ~2,2 s o tempo todo — nunca foram o gargalo.

**O que foi feito:**
- `/etc/sysctl.d/99-quic-udp-buffers.conf`: `rmem_max=wmem_max=7168000` (persistente, aplicado).
  O aviso de buffer do cloudflared sumiu após restart.
- Reescrito `~/.local/bin/geoserver-wms-healthcheck.sh`:
  - Probe público **leve**: `GET /geoserver/web/` (responde ~0,16 s; saudável se HTTP < 500) em
    vez de baixar os 2,9 MB do GetCapabilities. Local (8081/8082) segue com GetCapabilities real.
  - `--max-time` local 20→45.
  - **Cooldown de 300 s** no restart do túnel (`ActiveEnterTimestamp`): não reinicia se subiu há
    < 5 min → quebra a espiral, mantém auto-recuperação para queda real. Sem restart em cascata.
  - Backup: `geoserver-wms-healthcheck.sh.bak-20260902-140528`.

**Medição pós-fix:** público estabiliza em ~5-6 s total (era beira de 20 s + loop); healthcheck
passa limpo (exit 0). GeoServer/proxy locais inalterados (~2,2 s).

**Pendência (não-crítica):** TTFB público ~4,5 s vem da geração do GetCapabilities de 1507 camadas
(no-store, sem cache no edge). Se incomodar, avaliar cache de GetCapabilities no proxy.

## 2026-08-04 — Realce de cor fixo em todo o raster não-Byte (178 camadas) *(autor: Claude)*

**Problema:** a mesma área do chão voltava com cor diferente dependendo do BBOX pedido. Aparecia
como mapa do ArcMap em que o quadro principal e os minimapas (cada um é uma requisição com
extensão própria) não batiam — um roxo claro, outro roxo escuro.

**Causa raiz:** os rasters do acervo não são 8 bits (Int16, UInt16, UInt32, Float32). Para gerar o
PNG, o GeoServer precisa converter para 8 bits, e o realce era **automático por requisição**:
`landsat_rgb.sld` usava `<ContrastEnhancement><Normalize/></ContrastEnhancement>` sem faixa fixa, e
o estilo `raster` (sem realce declarado) cai no mesmo caminho de conversão. Resultado: o mapeamento
valor→cor era calculado com a estatística dos pixels daquele recorte.

**Medição antes (20 camadas amostradas, diferença máxima em níveis RGB entre a mesma área pedida
solta e pedida dentro da cena inteira):**

| dtype | camadas medidas | diferença |
|---|---|---|
| Byte | 4 | 0,0–0,2 (só ruído de reamostragem) |
| Int16 / UInt16 / UInt32 / Float32 | 16 | 8,9 a **102,3** |

**O que foi feito:**

1. **Censo dos 737 rasters** por tipo de dado: 558 já são Byte (528 WorldImage SPOT + 23 GeoTIFF +
   7 ImageMosaic) e **179 não são** (111 Int16, 41 UInt16, 22 UInt32, 4 Float32, 1 Int16 de 5 bandas).
2. **Um estilo por camada** (`<camada>_fixo`) para as não-Byte, com
   `StretchToMinimumMaximum` nos percentis 2/98 **de cada cena**, por banda — calculados uma vez a
   partir de um nível de overview, descartando nodata, valores não-finitos e a borda preta
   (pixel zero em todas as bandas). Tem que ser por camada: cada cena tem faixa própria e o acervo
   mistura Int16 com UInt32.
3. **178 camadas migradas.** 1 ficou de fora
   (`213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan` — arquivo ilegível no HD; segue no
   estilo antigo).
4. **As 558 Byte não foram tocadas** — 8 bits sai como está gravado, sem conversão, então a cor
   delas já era estável (medido: 0,0–0,2).
5. Cache do GeoWebCache (`cbers_*`, ~1MB) limpo, senão continuaria servindo tile com a cor velha.
6. `systemctl --user restart geoserver-wms.service` para recarregar o catálogo.

**Medição depois:** 20/20 camadas amostradas com diferença ≤ 1,2 nível (era até 102,3). Na cena
`landsat_224_069_2004_l5_tm_224069_20040623_c543`, quadro principal × minimapa saiu de
2,5/48,7/31,2 para 1,9/1,9/1,9 — os três canais deslocam igual, ou seja, sem desvio de matiz.

**Varredura de saúde:** GetMap em cada uma das 178 alteradas — **178/178 respondem PNG**. Uma
(`214_128_2023_cbers4a_wpm_20231228_214_128_c342_pan2`) estourou o timeout de 180s na primeira
passada e passou na segunda com folga (é cena pan-sharpened grande, render lento no 1º acesso).

**Reversão:** `landsat_rgb` e `raster` continuam existindo, intocados. Voltar é devolver o
`<defaultStyle><id>` anterior em cada `layer.xml` — os ids antigos estão gravados no plano
(`estilo_anterior_id`) e há backup completo do catálogo em
`/home/server/geoserver_backups/catalogo_antes_stretch_20260804_103325.tar.gz`.
O plano com os ids anteriores e as faixas usadas ficou em
`/home/server/geoserver_backups/plano_stretch_20260804.json` (e o censo de tipos de dado em
`censo_raster_20260804.json`) — e o arquivo que `--reverter` consome.

**Correção de registro:** a entrada de 2026-08-01 afirma que "CBERS/SPOT usam o SLD `raster` (só
Opacity 1.0 — nenhuma transformação de cor)". Isso vale para o **SPOT** (Byte), mas **não** para os
CBERS Int16: medidos antes desta mudança, variavam 16–30 níveis conforme o recorte. Sem realce
declarado no SLD o GeoServer ainda assim normaliza dado não-Byte.

**Ressalvas:**

- **Camada nova publicada daqui pra frente nasce com o estilo padrão** e volta a ter o problema.
  Depois de publicar, rodar `scripts/gerar_estilos_fixos.py` (censo → plano → `--aplicar`) e
  reiniciar o serviço.
- Mapas já exportados não mudam, mas reexportar um projeto antigo agora dá cor diferente do PDF
  anterior. É o efeito desejado.
- **Float32 com NaN quebra a camada** se o percentil vier `nan`: o SLD sai com
  `<VendorOption name="minValue">nan</VendorOption>` e o GetMap responde
  `Error rendering coverage on the fast path`. As 4 camadas Float32 caíram nisso e foram
  corrigidas na mesma sessão (máscara `np.isfinite`). O script já traz o guarda.
- **`SLD_BODY` exige `<NamedLayer><Name>` qualificado com o workspace** (`cbers:<camada>`). Com o
  nome sem prefixo o GeoServer aceita o XML, não acusa erro e **ignora o estilo em silêncio** —
  gastei vários testes achando que `StretchToMinimumMaximum` não funcionava nesta instância.
- **Existe um container Docker `geoserver-wms` ocioso** (sem porta publicada, data dir num volume
  próprio com o catálogo de exemplo). Quem está no ar é o **Jetty nativo** da user unit
  `geoserver-wms.service`, com data dir `/home/server/geoserver_data`. Reiniciar o container não
  tem efeito nenhum no serviço público.

**Scripts:** `scripts/gerar_estilos_fixos.py` (censo, plano, aplicar, reverter) e
`scripts/verificar_cor.py` (mede se a cor depende do BBOX).

## 2026-08-02 — Auditoria do sync mensal SIMCAR/Fiscalização (read-only, OK)

**Veredito: o sync automático está funcionando.** Nenhuma alteração feita — apenas verificação.

- **Timer:** `car-digital-sync.timer` (user) ativo/enabled, dia 01 às 02:00, retries diários até sucesso.
- **Última execução:** 01/08 02:00→03:32, `status: sucesso` (~1h32), snapshot `20260801T050001Z`, 38 camadas (30 SIMCAR + 8 Fiscalização).
- **Retry diário de 02/08 pulou corretamente** (`skip_reason: mes 2026-08 ja validado`).
- **Validação feita pelo próprio sync:** GetCapabilities local+público + GetMap + GetFeatureInfo (PNG/JSON reais, não XML de erro) — todos `ok`.
- **Dados:** `/media/server/HD Backup/VETOR/CAR_Digital/current/datasets/simcar_digital/<camada>/<camada>.zip` (30 zips, atualizados 01/08) + `Fiscalizacao/`. Upload Google Drive `SIMCAR_DIGITAL_V08.2026`. Arquivo mensal em `CAR_Digital/archive/YYYY-MM/`.
- **Ponto de atenção:** zips de agosto com **mesmo tamanho** dos de julho (ex.: `veredas` 111.578.555 B, `app` 1.790.946.475 B). Provável: dado-fonte do CAR Digital não mudou no mês. O script não compara por hash — para confirmar dado novo, comparar checksum de um zip entre os 2 meses.

## 2026-08-01 — GeoWebCache ativado p/ todo o raster + garantias de integridade

**Estado:** o GWC já estava habilitado globalmente (`cacheLayersByDefault=true`, 1470 camadas). O que foi feito:

1. **Cache em disco movido do SSD para o HD** — `geoserver_data/gwc` → `/media/server/HD Backup/GEOSERVER/gwc-cache` (symlink). Nada de tiles no SSD.
2. **Expiração de 30 dias (2592000s) nos 38 vetores** (SIMCAR Digital + Fiscalização) via REST — o sync mensal atualiza os shapes e o cache não pode ficar eterno. Limitação: grupos (`SIMCAR_DIGITAL`, `FISCALIZACAO`, `VETOR`, `GRADES_DE_SATELITE`) não persistem `expireCache` via REST (ficam em 0/nunca — risco baixo, ninguém cacheia o grupo inteiro).
3. **Endpoints de cache confirmados no público:**
   - `https://wms.cursar.space/geoserver/gwc/service/wms` (WMS-C) — ✅
   - `https://wms.cursar.space/geoserver/gwc/service/wmts` (WMTS) — ✅
   - TMS (`/gwc/tms/`) — **bloqueado pelo proxy** (sufixo fora da whitelist)
   - `TILED=true` no `/cbers/wms` — responde mas **não grava no cache** (só WMS-C/WMTS cacheiam de fato)

**Tempos medidos (2ª chamada = HIT):**

| Tipo | 1ª (MISS) | 2ª (HIT) |
|---|---|---|
| Cena CBERS (tile z7) | ~0.2-0.4s | **0.006-0.01s** |
| Cena Landsat | 0.3s | **0.006s** |
| Mosaico SPOT (município) | 4.6s | **0.04s** |

**Garantias de integridade (cor/deslocamento):**

- **Cache = render exato:** tiles repetidos retornam bytes idênticos (md5 igual); vs render direto a diferença média é de **1 nível RGB (0.4%)** em pixels de contraste — arredondamento do metatile (render 1024px→256px), imperceptível, sem deslocamento.
- **Alinhamento com grade oficial (centro cena vs tile da grade):** SPOT Canarana **4m** ✓ · Landsat 224/069 **~0.7km** (cena 185km) ✓ · CBERS 213/129 ~3km (folga normal de cena WPM 165km vs tile nominal 115km — cena contida na grade).
- **Cores:** CBERS/SPOT usam o SLD `raster` (só Opacity 1.0 — **nenhuma transformação de cor**). Landsat usa `landsat_rgb` com `Normalize` (stretch de contraste por canal — estilo histórico de visualização, não é alteração de dados).
- O cache não altera nada disso — serve o PNG que o GeoServer renderizou.

**Ressalvas:**
- Grupo `RASTER` inteiro é pesado para tile único (timeout em z6 — renderiza todas as órbitas sobrepostas). Usar subgrupos (`orbit_*`, `CBERS-4A-Apos_2019`, `LANDSAT`, `SPOT_SEMA`, mosaicos).
- Primeiro acesso de um tile gera (MISS); navegação posterior é instantânea (HIT).
- GeoForest continua consumindo o WMS normal (`/cbers/wms`) — não afetado; para ganhar cache basta apontar para o WMS-C/WMTS.

## 2026-08-01 — Reativação completa do SPOT SEMA (mosaicos + cenas)

**Contexto:** as 536 camadas SPOT estavam publicadas e `enabled`, mas os **7 mosaicos por município** (`spot_sema_<muni>_mosaic`) travavam (timeout 60s+) e 296 stores de cena apontavam para a pasta original sem overviews.

**O que foi feito:**

1. **Migração de 296 stores de cena** `SPOT_SEMA` → `SPOT_SEMA_OTIMIZADO` (rewrite do `url` nos coveragestore.xml; todos os 528 tiles existem no destino). Backup: `/media/server/HD Backup/GEOSERVER/backups/spot_store_xmls_20260801/` (296 XMLs).
2. **824 symlinks dos 7 mosaicos** repontados de `SPOT_SEMA` → `SPOT_SEMA_OTIMIZADO` (mesma estrutura, `.tif` + `.prj`).
3. **Fix de performance:** removidas as linhas `LevelsNum=1`/`Levels=...` dos `.properties` dos 7 mosaicos — o ImageMosaic passou a usar os overviews internos dos tiles (render de 53s → 2–10s).
4. **169 `.prj` criados** nos tiles de `Bom_Jesus_do_Araguaia` (40) e `Sao_Felix_do_Araguaia` (129) — esses 2 municípios nunca tiveram sidecar `.prj` (nem no original), causando `MismatchedReferenceSystemException` no mosaico. Copiado o WKT SIRGAS 2000/UTM 22S padrão.

**Validação (GetMap 512x512, WGS84, 1º acesso):**

| Município | Antes | Depois |
|---|---|---|
| Bom Jesus do Araguaia | erro CRS | 1.7s ✅ |
| Canarana | timeout 60s+ | ~10s ✅ |
| Confresa | timeout | 4.2s ✅ |
| Querência | timeout | ~42s (124 tiles, maior) ✅ |
| Ribeirão Cascalheira | timeout | 7.9s ✅ |
| São Félix do Araguaia | erro CRS | 5.0s ✅ |
| Serra Nova Dourada | timeout | 1.5s ✅ |

Acessos repetidos: 0.1–0.5s (cache OS + Cloudflare). Cenas individuais: ~0.16s.

**Observações:**
- Primeiro acesso de municípios grandes ainda demora (I/O do HD); cache de tiles (GeoWebCache) é a próxima otimização possível se necessário.
- Lixo no HD (não removido): `SPOT_SEMA_MOSAICS`, `SPOT_SEMA_MOSAICS_BACKUP`, `.deps`, `.venv`, `scripts/`.

## 2026-08-01 — Migração dos vetores do SSD para o HD

**O que foi feito:**

- Movidos os **vetores SIMCAR Digital + Fiscalização** (38 camadas, ~13GB) do SSD (`/home/server/geoserver_data/data/cbers/`) para o HD:
  `/media/server/HD Backup/GEOSERVER/data/cbers/`
- Criado **symlink** no lugar: `geoserver_data/data/cbers -> /media/server/HD Backup/GEOSERVER/data/cbers`
- **Nenhum datastore.xml foi alterado** — os 38 stores continuam apontando para o mesmo path lógico, resolvido pelo symlink. O sync mensal (`car-digital-sync`) continua gravando no mesmo lugar (via symlink → HD).

**Procedimento executado (servidor):**

1. `systemctl --user stop geoserver-wms-healthcheck.timer` (evita restart automático na janela)
2. `systemctl --user stop geoserver-wms-tunnel.service geoserver-wms-public-proxy.service geoserver-wms.service`
3. `rsync -a /home/server/geoserver_data/data/cbers/ "/media/server/HD Backup/GEOSERVER/data/cbers/"` (3min)
4. Verificação: 13G/13G, 195/195 arquivos
5. `rm -rf` da fonte no SSD + `ln -s "/media/server/HD Backup/GEOSERVER/data/cbers" /home/server/geoserver_data/data/cbers`
6. Subida na ordem: geoserver → proxy → tunnel; reativado o timer do healthcheck

**Validação pós-migração (tudo 200):**

- GetCapabilities público (wms.cursar.space)
- GetMap vetor SIMCAR (via symlink → HD) — PNG ok
- WFS GetFeature `fiscalizacao_autos_de_infracao` (count=2) — JSON com atributos ok
- GetMap raster CBERS (HD) — PNG ok

**Resultado:** SSD `/` de 89% → 77% (12G → 24G livres). Estrutura no HD: `/media/server/HD Backup/GEOSERVER/data/cbers/`.

## 2026-08-02 — Removida entrada saldopro-api do túnel geoserver-wms + desativação de serviços

**Operação (autor: Hermes-server):** limpeza de serviços/túneis inativos no server.

1. **Túnel geoserver-wms (config.yml):** removida a entrada `saldopro-api.cursar.space → 127.0.0.1:10000` (sem listener — config morta). Reiniciado `geoserver-wms-tunnel.service`. Validação: saldopro-api agora retorna 530 (hostname não roteado); wms/geoforest-api/ecogestor-api/9router seguem respondendo.
2. **Painel de Limites:** `painel-limites-cloudflared.service` parado + desabilitado (origem 8787/4173 estava fora do ar).
3. **VendaFácil PDV:** `vendafacil-backend`, `vendafacil-frontend`, `vendafacil-cloudflared` parados + desabilitados.
4. **Agro Oliveira:** `agro-oliveira-backend`, `agro-oliveira-cloudflared` parados + desabilitados.
5. **Túneis órfãos:** configs `auracore-config.yml` (api.cursar.space→8000) e `whatsapp-admin.yml` (→3190) movidos para `~/.cloudflared/disabled-backup-20260802/`. Units auracore já estavam disabled.
6. **SaldoPro:** já estava desativado (inactive/disabled) — só a entrada do túnel foi removida.

**Como reativar:** `systemctl --user enable --now <serviço>` + restaurar yml do backup se necessário.

## 2026-08-25 — Pipeline NDVI do GeoForest

- GeoForest `main` em `d926def7`: módulo `backend/ndvi/`, quarto card pós-recorte e documentação do contrato.
- `SIMCAR_NDVI_ENABLED=true` ativada no `backend.env`; processo reiniciado e variável confirmada no `/proc/<pid>/environ`.
- Preflight live: GDAL 3.8.4, `gdalwarp`, `gdal_calc.py` e `gdaldem` presentes; HD `/media/server/HD Backup/RASTER` gravável; `ndvi_ramp.sld` presente no checkout.
- Acervo alvo: `/media/server/HD Backup/RASTER/NDVI`; grupos alvo: `RASTER → NDVI → ndvi_orbit_<path>_<row> → ..._y<ano>`.
- O deploy não cria camada vazia. Float32, RGB, stores, grupos e o GetMap surgem na primeira execução NDVI sobre um recorte real.

**Pendente de evidência live:** primeira execução autenticada sobre CAR real, seguida de GetCapabilities/GetMap e conferência do laudo Word. Build/API/Hosting estão online.
