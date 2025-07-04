# transform_data.py
import os
import time

import numpy as np
import pandas as pd
import xxhash
from dotenv import load_dotenv
from hashids import Hashids

import MySqlSource


# nessus->pd
def transform_nessus_data(csv_file_path: str) -> pd.DataFrame:
    """
    清理、转换和丰富原始 Nessus 数据框，使其具备数据库存储条件。工作流程遵循以下具体步骤：

    1.过滤风险值无效的行
    2.合并重复发现项（基于插件 ID、主机和端口），并整合 CVE 信息
    3.为每个结果行生成唯一指纹
    4.基于源文件的创建时间添加 YYYY_MM_DD 格式的时间戳
    5.标准化数据类型（包括日期格式）以适配数据库存储

    参数说明：
    :param csv_file_path: 原始 CSV 文件的路径，用于获取文件创建时间
    """
    # ... (前面的代码部分保持不变) ...
    df = pd.read_csv(csv_file_path)

    if len(df) < 1:
        raise ValueError(f"CSV文件 '{csv_file_path}' 有效信息为空或仅包含表头。")
    if 'Risk' in df.columns:
        df = df.dropna(subset=['Risk'])
        if df.empty:
            print("警告：在删除'Risk'为空的行后，DataFrame为空。")
            return df

    if len(df) < 1:
        raise ValueError(f"CSV文件 '{csv_file_path}' 有效信息为空或仅包含表头。")

    print("步骤 2: 合并重复漏洞的CVE并去重...")
    grouping_key = ['Plugin ID', 'Host', 'Port']
    agg_functions = {
        col: 'first' for col in df.columns if col not in grouping_key
    }
    if 'CVE' in df.columns:
        agg_functions['CVE'] = lambda cves: ','.join(
            sorted(c for c in cves.unique() if pd.notna(c) and c != '')
        )
    df_transformed = df.groupby(grouping_key).agg(agg_functions).reset_index()
    print(f"  - 合并后，记录数从 {len(df)} 减少到 {len(df_transformed)}")
    df = df_transformed

    print("步骤 3: 为每条记录生成指纹和时间戳...")
    print("  - 正在生成指纹...")
    raw_strings_for_fingerprint = (df['Plugin ID'].astype(str) + '-' +
                                   df['Host'].astype(str) + '-' +
                                   df['Port'].astype(str))
    fingerprints = [xxhash.xxh64(s.encode('utf-8')).hexdigest() for s in raw_strings_for_fingerprint]

    print("  - 正在添加时间戳...")
    try:
        file_creation_time = os.path.getctime(csv_file_path)
        # <-- 关键修改: 格式化为 YYYY_MM_DD
        scan_date = time.strftime('%Y_%m_%d', time.localtime(file_creation_time))
    except FileNotFoundError:
        print(f"警告: 找不到源文件 '{csv_file_path}'，将使用当前日期作为时间戳。")
        # <-- 关键修改: 格式化为 YYYY_MM_DD
        scan_date = pd.to_datetime('today').strftime('%Y_%m_%d')

    print("  - 正在将新列添加到DataFrame...")
    df = df.assign(
        fingerprint=fingerprints,
        timestamp=scan_date
    )

    print("步骤 4: 标准化数据类型...")
    numeric_cols = ['CVSS v2.0 Base Score', 'CVSS v3.0 Base Score',
                    'CVSS v2.0 Temporal Score', 'CVSS v3.0 Temporal Score']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    date_cols = ['Plugin Publication Date', 'Plugin Modification Date']
    for col in date_cols:
        if col in df.columns:
            # <-- 关键修改: 将日期转换为 YYYY_MM_DD 格式的字符串
            # 这会将该列的数据类型变为字符串，但格式符合要求
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y_%m_%d')

    # ... (后面的列名映射和对齐部分保持不变) ...
    print("步骤 5: 对齐列名以匹配数据库 Schema...")
    column_mapping = {
        'Plugin ID': 'plugin_id', 'CVE': 'cve', 'CVSS v2.0 Base Score': 'cvss_v2_0_base_score',
        'fingerprint': 'fingerprint',
        'Risk': 'risk', 'Host': 'host', 'Protocol': 'protocol', 'Port': 'port', 'Name': 'name',
        'Synopsis': 'synopsis', 'Description': 'description', 'Solution': 'solution',
        'See Also': 'see_also', 'Plugin Output': 'plugin_output', 'STIG Severity': 'stig_severity',
        'CVSS v3.0 Base Score': 'cvss_v3_0_base_score', 'CVSS v2.0 Temporal Score': 'cvss_v2_0_temporal_score',
        'CVSS v3.0 Temporal Score': 'cvss_v3_0_temporal_score', 'Risk Factor': 'risk_factor',
        'BID': 'bid', 'XREF': 'xref', 'MSKB': 'mskb',
        'Plugin Publication Date': 'plugin_publication_date',
        'Plugin Modification Date': 'plugin_modification_date',
        'timestamp': 'timestamp',
        'is_indexed_to_chroma': 'is_indexed_to_chroma'
    }
    df.rename(columns=column_mapping, inplace=True)
    final_columns = list(column_mapping.values())
    for col in final_columns:
        if col not in df.columns:
            df[col] = None
    df_final = df[final_columns]
    print("最终输出列名:", df_final.columns.tolist())
    df_final.to_csv(r'H:\RagCline\out.csv', index=False)
    print("数据转换完成。")
    return df_final


