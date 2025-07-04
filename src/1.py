JudgementPrompt=r""""

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
JudgementMessage = [
        {"role": "system", "content": JudgementPrompt},
        {"role": "user", "content": "这是一个输入文本"}
    ]


Convert2JsonPrompt=r"""  你需要对于不同的问题做出不同的行为

# ------------------------------------------- 将问题装换成为检索问题的内容 --------------------------------------------------#

##-----------检索-------------##
检索：
问题的json结构={
    ”原问题“:”数据库里面有哪些高位漏洞，列出来“
    "保留原意精简后的问题":"有哪些高位漏洞？"
    ”子问题“:[“有哪些高位漏洞？”]
}

##-----------计数-------------##
计数：从原问题中提取出检索问题
     example:统计一下 CVSS 3.0 基础分(cvss_v3_0_base_score)超过 9.0 的漏洞总共有几个？

问题的json结构={
    ”原问题“:”统计一下 CVSS 3.0 基础分(cvss_v3_0_base_score)超过 9.0 的漏洞总共有几个？“
    "保留原意精简后的问题":"统计 cvss_v3_0_base_score 超过 9.0 的漏洞总数。"
    ”子问题“:[“有哪些cvss_v3_0_base_score 超过 9.0 的漏洞？”]
}

##-----------对比-------------## 
对比：将原问题转换为多个检索问题   
    对比一下主机 'prod-db-01' 和 'staging-db-01' 上 CVSS 3.0 分数大于7的漏洞列表。
    ->需要检索的关键字有{"关键字列表"}
    ->原问题
    ->prod-db-01的信息是：
    ->staging-db-01的信息是
    
{
  "原问题": "对比一下主机 'prod-db-01' 和 'staging-db-01' 上 CVSS 3.0 分数大于7的漏洞列表",
  "保留原意精简后的问题": "对比 'prod-db-01' 和 'staging-db-01' 上 cvss_v3_0_base_score 大于 7 的漏洞列表。",
  "子问题": [
    "主机 'prod-db-01' 上有哪些 cvss_v3_0_base_score 大于 7 的漏洞？",
    "主机 'staging-db-01' 上有哪些 cvss_v3_0_base_score 大于 7 的漏洞？"
  ]
}
## ----------链式查询---------##
链式查询:将原问题转换成为问题链
    原问题：找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞，并列出所有受该漏洞影响的主机地址(host)。
    ->步骤1:CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞的是什么？
    ->步骤2:{”上一个问题的答案输入后“}影响的主机有？


问题的json结构={
    ”原问题“:”我现在需要你帮我找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的那个漏洞，并列出所有受该漏洞影响的主机地址(host)“
    "保留原意精简后的问题":"找出 CVSS 3.0 基础分(cvss_v3_0_base_score)最高的漏洞，并列出所有受该漏洞影响的主机地址(host)"
    ”子问题“:[“子问题1”,“子问题2”,“子问题3”]子问题里面全是检索问题
    ### “子问题答案”:["子问题1的参考文档是:xxxxx","子问题2的参考文档是:xxxxx"]
}

# ------------------------------------------- 将检索问题转换成为json的内容 --------------------------------------------------#

子问题--llm-->json结构
应该解析的硬编码内容有：['plugin_id', 'cve', 'cvss_v2_0_base_score', 'fingerprint', 'risk', 'host', 'protocol', 'port', 'name', 'synopsis', 'description',
                    'solution', 'see_also', 'plugin_output', 'stig_severity', 'cvss_v3_0_base_score', 'cvss_v2_0_temporal_score', 'cvss_v3_0_temporal_score', 'risk_factor', 'bid', 
                    'xref', 'mskb', 'plugin_publication_date', 'plugin_modification_date', 'timestamp']

下面这些内容的目的是实现select a from b where c groupby d 

###-------这里需要调用time.datatime中获取信息-------###
在这里需要传入{current time}，使用time.datetime获取信息
你需要从{question}中理解句子的开始时间和结束时间，然后给出"daterange":{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}

- where c: filter里面的内容是用于where过滤
- groupby d 和 select a: aggregation_operation的目的是选出select 和 groupby的内容
- from b: 从daterange中获取信息，这个代表表名

我允许的操作符为:OPERATOR_MAP = {
    "$eq": "=", "$ne": "!=", "$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<=",
    "$in": "IN", "$nin": "NOT IN", "$like": "LIKE"
}

# ------一个检索问题会解析出来的json格式----------------- #

sub_problem_json = {

  "user_query": "查询2023年之后的数据，过滤掉描述中包含‘测试’的内容，并按主机和应用名称分组统计",
  "semantic": "TRUE",
  "overall_intent": "complex_aggregation_with_filters",
  "execution_plan": [
    {
      "step_type": "Retrieval", 
      "inputs": {
        "filter_conditions": {
          "$and": [
            { "field": "creation_date", "operator": "$gt", "value": "2023-01-01" },
            {"$not": {"field": "description","operator": "$like","value": "%测试%"}},
            {"$or": [{"field": "status","operator": "$eq","value": "Open"},{"field": "status","operator": "$eq","value": "In Progress"}]},
          ]
        },
        "aggregation_operation": [
          {"select_column_name": "host"},
          {"select_column_name": "app_name"}
        ]
      },
      "daterange":{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}
    }
  ]
}
    
# ------------------------------------------- 这是问题最后返回的形态 --------------------------------------------------#    

问题的json结构={
    ”原问题“:”这是一个原问题“
    "保留原意精简后的问题":"这是一个精简后的问题"
    “问题的类型”:
    ”子问题“:[“子问题1”,“子问题2”,“子问题3”]子问题里面全是检索问题
    ### “子问题答案”:["子问题1的参考文档是:xxxxx","子问题2的参考文档是:xxxxx"]
}

"""


#
# from ALiYunConnection import qwen_query
# qwen_query(JudgementMessage)
