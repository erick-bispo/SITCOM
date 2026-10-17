"""
SITCON | Insights de negócio para os donos do inventário de sinalização
Foco: risco para a operação, causa raiz, decisões, esforço e plano — não o dado em si.
Os números vêm da camada validada sitcon_dados (mesma do painel analítico app.py).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import sitcon_dados as sd

st.set_page_config(page_title="SITCON | Insights para decisão", page_icon="🚆", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 3.6rem;}
.cap {color:#6B7785; font-size:.82rem; letter-spacing:.09em; text-transform:uppercase;}
.headline {font-size:2.1rem; font-weight:700; line-height:1.2; color:#1F2D3D; margin:.2rem 0 .7rem 0;}
.lead {font-size:1.1rem; color:#3A4654; line-height:1.55; margin-bottom:1rem;}
.card {border:1px solid #E3E7EC; border-radius:12px; padding:16px 18px; height:100%; background:#fff;}
.card .t {font-size:.78rem; letter-spacing:.07em; text-transform:uppercase; color:#6B7785; margin-bottom:6px; font-weight:600;}
.card .c {font-size:1rem; color:#26313D; line-height:1.5;}
.risco {border-top:5px solid #D46A6A;} .sig {border-top:5px solid #E5A84B;} .dec {border-top:5px solid #36A18B;}
.big {font-size:3rem; font-weight:800; line-height:1; color:#C0504D;}
.big.ok {color:#2E8B6E;} .big.neu {color:#1F2D3D;}
.bigl {color:#4A5562; font-size:1rem; margin-top:6px;}
.ask {background:#1F2D3D; color:#fff; border-radius:12px; padding:18px 20px; margin-top:6px;}
.ask .t {font-size:.8rem; letter-spacing:.08em; text-transform:uppercase; opacity:.75; margin-bottom:8px;}
.ask ol {margin:0 0 0 1.1rem; padding:0;} .ask li {margin:5px 0; font-size:1.02rem;}
.linha {display:flex; gap:14px; align-items:flex-start; border-bottom:1px solid #EEF1F4; padding:10px 0;}
.linha .q {min-width:110px; font-weight:700; color:#1F2D3D;}
.tag {display:inline-block; font-size:.75rem; padding:2px 8px; border-radius:20px; background:#EEF1F4; color:#4A5562; margin-left:6px;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Preparando os insights...")
def carregar():
    r = sd.processar()
    r["legado"] = sd.metricas_painel_original(r["bruto"])
    return r


R = carregar()
bruto, df, erros, legado = R["bruto"], R["corrigido"], R["erros"], R["legado"]
pend = erros[erros["acao"] == sd.ACAO_PEND]
pontos = df[df["valor"].notna() & df["valor"].ne("-")].copy()

# --- indicadores de negócio --------------------------------------------------
N_EQ = bruto["bloco_id"].nunique()
N_EQ_ALTA = erros[erros.severidade == "Alta"]["bloco"].nunique()
N_CDV = df[df.tipo == "CDV"]["equipamento"].nunique()
N_ESCONDIDOS = N_CDV - legado["grupos_cdv"]
EVITAVEIS = erros["regra"].isin(["E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10"]).mean()
SEM_CAMPO = (len(erros) - len(pend)) / len(erros)
CONFLITOS = erros[erros.regra == "E17"]["detalhe"].str.extract(r"Ponto (.+?) usado")[0].nunique()

n12 = pontos[(pontos.funcao == "N12-CTP") & (pontos.nivel == "Locação")] \
    .groupby(["locacao", "valor"])["equipamento"].apply(set)
criticos = n12[n12.map(len) >= 6]
CDV_EM_CRITICOS = len(set().union(*criticos.values)) if len(criticos) else 0
MAX_N12 = int(n12.map(len).max())

p = pend.merge(df[["arquivo", "celula", "locacao", "nivel"]].drop_duplicates(["arquivo", "celula"]),
               on=["arquivo", "celula"], how="left", suffixes=("", "_d"))
p["onde"] = p["locacao"].fillna(p["nivel_d"]).fillna(p["nivel"])
p.loc[p["onde"].isin(["Armário TB", "Interface 2"]), "onde"] = "Sala técnica"
p.loc[p.regra.isin(["E01", "E18"]), "onde"] = "Escritório (projeto)"
ROTA = p.groupby("onde").agg(itens=("id_erro", "size"), alta=("severidade", lambda s: int((s == "Alta").sum()))) \
    .sort_values(["itens"], ascending=False)
CAMPO = ROTA.drop(index="Escritório (projeto)", errors="ignore")
TOP3_CAMPO = CAMPO.head(3)
TOP3_SHARE = TOP3_CAMPO["itens"].sum() / CAMPO["itens"].sum()

arm = pontos[pontos.nivel == "Armário TB"]
TB2_PCT = (arm["armario"] == "TB2").mean()
itf = pontos[pontos.nivel == "Interface 2"].dropna(subset=["bastidor"])
LIVRES = [f"B{i:02d}" for i in range(1, 52) if f"B{i:02d}" not in set(itf["bastidor"])]


def pct(x):
    return f"{x:.0%}"


def cabecalho(cap, headline, lead):
    st.markdown(f'<div class="cap">{cap}</div><div class="headline">{headline}</div><div class="lead">{lead}</div>',
                unsafe_allow_html=True)


def tres(risco, significa, decisao):
    a, b, c = st.columns(3)
    a.markdown(f'<div class="card risco"><div class="t">O que descobrimos</div><div class="c">{risco}</div></div>', unsafe_allow_html=True)
    b.markdown(f'<div class="card sig"><div class="t">O que isso significa para a operação</div><div class="c">{significa}</div></div>', unsafe_allow_html=True)
    c.markdown(f'<div class="card dec"><div class="t">Decisão recomendada</div><div class="c">{decisao}</div></div>', unsafe_allow_html=True)


def numero(col, v, legenda, tipo=""):
    col.markdown(f'<div class="big {tipo}">{v}</div><div class="bigl">{legenda}</div>', unsafe_allow_html=True)


def evidencia(texto):
    with st.expander("Evidência nos dados"):
        st.markdown(texto)


# --- navegação ----------------------------------------------------------------
CAPS = [
    "Para decidir hoje",
    "1 · Risco na intervenção",
    "2 · Causa raiz: o processo",
    "3 · Ativos sem identidade",
    "4 · Risco concentrado",
    "5 · Sanear é rápido",
    "6 · Capacidade e expansão",
    "7 · Plano e metas",
    "Anexo · Método e limites",
]
if "cap_nome" not in st.session_state:
    st.session_state.cap_nome = CAPS[0]


def ir(d):
    st.session_state.cap_nome = CAPS[CAPS.index(st.session_state.cap_nome) + d]


st.sidebar.markdown("### 🚆 SITCON")
st.sidebar.caption("Inventário de sinalização · Vias 1 e 2")
st.sidebar.radio("Roteiro", CAPS, key="cap_nome")
with st.sidebar.expander("Glossário"):
    st.markdown("""
