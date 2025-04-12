from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import mysql.connector
from mysql.connector import Error
from typing import List, Optional
from datetime import datetime

app = FastAPI(title="Restaurant Ordering System", version="1.0")

# MySQL 連線配置
db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "restaurant_db",
    "raise_on_warnings": True
}

# Pydantic 模型
class OrderItem(BaseModel):
    item_id: int
    quantity: int
    notes: Optional[str] = None

class OrderCreate(BaseModel):
    customer_id: int
    items: List[OrderItem]

class OrderUpdate(BaseModel):
    status: str
    staff_id: Optional[int] = None

# 資料庫連線函數
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        raise HTTPException(status_code=500, detail=f"資料庫連線失敗: {str(e)}")

# 取得菜單（支援分類過濾）
@app.get("/menu", response_model=List[dict])
async def get_menu(category: Optional[str] = Query(None)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if category:
        cursor.execute("SELECT * FROM MenuItems WHERE category = %s", (category,))
    else:
        cursor.execute("SELECT * FROM MenuItems")
    menu = cursor.fetchall()
    cursor.close()
    conn.close()
    return menu

# 新增訂單
@app.post("/orders", response_model=dict)
async def create_order(order: OrderCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Orders (customer_id, order_time, status) VALUES (%s, %s, %s)",
            (order.customer_id, datetime.now(), "製作中")
        )
        order_id = cursor.lastrowid
        
        for item in order.items:
            cursor.execute(
                "INSERT INTO OrderItems (order_id, item_id, quantity, notes) VALUES (%s, %s, %s, %s)",
                (order_id, item.item_id, item.quantity, item.notes)
            )
        
        conn.commit()
        return {"order_id": order_id}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"訂單建立失敗: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# 更新訂單狀態
@app.put("/orders/{order_id}", response_model=dict)
async def update_order(order_id: int, update: OrderUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE Orders SET status = %s, staff_id = %s WHERE order_id = %s",
            (update.status, update.staff_id, order_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="訂單不存在")
        conn.commit()
        return {"message": "狀態更新成功"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# 查詢單筆訂單
@app.get("/orders/{order_id}", response_model=dict)
async def get_order(order_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="訂單不存在")
        
        cursor.execute(
            "SELECT oi.*, mi.name, mi.price FROM OrderItems oi JOIN MenuItems mi ON oi.item_id = mi.item_id WHERE oi.order_id = %s",
            (order_id,)
        )
        items = cursor.fetchall()
        return {"order": order, "items": items}
    finally:
        cursor.close()
        conn.close()

# 取得訂單列表（支援狀態過濾）
@app.get("/orders", response_model=List[dict])
async def get_orders(status: Optional[str] = Query(None)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if status:
        cursor.execute("SELECT * FROM Orders WHERE status = %s", (status,))
    else:
        cursor.execute("SELECT * FROM Orders")
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders

# 熱門餐點排行
@app.get("/analytics/popular-items", response_model=List[dict])
async def get_popular_items():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.name, m.category, SUM(o.quantity) AS total_quantity
        FROM OrderItems o
        JOIN MenuItems m ON o.item_id = m.item_id
        GROUP BY m.name, m.category
        ORDER BY total_quantity DESC
        LIMIT 5
    """)
    popular_items = cursor.fetchall()
    cursor.close()
    conn.close()
    return popular_items