"""
增强的日志模块，支持文件输出和终端输出
"""
import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv


class EnhancedLogger:
    """增强的日志器，支持同时输出到文件和终端"""
    
    # 日志级别映射
    LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    def __init__(self, 
                 name: str = 'Frederica',
                 log_level: str = 'INFO',
                 log_to_file: bool = True,
                 log_to_console: bool = True,
                 log_dir: str = './logs',
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5):
        """
        初始化日志器
        
        Args:
            name: 日志器名称
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: 是否输出到文件
            log_to_console: 是否输出到终端
            log_dir: 日志文件目录
            max_file_size: 单个日志文件最大大小（字节）
            backup_count: 保留的备份文件数量
        """
        load_dotenv()
        
        # 从环境变量获取配置
        self.name = os.getenv('LOGGER_NAME', name)
        self.log_level = os.getenv('LOG_LEVEL', log_level).upper()
        self.log_to_file = os.getenv('LOG_TO_FILE', str(log_to_file)).lower() == 'true'
        self.log_to_console = os.getenv('LOG_TO_CONSOLE', str(log_to_console)).lower() == 'true'
        self.log_dir = os.getenv('LOG_DIR', log_dir)
        self.max_file_size = int(os.getenv('MAX_LOG_FILE_SIZE', max_file_size))
        self.backup_count = int(os.getenv('LOG_BACKUP_COUNT', backup_count))
        
        # 确保日志目录存在
        if self.log_to_file:
            os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建日志器
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.LEVELS.get(self.log_level, logging.INFO))
        
        # 清除现有的处理器
        self.logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 添加文件处理器
        if self.log_to_file:
            log_file = os.path.join(self.log_dir, f'{self.name.lower()}.log')
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(self.LEVELS.get(self.log_level, logging.INFO))
            self.logger.addHandler(file_handler)
        
        # 添加控制台处理器
        if self.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(self.LEVELS.get(self.log_level, logging.INFO))
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str, *args, **kwargs):
        """记录DEBUG级别日志"""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """记录INFO级别日志"""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """记录WARNING级别日志"""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """记录ERROR级别日志"""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """记录CRITICAL级别日志"""
        self.logger.critical(message, *args, **kwargs)
    
    def log(self, level: str, message: str, *args, **kwargs):
        """通用日志方法"""
        level_method = getattr(self.logger, level.lower(), None)
        if level_method:
            level_method(message, *args, **kwargs)
        else:
            self.logger.info(message, *args, **kwargs)
    
    def get_log_file_path(self) -> Optional[str]:
        """获取当前日志文件路径"""
        if not self.log_to_file:
            return None
        
        for handler in self.logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                return handler.baseFilename
        return None
    
    def get_log_stats(self) -> dict:
        """获取日志统计信息"""
        log_file = self.get_log_file_path()
        stats = {
            'name': self.name,
            'level': self.log_level,
            'log_to_file': self.log_to_file,
            'log_to_console': self.log_to_console,
            'log_dir': self.log_dir,
            'handlers': len(self.logger.handlers)
        }
        
        if log_file and os.path.exists(log_file):
            stats['log_file_size'] = os.path.getsize(log_file)
            stats['log_file_path'] = log_file
        
        return stats


# 全局日志器实例
_logger_instance = None


def get_logger(name: str = 'Frederica') -> EnhancedLogger:
    """获取日志器实例（单例模式）"""
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = EnhancedLogger(name=name)
    
    return _logger_instance


def setup_logging(name: str = 'Frederica', **kwargs) -> EnhancedLogger:
    """设置并获取日志器"""
    global _logger_instance
    
    _logger_instance = EnhancedLogger(name=name, **kwargs)
    return _logger_instance


# 便捷函数
def debug(message: str, *args, **kwargs):
    """全局DEBUG日志"""
    logger = get_logger()
    logger.debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs):
    """全局INFO日志"""
    logger = get_logger()
    logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs):
    """全局WARNING日志"""
    logger = get_logger()
    logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs):
    """全局ERROR日志"""
    logger = get_logger()
    logger.error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs):
    """全局CRITICAL日志"""
    logger = get_logger()
    logger.critical(message, *args, **kwargs)


def log(level: str, message: str, *args, **kwargs):
    """全局通用日志"""
    logger = get_logger()
    logger.log(level, message, *args, **kwargs)


if __name__ == "__main__":
    # 测试日志器
    logger = setup_logging(name='TestLogger', log_level='DEBUG')
    
    logger.debug("这是一条DEBUG消息")
    logger.info("这是一条INFO消息")
    logger.warning("这是一条WARNING消息")
    logger.error("这是一条ERROR消息")
    logger.critical("这是一条CRITICAL消息")
    
    stats = logger.get_log_stats()
    print("日志统计信息:", stats)
