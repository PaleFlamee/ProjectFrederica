# 企业微信回调接口配置指南

## 概述

本项目已实现完整的企业微信回调接口，支持：
1. **GET请求（验证）**：企业微信后台在配置时会发送验证请求，系统会原样返回echostr参数
2. **POST请求（接收消息）**：用户发送消息后，企业微信会将加密消息推送到接口，系统会解密、处理并回复

## 配置步骤

### 1. 环境配置

确保 `.env` 文件包含以下配置：

```env
# 企业微信基础配置
WECHAT_WORK_CORPID=ww1b7c2409ffbded94
WECHAT_WORK_CORPSECRET=bv4Xk3Ay1GGiI-Ynmt0LapmsqepKhSZRJszG_HT8rGM
WECHAT_WORK_AGENTID=1000002

# 回调配置（关键参数）
WECHAT_WORK_CALLBACK_TOKEN=FREDERICATOKEN
WECHAT_WORK_ENCODING_AES_KEY=norTzT7trWzPklIJEBILTG7UMzMXuibpzlAVaS4zag0
```

### 2. 启动回调服务器

#### 方式一：使用回调服务器（推荐）

```bash
# 启动回调服务器（默认端口8080）
python src/callback_server.py

# 指定端口启动
python src/callback_server.py --port 3000

# 指定监听地址和端口
python src/callback_server.py --host 0.0.0.0 --port 8080
```

#### 监听地址和端口说明（支持IPv4和IPv6）

**IPv4监听地址**：
- `127.0.0.1` 或 `localhost`：只允许本机IPv4访问
- `0.0.0.0`：允许所有IPv4网络接口访问
- 特定IPv4地址（如 `192.168.1.100`）：只允许特定IPv4网络接口访问

**IPv6监听地址**：
- `::1`：只允许本机IPv6访问
- `::`：允许所有IPv6地址，同时支持IPv4（双栈模式）
- 特定IPv6地址（如 `2001:db8::1`）：只允许特定IPv6网络接口访问

**监听端口 (Port)**：
- `80`：HTTP标准端口（需要管理员权限）
- `443`：HTTPS标准端口（需要管理员权限）
- `8080`、`3000`、`5000`等：常用开发端口
- 建议使用 `1024-65535` 之间的端口

**配置建议**：
- 开发环境（仅本地）：使用 `127.0.0.1:8080`（IPv4）或 `::1:8080`（IPv6）
- 测试环境（允许外部）：使用 `0.0.0.0:3000`（仅IPv4）或 `::3000`（IPv4+IPv6双栈）
- 生产环境：使用 `::80` 或 `::443`（双栈模式，需要配置域名和SSL证书）

**IPv6 URL格式**：
- IPv4地址：`http://192.168.1.100:8080/callback`
- IPv6地址：`http://[2001:db8::1]:8080/callback`
- 本机IPv6：`http://[::1]:8080/callback`
- 双栈模式：`http://localhost:8080/callback`（IPv4）或 `http://[::1]:8080/callback`（IPv6）

#### 方式二：集成到现有Web框架

如果你使用Flask、FastAPI等Web框架，可以这样调用：

```python
from src.wechat_bot import get_bot

bot = get_bot()

# 处理GET请求
@app.route('/callback', methods=['GET'])
def handle_callback_get():
    query_params = request.args.to_dict()
    response = bot.handle_callback_request('GET', query_params)
    return response

# 处理POST请求
@app.route('/callback', methods=['POST'])
def handle_callback_post():
    query_params = request.args.to_dict()
    request_body = request.data.decode('utf-8')
    response = bot.handle_callback_request('POST', query_params, request_body)
    return response, 200, {'Content-Type': 'text/xml; charset=utf-8'}
```

### 3. 企业微信后台配置

1. 登录企业微信管理后台
2. 进入「应用管理」→「自建应用」→选择你的应用
3. 在「接收消息」部分，点击「设置API接收」
4. 填写以下信息：
   - **URL**: `http://tx6p.paleflame.top/callback` (根据你的实际域名调整)
   - **Token**: `FREDERICATOKEN`
   - **EncodingAESKey**: `norTzT7trWzPklIJEBILTG7UMzMXuibpzlAVaS4zag0`
   - **消息加解密方式**: 选择「安全模式」
