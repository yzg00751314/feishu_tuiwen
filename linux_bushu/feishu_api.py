"""
飞书API模块
封装飞书API相关操作
"""
import requests
import json
import logging
import re
import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
from config import settings


def format_time_value(ts):
    """格式化时间戳 - 按照原版to_mysql.py的逻辑"""
    try:
        ts = float(ts)
        if ts > 1e12:
            dt = datetime.datetime.fromtimestamp(ts / 1000)
        else:
            dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def get_feishu_access_token(app_id: Optional[str] = None, app_secret: Optional[str] = None) -> Optional[str]:
    """获取飞书应用身份访问凭证(tenant_access_token)"""
    logger = logging.getLogger(__name__)
    
    # 使用传入的参数或配置文件的默认值
    app_id = app_id or settings.feishu_app_id
    app_secret = app_secret or settings.feishu_app_secret
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }
    data = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 0:
            token = result.get("tenant_access_token")
            logger.info(f"成功获取 access_token: {token[:20] if token else 'None'}...")
            return token
        else:
            logger.error(f"获取access token失败: {result}")
            return None
            
    except Exception as e:
        logger.error(f"请求access token异常: {e}")
        return None


def download_file_from_feishu(
    file_token: str, 
    save_path: str, 
    access_token: str,
    file_name: str = "文件"
) -> bool:
    """从飞书下载文件"""
    logger = logging.getLogger(__name__)
    
    if not file_token or not access_token:
        logger.warning(f"文件token或access_token为空，跳过下载: {file_name}")
        return False
    
    # 构造下载链接
    download_url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        logger.info(f"开始下载文件: {file_name}")
        logger.info(f"下载URL: {download_url}")
        
        response = requests.get(download_url, headers=headers, timeout=settings.download_timeout)
        response.raise_for_status()
        
        # 确保保存目录存在
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"文件下载成功: {save_path}")
        return True
        
    except Exception as e:
        logger.error(f"下载文件失败: {download_url} -> {e}")
        return False


def download_file_direct(url: str, save_path: str, access_token: Optional[str] = None) -> bool:
    """直接从URL下载文件（兼容性方法）"""
    logger = logging.getLogger(__name__)
    
    try:
        headers = {}
        # 如果是飞书的download接口，加上token
        if "open.feishu.cn/open-apis/drive/v1/medias/" in url and url.endswith("/download") and access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        
        logger.info(f"开始下载文件: {url}")
        
        response = requests.get(url, headers=headers, timeout=settings.download_timeout)
        response.raise_for_status()
        
        # 确保保存目录存在
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"文件下载成功: {save_path}")
        return True
        
    except Exception as e:
        logger.error(f"下载文件失败: {url} -> {e}")
        return False


def safe_json_loads(val: Any) -> list:
    """安全地将值转换为JSON列表"""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    elif isinstance(val, (list, dict)):
        return [val] if isinstance(val, dict) else val
    return []


