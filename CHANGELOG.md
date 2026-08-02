# Changelog — Documentação WMS

Registro de operações e mudanças no serviço WMS.

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
