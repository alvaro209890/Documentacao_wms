# Changelog — Documentação WMS

Registro de operações e mudanças no serviço WMS.

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
