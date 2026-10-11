#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity 界面全量动态汉化注入器

特性：
  1. 支持单次立即注入与 --watch 常驻守护模式。
  2. 结合 CDP Page.addScriptToEvaluateOnNewDocument 与 Runtime.evaluate：
     页面刷新、切换对话、路由跳转时浏览器内核级自动注入，彻底杜绝「汉化掉了」。
  3. 兼容 macOS 与 Linux 平台路径自适应。
  4. 多窗口同时注入，无缝覆盖所有打开的工作区。
  5. 词典文件热重载：编辑 zh-CN.json 后守护进程自动检测并生效。
  6. 增强动态文案规则（思考耗时、执行状态、消息提示等）。
"""

import os
import sys
import json
import time
import asyncio
import urllib.request
import websockets

def get_config_dirs():
    dirs = [
        os.path.expanduser("~/Library/Application Support/Antigravity"),
        os.path.expanduser("~/.config/Antigravity"),
    ]
    if "APPDATA" in os.environ:
        dirs.append(os.path.join(os.environ["APPDATA"], "Antigravity"))
    if "LOCALAPPDATA" in os.environ:
        dirs.append(os.path.join(os.environ["LOCALAPPDATA"], "Antigravity"))
    dirs.append(os.path.expanduser("~/.Antigravity"))
    return dirs

DICT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zh-CN.json")


def load_dictionary():
    if not os.path.exists(DICT_FILE):
        print(f"[错误] 词典文件不存在: {DICT_FILE}")
        sys.exit(1)
    with open(DICT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("translations", {})


def get_dict_mtime():
    try:
        return os.path.getmtime(DICT_FILE)
    except OSError:
        return 0


def get_devtools_port(strict=True):
    for d in get_config_dirs():
        pf = os.path.join(d, "DevToolsActivePort")
        if os.path.exists(pf):
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    port = f.readline().strip()
                    if port:
                        return port
            except Exception:
                pass
    if strict:
        print("[错误] 未检测到正在运行的 Antigravity。请先启动 Antigravity 客户端！")
        sys.exit(1)
    return None


def build_js(dict_data):
    """生成注入脚本。词典以 JSON 字面量内嵌，避免转义问题。"""
    dict_json = json.dumps(dict_data, ensure_ascii=False)
    return r"""
