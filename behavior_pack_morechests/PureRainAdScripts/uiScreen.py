# -*- coding: utf-8 -*-

import mod.client.extraClientApi as clientApi
from PureRainAdScripts.Configs import uiNode
try:
    from . import CNST
except Exception:
    import CNST


ScreenNode = clientApi.GetScreenNodeCls()


class mainScreen(ScreenNode):

    def __init__(self, namespace, name, param):
        ScreenNode.__init__(self, namespace, name, param)
        self.ClientSystem = None

    def Create(self):
        self.ClientSystem = clientApi.GetSystem(CNST.MOD_NAMESPACE, CNST.CLIENT_SYSTEM_NAME)
        self.AddTouchEventHandler(uiNode.open_ad_btn, self._on_open_ad_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.lobby_btn, self._on_lobby_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.addons_btn, self._on_addons_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.close_btn, self._on_close_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.footer_close_btn, self._on_close_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.dontshow_btn, self._on_dontshow_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.confirm_yes_btn, self._on_confirm_yes_btn, {"isSwallow": True})
        self.AddTouchEventHandler(uiNode.confirm_no_btn, self._on_confirm_no_btn, {"isSwallow": True})

    def Destroy(self):
        self.ClientSystem = None

    def _check_touch_up_event(self, args):
        touch_event = (args or {}).get("TouchEvent")
        return touch_event == clientApi.GetMinecraftEnum().TouchEvent.TouchUp

    def _on_open_ad_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.OpenRandomShopPanel()

    def _on_lobby_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.SwitchTab("lobby")

    def _on_addons_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.SwitchTab("addons")

    def _on_close_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.CloseShopPanel()

    def _on_dontshow_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.ShowDisableConfirm()

    def _on_confirm_yes_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.DisableAdEntry()

    def _on_confirm_no_btn(self, args):
        if self._check_touch_up_event(args) and self.ClientSystem:
            self.ClientSystem.HideDisableConfirm()
