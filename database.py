import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Tuple

DB_PATH = "financeiro.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    # Configurações do Cartão de Crédito
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cartao_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            valor_fatura REAL NOT NULL DEFAULT 0.0,
            data_fechamento TEXT NOT NULL
        )
    """)

    # Histórico de Despesas do Cartão de Crédito
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cartao_despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            data_despesa TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    # Configurações de Despesas Semanais
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semanal_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            valor_permitido REAL NOT NULL DEFAULT 0.0,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL
        )
    """)

    # Histórico de Despesas Semanais
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semanal_despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            data_despesa TEXT NOT NULL,
            periodo_semana TEXT NOT NULL DEFAULT '',
            criado_em TEXT NOT NULL
        )
    """)

    # Inicializa registro padrão de cartão se não existir
    cursor.execute("SELECT COUNT(*) as cnt FROM cartao_config WHERE id = 1")
    if cursor.fetchone()["cnt"] == 0:
        hoje = date.today().isoformat()
        cursor.execute(
            "INSERT INTO cartao_config (id, valor_fatura, data_fechamento) VALUES (1, 0.0, ?)",
            (hoje,),
        )

    # Inicializa registro padrão semanal se não existir
    cursor.execute("SELECT COUNT(*) as cnt FROM semanal_config WHERE id = 1")
    if cursor.fetchone()["cnt"] == 0:
        hoje = date.today()
        fim_semana = hoje + timedelta(days=6)
        cursor.execute(
            "INSERT INTO semanal_config (id, valor_permitido, data_inicio, data_fim) VALUES (1, 0.0, ?, ?)",
            (hoje.isoformat(), fim_semana.isoformat()),
        )

    conn.commit()
    conn.close()


# --- Funções Cartão de Crédito ---

def get_cartao_config() -> Dict[str, Any]:
    conn = get_connection()
    row = conn.execute("SELECT valor_fatura, data_fechamento FROM cartao_config WHERE id = 1").fetchone()
    conn.close()
    return dict(row)


def update_cartao_config(valor_fatura: float, data_fechamento: date) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE cartao_config SET valor_fatura = ?, data_fechamento = ? WHERE id = 1",
        (valor_fatura, data_fechamento.isoformat()),
    )
    conn.commit()
    conn.close()


def registrar_despesa_cartao(valor: float, descricao: str = "Despesa no Cartão", data_despesa: date = None) -> None:
    if data_despesa is None:
        data_despesa = date.today()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cartao_despesas (descricao, valor, data_despesa, criado_em) VALUES (?, ?, ?, ?)",
        (descricao.strip() or "Despesa no Cartão", valor, data_despesa.isoformat(), agora),
    )
    # Soma no Valor atual da Fatura
    cursor.execute(
        "UPDATE cartao_config SET valor_fatura = valor_fatura + ? WHERE id = 1",
        (valor,),
    )
    conn.commit()
    conn.close()


def listar_despesas_cartao() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, descricao, valor, data_despesa, criado_em FROM cartao_despesas ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def excluir_despesa_cartao(despesa_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT valor FROM cartao_despesas WHERE id = ?", (despesa_id,)).fetchone()
    if row:
        cursor.execute("DELETE FROM cartao_despesas WHERE id = ?", (despesa_id,))
        cursor.execute(
            "UPDATE cartao_config SET valor_fatura = MAX(0, valor_fatura - ?) WHERE id = 1",
            (row["valor"],),
        )
        conn.commit()
    conn.close()


# --- Funções Despesas Semanais ---

def get_semanal_config() -> Dict[str, Any]:
    conn = get_connection()
    row = conn.execute(
        "SELECT valor_permitido, data_inicio, data_fim FROM semanal_config WHERE id = 1"
    ).fetchone()
    conn.close()
    return dict(row)


def update_semanal_config(valor_permitido: float, data_inicio: date, data_fim: date) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE semanal_config SET valor_permitido = ?, data_inicio = ?, data_fim = ? WHERE id = 1",
        (valor_permitido, data_inicio.isoformat(), data_fim.isoformat()),
    )
    conn.commit()
    conn.close()


def _format_periodo(data_inicio: date, data_fim: date) -> str:
    return f"{data_inicio.isoformat()}_{data_fim.isoformat()}"


def registrar_despesa_semanal(
    valor: float,
    descricao: str = "Despesa Semanal",
    data_despesa: date = None,
    data_inicio_semana: date = None,
    data_fim_semana: date = None,
) -> None:
    if data_despesa is None:
        data_despesa = date.today()
    periodo = ""
    if data_inicio_semana and data_fim_semana:
        periodo = _format_periodo(data_inicio_semana, data_fim_semana)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO semanal_despesas (descricao, valor, data_despesa, periodo_semana, criado_em)
        VALUES (?, ?, ?, ?, ?)
        """,
        (descricao.strip() or "Despesa Semanal", valor, data_despesa.isoformat(), periodo, agora),
    )
    conn.commit()
    conn.close()


def listar_despesas_semanais(data_inicio: date = None, data_fim: date = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    if data_inicio and data_fim:
        periodo = _format_periodo(data_inicio, data_fim)
        rows = conn.execute(
            """
            SELECT id, descricao, valor, data_despesa, periodo_semana, criado_em
            FROM semanal_despesas
            WHERE (data_despesa BETWEEN ? AND ?) OR (periodo_semana = ?)
            ORDER BY data_despesa DESC, id DESC
            """,
            (data_inicio.isoformat(), data_fim.isoformat(), periodo),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, descricao, valor, data_despesa, periodo_semana, criado_em
            FROM semanal_despesas
            ORDER BY data_despesa DESC, id DESC
            """
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def calcular_saldo_semanal(valor_permitido: float, data_inicio: date, data_fim: date) -> Tuple[float, float]:
    """Retorna (total_gasto_na_semana, valor_disponivel_apos_subtracao)."""
    conn = get_connection()
    periodo = _format_periodo(data_inicio, data_fim)
    row = conn.execute(
        """
        SELECT COALESCE(SUM(valor), 0.0) as total_gasto
        FROM semanal_despesas
        WHERE (data_despesa BETWEEN ? AND ?) OR (periodo_semana = ?)
        """,
        (data_inicio.isoformat(), data_fim.isoformat(), periodo),
    ).fetchone()
    conn.close()
    total_gasto = float(row["total_gasto"])
    saldo_restante = valor_permitido - total_gasto
    return total_gasto, saldo_restante


def excluir_despesa_semanal(despesa_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM semanal_despesas WHERE id = ?", (despesa_id,))
    conn.commit()
    conn.close()
