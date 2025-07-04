import configparser
import os

import chromadb
import pandas as pd
from chromadb.types import Collection
from dotenv import load_dotenv


def load_mysql_config(config_path='config.ini'):
    load_dotenv()
    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"错误: 配置文件 '{config_path}' 不存在。请创建它并包含数据库配置。")

    try:
        config.read(config_path)
        mysql_db_config = {
            'host': config['DATABASE']['host'],
            'port': int(config['DATABASE']['port']),
            'user': config['DATABASE']['user'],
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': config['DATABASE']['db'],
            'charset': config['DATABASE']['charset']
        }

        print("成功从 config.ini 读取 MySQL 配置。\n")
        return mysql_db_config

    except KeyError as e:
        raise KeyError(f"config.ini 中缺少必要的配置项: {e}")
    except Exception as e:
        raise Exception(f"读取 config.ini 时发生未知错误: {e}")


def load_chroma_config(config_path='config.ini'):
    load_dotenv()

    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"错误: 配置文件 '{config_path}' 不存在。请创建它并包含数据库配置。")

    try:
        config.read(config_path)
        chroma_config = {
            'persistent_path': config.get('CHROMADB', 'persistent_path', fallback='./ChromaDatabase'),
            'collection_name': config.get('CHROMADB', 'collection_name', fallback='vulnerability_collection')
        }

        print("成功从 config.ini 读取 ChromaDB 配置。\n")
        return chroma_config

    except KeyError as e:
        raise KeyError(f"config.ini 中缺少必要的配置项: {e}")
    except Exception as e:
        raise Exception(f"读取 config.ini 时发生未知错误: {e}")


# 可单独使用，直接连接到chromadb
def connect_to_chromadb(chroma_config: dict | None = None, collection_name: str | None = None) -> tuple[
    chromadb.Client, Collection]:
    # 从配置中获取参数并设置默认值
    if chroma_config is None:
        chroma_config = load_chroma_config()  # 从config.ini加载配置
    print("chroma_config:", chroma_config)
    persistent_path = chroma_config.get('chroma_persistent_path', './ChromaDatabase')
    print("persistent_path:", persistent_path)
    default_collection_name = chroma_config.get('collection_name', 'default_collection')

    # 确定集合名称
    if collection_name is None:
        collection_name = default_collection_name

    # 确保持久化路径存在
    os.makedirs(persistent_path, exist_ok=True)

    # 创建ChromaDB客户端
    client = chromadb.PersistentClient(path=persistent_path)
    print(f"ChromaDB客户端已初始化 (持久化路径: {persistent_path})")

    # 获取或创建集合
    collection = client.get_or_create_collection(name=collection_name)

    # 打印集合信息
    doc_count = collection.count()
    print(f"已获取/创建集合: {collection_name} (文档数量: {doc_count})")

    return client, collection