- **Circuito de via (CDV):** detecta a presença de trem num trecho. Se falha, o trecho aparece como ocupado.
- **Borne:** ponto físico onde um fio é conectado.
- **Locação:** caixa de campo, ao lado da via.
- **Sala técnica:** armários de bornes (TB) e bastidores de interface.
- **Barramento N12:** alimentação comum a vários circuitos numa locação.
""")
cap = CAPS.index(st.session_state.cap_nome)

# ==============================================================================
if cap == 0:
    cabecalho("Resumo para decisão",
              "O inventário de sinalização não é seguro para orientar intervenções — e corrigir isso cabe numa campanha curta",
              "Revisamos o levantamento das vias 1 e 2 como se ele fosse usado amanhã por uma equipe de manutenção "
              "ou por um projeto de modernização. A conclusão cabe em três números.")
    a, b, c = st.columns(3)
    numero(a, pct(N_EQ_ALTA / N_EQ), "dos equipamentos têm pelo menos um erro capaz de levar a equipe ao borne errado")
    numero(b, pct(CDV_EM_CRITICOS / N_CDV), f"dos circuitos de via dependem de só {len(criticos)} pontos de alimentação", "neu")
    numero(c, pct(SEM_CAMPO), "dos problemas já foram resolvidos sem ir a campo", "ok")
    st.write("")
    st.markdown(f"""
