"""
日志配置模块
提供统一的日志配置和管理
"""
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class LogConfig:
    """日志配置类"""
    
    SINGLE_LOG = True  # 强制单文件模式
    BACKUP_DAYS = 2    # 保留2天日志
    LOG_DIR = str(Path(__file__).parent.parent.parent)  # 项目根目录
    LOG_LEVEL = logging.INFO
    LOG_FILE = 'trading_system.log'

    @classmethod
    def setup_logger(cls, log_dir: str = None):
        """
        设置日志配置
        
        Args:
            log_dir: 可选的日志目录，默认使用项目根目录
        """
        if log_dir:
            cls.LOG_DIR = log_dir
            
        logger = logging.getLogger()
        logger.setLevel(cls.LOG_LEVEL)
        
        # 清理所有现有处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 确保日志目录存在
        os.makedirs(cls.LOG_DIR, exist_ok=True)
        
        # 文件处理器
        log_path = os.path.join(cls.LOG_DIR, cls.LOG_FILE)
        file_handler = TimedRotatingFileHandler(
            log_path,
            when='midnight',
            interval=1,
            backupCount=cls.BACKUP_DAYS,
            encoding='utf-8',
            delay=True
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    @classmethod
    def clean_old_logs(cls):
        """清理过期日志文件"""
        if not os.path.exists(cls.LOG_DIR):
            return
            
        now = time.time()
        cutoff = now - cls.BACKUP_DAYS * 86400
        
        for fname in os.listdir(cls.LOG_DIR):
            # 只处理日志文件
            if not fname.endswith('.log'):
                continue
            if cls.SINGLE_LOG and fname != cls.LOG_FILE:
                continue
                
            path = os.path.join(cls.LOG_DIR, fname)
            try:
                if os.stat(path).st_mtime < cutoff:
                    os.remove(path)
                    logging.info(f"已清理过期日志: {fname}")
            except Exception as e:
                print(f"删除旧日志失败 {fname}: {str(e)}")

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取指定名称的logger
        
        Args:
            name: logger名称，通常使用类名
            
        Returns:
            配置好的Logger实例
        """
        return logging.getLogger(name)


# 导出
__all__ = ['LogConfig']