# # 将数据从pd->ChromaDB，不展开cve
# def index_dataframe_to_chromadb(df: pd.DataFrame, chroma_client: chromadb.Client, collection_name: str,
#                                 clear_existing_index: bool = False) -> Collection:
#     print("--- 开始执行数据索引流程 ---")
#
#     # --- 步骤 1: 准备集合 ---
#     collection = None
#     if clear_existing_index:
#         print(f"请求清空集合 '{collection_name}' 中的现有数据...")
#         try:
#             chroma_client.delete_collection(name=collection_name)
#             print(f"集合 '{collection_name}' 已成功删除。")
#         except Exception as e:
#             # 这是一个预期的行为，如果集合不存在，删除会失败。
#             print(f"清空集合失败 (可能集合原本就不存在): {e}")
#
#     try:
#         # 无论是清空后还是直接使用，都通过 get_or_create_collection 来获取集合对象
#         collection = chroma_client.get_or_create_collection(name=collection_name)
#         print(f"已成功获取或创建集合: '{collection_name}'。")
#     except Exception as e:
#         print(f"错误：无法获取或创建集合 '{collection_name}'。流程终止。错误信息: {e}")
#         raise  # 抛出异常，因为没有集合对象后续无法进行
#
#     # --- 步骤 2: 准备用于批量添加的列表 ---
#     chroma_ids = []
#     chroma_documents = []
#     chroma_metadatas = []
#
#     # --- 步骤 3: 校验输入数据的格式 ---
#     expected_columns = [
#         'id', 'uuid', 'fingerprint', 'plugin_id', 'cve', 'risk','host','name',
#         'synopsis', 'description', 'timestamp', 'host', 'protocol', 'port'
#     ]
#     print(f"数据校验通过。开始从 {len(df)} 条记录中准备索引数据...")
#
#     # --- 步骤 4: 遍历 DataFrame，转换每一行数据 ---
#     for index, row in df.iterrows():
#         # 使用 'uuid' 作为 ChromaDB 的全局唯一 ID，这是关键的主键
#         if pd.isna(row['uuid']):
#             print(f"警告: 跳过索引为 {index} 的行，因为其 'uuid' 为空，无法作为主键。")
#             continue
#         unique_id = str(row['uuid'])
#
#         # --- 4a. 构建丰富的文档上下文，用于语义搜索 ---
#         doc_host = str(row['host']) if pd.notna(row['host']) else '未知主机'
#         doc_port = str(row['port']) if pd.notna(row['port']) else '未知端口'
#         doc_protocol = str(row['protocol']) if pd.notna(row['protocol']) else '未知协议'
#         doc_risk = str(row['risk']) if pd.notna(row['risk']) else '未指定'
#         doc_name = str(row['name']) if pd.notna(row['name']) else '无名称'
#         doc_synopsis = str(row['synopsis']) if pd.notna(row['synopsis']) else '无摘要'
#         doc_description = str(row['description']) if pd.notna(row['description']) else '无详细描述'
#
#         document_content = (
#             f"漏洞名称：{doc_name}。"
#             f"摘要：{doc_synopsis}。"
#             f"详细描述：{doc_description}"
#         )
#
#         # --- 4b. 构建结构化的元数据，用于精确过滤 ---
#         metadata = {
#             "uuid": unique_id,
#             "host": doc_host,
#             "port": int(row['port']) if pd.notna(row['port']) and str(row['port']).isdigit() else -1,  # 使用-1表示无效或非数字端口
#             "protocol": doc_protocol,
#             "risk": doc_risk,
#             "original_id": str(row['id']) if pd.notna(row['id']) else None,
#             "plugin_id": str(row['plugin_id']) if pd.notna(row['plugin_id']) else None,
#             "cve": str(row['cve']) if pd.notna(row['cve']) else None,
#             "fingerprint": str(row['fingerprint']) if pd.notna(row['fingerprint']) else None,
#             "timestamp": str(row['timestamp']) if pd.notna(row['timestamp']) else None
#         }
#
#         # 将准备好的数据添加到列表中
#         chroma_ids.append(unique_id)
#         chroma_documents.append(document_content)
#         chroma_metadatas.append(metadata)
#
#     # --- 步骤 5: 执行批量添加操作 ---
#     if not chroma_ids:
#         print("警告: 没有有效数据可以添加到 ChromaDB。流程结束。")
#         return collection
#
#     print(f"数据准备完成。开始将 {len(chroma_ids)} 条记录批量添加到 ChromaDB 集合 '{collection_name}'...")
#     try:
#         # 这是函数的核心写入操作
#         collection.add(
#             documents=chroma_documents,
#             metadatas=chroma_metadatas,
#             ids=chroma_ids
#         )
#         print(f"数据添加成功！当前集合中的文档总数: {collection.count()}")
#     except Exception as e:
#         print(f"错误: 将数据添加到 ChromaDB 时发生严重错误。流程终止。错误信息: {e}")
#         raise  # 重新抛出异常，让调用者知道发生了严重问题
#
#     print("--- 数据索引流程成功结束 ---\n")
#     return collection


# 将数据pd->ChromaDB，展开cve
import pandas as pd
import chromadb
from chromadb.types import Collection


