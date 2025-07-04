import os
import json
from datetime import datetime, timedelta, date
import calendar
from pymysql.converters import escape_string
from dotenv import load_dotenv

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# ... (模块0 Pydantic模型定义 和 模块1 SQL转换器代码保持不变，此处省略)...
# (请从下面的 RealLLMPlanner 类开始替换)
# ==============================================================================
# 模块0: 加载环境变量和Pydantic模型定义 (与之前相同)
# ==============================================================================
print("--- 模块0: 加载环境变量与Pydantic模型 ---")
load_dotenv()


class AggregationOperation(BaseModel):
    type: Optional[str] = Field(None, description="聚合类型，如 'max', 'count', 'sum' 等。")
    select_column_name: str = Field(..., description="要进行操作的列名。")
    alias: Optional[str] = Field(None, description="此操作结果的别名，用于后续引用。")


class FilterCondition(BaseModel):
    field: str
    operator: str
    value: Any


class PlanInputs(BaseModel):
    filter_conditions: Optional[Dict] = Field(None, description="用于WHERE子句的过滤条件。")
    aggregation_operation: List[AggregationOperation] = Field(..., description="要执行的聚合或选择操作。")


class ExecutionStep(BaseModel):
    step: int = Field(..., description="步骤的序号，从0开始。")
    step_type: str = Field(..., description="步骤的类型，如 'aggregate_mysql' 或 'Retrieval'。")
    description: str = Field(..., description="对这一步骤要做什么的自然语言描述。")
    inputs: PlanInputs
    outputs: Dict[str, str] = Field(...,
                                    description="定义此步骤输出的上下文键名和来源别名。例如 {'max_score_value': 'max_score'} 表示将名为'max_score'的聚合结果存储为'max_score_value'。")


class QueryPlan(BaseModel):
    user_query: str
    overall_intent: str = Field(..., description="对用户整体意图的简短描述。")
    execution_plan: List[ExecutionStep]


# ==============================================================================
# 模块1：您的SQL转换器 (与之前版本相同)
# ==============================================================================
print("--- 模块1: SQL转换代码已加载 ---")


def _format_sql_value(value):
    if isinstance(value, str):
        if value.startswith("$ref:"): return value
        return f"'{escape_string(value)}'"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bool):
        return str(value).upper()
    elif value is None:
        return "NULL"
    elif isinstance(value, list):
        formatted_values = [_format_sql_value(v) for v in value]
        return f"({', '.join(formatted_values)})"
    else:
        return f"'{escape_string(str(value))}'"


OPERATOR_MAP = {"$eq": "=", "$ne": "!=", "$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=", "$in": "IN",
                "$nin": "NOT IN", "$like": "LIKE"}


def json_to_sql_where_clause(condition_obj):
    if not isinstance(condition_obj, dict): return ""
    if "$and" in condition_obj:
        clauses = [json_to_sql_where_clause(cond) for cond in condition_obj["$and"]]
        return f"({' AND '.join(c for c in clauses if c)})"
    elif "$or" in condition_obj:
        clauses = [json_to_sql_where_clause(cond) for cond in condition_obj["$or"]]
        return f"({' OR '.join(c for c in clauses if c)})"
    elif "$not" in condition_obj:
        inner_clause = json_to_sql_where_clause(condition_obj["$not"])
        return f"NOT ({inner_clause})" if inner_clause else ""
    else:
        field, op, value = condition_obj.get("field"), condition_obj.get("operator"), condition_obj.get("value")
        if not field or not op: return ""
        sql_op = OPERATOR_MAP.get(op)
        if not sql_op: raise ValueError(f"不支持的操作符: {op}")
        return f"`{field}` {sql_op} {_format_sql_value(value)}"


