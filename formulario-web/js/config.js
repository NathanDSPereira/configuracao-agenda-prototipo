/**
 * Configuração e dados do formulário
 * Define CONFIG (Google, logo), limites, prioridades, os modelos CASU/Imaginamente (tipos e campos por tipo) e os textos de validação.
 * É o arquivo a editar para mudar tipos, campos, destinatários, código/revisão ou prioridades.
 */
"use strict";

// Quem hospeda a página pode definir window.CONFIGURACAO_AGENDA antes deste script, sem editar o código.
// Configurações gerais. Podem ser sobrescritas por window.CONFIGURACAO_AGENDA (definido antes dos scripts).
// Ajustes de quem hospeda a página (podem vir de window.CONFIGURACAO_AGENDA).
const CONFIG = Object.assign({
  googleClientId: "",     // ID do cliente OAuth (tipo "Aplicativo da Web"). Vazio = envio pelo Gmail desligado.
  dominioPermitido: "",   // opcional: domínio do Google Workspace, usado como dica no login
  logoDataUrl: ""         // opcional: logo em PNG/JPEG (data URL) para o cabeçalho do PDF
}, window.CONFIGURACAO_AGENDA || {});

// Limites e regras: máximo de configurações por envio, faixa do tempo de slot (min), tamanho mínimo das descrições e versão do modelo.
const MAX_ITENS = 10, SLOT_MIN = 5, SLOT_MAX = 180, DESC_MIN = 15, VERSAO = "v2";
// Níveis de prioridade. v = texto exibido; cls = classe de cor no CSS; cu = valor da prioridade no ClickUp (1 = Urgente ... 4 = Baixa); cor = RGB usado no PDF.
// Níveis de prioridade. `cu` é o número da prioridade no ClickUp (1 = Urgente ... 4 = Baixa); `cor` é usada no PDF.
const PRIORIDADES = [
  { v: "Urgente", cls: "urgente", cu: 1, cor: [0.80, 0.25, 0.15] },
  { v: "Alta",    cls: "alta",    cu: 2, cor: [0.70, 0.43, 0.00] },
  { v: "Normal",  cls: "normal",  cu: 3, cor: [0.20, 0.42, 0.70] },
  { v: "Baixa",   cls: "baixa",   cu: 4, cor: [0.35, 0.43, 0.40] }
];
// Busca os dados de uma prioridade pelo texto (ex.: prio('Alta').cu === 2).
// Busca os dados de uma prioridade pelo nome.
const prio = v => PRIORIDADES.find(p => p.v === v);

// Tipos e colunas conforme os formulários oficiais. Em cada tipo: [campo, obrigatório (1/0)].
// Modelos de formulário. Em cada tipo, a lista traz [campo, obrigatório?] na ordem em que aparecem. 'detalhe' é a descrição específica do tipo.
// Modelos de formulário. Em `tipos`, cada tipo lista seus campos extras como [campo, obrigatório (1/0)].
const MODELOS = {
  CASU: {
    rotulo: "CASU", titulo: "Configuração de Agenda - CASU", destino: "agenda.casu@instituicao.example", codigo: "", revisao: "",
    detalheRot: "Descreva a alteração permanente", detalheLinha: "Descrição da alteração permanente",
    tipos: {
      "Antecipação": [],
      "Bloqueio": [["bloqueio_inicio", 1], ["bloqueio_fim", 1], ["reposicao", 1], ["data_reposicao", 1]],
      "Ajustes tempo slot": [["novo_slot_min", 1]],
      "Alterações permanentes": [["detalhe", 1]]
    }
  },
  IMAGINAMENTE: {
    rotulo: "Imaginamente", titulo: "Configuração de Agenda - Imaginamente", destino: "agenda.imaginamente@instituicao.example", codigo: "", revisao: "",
    detalheRot: "Descreva o bloqueio ou a alteração permanente", detalheLinha: "Descrição do bloqueio ou alteração permanente",
    tipos: {
      "Trocas": [["paciente", 1], ["horario_anterior", 1], ["horario_atual", 1]],
      "Ajustes": [["paciente", 0], ["horario_anterior", 1], ["horario_atual", 1]],
      "Bloqueio": [["detalhe", 1]],
      "Alterações permanentes": [["detalhe", 1]]
    }
  }
};
// Catálogo dos campos: rótulo (rot), tipo de controle (t), tamanho máximo e se ocupa a linha inteira (cheia).
// Como cada campo é desenhado: rótulo (rot), tipo de controle (t), tamanho máximo, largura e ajuda.
const CAMPOS = {
  descricao:        { rot: "Descrição", t: "area", rows: 2, max: 300, cheia: 1 },
  data_regencia:    { rot: "Data de regência da alteração", t: "date" },
  bloqueio_inicio:  { rot: "Bloqueio: início", t: "date" },
  bloqueio_fim:     { rot: "Bloqueio: fim", t: "date" },
  reposicao:        { rot: "Reposição", t: "chips", ops: ["Sem reposição", "Com reposição"] },
  data_reposicao:   { rot: "Data de reposição", t: "date" },
  novo_slot_min:    { rot: "Alteração de tempo de atendimento (minutos)", t: "num" },
  paciente:         { rot: "Dados do paciente", t: "text", max: 160, cheia: 1, ajuda: "Informe apenas o necessário para identificar o paciente." },
  horario_anterior: { rot: "Horário anterior", t: "time" },
  horario_atual:    { rot: "Horário atual", t: "time" },
  detalhe:          { rot: null, t: "area", rows: 3, max: 600, cheia: 1 },
  observacoes:      { rot: "Observações", t: "area", rows: 2, max: 400, cheia: 1 }
};
// Mensagens de erro para campo obrigatório vazio.
const MSG_OBRIG = {
  bloqueio_inicio: "Informe o início do bloqueio.", bloqueio_fim: "Informe o fim do bloqueio.", reposicao: "Informe se haverá reposição.",
  data_reposicao: "Informe a data de reposição.", novo_slot_min: "Informe o novo tempo de atendimento, em minutos.",
  paciente: "Informe os dados do paciente.", horario_anterior: "Informe o horário anterior.", horario_atual: "Informe o horário atual."
};
// Texto de rodapé (e-mail e PDF) sobre a LGPD.
// Aviso de LGPD usado no rodapé do PDF e no fim do e-mail.
const LGPD = "Este documento é classificado conforme Lei nº 13.709, de 14 de agosto de 2018, que dispõe sobre a proteção de dados pessoais e altera a Lei nº 12.965, de 23 de abril de 2014 (Marco Civil).";
