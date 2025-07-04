# 执行链（Chain of Thought）
import os
import pandas as pd
from dotenv import load_dotenv
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 在程序的开头调用 load_dotenv()
load_dotenv()

# 检查 API Key 是否已成功加载
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("错误：未找到 DASHSCOPE_API_KEY。请确保您的 .env 文件中已正确设置该变量。")

# 使用加载到的密钥初始化模型
llm = ChatTongyi(model_name="qwen-plus", temperature=0)

# 模拟数据
data = {
    'cve_id': ['CVE-2024-1001', 'CVE-2024-1002', 'CVE-2023-5001', 'CVE-2024-1001', 'CVE-2024-9999', 'CVE-2023-5001'],
    'host': ['prod-db-01', 'prod-db-01', 'staging-db-01', 'prod-web-05', 'prod-db-02', 'prod-web-05'],
    'cvss_v3_0_base_score': [7.5, 9.8, 8.1, 7.5, 9.8, 8.1]
}
vulnerabilities_df = pd.DataFrame(data)
dataframe_as_string = vulnerabilities_df.to_string()
print("--- 我们的模拟数据 ---")
print(dataframe_as_string)
print("--------------------------\n")

output_parser = StrOutputParser()

# 强化后的提示词
prompt_one = PromptTemplate.from_template("""
你是一个精准的数据提取助手。你的任务是严格按照指令从文本中提取信息，不要进行任何解释或说任何额外的话。
根据以下数据：
---
{dataframe_str}
---
请提取出最高的 cvss_v3_0_base_score 值。
你的回答必须只包含这个数字。
示例输出:
9.8
""")
#  prompt_one -> llm -> output_parser
chain_one = prompt_one | llm | output_parser

prompt_two = PromptTemplate.from_template("""
你是一个精准的数据提取助手。你的任务是严格按照指令从文本中提取信息，不要进行任何解释或说任何额外的话。
已知有以下数据：
---
{dataframe_str}
---
并且已知最高分是 {max_score}。
请提取出所有分数为 {max_score} 的 cve_id。
你的回答必须是一个用逗号分隔的列表。
示例输出:
CVE-2024-1234,CVE-2024-5678
""")
chain_two = prompt_two | llm | output_parser

prompt_three = PromptTemplate.from_template("""
你是一个精准的数据提取助手。你的任务是严格按照指令从文本中提取信息，不要进行任何解释或说任何额外的话。
已知有以下数据：
---
{dataframe_str}
---
以及相关的漏洞列表: {cve_list}。
请提取出所有受到这些漏洞影响的、不重复的主机名（host）。
你的回答必须是一个用逗号分隔的列表。
示例输出:
prod-db-01,staging-db-01,prod-web-05
""")
chain_three = prompt_three | llm | output_parser

# 【已修正】: 使用纯 LCEL 组合所有步骤
overall_chain = (
    RunnablePassthrough.assign(max_score=chain_one)
    | RunnablePassthrough.assign(cve_list=chain_two)
    | RunnablePassthrough.assign(host_list=chain_three) # 已移除多余的括号
)

# 执行并分析结果
print("--- 开始执行从 .env 加载密钥的 LCEL 链 ---")
final_result = overall_chain.invoke({"dataframe_str": dataframe_as_string})

print("\n--- 最终结构化结果 ---")
print(final_result)