# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
import mod.server.extraServerApi as serverApi
from mod.common.mod import Mod
from mod_log import logger

from PureRainMoreChestsScripts.modCommon import modConfig


@Mod.Binding(name=modConfig.ModName, version=modConfig.ModVersion)
class MoreChestsMod(object):

    def __init__(self):
        logger.info("===== MoreChests mod init =====")

    @Mod.InitServer()
    def MoreChestsServerInit(self):
        serverApi.RegisterSystem(modConfig.ModName, modConfig.ServerSystemName,
                                 modConfig.ServerSystemClsPath)

    @Mod.InitClient()
    def MoreChestsClientInit(self):
        clientApi.RegisterSystem(modConfig.ModName, modConfig.ClientSystemName,
                                 modConfig.ClientSystemClsPath)

    @Mod.DestroyServer()
    def MoreChestsServerDestroy(self):
        pass

    @Mod.DestroyClient()
    def MoreChestsClientDestroy(self):
        pass
