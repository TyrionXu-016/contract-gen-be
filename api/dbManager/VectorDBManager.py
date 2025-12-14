"""
向量数据库管理器
"""
import config
import numpy as np
import os
import shutil
import datetime
from api.dbManager.BGEModel import BGEModel
from api.Segment.contract_split import *
from typing import List, Union

class VectorDBManager:
    """向量数据库管理器"""
    
    def __init__(self, persist_directory: str = None):
        """
        初始化向量数据库管理器
        
        Args:
            persist_directory: 数据库存储目录
        """
        import chromadb
        from chromadb.config import Settings
        
        self.persist_directory = persist_directory or config.VECTOR_DB_DIR
        
        # 创建存储目录
        import os
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 初始化BGE模型
        self.bge_model = BGEModel()        
        
        # 获取或创建集合
        self.contract_collection = self.client.get_or_create_collection(
            name=config.COLLECTION_CONTRACTS,
            metadata={"description": "合同模板集合"}
        )
        
        self.law_collection = self.client.get_or_create_collection(
            name=config.COLLECTION_LAWS,
            metadata={"description": "法律法规集合"}
        )

        self.case_collection = self.client.get_or_create_collection(
            name=config.COLLECTION_CASE,
            metadata={"description": "法律案例集合"}
        )
        
    def add_contract_template(self, content: str, metadata: dict) -> dict:
        """
        添加合同模板（包含分段处理）
        
        Args:
            content: 合同内容
            metadata: 元数据
            
        Returns:
            包含模板ID和分段ID的字典
        """
        import uuid
        
        # 生成模板ID
        template_id = metadata.get("id") or str(uuid.uuid4())
        
        # 1. 分段处理
        segments = split_contract(content, data_type="contract")
        segment_embeddings = []
        for i in range(len(segments)):
            print(f"==向量化第{i}段合同文本==")
            embeddings = self.bge_model.encode(segments[i])
            segment_embeddings.append(embeddings)
        segment_embeddings = np.array(segment_embeddings)
        
        # 2. 整体合同向量生成（加权平均）
        # 这里可以根据分段的重要性进行加权，简化版本使用简单平均
        if len(segment_embeddings) > 0:
            # 简单平均
            template_embedding = segment_embeddings.mean(axis=0).tolist()
        else:
            # 如果没有分段，直接编码整个文本
            template_embedding = self.bge_model.encode(content).tolist()
            
        # 3. 存储整体模板
        self.contract_collection.add(
            documents=[content],
            embeddings=template_embedding,
            metadatas=[metadata],
            ids=[template_id]
        )
        
        return {
            "template_id": template_id,
            "segment_count": len(segments),
            "embedding_dim": len(template_embedding)
        }
    
    def add_law_regulation(self, content: str, metadata: dict) -> str:
        """
        添加法律法规
        
        Args:
            content: 法律条文内容
            metadata: 元数据
            
        Returns:
            法规ID
        """
        import uuid
        
        regulation_id = metadata.get("id") or str(uuid.uuid4())
        
        #  分段处理
        segments = split_contract(content, data_type="law")
        for i in range(len(segments)):
            if i%10 == 0:
                print(f"==向量化第{i}-{i+10}段法律文本==")
            embeddings = self.bge_model.encode(segments[i])

            # 存储 TODO 法律法规是否不需要整体存储，只存分段？
            self.law_collection.add(
                documents=[segments[i]],
                embeddings=embeddings,
                metadatas=[metadata],
                ids=[regulation_id]
            )

        return regulation_id
    
    def add_case_template(self, content: str, metadata: dict) -> str:
        """
        添加法律案例
        
        Args:
            content: 法律案例内容
            metadata: 元数据
            
        Returns:
            法律案例ID
        """
        import uuid
        
        regulation_id = metadata.get("id") or str(uuid.uuid4())
        
        #  分段处理
        segments = split_contract(content, data_type="case")
        segment_embeddings = []
        for i in range(len(segments)):
            print(f"==向量化第{i}段案例文本==")
            embeddings = self.bge_model.encode(segments[i])
            segment_embeddings.append(embeddings)
        segment_embeddings = np.array(segment_embeddings)

        # 整体案例向量生成（加权平均）
        # 这里可以根据分段的重要性进行加权，简化版本使用简单平均
        if len(segment_embeddings) > 0:
            # 简单平均
            template_embedding = segment_embeddings.mean(axis=0).tolist()
        else:
            # 如果没有分段，直接编码整个文本
            template_embedding = self.bge_model.encode(content).tolist()

        # 存储
        self.case_collection.add(
            documents=[content],
            embeddings=template_embedding,
            metadatas=[metadata],
            ids=[regulation_id]
        )
        
        return regulation_id

    def search_with_filter(self, query: str, filter_conditions: dict = None, 
                          collection_name: str = "contracts", n_results: int = 5) -> dict:
        """
        带条件过滤的向量搜索
        
        Args:
            query: 查询文本
            filter_conditions: 过滤条件
            collection_name: 集合名称（contracts/laws/case)
            n_results: 返回结果数量
            
        Returns:
            搜索结果
        """
        # 获取指定集合
        if collection_name == "contracts":
            collection = self.contract_collection
        elif collection_name == "laws":
            collection = self.law_collection
        elif collection_name == "case":
            collection = self.case_collection
        else:
            raise ValueError(f"未知的集合名称: {collection_name}")
            
        # 向量化查询文本
        query_embedding = self.bge_model.encode(query).tolist()
        
        # 构建where条件
        where_conditions = None
        if filter_conditions:
            # 转换过滤条件为ChromaDB格式
            where_conditions = {}
            for key, value in filter_conditions.items():
                if isinstance(value, list):
                    where_conditions[key] = {"$in": value}
                else:
                    where_conditions[key] = value
                    
        # 执行查询
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, 100),
            where=where_conditions,
            include=["documents", "metadatas", "distances", "embeddings"]
        )
        
        return results
    
    def dual_matching(self, user_query: str, user_filters: dict = None) -> dict:
        """
        双重匹配：匹配合同模板和法律法规
        
        Args:
            user_query: 用户查询（自然语言描述）
            user_filters: 用户筛选条件
            
        Returns:
            匹配结果
        """
        # 1. 合同模板匹配
        contract_results = self.search_with_filter(
            query=user_query,
            filter_conditions=user_filters,
            collection_name="contracts",
            n_results=config.MAX_CONTRACT_RESULTS
        )
        
        # 2. 法律法规匹配
        law_results = self.search_with_filter(
            query=user_query,
            filter_conditions=user_filters,
            collection_name="laws",
            n_results=config.MAX_LAW_RESULTS
        )
        
        # 3. 法律案例匹配 分段匹配（用于细粒度检索）
        case_results = self.search_with_filter(
            query=user_query,
            filter_conditions=user_filters,
            collection_name="case",
            n_results=config.MAX_CASE_RESULTS
        )
        
        # 处理结果
        processed_contracts = []
        for i in range(len(contract_results['ids'][0])):
            contract = {
                "id": contract_results['ids'][0][i],
                "content": contract_results['documents'][0][i],
                "metadata": contract_results['metadatas'][0][i],
                "similarity": 1 - contract_results['distances'][0][i],
                "embedding": contract_results['embeddings'][0][i] if contract_results['embeddings'] else None
            }
            processed_contracts.append(contract)           
        # 按相似度排序
        processed_contracts.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 处理法律法规
        processed_laws = []
        for i in range(len(law_results['ids'][0])):
            law = {
                "id": law_results['ids'][0][i],
                "content": law_results['documents'][0][i],
                "metadata": law_results['metadatas'][0][i],
                "similarity": 1 - law_results['distances'][0][i]
            }
            processed_laws.append(law)            
        # 过滤低于阈值的法律法规
        processed_laws = [law for law in processed_laws if law["similarity"] >= config.SIMILARITY_THRESHOLD]
        processed_laws.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 处理案例
        processed_case = []
        for i in range(len(case_results['ids'][0])):
            case = {
                "id": case_results['ids'][0][i],
                "content": case_results['documents'][0][i],
                "metadata": case_results['metadatas'][0][i],
                "similarity": 1 - case_results['distances'][0][i],
            }
            processed_case.append(case)
        # 过滤低于阈值的法律案例
        processed_case = [case for case in processed_case if case["similarity"] >= config.SIMILARITY_THRESHOLD]
        processed_case.sort(key=lambda x: x["similarity"], reverse=True)
        

        # 选择最匹配的合同和备用合同
        best_contract = processed_contracts[0] if processed_contracts else None
        alternative_contracts = processed_contracts[1:4] if len(processed_contracts) > 1 else []
        
        return {
            "best_contract": best_contract,
            "alternative_contracts": alternative_contracts,
            "relevant_laws": processed_laws,
            "relevant_case": processed_case,
            "query": user_query,
            "filters": user_filters
        }
    
    def backup_database(self, backup_name: str = None):
        """
        备份数据库到指定目录
        
        Args:
            backup_name: 备份名称，默认为时间戳
        """
        if backup_name is None:
            backup_name = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = os.path.join(self.persist_directory, backup_name)
        
        # 复制整个数据库目录
        if os.path.exists(self.persist_directory):
            shutil.copytree(self.persist_directory, backup_path, 
                          ignore=shutil.ignore_patterns('backups', '*.tmp'))
            
            # 记录备份信息
            info_file = os.path.join(backup_path, "backup_info.json")
            backup_info = {
                "backup_time": datetime.datetime.now().isoformat(),
                "source_path": self.persist_directory,
                "collection_count": len(self.client.list_collections()),
                "backup_name": backup_name
            }
            
            import json
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)
            
            return backup_path
        return None
    
    def restore_database(self, backup_name: str):
        """
        从备份恢复数据库
        
        Args:
            backup_name: 备份名称或路径
        """
        backup_path = os.path.join(self.persist_directory, backup_name)
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"备份不存在: {backup_path}")
        
        # 停止当前客户端
        del self.client
        
        # 清空当前数据库目录
        if os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory)
        
        # 恢复备份
        shutil.copytree(backup_path, self.persist_directory)
        
        # 重新初始化客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 重新获取集合
        self.contract_collection = self.client.get_collection(name=config.COLLECTION_CONTRACTS)
        self.law_collection = self.client.get_collection(name=config.COLLECTION_LAWS)
        self.case_collection = self.client.get_collection(name=config.COLLECTION_CASE)
        
        print(f"✅ 数据库已从备份恢复: {backup_name}")