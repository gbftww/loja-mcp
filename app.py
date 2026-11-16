"""Servidor MCP da loja — dá aos agentes de IA acesso à API da loja.

O MCP não guarda dados: cada tool chama a API (back/) por HTTP. Assim o site
e o agente enxergam o MESMO estoque.

Rode com:
    uv sync
    LOJA_API_URL=https://sua-api.onrender.com uv run python app.py

Sobe em http://127.0.0.1:8000/mcp  (sem LOJA_API_URL usa http://127.0.0.1:5000).
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.mcpserver import MCPServer

API_URL = os.environ.get("LOJA_API_URL", "http://127.0.0.1:5000").rstrip("/")

mcp = MCPServer("loja-mcp")


def chamar_api(caminho: str, metodo: str = "GET", corpo: dict | None = None):
    """Chama a API da loja. Erros da API (404, 409...) voltam como {'erro': ...}
    para o agente poder explicar o motivo ao usuário, em vez de quebrar a tool."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        API_URL + caminho, data=dados, method=metodo,
        headers={"Content-Type": "application/json"},
    )
    try:
        # timeout longo: no plano Free do Render a API pode levar ~1 min para acordar
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"erro": f"A API respondeu com erro {e.code}."}
    except (urllib.error.URLError, TimeoutError):
        return {"erro": f"Não consegui acessar a API da loja em {API_URL}."}


@mcp.tool()
def buscar_produtos(termo: str | None = None, preco_max: float | None = None) -> list[dict] | dict:
    """Busca produtos da loja pelo nome e, se informado, limita pelo preço máximo.
    Se termo não for informado, retorna todos os produtos.
    Cada produto traz id, nome, preco, estoque (0 = esgotado) e descricao."""
    print(f"[buscar_produtos] termo={termo!r} preco_max={preco_max}", flush=True)
    caminho = "/produtos"
    if termo:
        caminho += "?" + urllib.parse.urlencode({"q": termo.strip()})
    produtos = chamar_api(caminho)
    if isinstance(produtos, dict):  # erro
        return produtos
    if preco_max is not None:
        produtos = [p for p in produtos if p["preco"] <= preco_max]
    return produtos


@mcp.tool()
def detalhar_produto(produto_id: str) -> dict:
    """Mostra o detalhe de um produto a partir do seu id (ex.: 'fone-a')."""
    print(f"[detalhar_produto] produto_id={produto_id!r}", flush=True)
    return chamar_api("/produtos/" + urllib.parse.quote(produto_id))


@mcp.tool()
def comprar(itens: list[dict], nome: str, email: str) -> dict:
    """Finaliza uma compra na loja: baixa o estoque e devolve o número do pedido.
    itens é uma lista de {"id": "fone-a", "quantidade": 2}.
    Produto esgotado ou quantidade acima do estoque é recusado (retorna 'erro').
    Confirme com o usuário o que vai comprar, o nome e o e-mail antes de chamar."""
    print(f"[comprar] itens={itens} nome={nome!r}", flush=True)
    return chamar_api("/pedidos", "POST", {"cliente": {"nome": nome, "email": email}, "itens": itens})


@mcp.tool()
def resetar_estoques() -> dict:
    """Volta os estoques de todos os produtos ao valor inicial (uso em demonstrações)."""
    print("[resetar_estoques]", flush=True)
    return chamar_api("/resetar", "POST")


if __name__ == "__main__":
    # No Render a porta vem na variável PORT; localmente fica 127.0.0.1:8000.
    porta = os.environ.get("PORT")
    if porta:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(porta))
    else:
        mcp.run(transport="streamable-http")