def process_aggregation_operations(agg_ops_list):
    if not agg_ops_list: return "*", ""
    select_parts, group_by_parts = [], set()
    for agg_op in agg_ops_list:
        raw_agg_type = agg_op.get("type")
        agg_type = raw_agg_type.lower() if isinstance(raw_agg_type, str) else ""
        col, alias = agg_op.get("select_column_name", "*"), agg_op.get("alias")
        alias_str = f" AS `{alias}`" if alias else ""
        if agg_type == "max":
            select_parts.append(f"MAX(`{col}`){alias_str}")
        elif agg_type == "count":
            select_parts.append(f"COUNT(`{col}`){alias_str}")
        elif not agg_type and col != "*":  # 这是一个简单的列选择
            select_parts.append(f"`{col}`")
            # 只有当它是简单列选择时才应该考虑加入GROUP BY（如果它是聚合函数的参数则不应）
            # 这个逻辑可能需要根据更复杂的聚合场景调整
            # 简单的SELECT col FROM table GROUP BY col 是合法的
            group_by_parts.add(col)
        elif agg_type:
            raise ValueError(f"process_aggregation_operations 中不支持的聚合类型: '{agg_type}'")
    select_clause = ", ".join(select_parts) if select_parts else "*"
    # 修正：GROUP BY 子句应包含所有非聚合的SELECT列
    non_agg_select_cols = [part.replace('`', '') for part in select_parts if
                           '(' not in part and ' AS ' not in part]  # 简单获取非聚合列

    # 如果有聚合函数，并且有非聚合的列被选择，那么这些非聚合的列必须出现在GROUP BY中
    has_agg_function = any('(' in part for part in select_parts)

    if has_agg_function and non_agg_select_cols:
        for col_to_group in non_agg_select_cols:
            group_by_parts.add(col_to_group)

    group_by_clause = f"GROUP BY {', '.join(f'`{c}`' for c in sorted(list(group_by_parts)))}" if group_by_parts else ""
    return select_clause, group_by_clause


def plan_step_to_sql(step, table_name):
    inputs = step.get("inputs", {})
    where_clause_str = f"WHERE {json_to_sql_where_clause(inputs['filter_conditions'])}" if "filter_conditions" in inputs and inputs.get(
        "filter_conditions") else ""
    select_clause_str, group_by_clause_str = process_aggregation_operations(inputs.get("aggregation_operation"))
    sql = f"SELECT {select_clause_str} FROM `{table_name}` {where_clause_str} {group_by_clause_str};"
    return sql.strip()


# ==============================================================================
# 模块2：【再次强化Prompt】的规划器 和 工作流执行器
# ==============================================================================
print("--- 模块2: 智能规划器(使用真实LLM)与工作流执行器已加载 ---")


class RealLLMPlanner:
    def __init__(self, llm):
        self.llm = llm
        self.parser = PydanticOutputParser(pydantic_object=QueryPlan)
        self.prompt = self._create_prompt()

    def _create_prompt(self):
        # --- 【关键修正区域】: 再次强化对LLM的约束 ---
        prompt_text = """
        你是一个顶级的、遵循严格逻辑的数据库查询规划专家。你的任务是将用户的自然语言问题，分解成一个或多个、有逻辑顺序的执行步骤，并严格按照提供的JSON格式输出。

        **你的输出必须是且仅是一个合法的JSON对象。不要包含任何额外的解释、对话或文字。**

        **执行计划的核心规则**:
        1.  **分解依赖**: 如果任务A的结果是任务B的输入，那么任务A和任务B必须是两个独立的步骤。任务A必须在任务B之前。
        2.  **步骤编号**: 每个步骤 (`ExecutionStep`) 必须有一个从0开始的、连续的 `step` 编号。
        3.  **引用过去**: 一个步骤 (例如 `step: 1`) 在其 `inputs` 中，如果要引用其他步骤的输出，只能引用 `step` 编号严格小于它自身的步骤 (例如 `step: 0`)。
            引用语法为: `"$ref:steps[N].output.key"`，其中 `N` 是被引用步骤的 `step` 编号，`key` 是该步骤 `outputs` 字典中定义的键。
        4.  **禁止自我/未来引用**: 
            - **绝对禁止**一个步骤引用它自己的输出 (例如，`step: 1` 的 `inputs` 中不能出现 `"$ref:steps[1].output.some_key"`)。
            - **绝对禁止**一个步骤引用未来步骤的输出 (例如，`step: 1` 的 `inputs` 中不能出现 `"$ref:steps[2].output.some_key"`)。
        5.  **Outputs 定义**: 每个步骤的 `outputs` 字典都必须定义，它将此步骤的结果映射到一个或多个键上，以供后续步骤引用。键名应具有描述性。
            例如：`"outputs": {"max_cvss_score": "max_score_alias"}` 表示将名为 `max_score_alias` 的聚合结果，在上下文中存储为 `max_cvss_score`。

        **JSON输出格式要求**:
        {format_instructions}

        **示例1 (正确的多步计划)**:
        用户问题: "找出CVSS最高的漏洞ID，然后用这个ID找出受影响的主机。"
        可能的正确JSON片段 (仅示意execution_plan部分):
        ```json
        [
          {
            "step": 0,
            "description": "找出最高的CVSS分数。",
            "inputs": {"aggregation_operation": [{"type": "max", "select_column_name": "cvss_score", "alias": "max_val"}]},
            "outputs": {"highest_score": "max_val"}
          },
          {
            "step": 1,
            "description": "使用最高分找出漏洞ID。",
            "inputs": {
              "filter_conditions": {"field": "cvss_score", "operator": "$eq", "value": "$ref:steps[0].output.highest_score"},
              "aggregation_operation": [{"select_column_name": "vulnerability_id", "alias":"vuln_id"}]
            },
            "outputs": {"target_vulnerability_id": "vuln_id"}
          },
          {
            "step": 2,
            "description": "使用漏洞ID找出主机。",
            "inputs": {
                "filter_conditions": {"field": "vulnerability_id", "operator": "$eq", "value": "$ref:steps[1].output.target_vulnerability_id"},
                "aggregation_operation": [{"select_column_name": "host"}]
            },
            "outputs": {"affected_hosts_list": "host"}
          }
        ]
        ```

        **现在，请为以下用户问题生成执行计划:**
        用户问题:
        {user_query}
        """
        return ChatPromptTemplate.from_template(template=prompt_text, partial_variables={
            "format_instructions": self.parser.get_format_instructions()})

    def generate_plan(self, user_query: str) -> dict:
        print(f"\n[Real LLM Planner]: 正在调用通义千问API为问题 '{user_query}' 生成计划...")
        chain = self.prompt | self.llm | self.parser
        try:
            query_plan_obj = chain.invoke({"user_query": user_query})
            print("[Real LLM Planner]: API调用成功，已生成并解析计划。")
            return query_plan_obj.model_dump(by_alias=True)
        except Exception as e:
            print(f"[Real LLM Planner]: API调用或解析失败！错误: {e}")
            # 在这里可以加入更详细的日志记录，比如打印出LLM返回的原始文本，帮助调试Pydantic解析错误
            # print(f"LLM原始输出 (可能导致解析错误): {chain.invoke({'user_query': user_query})}") # 取消注释以查看
            raise


