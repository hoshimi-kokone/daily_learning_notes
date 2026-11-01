# Python 操作 MySQL 系统笔记

> 主线：驱动 -> DB-API -> 事务 -> 连接池 -> ORM -> 异步
> 版本：PyMySQL 1.1+、mysqlclient 2.2+、SQLAlchemy 2.0+、MySQL 8.0+

## 第 0 章 学习地图

### 0.1、全貌

- **Python 操作** MySQL
  - **1.基础层：驱动**
    - PyMySQL (纯 Python，最常用)
    - mysqlclient (C扩展，最快，Django 默认)
    - mysql-connector-python (Oracle 官方)
  - **2.协议层：DB-API-2.0**
    - connect / cursor / execute / fetch / commit
    - 参数风格 `%s`
    - 游标类型 (缓冲 / 流式 / 字典)
  - **3.事务层**
    - autocommit、BEGIN/COMMIT/ROLLBACK
    - 四种隔离级别
    - 行锁、死锁、重试
  - **4.资源层**
    - 连接池：DBUtils / SQLAlchemy Pool
    - pool_size / max_overflow / pool_recycle / pool_pre_ping
  - **5.抽象层**
    - SQLAlchemy Core (SQL 构造)
    - SQLAlchemy ORM (对象映射)
    - 异步：aiomysql / asyncmy
  - **6.工程层**
    - 批量写入、分页、upsert
    - 字符集 utf8mb4、时区、类型映射
    - 错误码、重试、监控

### 0.2、三条主线

| 主线 | 核心问题 | 对应章节 |
|---|---|---|
| **怎么连** | 用哪个驱动、怎么管连接 | 第 1、6 章 |
| **怎么查** | 参数化、游标、事务 | 第 3-5 章 |
| **怎么写得好** | 批量、ORM、异步、避坑 | 第 7-11 章 |

### 0.3、一句话

> **驱动负责“说协议”，DB-API 负责“统一接口”，连接池负责“复用”，ORM 负责“少写 SQL”。** 生产代码：**连接池 + 参数化 + 显式事务 + 上下文管理器** ，四件套缺一不可。

## 第 1 章 全景：四层选型

### 1.1、四层结构

```text
你的代码
   │
   ├─ ORM 层        SQLAlchemy / Django ORM / Peewee
   │                   ↓ 生成 SQL
   ├─ 连接池层       SQLAlchemy Pool / DBUtils.PooledDB
   │                   ↓ 借还连接
   ├─ DB-API 层      PEP 249 统一接口（cursor/execute/commit）
   │                   ↓
   └─ 驱动层         PyMySQL / mysqlclient / mysql-connector
                       ↓ MySQL 协议（TCP 3306）
                    MySQL Server
```

### 1.2、驱动对比 (选型第一问)

| 驱动 | 实现 | 安装 | 速度 | 维护 | 适用 |
|---|---|---|---|---|---|
| **PyMySQL** | 纯 Python | `pip install pymysql` | 中 | 活跃 | **默认选择、跨平台** |
| **mysqlclient** | C 扩展 (MySQLdb) | 需要编译环境 | **快** | 活跃 | 追求性能、Django 默认 |
| **mysql-connector-python** | Oracle 官方纯 Python | `pip install mysql-connector-python` | 中 | 官方 | 需要 X DecAPI、官方支持 |
| **asyncmy** | Cython | `pip install asyncmy` | 快 | 活跃 | **异步首选** |
| **aiomysql** | 纯 Python (基于 PyMySQL) | `pip install aiomysql` | 中 | 较慢 | 异步、安装简单 |

```python
pip install pymysql            # 最省事
pip install mysqlclient         # 最快，Windows 有 wheel
pip install sqlalchemy          # ORM
pip install aiomysql asyncmy    # 异步
```

> **Windows 上 mysqlclient 装不上**：多半缺 VC++ Build Tools。可直接用 PyMySQL，或预编译 wheel。

### 1.3、抽象层级选择

| 场景 | 推荐 |
|---|---|
| 写脚本、临时取数 | PyMySQL 裸写 |
| Web 服务 (FastAPI / Flask) | SQLAlchemy Core/ORM + 连接池 |
| Django 项目 | Django ORM (底层 mysqlclient) |
| 高并发异步服务 | SQLAlchemy async + asyncmy |
| 数据分析 | `pandas.read_sql` + SQLAlchemy engine` |
| 极致性能的批量导入 | `LOAD DATA LOCAL INFILE` |

### 1.4、Django 的特殊性

Django **不需要你手写 DB-API**，只需要装驱动：

```python
# settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "demo",
        "USER": "app",
        "PASSWORD": "***",
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {"charset": "utf8mb4"},
        "CONN_MAX_AGE": 60,          # 连接复用
    }
}
```

> Django 的 MySQL 后端 **只支持 mysqlclient (`MySQLdb`)** 。PyMySQL 需要打补丁 (不推荐用于生产)。

### 本章要点

1. 驱动 = 协议实现；DB-API = 统一接口；ORM = 抽象。
2. 新手直接用 **PyMySQL**；要性能用 **mysqlclient**；要异步用 **asyncmy**。
3. Django 只认 mysqlclient。

## 第 2 章 五分钟上手

### 2.1、建库建表

```sql
CREATE DATABASE IF NOT EXISTS demo
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE demo;

