/**
 * Resultado e ações
 * Tela de resultado, avisos (toast), copiar texto, baixar PDF, gerar, reiniciar e preencher exemplo.
 */
"use strict";

// Nome do PDF: Configuracao-Agenda_<modelo>_<protocolo>.pdf
// Nome do PDF gerado.
const nomeArquivo = d => "Configuracao-Agenda_" + d.modelo + "_" + d.protocolo + ".pdf";
// Mostra o resultado: ações (PDF, Gmail, copiar), prévia do e-mail e JSON.
// Desenha a tela de resultado: ações, prévia do e-mail e JSON.
function renderResultado() {
  const r = state.resultado, d = r.dados, e = r.email, box = $("#resultado"), gmailOk = !!CONFIG.googleClientId;
  box.innerHTML =
    '<header><h2 id="t-res">Documento gerado</h2><p>' + esc(d.protocolo) + '</p></header>' +
    '<div class="conteudo">' +
    '<div class="acoes">' +
      '<button type="button" class="btn btn-primario" data-acao="pdf">Baixar PDF</button>' +
      '<button type="button" class="btn btn-suave" data-acao="gmail"' + (gmailOk ? "" : " disabled") + '>Enviar pelo Gmail</button>' +
      '<button type="button" class="btn btn-ghost" data-acao="copiar-corpo">Copiar corpo do e-mail</button>' +
      '<button type="button" class="btn btn-ghost" data-acao="copiar-assunto">Copiar assunto</button>' +
    '</div>' +
    (gmailOk ? "" : '<p class="nota">O envio pelo Gmail (login Google, rascunho com o PDF já anexado) fica disponível na versão hospedada, depois de configurado o acesso do Google.</p>') +
    '<div class="gstatus" id="gmail-status" role="status" aria-live="polite" hidden></div>' +
    '<div class="email" aria-label="Prévia do e-mail">' +
      '<div class="linha"><span class="rot">Para</span><span class="val">' + esc(e.para) + '</span><button type="button" class="btn btn-ghost btn-sm" data-acao="copiar-para">Copiar</button></div>' +
      '<div class="linha"><span class="rot">Cc</span><span class="val">' + esc(e.cc) + '</span><span></span></div>' +
      '<div class="linha"><span class="rot">Assunto</span><span class="val">' + esc(e.assunto) + '</span><span></span></div>' +
      '<textarea id="corpo-email" readonly aria-label="Corpo do e-mail"></textarea>' +
    '</div>' +
    '<p class="nota">Neste protótipo, nada é enviado automaticamente. Na versão integrada, o sistema envia o e-mail com o PDF anexado e cria o card.</p>' +
    '<details><summary>Dados estruturados (JSON)</summary><pre id="json-saida"></pre></details>' +
    '<div><button type="button" class="btn" data-acao="nova">Preencher nova solicitação</button></div>' +
    '</div>';
  $("#corpo-email").value = e.corpo;
  $("#json-saida").textContent = JSON.stringify(d, null, 2);
  box.hidden = false;
}

// Aviso rápido no rodapé da tela.
// Aviso rápido (toast) no rodapé da tela.
let tToast;
function toast(t) { const el = $("#toast"); el.textContent = t; clearTimeout(tToast); tToast = setTimeout(() => { el.textContent = ""; }, 3500); }
// Copia texto para a área de transferência (com plano B para navegadores restritos).
// Copia texto para a área de transferência (com plano B para ambientes restritos).
async function copiar(texto, el, rotulo) {
  try { await navigator.clipboard.writeText(texto); toast(rotulo + " copiado."); return; } catch (_) { /* plano B abaixo */ }
  if (el) {
    el.focus(); el.select && el.select();
    let ok = false; try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    toast(ok ? rotulo + " copiado." : "Texto selecionado: use Ctrl+C para copiar.");
  } else toast("Não foi possível copiar automaticamente.");
}
// Gera e salva o PDF: usa a capacidade 'downloads' quando a página roda dentro do Claude; senão, download normal do navegador.
// Gera o PDF e o entrega: pela capacidade `downloads` do viewer, ou download comum fora dele.
async function baixarPDF() {
  const d = state.resultado.dados, nome = nomeArquivo(d);
  let buf;
  try { buf = await gerarPDF(d); } catch (err) { console.error(err); toast("Não foi possível gerar o PDF."); return; }
  if (window.claude && window.claude.use) {
    const dl = await window.claude.use("downloads");
    if (!dl) { toast("O download não está disponível nesta visualização."); return; }
    try { await dl.save({ filename: nome, data: buf }); toast("PDF salvo."); }
    catch (err) { toast(err && err.code === "declined" ? "Download cancelado." : "Não foi possível salvar o PDF."); }
  } else {
    const url = URL.createObjectURL(new Blob([buf], { type: "application/pdf" }));
    const a = document.createElement("a"); a.href = url; a.download = nome; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }
}

