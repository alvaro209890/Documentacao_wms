# Fundiário federal no WMS — SIGEF (INCRA) + SNCI (SINTER)

**Data:** 2026-11-15 · **Autor:** Hermes-aws · **Executado em:** server-desktop

## O que entrou

Duas camadas federais novas no GeoServer da IMAP, dentro do grupo pai `VETOR`:

| Grupo | Camada (store) | Fonte | Feições (MT) | Geometria |
|---|---|---|---|---|
| `FUNDIARIO_FEDERAL` (NAMED) | `fundiario_sigef_parcelas_mt` | INCRA — geoportal GeoNode | 166.047 | MultiPolygon, EPSG:4674 |
| `FUNDIARIO_FEDERAL` (NAMED) | `fundiario_snci_imoveis_mt` | SINTER (Receita Federal) | 6.109 | MultiPolygon, EPSG:4674 |

- **Espaço:** `cbers:fundiario_sigef_parcelas_mt` e `cbers:fundiario_snci_imoveis_mt` (workspace `cbers`).
- **Grupo:** `FUNDIARIO_FEDERAL`, modo **NAMED** (dá para pedir as duas bases de uma vez:
  `layers=cbers:FUNDIARIO_FEDERAL`); ele é filho do grupo `VETOR`, depois de `FISCALIZACAO`.
- **Render de controle** (Querência, 600×600): SIGEF 168 KB / SNCI 88 KB / grupo 220 KB.
- **Atributos preservados por inteiro** (UUID de 36 caracteres, matrícula, CNS, RT, área, datas) —
  por isso as duas camadas são publicadas em **GeoPackage**, não em shapefile (o DBF corta em 10
  caracteres e mataria `parcela_codigo`).

## De onde vêm os dados

### SIGEF — INCRA (geoportal novo)

- WFS: `https://geoportal.incra.gov.br/geoserver/wfs` · camada única **`geonode:sigef_geo`**
  ("Sigef – todas parcelas") · EPSG:4674.
- Atualização **diária de madrugada** (~00:20 Cuiabá): `last_updated` em
  `https://geoportal.incra.gov.br/api/v2/datasets/1`.
- Filtro usado: `CQL_FILTER=uf_id=51` (Mato Grosso). Outra UF/todo o Brasil = mudar essa linha.
- 🔴 O endereço antigo `acervofundiario.incra.gov.br/i3geo/ogc.php?tema=certificada_sigef_particular_*`
  **não resolve mais em DNS** (conferido 14/11/2026). Toda receita antiga que aponta para lá está morta.
- 🔴 Download em massa pelo GeoNode (`/datasets/geonode:sigef_geo/dataset_download`) responde
  **500 "Download Limits Exceeded"** — tem que paginar por UF/município via WFS.
- ⚠️ `sigef.incra.gov.br` (consulta pública) tem **WAF F5**: `curl` leva `Request Rejected` /
  desafio `/TSPD/`. Só navegador de verdade.

### SNCI — SINTER (Receita Federal)

- WFS: `https://www.sinter.fazenda.gov.br/geoserver/wfs` · camada **`sinter:snci`**
  (também há `sinter:imovel_snci`, `sinter:sigef`, `sinter:parcelas_sigef*`).
- Campos: `incra`, `cib`, `certificado`, `area`, `municipio`, `uf`, `poligono`.
- Filtro usado: `CQL_FILTER=uf='MT'` · 6.109 imóveis em MT (40.166 no Brasil).
- O SNCI é o **acervo histórico** (2ª NTGIR, anterior a 2013); o SIGEF cobre o que é certificado
  depois disso. Para análise de sobreposição as duas bases juntas são o correto.

## Como roda (mensal, junto com o SIMCAR)

O domínio novo entrou no **mesmo** `sync_car_digital.py` que sincroniza o SIMCAR Digital:

```bash
/usr/bin/python3 /home/server/.local/bin/sync_car_digital.py scheduled-run   # o que o timer chama
# forçar só o fundiário (download + publish):
/usr/bin/python3 /home/server/.local/bin/sync_car_digital.py run --domain fundiario
# só baixar (não mexe em produção):
/usr/bin/python3 /home/server/.local/bin/sync_car_digital.py download --domain fundiario
```

