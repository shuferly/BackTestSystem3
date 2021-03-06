
from lib.simulator.base import BacktestSys, HoldingClass, DataClass
import numpy as np
import re
import pandas as pd
import traceback

class BasisSpread(BacktestSys):

    def strategy(self, num, profit_window, iv_window, long_window, short_window):

        future_price = self.data['future_price']
        spot_price = self.data['spot_price']
        profit_rate = self.data['profit_rate']
        inventory = self.data['inventory']
        future_index = self.data['future_index']
        df_profit = pd.DataFrame(index=self.dt)
        for k, v in profit_rate.items():
            df_profit[v.commodity] = v.upper_profit_rate

        # ========================回测的时候需要======================
        # PVC/RU/TA/BU的利润率需要往后移一天
        df_profit[['V', 'RU']] = df_profit[['V', 'RU']].shift(periods=1)

        df_profit.fillna(method='ffill', inplace=True)
        profit_mean = df_profit.rolling(window=profit_window).mean()
        profit_std = df_profit.rolling(window=profit_window).std()
        df_profit = (df_profit - profit_mean) / profit_std
        # df_profit = df_profit.rolling(window=60, min_periods=50).mean()
        # profit_chg = df_profit.pct_change(periods=20)

        iv_df = pd.DataFrame(index=self.dt)
        sp_df = pd.DataFrame(index=self.dt)
        fp_df = pd.DataFrame(index=self.dt)
        index_vol = pd.DataFrame(index=self.dt)
        index_oi = pd.DataFrame(index=self.dt)

        for k, v in inventory.items():
            if 'inventory' in v.__dict__ and v.commodity not in iv_df:
                iv_df[v.commodity] = v.inventory
            elif 'inventory' in v.__dict__ and v.commodity in iv_df:
                iv_df[v.commodity] += v.inventory
            elif 'CLOSE' in v.__dict__ and v.commodity not in iv_df:
                iv_df[v.commodity] = v.CLOSE
            elif 'CLOSE' in v.__dict__ and v.commodity in iv_df:
                iv_df[v.commodity] += v.CLOSE

        # =============回测的时候需要=================
        # L和PP的库存需要往后移一周
        iv_df[['L', 'PP']] = iv_df[['L', 'PP']].shift(periods=5)

        for k, v in spot_price.items():
            if 'price' in v.__dict__:
                sp_df[v.commodity] = v.price
            elif 'CLOSE' in v.__dict__:
                sp_df[v.commodity] = v.CLOSE

        sp_df.fillna(method='ffill', inplace=True)

        for k, v in future_price.items():
            fp_df[v.commodity] = v.CLOSE
            if v.commodity == 'FU':
                fp_df.loc[:'2018-07-16', 'FU'] = np.nan
        fp_df.to_csv(r'C:\Users\uuuu\Desktop\fp_df.csv')

        def remove_invalid(fp_df, df):
            for commodity in df.columns:
                first_day = fp_df[commodity].dropna().index[0]
                df.loc[:first_day, commodity] = np.nan

        for k, v in future_index.items():
            index_vol[v.commodity] = v.VOLUME
            index_oi[v.commodity] = v.OI

        oi_short_mean = index_oi.rolling(window=short_window).mean()
        oi_long_mean = index_oi.rolling(window=long_window).mean()
        oi_chg = oi_short_mean / oi_long_mean

        vol_short_mean = index_vol.rolling(window=short_window).mean()
        vol_long_mean = index_vol.rolling(window=long_window).mean()
        vol_chg = vol_short_mean / vol_long_mean

        df_profit = df_profit * oi_chg * vol_chg
        df_profit.dropna(axis=1, inplace=True, how='all')
        remove_invalid(fp_df, df_profit)

        profit_rank = df_profit.rank(axis=1)
        profit_count = profit_rank.count(axis=1)

        holdings_profit_num = np.minimum(profit_count // 2, num)
        holdings_profit_num[holdings_profit_num == 0] = np.nan

        # 库存变化率
        # iv_df = iv_df.shift(periods=1)
        iv_mean = iv_df.rolling(window=iv_window).mean()
        iv_std = iv_df.rolling(window=iv_window).std()
        iv_change = (iv_df - iv_mean) / iv_std

        iv_change = iv_change * oi_chg * vol_chg
        remove_invalid(fp_df, iv_change)

        # iv_change = iv_df.pct_change(periods=5)
        iv_rank = iv_change.rank(axis=1)
        iv_rank_count = iv_rank.count(axis=1)

        holdings_iv_num = np.minimum(iv_rank_count // 2, num)
        holdings_iv_num[holdings_iv_num == 0] = np.nan

        sp_df['I'] = sp_df['I'] / 0.92
        sp_df['FU'] = (sp_df['FU']+7) * self.dollar2rmb.CLOSE
        # ================回测的时候需要========================
        # 现货价格需要往后移一天
        # sp_df = sp_df.shift(periods=1)

        bs_df = 1 - fp_df[sp_df.columns] / sp_df
        # bs_df = sp_df - fp_df[sp_df.columns]
        # bs_mean = bs_df.rolling(window=250, min_periods=200).mean()
        # bs_std = bs_df.rolling(window=250, min_periods=200).std()
        # bs_df = (bs_df - bs_mean) / bs_std

        # bs_df = bs_df * oi_chg * vol_chg

        bs_rank = bs_df.rank(axis=1)
        bs_rank_count = bs_rank.count(axis=1)

        holdings_bs_num = np.minimum(bs_rank_count // 2, num)
        holdings_bs_num[holdings_bs_num == 0] = np.nan

        rtn_df = fp_df.pct_change(periods=10)
        rtn_df = rtn_df * vol_chg * oi_chg
        rtn_rank = rtn_df.rank(axis=1)
        rtn_count = rtn_rank.count(axis=1)
        holdings_rtn_num = np.minimum(rtn_count // 2, num)
        holdings_rtn_num[holdings_rtn_num == 0] = np.nan

        holdings_df = pd.DataFrame(0, index=self.dt, columns=list(future_price.keys()))

        iv_rank.to_csv(r'C:\Users\uuuu\Desktop\iv_rank.csv')
        bs_rank.to_csv(r'C:\Users\uuuu\Desktop\bs_rank.csv')
        profit_rank.to_csv(r'C:\Users\uuuu\Desktop\profit_rank.csv')

        for c in holdings_df:
            for k, v in future_price.items():
                if k == c:

                    holdings_df[c][iv_rank[v.commodity] > iv_rank_count - holdings_iv_num] += -1
                    holdings_df[c][iv_rank[v.commodity] <= holdings_iv_num] += 1

                    holdings_df[c][bs_rank[v.commodity] > bs_rank_count - holdings_bs_num] += 1
                    holdings_df[c][bs_rank[v.commodity] <= holdings_bs_num] += -1

                    if v.commodity not in profit_rank:
                        continue
                    holdings_df[c][profit_rank[v.commodity] > profit_count - holdings_profit_num] += -1
                    holdings_df[c][profit_rank[v.commodity] <= holdings_profit_num] += 1

                    # holdings_df[c][rtn_rank[v.commodity] > rtn_count - holdings_rtn_num] += 1
                    # holdings_df[c][rtn_rank[v.commodity] <= holdings_rtn_num] = -1

        holdings = HoldingClass(self.dt)

        for c in holdings_df:
            holdings.add_holdings(c, holdings_df[c].values.flatten())

        return holdings

    def optimal(self):
        test_df = pd.DataFrame(columns=['num', 'profit_window', 'iv_window', 'short_window', 'long_window'])
        final_df = pd.DataFrame(columns=['num', 'profit_window', 'iv_window', 'short_window', 'long_window', 'AnnualRtn',
                                         'AnnualVol', 'Sharpe', 'MaxDrawdown', 'MaxDDStart', 'MaxDDEnd', 'Turnover',
                                         'Days', 'NetValueInit', 'NetValueFinal'])
        count = 1
        total = len([3, 4, 5])*len(range(10, 200, 10))*len(range(10, 100, 10))*len(range(5, 30, 5))*len(range(5, 30, 5))
        try:
            for num in [3, 4, 5]:
                for profit_window in range(10, 200, 10):
                    for iv_window in range(10, 100, 10):
                        for short_window in range(5, 30, 5):
                            for gap in range(5, 30, 5):
                                pctg = count/total*100
                                print('\r'+'进度:{:.4f}%|{}|'.format(pctg, '>'*int(pctg)+'-'*(100-int(pctg))), end='')
                                holdings = self.strategy(num, profit_window, iv_window, short_window + gap, short_window)
                                holdings = self.holdingsStandardization(holdings, mode=1)
                                holdings = self.holdingsProcess(holdings)
                                res_df = self.getTotalResult(holdings, show=False)
                                test_df.loc[count-1] = [num, profit_window, iv_window, short_window, short_window+gap]
                                final_df.loc[count-1] = test_df.loc[count-1].append(res_df.loc['total'])
                                count += 1
        except:
            final_df.to_csv(r'C:\Users\uuuu\Desktop\optimal.csv', encoding='gbk')
            traceback.print_exc()
        finally:
            final_df.to_csv(r'C:\Users\uuuu\Desktop\optimal.csv', encoding='gbk')
        # max_id = final_df['NV'].idxmax()
        # for x in ['num', 'profit_window', 'iv_window', 'short_window', 'long_window', 'NV']:
        #     print('{}:{}'.format(x, final_df[x][max_id]))

    def multi_strategy(self):
        holdings = HoldingClass(self.dt)

        strategy_dict = {'AnnualRtn': self.strategy(3, 150, 90, 30, 25),  # 年均收益率最大
                         'sharp': self.strategy(5, 190, 80, 40, 15),  # 夏普值最大
                         'MaxDrawdown': self.strategy(4, 20, 90, 30, 5),  # 最大回撤最小
                         'current': self.strategy(3, 20, 60, 20, 5),
                         }

        for k, v in strategy_dict.items():
            for c in v.asset:
                if c not in holdings.asset:
                    holdings.add_holdings(c, getattr(v, c))
                else:
                    holdings.update_holdings(c, getattr(holdings, c)+getattr(v, c))

        holdings = self.holdingsStandardization(holdings, mode=1)
        holdings = self.holdingsProcess(holdings)
        self.displayResult(holdings, saveLocal=True)


if __name__ == '__main__':
    a = BasisSpread()
    holdings = a.strategy(3, 20, 60, 20, 5)
    # holdings = a.strategy(5, 190, 80, 40, 15)
    holdings = a.holdingsStandardization(holdings, mode=1)
    holdings = a.holdingsProcess(holdings)
    holdings.to_frame().to_csv(r'C:\Users\uuuu\Desktop\holdings.csv', encoding='gbk')
    #
    a.displayResult(holdings, saveLocal=True)
    # a.optimal()
    # a.multi_strategy()


