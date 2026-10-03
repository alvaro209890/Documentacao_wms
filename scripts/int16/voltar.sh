#!/usr/bin/env bash
# =============================================================================
# voltar.sh — desfaz o aplicar.sh: devolve o .tif original (truncado) e tira o
# .ovr novo. Nada e apagado: o candidato que estava em producao vai para
# <backup>/removido_na_volta/.
# Uso: ./voltar.sh backups/<data> [--confirmo-producao]
# =============================================================================
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/comum.sh"
ORIG_BK="$(cd "${1:?uso: voltar.sh backups/<data>}" && pwd)"
CONFIRMO=0; [ "${2:-}" = --confirmo-producao ] && CONFIRMO=1
if [ "$EH_PROD" = 1 ] && [ "$CONFIRMO" != 1 ]; then
  echo "GS_URL e PRODUCAO ($GS). Rode com --confirmo-producao."; exit 2
fi
BK="$ORIG_BK"
[ "$(cat "$BK/arq_prod")" = "$ARQ_PROD" ] || { log "ERRO: backup e de outro arquivo ($(cat "$BK/arq_prod"))"; exit 3; }
[ -f "$BK/$NOME.tif" ] || { log "ERRO: sem $NOME.tif no backup"; exit 3; }
esperado=$(cat "$BK/sha256_original")
[ "$(sha "$BK/$NOME.tif")" = "$esperado" ] || { log "ERRO: sha256 do backup nao bate"; exit 3; }
log "voltar: backup ok ($esperado)"

mkdir -p "$BK/removido_na_volta"
for f in "$ARQ_PROD" "$ARQ_PROD.ovr" "$ARQ_PROD.novo" "$ARQ_PROD.ovr.novo"; do
  if [ -e "$f" ]; then mv "$f" "$BK/removido_na_volta/"; fi
done
mv "$BK/$NOME.tif" "$ARQ_PROD"
[ "$(sha "$ARQ_PROD")" = "$esperado" ] || { log "ERRO: sha256 depois da volta nao bate"; exit 4; }
echo revertido > "$BK/estado"
log "original devolvido (sha256 ok)"
reset_store || log "AVISO: reset do store falhou"
capabilities
conferir_render revertido || true
log "revertido. Estado igual ao de antes do aplicar.sh (sul da cena volta a sair vazio)."
