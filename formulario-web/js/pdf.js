/**
 * Geração do PDF
 * Desenha o PDF no navegador com pdf-lib, no layout do formulário oficial (cabeçalho, tipos marcados, blocos por configuração, assinatura).
 */
"use strict";

// Fontes padrão do PDF só codificam WinAnsi: o que não existe vira "?" para nunca falhar com texto digitado.
// Troca por '?' caracteres que a fonte padrão do PDF não suporta (como emoji), para nunca falhar com texto digitado.
// Normaliza texto para o PDF: as fontes padrão só aceitam WinAnsi; o que não existe vira "?" (nunca falha).
const limpa = s => String(s == null ? "" : s).replace(/\r/g, "").replace(/\t/g, " ")
  .replace(/[^\n\x20-\x7E\u00A0-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\u2022\u2026\u20AC\u2122]/gu, "?");
// Quebra texto em linhas que cabem na largura (larg) com a fonte e tamanho dados; palavras muito longas são cortadas.
// Quebra um texto em linhas que cabem na largura dada, na fonte e tamanho informados.
function quebra(txt, fonte, tam, larg) {
  const saida = [];
  limpa(txt).split("\n").forEach(par => {
    const palavras = par.split(/\s+/).filter(Boolean);
    if (!palavras.length) { saida.push(""); return; }
    let atual = "";
    palavras.forEach(w => {
      const tent = atual ? atual + " " + w : w;
      if (fonte.widthOfTextAtSize(tent, tam) <= larg) { atual = tent; return; }
      if (atual) saida.push(atual);
      if (fonte.widthOfTextAtSize(w, tam) <= larg) { atual = w; return; }
      let pedaco = "";
      for (const ch of w) { if (fonte.widthOfTextAtSize(pedaco + ch, tam) > larg) { saida.push(pedaco); pedaco = ch; } else pedaco += ch; }
      atual = pedaco;
    });
    saida.push(atual);
  });
  return saida;
}

