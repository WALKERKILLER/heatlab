# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1 | ❌ |

## Reporting a Vulnerability

HeatLab 默认绑定 `127.0.0.1` 本地开发服务，**不建议**在未加固的情况下直接暴露到公网。

若发现安全问题（例如未授权访问会话、路径遍历、依赖漏洞利用路径等）：

1. **请勿**开公开 Issue 贴出利用细节
2. 通过 GitHub **Private vulnerability reporting**（若已启用）或维护者私信说明：
   - 影响版本
   - 复现步骤
   - 预期影响范围
3. 我们会在合理时间内确认与回复修复计划

## 部署注意

- Web 版使用 Flask 开发服务器，生产环境请换 WSGI（gunicorn/uwsgi 等）并加反向代理
- 会话状态默认存于进程内存，多 worker 下不共享
- 不要把调试模式或任意 `host=0.0.0.0` 暴露到不可信网络
