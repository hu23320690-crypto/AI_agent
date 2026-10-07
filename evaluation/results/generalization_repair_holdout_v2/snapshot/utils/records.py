"""Read local demonstration records with normalized identifiers."""
import csv
import re
from datetime import date
from utils.config_hander import agent_conf
from utils.path_tool import get_abs_path

def normalize_month(value: str) -> str:
    match = re.fullmatch(r"(\d{4})[-/年](\d{1,2})月?", value.strip())
    if not match:
        raise ValueError("月份请使用 YYYY-MM，例如 2025-08。")
    year, month = map(int, match.groups())
    date(year, month, 1)
    return f"{year:04d}-{month:02d}"

def load_records(path: str | None = None) -> dict:
    records = {}
    path = path or get_abs_path(agent_conf["external_data_path"])
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"用户ID", "特征", "清洁效率", "耗材", "对比", "时间"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("使用记录缺少必要列。")
        for row in reader:
            user_id = row["用户ID"].strip()
            month = normalize_month(row["时间"])
            key = (user_id, month)
            if key in records:
                raise ValueError(f"使用记录重复：{user_id}/{month}")
            records[key] = {
                "特征": row["特征"], "效率": row["清洁效率"],
                "耗材": row["耗材"], "对比": row["对比"],
            }
    return records
