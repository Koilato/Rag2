import configparser
import os

import numpy as np
import pandas as pd
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

import VectorDatabase


def connect_to_mysql(db_name=None):
    """
    1. 连接到 MySQL 服务器 (配置与密钥分离的最佳实践)
    - 从 config.ini 读取非敏感配置。
    - 从 .env 安全地加载密码。
    - 确保配置项类型正确 (如 port 为整数)。
    """
    config_parser = configparser.ConfigParser()

    if not config_parser.read('config.ini'):
        print("错误: 找不到或无法读取 config.ini 文件。")
        return None

    try:
        db_config = dict(config_parser['DATABASE'])
    except KeyError:
        print("错误: config.ini 文件中缺少 [DATABASE] 节。")
        return None

    # --- 关键修正：将 port 转换为整数 ---
    if 'port' in db_config:
        try:
            # 将字符串类型的端口号转换为整数类型
            db_config['port'] = int(db_config['port'])
        except ValueError:
            print(f"错误: config.ini 中的 port '{db_config['port']}' 不是一个有效的数字。")
            return None

    load_dotenv()
    db_password = os.getenv('MYSQL_PASSWORD')
    if not db_password:
        print("错误: .env 文件中未设置 DB_PASSWORD。")
        return None

    db_config['password'] = db_password
    db_config['cursorclass'] = pymysql.cursors.DictCursor

    if db_name:
        db_config['db'] = db_name

    try:
        connection = pymysql.connect(**db_config)
        print(f"成功连接到 MySQL" + (f" 数据库 '{db_name}'" if db_name else " 服务器"))
        return connection
    except pymysql.MySQLError as e:
        print(f"连接失败: {e}")
        return None


def close_connection(connection):
    if connection:
        connection.close()
        print("数据库连接已关闭。")