class WorkflowExecutor:
    def __init__(self, table_name):
        self.table_name, self.context = table_name, {}

    def _substitute_references(self, inputs: dict) -> dict:
        inputs_copy = json.loads(json.dumps(inputs))

        def _walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if isinstance(value, str) and value.startswith("$ref:"):
                        ref_path = value.split(":")[1]
                        parts = ref_path.split('.')
                        try:
                            ref_value = self.context
                            for part in parts:
                                if '[' in part and ']' in part:
                                    list_name, index = part.split('[')[0], int(part.split('[')[1].replace(']', ''))
                                    # 增加对列表长度的检查，防止IndexError
                                    if list_name not in ref_value or not isinstance(ref_value[list_name],
                                                                                    list) or index >= len(
                                            ref_value[list_name]):
                                        raise IndexError(
                                            f"引用路径 '{ref_path}' 中的列表索引 '{index}' 超出范围或列表不存在。")
                                    ref_value = ref_value[list_name][index]
                                else:
                                    if part not in ref_value:
                                        raise KeyError(f"引用路径 '{ref_path}' 中的键 '{part}' 不存在于上下文中。")
                                    ref_value = ref_value[part]
                            node[key] = ref_value
                            print(f"[Executor]: 成功替换占位符 '{value}' 为值 '{ref_value}'")
                        except (KeyError, IndexError, TypeError) as e:  # 增加了TypeError捕获
                            raise ValueError(
                                f"无法解析引用 '{ref_path}'。上下文内容: {json.dumps(self.context, indent=2)}。错误: {e}")
                    else:
                        _walk(value)
            elif isinstance(node, list):
                for item in node: _walk(item)

        _walk(inputs_copy)
        return inputs_copy

    def _run_mock_sql(self, sql: str) -> any:
        print(f"[Mock SQL Engine]: 正在执行 -> {sql}")
        mock_data = [
            {'cve_id': 'CVE-2024-1002', 'host': 'prod-db-01', 'cvss_v3_0_base_score': 9.8},
            {'cve_id': 'CVE-2024-9999', 'host': 'prod-db-02', 'cvss_v3_0_base_score': 9.8},
            {'cve_id': 'CVE-2023-5001', 'host': 'staging-db-01', 'cvss_v3_0_base_score': 8.1}
        ]
        if "MAX(`cvss_v3_0_base_score`)" in sql: return [[9.8]]
        if "WHERE `cvss_v3_0_base_score` = 9.8" in sql and "SELECT `host`" in sql:  # 更精确匹配第二步
            hosts = {row['host'] for row in mock_data if row['cvss_v3_0_base_score'] == 9.8}
            return [[host] for host in sorted(list(hosts))]
        # 为了应对LLM可能生成的其他合理但我们未模拟的SQL，返回一个通用空结果
        print(f"[Mock SQL Engine]: 未找到与 '{sql}' 完全匹配的模拟查询，返回空列表。")
        return []

    def execute_plan(self, plan: dict) -> dict:
        for i, step in enumerate(plan.get('execution_plan', [])):
            print(f"\n========== 正在执行步骤 {step.get('step')}: {step.get('description')} ==========")

            # 在替换引用之前，检查步骤编号是否与循环索引i一致（可选的健全性检查）
            if step.get('step') != i:
                print(f"[警告] 步骤编号 ({step.get('step')}) 与循环索引 ({i}) 不匹配！将按计划中的步骤编号处理。")
                # 如果要严格按i来，这里可以抛错或调整逻辑

            resolved_inputs = self._substitute_references(step['inputs'])
            sql_query = plan_step_to_sql({"inputs": resolved_inputs},
                                         self.table_name)  # plan_step_to_sql需要整个step对象或仅inputs
            result_rows = self._run_mock_sql(sql_query)

            if result_rows:
                result_value = result_rows[0][0] if len(result_rows) == 1 and len(result_rows[0]) == 1 else [row[0] for
                                                                                                             row in
                                                                                                             result_rows] if result_rows and len(
                    result_rows[0]) == 1 else result_rows
                if 'steps' not in self.context: self.context['steps'] = []
                while len(self.context['steps']) <= i: self.context['steps'].append({})  # 按实际步骤索引i来填充
                if 'output' not in self.context['steps'][i]: self.context['steps'][i]['output'] = {}
                output_mapping = step.get('outputs', {})
                for context_key, alias_or_direct_col in output_mapping.items():
                    # 假设result_value是单值或单列列表
                    self.context['steps'][i]['output'][context_key] = result_value
                    print(
                        f"[Executor]: 步骤 {i} 的输出 '{result_value}' 已存入上下文的 'steps[{i}].output.{context_key}'")
            else:
                print(f"[Executor]: 步骤 {i} 没有返回结果。")

        print("\n========== 所有步骤执行完毕 ==========")
        return self.context