<div class="ask"><div class="t">O que pedimos aos donos do inventário</div><ol>
<li><b>Suspender a planilha bruta como fonte oficial</b> e usar a base saneada, que mantém o valor original ao lado do corrigido.</li>
<li><b>Aprovar uma campanha curta de verificação</b>: {pct(TOP3_SHARE)} das pendências de campo estão em 3 lugares.</li>
<li><b>Adotar um modelo único de levantamento com validação automática</b>, que evitaria cerca de {pct(EVITAVEIS)} dos erros encontrados.</li>
</ol></div>""", unsafe_allow_html=True)

# ==============================================================================
elif cap == 1:
    cabecalho("Insight 1 · Risco",
              f"Em 1 de cada 2 equipamentos, a documentação pode levar a equipe ao ponto errado",
              f"{N_EQ_ALTA} dos {N_EQ} equipamentos têm pelo menos um erro de severidade alta: ponto em conflito, "
              "pino trocado, endereço inexistente ou valor ausente.")
    tres(
        f"{N_EQ_ALTA} de {N_EQ} equipamentos com erro grave. Há {CONFLITOS} pontos físicos atribuídos a dois "
        "circuitos ou funções ao mesmo tempo, e um armário ('TB34') que não existe.",
        "Numa falha, a equipe chega ao campo com um mapa errado: <b>o diagnóstico demora mais, o trecho fica mais "
        "tempo em operação restritiva</b> e aumenta o risco de mexer no fio errado. Qualquer projeto que use essa base "
        "(modernização, integração, novo sistema) <b>herda os erros</b>.",
        "Tratar a planilha bruta como <b>não confiável</b> a partir de agora. Ordens de serviço e projetos passam a usar "
        "a base saneada, com o status de cada ponto (confirmado, corrigido ou pendente).",
    )
    evidencia(f"""
- Conflitos reais: TB3-A48 (2S15T e 2S14T), LC B-39 na Locação 5 (1N09T e 2N08T), LB B-31 na Locação 20 (TPR e TPRN do 1S07T),
  LB A-23 na Locação 15 (1S12T colide com o barramento N12).
- No 2S15T, duas funções foram anotadas com os mesmos pinos de outras duas.
- Sinais 28, 52 e 56 sem nenhum borne de armário registrado.
- Detalhe completo, célula a célula, no painel analítico (app.py → Erros na Base Bruta).
""")

# ==============================================================================
elif cap == 2:
    cabecalho("Insight 2 · Causa raiz",
              "O problema está no processo de levantamento, não nas pessoas",
              "A maior parte dos erros é do tipo que um formulário bem desenhado impede: digitação livre, "
              "blocos copiados e colados, nenhuma checagem na hora do registro.")
    tres(
        f"Cerca de <b>{pct(EVITAVEIS)} dos erros</b> são de formato ou estrutura: espaço faltando, prefixo invertido, "
        "armário incompleto, linha duplicada, duas informações na mesma célula. O mesmo lugar aparece com dois nomes "
        "('Armario TB' e 'Armários TB').",
        "Enquanto o levantamento for feito em planilha livre, <b>cada nova coleta vai gerar o mesmo tipo de erro</b> e "
        "o custo de conferência se repete. O problema não é pontual, é estrutural.",
        "Padronizar o levantamento: <b>uma linha por ligação</b>, listas fechadas (armário, régua, bastidor, função) e "
        "<b>validação no momento do registro</b>, com as regras que já sabemos que o projeto segue.",
    )
    evidencia("""
