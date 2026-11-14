import json
import os
import urllib.request
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Tuple, Sequence

DEFAULT_TURSO_URL = "libsql://controledespesas-bestlinux.aws-us-east-2.turso.io"
DEFAULT_TURSO_TOKEN = ""


def _get_turso_credentials() -> Tuple[str, str]:
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")

    if not url or not token:
        try:
            import streamlit as st
            url = url or st.secrets.get("TURSO_DATABASE_URL", DEFAULT_TURSO_URL)
            token = token or st.secrets.get("TURSO_AUTH_TOKEN", DEFAULT_TURSO_TOKEN)
        except Exception:
            url = url or DEFAULT_TURSO_URL
            token = token or DEFAULT_TURSO_TOKEN

    # Converte libsql:// para https:// para comunicação via API Hrana v2 do Turso
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    url = url.rstrip("/")
    return f"{url}/v2/pipeline", token


def _encode_arg(val: Any) -> Dict[str, Any]:
    if val is None:
        return {"type": "null"}
    if isinstance(val, bool):
        return {"type": "integer", "value": "1" if val else "0"}
    if isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    if isinstance(val, float):
        return {"type": "float", "value": float(val)}
    return {"type": "text", "value": str(val)}


def _decode_cell(cell: Dict[str, Any]) -> Any:
    cell_type = cell.get("type")
    if cell_type == "null" or cell_type is None:
        return None
    if cell_type == "integer":
        return int(cell["value"])
    if cell_type == "float":
        return float(cell["value"])
    return cell.get("value")


