"""Especificações dos minicontratos da B3.

Valores de referência (confirme margens e custos na sua corretora).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Contrato:
    codigo: str            # "WIN" ou "WDO"
    nome: str
    valor_ponto: float     # R$ por ponto por contrato
    tick: float            # oscilação mínima em pontos
    custo_rt: float        # custo ida+volta por contrato (corretagem+emolumentos), em R$
    slippage_ticks: int    # escorregão médio assumido na entrada/saída, em ticks

    @property
    def valor_tick(self) -> float:
        return self.tick * self.valor_ponto

    def arredonda_tick(self, preco: float) -> float:
        """Arredonda um preço para o múltiplo de tick mais próximo."""
        return round(round(preco / self.tick) * self.tick, 10)

    def pontos_para_reais(self, pontos: float, contratos: int = 1) -> float:
        return pontos * self.valor_ponto * contratos


WIN = Contrato(
    codigo="WIN",
    nome="Mini-índice Ibovespa",
    valor_ponto=0.20,
    tick=5.0,
    custo_rt=1.00,      # ex.: R$ 0,50 por lado; ajuste à sua corretora
    slippage_ticks=1,   # 1 tick = 5 pontos = R$ 1,00
)

WDO = Contrato(
    codigo="WDO",
    nome="Mini-dólar",
    valor_ponto=10.0,
    tick=0.5,
    custo_rt=2.00,
    slippage_ticks=1,   # 1 tick = 0,5 ponto = R$ 5,00
)

CONTRATOS = {"WIN": WIN, "WDO": WDO}
