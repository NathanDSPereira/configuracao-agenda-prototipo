"""Gera o formulário 'Configuração de Agenda - CASU' como PDF preenchível (AcroForm).

Regras de desenho:
- Uma solicitação por linha; cada linha tem UM tipo (lista suspensa).
- Nomes de campo estáveis: tipo_1..tipo_N, resumo_1..resumo_N etc. O leitor depende deles.
- Sem JavaScript: a validação real acontece no recebimento (leitor).

Uso: python gerar_formulario.py [saida.pdf] [N_itens]
"""
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "formulario_CASU_preenchivel.pdf"
N_ITENS = int(sys.argv[2]) if len(sys.argv) > 2 else 5

MODELO = "CASU"
VERSAO = "v1"

TIPOS = ["Selecione", "Antecipação", "Bloqueio", "Ajuste de tempo de slot", "Alteração permanente"]
REPOSICAO = ["Selecione", "Sem reposição", "Com reposição"]

W, H = landscape(A4)
M = 30  # margem
CINZA = colors.Color(0.93, 0.93, 0.93)
BORDA = colors.Color(0.55, 0.55, 0.55)
CAMPO = colors.Color(1, 1, 0.92)

c = canvas.Canvas(SAIDA, pagesize=(W, H))
c.setTitle("Configuração de Agenda - CASU (modelo preenchível)")
form = c.acroForm


def texto(x, y, s, size=8, bold=False, cor=colors.black):
    c.setFillColor(cor)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, s)


def caixa(x, y, w, h, fill=None):
    c.setStrokeColor(BORDA)
    c.setLineWidth(0.6)
    if fill is not None:
        c.setFillColor(fill)
        c.rect(x, y, w, h, stroke=1, fill=1)
    else:
        c.rect(x, y, w, h, stroke=1, fill=0)


def campo_texto(nome, x, y, w, h, dica, valor="", size=8, multi=False, somente_leitura=False):
    flags = []
    if multi:
        flags.append("multiline")
    if somente_leitura:
        flags.append("readOnly")
    form.textfield(
        name=nome, tooltip=dica, value=valor, x=x, y=y, width=w, height=h,
        borderStyle="solid", borderColor=BORDA, fillColor=CAMPO, textColor=colors.black,
        forceBorder=True, fontSize=size, fieldFlags=" ".join(flags),
    )


def campo_lista(nome, x, y, w, h, dica, opcoes, size=7):
    form.choice(
        name=nome, tooltip=dica, value=opcoes[0], options=opcoes, x=x, y=y, width=w, height=h,
        borderStyle="solid", borderColor=BORDA, fillColor=CAMPO, textColor=colors.black,
        forceBorder=True, fontSize=size, fieldFlags="combo",
    )


# ---------- Cabeçalho ----------
y_top = H - M
alt_cab = 46
caixa(M, y_top - alt_cab, 110, alt_cab)
texto(M + 40, y_top - 27, "LOGO", 10, True)
caixa(M + 110, y_top - alt_cab, W - 2 * M - 110 - 190, alt_cab)
texto(M + 120, y_top - 17, "FORMULÁRIO", 8, True)
texto(M + 120, y_top - 36, f"Configuração de Agenda - {MODELO}", 13, True)
caixa(W - M - 190, y_top - alt_cab, 190, alt_cab)
texto(W - M - 184, y_top - 14, "Código:", 7)
campo_texto("codigo", W - M - 150, y_top - 18, 140, 12, "Código do documento (preenchido pela equipe)", size=7)
texto(W - M - 184, y_top - 28, "Revisão:", 7)
campo_texto("revisao", W - M - 150, y_top - 32, 140, 12, "Revisão do documento (preenchida pela equipe)", size=7)
texto(W - M - 184, y_top - 42, "Modelo / versão:", 7)
campo_texto("modelo", W - M - 110, y_top - 45, 50, 11, "Identifica o modelo (não alterar)", MODELO, 7, somente_leitura=True)
campo_texto("versao_modelo", W - M - 56, y_top - 45, 46, 11, "Versão do modelo (não alterar)", VERSAO, 7, somente_leitura=True)

# ---------- 1. Dados do envio ----------
y = y_top - alt_cab - 18
caixa(M, y - 2, W - 2 * M, 16, CINZA)
texto(M + 6, y + 3, "1. DADOS DO ENVIO", 9, True)

y -= 38
texto(M, y + 16, "Solicitante (Profissional)", 7, True)
campo_texto("solicitante", M, y, 300, 14, "Nome completo do profissional solicitante")
texto(M + 312, y + 16, "Unidade", 7, True)
campo_texto("unidade", M + 312, y, 200, 14, "Unidade de atendimento")
texto(M + 524, y + 16, "Data e hora da solicitação", 7, True)
campo_texto("data_hora_envio", M + 524, y, 226, 14, "dd/mm/aaaa hh:mm")

