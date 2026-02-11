# ProjectFrederica - 多功能LLM交互平台

## 项目简介

ProjectFrederica 是一个多功能LLM交互平台，提供两种使用方式：
- **企业微信版本**：通过企业微信与企业员工交互的服务器端
- **本地客户端版本**：通过命令行交互的本地客户端

### 主要功能特点
- 🚀 **双模式支持**：企业微信集成 + 本地命令行交互
- 🛠️ **工具调用**：支持文件操作、搜索、创建等多种工具
- 🧠 **人格定义**：通过`soul.md`文件定义AI人格
- ⚡ **批量处理**：企业微信版本支持消息批量处理
- 🔧 **可扩展**：模块化设计，易于添加新工具
- 📝 **时间戳**：自动为消息添加时间信息
- 🔐 **环境配置**：通过环境变量灵活配置

### 技术栈
- **Python 3.8+**
- **DeepSeek API**：LLM服务提供商
- **企业微信SDK**：企业微信集成
- **OpenAI兼容API**：工具调用支持
- **环境变量管理**：dotenv配置

## 快速开始

### 环境要求
- Python 3.8 或更高版本
- DeepSeek API密钥
- 企业微信企业账号（仅企业微信版本需要）

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <项目地址>
   cd ProjectFrederica
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   # 复制示例配置文件
   cp .env.example .env
   
   # 编辑.env文件，填写您的配置
   ```

## 企业微信版本使用指南

### 配置要求
1. **企业微信配置**：
   - 在企业微信管理后台创建应用
   - 获取以下信息：
     - `WECHAT_WORK_CORPID`：企业ID
     - `WECHAT_WORK_CORPSECRET`：应用密钥
     - `WECHAT_WORK_AGENTID`：应用ID
     - `WECHAT_WORK_CALLBACK_TOKEN`：回调Token
     - `WECHAT_WORK_ENCODING_AES_KEY`：加密AES Key
   - 运行wecom_server同时设置回调URL：http://[your_domain]:8080/callback
   - 配置可信IP

2. **DeepSeek API配置**：
   - 获取DeepSeek API密钥
   - 在`.env`文件中设置`DEEPSEEK_API_KEY`

### 启动服务器
```bash
python wecom_server.py
```

### 功能特性
- **批量消息处理**：自动批量处理用户消息，提高效率
- **会话管理**：维护用户会话状态，支持超时清理
- **工具调用**：支持文件操作、搜索等工具
- **日志记录**：完整的日志系统，便于调试和监控
- **状态监控**：实时显示服务状态和用户统计

### 工具调用支持
企业微信版本支持以下工具：
- 📁 `list_files`：列出目录文件
- 📄 `read_file`：读取文件内容
- ➕ `create_file_or_folder`：创建文件或文件夹
- ✏️ `write_file`：写入文件内容
- 🔍 `search_files`：搜索文件内容
- 🗑️ `delete_file_or_folder`：删除文件或文件夹

## 本地客户端使用指南

### 环境配置
1. **必需配置**：
   ```bash
   # DeepSeek API密钥
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   
   # 本地用户ID（必须设置）
   LOCAL_USER_ID=YourUserName
   ```

2. **可选配置**：
   ```bash
   # DeepSeek API基础URL（默认：https://api.deepseek.com）
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   
   # LLM可访问的根目录（默认：brain）
   LLM_ROOT_DIRECTORY=brain
   ```

### 启动客户端
```bash
python local_client.py
```

### 交互示例
```
============================================================
简易LLM聊天客户端
============================================================
可用工具:
  1. list_files - 列出指定目录下的文件和文件夹...
  2. read_file - 读取指定文件的内容...
  3. create_file_or_folder - 创建文件或文件夹...
  4. write_file - 向指定文件写入内容...
  5. search_files - 在指定目录中搜索包含特定文本的文件...
  6. delete_file_or_folder - 删除指定的文件或文件夹...

输入 'quit' 或 'exit' 退出程序
============================================================

[User] > 列出当前目录的文件
[Assistant] > 让我来调用list_files工具...
  [Tool Call] > list_files({"path": "."})
[Tool Result] > 文件列表：...
[Assistant] > 已列出当前目录的文件，包含...
```

### 功能特性
- **交互式聊天**：自然的命令行交互界面
- **时间戳**：用户输入自动添加`[HH:MM:SS]`时间戳
- **工具调用**：支持与企业微信版本相同的工具集
- **人格定义**：使用`brain/soul.md`作为system prompt
- **错误处理**：完善的错误提示和恢复机制

## 工具模块说明

### 文件操作工具
- **list_files**：列出指定目录下的文件和文件夹
- **read_file**：读取指定文件的内容
- **create_file_or_folder**：创建文件或文件夹
- **write_file**：向指定文件写入内容
- **delete_file_or_folder**：删除指定的文件或文件夹

### 搜索工具
- **search_files**：在指定目录中搜索包含特定文本的文件

### 工具扩展
项目采用模块化设计，可以轻松添加新工具：
1. 在`tools/`目录下创建新的工具模块
2. 实现`TOOL_DEFINITION`和`execute_tool_call`函数
3. 在`local_client.py`中导入并注册工具

## 配置说明

### 环境变量详解

#### 必需配置
```bash
# DeepSeek API配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 本地客户端用户ID（用于local_client.py）
LOCAL_USER_ID=YourUserName

