"""Gestão de risco — as regras inegociáveis do robô.

- Risco por operação: percentual fixo do capital (padrão 1%).
- Posição dimensionada pelo stop: contratos = risco_R$ ÷ (stop_pontos × valor_ponto).
- Limite de perda diária (padrão 3% do capital no início do dia):
  atingiu, o robô para de operar até o dia seguinte (circuit breaker).
- Limite máximo de contratos como trava de segurança adicional.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contratos import Contrato


@dataclass
class ParametrosRisco:
    risco_por_trade_pct: float = 1.0    # % do capital arriscado por operação
    perda_maxima_dia_pct: float = 3.0   # % do capital; atingiu, para o dia
    max_contratos: int = 10             # trava de segurança absoluta


class GestorRisco:
    def __init__(self, capital_inicial: float, params: ParametrosRisco, contrato: Contrato):
        self.capital = capital_inicial
        self.params = params
        self.contrato = contrato
        self._capital_inicio_dia = capital_inicial
        self._pnl_dia = 0.0

    def novo_dia(self) -> None:
        self._capital_inicio_dia = self.capital
        self._pnl_dia = 0.0

    @property
    def bloqueado_no_dia(self) -> bool:
        limite = -self._capital_inicio_dia * self.params.perda_maxima_dia_pct / 100.0
        return self._pnl_dia <= limite

    def dimensiona(self, stop_pontos: float) -> int:
        """Número de contratos pelo risco definido. 0 = não opera."""
        if stop_pontos <= 0:
            return 0
        risco_reais = self.capital * self.params.risco_por_trade_pct / 100.0
        risco_por_contrato = stop_pontos * self.contrato.valor_ponto + self.contrato.custo_rt
        n = int(risco_reais // risco_por_contrato)
        return max(0, min(n, self.params.max_contratos))

    def registra_resultado(self, pnl_reais: float) -> None:
        self.capital += pnl_reais
        self._pnl_dia += pnl_reais