def download_project_files(
    manju: str,
    submit_time: str,
    zimu_data: str,
    miaoshu_data: str,
    access_token: str
) -> bool:
    """下载项目的所有相关文件"""
    logger = logging.getLogger(__name__)
    
    # 确保保存目录存在
    settings.ensure_save_directory()
    
    # 处理文件夹名称中的非法字符
    safe_submit_time = submit_time
    for ch in [":", "/", "\\", "*", "?", "\"", "<", ">", "|", " "]:
        safe_submit_time = safe_submit_time.replace(ch, "_")
    
    folder_name = f"{manju}_{safe_submit_time}"
    folder_path = f"{settings.save_root}/{folder_name}"
    
    import os
    os.makedirs(folder_path, exist_ok=True)
    
    logger.info(f"开始处理项目: {manju}")
    logger.info(f"保存路径: {folder_path}")
    
    # 下载字幕分组/分镜文件
    zimu_success = True
    zimu_files = safe_json_loads(zimu_data)
    
    logger.info(f"字幕文件列表: {zimu_files}")
    
    for item in zimu_files:
        if not isinstance(item, dict):
            continue
            
        file_token = item.get("file_token")
        name = item.get("name", "字幕.txt")
        
        if file_token and name:
            save_path = f"{folder_path}/{name}"
            logger.info(f"下载字幕文件: {name} (token: {file_token})")
            
            if not download_file_from_feishu(file_token, save_path, access_token, name):
                zimu_success = False
                logger.warning(f"字幕文件下载失败: {name}")
        else:
            logger.warning(f"字幕文件信息不完整: {item}")
    
    # 下载描述词文件
    miaoshu_success = True
    miaoshu_files = safe_json_loads(miaoshu_data)
    
    logger.info(f"描述词文件列表: {miaoshu_files}")
    
    for item in miaoshu_files:
        if not isinstance(item, dict):
            continue
            
        file_token = item.get("file_token")
        name = item.get("name", "描述词.txt")
        
        if file_token and name:
            save_path = f"{folder_path}/{name}"
            logger.info(f"下载描述词文件: {name} (token: {file_token})")
            
            if not download_file_from_feishu(file_token, save_path, access_token, name):
                miaoshu_success = False
                logger.warning(f"描述词文件下载失败: {name}")
        else:
            logger.warning(f"描述词文件信息不完整: {item}")
    
    # 返回整体下载是否成功
    overall_success = zimu_success and miaoshu_success
    
    if overall_success:
        logger.info(f"项目 {manju} 所有文件下载成功")
    else:
        logger.warning(f"项目 {manju} 部分文件下载失败")
    
    return overall_success


def parse_bitable_url(url: str) -> tuple:
    """
    解析飞书多维表格URL，提取app_token和table_id
    按照原版feishu_to_data.py的逻辑
    """
    logger = logging.getLogger(__name__)
    
    try:
        # 从URL路径中提取app_token (使用原版的正则表达式)
        path_pattern = r'/base/([a-zA-Z0-9]+)'
        app_token_match = re.search(path_pattern, url)
        
        if not app_token_match:
            raise ValueError("无法从URL中提取app_token")
        
        app_token = app_token_match.group(1)
        
        # 从URL查询参数中提取table_id
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        if 'table' not in query_params:
            raise ValueError("无法从URL中提取table_id")
        
        table_id = query_params['table'][0]
        
        logger.info(f"成功解析URL - App Token: {app_token}, Table ID: {table_id}")
        return app_token, table_id
        
    except Exception as e:
        logger.error(f"解析飞书URL失败: {e}")
        raise


def get_bitable_records(access_token: str, app_token: str, table_id: str, page_size: int = 500) -> List[Dict]:
    """
    获取飞书多维表格记录 - 按照原版feishu_to_data.py的逻辑
    """
    logger = logging.getLogger(__name__)
    
    all_records = []
    page_token = None
    has_more = True
    
    while has_more:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        params = {
            "page_size": page_size
        }
        
        if page_token:
            params["page_token"] = page_token
        
        try:
            logger.info(f"请求飞书数据: {url} (页面大小: {page_size})")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"API响应状态: {result.get('code')}")
            
            if result.get("code") == 0:
                data = result.get("data", {})
                items = data.get("items", [])
                all_records.extend(items)
                
                has_more = data.get("has_more", False)
                page_token = data.get("page_token")
                
                logger.info(f"已获取 {len(items)} 条记录，总计 {len(all_records)} 条")
                
            else:
                logger.error(f"获取记录失败: {result}")
                break
                
        except Exception as e:
            logger.error(f"请求记录异常: {e}")
            break
    
    logger.info(f"最终获取到 {len(all_records)} 条记录")
    return all_records


