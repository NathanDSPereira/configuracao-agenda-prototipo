"""Leitor + validador do formulário preenchível (AcroForm) de Configuração de Agenda.

Fluxo (pensado para ser chamado pelo n8n, um PDF por chamada):
  1. lê os campos do PDF (sem OCR, sem IA);
  2. valida cabeçalho e cada item (regras por tipo);
  3. detecta duplicidade (dentro do PDF e contra o que já foi aceito);
  4. devolve JSON: status, itens com payload do ClickUp e a mensagem pronta para o solicitante.

Política: TUDO OU NADA. Se qualquer item tiver erro, nada é aceito nem registrado e o
solicitante recebe a lista do que corrigir. Assim um e-mail corresponde a uma solicitação clara.

As regras de negócio estão nas constantes abaixo e DEVEM ser confirmadas com a equipe.

Uso:
  python leitor_pdf.py arquivo.pdf --message-id <id> [--db registro.db] [--hoje AAAA-MM-DD]
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, time, timedelta, timezone

from pypdf import PdfReader

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover
    TZ = timezone(timedelta(hours=-3))

# ----------------------------- Regras (ajustar com a equipe) -----------------------------
MODELOS_ACEITOS = {"CASU", "IMAGINOLOGIA"}
TIPOS = ["Antecipação", "Bloqueio", "Ajuste de tempo de slot", "Alteração permanente"]
SLOT_MIN, SLOT_MAX = 5, 180          # minutos
DESCRICAO_MIN_CHARS = 15             # alteração permanente exige descrição minimamente útil
CABECALHO_OBRIGATORIO = {
    "solicitante": "Solicitante (Profissional)",
    "unidade": "Unidade",
    "data_hora_envio": "Data e hora da solicitação",
    "data_assinatura": "Data (assinatura)",
    "assinatura_nome": "Assinatura do solicitante",
}
CAMPOS_ITEM = ["tipo", "resumo", "data_regencia", "bloqueio_inicio", "bloqueio_fim",
               "reposicao", "data_reposicao", "novo_slot_min", "descricao_obs"]
# campos que fazem sentido para cada tipo (preencher outro gera apenas aviso)
RELEVANTES = {
    "Antecipação": {"tipo", "resumo", "data_regencia", "descricao_obs"},
    "Bloqueio": {"tipo", "resumo", "data_regencia", "bloqueio_inicio", "bloqueio_fim",
                 "reposicao", "data_reposicao", "descricao_obs"},
    "Ajuste de tempo de slot": {"tipo", "resumo", "data_regencia", "novo_slot_min", "descricao_obs"},
    "Alteração permanente": {"tipo", "resumo", "data_regencia", "descricao_obs"},
}
ROTULOS = {
    "tipo": "Tipo", "resumo": "Resumo", "data_regencia": "Data de regência",
    "bloqueio_inicio": "Bloqueio - início", "bloqueio_fim": "Bloqueio - fim",
    "reposicao": "Reposição", "data_reposicao": "Data de reposição",
    "novo_slot_min": "Novo tempo de slot (min)", "descricao_obs": "Descrição / Observações",
}
# -----------------------------------------------------------------------------------------


def _txt(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s == "/Off" else s


def _vazio(s):
    return s in ("", "Selecione")


def _data(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def ler_campos(caminho):
    """Retorna {campo: valor} ou None se o PDF não tiver campos de formulário."""
    campos = PdfReader(caminho).get_fields()
    if not campos:
        return None
    return {nome: _txt(f.get("/V")) for nome, f in campos.items()}


# ----------------------------------- Banco (SQLite no protótipo) ----------------------------
def abrir_banco(caminho):
    db = sqlite3.connect(caminho)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS submissoes (
            message_id TEXT PRIMARY KEY, hash_pdf TEXT, status TEXT,
            resultado_json TEXT, recebido_em TEXT);
        CREATE TABLE IF NOT EXISTS itens (
            chave_natural TEXT PRIMARY KEY, message_id TEXT, item_n INTEGER, tipo TEXT,
            solicitante TEXT, data_regencia TEXT, card_id TEXT, criado_em TEXT,
            conteudo_hash TEXT);
    """)
    return db


def confirmar_card(db, chave_natural, card_id):
    """Chamar depois que o n8n criar o card, para amarrar item <-> card."""
    db.execute("UPDATE itens SET card_id=? WHERE chave_natural=?", (card_id, chave_natural))
    db.commit()


