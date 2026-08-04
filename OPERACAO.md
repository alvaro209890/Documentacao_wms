# Operação — diagnóstico e troubleshooting

## Testes rápidos

```bash
# GetCapabilities (as 3 camadas)
curl -fsS --max-time 20 -o /dev/null -w "HTTP %{http_code} em %{time_total}s\n" \
  "http://127.0.0.1:8081/geoserver/cbers/wms?service=WMS&request=GetCapabilities&version=1.3.0"
curl -fsS --max-time 20 -o /dev/null -w "HTTP %{http_code} em %{time_total}s\n" \
  "http://127.0.0.1:8082/geoserver/cbers/wms?service=WMS&request=GetCapabilities&version=1.3.0"
curl -fsS --max-time 20 -o /dev/null -w "HTTP %{http_code} em %{time_total}s\n" \
  "https://wms.cursar.space/geoserver/cbers/wms?service=WMS&request=GetCapabilities&version=1.3.0"

# GetMap real (render de verdade) — trocar layers pelo nome da camada
curl -fsS --max-time 60 -o /tmp/test.png \
  "https://wms.cursar.space/geoserver/cbers/wms?service=WMS&version=1.3.0&request=GetMap&layers=cbers:NOME_DA_CAMADA&bbox=-54,-13,-53,-12&width=256&height=256&format=image/png"
file /tmp/test.png   # deve ser PNG image data, não XML
```

## REST API (diagnóstico local)

```bash
# Listar coveragestores
curl -s -u admin:***** "http://127.0.0.1:8081/geoserver/rest/workspaces/cbers/coveragestores.json" | python3 -m json.tool

# Listar layer groups
curl -s -u admin:***** "http://127.0.0.1:8081/geoserver/rest/workspaces/cbers/layergroups.json" | python3 -m json.tool
```

> Credenciais REST do GeoServer: ver env do backend do GeoForest (`GEOSERVER_USER`/`GEOSERVER_PASSWORD`) — não documentar aqui (repo público).

## Cor: conferir e recompor o realce fixo

```bash
# a cor desta camada muda conforme o recorte? (>3 niveis RGB = sim)
python3 scripts/verificar_cor.py --camadas NOME_DA_CAMADA

# amostragem geral, N camadas por tipo de dado
python3 scripts/verificar_cor.py --n 4

# camada nova publicada: censo -> plano -> aplicar -> reiniciar
python3 scripts/gerar_estilos_fixos.py --censo /tmp/censo.json --plano /tmp/plano.json
python3 scripts/gerar_estilos_fixos.py --plano /tmp/plano.json --aplicar
systemctl --user restart geoserver-wms.service

# desfazer (devolve o estilo anterior e apaga os SLD gerados)
python3 scripts/gerar_estilos_fixos.py --plano /tmp/plano.json --reverter
```

> Depois de trocar estilo, **limpar o cache do GWC** das camadas afetadas
> (`/media/server/HD Backup/GEOSERVER/gwc-cache/cbers_*`), senão o tile antigo continua sendo
> servido com a cor velha.

## Problemas conhecidos

| Problema | Sintoma | Ação |
|---|---|---|
| Capabilities lento (4–6s) | Latência alta em todos os testes | Normal: healthcheck a cada 2min + XML gigante (737 camadas). Monitorar, não corrigir às cegas |
| Camada CBERS 2026 não renderiza | GetMap → XML `ServiceException` ou PNG vazio | Provável symlink quebrado em `data_dir/external/cbers/` apontando para `/media/server/HD Backup1/...` — corrigir store para apontar direto ao HD (`RASTER/CBERS_4A/...`) |
| Vetores SIMCAR desatualizados | Shapes antigos | Rodar `systemctl --user start car-digital-sync.service` (ou esperar o timer do dia 01) |
| Sync SIMCAR não confirma dado novo | Zips de um mês com mesmo tamanho do anterior (ex.: `veredas` 111.578.555 B em jul/ago/2026) | Provável: dado-fonte do CAR Digital não mudou. O script não compara por hash — comparar checksum de um zip entre os 2 meses se precisar confirmar. Sync em si está OK (auditoria 2026-08-02) |
| Camada com cor diferente entre recortes | Mesma área sai com matiz diferente conforme o zoom/extensão | Camada não-Byte sem estilo `_fixo`. Rodar `scripts/gerar_estilos_fixos.py` (ver acima) |
| Camada Float32 devolve `Error rendering coverage on the fast path` | GetMap → XML de exceção | SLD com `minValue`/`maxValue` = `nan` (dado tem NaN). Recalcular com o guarda `np.isfinite` do script |
| Reiniciei o Docker e nada mudou | `docker restart geoserver-wms` sem efeito | O container é **ocioso** (sem porta publicada). O serviço no ar é a user unit `geoserver-wms.service` (Jetty nativo, data dir `/home/server/geoserver_data`) |
| `SLD_BODY` ignorado sem erro | GetMap com SLD inline renderiza como se nada fosse | `<NamedLayer><Name>` precisa ser qualificado: `cbers:<camada>` |
| GeoServer fora do ar | Healthcheck reinicia em cascata | Ver `journalctl --user -u geoserver-wms.service -n 100` |
| Proxy devolvendo 403 | Request fora de `/wms`, `/wfs`, `/ows`, `/wmts`, `/schemas` | Policy intencional do proxy público |

## Segurança de operação

- Nunca rodar `kill`/`fuser` no processo do GeoServer **se houver o `Restart=always`** equivalente — sempre usar `systemctl --user restart`.
- Healthcheck script usa `curl -f` (falha em HTTP >= 400).
- Ao mexer em stores em lote, preferir Python (`urllib`) no lugar de curl um a um.