def create_database(connection, db_name):
    """2. 创建一个新的数据库"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
        connection.commit()
        print(f"数据库 '{db_name}' 创建成功或已存在。")
        return True
    except pymysql.MySQLError as e:
        print(f"创建数据库 '{db_name}' 失败: {e}")
        return False


def delete_database(connection, db_name):
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        connection.commit()
        print(f"数据库 '{db_name}' 已被删除。")
        return True
    except pymysql.MySQLError as e:
        print(f"删除数据库 '{db_name}' 失败: {e}")
        return False


# ------------------------------------------------------------------------------------------- #


# 辅助函数：检查表是否存在
def table_exists(connection, table_name, db_name=None):
    try:
        with connection.cursor() as cursor:
            if db_name:
                cursor.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_name = %s",
                    (db_name, table_name)
                )
            else:
                cursor.execute("SHOW TABLES LIKE %s", (table_name,))
            return cursor.fetchone() is not None
    except:
        return False


def create_pd_table(connection, db_name, table_name,
                    columns_definition=None, primary_key=None, unique_keys=None, foreign_keys=None,
                    check_exists=True, use_vulnerability_template=False):
    """
    动态创建数据库表，可选择使用预定义的漏洞表模板。
    创表中加入 is_indexed_to_chroma 字段

    :param connection: pymysql 的数据库连接对象
    :param db_name: 数据库名
    :param table_name: 表名
    :param columns_definition: 列定义字典，格式：{列名: 类型}。使用模板时可忽略。
    :param primary_key: 主键列名。使用模板时可忽略。
    :param unique_keys: 唯一键列表（可选），格式：['列名1', '列名2']
    :param foreign_keys: 外键定义列表（可选），格式：[(外键列, 引用表, 引用列)]
    :param check_exists: 是否检查表已存在
    :param use_vulnerability_template: 若为True，则使用内置的漏洞表模板创建表
    :return: True 表示成功或已存在，False 表示失败。
    """

    if use_vulnerability_template:
        print(f"检测到 'use_vulnerability_template=True'，将使用预定义的、包含同步状态字段的漏洞表模板。")
        # --- 核心修改在此处 ---
        columns_definition = {
            # 您原有的字段 (我保留了您之前的定义，不做改动)
            'id': 'INT UNSIGNED',
            'uuid': 'VARCHAR(20)',
            'fingerprint': 'VARCHAR(32)',
            'plugin_id': 'INT UNSIGNED',
            'cve': 'TEXT',
            'cvss_v2_0_base_score': 'DECIMAL(3, 1)',
            'risk': 'VARCHAR(10)',
            'host': 'VARCHAR(255)',
            'protocol': 'VARCHAR(10)',
            'port': 'INT UNSIGNED',
            'name': 'VARCHAR(255)',
            'synopsis': 'TEXT',
            'description': 'TEXT',
            'solution': 'TEXT',
            'see_also': 'TEXT',
            'plugin_output': 'MEDIUMTEXT',
            'stig_severity': 'VARCHAR(10)',
            'cvss_v3_0_base_score': 'DECIMAL(3, 1)',
            'cvss_v2_0_temporal_score': 'DECIMAL(3, 1)',
            'cvss_v3_0_temporal_score': 'DECIMAL(3, 1)',
            'risk_factor': 'VARCHAR(15)',
            'bid': 'VARCHAR(255)',
            'xref': 'TEXT',
            'mskb': 'VARCHAR(255)',
            'plugin_publication_date': 'DATE',
            'plugin_modification_date': 'DATE',
            'timestamp': 'VARCHAR(15)',
            'is_indexed_to_chroma': 'BOOLEAN NOT NULL DEFAULT FALSE'
        }
        primary_key = 'id'
        unique_keys = ['fingerprint']  # 保留您之前的唯一键定义
        # --- 结束修改 ---

    if not columns_definition:
        print("错误：未提供列定义（columns_definition），且未启用模板。")
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute(f"USE `{db_name}`")

            if check_exists and table_exists(connection, table_name, db_name):
                print(f"表 '{db_name}.{table_name}' 已存在，跳过创建。")
                return True

            columns_sql = []
            for col_name, col_type in columns_definition.items():
                columns_sql.append(f"`{col_name}` {col_type}")

            if primary_key:
                columns_sql.append(f"PRIMARY KEY (`{primary_key}`)")

            if unique_keys:
                for uk_col in unique_keys:
                    uk_name = f"uq_{uk_col}"
                    columns_sql.append(f"UNIQUE KEY `{uk_name}` (`{uk_col}`)")

            # --- 为状态字段创建索引 ---
            if use_vulnerability_template:
                columns_sql.append("INDEX `idx_is_indexed_to_chroma` (`is_indexed_to_chroma`)")

            if foreign_keys:
                for fk_col, ref_table, ref_col in foreign_keys:
                    fk_name = f"fk_{table_name}_{fk_col}"
                    columns_sql.append(
                        f"CONSTRAINT `{fk_name}` FOREIGN KEY (`{fk_col}`) "
                        f"REFERENCES `{ref_table}` (`{ref_col}`)"
                    )

            columns_sql_str = ",\n\t".join(columns_sql)
            create_sql = f"""
            CREATE TABLE `{table_name}` (
                {columns_sql_str}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            print("--- 将要执行的SQL ---")
            print(create_sql)
            print("--------------------")

            cursor.execute(create_sql)
            print(f"表 '{db_name}.{table_name}' 创建成功，并已包含 'is_indexed_to_chroma' 字段及索引。")
            return True

    except pymysql.MySQLError as e:
        print(f"创建表失败: {e}")
        return False


# pd->mysql
def insert_vulnerability_data(connection, table_name: str, df: pd.DataFrame) -> int:
    if df.empty:
        print("信息: 输入的 DataFrame 为空，没有数据需要插入。")
        return 0

    # 1. 定义数据库表列名
    REQUIRED_COLUMNS = [
        'id', 'uuid', 'plugin_id', 'cve', 'cvss_v2_0_base_score', 'risk',
        'host', 'protocol', 'port', 'name', 'synopsis', 'description',
        'solution', 'see_also', 'plugin_output', 'stig_severity',
        'cvss_v3_0_base_score', 'cvss_v2_0_temporal_score',
        'cvss_v3_0_temporal_score', 'risk_factor', 'bid', 'xref', 'mskb',
        'plugin_publication_date', 'plugin_modification_date', 'timestamp',
        'fingerprint', 'is_indexed_to_chroma'
    ]

    # 2. 验证 DataFrame 是否包含所有必需的列
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        print(f"错误: 输入的 DataFrame 缺少必需的列: {', '.join(missing_cols)}")
        return -1

    try:
        with connection.cursor() as cursor:
            # 3. 构建 INSERT IGNORE SQL 语句
            # 这是此策略的核心，将去重逻辑完全交给数据库处理。
            cols = ", ".join([f"`{c}`" for c in REQUIRED_COLUMNS])
            placeholders = ", ".join(["%s"] * len(REQUIRED_COLUMNS))
            sql = f"INSERT IGNORE INTO `{table_name}` ({cols}) VALUES ({placeholders})"  # <--- 关键在这里

            # 4. 准备待插入的数据元组
            data_tuples = list(
                map(
                    tuple,
                    df[REQUIRED_COLUMNS]
                    .replace({np.nan: None, pd.NaT: None, '': None})
                    .to_numpy()
                )
            )

            if not data_tuples:
                print("信息: 准备插入的数据为空，操作完成。")
                return 0

            # 5. 高效执行批量插入
            rows_affected = cursor.executemany(sql, data_tuples)

        connection.commit()
        print(f"成功向表 '{table_name}' 插入了 {rows_affected} 条新数据 (已存在的重复数据被自动忽略)。")
        return rows_affected

    except pymysql.MySQLError as e:
        print(f"批量插入数据到表 '{table_name}' 时失败: {e}")
        connection.rollback()
        return -1


# 从单表中读取 is_to_chroma=0 的内容，保留列名称和is_to_chroma字段
def get_max_id(connection, table_name: str, id_column: str = 'id') -> int:
    """
    获取指定表、指定ID列的最大值。
    如果表不存在或为空，则返回 0，以便调用方 +1 后从 1 开始。

    :param connection: 数据库连接对象。
    :param table_name: 目标数据库表名。
    :param id_column: 主键列的名称，默认为 'id'。
    :return: 表中最大的ID值，如果表为空或不存在则返回 0。
    """
    try:
        with connection.cursor() as cursor:
            # 1. 检查表是否存在
            cursor.execute("SHOW TABLES LIKE %s", (table_name,))
            if not cursor.fetchone():
                print(f"信息: 表 '{table_name}' 不存在，ID将从 1 开始。")
                return 0

            # 2. 检查表是否为空
            # 使用聚合函数COUNT来检查，比SELECT *高效
            cursor.execute(f"SELECT COUNT(`{id_column}`) AS count FROM `{table_name}`")
            if cursor.fetchone()['count'] == 0:
                print(f"信息: 表 '{table_name}' 为空，ID将从 1 开始。")
                return 0

            # 3. 表不为空，查询最大ID
            cursor.execute(f"SELECT MAX(`{id_column}`) AS max_id FROM `{table_name}`")
            result = cursor.fetchone()
            max_id = result['max_id']

            print(f"信息: 表 '{table_name}' 当前最大ID为 {max_id}。")
            return int(max_id) if max_id is not None else 0

    except (pymysql.MySQLError, KeyError) as e:
        print(f"错误: 在查询表 '{table_name}' 的最大ID时出错: {e}")
        # 向上抛出异常，让调用方决定如何处理错误
        raise


# 读取特定数据库中所有表的is_to_chroma=0的记录并转换为Pandas DataFrame
# 返回类型	dict[str, pd.DataFrame] (按表分离)
def select_is_to_chroma_data(connection, db_name, is_to_chroma_col='is_to_chroma', batch_size=10000):
    """
    读取特定数据库中所有表的is_to_chroma=0的记录并转换为Pandas DataFrame
    """
    all_tables_data = {}

    try:
        with connection.cursor() as cursor:
            # 获取指定数据库中的所有表名
            cursor.execute(f"USE `{db_name}`")
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]

            if not tables:
                print(f"数据库 '{db_name}' 中没有找到表")
                return all_tables_data

            print(f"开始处理数据库 '{db_name}' 中的 {len(tables)} 个表")

            # 遍历每个表
            for table_name in tables:
                # 检查表是否存在is_to_chroma列
                cursor.execute(f"""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = %s 
                    AND TABLE_NAME = %s 
                    AND COLUMN_NAME = %s
                """, (db_name, table_name, is_to_chroma_col))

                if not cursor.fetchone():
                    print(f"表 '{table_name}' 不包含 '{is_to_chroma_col}' 列，跳过")
                    continue

                # 查询is_to_chroma=0的记录总数
                cursor.execute(f"SELECT COUNT(*) as total FROM `{table_name}` WHERE `{is_to_chroma_col}` = 0")
                total_records = cursor.fetchone()['total']

                if total_records == 0:
                    print(f"表 '{table_name}' 中没有is_to_chroma=0的记录")
                    all_tables_data[table_name] = pd.DataFrame()  # 返回空DataFrame
                    continue

                print(f"从表 '{table_name}' 读取 {total_records} 条is_to_chroma=0的记录")

                # 分批查询数据，避免内存溢出
                offset = 0
                all_records = []

                while True:
                    cursor.execute(f"""
                        SELECT * 
                        FROM `{table_name}` 
                        WHERE `{is_to_chroma_col}` = 0 
                        LIMIT %s OFFSET %s
                    """, (batch_size, offset))

                    records = cursor.fetchall()
                    if not records:
                        break

                    all_records.extend(records)
                    offset += len(records)
                    print(f"  已读取 {offset}/{total_records} 条记录")

                # 转换为DataFrame
                if all_records:
                    df = pd.DataFrame(all_records)
                    all_tables_data[table_name] = df
                    print(f"表 '{table_name}' 的数据已转换为DataFrame，形状: {df.shape}")
                else:
                    all_tables_data[table_name] = pd.DataFrame()
                    print(f"表 '{table_name}' 没有符合条件的记录")

    except pymysql.MySQLError as e:
        print(f"查询数据失败: {e}")
        return all_tables_data

    return all_tables_data


