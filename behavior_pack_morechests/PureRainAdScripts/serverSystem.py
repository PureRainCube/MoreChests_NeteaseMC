# -*- coding: utf-8 -*-

import server.extraServerApi as serverApi

try:
    from . import CNST
except Exception:
    import CNST


ServerSystemBase = serverApi.GetServerSystemCls()


class MssAddServerSystem(ServerSystemBase):

    def __init__(self, namespace, systemName):
        ServerSystemBase.__init__(self, namespace, systemName)
        self.ListenEvent()

    def ListenEvent(self):
        for event_name, func in self._ClientEvents():
            self.ListenForEvent(CNST.MOD_NAMESPACE, CNST.CLIENT_SYSTEM_NAME, event_name, self, func)

    def Destroy(self):
        for event_name, func in self._ClientEvents():
            try:
                self.UnListenForEvent(CNST.MOD_NAMESPACE, CNST.CLIENT_SYSTEM_NAME, event_name, self, func)
            except Exception:
                pass

    def _ClientEvents(self):
        return (
            (CNST.EV_AD_ASK, self.OnAdAsk),
            (CNST.EV_AD_OFF, self.OnAdOff),
        )

    def _GetExtraDataComp(self, playerId):
        try:
            return serverApi.GetEngineCompFactory().CreateExtraData(playerId)
        except Exception:
            return None

    def OnAdAsk(self, args):
        """客户端界面加载完成，回答这个玩家是否已经永久关闭了推荐入口。

        答案读的是玩家自己的 ExtraData，会随玩家一起存档，所以重进游戏依然有效。
        """
        playerId = (args or {}).get("playerId")
        if not playerId:
            return
        off = False
        comp = self._GetExtraDataComp(playerId)
        if comp:
            try:
                off = bool(comp.GetExtraData(CNST.AD_OFF_KEY))
            except Exception:
                off = False
        self.NotifyToClient(playerId, CNST.EV_AD_STATE, {"off": off})

    def OnAdOff(self, args):
        """玩家在二次确认里点了确认，记下来。

        没关闭的情况不写任何值：“没有这个值”本身就是默认状态，而写一个表示
        “继续显示”的值反而多一条读取失败就把入口永久藏掉的路径。
        """
        playerId = (args or {}).get("playerId")
        if not playerId:
            return
        comp = self._GetExtraDataComp(playerId)
        if not comp:
            return
        try:
            comp.SetExtraData(CNST.AD_OFF_KEY, True, True)
        except TypeError:
            # 旧签名不接受 autoSave
            try:
                comp.SetExtraData(CNST.AD_OFF_KEY, True)
            except Exception:
                pass
        except Exception:
            pass