As regras usadas para validar vieram do próprio projeto e podem virar checagem automática:
- cada função do circuito usa sempre o mesmo pino da interface (21, 23, 26, 30, 31);
- o barramento N12 usa o mesmo borne em toda a locação;
- as locações 17 e 18 repetem os mesmos bornes;
- um ponto físico pertence a um único circuito e função.
""")

# ==============================================================================
elif cap == 3:
    cabecalho("Insight 3 · Governança",
              f"{N_ESCONDIDOS} circuitos de via não existem oficialmente — estão escondidos sob nomes repetidos",
              f"O inventário conta {legado['grupos_cdv']} circuitos, mas existem {N_CDV}. Dois nomes foram usados em "
              "blocos que são, fisicamente, circuitos diferentes.")
    tres(
        "'1S06T' aparece em 2 blocos e '2S11T' em 3, cada um com ligações e bastidor de interface próprios. "
        "A numeração da Via 1 Sul pula o 1S08T e o 1S10T — justamente onde o nome se repete.",
        "Um circuito sem identidade própria <b>pode ficar fora do plano de manutenção, das ordens de serviço e das "
        "auditorias</b>. Também gera confusão na hora de um atendimento: a equipe pode ir a um circuito pensando que é outro.",
        "Criar um <b>cadastro mestre de equipamentos</b> com identificador único e físico (por exemplo, o bastidor de "
        "interface) e pedir ao projeto a confirmação do nome real dos 5 blocos.",
    )
    evidencia("""
| Nome na planilha | Bloco | Bastidor de interface |
|---|---|---|
| 1S06T | I83 | B34 |
| 1S06T | B98 | B45 |
| 2S11T | B116 | B41 |
| 2S11T | I116 | B43 |
| 2S11T | B127 | B44 |