# ---------- 2. Solicitações ----------
y -= 22
caixa(M, y - 2, W - 2 * M, 16, CINZA)
texto(M + 6, y + 3, "2. SOLICITAÇÕES  (uma por linha, um único tipo por linha)", 9, True)

colunas = [
    ("n", "Nº", 18),
    ("tipo", "Tipo", 100),
    ("resumo", "Resumo", 120),
    ("data_regencia", "Data de regência\nda alteração", 62),
    ("bloqueio_inicio", "Bloqueio\nInício", 62),
    ("bloqueio_fim", "Bloqueio\nFim", 62),
    ("reposicao", "Reposição", 72),
    ("data_reposicao", "Data de\nreposição", 62),
    ("novo_slot_min", "Novo tempo\nslot (min)", 44),
    ("descricao_obs", "Descrição (obrig. em alteração\npermanente) / Observações", 176),
]
dicas = {
    "tipo": "Escolha UM tipo por linha",
    "resumo": "Resumo curto da solicitação",
    "data_regencia": "dd/mm/aaaa",
    "bloqueio_inicio": "dd/mm/aaaa (apenas para Bloqueio)",
    "bloqueio_fim": "dd/mm/aaaa (apenas para Bloqueio)",
    "reposicao": "Apenas para Bloqueio",
    "data_reposicao": "dd/mm/aaaa (se houver reposição)",
    "novo_slot_min": "Minutos (apenas para Ajuste de tempo de slot)",
    "descricao_obs": "Descreva a alteração permanente ou observações",
}

alt_cab_tab = 28
alt_linha = 40
y_tab = y - 4 - alt_cab_tab

# cabeçalho da tabela
x = M
for chave, rotulo, larg in colunas:
    caixa(x, y_tab, larg, alt_cab_tab, CINZA)
    linhas = rotulo.split("\n")
    ty = y_tab + alt_cab_tab - 11 if len(linhas) > 1 else y_tab + alt_cab_tab / 2 - 3
    for ln in linhas:
        texto(x + 3, ty, ln, 6.3, True)
        ty -= 8
    x += larg

# linhas
for i in range(1, N_ITENS + 1):
    yy = y_tab - i * alt_linha
    x = M
    for chave, rotulo, larg in colunas:
        caixa(x, yy, larg, alt_linha)
        nome = f"{chave}_{i}"
        pad = 2
        if chave == "n":
            texto(x + 6, yy + alt_linha / 2 - 3, str(i), 9, True)
        elif chave == "tipo":
            campo_lista(nome, x + pad, yy + alt_linha / 2 - 7, larg - 2 * pad, 14, dicas[chave], TIPOS)
        elif chave == "reposicao":
            campo_lista(nome, x + pad, yy + alt_linha / 2 - 7, larg - 2 * pad, 14, dicas[chave], REPOSICAO)
        elif chave == "descricao_obs":
            campo_texto(nome, x + pad, yy + pad, larg - 2 * pad, alt_linha - 2 * pad, dicas[chave], size=7, multi=True)
        elif chave == "resumo":
            campo_texto(nome, x + pad, yy + pad, larg - 2 * pad, alt_linha - 2 * pad, dicas[chave], size=7, multi=True)
        else:
            campo_texto(nome, x + pad, yy + alt_linha / 2 - 7, larg - 2 * pad, 14, dicas[chave], size=7)
        x += larg

# ---------- Aceite ----------
y_ac = y_tab - N_ITENS * alt_linha - 38
texto(M, y_ac + 22, "Data", 7, True)
campo_texto("data_assinatura", M, y_ac, 110, 14, "dd/mm/aaaa")
texto(M + 124, y_ac + 22, "Assinatura do solicitante (nome completo)  /  espaço para assinatura digital", 7, True)
campo_texto("assinatura_nome", M + 124, y_ac, 380, 14, "Digite o nome completo como aceite; assine digitalmente depois, se exigido")

# ---------- Rodapé LGPD ----------
c.setFillColor(colors.Color(0.3, 0.3, 0.3))
c.setFont("Helvetica", 6.3)
c.drawString(
    M, 20,
    "Este documento é classificado conforme Lei nº 13.709, de 14 de agosto de 2018, que dispõe sobre a proteção de dados "
    "pessoais e altera a Lei nº 12.965, de 23 de abril de 2014 (Marco Civil).",
)

c.showPage()
c.save()
print(f"Gerado: {SAIDA}  ({N_ITENS} itens)")
