/**
 * Eventos e inicialização
 * Liga os eventos da página e desenha a primeira tela. Deve ser o último script carregado.
 */
"use strict";

// Marca um campo como visitado e localiza a configuração a que um controle pertence.
// Marca um campo como "já visitado": só então o erro dele aparece na tela.
const tocar = id => state.tocados.add(id);
// Acha a configuração (item) dona do campo que disparou o evento.
const itemDe = t => state.itens.find(i => i.id === t.dataset.item);
// Digitação: guarda o valor no estado e revalida (sem redesenhar, para não perder o foco).
// Digitação: guarda o valor no estado e recalcula as pendências (sem redesenhar, para não perder o foco).
$("#itens").addEventListener("input", ev => {
  const t = ev.target, it = itemDe(t); if (!it || t.type === "radio") return;
  it[t.dataset.campo] = t.value; atualizar();
});
// Escolha de botão/data: guarda o valor; trocar tipo/prioridade/reposição redesenha os campos.
// Escolha de chip/data: guarda o valor; chips redesenham a configuração (ex.: tipo muda os campos exibidos).
$("#itens").addEventListener("change", ev => {
  const t = ev.target, it = itemDe(t); if (!it) return;
  it[t.dataset.campo] = t.value;
  const grupo = t.closest(".grupo"); tocar(grupo ? grupo.dataset.field : t.id);
  if (t.type === "radio") renderItens(t.id); else atualizar();
});
// Ao sair de um campo, marca como visitado para exibir o erro dele.
// Ao sair do campo, passa a mostrar o erro dele.
$("#itens").addEventListener("focusout", ev => {
  const id = ev.target.id; if (!id || ev.target.type === "radio") return;
  tocar(id); atualizar();
});
// Botão Remover de uma configuração.
// Botão "Remover" de uma configuração.
$("#itens").addEventListener("click", ev => {
  const b = ev.target.closest("[data-remover]"); if (!b) return;
  state.itens = state.itens.filter(i => i.id !== b.dataset.remover); renderItens();
});
// Botão 'Adicionar outra configuração' (limite em MAX_ITENS).
// Botão "Adicionar outra configuração" (limite em MAX_ITENS).
$("#btn-add").addEventListener("click", () => {
  if (state.itens.length >= MAX_ITENS) return;
  const it = novoItem(); state.itens.push(it); renderItens("f-" + it.id + "-tipo");
});
// Campos do cabeçalho (solicitante, unidade, e-mail, resumo): mesmo tratamento de digitação e saída do campo.
[["h-solicitante", "solicitante"], ["h-unidade", "unidade"], ["h-email", "email"], ["h-resumo", "resumo"]].forEach(([id, k]) => {
  const el = document.getElementById(id);
  el.addEventListener("input", () => { state.h[k] = el.value; atualizar(); });
  el.addEventListener("blur", () => { tocar(id); atualizar(); });
});
// Caixa de aceite.
// Checkbox de aceite.
$("#aceite").addEventListener("change", ev => { state.aceite = ev.target.checked; tocar("aceite"); atualizar(); });
// Abas CASU/Imaginamente: troca o modelo e descarta tipos que não existem no novo modelo.
document.querySelectorAll('input[name="modelo"]').forEach(r => r.addEventListener("change", () => {
  state.modelo = r.value; state.resultado = null; $("#resultado").hidden = true;
  state.itens.forEach(it => { if (!modeloAtual().tipos[it.tipo]) it.tipo = ""; });
  renderItens();
}));
// Finalizar (envio do formulário).
// Finalizar: valida tudo; só gera o documento se não houver pendências.
$("#form").addEventListener("submit", ev => { ev.preventDefault(); gerar(); });
// Preencher exemplo fictício.
// Preenche o formulário com dados fictícios, para demonstração.
$("#btn-exemplo").addEventListener("click", exemplo);
// Clique em um erro da lista: rola até o campo e foca nele.
// Clique em um erro do resumo leva o foco ao campo com problema.
$("#resumo-erros").addEventListener("click", ev => {
  const b = ev.target.closest("[data-foco]"); if (!b) return;
  const el = document.getElementById(b.dataset.foco); if (el) { el.scrollIntoView({ block: "center", behavior: reduzMov() ? "auto" : "smooth" }); el.focus({ preventScroll: true }); }
});
// Botões da tela de resultado (PDF, Gmail, copiar, nova solicitação).
// Botões da tela de resultado (baixar PDF, Gmail, copiar, nova solicitação).
$("#resultado").addEventListener("click", ev => {
  const b = ev.target.closest("[data-acao]"); if (!b || !state.resultado) return;
  const e = state.resultado.email;
  switch (b.dataset.acao) {
    case "pdf": baixarPDF(); break;
    case "gmail": enviarGmail(); break;
    case "copiar-corpo": copiar(e.corpo, $("#corpo-email"), "Corpo do e-mail"); break;
    case "copiar-assunto": copiar(e.assunto, null, "Assunto"); break;
    case "copiar-para": copiar(e.para, null, "Destinatário"); break;
    case "nova": reiniciar(); break;
  }
});

// Primeira tela.
renderItens();
