# 飞书文档创建技能 - 安装说明

将 Markdown 文件转换为飞书文档，支持25种飞书文档块类型。

## 环境要求

- Python 3.8+
- pip（Python包管理器）

## 安装步骤

### 1. 克隆或下载技能包

```bash
# 将技能包放到项目目录
# .claude/skills/feishu-doc-creator-skill/
```

### 2. 安装依赖

```bash
pip install requests lark-oapi playwright
```

### 3. 配置飞书应用

#### 3.1 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建自建应用
3. 获取 `App ID` 和 `App Secret`

#### 3.2 配置文件

复制配置模板：
```bash
cp .claude/skills/feishu-doc-creator-skill/feishu-config.env.template .claude/feishu-config.env
```

编辑 `.claude/feishu-config.env`，填入真实值：
```ini
FEISHU_APP_ID = "cli_xxx"
FEISHU_APP_SECRET = "xxxxxxxx"
```

### 4. 验证配置

```bash
python .claude/skills/feishu-doc-creator-skill/feishu-doc-creator-skill/scripts/check_config.py
```

应该看到：
```
[OK] FEISHU_APP_ID: cli_xxx...
[OK] FEISHU_APP_SECRET: xxxxxxxx...
[OK] API连接正常
配置检查通过！
```

## 使用方法

### 在 Claude Code 中使用

```
请帮我将 docs/example.md 转换为飞书文档
```

### 命令行使用

```bash
python .claude/skills/feishu-doc-creator-skill/feishu-doc-creator-skill/scripts/orchestrator.py docs/example.md "文档标题"
```

## 技能结构

```
claude/skills/
├── feishu-doc-creator-skill/        # 主编排技能
├── feishu-md-parser/               # Markdown解析
├── feishu-doc-creator-with-permission/  # 文档创建+权限
├── feishu-block-adder/             # 块添加
├── feishu-doc-verifier/            # 文档验证
└── feishu-logger/                  # 日志记录
```

## 支持的块类型

- **基础文本（11种）**：text, heading1-9, quote_container
- **列表（4种）**：bullet, ordered, todo, task
- **特殊块（5种）**：code, quote, callout, divider, image
- **AI块（1种）**：ai_template
- **高级块（5种）**：bitable, grid, sheet, table, board

**总计：25种块类型**

## 高级块使用说明

### 高亮块（Callout）

```markdown
:::info
信息提示
:::

:::warning
警告提示
:::
```

### 多维表格（Bitable）

用于创建结构化数据表格。

### 分栏（Grid）

将内容分成2-5列。

### 画板（Board）

用于绘图和白板协作。

## 测试

```bash
# 测试所有25种块类型
python .claude/skills/feishu-doc-creator-skill/feishu-doc-creator-skill/scripts/test_all_25_blocks.py
```

## 常见问题

### Q: 配置检查失败？

A: 请检查 `.claude/feishu-config.env` 文件是否正确配置，确保 APP_ID 和 APP_SECRET 正确。

### Q: 无法创建文档？

A:
1. 确认配置文件已正确设置
2. 运行配置检查工具验证
3. 检查网络连接

### Q: 权限问题？

A: 技能会自动处理权限，确保配置了 `FEISHU_AUTO_COLLABORATOR_ID`。

## 隐私数据

⚠️ **重要**：
- 配置文件 `feishu-config.env` 包含敏感信息，已加入 .gitignore
- 请勿将个人配置文件提交到 Git
- 分享项目前请删除或使用配置模板

## 开源协议

MIT License

## 支持

如有问题，请提交 Issue 或 Pull Request。
