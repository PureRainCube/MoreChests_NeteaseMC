# -*- coding: utf-8 -*-
u"""更多箱子 —— 客户端。

工作有两件：把服务端推来的数据交给容器界面，以及开合世界里那个箱盖。

## 箱盖为什么在客户端

箱子的模型是「客户端实体」（resource_pack/entity/，见 tools/gen_chest_entity.py），
箱盖开合是骨骼动画，由 molang 变量 `variable.chest_open` 驱动动画控制器换状态。
**改 molang 的接口只有客户端有**（`SetBlockEntityMolangValue`），
所以服务端只负责广播「哪个箱子开了/关了」，落地在这里。

这边自己留一份「哪些箱子开着」的缓存，因为方块实体会反复加载卸载
（区块进出视野、陷阱箱开关时换方块），每次重新加载 molang 都回到初始值 0，
得照着缓存补回去。缓存本身靠两条消息维护：进世界时问一次全量，之后收增量广播。

**这里一个 cancel 都不设。** `ClientBlockUseEvent` 的 cancel 拦的是
「与方块交互的逻辑」本身，设了之后交互压根到不了服务端，
`ServerBlockUseEvent` 也就不会触发 —— 自己的箱子右键打不开、
对着原版箱子用升级模板没反应，都是这个原因。
代价是用模板时原版箱子界面会闪一下，但方块随即被换掉，界面自己会关。
官方「自定义熔炉」示例同样没有监听 ClientBlockUseEvent。
"""

import mod.client.extraClientApi as clientApi
from mod_log import logger

from PureRainMoreChestsScripts.modCommon import modConfig
from PureRainMoreChestsScripts.modCommon import chestDefs
from PureRainMoreChestsScripts.modClient.clientManager.chestUIMgr import ChestUIMgr

compFactory = clientApi.GetEngineCompFactory()


