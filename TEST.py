import CsvDataOp
import MySqlSource
import VectorDatabase
import utils
import ALiYunConnection

#连接mysql和chromadb
mysql_connect = MySqlSource.connect_to_mysql()
chroma_client,chroma_collection=VectorDatabase.connect_to_chromadb()

pdfile = CsvDataOp.transform_nessus_data("H:\RagCline\input_data.csv")

# 文件名就是时间
filename = pdfile['timestamp'][0]
print(filename)

# 文件放到mysql中
MySqlSource.create_pd_table(mysql_connect, "rag", filename, use_vulnerability_template=True)
pdfile = utils.add_ids_and_uuid(mysql_connect, pdfile, filename, filename)
pdfile.to_csv('outid.csv', index=False, encoding='utf-8')
MySqlSource.insert_vulnerability_data(mysql_connect, filename, pdfile)

# mysql->chromadb

pd=MySqlSource.fetch_unindexed_data_from_all_tables(mysql_connect,'rag')
print("==============准备放入chromadb的内容===============")
print(pd)

## 写入到 集合 'vulnerability_collection'
MySqlSource.sync_mysql_to_chromadb(mysql_connect,chroma_client,'rag', filename,'vulnerability_collection',1000)

# 查询chromadb

## 文字->json

file_path = "prompt_for_json.txt"  # 请替换为实际文件路径
with open(file_path, 'r', encoding='utf-8') as file:
    prompt1 = file.read()
### ------------------------------- 在这输入问题 -------------------------------------------
question="“把所有和 ’SSL’相关的漏洞，按风险等级（risk）分类统计一下。”"
### --------------------------------在上面输入问题-------------------------------------
message = [
    {"role": "system", "content": f"{prompt1}"},
    {"role": "user", "content": f"{question}"}
]

response1 = ALiYunConnection.qwen_query(message, stream=False, enable_thinking=False)
full_text1 = response1.choices[0].message.content
print("full_text1:",full_text1)

"""
你的返回值只能是一个json
"""
# llm返回的是文本，文本要解析成为json
full_text1=utils.parse_llm_json_output(full_text1)

# n_result这个参数是需要手动调整参数的
n_results=30
where_clause=full_text1["chroma_where_filter"]
query_text=full_text1["query_text"]


uuids=VectorDatabase.query_vulnerabilities_for_uuids(query_text,n_results,where_clause,chroma_collection)
print(uuids)
# 注意这里uuids的类型是list
print(type(uuids))
# table_info=utils.decode_uuid_list(uuids)
# print(table_info)
docs=VectorDatabase.get_full_documents_from_mysql(uuids)
print(docs)


docs=utils.format_mysql_dataframe_for_llm(docs)
print(docs)
today_time=utils.get_today_date_formatted()

file_path = "prompt_for_answer.txt"  # 请替换为实际文件路径
with open(file_path, 'r', encoding='utf-8') as file:
    prompt2 = file.read()

new_message = [
    {"role": "system", "content": f"{prompt2}"},
    {"role": "user","content": f"{question}：今天的日期是：{today_time}以下是相关文本：\n\n{docs},要输出成markdown表格的形式，同时每一回答来源都要给出原始的uuid" }
]


response2=ALiYunConnection.qwen_query(new_message, stream=False, enable_thinking=False)
full_text2 = response2.choices[0].message.content
print("full_text2:",full_text2)