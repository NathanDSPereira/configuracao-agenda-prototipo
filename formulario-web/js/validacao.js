/**
 * Validação
 * Regras dos campos obrigatórios. Devolve a lista de pendências; nada aqui mexe na tela.
 */
"use strict";

// Valida uma configuração e devolve a lista de erros {item, campo, msg}.
// Valida o formulário inteiro (solicitante, e-mail, resumo, configurações e aceite). Lista vazia = pode finalizar.
// Valida uma configuração e devolve a lista de erros {item, campo, msg}.
function validarItem(it) {
  const e = [], add = (campo, msg) => e.push({ item: it.id, campo, msg });
  if (!it.tipo) add("tipo", "Selecione o tipo da solicitação.");
  if (!it.prioridade) add("prioridade", "Selecione a prioridade.");
  if (!it.tipo) return e;
  if (!it.descricao.trim()) add("descricao", "Descreva o que precisa ser configurado.");
  if (!it.data_regencia) add("data_regencia", "Informe a data de regência da alteração.");
  else if (it.data_regencia < hojeISO()) add("data_regencia", "A data de regência não pode ser anterior a hoje.");

  const nomes = camposDoTipo(it).map(x => x[0]);
  camposDoTipo(it).forEach(([c, req]) => {
    if (c === "detalhe") return;
    if (req && !String(it[c]).trim()) add(c, MSG_OBRIG[c]);
  });
  if (nomes.includes("detalhe") && it.detalhe.trim().length < DESC_MIN)
    add("detalhe", modeloAtual().detalheRot + " (mínimo de " + DESC_MIN + " caracteres).");
  if (it.bloqueio_inicio && it.bloqueio_fim && it.bloqueio_fim < it.bloqueio_inicio) add("bloqueio_fim", "O fim do bloqueio não pode ser anterior ao início.");
  if (it.reposicao === "Com reposição" && it.data_reposicao && it.bloqueio_fim && it.data_reposicao < it.bloqueio_fim)
    add("data_reposicao", "A reposição não pode ser anterior ao fim do bloqueio.");
  if (nomes.includes("novo_slot_min") && it.novo_slot_min.trim() && (!/^\d+$/.test(it.novo_slot_min.trim()) || +it.novo_slot_min < SLOT_MIN || +it.novo_slot_min > SLOT_MAX))
    add("novo_slot_min", "Informe um valor entre " + SLOT_MIN + " e " + SLOT_MAX + " minutos.");
  if (it.horario_anterior && it.horario_atual && it.horario_anterior === it.horario_atual) add("horario_atual", "O horário atual deve ser diferente do anterior.");
  return e;
}
// Chave que identifica o 'conteúdo' de uma configuração, usada para barrar repetidas no mesmo envio.
// Chave que identifica o conteúdo de uma configuração, para detectar repetidas no mesmo formulário.
function chaveItem(it) {
  const n = camposDoTipo(it).map(x => x[0]);
  return [it.tipo, it.data_regencia, n.includes("bloqueio_inicio") ? it.bloqueio_inicio + it.bloqueio_fim : "", n.includes("novo_slot_min") ? it.novo_slot_min.trim() : "",
    n.includes("paciente") ? it.paciente.trim().toLowerCase() : "", n.includes("horario_atual") ? it.horario_anterior + ">" + it.horario_atual : "",
    n.includes("detalhe") ? it.detalhe.trim().toLowerCase() : ""].join("|");
}
// Valida o formulário inteiro: cabeçalho, cada configuração, repetidas e aceite.
function validar() {
  const e = [], h = state.h;
  if (h.solicitante.trim().split(/\s+/).filter(Boolean).length < 2) e.push({ item: "h", campo: "solicitante", msg: "Informe o nome completo do profissional." });
  if (!h.unidade.trim()) e.push({ item: "h", campo: "unidade", msg: "Informe a unidade de atendimento." });
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(h.email.trim())) e.push({ item: "h", campo: "email", msg: "Informe um e-mail válido." });
  if (!h.resumo.trim()) e.push({ item: "h", campo: "resumo", msg: "Informe o resumo da solicitação." });
  const vistos = {};
  state.itens.forEach((it, i) => {
    const ei = validarItem(it);
    e.push.apply(e, ei);
    if (!ei.length) {
      const k = chaveItem(it);
      if (vistos[k] != null) e.push({ item: it.id, campo: "tipo", msg: "Esta configuração repete a configuração " + (vistos[k] + 1) + " deste formulário." });
      else vistos[k] = i;
    }
  });
  if (!state.aceite) e.push({ item: "a", campo: "aceite", msg: "Marque o aceite para finalizar." });
  return e;
}
// Id do elemento da tela que corresponde a um erro (para exibir a mensagem e focar o campo).
// Converte um erro no id do campo na página (usado para mostrar a mensagem e levar o foco).
const idCampo = e => e.item === "h" ? "h-" + e.campo : e.item === "a" ? "aceite" : "f-" + e.item + "-" + e.campo;
