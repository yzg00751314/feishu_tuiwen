"""
数据库操作模块
封装所有数据库相关操作
"""
import pymysql
import json
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple
from pymysql.cursors import DictCursor
from config import settings


def safe_json_loads(val: Any) -> List[Dict]:
    """安全地将值转换为JSON列表"""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    elif isinstance(val, (list, dict)):
        return [val] if isinstance(val, dict) else val
    return []


def safe_value(val: Any) -> str:
    """安全地将值转换为字符串"""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return val if val is not None else ""


def format_time(ts: Any) -> str:
    """格式化时间戳"""
    try:
        ts = float(ts)
        if ts > 1e12:
            dt = datetime.datetime.fromtimestamp(ts / 1000)
        else:
            dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts) if ts is not None else ""


def create_database_tables() -> bool:
    """创建或检查数据库表结构"""
    logger = logging.getLogger(__name__)
    
    # first_table 建表SQL（数据源表） - 按照原版to_mysql.py的结构
    CREATE_FIRST_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS first_table (
        `字幕分组/分镜` LONGTEXT,
        `漫剧名称` VARCHAR(255),
        `描述词` LONGTEXT,
        `类型` VARCHAR(100),
        `提交时间` VARCHAR(50),
        UNIQUE KEY uk_type_name (`类型`, `漫剧名称`)
    ) CHARACTER SET utf8mb4;
    """
    
    # second_table 建表SQL
    CREATE_SECOND_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS second_table (
        `字幕分组/分镜` LONGTEXT,
        `漫剧名称` VARCHAR(255),
        `描述词` LONGTEXT,
        `类型` VARCHAR(100),
        `提交时间` VARCHAR(50),
        `makevideo` INT DEFAULT 0,
        UNIQUE KEY uk_type_name (`类型`, `漫剧名称`)
    ) CHARACTER SET utf8mb4;
    """
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            # 创建 first_table（如果不存在）
            cursor.execute(CREATE_FIRST_TABLE_SQL)
            logger.info("first_table 表结构检查完成")
            
            # 先删除可能存在的旧约束
            try:
                cursor.execute("ALTER TABLE second_table DROP INDEX uk_type_name_time")
                logger.info("已删除旧的唯一键约束")
            except:
                pass  # 如果不存在就忽略
            
            cursor.execute(CREATE_SECOND_TABLE_SQL)
            logger.info("second_table 表结构检查完成")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"建表过程中出现错误: {e}")
        return False


def get_second_table_count() -> int:
    """获取 second_table 当前记录数"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM second_table")
            result = cursor.fetchone()
            count = result[0] if result else 0
        conn.close()
        
        logger.info(f"second_table 当前记录数: {count}")
        return count
        
    except Exception as e:
        logger.error(f"查询记录数失败: {e}")
        return 0


def get_new_records_from_first_table(limit: int = 2) -> List[Dict[str, Any]]:
    """从 first_table 中获取不在 second_table 的新记录"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor(DictCursor) as cursor:
            cursor.execute("""
                SELECT f.`字幕分组/分镜`, f.`漫剧名称`, f.`描述词`, f.`类型`, f.`提交时间`
                FROM first_table f
                LEFT JOIN second_table s ON f.`类型` = s.`类型` AND f.`漫剧名称` = s.`漫剧名称`
                WHERE TRIM(f.`字幕分组/分镜`) != '' AND f.`字幕分组/分镜` IS NOT NULL
                  AND TRIM(f.`描述词`) != '' AND f.`描述词` IS NOT NULL
                  AND s.`类型` IS NULL
                ORDER BY f.`提交时间` DESC
                LIMIT %s
            """, (limit,))
            
            new_records = cursor.fetchall()
        conn.close()
        
        logger.info(f"从 first_table 找到 {len(new_records)} 条新记录")
        return list(new_records)
        
    except Exception as e:
        logger.error(f"查询新记录失败: {e}")
        return []


def get_existing_records_from_first_table() -> List[Dict[str, Any]]:
    """从 first_table 中获取需要更新的现有记录"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor(DictCursor) as cursor:
            cursor.execute("""
                SELECT f.`字幕分组/分镜`, f.`漫剧名称`, f.`描述词`, f.`类型`, f.`提交时间`
                FROM first_table f
                INNER JOIN second_table s ON f.`类型` = s.`类型` AND f.`漫剧名称` = s.`漫剧名称`
                WHERE TRIM(f.`字幕分组/分镜`) != '' AND f.`字幕分组/分镜` IS NOT NULL
                  AND TRIM(f.`描述词`) != '' AND f.`描述词` IS NOT NULL
                ORDER BY f.`提交时间` DESC
            """)
            
            existing_records = cursor.fetchall()
        conn.close()
        
        logger.info(f"从 first_table 找到 {len(existing_records)} 条需要更新的记录")
        return list(existing_records)
        
    except Exception as e:
        logger.error(f"查询现有记录失败: {e}")
        return []


def insert_new_records(records: List[Dict[str, Any]]) -> int:
    """插入新记录到 second_table"""
    logger = logging.getLogger(__name__)
    
    if not records:
        logger.info("没有新记录需要插入")
        return 0
    
    insert_count = 0
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            insert_sql = """
            INSERT INTO second_table (`字幕分组/分镜`, `漫剧名称`, `描述词`, `类型`, `提交时间`, `makevideo`)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            for i, row in enumerate(records, 1):
                zimu = safe_value(row.get("字幕分组/分镜", ""))
                manju = safe_value(row.get("漫剧名称", ""))
                miaoshu = safe_value(row.get("描述词", ""))
                leixing = safe_value(row.get("类型", ""))
                submit_time = safe_value(row.get("提交时间", ""))
                
                logger.info(f"插入第 {i} 条新记录: {leixing} - {manju} - {submit_time}")
                
                values = (zimu, manju, miaoshu, leixing, submit_time, 0)
                cursor.execute(insert_sql, values)
                insert_count += 1
                logger.info(f"  -> 插入了新记录")
        
        conn.commit()
        conn.close()
        logger.info(f"成功插入 {insert_count} 条新记录")
        return insert_count
        
    except Exception as e:
        logger.error(f"插入新记录失败: {e}")
        return 0


