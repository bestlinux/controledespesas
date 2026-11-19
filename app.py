from datetime import date, datetime
import streamlit as st
from database import (
    init_db,
    get_cartao_config,
    update_cartao_config,
    registrar_despesa_cartao,
    listar_despesas_cartao,
    excluir_despesa_cartao,
    get_semanal_config,
    update_semanal_config,
    registrar_despesa_semanal,
    listar_despesas_semanais,
    calcular_saldo_semanal,
    excluir_despesa_semanal,
    registrar_receita_semanal,
    listar_receitas_semanais,
    excluir_receita_semanal,
)

# Configuração da página
st.set_page_config(
    page_title="Controle Financeiro",
    page_icon="💳",
    layout="wide",
)

# Inicializa o banco de dados no Turso Cloud (apenas uma vez por sessão)
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True


def format_brl(valor: float) -> str:
    """Formata um float para moeda Real (R$ 1.234,56)."""
    sinal = "-" if valor < 0 else ""
    valor_abs = abs(valor)
    formatado = f"{valor_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {formatado}"


def format_date_br(iso_date: str) -> str:
    """Converte YYYY-MM-DD para DD/MM/YYYY."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


# Carrega configurações atuais do banco
cartao_cfg = get_cartao_config()
semanal_cfg = get_semanal_config()

# Inicializa session_state para sincronizar inputs com o banco
if "valor_fatura_input" not in st.session_state:
    st.session_state["valor_fatura_input"] = float(cartao_cfg["valor_fatura"])
if "data_fechamento_input" not in st.session_state:
    st.session_state["data_fechamento_input"] = date.fromisoformat(cartao_cfg["data_fechamento"])

if "valor_permitido_input" not in st.session_state:
    st.session_state["valor_permitido_input"] = float(semanal_cfg["valor_permitido"])
if "semana_inicio_input" not in st.session_state:
    st.session_state["semana_inicio_input"] = date.fromisoformat(semanal_cfg["data_inicio"])
if "semana_fim_input" not in st.session_state:
    st.session_state["semana_fim_input"] = date.fromisoformat(semanal_cfg["data_fim"])


def on_change_cartao_config():
    update_cartao_config(
        float(st.session_state["valor_fatura_input"]),
        st.session_state["data_fechamento_input"],
    )


def on_change_semanal_config():
    inicio = st.session_state["semana_inicio_input"]
    fim = st.session_state["semana_fim_input"]
    if fim < inicio:
        fim = inicio
        st.session_state["semana_fim_input"] = fim
    update_semanal_config(
        float(st.session_state["valor_permitido_input"]),
        inicio,
        fim,
    )


# Cabeçalho Principal
st.title("💰 Controle Financeiro Pessoal")
st.caption("Gerencie a fatura do seu Cartão de Crédito e suas Despesas Semanais de forma simples e integrada.")

st.divider()

# ==============================================================================
# SEÇÃO 1: CARTÃO DE CRÉDITO
# ==============================================================================
st.header("💳 Cartão de Crédito")

with st.container(border=True):
    st.subheader("Configuração e Resumo da Fatura")

    # Campos lado a lado: "Valor atual da Fatura" e "Data para Fechamento da Fatura"
    col_fatura, col_fechamento = st.columns(2)

    with col_fatura:
        st.number_input(
            "Valor atual da Fatura (R$)",
            min_value=0.0,
            step=10.0,
            format="%.2f",
            key="valor_fatura_input",
            on_change=on_change_cartao_config,
            help="Insira ou ajuste o valor atual da fatura. Novas despesas registradas serão somadas a este valor.",
        )

    with col_fechamento:
        st.date_input(
            "Data para Fechamento da Fatura",
            format="DD/MM/YYYY",
            key="data_fechamento_input",
            on_change=on_change_cartao_config,
            help="Informe a data de fechamento da fatura do cartão.",
        )

    # Exibição em destaque lado a lado
    cartao_cfg = get_cartao_config()
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric(
            label="Valor atual da Fatura",
            value=format_brl(float(cartao_cfg["valor_fatura"])),
        )
    with m_col2:
        st.metric(
            label="Data para Fechamento da Fatura",
            value=format_date_br(cartao_cfg["data_fechamento"]),
        )

with st.container(border=True):
    st.subheader("Nova Despesa no Cartão")
    with st.form("form_despesa_cartao", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            desc_cartao = st.text_input(
                "Descrição da Despesa",
                placeholder="Ex: Supermercado, Farmácia, Assinatura...",
            )
        with c2:
            valor_despesa_cartao = st.number_input(
                "Valor da Despesa (R$)",
                min_value=0.01,
                value=None,
                step=5.0,
                format="%.2f",
                placeholder="0,00",
            )
        with c3:
            data_despesa_cartao = st.date_input(
                "Data da Despesa",
                value=date.today(),
                format="DD/MM/YYYY",
                disabled=False,
            )

        btn_registrar_cartao = st.form_submit_button("➕ Registrar Despesa", type="primary", use_container_width=True)

        if btn_registrar_cartao:
            if valor_despesa_cartao is None or valor_despesa_cartao <= 0:
                st.error("Por favor, informe um valor maior que zero para registrar a despesa.")
            else:
                registrar_despesa_cartao(
                    valor=float(valor_despesa_cartao),
                    descricao=desc_cartao or "Despesa no Cartão",
                    data_despesa=data_despesa_cartao,
                )
                novo_cfg = get_cartao_config()
                st.session_state["valor_fatura_input"] = float(novo_cfg["valor_fatura"])
                st.toast("Despesa registrada e somada à fatura!", icon="✅")
                st.rerun()

    # Lista de Despesas do Cartão
    despesas_cartao = listar_despesas_cartao()
    if despesas_cartao:
        with st.expander(f"📋 Histórico de Despesas do Cartão ({len(despesas_cartao)})", expanded=True):
            for item in despesas_cartao:
                hc1, hc2, hc3, hc4 = st.columns([2, 3, 2, 1])
                hc1.write(f"📅 **{format_date_br(item['data_despesa'])}**")
                hc2.write(item["descricao"])
                hc3.write(f"**+ {format_brl(item['valor'])}**")
                if hc4.button("🗑️", key=f"del_cartao_{item['id']}", help="Excluir lançamento e abater da fatura"):
                    excluir_despesa_cartao(item["id"])
                    novo_cfg = get_cartao_config()
                    st.session_state["valor_fatura_input"] = float(novo_cfg["valor_fatura"])
                    st.rerun()

st.divider()

# ==============================================================================
# SEÇÃO 2: DESPESAS SEMANAIS
# ==============================================================================
st.header("📅 Despesas Semanais")

with st.container(border=True):
    st.subheader("Configuração da Semana")

    col_perm, col_ini, col_fim = st.columns([2, 1, 1])

    with col_perm:
        st.number_input(
            "Valor Total Permitido para Semana (R$)",
            min_value=0.0,
            step=10.0,
            format="%.2f",
            key="valor_permitido_input",
            on_change=on_change_semanal_config,
            help="Insira o limite total permitido para gastar na semana selecionada.",
        )

    with col_ini:
        st.date_input(
            "Início da Semana",
            format="DD/MM/YYYY",
            key="semana_inicio_input",
            on_change=on_change_semanal_config,
        )

    with col_fim:
        st.date_input(
            "Fim da Semana",
            format="DD/MM/YYYY",
            key="semana_fim_input",
            on_change=on_change_semanal_config,
        )

    # Cálculo das despesas e receitas dentro da semana selecionada
    semanal_cfg = get_semanal_config()
    dt_ini = date.fromisoformat(semanal_cfg["data_inicio"])
    dt_fim = date.fromisoformat(semanal_cfg["data_fim"])
    valor_permitido_total = float(semanal_cfg["valor_permitido"])

    total_gasto_semana, total_receitas_semana, saldo_restante_semana = calcular_saldo_semanal(
        valor_permitido_total, dt_ini, dt_fim
    )

    periodo_str = f"{format_date_br(semanal_cfg['data_inicio'])} à {format_date_br(semanal_cfg['data_fim'])}"
    st.info(f"📆 **Período da Semana Ativa:** {periodo_str}")

    sm1, sm2, sm3, sm4 = st.columns(4)
    with sm1:
        movimentacao_liquida = total_receitas_semana - total_gasto_semana
        if total_gasto_semana == 0 and total_receitas_semana == 0:
            delta_texto = "Sem movimentações na semana"
            delta_cor = "off"
        else:
            sinal_liq = "+" if movimentacao_liquida >= 0 else ""
            delta_texto = f"{sinal_liq}{format_brl(movimentacao_liquida)} líquido na semana"
            delta_cor = "normal"
        st.metric(
            label="Saldo Restante na Semana",
            value=format_brl(saldo_restante_semana),
            delta=delta_texto,
            delta_color=delta_cor,
        )
    with sm2:
        st.metric(
            label="Limite Inicial Definido",
            value=format_brl(valor_permitido_total),
        )
    with sm3:
        st.metric(
            label="Total de Receitas na Semana",
            value=f"+ {format_brl(total_receitas_semana)}",
        )
    with sm4:
        st.metric(
            label="Total Gasto na Semana",
            value=f"- {format_brl(total_gasto_semana)}",
        )

    if saldo_restante_semana < 0:
        st.warning(
            f"⚠️ Atenção: Você ultrapassou o saldo disponível para a semana ({periodo_str}) em **{format_brl(abs(saldo_restante_semana))}**!"
        )

with st.container(border=True):
    st.subheader("Lançamentos da Semana")
    tab_despesa, tab_receita = st.tabs(["➖ Nova Despesa Semanal", "➕ Nova Receita"])

    with tab_despesa:
        with st.form("form_despesa_semanal", clear_on_submit=True):
            sc1, sc2, sc3 = st.columns([2, 1, 1])
            with sc1:
                desc_semanal = st.text_input(
                    "Descrição da Despesa",
                    placeholder="Ex: Almoço, Transporte, Padaria...",
                )
            with sc2:
                valor_despesa_semanal = st.number_input(
                    "Valor da Despesa (R$)",
                    min_value=0.01,
                    value=None,
                    step=5.0,
                    format="%.2f",
                    placeholder="0,00",
                )
            with sc3:
                data_despesa_semanal = st.date_input(
                    "Data da Despesa",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    help="Por padrão registra a data atual em que a despesa foi realizada.",
                )

            btn_registrar_semanal = st.form_submit_button("➖ Registrar Despesa", type="primary", use_container_width=True)

            if btn_registrar_semanal:
                if valor_despesa_semanal is None or valor_despesa_semanal <= 0:
                    st.error("Por favor, informe um valor maior que zero para registrar a despesa.")
                else:
                    registrar_despesa_semanal(
                        valor=float(valor_despesa_semanal),
                        descricao=desc_semanal or "Despesa Semanal",
                        data_despesa=data_despesa_semanal,
                        data_inicio_semana=dt_ini,
                        data_fim_semana=dt_fim,
                    )
                    st.toast("Despesa semanal registrada e subtraída do saldo da semana!", icon="✅")
                    st.rerun()

    with tab_receita:
        with st.form("form_receita_semanal", clear_on_submit=True):
            rc1, rc2, rc3 = st.columns([2, 1, 1])
            with rc1:
                desc_receita = st.text_input(
                    "Descrição da Receita",
                    placeholder="Ex: Freelance, Reembolso, Venda, Bônus...",
                )
            with rc2:
                valor_receita_semanal = st.number_input(
                    "Valor da Receita (R$)",
                    min_value=0.01,
                    value=None,
                    step=10.0,
                    format="%.2f",
                    placeholder="0,00",
                )
            with rc3:
                data_receita_semanal = st.date_input(
                    "Data da Receita",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    help="Por padrão registra a data atual em que a receita foi recebida.",
                )

            btn_registrar_receita = st.form_submit_button("➕ Registrar Receita", type="primary", use_container_width=True)

            if btn_registrar_receita:
                if valor_receita_semanal is None or valor_receita_semanal <= 0:
                    st.error("Por favor, informe um valor maior que zero para registrar a receita.")
                else:
                    registrar_receita_semanal(
                        valor=float(valor_receita_semanal),
                        descricao=desc_receita or "Receita Semanal",
                        data_receita=data_receita_semanal,
                        data_inicio_semana=dt_ini,
                        data_fim_semana=dt_fim,
                    )
                    st.toast("Receita registrada e somada ao saldo da semana!", icon="💰")
                    st.rerun()

    # Lista de Receitas da Semana Selecionada
    receitas_semana = listar_receitas_semanais(dt_ini, dt_fim)
    if receitas_semana:
        with st.expander(
            f"💰 Receitas Registradas na Semana ({periodo_str}) — {len(receitas_semana)} registro(s)",
            expanded=True,
        ):
            for item in receitas_semana:
                wr1, wr2, wr3, wr4 = st.columns([2, 3, 2, 1])
                wr1.write(f"📅 **{format_date_br(item['data_receita'])}**")
                wr2.write(item["descricao"])
                wr3.write(f":green[**+ {format_brl(item['valor'])}**]")
                if wr4.button("🗑️", key=f"del_receita_{item['id']}", help="Excluir receita semanal"):
                    excluir_receita_semanal(item["id"])
                    st.rerun()

    # Lista de Despesas da Semana Selecionada
    despesas_semana = listar_despesas_semanais(dt_ini, dt_fim)
    if despesas_semana:
        with st.expander(
            f"📋 Despesas Registradas na Semana ({periodo_str}) — {len(despesas_semana)} registro(s)",
            expanded=True,
        ):
            for item in despesas_semana:
                wc1, wc2, wc3, wc4 = st.columns([2, 3, 2, 1])
                wc1.write(f"📅 **{format_date_br(item['data_despesa'])}**")
                wc2.write(item["descricao"])
                wc3.write(f":red[**- {format_brl(item['valor'])}**]")
                if wc4.button("🗑️", key=f"del_semanal_{item['id']}", help="Excluir despesa semanal"):
                    excluir_despesa_semanal(item["id"])
                    st.rerun()

    if not despesas_semana and not receitas_semana:
        st.caption(f"Nenhuma despesa ou receita registrada para o período de {periodo_str}.")
