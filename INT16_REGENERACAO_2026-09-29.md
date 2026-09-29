# Regeneração da Cena Int16 20250813 213/129 PAN (em staging)

*(Data: 2026-09-29 · Autor: Hermes-server/wms · Sem alteração em produção)*

## Contexto

Na auditoria de 29/09/2026, a cena `cbers:213_129_2025_cbers_4a_wpm_20250813_213_129_l4_c342_pan`
(arquivo `/media/server/HD Backup/RASTER/CBERS_4A/213_129/2025/CBERS_4A_WPM_20250813_213_129_L4_C342_PAN.tif`)
foi identificada como o único GeoTIFF truncado entre os 743 rasters do acervo:
- Tamanho no disco: 7.626.696.695 bytes
- Fim do último bloco no IFD/cabeçalho: 7.644.370.148 bytes
- **Faltavam 17.673.453 bytes (~17,7 MB)** decorrentes de queda de conexão no download original da BAND0 em 2025.
- Efeito: 38.260 de 197.989 blocos 128×128 ilegíveis na porção sul (coordenada Y < 8.559.036 em EPSG:32722). Requisições GetMap nessa área devolviam `ServiceException` (NullPointerException), quebrando a camada individual e o grupo `orbit_213_129_y2025`.

## Ações Executadas (Staging)

1. **Download das bandas oficiais**:
   - Catálogo INPE BDC STAC (`CB4A-WPM-L4-DN/2025_08/.../213_129_0/4_BC_UTM_WGS84/`)
   - Bandas BAND0 (PAN 2m, 2.565.541.611 B), BAND2 (8m), BAND3 (8m) e BAND4 (8m) baixadas na íntegra para staging.

2. **Regeneração idêntica**:
   - Processamento realizado com ArcGIS 10.8 (`arcpy.CreatePansharpenedRasterDataset_management`)
   - Algoritmo Esri, pesos 0,166 / 0,167 / 0,167 / 0,5 (B3, B4, B2, PAN), dados Int16, compressão LZW, tile 128×128.
   - Arquivo resultante: 8.502.674.505 bytes (recuperando os dados íntegros da cena).

3. **Validação técnica**:
   - `checar_tiff_truncado.py`: 0 truncados, 0 erros.
   - Comparação pixel a pixel na parte norte legível: 100,0% idêntico (3.638.241 pixels amostrados em 75 blocos, diferença média 0.0, diferença máxima 0).
   - Validação da porção sul: 418 blocos lidos sem nenhum erro de descompressão.
   - `gdalinfo -checksum`: leitura completa das 3 bandas sem falhas (Band 1 = 21328, Band 2 = 64019, Band 3 = 3543).
   - Overviews gerados com `gdaladdo` nos níveis 2 a 256 (DEFLATE).

4. **Scripts de troca com reversão automática**:
   - `aplicar.sh` e `voltar.sh` preparados em `/home/server/Documentos/orquestracao-20260929/int16-redownload/`.
   - Utilizam rename atômico no mesmo disco, verificação de sha256 e reset de coveragestore via REST sem reiniciar o GeoServer.
   - Reversão automática embutida se o GetMap posterior falhar.

## Estado de Produção

Nenhum arquivo de produção foi alterado. O GeoServer e serviços permanecem 100% inalterados e saudáveis.
A aplicação fica a critério do operador conforme o runbook em `/home/server/Documentos/orquestracao-20260929/int16-redownload.md`.
