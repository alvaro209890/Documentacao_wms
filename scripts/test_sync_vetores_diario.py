import pytest
import sync_vetores_diario as sync


def registro(dia, chave):
    return {"dia": f"2026-11-{dia:02}", "objeto": chave * 64, "origem": "origem"}


def test_quarto_dia_remove_so_arquivo_sem_referencia(tmp_path):
    anteriores = [registro(1, "a"), registro(2, "b"), registro(3, "b")]
    for letra in "abc":
        (tmp_path / (letra * 64)).mkdir()
    assert sync.reter(tmp_path, anteriores, registro(4, "c")) == anteriores[1:] + [registro(4, "c")]
    assert not (tmp_path / ("a" * 64)).exists()
    assert (tmp_path / ("b" * 64)).exists()


def test_falha_de_gravacao_preserva_historico(monkeypatch, tmp_path):
    antigas = [registro(1, "a"), registro(2, "b"), registro(3, "c")]
    for letra in "abcd":
        (tmp_path / (letra * 64)).mkdir()

    def falhar(*_):
        raise OSError("sem espaço")

    monkeypatch.setattr(sync, "gravar", falhar)
    with pytest.raises(OSError):
        sync.reter(tmp_path, antigas, registro(4, "d"))
    assert (tmp_path / ("a" * 64)).is_dir()


def test_checksum_ignora_apenas_data_do_dbf(tmp_path):
    p = tmp_path / "camada.dbf"
    p.write_bytes(b"a123registros")
    antes = sync.identidade([p])
    p.write_bytes(b"a456registros")
    assert sync.identidade([p]) == antes
    p.write_bytes(b"a456REGISTROS")
    assert sync.identidade([p]) != antes
