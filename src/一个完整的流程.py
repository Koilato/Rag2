import CsvDataOp
import MySqlSource
import VectorDatabase

pdfile = CsvDataOp.transform_nessus_data("H:\RagCline\input_data.csv")
connect = MySqlSource.connect_to_mysql()

# 文件名就是时间
filename = pdfile['timestamp'][0]
print(filename)
MySqlSource.create_pd_table(connect, "rag", filename, use_vulnerability_template=True)
CsvDataOp.add_ids_and_uuid_inplace(connect, pdfile, filename, filename)
pdfile.to_csv('outid.csv', index=False, encoding='utf-8')
MySqlSource.insert_vulnerability_data(connect, filename, pdfile)