def index_dataframe_to_chromadb(
        df: pd.DataFrame,
        chroma_client: chromadb.Client,
        collection_name: str,
        clear_existing_index: bool = False
) -> Collection:
    """
    将经过清理的DataFrame数据索引到ChromaDB，并对包含多个CVE的行进行扁平化处理。

    此函数假设输入的DataFrame已经通过 utils.sanitize_dataframe_for_db() 进行了
    类型安全的空值处理，所有空值都已被替换为明确的哨兵值（如'', -1等）。
    """
    print("--- 开始执行数据索引流程 (支持CVE扁平化和类型安全元数据) ---")

    # --- 步骤 1: 准备集合 ---
    collection = None
    if clear_existing_index:
        print(f"请求清空集合 '{collection_name}' 中的现有数据...")
        try:
            chroma_client.delete_collection(name=collection_name)
            print(f"集合 '{collection_name}' 已成功删除。")
        except Exception:
            pass  # 如果集合不存在，删除会失败，这是正常行为

    collection = chroma_client.get_or_create_collection(name=collection_name)
    print(f"已成功获取或创建集合: '{collection_name}'。")

    # --- 步骤 2: 准备用于批量添加的列表 ---
    chroma_ids = []
    chroma_documents = []
    chroma_metadatas = []

    print(f"开始从 {len(df)} 条记录中准备索引数据...")

    # --- 步骤 3: 遍历DataFrame，转换并扁平化每一行数据 ---
    for index, row in df.iterrows():
        # 3a. 获取源UUID，这是所有子记录的“根”
        # 假设数据已被清理，'uuid'列不会是None或NaN
        source_uuid = str(row['uuid'])

        # 3b. 构建共享的文档上下文，用于语义搜索
        document_content = (
            f"漏洞名称：{row.get('name', '')}。"
            f"摘要：{row.get('synopsis', '')}。"
            f"详细描述：{row.get('description', '')}"
        )

        # 3c. 构建共享的基础元数据模板。
        # 这里的关键是，我们信任传入的row不含None，所有值都可以安全地转换类型。
        base_metadata = {
            "uuid": source_uuid,
            "host": str(row.get('host', '')),
            "port": int(row.get('port', -1)),
            "protocol": str(row.get('protocol', '')),
            "risk": str(row.get('risk', '')),
            "original_id": str(row.get('id', '')),  # original_id来自DataFrame的'id'列
            "plugin_id": str(row.get('plugin_id', '')),
            "fingerprint": str(row.get('fingerprint', '')),
            "timestamp": str(row.get('timestamp', '1970-01-01'))
        }

        # 3d. 处理CVE字段并进行扁平化
        cve_string = row.get('cve', '')
        cve_list = []
        # 只有在cve_string非空时才分割
        if cve_string:
            cve_list = [c.strip() for c in str(cve_string).split(',')]
        else:
            # 如果没有CVE信息，我们仍然需要为这条记录创建一个条目
            # 使用一个特殊值 'NO_CVE' 来确保ID的唯一性
            cve_list = ['NO_CVE']

        # 3e. 遍历拆分后的CVE列表，为每个CVE创建一条记录
        for cve_item in cve_list:
            # 创建唯一的复合ID，这是ChromaDB的实际主键
            composite_id = f"{source_uuid}:cve_{cve_item}"

            # 创建最终的元数据，从模板复制并添加特定的CVE
            final_metadata = base_metadata.copy()
            final_metadata['cve'] = cve_item if cve_item != 'NO_CVE' else ''

            # 将准备好的数据添加到列表中
            chroma_ids.append(composite_id)
            chroma_documents.append(document_content)
            chroma_metadatas.append(final_metadata)

    # --- 步骤 4: 执行批量添加操作 ---
    if not chroma_ids:
        print("警告: 没有有效数据可以添加到 ChromaDB。流程结束。")
        return collection

    print(f"数据准备完成。开始将 {len(chroma_ids)} 条记录批量添加到 ChromaDB 集合 '{collection_name}'...")
    try:
        # 这是函数的核心写入操作
        collection.add(
            documents=chroma_documents,
            metadatas=chroma_metadatas,
            ids=chroma_ids
        )
        print(f"数据添加成功！当前集合中的文档总数: {collection.count()}")
    except Exception as e:
        print(f"错误: 将数据添加到 ChromaDB 时发生严重错误。流程终止。错误信息: {e}")
        raise

    print("--- 数据索引流程成功结束 ---\n")
    return collection


import pandas as pd
import pymysql
from collections import defaultdict

# -------------  文本json->uuid  -----------------
from typing import List, Set, Optional
import chromadb