# --------------------------------------- Validação ------------------------------------------
def _validar_item(i, v, ref):
    """v: dict com os campos do item já normalizados ('' para vazio). Retorna (erros, avisos)."""
    erros, avisos = [], []

    def err(campo, msg):
        erros.append({"item": i, "campo": campo, "mensagem": msg})

    tipo = v["tipo"]
    if not tipo:
        err("tipo", "Selecione o tipo da solicitação (a linha tem dados, mas o tipo está em branco).")
        return erros, avisos
    if tipo not in TIPOS:
        err("tipo", f"Tipo inválido: '{tipo}'.")
        return erros, avisos

    if not v["resumo"]:
        err("resumo", "Informe o resumo da solicitação.")

    dr = None
    if not v["data_regencia"]:
        err("data_regencia", "Informe a data de regência da alteração.")
    else:
        dr = _data(v["data_regencia"])
        if dr is None:
            err("data_regencia", f"Data inválida '{v['data_regencia']}' (use dd/mm/aaaa).")
        elif dr < ref:
            err("data_regencia", f"A data de regência ({v['data_regencia']}) é anterior à data da solicitação.")

    if tipo == "Bloqueio":
        bi = bf = None
        for campo in ("bloqueio_inicio", "bloqueio_fim"):
            if not v[campo]:
                err(campo, f"Informe {ROTULOS[campo].lower()}.")
            elif _data(v[campo]) is None:
                err(campo, f"Data inválida '{v[campo]}' (use dd/mm/aaaa).")
        bi, bf = _data(v["bloqueio_inicio"]), _data(v["bloqueio_fim"])
        if bi and bf and bf < bi:
            err("bloqueio_fim", "O fim do bloqueio não pode ser anterior ao início.")
        if _vazio(v["reposicao"]):
            err("reposicao", "Informe se haverá reposição (Sem reposição / Com reposição).")
        elif v["reposicao"] == "Com reposição":
            if not v["data_reposicao"]:
                err("data_reposicao", "Reposição marcada como 'Com reposição': informe a data de reposição.")
            else:
                dp = _data(v["data_reposicao"])
                if dp is None:
                    err("data_reposicao", f"Data inválida '{v['data_reposicao']}' (use dd/mm/aaaa).")
                elif bf and dp < bf:
                    err("data_reposicao", "A reposição não pode ser anterior ao fim do bloqueio.")
        elif v["reposicao"] == "Sem reposição" and v["data_reposicao"]:
            err("data_reposicao", "Há data de reposição preenchida, mas a opção é 'Sem reposição'.")

    elif tipo == "Ajuste de tempo de slot":
        s = v["novo_slot_min"]
        if not s:
            err("novo_slot_min", "Informe o novo tempo de slot, em minutos.")
        elif not s.isdigit() or not (SLOT_MIN <= int(s) <= SLOT_MAX):
            err("novo_slot_min", f"Tempo de slot inválido '{s}': informe minutos entre {SLOT_MIN} e {SLOT_MAX}.")

    elif tipo == "Alteração permanente":
        if len(v["descricao_obs"]) < DESCRICAO_MIN_CHARS:
            err("descricao_obs", "Descreva a alteração permanente (mínimo de "
                                 f"{DESCRICAO_MIN_CHARS} caracteres).")

    for campo in CAMPOS_ITEM:
        if campo not in RELEVANTES[tipo] and not _vazio(v[campo]):
            avisos.append({"item": i, "campo": campo,
                           "mensagem": f"'{ROTULOS[campo]}' não se aplica a '{tipo}' e será ignorado."})
    return erros, avisos


def _chave_natural(modelo, unidade, solicitante, v):
    partes = [modelo, unidade, solicitante, v["tipo"], v["data_regencia"], v["bloqueio_inicio"],
              v["bloqueio_fim"], v["novo_slot_min"]]
    if v["tipo"] == "Alteração permanente":
        partes.append(v["descricao_obs"])
    return hashlib.sha256("|".join(_norm(p) for p in partes).encode()).hexdigest()[:20]


def _conteudo_hash(v):
    """Hash de TODOS os campos do item: distingue 'mesmo pedido' de 'mesmo alvo com dados diferentes'."""
    return hashlib.sha256("|".join(_norm(v[k]) for k in CAMPOS_ITEM).encode()).hexdigest()[:20]


