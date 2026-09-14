"""Testes da Hipótese 05 (barras sintéticas; sem rede, sem MT5).  Rodar:  python tests_sentinela.py"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta

import pandas as pd

from robo.estrategia_sentinela import (WIN_H05, ParametrosSentinela, agrega_m5, backtest_sentinela,
                                       contribuicao_saidas, dias_validos, dimensiona_h05, fechamentos_diarios,
                                       lado_permitido, sma_previa)
from robo.risco import GestorRisco, ParametrosRisco
import main_sentinela as ms


def dia_m1(dia: date, preco: float = 170000.0, ini: str = "09:00", fim: str = "18:20", volume: int = 100) -> pd.DataFrame:
    """Pregão plano em M1 (barras iguais) — a base para injetar movimentos."""
    idx = pd.date_range(datetime.combine(dia, time.fromisoformat(ini)), datetime.combine(dia, time.fromisoformat(fim)), freq="1min")
    return pd.DataFrame({"open": preco, "high": preco, "low": preco, "close": preco, "volume": volume}, index=idx)


def rompimento_compra(dia: date, preco: float = 170000.0, volume_gatilho: int = 400, pos_gatilho: str = "sobe",
                      **kw) -> pd.DataFrame:
    """Range 09:05–10:30 de 1000 pts (169500–170500); gatilho às 11:00–11:05 fechando em 170600 (+100 de folga);
    depois `pos_gatilho`: 'sobe' (vai a 171300 = alvo 500 além), 'stop' (cai 300), 'lateral' (fica)."""
    df = dia_m1(dia, preco, **kw)
    # range: uma barra alta e uma baixa dentro da janela
    df.loc[datetime.combine(dia, time(9, 30)), ["high"]] = preco + 500
    df.loc[datetime.combine(dia, time(9, 45)), ["low"]] = preco - 500
    # VWAP: preço fica em `preco` -> vwap ~ preco; gatilho fecha acima
    t0 = datetime.combine(dia, time(11, 0))
    for k in range(5):
        ts = t0 + timedelta(minutes=k)
        df.loc[ts, ["open", "high", "low", "close", "volume"]] = [preco + 550 + 10 * k, preco + 600, preco + 540, preco + 560 + 10 * k, volume_gatilho]
    df.loc[t0 + timedelta(minutes=4), "close"] = preco + 600            # fecha 170600 >= 170500 + 30
    # barra seguinte (11:05): abertura = entrada
    t1 = datetime.combine(dia, time(11, 5))
    df.loc[t1, ["open", "high", "low", "close"]] = [preco + 600, preco + 600, preco + 600, preco + 600]
    if pos_gatilho == "sobe":
        for k in range(1, 30):
            ts = t1 + timedelta(minutes=k)
            p = preco + 600 + 30 * k
            df.loc[ts, ["open", "high", "low", "close"]] = [p, p + 10, p - 10, p]
    elif pos_gatilho == "stop":
        for k in range(1, 30):
            ts = t1 + timedelta(minutes=k)
            p = preco + 600 - 30 * k
            df.loc[ts, ["open", "high", "low", "close"]] = [p, p + 10, p - 10, p]
    else:
        for ts in df.index[df.index > t1]:
            df.loc[ts, ["open", "high", "low", "close"]] = [preco + 600] * 4
    return df


def base(dias: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(dias).sort_index()


def d1_serie(primeiro_dia: date, n: int = 25, nivel: float = 160000.0) -> pd.Series:
    """n fechamentos diários ANTES de primeiro_dia, todos em `nivel` (SMA = nivel)."""
    datas = [primeiro_dia - timedelta(days=i) for i in range(n, 0, -1)]
    return pd.Series([nivel] * n, index=datas)


class TestPreparacao(unittest.TestCase):
    def test_dias_validos_descarta_incompleto_e_buraco(self):
        d1 = dia_m1(date(2026, 3, 2))
        d2 = dia_m1(date(2026, 3, 3), fim="12:00")                          # incompleto
        d3 = dia_m1(date(2026, 3, 4)).drop(datetime(2026, 3, 4, 13, 0))      # buraco
        df, desc = dias_validos(base([d1, d2, d3]), 400)
        self.assertEqual(sorted(set(df.index.date)), [date(2026, 3, 2)])
        self.assertEqual([d for d, _ in desc], [date(2026, 3, 3), date(2026, 3, 4)])

    def test_agrega_m5_e_horario_absoluto(self):
        df = dia_m1(date(2026, 3, 2), ini="09:02")                            # pregão começa 09:02
        m5 = agrega_m5(df)
        self.assertEqual(m5.index[0].time(), time(9, 0))                       # rótulo absoluto, não relativo
        self.assertEqual(int(m5.iloc[0]["volume"]), 300)                       # 09:02,03,04
        self.assertEqual(int(m5.iloc[1]["volume"]), 500)

    def test_sma_previa_e_lado(self):
        fech = pd.Series([100.0] * 20 + [110.0, 90.0], index=[date(2026, 1, 1) + timedelta(days=i) for i in range(22)])
        t = sma_previa(fech, 20)
        self.assertTrue(pd.isna(t.iloc[19]["sma_ant"]))                       # 20º dia: só 19 anteriores
        self.assertAlmostEqual(t.iloc[20]["sma_ant"], 100.0)                  # 21º dia: SMA dos 20 anteriores
        self.assertEqual(lado_permitido(110.0, 100.0), "compra")
        self.assertEqual(lado_permitido(90.0, 100.0), "venda")
        self.assertIsNone(lado_permitido(100.0, 100.0))
        self.assertIsNone(lado_permitido(float("nan"), 100.0))

    def test_fechamentos_diarios_com_aquecimento_d1(self):
        df = base([dia_m1(date(2026, 3, 2), 170000.0), dia_m1(date(2026, 3, 3), 171000.0)])
        d1 = d1_serie(date(2026, 3, 2), n=25)
        fech = fechamentos_diarios(df, d1)
        self.assertEqual(len(fech), 27)
        self.assertEqual(fech.loc[date(2026, 3, 3)], 171000.0)
        t = sma_previa(fech, 20)
        self.assertFalse(pd.isna(t.loc[date(2026, 3, 2)]["sma_ant"]))         # 1º pregão do M1 já tem SMA

    def test_dimensiona_h05(self):
        risco = GestorRisco(10000.0, ParametrosRisco(), WIN_H05)
        self.assertEqual(dimensiona_h05(risco, WIN_H05, 250.0, 5.0, 1.0), 1)   # 100 / 53 = 1
        risco.capital = 5000.0
        self.assertEqual(dimensiona_h05(risco, WIN_H05, 250.0, 5.0, 1.0), 0)   # piso = freio


class TestRegras(unittest.TestCase):
    def _roda(self, df, filtro=True, d1=None, **kw):
        risco = GestorRisco(10000.0, ParametrosRisco(), WIN_H05)
        params = ParametrosSentinela(filtro_tendencia=filtro, **kw)
        return backtest_sentinela(df, WIN_H05, params, risco, d1=d1)

    def test_gatilho_compra_entra_na_barra_seguinte_e_alvo(self):
        dia = date(2026, 3, 2)
        res, diag = self._roda(rompimento_compra(dia), filtro=False)
        self.assertEqual(diag.sinais, 1)
        self.assertEqual(len(res.trades), 1)
        t = res.trades[0]
        self.assertEqual(t.lado, "compra")
        self.assertEqual(t.hora_entrada, time(11, 5))                          # abertura da barra seguinte
        self.assertEqual(t.entrada, 170605.0)                                  # 170600 + 1 tick de slippage
        self.assertEqual(t.stop, 170355.0)
        self.assertEqual(t.alvo, 171105.0)
        self.assertEqual(t.contratos, 1)
        self.assertIn(t.motivo_saida, ("alvo", "stop_breakeven", "stop_trava_1R", "stop_trailing"))
        self.assertGreater(t.pnl_reais, 0)

    def test_folga_volume_vwap_e_range_vetam(self):
        dia = date(2026, 3, 2)
        fraco = rompimento_compra(dia, volume_gatilho=100)                      # volume = média -> < 1,2x
        self.assertEqual(self._roda(fraco, filtro=False)[1].sinais, 0)
        pouca_folga = rompimento_compra(dia)
        pouca_folga.loc[datetime(2026, 3, 2, 11, 4), "close"] = 170520.0       # só 20 pts acima do range
        self.assertEqual(self._roda(pouca_folga, filtro=False)[1].sinais, 0)
        range_grande = rompimento_compra(dia)
        range_grande.loc[datetime(2026, 3, 2, 9, 30), "high"] = 170000.0 + 2600.0   # range > 2500
        r, d = self._roda(range_grande, filtro=False)
        self.assertEqual(d.range_fora, 1)
        self.assertEqual(d.sinais, 0)
        range_pequeno = dia_m1(dia)                                             # range 0 < 300
        self.assertEqual(self._roda(range_pequeno, filtro=False)[1].range_fora, 1)

    def test_filtro_tendencia_veta_e_libera(self):
        dia = date(2026, 3, 2)
        df = rompimento_compra(dia)
        # SMA20 = 160000 < fechamento anterior? fech_ant = último D1 (160000) == SMA -> None -> veta
        r, d = self._roda(df, filtro=True, d1=d1_serie(dia, n=25, nivel=160000.0))
        self.assertEqual(d.sinais, 0)
        # fechamento anterior acima da SMA: libera compra
        d1 = d1_serie(dia, n=25, nivel=160000.0); d1.iloc[-1] = 165000.0
        r, d = self._roda(df, filtro=True, d1=d1)
        self.assertEqual(d.sinais, 1)
        # fechamento anterior abaixo da SMA: só venda -> compra vetada
        d1b = d1_serie(dia, n=25, nivel=160000.0); d1b.iloc[-1] = 150000.0
        r, d = self._roda(df, filtro=True, d1=d1b)
        self.assertEqual(d.sinais, 0)
        self.assertEqual(d.bloqueios_filtro, 1)
        # sem D1: sem SMA -> sem sinal (e o diagnóstico diz)
        r, d = self._roda(df, filtro=True, d1=None)
        self.assertEqual(d.sinais, 0)
        self.assertEqual(d.sem_sma, 1)

    def test_stop_inicial_no_m1_e_contagem_de_stops(self):
        dia = date(2026, 3, 2)
        res, diag = self._roda(rompimento_compra(dia, pos_gatilho="stop"), filtro=False)
        self.assertEqual(len(res.trades), 1)
        self.assertEqual(res.trades[0].motivo_saida, "stop")
        self.assertLess(res.trades[0].pnl_reais, 0)
        self.assertAlmostEqual(res.trades[0].saida, 170355.0 - 5.0)           # stop com 1 tick de slippage

    def test_stop_de_tempo_e_contrafactual(self):
        dia = date(2026, 3, 2)
        df = rompimento_compra(dia, pos_gatilho="lateral")
        res, _ = self._roda(df, filtro=False)
        self.assertEqual(res.trades[0].motivo_saida, "stop_tempo")
        self.assertEqual(res.trades[0].hora_saida, time(12, 5))               # 12 barras M5 após 11:05
        res2, _ = self._roda(df, filtro=False, desativar_stop_tempo=True)
        self.assertNotEqual(res2.trades[0].motivo_saida, "stop_tempo")         # sem a regra: segue até outra saída

    def test_reversao_vwap_fecha_em_duas_barras(self):
        dia = date(2026, 3, 2)
        df = rompimento_compra(dia, pos_gatilho="lateral")
        # após a entrada, o preço cai abaixo da VWAP (~170000) e fica lá, sem tocar o stop (170355)? não: 170000 < stop.
        # então: cai para 170400 (acima do stop 170355, abaixo da VWAP? VWAP ~170000+ -> não). Ajuste: VWAP alta.
        # Constrói VWAP alta: range em 171000 e gatilho em 172000 -> simplificar com preços deslocados:
        base_p = 170000.0
        # VWAP alta (~170400): volume grande em 170490 às 09:10-09:20 — dentro do range (169500-170500) e FORA da
        # janela de 20 barras M5 que define a média de volume do gatilho (11:00).
        for k in range(0, 10):
            ts = datetime(2026, 3, 2, 9, 10) + timedelta(minutes=k)
            df.loc[ts, ["open", "high", "low", "close", "volume"]] = [base_p + 490, base_p + 495, base_p + 485, base_p + 490, 5000]
        # depois da entrada (170605), o preço fica em 170380: acima do stop (170355) e ABAIXO da VWAP -> reversão em 2 barras
        for k in range(1, 40):
            ts = datetime(2026, 3, 2, 11, 5) + timedelta(minutes=k)
            df.loc[ts, ["open", "high", "low", "close"]] = [base_p + 380] * 4
        res, diag = self._roda(df, filtro=False)
        self.assertEqual(len(res.trades), 1)
        self.assertEqual(res.trades[0].motivo_saida, "reversao_vwap")
        self.assertEqual(res.trades[0].hora_saida, time(11, 15))               # 2 barras M5 fechadas contra
        res2, _ = self._roda(df, filtro=False, desativar_reversao_vwap=True)
        self.assertNotEqual(res2.trades[0].motivo_saida, "reversao_vwap")

    def test_zeragem_17h30_e_uma_posicao_por_vez(self):
        dia = date(2026, 3, 2)
        df = rompimento_compra(dia, pos_gatilho="lateral")
        res, _ = self._roda(df, filtro=False, max_barras_sem_1r=1000, desativar_reversao_vwap=True)
        self.assertEqual(res.trades[0].motivo_saida, "zeragem")
        self.assertEqual(res.trades[0].hora_saida, time(17, 30))
        self.assertEqual(len(res.trades), 1)

    def test_limites_do_dia(self):
        dia = date(2026, 3, 2)
        df = rompimento_compra(dia, pos_gatilho="stop")
        # depois do stop (~11:15), novos gatilhos a cada 20 min: 3 ops no dia no máximo, e cooldown de 15 min
        for j, h in enumerate((time(11, 40), time(12, 20), time(13, 0), time(13, 40))):
            t0 = datetime.combine(dia, h)
            for k in range(5):
                df.loc[t0 + timedelta(minutes=k), ["open", "high", "low", "close", "volume"]] = [170550, 170600, 170540, 170600, 400]
            t1 = t0 + timedelta(minutes=5)
            df.loc[t1, ["open", "high", "low", "close"]] = [170600] * 4
            for k in range(1, 15):
                p = 170600 - 30 * k
                df.loc[t1 + timedelta(minutes=k), ["open", "high", "low", "close"]] = [p, p + 10, p - 10, p]
        res, diag = self._roda(df, filtro=False)
        self.assertLessEqual(len(res.trades), 3)                                # máx 3 ops e 3 stops
        self.assertTrue(all(t.motivo_saida == "stop" for t in res.trades))

    def test_contribuicao_saidas(self):
        dia = date(2026, 3, 2)
        res, _ = self._roda(rompimento_compra(dia, pos_gatilho="lateral"), filtro=False)
        c = contribuicao_saidas(res)
        self.assertEqual(c["5. stop de tempo"]["n"], 1)
        self.assertEqual(c["4. reversão VWAP"]["n"], 0)
        self.assertIsNotNone(c["5. stop de tempo"]["media_rs"])


class TestTravas(unittest.TestCase):
    def _csv(self, pasta: str, nome: str, dias: list[date]) -> str:
        df = base([dia_m1(d) for d in dias])
        caminho = os.path.join(pasta, nome)
        df.reset_index().rename(columns={"index": "datetime"}).to_csv(caminho, index=False)
        return caminho

    def test_holdout_recusado_sem_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._csv(tmp, "win_holdout.csv", [date(2026, 7, 1)])
            df = pd.read_csv(c, parse_dates=["datetime"]).set_index("datetime")
            with self.assertRaises(SystemExit):
                ms.verificar_bloqueios(c, df)
            with self.assertRaises(SystemExit):                                 # holdout também contém bloco? não; só a trava
                ms.verificar_bloqueios("dados/win_holdout.csv", df)
            df2, notas = ms.verificar_bloqueios(c, df, liberar_holdout=True)   # só com autorização
            self.assertEqual(len(df2), len(df))

    def test_bloco_virgem_recusado_ate_40_pregoes_data_calculada(self):
        dias_uteis = [d.date() for d in pd.bdate_range("2026-08-12", periods=60)]
        with tempfile.TemporaryDirectory() as tmp:
            c = self._csv(tmp, "win$_1min.csv", [date(2026, 7, 20)] + dias_uteis[:15])   # 1 do holdout + 15 virgens
            df = pd.read_csv(c, parse_dates=["datetime"]).set_index("datetime")
            with self.assertRaises(SystemExit) as cm:
                ms.verificar_bloqueios(c, df)                                   # sem a flag: recusa
            self.assertIn("bloco virgem", str(cm.exception))
            with self.assertRaises(SystemExit) as cm:
                ms.verificar_bloqueios(c, df, bloco_virgem=True)                # com a flag, 15 < 40: recusa
            msg = str(cm.exception)
            self.assertIn("15 pregão", msg)
            prevista = ms.data_prevista_bloco(15, dias_uteis[14])
            self.assertIn(prevista.isoformat(), msg)                            # data calculada, não constante
            self.assertEqual(prevista, dias_uteis[39])                          # 25 dias úteis após o 15º = 40º
            c40 = self._csv(tmp, "win$_1min.csv", [date(2026, 7, 20)] + dias_uteis[:40])
            df40 = pd.read_csv(c40, parse_dates=["datetime"]).set_index("datetime")
            df_ok, notas = ms.verificar_bloqueios(c40, df40, bloco_virgem=True)
            self.assertEqual(min(df_ok.index.date), date(2026, 8, 12))          # holdout nunca avaliado
            self.assertTrue(any("descartados sem leitura" in n for n in notas))

    def test_insample_sem_bloco_passa(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._csv(tmp, "win_insample.csv", [date(2026, 3, 2), date(2026, 3, 3)])
            df = pd.read_csv(c, parse_dates=["datetime"]).set_index("datetime")
            df2, notas = ms.verificar_bloqueios(c, df)
            self.assertEqual(len(df2), len(df))
            self.assertEqual(notas, [])

    def test_veredicto_so_reprova(self):
        v, m = ms.veredicto_insample({"período todo": {"trades": 120, "fator_lucro": 1.5, "expectancia_por_trade_rs": 5.0},
                                      "1ª metade": {"trades": 60, "fator_lucro": 1.4}, "2ª metade": {"trades": 60, "fator_lucro": 0.9}})
        self.assertEqual(v, "MORTA")
        v, m = ms.veredicto_insample({"período todo": {"trades": 120, "fator_lucro": 1.5, "expectancia_por_trade_rs": 5.0},
                                      "1ª metade": {"trades": 60, "fator_lucro": 1.4}, "2ª metade": {"trades": 60, "fator_lucro": 1.2}})
        self.assertTrue(v.startswith("SOBREVIVE"))
        self.assertIn("não aprova", v)
        v, m = ms.veredicto_insample({"período todo": {"trades": 30}, "1ª metade": {}, "2ª metade": {}})
        self.assertEqual(v, "ILEGÍVEL")


if __name__ == "__main__":
    unittest.main(verbosity=1)