def query_vulnerabilities_for_uuids(
        query_text: str,
        n_results: int,
        where_clause: Optional[dict],
        chroma_collection: chromadb.Collection,
        parent_id_key: str = 'uuid'
) -> List[str]:
    """
    根据查询条件，从ChromaDB中检索并返回所有相关的不重复的父文档ID。

    Args:
        query_text (str): 语义查询文本。
        n_results (int): 从ChromaDB返回的最相似结果数量。
        # 3. 更新文档字符串
        where_clause (Optional[dict]): ChromaDB的元数据过滤条件。如果传入一个空字典 {}，
                                    将被视为无筛选条件。
        chroma_collection (chromadb.Collection): 已初始化的ChromaDB集合对象。
        parent_id_key (str): 在ChromaDB元数据中，存储父文档ID的键名。

    Returns:
        List[str]: 一个不包含重复项的父文档ID列表。如果无结果，返回空列表。
    """
    print(f"开始检索UUIDs: query='{query_text}', n_results={n_results}, where={where_clause}")

    # ==================== 核心改动 ====================
    # 在查询之前，检查 where_clause 是否为空。
    # ChromaDB 的 query 方法在不进行筛选时，期望 where 参数是 None，而不是一个空字典 {}。
    # 我们在这里进行转换，增强函数的健壮性。
    if where_clause == {}:
        print("信息: 接收到空的where_clause，将不启用元数据筛选。")
        where_clause = None
    # =================================================

    # 步骤 1: 从ChromaDB进行查询
    try:
        # 这里的 where_clause 现在可以是包含条件的字典，也可以是 None
        chroma_results = chroma_collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_clause,
            include=['metadatas']
        )
    except Exception as e:
        print(f"错误: 查询ChromaDB时发生错误: {e}")
        return []

    # 步骤 2 & 3: 提取和处理结果 (这部分无需改动)
    if not chroma_results or not chroma_results['ids'] or not chroma_results['ids'][0]:
        print("ChromaDB 没有返回任何匹配结果。")
        return []

    parent_ids: Set[str] = set()
    retrieved_metadatas = chroma_results['metadatas'][0]

    for metadata in retrieved_metadatas:
        parent_id = metadata.get(parent_id_key)
        if parent_id:
            parent_ids.add(parent_id)

    unique_parent_ids = list(parent_ids)
    print(
        f"检索完成。从 {len(retrieved_metadatas)} 个ChromaDB条目中，找到了 {len(unique_parent_ids)} 个不重复的父文档UUID。")
    return unique_parent_ids

# uuid->pd
# 假设这两个函数已经正确导入

from utils import decode_uuid


# 使用uuid名称列表访问mysql得到原始pd文档


def get_full_documents_from_mysql(uuids_from_chroma: list, db_name: str = "rag"):
    # 文件里面会有is_indexed_to_chroma，导出的时候需要删除
    """
    根据给定的UUID列表，从MySQL数据库中获取完整的文档记录。
    此函数会解码UUID以确定表名（格式为 YYYY_MM_DD），并聚合查询。

    Args:
        uuids_from_chroma (list): 从ChromaDB等来源获取的UUID字符串列表。
        db_name (str, optional): 可选的数据库名称。如果为None，则连接到默认数据库。

    Returns:
        pd.DataFrame: 包含所有查询到的完整文档记录的Pandas DataFrame。
    """
    # 会产生循环引用，所以放在代码里面
    from MySqlSource import connect_to_mysql
    if not uuids_from_chroma:
        return pd.DataFrame()

    # 1. 解码UUID并按表名分组
    ids_by_table = defaultdict(list)
    for uuid in uuids_from_chroma:
        date_str, original_id = decode_uuid(uuid)

        if date_str and original_id is not None:
            # --- 核心修改：将 YYYY-MM-DD 转换为 YYYY_MM_DD ---
            # 这是一个安全、合法的表名，不需要特殊引用。
            table_name = date_str.replace('-', '_')
            ids_by_table[table_name].append(original_id)
        else:
            print(f"警告: 跳过无法解码或解码不完整的UUID '{uuid}'")

    if not ids_by_table:
        return pd.DataFrame()

    # 2. 批量查询数据库
    all_records = []
    conn = None
    try:

        conn = connect_to_mysql(db_name=db_name)
        if conn:
            with conn.cursor() as cursor:
                for table_name, ids in ids_by_table.items():
                    id_placeholders = ', '.join(['%s'] * len(ids))

                    # 使用反引号包裹表名是一个好习惯，可以防止与SQL关键字冲突，虽然在这里不是必须的。
                    sql_query = f"SELECT * FROM `{table_name}` WHERE id IN ({id_placeholders});"

                    try:
                        cursor.execute(sql_query, tuple(ids))
                        records = cursor.fetchall()
                        all_records.extend(records)
                    except pymysql.MySQLError as table_err:
                        print(f"查询表 '{table_name}' 时出错: {table_err} (可能是表不存在)")
                        continue
        else:
            print("无法建立 MySQL 连接，跳过数据获取。")

    except pymysql.MySQLError as err:
        print(f"数据库操作时发生错误: {err}")
    finally:
        if conn:
            conn.close()

    # 3. 将所有结果合并为单个DataFrame
    return pd.DataFrame(all_records) if all_records else pd.DataFrame()