def _payload_clickup(modelo, solicitante, unidade, v, message_id):
    dr = _data(v["data_regencia"])
    due = int(datetime.combine(dr, time(23, 59), TZ).timestamp() * 1000) if dr else None
    linhas = [f"**Modelo:** {modelo}", f"**Solicitante:** {solicitante}", f"**Unidade:** {unidade}",
              f"**Tipo:** {v['tipo']}", f"**Resumo:** {v['resumo']}",
              f"**Data de regência:** {v['data_regencia']}"]
    if v["tipo"] == "Bloqueio":
        linhas += [f"**Bloqueio:** {v['bloqueio_inicio']} a {v['bloqueio_fim']}",
                   f"**Reposição:** {v['reposicao']}" + (f" ({v['data_reposicao']})" if v["data_reposicao"] else "")]
    if v["tipo"] == "Ajuste de tempo de slot":
        linhas.append(f"**Novo tempo de slot:** {v['novo_slot_min']} min")
    if v["descricao_obs"]:
        linhas.append(f"**Descrição/Observações:** {v['descricao_obs']}")
    linhas.append(f"\n_Origem: e-mail {message_id}_")
    return {
        "name": f"[{modelo}] {v['tipo']} - {solicitante} - {v['data_regencia']}",
        "markdown_description": "\n".join(linhas),
        "tags": [modelo.lower(), _norm(v["tipo"]).replace(" ", "-")],
        "due_date": due,
        "due_date_time": True,
        # custom fields do ClickUp exigem IDs do SEU workspace: mapear no n8n a partir de "campos".
    }


def _mensagem(status, erros, itens, avisos):
    if status == "SEM_CAMPOS":
        return ("Não foi possível ler o formulário anexado: o arquivo não é o modelo preenchível "
                "(provavelmente foi impresso/escaneado ou é o modelo antigo). Use o modelo atual, "
                "preencha no computador e reenvie sem imprimir. Nenhuma solicitação foi registrada.")
    if status == "MODELO_INVALIDO":
        return ("O modelo do formulário não foi reconhecido. Use o modelo oficial atual. "
                "Nenhuma solicitação foi registrada.")
    if status == "REJEITADO":
        por_item = {}
        for e in erros:
            por_item.setdefault(e["item"], []).append(e["mensagem"])
        txt = ["Sua solicitação NÃO foi registrada porque há informações pendentes. "
               "Corrija os pontos abaixo e reenvie o formulário:"]
        for k in sorted(por_item, key=lambda x: (x is not None, x or 0)):
            txt.append(("Cabeçalho" if k is None else f"Item {k}") + ":")
            txt += [f"  - {m}" for m in por_item[k]]
        return "\n".join(txt)
    dups = [it for it in itens if it["acao"] == "IGNORAR_DUPLICADO"]
    novos = [it for it in itens if it["acao"] == "CRIAR_CARD"]
    txt = [f"Recebido: {len(novos)} solicitação(ões) registrada(s)."]
    if dups:
        txt.append(f"{len(dups)} item(ns) já constavam como solicitados e foram ignorados: " +
                   ", ".join(f"item {d['n']}" for d in dups) + ".")
        div = [d["n"] for d in dups if d["duplicado_de"]["dados_divergentes"]]
        if div:
            txt.append("ATENÇÃO: nos itens " + ", ".join(map(str, div)) + " já existe uma solicitação para o "
                       "mesmo profissional, tipo e período, porém com dados diferentes (ex.: reposição ou "
                       "descrição). Para ALTERAR uma solicitação já registrada, fale com a equipe de agenda.")
    for a in avisos:
        txt.append(f"Aviso (item {a['item']}): {a['mensagem']}")
    return "\n".join(txt)