# ==============================================================================
# 模块3：主程序入口
# ==============================================================================
if __name__ == "__main__":
    print("\n--- 模块3: 主程序启动 ---\n")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("错误：未在.env文件中找到 DASHSCOPE_API_KEY。")

    llm = ChatTongyi(model_name="qwen-plus", temperature=0)  # 可以尝试qwen-max看是否效果更好
    llm_planner = RealLLMPlanner(llm)
    workflow_executor = WorkflowExecutor(table_name="vulnerabilities")

    user_query = "找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞，并列出所有受该漏洞影响的主机地址(host)。"

    try:
        json_plan = llm_planner.generate_plan(user_query)

        print("\n----------------- LLM生成的JSON执行计划 -----------------")
        print(json.dumps(json_plan, indent=2, ensure_ascii=False))
        print("----------------------------------------------------------\n")

        final_context = workflow_executor.execute_plan(json_plan)

        print("\n-------------------- 最终执行结果 --------------------")
        print("最终上下文 '记忆':")
        print(json.dumps(final_context, indent=2, ensure_ascii=False))

        # 提取最终答案时，使用计划中定义的最后一步的step索引和outputs键
        final_step_index = json_plan['execution_plan'][-1]['step']
        # 假设最后一步的outputs中只有一个键，或者你知道确切的键名
        final_output_keys = list(json_plan['execution_plan'][-1]['outputs'].keys())
        final_answer_key = final_output_keys[0] if final_output_keys else None

        if final_answer_key and 'steps' in final_context and len(final_context['steps']) > final_step_index and \
                'output' in final_context['steps'][final_step_index] and \
                final_answer_key in final_context['steps'][final_step_index]['output']:
            final_answer = final_context['steps'][final_step_index]['output'][final_answer_key]
        else:
            final_answer = "未在执行上下文中找到最终答案。"

        print(f"\n问题的最终答案: {final_answer}")

    except Exception as e:
        print(f"\n--- 主程序发生错误 ---")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        import traceback

        traceback.print_exc()  # 打印完整的堆栈跟踪

    print("----------------------------------------------------\n")