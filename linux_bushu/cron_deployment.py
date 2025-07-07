 #!/usr/bin/env python3
"""
Cron 定时任务专用部署脚本
每天早上8点执行完整的数据同步和文件下载流程
"""
import sys
import os
import logging
import traceback
import pymysql
from datetime import datetime
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from database import (
    create_database_tables,
    insert_test_data_to_first_table,
    clean_test_data,
    get_second_table_count,
    get_new_records_from_first_table,
    get_existing_records_from_first_table,
    insert_new_records,
    update_existing_records,
    get_pending_download_records,
    update_makevideo_status
)
from feishu_api import (
    get_feishu_access_token,
    download_project_files,
    fetch_feishu_data_to_first_table
)


def setup_logging():
    """设置日志配置"""
    # 确保日志目录存在
    log_dir = Path("/var/log/feishu")
    log_dir.mkdir(exist_ok=True, parents=True)
    
    # 设置日志格式
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    # 配置日志文件（按日期滚动）
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"feishu_{today}.log"
    
    # 配置根日志器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # 同时输出到控制台
        ]
    )
    
    return logging.getLogger(__name__)


def data_sync_task():
    """数据同步任务"""
    logger = logging.getLogger(__name__)
    logger.info("=== 开始数据同步任务 ===")
    
    try:
        # 1. 确保数据库表结构存在
        logger.info("检查数据库表结构...")
        if not create_database_tables():
            raise Exception("数据库表创建失败")
        
        # 2. 如果 first_table 为空，插入测试数据
        # 注意：在daily任务中，会先执行fetch，所以这里主要是为单独运行sync时提供数据
        try:
            conn = pymysql.connect(**settings.db_config)
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM first_table")
                result = cursor.fetchone()
                count = result[0] if result else 0
            conn.close()
            
            if count == 0:
                logger.info("first_table 为空，插入测试数据用于调试")
                insert_test_data_to_first_table()
            else:
                logger.info(f"first_table 已有 {count} 条数据，直接进行同步")
        except Exception as e:
            logger.warning(f"检查first_table失败: {e}，插入测试数据")
            insert_test_data_to_first_table()
        
        # 3. 获取当前记录数
        before_count = get_second_table_count()
        logger.info(f"同步前记录数: {before_count}")
        
        # 4. 获取新记录和需要更新的记录
        new_records = get_new_records_from_first_table(limit=2)
        existing_records = get_existing_records_from_first_table()
        logger.info(f"发现新记录: {len(new_records)} 条")
        logger.info(f"需要更新记录: {len(existing_records)} 条")
        
        # 5. 插入新记录
        inserted_count = insert_new_records(new_records)
        logger.info(f"成功插入: {inserted_count} 条新记录")
        
        # 6. 更新现有记录
        updated_count = update_existing_records(existing_records)
        logger.info(f"成功更新: {updated_count} 条记录")
        
        # 7. 获取更新后的记录数
        after_count = get_second_table_count()
        logger.info(f"同步后记录数: {after_count}")
        logger.info(f"记录数变化: +{after_count - before_count}")
        
        # 8. 数据同步完成（已移除Excel导出以减少文件产生）
        
        logger.info("=== 数据同步任务完成 ===")
        return {
            "success": True,
            "before_count": before_count,
            "after_count": after_count,
            "inserted_count": inserted_count,
            "updated_count": updated_count,
            "record_change": after_count - before_count
        }
        
    except Exception as e:
        logger.error(f"数据同步任务失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def file_download_task():
    """文件下载任务"""
    logger = logging.getLogger(__name__)
    logger.info("=== 开始文件下载任务 ===")
    
    try:
        # 1. 获取飞书访问令牌
        logger.info("获取飞书访问令牌...")
        access_token = get_feishu_access_token()
        if not access_token:
            raise Exception("无法获取飞书访问令牌")
        logger.info("飞书访问令牌获取成功")
        
        # 2. 确保下载目录存在
        download_dir = Path(settings.save_root)
        download_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"文件保存目录: {download_dir}")
        
        # 3. 获取待下载的记录
        pending_records = get_pending_download_records()
        logger.info(f"待下载项目数量: {len(pending_records)}")
        
        if not pending_records:
            logger.info("没有待下载的项目")
            return {"success": True, "message": "没有待下载的项目", "processed_count": 0}
        
        # 4. 下载文件并更新状态
        success_count = 0
        failed_count = 0
        
        for i, record in enumerate(pending_records, 1):
            manju = str(record.get("漫剧名称", "")).strip()
            submit_time = str(record.get("提交时间", "")).strip()
            zimu_data = str(record.get("字幕分组/分镜", ""))
            miaoshu_data = str(record.get("描述词", ""))
            
            logger.info(f"[{i}/{len(pending_records)}] 处理项目: {manju}")
            
            try:
                # 下载项目文件
                download_success = download_project_files(
                    manju=manju,
                    submit_time=submit_time,
                    zimu_data=zimu_data,
                    miaoshu_data=miaoshu_data,
                    access_token=access_token
                )
                
                if download_success:
                    # 更新状态为已完成
                    update_success = update_makevideo_status(manju, submit_time, 1)
                    if update_success:
                        success_count += 1
                        logger.info(f"✓ 项目 {manju} 处理成功")
                    else:
                        failed_count += 1
                        logger.error(f"✗ 项目 {manju} 文件下载成功但状态更新失败")
                else:
                    failed_count += 1
                    logger.error(f"✗ 项目 {manju} 文件下载失败")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"✗ 项目 {manju} 处理异常: {str(e)}")
        
        # 5. 文件下载完成（已移除Excel导出以减少文件产生）
        
        logger.info(f"=== 文件下载任务完成 ===")
        logger.info(f"总项目数: {len(pending_records)}")
        logger.info(f"成功下载: {success_count}")
        logger.info(f"下载失败: {failed_count}")
        
        return {
            "success": True,
            "total_records": len(pending_records),
            "success_count": success_count,
            "failed_count": failed_count
        }
        
    except Exception as e:
        logger.error(f"文件下载任务失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


def daily_complete_task():
    """每日完整任务（飞书数据拉取 + 数据同步 + 文件下载）"""
    logger = logging.getLogger(__name__)
    start_time = datetime.now()
    logger.info(f"=== 开始每日完整任务 ===")
    logger.info(f"执行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 从飞书拉取最新数据
    logger.info("=== 步骤1: 从飞书拉取数据 ===")
    # 先确保表结构存在
    if not create_database_tables():
        logger.error("数据库表创建失败")
        fetch_result = {"success": False, "error": "数据库表创建失败"}
    else:
        fetch_success = fetch_feishu_data_to_first_table()
        fetch_result = {"success": fetch_success}
    
    # 2. 执行数据同步
    logger.info("=== 步骤2: 数据同步 ===")
    sync_result = data_sync_task()
    
    # 3. 执行文件下载
    logger.info("=== 步骤3: 文件下载 ===")
    download_result = file_download_task()
    
    # 3. 汇总结果
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info(f"=== 每日完整任务结束 ===")
    logger.info(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"总耗时: {duration}")
    
    # 统计信息
    all_success = fetch_result.get("success") and sync_result.get("success") and download_result.get("success")
    
    if all_success:
        logger.info("✓ 所有任务执行成功")
        logger.info(f"  飞书拉取: {'成功' if fetch_result.get('success') else '失败'}")
        logger.info(f"  数据同步: 新增 {sync_result.get('inserted_count', 0)} 条，更新 {sync_result.get('updated_count', 0)} 条")
        logger.info(f"  文件下载: 成功 {download_result.get('success_count', 0)} 个，失败 {download_result.get('failed_count', 0)} 个")
    else:
        logger.error("✗ 部分任务执行失败")
        if not fetch_result.get("success"):
            logger.error(f"  飞书拉取失败: {fetch_result.get('error', '未知错误')}")
        if not sync_result.get("success"):
            logger.error(f"  数据同步失败: {sync_result.get('error', '未知错误')}")
        if not download_result.get("success"):
            logger.error(f"  文件下载失败: {download_result.get('error', '未知错误')}")
    
    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration.total_seconds(),
        "fetch_result": fetch_result,
        "sync_result": sync_result,
        "download_result": download_result
    }


def main():
    """主函数"""
    # 设置日志
    logger = setup_logging()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "sync":
            logger.info("执行数据同步任务...")
            result = data_sync_task()
            
        elif command == "download":
            logger.info("执行文件下载任务...")
            result = file_download_task()
            
        elif command == "daily":
            logger.info("执行每日完整任务...")
            result = daily_complete_task()
            
        elif command == "fetch":
            logger.info("从飞书拉取数据到 first_table...")
            # 先确保表结构存在
            if not create_database_tables():
                logger.error("数据库表创建失败")
                result = {"success": False, "error": "数据库表创建失败"}
            else:
                success = fetch_feishu_data_to_first_table()
                result = {"success": success}
            
        elif command == "clean":
            logger.info("清理测试数据...")
            success = clean_test_data()
            result = {"success": success}
            
        else:
            logger.error(f"未知命令: {command}")
            print("可用命令:")
            print("  python cron_deployment.py fetch    # 从飞书拉取数据")
            print("  python cron_deployment.py sync     # 数据同步")
            print("  python cron_deployment.py download # 文件下载")
            print("  python cron_deployment.py daily    # 每日完整任务")
            print("  python cron_deployment.py clean    # 清理测试数据")
            sys.exit(1)
    else:
        # 默认执行每日完整任务
        logger.info("执行每日完整任务...")
        result = daily_complete_task()
    
    # 输出最终结果
    if result.get("success", True):
        logger.info("任务执行完成")
        sys.exit(0)
    else:
        logger.error("任务执行失败")
        sys.exit(1)


if __name__ == "__main__":
    main()