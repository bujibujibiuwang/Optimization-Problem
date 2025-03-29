from dataclasses import dataclass
from typing import Dict
from collections import defaultdict
import pandas as pd


class InFileFD:
    pack_no = 'pakage_no'
    pack_quan = 'qty'
    pack_area = 'area'


@dataclass
class Package:
    quantity: int
    ware_list: list
    area_list: list

@dataclass
class WarePattern:
    package_nb: int
    goods_quantity: int
    area_pattern_list: list

@dataclass
class AreaPattern:
    package_nb: int
    goods_quantity: int


class System:
    def __init__(self, path: str, batch_nb: list, package_limit: list, goods_limit: list, solve_time: int):
        self.path: str = path
        self.batch_nb: list = batch_nb
        self.package_limit: list = package_limit
        self.goods_limit: list = goods_limit
        self.solve_time: int = solve_time

        """
        first
        """
        self.package_dict: Dict[str, Package]  = defaultdict()
        self.ware_pattern_dict: Dict[tuple, WarePattern] = defaultdict()
        self.ware_nb: int = 0
        self.ware_dict: Dict[str, int] = dict()
        self.if_batch_use: Dict[int, bool] = dict()
        self.batch_wp_count: Dict[int, Dict[tuple, int]] = defaultdict()

        """
        second
        """
        self.area_nb: int = 0
        self.area_dict: Dict[str, int] = dict()
        self.area_pattern_dict: Dict[tuple, AreaPattern] = defaultdict()
        self.batch_ap_count: Dict[int, Dict[tuple, int]] = defaultdict()
        self.system_init()

    def system_init(self):
        self.load_data()
        self.create_pattern()

    def load_data(self):
        data = pd.read_excel(self.path)
        # (1) 读取仓库信息，{仓库号：仓库索引}
        # (2) 读取库存信息，{库存号：库区索引}
        # (3) 读取包裹信息，{包裹号:Package对象}
        # Package存储了每个包裹的仓库索引列表, 商品数量和库存索引列表
        for row in data.itertuples():
            pack_no, quan = getattr(row, InFileFD.pack_no), getattr(row, InFileFD.pack_quan)
            area_no = str(getattr(row, InFileFD.pack_area))
            ware_no = area_no.split('-')[0]

            if ware_no not in self.ware_dict.keys():
                self.ware_nb += 1
                self.ware_dict[ware_no] = self.ware_nb
            if not self.area_dict.get(area_no, None):
                self.area_nb += 1
                self.area_dict[area_no] = self.area_nb

            ware_index = self.ware_dict[ware_no]
            area_index = self.area_dict[area_no]
            if pack_no not in self.package_dict.keys():
                package_obj = Package(quan, [ware_index], [area_index])
                self.package_dict[pack_no] = package_obj
            else:
                self.package_dict[pack_no].quantity += quan
                if ware_index not in self.package_dict[pack_no].ware_list:
                    self.package_dict[pack_no].ware_list.append(ware_index)
                if area_index not in self.package_dict[pack_no].area_list:
                    self.package_dict[pack_no].area_list.append(area_index)

    def create_pattern(self):
        # (1) 生成仓库样式信息，{(商品数量，仓库索引号升序)：WarePattern对象}，用于一阶段
        # WarePattern包括属于该样式的包裹件数，该样式的商品数量和细分的库存模式
        # (2) 生成库区样式信息，{(商品数量，库存索引号升序): AreaPattern对象}，用于二阶段
        # AreaPattern包括属于该样式的包裹件数，该样式的商品数量
        for pack_no, pack_obj in self.package_dict.items():
            ware_pattern = [pack_obj.quantity]
            ware_pattern.extend(sorted(pack_obj.ware_list))
            ware_pattern = tuple(ware_pattern)
            area_pattern = [pack_obj.quantity]
            area_pattern.extend(sorted(pack_obj.area_list))
            area_pattern = tuple(area_pattern)
            if not self.area_pattern_dict.get(area_pattern, None):
                area_pattern_obj = AreaPattern(1, pack_obj.quantity)
                self.area_pattern_dict[area_pattern] = area_pattern_obj
            else:
                self.area_pattern_dict[area_pattern].package_nb += 1
            if ware_pattern not in self.ware_pattern_dict.keys():
                ware_pattern_obj = WarePattern(1, pack_obj.quantity, [area_pattern])
                self.ware_pattern_dict[ware_pattern] = ware_pattern_obj
            else:
                ware_pattern_obj = self.ware_pattern_dict[ware_pattern]
                ware_pattern_obj.package_nb += 1
                if area_pattern not in ware_pattern_obj.area_pattern_list:
                    ware_pattern_obj.area_pattern_list.append(area_pattern)

    def show_system_info(self):
        print(f'package数量:{len(self.package_dict.keys())}')
        print(f'仓库模式数量:{len(self.ware_pattern_dict.keys())}')
        print(f'库存模式数量:{len(self.area_pattern_dict.keys())}')
        count = 0
        for pack_no, pack_obj in self.package_dict.items():
            count += pack_obj.quantity
        print(f'good数量:{count}')


