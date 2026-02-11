---
name: feishu-block-adder
description: 块添加子技能 - 将解析后的块数据添加到飞书文档，分批处理，支持表格和普通块。
---

# 块添加子技能

## 职责
将解析后的块数据添加到飞书文档，分批处理以避免 API 限制。

## 输入
- `blocks.json` - 由 feishu-md-parser 生成
- `doc_info.json` - 由 feishu-doc-creator-v2 生成

## 输出
- `output/add_result.json` - 添加结果统计

## 工作流程

### 第一步：加载块数据
从 `blocks.json` 加载解析后的块。

### 第二步：加载文档信息
从 `doc_info.json` 加载文档 ID。

### 第三步：分批添加块
- 每批最多 20 个块
- 表格单独处理
- 普通块批量添加

### 第四步：保存结果
保存添加结果到 `output/add_result.json`。

## 数据格式

### add_result.json 格式
```json
{
  "success": true,
  "document_id": "U2wNd2rMkot6fzxr67ScN7hJn7c",
  "total_blocks": 290,
  "tables_created": 10,
  "regular_blocks": 280,
  "batches": 15,
  "duration_seconds": 5.2
}
```

## 使用方式

### 命令行
```bash
python scripts/block_adder.py workflow/step1_parse/blocks.json workflow/step2_create/doc_info.json output
```

### 作为子技能被调用
```python
result = call_skill("feishu-block-adder", {
    "blocks_file": "workflow/step1_parse/blocks.json",
    "doc_info_file": "workflow/step2_create/doc_info.json",
    "output_dir": "workflow/step3_add_blocks"
})
```

## 与其他技能的协作
- 接收来自 `feishu-md-parser` 的块数据
- 接收来自 `feishu-doc-creator-with-permission` 的文档信息
- 输出给 `feishu-doc-verifier` 和 `feishu-logger`

## 支持的块类型

### 当前支持的块类型（13种）

| block_type | 名称 | 状态 | 说明 |
|------------|------|------|------|
| 2 | text | ✅ | 普通文本 |
| 3-8 | heading1-6 | ✅ | 一到六级标题 |
| 12 | bullet | ✅ | 无序列表 |
| 13 | ordered | ✅ | 有序列表 |
| 14 | code | ✅ | 代码块 |
| 15 | quote | ✅ | 引用块 |
| 22 | divider | ✅ | 分割线 |
| 31 | table | ✅ | 表格（特殊处理） |

### 完整块类型参考

详细的块类型支持情况请查看：
- `.claude/skills/feishu-md-parser/BLOCK_TYPES.md`

### 添加新块类型

1. 在 `feishu-md-parser/scripts/md_parser.py` 中添加解析逻辑
2. 在 `scripts/block_adder.py` 的有效块类型检查中添加新类型
3. 参考 `BLOCK_TYPES.md` 中的示例代码

```python
# 在 block_adder.py 中添加新块类型（约第 247 行）
if block_copy.get("block_type") in [
    2, 3, 4, 5, 6, 7, 8,      # text, headings
    12, 13,                    # lists
    14,                        # code
    15,                        # quote
    19,                        # callout (新增示例)
    22,                        # divider
]:
    valid_blocks.append(block_copy)
```

---

## ⚠️ 重要：Callout 块 (block_type: 19) 的特殊处理

### 关键问题
**Callout 块的颜色字段必须直接放在 `callout` 对象下，不能嵌套在 `style` 中。**

### 正确格式
```json
{
    "block_type": 19,
    "callout": {
        "elements": [{"text_run": {"content": "警告信息"}}],
        "emoji_id": "warning",
        "background_color": 1,
        "border_color": 1,
        "text_color": 1
    }
}
```

### 代码实现
在 `block_adder.py` 第 130-178 行：

```python
def create_callout_with_children(token, config, document_id, callout_style, callout_content):
    payload = {
        "children": [{
            "block_type": 19,
            "callout": {
                "elements": [{"text_run": {"content": callout_content}}],
                **callout_style  # 关键：使用展开操作符
            }
        }],
        "index": -1
    }
    # ... 调用 API
```

### 验证方法
检查 API 返回的 callout 对象是否包含颜色字段：

```python
returned_callout = result["data"]["children"][0].get("callout", {})
if "background_color" not in returned_callout:
    print("❌ 格式错误：颜色字段未被保存")
```