5. 点击「保存」，企业微信会发送GET请求验证服务器
6. 验证成功后，配置完成

## 回调接口说明

### GET请求（验证）

- **URL**: `/callback`
- **方法**: GET
- **参数**:
  - `msg_signature`: 企业微信加密签名
  - `timestamp`: 时间戳
  - `nonce`: 随机数
  - `echostr`: 随机字符串
- **响应**: 解密后的echostr原样返回

### POST请求（接收消息）

- **URL**: `/callback`
- **方法**: POST
- **参数**:
  - `msg_signature`: 企业微信加密签名
  - `timestamp`: 时间戳
  - `nonce`: 随机数
- **请求体**: 加密的XML消息
- **响应**: 加密的XML回复（立即返回success，实际回复异步发送）

## 消息处理流程

1. **接收加密消息**：企业微信发送加密的XML消息到回调接口
2. **解密验证**：使用WeChatCrypto解密消息并验证签名
3. **解析消息**：解析XML获取消息类型、发送者、内容等信息
4. **异步处理**：
   - 文本消息添加到消息队列
   - LLM生成回复
   - 通过企业微信API发送回复
5. **立即响应**：返回success表示已接收，避免企业微信重试

## 测试方法

### 1. 测试回调功能

```bash
# 运行测试
python src/callback_server.py --test
```

### 2. 测试同步消息处理

```python
from src.wechat_bot import get_bot

bot = get_bot()
reply = bot.process_callback_message_sync('test_user_id', '你好，测试消息')
print(f"回复: {reply}")
```

### 3. 测试完整流程

1. 启动回调服务器：`python src/callback_server.py`
2. 使用curl模拟企业微信请求：
   ```bash
   # GET验证（需要真实的签名参数）
   curl "http://localhost:8080/callback?msg_signature=xxx&timestamp=123&nonce=456&echostr=test"
   
   # POST消息（需要真实的加密消息）
   curl -X POST "http://localhost:8080/callback?msg_signature=xxx&timestamp=123&nonce=456" \
        -H "Content-Type: text/xml" \
        -d "<xml>...</xml>"
   ```

## 故障排除

### 1. GET验证失败
- 检查Token、EncodingAESKey配置是否正确
- 检查服务器时间是否同步
- 检查签名算法实现

### 2. POST消息处理失败
- 检查消息加解密配置
- 查看日志文件 `logs/frederica.log`
- 确认企业微信应用有发送消息权限

### 3. 消息未回复
- 检查企业微信API权限
- 确认access_token有效
- 查看消息队列状态：`python main.py --status`

### 4. 服务器无法访问
- 检查防火墙设置
- 确认端口开放
- 检查域名解析和SSL证书（如果使用HTTPS）

## 日志查看

所有回调相关的日志都会记录在 `logs/frederica.log` 中，可以通过以下方式查看：

```bash
# 查看实时日志
tail -f logs/frederica.log

# 查看错误日志
grep -i error logs/frederica.log

# 查看回调相关日志
grep -i callback logs/frederica.log
```

## 安全注意事项

1. **Token和AESKey保密**：不要泄露回调配置参数
2. **服务器安全**：确保回调服务器有适当的安全防护
3. **访问控制**：建议配置IP白名单（企业微信服务器IP）
4. **HTTPS推荐**：生产环境建议使用HTTPS
5. **定期更新**：定期更新Token和AESKey

## 扩展功能

### 1. 添加消息类型支持
当前主要支持文本消息，可以扩展支持：
- 图片消息
- 语音消息
- 文件消息
- 位置消息

### 2. 添加事件处理
支持企业微信事件：
- 成员关注/取消关注
- 进入应用
- 菜单点击

### 3. 性能优化
- 消息队列优化
- 缓存机制
- 并发处理

## 联系支持

如有问题，请查看项目文档或联系开发者。
```

<task_progress>
- [x] 分析项目结构和现有代码
- [x] 查看 wechat_bot.py 当前实现
- [x] 查看 llm.py 了解LLM调用方式
- [x] 查看 main.py 了解Web服务结构
- [x] 查看企业微信SDK示例代码
- [x] 实现GET验证接口
- [x] 实现POST消息处理接口
- [x] 集成消息加解密逻辑
- [x] 集成LLM回复生成
- [x] 集成消息发送功能
- [x] 测试实现
</task_progress>
</write_to_file>
