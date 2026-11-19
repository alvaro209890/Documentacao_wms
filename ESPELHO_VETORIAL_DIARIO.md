# Espelho vetorial diário

O timer `car-digital-sync.timer` dispara às 02h no server, em horário de Brasília. O serviço `wms-vetores-diarios.service` roda antes da verificação mensal da base de referência. O espelho mensal do SIMCAR Digital no Drive reaproveita os arquivos locais e é enviado uma vez por mês.

| Grupo | Dados |
|---|---|
| CAR | ATP em análise e analisada da SEMA, GeoPackage com índice por número do CAR |
| SIMCAR Digital | Camadas cadastradas na configuração do GeoServer |
| Fiscalização | Embargos, desembargos e autos da SEMA-MT e do SIGA |
| Fundiário | SIGEF do INCRA e SNCI do SINTER, filtrados para Mato Grosso |
| PAMGIA | IBAMA e ICMBio no entorno de Mato Grosso |

Cada camada é baixada para uma pasta temporária no HD. A contagem é confrontada com o WFS ou com os identificadores do PAMGIA. O GDAL confere o arquivo, o CRS e a extensão. Uma camada com zero feições só passa se o WFS de origem e o publicado já confirmarem zero. Para camadas publicadas, o script troca o caminho do datastore existente, preserva estilos e nomes, e confirma a contagem pelo WFS local. Se a confirmação falhar, restaura o caminho anterior. As novas ATPs e bases do PAMGIA ficam no HD, com leitura local pelo Optimus Geo. A publicação pública do GeoServer usa os mesmos datastores já existentes.

O `estado.json` de cada camada aponta as três versões válidas mais recentes. O mesmo arquivo é compartilhado quando o conteúdo das versões coincide. A remoção roda após gravar a nova versão e só alcança diretórios geridos pelo espelho que perderam todas as referências. Os arquivos históricos da rotina mensal anterior foram preservados. Os mosaicos raster continuam no fluxo próprio.

```sh
systemctl --user list-timers car-digital-sync.timer
systemctl --user status wms-vetores-diarios.service
journalctl --user -u wms-vetores-diarios.service --since today
```

Cada evento traz a camada, o estado e a contagem ou causa técnica. Se um provedor falhar, a última versão daquela camada continua disponível e os outros grupos seguem. O estado de cada camada indica a data da última coleta válida.

Para repetir uma carga sem esperar o próximo agendamento, use a CLI no server. A mesma camada validada no dia é reaproveitada.

```sh
python3 scripts/sync_vetores_diario.py --grupo fundiario
python3 scripts/sync_vetores_diario.py --grupo car
```

As definições de systemd estão em `services/`. Para suspender novas atualizações, pause o timer. Para voltar à agenda mensal anterior, remova apenas o drop-in `zz-espelho-diario.conf` e recarregue o systemd. Mantenha o espelho no HD enquanto um datastore apontar para ele.

## Verificação da implantação em 19/11/2026

- As duas ATPs da SEMA ficaram disponíveis com 53.272 feições analisadas e 125.394 em análise. O SIGEF publicou 166.465 feições e respondeu por WFS e GetMap do GeoServer. Confirmamos sete camadas de fiscalização, duas do PAMGIA de MT e duas camadas do SIMCAR Digital, com a primeira carga ainda em execução.
- O SINTER excedeu o prazo. O SNCI continuou no último arquivo publicado. Os consumidores já podiam usar as versões publicadas das camadas cuja atualização ainda estava em curso.
- O WMS e o Optimus Geo continuaram ativos. Os testes de retenção confirmaram a exclusão do arquivo expirado no quarto dia e a preservação de objetos reutilizados ou de versões anteriores quando a gravação de um novo estado falha.
