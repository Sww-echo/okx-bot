"""
持久化服务模块
处理状态保存和恢复
"""
import json
import os
import logging
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class PersistenceService:
    """
    持久化服务
    负责交易状态、历史记录的保存和加载
    """
    
    def __init__(self, data_dir: str = None):
        """
        初始化持久化服务
        
        Args:
            data_dir: 数据目录路径，默认为项目的 data/ 目录
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if data_dir:
            self.data_dir = data_dir
        else:
            # 默认使用项目根目录下的 data 目录
            self.data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data'
            )
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_file_path(self, filename: str) -> str:
        """获取文件完整路径"""
        return os.path.join(self.data_dir, filename)
    
    # ==================== 交易历史 ====================
    
    def save_trade_history(self, trades: List[Dict]) -> bool:
        """
        保存交易历史
        
        Args:
            trades: 交易记录列表
            
        Returns:
            是否保存成功
        """
        try:
            filepath = self._get_file_path('trade_history.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(trades, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"交易历史已保存: {len(trades)} 条记录")
            return True
        except Exception as e:
            self.logger.error(f"保存交易历史失败: {str(e)}")
            return False
    
    def load_trade_history(self) -> List[Dict]:
        """
        加载交易历史
        
        Returns:
            交易记录列表
        """
        try:
            filepath = self._get_file_path('trade_history.json')
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
                self.logger.debug(f"已加载交易历史: {len(trades)} 条记录")
                return trades
            return []
        except Exception as e:
            self.logger.error(f"加载交易历史失败: {str(e)}")
            return []
    
    # ==================== 状态保存 ====================
    
    def save_state(self, state: Dict, filename: str = 'trading_state.json') -> bool:
        """
        保存交易状态
        
        Args:
            state: 状态字典
            filename: 文件名
            
        Returns:
            是否保存成功
        """
        try:
            # 添加时间戳
            state['_saved_at'] = datetime.now().isoformat()
            
            filepath = self._get_file_path(filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"状态已保存到 {filename}")
            return True
        except Exception as e:
            self.logger.error(f"保存状态失败: {str(e)}")
            return False
    
    def load_state(self, filename: str = 'trading_state.json') -> Optional[Dict]:
        """
        加载交易状态
        
        Args:
            filename: 文件名
            
        Returns:
            状态字典，文件不存在返回 None
        """
        try:
            filepath = self._get_file_path(filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.logger.debug(f"已加载状态: {filename}")
                return state
            return None
        except Exception as e:
            self.logger.error(f"加载状态失败: {str(e)}")
            return None
    
    # ==================== 统计数据 ====================
    
    def save_statistics(self, stats: Dict) -> bool:
        """
        保存交易统计数据
        
        Args:
            stats: 统计数据字典
            
        Returns:
            是否保存成功
        """
        return self.save_state(stats, 'trade_statistics.json')
    
    def load_statistics(self) -> Optional[Dict]:
        """
        加载交易统计数据
        
        Returns:
            统计数据字典
        """
        return self.load_state('trade_statistics.json')
    
    # ==================== 归档操作 ====================
    
    def archive_old_trades(self, trades: List[Dict], days: int = 30) -> List[Dict]:
        """
        归档旧交易记录
        
        Args:
            trades: 交易记录列表
            days: 保留的天数
            
        Returns:
            归档后的活跃交易记录
        """
        try:
            cutoff_time = time.time() - (days * 86400)
            
            active_trades = []
            archived_trades = []
            
            for trade in trades:
                if trade.get('timestamp', 0) >= cutoff_time:
                    active_trades.append(trade)
                else:
                    archived_trades.append(trade)
            
            if archived_trades:
                # 保存归档文件
                archive_date = datetime.now().strftime('%Y%m%d')
                archive_file = f'trade_archive_{archive_date}.json'
                
                # 合并现有归档
                existing = self.load_state(archive_file) or {'trades': []}
                existing['trades'].extend(archived_trades)
                self.save_state(existing, archive_file)
                
                self.logger.info(f"已归档 {len(archived_trades)} 条交易记录")
            
            return active_trades
            
        except Exception as e:
            self.logger.error(f"归档交易记录失败: {str(e)}")
            return trades
    
    def clean_old_archives(self, keep_days: int = 90) -> int:
        """
        清理过期的归档文件
        
        Args:
            keep_days: 保留的天数
            
        Returns:
            清理的文件数量
        """
        try:
            cutoff_time = time.time() - (keep_days * 86400)
            cleaned = 0
            
            for filename in os.listdir(self.data_dir):
                if filename.startswith('trade_archive_') and filename.endswith('.json'):
                    filepath = os.path.join(self.data_dir, filename)
                    if os.stat(filepath).st_mtime < cutoff_time:
                        os.remove(filepath)
                        cleaned += 1
                        self.logger.info(f"已删除过期归档: {filename}")
            
            return cleaned
            
        except Exception as e:
            self.logger.error(f"清理归档文件失败: {str(e)}")
            return 0
    
    # ==================== 导出功能 ====================
    
    def export_trades_csv(self, trades: List[Dict], filename: str = None) -> Optional[str]:
        """
        导出交易记录为CSV格式
        
        Args:
            trades: 交易记录列表
            filename: 可选的文件名
            
        Returns:
            导出的文件路径
        """
        try:
            import csv
            
            if not filename:
                filename = f'trades_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            filepath = self._get_file_path(filename)
            
            if not trades:
                self.logger.warning("没有交易记录可导出")
                return None
            
            # 获取所有字段
            fieldnames = list(trades[0].keys())
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(trades)
            
            self.logger.info(f"交易记录已导出到: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"导出交易记录失败: {str(e)}")
            return None


# 导出
__all__ = ['PersistenceService']
