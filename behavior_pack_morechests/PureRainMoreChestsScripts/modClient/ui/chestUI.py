# -*- coding: utf-8 -*-
u"""更多箱子 —— 容器界面。

左边玩家背包 9x4，右边箱子（45 / 54 / 81 / 108 / 1 格）。
点一格选中，再点另一格就把东西挪过去或者对调；点「丢弃」把选中的那格扔掉；
「分堆」打开后挪的是半摞。

## 界面自己什么都不算

它只做两件事：把服务端发下来的物品画出来，以及把「点了哪一格」报上去。
搬多少、能不能搬、泥土箱收不收，全在服务端判。客户端手里那份是副本，
它要是能自己决定搬多少，改个数就能凭空变出东西来。

## 几条踩过的规矩

抄自 `E:/Project/FromBelowLand_NeteaseMC` 的深渊背包（PackScreen）
和官方「自定义熔炉」示例，每条都是静默失败型的坑：

* **按钮回调只能在 `Create()` 里绑。** `PushScreen` 之后控件不是立刻就建好，
  在 `__init__` 里绑拿到的是 None，点了没任何反应也没报错。
* **`SetText` 收的是 UTF-8 字节串。** 传 unicode 不报错，标签直接是空的。
* **`AddTouchEventParams` 必须在 `SetButtonTouchUpCallback` 之前调**，
  否则回调根本不触发。
* **回调要把槽位焊进默认参数里。** 直接在 lambda 里引用循环变量的话，
  所有按钮都会报最后一格。

## 声音和动画分在哪一层

* **按钮「咔」那一声**在 json 里（`sound_name` / `sound_volume` / `sound_pitch`，
  见 tools/gen_ui.py）。引擎自己播，脚本一行都不用写，也就不会出现
  「回调没绑上顺带连声音都没了」。
* **开箱子 / 关箱子那一声**在服务端（`random.chestopen` / `random.chestclosed`），
  因为它是**世界里**发出来的声音：站在旁边的人也该听见，和原版一样。
* **入场动画**在 json 里（`@panel_open_alpha` / `@panel_open_offset`），
  控件一建出来就播。
* **收场动画**只能在这儿做：json 的动画没法由脚本触发，
  所以按下关闭后先把面板往下推几帧，再 `PopScreen`。
"""

import mod.client.extraClientApi as clientApi
from mod_log import logger

from PureRainMoreChestsScripts.modCommon import modConfig
from PureRainMoreChestsScripts.modCommon import chestDefs
from PureRainMoreChestsScripts.modCommon import itemUtils

ScreenNode = clientApi.GetScreenNodeCls()
compFactory = clientApi.GetEngineCompFactory()

# common.base_screen 固定的那一长串安全区容器前缀，改不得。
# 末尾 morechests_panel 是 content_<layout> 里那个子控件的名字。
_ROOT = ("/variables_button_mappings_and_controls/safezone_screen_matrix"
         "/inner_matrix/safezone_screen_panel/root_screen_panel"
         "/morechests_panel")

PATH_INV_SLOTS = _ROOT + "/inv_slots"
PATH_CHEST_SLOTS = _ROOT + "/chest_slots"
PATH_TITLE = _ROOT + "/title"
PATH_STATUS = _ROOT + "/status"
PATH_CLOSE = _ROOT + "/close_btn"
PATH_DROP = _ROOT + "/drop_btn"
PATH_SPLIT = _ROOT + "/split_btn"
PATH_QUICK = _ROOT + "/quick_btn"
PATH_STORE = _ROOT + "/store_btn"
PATH_TAKE = _ROOT + "/take_btn"
PATH_SORT = _ROOT + "/sort_btn"

SIDE_INV = "inv"
SIDE_CHEST = "chest"

# 关界面的收场动画：面板往下滑一截再真的 PopScreen。
#
# 位移由 `Update()` 逐帧推（引擎每帧调一次，官方「自定义熔炉」示例也是这么用的），
# 而**真正的 PopScreen 交给定时器**，不由帧数决定 —— 万一 `Update` 没跑起来，
# 界面也一定会按时关掉，只是少了那一下滑动。反过来写就会卡死关不掉。
CLOSE_ANIM_SECONDS = 0.12
CLOSE_ANIM_FRAMES = 7
CLOSE_ANIM_DROP = 16

# GetPlatform()：0=Windows，1=iOS，2=Android，-1=其它（联机大厅 / Apollo）
PLATFORM_PC = 0


def _ToBytes(text):
    u"""引擎的 SetText 收 UTF-8 字节串；传 unicode 会静默变成空标签。"""
    if isinstance(text, type(u"")):
        return text.encode("utf-8")
    return text