CREATE TABLE users (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(50)  NOT NULL,
    email      VARCHAR(120) NOT NULL UNIQUE,
    age        TINYINT UNSIGNED DEFAULT NULL,
    balance    DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_name (name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
```

### 2.2、最小可运行脚本

```python
import pymysql

conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="app",
    password="secret",
    database="demo",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False,
    connect_timeout=5,
)

try:
    with conn.cursor() as cur:
        # 写
        cur.execute(
            "INSERT INTO users (name, email, age) VALUES (%s, %s, %s)",
            ("Alice", "alice@example.com", 20),
        )
        print("新 id:", cur.lastrowid, "影响行数:", cur.rowcount)
    conn.commit()

    with conn.cursor() as cur:
        # 读
        cur.execute("SELECT id, name, age FROM users WHERE name = %s", ("Alice",))
        print(cur.fetchone())          # {'id': 1, 'name': 'Alice', 'age': 20}
finally:
    conn.close()
```

> **三个必须记住的点**：
> 1. 占位符是 `%s` ，**不管什么类型** 都用 `%s` (不是 `?` ，不是 `%d`)。
> 2. 默认 `autocommit=False` ，**写完必须** `commit()`。
> 3. 连接用完必须 `close()` (池化后是“归还”)。

## 第 3 章 DB-API 2.0 基础

Python 的数据库接口遵循 **PEP 249 (DB-API 2.0)** ，所以 PyMySQL、mysqlclient、sqlite3、psycopg2 的用法高度一致 —— 换库时主要改 `connect()` 的参数。

### 3.1、标准流程

```text
connect() → cursor() → execute() → fetch*() → commit()/rollback() → close()
```

### 3.2、Connection 常用方法

| 方法 | 说明 |
|---|---|
| `conn.cursor()` | 创建游标 |
| `conn.commit()` | 提交事务 |
| `conn.rollback()` | 回滚事务 |
| `conn.close()` | 关闭连接 |
| `conn.autocommit(bool)` | 设置自动提交 |
| `conn.begin()` | 显示开启事务 (PyMySQL) |
| `conn.ping(reconnect=True)` | 心跳/重连 (PyMySQL) |
| `conn.open` / `conn.closed` | 状态 |

### 3.3、Cursor 常用方法

| 方法 / 属性 | 说明 |
|---|---|
| `cur.execute(sql, params)` | 执行一条，返回影响行数 |
| `cur.executemany(sql, seq)` | 批量执行 | 
| `cur.fetchone()` | 取一行 (`None` 表示没了) | 
| `cur.fetchmany(n)` | 取 n 行 |
| `cur.fetchall()` | 取全部 (大结果集会爆内存) |
| `cur.rowcount` | 影响行数 (SELECT 时依赖驱动) |
| `cur.lastrowid` | 最后插入的自增 ID |
| `cur.description` | 列元信息 (列名、类型) |
| `cur.close()` | 关闭游标 |

### 3.4、四种游标 (性能关键)

| 游标 | **PyMySQL** | 行为 | 用途 |
|---|---|---|---|
| 默认 | `Cursor` | **结果全部拉进内存** | 小结果集 |
| 字典 | `DictCursor` | 返回 `dict` | 可读性好，最常用 |
| 流式 | `SSCursor` | 逐行从服务器读 | 百万行导出 | 
| 流式字典 | `SSDictCursor` | 同上 + dict | 大结果集 |

```python
import pymysql

# 方式一：连接级默认
conn = pymysql.connect(..., cursorclass=pymysql.cursors.DictCursor)

# 方式二：单独指定
with conn.cursor(pymysql.cursors.SSCursor) as cur:
    cur.execute("SELECT * FROM huge_table")
    for row in cur:                 # 逐行，内存友好
        process(row)
```

> **流式游标限制**：必须把结果读完 (或 `close()`) 才能在同一连接上发下一条 SQL，否则报 `Commands out of sync` 。

### 3.5、上下文管理器

```python
# 游标：自动 close（不 commit）
with conn.cursor() as cur:
    cur.execute(...)

# 连接：驱动差异大，别依赖！
with pymysql.connect(...) as conn:      # PyMySQL: 成功提交/异常回滚，但不关闭
    ...
```

> `with connection` 在 **PyMySQL** 是“提交或回滚”，在 **mysqlclient**  里 `with conn as cursor` 返回的是游标。**语义不统一，生产代码请显式写** `try/except/finally` ，或直接用 SQLAlchemy 的 `Session` 。

### 3.6、推荐写法 (显式服务)

```python
def transfer(conn, from_id: int, to_id: int, amount: Decimal) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s",
                        (amount, from_id))
            if cur.rowcount != 1:
                raise ValueError("扣款失败")
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                        (amount, to_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

### 本章要点

1. 流程固定：连接 -> 游标 -> 执行 -> 取数 -> 提交 -> 关闭。
2. `%s` 是唯一占位符。
3. 大结果集用 `SSCursor` ，别用 `fetchall()` 。
4. `with connection` 语义各驱动不同，别依赖。

## 第 4 章 参数化查询与 SQL 注入

这是 **最重要的一章**，写错就是安全事故。

### 4.1、错误示范 (三种都会被注入)

```python
name = "x'; DROP TABLE users; --"

# ❌ 拼接
cur.execute("SELECT * FROM users WHERE name = '" + name + "'")

# ❌ f-string
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")

# ❌ % 格式化
cur.execute("SELECT * FROM users WHERE name = '%s'" % name)
```

### 4.2、正确做法

```python
# ✅ 占位符 + 参数元组
cur.execute("SELECT * FROM users WHERE name = %s", (name,))
```

驱动会把参数 **单独走协议传给服务器** (预处理/转义)，SQL 结构不会被污染。

### 4.3、占位符规则

| 类型 | 写法 | 说明 |
|---|---|---|
| 位置参数 | `%s` | 元组或列表 |
| 命名参数 | `%(name)s` | 字典 | 
| 单值 | `(value,)` | **必须带逗号**，否则是字符串 |
| 数字/日期 | 也用 `%s` | 驱动负责转换 |
| `LIKE` | `LIKE %s` + `f"%{kw}%"` | 通配符放在 **参数里**，不加引号 |
| `IN` | 动态占位符 | 见下 |

```python
# 单值陷阱
cur.execute("SELECT * FROM users WHERE id = %s", (1,))    # ✅
cur.execute("SELECT * FROM users WHERE id = %s", 1)       # ❌ TypeError
```

```python
# 命名参数
cur.execute(
    "SELECT * FROM users WHERE age > %(age)s AND name LIKE %(kw)s",
    {"age": 18, "kw": "%a%"},
)
```

```python
# LIKE：不要把 % 写进 SQL 字符串
cur.execute("SELECT * FROM users WHERE name LIKE %s", (f"%{kw}%",))   # ✅
cur.execute("SELECT * FROM users WHERE name LIKE '%%%s%%'", (kw,))     # ⚠️ 可读性差
```

```python
# IN：占位符个数要动态生成（此处 f-string 只拼 %s，安全）
ids = [1, 2, 3]
ph = ",".join(["%s"] * len(ids))
cur.execute(f"SELECT * FROM users WHERE id IN ({ph})", ids)
```

### 4.4、不能参数化的东西：表名、列名、排序方向

SQL 的参数化只覆盖 **值**，不覆盖 **标识符**。用白名单：

```python
ALLOWED_COLUMNS = {"id", "name", "created_at"}
ALLOWED_ORDERS = {"ASC", "DESC"}

col = input_col if input_col in ALLOWED_COLUMNS else "id"
order = input_order.upper() if input_order.upper() in ALLOWED_ORDERS else "ASC"

cur.execute(f"SELECT * FROM users ORDER BY {col} {order} LIMIT %s", (10,))
```

> 这里用 f-string 是安全的，因为 `col` / `order` 来自 **白名单**，不是用户原文。

### 4.5、其他安全要点

| 风险 | 防范 |
|---|---|
| 多语句注入 | 不要开 `client_flag=MULTI_STATEMENTS` |
| 明文密码 | 用环境变量 / 密钥管理；别写进代码和日志 |
| 权限过大 | 应用账号只给 DML + 必要 DDL，禁止 `DROP` / `GRANT` |
| 报错泄露 | 生产环境不把 SQL 原文返回给前端 |
| 慢查询拖垮 | 设 `max_execution_time` (8.0)、连接超时 |

### 本章要点

1. **永远用占位符**，永远不要拼字符串
2. `%s` 对数字、字符串、日期一视同仁
3. `IN` 要动态生成占位符；表名列名走白名单。
4. 参数化保护“值”，不保护“结构”

## 第 5 章 事务、隔离级别与锁

### 5.1、autocommit

| 设置 | 行为 |
|---|---|
| `autocommit=False` (默认) | 必须 `commit()`，否则连接关闭时回滚 |
| `autocommit=True` | 每条语句自动提交，**无法回滚** |

```python
conn = pymysql.connect(..., autocommit=False)   # 推荐
conn.autocommit(True)                            # 需要时切换
```

> **写操作后忘记 `commit()` 是最常见的“数据没进去”的原因：程序没报错，但连接关闭时事务被回滚了。

### 5.2、显示事务模板

```python
try:
    conn.begin()                       # 可选，autocommit=False 时隐式开启
    with conn.cursor() as cur:
        cur.execute(...)
        cur.execute(...)
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

### 5.3、四种隔离级别

| 级别 | 脏读 | 不可重复读 | 幻读 | MySQL默认 |
|---|---|---|---|---|
| `READ UNCOMMITTED` | 会 可能 | 会 | 会 |  |
| `READ COMMITTED` | 不会 | 会 | 会 |  |
| `REPEATABLE READ` | 不会 | 不会 | 会 部分 (间隙锁缓解) | 默认 |
| `SERIALIZABLE` | 不会 | 不会 | 不会 |  |

```sql
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

> **MySQL 的 RR 与标准不同**：通过 MVCC + 间隙锁，很大程度上避免了幻读。这也是很多“MySQL”为什么默认 RR“面试题的答案”。

### 5.4、显示加锁

```sql
-- 排他锁（写锁）：其他人不能读（当前读）也不能写
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;

-- 共享锁（读锁）：其他人可读，不能写
SELECT * FROM accounts WHERE id = 1 FOR SHARE;         -- 8.0
SELECT * FROM accounts WHERE id = 1 LOCK IN SHARE MODE; -- 5.7 写法

-- 跳过已被锁的行（8.0）
SELECT * FROM jobs WHERE status = 'pending' LIMIT 1 FOR UPDATE SKIP LOCKED;
```

> `FOR UPDATE` 是“任务队列”的标准实现：`SKIP LOCKED` 让多个 worker 不互相阻塞。

### 5.5、死锁与重试

MySQL 检测到死锁会 “杀掉其中一个事务”，抛错：

```text
(1213, 'Deadlock found when trying to get lock; try restarting transaction')
```

标准处理是 **重试整个事务** (不是重试单条SQL)：

```python
import time, random
import pymysql

RETRYABLE = {1213, 1205}          # 死锁 / 锁等待超时

def run_in_tx(conn, work, retries=3):
    for attempt in range(retries):
        try:
            with conn.cursor() as cur:
                result = work(cur)
            conn.commit()
            return result
        except pymysql.err.OperationalError as e:
            conn.rollback()
            if e.args[0] in RETRYABLE and attempt < retries - 1:
                time.sleep(0.05 * 2 ** attempt + random.random() * 0.05)
                continue
            raise
```

#### 减少死锁的写法

| 手段 | 说明 |
|---|---|
| **固定加锁顺序** | 按住键升序更新，永远先小后大 |
| **缩短事务** | 事务里不做网络请求、不做文件 IO |
| **一次批量加锁** | `WHERE id IN (...)` 一次性锁，优于逐行 |
| **降低隔离级别** | RC 比 RR 的间隙锁少 |
| **索引** | 没索引会锁全表，死锁概率飙升 |

```python
# ❌ 两个方向同时转账 → 死锁
# 线程A: 1 -> 2；线程B: 2 -> 1

# ✅ 按 id 排序后加锁
ids = sorted([1, 2])
cur.execute("SELECT id, balance FROM accounts WHERE id IN (%s, %s) FOR UPDATE", ids)
```

### 本章要点

1. 默认非自动提交，**必须 commit**
2. MySQL 默认 RR，靠 MVCC + 间隙锁缓解幻读
3. 死锁要 **重试整个事务**，不是重试单条 SQL
4. 固定加锁顺序 + 短事务 + 有索引，是防死锁的三板斧。

## 第 6 章 连接池

### 6.1、为什么必须用池

|  | 每次新建连接 | 连接池 |
|---|---|---|
| 建连耗时 | 10-100ms (TCP + 握手 + 认证) | ~0 |
| 并发能力 | 受 `max_connections` 限制 | 复用，稳定 |
| 连接泄露 | 容易 | 池会回收 |

> **MySQL 建立连接很贵** (尤其开了 SSL)，高频短链接会让数据库 CPU 飙升。

### 6.2、SQLAlchemy 连接池 (推荐)

```python
from sqlalchemy import create_engine

engine = create_engine(
    "mysql+pymysql://app:secret@127.0.0.1:3306/demo?charset=utf8mb4",
    pool_size=5,            # 常驻连接数
    max_overflow=10,        # 峰值可临时多开 10 个
    pool_timeout=30,        # 取连接最多等 30s
    pool_recycle=3600,      # 1 小时回收，防 MySQL 8h 断连
    pool_pre_ping=True,     # 取连接前先 ping，自动剔除失效连接
    echo=False,
)
```

| 参数 | 含义 | 建议 |
|---|---|---|
| `pool_size` | 常驻连接数 | 2-10，别按 CPU 核数拍 |
| `max_overflow` | 峰值额外连接 | `pool_size` 的 1-2 倍 |
| `pool_recycle` | 连接最大存活秒数 | 必须小于 MySQL `wait_timeout` (默认 28800) |
| `pool_pre_ping` | 用前探测 | **生产必开** |
| `pool_timeout` | 取连接超时 | 5-30s |

### 6.3、DBUtils 连接池 (不用 ORM 时)

```python
from dbutils.pooled_db import PooledDB
import pymysql

POOL = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=2,
    maxcached=5,
    blocking=True,          # 池满时阻塞等待
    ping=1,                 # 取连接时 ping（1=每次取都 ping）
    host="127.0.0.1", port=3306, user="app", password="secret",
    database="demo", charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False,
)

conn = POOL.connection()    # 借
try:
    ...
finally:
    conn.close()            # 还（不是真关闭）
```

### 6.4、池到底开多大

```text
连接数 ≈ 并发请求数 / (1 - 等待比例)
经验值： 4~16 之间，按 QPS × 平均耗时 估算
```

> **常见错误**：为了“提高并发”把 `pool_size` 开到 200。结果 MySQL 上下文切换爆炸，QPS 反而下降。
> **正确做法**：先小 (如 5)，压测看 `SHOW PROCESSLIST` 和慢查询，再调。

### 6.5、连接泄露的典型写法

```python
# ❌ 异常时连接没归还
conn = pool.connection()
cur = conn.cursor()
cur.execute(...)

# ✅ 用 try/finally
conn = pool.connection()
try:
    with conn.cursor() as cur:
        cur.execute(...)
finally:
    conn.close()      # 归还
```

### 本章要点

1. 连接池是生产必备，建连比查询还贵
2. `pool_pre_ping=True` + `pool_recycle` 解决 “MySQL server has gone away”。
3. 池不是越大越好，4-16 是常见区间
4. 借出的连接必须在 `finally` 里归还

## 第 7 章 批量操作与性能

### 7.1、三种插入方式

```python
# ① 逐条（最慢，N 次网络往返）
for u in users:
    cur.execute("INSERT INTO users (name, email) VALUES (%s, %s)", (u.name, u.email))

# ② executemany（驱动自动拼多值 INSERT）
cur.executemany("INSERT INTO users (name, email) VALUES (%s, %s)",
                [(u.name, u.email) for u in users])

# ③ 手拼多值（最可控，注意分批）
def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

for batch in chunks(users, 1000):
    sql = "INSERT INTO users (name, email) VALUES " + ",".join(["(%s,%s)"] * len(batch))
    cur.execute(sql, [v for u in batch for v in (u.name, u.email)])
```

| 方式 | 1 万条耗时 (量级) | 说明 |
|---|---|---|
| 逐条 | 数十秒 | N 次往返 |
| `executemany` | 数秒 | 驱动自动批处理 |
| 手拼多值 | 秒级 | 控制批次大小 |
| `LOAD DATA LOCAL INFILE` | **亚秒级** | 大数据导入首选 |

> 手拼时注意 `max_allowed_packet` (默认 64MB)，每批 500-2000行比较稳。

### 7.2、`LOAD DATA LOCAL INFILE`

```python
conn = pymysql.connect(..., local_infile=True)
cur.execute("""
    LOAD DATA LOCAL INFILE %s
    INTO TABLE users
    FIELDS TERMINATED BY ',' ENCLOSED BY '"'
    LINES TERMINATED BY '\\n'
    IGNORE 1 LINES
    (name, email)
""", ("/path/to/users.csv",))
```

> 服务端也要开 `local_infile=1` (`SET GLOBAL local_infile=1)，并且这是 **安全敏感** 功能，生产慎用。

### 7.3、分页：LIMIT OFFSET 的坑

```sql
-- ❌ 深分页：要扫描前 100000 行再丢弃
SELECT * FROM orders ORDER BY id LIMIT 100000, 20;

-- ✅ 游标分页（keyset），始终走索引
SELECT * FROM orders WHERE id > 100000 ORDER BY id LIMIT 20;
```

```python
def page_by_id(conn, last_id: int = 0, size: int = 20):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title FROM orders WHERE id > %s ORDER BY id LIMIT %s",
            (last_id, size),
        )
        return cur.fetchall()
```

| 方案 | 深分页性能 | 能否跳页 | 适用 |
|---|---|---|---|
| `LIMIT offset` | 不好，越翻越慢 | 支持 | 后台管理少量页 |
| keyset | 好，恒定 | 不支持 | 信息流、导出 |

### 7.4、Upsert

```python
INSERT INTO users (id, name, email) VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE name = VALUES(name), email = VALUES(email);
```

> **MySQL 8.0.20+ 推荐用行别名 (VALUES() 已废弃)**
> ```python
> INSERT INTO users (id, name) VALUES (%s, %s) AS new
> ON DUPLICATE KEY UPDATE name = new.name;
> ```

### 7.5、其他性能建议

| 建议 | 说明 |
|---|---|
| 只 SELECT 需要的列 | 减少网络与内存 |
| 用 `EXPLAIN` 看执行计划 | 重点看 `type`、`rows`、`Extra` |
| 避免 `SELECT *` | 尤其有大 `TEXT` / `BLOB` |
| 批量写而非循环写 | 往返次数是关键 |
| 合理索引 | 但别滥建，写放大 |
| 读写分离 | 注意主从延迟 (写完立即读可能读不到) |

### 本章要点

1. 批量写用 `executemany` 或手拼多值，别循环单条。
2. 超大导入用 `LOAD DATA LOCAL INFILE`
3. 深分页用 keyset，别用大 offset
4. `VALUES()` 在 8.0.20 后废弃，用行别名。

## 第 8 章 SQLAlchemy 2.0

### 8.1、两层 API

| 层 | 单位 | 特点 |
|---|---|---|
| **Core** | 表、SQL 表达式 | 接近 SQL，无对象状态 |
| **ORM** | 类、实例、Session | 对象映射、关系、自动flush |

### 8.2、Core：用表达式构造 SQL

```python
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select

engine = create_engine("mysql+pymysql://app:secret@127.0.0.1/demo?charset=utf8mb4")
meta = MetaData()

users = Table(
    "users", meta,
    Column("id", Integer, primary_key=True),
    Column("name", String(50)),
    autoload_with=engine,          # 反射已有表
)

with engine.connect() as conn:
    stmt = select(users.c.id, users.c.name).where(users.c.id > 10).limit(5)
    for row in conn.execute(stmt):
        print(row.id, row.name)
```

### 8.3、ORM：2.0 声明式模型

```python
from sqlalchemy import String, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    posts: Mapped[list["Post"]] = relationship(back_populates="author")

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="posts")
```

> 2.0 的 `Mapped[...]` + `mapped_column()` 是官方推荐写法，取代了 1.x 的 `Column(String(50))` 。

### 8.4、Session 用法

```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# 写
with SessionLocal() as session:
    with session.begin():                 # 自动 commit / rollback
        session.add(User(name="Alice", email="a@x.com"))

