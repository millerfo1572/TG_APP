import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_PATH = os.path.join(BASE_DIR, "target_groups.xlsx")
MY_PATH = os.path.join(BASE_DIR, "my_tg_groups.xlsx")
OUT_PATH = os.path.join(BASE_DIR, "target_groups_compare.xlsx")


def normalize(v):
    """把单元格值统一成可比较的字符串；数字按整数处理"""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int):
        return str(v)
    return str(v).strip()


def load_first_column_ids(path, skip_header=True):
    """读取表格 A 列，返回 id 集合（跳过表头）"""
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    ids = set()
    for i, row in enumerate(ws.iter_rows(min_col=1, max_col=1, values_only=True), start=1):
        if skip_header and i == 1:
            continue
        v = row[0]
        if v is None:
            continue
        ids.add(normalize(v))
    wb.close()
    return ids


def main():
    if not os.path.exists(TARGET_PATH):
        raise FileNotFoundError(f"未找到目标群组表: {TARGET_PATH}")
    if not os.path.exists(MY_PATH):
        raise FileNotFoundError(f"未找到我的群组表: {MY_PATH}")

    my_ids = load_first_column_ids(MY_PATH)
    print(f"📋 我的群组表 A 列去重后共 {len(my_ids)} 个 ID")

    # 以 target_groups.xlsx 为基准，加载进来修改
    wb = load_workbook(TARGET_PATH)
    ws = wb.active

    # E 列表头
    ws.cell(row=1, column=5, value="是否已在群组")

    red_fill = PatternFill("solid", fgColor="FFC7CE")  # 红底
    joined = 0
    not_joined = 0

    for r in range(2, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if v is None:
            continue
        tid = normalize(v)
        cell_e = ws.cell(row=r, column=5)
        if tid in my_ids:
            cell_e.value = "已加入"
            joined += 1
        else:
            cell_e.value = "未加入"
            cell_e.fill = red_fill
            not_joined += 1

    wb.save(OUT_PATH)
    print(f"✅ 比较完成：已加入 {joined} 个，未加入 {not_joined} 个")
    print(f"📄 结果已导出：{OUT_PATH}（未加入行已标红底）")


if __name__ == "__main__":
    main()
