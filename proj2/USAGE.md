# 🚀 CDC Pipeline 使用指南

## 📁 文件说明

### ✅ 生产环境使用这些文件

```
核心文件（生产环境）:
├── producer.py              ✅ Producer（已优化：连接池）
├── consumer_final.py        ✅ Consumer（终极版本，包含所有功能）
├── employee.py              ✅ 数据模型
├── setup_db.sql             ✅ 基础数据库设置
├── setup_db_with_idempotency.sql  ✅ 幂等性表（可选）
├── docker-compose.yml       ✅ 基础服务
└── docker-compose.monitoring.yml  ✅ 监控（可选）
```

### 📚 学习参考文件（教学用途）

```
教学演示文件（了解各个功能，不用于生产）:
├── consumer.py              📚 基础版本（展示核心功能）
├── consumer_with_dlq.py     📚 DLQ 演示版本
├── consumer_idempotent.py   📚 幂等性演示版本
└── ARCHITECTURE_IMPROVEMENTS.md  📚 架构改进指南
```

---

## 🎯 快速开始

### 1. 启动基础服务

```bash
# 启动 Kafka + PostgreSQL
docker-compose up -d

# 等待服务就绪
sleep 15
```

### 2. 设置数据库

```bash
# 方式 A: 基础设置（无幂等性）
docker exec -i proj2-db_source-1 psql -U postgres < setup_db.sql
docker exec proj2-db_dst-1 psql -U postgres -c "
CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    city VARCHAR(100),
    salary INT
);"

# 方式 B: 完整设置（推荐，包含幂等性）
docker exec -i proj2-db_source-1 psql -U postgres < setup_db.sql
docker exec -i proj2-db_dst-1 psql -U postgres < setup_db_with_idempotency.sql
```

### 3. 运行 CDC Pipeline

```bash
# Terminal 1: 启动 Producer
python producer.py

# Terminal 2: 启动 Consumer（生产版本）
python consumer_final.py
```

---

## ⚙️ Consumer 配置选项

### consumer_final.py 参数

```python
consumer = ProductionCDCConsumer(
    host="localhost",              # Kafka 主机
    port="29092",                  # Kafka 端口
    group_id='my_consumer_group',  # Consumer Group ID
    db_host="localhost",           # 目标数据库主机
    db_port="5433",                # 目标数据库端口
    enable_dlq=True,               # ✅ 启用 DLQ（推荐）
    enable_idempotency=True        # ✅ 启用幂等性（推荐）
)
```

### 功能开关

| 参数 | 默认值 | 说明 | 推荐 |
|------|--------|------|------|
| `enable_dlq` | `True` | Dead Letter Queue 错误隔离 | ✅ 生产必须 |
| `enable_idempotency` | `True` | 防止重复处理 | ✅ 生产必须 |

---

## 🧪 测试

### 测试 INSERT
```bash
docker exec proj2-db_source-1 psql -U postgres -c "
INSERT INTO employees (first_name, last_name, dob, city, salary)
VALUES ('John', 'Doe', '1990-01-01', 'NYC', 80000);
"
```

### 测试 UPDATE
```bash
docker exec proj2-db_source-1 psql -U postgres -c "
UPDATE employees SET salary = 90000 WHERE emp_id = 1;
"
```

### 测试 DELETE
```bash
docker exec proj2-db_source-1 psql -U postgres -c "
DELETE FROM employees WHERE emp_id = 1;
"
```

### 验证同步
```bash
# 源数据库
docker exec proj2-db_source-1 psql -U postgres -c "
SELECT * FROM employees ORDER BY emp_id;
"

# 目标数据库
docker exec proj2-db_dst-1 psql -U postgres -c "
SELECT * FROM employees ORDER BY emp_id;
"

# 应该完全一致！
```

---

## 📊 监控

### 启动监控栈（可选）
```bash
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# 访问 Grafana
open http://localhost:3000  # 默认: admin/admin

# 访问 Prometheus
open http://localhost:9090
```

### 查看统计信息
Consumer 会自动输出统计：
```
📊 Stats: Processed=100, Failed=0, Duplicates=5, DLQ=0
```

---

## 🐛 故障排查

### DLQ 消息查看
```bash
docker exec proj2-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic bf_employee_cdc_dlq \
  --from-beginning
```

### 重置 Consumer Group（重新消费）
```bash
# 停止 consumer
# 然后重置 offset
docker exec proj2-kafka-1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group production_cdc_consumer \
  --reset-offsets --to-earliest \
  --topic bf_employee_cdc \
  --execute
```

### 查看幂等性追踪
```bash
docker exec proj2-db_dst-1 psql -U postgres -c "
SELECT action_id, emp_id, action, processed_at
FROM processed_events
ORDER BY action_id DESC
LIMIT 10;
"
```

---

## 🔄 版本对比

### 我应该使用哪个 Consumer？

| 场景 | 使用文件 | 原因 |
|------|---------|------|
| **生产环境** | `consumer_final.py` | ✅ 包含所有功能 |
| **学习/开发** | `consumer_final.py` | ✅ 同样推荐 |
| **了解 DLQ 原理** | `consumer_with_dlq.py` | 📚 教学用途 |
| **了解幂等性原理** | `consumer_idempotent.py` | 📚 教学用途 |
| **最简单版本** | `consumer.py` | 📚 基础学习 |

**建议**: 直接使用 `consumer_final.py`，它是最完善的版本！

---

## 🎯 最佳实践

### 生产环境清单

✅ **必须做**:
- [ ] 使用 `consumer_final.py`
- [ ] 启用 DLQ (`enable_dlq=True`)
- [ ] 启用幂等性 (`enable_idempotency=True`)
- [ ] 设置 `processed_events` 表
- [ ] 配置监控 (Prometheus + Grafana)
- [ ] 设置告警规则

✅ **推荐做**:
- [ ] 使用配置文件（不硬编码密码）
- [ ] 设置日志级别
- [ ] 定期清理 DLQ
- [ ] 备份数据库

---

## 📚 更多信息

查看详细的架构改进指南:
```bash
cat ARCHITECTURE_IMPROVEMENTS.md
```

---

## 💡 常见问题

### Q: 为什么有这么多 consumer 文件？
**A**: 其他 consumer 文件是教学用途，展示各个功能。**生产环境只需使用 `consumer_final.py`**。

### Q: 如果不需要幂等性怎么办？
**A**: 设置 `enable_idempotency=False`，或者不创建 `processed_events` 表。

### Q: DLQ 消息怎么处理？
**A**:
1. 查看 DLQ 找出失败原因
2. 修复问题（数据或代码）
3. 手动重放 DLQ 消息

### Q: 性能如何？
**A**:
- 连接池：~100x 提升
- 批处理：每 10 条消息打印一次统计
- 事务：保证原子性的前提下最大化吞吐

---

## 🚀 总结

**简单版本**:
```bash
# 1. 启动服务
docker-compose up -d

# 2. 设置数据库
docker exec -i proj2-db_source-1 psql -U postgres < setup_db.sql
docker exec -i proj2-db_dst-1 psql -U postgres < setup_db_with_idempotency.sql

# 3. 运行
python producer.py &
python consumer_final.py
```

**就这么简单！** 🎉
