# Telegram 群组管理工具集

一组基于 pyrogram 的 Telegram 群组管理脚本：会话检查、群组导出、目标群比较、管理员身份检测、群成员批量剔除。

> ⚠️ **重要**：`clean_group_members.py` 和 `admin_batch_cleanup.py` **不带参数运行即真实踢人**；只有加 `--dry-run` 才是演练（只预览、不删除）。请先用 `--dry-run` 确认命中名单后再真实执行。

> 📘 **迁移部署**：需要在新电脑/新 Telegram 账号上重新部署？请阅读 [DEPLOYMENT.md](DEPLOYMENT.md)（含 Python 安装、API 注册、首次登录、目标名单准备与完整批量删除流程）。

> 🔒 **合规提示**：本工具仅用于你自己拥有管理权限的群组，请遵守 Telegram 服务条款与当地法律，避免滥用导致账号受限或封号。作者不对滥用后果负责。

---

## 1. 环境配置

- Python 3.11：`D:\conda\envs\py311\python.exe`
- 依赖：`pyrogram`、`python-dotenv`、`openpyxl`、`rich`（均已安装）
- 在项目根目录创建 `.env`，内容：

```dotenv
API_ID=你的api_id
API_HASH=你的api_hash
SESSION_NAME=my_tg_account
PROXY_SCHEME=http          # 不需要代理可留空或删除下面两项
PROXY_HOST=127.0.0.1
PROXY_PORT=7890
```

