# -*- coding: utf-8 -*-
u"""按布局注册容器界面，并在右键箱子时把对应的那块推出来。

槽位数相同的箱子共用一块界面（钻石 / 水晶 / 黑曜石都是 108 格 12 列），
所以是一个布局一份注册，而不是一个方块一份。

**只注册，不预先 CreateUI。** 用的时候 PushScreen 推模态界面，
关的时候 PopScreen —— 和深渊背包 / 信纸那几块一个路子。
早先那版用 CreateUI 建成常驻 HUD 再 SetVisible 显隐，
结果是五块界面同时存在，谁都想注册 `#itemDetailAlpha` 这个全局数据绑定，
第二块就直接弹 assert（bindFloat: Trying to override bind callback for global bind）。
"""

import mod.client.extraClientApi as clientApi
from mod_log import logger

from PureRainMoreChestsScripts.modCommon import modConfig
from PureRainMoreChestsScripts.modCommon import chestDefs


class ChestUIMgr(object):

    def __init__(self):
        self._registered = False

    @staticmethod
    def UIKey(layout):
        return "%s_%s" % (modConfig.UINamespace, layout)

    def RegisterAll(self, *args, **kwargs):
        u"""UiInitFinished 的落点。注册是幂等的，重复调没关系。"""
        if self._registered:
            return
        for layout in chestDefs.UI_LAYOUTS:
            try:
                clientApi.RegisterUI(modConfig.ModName, self.UIKey(layout),
                                     modConfig.UIClassPath,
                                     "%s.main_%s" % (modConfig.UINamespace, layout))
            except Exception as exc:
                logger.error("MoreChests: 注册界面失败 %s: %s" % (layout, exc))
                return
        self._registered = True
        logger.info("MoreChests: 界面已注册 %d 套" % len(chestDefs.UI_LAYOUTS))

    def Push(self, blockName):
        u"""推出这个箱子对应的界面，返回 ScreenNode。"""
        chest = chestDefs.CHESTS.get(blockName)
        if not chest:
            logger.error("MoreChests: 未知的箱子方块 %s" % blockName)
            return None
        self.RegisterAll()
        try:
            return clientApi.PushScreen(modConfig.ModName, self.UIKey(chest["ui"]))
        except Exception as exc:
            logger.error("MoreChests: 打开界面失败 %s: %s" % (blockName, exc))
            return None
