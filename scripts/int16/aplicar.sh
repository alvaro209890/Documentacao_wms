#!/usr/bin/env bash
# =============================================================================
# aplicar.sh — troca o GeoTIFF TRUNCADO da cena Int16 20250813 213/129 PAN pelo
# candidato regenerado (BAND0 do INPE + pansharpen ArcGIS igual ao original).
#
# O que faz, nesta ordem (para no primeiro erro):
#   1. confere o sha256 do candidato (.tif e .ovr) contra o SHA256SUMS do staging
#   2. confere que o arquivo em producao e o TRUNCADO conhecido (sha256)
#   3. capabilities + GetMap ANTES (norte/sul, camada e grupo) -> backup/<data>/
#   4. BACKUP: move (rename, mesmo disco, nada e apagado) o .tif truncado para
#      backups/<data>/ e grava o sha256 dele
#   5. copia o candidato para <nome>.tif.novo no diretorio de producao, confere o
#      sha256 e so entao renomeia para o nome final (troca atomica); idem .ovr
#   6. reset do coveragestore via REST (sem restart do GeoServer)
#   7. GetMap DEPOIS: camada e grupo, norte e sul, tem que sair PNG com dado.
#      Se nao sair, REVERTE SOZINHO (voltar.sh) e sai com erro.
#
# Nada e apagado. Desfazer: ./voltar.sh backups/<data>
# Credencial: GEOSERVER_USER / GEOSERVER_PASSWORD so no ambiente (nunca em arquivo).
#
# Producao:   ./aplicar.sh --confirmo-producao
# Ensaio:     GS_URL=http://127.0.0.1:18081/geoserver GRUPO= ARQ_PROD=<copia>.tif ./aplicar.sh
# =============================================================================
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/comum.sh"
CONFIRMO=0; [ "${1:-}" = --confirmo-producao ] && CONFIRMO=1
if [ "$EH_PROD" = 1 ] && [ "$CONFIRMO" != 1 ]; then
  echo "GS_URL e PRODUCAO ($GS). Rode com --confirmo-producao."; exit 2
fi
BK="$AQUI/backups/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BK"
echo "$ARQ_PROD" > "$BK/arq_prod"; echo "$GS" > "$BK/gs_url"
log "aplicar: gs=$GS arq=$ARQ_PROD backup=$BK"

# ---------------------------------------------------------------- 1. candidato
[ -n "$SHA_CAND_TIF" ] && [ -n "$SHA_CAND_OVR" ] || { log "ERRO: SHA256SUMS do candidato incompleto"; exit 3; }
for ext in tif tif.ovr; do
  esperado=$SHA_CAND_TIF; [ $ext = tif.ovr ] && esperado=$SHA_CAND_OVR
  obtido=$(sha "$CANDIDATO_DIR/$NOME.$ext")
  [ "$obtido" = "$esperado" ] || { log "ERRO: sha256 do candidato $ext nao bate ($obtido)"; exit 3; }
  log "candidato $ext ok ($obtido)"
done

# ---------------------------------------------------------------- 2. producao
[ -e "$ARQ_PROD.ovr" ] && { log "ERRO: ja existe $ARQ_PROD.ovr (estado inesperado)"; exit 4; }
atual=$(sha "$ARQ_PROD")
if [ "$atual" = "$SHA_CAND_TIF" ]; then log "ja aplicado (producao = candidato). Nada a fazer."; exit 0; fi
if [ "$atual" != "$SHA_PROD_TRUNCADO" ] && [ "${ACEITAR_OUTRO_SHA:-0}" != 1 ]; then
  log "ERRO: arquivo em producao nao e o truncado conhecido ($atual). ACEITAR_OUTRO_SHA=1 para forcar."; exit 4
fi
echo "$atual" > "$BK/sha256_original"
cp -p "$DIR_PROD/$NOME.tfw" "$BK/" 2>/dev/null || true
livre=$(df --output=avail -B1 "$DIR_PROD" | tail -1)
precisa=$(( $(stat -c %s "$CANDIDATO_DIR/$NOME.tif") + $(stat -c %s "$CANDIDATO_DIR/$NOME.tif.ovr") + 1073741824 ))
[ "$livre" -gt "$precisa" ] || { log "ERRO: espaco insuficiente em $DIR_PROD"; exit 5; }

# ---------------------------------------------------------------- 3. antes
capabilities
conferir_render antes || true

# ---------------------------------------------------------------- 4+5. troca
cp "$CANDIDATO_DIR/$NOME.tif" "$ARQ_PROD.novo"
cp "$CANDIDATO_DIR/$NOME.tif.ovr" "$ARQ_PROD.ovr.novo"
[ "$(sha "$ARQ_PROD.novo")" = "$SHA_CAND_TIF" ] || { log "ERRO: copia do .tif corrompida; nada trocado (.novo fica para inspecao)"; exit 6; }
[ "$(sha "$ARQ_PROD.ovr.novo")" = "$SHA_CAND_OVR" ] || { log "ERRO: copia do .ovr corrompida; nada trocado"; exit 6; }
log "copias conferidas por sha256"
mv "$ARQ_PROD" "$BK/$NOME.tif"            # original truncado -> backup (mesmo disco = rename)
echo trocado > "$BK/estado"
mv "$ARQ_PROD.novo" "$ARQ_PROD"
mv "$ARQ_PROD.ovr.novo" "$ARQ_PROD.ovr"
log "troca feita: $(sha "$ARQ_PROD" | cut -c1-16)… em producao; original em $BK/"

# ---------------------------------------------------------------- 6+7. depois
reset_store || log "AVISO: reset do store falhou (confira credencial)"
capabilities
if conferir_render depois; then
  echo aplicado > "$BK/estado"; log "OK: camada e grupo com dado no norte e no sul"
else
  log "FALHOU a conferencia depois -> revertendo"
  if [ "$CONFIRMO" = 1 ]; then "$AQUI/voltar.sh" "$BK" --confirmo-producao; else "$AQUI/voltar.sh" "$BK"; fi
  exit 7
fi