# def add_ids_and_uuid_inplace(
#         connection,
#         df: pd.DataFrame,
#         table_name: str,
#         filename: str,  # <-- 关键修改: 格式现在应为 'YYYY_MM_DD'
#         id_column: str = 'id'
# ) -> None:
#     """
#     【高效就地修改版】为DataFrame添加id、uuid，并清理空值。
#     1. 添加自增ID。
#     2. 添加基于 YYYY_MM_DD 格式文件名的可逆UUID。
#     3. 使用高效的 .replace() 方法将所有空值替换为Python的None。
#
#     警告：此函数会直接修改传入的DataFrame对象。
#     """
#     load_dotenv()
#     if df.empty:
#         print("信息: DataFrame为空，无需操作。")
#         return
#     try:
#         print(f"正在为表 '{table_name}' 决定ID起始值...")
#         max_id = MySqlSource.get_max_id(connection, table_name, id_column)
#         next_id_start = max_id + 1
#         print(f"信息: 当前最大ID为 {max_id}，新ID将从 {next_id_start} 开始计算。")
#         df[id_column] = np.arange(next_id_start, next_id_start + len(df))
#
#         print("正在生成 'uuid'...")
#         # <-- 关键修改: 将_替换为空，以匹配 YYYY_MM_DD 格式
#         extracted_value_str = filename.replace('_', '')
#         try:
#             extracted_value_int = int(extracted_value_str)
#         except ValueError:
#             print(f"错误: 无法将文件名部分 '{extracted_value_str}' 转换为整数。")
#             raise
#
#         HASH_SALT = os.getenv("HASH_SALT", "fallback_default_salt")
#         hashids_encoder = Hashids(salt=HASH_SALT, min_length=11)
#         generated_uuids = [
#             hashids_encoder.encode(extracted_value_int, row_id)
#             for row_id in df[id_column]
#         ]
#         df['uuid'] = generated_uuids
#         print("ID和可逆的UUID已添加完成。")
#
#         print("正在高效地将所有 NaN 和 NaT 值就地转换成 Python 的 None...")
#         df.replace({np.nan: None, pd.NaT: None, '': None}, inplace=True)
#         print("所有空值已成功就地转换为 None。")
#         print("\n最终数据准备完成。")
#     except Exception as e:
#         print(f"错误: 在为 '{table_name}' 准备数据时失败: {e}")
#         raise RuntimeError(f"无法为表 '{table_name}' 准备最终数据。") from e
#
#
# def decode_uuid(uuid_str: str) -> tuple[str | None, int | None]:
#     """
#     解码UUID，返回 (YYYY_MM_DD 格式的日期, 原始ID)
#     """
#     load_dotenv()
#     HASH_SALT = os.getenv("HASH_SALT", "fallback_default_salt")
#     MIN_LENGTH = 11
#
#     try:
#         hashids_decoder = Hashids(salt=HASH_SALT, min_length=MIN_LENGTH)
#         decoded_values = hashids_decoder.decode(uuid_str)
#         if not decoded_values or len(decoded_values) < 2:
#             print(f"警告: UUID '{uuid_str}' 解码失败或结果不完整。解码结果: {decoded_values}")
#             return None, None
#
#         extracted_value_int, original_id = decoded_values[0], decoded_values[1]
#         date_str_raw = str(extracted_value_int)
#
#         if len(date_str_raw) == 8 and date_str_raw.isdigit():
#             year = date_str_raw[:4]
#             month = date_str_raw[4:6]
#             day = date_str_raw[6:]
#             # <-- 关键修改: 格式化为 YYYY_MM_DD
#             formatted_date_str = f"{year}_{month}_{day}"
#         else:
#             print(f"警告: 解码出的日期整数 '{extracted_value_int}' 格式无效 (期望 YYYYMMDD)。")
#             return None, None
#
#         return formatted_date_str, original_id
#
#     except Exception as e:
#         print(f"错误: 解码UUID '{uuid_str}' 时发生异常: {e}")
#         return None, None
