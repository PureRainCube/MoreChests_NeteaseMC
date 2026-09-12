# -*- coding: utf-8 -*-
"""更多箱子 —— 服务端。

箱子内容存在自定义方块实体的 blockEntityData 里，一格一个 key（"c0"…"c107"），
所有的增删改都以服务端为准，客户端只负责显示和发点击请求。
"""

import mod.server.extraServerApi as serverApi
from mod_log import logger

from PureRainMoreChestsScripts.modCommon import modConfig
from PureRainMoreChestsScripts.modCommon import chestDefs
from PureRainMoreChestsScripts.modCommon import itemUtils

minecraftEnum = serverApi.GetMinecraftEnum()
compFactory = serverApi.GetEngineCompFactory()

# 四面向 aux：0=south 1=west 2=north 3=east（见网易文档《自定义方块 - 功能 - 多面向》）
#
# 原版箱子的朝向在不同版本上是两套状态：老的 facing_direction(2..5 的整数)，
# 新的 minecraft:cardinal_direction（"north" 这样的字符串）。两套都认。
VANILLA_FACING_TO_AUX = {2: 2, 3: 0, 4: 1, 5: 3}
CARDINAL_TO_AUX = {"south": 0, "west": 1, "north": 2, "east": 3}
CARDINAL_TO_FACING = {"north": 2, "south": 3, "west": 4, "east": 5}
CARDINALS = ("north", "south", "west", "east")

# 玩家离开箱子多远自动关界面
MAX_USE_DISTANCE_SQR = 8.0 * 8.0

# 「丢弃」把东西扔出去，而不是放在脚底下。
#
# 原来是 SpawnItemToLevel 到玩家脚底，结果刚丢下就被自己捡回去了。
# 原版手动丢东西不会这样，靠的是掉落物身上 40 tick 的拾取冷却 ——
# 那个冷却引擎没开放给脚本，所以只能靠距离：在身前生成，再给一个初速度，
# 十来 tick 就飞出拾取范围了。
#
# **方向只取水平朝向（yaw），不管俯仰（pitch）。** 开箱子时玩家多半正低头
# 看着脚边的箱子，照着视线扔就是往地上砸，一样会被捡回去。
DROP_FORWARD = 0.8        # 生成点在玩家身前几格
DROP_HEIGHT = 1.3         # 生成高度，大致是视线高度
DROP_SPEED = 0.62         # 水平初速度，格/tick
DROP_LIFT = 0.22          # 稍微上抛一点，免得贴着地面很快被摩擦停下


