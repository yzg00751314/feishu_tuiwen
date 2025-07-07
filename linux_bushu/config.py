"""
配置文件 - 使用 pydantic-settings 管理配置
支持从环境变量、.env文件或默认值加载配置
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置类"""
    
    # 数据库配置
    db_host: str = Field(default="115.190.39.113", description="数据库主机")
    db_user: str = Field(default="yujiu", description="数据库用户名")
    db_password: str = Field(default="0075Yzg123@", description="数据库密码")
    db_database: str = Field(default="makevideo", description="数据库名")
    db_charset: str = Field(default="utf8mb4", description="数据库字符集")
    db_port: int = Field(default=3306, description="数据库端口")
    
    # 飞书API配置
    feishu_app_id: str = Field(default="cli_a8e09d568977100d", description="飞书应用ID")
    feishu_app_secret: str = Field(default="JGaprk8OdT0WpyRPDpyYUgfavAJLgSqh", description="飞书应用密钥")
    feishu_bitable_url: str = Field(
        default="https://ao1vfh1ggx.feishu.cn/base/QBSybMwCZaYLlLsCf7mcUIYmnKg?table=tblgnCSUlKWO3GiE&view=vewxMJqPck",
        description="飞书多维表格URL"
    )
    
    # 文件存储配置
    save_root: str = Field(default="/home/feishu", description="文件保存根目录")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: Optional[str] = Field(default=None, description="日志文件路径")
    
    # Prefect配置
    prefect_api_url: Optional[str] = Field(default=None, description="Prefect API URL")
    prefect_work_pool: str = Field(default="default", description="Prefect工作池名称")
    
    # 任务调度配置
    data_sync_interval: int = Field(default=3600, description="数据同步间隔(秒)")
    download_interval: int = Field(default=1800, description="文件下载间隔(秒)")
    
    # 下载配置
    download_timeout: int = Field(default=30, description="下载超时时间(秒)")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @property
    def db_config(self) -> dict:
        """返回数据库连接配置字典"""
        return {
            "host": self.db_host,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_database,
            "charset": self.db_charset,
            "port": self.db_port
        }
    
    def ensure_save_directory(self):
        """确保保存目录存在"""
        os.makedirs(self.save_root, exist_ok=True)
        return self.save_root


# 全局配置实例
settings = Settings()

# 为了兼容性，导出常用配置
DB_CONFIG = settings.db_config
SAVE_ROOT = settings.save_root
APP_ID = settings.feishu_app_id
APP_SECRET = settings.feishu_app_secret
BITABLE_URL = settings.feishu_bitable_url 