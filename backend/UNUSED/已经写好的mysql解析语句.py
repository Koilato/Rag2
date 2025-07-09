from pymysql.converters import escape_string
from datetime import datetime, timedelta, date
import calendar # 确保导入

# --- 您已有的函数定义 ---
# 这个函数有一个问题，当mysql中的数据列中有缺失的情况，比如 risk==null
def _format_sql_value_for_execution_plan(value):
    if isinstance(value, str):
        return f"'{escape_string(value)}'"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bool):
        return str(value).upper()
    elif value is None:
        return "NULL"
    elif isinstance(value, list):
        formatted_values = [_format_sql_value_for_execution_plan(v) for v in value]
        return f"({', '.join(formatted_values)})"
    else:
        return f"'{escape_string(str(value))}'"

OPERATOR_MAP = {
    "$eq": "=", "$ne": "!=", "$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=",
    "$in": "IN", "$nin": "NOT IN", "$like": "LIKE"
}

def json_to_sql_where_clause(condition_obj):
    if not isinstance(condition_obj, dict):
        raise ValueError("条件必须是一个字典")
    if "$and" in condition_obj:
        if not isinstance(condition_obj["$and"], list) or not condition_obj["$and"]:
            raise ValueError("$and 的值必须是非空列表")
        clauses = [json_to_sql_where_clause(cond) for cond in condition_obj["$and"]]
        active_clauses = [c for c in clauses if c and c.strip()]
        if not active_clauses: return ""
        return f"({' AND '.join(active_clauses)})"
    elif "$or" in condition_obj:
        if not isinstance(condition_obj["$or"], list) or not condition_obj["$or"]:
            raise ValueError("$or 的值必须是非空列表")
        clauses = [json_to_sql_where_clause(cond) for cond in condition_obj["$or"]]
        active_clauses = [c for c in clauses if c and c.strip()]
        if not active_clauses: return ""
        return f"({' OR '.join(active_clauses)})"
    elif "$not" in condition_obj:
        if not isinstance(condition_obj["$not"], dict):
            raise ValueError("$not 的值必须是一个条件对象字典")
        inner_clause = json_to_sql_where_clause(condition_obj["$not"])
        return f"NOT ({inner_clause})" if inner_clause and inner_clause.strip() else ""
    else:
        field = condition_obj.get("field")
        operator_json = condition_obj.get("operator")
        if not field: raise ValueError(f"条件对象缺少 'field' 键: {condition_obj}")
        if not operator_json: raise ValueError(f"条件对象 '{field}' 缺少 'operator' 键: {condition_obj}")
        if operator_json == "$isNull": return f"{field} IS NULL"
        if operator_json == "$isNotNull": return f"{field} IS NOT NULL"
        # 对于其他操作符，检查value是否存在
        if "value" not in condition_obj:
             # 如果特定操作符允许没有value，在此处处理或修改此逻辑
             # 对于大多数操作符，value是必需的
             # raise ValueError(f"操作符 '{operator_json}' 需要 'value' 键，但在条件对象 '{field}' 中未找到。")
             pass # 保持原样，允许value为None，_format_sql_value_for_execution_plan 会处理
        value = condition_obj.get("value")
        sql_operator = OPERATOR_MAP.get(operator_json)
        if not sql_operator: raise ValueError(f"不支持的操作符: {operator_json}")
        formatted_value = _format_sql_value_for_execution_plan(value)
        return f"{field} {sql_operator} {formatted_value}"

