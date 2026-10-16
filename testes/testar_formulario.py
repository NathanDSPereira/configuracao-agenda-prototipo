"""Teste de ponta a ponta do formulário v2 (CASU + Imaginamente, prioridade, PDF, Gmail simulado)."""
import base64, email, json, os, re, sys
from datetime import date, timedelta
from email import policy
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDFLIB = os.environ.get("PDFLIB_JS", os.path.join(RAIZ, "node_modules/pdf-lib/dist/pdf-lib.min.js"))
URL = "file://" + os.path.join(RAIZ, "formulario-web", "index.html")
OUT = os.path.join(RAIZ, "testes", "saida")
os.makedirs(OUT, exist_ok=True)
falhas, erros_js = [], []


def ok(nome, cond, extra=""):
    print(("  OK    " if cond else "  FALHA ") + nome + ((" [" + str(extra)[:300] + "]") if (extra and not cond) else ""))
    if not cond:
        falhas.append(nome)


def d(n):
    return (date.today() + timedelta(days=n)).isoformat()


def nova_pagina(ctx, init=None):
    pg = ctx.new_page()
    pg.on("console", lambda m: erros_js.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text and "http_403" not in m.text else None)
    pg.on("pageerror", lambda e: erros_js.append(str(e)))
    pg.route("**/pdf-lib.min.js", lambda r: r.fulfill(path=PDFLIB, content_type="application/javascript"))
    pg.route(re.compile(r"fonts\.(googleapis|gstatic)\.com"), lambda r: r.abort())
    pg.route("**/gsi/client", lambda r: r.fulfill(body="", content_type="application/javascript"))
    if init:
        pg.add_init_script(init)
    pg.goto(URL)
    return pg


def texto_pdf(caminho):
    r = PdfReader(caminho)
    return len(r.pages), "\n".join((p.extract_text() or "") for p in r.pages)


def ids(pg):
    return pg.evaluate("[...document.querySelectorAll('#itens .item')].map(a=>a.dataset.id)")


def escolher(pg, iid, campo, valor):
    pg.check(f'input[name="n-{iid}-{campo}"][value="{valor}"]', force=True)


def opcoes(pg, iid, campo):
    return pg.eval_on_selector_all(f'input[name="n-{iid}-{campo}"]', "els => els.map(e => e.value)")


def campos(pg, iid):
    return pg.evaluate("""(iid) => [...document.querySelectorAll('[data-item="'+iid+'"]')]
        .map(e => e.dataset.campo).filter((c, i, a) => a.indexOf(c) === i)""", iid)


def rotulo(pg, iid, campo):
    return pg.evaluate("""([iid, c]) => { const el = document.getElementById('f-'+iid+'-'+c); if (!el) return null;
        const w = el.closest('.campo'); return w.querySelector('label').textContent.trim(); }""", [iid, campo])


def cab(pg, nome="Dra. Camila Torres (fictícia)", resumo="Resumo de teste"):
    pg.fill("#h-solicitante", nome)
    pg.fill("#h-unidade", "Unidade Centro (exemplo)")
    pg.fill("#h-email", "camila.torres@instituicao.example")
    pg.fill("#h-resumo", resumo)


