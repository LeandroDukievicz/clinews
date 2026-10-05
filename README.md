# clinews

Prévia funcional de um leitor de notícias por RSS para o terminal. Na primeira abertura, você escolhe fontes sugeridas por assunto ou cola o endereço de um site. O `clinews` salva as fontes e mostra as notícias no terminal.

Landing page: [leandrodukievicz.github.io/clinews](https://leandrodukievicz.github.io/clinews/).

A landing page mostra capturas reais da lista de notícias, das sugestões de fontes, da leitura e do seletor de temas no modo de demonstração.
As versões para a galeria da Snap Store ficam em [assets/store-screenshots](assets/store-screenshots).

O ícone do aplicativo fica em [assets/clinews-snap-icon.png](assets/clinews-snap-icon.png). A interface do terminal abre direto nas fontes e notícias para aproveitar melhor o espaço de leitura.

```text
 CLINEWS  ●  5 não lidas  •  WatchAI
 FONTES (3)                   NOTÍCIAS (5)
 Todas as fontes        5     ● O céu desta semana
 Ciência                2     ● Por que o RSS ainda é útil
 Cultura                1     ● Livros para descobrir neste mês
 Tecnologia             2     ● Pesquisadores publicam novos resultados
                              ● Uma nova forma de acompanhar a web

 Prévia de demonstração: dados fictícios
 Tab painel  j/k mover  Enter ler  s sugestões  a link  r atualizar  d remover  t temas  q sair
```

## Instalar

O clinews está publicado na [Snap Store](https://snapcraft.io/clinews):

```bash
sudo snap install clinews
clinews
```

## Rodar a partir do código

Requer Python 3.10 ou superior. Entre na pasta do projeto:

```bash
cd ~/Projetos/clinews
python3 -m clinews --demo
```

O modo `--demo` usa notícias fictícias e não grava fontes ou matérias. A escolha do tema é salva também nesse modo. Para cadastrar sites reais e salvar suas notícias:

```bash
python3 -m clinews
```

Execute os comandos a partir de `~/Projetos/clinews`.

No GNOME, o lançador em [desktop/clinews.desktop](desktop/clinews.desktop) abre o Snap em uma janela de terminal com o título `clinews`.

Na primeira abertura, aparece uma lista de fontes sugeridas. Use `j`/`k` ou as setas, `Espaço` para marcar quantas quiser e `Enter` para adicioná-las. A tecla `a` nessa tela abre o cadastro manual; `Esc` permite seguir sem adicionar nada. Nenhuma sugestão é cadastrada sem sua escolha. Depois, use `s` para reabrir a lista a qualquer momento. Fontes já cadastradas aparecem marcadas e não são adicionadas de novo.

Para cadastrar um site próprio, pressione `a` e cole a URL do site ou do próprio feed. Se o site divulgar RSS/Atom na página, o endereço do feed é encontrado automaticamente. `r` busca notícias novas. `Tab` muda entre fontes e notícias; `j`/`k` ou as setas movem a seleção; `Enter` abre a notícia no leitor, com o link original ao final; `o` abre o link no navegador; `d` remove a fonte selecionada; `t` abre os temas; `q` sai. Dentro da leitura, `t` traduz o título e o resumo do feed do inglês para português e alterna de volta para o original.

## Tradução

A tradução é feita sob demanda pela [Google Cloud Translation API v2](https://cloud.google.com/translate). Ative a API em um projeto do Google Cloud e crie uma chave de API. Na primeira vez que pressionar `t` em uma notícia, cole a chave no campo oculto; o clinews a salva somente para seu usuário, com acesso restrito, e a reutiliza nas próximas traduções. Também é possível definir `CLINEWS_GOOGLE_TRANSLATE_API_KEY` antes de iniciar o programa:

```bash
export CLINEWS_GOOGLE_TRANSLATE_API_KEY='sua-chave-do-google-cloud'
python3 -m clinews
```

O Google Cloud oferece crédito mensal equivalente aos primeiros 500 mil caracteres de tradução; depois disso, o uso é cobrado por caractere conforme a [tabela de preços](https://cloud.google.com/translate/pricing). A API detecta o idioma de origem; o clinews traduz qualquer matéria que não esteja já em português. O idioma é lido do texto mais longo enviado, porque a detecção erra com frequência em títulos curtos. Traduções ficam em cache no banco local, então abrir de novo uma notícia já traduzida não faz outra solicitação. Somente o título e o resumo que vieram no RSS são enviados; artigos cujo feed não fornece resumo continuam limitados ao título. O tempo limite de conexão é de 15 segundos.

As sugestões incluem fontes em português e inglês de notícias, tecnologia, ciência, economia e cultura. Os endereços vêm das páginas das próprias fontes, como os [feeds da Agência Brasil](https://agenciabrasil.ebc.com.br/feed/), o [feed do Manual do Usuário](https://manualdousuario.net/acompanhe/) e os [feeds da NASA](https://www.nasa.gov/rss-feeds/). A disponibilidade de cada feed é conferida ao adicioná-lo; se um endereço deixar de funcionar, o app mostra o erro e continua com as outras fontes escolhidas.

## Temas

Pressione `t`, escolha com `j`/`k` ou as setas e pressione `Enter`. A prévia muda de cor enquanto você navega. `Esc` cancela. A escolha fica em `~/.config/clinews/config.json` (ou `$XDG_CONFIG_HOME/clinews/config.json`) e também vale para o modo de demonstração.

São oito temas: as paletas do [WatchAI](https://github.com/LeandroDukievicz/WatchAI),
com os mesmos nomes e os mesmos valores de cor nos dois aplicativos. O padrão é
o WatchAI, como lá.

| Tema | Cores |
| --- | --- |
| WatchAI | Quase preto `#05070D` com ciano elétrico `#00E5FF` e magenta |
| Light | Fundo branco `#FBFCFD` com texto escuro e acentos em teal |
| Dark | Cinza-azulado `#0D1117` com ciano suave, no estilo do GitHub escuro |
| Night Owl | Azul-marinho `#011627` com verde-água `#7FDBCA` e lilás |
| Vampire | Roxo, rosa e ciano da [paleta Dracula](https://draculatheme.com/contribute) |
| Cyberpunk | Preto arroxeado `#05010A` com ciano `#00F0FF` e magenta `#FF00A0` |
| Steampunk | Marrom escuro `#140F0A` com verdete, cobre e latão |
| Grey | Sem matiz: os papéis se separam apenas por brilho |

Em terminais de 256 cores, as cores são aproximadas à paleta do terminal. Em terminais de 8 cores, o aplicativo usa a opção disponível mais próxima.

Os dados são guardados em `~/.local/share/clinews/clinews.db` ou em `$XDG_DATA_HOME/clinews/clinews.db`, quando essa variável estiver definida. As notícias já recebidas continuam acessíveis sem conexão. O texto mostrado vem do resumo ou conteúdo enviado pelo feed; alguns sites oferecem apenas um trecho e exigem abrir o link para ler tudo.

## Pacote Snap

O manifesto em [snap/snapcraft.yaml](snap/snapcraft.yaml) usa `core24` e isolamento estrito. Ele solicita acesso à rede para buscar feeds e ao desktop para abrir links no navegador. O ícone da loja tem 512×512 pixels.

Para gerar e testar o pacote em uma máquina com Snapcraft e LXD configurados:

```bash
snapcraft pack --use-lxd
sudo snap install --dangerous ./clinews_0.2.5_amd64.snap
clinews --demo
```

A publicação é automática. O workflow
[snap.yml](.github/workflows/snap.yml) roda os testes, compila o pacote e envia
para a loja a cada push na `main`, soltando no canal `edge`. Uma tag `vX.Y.Z`
publica em `stable`, que é o canal que o público instala — a tag tem que dizer o
mesmo número que o `version` do `snapcraft.yaml`, e o workflow falha se os dois
discordarem.

As capturas da galeria da loja ficam em
[assets/store-screenshots](assets/store-screenshots), mas não viajam dentro do
pacote: trocá-las é manual, no painel da Snap Store.

No Snap, notícias e preferências ficam em `~/snap/clinews/common/`, separados da instalação Python comum e preservados entre revisões. O pacote não importa automaticamente dados da instalação anterior.

O projeto é proprietário e todos os direitos são reservados; veja [LICENSE](LICENSE). A chave da Google Cloud Translation inserida no primeiro uso fica em `~/snap/clinews/common/config/google-translate-api-key` nas instalações Snap, com permissão de leitura e escrita apenas para seu usuário.

Esta é uma prévia inicial: atualização manual, sem sincronização em segundo plano e sem download da página completa do artigo.
