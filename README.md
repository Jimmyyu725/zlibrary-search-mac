# Z-Library：Mac 本地运行

## 使用
1. 编辑 `keywords.txt`，每行一个关键词，然后保存。
2. 双击桌面的「启动 Z-Library.command」。
3. 已接入你提供的登录 Cookie，会自动读取。本机凭证位置：`/Users/jingtianyu/Library/Application Support/ZLibrary/cookies.txt`（仅当前用户可读写）。若该文件不存在，才提示输入邮箱和密码。
4. CSV 保存在项目目录，书籍文件保存在 `downloads/`。再次运行时，已有 CSV 保留，新文件带时间戳。

程序保留原脚本的自动下载设置。只搜索时，在项目目录运行：

```sh
./.venv/bin/python zlibrary_search.py --search-only
```

本地检查：

```sh
./.venv/bin/python zlibrary_search.py --check
./.venv/bin/python test_local.py zlibrary_search.py
```

## 环境和验证
- 独立 Python 3.12 虚拟环境，不修改系统 Python。
- 依赖固定为 zlibrary 1.0.2；完整安装版本见 requirements.lock.txt。
- 本地测试使用模拟搜索结果和本机 HTTP 测试文件，不代表真实账号登录、在线搜索或书籍下载已成功。
- 上游接口说明：https://github.com/sertraline/zlibrary
- 桌面原脚本保持不变。修改副本、差异和验证记录见 evidence/VERIFICATION.txt。
- 回退脚本接收待恢复的副本路径，先保留当前副本，再恢复导入原版；不会删除下载文件。

## 本次联网结果
登录验证请求收到 HTTP 503；尚未确认 Cookie 有效，也未执行真实书籍下载。本地测试通过不等于线上服务可用。稍后可运行 `./.venv/bin/python zlibrary_search.py --check-login` 重试。

### 会话 Cookie 修复
已修复 Netscape 导出文件中 `expires=0` 被误判为过期的问题，并更新了本机凭证。再次联网验证仍收到 HTTP 503；无需反复导出相同 Cookie。修复及回退证据见 `evidence/session-cookie/VERIFICATION.txt`。

## 本机 Skill

已安装 `zlibrary-cli`，入口：`/Users/jingtianyu/.codex/skills/zlibrary-cli/SKILL.md`。

示例请求：

> 使用 $zlibrary-cli 搜索我指定的书，核对作者和语言后下载 EPUB；文件名不加数字编号或站点后缀。

Skill 源文件位于本项目 `skills/zlibrary-cli/`。按用户明确要求，账号邮箱与密码保存在包内 `.credentials.json`，权限为 600；不要把该文件内容输出到报告或公开发布。登录会话仍位于原有独立工具目录。

技能结构、离线行为、安装哈希及副本回退验证见 `evidence/skill-install/VERIFICATION.txt`。本次未新下载书籍。