# 聚合字段：由聚合函数生成的字段（如 COUNT(*) AS employee_count）。
# 非聚合字段：直接从表中选择并用于分组的字段
def process_aggregation_operations(agg_ops_list, outputs_map):
    if not agg_ops_list: return "*", ""
    select_parts = []
    group_by_parts = set()
    def get_alias_for_agg(agg_type, col_name, outputs_map): # outputs_map 用于更智能的别名
        # 简化版：尝试从outputs_map匹配
        if agg_type == "count":
            if "vulnerability_count" in outputs_map: return " AS vulnerability_count"
            if "total_count" in outputs_map: return " AS total_count"
        if col_name and col_name != "*":
            if agg_type == "sum" and f"sum_{col_name}" in outputs_map : return f" AS sum_{col_name}"
            if agg_type == "sum" and "total_revenue" in outputs_map : return f" AS total_revenue" # 更具体的匹配
            if agg_type == "avg" and f"avg_{col_name}" in outputs_map : return f" AS avg_{col_name}"
            if agg_type == "avg" and "average_transactions" in outputs_map : return f" AS average_transactions"
        return "" # 没有找到特定匹配

    selected_columns_for_group_by_check = set()
    for i, agg_op in enumerate(agg_ops_list):
        agg_type = agg_op.get("type", "").lower()
        select_column_name = agg_op.get("select_column_name", "*")
        group_by_str = agg_op.get("group_by", "")
        current_alias = get_alias_for_agg(agg_type, select_column_name, outputs_map)

        if not current_alias and len(agg_ops_list) == 1 : # 如果只有一个聚合操作，尝试使用outputs_map的单个key
            if outputs_map and len(outputs_map)==1 and agg_type : # 确保是聚合类型
                current_alias = f" AS {list(outputs_map.keys())[0]}"


        if agg_type == "count":
            col_for_count = select_column_name if select_column_name and select_column_name != "*" else "*"
            if not current_alias: current_alias = f" AS count_{col_for_count.replace('.', '_')}" if col_for_count != "*" else " AS count_all"
            select_parts.append(f"COUNT({col_for_count}){current_alias}")
        elif agg_type == "sum":
            if not select_column_name or select_column_name == "*": raise ValueError("SUM 聚合需要一个明确的 'select_column_name'。")
            if not current_alias: current_alias = f" AS sum_{select_column_name.replace('.', '_')}"
            select_parts.append(f"SUM({select_column_name}){current_alias}")
            selected_columns_for_group_by_check.add(select_column_name)
        elif agg_type == "avg":
            if not select_column_name or select_column_name == "*": raise ValueError("AVG 聚合需要一个明确的 'select_column_name'。")
            if not current_alias: current_alias = f" AS avg_{select_column_name.replace('.', '_')}"
            select_parts.append(f"AVG({select_column_name}){current_alias}")
            selected_columns_for_group_by_check.add(select_column_name)
        elif not agg_type and select_column_name and select_column_name != "*":
            select_parts.append(select_column_name)
            selected_columns_for_group_by_check.add(select_column_name)
        elif agg_type: raise ValueError(f"不支持的聚合类型: {agg_type}")

        if group_by_str:
            cols = [col.strip() for col in group_by_str.split(',') if col.strip()]
            for col in cols:
                group_by_parts.add(col)
                is_col_selected = any(col == part.split(" AS ")[0].strip() for part in select_parts) # 检查原始列名是否已选
                if not is_col_selected and col not in selected_columns_for_group_by_check:
                     if col not in [p.split(" AS ")[0].strip() for p in select_parts if '(' not in p]:
                        select_parts.append(col)
                     selected_columns_for_group_by_check.add(col)

    final_select_clause = ", ".join(select_parts) if select_parts else "*"
    final_group_by_clause = f"GROUP BY {', '.join(sorted(list(group_by_parts)))}" if group_by_parts else ""
    return final_select_clause, final_group_by_clause

