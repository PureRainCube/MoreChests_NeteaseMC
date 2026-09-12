# -*- coding: utf-8 -*-

_file = __file__
if "/" in _file:
    MOD_NAMESPACE = _file.rsplit("/", 2)[-2]
elif "\\" in _file:
    MOD_NAMESPACE = _file.rsplit("\\", 2)[-2]
else:
    MOD_NAMESPACE = _file.rsplit(".", 2)[-2]

SERVER_SYSTEM_NAME = "Server"
CLIENT_SYSTEM_NAME = "Client"

SHOP_UI_NAME = "mss_add_shop"
SHOP_UI_CLASS = MOD_NAMESPACE + ".uiScreen.mainScreen"
SHOP_UI_SCREEN = "pureRainAdUI.main"

GUIDE_INDEX_ITEM = "mss:guide_index"

# 玩家永久关闭推荐入口的开关。存在玩家的 ExtraData 上：脚本状态每次启动都会重建，
# 而世界级的开关会让一个人的选择影响所有人。
AD_OFF_KEY = "mss_ad_entry_off"

EV_AD_ASK = "mss_ad_ask"      # client -> server: HUD 就绪，这个玩家还要看广告入口吗
EV_AD_STATE = "mss_ad_state"  # server -> client: {"off": bool}
EV_AD_OFF = "mss_ad_off"      # client -> server: 玩家确认永久关闭
