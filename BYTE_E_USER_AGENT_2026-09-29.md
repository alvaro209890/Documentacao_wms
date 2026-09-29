# Raster Byte × Int16 (staging) e User-Agent no log do proxy (candidato) — 2026-09-29

*(autor: Hermes-server/wms)* · **Nada alterado em produção**: GeoServer 8081, proxy 8082, túnel,
data dir e o GeoTIFF original intocados; sha256 do proxy igual antes/depois; nenhum restart.

## Resumo

| | Resultado |
|---|---|
| Camada | `landsat_224_069_2005_lt05_224069_20051016` (Int16, 3 bandas, estilo `_fixo`) — a mais pedida do WMS público (111 GetMap) |
| Cópia Byte | RGB Byte com o realce do `_fixo` (p2–p98) gravado no pixel + overviews 2–32. 161 → 98 MB |
| Cor | GetMap reais do ArcMap: igual ao original (máx. 1 nível RGB). PNG 100% com dado |
| Ganho só do Byte | −17 a −18% no GetMap do ArcMap (1,24 → 1,01 s) · −38% na extensão inteira |
| 🟠 Achado | A cena está em **EPSG:32622** (UTM 22N, Y negativo) e o ArcMap pede **EPSG:31982** → o GeoServer reprojeta a cada pedido. Só reescrever o georreferenciamento para 31982 (pixel igual, PNG idêntico ao de produção) = −35 a −39%; com Byte junto = **−52 a −53%** (1,24 → 0,58 s) |
| Disco | HD USB × SSD e frio × quente: diferença ≤ 0,1 s nesta camada |
| User-Agent | Patch candidato no `log_message` do proxy, testado num proxy de teste; **não aplicado** |

## Método

- GeoServer de teste: mesmo binário 2.28.3, `-DGEOSERVER_DATA_DIR=<staging>`,
  `jetty.http.port=18081 jetty.http.host=127.0.0.1`, `-DSTOP.PORT=18079`; workspace `staging`.
  Parado no fim. Linha de base: [DESEMPENHO_2026-09-29.md](DESEMPENHO_2026-09-29.md).
- 5 camadas: original no HD (só leitura), cópia Int16 no SSD, cópia Byte, e as duas em 31982.
- Frio = `POST /rest/reset` + `posix_fadvise(DONTNEED)` nos `.tif`/`.ovr`. Quente = mediana de 3.
  3 amostras. Requisições: os 2 GetMap mais repetidos do journal do proxy + extensão inteira.
- Scripts: [`scripts/gerar_copia_byte.py`](scripts/gerar_copia_byte.py),
  [`scripts/bench_byte_vs_int16.py`](scripts/bench_byte_vs_int16.py).

| Requisição (quente, s) | Int16 produção | Byte | Int16 em 31982 | Byte em 31982 |
|---|---|---|---|---|
| ArcMap 31982 1108x631 | 1,24 | 1,01 | 0,80 | **0,58** |
| ArcMap 31982 613x839 | 0,89 | 0,74 | 0,55 | **0,43** |
| Extensão inteira em 32622 | 0,49 | **0,31** | 1,51 | 1,25 |

## Pitfalls

- ⚠️ `gdal_translate -ot Byte -scale min max 1 255` corta abaixo do mínimo em **0 = nodata** →
  pixel escuro vira transparente (732 mil pixels nesta cena). O script corta em 1 e só grava 0
  onde o original é nodata.
- ⚠️ O `.ovr` de produção (2020) não foi feito com `average`: a cópia com overview novo muda a cor
  em zoom afastado (mediana 10 níveis). Testar o método do overview antes de publicar.
- O "~2x" do não-Byte na linha de base era em boa parte **reprojeção**, não tipo de pixel.

## User-Agent no log do proxy (não aplicado)

Mudança de 1 função em `geoserver_wms_public_proxy.py` — a linha do journal ganha só um sufixo,
o prefixo não muda:

```python
    def log_message(self, fmt: str, *args: object) -> None:
        headers = getattr(self, "headers", None)
        user_agent = headers.get("User-Agent", "-") if headers is not None else "-"
        user_agent = "".join(ch if ch.isprintable() else "?" for ch in user_agent)
        user_agent = user_agent.replace('"', "'")[:200] or "-"
        print(f'{self.address_string()} - {fmt % args} ua="{user_agent}"', flush=True)
```

Testado (proxy de teste 18082 → GeoServer de teste): GetMap/GetCapabilities 200, 403 da política,
UA vazio, aspas, caractere de controle (vira `?`, sem injeção no journal), requisição malformada.
Não loga IP de cliente nem cabeçalho de credencial. Aplicar exige **restart do proxy** (~1–5 s de
502 no público) — decisão do Álvaro; script de aplicar/voltar com checagem de sha256 fica no
servidor, fora deste repo.

⚠️ Limite: o backend do GeoForest faz REST e GetMap direto no **8081** (sem proxy); o UA no proxy
não mostra esses pedidos. Para isso seria o request log do Jetty (restart do GeoServer).

## Pendências (decisão do Álvaro)

1. Aplicar o UA no proxy.
2. Levantar as Landsat em 32622 pedidas em 31982; decidir republicar com georreferenciamento
   31982 (ganho maior, sem mudar cor) e/ou Byte.
3. Request log do Jetty no 8081, se quiser separar o GeoForest.
