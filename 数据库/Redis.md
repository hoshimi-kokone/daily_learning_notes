# Redis 

## 第一章：Redis 是什么

### 1.1、定位

| 维度 | 说明 |
|---|---|
| 类型 | 内存 key-value 数据库 (NoSQL) |
| 数据模型 | key -> value，value 是结构化数据 |
| 存储 | 内存为主，磁盘做持久化 |
| 协议 | RESP3 (兼容 RESP2) |
| 默认端口 | 6379 |
| 线程模型 | 命令执行单线程，网络 IO 可多线程 |

### 1.2、为什么快 (四个原因)

| 原因 | 说明 |
|---|---|
| **纯内存** | 读写不落盘 | 
| **单线程执行** | 无锁竞争、无上下文切换 |
| **IO 多路复用** | epoll/kqueue 单线程处理海量连接 |
| **高效数据结构** | SDS、listpack、intset、跳表、渐进式 rehash |

### 1.3、单线程模型与推论

```text
客户端连接 ──┐
客户端连接 ──┼── epoll 就绪队列 ──> 事件循环 ──> 执行命令 ──> 写回
客户端连接 ──┘
```

#### 必须记住的推论：

- 一条慢命令会 **阻塞所有客户端**
- `KEYs *`、`FLUSHALL`、大 key 的 `HGETALL`、长 Lua 脚本都是事故源
- 6.0 起 `io-threads 4` 只让 **网络读写** 多线程，命令执行仍是单线程。

```text
io-threads 4              # 网络读写用 4 个线程（4 核以上建议开）
io-threads-do-reads yes   # 读也交给 IO 线程（默认 no）
```

### 1.4、和别的存储对比

|  | Redis | Memcached | MySQL |
|---|---|---|---|
| 存储介质 | 内存 + 持久化 | 纯内存 | 磁盘 |
| 数据结构 | 10 种 | 仅 KV | 关系表 |
| 持久化 | RDB / AOF | 无 | 有 |
| 分布式 | 主从 / 哨兵 / Cluster | 客户端分片 | 主从 / 分片 |
| 典型用途 | 缓存、队列、锁、计数 | 纯缓存 | 主数据 |

> Redis 不是数据库的替代品，它是 **热点数据与临时状态的加速层**。

## 第二章：版本与生态

### 2.1、版本演进

| 版本 | 关键特征 |
|---|---|
| 3.0 | Cluster 集群 |
| 4.0 | 模块系统、`UNLINK`、混合持久化 |
| 5.0 | Stream | 
| 6.0 | ACL、RESP3、IO 多线程、客户端缓存 |
| 7.0 | Functions、分片 Pub/Sub、multi-part AOF、listpack |
| 7.2 | `WAITAOF`、`CLIENT NO-EVICT` |
| 7.4 | **Hash 字段级 TTL**、`HGETEX` / `HSETEX` / `HGETDEL` |
| 8.0 | **Vector Set**、内置 JSON / Search / TimeSeries / Bloom、AGPLv3 |
| 8.2-8.10 | 向量集与查询引擎增强、性能优化、bug 修复 |

### 2.2、8.x 的四个实质变化

| 变化 | 影响 |
|---|---|
| **内置模块** | 不再需要单独部署 Redis Stack |
| **Vector Set** | 新增第 10 种数据类型 |
| **Hash 字段 TTL** | 一个 Hash 可存多组独立过期数据 |
| **许可证改 AGPLv3** | 商用需做合规评估 |

### 2.3、生态与许可证

| 项 | 说明 |
|---|---|
| 7.4 及之前 | RSALv2 / SSPL 双许可 |
| **8.0 起** | **AGPLv3** |
| 社区 fork | Valkey (Linux 基金会，2024，API 高度兼容) |
| 云厂商 | 阿里云/腾讯云/AWS 的托管 Redis 可能基于不同分支 |

### 2.4、环境自检

#### bash

```bash
# 看服务端版本和运行模式
redis-cli INFO server | grep -E "redis_version|redis_mode|os|arch_bits"

redis-cli MODULE LIST            # 已加载模块（JSON/Search 等）
redis-cli COMMAND COUNT          # 命令总数
redis-cli COMMAND DOCS VADD      # 查某个命令是否存在（不存在会报错）
```

#### python

```python
import redis

r = redis.Redis(decode_responses=True)          # 自动解码，返回 str
info = r.info("server")                          # 服务端信息字典

print(info["redis_version"])                     # → '8.10.3'
print(info["redis_mode"])                        # → 'standalone' 或 'cluster'

# 探测新命令是否可用：不存在时抛 ResponseError
for cmd in ("VADD", "HEXPIRE", "WAITAOF", "FCALL"):
    try:
        r.execute_command("COMMAND", "DOCS", cmd)   # 只查文档，不执行
        print(f"{cmd}: 支持")
    except redis.ResponseError:
        print(f"{cmd}: 不支持")
```

### 本章要点

1. 你的 8.10.3 拥有 7.0 - 8.0 的全部新特性
2. 8.x 最大的变化是**内置模块**、**Vector Set**、**Hash 字段 TTL**
3. 许可证变成 AGPLv3，商用要评估。
4. 用 `COMMAND DOCS` 确认具体命令

## 第三章：核心机制：key、过期、内存

### 3.1、key规范

| 规则 | 示例 |
|---|---|
| 冒号分层 | `user:1001:profile` |
| 控制长度 | `order:2025:10:29:count` |
| 避免单点热点 | 分片 或 hash tag |
| 统一前缀 | `app:cache:user:1001` |
| 不用中文空格 | 英文 + 数字 + `:` |

```python
# ✅ 可读、有层级、便于批量清理
r.set("user:1001:profile", '{"name":"Alice"}')
r.set("order:2026:10:29:count", 42)

# ❌ 无层级、无法按前缀扫描、浪费内存
# r.set("用户1001资料", "...")
```

### 3.2、TTL 命令

#### bash

```bash
EXPIRE key 60            # 给 `key` 设置过期时间，**60 秒后自动删除**
PEXPIRE key 1500         # 设置 key 1500 毫秒（1.5 秒）后过期
EXPIREAT key 1767225600  # 在**Unix 秒级时间戳 1767225600** 这个时刻过期删除 key
TTL key                  # 返回该 key 剩余多少秒过期：-1 永久，-2 不存在，>0 剩余秒数
PTTL key                 # 返回剩余毫秒
PERSIST key              # 移除 key 的过期时间，变成永久有效。
EXPIRETIME key           # Redis 7.0+，返回 到期的秒级 Unix 时间戳
EXPIRE key 60 NX         # Redis 7.0+，仅当 key 目前没有过期时间，才设置 60 秒过期；已有 TTL 则不修改
EXPIRE key 60 GT         # Redis 7.0+，只有新的过期时间晚于当前已有的到期时间，才更新 TTL（只能延长，不能缩短）
```

#### python

```python
import redis
# redis.Redis()创建 Redis 客户端连接实例
# 默认参数：host="127.0.0.1"，port=6379
# `decode_responses=True`：自动把 Redis 返回的 bytes 字节串转成普通字符串，不用每次手动 `decode()`
r = redis.Redis(decode_responses=True)

# key: tmp:code，value: 1234，写入时直接带 300 秒过期,ex:秒，px: 毫秒
r.set("tmp:code", "1234", ex=300)    

# r.ttl("tmp:code") 返回：
# `> 0`：距离 tmp:code 过期的剩余秒数
# `-1`：key 存在，无过期时间（永久，执行完 `persist` 就是这个）
# `-2`：key 不存在
print(r.ttl("tmp:code"))

# 将 tmp:code 的TTL 改成 600 秒
r.expire("tmp:code", 600)

# r.persist("tmp:code") 移除 `tmp:code` 的过期时间，变成永久 key，返回：
# `True`：成功，原本带有过期时间，现已取消过期
# `False`：失败（key 不存在 / 本来就没有过期时间）
print(r.persist("tmp:code"))

print(r.ttl("tmp:code"))
```

### 3.3、过期删除策略

| 策略 | 做法 | 特点 |
|---|---|---|
| **惰性删除** | 访问时才判断 | 省 CPU，可能长期占内存 |
| **定期删除** | 每 100ms 随机抽 20 个带 TTL 的 key，过期比例超 25% 继续抽 | 折中 |

> “过期了内存没释放” 是正常现象 —— 没被访问也没被抽中。

### 3.4、内存淘汰策略 (8 种)

| 策略 | 范围 | 算法 |
|---|---|---|
| `noeviction` | --- | 不淘汰，写入报错 (默认) |
| `allkeys-lru` | 所有 | 近似 LRU |
| `allkeys-lfu` | 所有 | 近似 LFU |
| `allkeys-random` | 所有 | 随机 |
| `volatile-lru` | 有 TTL 的 | 近似 LRU |
| `volatile-lfu` | 有 TTL 的 | 近似 LFU | 
| `volatile-random` | 有 TTL 的 | 随机 |
| `volatile-ttl` | 有 TTL 的 | 剩余时间最短优先 |

#### redis.conf 配置文件

```text
# redis.conf 配置文件

# Redis 使用内存的上限，达到这个阈值之后，触发淘汰策略。不配置的话，内存会一直涨，操作系统可能直接把 redis 进程杀掉（OOM killer）。
maxmemory 4gb

# 淘汰策略：在**所有 key 里面**，淘汰最近最少使用（LRU）的 key，非常适合纯缓存场景。
maxmemory-policy allkeys-lru

# Redis 的 LRU/LFU 不是精确算法，是 采样近似 ：淘汰时随机取 `10` 个 key，在里面挑最久没用的。
# 数字越大：结果越接近真实 LRU，但是 CPU 开销变大
# 数字越小：CPU 省一点，淘汰准确度下降
maxmemory-samples 10
```

#### 淘汰策略选择规则

