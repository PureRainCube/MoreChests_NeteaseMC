# -*- coding: utf-8 -*-

from mod.common.mod import Mod
import server.extraServerApi as serverApi
import client.extraClientApi as clientApi

try:
    from . import CNST
except Exception:
    import CNST


@Mod.Binding(name=CNST.MOD_NAMESPACE, version="0.0.1")
class Main(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def ServerInit(self):
        serverApi.RegisterSystem(
            CNST.MOD_NAMESPACE,
            CNST.SERVER_SYSTEM_NAME,
            CNST.MOD_NAMESPACE + ".serverSystem.MssAddServerSystem",
        )

    @Mod.DestroyServer()
    def ServerDestroy(self):
        pass

    @Mod.InitClient()
    def ClientInit(self):
        clientApi.RegisterSystem(
            CNST.MOD_NAMESPACE,
            CNST.CLIENT_SYSTEM_NAME,
            CNST.MOD_NAMESPACE + ".clientSystem.MssAddClientSystem",
        )

    @Mod.DestroyClient()
    def ClientDestroy(self):
        pass
