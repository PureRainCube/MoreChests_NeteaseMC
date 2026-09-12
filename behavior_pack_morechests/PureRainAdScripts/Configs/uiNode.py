# -*- coding: utf-8 -*-

# 广告面板的控件路径。改动 pureRainAdUI.json 的控件命名时必须同步这里：
# ModSDK 找不到路径不会报错，只会让回调永远不触发、标签永远不更新。

mainUI = None

# 整个弹窗（半透明遮罩 + 卡片 + 二次确认层），显示/隐藏都以它为单位
add_panel = "/panel/window"

_card = "/panel/window/card"
_nav = _card + "/nav"

lobby_btn = _nav + "/lobby_btn"
addons_btn = _nav + "/addons_btn"
pack_btn = _nav + "/pack_btn"

# 各分类按钮左侧的绿色高亮条，由客户端按当前分类切换显示
nav_active_suffix = "/active"
nav_btn_by_tab = {
    "addons": addons_btn,
    "lobby": lobby_btn,
    "pack": pack_btn,
}

close_btn = _card + "/close_btn"
footer_close_btn = _card + "/footer_close_btn"

top_tips_label = _card + "/tips_box/label"

# 永久关闭入口：按钮弹出二次确认，确认后写入玩家存档
dontshow_btn = _card + "/dontshow"
confirm_panel = "/panel/window/confirm"
confirm_yes_btn = confirm_panel + "/box/yes_btn"
confirm_no_btn = confirm_panel + "/box/no_btn"

# HUD 上可拖动的入口按钮
open_ad_btn = "/panel/entry_btn"

add_scroll_view = _card + "/scroll_view"
add_scroll_view_ad_stack = add_scroll_view + "/ad_stack"
add_scroll_view_ad_content_1 = add_scroll_view_ad_stack + "/ad_content_1"
add_scroll_view_image = add_scroll_view_ad_content_1 + "/image"
add_scroll_view_button = add_scroll_view_image + "/button"
dynamic_add_list = []
dynamic_add_image_list = []