# 查
with SessionLocal() as session:
    user = session.get(User, 1)                                   # 主键查
    users = session.scalars(select(User).where(User.id > 10)).all()
    one = session.scalars(select(User).order_by(User.id).limit(1)).first()

# 改
with SessionLocal() as session, session.begin():
    user = session.get(User, 1)
    user.name = "Bob"                     # 脏检查，自动 UPDATE

# 删
with SessionLocal() as session, session.begin():
    session.delete(session.get(User, 1))
```

| 写法 | 说明 |
|---|---|
| `session.execute(select(...)).scalars()` | 2.0 标准 |
| `session.scalars(select(...))` | 简写，推荐 |
| `session.get(Model, pk)` | 主键查询，走 identity map |
| `with session.begin()` | 自动事务边界 |

### 8.5、原生 SQL

```python
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT id, name FROM users WHERE id = :uid"),
        {"uid": 1},
    ).mappings().all()
```

> 2.0 里 **必须** `text()` 包装，否则报 `ArgumentError`。占位符用 `:name` (不是 `%s` )，驱动层会自动转换。

### 8.6、N + 1 问题 (ORM 头号性能杀手)

```python
# ❌ N+1：1 次查用户 + N 次查文章
for user in session.scalars(select(User)).all():
    print(user.posts)          # 每访问一次触发一条 SQL

