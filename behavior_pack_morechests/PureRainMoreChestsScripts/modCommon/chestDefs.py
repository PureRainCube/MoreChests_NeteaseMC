# -*- coding: utf-8 -*-
# ！！！本文件由 tools/gen_assets.py 生成，不要手改 ！！！
# 数据来源：tools/common.py（对应 Java 版 Iron Chests 的 IronChestsTypes）

NS = "purerain_chests"

# 方块名 -> {槽位数, 每行列数, UI 名}
CHESTS = {
    "purerain_chests:copper_chest": {"id": "copper_chest", "slots": 45, "cols": 9, "rows": 5, "ui": "chest_45"},
    "purerain_chests:iron_chest": {"id": "iron_chest", "slots": 54, "cols": 9, "rows": 6, "ui": "chest_54"},
    "purerain_chests:gold_chest": {"id": "gold_chest", "slots": 81, "cols": 9, "rows": 9, "ui": "chest_81"},
    "purerain_chests:diamond_chest": {"id": "diamond_chest", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:crystal_chest": {"id": "crystal_chest", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:obsidian_chest": {"id": "obsidian_chest", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:dirt_chest": {"id": "dirt_chest", "slots": 1, "cols": 1, "rows": 1, "ui": "chest_1"},
    "purerain_chests:trapped_copper_chest": {"id": "trapped_copper_chest", "slots": 45, "cols": 9, "rows": 5, "ui": "chest_45"},
    "purerain_chests:trapped_iron_chest": {"id": "trapped_iron_chest", "slots": 54, "cols": 9, "rows": 6, "ui": "chest_54"},
    "purerain_chests:trapped_gold_chest": {"id": "trapped_gold_chest", "slots": 81, "cols": 9, "rows": 9, "ui": "chest_81"},
    "purerain_chests:trapped_diamond_chest": {"id": "trapped_diamond_chest", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:trapped_crystal_chest": {"id": "trapped_crystal_chest", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:trapped_obsidian_chest": {"id": "trapped_obsidian_chest", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:trapped_dirt_chest": {"id": "trapped_dirt_chest", "slots": 1, "cols": 1, "rows": 1, "ui": "chest_1"},
    "purerain_chests:trapped_copper_chest_on": {"id": "trapped_copper_chest_on", "slots": 45, "cols": 9, "rows": 5, "ui": "chest_45"},
    "purerain_chests:trapped_iron_chest_on": {"id": "trapped_iron_chest_on", "slots": 54, "cols": 9, "rows": 6, "ui": "chest_54"},
    "purerain_chests:trapped_gold_chest_on": {"id": "trapped_gold_chest_on", "slots": 81, "cols": 9, "rows": 9, "ui": "chest_81"},
    "purerain_chests:trapped_diamond_chest_on": {"id": "trapped_diamond_chest_on", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:trapped_crystal_chest_on": {"id": "trapped_crystal_chest_on", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:trapped_obsidian_chest_on": {"id": "trapped_obsidian_chest_on", "slots": 108, "cols": 12, "rows": 9, "ui": "chest_108"},
    "purerain_chests:trapped_dirt_chest_on": {"id": "trapped_dirt_chest_on", "slots": 1, "cols": 1, "rows": 1, "ui": "chest_1"},
}

# UI 名 -> 该 UI 的槽位数 / 列数，UI json 里的 main_<ui> 与之一一对应
UI_LAYOUTS = {
    "chest_1": {"slots": 1, "cols": 1, "rows": 1},
    "chest_108": {"slots": 108, "cols": 12, "rows": 9},
    "chest_45": {"slots": 45, "cols": 9, "rows": 5},
    "chest_54": {"slots": 54, "cols": 9, "rows": 6},
    "chest_81": {"slots": 81, "cols": 9, "rows": 9},
}

# 升级模板 -> {能升的源方块: 升成什么}
#
# 对着陷阱箱用会升成陷阱版 —— Java 版 IronChestsTypes.source() 对每个等级
# 返回的就是 [普通, 陷阱] 两个方块，ChestUpgradeItem 按源是不是陷阱箱挑目标。
# 原版箱子那一档同理：Java 用 instanceof ChestBlock 判断，而原版陷阱箱
# 继承自它，所以原版陷阱箱也能升 —— 升出来是陷阱版。
# 通电态（有人开着的陷阱箱）也收，升出来是不通电的那个。
UPGRADES = {
    "purerain_chests:wood_to_copper_chest_upgrade": {
        "minecraft:chest": "purerain_chests:copper_chest",
        "minecraft:trapped_chest": "purerain_chests:trapped_copper_chest",
    },
    "purerain_chests:wood_to_iron_chest_upgrade": {
        "minecraft:chest": "purerain_chests:iron_chest",
        "minecraft:trapped_chest": "purerain_chests:trapped_iron_chest",
    },
    "purerain_chests:copper_to_iron_chest_upgrade": {
        "purerain_chests:copper_chest": "purerain_chests:iron_chest",
        "purerain_chests:trapped_copper_chest": "purerain_chests:trapped_iron_chest",
        "purerain_chests:trapped_copper_chest_on": "purerain_chests:trapped_iron_chest",
    },
    "purerain_chests:iron_to_gold_chest_upgrade": {
        "purerain_chests:iron_chest": "purerain_chests:gold_chest",
        "purerain_chests:trapped_iron_chest": "purerain_chests:trapped_gold_chest",
        "purerain_chests:trapped_iron_chest_on": "purerain_chests:trapped_gold_chest",
    },
    "purerain_chests:gold_to_diamond_chest_upgrade": {
        "purerain_chests:gold_chest": "purerain_chests:diamond_chest",
        "purerain_chests:trapped_gold_chest": "purerain_chests:trapped_diamond_chest",
        "purerain_chests:trapped_gold_chest_on": "purerain_chests:trapped_diamond_chest",
    },
    "purerain_chests:diamond_to_crystal_chest_upgrade": {
        "purerain_chests:diamond_chest": "purerain_chests:crystal_chest",
        "purerain_chests:trapped_diamond_chest": "purerain_chests:trapped_crystal_chest",
        "purerain_chests:trapped_diamond_chest_on": "purerain_chests:trapped_crystal_chest",
    },
    "purerain_chests:diamond_to_obsidian_chest_upgrade": {
        "purerain_chests:diamond_chest": "purerain_chests:obsidian_chest",
        "purerain_chests:trapped_diamond_chest": "purerain_chests:trapped_obsidian_chest",
        "purerain_chests:trapped_diamond_chest_on": "purerain_chests:trapped_obsidian_chest",
    },
}

# 能被升级模板作用的原版箱子
VANILLA_CHESTS = set(["minecraft:chest", "minecraft:trapped_chest"])

# 泥土箱只收这些方块（对应 Java 版 DirtChestSlot）。
# 陷阱泥土箱和它的通电态一样挑食，所以是个集合而不是单个方块名
DIRT_CHESTS = set([
    "purerain_chests:dirt_chest",
    "purerain_chests:trapped_dirt_chest",
    "purerain_chests:trapped_dirt_chest_on",
])
DIRT_CHEST_ITEMS = [
    "minecraft:dirt",
    "minecraft:coarse_dirt",
    "minecraft:podzol",
    "minecraft:rooted_dirt",
    "minecraft:grass_block",
    "minecraft:mycelium",
]

# 陷阱箱 <-> 它的通电态。基岩版没法在运行时改红石信号强度，
# 所以开箱时换成带红石源的通电态、关箱时换回来（见 tools/common.py 的说明）
POWERED_OF = {
    "purerain_chests:trapped_copper_chest": "purerain_chests:trapped_copper_chest_on",
    "purerain_chests:trapped_iron_chest": "purerain_chests:trapped_iron_chest_on",
    "purerain_chests:trapped_gold_chest": "purerain_chests:trapped_gold_chest_on",
    "purerain_chests:trapped_diamond_chest": "purerain_chests:trapped_diamond_chest_on",
    "purerain_chests:trapped_crystal_chest": "purerain_chests:trapped_crystal_chest_on",
    "purerain_chests:trapped_obsidian_chest": "purerain_chests:trapped_obsidian_chest_on",
    "purerain_chests:trapped_dirt_chest": "purerain_chests:trapped_dirt_chest_on",
}
UNPOWERED_OF = dict((v, k) for k, v in POWERED_OF.items())
TRAPPED_NAMES = set(POWERED_OF.keys()) | set(UNPOWERED_OF.keys())

# 本 mod 所有箱子方块名，供事件里做快速判断
CHEST_NAMES = set(CHESTS.keys())
UPGRADE_NAMES = set(UPGRADES.keys())
