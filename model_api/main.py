from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware  # CORS支持
import os
import openai
from dotenv import load_dotenv #用于加载env文件
from pathlib import Path # 使用 pathlib 处理路径
from pydantic import BaseModel # 用于更规范的请求体定义
import json
from .knowledge_retriever import retrieve_knowledge_from_kb

#用来暴露给后端的接口
app = FastAPI()

# 添加CORS中间件（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许哪些源访问
    allow_credentials=True, #是否允许携带cookie等凭证
    allow_methods=["*"], # 允许哪些HTTP方法
    allow_headers=["*"], # 允许哪些HTTP头部
)

#配置豆包AI客户端
load_dotenv()
api_key = os.getenv("VITE_HUOSHAN_API_KEY")
client = openai.OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=api_key,
)
model_name = "doubao-seed-1-6-251015"

# 用户请求体规范
class GenerateRequest(BaseModel):
    prompt: str  # 用户的原始提示
    contract_type: str  # 合同类型
    first_party: str = "甲方"  # 甲方名称，默认值
    second_party: str = "乙方"  # 乙方名称，默认值
    cooperation_purpose: str = None  # 合作目的
    Core_scenario: str = None #合同核心场景
    max_new_tokens: int = 5000
    temperature: float = 0.7
    use_new_knowledge_base: bool = True

#提前加载系统 prompt 的内容
base_dir = Path(__file__).parent.parent # 获取主目录
system_prompt_path = base_dir / "promptContract.txt"
system_prompt_content = ""
try:
    with open(system_prompt_path, 'r', encoding='utf-8') as f:
        system_prompt_content = f.read()
except FileNotFoundError:
    print(f"Error: System prompt file not found at {system_prompt_path}")
    system_prompt_content = "你是一个合同生成助手。请按正式合同格式、条款编号清晰地输出完整合同文本。" # Fallback
except Exception as e:
    print(f"Error reading system prompt file: {e}")
    system_prompt_content = "你是一个合同生成助手。请按正式合同格式、条款编号清晰地输出完整合同文本。" # Fallback

async def prompt_insert(request: GenerateRequest,template = system_prompt_content) -> str:

    # 默认值，如果未检索到信息或不使用知识库
    default_laws = "暂无检索到最新法律法规"
    default_cases = "暂无检索到相关典型案例"
    default_standards = "暂无检索到相关国标行规"
    default_templates = "暂无检索到相关合同范本"

    laws_str = default_laws
    cases_str = default_cases
    standards_str = default_standards
    templates_str = default_templates

    retrieve_knowledge = await retrieve_knowledge_from_kb(request.prompt, request.contract_type, request.cooperation_purpose,request.Core_scenario) if request.use_new_knowledge_base else None
    if retrieve_knowledge:
        # 将列表转换为字符串，每个条目一行，如果列表为空则使用默认值
        laws_str = " ".join(retrieve_knowledge.get("latest_laws", [])) or default_laws
        cases_str = " ".join(retrieve_knowledge.get("case_studies", [])) or default_cases 
        standards_str = " ".join(retrieve_knowledge.get("standards", [])) or default_standards
        templates_str = " ".join(retrieve_knowledge.get("templates", [])) or default_templates

    # 没有检索信息设为空或默认值
    template = template.replace("{最新法律法规}", laws_str)
    template = template.replace("{最新合同纠纷案}", cases_str)
    template = template.replace("{最新国标行规}", standards_str)
    template = template.replace("{最新合同范本}", templates_str)

    system_prompt_content = template.format(
        合同类型=request.contract_type,
        甲方=request.first_party,
        乙方=request.second_party,
        合作目的 = request.cooperation_purpose if request.cooperation_purpose is not None else "",
        合同核心场景 = request.Core_scenario if request.Core_scenario is not None else ""      
    )
    return system_prompt_content


@app.post("/generate-contract")
async def generate_contract(request: GenerateRequest):
    system_prompt_content = await prompt_insert(request)
    async def generate_chunks():
        full_content = ""  # 用于累积完整内容
        try:
            messages=[
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": request.prompt}
            ]
            print(messages)

            # 开启流式输出
            stream_response = client.chat.completions.create(
                model = model_name,
                messages=messages,
                max_tokens=request.max_new_tokens,
                temperature=request.temperature,
                stream=True,
            )

            for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    # 返回每个生成的文本块（SSE格式）
                    yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
            
            # 发送结束标记
            yield f"data: {json.dumps({'done': True, 'total_length': len(full_content)}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_msg = f"Error during streaming generation: {str(e)}"
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_chunks(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 防止Nginx缓冲
        }
    )