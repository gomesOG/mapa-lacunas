"""Cria o schema do banco e carrega conceitos e itens dos arquivos JSON.

Uso: python scripts/criar_banco.py           (recarrega o conteúdo, mantém alunos e respostas)
     python scripts/criar_banco.py --zerar   (apaga o banco inteiro e recria)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, repositorio  # noqa: E402
from app.db import conectar, criar_schema  # noqa: E402
from app.motor.grafo import carregar_grafo  # noqa: E402


def validar(conceitos: list[dict], itens: list[dict]) -> None:
    """Recusa conteúdo inconsistente antes de gravar qualquer coisa."""
    grafo = carregar_grafo(conceitos)
    for item in itens:
        desconhecidos = set(item["conceitos"]) - set(grafo.conceitos)
        if desconhecidos:
            raise ValueError(f"Item {item['id']} usa conceitos inexistentes: {sorted(desconhecidos)}")
        if not 0 <= item["correta"] < len(item["opcoes"]):
            raise ValueError(f"Item {item['id']} tem 'correta' fora das opções")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zerar", action="store_true", help="apaga o banco inteiro antes de recriar")
    args = parser.parse_args()

    conceitos = json.loads(config.ARQUIVO_CONCEITOS.read_text(encoding="utf-8"))
    itens = json.loads(config.ARQUIVO_ITENS.read_text(encoding="utf-8"))
    validar(conceitos, itens)

    if args.zerar and config.CAMINHO_BANCO.exists():
        config.CAMINHO_BANCO.unlink()
        print(f"Banco anterior apagado: {config.CAMINHO_BANCO}")

    con = conectar(config.CAMINHO_BANCO)
    try:
        criar_schema(con)
        repositorio.substituir_conteudo(con, conceitos, itens)
        n_alunos = len(repositorio.listar_alunos(con))
    finally:
        con.close()

    print(f"Banco pronto em {config.CAMINHO_BANCO}")
    print(f"  {len(conceitos)} conceitos, {len(itens)} itens, {n_alunos} alunos já cadastrados")


if __name__ == "__main__":
    main()