def _execute_pipeline(statements: Sequence[Tuple[str, Sequence[Any]]]) -> List[List[Dict[str, Any]]]:
    """Executa uma ou mais queries no Turso Cloud em uma única chamada HTTP pipeline."""
    endpoint, token = _get_turso_credentials()
    requests_payload = []

    for sql, params in statements:
        stmt_obj: Dict[str, Any] = {"sql": sql}
        if params:
            stmt_obj["args"] = [_encode_arg(p) for p in params]
        requests_payload.append({"type": "execute", "stmt": stmt_obj})

    requests_payload.append({"type": "close"})

    req = urllib.request.Request(
        endpoint,
        data=json.dumps({"requests": requests_payload}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    all_results: List[List[Dict[str, Any]]] = []
    for item in data.get("results", []):
        if item.get("type") == "error":
            err_msg = item.get("error", {}).get("message", "Erro desconhecido no Turso Cloud")
            raise RuntimeError(f"Erro Turso SQL: {err_msg}")
        response = item.get("response", {})
        if response.get("type") == "execute":
            res = response.get("result", {})
            cols = [c["name"] for c in res.get("cols", [])]
            rows_parsed = []
            for raw_row in res.get("rows", []):
                row_dict = {cols[i]: _decode_cell(raw_row[i]) for i in range(len(cols))}
                rows_parsed.append(row_dict)
            all_results.append(rows_parsed)

    return all_results


def _query(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    results = _execute_pipeline([(sql, params)])
    return results[0] if results else []


def init_db() -> None:
    hoje = date.today()
    fim_semana = hoje + timedelta(days=6)

    _execute_pipeline([
        (
            """
            CREATE TABLE IF NOT EXISTS cartao_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                valor_fatura REAL NOT NULL DEFAULT 0.0,
                data_fechamento TEXT NOT NULL
            )
            """,
            (),
        ),
        (
            """
            CREATE TABLE IF NOT EXISTS cartao_despesas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                data_despesa TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """,
            (),
        ),
        (
            """
            CREATE TABLE IF NOT EXISTS semanal_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                valor_permitido REAL NOT NULL DEFAULT 0.0,
                data_inicio TEXT NOT NULL,
                data_fim TEXT NOT NULL
            )
            """,
            (),
        ),
        (
            """
            CREATE TABLE IF NOT EXISTS semanal_despesas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                data_despesa TEXT NOT NULL,
                periodo_semana TEXT NOT NULL DEFAULT '',
                criado_em TEXT NOT NULL
            )
            """,
            (),
        ),
        (
            "INSERT OR IGNORE INTO cartao_config (id, valor_fatura, data_fechamento) VALUES (1, 0.0, ?)",
            (hoje.isoformat(),),
        ),
        (
            "INSERT OR IGNORE INTO semanal_config (id, valor_permitido, data_inicio, data_fim) VALUES (1, 0.0, ?, ?)",
            (hoje.isoformat(), fim_semana.isoformat()),
        ),
    ])


# --- Funções Cartão de Crédito ---

def get_cartao_config() -> Dict[str, Any]:
    rows = _query("SELECT valor_fatura, data_fechamento FROM cartao_config WHERE id = 1")
    if not rows:
        init_db()
        rows = _query("SELECT valor_fatura, data_fechamento FROM cartao_config WHERE id = 1")
    return rows[0]


def update_cartao_config(valor_fatura: float, data_fechamento: date) -> None:
    _query(
        "UPDATE cartao_config SET valor_fatura = ?, data_fechamento = ? WHERE id = 1",
        (float(valor_fatura), data_fechamento.isoformat()),
    )


def registrar_despesa_cartao(valor: float, descricao: str = "Despesa no Cartão", data_despesa: date = None) -> None:
    if data_despesa is None:
        data_despesa = date.today()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute_pipeline([
        (
            "INSERT INTO cartao_despesas (descricao, valor, data_despesa, criado_em) VALUES (?, ?, ?, ?)",
            (descricao.strip() or "Despesa no Cartão", float(valor), data_despesa.isoformat(), agora),
        ),
        (
            "UPDATE cartao_config SET valor_fatura = valor_fatura + ? WHERE id = 1",
            (float(valor),),
        ),
    ])


def listar_despesas_cartao() -> List[Dict[str, Any]]:
    return _query(
        "SELECT id, descricao, valor, data_despesa, criado_em FROM cartao_despesas ORDER BY id DESC"
    )


def excluir_despesa_cartao(despesa_id: int) -> None:
    rows = _query("SELECT valor FROM cartao_despesas WHERE id = ?", (int(despesa_id),))
    if rows:
        valor = float(rows[0]["valor"])
        _execute_pipeline([
            ("DELETE FROM cartao_despesas WHERE id = ?", (int(despesa_id),)),
            ("UPDATE cartao_config SET valor_fatura = MAX(0, valor_fatura - ?) WHERE id = 1", (valor,)),
        ])


# --- Funções Despesas Semanais ---

def get_semanal_config() -> Dict[str, Any]:
    rows = _query("SELECT valor_permitido, data_inicio, data_fim FROM semanal_config WHERE id = 1")
    if not rows:
        init_db()
        rows = _query("SELECT valor_permitido, data_inicio, data_fim FROM semanal_config WHERE id = 1")
    return rows[0]


def update_semanal_config(valor_permitido: float, data_inicio: date, data_fim: date) -> None:
    _query(
        "UPDATE semanal_config SET valor_permitido = ?, data_inicio = ?, data_fim = ? WHERE id = 1",
        (float(valor_permitido), data_inicio.isoformat(), data_fim.isoformat()),
    )


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
    _query(
        """
        INSERT INTO semanal_despesas (descricao, valor, data_despesa, periodo_semana, criado_em)
        VALUES (?, ?, ?, ?, ?)
        """,
        (descricao.strip() or "Despesa Semanal", float(valor), data_despesa.isoformat(), periodo, agora),
    )


def listar_despesas_semanais(data_inicio: date = None, data_fim: date = None) -> List[Dict[str, Any]]:
    if data_inicio and data_fim:
        periodo = _format_periodo(data_inicio, data_fim)
        return _query(
            """
            SELECT id, descricao, valor, data_despesa, periodo_semana, criado_em
            FROM semanal_despesas
            WHERE (data_despesa BETWEEN ? AND ?) OR (periodo_semana = ?)
            ORDER BY data_despesa DESC, id DESC
            """,
            (data_inicio.isoformat(), data_fim.isoformat(), periodo),
        )
    return _query(
        """
        SELECT id, descricao, valor, data_despesa, periodo_semana, criado_em
        FROM semanal_despesas
        ORDER BY data_despesa DESC, id DESC
        """
    )


def calcular_saldo_semanal(valor_permitido: float, data_inicio: date, data_fim: date) -> Tuple[float, float]:
    """Retorna (total_gasto_na_semana, valor_disponivel_apos_subtracao)."""
    periodo = _format_periodo(data_inicio, data_fim)
    rows = _query(
        """
        SELECT COALESCE(SUM(valor), 0.0) as total_gasto
        FROM semanal_despesas
        WHERE (data_despesa BETWEEN ? AND ?) OR (periodo_semana = ?)
        """,
        (data_inicio.isoformat(), data_fim.isoformat(), periodo),
    )
    total_gasto = float(rows[0]["total_gasto"]) if rows else 0.0
    saldo_restante = valor_permitido - total_gasto
    return total_gasto, saldo_restante


def excluir_despesa_semanal(despesa_id: int) -> None:
    _query("DELETE FROM semanal_despesas WHERE id = ?", (int(despesa_id),))