# ✅ 预加载
from sqlalchemy.orm import selectinload, joinedload

users = session.scalars(
    select(User).options(selectinload(User.posts))
).all()
```

| 加载策略 | SQL 条数 | 适用 |
|---|---|---|
| 默认 (lazy) | 1 + N | 小数据、按需 |
| `selectinload` | 2 | 一对多，推荐 |
| `joinedload` | 1 (JOIN) | 一对一、多对一 |
| `raise` | --- | 强制暴露 N + 1 |

### 8.7、连接池与引擎参数

```python
engine = create_engine(
    "mysql+pymysql://app:secret@127.0.0.1/demo?charset=utf8mb4",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    future=True,          # 2.0 默认，可省略
)
```

> 密码里有 `@`、`/`、`:` 等字符时，要用 `urllib.parse.quote_plus` 编码

```python
from urllib.parse import quote_plus
pwd = quote_plus("p@ss/w:rd")
url = f"mysql+pymysql://app:{pwd}@127.0.0.1/demo?charset=utf8mb4"
```

### 本章要点

1. 2.0 用 `Mapped` + `mapped_column` 定义模型
2. `session.scalars(select(...))` 是查询主入口。
3. 原生 SQL 必须 `text()` 占位符是 `:name` 。
4. N + 1 用 `selectinload` 解决，这是 ORM 最大的坑。

## 第 9 章 异步 MySQL

### 9.1、为什么需要

Web 服务用 `async def` 时，**同步驱动会阻塞事件循环**：

```python
async def bad():
    conn = pymysql.connect(...)      # ❌ 阻塞整个事件循环
