import configparser
import os
import mysql.connector
from dotenv import load_dotenv  # 新增导入
import pandas as pd
import chromadb
from chromadb.types import Collection

"""
你现在时一个问题拆分助手，我会输入一个问题，然后你将按我的要求分类和改造这些问题

一共有四类问题：检索、统计、对比、链式查询
以下是这四类问题的定义

"""




ls=r"""
1.  **【检索 (Retrieval)】**
    *   定义：查询关于**单个或一组特定目标**（如某个CVE、某个主机）的**具体信息**。
    *   关键特征：意图直接，获取具体字段的值。
    *   示例：
        *   "请告诉我 CVE-2021-44228 的解决方案(solution)是什么？"
        *   "查询主机 'web-server-01' 上漏洞名称(name)为 'Apache Log4j RCE' 的风险等级(risk)。"
        *   "plugin_id 为 155999 的漏洞的详细描述(description)是什么？"

2.  **【计数 (Counting)】**
    *   定义：统计满足一个或多个条件的**项目的总数**。。
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

ls=r"""
区分出类别之后（【检索 (Retrieval)】、【计数 (Counting)】、【对比 (Comparison)】、【链式查询 (ChainedQuery)】）
你需要对于不同的问题做出不同的行为
检索：返回精简过后的原问题:{"这里是精简过后的原问题"}
计数：将原问题转换为一个检索问题+一种操作
     example:统计一下 CVSS 3.0 基础分(cvss_v3_0_base_score)超过 9.0 的漏洞总共有几个？
     ->{”有哪些CVSS 3.0 基础分(cvss_v3_0_base_score)超过 9.0 的漏洞？"}+{”原问题一字不差的输入“}
 
对比：将原问题转换为多个检索问题+一种操作    
    对比一下主机 'prod-db-01' 和 'staging-db-01' 上 CVSS 3.0 分数大于7的漏洞列表。
    ->需要检索的关键字有{"关键字列表"}
    ->原问题
    ->prod-db-01的信息是：
    ->staging-db-01的信息是
    
链式查询:将原问题转换成为问题链
    原问题：找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞，并列出所有受该漏洞影响的主机地址(host)。
    ->步骤1:CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞的是什么？
    ->步骤2:{”上一个问题的答案输入后“}影响的主机有？

"""


output={
    "count_info":"原问题",
    "category":"Retrieval/Counting/Comparison/ChainedQuery",
    "question":"[”问题1”,”问题2”,“问题3”]",
    "select":["从原问题1中要选取的列号","从原问题2中要选取的列号","从原问题3中要选取的列号"],
}


from ALiYunConnection import qwen_query

# 将这个函数放在你的 query_vulnerabilities 函数之后，主程序之前
import chromadb
from chromadb.utils import embedding_functions
import VectorDatabase



# 因为对于不同类型的问题有可能可以使用where过滤，所以应该要使用这种if-else的写法

def get_info_from_json_through_chromadb(llm_info: dict,
                      chroma_collection: chromadb.Collection,
                      n_results: int = 5,
                      where_clause: dict = None):
    print(f"\n--- 正在处理LLM的请求: {llm_info['count_info']} ---")

    # 检查 category 字段
    category = llm_info.get("category")
    if category == "Retrieval":
        print(f"请求类别为 'f{category}'，开始执行语义相似度搜索。")
        questions = llm_info.get("question")
        if not questions or not isinstance(questions, list) or len(questions) == 0:
            return "错误：LLM输出的 'question' 字段为空或格式不正确。"
        print(f"使用的查询文本: '{questions}'")

        # 通过问题再chromadb中查询内容x
        results_df = chroma_collection.query(
            query_text=questions,
            n_results=n_results,
            where_clause=where_clause,  # 这里可以传入从LLM解析出的更复杂的过滤条件
            chroma_collection=chroma_collection,
            include= ["metadatas", "distances", "documents", "ids"],
            sort=["distance"]
        )
        print("Retrival输出的内容是:",results_df)
        return results_df

    elif category == "Counting":
        print(f"请求类别为 'f{category}'，开始执行语义相似度搜索。")
        questions = llm_info.get("question")
        if not questions or not isinstance(questions, list) or len(questions) == 0:
            return "错误：LLM输出的 'question' 字段为空或格式不正确。"
        print(f"使用的查询文本: '{questions}'")

        # 通过问题再chromadb中查询内容x
        results_df = chroma_collection.query(
            query_text=questions,
            n_results=n_results,
            where_clause=where_clause,  # 这里可以传入从LLM解析出的更复杂的过滤条件
            chroma_collection=chroma_collection,
            include=["metadatas", "distances", "documents", "ids"],
            sort=["distance"]
        )
        print("Retrival输出的内容是:", results_df)
        return results_df


    elif category == "Comparison":
        print(f"请求类别为 'f{category}'，开始执行语义相似度搜索。")
        questions = llm_info.get("question")
        if not questions or not isinstance(questions, list) or len(questions) == 0:
            return "错误：LLM输出的 'question' 字段为空或格式不正确。"
        print(f"使用的查询文本: '{questions}'")

        # 通过问题再chromadb中查询内容x
        results_df = chroma_collection.query(
            query_text=questions,
            n_results=n_results,
            where_clause=where_clause,  # 这里可以传入从LLM解析出的更复杂的过滤条件
            chroma_collection=chroma_collection,
            include=["metadatas", "distances", "documents", "ids"],
            sort=["distance"]
        )
        print("Retrival输出的内容是:", results_df)
        return results_df

    else:
        print(f"请求类别为 'f{category}'，开始执行语义相似度搜索。")
        questions = llm_info.get("question")
        if not questions or not isinstance(questions, list) or len(questions) == 0:
            return "错误：LLM输出的 'question' 字段为空或格式不正确。"
        print(f"使用的查询文本: '{questions}'")

        # 通过问题再chromadb中查询内容x
        results_df = chroma_collection.query(
            query_text=questions,
            n_results=n_results,
            where_clause=where_clause,  # 这里可以传入从LLM解析出的更复杂的过滤条件
            chroma_collection=chroma_collection,
            include=["metadatas", "distances", "documents", "ids"],
            sort=["distance"]
        )
        print("Retrival输出的内容是:", results_df)
        return results_df


if __name__ == "__main__":
    """
    连接chromadb->输入问题->查询数据库->
    """