- `car-digital-sync.service` roda **todo dia às 02:00** e **só executa quando o mês ainda não foi
  validado** — na prática, sincroniza **uma vez por mês** (dia 01, com retry diário até dar certo).
  O domínio `fundiario` tem o mesmo relógio e o mesmo `last_success_month` no `schedule_state.json`.
- Configuração declarativa: `/media/server/HD Backup/VETOR/Fundiario_Federal/config/sources.json`
  (duas fontes `wfs_shape_zip`, `_force_geopackage: true`, `_shape_zip_timeout: 900`).
- Snapshot: `/media/server/HD Backup/VETOR/Fundiario_Federal/{staging,current,archive}/<timestamp>`
  + `manifest.json`, relatório em `reports/` e `RELATORIO_ATUALIZACAO.md`.
- Dados publicados (GeoPackage versionado): `/media/server/HD Backup/GEOSERVER/data/cbers/fundiario_*/`
  (`fundiario_sigef_parcelas_mt__<stamp>.gpkg` 124 MB, `fundiario_snci_imoveis_mt__<stamp>.gpkg` 9 MB).
- Tempo medido (15/11/2026): download SIGEF 166.047 feições = 71 s / zip 59 MB; conversão para GPKG
  ≈ 2 min; publish total ≈ 3 min.

## Mudanças no código (`~/.local/bin/sync_car_digital.py`)

Backup: `sync_car_digital.py.bak-20261115-antes-fundiario`.

1. `FUNDIARIO_ROOT_DIR` (default `/media/server/HD Backup/VETOR/Fundiario_Federal`) + domínio
   `ManagedDomain(key="fundiario", group=FUNDIARIO_FEDERAL, group_mode="NAMED")`.
2. `FUNDIARIO_FEDERAL` entrou em `PARENT_GROUP_ORDER` (depois de `FISCALIZACAO`).
3. `split_wfs_params`: qualquer chave começando com `_` é interna e **não** vai para o WFS
   (habilitou `_force_geopackage`).
4. `build_snapshot` grava `force_geopackage` no layer e `needs_geopackage()` honra a flag —
   publica em GeoPackage mesmo abaixo de 1,9 GB, preservando nomes de campo longos.
5. **Cache-buster na validação pública:** o Cloudflare serve `GetCapabilities` com
   `cache-control: public, max-age=3600`. Sem `&_ts=<epoch>` a validação lia a cópia antiga e
   falhava (`GetCapabilities publico sem N camadas`) logo depois de publicar — os 4 retries de 75 s
   não adiantavam porque o TTL é de 1 h. Agora a conferência pública passa.

## Pitfalls

1. **Não confundir com o antigo** `acervofundiario` (morto) nem com `wms.cursar.space` desatualizado:
   a prova é `GetCapabilities` **com cache-buster** ou o REST local (`127.0.0.1:8081`).
2. **Grupo CONTAINER não é pedível** como camada única; por isso `FUNDIARIO_FEDERAL` é `NAMED`.
3. **Shapefile corta nome de campo em 10 caracteres** — para base fundiária o UUID tem que chegar
   inteiro; sempre GeoPackage nesse domínio.
4. `sinter:parcelas_sigef` responde **0 feições** — não usar; o SIGEF do SINTER é `sinter:sigef`
   (375.939 parcelas) ou, preferencialmente, o `geonode:sigef_geo` do INCRA.
5. O layer SIGEF em escala estadual é pesado (~12 s num GetMap 700×700 com o estilo `polygon`
   padrão). Para mapa final, recortar por município/bbox ou usar estilo simples.

## Como conferir depois de mexer

```bash
# 1) contagem no WFS local
curl -s "http://127.0.0.1:8081/geoserver/cbers/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=cbers:fundiario_sigef_parcelas_mt&resultType=hits" | grep -o 'numberMatched="[0-9]*"'
# 2) render
curl -s -o /tmp/x.png -w "%{http_code} %{size_download}\n" "http://127.0.0.1:8081/geoserver/cbers/wms?service=WMS&version=1.3.0&request=GetMap&layers=cbers:FUNDIARIO_FEDERAL&width=600&height=600&format=image/png&crs=EPSG:4326&bbox=-53.1,-13.3,-51.9,-11.6"
# 3) validação completa
/usr/bin/python3 ~/.local/bin/sync_car_digital.py validate
```