# --- 新函数：处理基于时间范围的分表查询 ---
def get_date_range(time_range_info):
    """
    根据时间范围信息生成日期字符串列表 (YYYY-MM-DD)。
    """
    dates = []
    range_type = time_range_info.get("type")
    today = date.today()

    if range_type == "last_n_days":
        days = time_range_info.get("days")
        if not isinstance(days, int) or days <= 0:
            raise ValueError("last_n_days 类型需要一个正整数 'days'。")
        for i in range(days):
            d = today - timedelta(days=i)
            dates.append(d.strftime("%Y-%m-%d"))
    elif range_type == "date_range":
        start_str = time_range_info.get("start_date")
        end_str = time_range_info.get("end_date")
        if not start_str or not end_str:
            raise ValueError("date_range 类型需要 start_date 和 end_date。")
        try:
            start_date_obj = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("日期格式应为 YYYY-MM-DD。")
        if start_date_obj > end_date_obj:
            raise ValueError("start_date 不能晚于 end_date。")
        current_date_obj = start_date_obj
        while current_date_obj <= end_date_obj:
            dates.append(current_date_obj.strftime("%Y-%m-%d"))
            current_date_obj += timedelta(days=1)
    elif range_type == "specific_dates":
        dates_str_list = time_range_info.get("dates", [])
        if not isinstance(dates_str_list, list):
            raise ValueError("specific_dates 类型需要一个 'dates' 列表。")
        for d_str in dates_str_list: # 可以添加对每个日期字符串格式的验证
            try:
                datetime.strptime(d_str, "%Y-%m-%d") # 验证格式
                dates.append(d_str)
            except ValueError:
                raise ValueError(f"specific_dates 中的日期格式无效: {d_str}，应为 YYYY-MM-DD。")
    elif range_type == "specific_month":
        year = time_range_info.get("year")
        month = time_range_info.get("month")
        if not isinstance(year, int) or not isinstance(month, int) or not (1 <= month <= 12):
            raise ValueError("specific_month 类型需要有效的整数 'year' 和 'month' (1-12)。")
        try:
            num_days = calendar.monthrange(year, month)[1]
            for day_num in range(1, num_days + 1):
                dates.append(date(year, month, day_num).strftime("%Y-%m-%d"))
        except Exception as e: # calendar.monthrange 对于无效年月也可能抛错
            raise ValueError(f"无效的年份或月份: {year}-{month} ({e})")
    else:
        raise ValueError(f"不支持的时间范围类型: '{range_type}'")

    return sorted(list(set(dates))) # 去重并排序，确保唯一性和顺序

def json_to_sql_time_sharded(json_plan_data, base_table_prefix=""):
    """
    简化版：处理包含时间范围信息、针对按天分表的JSON执行计划，并生成UNION ALL查询。
    聚合操作（如果有）被假定在每个分表内部执行。
    """
    if not isinstance(json_plan_data, dict):
        raise ValueError("输入必须是JSON对象（字典）。")

    execution_plan = json_plan_data.get("execution_plan")
    if not execution_plan or not isinstance(execution_plan, list) or not execution_plan[0]:
        raise ValueError("未找到有效的 'execution_plan'。")

    step = execution_plan[0]
    # 假设 step_type 用于选择调用哪个解析器，这里我们直接解析这个特定结构
    # if step.get("step_type") != "query_time_sharded_tables": # 你可以定义一个特定的类型
    #     raise ValueError("此函数设计用于特定类型的分表查询步骤。")

    inputs = step.get("inputs", {})
    outputs_map = step.get("outputs", {})

    time_range_info = inputs.get("time_range")
    if not time_range_info:
        raise ValueError("执行计划的 inputs 中缺少 'time_range' 信息。")

    table_date_suffixes = get_date_range(time_range_info)
    if not table_date_suffixes:
        raise ValueError("根据时间范围未能生成任何有效的表日期。")

    # 构建每个表的全名
    table_names = []
    for date_suffix in table_date_suffixes:
        # 如果表名就是日期，base_table_prefix 为空。
        # 如果表名是 log_2023-10-27，则 base_table_prefix 是 "log_"
        table_names.append(f"{base_table_prefix}{date_suffix}")


    # --- 获取 WHERE 子句（适用于每个子查询）---
    filter_conditions = inputs.get("filter_conditions")
    where_clause_part = ""
    if filter_conditions:
        raw_where = json_to_sql_where_clause(filter_conditions)
        if raw_where and raw_where.strip():
            where_clause_part = f"WHERE {raw_where}"

    # --- 获取 SELECT 和 GROUP BY (如果聚合是针对每个分表) ---
    sub_query_select_clause = "*"
    sub_query_group_by_clause = ""

    agg_ops = inputs.get("aggregation_operation")
    if agg_ops: # 如果有聚合操作，它们应用于每个子查询
        sub_query_select_clause, sub_query_group_by_clause = process_aggregation_operations(agg_ops, outputs_map)
    elif "select_columns" in inputs:
        sc = inputs["select_columns"]
        if isinstance(sc, list):
            sub_query_select_clause = ", ".join(sc)
        elif isinstance(sc, str) and sc.strip():
            sub_query_select_clause = sc
        # else:保持默认 SELECT * 或抛错
        if not sub_query_select_clause or sub_query_select_clause == "*": # 如果select_columns是空列表或"*"
            sub_query_select_clause = "*"


    individual_queries = []
    for table_name in table_names:
        # 注意表名可能包含特殊字符（如'-'），用反引号包围是安全的
        query_part = f"SELECT {sub_query_select_clause} FROM `{table_name}`"
        if where_clause_part:
            query_part += f" {where_clause_part}"
        if sub_query_group_by_clause: # 如果每个子查询内部需要分组
            query_part += f" {sub_query_group_by_clause}"
        individual_queries.append(f"({query_part})") # 将每个子查询用括号括起来

    if not individual_queries:
        return "-- 没有生成任何查询 --" # 或者根据情况返回

    final_sql = " UNION ALL ".join(individual_queries)

    # 如果UNION ALL之后还需要进行最终的聚合或DISTINCT，这通常需要在更外层处理
    # 例如，如果最外层需要对UNION ALL的结果进行COUNT或SUM
    # final_sql = f"SELECT COUNT(*) FROM ({final_sql}) AS combined_results"
    # 或者如果需要对某列去重:
    # final_sql = f"SELECT DISTINCT your_column FROM ({final_sql}) AS combined_results"
    # 目前这个函数只负责生成基础的 UNION ALL 语句

    return final_sql + ";"


