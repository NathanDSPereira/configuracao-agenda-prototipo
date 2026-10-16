/**
 * Estado da tela
 * Objeto `state` (modelo escolhido, cabeçalho, lista de configurações, aceite) e funções que o consultam.
 */
"use strict";

// Estado da tela. Cada configuração recebe um id único (i1, i2, ...) usado nos ids dos campos.
// Contador para gerar ids únicos das configurações (i1, i2, ...).
let seq = 0;
// Cria uma configuração vazia.
const novoItem = () => ({ id: "i" + (++seq), tipo: "", prioridade: "", descricao: "", data_regencia: "", bloqueio_inicio: "", bloqueio_fim: "",
  reposicao: "", data_reposicao: "", novo_slot_min: "", paciente: "", horario_anterior: "", horario_atual: "", detalhe: "", observacoes: "" });
// state.h = dados do solicitante; itens = configurações; tentou = já clicou em Finalizar; tocados = campos já visitados (erros só aparecem depois).
// Estado da tela: tudo o que o usuário preencheu e o que já foi "tocado".
const state = { modelo: "CASU", h: { solicitante: "", unidade: "", email: "", resumo: "" }, itens: [novoItem()],
  aceite: false, tentou: false, tocados: new Set(), resultado: null };

// Campos exibidos para o tipo escolhido. A data de reposição só aparece com 'Com reposição'.
// Campos extras do tipo escolhido (a data de reposição só existe quando há reposição).
const camposDoTipo = it => !it.tipo ? [] : modeloAtual().tipos[it.tipo].filter(x => x[0] !== "data_reposicao" || it.reposicao === "Com reposição");
// Rótulo de um campo ('detalhe' muda conforme o modelo).
// Rótulo de um campo; o campo `detalhe` muda de nome conforme o modelo.
const rotuloCampo = c => c === "detalhe" ? modeloAtual().detalheRot : CAMPOS[c].rot;
// Indica se o campo recebe o asterisco de obrigatório.
// Informa se um campo é obrigatório na configuração (define o asterisco e o "(opcional)").
function obrigatorio(it, c) {
  if (["tipo", "prioridade", "descricao", "data_regencia"].includes(c)) return true;
  if (c === "observacoes") return false;
  const def = (modeloAtual().tipos[it.tipo] || []).find(x => x[0] === c);
  return !!(def && def[1]);
}