- 纯缓存 (数据都可丢)
  - 淘汰策略选 `allkeys-lru`
- 混合用途 (缓存 + 队列 + 锁)
  - 淘汰策略选 `volatile-lru`，且所有缓存 key 必须设 TTL
  - 否则 队列/锁 数据会被当成缓存淘汰掉

### 本章要点

1. key 用冒号分层，短而可读
2. 过期是 “惰性 + 定期”，不是定时器
3. `SET NX EX` 是锁与缓存的标准原子写法
4. 混合用途别用 `allkeys-*`

## 第四章：数据类型 (10 种)

### 4.0、总览

| 类型 | 结构 | 典型场景 |
|---|---|---|
| String | 字节串 | 缓存、计数、锁 |
| List | 双向链表 | 队列、时间线 |
| Hash | 字段表 | 对象、购物车、会话 |
| Set | 无序去重集合 | 标签、去重、抽奖 |
| ZSet | 带分数的有序集合 | 排行榜、延迟队列、限流 |
| Bitmap | 位数组 | 签到、布尔标记 |
| HyperLogLog | 基数估算 | UV 统计 |
| GEO | 地理位置 | 附近的人 |
| Stream | 消息流 | 可靠队列 |
| Vector Set | 向量 + 图索引 | 语义检索、RAG |

### 4.1、String

#### bash

```bash
# 设置键 `user:1`，值是 JSON 字符串 `{"name":"Alice"}`；`EX 300` 代表 300 秒后自动过期删除这个 key
# 原子命令，写入 + 设置过期一步完成
SET user:1 '{"name":"Alice"}' EX 300

# 读取 `user:1` 对应的 value
# 如果 key 已经过期 / 不存在，返回 `nil`
GET user:1

# 对 `article:100:views` 的值原子 + 1（一般用来做阅读量、计数器）
# key 不存在 → 自动初始化为 0，再加 1；值必须是数字字符串，否则报错
INCR article:100:views

# 对 stock:1 按指定步长增减，这里步长 `-1`，等价减 1，常用于库存扣减
# 等价简写：`DECR stock:1`
INCRBY stock:1 -1

# 批量设置多个键值对，一次性存入 k1=v1、k2=v2
# 原子操作：全部成功或者全部不写入
MSET k1 v1 k2 v2

# 批量读取多个 key，一次拿到 k1、k2 的值
# 返回是一个列表；某个 key 不存在时，该位置返回 `nil`
MGET k1 k2

# 向 `log` 这个字符串的 末尾追加内容 `"line\n"`（换行文本）
# key 不存在就新建一个 key，值就是追加的字符串；适合简单日志累加
APPEND log "line\n"

# 获取 `user:1` 对应 value 的 字节长度（不是字符个数！）
# 中文一个汉字占多个字节，不能直接当成汉字数量
STRLEN user:1
```

#### Python

```python
import redis
r = redis.Redis(decode_responses=True)

# 设置 key `user:1:name` 值为 `Alice`，300 秒过期
r.set("user:1:name", "Alice", ex=300)

# 读取这个 key，输出 `Alice`
print(r.get("user:1:name"))

# r.incr("article:100:views"): `article:100:views` 自增 1。
# 第一次运行：key 不存在，初始 0→1，打印 `1`
print(r.incr("article:100:views"))
# 第二次这条 incr：1→2，打印 `2`
print(r.incr("article:100:views"))

# 分布式锁经典写法
# `nx=True`：**key 不存在才写入；已经存在就写入失败**
# `px=30000`：30000 毫秒 = 30 秒自动过期
# 返回 `True` 获取锁成功；`False` 锁已经被别人持有
ok = r.set("lock:order:1", "my-token", nx=True, px=30000)
print(ok)

# 批量设置：`a="1"`，`b="2"`，原子写入
r.mset({"a": "1", "b": "2"})

# 批量读取，输出列表 `['1', '2']`
print(r.mget("a", "b"))
```

**底层编码**：int (纯数字) / embstr (短串) / raw (长串)。上限 512 MB。

### 4.2、List

#### bash

```bash
# 从list链表 q 左边（队首）依次压入 a、b，执行后队列：`[b, a]`
LPUSH q a b

# 从list链表 q 右边（队尾）压入 c，队列变成：`[b, a, c]`
RPUSH q c

# 取出索引 `0 ~ -1`（-1 代表最后一个元素），也就是 取出整个列表，返回：`["b","a","c"]`
LRANGE q 0 -1

# 弹出左边第一个元素（队首），返回 b
LPOP q

# 弹出右边最后一个元素（队尾），返回 c
RPOP q

# 裁剪列表，只保留下标 0 ~ 99 的元素，多余尾部直接删掉；
# 如果总长度本来就 ≤100，这条命令什么都不做。用来限制队列最大长度。
LTRIM q 0 99

# 获取 list 里面元素个数（队列长度）
LLEN q

# B = Blocking 阻塞版 LPOP
# 队列有数据：立刻左边弹出一个返回
# 队列为空：最多阻塞等待 5 秒；5 秒内有人 RPUSH 数据就弹出；超时返回 `None`
# 常用做简单消息队列
BLPOP q 5

# 从多个 key `q1、q2` 里，按顺序找第一个非空的 list，左边弹出 1 个元素
# `2`：key 的数量（后面跟着 2 个 key：q1,q2）
# `LEFT`：从左端弹出；换成 `RIGHT` 就是右端
# `COUNT 1`：一次弹出几个
LMPOP 2 q1 q2 LEFT COUNT 1
```

#### python

```python
import redis
r = redis.Redis(decode_responses=True)

# 删除这个 key，清空队列，防止上次残留数据干扰测试。
r.delete("queue:mail")

# 从左侧（队头）推入 `task-1`，此时列表：`["task-1"]`
r.lpush("queue:mail", "task-1")
# 再从左侧推入 `task-2`
r.lpush("queue:mail", "task-2")

# `0,-1` 代表取出全部元素，输出：`['task-2', 'task-1']`
print(r.lrange("queue:mail", 0, -1))

# 从右侧队尾弹出，弹出 `task-1`，打印 `task-1`，弹出后队列剩下：`["task-2"]`
print(r.rpop("queue:mail"))

# `brpop` = 阻塞版 RPOP
# 目标 `queue:not-exist` 是空的（key 不存在等价空队列）
# 程序在这里阻塞等待最多 5 秒，期间如果没有 RPUSH 数据进来，超时后返回 `None`。
# 返回值格式：如果拿到数据是 `("queue:not-exist", "xxx")`
item = r.brpop("queue:not-exist", timeout=5)
print(item)

# 裁剪列表，只保留下标 0～99，最多 100 条记录，超过的旧数据直接删掉。
# 非常适合：用户动态流、浏览历史，限制最多存 100 条。
r.ltrim("feed:user:1", 0, 99)
```

**底层编码**：listpack (小) -> quicklist (大)

### 4.3、Hash

#### bash

```bash
# Hash 写入，在 `user:1` 这个 hash 里面，设置字段：`name=Alice`，`age=20`
# 适合存对象，不用自己拼接 json 字符串
HSET user:1 name Alice age 20

# 单独读取 hash 里面 `name` 这一个字段的值 → `Alice`
HGET user:1 name

# 取出这个 hash 里面 所有字段 + 值，返回字典：`{"name":"Alice", "age":"20"}`
# 大坑：hash 字段非常多时不要随便用 HGETALL，容易大 key、卡顿
HGETALL user:1

# 批量读取指定多个字段，按顺序返回 `["Alice", "20"]`
HMGET user:1 name age

# 对 hash 内的 `age` 字段原子 + 1；
# 前提：字段的值是数字；这里 age 从 20 → 21
HINCRBY user:1 age 1

# 删除 hash 里面 `age` 这个字段（不是删除整个 user:1 这个 key）
HDEL user:1 age

# 迭代遍历 hash 里面的字段，分批扫描，替代 HGETALL，不会一次性加载全部数据
# `0` = 起始游标（第一次遍历固定 0）
# `COUNT 100`：期望一次最多返回 100 个（只是参考，不保证精确）
# 适合字段很多的大 hash，避免 HGETALL 阻塞
HSCAN user:1 0 COUNT 100
```

#### python

```python
import redis
r = redis.Redis(decode_responses=True)

# Hash key 为 `user:1`，一次性存入两个字段：
# `name="Alice"`，`age="20"`（存入 Redis 后全部是字符串）
r.hset("user:1", mapping={
    "name": "Alice",
    "age": 20,
})

# 单独取字段 `name`，输出：`Alice`
print(r.hget("user:1", "name"))

# 取出该 hash 全部字段和值，返回字典：`{'name': 'Alice', 'age': '20'}`
# 注意：hash 字段数量巨大时不推荐 hgetall，容易阻塞
print(r.hgetall("user:1"))

# 对 `age` 字段原子加 1；原来 20 → 21，打印返回结果 `21`
print(r.hincrby("user:1", "age", 1))

# 判断 hash 里是否存在字段`age`，存在返回 `True`，不存在返回`False`
print(r.hexists("user:1", "age"))

# `hscan_iter` 是 redis-py 封装好的迭代器，内部自动维护游标，循环遍历 hash 所有 field，等价手动 `HSCAN` 循环。
# `count=100` 只是提示 Redis 每次尽量返回最多 100 条（不是严格保证）。
# 适合大 hash，替代 hgetall，防止阻塞。
for field, value in r.hscan_iter("user:1", count=100):
    print(field, value)
```

#### Hash 字段级 TTL (7.4+，重点新特征)

##### python

先说明：**HEXPIRE / HTTL / HGETEX / HGETDEL 是 Redis 7.4 才新增的 Hash 字段级过期命令**（给 hash 里面**单独某个 field 设置过期**，不是整个 hash key 过期！）

redis-py 没有对这几个新命令封装方法，所以只能用 `execute_command` 原生调用

