#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信客户端模块
用于发送消息给企业微信用户
"""

import json
import time
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .config import get_config
from .logger import get_logger


class WeChatClient:
    """企业微信客户端（简化版）"""
    
    def __init__(self):
        """初始化企业微信客户端"""
        self.config = get_config()
        self.logger = get_logger("WeChatClient")
        
        # 获取企业微信配置
        wechat_config = self.config.get_wechat_config()
        self.corpid = wechat_config["corpid"]
        self.corpsecret = wechat_config["corpsecret"]
        self.agentid = wechat_config["agentid"]
        
        # access_token缓存
        self.access_token: Optional[str] = None
        self.token_expire_time: Optional[datetime] = None
        
        # API基础URL
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        
        self.logger.info(f"企业微信客户端初始化完成，应用ID: {self.agentid}")
    
    def _get_access_token(self) -> Optional[str]:
        """获取access_token（带简单缓存）"""
        try:
            # 检查token是否有效（简单缓存：如果存在且未过期5分钟，则使用）
            if self.access_token and self.token_expire_time:
                if datetime.now() < self.token_expire_time - timedelta(minutes=5):
                    self.logger.debug("使用缓存的access_token")
                    return self.access_token
            
            # 获取新的access_token
            self.logger.info("获取新的access_token...")
            url = f"{self.base_url}/gettoken"
            params = {
                "corpid": self.corpid,
                "corpsecret": self.corpsecret
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("errcode") != 0:
                self.logger.error(f"获取access_token失败: {result}")
                return None
            
            self.access_token = result["access_token"]
            # 设置过期时间（企业微信token有效期为7200秒，我们设置为7000秒）
            self.token_expire_time = datetime.now() + timedelta(seconds=7000)
            
            self.logger.info("成功获取access_token")
            return self.access_token
            
        except Exception as e:
            self.logger.error(f"获取access_token时出错: {e}")
            return None
    
    def send_text_message(self, user_id: str, content: str) -> bool:
        """发送文本消息给指定用户"""
        try:
            # 获取access_token
            access_token = self._get_access_token()
            if not access_token:
                self.logger.error("无法获取access_token，消息发送失败")
                return False
            
            # 构建消息数据
            message_data = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": int(self.agentid),
                "text": {
                    "content": content
                },
                "safe": 0,  # 非保密消息
                "enable_id_trans": 0,  # 不开启id转译
                "enable_duplicate_check": 0,  # 不开启重复消息检查
                "duplicate_check_interval": 1800  # 重复消息检查时间间隔
            }
            
            self.logger.info(f"准备发送消息给用户 {user_id}，内容长度: {len(content)}")
            
            # 发送消息
            url = f"{self.base_url}/message/send"
            params = {"access_token": access_token}
            
            response = requests.post(
                url,
                params=params,
                json=message_data,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("errcode") == 0:
                self.logger.info(f"成功发送消息给用户 {user_id}")
                return True
            else:
                self.logger.error(f"发送消息失败: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送消息时出错: {e}")
            return False
    
    def send_messages(self, user_id: str, segments: list) -> bool:
        """发送多条消息（分段发送）"""
        if not segments:
            self.logger.warning(f"用户 {user_id} 没有消息需要发送")
            return True
        
        self.logger.info(f"开始发送 {len(segments)} 段消息给用户 {user_id}")
        
        success_count = 0
        fail_count = 0
        
        for i, segment in enumerate(segments, 1):
            self.logger.debug(f"发送第 {i}/{len(segments)} 段消息，长度: {len(segment)}")
            
            success = self.send_text_message(user_id, segment)
            
            if success:
                success_count += 1
                # 简单延迟，避免发送过快（虽然不需要考虑频率限制，但保持友好）
                if i < len(segments):
                    time.sleep(0.5)
            else:
                fail_count += 1
                self.logger.error(f"第 {i} 段消息发送失败")
        
        if fail_count == 0:
            self.logger.info(f"所有 {success_count} 段消息发送成功")
            return True
        else:
            self.logger.error(f"消息发送完成，成功: {success_count}, 失败: {fail_count}")
            return fail_count == 0  # 如果全部失败才返回False，部分成功也算成功
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            access_token = self._get_access_token()
            if access_token:
                self.logger.info("企业微信连接测试成功")
                return True
            else:
                self.logger.error("企业微信连接测试失败")
                return False
        except Exception as e:
            self.logger.error(f"企业微信连接测试出错: {e}")
            return False


# 全局企业微信客户端实例
_wechat_client_instance: Optional[WeChatClient] = None


def get_wechat_client() -> WeChatClient:
    """获取企业微信客户端实例（单例模式）"""
    global _wechat_client_instance
    
    if _wechat_client_instance is None:
        _wechat_client_instance = WeChatClient()
    
    return _wechat_client_instance


def setup_wechat_client() -> WeChatClient:
    """设置并获取企业微信客户端"""
    global _wechat_client_instance
    
    _wechat_client_instance = WeChatClient()
    return _wechat_client_instance


if __name__ == "__main__":
    # 测试企业微信客户端
    import os
    
    print("测试企业微信客户端...")
    
    # 设置测试配置
    os.environ["WECHAT_WORK_CORPID"] = "test_corpid"
    os.environ["WECHAT_WORK_CORPSECRET"] = "test_secret"
    os.environ["WECHAT_WORK_AGENTID"] = "test_agentid"
    
    client = setup_wechat_client()
    
    # 测试连接
    print("测试连接...")
    connected = client.test_connection()
    print(f"连接测试: {'成功' if connected else '失败'}")
    
    # 测试发送消息（需要真实的secret才能实际发送）
    # print("测试发送消息...")
    # success = client.send_text_message("test_user", "这是一条测试消息")
    # print(f"消息发送: {'成功' if success else '失败'}")
    
    print("测试完成")