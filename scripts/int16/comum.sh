#!/usr/bin/env bash
# comum.sh — variaveis e funcoes compartilhadas por aplicar.sh / voltar.sh
# Cena: CBERS-4A WPM 2025-08-13 213/129 L4 C342 PAN (Int16, pansharpen ArcGIS Esri 0,166/0,167/0,167/0,5)
# Tudo pode ser sobrescrito por ambiente para ensaiar fora de producao (ARQ_PROD, GS_URL, CANDIDATO_DIR).

L=213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan          # camada (producao)
# No GeoServer de TESTE a camada chama INT16_TRUNC (mesmo store reapontado para a
# copia do ensaio). Sem esta variavel o GetMap do conferir_render devolve
# LayerNotDefined e o aplicar.sh reverteria sem motivo — ja aconteceu no 1o ensaio.
L=${CAMADA:-213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan}
ST=${STORE:-213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan}  # store do reset REST
GRUPO="${GRUPO-orbit_213_129_y2025}"   # GRUPO= (vazio) no GeoServer de teste, que nao tem o grupo
NOME=CBERS_4A_WPM_20250813_213_129_L4_C342_PAN
ARQ_PROD="${ARQ_PROD:-/media/server/HD Backup/RASTER/CBERS_4A/213_129/2025/$NOME.tif}"
DIR_PROD="$(dirname "$ARQ_PROD")"
CANDIDATO_DIR="${CANDIDATO_DIR:-/media/server/HD Backup/Staging_WMS/int16_20250813/candidato}"
GS="${GS_URL:-http://127.0.0.1:8081/geoserver}"
# sha256 do .tif TRUNCADO que esta em producao (medido 29/09/2026 04:08)
SHA_PROD_TRUNCADO=0db328a9f94308e4e095299cdd8c532a4d1a8a4360b78c356ec76830e2466b26
# sha256 do candidato: lido do SHA256SUMS gerado no staging
SHA_CAND_TIF=$(awk -v n="$NOME.tif" '$2==n{print $1}' "$CANDIDATO_DIR/SHA256SUMS" 2>/dev/null)
SHA_CAND_OVR=$(awk -v n="$NOME.tif.ovr" '$2==n{print $1}' "$CANDIDATO_DIR/SHA256SUMS" 2>/dev/null)

EH_PROD=0; case "$GS" in *:8081/*|*wms.cursar.space*) EH_PROD=1;; esac
: "${GEOSERVER_USER:?defina GEOSERVER_USER (nunca em arquivo)}"
: "${GEOSERVER_PASSWORD:?defina GEOSERVER_PASSWORD (nunca em arquivo)}"
AUTH=(-u "$GEOSERVER_USER:$GEOSERVER_PASSWORD")
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PCT="$AQUI/pct_opaco.py"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$BK/log.txt"; }

sha() { sha256sum "$1" | awk '{print $1}'; }

# GetMap em EPSG:32722 (projetado: WMS 1.3.0 usa x,y; o gotcha lat,lon e so do geografico)
# norte = parte que sempre leu; sul = parte que estava ilegivel no arquivo truncado
# 🔴 2026-10-03: o BBOX_SUL antigo (330000,8545000,332000,8547000) cai FORA da borda
# da orbita 213/129 (que e inclinada) e dava 0% de dado mesmo no candidato integro.
# Com o bbox fora da area, o conferir_render reprovava o candidato e o aplicar.sh
# revertia sozinho — publicacao impossivel. Medido ponto a ponto em 03/10: a faixa
# que ainda tem dado no arquivo truncado E y>=8556000; em y=8557000 e abaixo o
# truncado quebra e o candidato devolve 100%. Valor corrigido e conferido:
BBOX_NORTE=330000,8600000,332000,8602000
BBOX_SUL=330000,8556000,332000,8558000
getmap() { # $1=camada $2=bbox $3=saida -> imprime "http=<code> <resultado pct_opaco>" e retorna o exit do pct
  local code
  code=$(curl -s -m 180 -o "$3" -w '%{http_code}' \
    "$GS/cbers/wms?service=WMS&version=1.3.0&request=GetMap&format=image/png&transparent=true&styles=&layers=cbers:$1&crs=EPSG:32722&bbox=$2&width=256&height=256")
  local r; r=$(/usr/bin/python3 "$PCT" "$3"); local ec=$?
  echo "http=$code $r"; return $ec
}

conferir_render() { # $1=rotulo ; grava PNGs em $BK/$1_* ; retorna 0 se TUDO com dado
  local ok=0 c b
  for c in "$L" ${GRUPO:+"$GRUPO"}; do
    for b in norte sul; do
      local bb=$BBOX_NORTE; [ $b = sul ] && bb=$BBOX_SUL
      local r; r=$(getmap "$c" "$bb" "$BK/${1}_${b}_${c}.png") || ok=1
      log "GetMap $1 $b $c: $r"
    done
  done
  return $ok
}

reset_store() { # derruba o reader em cache do GeoTIFF (sem restart do GeoServer)
  local c
  c=$(curl -s "${AUTH[@]}" -o /dev/null -w '%{http_code}' -X POST \
    "$GS/rest/workspaces/cbers/coveragestores/$ST/reset")
  log "reset coveragestore $ST: http=$c"
  [ "$c" = 200 ]
}

capabilities() {
  log "capabilities: $(curl -s -o /dev/null -m 90 -w '%{http_code} %{time_total}s' "$GS/cbers/wms?service=WMS&request=GetCapabilities")"
}