```python
import redis
r = redis.Redis(decode_responses=True)

# 写入 hash，key 是`session:u1001`，包含两个字段：`token=abc`、`refresh=def`
r.hset("session:u1001", mapping={"token": "abc", "refresh": "def"})

# 对应原生命令：HEXPIRE session:u1001 1800 FIELDS 1 token
# `session:u1001`：Hash 的 key
# `1800`：过期时长，单位 秒
# `FIELDS 1`：后面一共有 1 个字段要设置过期
# `token`：要设置过期的 field 名字
# 返回 `1` = 设置成功；`0` = 字段不存在，设置失败。
# 给 hash 里面 单个字段 token 设置 1800 秒（30 分钟）过期
# 只有 token 会到期消失；refresh 字段不受影响。
r.execute_command("HEXPIRE", "session:u1001", 1800, "FIELDS", 1, "token")

# 对应原生命令：HTTL session:u1001 FIELDS 1 token
# 查询 token 字段剩余存活秒数，返回：
# ≥0：剩余秒数
# -1：字段存在、没有设置字段 TTL
# -2：字段不存在
# 打印 hash session:u1001 的 token 的TTL
print(r.execute_command("HTTL", "session:u1001", "FIELDS", 1, "token")) 

# 原子操作：读取 token 的值，同时把 token 的过期时间重置为 1800s
# 会话续期场景专用
r.execute_command("HGETEX", "session:u1001", "EX", 1800, "FIELDS", 1, "token")

# 原子操作：先拿到 refresh 的值，然后立刻删除 refresh 这个字段。
# 一次性凭证、一次性验证码很适合这个命令
r.execute_command("HGETDEL", "session:u1001", "FIELDS", 1, "refresh")
```

> **价值**：过去“每个会话一个key”，现在可以“一个 Hash 存一个用户的所有会话字段”，**key 数量骤降**，碎片和内存都省。**注意**：字段过期同样走 “懒惰 + 定期”，不保证那一秒精确消失

**底层编码**：listpack (小) -> hashtable (大)

### 4.4、Set

#### bash

```bash
# 往集合 `tag:py` 添加成员 `u1`、`u2`；重复添加同一个元素会自动忽略，不会报错。
# 用途：打标签、用户分组、标签系统
SADD tag:py u1 u2

# 取出集合里 全部成员。
# 集合很大时不要用，容易阻塞，大集合改用 SSCAN
SMEMBERS tag:py

# 判断 `u1` 是否在这个集合里；存在返回 `1`，不存在返回 `0`。
SISMEMBER tag:py u1

# card = cardinality，获取集合内元素总个数（集合大小）。
SCARD tag:py

# SINTER 交集：同时存在于 `tag:py` 和 `tag:mysql` 的元素（既打 py 标签、又打 mysql 标签的用户）
# SUNION / SDIFF：类似
SINTER tag:py tag:mysql

# 并集：在 py 集合 或者 在 mysql 集合里的全部元素，合并去重。
SUNION tag:py tag:mysql

# 差集：只在 `tag:py` 里面、不在 `tag:mysql` 的元素。
# 顺序敏感：`SDIFF A B` ≠ `SDIFF B A`
SDIFF tag:py tag:mysql

# 随机取出 3 个元素，不取走，集合不变，抽奖、随机推荐常用
SRANDMEMBER tag:py 3

# 随机弹出一个元素，取出来并且从集合删掉，一次性随机抽取。
SPOP tag:py

# 分批迭代遍历集合，替代 SMEMBERS；适合超大集合，防止一次性加载所有数据造成卡顿，游标从 0 开始。
SSCAN tag:py 0 COUNT 100
```

#### python

```python
# 向集合添加一个 / 多个元素，已存在的自动忽略，返回成功新增的数量。
# 集合自动去重，写重复元素不会报错，只是忽略
r.sadd("tag:py", "u1", "u2", "u3")
r.sadd("tag:mysql", "u2", "u3", "u4")

# 获取集合里面元素的总数（集合基数）
# 如果 key 不存在（集合不存在），`scard` 返回 `0`，不会报错。
print(r.scard("tag:py"))

# 判断某个值是否在集合内，存在返回True，不存在False
print(r.sismember("tag:py", "u1"))

# 求多个集合的 交集，同时存在于所有集合的元素
print(r.sinter("tag:py", "tag:mysql"))

# 随机从集合里面取出 N 个元素，但是！不会修改原集合，数据还在
# 只读、不删除，适合：随机推荐、抽奖但不剔除候选人
# 不写第二个参数，默认只随机拿 1 个；
print(r.srandmember("tag:py", 3))

# 随机选出集合里一个元素，返回它，并且把这个元素从原集合永久删掉！
print(r.spop("tag:py"))
```

**底层编码**：intset (全整数) / listpack (小) / hashtable (大)

### 4.5、ZSet

#### bash