(() => {
    const dict = %s;

    /* ---------- 1. 挂载到 window，便于调试与热更新 ---------- */
    window.__antigravityZhDict = dict;
    window.__antigravityZh = {
        dict,
        version: 1,
        translated: 0,
        skippedConversation: 0
    };

    /* ---------- 2. 不该被翻译的容器 ---------- */
    // 对话正文、代码、终端、输入框内容属于「用户/助手内容」，不能改写
    const SKIP_TAGS = new Set([
        'SCRIPT', 'STYLE', 'CODE', 'PRE', 'KBD', 'SAMP', 'TEXTAREA',
        'NOSCRIPT', 'SVG', 'CANVAS', 'IFRAME', 'MATH'
    ]);

    function isSkipped(el) {
        if (!el || el.nodeType !== 1) return true;
        if (SKIP_TAGS.has(el.tagName)) return true;
        // contenteditable 输入区（对话框）整体跳过
        if (el.isContentEditable) return true;
        // 对话消息区 / 代码视图：Antigravity 用这些标记承载用户内容
        if (el.dataset && el.dataset.antigravityZhSkip === '1') return true;
        const cls = el.className;
        if (typeof cls === 'string' && cls) {
            if (/(^|\s)(markdown-body|monaco-editor|cm-editor|cm-content|prose|message-content|chat-message|conversation-message|artifact-content|trajectory-content)(\s|$)/.test(cls)) return true;
        }
        return false;
    }

    // 对话区根节点：优先跳过「消息列表」子树
    function isConversationRoot(el) {
        if (!el || el.nodeType !== 1 || !el.getAttribute) return false;
        const al = el.getAttribute('aria-label') || '';
        const role = el.getAttribute('role') || '';
        if (role === 'log' || (role === 'list' && /message|conversation/i.test(al))) return true;
        return /^(Conversation|Messages|Chat transcript|对话)/i.test(al) && role !== 'menu';
    }

    /* ---------- 3. 动态串规则（正则 → 生成中文） ---------- */
    const DYNAMIC = [
        // Thought for 11s / 1m 20s
        [/^Thought for\s+(.+)$/,
            m => '思考耗时 ' + m[1].replace(/(\d+)\s*s\b/g, '$1 秒')
                                   .replace(/(\d+)\s*m\b/g, '$1 分钟')
                                   .replace(/(\d+)\s*h\b/g, '$1 小时')],
        // Thinking...
        [/^Thinking\.\.\.$/, () => '思考中...'],
        [/^Thinking$/, () => '思考中'],
        // Analyzed
        [/^Analyzed$/, () => '已分析'],
        // No more older messages
        [/^No more older messages$/, () => '没有更早的消息了'],
        // Exploring file, running commands
        [/^Exploring file,\s*running commands$/, () => '探索文件中，正在执行命令'],
        // Worked for 2m / Worked for 1h 30m
        [/^Worked for\s+(.+)$/,
            m => '耗时 ' + m[1].replace(/(\d+)\s*s\b/g, '$1 秒')
                                   .replace(/(\d+)\s*m\b/g, '$1 分钟')
                                   .replace(/(\d+)\s*h\b/g, '$1 小时')
                                   .replace(/(\d+)\s*d\b/g, '$1 天')],
        // Working...
        [/^Working\.\.\.$/, () => '正在执行...'],
        [/^Working$/, () => '正在执行'],
        // 3 files changed / 1 file changed
        [/^(\d+)\s+files?\s+changed$/, m => `${m[1]} 个文件已变更`],
        // 5m ago / 2h ago / 3d ago
        [/^(\d+)\s*(s|m|h|d)\s+ago$/, m => {
            const u = { s: '秒', m: '分钟', h: '小时', d: '天' }[m[2]];
            return `${m[1]} ${u}前`;
        }],
        // 刚刚
        [/^just now$/i, () => '刚刚'],
        // Load older messages, showing 44 of 229
        [/^Load older messages,\s*showing\s+(\d+)\s+of\s+(\d+)$/,
            m => `加载更早的消息（已显示 ${m[1]} / ${m[2]}）`],
        // Select model, current: Gemini 3.8 Flash High
        [/^Select model,\s*current:\s*(.+)$/, m => `选择模型（当前：${m[1]}）`],
        // Fold lines 2-290
        [/^Fold lines\s+(\d+)\s*-\s*(\d+)$/, m => `折叠第 ${m[1]}-${m[2]} 行`],
        // Remove xxx.svg / 附件名
        [/^Remove\s+(.+)$/, m => `移除 ${m[1]}`],
        // showing 44 of 229
        [/^showing\s+(\d+)\s+of\s+(\d+)$/, m => `已显示 ${m[1]} / ${m[2]}`],
        // N minutes ago 变体
        [/^(\d+)\s+minutes?\s+ago$/, m => `${m[1]} 分钟前`],
        [/^(\d+)\s+hours?\s+ago$/, m => `${m[1]} 小时前`],
        [/^(\d+)\s+days?\s+ago$/, m => `${m[1]} 天前`],
        // Today / Yesterday
        [/^Today$/i, () => '今天'],
        [/^Yesterday$/i, () => '昨天'],
        // Close (Esc) 之类的快捷键提示
        [/^Close\s*\(Esc\)$/, () => '关闭 (Esc)'],
        // Run command: xxx
        [/^Run command:\s*(.+)$/, m => `执行命令: ${m[1]}`],
        [/^Running command$/, () => '正在执行命令']
    ];

    /* ---------- 4. 单串翻译 ---------- */
    function translate(text) {
        if (!text) return null;
        const lead = text.match(/^\s*/)[0];
        const tail = text.match(/\s*$/)[0];
        const core = text.trim();
        if (!core) return null;

        // 精确命中
        if (Object.prototype.hasOwnProperty.call(dict, core)) {
            return lead + dict[core] + tail;
        }
        // 动态规则
        for (const [re, fn] of DYNAMIC) {
            const m = core.match(re);
            if (m) return lead + fn(m) + tail;
        }
        return null;
    }

    const ATTRS = ['placeholder', 'title', 'aria-label', 'data-tooltip', 'alt'];

    /* ---------- 5. 遍历 ---------- */
    function handleTextNode(node) {
        const parent = node.parentNode;
        if (!parent || parent.nodeType !== 1) return;
        if (isSkipped(parent)) return;
        let p = parent, depth = 0;
        while (p && depth++ < 12) {
            if (isSkipped(p) || isConversationRoot(p)) return;
            p = p.parentNode;
        }
        const out = translate(node.nodeValue);
        if (out !== null && out !== node.nodeValue) {
            node.nodeValue = out;
            window.__antigravityZh.translated++;
        }
    }

    function handleAttrs(el) {
        if (isSkipped(el)) return;
        let p = el, depth = 0;
        while (p && depth++ < 12) {
            if (isConversationRoot(p)) return;
            p = p.parentNode;
        }
        for (const a of ATTRS) {
            const v = el.getAttribute && el.getAttribute(a);
            if (!v) continue;
            const out = translate(v);
            if (out !== null && out !== v) {
                el.setAttribute(a, out);
                window.__antigravityZh.translated++;
            }
        }
    }

    function walk(node, isRoot) {
        if (!node || node.nodeType === undefined) return;
        if (node.nodeType === 1) {
            if (isSkipped(node)) return;
            if (!isRoot && isConversationRoot(node)) { window.__antigravityZh.skippedConversation++; return; }
            handleAttrs(node);
        } else if (node.nodeType === 3) {
            handleTextNode(node);
            return;
        }
        for (let c = node.firstChild; c; c = c.nextSibling) walk(c, false);
    }

    window.__antigravityZhWalk = () => {
        if (document.body) walk(document.body, true);
    };

    /* ---------- 6. 首次全量扫描 ---------- */
    if (document.body) {
        walk(document.body, true);
    } else {
        document.addEventListener('DOMContentLoaded', () => walk(document.body, true), { once: true });
    }

    /* ---------- 7. 监听动态更新 ---------- */
    if (window.__antigravityZhObserver) {
        window.__antigravityZhObserver.disconnect();
    }
    const observer = new MutationObserver(mutations => {
        for (const m of mutations) {
            if (m.type === 'childList') {
                m.addedNodes.forEach(n => walk(n, false));
            } else if (m.type === 'characterData') {
                handleTextNode(m.target);
            } else if (m.type === 'attributes' && m.target) {
                handleAttrs(m.target);
            }
        }
    });

    const targetNode = document.body || document.documentElement;
    if (targetNode) {
        observer.observe(targetNode, {
            childList: true,
            subtree: true,
            characterData: true,
            attributes: true,
            attributeFilter: ATTRS
        });
        window.__antigravityZhObserver = observer;
    }

    return JSON.stringify({
        ok: true,
        entries: Object.keys(dict).length,
        translated: window.__antigravityZh.translated,
        skipped: window.__antigravityZh.skippedConversation
    });
})();
""" % dict_json


async def inject_page_via_cdp(ws_url, dict_data):
    """通过 WebSocket 连接单个页面目标，注入汉化脚本及新文档生命周期监听。"""
    js_code = build_js(dict_data)
    async with websockets.connect(ws_url, max_size=None) as ws:
        # 1. 注册新文档自动注入（页面刷新或路由导航时内核级自动运行）
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.recv()

        await ws.send(json.dumps({
            "id": 2,
            "method": "Page.addScriptToEvaluateOnNewDocument",
            "params": {"source": js_code}
        }))
        await ws.recv()

        # 2. 等待 React DOM 渲染后执行当前页面的热替换
        for _ in range(30):
            probe = {
                "id": 100,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "!!document.body && document.body.innerText.length > 50",
                    "returnByValue": True,
                },
            }
            await ws.send(json.dumps(probe))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3)
                if json.loads(raw).get("result", {}).get("result", {}).get("value"):
                    break
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(0.5)

        # 3. 对当前 DOM 立即执行注入
        eval_msg = {
            "id": 101,
            "method": "Runtime.evaluate",
            "params": {
                "expression": js_code,
                "returnByValue": True,
                "awaitPromise": False,
            },
        }
        await ws.send(json.dumps(eval_msg))
        raw = await ws.recv()
        result = json.loads(raw)
        res = result.get("result", {}).get("result", {})
        val = res.get("value")
        if val:
            try:
                return json.loads(val)
            except Exception:
                pass
        return {"ok": True, "translated": 0}


async def check_page_status(ws_url):
    """检测页面当前是否处于汉化就绪状态。"""
    try:
        async with websockets.connect(ws_url, max_size=None) as ws:
            check_msg = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "!!(window.__antigravityZh && window.__antigravityZh.version === 1)",
                    "returnByValue": True,
                },
            }
            await ws.send(json.dumps(check_msg))
            raw = await asyncio.wait_for(ws.recv(), timeout=2.5)
            res = json.loads(raw)
            return bool(res.get("result", {}).get("result", {}).get("value"))
    except Exception:
        return False


async def refresh_page_walk(ws_url):
    """唤醒页面重刷遍历，捕捉新渲染的 React 组件。"""
    try:
        async with websockets.connect(ws_url, max_size=None) as ws:
            msg = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "window.__antigravityZhWalk ? (window.__antigravityZhWalk(), true) : false",
                    "returnByValue": True,
                },
            }
            await ws.send(json.dumps(msg))
            await asyncio.wait_for(ws.recv(), timeout=2.0)
    except Exception:
        pass


def get_active_targets(port):
    """获取所有非开屏过渡的 Antigravity 页面目标。"""
    url = f"http://127.0.0.1:{port}/json"
    try:
        with urllib.request.urlopen(url, timeout=2.5) as resp:
            targets = json.loads(resp.read().decode())
        pages = [t for t in targets if t.get("type") == "page" and not t.get("url", "").startswith("data:")]
        return pages
    except Exception:
        return []


async def inject_translation(dict_data):
    """单次立即注入所有打开的窗口。"""
    port = get_devtools_port(strict=True)
    pages = get_active_targets(port)
    if not pages:
        print("[错误] 未找到处于活动状态的 Antigravity 界面窗口。")
        return False

    success = False
    for p in pages:
        ws_url = p.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        try:
            info = await inject_page_via_cdp(ws_url, dict_data)
            print(f"✅ [成功] 已注入窗口: {p.get('title', '主界面')}，翻译 {info.get('translated', 0)} 处文案。")
            success = True
        except Exception as e:
            print(f"[警告] 注入窗口 {p.get('title')} 失败: {e}")

    return success


async def watch_daemon():
    """常驻守护进程：全自动侦测、热注入、重载以及内核级保活。"""
    dict_data = load_dictionary()
    last_dict_mtime = get_dict_mtime()
    print(f"[*] 守护进程已启动，初始词典词条: {len(dict_data)}", flush=True)

    tick_counter = 0
    while True:
        try:
            # 1. 检查词典文件是否有更新，热重载
            cur_mtime = get_dict_mtime()
            if cur_mtime > last_dict_mtime:
                last_dict_mtime = cur_mtime
                dict_data = load_dictionary()
                print(f"[!] 检测到词典更新 ({time.strftime('%H:%M:%S')})，已重新加载 {len(dict_data)} 条词条。", flush=True)
                # 触发全量重注
                port = get_devtools_port(strict=False)
                if port:
                    for p in get_active_targets(port):
                        ws = p.get("webSocketDebuggerUrl")
                        if ws:
                            await inject_page_via_cdp(ws, dict_data)

            # 2. 检查调试端口与活跃页面
            port = get_devtools_port(strict=False)
            if not port:
                await asyncio.sleep(2.0)
                continue

            pages = get_active_targets(port)
            tick_counter += 1

            for p in pages:
                ws = p.get("webSocketDebuggerUrl")
                if not ws:
                    continue

                is_zh_active = await check_page_status(ws)
                if not is_zh_active:
                    # 发现页面未汉化（或页面刷新、导航发生）
                    print(f"[+] 检测到新页面或重新加载，正在热注入: {p.get('title', '未知窗口')} ({time.strftime('%H:%M:%S')})", flush=True)
                    try:
                        info = await inject_page_via_cdp(ws, dict_data)
                        print(f"    ↳ 注入成功，已汉化 {info.get('translated', 0)} 处。", flush=True)
                    except Exception as err:
                        print(f"    ↳ 注入出现异常: {err}", flush=True)
                elif tick_counter % 3 == 0:
                    # 页面已汉化，每隔 6 秒轻量唤醒一次遍历，确保异步加载的新组件被汉化
                    await refresh_page_walk(ws)

        except Exception as e:
            # 守护进程捕获所有异常，保障持续稳定运行
            pass

        await asyncio.sleep(2.0)


if __name__ == "__main__":
    if "--watch" in sys.argv or "-w" in sys.argv:
        asyncio.run(watch_daemon())
    else:
        translations = load_dictionary()
        print(f"[*] 已加载汉化词条数量: {len(translations)}")
        asyncio.run(inject_translation(translations))
