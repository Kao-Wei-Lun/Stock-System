# QuantVision LAN 存取安全

QuantVision 是單人使用系統。預設 `APP_BIND_HOST=127.0.0.1` 且
`ALLOW_LAN_ACCESS=false`，本機瀏覽器不需要登入或 token；不要為了方便而將服務直接
暴露到公網。

## 啟用 LAN

在未納入 Git 的 `.env` 設定：

```env
APP_BIND_HOST=0.0.0.0
ALLOW_LAN_ACCESS=true
LAN_ALLOWED_NETWORKS=192.168.1.0/24
LAN_ALLOWED_ORIGINS=http://192.168.1.10:8001
LAN_ACCESS_TOKEN=請填入獨立且足夠長的隨機值
```

`LAN_ALLOWED_NETWORKS` 應縮到實際家用網段；`LAN_ALLOWED_ORIGINS` 必須是瀏覽器
實際開啟 QuantVision 的完整 origin（協定、IP、port）。不支援 `*`。可用下列命令
產生 token：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Windows `start.bat` 與 Unix `scripts/start.sh` 會先執行安全預檢。LAN 已開啟但缺少
網段、來源或強 token 時，服務會 fail closed，不會進入反覆重啟。

## 瀏覽器驗證

從 LAN IP 第一次開啟頁面時，前端會要求輸入 LAN token。token 只保存在該分頁工作階段
的 `sessionStorage`，HTTP 請求使用 `Authorization` header，WebSocket 使用
subprotocol；不會放入 URL、前端 build 變數或應用程式 log。關閉分頁後需重新輸入。

私人 `/api/*`（健康與 readiness 除外）均需驗證。寫入請求另外檢查精確 Origin 與
`X-Requested-With` CSRF header。WebSocket 也必須驗證。同步、重連與匯入等敏感流程
有記憶體內 rate limit。

## 回復本機模式

將設定恢復為：

```env
APP_BIND_HOST=127.0.0.1
ALLOW_LAN_ACCESS=false
LAN_ALLOWED_NETWORKS=
LAN_ALLOWED_ORIGINS=
LAN_ACCESS_TOKEN=
```

重新啟動後即可回到只允許本機連線的模式。不要以移除驗證但仍綁定 `0.0.0.0` 的方式
「回滾」。
