import functools
import numpy as np 
import onnxruntime as ort
from django.conf import settings
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer
from django.db import transaction
from .models import Problem

MAX_LENGTH =256

@functools.lru_cache(maxsize=1)
def _runtime():
    cache_dir= str(settings.MODEL_CACHE_DIR)
    model_path = hf_hub_download(
        repo_id=settings.EMBEDDING_MODEL,
        filename=settings.EMBEDDING_MODEL_FILE,
        cache_dir=cache_dir
    )
    tokenizer = AutoTokenizer.from_pretrained(
        settings.EMBEDDING_MODEL,
        cache_dir=cache_dir
    )
    session=ort.InferenceSession(
        model_path,
        providers=["CPUExecutionProvider"]
    )
    input_names = { item.name for item in session.get_inputs()}
    output_names = [item.name for item in session.get_outputs()]
    hidden_index = (
        output_names.index("last_hidden_state")
        if "last_hidden_state" in output_names
        else 0
    )
    return tokenizer, session,input_names, hidden_index

def _as_text(text):
    return text.decode("utf-8", "replace") if isinstance(text, bytes) else (text or "")

@functools.lru_cache(maxsize=2048)
def embed_text(text):
    tokenizer,session, input_names,hidden_index=_runtime()
    encoded=tokenizer(
        [_as_text(text)],
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="np"
    )
    inputs={
        name:encoded[name].astype(np.int64)
        for name in input_names
        if name in encoded
    }
    hidden=session.run(None, inputs)[hidden_index][0]
    mask=encoded["attention_mask"][0].astype(np.float32)
    vector=(hidden*mask[:,None]).sum(axis=0)/max(float(mask.sum()),1.0)
    norm=float(np.linalg.norm(vector))
    if norm ==0.0:
        return np.zeros_like(vector,dtype=np.float32)
    return (vector/norm).astype(np.float32)

def cosine_sim(left,right):
    left =np.asarray(left,dtype=np.float32)
    right=np.asarray(right,dtype=np.float32)
    denominator=float(np.linalg.norm(left)*np.linalg.norm(right))
    return float(np.dot(left,right)/denominator) if denominator else 0.0

similarity=cosine_sim

def _decrement_prob(problem):
    problem.num_occurrences-=1
    if problem.num_occurrences <=0:
        problem.delete()
    else:
        problem.save(update_fields=["num_occurrences"])

@transaction.atomic
def group_run(run,signature):
    signature=(signature or "").strip()
    current=run.problem if run.problem_id else None
    if not signature:
        if current is not None:
            run.problem=None
            run.save(update_fields=["problem"])
            _decrement_prob(current)
        return None
    if current is not None and current.signature==signature:
        return current
    vector=embed_text(signature)
    candidates= [
        (float(np.dot(vector,embed_text(problem.signature))),problem)
        for problem in run.repository.problems.all()
    ]
    score,problem=max(candidates,default=(0.0, None),key=lambda item:item[0])
    if problem is None or score < settings.PROBLEM_SIMILARITY_THRESHOLD:
        problem=Problem.objects.create(
            repository=run.repository,
            signature=signature
        )
    elif current is None or problem.pk !=current.pk:
        problem.num_occurrences+=1
        problem.save(update_fields=["num_occurrences","last_occ"])
    if current is not None and current.pk !=problem.pk:
        _decrement_prob(current)

    run.problem=problem
    run.save(update_fields=["problem"])
    return problem