// Desenha o PDF (A4) e devolve os bytes. Medidas em pontos, origem no canto inferior esquerdo (y cresce para cima).
// Desenha o PDF (A4) e devolve os bytes. Páginas extras são criadas quando o conteúdo não cabe.
async function gerarPDF(d) {
  if (!window.PDFLib) throw new Error("pdf-lib não carregou");
  const { PDFDocument, StandardFonts, rgb } = window.PDFLib;
  const m = MODELOS[d.modelo];
  const doc = await PDFDocument.create();
  doc.setTitle(m.titulo + " - " + d.protocolo);
  doc.setCreator("Configuração de Agenda (protótipo)");
  const reg = await doc.embedFont(StandardFonts.Helvetica), neg = await doc.embedFont(StandardFonts.HelveticaBold), mono = await doc.embedFont(StandardFonts.Courier);
  let logo = null;
  if (CONFIG.logoDataUrl) {
    try {
      const partes = CONFIG.logoDataUrl.split(","), bin = atob(partes[1]), bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
      logo = /png/i.test(partes[0]) ? await doc.embedPng(bytes) : await doc.embedJpg(bytes);
    } catch (_) { logo = null; }
  }
  const W = 595.28, H = 841.89, M = 42.5, CW = W - 2 * M, LBL = 160, RODAPE = 72;
  const C = { linha: rgb(0.62, 0.68, 0.66), cinza: rgb(0.93, 0.95, 0.94), verde: rgb(0.88, 0.95, 0.92), preto: rgb(0, 0, 0), suave: rgb(0.3, 0.3, 0.3) };
  let page = doc.addPage([W, H]), y = H - M;
  const caixa = (x, topo, w, h, fill) => page.drawRectangle({ x, y: topo - h, width: w, height: h, borderColor: C.linha, borderWidth: 0.7, color: fill });
  const texto = (s, x, base, o) => { o = o || {}; page.drawText(limpa(s), { x, y: base, font: o.f || reg, size: o.size || 9, color: o.color || C.preto }); };

  // cabeçalho no estilo do formulário oficial: logo | FORMULÁRIO | Código/Revisão/Página, e linha do título
  const topoCab = y;
  caixa(M, y, 84, 50);
  if (logo) {
    const s = Math.min(72 / logo.width, 38 / logo.height);
    page.drawImage(logo, { x: M + 42 - logo.width * s / 2, y: y - 25 - logo.height * s / 2, width: logo.width * s, height: logo.height * s });
  } else texto("LOGO", M + 42 - neg.widthOfTextAtSize("LOGO", 10) / 2, y - 29, { f: neg, size: 10 });
  caixa(M + 84, y, CW - 84 - 150, 50);
  texto("FORMULÁRIO", M + 84 + (CW - 84 - 150) / 2 - neg.widthOfTextAtSize("FORMULÁRIO", 11) / 2, y - 29, { f: neg, size: 11 });
  const xr = W - M - 150;
  caixa(xr, y, 150, 50);
  texto("Código:", xr + 8, y - 14, { f: neg, size: 8.5 }); texto(m.codigo, xr + 50, y - 14, { size: 8.5 });
  texto("Revisão:", xr + 8, y - 27, { f: neg, size: 8.5 }); texto(m.revisao, xr + 50, y - 27, { size: 8.5 });
  texto("Página:", xr + 8, y - 40, { f: neg, size: 8.5 });
  y -= 50;
  caixa(M, y, CW, 26);
  texto(m.titulo, M + 8, y - 17, { f: neg, size: 11 });
  const prot = d.protocolo, wp = mono.widthOfTextAtSize(prot, 8.5);
  texto(prot, W - M - 8 - wp, y - 17, { f: mono, size: 8.5, color: C.suave });
  y -= 26 + 16;

  const garantir = h => {
    if (y - h < RODAPE) {
      page = doc.addPage([W, H]); y = H - M;
      texto(m.titulo + " - Protocolo " + d.protocolo + " (continuação)", M, y - 8, { size: 8, color: C.suave });
      y -= 24;
    }
  };
  const barra = (txt, fill, dir) => {
    garantir(60);
    caixa(M, y, CW, 20, fill);
    texto(txt, M + 8, y - 14, { f: neg, size: 9 });
    if (dir) texto(dir.t, W - M - 8 - neg.widthOfTextAtSize(dir.t, 9), y - 14, { f: neg, size: 9, color: dir.cor });
    y -= 20;
  };
  const linha = (rot, val) => {
    const lv = quebra(val || "-", reg, 9, CW - LBL - 12), lr = quebra(rot, neg, 8, LBL - 12);
    const h = Math.max(22, Math.max(lv.length * 11.2, lr.length * 10) + 11);
    garantir(h);
    caixa(M, y, LBL, h, C.cinza); caixa(M + LBL, y, CW - LBL, h);
    lr.forEach((t, i) => texto(t, M + 6, y - 14 - i * 10, { f: neg, size: 8 }));
    lv.forEach((t, i) => texto(t, M + LBL + 6, y - 14 - i * 11.2, { size: 9 }));
    y -= h;
  };

  // 1. TIPO (marca os tipos usados)
  barra("1. TIPO", C.verde);
  const tipos = Object.keys(m.tipos), usados = new Set(d.itens.map(i => i.tipo));
  garantir(60);
  const hTipo = 20 * Math.ceil(tipos.length / 2) + 10;
  caixa(M, y, CW, hTipo);
  tipos.forEach((t, k) => {
    const cx = M + 14 + (k % 2) * (CW / 2), cy = y - 20 - Math.floor(k / 2) * 20;
    page.drawRectangle({ x: cx, y: cy - 1, width: 9, height: 9, borderColor: C.preto, borderWidth: 0.8 });
    if (usados.has(t)) {
      page.drawLine({ start: { x: cx + 1.5, y: cy + 0.5 }, end: { x: cx + 7.5, y: cy + 6.5 }, thickness: 1.2, color: C.preto });
      page.drawLine({ start: { x: cx + 1.5, y: cy + 6.5 }, end: { x: cx + 7.5, y: cy + 0.5 }, thickness: 1.2, color: C.preto });
    }
    texto(t, cx + 16, cy, { size: 9.5 });
  });
  y -= hTipo + 16;

  // 2. DADOS DA SOLICITAÇÃO
  barra("2. DADOS DA SOLICITAÇÃO", C.verde);
  linha("Solicitante (profissional)", d.solicitante.nome);
  linha("Unidade de atendimento", d.solicitante.unidade);
  linha("E-mail do solicitante", d.solicitante.email);
  linha("Data da solicitação e hora", d.emitido_em_br);
  linha("Resumo", d.resumo);
  d.itens.forEach(it => {
    y -= 12;
    const pr = prio(it.prioridade);
    barra("Configuração " + it.n + " de " + d.itens.length + " - " + it.tipo, C.cinza, { t: "Prioridade: " + it.prioridade, cor: rgb(pr.cor[0], pr.cor[1], pr.cor[2]) });
    pares(it, m).slice(1).forEach(p => linha(p[0], p[1]));
  });
  y -= 18;

  // 3. Data e assinatura
  barra("3. DATA E ASSINATURA", C.verde);
  linha("Data", d.data_br);
  linha("Assinatura do solicitante", d.solicitante.nome + " (aceite eletrônico)");
  linha("Declaração", "O solicitante declara que as informações acima são verdadeiras.");

  const pgs = doc.getPages();
  pgs[0].drawText("1/" + pgs.length, { x: xr + 50, y: topoCab - 40, font: reg, size: 8.5, color: C.preto });
  pgs.forEach((pg, i) => {
    pg.drawLine({ start: { x: M, y: 58 }, end: { x: W - M, y: 58 }, thickness: 0.6, color: C.linha });
    quebra(LGPD, reg, 6.5, CW - 70).forEach((t, k) => pg.drawText(t, { x: M, y: 47 - k * 8, font: reg, size: 6.5, color: C.suave }));
    const num = "Página " + (i + 1) + "/" + pgs.length;
    pg.drawText(num, { x: W - M - reg.widthOfTextAtSize(num, 7), y: 47, font: reg, size: 7, color: C.suave });
  });
  return await doc.save(); // Uint8Array
}
