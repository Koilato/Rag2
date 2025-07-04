"""
### 你的原始提示评估：

**优点：**
1.  **角色和任务明确：** 一开始就清晰地定义了模型的能力和目标。
2.  **分类标准清晰细致：** 对每种分类类型都有明确的定义、关键特征和多个示例，这对于模型理解任务至关重要。
3.  **输出格式要求严格：** 明确要求 JSON 格式，并定义了字段名称和类型，避免了自由文本输出。
4.  **示例直接：** 提供了JSON输出的示例，直观展示了预期结果。

**缺点（与 `ComparativeAnswerPrompt` 结构对比）：**
1.  **结构缺乏Pydantic的规范化：** `ComparativeAnswerPrompt` 使用 Pydantic `BaseModel` 来定义输出 Schema，这使得 Schema 定义更具代码化、可验证性，并且能够通过 `inspect` 动态提取，便于在代码中使用和维护。你的原始提示是文本描述 JSON 结构。
2.  **指令、示例、用户提示混杂：** 你的提示将“角色”、“任务”、“分类标准”和“输出格式要求”混合在一起，没有像 `ComparativeAnswerPrompt` 那样明确地将 `instruction` (指令)、`user_prompt` (用户输入模板) 和 `example` (示例) 分离开来，并通过 `build_system_prompt` 函数组合。
3.  **缺少独立的 `user_prompt` 模板：** 你的提示中没有明确指出用户提问的格式，只是给出“输出格式要求”下的一个输出示例。而 `ComparativeAnswerPrompt` 有一个独立的 `user_prompt` 字符串模板，明确了用户如何与系统交互。
4.  **`system_prompt` 的构建不明确：** 你的提示是一个整体，没有展示如何将指令、模式和示例组合成最终发送给 LLM 的 `system_prompt`。`build_system_prompt` 函数提供了这种规范化组合的方式。
5.  **`analysis` 字段的粒度：** `ComparativeAnswerPrompt` 经常包含 `step_by_step_analysis` 和 `reasoning_summary` 两个字段，前者更详细，后者更简洁。你的 `analysis` 字段更接近 `reasoning_summary` 的作用。对于意图分类这种相对直接的任务，你的 `analysis` 字段可能足够，但在更复杂的推理任务中，`step_by_step_analysis` 可以强制模型进行更深入的思考。

"""

### 模仿 `ComparativeAnswerPrompt` 结构的重写：
"""
为了模仿 `ComparativeAnswerPrompt` 的结构，我们将你的提示内容拆分并重构：

*   **`instruction`**: 包含你的“角色”、“任务”和“分类标准与定义”部分。
*   **`user_prompt`**: 定义用户如何提问的模板，这里简单地假设用户直接提供查询字符串。
*   **`ClassificationSchema`**: 一个 Pydantic `BaseModel`，用于定义 `category` 和 `analysis` 字段及其描述。
*   **`pydantic_schema`**: 动态从 `ClassificationSchema` 生成的字符串表示。
*   **`example`**: 包含输入和输出的完整示例。
*   **`system_prompt` 和 `system_prompt_with_schema`**: 使用 `build_system_prompt` 函数构建。
"""

from pydantic import BaseModel, Field
from typing import Literal, List, Union
import inspect
import re



# build_system_prompt 函数的定义
def build_system_prompt(instruction: str = "", example: str = "", pydantic_schema: str = "") -> str:
    delimiter = "\n\n---\n\n"
    schema = f"Your answer should be in JSON and strictly follow this schema, filling in the fields in the order they are given:\n```\n{pydantic_schema}\n```"
    if example:
        example = delimiter + example.strip()
    if schema:
        schema = delimiter + schema.strip()

    system_prompt = instruction.strip() + schema + example
    return system_prompt