# 沿用您之前的 json_to_sql 和 json_execution_plan_to_sql (如果还需要它们处理非分表查询)
# ... (您的 json_to_sql 和 json_execution_plan_to_sql 函数定义) ...
# 为了这个测试的独立性，我将只包含与分表查询相关的测试。
# 如果您想测试旧的函数，可以取消下面 json_execution_plan_to_sql 的注释并提供它的定义。

def json_execution_plan_to_sql(json_plan_data, table_name):
    """
    (这是您之前的函数，用于处理单个表、可能包含聚合的查询)
    将包含执行计划的JSON对象转换为SQL查询语句。
    """
    if not isinstance(json_plan_data, dict):
        raise ValueError("输入必须是JSON对象（字典）。")
    if not table_name or not isinstance(table_name, str):
        raise ValueError("表名 (table_name) 必须是一个非空字符串。")

    execution_plan = json_plan_data.get("execution_plan")
    if not execution_plan or not isinstance(execution_plan, list) or not execution_plan[0]:
        raise ValueError("未找到有效的 'execution_plan' (应为包含至少一个步骤的列表)。")

    step = execution_plan[0]
    step_type = step.get("step_type")
    inputs = step.get("inputs")
    outputs_map = step.get("outputs", {})

    if not inputs or not isinstance(inputs, dict):
        raise ValueError("步骤的 'inputs' 未找到或格式无效。")

    filter_conditions = inputs.get("filter_conditions")
    where_clause_str = ""
    if filter_conditions:
        raw_where = json_to_sql_where_clause(filter_conditions)
        if raw_where and raw_where.strip():
            where_clause_str = f"WHERE {raw_where}"

    select_clause_str = "*"
    group_by_clause_str = ""

    if step_type == "aggregate_mysql" or "aggregation_operation" in inputs:
        agg_ops = inputs.get("aggregation_operation")
        if agg_ops:
            select_clause_str, group_by_clause_str = process_aggregation_operations(agg_ops, outputs_map)
        else:
            select_clause_str = "COUNT(*) AS total_count"
    elif "select_columns" in inputs:
        select_clause_str = inputs["select_columns"]
        if isinstance(select_clause_str, list):
            select_clause_str = ", ".join(select_clause_str)
        elif not isinstance(select_clause_str, str) or not select_clause_str.strip():
            select_clause_str = "*"

    sql_parts = [
        f"SELECT {select_clause_str}",
        f"FROM `{table_name}`", #  确保表名被反引号包围
    ]
    if where_clause_str:
        sql_parts.append(where_clause_str)
    if group_by_clause_str:
        sql_parts.append(group_by_clause_str)

    return " ".join(sql_parts) + ";"