class MoreChestsClientSystem(clientApi.GetClientSystemCls()):

    def __init__(self, namespace, name):
        super(MoreChestsClientSystem, self).__init__(namespace, name)
        # ChestUIScreen 建好时自己回填；界面没开着的时候是 None
        self.chestScreen = None
        self.mUIMgr = ChestUIMgr()
        # 开着的箱子：(维度, x, y, z) 的集合。方块实体重新加载时照它补 molang
        self.mOpenChests = set()
        self.ListenEvent()
        logger.info("===== MoreChests 客户端就绪 =====")

    def ListenEvent(self):
        engineNs = clientApi.GetEngineNamespace()
        engineSys = clientApi.GetEngineSystemName()
        self.ListenForEvent(engineNs, engineSys, modConfig.UiInitFinishedEvent,
                            self.mUIMgr, self.mUIMgr.RegisterAll)
        listen = [
            (engineNs, engineSys, modConfig.UiInitFinishedEvent, self.OnUiReady),
            (engineNs, engineSys, modConfig.ModBlockEntityLoadedClientEvent,
             self.OnBlockEntityLoaded),
            (modConfig.ModName, modConfig.ServerSystemName,
             modConfig.ChestLidStateServerEvent, self.OnChestLidState),
            (modConfig.ModName, modConfig.ServerSystemName,
             modConfig.ChestLidSnapshotServerEvent, self.OnChestLidSnapshot),
            (modConfig.ModName, modConfig.ServerSystemName, modConfig.OpenChestUIEvent, self.OnOpenChestUI),
            (modConfig.ModName, modConfig.ServerSystemName, modConfig.ChestContentChangedEvent, self.OnChestChanged),
            (modConfig.ModName, modConfig.ServerSystemName, modConfig.BagChangedEvent, self.OnBagChanged),
            (modConfig.ModName, modConfig.ServerSystemName, modConfig.ItemSwapServerEvent, self.OnItemSwap),
            (modConfig.ModName, modConfig.ServerSystemName, modConfig.ItemDropServerEvent, self.OnItemDrop),
            (modConfig.ModName, modConfig.ServerSystemName, modConfig.CloseChestUIServerEvent, self.OnCloseChestUI),
        ]
        for ns, sysName, evt, cb in listen:
            self.ListenForEvent(ns, sysName, evt, self, cb)
        self.mListened = listen

    def UnListenEvent(self):
        engineNs = clientApi.GetEngineNamespace()
        engineSys = clientApi.GetEngineSystemName()
        self.UnListenForEvent(engineNs, engineSys, modConfig.UiInitFinishedEvent,
                              self.mUIMgr, self.mUIMgr.RegisterAll)
        for ns, sysName, evt, cb in getattr(self, "mListened", []):
            self.UnListenForEvent(ns, sysName, evt, self, cb)

    def Destroy(self):
        self.UnListenEvent()

    # ------------------------------------------------------------ 服务端推送

    def OnOpenChestUI(self, args):
        if self.chestScreen:
            # 界面已经开着（换了个箱子点），直接换内容就行
            self.chestScreen.Fill(args)
            return
        screen = self.mUIMgr.Push(args.get("blockName"))
        if not screen:
            return
        self.chestScreen = screen
        # PushScreen 返回时 Create() 可能还没跑，Fill 里会自己判断 _ready
        screen.Fill(args)

    def OnChestChanged(self, args):
        if self.chestScreen:
            self.chestScreen.Fill(args)

    def OnBagChanged(self, args):
        if self.chestScreen:
            self.chestScreen.Fill(args)

    def OnItemSwap(self, args):
        if self.chestScreen:
            self.chestScreen.OnSwapResult(args)

    def OnItemDrop(self, args):
        if self.chestScreen:
            self.chestScreen.OnDropResult(args)

    def OnCloseChestUI(self, args):
        if self.chestScreen:
            self.chestScreen.OnClose()

    # ------------------------------------------------------------ 箱盖

    def OnUiReady(self, args=None):
        u"""界面就绪 = 这个客户端算是进世界了，问服务端要一次全量。

        之后靠广播增量维护。没有这一次的话，别人早就开着的箱子在刚进来的人
        眼里是关着的。
        """
        data = self.CreateEventData()
        data["playerId"] = clientApi.GetLocalPlayerId()
        self.NotifyToServer(modConfig.SyncChestLidsClientEvent, data)

    def OnChestLidSnapshot(self, args):
        self.mOpenChests = set()
        for entry in (args or {}).get("chests") or []:
            key = self.LidKey(entry[0], entry[1:])
            if key:
                self.mOpenChests.add(key)
                self.ApplyLid(key[1:], True)

    def OnChestLidState(self, args):
        args = args or {}
        key = self.LidKey(args.get("dimension"), args.get("blockPos"))
        if not key:
            return
        isOpen = bool(args.get("open"))
        if isOpen:
            self.mOpenChests.add(key)
        else:
            self.mOpenChests.discard(key)
        # 不在同一个维度就只更新缓存，不去动 molang ——
        # SetBlockEntityMolangValue 只认坐标不认维度，隔着维度设会打到别的方块上
        if self.LocalDimension() not in (None, key[0]):
            return
        self.ApplyLid(key[1:], isOpen)

    def OnBlockEntityLoaded(self, args):
        u"""方块实体（重新）加载：molang 回到了初始值 0，照缓存补回去。"""
        args = args or {}
        if args.get("blockName") not in chestDefs.CHEST_NAMES:
            return
        key = self.LidKey(args.get("dimensionId"),
                          (args.get("posX"), args.get("posY"), args.get("posZ")))
        if not key:
            return
        self.ApplyLid(key[1:], key in self.mOpenChests)

    @staticmethod
    def LidKey(dimension, pos):
        u"""(维度, x, y, z)。任何一项读不出来就返回 None，别硬塞进缓存。"""
        if not pos or len(pos) != 3:
            return None
        try:
            return (int(dimension), int(pos[0]), int(pos[1]), int(pos[2]))
        except (TypeError, ValueError):
            return None

    def LocalDimension(self):
        try:
            return compFactory.CreateDimension(
                clientApi.GetLocalPlayerId()).GetPlayerDimensionId()
        except Exception:
            return None

    def ApplyLid(self, blockPos, isOpen):
        u"""真正去开合那个箱盖。

        `SetEnableBlockEntityAnimations` 每次都调：方块实体重新加载后动画开关
        也会回到默认值，只在第一次调的话，第二次进视野箱盖就不动了。
        """
        try:
            comp = compFactory.CreateBlockInfo(clientApi.GetLevelId())
            comp.SetEnableBlockEntityAnimations(tuple(blockPos), True)
            comp.SetBlockEntityMolangValue(tuple(blockPos),
                                           modConfig.CHEST_OPEN_MOLANG,
                                           1.0 if isOpen else 0.0)
        except Exception as exc:
            logger.warning("MoreChests: 设置箱盖状态失败 %s %s" % (str(blockPos), exc))

    def Update(self):
        pass
