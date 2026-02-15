# ProjectFrederica - Multi-mode LLM Interaction Platform

> 📖 [中文版文档](README_ZH.md) | English Documentation

## Project Introduction

ProjectFrederica is a multi-functional LLM interaction platform that provides two usage modes:
- **WeChat Work Version**: Server-side for interacting with enterprise employees through WeChat Work
- **Local Client Version**: Local client for command-line interaction

### Key Features
- 🚀 **Dual-mode Support**: WeChat Work integration + local command-line interaction
- 🛠️ **Tool Calling**: Supports various tools including file operations, search, creation, etc.
- 🧠 **Personality Definition**: Defines AI personality through `soul.md` file
- ⚡ **Batch Processing**: WeChat Work version supports batch message processing
- 🔧 **Extensible**: Modular design, easy to add new tools
- 📝 **Timestamp**: Automatically adds time information to messages
- 🔐 **Environment Configuration**: Flexible configuration through environment variables

### Technology Stack
- **Python 3.8+**
- **DeepSeek API**: LLM service provider
- **WeChat Work SDK**: WeChat Work integration
- **OpenAI-compatible API**: Tool calling support
- **Environment Variable Management**: dotenv configuration

## Quick Start

### Environment Requirements
- Python 3.8 or higher
- DeepSeek API key
- WeChat Work enterprise account (only required for WeChat Work version)

### Installation Steps

1. **Clone the Project**
   ```bash
   git clone <project-url>
   cd ProjectFrederica
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   ```bash
   # Copy example configuration file
   cp .env.example .env
   
   # Edit .env file and fill in your configuration
   ```

## WeChat Work Version Guide

### Configuration Requirements
1. **WeChat Work Configuration**:
   - Create an application in WeChat Work management console
   - Obtain the following information:
     - `WECHAT_WORK_CORPID`: Enterprise ID
     - `WECHAT_WORK_CORPSECRET`: Application secret
     - `WECHAT_WORK_AGENTID`: Application ID
     - `WECHAT_WORK_CALLBACK_TOKEN`: Callback token
     - `WECHAT_WORK_ENCODING_AES_KEY`: Encryption AES key
   - Run `wecom_server.py`, and set the callback URL: `http://[your_domain]:8080/callback`
   - Configure trusted IP addresses

2. **DeepSeek API Configuration**:
   - Obtain DeepSeek API key
   - Set `DEEPSEEK_API_KEY` in `.env` file

### Start the Server
```bash
python wecom_server.py
```

### Features
- **Batch Message Processing**: Automatically processes user messages in batches for efficiency
- **Session Management**: Maintains user session state with timeout cleanup
- **Tool Calling**: Supports file operations, search, and other tools
- **Logging**: Complete logging system for debugging and monitoring
- **Status Monitoring**: Real-time display of service status and user statistics

### Tool Calling Support
WeChat Work version supports the following tools:
- 📁 `list_files`: List directory files
- 📄 `read_file`: Read file content
- ➕ `create_file_or_folder`: Create file or folder
- ✏️ `write_file`: Write content to file
- 🔍 `search_files`: Search file content
- 🗑️ `delete_file_or_folder`: Delete file or folder
- 🔍 `duckduckgo_search`: Search the web using DuckDuckGo
- 🌐 `fetch_url`: Fetch webpage content using Jina Reader API

## Local Client Version Guide

### Environment Configuration
1. **Required Configuration**:
   ```bash
   # DeepSeek API key
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   
   # Local user ID (must be set)
   LOCAL_USER_ID=YourUserName
   ```

2. **Optional Configuration**:
   ```bash
   # DeepSeek API base URL (default: https://api.deepseek.com)
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   
   # Root directory accessible to LLM (default: brain)
   LLM_ROOT_DIRECTORY=brain
   ```

### Start the Client
```bash
python local_client.py
```

### Interaction Example
```
============================================================
Simple LLM Chat Client
============================================================
Available Tools:
  1. list_files - List files and folders in the specified directory...
  2. read_file - Read the content of the specified file...
  3. create_file_or_folder - Create a file or folder...
  4. write_file - Write content to the specified file...
  5. search_files - Search for files containing specific text in the specified directory...
  6. delete_file_or_folder - Delete the specified file or folder...

Type 'quit' or 'exit' to exit the program
============================================================

[User] > List files in the current directory
[Assistant] > Let me call the list_files tool...
  [Tool Call] > list_files({"path": "."})
[Tool Result] > File list: ...
[Assistant] > Listed files in the current directory, including...
```

### Features
- **Interactive Chat**: Natural command-line interaction interface
- **Timestamp**: Automatically adds `[HH:MM:SS]` timestamp to user input
- **Tool Calling**: Supports the same toolset as the WeChat Work version
- **Personality Definition**: Uses `brain/soul.md` as system prompt
- **Error Handling**: Comprehensive error prompts and recovery mechanisms

## Tool Module Description

### File Operation Tools
- **list_files**: List files and folders in the specified directory
- **read_file**: Read the content of the specified file
- **create_file_or_folder**: Create a file or folder
- **write_file**: Write content to the specified file
- **delete_file_or_folder**: Delete the specified file or folder

### Search Tool
- **search_files**: Search for files containing specific text in the specified directory

### Web Tools
- **duckduckgo_search**: Search the web using DuckDuckGo. Returns formatted search results with titles, URLs, and summaries.
- **fetch_url**: Fetch webpage content using Jina Reader API. Converts webpages to Markdown format with content extraction.