// Ação de Finalizar: valida; se houver pendências, mostra o resumo; se não, gera protocolo, e-mail e resultado.
// Ação de finalizar: valida; se estiver tudo certo, monta dados/e-mail e mostra o resultado.
function gerar() {
  state.tentou = true;
  const erros = atualizar();
  if (erros.length) {
    state.resultado = null; $("#resultado").hidden = true;
    const box = $("#resumo-erros"); box.scrollIntoView({ behavior: reduzMov() ? "auto" : "smooth", block: "center" }); box.focus({ preventScroll: true });
    return;
  }
  const dados = montarDados();
  state.resultado = { dados, email: montarEmail(dados) };
  renderResultado();
  const box = $("#resultado"); box.scrollIntoView({ behavior: reduzMov() ? "auto" : "smooth", block: "start" }); box.focus({ preventScroll: true });
}
// Copia o estado para os campos do cabeçalho e aceite (após reiniciar ou carregar exemplo).
// Copia o estado para os campos do cabeçalho e do aceite.
function sincronizarCabecalho() {
  $("#h-solicitante").value = state.h.solicitante; $("#h-unidade").value = state.h.unidade; $("#h-email").value = state.h.email; $("#h-resumo").value = state.h.resumo;
  $("#aceite").checked = state.aceite;
  document.querySelectorAll('input[name="modelo"]').forEach(r => { r.checked = r.value === state.modelo; });
}
// Limpa tudo para uma nova solicitação.
// Limpa tudo para uma nova solicitação.
function reiniciar() {
  state.h = { solicitante: "", unidade: "", email: "", resumo: "" }; state.itens = [novoItem()]; state.aceite = false;
  state.tentou = false; state.tocados = new Set(); state.resultado = null; $("#resultado").hidden = true;
  sincronizarCabecalho(); renderItens();
  window.scrollTo({ top: 0, behavior: reduzMov() ? "auto" : "smooth" });
}
// Preenche dados fictícios do modelo atual, para demonstração.
// Preenche dados fictícios (CASU ou Imaginamente, conforme o modelo escolhido).
function exemplo() {
  const dia = n => { const x = new Date(); x.setDate(x.getDate() + n); return isoDe(x); };
  const a = novoItem(), b = novoItem(), c = novoItem();
  if (state.modelo === "CASU") {
    state.h = { solicitante: "Dra. Camila Torres (fictícia)", unidade: "Unidade Centro (exemplo)", email: "camila.torres@instituicao.example", resumo: "Bloqueio por congresso e ajustes de agenda" };
    Object.assign(a, { tipo: "Bloqueio", prioridade: "Alta", descricao: "Bloquear agenda da manhã para participação em congresso.", data_regencia: dia(7), bloqueio_inicio: dia(7), bloqueio_fim: dia(9), reposicao: "Sem reposição" });
    Object.assign(b, { tipo: "Ajustes tempo slot", prioridade: "Normal", descricao: "Reduzir a duração das consultas de retorno.", data_regencia: dia(21), novo_slot_min: "20" });
    Object.assign(c, { tipo: "Alterações permanentes", prioridade: "Baixa", descricao: "Novos dias fixos de atendimento.", data_regencia: dia(45), detalhe: "A partir da data de regência, atendimento apenas às terças e quintas, no período da tarde." });
  } else {
    state.h = { solicitante: "Dr. Rafael Menezes (fictício)", unidade: "Imagem - Unidade Centro (exemplo)", email: "rafael.menezes@instituicao.example", resumo: "Troca de horário e bloqueio de equipamento" };
    Object.assign(a, { tipo: "Trocas", prioridade: "Urgente", descricao: "Trocar o horário do exame do paciente.", data_regencia: dia(2), paciente: "Paciente Exemplo (fictício) - carteirinha 0000", horario_anterior: "08:00", horario_atual: "10:30" });
    Object.assign(b, { tipo: "Bloqueio", prioridade: "Normal", descricao: "Bloqueio por manutenção do equipamento.", data_regencia: dia(14), detalhe: "Equipamento indisponível das 08:00 às 12:00 para manutenção preventiva." });
    Object.assign(c, { tipo: "Alterações permanentes", prioridade: "Baixa", descricao: "Novo horário fixo de início da agenda.", data_regencia: dia(40), detalhe: "A agenda passa a iniciar às 07:30 em todas as quartas-feiras." });
  }
  state.itens = [a, b, c]; state.aceite = true; state.tentou = false; state.tocados = new Set(); state.resultado = null; $("#resultado").hidden = true;
  sincronizarCabecalho(); renderItens();
  toast("Exemplo fictício carregado.");
}
