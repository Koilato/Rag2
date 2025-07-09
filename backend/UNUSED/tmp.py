import chromadb
import json
import pandas as pd


# ==============================================================================
# 1. JSON 到 ChromaDB 'where' 过滤器转换函数 (此函数无需修改)
# ==============================================================================
def json_to_chromadb_where_filter(condition_obj):
    if not isinstance(condition_obj, dict):
        raise ValueError("条件必须是一个字典")
    if "$and" in condition_obj:
        if not isinstance(condition_obj["$and"], list) or not condition_obj["$and"]:
            raise ValueError("$and 的值必须是非空列表")
        clauses = [json_to_chromadb_where_filter(cond) for cond in condition_obj["$and"]]
        return {"$and": clauses}
    elif "$or" in condition_obj:
        if not isinstance(condition_obj["$or"], list) or not condition_obj["$or"]:
            raise ValueError("$or 的值必须是非空列表")
        clauses = [json_to_chromadb_where_filter(cond) for cond in condition_obj["$or"]]
        return {"$or": clauses}
    elif "$not" in condition_obj:
        inner_condition = condition_obj["$not"]
        if not isinstance(inner_condition, dict) or "operator" not in inner_condition:
            raise ValueError("$not 的值必须是一个包含 'operator' 的条件对象")
        field, op, value = inner_condition.get("field"), inner_condition.get("operator"), inner_condition.get("value")
        inverse_op_map = {"$eq": "$ne", "$ne": "$eq", "$gt": "$lte", "$gte": "$lt", "$lt": "$gte", "$lte": "$gt",
                          "$in": "$nin", "$nin": "$in"}
        if op in inverse_op_map:
            return {field: {inverse_op_map[op]: value}}
        elif op == "$like":
            raise NotImplementedError("ChromaDB 不支持 '$like' 或 'NOT $like' 操作。")
        else:
            raise ValueError(f"无法对操作符 '{op}' 执行 $not 操作。")
    else:
        field, operator_json = condition_obj.get("field"), condition_obj.get("operator")
        if not field: raise ValueError(f"条件对象缺少 'field' 键: {condition_obj}")
        if not operator_json: raise ValueError(f"条件对象 '{field}' 缺少 'operator' 键: {condition_obj}")

        # !! 注意: 虽然我们不再存储None, 但保留此逻辑可能对其他场景有用 !!
        # 如果查询JSON仍然可能包含$isNull, 我们将其转换为查询我们的占位符 ""
        if operator_json == "$isNull":
            return {field: {"$eq": ""}}  # 关键修改：查询空字符串
        if operator_json == "$isNotNull":
            return {field: {"$ne": ""}}  # 关键修改：查询非空字符串

        if "value" not in condition_obj:
            raise ValueError(f"操作符 '{operator_json}' 需要 'value' 键，但在条件对象 '{field}' 中未找到。")
        value = condition_obj.get("value")
        supported_chroma_ops = ["$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin"]
        if operator_json in supported_chroma_ops:
            return {field: {operator_json: value}}
        elif operator_json == "$like":
            raise NotImplementedError("ChromaDB 的元数据过滤不支持 '$like' 模糊匹配操作。")
        else:
            raise ValueError(f"不支持的ChromaDB操作符: {operator_json}")


