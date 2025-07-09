# H:\Rag2\utils.py

import os
import numpy as np
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from hashids import Hashids
# 确保你的 MySqlSource 模块可以被正确导入
import MySqlSource

# --- 【修改1: 结构优化】---
# 将 load_dotenv() 移至模块顶层。
# 原因: 保证环境变量在任何函数被调用前都已加载，且在整个应用生命周期中只执行一次，提高效率。
load_dotenv()


def sanitize_dataframe_for_db(df: pd.DataFrame) -> None:
    """
    【最终健壮版】就地清理DataFrame，用明确的、类型安全的哨兵值替换空值。
    此版本修复了全空浮点数列的边界情况。

    警告: 此函数会直接修改传入的DataFrame对象。
    """
    print("正在根据类型安全的策略清理空值...")

    for col in df.columns:
        if df[col].isnull().all():
            print(f"  - 警告: 列 '{col}' 完全为空，跳过清理。")
            continue

        # 1. 处理日期时间类型
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            print(f"  - 清理日期列 '{col}' -> '1970-01-01'")
            df[col] = df[col].fillna(pd.Timestamp('1970-01-01')).dt.strftime('%Y-%m-%d')
            continue

        # --- 【修改2: 关键错误修复与逻辑重构】---
        # 原因: 修复了原逻辑中一个全空的浮点数列会被错误识别为整数列的边界情况。
        #      重构了判断逻辑，使其更清晰、更健壮。
        # 2. 处理浮点数类型
        if pd.api.types.is_float_dtype(df[col]):
            series_after_dropna = df[col].dropna()

            # 判断是否是“整数型”浮点数（即所有非空值都是整数，如 1.0, 2.0）
            is_int_like_float = (
                    not series_after_dropna.empty and  # 关键检查点1: 确保有非空值存在
                    series_after_dropna.mod(1).eq(0).all()  # 关键检查点2: 检查所有非空值的小数部分是否为0
            )

            if is_int_like_float:
                print(f"  - 清理整数型浮点数列 '{col}' -> -1")
                df[col] = df[col].fillna(-1).astype(int)
            else:
                # 对于纯浮点数列 或 全空的浮点数列，都按浮点数处理
                print(f"  - 清理纯浮点数列 '{col}' -> -1.0")
                df[col] = df[col].fillna(-1.0)
            continue
        # --- 结束修改2 ---

        # 3. 处理原生整数类型
        if pd.api.types.is_integer_dtype(df[col]):
            print(f"  - 清理整数列 '{col}' -> -1")
            df[col] = df[col].fillna(-1).astype(int)
            continue

        # 4. 处理对象/字符串类型
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            print(f"  - 清理字符串/对象列 '{col}' -> ''")
            df[col] = df[col].fillna('').astype(str).replace({'None': '', 'nan': '', 'NaT': ''})
            continue

    print("类型安全的空值清理完成。")


def add_ids_and_uuid(
        connection,
        db_name: str,  # 添加 db_name 参数
        df: pd.DataFrame,
        table_name: str,
        filename: str,
        id_column: str = 'id'
) -> pd.DataFrame:
    """
    为DataFrame添加ID、UUID并清理，将其完全准备为可入库状态。

    修改内容:
    - 此函数现在返回一个【新的DataFrame副本】，而不是在原地修改传入的对象。
    - 这样可以避免意外的副作用，保护原始数据不被篡改，是更安全、更专业的编程实践。

    返回:
        pd.DataFrame: 一个经过完整处理的、新的DataFrame。
    """
    if df.empty:
        print("信息: DataFrame为空，无需操作。")
        return df  # 直接返回空的DataFrame

    # 原因: 创建一个副本进行操作，避免修改原始传入的DataFrame。这使得函数没有副作用，
    #      代码更可预测、更安全，也更容易在复杂的数据管道中被重用。
    df_copy = df.copy()

    try:
        # 所有后续操作都在 df_copy 上进行
        print(f"正在为表 '{db_name}.{table_name}' 决定ID起始值...")
        max_id = MySqlSource.get_max_id(connection, db_name, table_name, id_column)
        next_id_start = max_id + 1
        print(f"信息: 当前最大ID为 {max_id}，新ID将从 {next_id_start} 开始计算。")

        df_copy[id_column] = np.arange(next_id_start, next_id_start + len(df_copy))

        print("正在生成 'uuid'...")
        extracted_value_str = filename.replace('_', '')
        try:
            extracted_value_int = int(extracted_value_str)
        except ValueError:
            print(f"错误: 无法将文件名部分 '{extracted_value_str}' 转换为整数。")
            raise

        HASH_SALT = os.getenv("HASH_SALT", "thisishashsalt")
        hashids_encoder = Hashids(salt=HASH_SALT, min_length=11)

        df_copy['uuid'] = df_copy[id_column].apply(
            lambda row_id: hashids_encoder.encode(extracted_value_int, row_id)
        )
        print("ID和可逆的UUID已添加完成。")

        # 调用清理函数，它将直接修改 df_copy
        sanitize_dataframe_for_db(df_copy)

        print("\n最终数据准备完成。")
        return df_copy  # 返回被完整处理过的副本
    except Exception as e:
        print(f"错误: 在为 '{table_name}' 准备数据时失败: {e}")
        raise RuntimeError(f"无法为表 '{table_name}' 准备最终数据。") from e


