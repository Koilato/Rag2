# 在 utils.py 中，用这个版本替换之前的函数

import pandas as pd
from typing import List, Optional


def format_dataframe_for_llm(
        df: pd.DataFrame,
        columns_to_include: Optional[List[str]] = None,
        columns_to_exclude: Optional[List[str]] = None,
        max_rows: int = 10,
        format_type: str = 'markdown'
) -> str:
    """
    将Pandas DataFrame格式化为适合LLM处理的纯文本字符串。
    此版本支持自定义要包含或排除的列。

    Args:
        df (pd.DataFrame): 要格式化的DataFrame。
        columns_to_include (Optional[List[str]], optional):
            【新功能】一个只希望包含在输出中的列名列表。
            如果提供此参数，则会忽略 `columns_to_exclude`。
        columns_to_exclude (Optional[List[str]], optional):
            要从输出中排除的列名列表。默认为 ['is_indexed_to_chroma']。
            仅在 `columns_to_include` 未提供时生效。
        max_rows (int, optional): 最多包含的行数，以防止上下文过长。默认为10。
        format_type (str, optional): 输出格式。支持 'markdown' (默认) 或 'key_value'。

    Returns:
        str: 格式化后的纯文本字符串。如果DataFrame为空，则返回提示信息。
    """
    if df.empty:
        return "（没有找到相关的详细文档。）"

    # 复制DataFrame以避免修改原始数据
    df_processed = df.copy()

    # --- 核心逻辑：选择或排除列 ---
    if columns_to_include is not None:
        # 模式一：如果指定了要包含的列，则只选择这些列
        # 筛选出实际存在于DataFrame中的列，避免KeyError
        existing_cols_to_include = [col for col in columns_to_include if col in df_processed.columns]
        if not existing_cols_to_include:
            return "（指定的列均不存在于数据中。）"
        df_processed = df_processed[existing_cols_to_include]

    else:
        # 模式二：如果未指定包含列，则按排除列表进行操作
        if columns_to_exclude is None:
            # 设置默认要排除的列
            columns_to_exclude = ['is_indexed_to_chroma', 'id', 'uuid', 'fingerprint']

        # 使用 .drop() 并设置 errors='ignore' 可以安全地处理列不存在的情况
        df_processed = df_processed.drop(columns=columns_to_exclude, errors='ignore')

    # 限制行数
    if len(df_processed) > max_rows:
        df_limited = df_processed.head(max_rows)
    else:
        df_limited = df_processed

    # 根据选择的格式进行转换
    if format_type == 'markdown':
        return df_limited.to_markdown(index=False, tablefmt="pipe")

    elif format_type == 'key_value':
        output_parts = []
        for index, row in df_limited.iterrows():
            output_parts.append(f"--- 记录 {index + 1} ---")
            for col, value in row.items():
                output_parts.append(f"{col}: {value}")
        return "\n".join(output_parts)

    else:
        return df_limited.to_string(index=False)