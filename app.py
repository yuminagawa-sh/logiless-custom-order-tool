import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import yaml
import os
import re

st.set_page_config(page_title="カスタムオーダー抽出ツール", layout="wide")
st.title("📦 ロジレス注文データ - カスタムオーダー抽出")

st.markdown("""
このツールでは、ロジレスから出力された注文CSVファイルをアップロードし、
楽天・Amazon・Yahooなどのカスタムオーダー製作内容を抽出します。
""")

# 設定ファイルの読み込み
def load_yaml(path):
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

config = load_yaml("config.yaml")
shop_settings = config.get("店舗定義", {})

# セット商品マスタの読み込み
def load_set_items(path="set_items.yaml"):
    return set(load_yaml(path).get("セット商品コード一覧", []))

SET_ITEMS = load_set_items()

uploaded_file = st.file_uploader("CSVファイルをアップロードしてください（Shift_JIS形式）", type="csv")

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, encoding="cp932")

        def extract_custom_order(row):
            for shop, rule in shop_settings.items():
                if rule["キーワード"] in row["店舗名"]:
                    return row.get(rule["カスタムオーダー列"], "")
            return ""

        df["製作内容"] = df.apply(extract_custom_order, axis=1)
        df["製作内容"] = df["製作内容"].astype(str).str.strip().replace("nan", "")
        df["数量"] = pd.to_numeric(df["数量"], errors="coerce").fillna(0).astype(int)

        # セット商品のみ対象にフィルタ
        df_set = df[df["ロジレス商品コード"].isin(SET_ITEMS)].copy()

        # 注文ごと（受注コード＋商品コード）にグループ化
        grouped = df_set.groupby(["受注コード", "ロジレス商品コード"], as_index=False)

        rows = []

        for _, group in grouped:
            代表 = group.iloc[0]
            all_notes = "\n".join(group["製作内容"].dropna().unique())

            # 製作内容ブロックを抽出
            def split_blocks(text):
                orders = re.findall(r'(〇\s*\d{10,}.*?)((?=〇\s*\d{10,})|$)', text, flags=re.DOTALL)
                return [block.strip() for block, _ in orders] if orders else [text.strip()] if text.strip() else []

            blocks = split_blocks(all_notes)
            quantity_total = group["数量"].sum()

            if len(blocks) == 0:
                rows.append({
                    "受注ID": 代表["受注コード"],
                    "受注日時": 代表["受注日時"],
                    "購入者名": 代表["購入者名1"],
                    "店舗名": 代表["店舗名"],
                    "商品名": 代表["商品名"],
                    "数量": quantity_total,
                    "製作内容": "",
                    "不備フラグ": "⚠️不備あり"
                })
            elif len(blocks) == 1:
                rows.append({
                    "受注ID": 代表["受注コード"],
                    "受注日時": 代表["受注日時"],
                    "購入者名": 代表["購入者名1"],
                    "店舗名": 代表["店舗名"],
                    "商品名": 代表["商品名"],
                    "数量": quantity_total,
                    "製作内容": blocks[0],
                    "不備フラグ": "" if blocks[0] else "⚠️不備あり"
                })
            else:
                for block in blocks:
                    rows.append({
                        "受注ID": 代表["受注コード"],
                        "受注日時": 代表["受注日時"],
                        "購入者名": 代表["購入者名1"],
                        "店舗名": 代表["店舗名"],
                        "商品名": 代表["商品名"],
                        "数量": 1,
                        "製作内容": block,
                        "不備フラグ": "" if block else "⚠️不備あり"
                    })

        summary = pd.DataFrame(rows)

        st.success("✅ 抽出が完了しました！")
        st.dataframe(summary, use_container_width=True)

        csv_output = summary.copy()
        csv_output["不備フラグ"] = csv_output["不備フラグ"].str.replace("⚠️", "", regex=False)
        csv = csv_output.to_csv(index=False, encoding="cp932", errors="replace")
        b = BytesIO()
        b.write(csv.encode("cp932", errors="replace"))
        b.seek(0)

        now = datetime.now().strftime("%Y%m%d%H%M")
        filename = f"custom_order_summary_{now}.csv"

        st.download_button(
            label="📥 加工済みCSVをダウンロード",
            data=b,
            file_name=filename,
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ エラーが発生しました：{e}")