# utils.py

import os
from datetime import datetime
from hashids import Hashids
from typing import List, Dict, Tuple, Union


# 您可能已经有了 parse_llm_json_output 函数，这里不再重复

def decode_uuid(uuid_str: str) -> Tuple[Union[str, None], Union[int, None]]:
    """
    解码单个UUID字符串，返回 (YYYY_MM_DD 格式的日期, 原始ID)。
    此函数设计健壮，包含类型检查和异常捕获。

    Args:
        uuid_str (str): 要解码的单个UUID字符串。

    Returns:
        Tuple[Union[str, None], Union[int, None]]: 一个包含日期字符串和ID的元组。
                                                    如果解码失败，则返回 (None, None)。
    """
    # 异常检测 1: 检查输入类型是否为字符串
    if not isinstance(uuid_str, str):
        print(f"错误: [decode_uuid] 期望一个字符串参数，但收到了 {type(uuid_str)} 类型。")
        return None, None

    # 异常检测 2: 检查输入字符串是否为空
    if not uuid_str:
        print("错误: [decode_uuid] 接收到空字符串，无法解码。")
        return None, None

    # --- 核心解码逻辑 ---
    try:
        # 确保从环境中获取 salt 和 min_length，并有可靠的默认值
        HASH_SALT = os.getenv("HASH_SALT", "thisishashsalt")
        MIN_LENGTH = int(os.getenv("HASH_MIN_LENGTH", 11))

        hashids_decoder = Hashids(salt=HASH_SALT, min_length=MIN_LENGTH)
        decoded_values = hashids_decoder.decode(uuid_str)

        # 检查解码结果是否符合预期
        if not decoded_values or len(decoded_values) < 2:
            print(f"警告: UUID '{uuid_str}' 解码失败或结果不完整。解码结果: {decoded_values}")
            return None, None

        # 解构解码值
        extracted_value_int, original_id = decoded_values[0], decoded_values[1]
        date_str_raw = str(extracted_value_int)

        # 验证日期格式是否有效
        try:
            valid_date = datetime.strptime(date_str_raw, '%Y%m%d')
            formatted_date_str = valid_date.strftime('%Y_%m_%d')
        except ValueError:
            print(f"警告: 从UUID '{uuid_str}' 解码出的日期字符串 '{date_str_raw}' 不是一个有效的日期。")
            return None, None

        return formatted_date_str, original_id

    # 异常检测 3: 捕获所有其他在解码过程中可能发生的未知异常
    except Exception as e:
        print(f"错误: 解码UUID '{uuid_str}' 时发生未知异常: {e}")
        return None, None


def decode_uuid_list(uuid_list: List[str]) -> List[Dict]:
    """
    安全地接收一个UUID字符串列表，并对其中每一个进行解码。
    返回一个结构化的字典列表，便于后续处理。

    Args:
        uuid_list (List[str]): 从ChromaDB等来源获取的UUID字符串列表。

    Returns:
        List[Dict]: 一个字典列表，每个字典包含原始UUID和解码结果。
                    示例: [{'uuid': '...', 'date': '...', 'id': ...}, ...]
    """
    # 异常检测 1: 检查输入类型是否为列表
    if not isinstance(uuid_list, list):
        print(f"错误: [decode_uuid_list] 期望一个列表参数，但收到了 {type(uuid_list)} 类型。")
        return []

    if not uuid_list:
        print("信息: [decode_uuid_list] 接收到空列表，无需解码。")
        return []

    decoded_results = []
    # 遍历列表，调用单一解码函数
    for single_uuid in uuid_list:
        # decode_uuid 函数本身已经包含了丰富的异常检测
        date_str, id_str = decode_uuid(single_uuid)

        # 将结果整理成一个字典，无论成功与否都保留原始UUID
        result_dict = {
            'uuid': single_uuid,
            'date': date_str,
            'id': id_str
        }
        decoded_results.append(result_dict)

    return decoded_results


import json
import re
from typing import Union

class LLMJSONParsingError(ValueError):
    """当从LLM的文本输出中解析JSON失败时引发的自定义异常。"""

    def __init__(self, message: str, original_text: str = None):
        self.original_text = original_text
        full_message = f"错误: {message}"
        if original_text:
            # 截取部分原始文本以防过长
            snippet = original_text[:200] + '...' if len(original_text) > 200 else original_text
            full_message += f"\n--- 原始文本片段 ---\n{snippet}"
        # 调用父类的构造函数来设置最终的错误消息
        super().__init__(full_message)