```

### 9.2、aiomysql / asyncmy

```python
import asyncio
import aiomysql

async def main():
    pool = await aiomysql.create_pool(
        host="127.0.0.1", port=3306, user="app", password="secret",
        db="demo", charset="utf8mb4", autocommit=True,
        minsize=1, maxsize=10,
    )
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, name FROM users WHERE id = %s", (1,))
                print(await cur.fetchone())

                await cur.executemany(
                    "INSERT INTO users (name, email) VALUES (%s, %s)",
                    [("A", "a@x.com"), ("B", "b@x.com")],
                )
    finally:
        pool.close()
        await pool.wait_closed()

asyncio.run(main())
```

```python
# asyncmy 用法几乎一致，性能更好（Cython 实现）
import asyncmy
pool = await asyncmy.create_pool(...)
```

### SQLAlchemy 异步

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

engine = create_async_engine(
    "mysql+asyncmy://app:secret@127.0.0.1/demo?charset=utf8mb4",
    pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=3600,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_user(user_id: int):
    async with SessionLocal() as session:
        return await session.get(User, user_id)

# 关闭时
await engine.dispose()
```

| 场景 | 方案 |
|---|---|
| 已有同步代码 | `asyncio.to_thread(...)` 包一层，最小改动 |
| 新项目、纯异步 | `SQLAlchemy async` + `asyncmy` |
| 只做简单查询 | `aiomysql` 裸用 |

