/**
 * Dados, JSON e e-mail
 * Monta o JSON estruturado (protocolo, itens, prioridade ClickUp) e o texto do e-mail a partir do estado.
 */
"use strict";

// Monta o JSON final: protocolo, solicitante, resumo e configurações (só com os campos do tipo). Pronto para integrar ao n8n/banco/ClickUp.
// Monta o JSON final (protocolo, solicitante, resumo, configurações e aceite). É o que o n8n receberá.
function montarDados() {
  const agora = new Date(), m = modeloAtual();
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase();
  const protocolo = state.modelo + "-" + agora.getFullYear() + p2(agora.getMonth() + 1) + p2(agora.getDate()) + "-" + p2(agora.getHours()) + p2(agora.getMinutes()) + "-" + rand;
  return {
    protocolo, modelo: state.modelo, versao_modelo: VERSAO, emitido_em: agora.toISOString(), emitido_em_br: dataHoraBR(agora), data_br: dataBR(agora),
    solicitante: { nome: state.h.solicitante.trim(), email: state.h.email.trim(), unidade: state.h.unidade.trim() },
    resumo: state.h.resumo.trim(),
    itens: state.itens.map((it, i) => {
      const o = { n: i + 1, tipo: it.tipo, prioridade: it.prioridade, prioridade_clickup: prio(it.prioridade).cu, descricao: it.descricao.trim(), data_regencia: it.data_regencia };
      camposDoTipo(it).forEach(([c]) => { o[c] = c === "novo_slot_min" ? Number(it[c]) : (String(it[c]).trim() || null); });
      if (o.reposicao && o.reposicao !== "Com reposição") o.data_reposicao = null;
      o.observacoes = it.observacoes.trim() || null;
      return o;
    }),
    aceite: { aceito: true, em: agora.toISOString() }
  };
}
// Prioridade mais alta entre as configurações (menor número do ClickUp).
// Prioridade mais alta entre as configurações (vai para o assunto do e-mail).
const maiorPrioridade = d => d.itens.map(i => prio(i.prioridade)).sort((a, b) => a.cu - b.cu)[0];
// Lista [rótulo, valor] de uma configuração, usada no e-mail e no PDF.
// Lista [rótulo, valor] de uma configuração, na ordem exibida no e-mail e no PDF.
function pares(it, m) {
  const p = [["Prioridade", it.prioridade], ["Descrição", it.descricao], ["Data de regência da alteração", br(it.data_regencia)]];
  if (it.bloqueio_inicio) p.push(["Bloqueio", br(it.bloqueio_inicio) + " a " + br(it.bloqueio_fim)]);
  if (it.reposicao) p.push(["Reposição", it.reposicao === "Com reposição" ? "Com reposição em " + br(it.data_reposicao) : "Sem reposição"]);
  if (it.novo_slot_min != null) p.push(["Alteração de tempo de atendimento", it.novo_slot_min + " minutos"]);
  if (it.paciente) p.push(["Dados do paciente", it.paciente]);
  if (it.horario_anterior) p.push(["Horário anterior", it.horario_anterior]);
  if (it.horario_atual) p.push(["Horário atual", it.horario_atual]);
  if (it.detalhe) p.push([m.detalheLinha, it.detalhe]);
  if (it.observacoes) p.push(["Observações", it.observacoes]);
  return p;
}
// Monta destinatário, Cc, assunto (marca prioridade Urgente/Alta) e corpo do e-mail.
// Monta destinatário, assunto e corpo do e-mail.
function montarEmail(d) {
  const m = MODELOS[d.modelo], n = d.itens.length, mp = maiorPrioridade(d);
  const tag = mp.cu <= 2 ? " [" + mp.v + "]" : "";
  const assunto = "[" + m.rotulo + "]" + tag + " " + d.resumo + " - " + d.solicitante.nome + " - " + (n === 1 ? "1 configuração" : n + " configurações") + " - " + d.protocolo;
  const L = ["Prezada equipe de Agenda,", "", "Segue solicitação de configuração de agenda (" + m.rotulo + "). O formulário em PDF está em anexo.", ""];
  L.push("Protocolo: " + d.protocolo, "Resumo: " + d.resumo, "Prioridade mais alta: " + mp.v, "Solicitante: " + d.solicitante.nome,
    "Unidade: " + d.solicitante.unidade, "E-mail: " + d.solicitante.email, "Enviado em: " + d.emitido_em_br, "Total de configurações: " + n, "");
  d.itens.forEach(it => {
    L.push("CONFIGURAÇÃO " + it.n + " - " + it.tipo.toUpperCase() + " (Prioridade: " + it.prioridade + ")");
    pares(it, m).slice(1).forEach(p => L.push("- " + p[0] + ": " + p[1]));
    L.push("");
  });
  L.push("Aceite eletrônico: o solicitante declarou que as informações são verdadeiras em " + d.emitido_em_br + ".", "");
  L.push("Atenciosamente,", d.solicitante.nome, "", "---", LGPD);
  return { para: m.destino, cc: d.solicitante.email, assunto, corpo: L.join("\n") };
}