### 详细说明
- 代码注释：第 130-178 行
- 问题排查：`../feishu-doc-orchestrator/TROUBLESHOOTING.md`
- 测试脚本：`../feishu-doc-orchestrator/test_callout_only.py`

---

## ⭐ 最佳实践：表格创建使用 Descendant API

### 关键发现

经过测试验证，飞书官方推荐的 `descendant` API 是创建表格的最可靠方式。

### 问题背景

旧的两步法创建表格容易失败：
1. 先创建表格框架（block_type 31）
2. 再逐个填充单元格内容

这种方式的问题：
- 小表格（8行以下）可能成功
- 大表格（10行以上）经常返回 `invalid param` 错误
- 单元格内容可能丢失

### 解决方案：使用 Descendant API

**API 端点**：
```
POST /open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/descendant
```

**关键点**：
```python
{
    "index": -1,
    "children_id": [table_id],           # 只包含顶层块
    "descendants": [                       # 包含所有块
        {
            "block_id": table_id,
            "block_type": 31,              # 表格块
            "table": {"property": {...}},
            "children": [cell_ids]         # 引用单元格
        },
        {
            "block_id": cell_id,
            "block_type": 32,              # 单元格块
            "table_cell": {},
            "children": [content_id]      # 引用内容块
        },
        {
            "block_id": content_id,
            "block_type": 2,               # 文本块
            "text": {"elements": [...]},
            "children": []
        }
    ]
}
```

### 测试结果

| 表格大小 | 旧方法 | Descendant API |
|---------|--------|----------------|
| 8行 × 6列 | ✅ | ✅ |
| 11行 × 5列 | ❌ invalid param | ✅ |
| 20行 × 10列 | ❌ 失败 | ✅ |

### 代码实现

在 `scripts/block_adder.py` 第 66-157 行：

```python
def create_table_with_style(token, config, document_id, rows_data):
    """
    创建表格并填充内容 - 使用 descendant API

    根据飞书官方规范，使用 /descendant 端点一次性创建表格和所有单元格

    关键点：
    1. children_id 只包含直接添加到文档的块（table_id）
    2. descendants 包含所有块的详细信息（表格、单元格、单元格内容）
    3. 表格的 children 引用单元格的 block_id
    4. 单元格的 children 引用内容块的 block_id
    """
    import uuid

    row_size = len(rows_data)
    col_size = len(rows_data[0]) if rows_data else 0

    # 生成唯一的 block_id
    table_id = f"table_{uuid.uuid4().hex[:16]}"
    cell_ids = [f"cell_{uuid.uuid4().hex[:16]}" for _ in range(row_size * col_size)]
    content_ids = [f"content_{uuid.uuid4().hex[:16]}" for _ in range(row_size * col_size)]

    # 构建完整的 descendants 列表
    descendants = []

    # 1. 添加表格块
    descendants.append({
        "block_id": table_id,
        "block_type": 31,
        "table": {"property": {"row_size": row_size, "column_size": col_size}},
        "children": cell_ids
    })

    # 2. 添加所有单元格块和内容块
    for i, (cell_id, content_id) in enumerate(zip(cell_ids, content_ids)):
        row_idx, col_idx = i // col_size, i % col_size
        cell_content = clean_cell_content(rows_data[row_idx][col_idx])

        # 单元格块
        descendants.append({
            "block_id": cell_id,
            "block_type": 32,
            "table_cell": {},
            "children": [content_id]
        })

        # 内容块
        descendants.append({
            "block_id": content_id,
            "block_type": 2,
            "text": {"elements": [{"text_run": {"content": cell_content}}]},
            "children": []
        })

    # 发送请求
    url = f"{config['FEISHU_API_DOMAIN']}/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/descendant"
    response = requests.post(url, json={
        "index": -1,
        "children_id": [table_id],
        "descendants": descendants
    }, headers={"Authorization": f"Bearer {token}"})

    return table_id
```

### 块添加顺序策略

为避免块位置混乱，采用顺序添加策略：

```python
# ✅ 正确：逐块添加，保持原始顺序
for i, block in enumerate(blocks):
    if block.get("type") == "table":
        create_table_with_descendant_api(...)  # 表格使用专门API
    else:
        add_children_to_block(..., [block])     # 其他块正常添加
    time.sleep(0.05)  # 控制速率
```

### 相关文档
- 问题排查：`../feishu-doc-orchestrator/TROUBLESHOOTING.md`
- 主文档：`../feishu-doc-orchestrator/README.md`