# --- 测试用例 ---
if __name__ == '__main__':
    print("========== 测试时间分片表查询 (json_to_sql_time_sharded) ==========")

    # 测试用例1: 近 N 天
    time_sharded_json_last_n_days = {
      "user_query": "近3天内出现了哪些cve漏洞，且来源是外部",
      "execution_plan": [
        {
          "step_type": "query_time_sharded_tables", # 假设我们为此定义了类型
          "description": "查询近3天内外部来源的CVE漏洞",
          "inputs": {
            "time_range": {
              "type": "last_n_days",
              "days": 3
            },
            "filter_conditions": {
              "$and": [
                { "field": "vulnerability_type", "operator": "$eq", "value": "CVE" },
                { "field": "source", "operator": "$eq", "value": "external" }
              ]
            },
            "select_columns": ["DISTINCT cve_id", "report_date"] # 选择不重复的cve_id和报告日期
          },
          "outputs": { "cve_id": "string", "report_date": "date" }
        }
      ]
    }
    try:
        # 假设表名就是日期，所以 base_table_prefix=""
        sql_time_sharded_1 = json_to_sql_time_sharded(time_sharded_json_last_n_days, base_table_prefix="")
        print(f"生成的SQL (近N天):\n{sql_time_sharded_1}\n")
    except ValueError as e:
        print(f"值错误 (近N天): {e}\n")
    except Exception as e:
        print(f"发生意外错误 (近N天): {e}\n")

    # 测试用例2: 指定日期范围
    time_sharded_json_date_range = {
      "user_query": "从2023-10-01到2023-10-02的ERROR日志数量",
      "execution_plan": [
        {
          "inputs": {
            "time_range": {
              "type": "date_range",
              "start_date": "2023-10-01",
              "end_date": "2023-10-02"
            },
            "filter_conditions": {
              "field": "log_level", "operator": "$eq", "value": "ERROR"
            },
            "aggregation_operation": [ # 在每个分表内部进行COUNT
                {"type": "count", "select_column_name": "*"}
            ]
          },
           "outputs": { "error_count_per_day": "integer" } # 别名用于每个子查询的COUNT
        }
      ]
    }
    try:
        # 假设表名是 log_YYYY-MM-DD
        sql_time_sharded_2 = json_to_sql_time_sharded(time_sharded_json_date_range, base_table_prefix="log_")
        print(f"生成的SQL (指定日期范围，每日计数):\n{sql_time_sharded_2}\n")
        # 预期：(SELECT COUNT(*) AS error_count_per_day FROM `log_2023-10-01` WHERE log_level = 'ERROR')
        #       UNION ALL
        #       (SELECT COUNT(*) AS error_count_per_day FROM `log_2023-10-02` WHERE log_level = 'ERROR');
        # 注意：这里的别名 error_count_per_day 可能需要调整 get_alias_for_agg 来精确匹配
        # 当前 process_aggregation_operations 对于单个聚合操作会尝试使用 outputs 的单个 key (如果只有一个)
    except ValueError as e:
        print(f"值错误 (指定日期范围): {e}\n")
    except Exception as e:
        print(f"发生意外错误 (指定日期范围): {e}\n")


    # 测试用例3: 特定月份，并且有全局聚合的意图（需要外部处理或更复杂的函数）
    time_sharded_json_specific_month_global_agg = {
      "user_query": "2023年5月份的总用户访问次数",
      "execution_plan": [
        {
          "inputs": {
            "time_range": {
              "type": "specific_month",
              "year": 2023,
              "month": 5 # 假设5月有31天
            },
            # "filter_conditions": {}, # 无特定过滤，查询所有访问
            "aggregation_operation": [ # 这是期望的最终聚合
                {"type": "sum", "select_column_name": "daily_visits"}
            ],
            # 为了实现上述聚合，子查询应该 select COUNT(*) AS daily_visits
            # 这需要json更明确地定义子查询做什么，或者函数更智能
            # 当前简化版函数可能无法直接生成最理想的SQL，除非JSON明确子查询的SELECT
            "sub_query_select": ["COUNT(*) AS daily_visits"] # 新增一个字段告诉子查询选什么
          },
           "outputs": { "total_may_visits": "integer" }
        }
      ]
    }
    # 为了让上面的JSON能被当前简化版函数处理，我们需要调整它：
    # 将 "aggregation_operation" 定义为每个子查询内部的操作
    # 然后外部如果需要总和，需要另一层SQL。
    # 或者，如果函数被设计成，当有aggregation_operation时，子查询就执行这些聚合。
    time_sharded_json_specific_month_sub_agg = {
      "user_query": "2023年5月份的每日用户访问次数列表",
      "execution_plan": [
        {
          "inputs": {
            "time_range": {
              "type": "specific_month",
              "year": 2023,
              "month": 5
            },
            "aggregation_operation": [
                {"type": "count", "select_column_name": "user_id", "group_by": ""} # 每日独立用户数
                # 或者 {"type": "count", "select_column_name": "*"} 每日总访问数
            ]
          },
           "outputs": { "daily_unique_visits": "integer" }
        }
      ]
    }
    try:
        sql_time_sharded_3 = json_to_sql_time_sharded(time_sharded_json_specific_month_sub_agg, base_table_prefix="user_visits_")
        print(f"生成的SQL (特定月份，每日计数):\n{sql_time_sharded_3}\n")
        # 预期会生成31个 (SELECT COUNT(user_id) AS daily_unique_visits FROM `user_visits_YYYY-MM-DD`) 的 UNION ALL
    except ValueError as e:
        print(f"值错误 (特定月份): {e}\n")
    except Exception as e:
        print(f"发生意外错误 (特定月份): {e}\n")

    # 您之前的 original_testjson (非分表查询)，使用 json_execution_plan_to_sql
    print("========== 第一个测试用例 (original_testjson, 使用旧函数) ==========")
    original_testjson = {
      "user_query": "查询2023年之后...",
      "semantic": "TRUE",
      "overall_intent": "complex_aggregation_with_filters",
      "execution_plan": [
        {
          "step_type": "aggregate_mysql", # 这个step_type对应旧函数
          "description": "复杂条件过滤并按主机和应用聚合统计漏洞数量",
          "inputs": {
            "filter_conditions": {
              "$and": [
                { "field": "creation_date", "operator": "$gt", "value": "2023-01-01T00:00:00Z" },
                {"field": "created_by","operator": "$in","value": ["admin", "system", "superuser"]},
                {"field": "description","operator": "$like","value": "%关键%"},
                {"$not": {"field": "description","operator": "$like","value": "%测试%"}},
                {"$or": [{"field": "status","operator": "$eq","value": "Open"},{"field": "status","operator": "$eq","value": "In Progress"}]},
                {"$or": [{"$and": [{"field": "port","operator": "$gte","value": 8000},{"field": "port","operator": "$lte","value": 9000}]},{"field": "port","operator": "$in","value": [80,443,22,8080]}]},
                {"field": "severity","operator": "$nin","value": ["Low", "Informational"]},
                {"field": "risk_level","operator": "$in","value": ["High", "Critical"]},
                {"field": "cvss_score","operator": "$gte","value": 7.0},
                {"field": "last_seen_date","operator": "$lte","value": "2024-12-31T23:59:59Z"},
                {"field": "target_os","operator": "$ne","value": "Windows XP"},
                {"field": "notes","operator": "$isNull"}
              ]
            },
            "aggregation_operation": [
              {"type": "count","select_column_name": "*","group_by": "host, app_name"},
              {"select_column_name": "host"},
              {"select_column_name": "app_name"}
            ]
          },
          "outputs": {"host": "string","app_name": "string","vulnerability_count": "integer"}
        }
      ]
    }
    try:
        sql_query_original = json_execution_plan_to_sql(original_testjson, table_name="vulnerabilities_data")
        print(f"生成的SQL (original_testjson):\n{sql_query_original}\n")
    except ValueError as e:
        print(f"值错误 (original_testjson): {e}\n")
    except Exception as e:
        print(f"发生意外错误 (original_testjson): {e}\n")