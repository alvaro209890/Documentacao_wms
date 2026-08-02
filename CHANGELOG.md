# Changelog — Documentação WMS

Registro de operações e mudanças no serviço WMS.

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