```bash
# 向有序集合 `rank` 添加成员和对应分数，`u1:100`，`u2:200`
# 升序，从小到大
# 返回值：成功新增成员数量，这里返回 `2`
ZADD rank 100 u1 200 u2

# 给成员 `u1` 的分数加上增量 10
# 如果成员不存在，会自动新建这个成员，分数 = 增量
ZINCRBY rank 10 u1

# 按分数升序（从小到大）取区间元素
# `0 -1`：从下标 0 到最后一个元素（取出全部）
# `WITHSCORES`：连带分数一起返回，不写只返回成员名
# 下标规则：0 是第一名（分数最小），-1 代表最后一个
ZRANGE rank 0 -1 WITHSCORES

# 降序（分数从大到小）取区间元素
# `0 9`：取下标 0~9，我们只有 2 个元素，等价取全部
# 场景：排行榜从高到低展示
ZREVRANGE rank 0 9 WITHSCORES

# 查询成员升序排名（下标，从 0 开始），升序顺序：0:u1，1:u2
# 重点：返回的是索引，不是第 1 名！从 0 计数；成员不存在返回 `None`，
ZRANK rank u1

# 查询成员降序排名（下标，从 0 开始），降序顺序：0:u2，1:u1
ZREVRANK rank u1

# 直接查询该成员对应的分数
# 成员不存在返回 `None`
ZSCORE rank u1

# 根据分数范围筛选成员，升序返回，分数 ≥100 且 ≤200
# `(100` 代表大于 100（不包含 100）；`+inf`、`-inf` 正负无穷
ZRANGEBYSCORE rank 100 200

# 统计分数在 min~max 之间的成员数量
# 和 ZRANGEBYSCORE 区别：ZRANGEBYSCORE 返回元素列表；ZCOUNT 只返回个数
ZCOUNT rank 100 200

# 从有序集合弹出元素（Redis 6.2+）
# 一共给 1 个 key（就是 rank） 
# - `MIN`：优先弹出分数最小的元素（换成 MAX 就是弹最大）
ZMPOP 1 rank MIN
```

#### python

```python
r.zadd("rank:week", {"u1": 100, "u2": 200, "u3": 150})   # 成员: 分数

r.zincrby("rank:week", 10, "u1")                          # u1 加 10 分 → 110

# 降序取前 3；withscores=True 同时返回分数
top3 = r.zrevrange("rank:week", 0, 2, withscores=True)
print(top3)   # → [('u2', 200.0), ('u3', 150.0), ('u1', 110.0)]

rank = r.zrevrank("rank:week", "u1")   # 从 0 开始，不存在返回 None
print(rank + 1)                        # → 3（展示排名要 +1）

print(r.zscore("rank:week", "u1"))     # → 110.0
```

**底层编码**：listpack (小) -> skiplist + dict (大)

### 4.6、Bitmap

#### bash

```bash
# 把下标 1001 这一个 bit 设置为 1（代表用户 1001 签到了）
# 返回值：这个 offset 上原来的 bit 值
SETBIT sign:2026-10-05 1001 1

# 读取 key 里面，offset=1001 位置上的 bit 值
# 返回：`0` 或者 `1`
# 坑：offset 超出当前位图长度，直接返回 0，不会报错
GETBIT sign:2026-10-05 1001

# 统计这个位图里，值为 1 的 bit 一共有多少个
BITCOUNT sign:2026-10-05

# 对源位图 `a` 和 `b` 的每一个 bit 做 按位与（AND）运算，结果保存到新 key `dest`
# AND、OR、XOR、NOT
BITOP AND dest a b
```

#### python

```python
r.setbit("sign:2026-10-05", 1001, 1)      # 偏移量直接用用户 ID
r.setbit("sign:2026-10-05", 1002, 1)

print(r.getbit("sign:2026-10-05", 1001))  # → 1（已签到）
print(r.bitcount("sign:2026-10-05"))      # → 2（当天 2 人）
```

> 只适合 **稠密 ID** (从 1 开始且连续)。雪花 ID 这种稀疏 ID 会浪费大量空间

### 4.7、HyperLogLog

#### python

```python
# 往 HLL 里面添加元素（u1,u2,u3），用来参与基数估算
# 返回值：`1` 代表 HLL 内部结构发生变化（新增有效元素）；`0` 代表元素之前已经存在，没有变化
# 注意：HLL 不会保存 u1、u2、u3 本身，只维护哈希统计结构
r.pfadd("uv:2026-10-05", "u1", "u2", "u3")

# 获取这个 HyperLogLog 的估算独立数量
# 可以同时传多个 key：`pfcount(k1,k2)` 等价先合并再统计，但不产生新 key
print(r.pfcount("uv:2026-10-05"))

# 把多个源 HLL 合并成一个新的 HLL，存入目标 key `uv:week`
# 合并后的基数 ≈ 两天所有独立用户总数（自动去重，同一个用户两天都来只算 1 次
# 返回：`True` 代表合并成功
r.pfmerge("uv:week", "uv:2026-10-04", "uv:2026-10-05")

# 读取合并之后 HLL 的估算独立数
print(r.pfcount("uv:week"))
```

> 12 KB，误差 0.81%，**不能取出成员**，只能估算基数。

### 4.8、GEO

#### python

```python
# 参数顺序：经度、纬度、名称
r.geoadd("cities", (116.40, 39.90, "beijing"))
r.geoadd("cities", (121.47, 31.23, "shanghai"))

print(r.geodist("cities", "beijing", "shanghai", unit="km"))   # → 1067.xx

print(r.geosearch("cities", longitude=116.40, latitude=39.90,
                  radius=100, unit="km"))   # 半径 100km 内的城市
```

> 底层是 ZSet，score 是 geohash

### 4.9、Stream

#### bash

```bash
XADD orders * user alice amount 100      # * = 自动生成消息 ID
XADD orders MAXLEN ~ 10000 * user bob amount 50   # 只保留约 1 万条
XLEN orders
XRANGE orders - +
XGROUP CREATE orders g1 0 MKSTREAM       # 创建消费组
XREADGROUP GROUP g1 c1 COUNT 10 STREAMS orders >
XACK orders g1 1767225600000-0
XPENDING orders g1
XCLAIM orders g1 c2 60000 1767225600000-0
```

#### python

```python
# 生产：maxlen 限制长度；approximate=True 用近似裁剪，性能更好
msg_id = r.xadd("orders",
                {"user": "alice", "amount": 100},
                maxlen=10000, approximate=True)
print(msg_id)      # → '1767225600000-0'

# 创建消费组；重复创建会抛 BUSYGROUP，属于正常
try:
    r.xgroup_create("orders", "g1", id="0", mkstream=True)
except redis.ResponseError:
    pass

# 消费
resp = r.xreadgroup("g1", "consumer-1", {"orders": ">"},
                    count=10, block=2000)
for stream_name, messages in resp or []:
    for mid, fields in messages:
        handle(fields)                 # 业务处理
        r.xack("orders", "g1", mid)    # ★ 处理成功才 ACK
```

> 详细见第 9 章

### 4.10、Vector Set (8.0+)

#### python

```python
# VADD key VALUES 维度 分量1 分量2 分量3 元素名
r.execute_command("VADD", "items", "VALUES", 3, 0.10, 0.20, 0.30, "doc1")
r.execute_command("VADD", "items", "VALUES", 3, 0.11, 0.19, 0.29, "doc2")

# VSIM：找最相似的 2 个
print(r.execute_command("VSIM", "items", "VALUES", 3, 0.10, 0.20, 0.31,
                        "COUNT", 2))      # → ['doc1', 'doc2']

print(r.execute_command("VDIM", "items"))    # → 3（维度）
print(r.execute_command("VCARD", "items"))   # → 2（元素数）
```

> 详见第 11 章

### 4.11、底层编码

| 类型 | 小数据量 | 大数据量 |
|---|---|---|
| String | int / embstr | raw |
| List | listpack | quicklist |
| Hash | listpack | hashtable | 
| Set | intset / listpack | hashtable |
| ZSet | listpack | skiplist + dict |
| Stream | --- | rax + listpack |

```python
# 查看某个 key 的实际编码（面试常问"ZSet 什么时候转跳表"）
print(r.object("encoding", "rank:week"))   # → 'listpack' 或 'skiplist'
```

> 面试常问 “ZSet 为什么用跳表”：实现简单、范围查询高效、无需旋转、内存局部性好

## 第五章：命令速查

### 5.1、通用

#### bash

```bash
KEYS pattern                     # ⚠️ 生产禁用，阻塞全库
SCAN 0 MATCH "user:*" COUNT 100  # 游标遍历
EXISTS key
TYPE key
DEL key
UNLINK key                       # 异步删除，删大 key 用它
EXPIRE / TTL / PERSIST / EXPIRETIME
RENAME / RENAMENX
MEMORY USAGE key
OBJECT ENCODING key
```

### 5.2、8.x 新增命令速查

#### bash

```bash
# Hash 字段 TTL（7.4+）
HEXPIRE HPEXPIRE HEXPIREAT HPEXPIREAT
HTTL HPTTL HEXPIRETIME HPEXPIRETIME
HPERSIST HGETEX HSETEX HGETDEL

# 落盘确认（7.2+）
WAITAOF numlocal numreplicas timeout

# 分片 Pub/Sub（7.0+）
SSUBSCRIBE SUNSUBSCRIBE SPUBLISH

# Functions（7.0+）
FUNCTION LOAD / LIST / DUMP / RESTORE / DELETE / STATS
FCALL / FCALL_RO

# 集合/列表（7.0+）
SINTERCARD LMPOP BLMPOP ZMPOP BZMPOP

# Vector Set（8.0+）
VADD VSIM VDIM VCARD VREM VEMB VINFO VLINKS

# 内置模块（8.x）
JSON.SET / JSON.GET / JSON.DEL
FT.CREATE / FT.SEARCH / FT.AGGREGATE
TS.ADD / TS.RANGE / TS.MRANGE
BF.ADD / BF.EXISTS / BF.RESERVE
```

### 5.3、服务端

#### bash

```bash
INFO [section]
CONFIG GET / SET
CLIENT LIST / CLIENT KILL / CLIENT NO-EVICT ON
SLOWLOG GET 10
MEMORY STATS / MEMORY USAGE key
LATENCY HISTORY event
DBSIZE
FLUSHDB / FLUSHALL      # ⚠️ 慎用
DEBUG SLEEP 10          # ⚠️ 会阻塞
MONITOR                 # ⚠️ 生产慎用
```

## 第六章：持久化

### 6.1、RDB (快照)

**原理**：`fork()` 子进程写快照，父进程继续服务 (写时复制 COW)

#### redis.conf

```text
# redis.conf

save 900 1
save 300 10
save 60 10000
dbfilename dump.rdb
```

#### bash

```bash
BGSAVE      # 后台快照，不阻塞主进程
LASTSAVE    # 上次成功快照的时间戳
```

| 优点 | 缺点 |
|---|---|
| 文件紧凑，适合备份 | 两次快照间宕机丢数据 |
| 恢复快 | 大内存下 `fork` 卡顿 |
| 对性能影响小 | 子进程可能内存翻倍 | 

### 6.2、AOF (追加日志)

#### redis.conf

```text
# redis.conf

appendonly yes                   # 开启
appendfsync everysec             # 每秒刷盘：最多丢 1 秒（推荐）
# appendfsync always             # 每条刷：最安全但最慢
# appendfsync no                 # 交给 OS：最快但可能丢几十秒

auto-aof-rewrite-percentage 100  # 文件比上次大 100% 时重写
auto-aof-rewrite-min-size 64mb   # 且至少 64MB 才重写
```

#### bash

```bash
BGREWRITEAOF    # 手动触发重写，压缩日志体积
```

### 6.3、混合持久化 

#### redis.conf

```text
# redis.conf

aof-use-rdb-preamble yes   # AOF 头部用 RDB 格式（加载快），尾部是增量命令（丢得少）
```

### 6.4、multi-part AOF (7.0+)

AOF 拆成 **base(RDB) + incr (增量) + manifest (清单)** ，放在 `appendonlydir/`。重写不在需要大缓冲区。

### 6.5、落盘确认

```bash
# WAIT：等 N 个副本确认"已收到"（单位毫秒）
print(r.execute_command("WAIT", 1, 100))        # → 1

# WAITAOF：等本地/副本的 AOF "真正落盘"（7.2+）
print(r.execute_command("WAITAOF", 1, 1, 100))  # → [1, 1]
```

| 命令 | 确认什么 | 延迟 |
|---|---|---|
| `WALT` | 副本已收到 | 低 |
| `WAITAOF` | AOF 已落盘 | 高 | 

### 6.6、怎么选

| 场景 | 配置 |
|---|---|
| 纯缓存 | 可关持久化，或只留 RDB |
| 一般业务 | RDB + AOF + 混合持久化 |
| 不能丢 | AOF `everysec` + `WAITAOF` + 主从 |
| 极致性能 | 关持久化，靠复制和备份 |

> **持久化** $\neq$ **备份**。RDB 文件要异地备份，并**定期演练恢复**

## 第七章：高可用

### 7.1、主从复制

#### redis.conf

```text
# redis.conf

replicaof 127.0.0.1 6379
replica-read-only yes
```

#### bash

```bash
INFO replication           # 查看角色、偏移量、从节点列表
```

| 机制 | 说明 |
|---|---|
| 全量同步 | 首次链接，主库 `BGSAVE` 传 RDB |
| 增量同步 | 断线重连，靠 `repl_backlog` 补发 |
| 异步复制 | 主库写完即返回，**可能丢数据** |

### 7.2、哨兵 (Sentinel)

```text
        ┌──────────────┐
        │ Sentinel × 3 │（奇数，分散部署）
        └───────┬──────┘
   ┌────────────┼────────────┐
 Master ──── Replica1 ──── Replica2
```

#### redis.conf

```text
# redis.conf

sentinel monitor mymaster 127.0.0.1 6379 2      # 2 = quorum，至少 2 个哨兵认为挂了才切换
sentinel down-after-milliseconds mymaster 30000 # 30 秒无响应判主观下线
sentinel failover-timeout mymaster 180000       # 故障转移超时
sentinel parallel-syncs mymaster 1              # 每次只让 1 个从库同步新主
```

| 概念 | 说明 |
|---|---|
| 主观下线 SDOWN | 单个哨兵认为挂了 |
| 客观下线 ODOWN | 超过 quorum 个哨兵认为挂了 |
| Leader 选举 | 哨兵之间选一个执行切换 |
| 故障转移 | 选新主、从库跟随、通知客户端 |

### 7.3、Cluster (集群)

```text
key → CRC16(key) % 16384 → 槽 → 节点
```

#### bash

```bash
# 创建 3 主 3 从
redis-cli --cluster create \
  127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003 \
  127.0.0.1:7004 127.0.0.1:7005 127.0.0.1:7006 \
  --replicas 1              # 每个主配 1 个从

redis-cli -c -p 7001        # -c = 自动跟随 MOVED 重定向
```

```bash
CLUSTER INFO                # 集群状态
CLUSTER NODES               # 节点与槽分配
CLUSTER KEYSLOT mykey       # 某 key 属于哪个槽
```

#### python

```python
# hash tag：花括号内的部分参与槽计算，保证相关 key 同槽
r.set("{user:1001}:name", "Alice")
r.set("{user:1001}:age", 20)
# 两个 key 的槽都由 "user:1001" 决定 → 可以一起 MGET
print(r.mget("{user:1001}:name", "{user:1001}:age"))   # → ['Alice', '20']
```

| 特性 | 说明 |
|---|---|
| 最少节点 | 3 主 3 从 |
| 重定向 | `MOVED` (槽已迁走)、`ASK` (迁移中) |
| 多 key 操作 | 必须同槽，否则 `CROSSSLOT` |
| 事务/Lua | 只能操作同槽 key |
| 数据库 | 只有 db0，不支持 `SELECT` |

### 7.4、选型

| 方案 | 数据量 | 可用性 | 复杂度 |
|---|---|---|---|
| 单机 | 小 | 低 | 低 |
| 主从 | 中 | 中 (人工切换) | 低 |
| 哨兵 | 中 | 高 | 中 |
| Cluster | 大 | 高 | 高 | 
| 云托管 | 任意 | 高 | 低 (推荐生产) |

## 第八章：事务、Lua、Pipeline、Functions

### 8.1、事务

#### bash

```bash
MULTI              # 开启
SET a 1            # 入队
INCR a             # 入队
EXEC               # 一次性执行，返回结果列表
# DISCARD          # 放弃
# WATCH key        # 乐观锁：key 被改过则 EXEC 返回 nil
```

#### python

```python
# transaction=True 会把命令包在 MULTI ... EXEC 里
with r.pipeline(transaction=True) as pipe:
    pipe.set("a", 1)         # 只是入队，还没发出去
    pipe.incr("a")
    results = pipe.execute() # 此刻一次性执行
print(results)               # → [True, 2]
```

> **Redis 事务不会滚**：运行时错误不会撤销已执行的命令。

### 8.2、Lua

#### lua脚本

```lua
-- 目标：计数器小于上限就 +1 并返回 1，否则返回 0
local v = tonumber(redis.call('GET', KEYS[1]) or '0')
--  ^ KEYS[1] 是第一个 key；key 不存在时返回 false，用 or '0' 兜底

if v >= tonumber(ARGV[1]) then
--  ^ ARGV[1] 是第一个参数（上限）
  return 0                 -- 已达上限
end

redis.call('INCR', KEYS[1]) -- 未达上限，自增
return 1                    -- 放行
```

#### python

```python
LUA = """
local v = tonumber(redis.call('GET', KEYS[1]) or '0')
if v >= tonumber(ARGV[1]) then
  return 0
end
redis.call('INCR', KEYS[1])
return 1
"""

# register_script：首次发送脚本，之后自动用 EVALSHA（只发哈希，省带宽）
allow = r.register_script(LUA)

print(allow(keys=["limit:api"], args=[10]))   # → 1（第一次，放行）
print(allow(keys=["limit:api"], args=[10]))   # → 1（第二次）
print(allow(keys=["limit:api"], args=[2]))    # → 0（已达上限）
```

> 脚本执行期间 Redis 不执行其他命令，所以 **脚本必须短**，别写大循环

### 8.3、Functions (7.0+)

```bash
FUNCTION LOAD "#!lua name=mylib
redis.register_function('myincr', function(keys, args)
  return redis.call('INCR', keys[1])
end)"

FCALL myincr 1 counter     # 函数名、key 数量、key
FUNCTION LIST
FUNCTION DUMP
```

|  | Lua (EVAL) | Functions |
|---|---|---|
| 代码存放 | 客户端每次发 | 服务器端持久化 |
| 调用 | `EVALSHA` | `FCALL` |
| 适合 | 临时脚本 | 长期复用的库 |

### 8.4、Pipeline

```python
# transaction=False：不包 MULTI/EXEC，只攒批发送
with r.pipeline(transaction=False) as pipe:
    for i in range(1000):
        pipe.set(f"k:{i}", i)    # 入队，不发网络
    results = pipe.execute()     # 一次往返发完 1000 条
print(len(results))              # → 1000
```

|  | Pipeline | 事务 | Lua |
|---|---|---|---|
| 减少 RTT | 支持 | 支持 | 支持 |
| 原子性 | 不支持 | 部分支持 | 支持 |
| 条件逻辑 | 不支持 | 不支持 | 支持 |
| 阻塞风险 | 低 | 低 | 高 |

> 批大小 500–1000 条，太大容易撑爆服务端输出缓冲区。

## 第九章：消息：Pub/Sub 与 Stream

### 9.1、Pub/Sub

#### bash

```bash
SUBSCRIBE news
PSUBSCRIBE news.*
PUBLISH news "hello"        # 返回收到消息的订阅者数量

# 分片 Pub/Sub（7.0+，Cluster 下按槽分发）
SSUBSCRIBE shard:1
SPUBLISH shard:1 "msg"
```

#### python

```python
r.publish("news", "hello")        # 发布，返回接收者数量

pubsub = r.pubsub()
pubsub.subscribe("news")          # 订阅频道

for msg in pubsub.listen():       # 阻塞等待
    if msg["type"] == "message":  # 忽略 subscribe 的确认消息
        print(msg["channel"], msg["data"])
```

| 特点 | 说明 |
|---|---|
| 实时 | 延迟极低 |
| 不持久化 | 无定阅者时消息丢弃 |
| 无 ACK | 掉线即丢 |
| 无消费组 | 所有订阅者都收到 |

### 9.2、Stream

#### bash

```bash
XADD orders * user alice amount 100
XADD orders MAXLEN ~ 10000 * user bob amount 50
XLEN orders
XRANGE orders - +
XGROUP CREATE orders g1 0 MKSTREAM
XREADGROUP GROUP g1 c1 COUNT 10 BLOCK 5000 STREAMS orders >
XACK orders g1 1767225600000-0
XPENDING orders g1
XCLAIM orders g1 c2 60000 1767225600000-0
XINFO STREAM orders
```

#### python

```python
# ① 创建消费组，id="0" 表示从头消费；mkstream 让 stream 不存在时自动创建
try:
    r.xgroup_create("orders", "g1", id="0", mkstream=True)
except redis.ResponseError:
    print("消费组已存在（BUSYGROUP），忽略")

# ② 循环消费
while True:
    resp = r.xreadgroup(
        "g1",               # 消费组
        "consumer-1",       # 消费者名（同组内唯一）
        {"orders": ">"},    # ">" 表示只要从未投递的新消息
        count=10,           # 一次最多 10 条
        block=2000,         # 无消息时最多阻塞 2 秒，避免空转
    )

    if not resp:            # 超时没拿到
        continue

    # 结构：[('orders', [('id1', {...}), ('id2', {...})])]
    for stream_name, messages in resp:
        for msg_id, fields in messages:
            try:
                handle(fields)                    # 业务逻辑
                r.xack("orders", "g1", msg_id)    # ★ 成功才 ACK
            except Exception:
                pass    # 不 ACK，留在 pending，之后可 XCLAIM 重试
```

| 概念 | 类比 **Kafka** |
|---|---|
| Stream | topic |
| Consumer Group | 消费组 |
| `XACK` | 提交 offset |
| `XPENDING` | 未确认消息 |
| `XCLAIM` | 转移超时消息 |

> Stream 不是专业 MQ：没有分区、没有复杂重试。量大用 Kafka/RabbitMQ。

## 第十章：内置模块：JSON / Search / TimeSeries / Bloom

> 8.0 起内置，**不再需要 Redis Stack**。

### 10.1、JSON

#### python

```python
# $ 是根节点（JSONPath）；SET 会整体覆盖
r.execute_command("JSON.SET", "doc:1", "$", '{"name":"Alice","age":20}')

print(r.execute_command("JSON.GET", "doc:1", "$.name"))   # → '["Alice"]'

# 只改某个字段，不用读出来再写回
r.execute_command("JSON.SET", "doc:1", "$.age", 21)

# 数组追加
r.execute_command("JSON.SET", "doc:1", "$.tags", '["a"]')
r.execute_command("JSON.ARRAPPEND", "doc:1", "$.tags", '"b"')
```

### 10.2、Search

#### python

```python
# 对 user: 前缀的 Hash 建索引：name 全文检索，age 数值过滤
r.execute_command(
    "FT.CREATE", "idx:user",
    "ON", "HASH",
    "PREFIX", 1, "user:",     # 1 = 后面有 1 个前缀
    "SCHEMA",
    "name", "TEXT",
    "age", "NUMERIC",
)

print(r.execute_command("FT.SEARCH", "idx:user", "@name:Alice"))
```

### 10.3、TimeSeries

#### python

```python
r.execute_command("TS.ADD", "ts:cpu:1", "*", 0.75)   # * = 用当前时间
print(r.execute_command("TS.RANGE", "ts:cpu:1", "-", "+"))
```

### 10.4、Bloom

#### python

```python
# 0.01 = 误判率，1000000 = 预估元素数
r.execute_command("BF.RESERVE", "bf:uid", 0.01, 1000000)
r.execute_command("BF.ADD", "bf:uid", 1001)
print(r.execute_command("BF.EXISTS", "bf:uid", 1001))   # → 1（可能存在）
```

> 布隆过滤器"说不存在就一定不存在，说存在可能误判"——正好防缓存穿透。

## 第十一章：Vector Set (8.0+)

#### python

```python
# 写入：VALUES 后先跟维度，再跟分量，最后是元素名
r.execute_command("VADD", "items", "VALUES", 3, 0.10, 0.20, 0.30, "doc1")
r.execute_command("VADD", "items", "VALUES", 3, 0.11, 0.19, 0.29, "doc2")
r.execute_command("VADD", "items", "VALUES", 3, 0.90, 0.10, 0.00, "doc3")

# 查询：找与 [0.10,0.20,0.31] 最相似的 2 个
print(r.execute_command("VSIM", "items", "VALUES", 3, 0.10, 0.20, 0.31,
                        "COUNT", 2))        # → ['doc1', 'doc2']

# 以已有元素为查询
print(r.execute_command("VSIM", "items", "ELEM", "doc1", "COUNT", 3))

# 元信息
print(r.execute_command("VDIM", "items"))    # → 3
print(r.execute_command("VCARD", "items"))   # → 3
```

| 参数 | 说明 |
|---|---|
| `VALUES <dim>` | 后面跟 dim 个浮点数 |
| `COUNT n` | 返回前 n 个 |
| `ELEM x` | 用已有元素向量查询 |
| `FILTER expr` | 属性过滤表达式 |

|  | Vector Set | FT 向量索引 |
|---|---|---|
| 上手 | 一条命令 | 需建 schema |
| 混合检索 | 有限 | 强 |
| 适用 | 小规模语义召回 | 复杂检索系统 |

> 维度必须一致 (先定 embedding 模型)，上限 4096

## 第十二章：缓存三大问题与一致性

### 12.1、穿透

**问题**：查不存在的数据，缓存永不命中，全部打到 DB。

#### python

```python
def get_user(uid: int):
    key = f"user:{uid}"

    cached = r.get(key)
    if cached is not None:
        # 缓存过的空值用 "NULL" 标记，避免反复查库
        return None if cached == "NULL" else json.loads(cached)

    user = db.query_user(uid)      # 假设这是你的 ORM

    if user is None:
        r.set(key, "NULL", ex=60)  # 空值也缓存，TTL 要短
        return None

    r.set(key, json.dumps(user), ex=3600)
    return user
```

| 方案 | 说明 |
|---|---|
| 缓存控制 | 写 `NULL`，TTL 30-60秒 |
| 布隆过滤器 | 提前拦截 |
| 参数校验 | 格式、范围 |
| 限流 | 防恶意请求 |

### 12.2、击穿

**问题**：**单个热点 key 过期**瞬间，大量请求同时回源

#### python

```python
def get_user(uid: int):
    key = f"user:{uid}"

    cached = r.get(key)
    if cached is not None:
        # 缓存过的空值用 "NULL" 标记，避免反复查库
        return None if cached == "NULL" else json.loads(cached)

    user = db.query_user(uid)      # 假设这是你的 ORM

    if user is None:
        r.set(key, "NULL", ex=60)  # 空值也缓存，TTL 要短
        return None

    r.set(key, json.dumps(user), ex=3600)
    return user
```

| 方案 | 说明 |
|---|---|
| 互斥锁 | 只放一个线程回源 |
| 逻辑过期 | 值里带过期时间，异步刷新 |
| 热点永不过期 | 后台定时更新 |

### 12.3、雪崩

**问题**：大量 key 同时过期，或 Redis 整体不可用

#### python

```python
import random

def set_with_jitter(key: str, value: str, base_ttl: int = 3600):
    # 给 TTL 加随机抖动，避免同一批 key 同时失效
    ttl = base_ttl + random.randint(0, 300)   # 3600 ~ 3900
    r.set(key, value, ex=ttl)
```

| 方案 | 说明 |
|---|---|
| TTL 加随机 | 打散过期时间 |
| 多级缓存 | 本地 Caffeine + Redis |
| 熔断降级 | Redis 挂了返回兜底 |
| 高可用 | 哨兵 / Cluster |

### 12.4、一致性

```text
读：缓存 → 未命中 → DB → 回写缓存
写：更新 DB → 删除缓存
```

#### python

```python
def update_user(uid: int, data: dict):
    db.update_user(uid, data)      # ① 先更新数据库
    r.delete(f"user:{uid}")        # ② 删除缓存（不是更新）
    time.sleep(0.1)
    r.delete(f"user:{uid}")        # ③ 延迟双删，覆盖"读请求写回旧值"的窗口
```

| 策略 | 问题 |
|---|---|
| 先删缓存再更库 | 并发读会把旧值写回 |
| 先更库再删缓存 | 推荐 |
| 更库后更新缓存 | 并发下可能写旧值 | 
| 订阅 binlog | Canal 异步删，最终一致 |

## 第十三章：分布式锁

#### python

```python
import uuid

# 解锁脚本：只有 value 等于自己的 token 才删除
# 防止"业务超时 → 锁释放 → 别人加锁 → 自己删掉别人的锁"
LUA_UNLOCK = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

class RedisLock:
    def __init__(self, client, name: str, ttl: int = 30):
        self.r = client
        self.key = f"lock:{name}"      # 统一前缀，便于排查
        self.ttl = ttl                 # 超时秒数，防止死锁
        self.token = None              # 唯一标识，用于安全释放
        self._release = client.register_script(LUA_UNLOCK)

    def acquire(self) -> bool:
        self.token = uuid.uuid4().hex  # 每次加锁生成新 token
        # SET key token NX PX ttl —— 一条命令原子完成"判断+设置+过期"
        ok = self.r.set(self.key, self.token, nx=True, px=self.ttl * 1000)
        return bool(ok)                # ok 为 True 或 None

    def release(self) -> bool:
        if not self.token:
            return False
        return bool(self._release(keys=[self.key], args=[self.token]))

    def extend(self, seconds: int) -> bool:
        # 续期（看门狗）：只有自己还持有锁时才能延长
        lua = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('PEXPIRE', KEYS[1], ARGV[2])
        end
        return 0
        """
        return bool(self.r.eval(lua, 1, self.key, self.token, seconds * 1000))
```

```python
lock = RedisLock(r, "order:123", ttl=30)

if lock.acquire():
    try:
        do_something()
    finally:
        lock.release()     # ★ 必须释放
else:
    print("没抢到锁")
```

| 问题 | 方案 |
|---|---|
| 死锁 | `px=ttl*1000` 自动过期 | 
| 误删别人的锁 | token + Lua 比较后删 |
| 业务超时 | `extend()` 续期 |
| 主从切换丢锁 | Redlock 或接受风险 |

#### 什么时候不该用：

| 场景 | 更好方案 |
|---|---|
| 能用数据库唯一索引 | 别引入 Redis |
| 需要强一致 | ZooKeeper / etcd |
| 只是防重复提交 | 幂等 token + 唯一索引 |

> Redlock 争议：依赖时钟与网络延迟，GC 停顿可能导致锁失效

## 第十四章：典型业务模式

### 14.1、排行榜 (ZSet)

#### python

```python
def add_score(board: str, member: str, delta: int):
    # zincrby 原子加分；member 不存在时从 0 开始
    return r.zincrby(f"rank:{board}", delta, member)

def top_n(board: str, n: int = 10):
    # 0 到 n-1 就是前 n 名；withscores 同时返回分数
    return r.zrevrange(f"rank:{board}", 0, n - 1, withscores=True)

def my_rank(board: str, member: str):
    rank = r.zrevrank(f"rank:{board}", member)
    return None if rank is None else rank + 1   # 展示排名要 +1
```

### 14.2、限流：固定窗口

#### python

```python
import time

def allow_fixed(user: str, limit: int = 10, window: int = 60) -> bool:
    bucket = int(time.time()) // window      # 同一窗口共用一个 key
    key = f"rl:fixed:{user}:{bucket}"

    n = r.incr(key)          # 原子 +1，返回当前计数
    if n == 1:               # 首次创建才需要设过期
        r.expire(key, window)
    return n <= limit        # 没超限就放行
```

> 缺点：窗口边界会 “双倍放行” (59秒、61秒 各 10 次)

### 14.3、限流：滑动窗口 (ZSet)

#### python

```python
import time, uuid

def allow_sliding(user: str, limit: int = 10, window: int = 60) -> bool:
    key = f"rl:slide:{user}"
    now = time.time()

    pipe = r.pipeline()                            # 攒批，减少往返
    pipe.zremrangebyscore(key, 0, now - window)    # ① 删掉窗口外的旧记录
    pipe.zadd(key, {f"{now}-{uuid.uuid4().hex[:6]}": now})  # ② 记录本次请求
    pipe.zcard(key)                                # ③ 统计窗口内数量
    pipe.expire(key, window)                       # ④ 兜底过期
    _, _, count, _ = pipe.execute()                # 对应 ①②③④ 的返回值

    return count <= limit
```

> ZSet 的 score 存时间戳，成员名用 “时间戳 + 随机串” 保证唯一

### 14.4、签到 (Bitmap)

#### python

```python
def sign_in(uid: int, day: str):
    return r.setbit(f"sign:{day}", uid, 1)     # 偏移量直接用用户 ID

def signed_count(day: str) -> int:
    return r.bitcount(f"sign:{day}")           # 统计 1 的个数

def is_signed(uid: int, day: str) -> bool:
    return bool(r.getbit(f"sign:{day}", uid))
```

### 14.5、去重与 UV

#### python

```python
# 精确去重：Set
r.sadd("day:2026-10-05", uid)

# 近似 UV：HyperLogLog（12KB，误差 0.81%）
r.pfadd("uv:2026-10-05", uid)
r.pfcount("uv:2026-10-05")
```

### 14.6、购物车 (Hash)

#### python

```python
def add_to_cart(uid: int, sku: str, qty: int = 1):
    r.hincrby(f"cart:{uid}", sku, qty)     # 字段=商品，值=数量

def get_cart(uid: int) -> dict:
    return r.hgetall(f"cart:{uid}")        # 值都是字符串，用前要 int()

def clear_cart(uid: int):
    r.delete(f"cart:{uid}")
```

### 14.7、简单队列

#### python

```python
r.lpush("queue:mail", json.dumps(task))    # 生产

while True:
    item = r.brpop("queue:mail", timeout=5)  # 阻塞消费
    if item is None:
        continue                             # 超时，继续等
    _, data = item                           # 返回的是 (key, value)
    handle(json.loads(data))
```

### 14.8、延迟队列

#### python

```python
import time

def delay_push(queue: str, task_id: str, delay_sec: int):
    # score = 期望执行的时间戳
    r.zadd(f"delay:{queue}", {task_id: time.time() + delay_sec})

def delay_poll(queue: str, batch: int = 10):
    now = time.time()
    # 取出所有到期任务（score <= 当前时间）
    due = r.zrangebyscore(f"delay:{queue}", 0, now, start=0, num=batch)

    for task_id in due:
        # zrem 返回 1 表示"我抢到了"，多 worker 并发时天然防重复
        if r.zrem(f"delay:{queue}", task_id):
            handle(task_id)
```

## 第十五章：Python 实战

### 15.1、连接

#### python

```python
import redis

r = redis.Redis(
    host="127.0.0.1",
    port=6379,
    db=0,                       # Cluster 只有 0
    password=None,
    decode_responses=True,      # ★ 返回 str 而不是 bytes
    socket_timeout=3,           # ★ 生产必设，防卡死
    socket_connect_timeout=3,
    health_check_interval=30,   # 空闲 30 秒自动 PING
    retry_on_timeout=True,
)
print(r.ping())                 # → True
```

### 15.2、连接池

#### python

```python
pool = redis.ConnectionPool(
    host="127.0.0.1",
    port=6379,
    db=0,
    max_connections=20,         # 超过会阻塞等待
    decode_responses=True,      # 池级别生效
    socket_timeout=3,
)
r = redis.Redis(connection_pool=pool)

# 或者用 URL
r = redis.Redis.from_url("redis://:pwd@127.0.0.1:6379/0",
                         decode_responses=True, max_connections=20)
```

> **注意**：每请求 `redis.Redis(...)` 会不断建池，很快耗尽连接

### 15.3、基础操作

#### python

```python
r.set("k", "v", ex=60)                 # 带过期
r.set("k", "v", nx=True, px=30000)     # 锁
r.get("k")
r.incr("counter")
r.mset({"a": 1, "b": 2})
r.mget("a", "b")

r.hset("user:1", mapping={"name": "Alice"})
r.hgetall("user:1")

r.lpush("q", "a")
r.brpop("q", timeout=5)

r.sadd("tags", "py")
r.smembers("tags")

r.zadd("rank", {"u1": 100})
r.zrevrange("rank", 0, 9, withscores=True)

r.exists("k")
r.expire("k", 60)
r.delete("k")
```

### 15.4、遍历

#### python

```python
# ❌ keys() 阻塞全库
# for k in r.keys("user:*"): ...

# ✅ scan_iter 分批，内存友好
for key in r.scan_iter(match="user:*", count=100):
    print(key)
```

### 15.5、Pipeline

#### python

```python
with r.pipeline(transaction=False) as pipe:
    for i in range(1000):
        pipe.set(f"k:{i}", i)      # 入队
    results = pipe.execute()        # 一次往返
```

### 15.6、Lua 与 Functions

#### python

```python
script = r.register_script("return redis.call('INCR', KEYS[1])")
print(script(keys=["counter"], args=[]))       # → 1

# Functions：需先在服务端 FUNCTION LOAD 过
print(r.execute_command("FCALL", "myincr", 1, "counter"))
```

### 15.7、分布式锁

#### python

```python
lock = r.lock("order:123", timeout=10, blocking_timeout=5)
if lock.acquire(blocking=True):
    try:
        do_work()
    finally:
        lock.release()
```

> redis-py 的 `Lock` **不可重入**。需要重入要自己实现计数或 Redisson

### 15.8、Pub/Sub

#### python

```python
pubsub = r.pubsub()
pubsub.subscribe("news")

for msg in pubsub.listen():        # 阻塞，通常放独立线程
    if msg["type"] == "message":
        print(msg["channel"], msg["data"])
```

### 15.9、Stream

```python
msg_id = r.xadd("orders", {"user": "alice", "amount": 100},
                maxlen=10000, approximate=True)   # 限制长度，防内存涨

try:
    r.xgroup_create("orders", "g1", id="0", mkstream=True)
except redis.ResponseError:
    pass                                          # BUSYGROUP，忽略

while True:
    resp = r.xreadgroup("g1", "consumer-1", {"orders": ">"},
                        count=10, block=2000)
    for stream, messages in resp or []:
        for mid, fields in messages:
            handle(fields)
            r.xack("orders", "g1", mid)           # ★ 成功后 ACK
```

### 15.10、8.x 新命令

#### python

```python
# Hash 字段 TTL
r.execute_command("HEXPIRE", "user:1", 60, "FIELDS", 1, "token")
r.execute_command("HTTL", "user:1", "FIELDS", 1, "token")

# 落盘确认
r.execute_command("WAITAOF", 1, 1, 100)

# Vector Set
r.execute_command("VADD", "items", "VALUES", 3, 0.1, 0.2, 0.3, "doc1")
r.execute_command("VSIM", "items", "VALUES", 3, 0.1, 0.2, 0.31, "COUNT", 2)

# 内置模块
r.execute_command("JSON.SET", "doc", "$", '{"a":1}')
r.execute_command("BF.ADD", "bf:uid", 1001)
```

### 15.11、异步

#### python

```python
import asyncio
import redis.asyncio as aredis        # 异步客户端在这个命名空间

async def main():
    r = aredis.Redis(host="127.0.0.1", decode_responses=True,
                     socket_timeout=3)

    await r.set("k", "v", ex=60)      # 所有命令都要 await
    print(await r.get("k"))           # → 'v'

    async with r.pipeline(transaction=False) as pipe:   # 异步 pipeline 用 async with
        pipe.set("a", 1)
        pipe.incr("a")
        print(await pipe.execute())   # → [True, 2]

    await r.aclose()                  # 显式关闭连接池

asyncio.run(main())
```

> 异步代码里绝不能用同步 `redis.Redis` ，会阻塞事件循环

### 15.12、错误处理与降级

#### python

```python
import logging
from redis.exceptions import ConnectionError, TimeoutError, ResponseError

log = logging.getLogger(__name__)

def safe_get(key: str):
    try:
        return r.get(key)
    except (ConnectionError, TimeoutError) as e:
        log.warning("Redis 不可用，降级：%s", e)    # 网络类：降级
        return None
    except ResponseError as e:
        log.error("命令错误：%s", e)                # 命令类：是 bug，要暴露
        raise
```

| 异常 | 场景 |
|---|---|
| `ConnectionError` | 连不上，断连 | 
| `TimeoutError` | 超时 |
| `ResponseError` | 命令语法 / 类型错误 |
| `AuthenticationError` | 密码错误 |
| `BusyLoadingError` | 加载数据中 |

### 15.13、缓存装饰器

#### python

```python
import functools, json

def cache(key_fmt: str, ttl: int = 300):
    def deco(fn):
        @functools.wraps(fn)              # 保留原函数名和文档
        def wrapper(*args, **kwargs):
            key = key_fmt.format(*args, **kwargs)   # 生成 key，如 "user:1001"

            cached = r.get(key)
            if cached is not None:
                return json.loads(cached)           # ① 命中，反序列化返回

            result = fn(*args, **kwargs)            # ② 未命中，执行原函数

            if result is not None:
                r.set(key, json.dumps(result, ensure_ascii=False), ex=ttl)
            return result
        return wrapper
    return deco


@cache("user:{0}", ttl=600)
def get_user(uid: int):
    return db.query_user(uid)       # 只有缓存未命中时才会执行
```

### 15.14、集群客户群

#### python

```python
from redis.cluster import RedisCluster

rc = RedisCluster(
    startup_nodes=[{"host": "127.0.0.1", "port": 7001}],
    decode_responses=True,
)

# 用 hash tag 保证相关 key 同槽
rc.set("{user:1}:name", "Alice")
rc.set("{user:1}:age", 20)
```

## 第十六章：运维、监控与安全

### 16.1、关键指标

#### bash

```bash
redis-cli INFO memory        # 内存
redis-cli INFO stats         # 命中率、连接数
redis-cli INFO replication   # 主从
redis-cli INFO persistence   # RDB/AOF
```

| 指标 | 含义 | 告警 |
|---|---|---|
| `used_memory` | 已用内存 | 接近 maxmemory |
| `evicted_keys` | 淘汰数 | 持续增长 |
| `keyspace_hits` / `misses` | 命中率 | 低于 90% 排查 |
| `connected_clients` | 连接数 | 接近 maxclients |
| `blocked_clients` | 阻塞客户端 | 异常增长 |
| `instantaneous_ops_per_sec` | QPS | 突增突降 |
| `latest_fork_usec` | fork 耗时 | 超过 100ms |
| `rdb_last_besave_status` | 快照状态 | 非 ok |
| `aof_last_write_status` | AOF 状态 | 非 ok |

### 16.2、慢查询与大 key

#### bash

```bash
redis-cli CONFIG SET slowlog-log-slower-than 10000   # 记录超过 10ms 的命令（微秒）
redis-cli SLOWLOG GET 10                              # 最近 10 条
redis-cli SLOWLOG RESET

redis-cli --bigkeys            # 各类最大的 key
redis-cli --hotkeys            # 热点 key（需 LFU 策略）
redis-cli MEMORY USAGE user:1  # 单个 key 占用字节
```

| 大 key 阈值 (经验) | 类型 |
|---|---|
| 大于 10 KB | String |
| 大于 5000 元素 | List / Hash / Set / ZSet | 

### 16.3、安全

```text
bind 127.0.0.1          # 只监听本机
protected-mode yes      # 保护模式
requirepass 强密码       # 密码
```

#### bash

```bash
# ACL：只允许操作 app: 前缀、只允许少量命令
ACL SETUSER app on '>password' '~app:*' +get +set +del +expire
ACL LIST
ACL WHOAMI
```

> Redis 未授权访问是最常见的入侵入口，绝不暴露公网。

### 16.4、备份

```bash
BGSAVE                                                    # 生成快照
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%F).rdb  # 异地备份
```

> 持久化不是备份，要定期 **演练恢复**

## 第十七章：坑清单

### 17.1、使用类

| 坑 | 后果 | 解法 |
|---|---|---|
| `KEYS *` | 阻塞全库 | `SCAN` |
| `FLUSHALL` 手抖 | 数据全没 | 禁用命令 |
| 大 key `DEL` | 阻塞 | `UNLINK` | 
| 大 Hash `HGETALL` | 阻塞 | `HSCAN` 分批 |
| 长时间 `MONITOR` | 性能骤降 | 只短时排查 | 
| Lua 死循环 | 全库卡死 | 限制脚本 | 
| 无超时 | 线程堆积 | `socket_timeout` | 
| 每请求新建连接 | 连接耗尽 | 连接池 |

### 17.2、设计类

| 坑 | 后果 | 解法 |
|---|---|---|
| 缓存同时过期 | 雪崩 | TTL 加随机 |
| 空值缓存不设 TTL | 内存泄漏 | 短 TTL |
| 先删缓存再更库 | 脏数据 | 先更库再删 | 
| 锁无过期 | 死锁 | `PX` |
| 锁 value 不唯一 | 误删 | UUID + Lua |
| Cluster 跨槽 | `CROSSSLOT` | hash tag |
| Pub/Sub 传业务消息 | 丢消息 | Stream 或 MQ |
| Stream 不设 MAXLEN | 内存涨满 | `MAXLEN ~` |

### 17.3、运维类

| 坑 | 后果 | 解法 |
|---|---|---|
| 没设 `maxmemory` | OOM 被 kill | 设上限 |
| `noeviction` 当缓存 | 写入报错 | `allkeys-lru` |
| 混合用途用 `allkeys-*` | 队列被淘汰 | `volatile-*` + TTL |
| 主从延迟 | 读不到新数据 | 关键读走主 |
| 只有 1 个哨兵 | 脑裂 | 至少 3 个 |
| 无持久化 | 重启全丢 | RDB + AOF |
| 公网暴露 | 被入侵 | 内网 + ACL |

## 第十八章：面试高频问答

### Q1：Redis 为什么快？

纯内存、单线程无锁、IO 多路复用、高效数据结构

### Q2：单线程为什么能高并发？

瓶颈在网络不在 CPU；epoll 单线程处理海量连接；命令都是轻量操作

### Q3：6.0 的多线程是什么？

只是网络读写多线程，命令执行仍单线程。

### Q4：RDB 和 AOF 怎么选？

RDB 恢复快、体积小但可能丢数据；AOF 丢的少但文件大。生产用混合持久化。

### Q5：`WAIT` 和 `WAITAOF` 的区别？

`WAIT` 等副本收到；`WAITAOF` 等本地/副本 AOF 真正落盘，更严格 (7.2+)

### Q6：Hash 字段 TTL 有什么用？

让一个 Hash 承载多组独立过期的数据 (会话、验证码)，大幅减少 key 数量 (7.4+)

### Q7：缓存穿透、击穿、雪崩的区别？

穿透查不存在的数据；击穿是热点 key 过期；雪崩是大量 key 同时失效或 Redis 挂。

### Q8：如何保证缓存一致性？

Cache Aside：先更库再删缓存，配合延迟双删或 binlog 订阅，最终一致。

### Q9：Redis 事务支持回滚吗？

不支持。运行时错误不会回滚已执行命令。

### Q10：Lua 和 Functions 的区别？

Lua 由客户端发送，Functions 注册在服务端可持久化复用 (7.0+)

### Q11：分布式锁怎么实现？

`SET NX PX` 加锁，Lua 比较 token 释放，超时用看门狗续期。

### Q12：Cluster 为什么是 16384？

CRC16 mod 16384；在心跳包大小与节点规模间取得折中值。

### Q13：ZSet 为什么用跳表？

实现简单、范围查询高效、无需旋转、内存局部性好。

### Q14：Redis 内存满了会怎样？

按 `maxmemory-policy` 淘汰；`noeviction` 时写报错、读仍可用。

### Q15：大 key 有什么危害？

删除阻塞、网络拥塞、集群倾斜、迁移慢。用 `--bigkeys` 和 `MEMONY USAGE` 发现。

### Q16：Vector Set 和 FT 向量索引怎么选？

轻量语义召回用 Vector Set；需要向量 + 文本 + 数值混合检索用 Search 索引。

### Q17：主从同步是同步还是异步？

异步，主库写完即返回，可能丢数据。

### Q18：延迟队列怎么实现？

ZSet 存 score=执行时间戳，轮询 `ZRANGEBYSCORE` 取到期任务，用 `ZREM` 防重复消费。

## 第十九章：速查表

### 19.1、命令速查

#### bash

```text
【通用】     SET GET DEL EXISTS EXPIRE TTL PERSIST TYPE SCAN UNLINK
【String】   SET EX NX PX / INCR DECR INCRBY / MSET MGET / APPEND STRLEN
【List】     LPUSH RPUSH LPOP RPOP LRANGE LLEN LTRIM BLPOP BRPOP LMOVE LMPOP
【Hash】     HSET HGET HMGET HGETALL HDEL HINCRBY HKEYS HLEN HSCAN
【Hash TTL】 HEXPIRE HTTL HPERSIST HGETEX HSETEX HGETDEL
【Set】      SADD SREM SMEMBERS SISMEMBER SCARD SINTER SUNION SDIFF SPOP SSCAN
【ZSet】     ZADD ZREM ZSCORE ZINCRBY ZRANGE ZREVRANGE ZRANK ZREVRANK ZRANGEBYSCORE
【Bitmap】   SETBIT GETBIT BITCOUNT BITOP BITFIELD
【HLL】      PFADD PFCOUNT PFMERGE
【GEO】      GEOADD GEODIST GEOSEARCH GEOPOS
【Stream】   XADD XREAD XRANGE XLEN XGROUP XREADGROUP XACK XPENDING XCLAIM
【Vector】   VADD VSIM VDIM VCARD VREM VEMB VINFO
【事务】     MULTI EXEC DISCARD WATCH
【脚本】     EVAL EVALSHA SCRIPT LOAD / FUNCTION LOAD FCALL
【持久化】   BGSAVE BGREWRITEAOF WAIT WAITAOF
【发布订阅】 SUBSCRIBE PUBLISH PSUBSCRIBE SSUBSCRIBE SPUBLISH
【模块】     JSON.* FT.* TS.* BF.*
【服务】     INFO CONFIG CLIENT SLOWLOG MEMORY LATENCY MONITOR
```

### 19.2、redis-py 速查

#### python

```python
r = redis.Redis(host="127.0.0.1", decode_responses=True, socket_timeout=3)

r.set("k", "v", ex=60)                        # 带过期
r.set("k", "v", nx=True, px=30000)            # 锁
r.incr("c")
r.hset("h", mapping={"a": 1})
r.zadd("z", {"m": 1})
r.scan_iter(match="user:*", count=100)        # 遍历（不用 keys）

with r.pipeline(transaction=False) as p:      # 攒批
    p.set("a", 1)
    p.execute()

r.register_script(lua)(keys=["k"], args=[1])  # Lua
r.execute_command("VADD", "items", "VALUES", 3, 0.1, 0.2, 0.3, "doc1")
```

### 19.3、配置速查

#### redis.conf

```text
# redis.conf

maxmemory 4gb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
save 900 1
tcp-keepalive 300
io-threads 4
```

### 19.4、排查命令

#### bash

```bash
redis-cli -h host -p 6379 -a pwd ping
redis-cli INFO memory
redis-cli --bigkeys
redis-cli --hotkeys
redis-cli SLOWLOG GET 10
redis-cli CLIENT LIST
redis-cli MEMORY USAGE key
redis-cli --latency
redis-cli MONITOR        # 慎用
```

## 第二十章：学习路线

### 阶段一：能跑 (1-2天)

- 起一个 Reids 8 实例
- 用 `redis-cli` 跑通 5 种基础类型
- Python 连接，做一次缓存读写
- 理解 `SET NX EX`

### 阶段二：能设计 (1 周)

- ZSet 排行榜
- Bitmap 签到
- Hash 购物车
- Lua 限流
- 手写分布式锁

### 阶段三：懂原理 (2 周)

- RDB/AOF 回复演练
- 一主一从 + 哨兵
- 理解 16384 槽与 `MOVED` 
- 分析大 key 与慢查询

### 阶段四：用上 8.x (1 周)

- Hash 字段 TTL 改造会话
- `WAITAOF` 做落盘确认
- Vector Set 做一次语义检索 demo
- JSON / Search 做一次混合查询

### 阶段五：生产化 (持续)

- 连接池 + 超时 + 降级
- 监控告警
- Cluster 部署与扩容
- 缓存一致性 (binlog 订阅)
- 压测与容量规划

## 资源

| 类型 | 名称 |
|---|---|
| 官方 | redis.io/docs (含 8.x 新命令文档) |
| 书 | 《Redis 设计与实现》 |
| 书 | 《Redis 深度历险》 |
| 源码 | `src/server.c`、`src/t_zset.c`、`src/vector*.c` |
| 工具 | RedisInsight / Another Redis Desktop Manager | 