# 企业微信配置（企业微信版本需要）
WECHAT_WORK_CORPID=your_corpid_here
WECHAT_WORK_CORPSECRET=your_corpsecret_here
WECHAT_WORK_AGENTID=yout_agentid_here
WECHAT_WORK_CALLBACK_TOKEN=your_token_here
WECHAT_WORK_ENCODING_AES_KEY=your_aes_key_here
```

#### 可选配置
```bash
# DeepSeek API基础URL
DEEPSEEK_BASE_URL=https://api.deepseek.com

# LLM可访问的根目录
LLM_ROOT_DIRECTORY=brain

# 日志配置
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_TO_CONSOLE=true
LOG_DIR=./logs
MAX_LOG_FILE_SIZE=10485760
LOG_BACKUP_COUNT=5

# 消息处理配置
MESSAGE_BATCH_TIMEOUT=40  # 秒，批量处理超时时间
CONVERSATION_TIMEOUT=3600  # 秒，对话超时时间（60分钟）
MAX_USERS=10  # 最大用户数
```

### soul.md人格定义
`brain/soul.md`文件用于定义AI的人格和系统提示词。该文件内容将作为system prompt发送给LLM。

**文件要求**：
- 位置：`brain/soul.md`
- 大小限制：10KB
- 编码：UTF-8或GBK
- 内容：Markdown格式的AI人格描述

## 项目结构

```
ProjectFrederica/
├── README.md                    # 项目说明文档
├── requirements.txt             # Python依赖
├── .env.example                 # 环境变量示例
├── .env                         # 环境变量配置（需自行创建）
├── wecom_server.py              # 企业微信服务器入口
├── local_client.py              # 本地客户端入口
├── brain/
│   ├── soul.md                  # AI人格定义文件
│   └── ...                      # LLM可访问的文件
├── src/
│   ├── config.py                # 配置管理
│   ├── logger.py                # 日志系统
│   ├── message_processor.py     # 消息处理器
│   ├── user_session.py          # 用户会话管理
│   ├── wechat_client.py         # 企业微信客户端
│   └── wechat_server.py         # 企业微信服务器
├── tools/                       # 工具模块
│   ├── list_file_tool.py        # 列出文件工具
│   ├── read_file_tool.py        # 读取文件工具
│   ├── create_file_or_folder_tool.py  # 创建文件工具
│   ├── write_to_file_tool.py    # 写入文件工具
│   ├── search_files_tool.py     # 搜索文件工具
│   └── delete_file_or_folder_tool.py  # 删除文件工具
├── data/                        # 数据存储
│   └── sessions/                # 用户会话数据
└── logs/                        # 日志文件
```

## 故障排除

### 常见问题

#### 1. 本地客户端启动失败
**问题**：`错误：未设置LOCAL_USER_ID环境变量`
**解决**：在`.env`文件中设置`LOCAL_USER_ID=YourUserName`

#### 2. API调用失败
**问题**：`API调用失败: ...`
**解决**：
- 检查`DEEPSEEK_API_KEY`是否正确
- 检查网络连接
- 确认DeepSeek API服务状态

#### 3. 工具调用错误
**问题**：`执行工具时发生错误: ...`
**解决**：
- 检查工具参数格式
- 确认文件路径权限
- 查看详细错误日志

#### 4. 企业微信服务器无法启动
**问题**：`配置验证失败`
**解决**：
- 检查所有企业微信配置项是否完整
- 确认企业微信应用权限
- 检查回调URL配置

### 日志查看
- 控制台日志：启动时添加`LOG_TO_CONSOLE=true`
- 文件日志：查看`logs/`目录下的日志文件
- 日志级别：通过`LOG_LEVEL`调整（DEBUG, INFO, WARNING, ERROR）

## 开发指南

### 代码结构
项目采用模块化设计，主要组件：
- **配置管理**：`src/config.py`
- **日志系统**：`src/logger.py`
- **消息处理**：`src/message_processor.py`
- **会话管理**：`src/user_session.py`
- **企业微信集成**：`src/wechat_client.py`, `src/wechat_server.py`
- **工具模块**：`tools/`目录下的各个工具

### 扩展工具
添加新工具的步骤：
1. 在`tools/`目录创建新工具文件
2. 实现`TOOL_DEFINITION`（工具定义）和`execute_tool_call`（工具执行）函数
3. 在`local_client.py`中导入并注册工具
4. 在企业微信版本的`message_processor.py`中同样导入

### 贡献指南
1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

本项目采用MIT许可证。

## 支持与反馈

如有问题或建议，请：
1. 查看项目文档和故障排除部分
2. 检查日志文件获取详细信息
3. 提交Issue或Pull Request

---

**感谢使用ProjectFrederica！** 🚀

希望这个多功能LLM交互平台能够帮助您更高效地工作和开发。