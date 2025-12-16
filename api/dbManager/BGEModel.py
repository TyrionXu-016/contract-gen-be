"""
向量化模块 - 使用BGE模型
"""
import config
import torch
import numpy as np
from typing import List, Union
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer

class BGEModel:
    """BGE模型封装类"""
    
    def __init__(self, model_name: str = None, device: str = None):
        """
        初始化BGE模型
        
        Args:
            model_name: 模型名称
            device: 设备 (cuda/cpu)
        """
        self.model_name = model_name or config.BGE_MODEL_NAME
        
        # 自动选择设备
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"正在加载BGE模型: {self.model_name} 到设备: {self.device}")
        
        # 加载模型和tokenizer
        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.use_sentence_transformer = True
        except:
            # 使用transformers方式加载
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.use_sentence_transformer = False
            
        self.model.eval()
        
    def encode(self, texts: Union[str, List[str]], 
               normalize: bool = None) -> np.ndarray:
        """
        编码文本为向量
        
        Args:
            texts: 文本或文本列表
            normalize: 是否归一化
            
        Returns:
            向量数组
        """
        normalize = normalize if normalize is not None else config.NORMALIZE_EMBEDDINGS
        is_single_text = isinstance(texts, str)
        
        if is_single_text:
            texts = [texts]
            
        if self.use_sentence_transformer:
            # 使用sentence-transformers接口
            embeddings = self.model.encode(
                texts, 
                normalize_embeddings=normalize,
                convert_to_numpy=True
            )
        else:
            # 使用transformers接口
            encoded_input = self.tokenizer(
                texts, 
                padding=True, 
                truncation=True, 
                max_length=512, 
                return_tensors='pt'
            ).to(self.device)
            
            with torch.no_grad():
                model_output = self.model(**encoded_input)
                # 使用[CLS] token作为句子表示
                embeddings = model_output[0][:, 0]
                
            if normalize:
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                
            embeddings = embeddings.cpu().numpy()
        
        if is_single_text:
            if isinstance(embeddings, np.ndarray):
                return np.squeeze(embeddings, axis=0)
            if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], (list, np.ndarray)):
                return embeddings[0]
            return embeddings
        
        return embeddings
    
    def encode_batch(self, texts: List[str], batch_size: int = 32, **kwargs):
        """
        批量编码文本
        
        Args:
            texts: 文本列表
            batch_size: 批大小
            
        Returns:
            向量列表
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self.encode(batch, **kwargs)
            all_embeddings.append(embeddings)
            
        return np.vstack(all_embeddings)
    
    def get_embedding_dim(self) -> int:
        """获取向量维度"""
        if self.use_sentence_transformer:
            return self.model.get_sentence_embedding_dimension()
        else:
            # BGE-large-zh的维度是1024
            return config.EMBEDDING_DIM