class MoreChestsServerSystem(serverApi.GetServerSystemCls()):

    def __init__(self, namespace, name):
        super(MoreChestsServerSystem, self).__init__(namespace, name)
        self.mLevelId = serverApi.GetLevelId()
        # playerId -> {"blockName", "blockPos", "dimension"}
        self.mCurOpenedBlock = {}
        # 正在做原地升级的方块，避免 BlockRemoveServerEvent 把内容当成掉落物撒一地
        self.mUpgrading = set()
        # 正在处理交换时不要往客户端推背包全量刷新，否则会盖掉飞行动画
        self.mSuppressBagSync = 0
        self.mTickCount = 0
        self.mWhiteListRetried = False
        self.ListenEvent()
        self.RegisterVanillaChestUse()
        logger.info("===== MoreChests 服务端就绪 =====")

    # ------------------------------------------------------------ 事件

    def ListenEvent(self):
        engineNs = serverApi.GetEngineNamespace()
        engineSys = serverApi.GetEngineSystemName()
        listen = [
            (engineNs, engineSys, modConfig.ServerBlockUseEvent, self.OnBlockUse),
            (engineNs, engineSys, modConfig.ServerItemUseOnEvent, self.OnItemUseOn),
            (engineNs, engineSys, modConfig.ServerPlayerTryDestroyBlockEvent, self.OnTryDestroyBlock),
            (engineNs, engineSys, modConfig.BlockRemoveServerEvent, self.OnBlockRemove),
            (engineNs, engineSys, modConfig.ActorAcquiredItemServerEvent, self.OnActorAcquiredItem),
            (engineNs, engineSys, modConfig.PlayerDieEvent, self.OnPlayerDie),
            (engineNs, engineSys, modConfig.DelServerPlayerEvent, self.OnPlayerLeave),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.CloseChestUIClientEvent, self.OnClientCloseUI),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.ItemSwapClientEvent, self.OnItemSwap),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.ItemDropClientEvent, self.OnItemDrop),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.QuickMoveClientEvent, self.OnQuickMove),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.BulkMoveClientEvent, self.OnBulkMove),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.SortChestClientEvent, self.OnSortChest),
            (modConfig.ModName, modConfig.ClientSystemName, modConfig.SyncChestLidsClientEvent, self.OnSyncChestLids),
        ]
        for ns, sysName, evt, cb in listen:
            self.ListenForEvent(ns, sysName, evt, self, cb)
        self.mListened = listen

    def UnListenEvent(self):
        for ns, sysName, evt, cb in getattr(self, "mListened", []):
            self.UnListenForEvent(ns, sysName, evt, self, cb)

    def RegisterVanillaChestUse(self):
        """原版箱子默认不会抛 ServerBlockUseEvent，要先加进白名单，
        木→铜 / 木→铁 的升级模板才能对着原版箱子用。
        原版陷阱箱也要 —— 对它用模板会升成本 mod 的陷阱箱。

        除了 `namespace:name:*` 之外，把箱子朝向那几个附加值也逐个登记一遍：
        文档只说 `*` 匹配所有附加值，但没说在所有版本上都灵，多写几条不亏。
        另外 System 的 __init__ 跑得比世界加载早，这时候注册不一定生效，
        所以 Update 里还会再补一次。
        """
        ok = []
        try:
            comp = compFactory.CreateBlockUseEventWhiteList(self.mLevelId)
            for name in chestDefs.VANILLA_CHESTS:
                ok.append(comp.AddBlockItemListenForUseEvent("%s:*" % name))
                for aux in range(6):
                    comp.AddBlockItemListenForUseEvent("%s:%d" % (name, aux))
        except Exception as e:
            logger.warning("MoreChests: 注册原版箱子监听失败 %s" % e)
            return False
        logger.info("MoreChests: 原版箱子监听登记 %s -> %s"
                    % (sorted(chestDefs.VANILLA_CHESTS), ok))
        return True

    def Destroy(self):
        self.UnListenEvent()

    # ------------------------------------------------------------ 工具

    def GetDimension(self, args, playerId):
        dim = args.get("dimensionId")
        if dim is None:
            dim = args.get("dimension")
        if dim is None and playerId:
            dim = compFactory.CreateDimension(playerId).GetPlayerDimensionId()
        return dim or 0

    def GetHeldItem(self, playerId):
        # 开箱子是主路径，读手持物品失败不能把它带崩
        try:
            return compFactory.CreateItem(playerId).GetPlayerItem(
                minecraftEnum.ItemPosType.CARRIED, 0, True)
        except Exception as e:
            logger.warning("MoreChests: 读手持物品失败 %s" % e)
            return None

    def IsSneaking(self, playerId):
        """玩家在潜行。潜行时对着箱子右键应该是放方块，而不是开箱子 —— 和原版一致。"""
        try:
            return bool(compFactory.CreatePlayer(playerId).isSneaking())
        except Exception:
            return False

    # ------------------------------------------------------------ 箱盖开合
    #
    # 箱子的模型是客户端实体，箱盖靠 molang 变量驱动动画控制器（见
    # tools/gen_chest_entity.py）。**改 molang 的接口只有客户端有**，
    # 所以服务端能做的就是把「哪个箱子开了/关了」广播出去，各自客户端自己去改。
    #
    # 为什么是广播而不是只发给开箱的人：箱盖是世界里看得见的东西，
    # 站在旁边的人也该看见它掀开 —— 和原版一样。

    def BroadcastLid(self, dimension, blockPos, isOpen):
        data = self.CreateEventData()
        data["blockPos"] = list(blockPos)
        data["dimension"] = dimension
        data["open"] = 1 if isOpen else 0
        self.BroadcastToAllClient(modConfig.ChestLidStateServerEvent, data)

    def OpenChestPosList(self):
        seen = []
        for info in self.mCurOpenedBlock.values():
            entry = [info["dimension"]] + list(info["blockPos"])
            if entry not in seen:
                seen.append(entry)
        return seen

    def OnSyncChestLids(self, args):
        u"""玩家刚进世界，把当前开着的箱子一次性给他。

        平时靠广播增量更新就够了，但**刚连上的人没听见之前那些广播** ——
        没有这一条，别人早就开着的箱子在他眼里是关着的。
        """
        playerId = args.get("playerId")
        if not playerId:
            return
        data = self.CreateEventData()
        data["chests"] = self.OpenChestPosList()
        self.NotifyToClient(playerId, modConfig.ChestLidSnapshotServerEvent, data)

    def PlayBlockSound(self, dimension, blockPos, soundName):
        u"""在方块那个位置放一声，附近的人都听得见 —— 和原版开合箱子一样。

        服务端没有直接播音效的接口：`PlayCustomMusic` 是客户端的，在服务端调
        只会返回 -1。参考库里唯一验证过的路子是命令 ——
        `CreateCommand(levelId).SetCommand("/playsound ...", playerId)`。

        为什么是「逐个玩家发 @s」而不是一条 `@a`：命令的坐标按**执行者所在维度**
        解释，`@a` 会把别的维度的人也算进去，于是主世界开个箱子、地狱里的人
        脚底下也响一声。这里自己按维度和距离筛一遍，再以每个听得见的人为原点发，
        用到的都是确定存在的接口。
        """
        x, y, z = blockPos[0] + 0.5, blockPos[1] + 0.5, blockPos[2] + 0.5
        rangeSqr = modConfig.SOUND_HEAR_RANGE * modConfig.SOUND_HEAR_RANGE
        try:
            players = serverApi.GetPlayerList() or []
        except Exception:
            players = []
        cmdComp = compFactory.CreateCommand(self.mLevelId)
        for playerId in players:
            try:
                if compFactory.CreateDimension(playerId).GetPlayerDimensionId() != dimension:
                    continue
                pos = compFactory.CreatePos(playerId).GetFootPos()
                if not pos:
                    continue
                dx, dy, dz = pos[0] - x, pos[1] - y, pos[2] - z
                if dx * dx + dy * dy + dz * dz > rangeSqr:
                    continue
                cmdComp.SetCommand(
                    "/playsound %s @s %.2f %.2f %.2f 1 1" % (soundName, x, y, z),
                    playerId)
            except Exception as exc:
                logger.warning("MoreChests: 播音效失败 %s" % exc)

    def Tip(self, playerId, text):
        try:
            compFactory.CreateMsg(self.mLevelId).NotifyOneMessage(playerId, text)
        except Exception:
            pass

    # ------------------------------------------------------------ 箱子内容存取

    def GetEntityData(self, dimension, blockPos):
        return compFactory.CreateBlockEntityData(self.mLevelId).GetBlockEntityData(dimension, blockPos)

    def GetChestItems(self, dimension, blockPos, blockName):
        """返回 {槽位名: itemDict or None}。"""
        slots = chestDefs.CHESTS.get(blockName, {}).get("slots", 0)
        data = self.GetEntityData(dimension, blockPos)
        items = {}
        for i in range(slots):
            key = itemUtils.ChestSlotName(i)
            items[key] = itemUtils.Restore(data[key]) if data else None
        return items

    def GetChestItem(self, dimension, blockPos, slotName):
        data = self.GetEntityData(dimension, blockPos)
        if not data:
            return None
        return itemUtils.Restore(data[slotName])

    def SetChestItem(self, dimension, blockPos, slotName, item):
        data = self.GetEntityData(dimension, blockPos)
        if data is None:
            logger.error("MoreChests: 取不到方块实体数据 %s %s" % (str(blockPos), slotName))
            return False
        data[slotName] = itemUtils.Sanitize(item)
        return True

    def ClearChest(self, dimension, blockPos, blockName):
        data = self.GetEntityData(dimension, blockPos)
        if not data:
            return
        for i in range(chestDefs.CHESTS.get(blockName, {}).get("slots", 0)):
            data[itemUtils.ChestSlotName(i)] = None

    # ------------------------------------------------------------ 打开界面

    def OnBlockUse(self, args):
        blockName = args["blockName"]
        playerId = args["playerId"]
        if blockName not in chestDefs.CHEST_NAMES and blockName not in chestDefs.VANILLA_CHESTS:
            return
        blockPos = (args["x"], args["y"], args["z"])
        dimension = self.GetDimension(args, playerId)

        held = self.GetHeldItem(playerId)
        heldName = held.get("itemName") if held else None

        if blockName in chestDefs.CHEST_NAMES:
            # 自己的箱子不设 args["cancel"] —— 那拦的是交互逻辑本身，设了右键就没反应了。
            # 自定义方块没有需要压制的默认右键行为；防止顺手放方块是靠
            # ServerItemUseOnEvent 里的 ret=True，不是靠这里。
            if heldName in chestDefs.UPGRADE_NAMES:
                self.TryUpgrade(playerId, dimension, blockPos, blockName, heldName)
                return
            if self.IsSneaking(playerId):
                # 潜行 = 想放方块，不是想开箱子（和原版箱子一个手感）
                return
            # 这个事件每 tick 都会来，同一个箱子别重复开
            opened = self.mCurOpenedBlock.get(playerId)
            if opened:
                if opened["blockPos"] == blockPos and opened["dimension"] == dimension:
                    return
                # 换了个箱子点，先把上一个关掉
                self.CloseUIFor(playerId)
            self.OpenChestUI(playerId, dimension, blockPos, blockName)
            return

        # 原版箱子 / 原版陷阱箱：手里拿着对得上的模板才拦，否则不打扰玩家开箱子
        sources = chestDefs.UPGRADES.get(heldName) or {}
        if heldName in chestDefs.UPGRADE_NAMES:
            logger.info("MoreChests: 对 %s 用 %s，匹配=%s"
                        % (blockName, heldName, blockName in sources))
        if blockName in sources:
            args["cancel"] = True
            self.TryUpgrade(playerId, dimension, blockPos, blockName, heldName)

    def OnItemUseOn(self, args):
        """两件事：拦掉对着本 mod 箱子放方块；给原版箱子的升级留一条兜底路径。

        网易文档提到原版那些「有使用功能」的方块（箱子就是）可能不抛
        ServerBlockUseEvent，只抛这个。所以升级走两条路，谁先到算谁的，
        mUpgrading 那个标记顺带保证同一格不会被升两次。
        """
        blockName = args.get("blockName")
        playerId = args.get("entityId")
        if blockName in chestDefs.CHEST_NAMES:
            # 潜行时放行：玩家要贴着箱子放方块。不潜行才拦，免得右键开箱子
            # 的时候顺手把手里的方块放出去
            if not self.IsSneaking(playerId):
                args["ret"] = True
            return
        if blockName not in chestDefs.VANILLA_CHESTS:
            return
        heldName = (args.get("itemDict") or {}).get("itemName")
        sources = chestDefs.UPGRADES.get(heldName) or {}
        if blockName not in sources:
            return
        blockPos = (args["x"], args["y"], args["z"])
        dimension = self.GetDimension(args, playerId)
        if (dimension, blockPos) in self.mUpgrading:
            return
        args["ret"] = True
        self.TryUpgrade(playerId, dimension, blockPos, blockName, heldName)

    # ------------------------------------------------------------ 陷阱箱通电
    #
    # 基岩版发红石信号只能靠 netease:redstone，而它是静态配置 —— 红石那组接口
    # 只有 GetStrength / GetBlockPoweredState 两个读接口，没有写的。
    # 所以陷阱箱做成两个方块：平时不带红石，有人打开时换成带红石源的通电态，
    # 最后一个人关上再换回来。
    #
    # 换方块会重建自定义方块实体，内容物要跟着搬。**一次开箱只搬两次**
    # （开一次、关一次），不是每次点格子都搬 —— 界面开着的时候读写的是
    # 通电态那个方块的实体，和普通箱子没区别。

    def ViewerCount(self, dimension, blockPos, exceptPlayer=None):
        count = 0
        for playerId, info in self.mCurOpenedBlock.items():
            if playerId == exceptPlayer:
                continue
            if info["blockPos"] == blockPos and info["dimension"] == dimension:
                count += 1
        return count

    def SwapKeepingItems(self, dimension, blockPos, fromName, toName):
        """原地把方块换成另一种，内容物搬过去。失败时不动原方块。"""
        items = [v for _, v in sorted(
            self.GetChestItems(dimension, blockPos, fromName).items(),
            key=lambda kv: itemUtils.ChestSlotIndex(kv[0]))]

        blockInfoComp = compFactory.CreateBlockInfo(self.mLevelId)
        try:
            blockDict = blockInfoComp.GetBlockNew(blockPos, dimension)
        except Exception:
            blockDict = None
        if not blockDict or blockDict.get("name") != fromName:
            # 方块已经不在了（被挖掉 / 区块没加载），什么都别做
            return False
        # 朝向和升级那边共用一套读法，免得开一次箱子箱子就转个身
        aux = self.GetUpgradedAux(blockInfoComp, blockPos, dimension, fromName)

        key = (dimension, blockPos)
        self.mUpgrading.add(key)
        try:
            # 中间过一次空气：同类型方块实体直接替换时旧数据不一定会清掉
            blockInfoComp.SetBlockNew(blockPos, {"name": "minecraft:air", "aux": 0},
                                      0, dimension, True)
            ok = blockInfoComp.SetBlockNew(blockPos, {"name": toName, "aux": aux},
                                           0, dimension, True)
        finally:
            self.mUpgrading.discard(key)
        if not ok:
            logger.error("MoreChests: 陷阱箱换方块失败 %s -> %s" % (fromName, toName))
            return False

        data = self.GetEntityData(dimension, blockPos)
        if data is None:
            # 方块换成了但实体拿不到，东西不能凭空没了，原地掉出来
            logger.error("MoreChests: 换方块后取不到方块实体，内容改为掉落")
            itemComp = compFactory.CreateItem(self.mLevelId)
            for item in items:
                if not itemUtils.IsEmpty(item):
                    itemComp.SpawnItemToLevel(item, dimension,
                                              (blockPos[0] + 0.5, blockPos[1] + 0.5,
                                               blockPos[2] + 0.5))
            return True
        for i, item in enumerate(items):
            data[itemUtils.ChestSlotName(i)] = itemUtils.Sanitize(item)
        return True

    def PowerOn(self, dimension, blockPos, blockName):
        """陷阱箱被打开：换成通电态。返回界面该用的方块名。"""
        powered = chestDefs.POWERED_OF.get(blockName)
        if not powered:
            return blockName
        if self.SwapKeepingItems(dimension, blockPos, blockName, powered):
            return powered
        return blockName

    def PowerOffIfIdle(self, dimension, blockPos, blockName):
        """最后一个人关上陷阱箱：换回不通电的那个。"""
        unpowered = chestDefs.UNPOWERED_OF.get(blockName)
        if not unpowered:
            return
        if self.ViewerCount(dimension, blockPos):
            return
        self.SwapKeepingItems(dimension, blockPos, blockName, unpowered)

    def ForgetViewer(self, playerId):
        """把玩家从「正开着的箱子」里摘掉，必要时把陷阱箱断电。"""
        blockInfo = self.mCurOpenedBlock.pop(playerId, None)
        if blockInfo:
            self.PlayBlockSound(blockInfo["dimension"], blockInfo["blockPos"],
                                modConfig.SOUND_CHEST_CLOSE)
            # 还有人开着就别合盖 —— pop 已经做完了，这时候数的是剩下的人
            if not self.ViewerCount(blockInfo["dimension"], blockInfo["blockPos"]):
                self.BroadcastLid(blockInfo["dimension"], blockInfo["blockPos"], False)
            self.PowerOffIfIdle(blockInfo["dimension"], blockInfo["blockPos"],
                                blockInfo["blockName"])
        return blockInfo

    def OpenChestUI(self, playerId, dimension, blockPos, blockName):
        # 陷阱箱：开之前先换成通电态，之后所有读写都落在这个新方块上
        blockName = self.PowerOn(dimension, blockPos, blockName)
        logger.info("MoreChests: 打开 %s @ %s" % (blockName, str(blockPos)))
        self.PlayBlockSound(dimension, blockPos, modConfig.SOUND_CHEST_OPEN)
        self.BroadcastLid(dimension, blockPos, True)
        self.mCurOpenedBlock[playerId] = {
            "blockName": blockName,
            "blockPos": blockPos,
            "dimension": dimension,
        }
        eventData = self.CreateEventData()
        eventData["blockName"] = blockName
        eventData["blockPos"] = blockPos
        eventData["dimension"] = dimension
        eventData[modConfig.CHEST_BAG] = self.GetChestItems(dimension, blockPos, blockName)
        self.NotifyToClient(playerId, modConfig.OpenChestUIEvent, eventData)
        # 界面刚创建时 grid 的子控件还没生成，等 0.1 秒再推背包数据
        compFactory.CreateGame(self.mLevelId).AddTimer(0.1, self.SyncBag, playerId)

    def SyncBag(self, playerId):
        blockInfo = self.mCurOpenedBlock.get(playerId)
        if not blockInfo:
            return
        itemComp = compFactory.CreateItem(playerId)
        bag = {}
        for i in range(modConfig.INV_SLOT_NUM):
            bag[i] = itemComp.GetPlayerItem(minecraftEnum.ItemPosType.INVENTORY, i, True)
        eventData = self.CreateEventData()
        eventData["blockName"] = blockInfo["blockName"]
        eventData[modConfig.INVENTORY_BAG] = bag
        self.NotifyToClient(playerId, modConfig.BagChangedEvent, eventData)

    def CloseUIFor(self, playerId):
        blockInfo = self.ForgetViewer(playerId)
        if not blockInfo:
            return
        eventData = self.CreateEventData()
        eventData["blockName"] = blockInfo["blockName"]
        self.NotifyToClient(playerId, modConfig.CloseChestUIServerEvent, eventData)

    def CloseUIForBlock(self, dimension, blockPos):
        """方块本身要没了（被挖 / 被炸 / 要换成别的）时把界面关掉。

        这里**不能**走 ForgetViewer —— 那会顺手把陷阱箱断电，
        而断电是靠换方块实现的，对着一个正要消失的方块换来换去只会添乱。
        """
        for playerId in list(self.mCurOpenedBlock.keys()):
            info = self.mCurOpenedBlock[playerId]
            if info["blockPos"] != blockPos or info["dimension"] != dimension:
                continue
            self.mCurOpenedBlock.pop(playerId, None)
            eventData = self.CreateEventData()
            eventData["blockName"] = info["blockName"]
            self.NotifyToClient(playerId, modConfig.CloseChestUIServerEvent, eventData)
        # 方块要没了，客户端缓存里那条「这里有个开着的箱子」也得清掉，
        # 否则以后在同一个坐标放新箱子，它一出生就是开着的
        self.BroadcastLid(dimension, blockPos, False)

    def OnClientCloseUI(self, args):
        self.ForgetViewer(args["playerId"])

    def OnPlayerDie(self, args):
        self.CloseUIFor(args["id"])

    def OnPlayerLeave(self, args):
        self.ForgetViewer(args.get("id"))

    def OnActorAcquiredItem(self, args):
        if self.mSuppressBagSync:
            return
        playerId = args["actor"]
        if playerId in self.mCurOpenedBlock:
            self.SyncBag(playerId)

    # ------------------------------------------------------------ 交换 / 丢弃

    def ReadSlot(self, playerId, blockInfo, slot):
        if itemUtils.IsChestSlot(slot):
            return self.GetChestItem(blockInfo["dimension"], blockInfo["blockPos"], slot)
        return compFactory.CreateItem(playerId).GetPlayerItem(
            minecraftEnum.ItemPosType.INVENTORY, slot, True)

    def WriteSlot(self, playerId, blockInfo, slot, item):
        if itemUtils.IsChestSlot(slot):
            return self.SetChestItem(blockInfo["dimension"], blockInfo["blockPos"], slot, item)
        itemComp = compFactory.CreateItem(playerId)
        itemComp.SetInvItemNum(slot, 0)
        if itemUtils.IsEmpty(item):
            return True
        if itemComp.SpawnItemToPlayerInv(item, playerId, slot):
            return True
        # 放不进背包就掉在脚下，总之不能让东西凭空没了
        logger.error("MoreChests: 物品写回背包失败，改为掉落 %s" % str(item.get("itemName")))
        try:
            pos = compFactory.CreatePos(playerId).GetFootPos()
            compFactory.CreateItem(self.mLevelId).SpawnItemToLevel(
                item, blockInfo["dimension"], pos)
        except Exception as e:
            logger.error("MoreChests: 掉落也失败了 %s" % e)
        return False

    def MaxStackSize(self, playerId, item):
        info = compFactory.CreateItem(playerId).GetItemBasicInfo(
            item.get("itemName", ""), item.get("auxValue", 0))
        if info and info.get("maxStackSize"):
            return info["maxStackSize"]
        return 64

    def CanPutIntoChest(self, blockName, item):
        """泥土箱 9000 只收泥土类方块，其余箱子什么都收。

        Java 原版的 DirtChestSlot.mayPlace 只认 Blocks.DIRT 一种，这里放宽到
        六种泥土类方块（见 chestDefs.DIRT_CHEST_ITEMS），不然这个彩蛋箱子
        实在太难用。拒收时把物品 id 打进日志 —— 玩家报「放不进去」的时候，
        没有这行就只能猜是哪个 id 没对上。
        """
        if blockName not in chestDefs.DIRT_CHESTS:
            return True
        if itemUtils.IsEmpty(item):
            return True
        if item.get("itemName") in chestDefs.DIRT_CHEST_ITEMS:
            return True
        logger.info("MoreChests: 泥土箱拒收 %s" % item.get("itemName"))
        return False

    def ComputeMove(self, playerId, fromItem, toItem, takePercent):
        """算出交换/堆叠/分堆之后两个槽各自应该变成什么。
        返回 (newFromItem, newToItem)，不允许时返回 (None, None)。"""
        total = fromItem.get("count", 0)
        if total <= 0:
            return None, None
        moveCount = total if takePercent >= 1 else max(1, int(total * takePercent))

        if itemUtils.IsSameItem(fromItem, toItem):
            maxStack = self.MaxStackSize(playerId, toItem)
            space = maxStack - toItem.get("count", 0)
            if space <= 0:
                return None, None
            move = min(moveCount, space)
            newTo = dict(toItem)
            newTo["count"] = toItem.get("count", 0) + move
            rest = total - move
            newFrom = None
            if rest > 0:
                newFrom = dict(fromItem)
                newFrom["count"] = rest
            return newFrom, newTo

        if itemUtils.IsEmpty(toItem):
            if moveCount >= total:
                return None, dict(fromItem)
            newTo = dict(fromItem)
            newTo["count"] = moveCount
            newFrom = dict(fromItem)
            newFrom["count"] = total - moveCount
            return newFrom, newTo

        # 两边都有东西且不是同一种：只允许整堆对调
        if takePercent < 1:
            return None, None
        return dict(toItem), dict(fromItem)

    def OnItemSwap(self, args):
        playerId = args["playerId"]
        blockInfo = self.mCurOpenedBlock.get(playerId)
        if not blockInfo:
            return
        fromSlot = args["fromSlot"]
        toSlot = args["toSlot"]
        if fromSlot == toSlot:
            return
        takePercent = args.get("takePercent", 1)

        self.mSuppressBagSync += 1
        try:
            fromItem = self.ReadSlot(playerId, blockInfo, fromSlot)
            toItem = self.ReadSlot(playerId, blockInfo, toSlot)
            if itemUtils.IsEmpty(fromItem):
                self.ResyncAll(playerId, blockInfo)
                return

            newFrom, newTo = self.ComputeMove(playerId, fromItem, toItem, takePercent)
            if newFrom is None and newTo is None:
                # 目标格满了 / 不同物品又在分堆，都会走到这儿。
                # 静默失败最难查，所以给一句提示
                if itemUtils.IsChestSlot(toSlot):
                    self.Tip(playerId, modConfig.TIP_CHEST_FULL)
                self.ResyncAll(playerId, blockInfo)
                return

            blockName = blockInfo["blockName"]
            # 放进箱子的东西要过一遍准入检查（泥土箱）
            if itemUtils.IsChestSlot(toSlot) and not self.CanPutIntoChest(blockName, newTo):
                self.Tip(playerId, modConfig.TIP_DIRT_ONLY)
                self.ResyncAll(playerId, blockInfo)
                return
            if itemUtils.IsChestSlot(fromSlot) and not self.CanPutIntoChest(blockName, newFrom):
                self.Tip(playerId, modConfig.TIP_DIRT_ONLY)
                self.ResyncAll(playerId, blockInfo)
                return

            self.WriteSlot(playerId, blockInfo, fromSlot, newFrom)
            self.WriteSlot(playerId, blockInfo, toSlot, newTo)

            eventData = self.CreateEventData()
            eventData["blockName"] = blockName
            eventData["fromSlot"] = fromSlot
            eventData["toSlot"] = toSlot
            eventData["fromItem"] = newFrom
            eventData["toItem"] = newTo
            eventData["movedItem"] = dict(fromItem)
            self.NotifyToClient(playerId, modConfig.ItemSwapServerEvent, eventData)

            # 同一个箱子被别人开着的话也要跟着刷新
            if itemUtils.IsChestSlot(fromSlot) or itemUtils.IsChestSlot(toSlot):
                self.SyncChestForOthers(playerId, blockInfo)
        finally:
            self.mSuppressBagSync -= 1

    def OnItemDrop(self, args):
        playerId = args["playerId"]
        blockInfo = self.mCurOpenedBlock.get(playerId)
        if not blockInfo:
            return
        slot = args["slot"]
        self.mSuppressBagSync += 1
        try:
            item = self.ReadSlot(playerId, blockInfo, slot)
            if itemUtils.IsEmpty(item):
                self.ResyncAll(playerId, blockInfo)
                return
            self.WriteSlot(playerId, blockInfo, slot, None)
            self.ThrowItem(playerId, blockInfo["dimension"], item)

            eventData = self.CreateEventData()
            eventData["blockName"] = blockInfo["blockName"]
            eventData["slot"] = slot
            self.NotifyToClient(playerId, modConfig.ItemDropServerEvent, eventData)
            if itemUtils.IsChestSlot(slot):
                self.SyncChestForOthers(playerId, blockInfo)
        finally:
            self.mSuppressBagSync -= 1

    def ThrowItem(self, playerId, dimension, item):
        u"""把东西朝玩家正前方扔出去（见文件头 DROP_* 那几个常数）。

        每一步都可能失败，但**东西一定得落地** —— 上层已经把格子清空了，
        这里扔不出去就是凭空少一摞。所以每层都有退路，最后兜底到
        「原地生成」，宁可被捡回去也不能丢。
        """
        itemComp = compFactory.CreateItem(self.mLevelId)
        try:
            pos = compFactory.CreatePos(playerId).GetFootPos()
        except Exception as exc:
            logger.warning("MoreChests: 读玩家坐标失败 %s" % exc)
            pos = None
        if not pos:
            itemComp.SpawnItemToLevel(item, dimension, (0, 64, 0))
            return
        try:
            rot = compFactory.CreateRot(playerId).GetRot()
            # pitch 填 0：只要水平朝向，低头看箱子时也照样往前扔
            dx, _, dz = serverApi.GetDirFromRot((0.0, rot[1]))
        except Exception as exc:
            logger.warning("MoreChests: 读玩家朝向失败 %s" % exc)
            dx, dz = 0.0, 0.0
        spawnPos = (pos[0] + dx * DROP_FORWARD,
                    pos[1] + DROP_HEIGHT,
                    pos[2] + dz * DROP_FORWARD)
        entityId = None
        try:
            entityId = self.CreateEngineItemEntity(item, dimension, spawnPos)
        except Exception as exc:
            logger.warning("MoreChests: 生成掉落物失败 %s" % exc)
        if not entityId:
            # 拿不到实体 id 就没法给速度，退回「在身前生成」——
            # 比脚底下强，但确实可能被捡回去
            itemComp.SpawnItemToLevel(item, dimension, spawnPos)
            return
        try:
            compFactory.CreateActorMotion(entityId).SetMotion(
                (dx * DROP_SPEED, DROP_LIFT, dz * DROP_SPEED))
        except Exception as exc:
            logger.warning("MoreChests: 给掉落物加初速度失败 %s" % exc)

    # ------------------------------------------------------------ 快速转移 / 一键存取
    #
    # 对应 Java 版的 shift + 点击。基岩版手机端没有 shift，所以做成界面上的
    # 开关按钮，外加「存入 / 取出」两个一键操作。
    #
    # 这几个操作一次可能动几十格，所以先把两边快照到内存里算完，
    # 最后只把真正变了的格子写回去 —— 一格一次 GetBlockEntityData 的话，
    # 108 格箱子做一次「取出」就是上百次取方块实体。

    def Snapshot(self, playerId, blockInfo):
        chest = self.GetChestItems(blockInfo["dimension"], blockInfo["blockPos"],
                                   blockInfo["blockName"])
        itemComp = compFactory.CreateItem(playerId)
        bag = {}
        for i in range(modConfig.INV_SLOT_NUM):
            bag[i] = itemComp.GetPlayerItem(minecraftEnum.ItemPosType.INVENTORY, i, True)
        return bag, chest

    def WriteBack(self, playerId, blockInfo, bag, chest, changed):
        chestSlots = [s for s in changed if itemUtils.IsChestSlot(s)]
        if chestSlots:
            data = self.GetEntityData(blockInfo["dimension"], blockInfo["blockPos"])
            if data is None:
                logger.error("MoreChests: 写回时取不到方块实体数据")
                return False
            for slot in chestSlots:
                data[slot] = itemUtils.Sanitize(chest.get(slot))
        for slot in changed:
            if not itemUtils.IsChestSlot(slot):
                self.WriteSlot(playerId, blockInfo, slot, bag.get(slot))
        return True

    def MoveOneStack(self, playerId, blockName, srcMap, srcSlot, dstMap, dstOrder,
                     toChest, changed):
        """把 srcSlot 那一摞尽量挪到另一侧。返回是否动了东西。"""
        item = srcMap.get(srcSlot)
        if itemUtils.IsEmpty(item):
            return False
        if toChest and not self.CanPutIntoChest(blockName, item):
            return False
        maxStack = self.MaxStackSize(playerId, item)
        remaining = item.get("count", 0)

        # 先并到同种物品上，再找空格 —— 和原版 shift 点击的顺序一致
        for slot in dstOrder:
            if remaining <= 0:
                break
            existing = dstMap.get(slot)
            if not itemUtils.IsSameItem(existing, item):
                continue
            space = maxStack - existing.get("count", 0)
            if space <= 0:
                continue
            move = min(space, remaining)
            merged = dict(existing)
            merged["count"] = existing.get("count", 0) + move
            dstMap[slot] = merged
            changed.add(slot)
            remaining -= move
        for slot in dstOrder:
            if remaining <= 0:
                break
            if not itemUtils.IsEmpty(dstMap.get(slot)):
                continue
            placed = dict(item)
            placed["count"] = min(remaining, maxStack)
            dstMap[slot] = placed
            changed.add(slot)
            remaining -= placed["count"]

        if remaining == item.get("count", 0):
            return False
        if remaining > 0:
            left = dict(item)
            left["count"] = remaining
            srcMap[srcSlot] = left
        else:
            srcMap[srcSlot] = None
        changed.add(srcSlot)
        return True

    def SideOrder(self, blockInfo, chestSide):
        if chestSide:
            slots = chestDefs.CHESTS.get(blockInfo["blockName"], {}).get("slots", 0)
            return [itemUtils.ChestSlotName(i) for i in range(slots)]
        return list(range(modConfig.INV_SLOT_NUM))

    def OnQuickMove(self, args):
        playerId = args["playerId"]
        blockInfo = self.mCurOpenedBlock.get(playerId)
        if not blockInfo:
            return
        slot = args.get("slot")
        if slot is None:
            return
        self.mSuppressBagSync += 1
        try:
            bag, chest = self.Snapshot(playerId, blockInfo)
            toChest = not itemUtils.IsChestSlot(slot)
            srcMap, dstMap = (bag, chest) if toChest else (chest, bag)
            changed = set()
            moved = self.MoveOneStack(playerId, blockInfo["blockName"], srcMap, slot,
                                      dstMap, self.SideOrder(blockInfo, toChest),
                                      toChest, changed)
            if not moved:
                if toChest and blockInfo["blockName"] in chestDefs.DIRT_CHESTS:
                    self.Tip(playerId, modConfig.TIP_DIRT_ONLY)
                return
            self.WriteBack(playerId, blockInfo, bag, chest, changed)
            self.PushAll(playerId, blockInfo)
        finally:
            self.mSuppressBagSync -= 1

    def OnBulkMove(self, args):
        playerId = args["playerId"]
        blockInfo = self.mCurOpenedBlock.get(playerId)
        if not blockInfo:
            return
        toChest = args.get("direction") != "out"
        self.mSuppressBagSync += 1
        try:
            bag, chest = self.Snapshot(playerId, blockInfo)
            srcMap, dstMap = (bag, chest) if toChest else (chest, bag)
            srcOrder = self.SideOrder(blockInfo, not toChest)
            dstOrder = self.SideOrder(blockInfo, toChest)
            changed = set()
            for slot in srcOrder:
                self.MoveOneStack(playerId, blockInfo["blockName"], srcMap, slot,
                                  dstMap, dstOrder, toChest, changed)
            if not changed:
                return
            self.WriteBack(playerId, blockInfo, bag, chest, changed)
            self.PushAll(playerId, blockInfo)
        finally:
            self.mSuppressBagSync -= 1

    def MergeAndSort(self, playerId, items):
        """合并同种物品再按名字排序。只整理箱子这一侧，不碰玩家背包。"""
        out = []
        for item in items:
            if itemUtils.IsEmpty(item):
                continue
            item = dict(item)
            maxStack = self.MaxStackSize(playerId, item)
            for existing in out:
                if item.get("count", 0) <= 0:
                    break
                if not itemUtils.IsSameItem(existing, item):
                    continue
                space = maxStack - existing.get("count", 0)
                if space <= 0:
                    continue
                move = min(space, item["count"])
                existing["count"] = existing.get("count", 0) + move
                item["count"] -= move
            if item.get("count", 0) > 0:
                out.append(item)
        out.sort(key=lambda it: (str(it.get("itemName") or ""), it.get("auxValue") or 0))
        return out

    @staticmethod
    def SameSlotContent(a, b):
        if itemUtils.IsEmpty(a) and itemUtils.IsEmpty(b):
            return True
        if itemUtils.IsEmpty(a) or itemUtils.IsEmpty(b):
            return False
        return itemUtils.IsSameItem(a, b) and a.get("count") == b.get("count")

    def OnSortChest(self, args):
        playerId = args["playerId"]
        blockInfo = self.mCurOpenedBlock.get(playerId)
        if not blockInfo:
            return
        self.mSuppressBagSync += 1
        try:
            chest = self.GetChestItems(blockInfo["dimension"], blockInfo["blockPos"],
                                       blockInfo["blockName"])
            order = self.SideOrder(blockInfo, True)
            merged = self.MergeAndSort(playerId, [chest.get(s) for s in order])
            changed = set()
            for i, slot in enumerate(order):
                newItem = merged[i] if i < len(merged) else None
                if not self.SameSlotContent(chest.get(slot), newItem):
                    chest[slot] = newItem
                    changed.add(slot)
            if not changed:
                return
            self.WriteBack(playerId, blockInfo, {}, chest, changed)
            self.PushAll(playerId, blockInfo)
        finally:
            self.mSuppressBagSync -= 1

    def PushAll(self, playerId, blockInfo):
        """一次动了很多格，直接把两边的最新状态整个推下去，比逐格通知省事也更稳。"""
        self.ResyncAll(playerId, blockInfo)
        self.SyncChestForOthers(playerId, blockInfo)

    def ResyncAll(self, playerId, blockInfo):
        """出现分歧时把服务端的真实状态整个推一遍，避免客户端显示错位。"""
        eventData = self.CreateEventData()
        eventData["blockName"] = blockInfo["blockName"]
        eventData[modConfig.CHEST_BAG] = self.GetChestItems(
            blockInfo["dimension"], blockInfo["blockPos"], blockInfo["blockName"])
        self.NotifyToClient(playerId, modConfig.ChestContentChangedEvent, eventData)
        self.SyncBag(playerId)

    def SyncChestForOthers(self, playerId, blockInfo):
        items = None
        for otherId, info in self.mCurOpenedBlock.items():
            if otherId == playerId:
                continue
            if info["blockPos"] != blockInfo["blockPos"] or info["dimension"] != blockInfo["dimension"]:
                continue
            if items is None:
                items = self.GetChestItems(blockInfo["dimension"], blockInfo["blockPos"],
                                           blockInfo["blockName"])
            eventData = self.CreateEventData()
            eventData["blockName"] = blockInfo["blockName"]
            eventData[modConfig.CHEST_BAG] = items
            self.NotifyToClient(otherId, modConfig.ChestContentChangedEvent, eventData)

    # ------------------------------------------------------------ 破坏箱子

    def OnTryDestroyBlock(self, args):
        blockName = args.get("fullName")
        if blockName not in chestDefs.CHEST_NAMES:
            return
        blockPos = (args["x"], args["y"], args["z"])
        dimension = self.GetDimension(args, args.get("playerId"))
        self.CloseUIForBlock(dimension, blockPos)
        self.SpillAndClear(dimension, blockPos, blockName)

        # 挖到的是陷阱箱的通电态时，掉落物要换成不通电的那个 ——
        # 不然玩家会拿到一个永远通电的方块，放下去就是个红石块
        unpowered = chestDefs.UNPOWERED_OF.get(blockName)
        if unpowered:
            args["spawnResources"] = False
            compFactory.CreateItem(self.mLevelId).SpawnItemToLevel(
                {"itemName": unpowered, "count": 1, "auxValue": 0}, dimension,
                (blockPos[0] + 0.5, blockPos[1] + 0.5, blockPos[2] + 0.5))

    def OnBlockRemove(self, args):
        """爆炸、活塞等非玩家挖掘的情况兜底。
        玩家挖掘时 OnTryDestroyBlock 已经把内容清空了，这里会读到空值自然跳过。"""
        blockName = args.get("fullName")
        if blockName not in chestDefs.CHEST_NAMES:
            return
        blockPos = (args["x"], args["y"], args["z"])
        dimension = args.get("dimension", 0)
        if (dimension, blockPos) in self.mUpgrading:
            return
        self.CloseUIForBlock(dimension, blockPos)
        self.SpillAndClear(dimension, blockPos, blockName)

    def SpillAndClear(self, dimension, blockPos, blockName):
        items = self.GetChestItems(dimension, blockPos, blockName)
        itemComp = compFactory.CreateItem(self.mLevelId)
        dropPos = (blockPos[0] + 0.5, blockPos[1] + 0.5, blockPos[2] + 0.5)
        for item in items.values():
            if itemUtils.IsEmpty(item):
                continue
            if not itemComp.SpawnItemToLevel(item, dimension, dropPos):
                logger.error("MoreChests: 掉落物生成失败 %s" % str(item.get("itemName")))
        self.ClearChest(dimension, blockPos, blockName)

    # ------------------------------------------------------------ 原地升级

    def TryUpgrade(self, playerId, dimension, blockPos, blockName, upgradeName):
        # 一个模板能作用于好几种源方块：普通箱子、对应的陷阱箱、以及陷阱箱的通电态。
        # 对着陷阱箱用就升成陷阱版（和 Java 版 IronChestsTypes.source() 的行为一致）
        sources = chestDefs.UPGRADES.get(upgradeName) or {}
        dstName = sources.get(blockName)
        if not dstName:
            logger.info("MoreChests: %s 用不到 %s 上" % (upgradeName, blockName))
            self.Tip(playerId, modConfig.TIP_UPGRADE_FAIL)
            return
        dstSlots = chestDefs.CHESTS[dstName]["slots"]
        logger.info("MoreChests: 升级 %s -> %s @ %s" % (blockName, dstName, str(blockPos)))

        blockInfoComp = compFactory.CreateBlockInfo(playerId)
        isVanilla = blockName in chestDefs.VANILLA_CHESTS

        # 朝向要在拆大箱子之前读 —— 拆的办法就是把这一半转个身，转完就读不到原朝向了
        aux = self.GetUpgradedAux(blockInfoComp, blockPos, dimension, blockName)

        # 大箱子：优先只升玩家点的那一半（和 Java 版一致 —— 原版大箱子本来就是
        # 两个各存 27 格的方块实体，只是显示成一个）。
        #
        # 但基岩版的容器接口是按合并后的 54 格寻址的，分不清哪 27 格属于哪一半。
        # 先试着把这一半转个身拆开配对；拆得开就只动它自己那 27 格。
        # **拆不开也照样升**，只是这时候整个大箱子的东西都会并进新箱子、
        # 另一半留成空的原版箱子 —— 一件都不会丢，只是位置和预期不同。
        # 早先那版在这里直接拒绝，结果就是大箱子根本升不了。
        splitFacing = None
        mergedWholeDouble = False
        if isVanilla and blockInfoComp.GetChestPairedPosition(blockPos):
            splitFacing = self.SplitDoubleChest(blockInfoComp, blockPos, dimension)
            if splitFacing is None:
                mergedWholeDouble = True
            else:
                size = self.VanillaChestSize(dimension, blockPos)
                logger.info("MoreChests: 拆开后容器大小 %s" % size)
                if size > 27:
                    # 配对报告说拆开了，但容器还是合并的，那就还是走合并那条路
                    mergedWholeDouble = True
            if mergedWholeDouble:
                logger.info("MoreChests: 大箱子没拆开，改为把整箱内容并进新箱子")

        # 先只读不改，确认装得下再动手，免得中途失败把东西弄丢
        if isVanilla:
            items = self.PeekVanillaChestItems(dimension, blockPos)
        else:
            items = [v for _, v in sorted(
                self.GetChestItems(dimension, blockPos, blockName).items(),
                key=lambda kv: itemUtils.ChestSlotIndex(kv[0]))]
        items = [it for it in items if not itemUtils.IsEmpty(it)]
        if len(items) > dstSlots:
            self.Tip(playerId, modConfig.TIP_UPGRADE_TOO_SMALL)
            # 拆过大箱子就把朝向转回去，别让玩家白白多一个转了向的箱子
            self.RestoreFacing(blockPos, dimension, splitFacing)
            return

        # 清空旧箱子，再换方块，最后写进新箱子
        if isVanilla:
            self.ClearVanillaChest(dimension, blockPos)
        else:
            self.ClearChest(dimension, blockPos, blockName)
        self.CloseUIForBlock(dimension, blockPos)

        key = (dimension, blockPos)
        self.mUpgrading.add(key)
        try:
            # 中间过一次空气：网易文档提到同类型方块实体直接替换时旧数据不会清掉
            blockInfoComp.SetBlockNew(blockPos, {"name": "minecraft:air", "aux": 0}, 0, dimension, True)
            ok = blockInfoComp.SetBlockNew(blockPos, {"name": dstName, "aux": aux}, 0, dimension, True)
            if ok:
                # aux 设进去了不代表方块状态就是想要的那个，读回来确认一次。
                # 朝向要是还不对，这两行日志能直接看出是没设上还是设上了但解释不一样
                self.VerifyFacing(blockPos, dimension, aux)
        finally:
            self.mUpgrading.discard(key)

        if not ok:
            logger.error("MoreChests: 升级时放置方块失败 %s -> %s" % (blockName, dstName))
            # 方块没放成，东西不能凭空消失，原地掉出来
            itemComp = compFactory.CreateItem(self.mLevelId)
            for item in items:
                itemComp.SpawnItemToLevel(item, dimension,
                                          (blockPos[0] + 0.5, blockPos[1] + 0.5, blockPos[2] + 0.5))
            return

        data = self.GetEntityData(dimension, blockPos)
        if data is None:
            logger.error("MoreChests: 升级后取不到方块实体数据，内容改为掉落")
            itemComp = compFactory.CreateItem(self.mLevelId)
            for item in items:
                itemComp.SpawnItemToLevel(item, dimension,
                                          (blockPos[0] + 0.5, blockPos[1] + 0.5, blockPos[2] + 0.5))
        else:
            for i, item in enumerate(items):
                data[itemUtils.ChestSlotName(i)] = itemUtils.Sanitize(item)

        if mergedWholeDouble:
            self.Tip(playerId, modConfig.TIP_UPGRADE_DOUBLE_CHEST)
        self.ConsumeHeldUpgrade(playerId)

    def GetUpgradedAux(self, blockInfoComp, blockPos, dimension, blockName):
        """读出源箱子的朝向，换算成本 mod 四面向方块的 aux。

        原先直接拿 GetBlockNew 的 aux 当 facing_direction 硬转，升级后朝向丢了。
        原因是 aux 到方块状态的对应关系随版本在变（网易文档在 SetBlockNew 那条
        备注里专门提过），原版箱子在新版本上用的是 minecraft:cardinal_direction
        这个**字符串**状态，不是老的 facing_direction 数值。

        所以改成读方块状态，按状态名分别处理，读不到才退回 aux。
        """
        states = None
        try:
            states = compFactory.CreateBlockState(self.mLevelId).GetBlockStates(
                blockPos, dimension)
        except Exception as exc:
            logger.warning("MoreChests: 读方块状态失败 %s" % exc)
        if states:
            logger.info("MoreChests: %s 的方块状态 %s" % (blockName, str(states)))
            aux = self.FacingAuxFromStates(states)
            if aux is not None:
                return aux

        try:
            blockDict = blockInfoComp.GetBlockNew(blockPos, dimension)
        except Exception:
            blockDict = None
        aux = blockDict.get("aux", 0) if blockDict else 0
        if blockName in chestDefs.VANILLA_CHESTS:
            return VANILLA_FACING_TO_AUX.get(aux, 0)
        return aux & 3

    def SplitDoubleChest(self, blockInfoComp, blockPos, dimension):
        """把大箱子的这一半转个身，拆开与邻居的配对。

        为什么要拆：大箱子的容器接口是按合并后的 54 格寻址的，
        分不清哪 27 格属于哪一半，直接读会把邻居的东西一起搬走。
        转身不动箱子里的东西，配对一断，这一格就只剩自己的 27 格。

        返回原来的朝向状态（dict），拆不开返回 None。
        """
        stateComp = compFactory.CreateBlockState(self.mLevelId)
        try:
            original = stateComp.GetBlockStates(blockPos, dimension) or {}
        except Exception as exc:
            logger.warning("MoreChests: 拆大箱子时读状态失败 %s" % exc)
            return None
        logger.info("MoreChests: 准备拆大箱子，原版箱子状态 %s" % str(original))
        if not original:
            logger.warning("MoreChests: 读不到原版箱子的方块状态，拆不了")
            return None

        for cardinal in CARDINALS:
            states = dict(original)
            if "minecraft:cardinal_direction" in original:
                if original["minecraft:cardinal_direction"] == cardinal:
                    continue
                states["minecraft:cardinal_direction"] = cardinal
            elif "facing_direction" in original:
                facing = CARDINAL_TO_FACING[cardinal]
                if original["facing_direction"] == facing:
                    continue
                states["facing_direction"] = facing
            else:
                logger.warning("MoreChests: 认不出原版箱子的朝向状态 %s" % str(original))
                return None
            try:
                setOk = stateComp.SetBlockStates(blockPos, states, dimension)
            except Exception as exc:
                logger.warning("MoreChests: 拆大箱子时改朝向失败 %s" % exc)
                return None
            paired = blockInfoComp.GetChestPairedPosition(blockPos)
            logger.info("MoreChests: 试转向 %s -> SetBlockStates=%s 仍配对=%s"
                        % (cardinal, setOk, paired))
            if not paired:
                return original
        # 四个朝向都试过还连着，八成是接口行为和预期不符，别硬来
        self.RestoreFacing(blockPos, dimension, original)
        logger.warning("MoreChests: 拆不开大箱子 @ %s" % str(blockPos))
        return None

    def RestoreFacing(self, blockPos, dimension, states):
        if not states:
            return
        try:
            compFactory.CreateBlockState(self.mLevelId).SetBlockStates(
                blockPos, states, dimension)
        except Exception as exc:
            logger.warning("MoreChests: 恢复朝向失败 %s" % exc)

    def VerifyFacing(self, blockPos, dimension, wantAux):
        """换完方块把朝向读回来对一下，对不上就再用 SetBlockStates 补一刀。

        SetBlockNew 传的是 aux，而 aux 到方块状态的对应关系是会随版本变的；
        直接写 direction 状态更稳，但不是所有版本都支持，所以只在对不上时才补。
        """
        try:
            comp = compFactory.CreateBlockState(self.mLevelId)
            states = comp.GetBlockStates(blockPos, dimension)
        except Exception as exc:
            logger.warning("MoreChests: 换完方块读状态失败 %s" % exc)
            return
        got = self.FacingAuxFromStates(states or {})
        if got == wantAux:
            return
        logger.info("MoreChests: 朝向对不上（想要 %s，实际 %s，状态 %s），补写 direction"
                    % (wantAux, got, str(states)))
        try:
            newStates = dict(states or {})
            newStates["direction"] = wantAux
            comp.SetBlockStates(blockPos, newStates, dimension)
        except Exception as exc:
            logger.warning("MoreChests: 补写朝向失败 %s" % exc)

    @staticmethod
    def FacingAuxFromStates(states):
        """方块状态 -> 四面向 aux（0=south 1=west 2=north 3=east）。认不出来返回 None。"""
        cardinal = states.get("minecraft:cardinal_direction")
        if cardinal is None:
            cardinal = states.get("cardinal_direction")
        if isinstance(cardinal, str) or isinstance(cardinal, type(u"")):
            return CARDINAL_TO_AUX.get(str(cardinal).lower())

        facing = states.get("facing_direction")
        if isinstance(facing, int):
            return VANILLA_FACING_TO_AUX.get(facing)

        # 本 mod 自己的四面向方块，状态里就是 direction，含义一致
        direction = states.get("direction")
        if isinstance(direction, int):
            return direction & 3
        return None

    def VanillaChestSize(self, dimension, blockPos):
        size = compFactory.CreateItem(self.mLevelId).GetContainerSize(blockPos, dimension)
        if size is None or size < 0:
            return 27
        return size

    def PeekVanillaChestItems(self, dimension, blockPos):
        itemComp = compFactory.CreateItem(self.mLevelId)
        items = []
        for i in range(self.VanillaChestSize(dimension, blockPos)):
            item = itemComp.GetContainerItem(blockPos, i, dimension, True)
            if not itemUtils.IsEmpty(item):
                items.append(item)
        return items

    def ClearVanillaChest(self, dimension, blockPos):
        """不清空的话，把箱子换成别的方块时里面的东西会掉一地。"""
        itemComp = compFactory.CreateItem(self.mLevelId)
        for i in range(self.VanillaChestSize(dimension, blockPos)):
            itemComp.SpawnItemToContainer({}, i, blockPos, dimension)

    def ConsumeHeldUpgrade(self, playerId):
        try:
            gameType = compFactory.CreateGame(self.mLevelId).GetPlayerGameType(playerId)
            if gameType == minecraftEnum.GameType.Creative:
                return
        except Exception:
            pass
        itemComp = compFactory.CreateItem(playerId)
        slotId = itemComp.GetSelectSlotId()
        if slotId is None or slotId < 0:
            return
        held = itemComp.GetPlayerItem(minecraftEnum.ItemPosType.INVENTORY, slotId, False)
        if not held:
            return
        itemComp.SetInvItemNum(slotId, max(0, held.get("count", 1) - 1))

    # ------------------------------------------------------------ tick

    def Update(self):
        # System 的 __init__ 可能跑在世界加载之前，那时候登记白名单不一定生效，
        # 所以这里再补一次（只补一次）
        if not self.mWhiteListRetried:
            self.mWhiteListRetried = True
            self.RegisterVanillaChestUse()

        # 玩家走远了就把界面关掉，免得隔着半张地图搬东西
        self.mTickCount += 1
        if self.mTickCount < 20:
            return
        self.mTickCount = 0
        if not self.mCurOpenedBlock:
            return
        for playerId in list(self.mCurOpenedBlock.keys()):
            info = self.mCurOpenedBlock[playerId]
            try:
                pos = compFactory.CreatePos(playerId).GetFootPos()
            except Exception:
                continue
            if not pos:
                continue
            blockPos = info["blockPos"]
            dx = pos[0] - (blockPos[0] + 0.5)
            dy = pos[1] - (blockPos[1] + 0.5)
            dz = pos[2] - (blockPos[2] + 0.5)
            if dx * dx + dy * dy + dz * dz > MAX_USE_DISTANCE_SQR:
                self.CloseUIFor(playerId)
