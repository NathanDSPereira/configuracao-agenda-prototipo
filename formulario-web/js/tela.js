/**
 * Desenho da tela
 * Gera o HTML das configurações, mostra/oculta erros, contador de pendências e resumo de erros.
 */
"use strict";

// HTML de um grupo de botões de escolha (tipo, prioridade, reposição). pri=true aplica as cores de prioridade.
// HTML de um grupo de botões de escolha (tipo, prioridade, reposição).
function chipsHTML(it, c, ops, pri) {
  return '<div class="chips">' + ops.map((o, k) => {
    const v = pri ? o.v : o, id = "f-" + it.id + "-" + c + (k ? "-" + k : "");
    return '<label class="chip' + (pri ? " chip-p p-" + o.cls : "") + '"><input type="radio" name="n-' + it.id + "-" + c + '" id="' + id + '" value="' + esc(v) +
      '" data-item="' + it.id + '" data-campo="' + c + '"' + (it[c] === v ? " checked" : "") + '><span>' + esc(v) + '</span></label>';
  }).join("") + '</div>';
}
// HTML de um campo (rótulo + controle + espaço da mensagem de erro).
// HTML de um campo com rótulo, controle e área de erro.
function campoHTML(it, c) {
  const meta = CAMPOS[c], id = "f-" + it.id + "-" + c, v = it[c], req = obrigatorio(it, c);
  const marca = req ? ' <span class="req" aria-hidden="true">*</span>' : ' <span class="opt">(opcional)</span>';
  const rot = c === "tipo" ? "Tipo" : c === "prioridade" ? "Prioridade / urgência" : rotuloCampo(c);
  const desc = ' aria-describedby="e-' + id + '"', data = ' data-item="' + it.id + '" data-campo="' + c + '"';
  const erro = '<p class="err" id="e-' + id + '"></p>';
  if (c === "tipo" || c === "prioridade" || meta.t === "chips") {
    const ops = c === "tipo" ? Object.keys(modeloAtual().tipos) : c === "prioridade" ? PRIORIDADES : meta.ops;
    return '<fieldset class="campo cheia grupo" data-field="' + id + '"' + desc + '><legend class="rot">' + rot + marca + '</legend>' + chipsHTML(it, c, ops, c === "prioridade") + erro + '</fieldset>';
  }
  let ctrl;
  if (meta.t === "area") ctrl = '<textarea id="' + id + '"' + data + desc + ' maxlength="' + meta.max + '" rows="' + meta.rows + '"' + (req ? ' aria-required="true"' : "") + '>' + esc(v) + '</textarea>';
  else if (meta.t === "text") ctrl = '<input type="text" id="' + id + '"' + data + desc + ' maxlength="' + meta.max + '" value="' + esc(v) + '"' + (req ? ' aria-required="true"' : "") + '>';
  else if (meta.t === "num") ctrl = '<input type="number" inputmode="numeric" id="' + id + '"' + data + desc + ' min="' + SLOT_MIN + '" max="' + SLOT_MAX + '" step="1" value="' + esc(v) + '" aria-required="true">';
  else if (meta.t === "time") ctrl = '<input type="time" id="' + id + '"' + data + desc + ' value="' + esc(v) + '"' + (req ? ' aria-required="true"' : "") + '>';
  else {
    const min = c === "data_regencia" ? hojeISO() : c === "data_reposicao" ? (it.bloqueio_fim || hojeISO()) : "";
    ctrl = '<input type="date" id="' + id + '"' + data + desc + (min ? ' min="' + min + '"' : "") + ' value="' + esc(v) + '" aria-required="true">';
  }
  return '<div class="campo' + (meta.cheia ? " cheia" : "") + '"><label for="' + id + '">' + rot + marca + '</label>' + ctrl +
    (meta.ajuda ? '<p class="ajuda">' + meta.ajuda + '</p>' : "") + erro + '</div>';
}
// HTML de um cartão de configuração. Sem tipo escolhido, mostra só Tipo e Prioridade.
// HTML de uma configuração completa (cartão com seus campos).
function itemHTML(it, i) {
  const campos = ["tipo", "prioridade"];
  if (it.tipo) campos.push("descricao", "data_regencia", ...camposDoTipo(it).map(x => x[0]), "observacoes");
  return '<article class="item" data-id="' + it.id + '" aria-label="Configuração ' + (i + 1) + '">' +
    '<div class="item-cab"><h3>Configuração ' + (i + 1) + (it.tipo ? '<small>' + esc(it.tipo) + '</small>' : "") + '</h3>' +
    (state.itens.length > 1 ? '<button type="button" class="btn btn-ghost btn-sm" data-remover="' + it.id + '">Remover</button>' : "") + '</div>' +
    '<div class="grade">' + campos.map(c => campoHTML(it, c)).join("") + '</div></article>';
}
// Redesenha todas as configurações. Use após mudar tipo/prioridade, adicionar ou remover. focoId devolve o foco ao controle.
// Redesenha todas as configurações e atualiza o botão de adicionar.
function renderItens(focoId) {
  $("#itens").innerHTML = state.itens.map(itemHTML).join("");
  const b = $("#btn-add");
  b.textContent = "+ Adicionar outra configuração (" + state.itens.length + " de " + MAX_ITENS + ")";
  b.disabled = state.itens.length >= MAX_ITENS;
  if (focoId) { const el = document.getElementById(focoId); if (el) el.focus(); }
  atualizar();
}
// Revalida e atualiza mensagens de erro, contador de pendências e resumo. Erros só aparecem em campos tocados ou após tentar finalizar.
// Recalcula as pendências e mostra/oculta erros, contador e resumo. Chamada a cada alteração.
function atualizar() {
  const erros = validar(), mapa = {};
  erros.forEach(e => { mapa[idCampo(e)] = e.msg; });
  const mostra = id => (state.tentou || state.tocados.has(id)) && mapa[id];
  document.querySelectorAll(".err").forEach(p => {
    const id = p.id.slice(2), m = mostra(id);
    p.textContent = m || "";
    const ctrl = document.getElementById(id);
    if (ctrl && ctrl.tagName !== "FIELDSET") { if (m) ctrl.setAttribute("aria-invalid", "true"); else ctrl.removeAttribute("aria-invalid"); }
  });
  document.querySelectorAll(".grupo").forEach(g => g.classList.toggle("invalido", !!mostra(g.dataset.field)));
  const c = $("#contador");
  if (erros.length) { c.className = "contador"; c.innerHTML = '<b>' + erros.length + '</b> ' + (erros.length === 1 ? "pendência" : "pendências") + ' para finalizar'; }
  else { c.className = "contador ok"; c.textContent = "Tudo preenchido. Pronto para finalizar."; }
  renderResumo(erros);
  return erros;
}
// Caixa vermelha com todas as pendências agrupadas; cada item leva ao campo ao clicar.
// Caixa de resumo de erros, agrupada por configuração, exibida após tentar finalizar.
function renderResumo(erros) {
  const box = $("#resumo-erros");
  if (!(state.tentou && erros.length)) { box.hidden = true; box.innerHTML = ""; return; }
  const grupos = [];
  erros.forEach(e => {
    const nome = e.item === "h" ? "Dados da solicitação" : e.item === "a" ? "Aceite" : "Configuração " + (state.itens.findIndex(i => i.id === e.item) + 1);
    let g = grupos.find(x => x.nome === nome);
    if (!g) { g = { nome, itens: [] }; grupos.push(g); }
    g.itens.push(e);
  });
  box.innerHTML = '<h2>O formulário não pode ser finalizado: ' + erros.length + (erros.length === 1 ? " pendência" : " pendências") + '</h2><ul>' +
    grupos.map(g => '<li><span class="grupo">' + g.nome + '</span><ul>' +
      g.itens.map(e => '<li><button type="button" class="btn-link" data-foco="' + idCampo(e) + '">' + esc(e.msg) + '</button></li>').join("") + '</ul></li>').join("") + '</ul>';
  box.hidden = false;
}
