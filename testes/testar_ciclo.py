"""Teste de ponta a ponta: preenche o modelo, lê de volta e confere validação e duplicidade."""
import os
import sys
import tempfile
from datetime import date

from pypdf import PdfReader, PdfWriter

import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "leitor-pdf"))
import leitor_pdf as L

MODELO = os.path.join(RAIZ, "leitor-pdf", "modelos", "modelo_CASU_preenchivel.pdf")
LEGADO = "/mnt/user-data/uploads/01_CASU_bloqueio_completo.pdf"
HOJE = date(2026, 10, 14)
tmp = tempfile.mkdtemp()

CAB = {"solicitante": "Dra. Camila Torres (fictícia)", "unidade": "Unidade Centro",
       "data_hora_envio": "14/10/2026 09:15", "data_assinatura": "14/10/2026",
       "assinatura_nome": "Camila Torres"}


def preencher(nome, valores):
    w = PdfWriter(clone_from=PdfReader(MODELO))
    w.update_page_form_field_values(w.pages[0], valores, auto_regenerate=False)
    w.set_need_appearances_writer(True)
    caminho = os.path.join(tmp, nome)
    with open(caminho, "wb") as f:
        w.write(f)
    return caminho


def item(n, **kw):
    return {f"{k}_{n}": v for k, v in kw.items()}


bloqueio = item(1, tipo="Bloqueio", resumo="Congresso", data_regencia="20/10/2026",
                bloqueio_inicio="20/10/2026", bloqueio_fim="22/10/2026", reposicao="Sem reposição")
slot = item(2, tipo="Ajuste de tempo de slot", resumo="Slot menor", data_regencia="03/11/2026", novo_slot_min="20")
perm = item(3, tipo="Alteração permanente", resumo="Novo dia fixo", data_regencia="01/12/2026",
            descricao_obs="Passa a atender apenas às terças e quintas, no período da tarde.")

falhas = []


