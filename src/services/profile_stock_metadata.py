# -*- coding: utf-8 -*-
"""
Static stock metadata registry for profile strategy pages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ProfileStockMetadata:
    code: str
    name_en: str
    name_zh: str
    sector: str
    industry: Optional[str] = None


PROFILE_STOCK_METADATA: Dict[str, Dict[str, ProfileStockMetadata]] = {
    "mag7": {
        "AAPL": ProfileStockMetadata("AAPL", "Apple", "苹果", "信息技术", "消费电子"),
        "AMZN": ProfileStockMetadata("AMZN", "Amazon", "亚马逊", "可选消费", "电商与云服务"),
        "GOOGL": ProfileStockMetadata("GOOGL", "Alphabet", "谷歌", "通信服务", "互联网平台"),
        "META": ProfileStockMetadata("META", "Meta Platforms", "Meta", "通信服务", "社交媒体平台"),
        "MSFT": ProfileStockMetadata("MSFT", "Microsoft", "微软", "信息技术", "软件与云服务"),
        "NVDA": ProfileStockMetadata("NVDA", "NVIDIA", "英伟达", "信息技术", "半导体"),
        "TSLA": ProfileStockMetadata("TSLA", "Tesla", "特斯拉", "可选消费", "电动车"),
    },
    "nasdaq100": {
        "ADBE": ProfileStockMetadata("ADBE", "Adobe", "奥多比", "信息技术", "应用软件"),
        "AMD": ProfileStockMetadata("AMD", "Advanced Micro Devices", "超威半导体", "信息技术", "半导体"),
        "ABNB": ProfileStockMetadata("ABNB", "Airbnb", "爱彼迎", "可选消费", "在线旅行平台"),
        "ALNY": ProfileStockMetadata("ALNY", "Alnylam Pharmaceuticals", "艾尼兰制药", "医疗保健", "生物科技"),
        "GOOGL": ProfileStockMetadata("GOOGL", "Alphabet", "谷歌", "通信服务", "互联网平台"),
        "GOOG": ProfileStockMetadata("GOOG", "Alphabet", "谷歌", "通信服务", "互联网平台"),
        "AMZN": ProfileStockMetadata("AMZN", "Amazon", "亚马逊", "可选消费", "电商与云服务"),
        "AEP": ProfileStockMetadata("AEP", "American Electric Power", "美国电力", "公用事业", "综合电力"),
        "AMGN": ProfileStockMetadata("AMGN", "Amgen", "安进", "医疗保健", "生物科技"),
        "ADI": ProfileStockMetadata("ADI", "Analog Devices", "亚德诺", "信息技术", "模拟芯片"),
        "AAPL": ProfileStockMetadata("AAPL", "Apple", "苹果", "信息技术", "消费电子"),
        "AMAT": ProfileStockMetadata("AMAT", "Applied Materials", "应用材料", "信息技术", "半导体设备"),
        "APP": ProfileStockMetadata("APP", "AppLovin", "AppLovin", "信息技术", "广告与营销软件"),
        "ARM": ProfileStockMetadata("ARM", "Arm Holdings", "安谋", "信息技术", "芯片设计"),
        "ASML": ProfileStockMetadata("ASML", "ASML Holding", "阿斯麦", "信息技术", "半导体设备"),
        "ADSK": ProfileStockMetadata("ADSK", "Autodesk", "欧特克", "信息技术", "设计软件"),
        "ADP": ProfileStockMetadata("ADP", "Automatic Data Processing", "自动数据处理", "工业", "人力资源外包"),
        "AXON": ProfileStockMetadata("AXON", "Axon Enterprise", "Axon", "工业", "公共安全设备"),
        "BKR": ProfileStockMetadata("BKR", "Baker Hughes", "贝克休斯", "能源", "油服设备"),
        "BKNG": ProfileStockMetadata("BKNG", "Booking Holdings", "缤客控股", "可选消费", "在线旅行平台"),
        "AVGO": ProfileStockMetadata("AVGO", "Broadcom", "博通", "信息技术", "半导体"),
        "CDNS": ProfileStockMetadata("CDNS", "Cadence Design Systems", "铿腾电子", "信息技术", "EDA 软件"),
        "CHTR": ProfileStockMetadata("CHTR", "Charter Communications", "特许通讯", "通信服务", "有线与宽带"),
        "CTAS": ProfileStockMetadata("CTAS", "Cintas", "辛塔斯", "工业", "企业服务"),
        "CSCO": ProfileStockMetadata("CSCO", "Cisco", "思科", "信息技术", "网络设备"),
        "CCEP": ProfileStockMetadata("CCEP", "Coca-Cola Europacific Partners", "可口可乐欧洲太平洋合伙公司", "必需消费", "饮料装瓶"),
        "CTSH": ProfileStockMetadata("CTSH", "Cognizant", "高知特", "信息技术", "IT 服务"),
        "CMCSA": ProfileStockMetadata("CMCSA", "Comcast", "康卡斯特", "通信服务", "媒体与宽带"),
        "CEG": ProfileStockMetadata("CEG", "Constellation Energy", "星座能源", "公用事业", "发电与零售电力"),
        "CPRT": ProfileStockMetadata("CPRT", "Copart", "Copart", "工业", "汽车拍卖平台"),
        "CSGP": ProfileStockMetadata("CSGP", "CoStar Group", "科斯塔集团", "房地产", "地产数据服务"),
        "COST": ProfileStockMetadata("COST", "Costco", "开市客", "必需消费", "仓储零售"),
        "CRWD": ProfileStockMetadata("CRWD", "CrowdStrike", "CrowdStrike", "信息技术", "网络安全"),
        "CSX": ProfileStockMetadata("CSX", "CSX", "CSX 铁路", "工业", "铁路运输"),
        "DDOG": ProfileStockMetadata("DDOG", "Datadog", "Datadog", "信息技术", "可观测性软件"),
        "DXCM": ProfileStockMetadata("DXCM", "DexCom", "德康医疗", "医疗保健", "医疗器械"),
        "FANG": ProfileStockMetadata("FANG", "Diamondback Energy", "响尾蛇能源", "能源", "油气勘探"),
        "DASH": ProfileStockMetadata("DASH", "DoorDash", "DoorDash", "可选消费", "即时配送平台"),
        "EA": ProfileStockMetadata("EA", "Electronic Arts", "艺电", "通信服务", "游戏内容"),
        "EXC": ProfileStockMetadata("EXC", "Exelon", "爱克斯龙", "公用事业", "综合公用事业"),
        "FAST": ProfileStockMetadata("FAST", "Fastenal", "法思诺", "工业", "工业分销"),
        "FER": ProfileStockMetadata("FER", "Ferrovial", "费罗维亚尔", "工业", "基础设施运营"),
        "FTNT": ProfileStockMetadata("FTNT", "Fortinet", "飞塔", "信息技术", "网络安全"),
        "GEHC": ProfileStockMetadata("GEHC", "GE HealthCare", "GE 医疗", "医疗保健", "医疗设备"),
        "GILD": ProfileStockMetadata("GILD", "Gilead Sciences", "吉利德科学", "医疗保健", "生物制药"),
        "HON": ProfileStockMetadata("HON", "Honeywell", "霍尼韦尔", "工业", "工业自动化"),
        "IDXX": ProfileStockMetadata("IDXX", "IDEXX Laboratories", "爱德士", "医疗保健", "诊断设备"),
        "INSM": ProfileStockMetadata("INSM", "Insmed", "Insmed", "医疗保健", "生物科技"),
        "INTC": ProfileStockMetadata("INTC", "Intel", "英特尔", "信息技术", "半导体"),
        "INTU": ProfileStockMetadata("INTU", "Intuit", "财捷", "信息技术", "财务软件"),
        "ISRG": ProfileStockMetadata("ISRG", "Intuitive Surgical", "直觉外科", "医疗保健", "医疗器械"),
        "KDP": ProfileStockMetadata("KDP", "Keurig Dr Pepper", "Keurig Dr Pepper", "必需消费", "饮料"),
        "KLAC": ProfileStockMetadata("KLAC", "KLA", "科磊", "信息技术", "半导体设备"),
        "KHC": ProfileStockMetadata("KHC", "Kraft Heinz", "卡夫亨氏", "必需消费", "食品"),
        "LRCX": ProfileStockMetadata("LRCX", "Lam Research", "泛林集团", "信息技术", "半导体设备"),
        "LIN": ProfileStockMetadata("LIN", "Linde", "林德", "原材料", "工业气体"),
        "MAR": ProfileStockMetadata("MAR", "Marriott International", "万豪国际", "可选消费", "酒店"),
        "MRVL": ProfileStockMetadata("MRVL", "Marvell Technology", "迈威尔科技", "信息技术", "半导体"),
        "MELI": ProfileStockMetadata("MELI", "MercadoLibre", "美客多", "可选消费", "拉美电商平台"),
        "META": ProfileStockMetadata("META", "Meta Platforms", "Meta", "通信服务", "社交媒体平台"),
        "MCHP": ProfileStockMetadata("MCHP", "Microchip Technology", "微芯科技", "信息技术", "半导体"),
        "MU": ProfileStockMetadata("MU", "Micron Technology", "美光科技", "信息技术", "存储芯片"),
        "MSFT": ProfileStockMetadata("MSFT", "Microsoft", "微软", "信息技术", "软件与云服务"),
        "MSTR": ProfileStockMetadata("MSTR", "MicroStrategy", "微策略", "信息技术", "商业智能软件"),
        "MDLZ": ProfileStockMetadata("MDLZ", "Mondelez", "亿滋国际", "必需消费", "零食食品"),
        "MPWR": ProfileStockMetadata("MPWR", "Monolithic Power Systems", "芯源系统", "信息技术", "电源管理芯片"),
        "MNST": ProfileStockMetadata("MNST", "Monster Beverage", "怪兽饮料", "必需消费", "功能饮料"),
        "NFLX": ProfileStockMetadata("NFLX", "Netflix", "奈飞", "通信服务", "流媒体平台"),
        "NVDA": ProfileStockMetadata("NVDA", "NVIDIA", "英伟达", "信息技术", "半导体"),
        "NXPI": ProfileStockMetadata("NXPI", "NXP Semiconductors", "恩智浦", "信息技术", "半导体"),
        "ORLY": ProfileStockMetadata("ORLY", "O'Reilly Automotive", "奥莱利汽车", "可选消费", "汽车零配件零售"),
        "ODFL": ProfileStockMetadata("ODFL", "Old Dominion Freight Line", "老多明尼恩货运", "工业", "物流运输"),
        "PCAR": ProfileStockMetadata("PCAR", "PACCAR", "帕卡", "工业", "商用车制造"),
        "PLTR": ProfileStockMetadata("PLTR", "Palantir", "Palantir", "信息技术", "数据分析平台"),
        "PANW": ProfileStockMetadata("PANW", "Palo Alto Networks", "派拓网络", "信息技术", "网络安全"),
        "PAYX": ProfileStockMetadata("PAYX", "Paychex", "Paychex", "工业", "薪资与人力资源服务"),
        "PYPL": ProfileStockMetadata("PYPL", "PayPal", "贝宝", "金融服务", "数字支付"),
        "PDD": ProfileStockMetadata("PDD", "PDD Holdings", "拼多多", "可选消费", "电商平台"),
        "PEP": ProfileStockMetadata("PEP", "PepsiCo", "百事公司", "必需消费", "食品饮料"),
        "QCOM": ProfileStockMetadata("QCOM", "Qualcomm", "高通", "信息技术", "无线通信芯片"),
        "REGN": ProfileStockMetadata("REGN", "Regeneron Pharmaceuticals", "再生元制药", "医疗保健", "生物制药"),
        "ROP": ProfileStockMetadata("ROP", "Roper Technologies", "罗珀科技", "工业", "工业与软件解决方案"),
        "ROST": ProfileStockMetadata("ROST", "Ross Stores", "罗斯百货", "可选消费", "折扣零售"),
        "SNDK": ProfileStockMetadata("SNDK", "Sandisk", "闪迪", "信息技术", "存储设备"),
        "STX": ProfileStockMetadata("STX", "Seagate Technology", "希捷科技", "信息技术", "存储设备"),
        "SHOP": ProfileStockMetadata("SHOP", "Shopify", "Shopify", "信息技术", "电商 SaaS"),
        "SBUX": ProfileStockMetadata("SBUX", "Starbucks", "星巴克", "可选消费", "连锁咖啡"),
        "SNPS": ProfileStockMetadata("SNPS", "Synopsys", "新思科技", "信息技术", "EDA 软件"),
        "TMUS": ProfileStockMetadata("TMUS", "T-Mobile US", "T-Mobile", "通信服务", "无线通信"),
        "TTWO": ProfileStockMetadata("TTWO", "Take-Two Interactive", "Take-Two", "通信服务", "游戏内容"),
        "TSLA": ProfileStockMetadata("TSLA", "Tesla", "特斯拉", "可选消费", "电动车"),
        "TXN": ProfileStockMetadata("TXN", "Texas Instruments", "德州仪器", "信息技术", "模拟芯片"),
        "TRI": ProfileStockMetadata("TRI", "Thomson Reuters", "汤森路透", "金融服务", "金融信息服务"),
        "VRSK": ProfileStockMetadata("VRSK", "Verisk Analytics", "维里斯克分析", "工业", "数据分析服务"),
        "VRTX": ProfileStockMetadata("VRTX", "Vertex Pharmaceuticals", "福泰制药", "医疗保健", "生物制药"),
        "WMT": ProfileStockMetadata("WMT", "Walmart", "沃尔玛", "必需消费", "综合零售"),
        "WBD": ProfileStockMetadata("WBD", "Warner Bros. Discovery", "华纳兄弟探索", "通信服务", "媒体娱乐"),
        "WDC": ProfileStockMetadata("WDC", "Western Digital", "西部数据", "信息技术", "存储设备"),
        "WDAY": ProfileStockMetadata("WDAY", "Workday", "Workday", "信息技术", "企业软件"),
        "XEL": ProfileStockMetadata("XEL", "Xcel Energy", "Xcel Energy", "公用事业", "综合公用事业"),
        "ZS": ProfileStockMetadata("ZS", "Zscaler", "Zscaler", "信息技术", "网络安全"),
    },
}


def get_profile_stock_metadata(profile_name: str, code: str) -> Optional[ProfileStockMetadata]:
    return PROFILE_STOCK_METADATA.get(profile_name, {}).get(code.upper())


def build_profile_stock_items(profile_name: str, stock_universe: List[str]) -> List[dict]:
    items: List[dict] = []
    for code in stock_universe:
        metadata = get_profile_stock_metadata(profile_name, code)
        if metadata is None:
            items.append(
                {
                    "code": code,
                    "name_en": code,
                    "name_zh": code,
                    "sector": "未分类",
                    "industry": None,
                }
            )
            continue
        items.append(asdict(metadata))
    return items