def processar(caminho_pdf, message_id, db, hoje=None):
    hoje = hoje or date.today()
    ja = db.execute("SELECT resultado_json FROM submissoes WHERE message_id=?", (message_id,)).fetchone()
    if ja:  # idempotência: mesma mensagem reprocessada devolve o mesmo resultado
        r = json.loads(ja[0])
        r["reprocessado"] = True
        return r

    hash_pdf = hashlib.sha256(open(caminho_pdf, "rb").read()).hexdigest()
    res = {"status": None, "message_id": message_id, "hash_pdf": hash_pdf, "modelo": None,
           "versao_modelo": None, "solicitante": None, "unidade": None,
           "itens": [], "erros": [], "avisos": [], "mensagem_para_solicitante": ""}

    def fechar(status):
        res["status"] = status
        res["mensagem_para_solicitante"] = _mensagem(status, res["erros"], res["itens"], res["avisos"])
        db.execute("INSERT INTO submissoes VALUES (?,?,?,?,?)",
                   (message_id, hash_pdf, status, json.dumps(res, ensure_ascii=False),
                    datetime.now(TZ).isoformat(timespec="seconds")))
        db.commit()
        return res

    c = ler_campos(caminho_pdf)
    if c is None:
        return fechar("SEM_CAMPOS")

    res["modelo"], res["versao_modelo"] = c.get("modelo", ""), c.get("versao_modelo", "")
    if res["modelo"] not in MODELOS_ACEITOS:
        return fechar("MODELO_INVALIDO")
    res["solicitante"], res["unidade"] = c.get("solicitante", ""), c.get("unidade", "")

    for campo, rotulo in CABECALHO_OBRIGATORIO.items():
        if not c.get(campo):
            res["erros"].append({"item": None, "campo": campo, "mensagem": f"Preencha '{rotulo}'."})
    if c.get("data_hora_envio"):
        try:
            datetime.strptime(c["data_hora_envio"], "%d/%m/%Y %H:%M")
        except ValueError:
            res["erros"].append({"item": None, "campo": "data_hora_envio",
                                 "mensagem": "Data e hora inválidas (use dd/mm/aaaa hh:mm)."})

    ns = sorted(int(m.group(1)) for k in c if (m := re.fullmatch(r"tipo_(\d+)", k)))
    vistos = {}  # chave -> item_n (duplicidade dentro do próprio PDF)
    for i in ns:
        v = {k: ("" if c.get(f"{k}_{i}", "") == "Selecione" else c.get(f"{k}_{i}", "")) for k in CAMPOS_ITEM}
        if all(_vazio(x) for x in v.values()):
            continue  # linha em branco
        erros, avisos = _validar_item(i, v, hoje)
        res["erros"] += erros
        res["avisos"] += avisos
        item = {"n": i, "tipo": v["tipo"], "campos": v, "chave_natural": None,
                "acao": None, "duplicado_de": None, "avisos": avisos}
        if not erros:
            item["chave_natural"] = _chave_natural(res["modelo"], res["unidade"], res["solicitante"], v)
            if item["chave_natural"] in vistos:
                res["erros"].append({"item": i, "campo": "tipo", "mensagem":
                                     f"Este item repete o item {vistos[item['chave_natural']]} deste mesmo formulário."})
            vistos.setdefault(item["chave_natural"], i)
        res["itens"].append(item)

    if not res["itens"]:
        res["erros"].append({"item": None, "campo": "itens", "mensagem": "Nenhuma solicitação foi preenchida."})

    if res["erros"]:
        for it in res["itens"]:
            it["acao"] = "NAO_REGISTRADO"
        return fechar("REJEITADO")

    # sem erros: checa duplicidade contra o que já foi aceito e registra os novos
    novos = 0
    for it in res["itens"]:
        ex = db.execute("SELECT message_id, item_n, card_id, conteudo_hash FROM itens WHERE chave_natural=?",
                        (it["chave_natural"],)).fetchone()
        ch = _conteudo_hash(it["campos"])
        if ex:
            it["acao"] = "IGNORAR_DUPLICADO"
            it["duplicado_de"] = {"message_id": ex[0], "item_n": ex[1], "card_id": ex[2],
                                  "dados_divergentes": ex[3] != ch}
        else:
            it["acao"] = "CRIAR_CARD"
            it["clickup"] = _payload_clickup(res["modelo"], res["solicitante"], res["unidade"],
                                             it["campos"], message_id)
            db.execute("INSERT INTO itens (chave_natural,message_id,item_n,tipo,solicitante,data_regencia,"
                       "criado_em,conteudo_hash) VALUES (?,?,?,?,?,?,?,?)",
                       (it["chave_natural"], message_id, it["n"], it["tipo"], res["solicitante"],
                        it["campos"]["data_regencia"], datetime.now(TZ).isoformat(timespec="seconds"), ch))
            novos += 1
    return fechar("OK" if novos else "DUPLICADO")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--message-id", required=True, help="Message-ID do e-mail (chave de idempotência)")
    ap.add_argument("--db", default="registro.db")
    ap.add_argument("--hoje", help="AAAA-MM-DD (padrão: hoje)")
    a = ap.parse_args()
    hoje = date.fromisoformat(a.hoje) if a.hoje else None
    print(json.dumps(processar(a.pdf, a.message_id, abrir_banco(a.db), hoje), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