### 本章要点

1. 异步服务里 **绝不能** 用同步驱动。
2. `aiomysql` 是PyMySQL 的异步版，`asyncmy` 更快
3. SQLAlchemy 异步要用 `create_async_engine` + `async_sessionmaker` 。

## 第 10 章 类型映射、字符集、时区

### 10.1、类型映射 (PyMySQL)

| **MySQL** 类型 | **Python** 类型 | 注意 |
|---|---|---|
| `TINYINT` | `int` | `TINYINT(1)` 也 **不是** bool |
| `INT` / `BIGINT` | `int` | BIGINT UNSIGNED 超范围要注意 |
| `DECIMAL` | `decimal.Decimal` | 金额必须用它，别用 float |
| `FLOAT` / `DOUBLE` | `float` | 精度丢失 |
| `VARCHAR` / `TEXT` | `str` |  |
| `DATETIME` / `TIMESTAMP` | `detetime.datetime` | **naive** (无时区) |
| `DATE` | `datatime.date` |  |
| `TIME` | `datetiem.timedelta` | 不是 `time` |
| `BLOB` | `bytes` | 大对象注意 `max_allowed_packet` |
| `JOSN` | `str` | 需要自己 `json.loads` | 
| `BIT` | `bytes` |  |

### 10.2、字符集：必须 utf8mb4

| 名称 | 字节 | 能存 emoji | 说明 |
|---|---|---|---|
| `utf8` (=utf8nb3) | 最多 3 | 不能 | **MySQL 的历史遗留** |
| `utf8mb4` | 最多 4 | 能 | 唯一正确选择 |

```sql
-- 建库建表都要指定
CREATE DATABASE demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

```python
conn = pymysql.connect(..., charset="utf8mb4")
```

> 报 `1366 Incorrect value: '\xF0\x9F...'` 就是 emoji 存不进去 -> 表还是 utf8mb3。

### 10.3、时区

| 类型 | 存什么 | 时区转换 |
|---|---|---|
| `DATETIME` | 字面值 | 不转换 |
| `TIMESTAMP` | UTC 时间戳 | 按会话时区转换 |

```python
# 统一 UTC 存储，展示时再转
conn = pymysql.connect(..., init_command="SET time_zone='+00:00'")
```

| 建议 | 理由 |
|---|---|
| 数据库统一存 UTC | 避免夏令时 / 跨时区混乱 |
| 用 `TIMESTAMP` 存“时刻”，`DATETIME` 存“记录值” | 语义不同 |
| Python 端统一用 aware datetime | 显式时区，避免 naive |
| 注意 `TIMESTAMP` 2038 问题 | 长期系统用 `DATETIME` |

### 10.4、金额：永远用 DECIMAL

```python
# ❌
price = 19.99          # float 有精度误差
# ✅
from decimal import Decimal
price = Decimal("19.99")
```

### 本章要点

1. 字符集统一 `utf8mb4`
2. `TIME` -> `timedelta`，`JSON` -> `str`，容易踩
3. 金额用 `DECIMAL` / `Decimal`
4. 时间统一 UTC，存 `TIMESTAMP` ，读出来补时区

## 第 11 章 错误码与坑清单

### 11.1、高频错误码

| 错误码 | 含义 | 处理 |
|---|---|---|
| `1045` | Access denied | 查帐号密码 / 权限 |
| `2003` | Can't connect | 服务没起 / 防火墙 / 端口 |
| `2006` | MySQL server has gone away | 连接超时 -> `pool_recycle` |
| `2013` | Lost connection during query | 网络 / 超时 /大查询 |
| `1054` | Unknown column | 字段名错 |
| `1062` | Duplicate entry | 唯一键冲突，改 `INSERT IGNORE` 或 upsert |
| `1205` | Lock wait timeout | 事务太长 -> 缩短 + 重试 |
| `1213` | Deadlock | 固定加锁顺序 + 重试 |
| `1406` | Data too long | 字段长度不够 |
| `1366` | Incorrect string value | 字符集不是 utf8mb4 |
| `1040` | Too many connections | 连接池泄露 / 池太大 |
| `1698` | Access denied for user 'root'@'localhost' | root 用了 auth_socket |
| `2059` | Authentication plugin 'caching_sha2_password' | 装 `crytography` |

```bash
pip install cryptography     # 解决 2059
```

### 11.2、坑清单

| 坑 | 现象 | 解法 |
|---|---|---|
| 忘 `commit()` | 数据没进去 | 显式 commit 或用 `session.begin()` | 
| 拼字符串 SQL | 被注入 | 参数化 |
| `%s` 写成 `%d` | 报错/类型错 | 一律 `%s` |
| 单值参数没逗号 | `TypeError` | `(v,)` |
| `fetchall()` 大表 | OOM | `SSCursor` | 
| 流式游标不读完 | `Commands out of sync` | 读完或 `close()` | 
| `autocommit=True` 又 `rollback` | 回滚无效 | 关自动提交 |
| Django 用 PyMySQL | 报错 | 装 mysqlclient |
| 表 utf8 | emoji 存入失败 | 改 `utf8mb4` | 
| 密码含 `@` | 连接串解析错 | `quote_plus` 编码 | 
| 连接池开太大 | MySQL 拒绝连接 / 变慢 | 调小 + 压测 |
| 长事务 | 锁等待、主从延迟 | 事务里别做网络 IO |
| `SELECT *` 大表 | 慢 + 内存 | 只取需要的列 |

### 11.3、代码审查清单

- 所有 SQL 都是参数化的？
- `commit() / rollback()` 都有？
- 连接在 `finally` 里归还？
- 大结果集用了流式游标？
- 字符集是 `utf8mb4`？
- 金额用 `Decimal` ？
- 连接池有 `pool_pre_ping`？
- 事务里没有外部调用 (HTTP/文件)？

## 第 12 章 实战：完整 DAO 层

```python
"""db.py —— 生产可用的最小 DAO 层"""
from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import pymysql
from dbutils.pooled_db import PooledDB