# 从数据库中的全部表里读取 is_to_chroma=0 的内容，保留列名称和is_to_chroma字段
# pd.DataFrame (所有数据合并)
def fetch_unindexed_data_from_all_tables(connection, db_name: str,
                                         status_column: str = 'is_indexed_to_chroma') -> pd.DataFrame:
    """
    扫描指定数据库中的所有表，提取尚未被索引的行，并聚合成一个 Pandas DataFrame。
    从数据库中的全部表里读取 is_to_chroma=0 的内容，保留列名称和is_to_chroma字段
    pd.DataFrame (所有数据合并)
    """
    all_unindexed_dfs = []
    total_rows_found = 0

    try:
        with connection.cursor() as cursor:
            # 1. 切换到目标数据库
            cursor.execute(f"USE `{db_name}`")

            # 2. 获取数据库中的所有表名
            cursor.execute("SHOW TABLES")
            tables = [table[f'Tables_in_{db_name}'] for table in cursor.fetchall()]

            if not tables:
                print(f"信息: 数据库 '{db_name}' 中没有找到任何表。")
                return pd.DataFrame()

            print(f"在数据库 '{db_name}' 中找到 {len(tables)} 个表，开始扫描未索引数据...")

            # 3. 遍历每个表，查询未索引的数据
            for table_name in tables:
                print(f"  -> 正在扫描表: '{table_name}'...")
                try:
                    # 使用参数化查询防止SQL注入，尽管这里列名是硬编码的，但这是最佳实践
                    # 查询 is_indexed_to_chroma = FALSE (或 0) 的行
                    query = f"SELECT * FROM `{table_name}` WHERE `{status_column}` = %s"
                    cursor.execute(query, (0,))  # FALSE 在SQL中等价于 0

                    results = cursor.fetchall()

                    if results:
                        num_found = len(results)
                        total_rows_found += num_found
                        print(f"     ✅ 在 '{table_name}' 中找到 {num_found} 条未索引的记录。")
                        # 将查询结果（字典列表）转换为DataFrame
                        df = pd.DataFrame(results)
                        all_unindexed_dfs.append(df)
                    else:
                        print(f"     - 在 '{table_name}' 中没有未索引的记录。")

                except pymysql.MySQLError as e:
                    # 如果特定表查询失败（例如，它没有 status_column），则打印警告并继续
                    print(f"     ⚠️ 警告: 无法从表 '{table_name}' 查询数据。错误: {e}")
                    print(f"     跳过此表。请确保它包含 '{status_column}' 列或从扫描中排除。")
                    continue

        # 4. 将所有收集到的 DataFrame 合并成一个
        if not all_unindexed_dfs:
            print("\n扫描完成: 未在任何表中找到新的未索引数据。")
            return pd.DataFrame()

        print(f"\n扫描完成: 共找到 {total_rows_found} 条未索引记录。正在合并数据...")
        final_df = pd.concat(all_unindexed_dfs, ignore_index=True)
        print("数据合并成功。")
        return final_df

    except pymysql.MySQLError as e:
        print(f"错误: 操作数据库 '{db_name}' 时失败: {e}")
        return pd.DataFrame()


