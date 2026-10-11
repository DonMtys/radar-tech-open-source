# Radar Tech Bot no Google Apps Script

Esta versão mantém o projeto Python intacto e move somente a publicação automática para o Google Apps Script.

## Configuração

1. Acesse <https://script.google.com> e crie um **Novo projeto**.
2. Substitua o conteúdo de `Código.gs` pelo conteúdo de `Code.gs` desta pasta.
3. Abra **Configurações do projeto** e, em **Propriedades do script**, adicione:
   - `TELEGRAM_BOT_TOKEN`: token do bot.
   - `TELEGRAM_CHAT_ID`: identificador do canal ou grupo.
   - `GITHUB_TOKEN`: opcional; aumenta o limite da API do GitHub.
4. No seletor de funções, escolha `previewNextPost` e clique em **Executar**. Autorize o acesso solicitado e confira o conteúdo nos registros.
5. Escolha `runRadarBot` e clique em **Executar** para publicar uma mensagem real de teste.
6. Depois do teste, escolha `installRadarTrigger` e clique em **Executar** uma única vez.

O gatilho chama `runRadarBot` a cada 30 minutos. O estado é salvo nas propriedades do script para evitar duplicações. O token nunca deve ser colocado diretamente no arquivo `Code.gs`.
