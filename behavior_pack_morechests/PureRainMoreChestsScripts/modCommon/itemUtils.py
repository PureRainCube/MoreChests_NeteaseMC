# -*- coding: utf-8 -*-
"""物品字典的公共处理。

blockEntityData 有几条硬限制（见网易文档《方块实体 - GetBlockEntityData》）：
  * 不支持 tuple
  * list 里各项类型必须一致
  * dict 的 key 必须是字符串
物品字典里的 enchantData 恰好是 [(附魔类型, 等级), ...] 这种 tuple 列表，
直接塞进去会存储失败，所以存之前要过一遍 Sanitize，取出来再 Restore。
"""

from PureRainMoreChestsScripts.modCommon import modConfig


def IsChestSlot(slot):
    """箱子槽位是字符串（"c0"…），背包槽位是整数。

    判断写成「是不是字符串」而不是「不是 int」：ModSDK 跑的是 Python 2，
    事件数据跨端回来的整数可能是 long，而 long 不是 int —— 那样背包槽位
    会被当成箱子槽位，读出来是空的，整个交换静默失败。
    type(u"") 在 py2 是 unicode、py3 是 str，两边都盖到。
    """
    return isinstance(slot, str) or isinstance(slot, type(u""))


def ChestSlotName(index):
    return "%s%d" % (modConfig.CHEST_SLOT_PREFIX, index)


def ChestSlotIndex(slotName):
    try:
        return int(slotName[len(modConfig.CHEST_SLOT_PREFIX):])
    except (ValueError, TypeError):
        return -1


def IsSameItem(item1, item2):
    """只有名称、附加值、userData、耐久都一样才算同一种物品。"""
    if not item1 or not item2:
        return False
    if item1.get("itemName") != item2.get("itemName"):
        return False
    if item1.get("auxValue") != item2.get("auxValue"):
        return False
    if item1.get("userData") != item2.get("userData"):
        return False
    if item1.get("durability") != item2.get("durability"):
        return False
    if item1.get("enchantData") != item2.get("enchantData"):
        return False
    return True


def IsEmpty(item):
    if not item:
        return True
    if not item.get("itemName") or item.get("itemName") == "minecraft:air":
        return True
    if not item.get("count"):
        return True
    return False


def _ToStorable(value):
    if isinstance(value, tuple):
        return [_ToStorable(v) for v in value]
    if isinstance(value, list):
        return [_ToStorable(v) for v in value]
    if isinstance(value, dict):
        return dict((str(k), _ToStorable(v)) for k, v in value.items())
    return value


def Sanitize(item):
    """转成 blockEntityData 存得下的形式；空物品统一存 None。"""
    if IsEmpty(item):
        return None
    return _ToStorable(dict(item))


def Restore(item):
    """从 blockEntityData 读出来后还原成引擎接口要的形式。"""
    if IsEmpty(item):
        return None
    out = dict(item)
    ench = out.get("enchantData")
    if ench:
        restored = []
        for entry in ench:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                restored.append((entry[0], entry[1]))
        out["enchantData"] = restored
    return out
