# -*- coding: utf-8 -*-
"""更多箱子 —— 全局常量。

箱子/升级模板的数据表在 chestDefs.py（由 tools/gen_assets.py 生成），
这里只放与引擎、事件、UI 名字相关的固定配置。
"""

ModName = "PureRainMoreChestsMod"
ModVersion = "1.0.0"

ServerSystemName = "PureRainMoreChestsServerSystem"
ServerSystemClsPath = "PureRainMoreChestsScripts.modServer.serverSystem.moreChestsServerSystem.MoreChestsServerSystem"

ClientSystemName = "PureRainMoreChestsClientSystem"
ClientSystemClsPath = "PureRainMoreChestsScripts.modClient.clientSystem.moreChestsClientSystem.MoreChestsClientSystem"

# ---------------------------------------------------------------- 引擎事件

ServerBlockUseEvent = "ServerBlockUseEvent"
ServerItemUseOnEvent = "ServerItemUseOnEvent"
ServerPlayerTryDestroyBlockEvent = "ServerPlayerTryDestroyBlockEvent"
BlockRemoveServerEvent = "BlockRemoveServerEvent"
ActorAcquiredItemServerEvent = "ActorAcquiredItemServerEvent"
PlayerDieEvent = "PlayerDieEvent"
DelServerPlayerEvent = "DelServerPlayerEvent"

# 客户端那边一个自定义方块实体加载出来了（进视野 / 区块加载 / 换了方块）。
# 箱盖动画要靠它补状态：不补的话，走进一个别人正开着的箱子的视野里，
# 看到的会是关着的盖子
ModBlockEntityLoadedClientEvent = "ModBlockEntityLoadedClientEvent"

ClientBlockUseEvent = "ClientBlockUseEvent"
ClientItemUseOnEvent = "ClientItemUseOnEvent"
UiInitFinishedEvent = "UiInitFinished"

# ---------------------------------------------------------------- 自定义事件
# 服务端 -> 客户端
OpenChestUIEvent = "OpenChestUIEvent"
ChestContentChangedEvent = "ChestContentChangedEvent"
BagChangedEvent = "BagChangedEvent"
ItemSwapServerEvent = "ItemSwapServerEvent"
ItemDropServerEvent = "ItemDropServerEvent"
CloseChestUIServerEvent = "CloseChestUIServerEvent"
# 箱盖开合。开关箱子时广播给所有人 —— 这是世界里看得见的东西，
# 不是只给开箱那个人看的
ChestLidStateServerEvent = "ChestLidStateServerEvent"
# 进世界时的一次性全量：当前开着的箱子列表
ChestLidSnapshotServerEvent = "ChestLidSnapshotServerEvent"

# 客户端 -> 服务端
CloseChestUIClientEvent = "CloseChestUIClientEvent"
ItemSwapClientEvent = "ItemSwapClientEvent"
ItemDropClientEvent = "ItemDropClientEvent"
# 快速转移（相当于 Java 版的 shift + 点击）与一键存入 / 取出
QuickMoveClientEvent = "QuickMoveClientEvent"
BulkMoveClientEvent = "BulkMoveClientEvent"
# 一键整理：箱子这一侧合并同种物品再排序
SortChestClientEvent = "SortChestClientEvent"
# 进世界时问一次「现在哪些箱子是开着的」
SyncChestLidsClientEvent = "SyncChestLidsClientEvent"

# ---------------------------------------------------------------- UI

UIClassPath = "PureRainMoreChestsScripts.modClient.ui.chestUI.ChestUIScreen"
UINamespace = "pureRainChestsUI"

# ---------------------------------------------------------------- 其它

# 玩家背包槽位数（主物品栏，含快捷栏）
INV_SLOT_NUM = 36
# 箱子槽位在事件里的 key 前缀，与 blockEntityData 的 key 一致
CHEST_SLOT_PREFIX = "c"
# 事件数据里两个背包的分区键
INVENTORY_BAG = "bag"
CHEST_BAG = "chest"

# ---------------------------------------------------------------- 箱盖动画
# 箱子的模型是「客户端实体」（见 tools/gen_chest_entity.py），
# 箱盖开合靠改这个 molang 变量触发动画控制器换状态。
# **必须和 gen_chest_entity.MOLANG_OPEN 一字不差**，validate.py 会核对
CHEST_OPEN_MOLANG = "variable.chest_open"

# ---------------------------------------------------------------- 音效
# 开合箱子用原版自己那两个事件名，不用随包带 ogg。
# 界面里按钮的「咔」那一声不在这儿 —— 它写在 ui json 的 button 上，引擎自己播。
SOUND_CHEST_OPEN = "random.chestopen"
SOUND_CHEST_CLOSE = "random.chestclosed"
# 多远以内的人能听见。原版箱子大致就是这个量级
SOUND_HEAR_RANGE = 16.0

# ---------------------------------------------------------------- 提示文案
# NotifyOneMessage 走的是聊天框原文，不会把 .lang 的键翻译过来，
# 所以这几条直接写中文（本 mod 面向中国版）。UI 里的文字仍然走 .lang。
TIP_DIRT_ONLY = u"§e泥土箱 9000 只收泥土：泥土 / 砂土 / 灰化土 / 缠根泥土 / 草方块 / 菌丝"
TIP_CHEST_FULL = u"§e箱子这一格放不下了"
TIP_UPGRADE_FAIL = u"§e这个升级模板对这个箱子没用"
TIP_UPGRADE_DOUBLE_CHEST = u"§e大箱子拆不开，已把整箱东西并进新箱子，另一半空了"
TIP_UPGRADE_TOO_SMALL = u"§e新箱子装不下里面的东西"
