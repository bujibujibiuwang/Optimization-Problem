import pandas as pd
from pulp import *
from System import System
from collections import defaultdict

class FirstModel:
    def __init__(self, system: System):
        self.system = system
        self.x_vars = {}
        self.y_vars = {}
        self.z_vars = {}

    def solve(self):
        self.model = LpProblem(name=f'BatchOptFirstModel', sense=LpMinimize)
        self.add_vars()
        self.add_cons()
        self.add_objs()
        self.model.writeLP(f'../Result/BatchOptFirstModel.lp')
        self.model.solve(GUROBI(timeLimit=self.system.solve_time,
                                logPath=f'../Result/BatchOptFirstModel.log'))
        self.record_solve_result()

    def add_vars(self):
        # x(bp)：波次b包含样式p的包裹数
        # y(bw)：波次b是否包含仓库w
        # z(b)：波次b是否被使用
        for b in range(1, self.system.batch_nb[1] + 1):
            for p in self.system.ware_pattern_dict.keys():
                self.x_vars[(b, p)] = LpVariable(name=f'batch {b} use pattern {p}', lowBound=0, cat=LpInteger)
            for w in self.system.ware_dict.values():
                self.y_vars[(b, w)] = LpVariable(name=f'batch {b} include warehouse {w}',
                                                 lowBound=0, upBound=1, cat=LpBinary)
            self.z_vars[b] = LpVariable(name=f'batch:{b} if used', lowBound=0, upBound=1, cat=LpBinary)

    def add_cons(self):
        self.batch_nb_cons()
        self.wp_map_package_cons()
        self.single_batch_cons()
        self.batch_map_ware_cons()

    def batch_nb_cons(self):
        # 约束(1) 保证分配的波次数量
        lhs = 0
        for b in self.z_vars.keys():
            lhs += self.z_vars[b]
        self.model += (self.system.batch_nb[0] <= lhs <= self.system.batch_nb[1],
                              f'batch must be used')

    def wp_map_package_cons(self):
        # 约束(2) 保证模式使用次数和其包裹数量匹配
        for pattern_key, pattern_obj in self.system.ware_pattern_dict.items():
            lhs = 0
            for (b, p) in self.x_vars.keys():
                if pattern_key == p:
                    lhs += self.x_vars[(b, p)]
            self.model += (lhs == pattern_obj.package_nb, f'{pattern_key} number match')

    def single_batch_cons(self):
        # 约束(3) 保证单一波次商品件数在区间[G1,G2]中
        # 约束(4) 保证单一波次包裹数量在区间[P1,P2]中
        for batch_key in range(1, self.system.batch_nb[1] + 1):
            lhs_good_nb, lhs_pack_nb = 0, 0
            for (b, p) in self.x_vars.keys():
                if b == batch_key:
                    pattern_obj = self.system.ware_pattern_dict[p]
                    lhs_pack_nb += self.x_vars[(b, p)]
                    lhs_good_nb += self.x_vars[(b, p)] * pattern_obj.goods_quantity
            self.model += (lhs_pack_nb >= self.system.package_limit[0] * self.z_vars[batch_key],
                                  f'{batch_key} package limit low')
            self.model += (lhs_pack_nb <= self.system.package_limit[1] * self.z_vars[batch_key],
                                  f'{batch_key} package limit up')
            self.model += (lhs_good_nb >= self.system.goods_limit[0] * self.z_vars[batch_key],
                                  f'{batch_key} good limit low')
            self.model += (lhs_good_nb <= self.system.goods_limit[1] * self.z_vars[batch_key],
                                  f'{batch_key} good limit up')

    def batch_map_ware_cons(self):
        # 约束(5) 确认波次b是否用到仓库w
        for b in range(1, self.system.batch_nb[1] + 1):
            for w in self.system.ware_dict.values():
                lhs = 0
                for p in self.system.ware_pattern_dict.keys():
                    if w in p[1:]:
                        lhs += self.x_vars[(b, p)]
                big_M = len(self.system.package_dict.keys())
                rhs = big_M * self.y_vars[(b, w)]
                self.model += (lhs <= rhs, f'{b} use {w}')

    def add_objs(self):
        # 每个波次使用的仓库数总和
        objs = 0
        for (b, w) in self.y_vars.keys():
            objs += self.y_vars[(b, w)]
        self.model += (objs, f'minimize warehouse count ')

    def record_solve_result(self):
        for b, var in self.z_vars.items():
            if var.varValue > 1e-5:
                self.system.if_batch_use[b] = True
            else:
                self.system.if_batch_use[b] = False
        for (b, wp), var in self.x_vars.items():
            if var.varValue > 1e-5:
                if b not in self.system.batch_wp_count.keys():
                    self.system.batch_wp_count[b] = {}
                self.system.batch_wp_count[b][wp] = var.varValue

