"""
API服务器启动脚本

用于启动Kaidoki REST API服务器。

使用方法：
    python server.py [--host HOST] [--port PORT] [--reload]

Author: Kaidoki Team (Refactored)
"""

import argparse
import asyncio
import signal
import sys
from pathlib import Path
import uvicorn
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from kaidoki.shared.config.app_config import get_config
from kaidoki.shared.utils.logger_utils import setup_logging, get_logger
from kaidoki.interfaces.api.main import create_app

logger = get_logger(__name__)


class APIServer:
    """API服务器管理类"""
    
    def __init__(self, host: str = None, port: int = None, reload: bool = False):
        """
        初始化API服务器
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
            reload: 是否启用自动重载
        """
        self.config = get_config()
        self.host = host or self.config.api.host
        self.port = port or self.config.api.port
        self.reload = reload or self.config.debug
        self.app = None
        self.server = None
        
        # 设置日志
        setup_logging(
            log_level=self.config.logging.level,
            log_dir=self.config.logging.log_dir
        )
    
    async def start(self):
        """启动API服务器"""
        try:
            logger.info(f"启动API服务器 - 主机: {self.host}, 端口: {self.port}")
            
            # 创建应用
            self.app = create_app()
            
            # 配置uvicorn
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                reload=self.reload,
                log_level=self.config.logging.level.lower(),
                access_log=True,
                reload_dirs=[str(project_root)] if self.reload else None
            )
            
            # 启动服务器
            self.server = uvicorn.Server(config)
            await self.server.serve()
            
        except Exception as e:
            logger.error(f"启动API服务器失败: {e}")
            raise
    
    async def stop(self):
        """停止API服务器"""
        if self.server:
            logger.info("停止API服务器...")
            self.server.should_exit = True
            await asyncio.sleep(0.1)
    
    def run(self):
        """运行API服务器"""
        try:
            # 设置信号处理器
            def signal_handler(signum, frame):
                logger.info(f"收到信号 {signum}，正在关闭服务器...")
                asyncio.create_task(self.stop())
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # 启动服务器
            asyncio.run(self.start())
            
        except KeyboardInterrupt:
            logger.info("用户中断，服务器已停止")
        except Exception as e:
            logger.error(f"服务器运行错误: {e}")
            sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Kaidoki API服务器")
    parser.add_argument(
        "--host", 
        default=None, 
        help="服务器主机地址"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=None, 
        help="服务器端口"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="启用自动重载"
    )
    parser.add_argument(
        "--config", 
        default=None, 
        help="配置文件路径"
    )
    
    args = parser.parse_args()
    
    # 如果指定了配置文件，设置环境变量
    if args.config:
        import os
        os.environ["KAIDOKI_CONFIG_PATH"] = args.config
    
    # 创建并启动服务器
    server = APIServer(
        host=args.host,
        port=args.port,
        reload=args.reload
    )
    
    server.run()


if __name__ == "__main__":
    main()