- Windows PowerShell 推荐先切换到 UTF-8，避免中文/emoji 乱码：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; chcp.com 65001
```

下文命令均用 `python` 代指 `D:\conda\envs\py311\python.exe`，且默认在项目目录 `d:\workbuddyspace\TG_App` 下执行。

---

## 2. 脚本清单

| 脚本 | 作用 | 默认行为 |
|---|---|---|
| `check_session.py` | 验证 `.env` 会话有效性，打印当前账号信息 | 只读 |
| `export_tg_groups.py` | 导出所有 GROUP/SUPERGROUP 到 `my_tg_groups.xlsx` | 只读 |
| `compare_groups.py` | 比较目标群表与已加入群表，生成标记结果 | 只读 |
| `test主对话列表.py` | 打印主列表/置顶/自定义文件夹，并显示管理员身份 | 只读 |
| `tg_member_cleaner.py` | 核心模块（供其他脚本 import），含管理群检测、命中检测、踢人、限速 | 一般不直接运行 |
| `clean_group_members.py` | 对指定群配置批量剔除名单成员 | **默认真实执行** |
| `admin_batch_cleanup.py` | 实时检测管理群 → 导出清单 → 批量剔除 | **默认真实执行** |

---

## 3. 各脚本用法

### 3.1 `check_session.py` — 验证会话

```powershell
python check_session.py
```

输出：Session 是否有效、账号 ID、名称、用户名。无文件产物。

### 3.2 `export_tg_groups.py` — 导出所在群组

```powershell
python export_tg_groups.py
```

- 扫描全部对话，只保留 `GROUP`（普通群）和 `SUPERGROUP`（超级群）。
- 产物：`my_tg_groups.xlsx`，列为 `群ID` / `群属性` / `群名称`，含表头样式与冻结首行。
- 同时打印总对话数、群组数和执行耗时。

### 3.3 `compare_groups.py` — 比较目标群与已加入群

前置：`target_groups.xlsx`（A 列为群 ID）与 `my_tg_groups.xlsx`（A 列为群 ID）都存在。

```powershell
python compare_groups.py
```

- 以 `target_groups.xlsx` 为基准比较 A 列 ID。
- 产物：`target_groups_compare.xlsx`，E 列填写"已加入/未加入"，未加入的单元格红底填充。
- 打印已加入数、未加入数。

### 3.4 `test主对话列表.py` — 会话与管理员身份检测

```powershell
python test主对话列表.py
```

- 打印三段：主对话列表、置顶对话（`folder_id=1`）、自定义聊天文件夹。
- 每行含 `群ID | 类型 | 管理员属性（群主/管理员/否/-） | 名称`。
- 末尾汇总群组管理员统计。
- 无文件产物。

### 3.5 `tg_member_cleaner.py` — 核心模块（供 import）

一般不直接运行，供其他脚本调用。主要接口：

```python
from tg_member_cleaner import (
    build_client,            # 构造 Client（.env + 代理，sleep_threshold=60）
    load_delete_members,     # 加载待删除名单（按用户 ID 去重、合并用户名）
    load_target_chats,       # 加载群 ID 数组
    export_admin_chats,      # 实时检测管理员/群主身份的群，导出 JSON
    find_members_in_chat,    # 检测群内命中的名单成员（跳过群主/管理员）
    kick_member,             # 踢出单个成员（超级群 ban+unban；普通群仅 ban）
    clean_chats,             # 遍历群：execute=False 预览；execute=True 带限速执行
)
```

`clean_chats()` 的限速参数（仅 `execute=True` 生效）：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `min_delay` / `max_delay` | 3 / 5 | 每次剔除后的随机等待秒数 |
| `pause_every` | 20 | 每累计多少次剔除长暂停一次 |
| `pause_seconds` | 30 | 长暂停秒数 |
| `max_kicks` | 0 | 单次剔除上限：`0`=不限制（默认，一次跑完所有命中）；正数=达到后提前停止 |

汇总输出示例：
```
📊 汇总：检测群数 81 | 命中 382 | 成功剔除 382 | 失败 0 | 预览跳过 0 | 已从 79 个群组中剔除目标
```
其中"已从 XX 个群组中剔除目标"统计的是**本次至少有 1 人成功剔除的群数量**（不是人次）。

### 3.6 `clean_group_members.py` — 指定群批量清理

```powershell
python clean_group_members.py --dry-run    # 演练：只预览命中
python clean_group_members.py              # 默认：真实执行剔除（不限人数）
python clean_group_members.py --max-kicks 50   # 限制单次最多剔除 50 人
python clean_group_members.py --members 名单.json --chats 群配置.json
```

参数：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `--dry-run` | 关闭 | 演练模式，不执行删除 |
| `--max-kicks` | 0 | 单次剔除上限，0=不限制，正数=设上限（负数会报错） |
| `--members` | `delete_members.json` | 待删除名单 JSON |
| `--chats` | `target_chat_ids.json` | 目标群 ID 配置 JSON |

### 3.7 `admin_batch_cleanup.py` — 管理群批量清理（组合脚本）

```powershell
python admin_batch_cleanup.py --dry-run    # 演练：检测管理群 + 预览命中
python admin_batch_cleanup.py              # 默认：检测管理群 + 真实执行批量剔除（不限人数）
python admin_batch_cleanup.py --max-kicks 50   # 限制单次最多剔除 50 人
python admin_batch_cleanup.py --members 名单.json --admins-out 管理群.json
```

流程：实时检测"我是管理员/群主"的群 → 导出 `admin_chat_ids.json` → 加载名单 → 批量剔除（或 `--dry-run` 预览）。

参数：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `--dry-run` | 关闭 | 演练模式，不执行删除 |
| `--max-kicks` | 0 | 单次剔除上限，0=不限制，正数=设上限（负数会报错） |
| `--members` | `delete_members.json` | 待删除名单 JSON |
| `--admins-out` | `admin_chat_ids.json` | 管理群清单输出路径 |

实测：检测到 81 个管理群，名单 17 人（去重后），预览命中 382 人次。真实执行默认不限人数，受风控限速约束（3~5 秒间隔、每 20 人暂停 30 秒）。

---

## 4. 数据文件说明

| 文件 | 格式 | 作用 |
|---|---|---|
| `delete_members.json` | `{用户名: 用户ID}` | 待删除名单；按 ID 去重，重复 ID 的多个用户名合并显示 |
| `target_chat_ids.json` | 群 ID 数组 | `clean_group_members.py` 的默认目标群配置 |
| `admin_chat_ids.json` | 群 ID 数组 | `export_admin_chats()` 导出的管理群清单，可被清理脚本直接复用 |
| `target_groups.xlsx` | Excel | 目标群表，A 列为群 ID |
| `my_tg_groups.xlsx` | Excel | 已加入群表，A 列为群 ID |
| `target_groups_compare.xlsx` | Excel | 比较结果，E 列标记是否加入，未加入红底 |
| `report_groups.md` | Markdown | `test主对话列表.py` 的历史运行日志（仅供查阅，不作为程序输入） |

---

## 5. 典型工作流

```powershell
# 0) 确认会话可用
python check_session.py