### Tool Extension
The project uses modular design, making it easy to add new tools:
1. Create a new tool module in the `tools/` directory
2. Implement `TOOL_DEFINITION` and `execute_tool_call` functions
3. Import and register the tool in `local_client.py`

## Configuration Guide

### Environment Variables Details

#### Required Configuration
```bash
# DeepSeek API configuration
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Local client user ID (for local_client.py)
LOCAL_USER_ID=YourUserName

# WeChat Work configuration (required for WeChat Work version)
WECHAT_WORK_CORPID=your_corpid_here
WECHAT_WORK_CORPSECRET=your_corpsecret_here
WECHAT_WORK_AGENTID=yout_agentid_here
WECHAT_WORK_CALLBACK_TOKEN=your_token_here
WECHAT_WORK_ENCODING_AES_KEY=your_aes_key_here
```

#### Optional Configuration
```bash
# DeepSeek API base URL
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Root directory accessible to LLM
LLM_ROOT_DIRECTORY=brain

# Log configuration
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_TO_CONSOLE=true
LOG_DIR=./logs
MAX_LOG_FILE_SIZE=10485760
LOG_BACKUP_COUNT=5

# Message processing configuration
MESSAGE_BATCH_TIMEOUT=40  # seconds, batch processing timeout
CONVERSATION_TIMEOUT=3600  # seconds, conversation timeout (60 minutes)
MAX_USERS=10  # maximum number of users

# Jina Reader API configuration (for fetch_url tool)
JINA_API_BASE=https://r.jina.ai
JINA_API_KEY=your_jina_api_key_here
```

### soul.md Personality Definition
The `brain/soul.md` file is used to define the AI's personality and system prompts. The content of this file will be sent as system prompt to the LLM.

**File Requirements**:
- Location: `brain/soul.md`
- Size limit: 10KB
- Encoding: UTF-8 or GBK
- Content: Markdown-formatted AI personality description

## Project Structure

```
ProjectFrederica/
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable example
├── .env                         # Environment variable configuration (create yourself)
├── wecom_server.py              # WeChat Work server entry
├── local_client.py              # Local client entry
├── brain/
│   ├── soul.md                  # AI personality definition file
│   └── ...                      # Files accessible to LLM
├── src/
│   ├── config.py                # Configuration management
│   ├── logger.py                # Logging system
│   ├── message_processor.py     # Message processor
│   ├── user_session.py          # User session management
│   ├── wechat_client.py         # WeChat Work client
│   └── wechat_server.py         # WeChat Work server
├── tools/                       # Tool modules
│   ├── list_file_tool.py        # List files tool
│   ├── read_file_tool.py        # Read file tool
│   ├── create_file_or_folder_tool.py  # Create file tool
│   ├── write_to_file_tool.py    # Write to file tool
│   ├── search_files_tool.py     # Search files tool
│   └── delete_file_or_folder_tool.py  # Delete file tool
├── data/                        # Data storage
│   └── sessions/                # User session data
└── logs/                        # Log files
```

## Troubleshooting

### Common Issues

#### 1. Local Client Startup Failure
**Problem**: `Error: LOCAL_USER_ID environment variable not set`
**Solution**: Set `LOCAL_USER_ID=YourUserName` in `.env` file

#### 2. API Call Failure
**Problem**: `API call failed: ...`
**Solution**:
- Check if `DEEPSEEK_API_KEY` is correct
- Check network connection
- Verify DeepSeek API service status

#### 3. Tool Calling Error
**Problem**: `Error occurred while executing tool: ...`
**Solution**:
- Check tool parameter format
- Verify file path permissions
- View detailed error logs

#### 4. WeChat Work Server Startup Failure
**Problem**: `Configuration validation failed`
**Solution**:
- Check if all WeChat Work configuration items are complete
- Verify WeChat Work application permissions
- Check callback URL configuration

### Log Viewing
- Console logs: Add `LOG_TO_CONSOLE=true` when starting
- File logs: View log files in `logs/` directory
- Log level: Adjust via `LOG_LEVEL` (DEBUG, INFO, WARNING, ERROR)

## Development Guide

### Code Structure
The project uses modular design with main components:
- **Configuration Management**: `src/config.py`
- **Logging System**: `src/logger.py`
- **Message Processing**: `src/message_processor.py`
- **Session Management**: `src/user_session.py`
- **WeChat Work Integration**: `src/wechat_client.py`, `src/wechat_server.py`
- **Tool Modules**: Various tools in `tools/` directory

### Extending Tools
Steps to add new tools:
1. Create a new tool file in `tools/` directory
2. Implement `TOOL_DEFINITION` (tool definition) and `execute_tool_call` (tool execution) functions
3. Import and register the tool in `local_client.py`
4. Similarly import in `message_processor.py` for WeChat Work version

### Contribution Guidelines
1. Fork the project
2. Create a feature branch
3. Commit changes
4. Create a Pull Request

## License

This project uses the MIT License.

## Support & Feedback

If you have questions or suggestions, please:
1. Check the project documentation and troubleshooting section
2. Examine log files for detailed information
3. Submit an Issue or Pull Request

---

**Thank you for using ProjectFrederica!** 🚀

We hope this multi-functional LLM interaction platform helps you work and develop more efficiently.