A relação com os números ausentes é uma hipótese a validar com o projeto.
""")

# ==============================================================================
elif cap == 4:
    cabecalho("Insight 4 · Risco operacional",
              f"{pct(CDV_EM_CRITICOS / N_CDV)} dos circuitos de via dependem de apenas {len(criticos)} pontos de alimentação",
              f"Cada locação tem uma alimentação comum (barramento N12). Em {len(criticos)} bornes, entre 6 e {MAX_N12} "
              "circuitos estão pendurados no mesmo ponto. Isso é do projeto — mas faz desses pontos os mais críticos da via.")
    tres(
        f"{CDV_EM_CRITICOS} dos {N_CDV} circuitos estão ligados a um desses {len(criticos)} bornes. "
        "E na <b>Locação 17</b>, uma das mais carregadas, o barramento está anotado de forma divergente em dois circuitos.",
        "Uma falha num desses pontos <b>afeta vários circuitos ao mesmo tempo</b>. Para a circulação, circuito em falha "
        "costuma significar trecho tratado como ocupado e operação mais lenta. Se a documentação desse ponto estiver "
        "errada, o tempo de restabelecimento aumenta.",
        "Colocar esses bornes e as locações 5, 17 e 18 <b>no topo do plano de inspeção preventiva</b>, e conferir a "
        "Locação 17 antes de qualquer outra.",
    )
    tab = pd.DataFrame([(l, v, len(s)) for (l, v), s in criticos.items()], columns=["Locação", "Borne", "Circuitos"]) \
        .sort_values("Circuitos", ascending=False)
    with st.expander("Evidência nos dados"):
        st.markdown("**Pontos de alimentação com 6 ou mais circuitos**")
        st.dataframe(tab, hide_index=True, width="stretch")

# ==============================================================================
elif cap == 5:
    cabecalho("Insight 5 · Esforço",
              "Sanear a base é rápido: quase metade já está feita e o resto cabe numa campanha curta",
              f"{pct(SEM_CAMPO)} dos problemas foram corrigidos em escritório, com evidência no próprio dado. "
              f"Os {len(pend)} restantes foram transformados num roteiro, agrupados por onde precisam ser conferidos.")
    a, b = st.columns([1.05, 1])
    with a:
        r = ROTA.reset_index()
        cores = ["#D46A6A" if o in TOP3_CAMPO.index else ("#8C79B8" if o.startswith("Escritório") else "#B8C1CC") for o in r["onde"]]
        fig = go.Figure(go.Bar(x=r["itens"], y=r["onde"], orientation="h", text=r["itens"], marker_color=cores))
        fig.update_layout(height=360, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
                          yaxis={"autorange": "reversed"}, xaxis_title="Verificações")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption(f"Em vermelho: os 3 lugares que concentram {pct(TOP3_SHARE)} das verificações de campo. "
                   "Em roxo: itens que se resolvem com o projeto, sem ir a campo.")
    with b:
        st.markdown("**Estimativa de esforço** · ajuste as premissas")
        c1, c2 = st.columns(2)
        minutos = c1.number_input("Minutos por verificação", 5, 120, 20, 5)
        desloc = c2.number_input("Horas de deslocamento por local", 0.0, 8.0, 1.5, 0.5)
        pessoas = c1.number_input("Pessoas por equipe", 1, 6, 2)
        jornada = c2.number_input("Horas úteis por dia", 4, 12, 8)
        n_locais = len(CAMPO)
        n_itens = int(CAMPO["itens"].sum())
        horas = n_itens * minutos / 60 + n_locais * desloc
        st.metric("Horas de equipe em campo", f"{horas:.0f} h", f"{n_itens} verificações em {n_locais} locais", delta_color="off", delta_arrow="off")
        st.metric("Dias de uma equipe", f"{horas / jornada:.1f}", f"{horas * pessoas:.0f} homem-hora", delta_color="off", delta_arrow="off")
        st.caption("Premissas editáveis, não medidas. Servem para dimensionar a ordem de grandeza da campanha.")
    st.markdown(f'<div class="card dec"><div class="t">Decisão recomendada</div><div class="c">Aprovar uma campanha de '
                f'verificação começando por <b>{", ".join(TOP3_CAMPO.index)}</b>, e em paralelo levar os itens de escritório ao '
                f'projeto. Ao final, a base passa a ser a referência oficial.</div></div>', unsafe_allow_html=True)
    st.download_button("Baixar roteiro de verificação (CSV)",
                       p[["id_erro", "severidade", "onde", "equipamento", "funcao", "celula", "valor_bruto", "sugestao", "detalhe"]]
                       .to_csv(index=False).encode("utf-8-sig"), "roteiro_verificacao.csv", "text/csv")

# ==============================================================================
elif cap == 6:
    cabecalho("Insight 6 · Planejamento",
              f"Há espaço para crescer sem obra nova — mas quase metade da sala técnica depende de um só armário",
              "O mapa de ocupação mostra capacidade livre e um ponto de concentração. As duas coisas importam para "
              "expansão e para contingência.")
    tres(
        f"<b>{len(LIVRES)} bastidores de interface livres</b> entre B01 e B51. O armário <b>TB2 concentra "
        f"{pct(TB2_PCT)} dos bornes</b>, incluindo a maioria dos sinais.",
        "Novos circuitos ou sinais podem usar capacidade já instalada, <b>reduzindo custo e prazo de expansão</b>. "
        "Por outro lado, um problema no TB2 (umidade, incêndio, intervenção mal feita) afeta uma parte grande da sinalização.",
        "Usar o mapa de capacidade no <b>planejamento de investimentos</b> e incluir o TB2 no <b>plano de contingência</b> "
        "da sala técnica. Antes, confirmar os bastidores B11 e B59, que aparecem só num circuito e indicam erro de anotação.",
    )
    evidencia(f"Bastidores livres: {', '.join(LIVRES)}.\n\nOcupação por armário: " +
              ", ".join(f"{k}: {v} bornes" for k, v in arm['armario'].value_counts().sort_index().items()) + ".")

# ==============================================================================
elif cap == 7:
    cabecalho("Plano e metas",
              "Oito ações, 90 dias, metas mensuráveis",
              "As ações foram priorizadas por impacto na segurança e na operação versus esforço para executar.")
    acoes = pd.DataFrame([
        ("Suspender a planilha bruta como fonte oficial", 1.2, 4.6, "Dono do inventário"),
        ("Verificar Locação 17 e sala técnica", 2.4, 4.8, "Manutenção"),
        ("Confirmar nomes dos 5 blocos repetidos", 1.6, 3.6, "Engenharia/projeto"),
        ("Campanha nas demais locações", 3.4, 3.4, "Manutenção"),
        ("Modelo único + validação automática", 3.0, 4.3, "Dados/TI"),
        ("Inspeção preventiva nos pontos críticos", 3.8, 4.0, "Manutenção"),
        ("Cadastro mestre de equipamentos", 4.2, 3.9, "Engenharia + Dados"),
        ("Mapa de capacidade no plano de investimentos", 2.2, 2.6, "Planejamento"),
    ], columns=["Ação", "Esforço", "Impacto", "Dono"])
    a, b = st.columns([1.1, 1])
    with a:
        fig = go.Figure()
        fig.add_shape(type="rect", x0=0.5, x1=3, y0=3, y1=5.2, fillcolor="#EAF4EE", line_width=0, layer="below")
        fig.add_trace(go.Scatter(x=acoes["Esforço"], y=acoes["Impacto"], mode="markers+text",
                                 text=[str(i + 1) for i in range(len(acoes))], textposition="middle center",
                                 textfont=dict(color="white", size=12),
                                 marker=dict(size=26, color="#1F2D3D"), hovertext=acoes["Ação"], hoverinfo="text"))
        fig.add_annotation(x=0.6, y=5.1, text="Fazer já", showarrow=False, xanchor="left", font=dict(color="#2E8B6E"))
        fig.update_layout(height=380, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                          xaxis=dict(title="Esforço →", range=[0.5, 5], showticklabels=False),
                          yaxis=dict(title="Impacto →", range=[2, 5.2], showticklabels=False))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("Posição relativa estimada pela equipe de análise, para orientar a priorização.")
    with b:
        for i, r in acoes.iterrows():
            st.markdown(f"**{i + 1}.** {r['Ação']} <span class='tag'>{r['Dono']}</span>", unsafe_allow_html=True)
    st.markdown("**Cronograma**")
    for quando, o_que in [
        ("30 dias", "Base saneada como referência oficial · Locação 17 e sala técnica verificadas · nomes dos blocos confirmados"),
        ("60 dias", "Campanha concluída nas demais locações · modelo único de levantamento em uso · inspeção nos pontos críticos"),
        ("90 dias", "Validação automática na entrada · cadastro mestre publicado · capacidade no plano de investimentos"),
    ]:
        st.markdown(f'<div class="linha"><div class="q">{quando}</div><div>{o_que}</div></div>', unsafe_allow_html=True)
    st.markdown("**Como medir o sucesso**")
    k = st.columns(3)
    numero(k[0], f"{pct(1 - N_EQ_ALTA / N_EQ)} → 100%", "equipamentos sem erro grave", "neu")
    numero(k[1], f"{len(pend)} → 0", "pendências abertas no inventário", "neu")
    numero(k[2], "0", "erros de formato em novos levantamentos (meta)", "ok")

# ==============================================================================
else:
    cabecalho("Anexo", "Como chegamos a essas conclusões — e o que elas não dizem",
              "As conclusões vêm da coerência interna dos dados, não de inspeção em campo.")
    a, b = st.columns(2)
    with a:
        st.markdown("""
