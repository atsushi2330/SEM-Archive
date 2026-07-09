"""閲覧・取込タブ共通のフォルダ表カラム定義。"""

COL_PATH = 0
COL_SUBSTRATE = 1
COL_LOT_NAME = 2
COL_LOT_ID = 3
COL_SLOT = 4
COL_PROCESS = 5
COL_CONDITION = 6
COL_MEMO = 7

HEADERS = ["パス", "下地", "Lot Name", "Lot ID", "Slot", "工程", "条件", "メモ"]
FIELD_BY_COL = {
    COL_SUBSTRATE: "substrate",
    COL_LOT_NAME: "lot_name",
    COL_LOT_ID: "lot_id",
    COL_SLOT: "slot_id",
    COL_PROCESS: "process",
    COL_CONDITION: "condition",
    COL_MEMO: "memo",
}