class ChestUIScreen(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self._system = clientApi.GetSystem(modConfig.ModName, modConfig.ClientSystemName)
        if self._system:
            self._system.chestScreen = self

        self._blockName = None
        self._blockPos = None
        self._dimension = None
        self._chestSlots = 0
        self._chest = {}
        self._bag = {}

        self._selected = None        # (side, index)
        self._split = False          # 分堆：挪一半
        self._quick = False          # 快速转移：点一下直接挪到另一侧
        self._ready = False
        self._bound = False
        self._closing = False        # 正在播收场动画，这期间不再响应点击
        self._closeFrame = 0
        self._closeAnchor = None

    # ============================================================ 生命周期

    def Create(self):
        u"""引擎把控件都建好了 —— 按钮回调只能在这里绑。"""
        self._ready = True
        self._BindButton(PATH_CLOSE, self.OnClose)
        self._BindButton(PATH_DROP, self.OnDrop)
        self._BindButton(PATH_SPLIT, self.OnToggleSplit)
        self._BindButton(PATH_QUICK, self.OnToggleQuick)
        self._BindButton(PATH_STORE, self.OnStoreAll)
        self._BindButton(PATH_TAKE, self.OnTakeAll)
        self._BindButton(PATH_SORT, self.OnSort)
        self._BindSlots()
        self._UpdateModes()
        self._Refresh()

    def Update(self):
        u"""引擎每帧调一次。这里只做收场动画的位移，别的什么都不干。"""
        if not self._closing or self._closeFrame >= CLOSE_ANIM_FRAMES:
            return
        self._closeFrame += 1
        if self._closeAnchor is None:
            return
        panel = self._Control(_ROOT)
        if not panel:
            self._closeFrame = CLOSE_ANIM_FRAMES
            return
        ratio = float(self._closeFrame) / CLOSE_ANIM_FRAMES
        try:
            panel.SetPosition((self._closeAnchor[0],
                               self._closeAnchor[1] + CLOSE_ANIM_DROP * ratio))
        except Exception:
            # 动画做不出来不是什么大事，别再每帧试了
            self._closeFrame = CLOSE_ANIM_FRAMES

    def Destroy(self):
        # 按叉、按 esc、被别的界面顶掉都会走到这儿，所以关箱子这一声在这里发
        self._RestorePCInput()
        self._Notify(modConfig.CloseChestUIClientEvent, {})
        if self._system and getattr(self._system, "chestScreen", None) is self:
            self._system.chestScreen = None

    # ============================================================ 控件助手

    def _Control(self, path):
        try:
            return self.GetBaseUIControl(path)
        except Exception:
            return None

    def _SetVisible(self, path, visible):
        try:
            self.SetVisible(path, bool(visible), False)
        except Exception:
            pass

    def _SetText(self, path, text):
        control = self._Control(path)
        if not control:
            return
        try:
            control.asLabel().SetText(_ToBytes(text))
        except Exception:
            pass

    def _BindButton(self, path, callback):
        control = self._Control(path)
        if not control:
            logger.error("MoreChests: 界面找不到按钮 %s" % path)
            return False
        try:
            button = control.asButton()
            # AddTouchEventParams 必须先调，不然回调不会触发
            button.AddTouchEventParams({"isSwallow": True})
            button.SetButtonTouchUpCallback(callback)
            return True
        except Exception as exc:
            logger.error("MoreChests: 绑按钮失败 %s: %s" % (path, exc))
            return False

    # ============================================================ 格子

    @staticmethod
    def _SlotPath(side, index):
        base = PATH_CHEST_SLOTS if side == SIDE_CHEST else PATH_INV_SLOTS
        return "%s/slot%d" % (base, index)

    def _BindSlots(self):
        if self._bound or not self._ready:
            return
        if not self._chestSlots:
            # 还不知道这个箱子有几格，等服务端把数据发下来再绑
            return
        self._bound = True
        for side, count in ((SIDE_INV, modConfig.INV_SLOT_NUM),
                            (SIDE_CHEST, self._chestSlots)):
            for index in range(count):
                # 槽位焊进默认参数，否则所有按钮都会报最后一格
                def callback(args=None, side=side, index=index):
                    self._OnSlot(side, index)
                self._BindButton(self._SlotPath(side, index), callback)

    def _ServerSlot(self, side, index):
        u"""界面上的格子 -> 服务端认的槽位号。背包是 int，箱子是 "cN" 字符串。"""
        if side == SIDE_CHEST:
            return itemUtils.ChestSlotName(index)
        return index

    def _ItemAt(self, side, index):
        if side == SIDE_CHEST:
            return self._chest.get(itemUtils.ChestSlotName(index))
        return self._bag.get(index)

    # ============================================================ 点击

    def _OnSlot(self, side, index):
        if self._closing:
            return
        if self._quick:
            # 相当于 Java 版的 shift + 点击：一下把整摞挪到另一侧
            if itemUtils.IsEmpty(self._ItemAt(side, index)):
                return
            self._Notify(modConfig.QuickMoveClientEvent, {
                "blockName": self._blockName,
                "slot": self._ServerSlot(side, index),
            })
            return
        if self._selected is None:
            if itemUtils.IsEmpty(self._ItemAt(side, index)):
                return
            self._Select(side, index)
            return
        if self._selected == (side, index):
            self._Select(None)
            return
        fromSide, fromIndex = self._selected
        self._Notify(modConfig.ItemSwapClientEvent, {
            "blockName": self._blockName,
            "blockPos": self._blockPos,
            "dimension": self._dimension,
            "fromSlot": self._ServerSlot(fromSide, fromIndex),
            "toSlot": self._ServerSlot(side, index),
            "takePercent": 0.5 if self._split else 1,
        })
        self._Select(None)

    def _Select(self, side, index=0):
        if self._selected:
            self._SetVisible(self._SlotPath(*self._selected) + "/selected", False)
        if side is None:
            self._selected = None
        else:
            self._selected = (side, index)
            self._SetVisible(self._SlotPath(side, index) + "/selected", True)
        self._UpdateStatus()

    def OnClose(self, args=None):
        self.BeginClose()

    def BeginClose(self):
        u"""开始关界面：先播收场动画，到点再 PopScreen。

        `Destroy()` 里才发 CloseChestUIClientEvent，所以关箱子那一声会比按下
        晚 0.12 秒 —— 正好和面板滑走同步，听起来就是「盖子跟着合上」。
        """
        if self._closing:
            return
        self._closing = True
        self._closeFrame = 0
        self._Select(None)
        panel = self._Control(_ROOT)
        try:
            # 入场动画这时候早跑完了，取到的就是静止位置
            self._closeAnchor = tuple(panel.GetPosition()) if panel else None
        except Exception:
            self._closeAnchor = None
        if not self._Delay(CLOSE_ANIM_SECONDS, self.PopNow):
            self.PopNow()

    def PopNow(self):
        try:
            clientApi.PopScreen()
        except Exception as exc:
            logger.error("MoreChests: 关界面失败 %s" % exc)

    def _RestorePCInput(self):
        u"""PC：关界面后把键鼠还给玩家。

        界面开着的时候 PC 是「鼠标模式」（等同按了 F11）：光标出来、视角不跟着
        鼠标转。引擎在 `PopScreen` 之后**不一定**自己切回普通模式，玩家就卡在
        有光标、按 WASD 也不转视角的状态里。`SimulateTouchWithMouse(False)`
        就是那个开关（参考库里 InfinityWar 关面板时用的也是它）。

        只在关的时候切回来，不在开的时候强行切进去 —— 开这一侧现在是好好的，
        动它没有收益只有风险。

        副作用：玩家要是开箱子**之前**自己按了 F11，关箱子后会被切回普通模式。
        比起「关了箱子动不了」，这个代价可以接受，再按一次 F11 就回去了。
        """
        try:
            if clientApi.GetPlatform() != PLATFORM_PC:
                return
            compFactory.CreateGame(clientApi.GetLevelId()).SimulateTouchWithMouse(False)
        except Exception as exc:
            logger.warning("MoreChests: 切回普通键鼠模式失败 %s" % exc)

    def _Delay(self, seconds, callback):
        try:
            compFactory.CreateGame(clientApi.GetLevelId()).AddTimer(seconds, callback)
            return True
        except Exception as exc:
            logger.warning("MoreChests: 客户端定时器建不起来 %s" % exc)
            return False

    def OnDrop(self, args=None):
        if self._closing or not self._selected:
            return
        side, index = self._selected
        self._Notify(modConfig.ItemDropClientEvent, {
            "blockName": self._blockName,
            "blockPos": self._blockPos,
            "dimension": self._dimension,
            "slot": self._ServerSlot(side, index),
        })
        self._Select(None)

    def OnToggleSplit(self, args=None):
        if self._closing:
            return
        self._split = not self._split
        if self._split:
            self._quick = False
        self._UpdateModes()

    def OnToggleQuick(self, args=None):
        if self._closing:
            return
        self._quick = not self._quick
        if self._quick:
            self._split = False
            self._Select(None)
        self._UpdateModes()

    def OnStoreAll(self, args=None):
        self._BulkMove("in")

    def OnTakeAll(self, args=None):
        self._BulkMove("out")

    def OnSort(self, args=None):
        if self._closing:
            return
        self._Select(None)
        self._Notify(modConfig.SortChestClientEvent, {"blockName": self._blockName})

    def _BulkMove(self, direction):
        if self._closing:
            return
        self._Select(None)
        self._Notify(modConfig.BulkMoveClientEvent, {
            "blockName": self._blockName,
            "direction": direction,
        })

    def _UpdateModes(self):
        u"""开关按钮亮不亮，以及左上角那行提示。"""
        self._SetVisible(PATH_QUICK + "/on", self._quick)
        self._SetVisible(PATH_SPLIT + "/on", self._split)
        self._UpdateStatus()

    def _UpdateStatus(self):
        if self._quick:
            text = u"快速转移：点一格直接挪过去"
        elif self._split:
            text = u"分堆：选中后放下时只挪一半"
        elif self._selected:
            text = u"已选中，点另一格放过去"
        else:
            text = u"点一格选中，再点另一格放过去"
        self._SetText(PATH_STATUS, text)

    # ============================================================ 服务端喂数据

    def Fill(self, args):
        u"""OpenChestUIEvent / ChestContentChangedEvent / BagChangedEvent 的落点。"""
        args = args or {}
        blockName = args.get("blockName")
        if blockName:
            self._blockName = blockName
            self._chestSlots = chestDefs.CHESTS.get(blockName, {}).get("slots", 0)
        if args.get("blockPos") is not None:
            self._blockPos = args["blockPos"]
        if args.get("dimension") is not None:
            self._dimension = args["dimension"]
        if modConfig.CHEST_BAG in args:
            self._chest = dict(args[modConfig.CHEST_BAG] or {})
        if modConfig.INVENTORY_BAG in args:
            self._bag = dict(args[modConfig.INVENTORY_BAG] or {})
        if self._ready:
            self._BindSlots()
            self._Refresh()

    def OnSwapResult(self, args):
        for slot, item in ((args.get("fromSlot"), args.get("fromItem")),
                           (args.get("toSlot"), args.get("toItem"))):
            if slot is None:
                continue
            if itemUtils.IsChestSlot(slot):
                self._chest[slot] = item
            else:
                self._bag[slot] = item
        self._Refresh()

    def OnDropResult(self, args):
        slot = args.get("slot")
        if slot is None:
            return
        if itemUtils.IsChestSlot(slot):
            self._chest[slot] = None
        else:
            self._bag[slot] = None
        self._Refresh()

    def _Refresh(self):
        if not self._ready:
            return
        self._SetText(PATH_TITLE, self._TitleText())
        for index in range(modConfig.INV_SLOT_NUM):
            self._DrawSlot(self._SlotPath(SIDE_INV, index), self._bag.get(index))
        for index in range(self._chestSlots):
            key = itemUtils.ChestSlotName(index)
            self._DrawSlot(self._SlotPath(SIDE_CHEST, index), self._chest.get(key))
        self._UpdateStatus()

    def _DrawSlot(self, path, item):
        imgPath = path + "/itemImg"
        count = int((item or {}).get("count") or 0)
        if not item or count <= 0:
            self._SetVisible(imgPath, False)
            return
        try:
            self.SetUiItem(imgPath, item.get("itemName"),
                           int(item.get("auxValue") or 0),
                           bool(item.get("enchantData")),
                           item.get("userData"))
        except Exception as exc:
            logger.error("MoreChests: 画不出 %s: %s" % (item.get("itemName"), exc))
            self._SetVisible(imgPath, False)
            return
        self._SetVisible(imgPath, True)
        self._SetText(imgPath + "/itemNum", str(count) if count > 1 else "")

    def _TitleText(self):
        if not self._blockName:
            return ""
        try:
            itemComp = compFactory.CreateItem(clientApi.GetLevelId())
            hover = itemComp.GetItemFormattedHoverText(self._blockName, 0, False)
            if hover:
                return hover.split("\n")[0]
        except Exception:
            pass
        chest = chestDefs.CHESTS.get(self._blockName) or {}
        return "morechests.container.%s" % chest.get("id", "")

    # ============================================================ 上报

    def _Notify(self, event, payload):
        if not self._system:
            return
        data = dict(payload)
        data["playerId"] = clientApi.GetLocalPlayerId()
        self._system.NotifyToServer(event, data)