# ==============================================================================
# 2. 主测试脚本
# ==============================================================================
if __name__ == '__main__':
    print("--- 开始完整的JSON到ChromaDB转换测试 (已修复NoneType错误) ---")

    # --- 配置ChromaDB（内存模式） ---
    print("\n[步骤 1: 配置内存中的ChromaDB...]")
    client = chromadb.Client()
    collection_name = "vulnerabilities_test_cn_fixed"
    if collection_name in [c.name for c in client.list_collections()]:
        client.delete_collection(name=collection_name)
    collection = client.create_collection(name=collection_name)
    print(f"集合 '{collection_name}' 创建成功。")

    # --- 准备示例数据 ---
    print("\n[步骤 2: 向集合中添加示例数据...]")
    docs = [
        "Critical vulnerability in Apache Log4j server.",
        "Medium-level security flaw in OpenSSH allowing user enumeration.",
        "Default password found on FTP service on port 21.",
        "Nginx web server with an outdated version, low risk.",
        "SQL injection vulnerability in the internal web application.",
        "Host with no CVE findings but port 8080 is open.",
        "Self-signed TLS certificate detected on port 9000.",
    ]

    # ==========================================================
    # !! 关键修复 1: 将所有 `None` 值替换为空字符串 `""` !!
    # ==========================================================
    metadatas = [
        {'host': 'server-01', 'port': 443, 'protocol': 'tcp', 'risk': 'Critical', 'cve': 'CVE-2021-44228',
         'name': 'Apache Log4j', 'timestamp': 1672531200},
        {'host': 'server-02', 'port': 22, 'protocol': 'tcp', 'risk': 'Medium', 'cve': 'CVE-2018-15473',
         'name': 'OpenSSH', 'timestamp': 1675209600},
        {'host': 'server-03', 'port': 21, 'protocol': 'tcp', 'risk': 'High', 'cve': "", 'name': 'vsftpd',
         'timestamp': 1677628800},
        {'host': 'server-01', 'port': 80, 'protocol': 'tcp', 'risk': 'Low', 'cve': "", 'name': 'Nginx',
         'timestamp': 1680307200},
        {'host': 'webapp-db', 'port': 3306, 'protocol': 'tcp', 'risk': 'High', 'cve': 'CVE-2019-12345',
         'name': 'Custom Web App', 'timestamp': 1682899200},
        {'host': 'test-vm', 'port': 8080, 'protocol': 'tcp', 'risk': 'Info', 'cve': "", 'name': 'Tomcat',
         'timestamp': 1685577600},
        {'host': 'server-01', 'port': 9000, 'protocol': 'tcp', 'risk': 'Medium', 'cve': "", 'name': 'Internal API',
         'timestamp': 1688169600},
    ]
    ids = [f"doc_{i + 1}" for i in range(len(docs))]

    collection.add(documents=docs, metadatas=metadatas, ids=ids)
    print(f"{collection.count()} 个文档已添加到集合中。")

    # --- 定义测试用例 ---
    print("\n[步骤 3: 定义JSON过滤器测试用例...]")
    # ===================================================================
    # !! 关键修复 2: 更新空值测试用例以匹配新的数据表示法 !!
    # ===================================================================
    test_cases = [
        {
            "description": "复杂测试：风险为'High'或'Critical' 并且 (端口 > 1000 或 协议为 'tcp')",
            "json_filter": {
                "$and": [
                    {"field": "risk", "operator": "$in", "value": ["High", "Critical"]},
                    {"$or": [{"field": "port", "operator": "$gt", "value": 1000},
                             {"field": "protocol", "operator": "$eq", "value": "tcp"}]}
                ]
            }
        },
        {
            "description": "简单测试：精确查找Log4j的CVE编号",
            "json_filter": {"field": "cve", "operator": "$eq", "value": "CVE-2021-44228"}
        },
        {
            "description": "范围测试：端口在1到100之间",
            "json_filter": {"$and": [{"field": "port", "operator": "$gt", "value": 0},
                                     {"field": "port", "operator": "$lte", "value": 100}]}
        },
        {
            "description": "空值测试：查找'cve'字段为空字符串 `""` 的文档 (替代原来的isNull)",
            "json_filter": {"field": "cve", "operator": "$eq", "value": ""}  # 原来是 $isNull
        },
        {
            "description": "否定测试：查找主机名不是'server-01'的文档",
            "json_filter": {"$not": {"field": "host", "operator": "$eq", "value": "server-01"}}
        },
        {
            "description": "错误处理测试：尝试使用不支持的操作符'$like'",
            "json_filter": {"field": "name", "operator": "$like", "value": "%Apache%"}
        }
    ]

    # --- 执行与验证 ---
    print("\n[步骤 4: 执行测试用例...]")
    for i, test in enumerate(test_cases):
        print(f"\n--- 测试用例 {i + 1}: {test['description']} ---")
        print("输入的JSON过滤器:")
        print(json.dumps(test['json_filter'], indent=2, ensure_ascii=False))
        try:
            chromadb_filter = json_to_chromadb_where_filter(test['json_filter'])
            print("--------------------")
            print(test['json_filter'])
            print(chromadb_filter)
            print("--------------------")
            print("\n转换后的ChromaDB过滤器:")
            print(json.dumps(chromadb_filter, indent=2, ensure_ascii=False))
            results = collection.get(where=chromadb_filter)
            print(f"\n数据库查询结果 (找到 {len(results['ids'])} 条):")
            if results['ids']:
                for j, doc_id in enumerate(results['ids']):
                    print(f"  - ID: {doc_id}, 元数据: {results['metadatas'][j]}")
            else:
                print("  - 未找到匹配此过滤器的文档。")
        except (ValueError, NotImplementedError) as e:
            print(f"\n错误：转换按预期失败。")
            print(f"  错误信息: {e}")

    print("\n--- 所有测试已完成。 ---")