log = logging.getLogger(__name__)

POOL = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=2,
    maxcached=5,
    blocking=True,
    ping=1,
    host="127.0.0.1",
    port=3306,
    user="app",
    password="secret",
    database="demo",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False,
)

RETRYABLE_ERRORS = {1213, 1205}     # 死锁 / 锁等待超时


@contextmanager
def get_conn() -> Iterator[pymysql.connections.Connection]:
    """借出连接，用完自动归还。"""
    conn = POOL.connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn) -> Iterator[pymysql.cursors.Cursor]:
    """事务上下文：正常提交，异常回滚。"""
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def _with_retry(fn, *args, retries: int = 3, **kwargs) -> Any:
    """死锁自动重试整个事务。"""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except pymysql.err.OperationalError as e:
            if e.args[0] in RETRYABLE_ERRORS and attempt < retries - 1:
                delay = 0.05 * 2 ** attempt + random.random() * 0.05
                log.warning("可重试错误 %s，%.2fs 后重试", e.args[0], delay)
                time.sleep(delay)
                continue
            raise


# ---------------- 业务方法 ----------------

def create_user(name: str, email: str, age: int | None = None) -> int:
    with get_conn() as conn, transaction(conn) as cur:
        cur.execute(
            "INSERT INTO users (name, email, age) VALUES (%s, %s, %s)",
            (name, email, age),
        )
        return cur.lastrowid


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, email, age, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        return cur.fetchone()


def list_users(ids: Sequence[int]) -> list[dict]:
    if not ids:
        return []
    ph = ",".join(["%s"] * len(ids))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id, name FROM users WHERE id IN ({ph})",
            list(ids),
        )
        return list(cur.fetchall())


def batch_insert_users(rows: Sequence[tuple[str, str]], batch_size: int = 500) -> int:
    total = 0
    with get_conn() as conn, transaction(conn) as cur:
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            cur.executemany(
                "INSERT INTO users (name, email) VALUES (%s, %s)",
                chunk,
            )
            total += len(chunk)
    return total


def transfer(from_id: int, to_id: int, amount) -> None:
    """转账：按 id 排序加锁，避免死锁。"""
    def work():
        a, b = sorted((from_id, to_id))
        with get_conn() as conn, transaction(conn) as cur:
            cur.execute(
                "SELECT id, balance FROM accounts WHERE id IN (%s, %s) FOR UPDATE",
                (a, b),
            )
            rows = {r["id"]: r["balance"] for r in cur.fetchall()}
            if rows[from_id] < amount:
                raise ValueError("余额不足")
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s",
                        (amount, from_id))
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                        (amount, to_id))

    _with_retry(work)