# 1) 导出所在群组
python export_tg_groups.py

# 2) 比较目标群（把要核对的群 ID 放入 target_groups.xlsx 的 A 列）
python compare_groups.py

# 3) 查看会话、置顶、文件夹及管理员身份
python test主对话列表.py

# 4a) 对指定群清理：先演练确认命中名单
python clean_group_members.py --dry-run
# 4b) 确认无误后真实执行
python clean_group_members.py

# 5a) 管理群批量清理：先演练
python admin_batch_cleanup.py --dry-run
# 5b) 确认无误后真实执行
python admin_batch_cleanup.py
```

---

## 6. 风控与安全说明

- 核心模块限速：每次剔除后随机等待 3~5 秒，每累计 20 次额外暂停 30 秒；**单次剔除上限默认不限制**（`max_kicks=0`，可用 `--max-kicks 正数` 自行设上限，或在 `clean_chats()` 调参）。
- `build_client()` 的 `sleep_threshold=60` 让 pyrogram 自动等待最长 60 秒的 `FLOOD_WAIT`，避免因超过默认 15 秒阈值而抛错。
- 演练模式（`--dry-run`）**零等待、零副作用**，可放心用于核对名单。
- 踢人语义：超级群用 `ban_chat_member` + `unban_chat_member`（移出但可再次加入）；普通群仅 `ban_chat_member`（普通群不支持 unban）。
- 跳过群主（OWNER）和管理员（ADMINISTRATOR），不会踢有管理权限的成员。
- 历史日志中曾出现 17~21 秒 `FLOOD_WAIT`，如遇风控加重，建议增大 `min_delay/max_delay` 或用 `--max-kicks 50` 限制单次规模、分多次执行。

---

## 7. 数据脱敏与示例文件

公开仓库**不包含任何真实数据**：`.env`（API 凭据）、`*.session`（登录会话）、`delete_members.json`（真实目标名单）、`admin_chat_ids.json` / `target_chat_ids.json`（真实群 ID）、所有 `*.xlsx`（含真实群名）、`*.log` 与 `report_groups.md` 均已被 `.gitignore` 忽略。

仓库提供以下**脱敏模板**（值为假数据，字段名与真实文件一致），复制后按需填写即可：

| 示例文件 | 复制为 | 用途 |
|---|---|---|
| `.env.example` | `.env` | Telegram API 凭据与代理配置 |
| `delete_members.example.json` | `delete_members.json` | 待删除目标账户名单（`@用户名`: 用户 ID） |
| `target_chat_ids.example.json` | `target_chat_ids.json` | 手工指定的目标群 ID 数组 |
| `admin_chat_ids.example.json` | `admin_chat_ids.json` | 管理群清单（通常由脚本自动生成，无需手填） |

新电脑从零部署、注册 API、首次登录、复用目标名单的完整步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

---

## 8. 注意事项

- 所有脚本读写文件均基于脚本所在目录，`target_groups.xlsx` 等数据文件需放在同一目录。
- `report_groups.md` 只是历史日志输出，程序不读取它；管理群清单以实时 API 检测为准。
- 真实执行前务必用 `--dry-run` 预览，避免误删。
