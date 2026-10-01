# clinews

![Logo em pixel art do clinews](assets/clinews-logo.png)

Prévia funcional de um leitor de notícias por RSS para o terminal. Você cola o endereço de um site uma vez; o `clinews` procura o feed RSS/Atom, salva a fonte e mostra as notícias no terminal.

O arquivo [assets/clinews-logo.png](assets/clinews-logo.png) é o logo e também o ícone do aplicativo. No terminal, o cabeçalho mostra uma versão colorida em pixels do mesmo símbolo. Em terminais sem suporte a cores, ela aparece em uma só cor.

```text
 CLINEWS  ●  5 não lidas

          ▉ ▉
    ▉▉▉▉  ▉▉▉
   ▉▉▉▉▉▉  ▉▉   C L I N E W S
   ▉▉▉▉▉▉   ▉   Notícias dos sites que você escolhe
   ▉▉▉▉▉▉
   ▉▉▉▉▉▉

 FONTES                    NOTÍCIAS
 Todas as fontes       5    ● Uma nova forma de acompanhar a web
 Tecnologia            2    ● Por que o RSS ainda é útil
 Ciência               2    ● Pesquisadores publicam novos resultados
 Cultura               1    ● O céu desta semana
                            ● Livros para descobrir neste mês

 Cole um site com 'a' para começar.
 Tab painel   j/k mover   Enter ler   a adicionar   r atualizar   d remover   t temas   q sair
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

Pressione `a` e cole a URL de um site ou do próprio feed. Se o site divulgar RSS/Atom na página, o endereço do feed é encontrado automaticamente. `r` busca notícias novas. `Tab` muda entre fontes e notícias; `j`/`k` ou as setas movem a seleção; `Enter` abre a notícia no leitor, com o link original ao final; `o` abre o link no navegador; `d` remove a fonte selecionada; `t` abre os temas; `q` sai.

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

Esta é uma prévia inicial: atualização manual, sem sincronização em segundo plano e sem download da página completa do artigo.
