# Evaluation

这里保存版本化 RAG 评测集、执行器和结果摘要。评测数据不得包含生产用户的私有内容。

## 数据格式

每行一个 JSON：

```json
{
  "id": "project-code",
  "question": "项目验收代号是什么？",
  "knowledge_base_id": "可选；不写时使用命令行默认值",
  "expected_document_ids": [],
  "expected_document_titles": ["项目记录"],
  "reference_answer": "可选参考答案"
}
```

至少填写 `expected_document_ids` 或 `expected_document_titles` 之一。正式评测集应使用
专门构建的公开或合成知识库，不直接复制生产用户资料。

## 执行

```bash
cd api
uv run python ../eval/run_rag_eval.py \
  --dataset ../eval/datasets/example.jsonl \
  --user-id <评测用户ID> \
  --knowledge-base-id <评测知识库ID> \
  --top-k 6 \
  --output ../eval/results/v0.9.json
```

输出包含：

- Recall@K
- MRR
- 引用文档命中率
- 每个案例的命中明细

`app.evaluation.rag.evaluate_answer_citations` 另外检查回答引用编号是否越界，以及无来源
时是否出现伪造编号。这里不使用模型充当裁判，避免评测自身产生不透明波动。