def comuns(pg, iid, prio, n):
    escolher(pg, iid, "prioridade", prio)
    pg.fill(f"#f-{iid}-descricao", "Descrição do pedido para teste automatizado.")
    pg.fill(f"#f-{iid}-data_regencia", d(n))


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1100, "height": 900}, accept_downloads=True)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = nova_pagina(ctx)

    print("A) Formulário vazio não pode ser finalizado")
    ok("contador mostra pendências", "pendência" in pg.inner_text("#contador"), pg.inner_text("#contador"))
    pg.click("#btn-gerar")
    r = pg.inner_text("#resumo-erros")
    ok("resumo visível", pg.is_visible("#resumo-erros"))
    for t in ["Selecione o tipo da solicitação", "Selecione a prioridade", "nome completo", "unidade de atendimento", "e-mail válido", "resumo da solicitação", "Marque o aceite"]:
        ok("lista '" + t + "'", t in r, r)
    ok("resultado NÃO foi gerado", not pg.is_visible("#resultado"))
    pg.screenshot(path=OUT + "/01_vazio_erros.png", full_page=True)

    print("B) Campos por modelo e por tipo")
    i1 = ids(pg)[0]
    ok("CASU: tipos oficiais", opcoes(pg, i1, "tipo") == ["Antecipação", "Bloqueio", "Ajustes tempo slot", "Alterações permanentes"], opcoes(pg, i1, "tipo"))
    ok("prioridade: 4 níveis", opcoes(pg, i1, "prioridade") == ["Urgente", "Alta", "Normal", "Baixa"], opcoes(pg, i1, "prioridade"))
    ok("sem tipo: só tipo e prioridade", set(campos(pg, i1)) == {"tipo", "prioridade"}, campos(pg, i1))
    escolher(pg, i1, "tipo", "Antecipação")
    ok("Antecipação: só campos comuns", set(campos(pg, i1)) == {"tipo", "prioridade", "descricao", "data_regencia", "observacoes"}, campos(pg, i1))
    escolher(pg, i1, "tipo", "Bloqueio")
    c = set(campos(pg, i1))
    ok("Bloqueio: início, fim e reposição, sem data de reposição", {"bloqueio_inicio", "bloqueio_fim", "reposicao"} <= c and "data_reposicao" not in c, c)
    escolher(pg, i1, "reposicao", "Com reposição")
    ok("'Com reposição' mostra a data", "data_reposicao" in campos(pg, i1))
    escolher(pg, i1, "reposicao", "Sem reposição")
    ok("'Sem reposição' esconde a data", "data_reposicao" not in campos(pg, i1))
    escolher(pg, i1, "tipo", "Ajustes tempo slot")
    ok("Ajustes tempo slot: minutos", "novo_slot_min" in campos(pg, i1) and "bloqueio_inicio" not in campos(pg, i1))
    escolher(pg, i1, "tipo", "Alterações permanentes")
    ok("Alterações permanentes: descrição específica", rotulo(pg, i1, "detalhe").startswith("Descreva a alteração permanente"), rotulo(pg, i1, "detalhe"))

    pg.check('input[name="modelo"][value="IMAGINAMENTE"]', force=True)
    i1 = ids(pg)[0]
    ok("Imaginamente: tipos oficiais", opcoes(pg, i1, "tipo") == ["Trocas", "Ajustes", "Bloqueio", "Alterações permanentes"], opcoes(pg, i1, "tipo"))
    escolher(pg, i1, "tipo", "Trocas")
    ok("Trocas: paciente e horários", {"paciente", "horario_anterior", "horario_atual"} <= set(campos(pg, i1)))
    ok("Trocas: paciente obrigatório", "(opcional)" not in rotulo(pg, i1, "paciente"), rotulo(pg, i1, "paciente"))
    escolher(pg, i1, "tipo", "Ajustes")
    ok("Ajustes: paciente opcional", "(opcional)" in rotulo(pg, i1, "paciente"), rotulo(pg, i1, "paciente"))
    escolher(pg, i1, "tipo", "Bloqueio")
    ok("Bloqueio (Imaginamente): descrição específica e sem datas", rotulo(pg, i1, "detalhe").startswith("Descreva o bloqueio ou a alteração permanente") and "bloqueio_inicio" not in campos(pg, i1))
    escolher(pg, i1, "tipo", "Trocas")
    pg.check('input[name="modelo"][value="CASU"]', force=True)
    ok("trocar de modelo limpa tipo inexistente", pg.evaluate("document.querySelectorAll('#itens input[name$=\"-tipo\"]:checked').length") == 0)
    pg.check('input[name="modelo"][value="IMAGINAMENTE"]', force=True)

    print("C) Regras de validação (Imaginamente)")
    cab(pg, resumo="Trocas e bloqueios da semana")
    i1 = ids(pg)[0]
    escolher(pg, i1, "tipo", "Trocas")
    comuns(pg, i1, "Urgente", 3)
    pg.fill(f"#f-{i1}-data_regencia", d(-1)); pg.press(f"#f-{i1}-data_regencia", "Tab")
    ok("data no passado barrada", "anterior a hoje" in pg.inner_text(f"#e-f-{i1}-data_regencia"))
    pg.fill(f"#f-{i1}-data_regencia", d(3))
    pg.fill(f"#f-{i1}-paciente", "Paciente Exemplo (fictício) - carteirinha 000000")
    pg.fill(f"#f-{i1}-horario_anterior", "14:30"); pg.fill(f"#f-{i1}-horario_atual", "14:30"); pg.press(f"#f-{i1}-horario_atual", "Tab")
    ok("horário atual igual ao anterior barrado", "diferente do anterior" in pg.inner_text(f"#e-f-{i1}-horario_atual"))
    pg.fill(f"#f-{i1}-horario_atual", "09:00")

    pg.click("#btn-add"); i2 = ids(pg)[1]
    escolher(pg, i2, "tipo", "Bloqueio"); comuns(pg, i2, "Alta", 10)
    pg.fill(f"#f-{i2}-detalhe", "curto"); pg.press(f"#f-{i2}-detalhe", "Tab")
    ok("descrição específica curta barrada", "mínimo de 15" in pg.inner_text(f"#e-f-{i2}-detalhe"))
    pg.fill(f"#f-{i2}-detalhe", "Bloquear todos os horários da manhã para manutenção do equipamento.")

    pg.click("#btn-add"); i3 = ids(pg)[2]
    escolher(pg, i3, "tipo", "Ajustes"); comuns(pg, i3, "Normal", 20)
    pg.fill(f"#f-{i3}-horario_anterior", "08:00"); pg.fill(f"#f-{i3}-horario_atual", "07:30")
    ok("Ajustes aceita sem dados do paciente", not pg.inner_text(f"#e-f-{i3}-paciente"))

    pg.click("#btn-add"); i4 = ids(pg)[3]
    escolher(pg, i4, "tipo", "Ajustes"); comuns(pg, i4, "Normal", 20)
    pg.fill(f"#f-{i4}-horario_anterior", "08:00"); pg.fill(f"#f-{i4}-horario_atual", "07:30")
    pg.click("#btn-gerar")
    ok("item repetido barrado", "repete a configuração 3" in pg.inner_text("#resumo-erros"), pg.inner_text("#resumo-erros"))
    pg.click(f'[data-remover="{i4}"]')
    ok("repetido removido", pg.locator("#itens .item").count() == 3 and "repete" not in pg.inner_text("#itens"))
    pg.click("#btn-gerar")
    pg.click('#resumo-erros [data-foco="aceite"]')
    ok("clique no erro leva ao campo", pg.evaluate("document.activeElement && document.activeElement.id") == "aceite")
    pg.check("#aceite")
    ok("contador: tudo preenchido", "Tudo preenchido" in pg.inner_text("#contador"), pg.inner_text("#contador"))

    print("D) Saídas: e-mail com prioridade, JSON e PDF (Imaginamente)")
    pg.click("#btn-gerar")
    ok("resultado visível", pg.is_visible("#resultado"))
    res = pg.inner_text("#resultado")
    dados = json.loads(pg.text_content("#json-saida"))
    corpo = pg.input_value("#corpo-email")
    ok("protocolo", re.fullmatch(r"IMAGINAMENTE-\d{8}-\d{4}-[A-Z0-9]{4}", dados["protocolo"]), dados["protocolo"])
    assunto = f"[Imaginamente] [Urgente] Trocas e bloqueios da semana - Dra. Camila Torres (fictícia) - 3 configurações - {dados['protocolo']}"
    ok("assunto com prioridade mais alta", assunto in res, res[:500])
    ok("destinatário do modelo", "agenda.imaginamente@instituicao.example" in res)
    for t in ["CONFIGURAÇÃO 1 - TROCAS (Prioridade: Urgente)", "- Dados do paciente: Paciente Exemplo", "- Horário anterior: 14:30", "- Horário atual: 09:00",
              "CONFIGURAÇÃO 2 - BLOQUEIO (Prioridade: Alta)", "- Descrição do bloqueio ou alteração permanente: Bloquear todos",
              "CONFIGURAÇÃO 3 - AJUSTES (Prioridade: Normal)", "Prioridade mais alta: Urgente", "Resumo: Trocas e bloqueios da semana", "Aceite eletrônico", "Lei nº 13.709"]:
        ok("corpo contém '" + t + "'", t in corpo, corpo[:300])
    ok("JSON: prioridade e escala do ClickUp", [(i["prioridade"], i["prioridade_clickup"]) for i in dados["itens"]] == [("Urgente", 1), ("Alta", 2), ("Normal", 3)], dados["itens"])
    ok("JSON: campos só do tipo", "horario_anterior" in dados["itens"][0] and "bloqueio_inicio" not in dados["itens"][0] and dados["itens"][1]["observacoes"] is None)
    ok("JSON: resumo no nível da solicitação", dados["resumo"] == "Trocas e bloqueios da semana")
    with pg.expect_download() as dl:
        pg.click('[data-acao="pdf"]')
    arq = OUT + "/imaginamente.pdf"; dl.value.save_as(arq)
    n, t = texto_pdf(arq)
    ok("PDF: até 2 páginas", n <= 2, n)
    tn = re.sub(r"\s+", " ", t)
    for x in ["Configuração de Agenda - Imaginamente", "FORMULÁRIO", "1. TIPO", "Trocas", "Configuração 1 de 3 - Trocas", "Prioridade: Urgente", "Dados do paciente",
              "Horário anterior", "14:30", "Configuração 2 de 3 - Bloqueio", "Configuração 3 de 3 - Ajustes", "3. DATA E ASSINATURA", "aceite eletrônico", "Página 1/", "Lei nº 13.709"]:
        ok("PDF contém '" + x + "'", x in tn, tn[:300])
    os.system(f"pdftoppm -r 80 -png '{arq}' '{OUT}/pdf_imaginamente'")

    print("E) Prefixo de prioridade no assunto")
    pg.click('[data-acao="nova"]')
    pg.check('input[name="modelo"][value="CASU"]', force=True)
    cab(pg); i1 = ids(pg)[0]
    escolher(pg, i1, "tipo", "Antecipação"); comuns(pg, i1, "Baixa", 6); pg.check("#aceite"); pg.click("#btn-gerar")
    ok("só Baixa: sem marca", "[CASU] Resumo de teste" in pg.inner_text("#resultado"), pg.inner_text("#resultado")[:300])
    pg.click('[data-acao="nova"]')
    cab(pg); i1 = ids(pg)[0]
    escolher(pg, i1, "tipo", "Antecipação"); comuns(pg, i1, "Alta", 6); pg.check("#aceite"); pg.click("#btn-gerar")
    ok("Alta: marca no assunto", "[CASU] [Alta] Resumo de teste" in pg.inner_text("#resultado"), pg.inner_text("#resultado")[:300])

    print("F) CASU completo pelo exemplo e PDF")
    pg.click('[data-acao="nova"]')
    pg.click("#btn-exemplo")
    ok("exemplo CASU pronto", "Tudo preenchido" in pg.inner_text("#contador") and pg.locator("#itens .item").count() == 3, pg.inner_text("#contador"))
    pg.click("#btn-gerar")
    dc = json.loads(pg.text_content("#json-saida"))
    ok("exemplo CASU: tipos e prioridades", [(i["tipo"], i["prioridade"]) for i in dc["itens"]] == [("Bloqueio", "Alta"), ("Ajustes tempo slot", "Normal"), ("Alterações permanentes", "Baixa")], dc["itens"])
    with pg.expect_download() as dl:
        pg.click('[data-acao="pdf"]')
    arq = OUT + "/casu.pdf"; dl.value.save_as(arq)
    n, t = texto_pdf(arq); tn = re.sub(r"\s+", " ", t)
    for x in ["Configuração de Agenda - CASU", "Antecipação", "Ajustes tempo slot", "Configuração 1 de 3 - Bloqueio", "Sem reposição", "Alteração de tempo de atendimento", "20 minutos", "Descrição da alteração permanente"]:
        ok("PDF CASU contém '" + x + "'", x in tn, tn[:300])
    os.system(f"pdftoppm -r 80 -png '{arq}' '{OUT}/pdf_casu'")
    pg.click('[data-acao="nova"]')
    pg.check('input[name="modelo"][value="IMAGINAMENTE"]', force=True)
    pg.click("#btn-exemplo"); pg.click("#btn-gerar")
    ok("exemplo Imaginamente gera documento", pg.is_visible("#resultado") and "[Urgente]" in pg.inner_text("#resultado"))

    print("G) 10 configurações: várias páginas e caracteres fora do WinAnsi")
    pg.click('[data-acao="nova"]')
    pg.check('input[name="modelo"][value="CASU"]', force=True)
    cab(pg, "Dr. João D'Ávila Ñandú Çelik", "Resumo com emoji 😀 e símbolo ∑ fora do alfabeto")
    for _ in range(9):
        pg.click("#btn-add")
    lista = ids(pg)
    ok("10 itens e botão de adicionar desabilitado", len(lista) == 10 and pg.is_disabled("#btn-add"), lista)
    longo = ("Texto longo de observação para testar a quebra de linhas no PDF. " * 9)[:560]
    for k, iid in enumerate(lista, 1):
        escolher(pg, iid, "tipo", "Alterações permanentes")
        escolher(pg, iid, "prioridade", "Baixa")
        pg.fill(f"#f-{iid}-descricao", longo)
        pg.fill(f"#f-{iid}-data_regencia", d(30 + k))
        pg.fill(f"#f-{iid}-detalhe", longo + f"\nLinha extra do item {k}.")
    pg.check("#aceite")
    ok("pronto para finalizar", "Tudo preenchido" in pg.inner_text("#contador"), pg.inner_text("#contador"))
    pg.click("#btn-gerar")
    with pg.expect_download() as dl:
        pg.click('[data-acao="pdf"]')
    arq = OUT + "/grande.pdf"; dl.value.save_as(arq)
    n2, t2 = texto_pdf(arq); tn2 = re.sub(r"\s+", " ", t2)
    ok("várias páginas", n2 >= 3, n2)
    ok("numeração e continuação", f"Página {n2}/{n2}" in tn2 and "(continuação)" in tn2)
    ok("10 configurações presentes", all(f"Configuração {k} de 10" in tn2 for k in range(1, 11)))
    ok("nome com acentos e apóstrofo", "João D'Ávila Ñandú Çelik" in tn2)
    ok("fora do WinAnsi vira '?'", "emoji ? e símbolo ?" in tn2, tn2[:400])
    os.system(f"pdftoppm -r 60 -png '{arq}' '{OUT}/pdf_grande'")
    pg.close()

    print("H) Gmail: desligado sem client id")
    pd0 = nova_pagina(ctx)
    pd0.click("#btn-exemplo"); pd0.click("#btn-gerar")
    ok("botão do Gmail desabilitado e com explicação", pd0.is_disabled('[data-acao="gmail"]') and "versão hospedada" in pd0.inner_text("#resultado"))
    pd0.close()

    print("I) Gmail: fluxo completo com Google simulado")
    init = """
    window.CONFIGURACAO_AGENDA = {googleClientId: 'teste.apps.googleusercontent.com', dominioPermitido: 'instituicao.example'};
    window.__cfg = null; window.__opened = null;
    window.google = {accounts: {oauth2: {initTokenClient: (cfg) => { window.__cfg = cfg; return {requestAccessToken: () => {
        if (window.__modo === 'fechar') cfg.error_callback({type: 'popup_closed', message: 'x'});
        else cfg.callback({access_token: 'tok-123', expires_in: '3599'}); }}; }}}};
    """
    pgm = nova_pagina(ctx, init)
    chamadas = []

    def gmail(route):
        req = route.request
        chamadas.append((req.method, req.url, req.headers.get("authorization"), req.post_data))
        if req.url.endswith("/profile"):
            route.fulfill(json={"emailAddress": "camila.torres@instituicao.example"})
        elif req.url.endswith("/drafts"):
            route.fulfill(json={"id": "r-1", "message": {"id": "m-9"}})
        else:
            route.fulfill(status=404, body="{}")
    pgm.route("https://gmail.googleapis.com/**", gmail)
    pgm.click("#btn-exemplo"); pgm.click("#btn-gerar")
    ok("botão do Gmail habilitado", pgm.is_enabled('[data-acao="gmail"]'))
    pgm.evaluate("window.__modo = 'fechar'")
    pgm.click('[data-acao="gmail"]'); pgm.wait_for_selector(".gstatus.erro")
    ok("login cancelado: mensagem clara e nenhum rascunho", "Login cancelado" in pgm.inner_text("#gmail-status") and not chamadas)
    pgm.evaluate("window.__modo = 'ok'")
    pgm.click('[data-acao="gmail"]'); pgm.wait_for_selector("#lnk-gmail")
    cfg = pgm.evaluate("({s: window.__cfg.scope, id: window.__cfg.client_id, hd: window.__cfg.hd})")
    ok("escopo e client id corretos", cfg == {"s": "https://www.googleapis.com/auth/gmail.compose", "id": "teste.apps.googleusercontent.com", "hd": "instituicao.example"}, cfg)
    post = [c for c in chamadas if c[0] == "POST"]
    ok("um rascunho criado com token Bearer", len(post) == 1 and post[0][2] == "Bearer tok-123", chamadas)
    raw = json.loads(post[0][3])["message"]["raw"]
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)), policy=policy.default)
    corpo_m = pgm.input_value("#corpo-email")
    ok("MIME: Para e Cc", msg["To"] == "agenda.imaginamente@instituicao.example" and "camila.torres" not in msg["To"] or msg["To"].startswith("agenda."), msg["To"])
    ok("MIME: assunto UTF-8 íntegro", msg["Subject"].startswith("[CASU]") or msg["Subject"].startswith("[Imaginamente]"), msg["Subject"])
    corpo_txt = msg.get_body(preferencelist=("plain",)).get_content()
    ok("MIME: corpo igual ao da tela (acentos)", corpo_txt.replace("\r\n", "\n").strip() == corpo_m.strip(), corpo_txt[:200])
    anexos = list(msg.iter_attachments())
    ok("MIME: 1 anexo PDF com nome do protocolo", len(anexos) == 1 and anexos[0].get_content_type() == "application/pdf" and anexos[0].get_filename().endswith(".pdf"), [a.get_filename() for a in anexos])
    pdfb = anexos[0].get_content()
    ok("MIME: anexo é PDF válido", pdfb[:5] == b"%PDF-" and len(pdfb) > 2000)
    open(OUT + "/anexo_gmail.pdf", "wb").write(pdfb)
    tg = re.sub(r"\s+", " ", texto_pdf(OUT + "/anexo_gmail.pdf")[1])
    ok("anexo traz o formulário preenchido", "Configuração 1 de 3" in tg and "Prioridade: Alta" in tg, tg[:200])
    href = pgm.get_attribute("#lnk-gmail", "href")
    ok("link abre o rascunho na conta certa", href == "https://mail.google.com/mail/u/camila.torres%40instituicao.example/#drafts?compose=m-9", href)
    ok("status de sucesso", "Rascunho criado" in pgm.inner_text("#gmail-status"))
    pgm.click('[data-acao="gmail"]'); pgm.wait_for_timeout(500)
    ok("segundo clique reaproveita o token (sem novo login)", pgm.evaluate("window.__cfg !== null") and len([c for c in chamadas if c[0] == "POST"]) == 2)
    pgm.screenshot(path=OUT + "/05_gmail_ok.png", full_page=True)
    pgm.close()

    pge = nova_pagina(ctx, init)
    pge.route("https://gmail.googleapis.com/**", lambda r: r.fulfill(status=403, body="{}"))
    pge.click("#btn-exemplo"); pge.click("#btn-gerar"); pge.click('[data-acao="gmail"]'); pge.wait_for_selector(".gstatus.erro")
    ok("403: orienta sobre API/permite envio manual", "API do Gmail" in pge.inner_text("#gmail-status"))
    ok("botão volta a ficar utilizável", pge.is_enabled('[data-acao="gmail"]'))
    pge.close()

    print("J) Dentro do viewer (capacidade 'downloads' simulada)")
    pv = nova_pagina(ctx, """window.__saved=null; window.claude={use: async (n)=> n==='downloads' ? {save: async (r)=>{window.__saved=r; return {status:'saved'}}} : null};""")
    pv.click("#btn-exemplo"); pv.click("#btn-gerar"); pv.click('[data-acao="pdf"]')
    pv.wait_for_function("window.__saved !== null", timeout=8000)
    s = pv.evaluate("({f: window.__saved.filename, head: String.fromCharCode(...window.__saved.data.slice(0,5)), n: window.__saved.data.length})")
    ok("downloads.save com PDF válido", s["f"].endswith(".pdf") and s["head"] == "%PDF-" and s["n"] > 1000, s)
    pv.wait_for_timeout(200); ok("avisa que salvou", "PDF salvo" in pv.inner_text("#toast"))
    pv.close()
    pn = nova_pagina(ctx, "window.claude={use: async ()=>null};")
    pn.click("#btn-exemplo"); pn.click("#btn-gerar"); pn.click('[data-acao="pdf"]'); pn.wait_for_timeout(600)
    ok("sem a capacidade: avisa", "não está disponível" in pn.inner_text("#toast")); pn.close()
    pr = nova_pagina(ctx, "window.claude={use: async (n)=> n==='downloads' ? {save: async ()=>{throw {code:'declined',message:'x'}}} : null};")
    pr.click("#btn-exemplo"); pr.click("#btn-gerar"); pr.click('[data-acao="pdf"]'); pr.wait_for_timeout(600)
    ok("viewer recusa: mensagem clara", "cancelado" in pr.inner_text("#toast")); pr.close()

    print("K) Teclado")
    pk = nova_pagina(ctx)
    pk.focus("input[name^='n-'][name$='-tipo']"); pk.keyboard.press("ArrowRight")
    ok("setas escolhem o tipo", pk.evaluate("document.querySelector('input[name$=\"-tipo\"]:checked')?.value") == "Bloqueio")
    pk.close()

    print("L) Visual")
    pd = nova_pagina(ctx)
    pd.click("#btn-exemplo"); pd.screenshot(path=OUT + "/02_desktop_casu.png", full_page=True)
    pd.click("#btn-gerar"); pd.screenshot(path=OUT + "/03_desktop_resultado.png", full_page=True); pd.close()
    ph = b.new_context(viewport={"width": 390, "height": 800}, color_scheme="dark", device_scale_factor=2)
    pm = nova_pagina(ph)
    pm.check('input[name="modelo"][value="IMAGINAMENTE"]', force=True); pm.click("#btn-exemplo")
    pm.screenshot(path=OUT + "/04_celular_escuro.png", full_page=True)
    larg = pm.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    ok("sem rolagem horizontal no celular", larg[0] <= larg[1], larg)
    pm.click("#btn-gerar"); pm.screenshot(path=OUT + "/06_celular_resultado.png", full_page=True)
    larg = pm.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    ok("sem rolagem horizontal no resultado (celular)", larg[0] <= larg[1], larg)
    pm.close(); ph.close()
    for w in (320, 768):
        pc = b.new_context(viewport={"width": w, "height": 900}); pt = nova_pagina(pc)
        pt.click("#btn-exemplo"); pt.click("#btn-gerar")
        lg = pt.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        ok(f"sem rolagem horizontal em {w}px", lg[0] <= lg[1], lg)
        pt.screenshot(path=OUT + f"/07_{w}.png", full_page=True); pt.close(); pc.close()
    b.close()

print()
ok("nenhum erro de JavaScript no console", not erros_js, erros_js[:3])
print("RESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S): {falhas}")
sys.exit(1 if falhas else 0)
