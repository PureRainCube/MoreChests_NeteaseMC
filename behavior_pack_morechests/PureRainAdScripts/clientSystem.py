# -*- coding: utf-8 -*-

import random
import time
import mod.client.extraClientApi as clientApi

from PureRainAdScripts.Configs import addConfig
from PureRainAdScripts.Configs import uiNode
try:
    from . import CNST
except Exception:
    import CNST


ClientSystemBase = clientApi.GetClientSystemCls()


class MssAddClientSystem(ClientSystemBase):

    def __init__(self, namespace, systemName):
        ClientSystemBase.__init__(self, namespace, systemName)
        self.ui = None
        self._scroll_btn_block_until = {}
        self._current_tab = "addons"
        # 玩家是否已永久关闭推荐入口。默认 False：答案在服务端，若服务端没有回应，
        # 宁可照常显示，也不要因为一次读取失败就把入口永久藏起来。
        self._ad_off = False
        self.ListenEvent()
    def ListenEvent(self):
        engine_namespace = clientApi.GetEngineNamespace()
        engine_system_name = clientApi.GetEngineSystemName()
        self.ListenForEvent(engine_namespace, engine_system_name, "UiInitFinished", self, self.UiInitFinished)
        self.ListenForEvent(CNST.MOD_NAMESPACE, CNST.SERVER_SYSTEM_NAME, CNST.EV_AD_STATE, self, self.OnAdState)

    def Destroy(self):
        try:
            self.UnListenForEvent(CNST.MOD_NAMESPACE, CNST.SERVER_SYSTEM_NAME, CNST.EV_AD_STATE, self, self.OnAdState)
        except Exception:
            pass
        try:
            getattr(uiNode, "dynamic_add_list", [])[:] = []
            getattr(uiNode, "dynamic_add_image_list", [])[:] = []
        except Exception:
            pass
        self.ui = None

    def UiInitFinished(self, args):
        try:
            clientApi.RegisterUI(CNST.MOD_NAMESPACE, CNST.SHOP_UI_NAME, CNST.SHOP_UI_CLASS, CNST.SHOP_UI_SCREEN)
        except Exception:
            pass
        try:
            uiNode.mainUI = clientApi.CreateUI(CNST.MOD_NAMESPACE, CNST.SHOP_UI_NAME, {"isHud": 1})
        except Exception:
            uiNode.mainUI = None
        try:
            self.ui = clientApi.GetUI(CNST.MOD_NAMESPACE, CNST.SHOP_UI_NAME)
        except Exception:
            self.ui = None
        self.CloseShopPanel()
        self._AskAdState()

    # --- 永久关闭推荐入口 ---------------------------------------------------
    def _AskAdState(self):
        try:
            self.NotifyToServer(CNST.EV_AD_ASK, {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass

    def OnAdState(self, args):
        """服务端回答了这个玩家的选择。"""
        if (args or {}).get("off"):
            self._ad_off = True
            self.CloseShopPanel()
            self._SetVisible(uiNode.open_ad_btn, False)

    def ShowDisableConfirm(self):
        """“永久关闭推荐入口”只是弹出确认，真正生效要再点一次。

        这一步不可撤销，而误触一次就再也找不回入口，所以必须两次点击。
        """
        self._SetVisible(uiNode.confirm_panel, True)

    def HideDisableConfirm(self):
        self._SetVisible(uiNode.confirm_panel, False)

    def DisableAdEntry(self):
        """玩家确认了：立刻收掉入口，并让服务端把这件事写进存档。"""
        self._ad_off = True
        self.HideDisableConfirm()
        self.CloseShopPanel()
        self._SetVisible(uiNode.open_ad_btn, False)
        try:
            self.NotifyToServer(CNST.EV_AD_OFF, {"playerId": clientApi.GetLocalPlayerId()})
        except Exception:
            pass

    def _SetVisible(self, path, visible):
        try:
            if uiNode.mainUI:
                uiNode.mainUI.SetVisible(path, bool(visible))
        except Exception:
            pass

    def _UpdateNavHighlight(self):
        """左侧分类按钮的绿色高亮条，只有当前分类那一条显示。"""
        for tab_name, btn_path in (getattr(uiNode, "nav_btn_by_tab", {}) or {}).items():
            self._SetVisible(btn_path + uiNode.nav_active_suffix, tab_name == self._current_tab)

    def OpenShopPanel(self, tab_name="addons"):
        if self._ad_off:
            return
        self._current_tab = str(tab_name or "addons")
        try:
            clientApi.HideHudGUI(True)
        except Exception:
            pass
        try:
            if uiNode.mainUI:
                uiNode.mainUI.SetResponse(False)
        except Exception:
            pass
        try:
            if uiNode.mainUI:
                uiNode.mainUI.SetText(uiNode.top_tips_label, self._get_top_tips_text())
        except Exception:
            pass
        self._UpdateNavHighlight()
        # 每次打开都重置：确认框停留在上次打开时的状态，等于替玩家回答了一个他没回答的问题
        self.HideDisableConfirm()
        try:
            if uiNode.mainUI:
                uiNode.mainUI.SetVisible(uiNode.add_panel, True)
        except Exception:
            pass
        self.RefreshScrollView()

    def CloseShopPanel(self):
        self.HideDisableConfirm()
        try:
            if uiNode.mainUI:
                uiNode.mainUI.SetVisible(uiNode.add_panel, False)
        except Exception:
            pass
        try:
            if uiNode.mainUI:
                uiNode.mainUI.SetResponse(True)
        except Exception:
            pass
        try:
            clientApi.HideHudGUI(False)
        except Exception:
            pass

    def SwitchTab(self, tab_name):
        self.OpenShopPanel(tab_name)

    def OpenRandomShopPanel(self):
        self.OpenShopPanel(random.choice(("lobby", "addons")))

    def _get_top_tips_text(self):
        return "B站/抖音：清雨立方\nQQ群：1057705613"

    def GetCurrentGoods(self):
        if self._current_tab == "lobby":
            return list(getattr(addConfig, "LOBBY_LIST", []) or [])
        if self._current_tab == "pack":
            return list(getattr(addConfig, "PACK_LIST", []) or [])
        # 模组是默认分类：皮肤分类连同素材已整个移除，兜底不能再落回一个不存在的表
        return list(getattr(addConfig, "ADDONS_LIST", []) or [])

    def RefreshScrollView(self):
        if not uiNode.mainUI:
            return
        items = self.GetCurrentGoods()
        total = len(items)
        try:
            scroll = uiNode.mainUI.GetBaseUIControl(uiNode.add_scroll_view).asScrollView()
            content_path = scroll.GetScrollViewContentPath()
            children = uiNode.mainUI.GetAllChildrenPath(content_path) or []
        except Exception:
            return
        if not children:
            return
        first_row_path = uiNode.add_scroll_view_ad_content_1
        if first_row_path not in children:
            first_row_path = children[0]
        parent_path = content_path
        self._clear_dynamic_nodes(parent_path)
        groups = 1
        if total > 0:
            groups = int((total + 4) / 5)
        try:
            base = uiNode.mainUI.GetBaseUIControl(parent_path)
            size = base.GetSize()
            height = 120 * groups
            if isinstance(size, (tuple, list)) and len(size) >= 2:
                base.SetSize((size[0], height))
        except Exception:
            pass
        for group_index in range(groups):
            row_path = first_row_path
            if group_index > 0:
                clone_name = "ad_content_{}".format(group_index + 1)
                row_path = parent_path + "/" + clone_name
                try:
                    uiNode.mainUI.Clone(first_row_path, parent_path, clone_name, False)
                    getattr(uiNode, "dynamic_add_list", []).append(row_path)
                except Exception:
                    continue
            self._refresh_row(row_path, items, group_index)
        try:
            uiNode.mainUI.UpdateScreen(True)
        except Exception:
            pass

    def _clear_dynamic_nodes(self, parent_path):
        try:
            for path in list(getattr(uiNode, "dynamic_add_image_list", []) or []):
                try:
                    image_parent = path.rsplit("/", 1)[0]
                    uiNode.mainUI.RemoveComponent(path, image_parent)
                except Exception:
                    pass
            getattr(uiNode, "dynamic_add_image_list", [])[:] = []
        except Exception:
            pass
        try:
            for path in list(getattr(uiNode, "dynamic_add_list", []) or []):
                try:
                    uiNode.mainUI.RemoveComponent(path, parent_path)
                except Exception:
                    pass
            getattr(uiNode, "dynamic_add_list", [])[:] = []
        except Exception:
            pass

    def _refresh_row(self, row_path, items, group_index):
        base_image_path = row_path + "/image"
        start_index = group_index * 5
        row_count = len(items) - start_index
        if row_count > 5:
            row_count = 5
        if row_count <= 0:
            row_count = 1
        for slot_index in range(1, 5):
            clone_name = "image_{}".format(slot_index + 1)
            image_path = row_path + "/" + clone_name
            try:
                uiNode.mainUI.RemoveComponent(image_path, row_path)
            except Exception:
                pass
        try:
            uiNode.mainUI.SetVisible(base_image_path, row_count > 0)
        except Exception:
            pass
        for slot_index in range(row_count):
            image_path = base_image_path
            if slot_index > 0:
                clone_name = "image_{}".format(slot_index + 1)
                image_path = row_path + "/" + clone_name
                try:
                    uiNode.mainUI.Clone(base_image_path, row_path, clone_name, False)
                    getattr(uiNode, "dynamic_add_image_list", []).append(image_path)
                except Exception:
                    continue
            data_index = start_index + slot_index
            self._refresh_item(image_path, items[data_index])

    def _refresh_item(self, image_path, data):
        goods_id = int((data or {}).get("store_id", -1) or -1)
        sprite = str(getattr(addConfig, "ICON_PREFIX", "textures/ui/icon/") or "textures/ui/icon/") + str((data or {}).get("id") or "")
        try:
            uiNode.mainUI.SetVisible(image_path, True)
        except Exception:
            pass
        for target in (image_path, image_path + "/default", image_path + "/hover", image_path + "/pressed"):
            try:
                uiNode.mainUI.SetSprite(target, sprite)
            except Exception:
                pass
        button_path = image_path + "/button"
        try:
            btn = uiNode.mainUI.GetBaseUIControl(button_path).asButton()
            btn.AddTouchEventParams({"isSwallow": True, "goods_id": goods_id})
            btn.SetButtonTouchMoveCallback(self._on_scroll_button_move)
            btn.SetButtonTouchUpCallback(self._on_goods_btn_click)
        except Exception:
            pass

    def _on_scroll_button_move(self, args):
        button_path = str((args or {}).get("ButtonPath", "") or "")
        if not button_path:
            return
        self._scroll_btn_block_until[button_path] = time.time() + 0.15

    def _on_goods_btn_click(self, args):
        button_path = str((args or {}).get("ButtonPath", "") or "")
        if not button_path:
            return
        try:
            if time.time() < float(self._scroll_btn_block_until.get(button_path, 0)):
                return
        except Exception:
            pass
        touch_params = (args or {}).get("AddTouchEventParams") or {}
        goods_id = int(touch_params.get("goods_id", -1) or -1)
        if goods_id <= 0:
            return
        self._open_store(goods_id)

    def _open_store(self, goods_id):
        try:
            goods_id = int(goods_id or -1)
        except Exception:
            goods_id = -1
        if goods_id == -1:
            return
        try:
            player_id = clientApi.GetLocalPlayerId()
        except Exception:
            player_id = None
        try:
            comp = clientApi.GetEngineCompFactory().CreateNeteaseWindow(player_id)
            comp.OpenResourceCenterDetailWindow(str(goods_id))
        except Exception:
            pass
