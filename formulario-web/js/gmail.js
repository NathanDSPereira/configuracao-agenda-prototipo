/**
 * Envio pelo Gmail
 * Login Google (Identity Services) e criação do rascunho via API do Gmail, com o PDF anexado. Só funciona com CONFIG.googleClientId.
 */
"use strict";

// Fluxo: login Google (popup) -> rascunho criado na conta da pessoa, com corpo e PDF anexado -> link para abrir no Gmail.
// O escopo gmail.compose permite criar rascunhos; a pessoa revisa e clica em Enviar no próprio Gmail.
const b64 = bytes => { let s = ""; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); };
const b64Txt = s => b64(new TextEncoder().encode(s));
const em76 = s => s.replace(/(.{76})/g, "$1\r\n");
// Codifica o assunto em UTF-8 (RFC 2047) quando tem acentos.
// Codifica o assunto em UTF-8 (RFC 2047) para aceitar acentos.
function assuntoMIME(s) {
  s = s.replace(/[\r\n]+/g, " ");
  if (/^[\x20-\x7E]*$/.test(s)) return s;
  const partes = []; let atual = "", bytes = 0;
  for (const ch of s) { const n = new TextEncoder().encode(ch).length; if (bytes + n > 45) { partes.push(atual); atual = ""; bytes = 0; } atual += ch; bytes += n; }
  if (atual) partes.push(atual);
  return partes.map(p => "=?UTF-8?B?" + b64Txt(p) + "?=").join("\r\n ");
}
// Monta a mensagem completa (texto + PDF anexado) em base64url, formato exigido pela API do Gmail.
// Monta a mensagem de e-mail completa (texto + PDF anexado) em base64url, como a API do Gmail exige.
function montarMIME(o) {
  const fr = "=_agenda_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  const linhas = ["MIME-Version: 1.0", "To: " + o.para.replace(/[\r\n]+/g, " ")];
  if (o.cc) linhas.push("Cc: " + o.cc.replace(/[\r\n]+/g, " "));
  linhas.push("Subject: " + assuntoMIME(o.assunto), 'Content-Type: multipart/mixed; boundary="' + fr + '"', "",
    "--" + fr, "Content-Type: text/plain; charset=UTF-8", "Content-Transfer-Encoding: base64", "", em76(b64Txt(o.corpo)),
    "--" + fr, 'Content-Type: application/pdf; name="' + o.nomeAnexo + '"', 'Content-Disposition: attachment; filename="' + o.nomeAnexo + '"',
    "Content-Transfer-Encoding: base64", "", em76(b64(o.bytes)), "--" + fr + "--", "");
  return btoa(linhas.join("\r\n")).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
// Login Google: carrega a biblioteca sob demanda e guarda o token de acesso enquanto válido.
// Cache do carregamento do Google Identity Services e do token de acesso.
let promessaGIS = null, tokenGoogle = null;
// Carrega o script de login do Google uma única vez.
function carregarGIS() {
  if (window.google && window.google.accounts && window.google.accounts.oauth2) return Promise.resolve();
  if (!promessaGIS) promessaGIS = new Promise((ok, falha) => {
    const s = document.createElement("script"); s.src = "https://accounts.google.com/gsi/client"; s.async = true;
    s.onload = ok; s.onerror = () => { promessaGIS = null; falha(new Error("gis_indisponivel")); }; document.head.appendChild(s);
  });
  return promessaGIS;
}
// Abre o login/consentimento do Google e devolve o token (reaproveita o anterior se ainda válido).
// Abre o login do Google (popup) e devolve o token; reaproveita o token ainda válido.
function pedirToken() {
  if (tokenGoogle && tokenGoogle.exp > Date.now() + 30000) return Promise.resolve(tokenGoogle.token);
  return new Promise((ok, falha) => {
    const cfg = {
      client_id: CONFIG.googleClientId, scope: "https://www.googleapis.com/auth/gmail.compose", prompt: "select_account",
      callback: r => {
        if (r.error) return falha(Object.assign(new Error(r.error_description || r.error), { codigo: r.error }));
        tokenGoogle = { token: r.access_token, exp: Date.now() + (Number(r.expires_in) || 3000) * 1000 }; ok(tokenGoogle.token);
      },
      error_callback: e => falha(Object.assign(new Error(e.message || e.type), { codigo: e.type }))
    };
    if (CONFIG.dominioPermitido) cfg.hd = CONFIG.dominioPermitido;
    window.google.accounts.oauth2.initTokenClient(cfg).requestAccessToken();
  });
}
// Chamada autenticada à API do Gmail.
// Chamada autenticada à API do Gmail.
async function gmailFetch(url, token, corpo) {
  const r = await fetch(url, { method: corpo ? "POST" : "GET", headers: Object.assign({ Authorization: "Bearer " + token }, corpo ? { "Content-Type": "application/json" } : {}), body: corpo ? JSON.stringify(corpo) : undefined });
  if (!r.ok) throw Object.assign(new Error("http_" + r.status), { codigo: "http_" + r.status });
  return r.json();
}
// Traduz o erro em mensagem clara para o usuário.
// Traduz erros do Google em mensagens claras para o usuário.
function mensagemErroGmail(e) {
  const c = e && e.codigo;
  if (c === "popup_closed") return "Login cancelado. Nenhum rascunho foi criado.";
  if (c === "popup_failed_to_open") return "O navegador bloqueou a janela de login. Permita pop-ups para este site e tente de novo.";
  if (c === "access_denied") return "A permissão para criar rascunhos não foi concedida. Sem ela não é possível anexar o PDF.";
  if (c === "gis_indisponivel") return "Não foi possível carregar o login do Google. Verifique a conexão e tente de novo.";
  if (c === "http_401") { tokenGoogle = null; return "A sessão do Google expirou. Clique em Enviar pelo Gmail para entrar de novo."; }
  if (c === "http_403") return "O Google recusou a operação: a API do Gmail pode não estar ativada neste projeto, ou a conta não tem permissão.";
  return "Não foi possível criar o rascunho no Gmail. O PDF e o texto continuam disponíveis acima para envio manual.";
}
// Mostra o andamento/resultado do envio no quadro de status.
function statusGmail(html, tipo) { const el = $("#gmail-status"); el.className = "gstatus" + (tipo ? " " + tipo : ""); el.innerHTML = html; el.hidden = !html; }
// Fluxo do botão: login -> gera PDF -> cria o rascunho -> mostra o link para abrir no Gmail. Nada é enviado sem o usuário clicar em Enviar no Gmail.
// Fluxo completo: login -> cria rascunho com o PDF -> abre o rascunho no Gmail.
async function enviarGmail() {
  if (!CONFIG.googleClientId) { toast("Envio pelo Gmail indisponível: falta configurar o login Google."); return; }
  const btn = document.querySelector('[data-acao="gmail"]'); btn.disabled = true;
  try {
    statusGmail("Conectando ao Google…");
    await carregarGIS();
    const token = await pedirToken();
    statusGmail("Criando o rascunho com o PDF anexado…");
    const d = state.resultado.dados, e = state.resultado.email, bytes = await gerarPDF(d);
    const raw = montarMIME({ para: e.para, cc: e.cc, assunto: e.assunto, corpo: e.corpo, nomeAnexo: nomeArquivo(d), bytes });
    const [perfil, rascunho] = await Promise.all([
      gmailFetch("https://gmail.googleapis.com/gmail/v1/users/me/profile", token).catch(() => null),
      gmailFetch("https://gmail.googleapis.com/gmail/v1/users/me/drafts", token, { message: { raw } })
    ]);
    const conta = perfil && perfil.emailAddress, id = rascunho.message && rascunho.message.id;
    const url = "https://mail.google.com/mail/u/" + (conta ? encodeURIComponent(conta) : "0") + "/#drafts" + (id ? "?compose=" + encodeURIComponent(id) : "");
    statusGmail('<div><strong>Rascunho criado' + (conta ? " na conta " + esc(conta) : "") + '.</strong> Ele já tem o texto e o PDF anexado. Revise o destinatário e o assunto e clique em Enviar.</div>' +
      '<div><a class="btn btn-primario" id="lnk-gmail" href="' + esc(url) + '" target="_blank" rel="noopener">Abrir rascunho no Gmail</a></div>', "ok");
    try { window.open(url, "_blank", "noopener"); } catch (_) { /* o botão acima cobre o bloqueio de pop-up */ }
  } catch (err) {
    if (!["popup_closed", "access_denied"].includes(err && err.codigo)) console.error(err);
    statusGmail(esc(mensagemErroGmail(err)), "erro");
  } finally { btn.disabled = false; }
}