import chromadb


# 将单个表中的 is_indexed_to_chroma=0 的值给放到chromadb中后，修改is_indexed_to_chroma=1
def sync_mysql_to_chromadb(
        connection,
        chroma_client: chromadb.Client,
        db_name: str,
        table_name: str,
        collection_name: str,
        batch_size: int = 500
) -> (int, int):
    print(f"\n--- 开始执行 MySQL -> ChromaDB 增量同步调度 (批次大小: {batch_size}) ---")

    try:
        # --- 步骤 1: 从 MySQL 中分批读取“未索引”的数据 ---
        connection.select_db(db_name)
        with connection.cursor() as cursor:
            query_sql = f"SELECT * FROM `{table_name}` WHERE `is_indexed_to_chroma` = FALSE LIMIT %s"
            cursor.execute(query_sql, (batch_size,))
            results = cursor.fetchall()

        if not results:
            print("信息: 没有需要同步到 ChromaDB 的新数据。调度完成。")
            return (0, 0)

        # 将查询结果转换为 Pandas DataFrame
        incremental_df = pd.DataFrame(results)
        print(f"从 MySQL 中查询到 {len(incremental_df)} 条新数据，准备交由处理函数进行索引。")

        # --- 步骤 2: 调用核心处理函数来执行索引 ---
        # 注意：这里的 clear_existing_index 必须为 False，因为我们是在做增量添加
        collection = VectorDatabase.index_dataframe_to_chromadb(
            df=incremental_df,
            chroma_client=chroma_client,
            collection_name=collection_name,
            clear_existing_index=False
        )

        # 记录成功处理的数量
        processed_count = len(incremental_df)

        # --- 步骤 3: 如果索引成功，更新 MySQL 中的状态 ---
        uuids_to_update = incremental_df['uuid'].tolist()

        with connection.cursor() as cursor:
            # 使用 executemany 以获得更好的性能和安全性
            update_sql = f"UPDATE `{table_name}` SET `is_indexed_to_chroma` = TRUE WHERE `uuid` = %s"
            # 准备待更新的 uuid 元组列表
            update_tuples = [(uuid,) for uuid in uuids_to_update]
            rows_updated = cursor.executemany(update_sql, update_tuples)

        connection.commit()
        print(f"成功在 MySQL 中将 {rows_updated} 条记录的状态更新为“已索引”。")
        print(f"--- 增量同步调度批次成功结束 ---\n")

        return (processed_count, rows_updated)

    except Exception as e:
        print(f"错误: 在同步调度过程中发生严重错误: {e}")
        if connection and connection.open:
            connection.rollback()
        return (-1, -1)