class SecondModel:
    def __init__(self, system: System):
        self.system = system
        self.x_vars = {}
        self.y_vars = {}

    def solve(self):
        self.model = LpProblem(name=f'BatchOptSecondModel', sense=LpMinimize)
        self.add_vars()
        self.add_cons()
        self.add_objs()
        self.model.writeLP(f'../Result/BatchOptSecondModel.log')
        self.model.solve(GUROBI(timeLimit=self.system.solve_time,
                                logPath=f'../Result/BatchOptSecondModel.log'))
        self.record_solve_result()

    def add_vars(self):
        # (1) x(bp): 波次b使用库区模式p的次数
        # (2) y(ba)：波次b是否用到区域a
        for b in range(1, self.system.batch_nb[1] + 1):
            if self.system.if_batch_use[b]:
                for ware_pattern in self.system.batch_wp_count[b].keys():
                    ware_pattern_obj = self.system.ware_pattern_dict[ware_pattern]
                    for area_pattern in ware_pattern_obj.area_pattern_list:
                        self.x_vars[(b, area_pattern)] = LpVariable(name=f'batch:{b} use pattern:{area_pattern}',
                                                                    lowBound=0, cat=LpInteger)
            for a in self.system.area_dict.values():
                self.y_vars[(b, a)] = LpVariable(name=f'batch:{b} use area:{a}', lowBound=0, cat=LpBinary)

    def add_cons(self):
        self.batch_map_area_cons()
        self.batch_ap_map_wp_cons()
        self.ap_map_package_cons()

    def batch_map_area_cons(self):
        # (1) 确认波次b用到区域a
        batch_area_map_x_index = defaultdict(list)
        for (b, ap) in self.x_vars.keys():
            for a in ap[1:]:
                batch_area_map_x_index[(b, a)].append((b, ap))
        for (b, a) in batch_area_map_x_index.keys():
            lhs, rhs = 0, self.y_vars[(b, a)]
            for (b, ap) in batch_area_map_x_index[(b, a)]:
                lhs += self.x_vars[(b, ap)]
            big_M = len(self.system.package_dict.keys())
            self.model += (lhs <= rhs * big_M, f'batch:{b} use area:{a} cons')

    def batch_ap_map_wp_cons(self):
        # (2) 波次b使用库区模式的次数要和使用仓库模式次数匹配
        for batch, wp_count_dict in self.system.batch_wp_count.items():
            for wp, count in wp_count_dict.items():
                lhs, rhs = 0, count
                for ap in self.system.ware_pattern_dict[wp].area_pattern_list:
                    lhs += self.x_vars[(batch, ap)]
                self.model += (lhs == rhs, f'batch:{batch} use area match ware:{wp} cons')

    def ap_map_package_cons(self):
        # (3) 每个库区模式被各个波次使用的数量与包裹数量匹配
        area_pattern_map_x_index = defaultdict(list)
        for (b, ap) in self.x_vars.keys():
            area_pattern_map_x_index[ap].append((b, ap))
        for ap in self.system.area_pattern_dict.keys():
            lhs, rhs = 0, self.system.area_pattern_dict[ap].package_nb
            for (b, ap) in area_pattern_map_x_index[ap]:
                lhs += self.x_vars[(b, ap)]
            self.model += (lhs == rhs, f'area_pattern:{ap} package nb cons')

    def add_objs(self):
        # 最小化波次使用的不同区域的次数
        objs = 0
        for (b, a) in self.y_vars.keys():
            objs += self.y_vars[(b, a)]
        self.model += (objs, f'minimize area count')
    
    def record_solve_result(self):
        for (b, ap), var in self.x_vars.items():
            if var.varValue > 1e-5:
                if b not in self.system.batch_ap_count.keys():
                    self.system.batch_ap_count[b] = {}
                self.system.batch_ap_count[b][ap] = var.varValue


class Result:
    def __init__(self, system: System):
        self.system = system

    def export_solve_result(self):
        res_matrix = []
        for batch in self.system.batch_ap_count.keys():
            for ap in self.system.batch_ap_count[batch].keys():
                count = self.system.batch_ap_count[batch][ap]
                res_matrix.append([f'波次' + str(batch), ap, count])
        res = pd.DataFrame(res_matrix, columns=['BatchNo', 'AreaPattern', 'Count'])
        res.to_csv(f'../Result/Solution.csv', index=False)


if __name__ == '__main__':
    path = '../Data/BOdata.xlsx'
    batch_nb = [107, 107]
    package_limit = [500, 550]
    goods_limit = [1800,3000]
    solve_time = 50

    system = System(path, batch_nb, package_limit, goods_limit, solve_time)
    first_model = FirstModel(system)
    second_model = SecondModel(system)
    result = Result(system)

    first_model.solve()
    second_model.solve()
    result.export_solve_result()