```

**使用**

```python
uid = create_user("Alice", "alice@example.com", 20)
print(uid, get_user(uid))
print(list_users([uid]))
```

## 第 13 章 面试高频问答

### Q1：PyMySQL 和 mysqlclient 的区别？

PyMySQL 纯 Python，安装简单、跨平台，速度中等；
mysqlclient 是 C 扩展 (MySQLdb API)，性能更好，但需要编译环境，Django 默认用它。

### Q2：为什么 SQL 要用 `%s` 而不是 f-string ？

参数化查询会把值单独通过协议传递，SQL 结构不会被用户输入改变，从而防注入。拼接则把数据和语法混在一起。

### Q3：`%s` 能用于数字吗？为什么不用 `%d` ？

能。DB-API 的 `%s` 是“参数占位”，类型有驱动处理，不是字符串格式化，所以对数字、日期通用。

### Q4：`executemany` 为什么快？

驱动会把 `INSERT` 改写成多值形式 `VALUES(...),(...),...`，把 N 次往返变成 1 次。

### Q5：`MySQL` 默认隔离级别？会幻读吗？

REPEATABLE READ。标准 RR 允许幻读，但 InnoDB 通过 MVCC (快照读) + 间隙锁 (当前读) 在很大程度上避免了幻读。

### Q6：死锁怎么处理？

捕获 1213，**重试整个事务** (带指数退避)；同时优化：固定加锁顺序、缩短事务、加索引、降低隔离级别。

### Q7：连接池的 `pool_recycle` 为什么必要？

MySQL 默认 `wait_timeout=28800` (8 小时)，空闲连接会被服务器断开，客户端却以为还活着。`pool_recycle` 小于该值可提前回收，配合 `pool_pre_ping` 双保险。

### Q8：大结果集怎么处理？

用流式游标 (`SSCursor` / `SSDictCursor`) 逐行读；或分页 (keyset) ；或 `LOAD DATA` 导出。

### Q9：ORM 的 N + 1 是什么？

查 N 个 主对象后，逐个访问关联对象又发 N 条 SQL。用 `selectinload` / `joinedload` 预加载解决。

### Q10：`utf8` 和 `utf8mb4` 的区别？

MySQL 的 `utf8` 是 `utf8mb3`，最多 3 字节，存不了 emoji 和部分生僻字；`utf8mb4` 才是完整的 UTF-8 。

### Q11：`DATETIME` 和 `TIMESTAMP` 怎么选？

`TIMESTAMP` 按会话时区自动转换、占 4 字节、范围到2038；`DATETIME` 存字面值、占 8 个字节、方位到9999。跨时区用 `TIMESTAMP` ，长期归档用 `DATETIME` 。

### Q12：`FOR UPDATE` 和 `LOCK IN SHARE MODE` 的区别？

前者排他锁 (别人不能读当前读、不能写)，后这共享锁 (别人可读，不能写)。8.0 里后者叫 `FOR SHARE`。

## 第 14 章 速查表

### 14.1、连接

```python
import pymysql

conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="app", password="pwd",
    database="demo", charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False, connect_timeout=5,
    read_timeout=10, write_timeout=10,
)
```

### 14.2、CRUD 模板

```python
# 增
cur.execute("INSERT INTO t (a, b) VALUES (%s, %s)", (1, "x"))
cur.lastrowid

# 删
cur.execute("DELETE FROM t WHERE id = %s", (1,))
cur.rowcount

# 改
cur.execute("UPDATE t SET a = %s WHERE id = %s", (2, 1))

# 查
cur.execute("SELECT * FROM t WHERE id = %s", (1,))
cur.fetchone() / cur.fetchall() / cur.fetchmany(n)
```

### 14.3、常用片段

```python
# 事务
try:
    cur.execute(...); conn.commit()
except Exception:
    conn.rollback(); raise

# 批量
cur.executemany("INSERT INTO t (a,b) VALUES (%s,%s)", rows)

# IN
ph = ",".join(["%s"] * len(ids)); cur.execute(f"... IN ({ph})", ids)

# LIKE
cur.execute("... LIKE %s", (f"%{kw}%",))

# 分页（keyset）
cur.execute("... WHERE id > %s ORDER BY id LIMIT %s", (last_id, size))

# 加锁
cur.execute("SELECT ... WHERE id = %s FOR UPDATE", (1,))

# 流式
with conn.cursor(pymysql.cursors.SSCursor) as cur:
    cur.execute("SELECT ..."); 
    for row in cur: ...
```

### 14.4、SQLAlchemy

```python
engine = create_engine("mysql+pymysql://u:p@h:3306/db?charset=utf8mb4",
                       pool_size=5, max_overflow=10,
                       pool_pre_ping=True, pool_recycle=3600)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

with SessionLocal() as s, s.begin():
    s.add(obj)

with SessionLocal() as s:
    s.scalars(select(User).where(User.id > 10)).all()
    s.execute(text("SELECT 1")).scalar()
```

### 14.5、常用 SQL

```sql
SHOW PROCESSLIST;                              -- 看连接
SHOW VARIABLES LIKE 'wait_timeout';
SHOW VARIABLES LIKE 'max_connections';
SHOW VARIABLES LIKE '%local_infile%';
SHOW TABLE STATUS LIKE 'users';
SHOW INDEX FROM users;
EXPLAIN SELECT ...;                            -- 执行计划
SHOW ENGINE INNODB STATUS;                     -- 最近一次死锁
SELECT @@transaction_isolation;
```

## 第 15 章 学习路线

### 阶段一：能跑通 (1-2天)

- 装 PyMySQL，连上本地库
- 跑通CRUD + `commit`
- 用 `DictCursor` 取字典
- 写一个参数化的登陆查询

### 阶段二：能写对 (1 周)

- 显式事务 + `try / except / finally`
- 批量插入 1 万条，对比逐条
- 用连接池改写上面的代码
- 手写一个死锁重试装饰器

### 阶段三：能写好 (2 周)

- SQLAlchemy 2.0 建模 + 关联查询
- 用 `selectinload` 解决 N + 1 
- keyset 分页
- 用 `EXPLAIN` 优化一条慢查询

### 阶段四：生产化 (持续)

- 异步版 (aiomysql / asyncmy)
- 监控：慢查询日志、连接数、QPS
- 主从读写分离
- 备份与恢复演练
- 容量规划 (连接池大小、`max_connections`)

## 资源

| 类型 | 名称 |
|---|---|
| 官方 | MySQL 8.0 Reference Manual |
| 官方 | PyMySQL 文档 |
| 官方 | SQLAlchemy 2.0 Documentation |
| 标准 | PEP 249 (DB-API 2.0) |
| 书 | 《高性能 MySQL》第 4 版 |
| 工具 | DBeaver / DataGrip / MySQL Workbench |

## 附录：最小可用环境

```bash
docker run -d --name mysql8 \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=demo \
  -e MYSQL_USER=app \
  -e MYSQL_PASSWORD=secret \
  -p 3306:3306 mysql:8.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_0900_ai_ci
```

```bash
pip install pymysql dbutils sqlalchemy cryptography
```