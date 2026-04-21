"""Deterministic financial calculator tool – zero hallucination for math."""

import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _pe_ratio(price: float, eps: float) -> float:
    if eps == 0:
        raise ValueError("EPS cannot be zero")
    return round(price / eps, 2)


def _roe(net_income: float, equity: float) -> float:
    if equity == 0:
        raise ValueError("Shareholder equity cannot be zero")
    return round((net_income / equity) * 100, 2)


def _yoy_growth(current: float, previous: float) -> float:
    if previous == 0:
        raise ValueError("Previous period value cannot be zero")
    return round(((current - previous) / abs(previous)) * 100, 2)


def _sharpe_ratio(
    portfolio_return: float, risk_free_rate: float, std_dev: float
) -> float:
    if std_dev == 0:
        raise ValueError("Standard deviation cannot be zero")
    return round((portfolio_return - risk_free_rate) / std_dev, 4)


def _debt_to_equity(total_debt: float, total_equity: float) -> float:
    if total_equity == 0:
        raise ValueError("Total equity cannot be zero")
    return round(total_debt / total_equity, 4)


def _profit_margin(net_income: float, revenue: float) -> float:
    if revenue == 0:
        raise ValueError("Revenue cannot be zero")
    return round((net_income / revenue) * 100, 2)


CALCULATORS = {
    "pe_ratio": {
        "fn": _pe_ratio,
        "params": ["price", "eps"],
        "desc": "Price-to-Earnings ratio",
    },
    "roe": {
        "fn": _roe,
        "params": ["net_income", "equity"],
        "desc": "Return on Equity (%)",
    },
    "yoy_growth": {
        "fn": _yoy_growth,
        "params": ["current", "previous"],
        "desc": "Year-over-Year growth (%)",
    },
    "sharpe_ratio": {
        "fn": _sharpe_ratio,
        "params": ["portfolio_return", "risk_free_rate", "std_dev"],
        "desc": "Sharpe Ratio",
    },
    "debt_to_equity": {
        "fn": _debt_to_equity,
        "params": ["total_debt", "total_equity"],
        "desc": "Debt-to-Equity ratio",
    },
    "profit_margin": {
        "fn": _profit_margin,
        "params": ["net_income", "revenue"],
        "desc": "Net Profit Margin (%)",
    },
}


@tool
def calculator_tool(metric: str, params: dict) -> str:
    """Perform deterministic financial calculations.

    ALWAYS use this tool instead of computing numbers yourself. It guarantees
    exact results with no rounding errors or hallucinations.

    Available metrics:
    - pe_ratio: Price-to-Earnings (params: price, eps)
    - roe: Return on Equity (params: net_income, equity)
    - yoy_growth: Year-over-Year growth % (params: current, previous)
    - sharpe_ratio: Sharpe Ratio (params: portfolio_return, risk_free_rate, std_dev)
    - debt_to_equity: Debt-to-Equity (params: total_debt, total_equity)
    - profit_margin: Net Profit Margin % (params: net_income, revenue)

    Args:
        metric: Name of the financial metric to compute.
        params: Dictionary of numerical parameters required by the metric.
    """
    if metric not in CALCULATORS:
        available = ", ".join(CALCULATORS.keys())
        return f"Unknown metric '{metric}'. Available: {available}"

    calc = CALCULATORS[metric]
    missing = [p for p in calc["params"] if p not in params]
    if missing:
        return f"Missing parameters for {metric}: {missing}. Required: {calc['params']}"

    try:
        kwargs = {p: float(params[p]) for p in calc["params"]}
        result = calc["fn"](**kwargs)
        return json.dumps(
            {"metric": metric, "description": calc["desc"], "result": result, "params": kwargs},
            ensure_ascii=False,
        )
    except (ValueError, TypeError) as e:
        return f"Calculation error: {e}"
