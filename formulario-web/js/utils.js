/**
 * Utilidades
 * Funções pequenas e sem estado: seletor, escape de HTML, datas e atalhos.
 */
"use strict";

const $ = (s, r) => (r || document).querySelector(s);
// Escapa texto antes de colocá-lo em HTML (evita injeção de código).
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const p2 = n => String(n).padStart(2, "0");
// Datas: converte Date para 'AAAA-MM-DD' (formato dos campos de data) e formata em padrão brasileiro.
const isoDe = d => d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate());
const hojeISO = () => isoDe(new Date());
const br = iso => iso ? iso.split("-").reverse().join("/") : "";
const dataBR = d => p2(d.getDate()) + "/" + p2(d.getMonth() + 1) + "/" + d.getFullYear();
const dataHoraBR = d => dataBR(d) + " " + p2(d.getHours()) + ":" + p2(d.getMinutes());
// Verdadeiro se o usuário pediu menos movimento (desliga a rolagem suave).
const reduzMov = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
// Modelo escolhido na tela (CASU ou IMAGINAMENTE).
const modeloAtual = () => MODELOS[state.modelo];
