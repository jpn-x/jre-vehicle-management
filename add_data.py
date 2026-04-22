#!/usr/bin/env python3
"""
JRE車両売買管理システム - データ追加スクリプト
使い方:
  python add_data.py vehicle    # 新規車両追加
  python add_data.py settle     # 精算データ追加
  python add_data.py status     # ステータス変更
  python add_data.py show       # 現在データ表示
"""

import json
import sys
from datetime import date
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "transactions.json"

STATUS_MAP = {
    "1": "in_stock",
    "2": "sold_pending",
    "3": "principal_returned",
    "4": "settled",
}
STATUS_LABEL = {
    "in_stock": "在庫",
    "sold_pending": "売却済・入金待ち",
    "principal_returned": "元金回収済・利益精算待ち",
    "settled": "精算完了",
}


def load():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ data/transactions.json を更新しました")


def ask(prompt, default=None):
    hint = f" [{default}]" if default else ""
    val = input(f"  {prompt}{hint}: ").strip()
    return val if val else default


def ask_int(prompt, default=None):
    val = ask(prompt, default)
    return int(val) if val else None


def ask_date(prompt):
    while True:
        val = ask(prompt + " (YYYY-MM-DD または空=未定)")
        if not val:
            return None
        try:
            date.fromisoformat(val)
            return val
        except ValueError:
            print("  ❌ 日付の形式が正しくありません (例: 2026-04-23)")


def show(data):
    print("\n=== 現在の取引データ ===")
    print(f"{'No':<4} {'ステータス':<18} {'車種':<22} {'仕入日':<12} {'仕入価格':>10} {'利益JRE':>10}")
    print("-" * 82)
    for v in data["vehicles"]:
        label = STATUS_LABEL.get(v["status"], v["status"])
        profit = f"¥{v['jre_share']:,}" if v["jre_share"] else "—"
        print(f"{v['no']:<4} {label:<18} {v['name']:<22} {(v['purchase_date'] or ''):<12} ¥{v['purchase_price']:>8,} {profit:>10}")
    total_jre = sum(s["jre_distribution"] for s in data["settlements"])
    print("-" * 82)
    print(f"  JRE確定利益累計: ¥{total_jre:,}  |  車両計: {len(data['vehicles'])}台")


def add_vehicle(data):
    print("\n=== 新規車両追加 ===")
    vehicles = data["vehicles"]
    new_no = max(v["no"] for v in vehicles) + 1
    new_id = f"V{new_no:03d}"

    v = {
        "id": new_id,
        "no": new_no,
        "name": ask("車種名 (例: ヴェルファイアH25)"),
        "year": ask("年式 (例: H25)"),
        "color": ask("カラー"),
        "mileage": ask_int("走行距離(km)"),
        "purchase_date": ask_date("仕入日"),
        "purchase_price": ask_int("仕入価格(円)"),
        "expenses": None,
        "total_cost": None,
        "sale_date": None,
        "sale_price": None,
        "profit": None,
        "jre_share": None,
        "principal_returned_date": None,
        "settlement_date": None,
        "status": "in_stock",
        "settlement_id": None,
        "notes": ask("備考 (空=なし)") or "",
    }
    purchase_price = v["purchase_price"] or 0
    v["total_cost"] = purchase_price
    v["expenses"] = None

    print(f"\n  登録内容: [{new_id}] {v['name']} ({v['year']}) ¥{purchase_price:,}")
    if ask("登録しますか? (y/n)", "y").lower() == "y":
        vehicles.append(v)
        data["meta"]["last_updated"] = str(date.today())
        save(data)


