# Configuração de agenda: protótipo

Protótipo para substituir o pedido de configuração de agenda enviado por PDF/e-mail por um **formulário web com campos obrigatórios**, que bloqueia o envio incompleto e gera o PDF e o texto do e-mail. Dois modelos: **CASU** e **Imaginamente**, cada um com **prioridade/urgência** por configuração. Não escreve na agenda real.

## Estrutura

```
formulario-web/   página única (HTML + JS), sem build; PDF gerado no navegador com pdf-lib
leitor-pdf/       caminho de contingência: gera o PDF preenchível (AcroForm) e lê/valida PDFs recebidos
  modelos/  exemplos/
testes/           testes ponta a ponta (Playwright) e do leitor de PDF
```

## Formulário web

Abra `formulario-web/configuracao_agenda.html` no navegador (usa o pdf-lib pelo CDN jsDelivr).
Ajustes ficam no topo do script (`CONFIG`), ou em `window.CONFIGURACAO_AGENDA` definido antes do script:

| Chave | Uso |
|---|---|
| `googleClientId` | ID de cliente OAuth (Aplicativo da Web). Vazio = botão "Enviar pelo Gmail" desligado |
| `dominioPermitido` | domínio do Google Workspace, como dica no login |
| `logoDataUrl` | logo PNG/JPEG para o cabeçalho do PDF |

Em `MODELOS` ficam os tipos e campos de cada formulário; `destino`, `codigo` e `revisao` estão com valores de exemplo e devem ser trocados.

### Envio pelo Gmail
Login Google (Google Identity Services) → rascunho criado pela API do Gmail com corpo e PDF anexado → abre no Gmail. Requer página hospedada em **https**, API do Gmail ativada, cliente OAuth com a origem autorizada, e o escopo `gmail.compose` (**restrito**: use app "Interno" no Workspace para dispensar a verificação). O link de abertura do rascunho não é documentado pelo Google.

## Saída estruturada
Cada envio gera um JSON (protocolo, solicitante, resumo, itens com `prioridade` e `prioridade_clickup` 1=Urgente a 4=Baixa) pronto para o fluxo n8n → banco → ClickUp → BI.

## Testes
```
pip install -r requirements.txt && playwright install chromium
npm install                      # traz o pdf-lib local para os testes
python3 testes/testar_formulario.py
python3 testes/testar_ciclo.py
```

## Privacidade (LGPD)
"Dados do paciente" é dado sensível de saúde: peça só o mínimo. Os PDFs oficiais da instituição **não** estão neste repositório.