def parse_llm_json_output(text_input: str) -> Union[dict, list]:
    """
    将一个可能包含非JSON文本的字符串解析为Python字典或列表。
    如果所有策略都失败，将引发 LLMJSONParsingError 异常。
    """
    if not isinstance(text_input, str) or not text_input.strip():
        raise ValueError("输入必须是一个非空的字符串。")

    # 策略 1: 直接解析
    try:
        return json.loads(text_input)
    except json.JSONDecodeError:
        pass  # 失败则继续

    # 策略 2: 提取Markdown代码块
    match = re.search(r"```(json)?\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*```", text_input, re.DOTALL)
    if match:
        clean_text = match.group(2)
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            raise LLMJSONParsingError(f"在提取的JSON Markdown代码块内解析失败: {e}", original_text=clean_text)

    # 策略 3: 提取最外层的 { ... } 或 [ ... ]
    try:
        start_pos = -1
        first_bracket_pos = text_input.find('[')
        first_brace_pos = text_input.find('{')
        if first_brace_pos != -1 and (first_brace_pos < first_bracket_pos or first_bracket_pos == -1):
            start_pos = first_brace_pos
            end_char = '}'
        elif first_bracket_pos != -1:
            start_pos = first_bracket_pos
            end_char = ']'
        if start_pos != -1:
            end_pos = text_input.rfind(end_char)
            if end_pos > start_pos:
                return json.loads(text_input[start_pos: end_pos + 1])
    except json.JSONDecodeError:
        pass  # 失败则进入最终的错误流程

    # 所有策略失败
    raise LLMJSONParsingError("所有解析策略均告失败，无法在文本中找到有效的JSON。", original_text=text_input)



# mysql返回数据处理

import pandas as pd
from typing import List, Optional

def format_mysql_dataframe_for_llm(
        df: pd.DataFrame,
        columns_to_include: Optional[List[str]] = None,
        format_type: str = 'markdown',
        na_rep: str = 'N/A'  # 自定义空值的显示方式
) -> str:
    """
    将Pandas DataFrame格式化为适合LLM处理的纯文本字符串。

    此版本特性:
    - 会完整显示所有数据，不进行截断。
    - 内置默认的“最佳列”选择。
    - 用户可通过 `columns_to_include` 自定义列。
    - 【新】将数据中的 NaN/None 值替换为指定的占位符 (默认为 'N/A')，使输出更清晰。

    Args:
        df (pd.DataFrame): 要格式化的DataFrame。
        columns_to_include (Optional[List[str]], optional):
            要包含的列名列表。为 None 时使用内置默认值。
        format_type (str, optional): 输出格式，支持 'markdown' 或 'key_value'。
        na_rep (str, optional): 在表格中如何表示 NaN/None 值。默认为 'N/A'。

    Returns:
        str: 格式化后的纯文本字符串。
    """
    if df.empty:
        return "（没有找到相关的详细文档。）"

    # 复制DataFrame以避免修改原始数据
    df_processed = df.copy()

    # 1. 选择列
    if columns_to_include is None:
        columns_to_include = [
            'cve', 'risk', 'host', 'name', #'synopsis',
            'description',
            #'solution',
            'uuid', 'plugin_id',
            #'protocol',
            'port', 'timestamp'
        ]
        print(f"信息: 未指定 columns_to_include，将使用默认的列列表: {columns_to_include}")

    existing_cols = [col for col in columns_to_include if col in df_processed.columns]
    if not existing_cols:
        return "（指定的列或默认列均不存在于数据中。）"
    df_processed = df_processed[existing_cols]

    # 2. 【核心修改】将所有 NaN/None 值替换为指定的占位符
    # .fillna() 是Pandas中处理空值的标准方法。
    # 我们直接对整个处理后的DataFrame进行填充，这会处理所有列的空值。
    df_filled = df_processed.fillna(na_rep)

    # 3. 格式化转换
    if format_type == 'markdown':
        # to_markdown 会将 DataFrame 转换为 Markdown 表格
        # 我们对填充了空值后的 df_filled 进行操作
        return df_filled.to_markdown(index=False, tablefmt="pipe")

    elif format_type == 'key_value':
        output_parts = []
        # 同样，在填充后的 DataFrame 上进行迭代
        for index, row in df_filled.iterrows():
            output_parts.append(f"--- 记录 {index + 1} ---")
            for col, value in row.items():
                output_parts.append(f"{col}: {value}")
        return "\n".join(output_parts)

    else:
        # to_string 支持 na_rep 参数，我们可以直接使用
        return df_processed.to_string(index=False, na_rep=na_rep)


from datetime import datetime


def get_today_date_formatted() -> str:
    today = datetime.now()
    formatted_date = today.strftime('%Y_%m_%d')
    return formatted_date


# --- 示例用法 ---
if __name__ == "__main__":
    today_date = get_today_date_formatted()
    print(f"今天的日期是: {today_date}")

    # 您可以在任何需要今天日期的地方调用这个函数
    # 例如，用于文件名、日志记录、或数据库查询等
    # filename = f"report_{today_date}.csv"
    # print(f"生成的文件名: {filename}")