class SecurityQueryIntentPrompt:
    instruction = """
你是一个专业的网络安全数据查询意图分析引擎。
我的数据库包含了漏洞扫描的详细结果，主要列名有 `cve`, `cvss_v3_0_base_score`, `risk`, `host`, `port`, `name`, `solution`, `plugin_publication_date` 等。

你的任务是严格按照以下给出的分类标准，将用户基于网络安全数据的提问，准确地归类到以下四种类型中的一种：【检索】、【计数】、【对比】、【链式查询】。

分类标准与定义:

1.  **【检索 (Retrieval)】**
    *   定义：查询关于**单个或一组特定目标**（如某个CVE、某个主机）的**具体信息**。问题通常可以直接通过一次数据库查找来回答。
    *   关键特征：意图直接，获取具体字段的值。
    *   示例：
        *   "请告诉我 CVE-2021-44228 的解决方案(solution)是什么？"
        *   "查询主机 'web-server-01' 上漏洞名称(name)为 'Apache Log4j RCE' 的风险等级(risk)。"
        *   "plugin_id 为 155999 的漏洞的详细描述(description)是什么？"

2.  **【计数 (Counting)】**
    *   定义：统计满足一个或多个条件的**项目的总数**。答案是一个数字。
    *   关键特征：问题的核心是“有多少”、“总数是”、“统计一下数量”。
    *   示例：
        *  "我们有多少个风险等级(risk)为‘Critical’的漏洞？"
        *  "统计一下 CVSS 3.0 基础分(cvss_v3_0_base_score)超过 9.0 的漏洞总共有几个？"
        *  "主机 'prod-db-01' 上总共发现了多少个漏洞？"

3.  **【对比 (Comparison)】**
    *   定义：比较**两个或多个明确的主体**（如两个主机、两个CVE），在**一个或多个共同属性**上的异同点。
    *   关键特征：问题中明确出现了两个或以上需要进行比较的对象。
    *   示例：
        *  "对比一下主机 'prod-db-01' 和 'staging-db-01' 上 CVSS 3.0 分数大于7的漏洞列表。"
        *  "CVE-2021-44228 和 CVE-2022-22965 这两个漏洞，哪个的 CVSS 3.0 基础分(cvss_v3_0_base_score)更高？"
        *  "比较一下漏洞 'Log4Shell' 和 'Spring4Shell' 在风险因素(risk_factor)上有什么不同？"

4.  **【链式查询 (Chained Query)】**
    *   定义：问题包含**嵌套的依赖关系**，需要先进行一次查询，并利用其结果作为输入进行第二次查询。
    *   关键特征：存在“A的B的C”这种从属结构，或者一个查询的结果是下一个查询的条件。
    *   示例：
        *  "找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞，并列出所有受该漏洞影响的主机地址(host)。"
        *  "列出所有受 'Apache Log4j RCE' 漏洞影响的主机，并统计这些主机上一共有多少个风险等级为'High'的漏洞。"
        *  "找到最新发布(plugin_publication_date)的那个漏洞的CVE编号，并查询该CVE的解决方案(solution)。"
"""

    user_prompt = "用户查询: '{query}'"

    class ClassificationSchema(BaseModel):
        """对网络安全数据查询意图进行分类"""
        category: Literal["检索", "计数", "对比", "链式查询"] = Field(
            description="查询的分类，必须是【检索】、【计数】、【对比】、【链式查询】中的一个。"
        )
        analysis: str = Field(
            description="对分类判断依据的简要解释，用一句话概括。"
        )

    # 动态生成 Pydantic Schema 字符串，模仿原文的 inspect.getsource 和 re.sub
    # 注意：为了简化，这里直接复制了模型的字符串表示，实际应用中会用 inspect
    pydantic_schema = '''
class ClassificationSchema(BaseModel):
    """对网络安全数据查询意图进行分类"""
    category: Literal["检索", "计数", "对比", "链式查询"] = Field(
        description="查询的分类，必须是【检索】、【计数】、【对比】、【链式查询】中的一个。"
    )
    analysis: str = Field(
        description="对分类判断依据的简要解释，用一句话概括。"
    )
'''
    # 移除多余的缩进，与原文的 re.sub(r"^ {4}", "", inspect.getsource(AnswerSchema), flags=re.MULTILINE) 类似
    pydantic_schema = re.sub(r"^ {4}", "", pydantic_schema, flags=re.MULTILINE)


    example = r"""
Example:
Input:
用户查询: '找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞，并列出所有受该漏洞影响的主机地址(host)。'

Output:
```json
{
  "category": "链式查询",
  "analysis": "问题需要先找出CVSS分数最高的漏洞，再用该漏洞作为条件去查找受影响的主机。"
}
```
"""
    # 完整系统提示 (不包含 Pydantic Schema，仅用于说明)
    system_prompt = build_system_prompt(instruction, example)

    # 完整系统提示 (包含 Pydantic Schema)
    system_prompt_with_schema = build_system_prompt(instruction, example, pydantic_schema)