def conferir(nome, cond, extra=""):
    print(("  OK   " if cond else "  FALHA ") + nome + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        falhas.append(nome)


db = L.abrir_banco(os.path.join(tmp, "teste.db"))

print("1) Formulário válido com 3 itens e 2 linhas em branco")
r1 = L.processar(preencher("ok.pdf", {**CAB, **bloqueio, **slot, **perm}), "msg-001", db, HOJE)
conferir("status OK", r1["status"] == "OK", r1["status"])
conferir("3 itens = 3 cards a criar", [i["acao"] for i in r1["itens"]] == ["CRIAR_CARD"] * 3)
conferir("linhas em branco ignoradas", len(r1["itens"]) == 3)
conferir("payload ClickUp com data de entrega", all(i["clickup"]["due_date"] for i in r1["itens"]))
conferir("nome do card", r1["itens"][0]["clickup"]["name"] == "[CASU] Bloqueio - Dra. Camila Torres (fictícia) - 20/10/2026",
         r1["itens"][0]["clickup"]["name"])

print("2) Reenvio do MESMO e-mail (mesmo Message-ID) -> idempotente")
r2 = L.processar(preencher("ok.pdf", {**CAB, **bloqueio, **slot, **perm}), "msg-001", db, HOJE)
conferir("devolve o resultado guardado", r2.get("reprocessado") and r2["status"] == "OK")

print("3) Outro e-mail com os mesmos itens -> duplicidade")
r3 = L.processar(preencher("ok2.pdf", {**CAB, **bloqueio, **slot, **perm}), "msg-002", db, HOJE)
conferir("status DUPLICADO", r3["status"] == "DUPLICADO", r3["status"])
conferir("nenhum card novo", all(i["acao"] == "IGNORAR_DUPLICADO" for i in r3["itens"]))
L.confirmar_card(db, r1["itens"][0]["chave_natural"], "CU-123")
r3b = L.processar(preencher("ok3.pdf", {**CAB, **bloqueio}), "msg-003", db, HOJE)
conferir("aponta o card existente", r3b["itens"][0]["duplicado_de"]["card_id"] == "CU-123", str(r3b["itens"][0]["duplicado_de"]))

print("4) Duplicata parcial: 1 item novo + 1 repetido")
novo = item(2, tipo="Antecipação", resumo="Antecipar agenda", data_regencia="05/11/2026")
r4 = L.processar(preencher("p.pdf", {**CAB, **bloqueio, **novo}), "msg-004", db, HOJE)
conferir("status OK com 1 novo e 1 ignorado",
         r4["status"] == "OK" and sorted(i["acao"] for i in r4["itens"]) == ["CRIAR_CARD", "IGNORAR_DUPLICADO"],
         str([(i["n"], i["acao"]) for i in r4["itens"]]))

print("5) Formulário incompleto -> barrado, nada registrado")
ruim = {**CAB,
        **item(1, tipo="Bloqueio", resumo="Curso", data_regencia="10/11/2026", bloqueio_inicio="10/11/2026",
               reposicao="Sem reposição"),                       # falta fim do bloqueio
        **item(2, tipo="Ajuste de tempo de slot", resumo="Slot", data_regencia="03/11/2026"),  # falta minutos
        **item(3, resumo="Linha sem tipo", data_regencia="10/11/2026"),                          # falta tipo
        **item(4, tipo="Alteração permanente", resumo="x", data_regencia="01/12/2026", descricao_obs="curta")}
r5 = L.processar(preencher("ruim.pdf", ruim), "msg-005", db, HOJE)
campos_erro = sorted((e["item"], e["campo"]) for e in r5["erros"])
conferir("status REJEITADO", r5["status"] == "REJEITADO")
conferir("4 erros esperados", campos_erro == [(1, "bloqueio_fim"), (2, "novo_slot_min"), (3, "tipo"), (4, "descricao_obs")], str(campos_erro))
conferir("nada registrado no banco", db.execute("SELECT COUNT(*) FROM itens WHERE message_id='msg-005'").fetchone()[0] == 0)
print("\n   Mensagem que o solicitante receberia:\n   " + r5["mensagem_para_solicitante"].replace("\n", "\n   ") + "\n")

print("6) Após corrigir e reenviar (novo Message-ID), é aceito (rejeitado não conta como duplicado)")
certo = {**CAB,
         **item(1, tipo="Bloqueio", resumo="Curso", data_regencia="10/11/2026", bloqueio_inicio="10/11/2026",
                bloqueio_fim="12/11/2026", reposicao="Com reposição", data_reposicao="30/11/2026")}
r6 = L.processar(preencher("certo.pdf", certo), "msg-006", db, HOJE)
conferir("status OK e card a criar", r6["status"] == "OK" and r6["itens"][0]["acao"] == "CRIAR_CARD", str(r6["erros"]))

print("6b) Mesmo bloqueio já aceito (msg-001), mas agora COM reposição -> duplicado com dados divergentes")
diverg = {**CAB, **item(1, tipo="Bloqueio", resumo="Congresso", data_regencia="20/10/2026", bloqueio_inicio="20/10/2026",
                        bloqueio_fim="22/10/2026", reposicao="Com reposição", data_reposicao="30/10/2026")}
r6b = L.processar(preencher("diverg.pdf", diverg), "msg-006b", db, HOJE)
conferir("status DUPLICADO", r6b["status"] == "DUPLICADO", r6b["status"])
conferir("marcado como divergente", r6b["itens"][0]["duplicado_de"]["dados_divergentes"] is True)
conferir("mensagem orienta falar com a equipe", "fale com a equipe" in r6b["mensagem_para_solicitante"])
conferir("duplicata idêntica NÃO é divergente", r3b["itens"][0]["duplicado_de"]["dados_divergentes"] is False)

print("7) Regras de datas e reposição")
r7 = L.processar(preencher("datas.pdf", {**CAB,
        **item(1, tipo="Bloqueio", resumo="a", data_regencia="01/09/2026", bloqueio_inicio="25/10/2026",
               bloqueio_fim="24/10/2026", reposicao="Com reposição"),
        **item(2, tipo="Bloqueio", resumo="b", data_regencia="31/02/2026", bloqueio_inicio="20/10/2026",
               bloqueio_fim="21/10/2026", reposicao="Sem reposição", data_reposicao="22/10/2026")}), "msg-007", db, HOJE)
msgs = " | ".join(e["mensagem"] for e in r7["erros"])
conferir("data de regência no passado", "anterior à data da solicitação" in msgs)
conferir("fim antes do início", "não pode ser anterior ao início" in msgs)
conferir("'Com reposição' sem data", "informe a data de reposição" in msgs)
conferir("data inexistente (31/02)", "Data inválida '31/02/2026'" in msgs)
conferir("'Sem reposição' com data", "opção é 'Sem reposição'" in msgs)

print("8) Duplicado dentro do mesmo PDF")
r8 = L.processar(preencher("dup.pdf", {**CAB, **item(1, **{k.rsplit('_', 1)[0]: v for k, v in novo.items()}),
                                        **item(2, **{k.rsplit('_', 1)[0]: v for k, v in novo.items()})}), "msg-008", db, HOJE)
conferir("REJEITADO por repetição", r8["status"] == "REJEITADO" and any("repete o item" in e["mensagem"] for e in r8["erros"]),
         str(r8["erros"]))

print("9) Formulário sem tipo nem dados e cabeçalho vazio")
r9 = L.processar(preencher("vazio.pdf", {}), "msg-009", db, HOJE)
conferir("REJEITADO com cabeçalho e 'nenhuma solicitação'",
         r9["status"] == "REJEITADO" and any(e["campo"] == "itens" for e in r9["erros"]) and any(e["campo"] == "solicitante" for e in r9["erros"]))

print("10) PDF achatado/legado (sem campos)")
r10 = L.processar(LEGADO, "msg-010", db, HOJE)
conferir("status SEM_CAMPOS", r10["status"] == "SEM_CAMPOS", r10["status"])

print("11) Aviso para campo que não se aplica ao tipo")
r11 = L.processar(preencher("aviso.pdf", {**CAB, **item(1, tipo="Antecipação", resumo="Antecipar", data_regencia="06/11/2026",
                                                         novo_slot_min="30")}), "msg-011", db, HOJE)
conferir("aceito com aviso", r11["status"] == "OK" and len(r11["avisos"]) == 1, str(r11["avisos"]))

print()
print("RESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S): {falhas}")
sys.exit(1 if falhas else 0)
