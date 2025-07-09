### 下面是整合了所有优点后的最终版本。它保留了旧示例中的基础场景，并融入了新示例中的复杂混合场景，形成了一个全面且强大的提示。


from pydantic import BaseModel, Field
from typing import Literal, List
import inspect
import re

# 假设 build_system_prompt 函数已定义
def build_system_prompt(instruction: str="", example: str="", pydantic_schema: str="") -> str:
    # ... function implementation ...
    delimiter = "\n\n---\n\n"
    schema_section = ""
    if pydantic_schema:
        schema_section = f"Your answer should be in JSON and strictly follow this schema, filling in the fields in the order they are given:\n```\n{pydantic_schema}\n```"
    if example:
        example = delimiter + example.strip()
    if schema_section:
        schema_section = delimiter + schema_section.strip()
    system_prompt = instruction.strip() + schema_section + example
    return system_prompt

class QueryRouterPrompt:

    # 需要语义理解的字段 (用于 ChromaDB)
    _SEMANTIC_FIELDS = [
        "name", "synopsis", "description", "solution", "see_also", "plugin_output", "stig_severity"
    ]
    # 无需语义理解的结构化字段 (用于 MySQL)
    _STRUCTURED_FIELDS = [
        "id", "uuid", "plugin_id", "cve", "cvss_v2_0_base_score", "risk", "host",
        "protocol", "port", "cvss_v3_0_base_score", "cvss_v2_0_temporal_score",
        "cvss_v3_0_temporal_score", "risk_factor", "bid", "xref", "mskb",
        "plugin_publication_date", "plugin_modification_date", "timestamp"
    ]

    instruction = """
你是一个顶级的智能查询路由系统。
你的任务是深入分析用户的查询意图，并判断该查询应该由哪种数据库处理：

- **ChromaDB (语义数据库)**: 用于处理需要理解**概念**、**意义**或**上下文**的查询。当你需要**发现**、**探索**或**查找与某个主题相关**的信息时，这是首选。这通常涉及对`name`, `description`, `synopsis`, `solution`等文本字段的搜索。

- **MySQL (关系型数据库)**: 用于处理**精确**、**结构化**的查询。当你需要基于明确的字段值（如ID, CVE编号, IP地址, 日期, 端口号, 分数）进行**过滤**、**计数**、**聚合**、**排序**或**计算**时，这是首选。

**关键决策原则：**
对于混合查询（同时包含语义概念和结构化条件），请遵循**“语义优先”**原则。如果查询的核心目的是**发现**一类事物（例如，“远程代码执行漏洞”、“凭证泄露问题”），那么即使它附带了结构化过滤器（如时间范围、主机IP），也应首先路由到ChromaDB进行语义发现，后续的过滤和聚合可以在结果集上进行。
"""

    class QueryRouteDecision(BaseModel):
        database_choice: Literal["ChromaDB", "MySQL"] = Field(description="选择 'ChromaDB' 用于语义/发现类查询，选择 'MySQL' 用于精确/结构化查询。")
        reasoning: str = Field(description="详细解释你的决策过程。说明查询的意图是什么，为什么所选数据库是最佳选择，并简述可能的执行逻辑。")
        relevant_fields: List[str] = Field(description="列出查询中明确或隐含提及的、影响你决策的所有字段。")

    pydantic_schema = re.sub(r"^ {4}", "", inspect.getsource(QueryRouteDecision), flags=re.MULTILINE)

    example = r"""
Example 1 (纯语义发现):
用户查询: "查找所有关于Apache Struts的远程代码执行漏洞。"
```json
{
    "database_choice": "ChromaDB",
    "reasoning": "查询的核心是发现一个特定的漏洞类别：'Apache Struts远程代码执行'。这是一个纯粹的语义概念搜索，需要理解文本内容，因此ChromaDB是最佳选择。",
    "relevant_fields": ["name", "description", "synopsis"]
}
```

Example 2 (纯结构化过滤):
用户查询: "查找CVE编号为'CVE-2023-12345'的插件信息。"
```json
{
    "database_choice": "MySQL",
    "reasoning": "查询要求根据一个精确的、结构化的ID ('CVE-2023-12345') 进行查找。这是关系型数据库的经典精确匹配用例，应在MySQL中对'cve'字段执行WHERE查询。",
    "relevant_fields": ["cve"]
}
```

Example 3 (纯结构化聚合):
用户查询: "列出当前漏洞数量最多的前5个主机（host）。"
```json
{
    "database_choice": "MySQL",
    "reasoning": "该查询完全不涉及任何语义理解。它是一个纯粹的结构化数据聚合操作：按'host'字段分组(GROUP BY)，对每个组进行计数(COUNT)，按计数值降序排序(ORDER BY)，并取前5条结果(LIMIT)。这是MySQL的经典分析查询。",
    "relevant_fields": ["host"]
}
```

Example 4 (混合查询 - 语义优先):
用户查询: "最近一个月，与远程代码执行相关的漏洞，主要集中在哪些主机上？"
```json
{
    "database_choice": "ChromaDB",
    "reasoning": "此查询的核心意图是首先'发现'所有与'远程代码执行'这一概念相关的漏洞。这是一个语义搜索任务。虽然它有结构化条件（'最近一个月'和按'主机'聚合），但这些是应用于语义搜索结果之上的次要操作。根据'语义优先'原则，应首先使用ChromaDB进行发现。",
    "relevant_fields": ["description", "name", "plugin_publication_date", "host"]
}
```

Example 5 (混合查询 - 语义优先):
用户查询: "在所有cvss_v3_0_base_score大于7.0的漏洞中，配置错误类的有多少个？"
```json
{
    "database_choice": "ChromaDB",
    "reasoning": "尽管存在一个明确的结构化过滤器（'cvss_v3_0_base_score > 7.0'），但查询的主要目的是识别一个模糊的类别：'配置错误类'。这是一个语义概念。最高效的路径是先通过ChromaDB找到所有关于'配置错误'的漏洞，然后再对结果集应用CVSS分数过滤器进行计数。",
    "relevant_fields": ["cvss_v3_0_base_score", "name", "description", "solution"]
}
```

Example 6 (混合查询 - 结构化优先):
用户查询: "当cve-1101-1254发生的附近时间时，还产生了哪些漏洞？"
```json
{
    "database_choice": "MySQL",
    "reasoning": "此查询的核心约束是一个基于时间的范围过滤，而这个时间范围本身需要通过一次精确查找（cve-1101-1254）来确定。整个操作可以完全在MySQL中通过两步结构化查询高效完成：1. 查找CVE的日期。2. 使用该日期进行范围查询。语义搜索在此不是必需的，也不是最高效的。",
    "relevant_fields": ["cve", "plugin_publication_date", "timestamp"]
}
```
"""

    user_prompt = "用户查询: '{query}'"

    system_prompt = build_system_prompt(instruction, example, pydantic_schema)



