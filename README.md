# clinews

![Logo em pixel art do clinews](assets/clinews-logo.png)

Prévia funcional de um leitor de notícias por RSS para o terminal. Na primeira abertura, você escolhe fontes sugeridas por assunto ou cola o endereço de um site. O `clinews` salva as fontes e mostra as notícias no terminal.

Landing page: [leandrodukievicz.github.io/clinews](https://leandrodukievicz.github.io/clinews/).

O arquivo [assets/clinews-logo.png](assets/clinews-logo.png) é o logo do projeto e o ícone do aplicativo. A interface do terminal abre direto nas fontes e notícias para aproveitar melhor o espaço de leitura.

```text
 CLINEWS  ●  5 não lidas  •  Midnight
 FONTES (3)                NOTÍCIAS (5)
 Todas as fontes       5    ● Uma nova forma de acompanhar a web
 Tecnologia            2    ● Por que o RSS ainda é útil
 Ciência               2    ● Pesquisadores publicam novos resultados
 Cultura               1    ● O céu desta semana
                            ● Livros para descobrir neste mês

 Tab painel  j/k mover  Enter ler  s sugestões  a link  r atualizar  d remover  t temas  q sair
```

## Experimentar a prévia

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

Na primeira abertura, aparece uma lista de fontes sugeridas. Use `j`/`k` ou as setas, `Espaço` para marcar quantas quiser e `Enter` para adicioná-las. A tecla `a` nessa tela abre o cadastro manual; `Esc` permite seguir sem adicionar nada. Nenhuma sugestão é cadastrada sem sua escolha. Depois, use `s` para reabrir a lista a qualquer momento. Fontes já cadastradas aparecem marcadas e não são adicionadas de novo.

Para cadastrar um site próprio, pressione `a` e cole a URL do site ou do próprio feed. Se o site divulgar RSS/Atom na página, o endereço do feed é encontrado automaticamente. `r` busca notícias novas. `Tab` muda entre fontes e notícias; `j`/`k` ou as setas movem a seleção; `Enter` abre a notícia no leitor, com o link original ao final; `o` abre o link no navegador; `d` remove a fonte selecionada; `t` abre os temas; `q` sai. Dentro da leitura, `t` traduz o título e o resumo do feed do inglês para português e alterna de volta para o original.

## Tradução

A tradução é feita sob demanda pela DeepL API. Crie uma chave em um plano da [DeepL API](https://www.deepl.com/pro#developer). Na primeira vez que pressionar `t` em uma notícia, cole a chave no campo oculto; o clinews a salva somente para seu usuário, com acesso restrito, e a reutiliza nas próximas traduções. Também é possível definir `CLINEWS_DEEPL_API_KEY` antes de iniciar o programa:

```bash
export CLINEWS_DEEPL_API_KEY='sua-chave-da-deepl-api'
python3 -m clinews
```

O programa usa por padrão o endpoint da DeepL API Free. Para uma chave Pro, configure também `CLINEWS_DEEPL_API_URL=https://api.deepl.com/v2/translate`. A API detecta o idioma de origem; o clinews só mostra a tradução se o texto for identificado como inglês. Traduções ficam em cache no banco local, então abrir de novo uma notícia já traduzida não faz outra solicitação. Somente o título e o resumo que vieram no RSS são enviados; artigos cujo feed não fornece resumo continuam limitados ao título.

As sugestões incluem fontes em português e inglês de notícias, tecnologia, ciência, economia e cultura. Os endereços vêm das páginas das próprias fontes, como os [feeds da Agência Brasil](https://agenciabrasil.ebc.com.br/feed/), o [feed do Manual do Usuário](https://manualdousuario.net/acompanhe/) e os [feeds da NASA](https://www.nasa.gov/rss-feeds/). A disponibilidade de cada feed é conferida ao adicioná-lo; se um endereço deixar de funcionar, o app mostra o erro e continua com as outras fontes escolhidas.

## Temas

Pressione `t`, escolha com `j`/`k` ou as setas e pressione `Enter`. A prévia muda de cor enquanto você navega. `Esc` cancela. A escolha fica em `~/.config/clinews/config.json` (ou `$XDG_CONFIG_HOME/clinews/config.json`) e também vale para o modo de demonstração.

| Tema | Cores |
| --- | --- |
| Vampire | Roxo, rosa e ciano da [paleta Dracula](https://draculatheme.com/contribute) |
| NeoTokio | Rosa neon, ciano e amarelo em fundo escuro, inspirado em cyberpunk |
| OldCity | Cobre, bronze e sépia, inspirado em steampunk |
| FullDark | Preto com verdes vivos |
| SunMode | Fundo branco com texto escuro |
| Midnight | Azul e roxo da [paleta Night Owl](https://github.com/sdras/night-owl-vscode-theme/blob/main/themes/Night%20Owl-color-theme.json) |
| Zenmode | Verdes suaves em fundo claro |

Em terminais de 256 cores, as cores são aproximadas à paleta do terminal. Em terminais de 8 cores, o aplicativo usa a opção disponível mais próxima.

Os dados são guardados em `~/.local/share/clinews/clinews.db` ou em `$XDG_DATA_HOME/clinews/clinews.db`, quando essa variável estiver definida. As notícias já recebidas continuam acessíveis sem conexão. O texto mostrado vem do resumo ou conteúdo enviado pelo feed; alguns sites oferecem apenas um trecho e exigem abrir o link para ler tudo.

## Pacote Snap

O manifesto em [snap/snapcraft.yaml](snap/snapcraft.yaml) usa `core24` e isolamento estrito. Ele solicita acesso à rede para buscar feeds e ao desktop para abrir links no navegador. O ícone da loja é uma versão de 512×512 do logo do projeto.

Para gerar e testar o pacote em uma máquina com Snapcraft e LXD configurados:

```bash
snapcraft pack --use-lxd
sudo snap install --dangerous ./clinews_0.2.1_amd64.snap
clinews --demo
```

No Snap, notícias e preferências ficam em `~/snap/clinews/common/`, separados da instalação Python comum e preservados entre revisões. O pacote não importa automaticamente dados da instalação anterior.

O projeto é proprietário e todos os direitos são reservados; veja [LICENSE](LICENSE). A chave da DeepL inserida no primeiro uso fica em `~/snap/clinews/common/config/deepl-api-key` nas instalações Snap, com permissão de leitura e escrita apenas para seu usuário.

Esta é uma prévia inicial: atualização manual, sem sincronização em segundo plano e sem download da página completa do artigo.
