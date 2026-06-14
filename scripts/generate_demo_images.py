"""生成 README 演示截图（高保真，忠于真实 UI 配色与布局）。

输出：
  docs/images/dashboard-demo.png   数据可视化仪表板
  docs/images/relationships-demo.png  关系图谱

这些是演示用的静态渲染图，配色与组件布局严格对应前端实际实现。
"""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

# ===== 项目实际配色（Tailwind 等价值）=====
GRAY_50 = "#f9fafb"
GRAY_100 = "#f3f4f6"
GRAY_200 = "#e5e7eb"
GRAY_300 = "#d1d5db"
GRAY_400 = "#9ca3af"
GRAY_500 = "#6b7280"
GRAY_700 = "#374151"
GRAY_900 = "#111827"
BLUE_500 = "#3b82f6"
BLUE_600 = "#2563eb"
EMERALD_500 = "#10b981"
INDIGO_400 = "#818cf8"
INDIGO_500 = "#6366f1"
PURPLE_500 = "#8b5cf6"
AMBER_100 = "#fef3c7"
AMBER_800 = "#92400e"
PINK_400 = "#f472b6"
ORANGE_500 = "#f97316"
WHITE = "#ffffff"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "images")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载字体，优先用系统黑体，退化到默认"""
    candidates = (
        ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"]
        if bold
        else ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhl.ttc"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    # 退化
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _heat_color(count: int, max_count: int) -> str:
    """复刻 dashboard.vue 的 heatmapColor：浅蓝→深紫"""
    if count == 0 or max_count == 0:
        return GRAY_100
    intensity = math.log(count + 1) / math.log(max_count + 1)
    hue = 220 - intensity * 40
    lightness = 90 - intensity * 50
    return f"hsl({hue:.0f}, 65%, {lightness:.0f}%)"


def _color_to_rgb(color: str) -> tuple[int, int, int]:
    """解析 'hsl(H, S%, L%)' 或 '#rrggbb' 为 RGB 元组"""
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    s = color[4:-1]  # 去掉 'hsl(' 和 ')'
    h_part, s_part, l_part = [p.strip() for p in s.split(",")]
    h = float(h_part)
    sat = float(s_part.rstrip("%")) / 100
    l = float(l_part.rstrip("%")) / 100
    c = (1 - abs(2 * l - 1)) * sat
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def _rounded_rect(draw, xy, radius, fill, outline=None):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline)


def _draw_navbar(draw, width: int):
    """顶部导航栏（对应 app.vue）"""
    _rounded_rect(draw, [0, 0, width, 56], 0, WHITE)
    draw.line([(0, 56), (width, 56)], fill=GRAY_200, width=1)
    f_bold = _font(18, bold=True)
    f_nav = _font(14)
    draw.text((32, 18), "LifeVault", fill=GRAY_900, font=f_bold)
    items = ["消息", "仪表板", "话题", "关系图谱", "搜索", "AI 助手", "导入", "导出"]
    x = width - 32
    for item in reversed(items):
        w = draw.textlength(item, font=f_nav)
        x -= w + 6
        color = BLUE_600 if item == "仪表板" else GRAY_500
        draw.text((x, 20), item, fill=color, font=f_nav)
        x -= 24


def _draw_header(draw, x, y, title, subtitle):
    f_title = _font(28, bold=True)
    f_sub = _font(13)
    draw.text((x, y), title, fill=GRAY_900, font=f_title)
    draw.text((x, y + 40), subtitle, fill=GRAY_500, font=f_sub)
    return y + 70


def _draw_stat_card(draw, x, y, w, h, label, value, color):
    _rounded_rect(draw, [x, y, x + w, y + h], 8, WHITE)
    f_label = _font(12)
    f_value = _font(26, bold=True)
    draw.text((x + 16, y + 14), label, fill=GRAY_500, font=f_label)
    draw.text((x + 16, y + 36), value, fill=color, font=f_value)


def _draw_heatmap(draw, x, y, width, height):
    """7×24 活动热力图（对应 dashboard.vue 的活动热力图区块）"""
    f_title = _font(17, bold=True)
    f_small = _font(11)
    draw.text((x, y), "活动热力图", fill=GRAY_900, font=f_title)
    draw.text((x + width - 130, y + 4), "星期 × 小时 (UTC+8)", fill=GRAY_500, font=f_small)

    grid_x = x + 60
    grid_y = y + 38
    cell_w = (width - 60) / 24
    cell_h = 22
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # 随机但合理的数据（工作日晚上 + 周末白天高频）
    random.seed(42)
    matrix = [[0] * 24 for _ in range(7)]
    for d in range(7):
        for h in range(24):
            base = 0
            if d < 5:  # 工作日
                if 9 <= h <= 12:
                    base = random.randint(3, 8)
                elif 14 <= h <= 18:
                    base = random.randint(2, 6)
                elif 19 <= h <= 23:
                    base = random.randint(8, 20)
                elif 0 <= h <= 1:
                    base = random.randint(2, 5)
            else:  # 周末
                if 10 <= h <= 23:
                    base = random.randint(5, 16)
            matrix[d][h] = base
    max_count = max(max(row) for row in matrix)

    # 小时标签
    for h in range(24):
        if h % 6 == 0:
            lx = grid_x + h * cell_w + cell_w / 2
            draw.text((lx - 6, grid_y - 16), f"{h}", fill=GRAY_400, font=f_small)

    for d in range(7):
        draw.text((x, grid_y + d * cell_h + 4), weekdays[d], fill=GRAY_500, font=f_small)
        for h in range(24):
            cx = grid_x + h * cell_w
            cy = grid_y + d * cell_h
            color = _color_to_rgb(_heat_color(matrix[d][h], max_count))
            _rounded_rect(draw, [cx + 1, cy + 1, cx + cell_w - 1, cy + cell_h - 1], 2, color)


def _draw_hourly_bars(draw, x, y, width, height, color):
    """每小时分布柱状图（对应 dashboard.vue）"""
    f_title = _font(17, bold=True)
    draw.text((x, y), "每小时分布", fill=GRAY_900, font=f_title)
    random.seed(7)
    data = [random.randint(0, 8) for _ in range(24)]
    for h in [9, 12, 19, 20, 21, 22, 23]:
        data[h] = random.randint(12, 24)
    for h in range(0, 6):
        data[h] = random.randint(0, 3)
    max_v = max(data)
    bar_area_h = height - 40
    bar_w = (width - 20) / 24 - 2
    for i, v in enumerate(data):
        bh = (v / max_v) * bar_area_h if max_v > 0 else 0
        bx = x + 10 + i * (bar_w + 2)
        by = y + 30 + bar_area_h - bh
        if bh > 0:
            _rounded_rect(draw, [bx, by, bx + bar_w, y + 30 + bar_area_h], 2, color)


def _draw_weekday_bars(draw, x, y, width, height, color):
    f_title = _font(17, bold=True)
    f_small = _font(11)
    draw.text((x, y), "每周分布", fill=GRAY_900, font=f_title)
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    data = [18, 22, 19, 25, 28, 35, 31]
    max_v = max(data)
    bar_area_h = height - 50
    slot_w = width / 7
    bar_w = 28
    for i, (v, label) in enumerate(zip(data, labels)):
        bh = (v / max_v) * bar_area_h
        bx = x + i * slot_w + (slot_w - bar_w) / 2
        by = y + 30 + bar_area_h - bh
        _rounded_rect(draw, [bx, by, bx + bar_w, y + 30 + bar_area_h], 2, color)
        draw.text((x + i * slot_w + slot_w / 2 - 12, y + 30 + bar_area_h + 6),
                  label, fill=GRAY_500, font=f_small)


def _draw_trend_line(draw, x, y, width, height):
    """每日消息趋势折线图（对应 dashboard.vue 的 SVG 趋势）"""
    f_title = _font(17, bold=True)
    f_small = _font(11)
    draw.text((x, y), "每日消息趋势", fill=GRAY_900, font=f_title)
    random.seed(11)
    data = [random.randint(5, 40) for _ in range(30)]
    # 制造一个峰
    data[20] = 48
    max_v = max(data)
    pad = 12
    area_h = height - 40
    area_w = width - 2 * pad
    pts = []
    for i, v in enumerate(data):
        px = x + pad + (i / (len(data) - 1)) * area_w
        py = y + 30 + area_h - (v / max_v) * area_h
        pts.append((px, py))
    # 渐变填充区域
    fill_pts = pts + [(pts[-1][0], y + 30 + area_h), (pts[0][0], y + 30 + area_h)]
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.polygon(fill_pts, fill=(99, 102, 241, 60))
    img = draw._image
    img.paste(overlay, (x, y), overlay)
    # 折线
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=(79, 70, 229), width=2)
    draw.text((x + pad, y + 8), f"峰值 {max_v}", fill=GRAY_400, font=f_small)


def _draw_top_terms(draw, x, y, width, height):
    """高频词 Top 标签云（对应 dashboard.vue）"""
    f_title = _font(17, bold=True)
    f_small = _font(13)
    draw.text((x, y), "高频词 Top", fill=GRAY_900, font=f_title)
    terms = [
        ("工作", 86, True), ("周末", 72, True), ("python", 58, False),
        ("吃饭", 45, False), ("开会", 38, False), ("项目", 31, False),
        ("谢谢", 28, False), ("好的", 24, False), ("哈哈", 21, False),
    ]
    cx, cy = x + 8, y + 38
    line_h = 30
    for term, count, top in terms:
        w = draw.textlength(term, font=f_small)
        bg = AMBER_100 if top else "#e0e7ff"
        tc = AMBER_800 if top else "#3730a3"
        tag_w = w + 24
        _rounded_rect(draw, [cx, cy, cx + tag_w, cy + 24], 12, bg)
        draw.text((cx + 12, cy + 4), term, fill=tc, font=f_small)
        cnt_w = draw.textlength(str(count), font=_font(11))
        draw.text((cx + tag_w - cnt_w - 10, cy + 6), str(count), fill=GRAY_500, font=_font(11))
        cx += tag_w + 8
        if cx + 80 > x + width:
            cx = x + 8
            cy += line_h


def _draw_sender_ratio(draw, x, y, width, height):
    f_title = _font(17, bold=True)
    f_small = _font(12)
    draw.text((x, y), "发送 / 接收比例", fill=GRAY_900, font=f_title)
    bar_y = y + 40
    bar_h = 32
    sent_pct = 38.5
    sent_w = width * sent_pct / 100
    _rounded_rect(draw, [x, bar_y, x + width, bar_y + bar_h], 6, GRAY_300)
    _rounded_rect(draw, [x, bar_y, x + sent_w, bar_y + bar_h], 6, BLUE_500)
    draw.text((x + 12, bar_y + 9), f"发送 {sent_pct}%", fill=WHITE, font=_font(13, bold=True))
    draw.text((x + sent_w + 12, bar_y + 9), f"接收 {100 - sent_pct:.1f}%", fill=GRAY_700, font=_font(13))
    draw.text((x + width - 80, bar_y + bar_h + 12), "总互动 2,847", fill=GRAY_500, font=f_small)


def make_dashboard_demo():
    width, height = 1200, 1180
    img = Image.new("RGB", (width, height), GRAY_50)
    draw = ImageDraw.Draw(img, "RGBA")
    _draw_navbar(draw, width)
    y = _draw_header(draw, 48, 88, "数据可视化仪表板",
                     "基于消息时间、类型、发送者维度的多角度分析")

    # 四张统计卡
    card_y = y
    card_w = (width - 96 - 3 * 16) / 4
    _draw_stat_card(draw, 48, card_y, card_w, 80, "总消息数", "12,847", BLUE_600)
    _draw_stat_card(draw, 48 + (card_w + 16) * 1, card_y, card_w, 80, "活跃天数", "186", EMERALD_500)
    _draw_stat_card(draw, 48 + (card_w + 16) * 2, card_y, card_w, 80, "最活跃时段", "21:00", PURPLE_500)
    _draw_stat_card(draw, 48 + (card_w + 16) * 3, card_y, card_w, 80, "最活跃星期", "周六", ORANGE_500)
    y = card_y + 80 + 24

    # 热力图
    heat_w = width - 96
    heat_h = 230
    _rounded_rect(draw, [48, y, 48 + heat_w, y + heat_h], 8, WHITE)
    _draw_heatmap(draw, 64, y + 16, heat_w - 32, heat_h - 32)
    y += heat_h + 24

    # 每小时 + 每周（两列）
    col_w = (width - 96 - 24) / 2
    _rounded_rect(draw, [48, y, 48 + col_w, y + 200], 8, WHITE)
    _draw_hourly_bars(draw, 64, y + 16, col_w - 32, 170, BLUE_500)
    _rounded_rect(draw, [48 + col_w + 24, y, 48 + col_w + 24 + col_w, y + 200], 8, WHITE)
    _draw_weekday_bars(draw, 64 + col_w + 24, y + 16, col_w - 32, 170, EMERALD_500)
    y += 200 + 24

    # 每日趋势（整行）
    _rounded_rect(draw, [48, y, 48 + heat_w, y + 180], 8, WHITE)
    _draw_trend_line(draw, 64, y + 16, heat_w - 32, 150)
    y += 180 + 24

    # 高频词 + 发送接收（两列）
    _rounded_rect(draw, [48, y, 48 + col_w, y + 160], 8, WHITE)
    _draw_top_terms(draw, 64, y + 16, col_w - 32, 130)
    _rounded_rect(draw, [48 + col_w + 24, y, 48 + col_w + 24 + col_w, y + 160], 8, WHITE)
    _draw_sender_ratio(draw, 64 + col_w + 24, y + 16, col_w - 32, 130)

    img.save(os.path.join(OUTPUT_DIR, "dashboard-demo.png"), quality=95)
    print("saved: dashboard-demo.png")


def make_relationships_demo():
    """关系图谱页：圆形布局节点 + 边 + 关系对排行"""
    width, height = 1200, 820
    img = Image.new("RGB", (width, height), GRAY_50)
    draw = ImageDraw.Draw(img, "RGBA")
    _draw_navbar(draw, width)
    y = _draw_header(draw, 48, 88, "关系图谱",
                     "基于共同聊天出现的发送者关系网络")

    # 概览三卡
    card_w = (width - 96 - 2 * 16) / 3
    _draw_stat_card(draw, 48, y, card_w, 80, "发送者总数", "24", BLUE_600)
    _draw_stat_card(draw, 48 + (card_w + 16), y, card_w, 80, "群聊数量（多人）", "7", EMERALD_500)
    _draw_stat_card(draw, 48 + (card_w + 16) * 2, y, card_w, 80, "关系对数量", "31", PURPLE_500)
    y += 80 + 24

    # 左：关系网络图（圆布局）
    graph_w = (width - 96 - 24) * 3 / 5
    graph_h = 480
    _rounded_rect(draw, [48, y, 48 + graph_w, y + graph_h], 8, WHITE)
    f_title = _font(17, bold=True)
    f_small = _font(11)
    draw.text((64, y + 16), "关系网络图", fill=GRAY_900, font=f_title)
    draw.text((64, y + 40), "节点大小 = 消息量；连线粗细 = 关系强度", fill=GRAY_500, font=f_small)

    # 节点定义（名字, 消息量, 颜色）
    nodes = [
        ("Alice", 320, INDIGO_500),
        ("Bob", 280, BLUE_500),
        ("Carol", 210, EMERALD_500),
        ("David", 175, PURPLE_500),
        ("Eve", 140, ORANGE_500),
        ("Frank", 95, PINK_400),
        ("Grace", 70, "#14b8a6"),
        ("Henry", 55, "#6366f1"),
    ]
    cx = 48 + graph_w / 2
    cy = y + graph_h / 2 + 20
    radius = 160
    n = len(nodes)
    positions = []
    for i, (name, count, color) in enumerate(nodes):
        angle = (2 * math.pi * i) / n - math.pi / 2
        px = cx + radius * math.cos(angle)
        py = cy + radius * math.sin(angle)
        node_r = 12 + (count / 320) * 18
        positions.append((name, count, color, px, py, node_r))

    # 边（按强度连）
    edges = [
        (0, 1, 45), (0, 2, 38), (1, 2, 32), (0, 3, 28),
        (2, 3, 22), (1, 4, 18), (3, 4, 15), (0, 4, 12),
        (4, 5, 10), (2, 6, 8), (5, 7, 6), (3, 5, 5),
    ]
    max_strength = max(s for _, _, s in edges)
    for a, b, s in edges:
        _, _, _, ax, ay, _ = positions[a]
        _, _, _, bx, by, _ = positions[b]
        # 不透明实色 + 明显的粗细梯度（1.5 ~ 6.5）
        line_w = max(1.5, 1.5 + (s / max_strength) * 5.0)
        # 强度越高颜色越深
        alpha_ratio = s / max_strength
        edge_color = _color_to_rgb(f"hsl({235 - alpha_ratio * 15:.0f}, 70%, {62 - alpha_ratio * 18:.0f}%)")
        draw.line([(ax, ay), (bx, by)], fill=edge_color, width=int(round(line_w)))

    # 节点（画在边之上）
    for name, count, color, px, py, node_r in positions:
        draw.ellipse([px - node_r, py - node_r, px + node_r, py + node_r],
                     fill=color, outline=WHITE, width=2)
        label_w = draw.textlength(name, font=f_small)
        draw.text((px - label_w / 2, py + node_r + 4), name, fill=GRAY_700, font=f_small)

    # 右：关系对排行
    rank_x = 48 + graph_w + 24
    rank_w = (width - 96 - 24) * 2 / 5
    _rounded_rect(draw, [rank_x, y, rank_x + rank_w, y + graph_h], 8, WHITE)
    draw.text((rank_x + 16, y + 16), "关系强度排行", fill=GRAY_900, font=f_title)

    pairs = [
        ("Alice", "Bob", 45, BLUE_500, EMERALD_500),
        ("Alice", "Carol", 38, BLUE_500, PURPLE_500),
        ("Bob", "Carol", 32, EMERALD_500, PURPLE_500),
        ("Alice", "David", 28, BLUE_500, ORANGE_500),
        ("Carol", "David", 22, PURPLE_500, ORANGE_500),
        ("Bob", "Eve", 18, EMERALD_500, PINK_400),
    ]
    max_s = max(s for _, _, s, _, _ in pairs)
    item_y = y + 56
    for a, b, s, ca, cb in pairs:
        # 名字
        draw.text((rank_x + 16, item_y), a, fill=ca, font=_font(13, bold=True))
        aw = draw.textlength(a, font=_font(13, bold=True))
        draw.text((rank_x + 16 + aw + 4, item_y), "↔", fill=GRAY_400, font=_font(13))
        draw.text((rank_x + 16 + aw + 20, item_y), b, fill=cb, font=_font(13, bold=True))
        # 强度条
        bar_y = item_y + 22
        bar_w = rank_w - 32
        _rounded_rect(draw, [rank_x + 16, bar_y, rank_x + 16 + bar_w, bar_y + 8], 4, GRAY_200)
        fill_w = bar_w * s / max_s
        _rounded_rect(draw, [rank_x + 16, bar_y, rank_x + 16 + fill_w, bar_y + 8], 4, INDIGO_500)
        # 元数据
        meta = f"强度 {s}"
        draw.text((rank_x + 16, bar_y + 12), meta, fill=GRAY_500, font=_font(10))
        item_y += 56

    img.save(os.path.join(OUTPUT_DIR, "relationships-demo.png"), quality=95)
    print("saved: relationships-demo.png")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    make_dashboard_demo()
    make_relationships_demo()
    print("done")
