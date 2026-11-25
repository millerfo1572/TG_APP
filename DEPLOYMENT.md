# TG_APP 迁移部署教程（新电脑 / 新 Telegram 管理员账号）

本教程用于在一台**全新的电脑**上，使用**另一个 Telegram 账号**（需是目标群的管理员或群主）从零部署本项目，并复用"批量剔除群成员"功能再次执行清理。

> ⚠️ **合规提醒**：本工具仅可用于你自己拥有管理权限的群组，并应遵守 Telegram 服务条款与当地法律。批量踢人有触发风控（FLOOD_WAIT / 限制操作 / 封号）的风险，请始终先用 `--dry-run` 演练、小批量执行，并控制频率。作者不对滥用后果负责。

---

## 目录

1. [整体思路](#1-整体思路)
2. [新电脑安装 Python](#2-新电脑安装-python)
3. [获取代码](#3-获取代码)
4. [安装依赖](#4-安装依赖)
5. [注册 Telegram API（获取 api_id / api_hash）](#5-注册-telegram-api获取-api_id--api_hash)
6. [配置 .env](#6-配置-env)
7. [首次登录生成会话文件](#7-首次登录生成会话文件)
8. [准备目标名单与群清单](#8-准备目标名单与群清单)
9. [批量清理完整流程](#9-批量清理完整流程)
10. [从旧电脑迁移要带走的文件](#10-从旧电脑迁移要带走的文件)
11. [常见问题](#11-常见问题)

---

## 1. 整体思路

项目通过 Telegram 官方 API（pyrogram）以"用户账号"身份登录，实时检测你当前是**管理员/群主**的群，然后按你提供的目标账户名单批量剔除成员。

迁移到新电脑 = 四件事：

1. 新电脑装好 Python 与依赖；
2. 用**新账号**注册 Telegram API，拿到 `api_id` / `api_hash`；
3. 配置 `.env` 并完成首次手机号登录（生成 `.session`）；
4. 准备目标名单（本仓库只提供脱敏模板，真实名单需自行填入或从旧电脑安全拷贝）。

> 关键：**凭据（.env）、会话（*.session）、真实名单（delete_members.json）都不在 Git 仓库里**，需要在新电脑本地生成/放置。

---

## 2. 新电脑安装 Python

### Windows（推荐，与开发环境一致）

1. 前往 <https://www.python.org/downloads/> 下载 **Python 3.11**（或 3.10+）安装包。
2. 安装时勾选 **Add Python to PATH**，然后点 Install Now。
3. 打开 PowerShell，验证：

```powershell
python --version
# 期望输出：Python 3.11.x
```

4. （可选）使用虚拟环境隔离依赖：

```powershell
cd D:\TG_APP
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> 若激活脚本报"禁止运行脚本"，先执行：`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### macOS / Linux

```bash
python3 --version          # 3.10+
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. 获取代码

```powershell
git clone https://github.com/<你的账号>/TG_APP.git
cd TG_APP
```

若没有 Git，可直接在 GitHub 页面点 **Code → Download ZIP** 解压。

---

## 4. 安装依赖

在项目根目录执行：

```powershell
pip install pyrogram python-dotenv openpyxl rich
```

可选加速（纯 Python 的加密较慢，装上会明显提速）：

```powershell
pip install TgCrypto
```

验证：

```powershell
python -c "import pyrogram, dotenv, openpyxl, rich; print('deps ok')"
```

---

## 5. 注册 Telegram API（获取 api_id / api_hash）

**注意：这是注册"API 应用"，不是注册 Telegram 账号。** 每个 Telegram 账号都需要自己的一组 `api_id` / `api_hash`。

1. 用你要在新电脑上使用的 Telegram 账号登录网页版 <https://my.telegram.org/apps>
2. 点击 **API Development tools**。
3. 填写表单：
   - **App title**：随意，如 `TG_APP`
   - **Short description**：随意，如 `group management tool`
   - **Platform**：选 `Desktop` 或其他
   - **Description / URL**：可留空或简短填写
4. 提交后页面会显示：
   - `App api_id`（一串数字）
   - `App api_hash`（一串 32 位十六进制字符串）
5. 妥善保存这两个值，下一步要用。**不要提交到 Git。**

---

## 6. 配置 .env

仓库中提供脱敏模板 `.env.example`。在项目根目录复制并改名：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填入第 5 步得到的值：

```dotenv
API_ID=12345678
API_HASH=0123456789abcdef0123456789abcdef
SESSION_NAME=my_tg_account
PROXY_SCHEME=
PROXY_HOST=
PROXY_PORT=
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `API_ID` | 是 | 第 5 步获得的数字 |
| `API_HASH` | 是 | 第 5 步获得的 32 位字符串 |
| `SESSION_NAME` | 是 | 会话文件名前缀，随意英文，如 `my_tg_account` |
| `PROXY_SCHEME/HOST/PORT` | 否 | 需要代理才填，如 `http` / `127.0.0.1` / `7890`；不需要就留空 |

> `.env` 已被 `.gitignore` 忽略，不会被上传。**切勿把真实的 api_hash 发到聊天群、截图或提交到公开仓库。**

---

## 7. 首次登录生成会话文件

首次运行会要求你用**新账号**登录（手机号 → Telegram App 里的验证码，可能还要两步验证密码）：

```powershell
python check_session.py
```

按提示输入：
1. 手机号（带国家区号，如 `+8613800138000`）
2. Telegram 客户端收到的验证码
3. 如设置了两步验证，再输入密码

成功后会打印：

```
✅ Session 有效！
ID: ...
Name: ...
Username: @...
```

并在当前目录生成 `<SESSION_NAME>.session`（如 `my_tg_account.session`）。这个文件等于你的登录凭证，**已被 .gitignore 忽略，不要外传**。

> 登录时如提示 `PHONE_NUMBER_FLOOD`（号码请求太频繁），等几分钟到几小时再试，或改用已导出的 session 文件（见[第 10 节](#10-从旧电脑迁移要带走的文件)）。

---

## 8. 准备目标名单与群清单

项目的数据文件都不会随仓库上传，需按下面方式准备。

### 8.1 待删除名单 `delete_members.json`

模板见 `delete_members.example.json`，结构是 `"用户名": "用户ID"` 的 JSON 对象：

```json
{
  "@example_user_1": "10000000001",
  "@example_user_2": "10000000002"
}
```

复制模板并填入真实目标：

```powershell
Copy-Item delete_members.example.json delete_members.json
# 然后用文本编辑器打开 delete_members.json，替换为真实用户名和用户 ID
```

说明：
- 值是** Telegram 数字用户 ID**（字符串形式），不是用户名。
- 同一个 ID 可对应多个用户名，程序会按 ID 去重并合并标注（如 `@a/@b`）。
- 如何获取用户 ID：在目标群成员列表查看，或用其它 Telegram 工具查询；填错 ID 不会误删，只是不命中。

### 8.2 目标群清单（两种方式，二选一）

**方式 A（推荐）：自动检测管理群**
`admin_batch_cleanup.py` 会实时检测你在所有群里是否为管理员/群主，自动生成 `admin_chat_ids.json`，无需手工准备。

**方式 B：手工指定群**
复制模板 `target_chat_ids.example.json` 为 `target_chat_ids.json`，填入群 ID 数组：

```json
[-1001234567890, -1009876543210]
```

群 ID 是负数（超级群形如 `-100xxxxxxxxxx`，普通群形如 `-xxxxxxxxx`）。

### 8.3（可选）Excel 表格

仅在使用 `export_tg_groups.py` / `compare_groups.py` 时需要：

| 文件 | A 列含义 | 其它列 |
|---|---|---|
| `target_groups.xlsx` | 目标群 ID | — |
| `my_tg_groups.xlsx` | 你已加入的群 ID | B=群属性（GROUP/SUPERGROUP），C=群名称 |
| `target_groups_compare.xlsx` | 比较结果（程序生成） | E=是否已在群组，未加入红底 |

真实 xlsx 均被 `.gitignore` 忽略，仓库不提供；需要时按上述列名自行创建。

---

## 9. 批量清理完整流程

### 9.1 方式 A：自动检测管理群并批量清理（推荐）

```powershell
# 1) 先演练：检测管理群 + 预览命中名单，不改动任何成员
python admin_batch_cleanup.py --dry-run

# 2) 确认输出中的命中名单无误后，正式执行（默认不限人数）
python admin_batch_cleanup.py

# 3) 如需限制单次规模，分批执行：
python admin_batch_cleanup.py --max-kicks 50
```

程序会：
1. 扫描你所在的所有群，筛出你是管理员/群主的群（打印 `[ADMINISTRATOR]` / `[OWNER]`）；
2. 导出 `admin_chat_ids.json`；
3. 在这些群里查找 `delete_members.json` 的命中成员；
4. 逐个剔除并打印 `✅ @xxx (ID: ...) 已剔除群组`；
5. 汇总打印：`已从 XX 个群组中剔除目标`。

### 9.2 方式 B：对指定群清理

```powershell
python clean_group_members.py --dry-run          # 演练
python clean_group_members.py                    # 执行
python clean_group_members.py --max-kicks 50     # 限制单次 50 人
```

### 9.3 常用参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--dry-run` | 关闭 | 演练模式，只预览不删除 |
| `--max-kicks` | 0 | 单次上限，0=不限，正数=上限（负数报错） |
| `--members` | `delete_members.json` | 指定名单文件 |
| `--chats` | `target_chat_ids.json` | 指定群配置（仅 clean_group_members.py） |
| `--admins-out` | `admin_chat_ids.json` | 管理群清单输出路径（仅 admin_batch_cleanup.py） |

### 9.4 风控与限速

- 默认每次剔除后随机等待 **3~5 秒**，每累计 **20 人**额外暂停 **30 秒**。
- `build_client()` 设置 `sleep_threshold=60`，自动等待最长 60 秒的 FLOOD_WAIT。
- 若日志频繁出现 `FLOOD_WAIT` 或账号受限，建议：
  - 用 `--max-kicks 30` 分批，间隔数小时再跑；
  - 增大 `tg_member_cleaner.py` 中 `clean_chats()` 的 `min_delay/max_delay`；
  - 暂停一段时间，避免连续批量操作。
- 演练模式（`--dry-run`）零等待、零副作用，可放心反复核对。

---

## 10. 从旧电脑迁移要带走的文件

仓库里**没有**以下文件，请通过安全渠道（加密 U 盘、私有网盘、密码管理器等）从旧电脑拷贝到新电脑对应目录：

| 文件 | 作用 | 注意 |
|---|---|---|
| `.env` | 新账号的 API 凭据 | 也可在新电脑按第 5、6 步重新生成，不一定要拷贝 |
| `<SESSION_NAME>.session` | 登录会话 | 拷贝后无需验证码即可登录；**等同于账号密码，务必保密** |
| `delete_members.json` | 本批待删除目标账户名单 | 若新电脑要删同一批人，必须拷贝；或按第 8.1 节重新填写 |
| `target_chat_ids.json` / `admin_chat_ids.json` | 群清单 | 也可由 `admin_batch_cleanup.py` 自动生成 |

不建议带走：`*.xlsx`（含真实群名）、`report_groups.md`、`*.log`（含真实运行记录），它们对批量删除功能非必需。

---

## 11. 常见问题

**Q：运行时提示 `TgCrypto is missing`？**
A：只是变慢，不影响功能。执行 `pip install TgCrypto` 可加速。

**Q：`FLOOD_WAIT_X - A wait of N seconds is required`？**
A：Telegram 限流，程序会自动等待（最长 60 秒）后继续；若很频繁请按 9.4 节降低频率。

**Q：某群提示 `USER_NOT_PARTICIPANT` / `CHANNEL_INVALID`？**
A：说明该账号已不在该群，或群类型不支持；程序会跳过，不影响其它群。

**Q：为什么检测到的管理群数量和旧电脑不一样？**
A：管理群是按当前登录账号实时检测的；换了账号，权限自然不同。请确认新账号确实加入了目标群且有管理员权限（能踢人）。

**Q：中文/emoji 在 PowerShell 里乱码？**
A：执行前设置 UTF-8：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; chcp.com 65001
```

**Q：如何确认配置正确？**
A：依次运行 `python check_session.py`（看账号信息）→ `python admin_batch_cleanup.py --dry-run`（看检测到的管理群与命中名单）。

---

回到项目主文档：[README.md](README.md)
