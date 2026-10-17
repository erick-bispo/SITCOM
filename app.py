"""
SITCON | Inventário de sinalização ferroviária — Vias 1 e 2
Painel com a base bruta (e seus erros) x base corrigida (e as análises).
"""
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import sitcon_dados as sd

st.set_page_config(page_title="SITCON | Inventário", page_icon="🚆", layout="wide")

AZUL, VERDE, AMARELO, ROXO, VERMELHO, CINZA = "#2878B5", "#36A18B", "#E5A84B", "#8C79B8", "#D46A6A", "#9AA5B1"
CORES = [AZUL, VERDE, AMARELO, ROXO, VERMELHO]
COR_SEV = {"Alta": VERMELHO, "Média": AMARELO, "Baixa": "#7FB3D5"}
COR_ACAO = {sd.ACAO_AUTO: VERDE, sd.ACAO_INFER: AZUL, sd.ACAO_PEND: VERMELHO}
ORDEM_SEV = ["Alta", "Média", "Baixa"]


def layout(fig, h=380, **kw):
    fig.update_layout(height=h, template="plotly_white", margin=dict(l=10, r=10, t=40, b=10),
                      legend_title=None, **kw)
    return fig


def plot(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def n(v):
    return f"{v:,}".replace(",", ".")


@st.cache_data(show_spinner="Lendo e validando as planilhas...")
def carregar():
    r = sd.processar()
    r["legado"] = sd.metricas_painel_original(r["bruto"])
    return r


try:
    R = carregar()
except FileNotFoundError as erro:
    st.error(f"Arquivo não encontrado: {erro.filename}")
    st.stop()

bruto, df, erros, planilhas, legado = R["bruto"], R["corrigido"], R["erros"], R["planilhas"], R["legado"]
pontos = df[df["valor"].notna() & df["valor"].ne("-")].copy()
pontos["ponto"] = pontos.apply(lambda r: f"{r['locacao']} · {r['valor']}" if r["nivel"] == "Locação" else r["valor"], axis=1)
pend = erros[erros["acao"] == sd.ACAO_PEND]

# ---------------------------------------------------------------------------
# Indicadores de qualidade (bruto x corrigido)
# ---------------------------------------------------------------------------
cel_preench = bruto[bruto["valor_bruto"].notna() & bruto["valor_bruto"].astype(str).str.strip().ne("")]
cel_erro = set(zip(erros["arquivo"], erros["celula"]))
cel_pend = set(zip(pend["arquivo"], pend["celula"]))
tot_pos = len(bruto)
pos_com_erro = sum((a, c) in cel_erro for a, c in zip(bruto["arquivo"], bruto["celula"]))
pos_com_pend = sum((a, c) in cel_pend for a, c in zip(bruto["arquivo"], bruto["celula"]))
blocos = bruto.groupby("bloco_id")["equipamento_bruto"].first()
eq_err = erros.groupby(["tipo", "bloco"]).size()
blocos_com_erro = erros["bloco"].nunique()

st.sidebar.title("🚆 SITCON")
st.sidebar.caption("Inventário de sinalização · Vias 1 e 2")
pagina = st.sidebar.radio("Navegação", [
    "Visão Geral",
    "Erros na Base Bruta",
    "Correções Aplicadas",
    "Análises (dados corrigidos)",
    "Explorar Dados",
    "Metodologia",
])
st.sidebar.divider()
st.sidebar.metric("Ocorrências na base bruta", n(len(erros)))
st.sidebar.metric("Pendentes de validação em campo", n(len(pend)))

st.title("🚆 SITCON")
st.caption("Painel de análise do inventário de sinalização ferroviária — base bruta x base corrigida")

# ===========================================================================
# 1. VISÃO GERAL
# ===========================================================================
if pagina == "Visão Geral":
    st.header("A base bruta é suja — e isso muda as conclusões")
    st.write(
        "O levantamento foi feito à mão em blocos lado a lado. Antes de analisar, cada célula foi "
        "extraída com sua coordenada, validada com 18 regras e corrigida de forma rastreável. "
        "Nada foi apagado: o valor bruto continua ao lado do corrigido."
    )

    c = st.columns(4)
    c[0].metric("Ocorrências de erro", n(len(erros)), help="Total de problemas encontrados pelas 18 regras.")
    medalta = erros[erros.severidade != "Baixa"]["bloco"].nunique()
    c[1].metric("Equipamentos com erro", f"{blocos_com_erro} de {len(blocos)}",
                f"{medalta} com erro médio ou alto", delta_color="off", delta_arrow="off")
    c[2].metric("Corrigidas", n(len(erros) - len(pend)),
                f"{(len(erros) - len(pend)) / len(erros):.0%} das ocorrências")
    c[3].metric("Pendentes (campo)", n(len(pend)), "não inventamos dados", delta_color="off", delta_arrow="off")

    st.divider()
    st.subheader("O que o painel anterior mostrava x o que os dados realmente dizem")
    rep_n12 = pontos[pontos["funcao"] == "N12-CTP"].groupby("ponto")["equipamento"].nunique()
    comp = pd.DataFrame([
        ["CDVs no inventário", f"{legado['grupos_cdv']} grupos", f"{df[df.tipo=='CDV'].equipamento.nunique()} circuitos",
         "1S06T aparece 2x e 2S11T aparece 3x, cada um com bastidor de interface próprio — são circuitos diferentes com nome repetido."],
        ["Identificadores 'sem valor'", n(legado["sem_id"]), f"{n(int((bruto.valor_bruto.astype(str).str.strip()=='-').sum()))} '-' + 15 vazios",
         "O '-' significa 'não se aplica' (ex.: N12 não passa pelo armário). Só 15 posições estão realmente vazias."],
        ["IDs 'repetidos'", n(legado["repetidos"]), f"{int((erros.regra=='E17').sum())} registros em conflito real",
         "A maioria das repetições é por projeto: barramento N12 compartilhado e o mesmo nome de borne em locações diferentes."],
        ["Locais de 'Armário'", "2 categorias", "1 nível",
         "'Armario TB' (sinais) e 'Armários TB' (CDVs) eram tratados como lugares diferentes."],
        ["Erros de conteúdo", "não avaliados", f"{n(len(erros))} ocorrências",
         "Formato, consistência, ausência e conflito de ponto físico, cada uma com a célula de origem."],
    ], columns=["Métrica", "Painel anterior (bruto)", "Base corrigida", "Por quê"])
    st.table(comp.set_index("Métrica"))

    st.divider()
    a, b = st.columns(2)
    with a:
        st.subheader("Qualidade das posições")
        qual = pd.DataFrame({
            "Base": ["Bruta", "Bruta", "Corrigida", "Corrigida"],
            "Situação": ["Sem problema", "Com problema", "Sem problema", "Pendente"],
            "Posições": [tot_pos - pos_com_erro, pos_com_erro, tot_pos - pos_com_pend, pos_com_pend],
        })
        qual["%"] = qual["Posições"] / tot_pos * 100
        qual["rot"] = qual.apply(lambda r: f"{r['Posições']} ({r['%']:.1f}%)", axis=1)
        fig = px.bar(qual, y="Base", x="%", color="Situação", text="rot", orientation="h",
                     color_discrete_map={"Sem problema": VERDE, "Com problema": VERMELHO, "Pendente": AMARELO})
        fig.update_traces(textposition="inside", insidetextanchor="middle")
        plot(layout(fig, 300, xaxis_title="% das posições", yaxis_title=None,
                    legend=dict(orientation="h", y=-0.3)))
        st.caption(f"Posições = células de ligação extraídas ({n(tot_pos)}). Após a correção, só restam "
                   f"{pos_com_pend} posições pendentes de validação em campo.")
    with b:
        st.subheader("Ocorrências por severidade")
        sev = erros.groupby(["severidade", "acao"]).size().reset_index(name="Ocorrências")
        fig = px.bar(sev, x="severidade", y="Ocorrências", color="acao", text="Ocorrências",
                     category_orders={"severidade": ORDEM_SEV}, color_discrete_map=COR_ACAO)
        plot(layout(fig, 360, xaxis_title=None))
        st.caption("Severidade Alta = pode levar a uma ligação errada em campo (conflito, pino trocado, valor ausente).")

    st.divider()
    st.subheader("Inventário corrigido")
    c = st.columns(5)
    c[0].metric("Circuitos de via (CDV)", df[df.tipo == "CDV"].equipamento.nunique())
    c[1].metric("Sinais luminosos", df[df.tipo == "Sinal"].equipamento.nunique())
    c[2].metric("Pontos de ligação", n(len(pontos)))
    c[3].metric("Locações de campo", pontos["locacao"].nunique())
    c[4].metric("Bastidores de interface", pontos["bastidor"].nunique())

# ===========================================================================
# 2. ERROS NA BASE BRUTA
# ===========================================================================
elif pagina == "Erros na Base Bruta":
    st.header("Erros encontrados na base bruta")
    st.write("Cada ocorrência aponta a planilha e a célula exata. Use o mapa para ver os erros na própria planilha.")

    c = st.columns(4)
    c[0].metric("Ocorrências", n(len(erros)))
    c[1].metric("Células afetadas", n(erros["celula"].nunique()))
    c[2].metric("Severidade alta", n(int((erros.severidade == "Alta").sum())))
    c[3].metric("Equipamentos afetados", f"{blocos_com_erro} de {len(blocos)}")

    a, b = st.columns(2)
    with a:
        cat = erros.groupby(["categoria", "severidade"]).size().reset_index(name="Ocorrências")
        fig = px.bar(cat, y="categoria", x="Ocorrências", color="severidade", orientation="h",
                     color_discrete_map=COR_SEV, category_orders={"severidade": ORDEM_SEV},
                     title="Por categoria de erro")
        plot(layout(fig, 380, yaxis={"categoryorder": "total ascending"}, yaxis_title=None))
    with b:
        reg = erros.groupby(["regra", "nome_regra", "severidade"]).size().reset_index(name="Ocorrências")
        reg["Regra"] = reg["regra"] + " · " + reg["nome_regra"]
        fig = px.bar(reg, y="Regra", x="Ocorrências", color="severidade", orientation="h",
                     color_discrete_map=COR_SEV, title="Por regra de validação")
        plot(layout(fig, 380, yaxis={"categoryorder": "total ascending"}, yaxis_title=None, showlegend=False))

    st.subheader("Equipamentos com mais problemas")
    eq = erros.assign(Equipamento=erros["equipamento"] + " (" + erros["bloco"] + ")") \
        .groupby(["Equipamento", "severidade"]).size().reset_index(name="Ocorrências")
    top = eq.groupby("Equipamento")["Ocorrências"].sum().nlargest(15).index
    fig = px.bar(eq[eq.Equipamento.isin(top)], x="Ocorrências", y="Equipamento", color="severidade",
                 orientation="h", color_discrete_map=COR_SEV, category_orders={"severidade": ORDEM_SEV})
    plot(layout(fig, 480, yaxis={"categoryorder": "total ascending"}, yaxis_title=None,
                legend=dict(orientation="h", y=1.08, x=0)))
    st.caption("O bloco (célula do título) diferencia equipamentos com o mesmo nome, como os três blocos '2S11T'.")

    st.divider()
    st.subheader("Exemplos de sujeira na base")
    exemplos = [
        ("E01", "Mesmo nome, circuitos diferentes", "'CDV 2S11T LUZ' em B116, I116 e B127 — bastidores B41, B43 e B44"),
        ("E12", "Pino repetido", "2S15T: NCTP = 'B36 30' e SCTP = 'B36 31', iguais aos pinos de TPR/TPRN"),
        ("E17", "Ponto físico em conflito", "TB3-A48 atribuído ao NCTP do 2S15T e ao NCTP do 2S14T"),
        ("E09", "Armário inexistente", "'TB34-A3' (2S11T, K124) — não existe TB34"),
        ("E13", "Barramento N12 divergente", "Locação 17: 6 CDVs usam LB C-15; 1S11T e 1S09T usam LB A-23"),
        ("E06", "Formato", "'B0923', 'B4423', 'B3028', 'B5032', 'B 59 01'"),
    ]
    cols = st.columns(3)
    for i, (rg, tit, txt) in enumerate(exemplos):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{tit}**  \n`{rg}` · {sd.REGRAS[rg][2]}")
                st.write(txt)

    st.divider()
    st.subheader("Mapa da planilha bruta")
    escolha = st.radio("Planilha", ["CDVs", "Sinais"], horizontal=True)
    tipo = "CDV" if escolha == "CDVs" else "Sinal"
    arq = sd.ARQ_CDVS.name if tipo == "CDV" else sd.ARQ_SINAIS.name
    grade = planilhas[tipo].copy()
    from openpyxl.utils import get_column_letter
    grade.columns = [get_column_letter(i + 1) for i in range(grade.shape[1])]
    grade.index = range(1, len(grade) + 1)
    pior = {}
    for _, e in erros[erros["arquivo"] == arq].iterrows():
        m = re.match(r"^([A-Z]+)(\d+)$", e["celula"])
        k = (int(m.group(2)), m.group(1))
        if k not in pior or ORDEM_SEV.index(e["severidade"]) < ORDEM_SEV.index(pior[k]):
            pior[k] = e["severidade"]
    fundo = {"Alta": "background-color:#F5B7B1", "Média": "background-color:#FAD7A0", "Baixa": "background-color:#D6EAF8"}

    def estilo(_):
        s = pd.DataFrame("", index=grade.index, columns=grade.columns)
        for (lin, col), sv in pior.items():
            if lin in s.index and col in s.columns:
                s.at[lin, col] = fundo[sv]
        return s

    st.dataframe(grade.fillna("").astype(str).style.apply(estilo, axis=None), width="stretch", height=520)
    st.caption("Vermelho = severidade alta · laranja = média · azul = baixa. Linhas e colunas seguem o Excel original.")

    st.divider()
    st.subheader("Catálogo completo de erros")
    f1, f2, f3 = st.columns(3)
    sev_f = f1.multiselect("Severidade", ORDEM_SEV, default=ORDEM_SEV)
    cat_f = f2.multiselect("Categoria", sorted(erros.categoria.unique()), default=sorted(erros.categoria.unique()))
    tipo_f = f3.multiselect("Planilha", ["CDV", "Sinal"], default=["CDV", "Sinal"])
    vis = erros[erros.severidade.isin(sev_f) & erros.categoria.isin(cat_f) & erros.tipo.isin(tipo_f)] \
        .sort_values(["severidade", "regra"], key=lambda s: s.map(ORDEM_SEV.index) if s.name == "severidade" else s)
    cols = ["id_erro", "regra", "nome_regra", "severidade", "tipo", "equipamento", "bloco", "celula", "nivel",
            "funcao", "valor_bruto", "valor_corrigido", "acao", "sugestao", "detalhe"]
    st.dataframe(vis[cols].rename(columns={
        "id_erro": "ID", "regra": "Regra", "nome_regra": "Erro", "severidade": "Severidade", "tipo": "Planilha",
        "equipamento": "Equipamento", "bloco": "Bloco", "celula": "Célula", "nivel": "Nível", "funcao": "Função",
        "valor_bruto": "Valor bruto", "valor_corrigido": "Valor corrigido", "acao": "Ação",
        "sugestao": "Sugestão", "detalhe": "Detalhe"}).fillna(""), width="stretch", hide_index=True, height=480)
    st.download_button("Baixar catálogo de erros (CSV)", vis.to_csv(index=False).encode("utf-8-sig"),
                       "catalogo_erros_sitcon.csv", "text/csv")

# ===========================================================================
# 3. CORREÇÕES
# ===========================================================================
elif pagina == "Correções Aplicadas":
    st.header("Como a base foi corrigida")
    st.write(
        "Três níveis de confiança. **Automático**: formato evidente (espaço, zero à esquerda, rótulo). "
        "**Inferência**: o próprio dado prova o valor certo (borne vizinho, sequência de pinos). "
        "**Pendente**: ausente, ambíguo ou contraditório — não foi inventado, vai para validação em campo."
    )
    resumo = erros["acao"].value_counts().reindex([sd.ACAO_AUTO, sd.ACAO_INFER, sd.ACAO_PEND]).fillna(0)
    c = st.columns(3)
    for col, (k, v) in zip(c, resumo.items()):
        col.metric(k, int(v), f"{v / len(erros):.0%}", delta_color="off", delta_arrow="off")

    fig = go.Figure(go.Funnel(
        y=["Ocorrências encontradas", "Após correção automática", "Após inferência (= pendentes)"],
        x=[len(erros), len(erros) - resumo[sd.ACAO_AUTO], len(pend)],
        marker={"color": [VERMELHO, AMARELO, ROXO]}, textinfo="value"))
    plot(layout(fig, 300))

    st.subheader("De → Para (correções aplicadas)")
    corr = erros[erros["acao"] != sd.ACAO_PEND]
    st.dataframe(corr[["id_erro", "acao", "nome_regra", "equipamento", "celula", "valor_bruto", "valor_corrigido", "detalhe"]]
                 .rename(columns={"id_erro": "ID", "acao": "Confiança", "nome_regra": "Erro", "equipamento": "Equipamento",
                                  "celula": "Célula", "valor_bruto": "Bruto", "valor_corrigido": "Corrigido",
                                  "detalhe": "Justificativa"}).fillna(""),
                 width="stretch", hide_index=True, height=420)

    st.subheader("Checklist de validação em campo")
    st.caption("Itens pendentes, com a sugestão quando o próprio padrão dos dados aponta um valor provável.")
    st.dataframe(pend[["id_erro", "severidade", "nome_regra", "equipamento", "celula", "nivel", "funcao", "valor_bruto", "sugestao", "detalhe"]]
                 .sort_values("severidade", key=lambda s: s.map(ORDEM_SEV.index))
                 .rename(columns={"id_erro": "ID", "severidade": "Severidade", "nome_regra": "Erro", "equipamento": "Equipamento",
                                  "celula": "Célula", "nivel": "Nível", "funcao": "Função", "valor_bruto": "Bruto",
                                  "sugestao": "Sugestão", "detalhe": "Detalhe"}).fillna(""),
                 width="stretch", hide_index=True, height=460)
    st.download_button("Baixar checklist (CSV)", pend.to_csv(index=False).encode("utf-8-sig"),
                       "checklist_campo_sitcon.csv", "text/csv")

# ===========================================================================
# 4. ANÁLISES
# ===========================================================================
elif pagina == "Análises (dados corrigidos)":
    st.header("Análises com a base corrigida")
    abas = st.tabs(["Inventário", "Locações", "Barramento N12", "Armários TB", "Interface 2", "Repetições x conflitos"])

    cdv = pontos[pontos.tipo == "CDV"]
    cdv_all = df[df.tipo == "CDV"]

    with abas[0]:
        st.subheader("Circuitos de via por via e sentido")
        vs = cdv_all.drop_duplicates("equipamento").groupby(["via", "sentido"]).size().reset_index(name="CDVs")
        vs["sentido"] = vs["sentido"].map({"N": "Norte (N)", "S": "Sul (S)"})
        a, b = st.columns([1, 1])
        with a:
            fig = px.bar(vs, x="via", y="CDVs", color="sentido", barmode="group", text="CDVs",
                         color_discrete_sequence=[AZUL, VERDE])
            plot(layout(fig, 340, xaxis_title=None))
        with b:
            st.markdown("**Lacunas na numeração**")
            nomes = sorted(cdv_all["equipamento_bruto"].unique())
            linhas = []
            for pref in ["1N", "1S", "2N", "2S"]:
                nums = sorted({int(x[2:4]) for x in nomes if x.startswith(pref)})
                falt = [f"{pref}{k:02d}T" for k in range(min(nums), max(nums) + 1) if k not in nums]
                dup = cdv_all[cdv_all.equipamento_bruto.str.startswith(pref)].groupby("equipamento_bruto")["bloco_id"].nunique()
                linhas.append([pref, f"{pref}{min(nums):02d}–{pref}{max(nums):02d}", ", ".join(falt) or "—",
                               ", ".join(f"{k} ({v}x)" for k, v in dup[dup > 1].items()) or "—"])
            st.dataframe(pd.DataFrame(linhas, columns=["Grupo", "Faixa", "Números ausentes", "Nomes repetidos"]),
                         hide_index=True, width="stretch")
            st.info("Hipótese para validar: na Via 1 Sul faltam 1S08T e 1S10T e o 1S06T aparece duas vezes; "
                    "na Via 2 Sul a numeração começa no 2S11T, que aparece três vezes. Os blocos repetidos podem ser "
                    "circuitos de outra numeração com o nome copiado errado.")

        st.subheader("Complexidade de cada CDV")
        cx = cdv.groupby("equipamento").agg(Locações=("locacao", "nunique"), Pontos=("valor", "size")).reset_index()
        cx["Via"] = cx["equipamento"].str[0].radd("Via ")
        fig = px.bar(cx.sort_values("Pontos"), x="Pontos", y="equipamento", color="Locações", orientation="h",
                     color_continuous_scale=["#9CC3E4", AZUL, "#0B3C6B"], hover_data=["Via"])
        plot(layout(fig, 560, yaxis_title=None))
        st.caption("Quanto mais locações um CDV atravessa, mais pontos de ligação ele tem — e mais chance de erro no levantamento. "
                   "Os dois blocos '1S06T' passam por 8 e 9 locações.")

        st.subheader("Cobertura de funções por nível")
        cob = cdv_all.assign(tem=cdv_all["valor"].notna() & cdv_all["valor"].ne("-")) \
            .groupby(["equipamento", "funcao", "nivel"])["tem"].any().reset_index()
        cob["col"] = cob["funcao"] + " · " + cob["nivel"].str.replace(" TB", "").str.replace(" 2", "")
        mat = cob.pivot(index="equipamento", columns="col", values="tem").astype(float)
        ordem = [f"{f} · {nv}" for f in sd.FUNCOES_CDV for nv in ["Locação", "Armário", "Interface"]]
        mat = mat[[c for c in ordem if c in mat.columns]]
        fig = px.imshow(mat, color_continuous_scale=[[0, "#F2F3F4"], [1, VERDE]], aspect="auto")
        fig.update_coloraxes(showscale=False)
        plot(layout(fig, 620, xaxis_title=None, yaxis_title=None))
        st.caption("Verde = existe ponto. O N12 nunca passa pelo armário (por projeto). 1N08T, 2N06T e os dois 1S06T não têm SCTP em nenhum nível.")

    with abas[1]:
        st.subheader("Carga por locação de campo")
        loc = pontos[pontos.nivel == "Locação"].copy()
        loc["n"] = loc["locacao"].str.extract(r"(\d+)").astype(int)
        carga = loc.groupby(["locacao", "n", "tipo"]).size().reset_index(name="Pontos").sort_values("n")
        fig = px.bar(carga, x="locacao", y="Pontos", color="tipo", color_discrete_sequence=[AZUL, AMARELO])
        plot(layout(fig, 380, xaxis_title=None, xaxis={"categoryorder": "array", "categoryarray": carga.drop_duplicates("locacao")["locacao"].tolist()}))
        eqloc = loc.groupby("locacao")["equipamento"].nunique().sort_values(ascending=False)
        c = st.columns(3)
        c[0].metric("Locação com mais pontos", carga.groupby("locacao")["Pontos"].sum().idxmax(),
                    f"{carga.groupby('locacao')['Pontos'].sum().max()} pontos", delta_color="off", delta_arrow="off")
        c[1].metric("Locação com mais equipamentos", eqloc.index[0], f"{eqloc.iloc[0]} equipamentos", delta_color="off", delta_arrow="off")
        c[2].metric("Locações de campo", loc["locacao"].nunique())
        st.caption("Os CDVs 'N' ocupam as locações 1–13 e os 'S' as locações 6–23 (sobreposição em 6–13). As locações 5, 17 e 18 "
                   "são as mais carregadas e merecem prioridade na conferência de campo.")

        st.subheader("Matriz equipamento × locação")
        mat = loc.groupby(["equipamento", "locacao"]).size().unstack(fill_value=0)
        mat = mat[sorted(mat.columns, key=lambda x: int(re.sub(r"\D", "", x)))]
        fig = go.Figure(go.Heatmap(z=mat.values, x=mat.columns, y=mat.index, text=mat.replace(0, "").values,
                                   texttemplate="%{text}", colorscale=[[0, "#FFFFFF"], [0.01, "#D6EAF8"], [1, AZUL]],
                                   showscale=False, xgap=1, ygap=1))
        plot(layout(fig, 900, xaxis_title=None, yaxis={"autorange": "reversed"}))

    with abas[2]:
        st.subheader("Barramento N12: quem depende de cada borne")
        n12 = cdv[(cdv.funcao == "N12-CTP") & (cdv.nivel == "Locação")]
        bus = n12.groupby(["locacao", "valor"]).agg(CDVs=("equipamento", "nunique"),
                                                    Lista=("equipamento", lambda s: ", ".join(sorted(set(s))))).reset_index()
        bus["n"] = bus["locacao"].str.extract(r"(\d+)").astype(int)
        bus = bus.sort_values(["n", "CDVs"], ascending=[True, False])
        bus["Barramento"] = bus["locacao"] + " · " + bus["valor"]
        e13 = pend[pend.regra == "E13"].merge(df[["arquivo", "celula", "locacao"]], on=["arquivo", "celula"])
        minoritarios = set(zip(e13["locacao"], e13["valor_bruto"]))
        bus["Divergente"] = [(l, v) in minoritarios for l, v in zip(bus["locacao"], bus["valor"])]
        fig = px.bar(bus, x="CDVs", y="Barramento", orientation="h", text="CDVs", hover_data=["Lista"],
                     color="Divergente", color_discrete_map={False: AZUL, True: VERMELHO})
        plot(layout(fig, 620, yaxis={"autorange": "reversed"}, yaxis_title=None, showlegend=False))
        st.caption("Cada borne N12 é um ponto comum de vários CDVs: uma falha nele afeta todos os circuitos listados "
                   "(até 7 CDVs nas locações 5, 18 e 20). "
                   "Em vermelho, os bornes minoritários que divergem do padrão da locação (regra E13).")
        st.dataframe(bus[["locacao", "valor", "CDVs", "Lista"]].rename(columns={"locacao": "Locação", "valor": "Borne N12"}),
                     hide_index=True, width="stretch")

    with abas[3]:
        st.subheader("Ocupação dos armários TB por régua")
        arm = pontos[pontos.nivel == "Armário TB"]
        occ = arm.groupby(["armario", "regua", "tipo"]).size().reset_index(name="Bornes")
        fig = px.bar(occ, x="regua", y="Bornes", color="tipo", facet_col="armario", text="Bornes",
                     color_discrete_sequence=[AZUL, AMARELO])
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        plot(layout(fig, 380))
        tot = arm.groupby("armario").size()
        st.caption(f"TB2 concentra {tot.get('TB2', 0)} bornes ({tot.get('TB2', 0) / tot.sum():.0%}) — é o armário mais crítico. "
                   "10 dos 16 sinais com armário informado estão no TB2; o TB4 atende só CDVs do lado Sul.")
        st.subheader("Mapa de bornes")
        arm2 = arm.copy()
        arm2["borne"] = arm2["valor"].str.extract(r"(\d+)$")[0].astype(int)
        arm2["régua"] = arm2["armario"] + "-" + arm2["regua"]
        fig = px.scatter(arm2, x="borne", y="régua", color="tipo", hover_data=["equipamento", "funcao", "valor"],
                         color_discrete_sequence=[AZUL, AMARELO])
        fig.update_traces(marker=dict(size=11, symbol="square"))
        plot(layout(fig, 480, yaxis={"categoryorder": "category descending"}))

    with abas[4]:
        st.subheader("Mapa da Interface 2 (bastidor × pino)")
        itf = pontos[pontos.nivel == "Interface 2"].dropna(subset=["bastidor", "pino"])
        itf = itf.assign(rotulo=itf["equipamento"].str.replace("Sinal ", "S") + " " + itf["funcao"])
        piv = itf.groupby(["pino", "bastidor"]).agg(qtd=("valor", "size"), txt=("rotulo", " / ".join)).reset_index()
        z = piv.pivot(index="pino", columns="bastidor", values="qtd")
        t = piv.pivot(index="pino", columns="bastidor", values="txt").reindex_like(z)
        tipo_b = itf.groupby("bastidor")["tipo"].agg(lambda s: "/".join(sorted(set(s))))
        fig = go.Figure(go.Heatmap(z=z.notna().astype(int).values * z.columns.map(lambda b: 1 if tipo_b[b] == "CDV" else 2).values,
                                   x=z.columns, y=z.index, text=t.fillna("").values, hovertemplate="%{x} pino %{y}<br>%{text}<extra></extra>",
                                   colorscale=[[0, "#F2F3F4"], [0.5, AZUL], [1, AMARELO]], showscale=False, xgap=2, ygap=2))
        plot(layout(fig, 360, xaxis={"type": "category"}, yaxis={"type": "category"}))
        st.caption("Azul = CDV, amarelo = sinal. A lógica de alocação aparece: CDVs N nos bastidores B02–B10, "
                   "sinais N em B13–B19, CDVs S em B26–B45 e sinais S em B24, B30, B38 e B47–B51. "
                   "Os sinais compartilham bastidores em pares (pinos 22–28 para um sinal, 30–32 para outro). "
                   "B11 e B59 aparecem só no 1N08T — indício do erro de pino (E12).")
        todos = [f"B{i:02d}" for i in range(1, 52)]
        livres = [b for b in todos if b not in set(itf["bastidor"])]
        st.metric("Bastidores sem uso entre B01 e B51", len(livres))
        st.write(", ".join(livres))

    with abas[5]:
        st.subheader("Os 'IDs repetidos' do painel anterior, explicados")
        b0 = bruto.copy()
        b0["v"] = b0["valor_bruto"].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
        b0 = b0[b0["v"].notna() & ~b0["v"].isin(["", "-"])]
        rep = b0[b0["v"].duplicated(keep=False)].merge(
            df[["arquivo", "celula", "funcao", "nivel", "locacao", "equipamento"]].drop_duplicates(["arquivo", "celula"]),
            on=["arquivo", "celula"], how="left")
        conflito = set(zip(erros[erros.regra == "E17"]["arquivo"], erros[erros.regra == "E17"]["celula"]))
        corrig = set(zip(erros[erros.acao != sd.ACAO_PEND]["arquivo"], erros[erros.acao != sd.ACAO_PEND]["celula"]))

        v_corrig = set(rep[[(x, y) in corrig for x, y in zip(rep["arquivo"], rep["celula"])]]["v"])

        def classe(r):
            if pd.isna(r["nivel"]):
                return "Linha duplicada (removida)"
            if r["nivel"] == "Interface 2" and r["v"] in v_corrig:
                return "Erro de digitação (corrigido)"
            if (r["arquivo"], r["celula"]) in conflito:
                return "Conflito real de ponto físico"
            if (r["arquivo"], r["celula"]) in corrig and r["nivel"] == "Interface 2":
                return "Erro de digitação (corrigido)"
            if r["funcao"] == "N12-CTP":
                return "Barramento N12 compartilhado (por projeto)"
            if r["nivel"] == "Locação":
                return "Mesmo borne em locações diferentes (pontos distintos)"
            return "Outros"

        rep["Classe"] = rep.apply(classe, axis=1)
        cl = rep["Classe"].value_counts().reset_index()
        cl.columns = ["Classe", "Registros"]
        fig = px.bar(cl, x="Registros", y="Classe", orientation="h", text="Registros",
                     color="Classe", color_discrete_sequence=[AZUL, VERDE, CINZA, VERMELHO, AMARELO])
        plot(layout(fig, 320, yaxis={"categoryorder": "total ascending"}, yaxis_title=None, showlegend=False))
        st.caption(f"Dos {len(rep)} registros 'repetidos', só {int((rep.Classe == 'Conflito real de ponto físico').sum())} "
                   "são conflitos reais. Contar repetição de texto sem considerar locação e função superestima o problema "
                   "e esconde os erros que importam.")
        st.subheader("Conflitos reais")
        cf = erros[erros.regra == "E17"][["equipamento", "funcao", "celula", "valor_bruto", "detalhe"]]
        st.dataframe(cf.rename(columns={"equipamento": "Equipamento", "funcao": "Função", "celula": "Célula",
                                        "valor_bruto": "Ponto", "detalhe": "Detalhe"}),
                     hide_index=True, width="stretch")

# ===========================================================================
# 5. EXPLORAR
# ===========================================================================
elif pagina == "Explorar Dados":
    st.header("Explorar dados")
    base = st.radio("Base", ["Corrigida", "Bruta"], horizontal=True)
    if base == "Corrigida":
        t = df[["tipo", "equipamento", "via", "nivel", "locacao", "funcao", "valor_bruto", "valor", "status", "celula", "arquivo"]]
    else:
        t = bruto[["tipo", "equipamento_bruto", "nivel_bruto", "codigo_bruto", "valor_bruto", "celula", "arquivo"]]
    c1, c2, c3 = st.columns(3)
    busca = c1.text_input("Pesquisar", placeholder="ex.: 2S11T, TB3-A48, Locação 17")
    tipo = c2.selectbox("Tipo", ["Todos", "CDV", "Sinal"])
    if base == "Corrigida":
        status = c3.selectbox("Status", ["Todos", "OK", sd.ACAO_AUTO, sd.ACAO_INFER, sd.ACAO_PEND])
    else:
        status = "Todos"
    if tipo != "Todos":
        t = t[t["tipo"] == tipo]
    if status != "Todos":
        t = t[t["status"] == status]
    if busca.strip():
        t = t[t.astype(str).apply(lambda c: c.str.contains(busca.strip(), case=False, regex=False)).any(axis=1)]
    st.metric("Registros", n(len(t)))
    st.dataframe(t.fillna(""), width="stretch", hide_index=True, height=520)
    a, b, c = st.columns(3)
    a.download_button("Base bruta (CSV)", bruto.to_csv(index=False).encode("utf-8-sig"), "base_bruta_sitcon.csv", "text/csv")
    b.download_button("Base corrigida (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "base_corrigida_sitcon.csv", "text/csv")
    c.download_button("Catálogo de erros (CSV)", erros.to_csv(index=False).encode("utf-8-sig"), "catalogo_erros_sitcon.csv", "text/csv")

# ===========================================================================
# 6. METODOLOGIA
# ===========================================================================
elif pagina == "Metodologia":
    st.header("Metodologia")
    st.markdown("""
**1. Extração estrutural.** As planilhas têm blocos lado a lado. Cada bloco é localizado pelo título
(`CDV … LUZ` / `SINAL … LUZ`) e lido posição a posição, guardando a **célula de origem** (ex.: `K124`).
Resultado: uma linha por ponto de ligação — `equipamento | função | nível | locação | valor`.

**2. Validação.** 18 regras em 7 categorias (estrutura, padronização, formato, ausência, consistência,
conflito e completude). As regras de consistência vêm dos padrões do próprio projeto:
- pinos fixos por função nos CDVs: NCTP 21, SCTP 23, N12 26, TPR 30, TPRN 31;
- barramento N12 com borne fixo por locação;
- locações 17 e 18 com os mesmos bornes;
- TPRN = TPR + 1 ou + 2; aspectos de sinal agrupados;
- um ponto físico pertence a um único equipamento e função (exceto o barramento N12).

**3. Correção rastreável.** Automática (formato), por inferência (evidência no dado) ou pendente.
Valores ausentes e ambíguos **não são preenchidos**: viram itens do checklist de campo.

**4. Análise.** Feita apenas sobre a base corrigida, separando o que é compartilhado por projeto do que é conflito.
""")
    st.subheader("Catálogo de regras")
    st.dataframe(pd.DataFrame([(k, *v) for k, v in sd.REGRAS.items()],
                              columns=["Regra", "Nome", "Categoria", "Severidade", "Descrição"]),
                 hide_index=True, width="stretch")