def update_status(data):
    show(data)
    print("\n=== ステータス変更 ===")
    no = ask_int("変更する車両番号 (No)")
    v = next((x for x in data["vehicles"] if x["no"] == no), None)
    if not v:
        print(f"  ❌ No.{no} が見つかりません")
        return

    print(f"\n  対象: {v['name']} ({v['year']}) - 現在: {STATUS_LABEL.get(v['status'])}")
    print("  新しいステータス:")
    for k, lbl in STATUS_LABEL.items():
        num = next(n for n, s in STATUS_MAP.items() if s == k)
        print(f"    {num}: {lbl}")
    new_status = STATUS_MAP.get(ask("番号を選択"))
    if not new_status:
        print("  ❌ 無効な選択です")
        return

    v["status"] = new_status

    if new_status in ("sold_pending", "principal_returned", "settled"):
        sale_price = ask_int("販売価格(円) (確定していれば)")
        if sale_price:
            v["sale_price"] = sale_price
            v["sale_date"] = ask_date("売却日")
            expenses = ask_int("諸経費(円) (確定していれば)")
            if expenses:
                v["expenses"] = expenses
                v["total_cost"] = v["purchase_price"] + expenses
                v["profit"] = sale_price - v["total_cost"]
                v["jre_share"] = round(v["profit"] * 0.4)
                print(f"  → 利益: ¥{v['profit']:,}  JRE分配: ¥{v['jre_share']:,}")

    if new_status in ("principal_returned", "settled"):
        v["principal_returned_date"] = ask_date("元金返金日")

    if new_status == "settled":
        v["settlement_date"] = ask_date("利益精算日")
        if v["jre_share"]:
            sid = f"S{len(data['settlements'])+1:03d}"
            data["settlements"].append({
                "id": sid,
                "date": v["settlement_date"],
                "label": f"精算 {v['name']}",
                "vehicles": [v["id"]],
                "principal": v["purchase_price"],
                "gross_profit": v["profit"],
                "jre_distribution": v["jre_share"],
                "confirmed": True,
            })
            v["settlement_id"] = sid

    data["meta"]["last_updated"] = str(date.today())
    save(data)


def add_settlement(data):
    print("\n=== 精算データ一括追加 ===")
    print("（複数台まとめて精算する場合）")
    label = ask("精算ラベル (例: 第4回精算（2台）)")
    settle_date = ask_date("精算日")

    show(data)
    nos = ask("対象車両番号 (カンマ区切り, 例: 3,5)")
    nos = [int(x.strip()) for x in nos.split(",")]
    vs = [v for v in data["vehicles"] if v["no"] in nos]
    if not vs:
        print("  ❌ 対象車両が見つかりません")
        return

    total_principal = 0
    total_profit = 0
    total_jre = 0
    vids = []

    for v in vs:
        print(f"\n  --- {v['name']} ({v['year']}) ---")
        sale_price = ask_int("販売価格(円)")
        expenses = ask_int("諸経費(円)")
        profit = sale_price - v["purchase_price"] - expenses
        jre_share = round(profit * 0.4)
        print(f"  利益: ¥{profit:,}  JRE分配: ¥{jre_share:,}")

        v.update({
            "sale_price": sale_price,
            "expenses": expenses,
            "total_cost": v["purchase_price"] + expenses,
            "profit": profit,
            "jre_share": jre_share,
            "sale_date": ask_date("売却日"),
            "principal_returned_date": settle_date,
            "settlement_date": settle_date,
            "status": "settled",
        })
        total_principal += v["purchase_price"]
        total_profit += profit
        total_jre += jre_share
        vids.append(v["id"])

    sid = f"S{len(data['settlements'])+1:03d}"
    data["settlements"].append({
        "id": sid,
        "date": settle_date,
        "label": label,
        "vehicles": vids,
        "principal": total_principal,
        "gross_profit": total_profit,
        "jre_distribution": total_jre,
        "confirmed": True,
    })
    for v in vs:
        v["settlement_id"] = sid

    print(f"\n  精算合計: 元金¥{total_principal:,} / 粗利¥{total_profit:,} / JRE受取¥{total_jre:,}")
    if ask("登録しますか? (y/n)", "y").lower() == "y":
        data["meta"]["last_updated"] = str(date.today())
        save(data)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    data = load()

    if cmd == "show":
        show(data)
    elif cmd == "vehicle":
        add_vehicle(data)
    elif cmd == "status":
        update_status(data)
    elif cmd == "settle":
        add_settlement(data)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