# You can also add these for clarity, though they are implicitly part of the instruction
    @property
    def semantic_fields_description(self):
        return f"语义相关字段 (ChromaDB): {', '.join(self._SEMANTIC_FIELDS)}"

    @property
    def structured_fields_description(self):
        return f"结构化相关字段 (MySQL): {', '.join(self._STRUCTURED_FIELDS)}"



if __name__ == "__main__":
    # 示例查询列表，用于测试不同的场景
    test_queries = [
        "查找所有关于Apache Struts的远程代码执行漏洞。",
        "查找CVE编号为'CVE-2023-12345'的插件信息。",
        "列出当前漏洞数量最多的前5个主机（host）。",
        "最近一个月，与远程代码执行相关的漏洞，主要集中在哪些主机上？",
        "在所有cvss_v3_0_base_score大于7.0的漏洞中，配置错误类的有多少个？",
        "当cve-1101-1254发生的附近时间时，还产生了哪些漏洞？"
    ]

    # 实例化 QueryRouterPrompt
    qr_prompt = QueryRouterPrompt()

    # 打印构建好的 system_prompt 作为参考
    print("=== System Prompt ===")
    print(qr_prompt.system_prompt)
    print("\n" + "=" * 80 + "\n")

    # 针对每个测试查询，生成用户提示
    for i, query in enumerate(test_queries, 1):
        full_prompt = qr_prompt.user_prompt.format(query=query.strip())
        print(f"Test Query {i}:")
        print(full_prompt)
        print("-" * 80)