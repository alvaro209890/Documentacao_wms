# Serviços, timers e automação

Todos são **systemd user** — gerenciados com `systemctl --user`.

## Serviços

| Serviço | Porta | Descrição | Restart |
|---|---|---|---|
| `geoserver-wms.service` | 8081 | GeoServer Jetty (java) | via healthcheck |
| `geoserver-wms-public-proxy.service` | 8082 | Proxy Python público | via healthcheck |
| `geoserver-wms-tunnel.service` | — | Cloudflare Tunnel `wms.cursar.space` | via healthcheck |

Units: `/home/server/.config/systemd/user/*.service`

## Timers

| Timer | Agenda | O que faz |
|---|---|---|
| `geoserver-wms-healthcheck.timer` | a cada 2 min | Roda o healthcheck (abaixo) |
| `car-digital-sync.timer` | dia 01 às 02:00 (+ retry diário até sucesso) | Sincroniza SIMCAR Digital + Fiscalização |
| `geoforest-autosync.timer` | a cada 2 min | CI/CD do GeoForest (pull → build → deploy) |

## Healthcheck — `~/.local/bin/geoserver-wms-healthcheck.sh`

Testa as 3 URLs em cascata com `curl --max-time 20`:

1. **Admin** (`127.0.0.1:8081`) — falhou → restart `geoserver-wms.service` + re-teste
2. **Proxy** (`127.0.0.1:8082`) — falhou → restart `geoserver-wms-public-proxy.service` + re-teste
3. **Público** (`wms.cursar.space`) — falhou → restart tunnel; se ainda falhar, restart proxy + tunnel

> **Limitação:** só testa GetCapabilities (metadados). Não detecta camada com arquivo quebrado, symlink morto ou render falhando — o GeoServer responde 200 no capabilities mesmo com camadas internas quebradas.

## Sync mensal SIMCAR — `~/.local/bin/sync_car_digital.py`

- Executado por `car-digital-sync.service` (oneshot), working dir `/media/server/HD Backup/VETOR/CAR_Digital`
- Agenda: `*-*-01 02:00:00` + retry diário `*-*-02..31 02:00:00` com `Persistent=true` (se o dia 01 falhar, tenta de novo nos dias seguintes)
- Atualiza os 38 datastores vetoriais (SIMCAR Digital + Fiscalização) em `geoserver_data/data/cbers/` — desde 2026-08-01 esse path é **symlink** para `/media/server/HD Backup/GEOSERVER/data/cbers/` (HD); o sync continua gravando pelo mesmo path lógico, sem mudanças no script
- Depende de: `network-online.target` + `geoserver-wms.service`

## Comandos úteis

```bash
# Status dos 3 serviços
systemctl --user status geoserver-wms.service geoserver-wms-public-proxy.service geoserver-wms-tunnel.service

# Timers
systemctl --user list-timers | grep -E "geo|car"

# Logs do GeoServer
tail -f /home/server/geoserver_data/logs/geoserver.log

# Último sync SIMCAR
journalctl --user -u car-digital-sync.service --no-pager -n 30

# Rodar healthcheck manualmente
~/.local/bin/geoserver-wms-healthcheck.sh
```

## Estados verificados

- 2026-08-01: 3 serviços ativos, healthcheck ok, GetCapabilities 200 nas 3 camadas (3.9s / 4.2s / 5.9s), GetMap renderizando PNG em ~1.2s.
- GeoServer: memória 1.6GB em uso (pico 4.8GB), CPU 2h06 acumulada.
- Logs rotacionam em ~20MB (`geoserver-1.log`, `geoserver-2.log`, ...).