def fetch_feishu_data_to_first_table() -> bool:
    """
    从飞书多维表格拉取数据到 first_table
    """
    logger = logging.getLogger(__name__)
    
    try:
        # 1. 获取访问令牌
        access_token = get_feishu_access_token()
        if not access_token:
            logger.error("无法获取飞书访问令牌")
            return False
        
        # 2. 解析URL获取app_token和table_id
        logger.info(f"解析飞书URL: {settings.feishu_bitable_url}")
        app_token, table_id = parse_bitable_url(settings.feishu_bitable_url)
        logger.info(f"App Token: {app_token}")
        logger.info(f"Table ID: {table_id}")
        
        # 3. 获取记录
        records = get_bitable_records(access_token, app_token, table_id)
        if not records:
            logger.warning("未获取到任何记录")
            return True
        
        # 4. 调试：查看前几条记录的结构
        if records and len(records) > 0:
            logger.info("=== 调试信息：前3条记录的字段结构 ===")
            for i, record in enumerate(records[:3]):
                logger.info(f"记录 {i+1}:")
                logger.info(f"  record_id: {record.get('record_id')}")
                logger.info(f"  fields: {record.get('fields', {})}")
                
                fields = record.get("fields", {})
                logger.info(f"  可用字段名: {list(fields.keys())}")
                
        # 5. 处理数据并插入数据库
        import pymysql
        from database import safe_value
        
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            # 清空 first_table（可选）
            cursor.execute("DELETE FROM first_table WHERE `漫剧名称` NOT LIKE '测试漫剧%'")
            logger.info("已清空 first_table 中的非测试数据")
            
            insert_count = 0
            insert_sql = """
            INSERT INTO first_table (`字幕分组/分镜`, `漫剧名称`, `描述词`, `类型`, `提交时间`)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            `字幕分组/分镜`=VALUES(`字幕分组/分镜`),
            `描述词`=VALUES(`描述词`),
            `类型`=VALUES(`类型`),
            `提交时间`=VALUES(`提交时间`)
            """
            
            for record in records:
                fields = record.get("fields", {})
                
                # 提取字段数据 - 使用原版to_mysql.py的字段映射
                zimu_data = safe_value(fields.get("字幕分组/分镜", ""))
                manju_name = safe_value(fields.get("您创作的漫剧名称为？", ""))  # 原版使用的字段名
                miaoshu_data = safe_value(fields.get("描述词", ""))
                leixing = safe_value(fields.get("男/女频？", ""))  # 原版使用的字段名
                
                # 处理提交时间 - 按照原版to_mysql.py的逻辑
                raw_time = fields.get("提交时间", None)
                if isinstance(raw_time, (dict, list)):
                    raw_time = json.dumps(raw_time, ensure_ascii=False)
                
                if raw_time not in [None, ""]:
                    submit_time = format_time_value(raw_time)
                else:
                    submit_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                logger.info(f"提取的字段值:")
                logger.info(f"  字幕分组/分镜: {zimu_data[:50] if zimu_data else 'None'}...")
                logger.info(f"  漫剧名称: {manju_name}")
                logger.info(f"  描述词: {miaoshu_data[:50] if miaoshu_data else 'None'}...")
                logger.info(f"  类型: {leixing}")
                logger.info(f"  提交时间: {submit_time}")
                
                # 跳过空记录
                if not manju_name:
                    logger.warning("跳过空的漫剧名称记录")
                    continue
                if not zimu_data:
                    logger.warning(f"跳过没有字幕数据的记录: {manju_name}")
                    continue
                if not miaoshu_data:
                    logger.warning(f"跳过没有描述词的记录: {manju_name}")
                    continue
                
                values = (zimu_data, manju_name, miaoshu_data, leixing, submit_time)
                cursor.execute(insert_sql, values)
                insert_count += 1
                
                logger.info(f"✓ 处理记录: {manju_name} - {leixing}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"成功从飞书拉取并插入 {insert_count} 条记录到 first_table")
        return True
        
    except Exception as e:
        logger.error(f"从飞书拉取数据失败: {e}")
        return False 