# Segurança

## Modelo de exposição pública

O serviço público (`wms.cursar.space`) passa por um proxy Python que foi desenhado para **apresentação** — limpar o catálogo visível — e não como barreira de segurança.

### O que o proxy filtra

- **Path**: só `/geoserver/...` terminando em `/ows`, `/wms`, `/wfs`, `/wmts` ou `/geoserver/schemas/...` → resto 403
- **Métodos**: GET/HEAD/POST (PUT/DELETE/OPTIONS → 405)
- **GetCapabilities do WMS**: reescrito para expor apenas os grupos **RASTER** e **VETOR**

### Exposição conhecida (verificada em 2026-08-01)

1. **Nomes de camada não são validados** — o proxy encaminha qualquer `layers=`/`typeName=` ao GeoServer. Camadas fora do catálogo público respondem por GetMap/GetFeatureInfo se o nome for conhecido.
2. **WFS GetCapabilities não é reescrito** — lista as 737 camadas completas, incluindo SIMCAR Digital (`car_digital_simcar_d_*`) e Fiscalização (`fiscalizacao_*`), com nomes exatos. Descobrir os nomes é trivial.
3. **WFS GetFeature permite download bruto** — geometria + atributos de qualquer camada vetorial sem autenticação.

### Decisão

**Manter como está** (decisão do proprietário, 2026-08-01). Reavaliar se o modelo comercial/produto mudar. Registrado também no Segundo Cérebro (`03-gis-ambiental/wms-wfs.md`).

### Correção possível (se um dia quiser)

1. **Whitelist de camadas no proxy** — validar `layers`/`typeName` contra a lista dos grupos públicos (RASTER, VETOR + filhos) → 403 para o resto
2. **Bloquear WFS GetFeature de camadas internas** (no proxy ou publicando WFS só para o que é público no GeoServer)
3. Defesa extra: regra no Cloudflare WAF por padrão de URL

**Efeito colateral:** clientes que usam RASTER/VETOR não sentem nada; consumo interno de camadas internas pela URL pública precisaria de caminho autenticado.

## Outros pontos

- **Healthcheck**: não detecta camadas quebradas (só GetCapabilities) — ver [SERVICOS.md](SERVICOS.md).
- **GeoServer admin REST** (8081) escuta em 127.0.0.1 — não exposto publicamente. O proxy não encaminha `/rest`.
- **Credenciais**: senha do admin do GeoServer e authkeys vivem em env files locais — não versionar em repos públicos (este repositório deve continuar sem segredos).