**Método**
1. Cada célula das duas planilhas foi lida com sua coordenada no Excel.
2. 18 regras de validação, baseadas nos padrões do próprio projeto.
3. Correção em três níveis: automática (formato), por evidência no dado, ou pendente.
4. Valores ausentes ou ambíguos **não foram preenchidos**.
5. Os insights usam a base saneada; o valor original fica sempre registrado.
""")
    with b:
        st.markdown(f"""
**Limites**
- Uma inconsistência indica onde olhar; a confirmação é a verificação em campo.
- As consequências operacionais descritas são qualitativas — não medimos tempo de reparo nem custo.
- A estimativa de esforço depende das premissas informadas na tela 5.

**Base**: {N_CDV} circuitos de via, {df[df.tipo == 'Sinal']['equipamento'].nunique()} sinais, {len(pontos)} pontos de ligação,
{len(erros)} problemas catalogados. Detalhes no painel analítico (app.py).
""")

# --- rodapé de navegação --------------------------------------------------------
st.write("")
st.divider()
e, m, d = st.columns([1, 3, 1])
e.button("← Anterior", disabled=cap == 0, width="stretch", on_click=ir, args=(-1,))
m.markdown(f"<div style='text-align:center;color:#6B7785;padding-top:6px'>{cap + 1} / {len(CAPS)}</div>", unsafe_allow_html=True)
d.button("Próximo →", disabled=cap == len(CAPS) - 1, width="stretch", on_click=ir, args=(1,))