def update_existing_records(records: List[Dict[str, Any]]) -> int:
    """更新 second_table 中的现有记录"""
    logger = logging.getLogger(__name__)
    
    if not records:
        logger.info("没有记录需要更新")
        return 0
    
    update_count = 0
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            update_sql = """
            UPDATE second_table 
            SET `字幕分组/分镜`=%s, `描述词`=%s, `提交时间`=%s, `makevideo`=0
            WHERE `类型`=%s AND `漫剧名称`=%s
            """
            
            for i, row in enumerate(records, 1):
                zimu = safe_value(row.get("字幕分组/分镜", ""))
                manju = safe_value(row.get("漫剧名称", ""))
                miaoshu = safe_value(row.get("描述词", ""))
                leixing = safe_value(row.get("类型", ""))
                submit_time = safe_value(row.get("提交时间", ""))
                
                logger.info(f"更新第 {i} 条已存在记录: {leixing} - {manju} - {submit_time}")
                
                values = (zimu, miaoshu, submit_time, leixing, manju)
                cursor.execute(update_sql, values)
                update_count += 1
                logger.info(f"  -> 更新了现有记录")
        
        conn.commit()
        conn.close()
        logger.info(f"成功更新 {update_count} 条记录")
        return update_count
        
    except Exception as e:
        logger.error(f"更新记录失败: {e}")
        return 0


def get_pending_download_records() -> List[Dict[str, Any]]:
    """获取等待下载的记录 (makevideo=0)"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor(DictCursor) as cursor:
            cursor.execute("""
                SELECT `漫剧名称`, `提交时间`, `字幕分组/分镜`, `描述词`
                FROM second_table
                WHERE `makevideo`=0
            """)
            
            records = cursor.fetchall()
        conn.close()
        
        logger.info(f"找到 {len(records)} 条等待下载的记录")
        return list(records)
        
    except Exception as e:
        logger.error(f"查询等待下载记录失败: {e}")
        return []


def update_makevideo_status(manju: str, submit_time: str, status: int = 1) -> bool:
    """更新记录的 makevideo 状态"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE second_table SET makevideo=%s WHERE `漫剧名称`=%s AND `提交时间`=%s
                """,
                (status, manju, submit_time)
            )
        
        conn.commit()
        conn.close()
        logger.info(f"已更新makevideo={status}: {manju}_{submit_time}")
        return True
        
    except Exception as e:
        logger.error(f"更新makevideo状态失败: {e}")
        return False


def insert_test_data_to_first_table(force_insert: bool = False) -> bool:
    """向 first_table 插入测试数据（如果表为空或强制插入）"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            # 检查是否已有数据
            cursor.execute("SELECT COUNT(*) FROM first_table")
            result = cursor.fetchone()
            count = result[0] if result else 0
            
            if count > 0 and not force_insert:
                logger.info(f"first_table 已有 {count} 条数据，跳过插入测试数据")
                conn.close()
                return True
            
            # 如果强制插入，先清空测试数据
            if force_insert:
                cursor.execute("DELETE FROM first_table WHERE `漫剧名称` LIKE '测试漫剧%'")
                logger.info("已清除旧的测试数据")
            
            # 插入测试数据 - 使用真实格式的 file_token
            test_data = [
                ("file_token_test1", "测试漫剧1", "file_token_desc1", "原创", "2025-01-01 10:00:00"),
                ("file_token_test2", "测试漫剧2", "file_token_desc2", "改编", "2025-01-01 11:00:00"),
            ]
            
            insert_sql = """
            INSERT INTO first_table (`字幕分组/分镜`, `漫剧名称`, `描述词`, `类型`, `提交时间`)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            `字幕分组/分镜`=VALUES(`字幕分组/分镜`),
            `描述词`=VALUES(`描述词`)
            """
            
            cursor.executemany(insert_sql, test_data)
            conn.commit()
            logger.info(f"成功向 first_table 插入 {len(test_data)} 条测试数据")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"插入测试数据失败: {e}")
        return False


def clean_test_data() -> bool:
    """清理测试数据"""
    logger = logging.getLogger(__name__)
    
    try:
        conn = pymysql.connect(**settings.db_config)
        with conn.cursor() as cursor:
            # 删除测试数据
            cursor.execute("DELETE FROM first_table WHERE `漫剧名称` LIKE '测试漫剧%'")
            first_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM second_table WHERE `漫剧名称` LIKE '测试漫剧%'")
            second_deleted = cursor.rowcount
            
        conn.commit()
        conn.close()
        
        logger.info(f"清理测试数据完成: first_table删除{first_deleted}条, second_table删除{second_deleted}条")
        return True
        
    except Exception as e:
        logger.error(f"清理测试数据失败: {e}")
        return False


def export_table_to_excel(table_name: str, output_file: str) -> bool:
    """导出数据库表为Excel文件"""
    logger = logging.getLogger(__name__)
    
    try:
        import pandas as pd
        
        conn = pymysql.connect(**settings.db_config)
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        df.to_excel(output_file, index=False, engine="openpyxl")
        conn.close()
        
        logger.info(f"{table_name} 已导出为 {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"导出 {table_name} 失败: {e}")
        return False 