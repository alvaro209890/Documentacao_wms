# Cena Int16 20250813 213/129 PAN — ganho medido e publicação preparada

*(Medição e preparação: 2026-10-03 · Autor: Hermes-server/wms · card `t_8c7c6b37`*
🔴 **Nada foi alterado em produção.** O GeoServer, o proxy, o túnel e os arquivos de
produção estão como estavam. A publicação é decisão do Álvaro.*

Documento de continuação de `INT16_REGENERACAO_2026-09-29.md` (que regeneration e validou o
candidato). Aqui está o **ganho medido com número** e a **sequência de publicação pronta**.

---

## 1. Resumo — o que a troca resolve

| | Hoje (produção) | Com o candidato | Ganho |
|---|---|---|---|
| `.tif` | 7.626.696.695 B, **truncado** | 8.502.674.505 B, íntegro | +875.977.810 B legíveis |
| `.ovr` (overviews) | **não existe** | 2.318.410.322 B, níveis 2–256 | render de cena inteira sai de **90,87 s → 0,18 s** |
| Metade sul da cena | **erro de leitura** (319 blocos de grade) | lida inteira, **0 erro** | dado recuperado |
| Estilo `_fixo` | **ausente** no capabilities | ainda ausente | ver §5 |

---

## 2. Shas conferidos hoje (03/10/2026)

Medidos de novo, byte a byte, contra o `SHA256SUMS` do staging:

| Arquivo | sha256 | Confere? |
|---|---|---|
| `CBERS_4A_WPM_20250813_213_129_L4_C342_PAN.tif` | `f12dc7bcfd22366383b1fa6518d11578c3dc9de129caf6e4e3c234c744ded042` | ✅ bate |
| `CBERS_4A_WPM_20250813_213_129_L4_C342_PAN.tif.ovr` | `59367e7e870af0898d05905488b635c155094eb3934ccd17115723087700b037` | ✅ bate |

Arquivo em produção hoje (o truncado), sha registrado em `comum.sh`:
`0db328a9f94308e4e095299cdd8c532a4d1a8a4360b78c356ec76830e2466b26` — **não alterado**.

Scripts conferidos intactos: `aplicar.sh`, `voltar.sh`, `comum.sh`, `pct_opaco.py`
(`~/Documentos/orquestracao-20260929/int16-redownload/`).

---

## 3. Ganho medido (números, não impressão)

Medido no **GeoServer de teste** (`127.0.0.1:18081`, mesmo binário 2.28.3, data_dir próprio,
produção só lida) com 4 versões da mesma cena publicadas lado a lado, para o comparativo ser justo:

- `TRUNC` = o `.tif` de produção (truncado, sem `.ovr`)
- `CAND` = o candidato (íntegro, **com** `.ovr`)
- `NOOVR` = o **mesmo** `.tif` do candidato, **sem** o `.ovr` (isola o efeito do overview)
- `IRMA` = a cena Byte irmã de 8 m, mesma data (sanidade)

GetMap 256×256, EPSG:32722 (projetado → `x,y`), `transparent=true`, estilo padrão.
Pontos escolhidos **dentro da área com dado** (ver §4 — fora da borda da órbita todos dão 0%).

| Ponto | TRUNC (hoje) | CAND | NOOVR | IRMA (Byte) |
|---|---|---|---|---|
| **cena inteira** (`281266,8535736,393570,8651156`) | **90,87 s · ERRO** (0,7 KB XML) | **0,18 s · PNG 100,0 KB · 68,30% dado** | 162,69 s · PNG 129,8 KB · 66,85% | 0,42 s · PNG 111,0 KB · 70,59% |
| norte (2 km×2 km) | 0,74 s · 203,1 KB · 100% | 0,44 s · 193,3 KB · 100% | 0,70 s · 203,1 KB · 100% | 0,38 s · 179,7 KB · 100% |
| meio | 0,47 s · 168,4 KB · 100% | 0,30 s · 156,0 KB · 100% | 0,41 s · 168,4 KB · 100% | 0,25 s · 157,6 KB · 100% |
| sul com dado | 0,16 s · 1,6 KB · **0%** | 0,16 s · 1,6 KB · 0% | 0,14 s · 1,6 KB · 0% | 0,23 s · 19,6 KB · 21,56% |

🔴 **O número que importa: 90,87 s → 0,18 s na cena inteira (≈505× mais rápido), e o "antes"
não devolvia imagem — devolvia `ServiceException`.** Qualquer cliente que peça a cena
completa hoje ou espera ~91 s ou leva erro; depois passa a receber PNG em 0,18 s.

⚠️ **Ganho vem do `.ovr`, não do `.tif` ser maior.** O `NOOVR` (mesmo arquivo íntegro, sem
overview) levou **162,69 s** na cena inteira — mais que o truncado, porque agora lê o arquivo
todo em resolução nativa. Ou seja: **publicar o `.tif` sem o `.ovr` seria pior que hoje.**
O `.ovr` é obrigatório, não opcional.

### 3.1 Por que o "antes" falhava (medido, não deduzido)

Mapa de dado por grade (blocos de 2,8 km) do arquivo **truncado**:

```
 32 +#################################+EEEEEEE
 33 EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
 ...  (linhas 33 a 40: 100% erro de leitura)
```

319 blocos com erro de leitura — **toda a metade sul**. O candidato, na mesma grade:

```
 32 +#################################+....
 33 ++++##############################+....
 34 .....++++#########################+....
 ...  (0 erro)
```

O sul da cena não era "imagem com pixel faltando": era **erro de leitura** — o GeoServer
devolve `ServiceException` (HTTP 200), e isso quebra também o **layergroup**
`orbit_213_129_y2025` ao pedir a parte sul, porque a falha de uma cena filha derruba o grupo.

### 3.2 Efeito no grupo (medido em produção, leitura pura)

GetMap do grupo `orbit_213_129_y2025` no 8081, hoje:

| Ponto | Grupo hoje |
|---|---|
| norte / meio | PNG 100% opaco |
| `sul_ant` (sul_ant) | **ERRO** (`ServiceException`) |
| sul / sul_fim | PNG **0,00%** — imagem vazia |

Ou seja: hoje um mapa que cobre o sul da órbita 213/129 sai **vazio ou com erro**, sem
nenhum aviso — é o pior modo de falha, o que a casa chama de WMS que falha em silêncio.

---

## 4. ⚠️ Detalhe de método: janela fora da borda engana

A borda da órbita é inclinada. Uma janela de 2 km em `y=8550000` fica **fora** da cena e dá
0% de dado **em todas as versões** — inclusive no candidato. Medir por aí faz concluir
falsamente que a troca não serve. Os pontos da tabela acima estão dentro da área com dado,
confirmados pela grade (§3.1). Registro isso porque foi o erro que quase me fez publicar
uma conclusão errada.

---

## 5. 🔴 Pendência conhecida: o estilo `_fixo` continua faltando

A camada **não tem** `<camada>_fixo` no capabilities (a irmã 20250913 tem):

```
213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_fixo     ✅ existe
213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan       ✅ existe
213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan_fixo  ❌ AUSENTE
```

`gerar_estilos_fixos.py` pula a camada ("erro nas estatísticas") porque o arquivo está
truncado. **Depois de publicar o candidato, rodar `gerar_estilos_fixos.py`** — aí ele passa.
Sem o `_fixo`, a cena Int16 continua saindo com realce automático, que varia conforme o BBOX
(gotcha registrado em `03-gis-ambiental/wms-wfs.md` no vault). Não bloqueia a publicação.

---

## 6. O que o `aplicar.sh` faz, e o que cai durante a troca

`aplicar.sh` (em `~/Documentos/orquestracao-20260929/int16-redownload/`), nesta ordem:

1. confere sha256 do candidato (`.tif` e `.ovr`) contra `SHA256SUMS`
2. confere que o arquivo em produção é o truncado conhecido — **aborta se não for**
3. capabilities + GetMap antes (norte e sul, camada e grupo)
4. **backup**: renomeia (mesmo disco, instantâneo) o `.tif` truncado para `backups/<data>/`
5. copia o candidato como `.novo`, confere sha256 da cópia, **só então** renomeia
   (troca atômica); idem `.ovr`
6. reset do coveragestore via REST — **sem reiniciar o GeoServer**
7. GetMap depois: tem que sair PNG com dado. **Se falhar, reverte sozinho** e sai com erro

| | O que cai | Por quanto tempo |
|---|---|---|
| GeoServer 8081 | **não reinicia** — o reader é derrubado por reset via REST | reader da cena só, ~1 s |
| Demais 737 camadas | **não sente nada** | — |
| AlertaCAR / GeoForest | sem indisponibilidade; requisições da cena 20250813 durante a cópia do `.novo` podem ler o arquivo antigo | janela da cópia |
| Disco | precisa de ~10,8 GB livres (`.novo` + `.ovr` + folga de 1 GB) | HD tem 1,1 TB livres ✅ |

**Tempo estimado:** cópia de 8,5 GB + 2,3 GB no HD ≈ **6–10 min**, mais ~1 min de GetMap
de conferência. O `gerar_estilos_fixos.py` depois é separado.

---

## 7. Sequência de publicação (para o Álvaro decidir)

```bash
# 1. Credencial só no ambiente (nunca em arquivo, nunca no repo público)
export GEOSERVER_USER=admin
export GEOSERVER_PASSWORD=...

# 2. Healthcheck antes (se já estiver quebrado, você precisa saber antes)
curl -s -o /dev/null -w "local  %{http_code}\n" \
  "http://127.0.0.1:8081/geoserver/cbers/wms?service=WMS&request=GetCapabilities"
curl -s -o /dev/null -w "público %{http_code}\n" \
  "https://wms.cursar.space/geoserver/cbers/wms?service=WMS&request=GetCapabilities"

# 3. Trocar (backup automático + conferência com reversão automática)
cd /home/server/Documentos/orquestracao-20260929/int16-redownload
./aplicar.sh --confirmo-producao

# 4. Conferir que deu certo (tem que sair PNG, não XML)
curl -s -o /tmp/sul.png -w "%{http_code}\n" \
 "http://127.0.0.1:8081/geoserver/cbers/wms?service=WMS&version=1.3.0&request=GetMap\
&format=image/png&transparent=true&styles=&layers=cbers:orbit_213_129_y2025\
&crs=EPSG:32722&bbox=300000,8550000,302000,8552000&width=256&height=256"
file /tmp/sul.png     # tem que dizer PNG

# 5. Estilo _fixo que ficou faltando (agora que a estatística roda)
/home/server/Documentação_wms/scripts/gerar_estilos_fixos.py

# 6. Healthcheck depois + CHANGELOG
```

**Comando de volta (exatamente):**

```bash
cd /home/server/Documentos/orquestracao-20260929/int16-redownload
ls -dt backups/*/ | head -1        # o backup que o aplicar.sh criou
./voltar.sh backups/<essa-data> --confirmo-producao
```

Nada é apagado: o original vai para `<backup>/`, e o que estava em produção na hora da volta
vai para `<backup>/removido_na_volta/`.

---

## 8. Ensaio do ciclo aplicar → voltar (feito 03/10/2026)

O ciclo foi ensaiado **de ponta a ponta** no GeoServer de teste (`127.0.0.1:18081`, mesmo
binário 2.28.3) com um `ARQ_PROD` de **cópia** em `/media/server/HD Backup/Staging_WMS/…/ensaio_prod/`.
O `aplicar.sh` de produção **não foi executado** — produção ficou com o arquivo original
(`sha 0db328a9…`, sem `.ovr`) e os três serviços `active`, WMS público 200.

| Etapa | Resultado |
|---|---|
| shas do candidato (`.tif` + `.ovr`) | conferidos ✅ |
| `GetMap` **antes** — norte | ✅ PNG 100% opaco |
| `GetMap` **antes** — sul | ❌ `ServiceException` (o defeito) |
| cópias `.novo` conferidas por sha256 | ✅ |
| troca (rename atômico) | ✅ `f12dc7bc…` instalado |
| `reset` do coveragestore via REST | ✅ http 200 |
| `GetMap` **depois** — norte e sul | ✅ PNG 100% nos dois |
| `aplicar.sh` | ✅ **exit 0** |
| `voltar.sh` | ✅ **exit 0**, sha voltou a `0db328a9…`, `.ovr` removido, sul volta ao erro |
| Estado final idêntico ao inicial | ✅ |

Duração real do `aplicar.sh`: **~25 min** (sha das cópias ~10 min + conferência ~4 min).
Mais `voltar.sh`: **~13 min**. Planeje ~40 min para o ciclo completo.

### 8.1 🔴 Dois bugs do `comum.sh` corrigidos no ensaio

Ambos teriam feito a publicação **reverter sozinha** em produção, sem culpa do candidato:

1. **`BBOX_SUL` estava fora da borda da órbita.** O valor antigo
   (`330000,8545000,332000,8547000`) cai fora da cena 213/129, que tem borda inclinada, e dava
   **0% de dado mesmo no candidato íntegro**. O `conferir_render` reprovava o arquivo bom e o
   `aplicar.sh` revertia. Corrigido para `330000,8556000,332000,8558000` — conferido: no
   truncado dá erro, no candidato dá 100%.

2. **Camada e store fixos no `comum.sh`.** O `reset` REST e o `GetMap` usavam o nome de
   produção, que não existe no GeoServer de teste (dava 404 e `LayerNotDefined`). Agora são
   `CAMADA` e `STORE`, sobreponíveis por ambiente — em produção continuam com o valor padrão.

⚠️ **Espaço:** o ensaio precisa de ~26 GB (truncado + candidato + `.ovr` + `.novo` + backup).
Feito no SSD levou o disco do sistema a **97%** e foi interrompido a tempo. **Rode no HD.**

### 8.2 Ganho de tempo do script: dá para preparar antes

O `aplicar.sh` gasta ~10 min conferindo sha256 do candidato (8,5 GB + 2,3 GB lidos do HD) e
depois ~10 min copiando e conferindo de novo. Dá para baixar pela metade deixando o `.novo` e o
`.ovr.novo` já copiados e conferidos antes da janela — mas **não fiz isso**, para o runbook
publicado ser exatamente o que foi ensaiado. Se a janela for apertada, essa é a otimização.

---

## 9. Como reproduzir a medição

```bash
# GS de teste (produção 8081 não é tocada)
bash ~/Documentos/orquestracao-20260929/.../montar_comparativo2.sh   # 4 versões
/usr/bin/python3 comparativo2.py comp2 http://127.0.0.1:18081/geoserver
/usr/bin/python3 grade.py <tif>                                      # mapa de dado/erro
```

Ferramentas desta medição (no workspace do card `t_8c7c6b37`): `comparativo2.py`, `grade.py`,
`diff_png.py`, `janela.py`, `montar_comparativo2.sh`, `ensaio_voltar.sh`.

---

## Ver também

- `INT16_REGENERACAO_2026-09-29.md` — regeneração e validação do candidato
- `BYTE_E_USER_AGENT_2026-09-29.md` — raster Byte × Int16 e log com User-Agent
- `DESEMPENHO_2026-09-29.md` — linha de base do WMS
- vault: `02-projetos/geoserver-wms.md` · `04-playbooks/publicar-camada-wms.md`