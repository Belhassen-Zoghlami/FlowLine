import functools
import logging

import numpy as np
import onnxruntime as ort
from django.conf import settings
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer

from .models import FaultCategory

logger = logging.getLogger(__name__)

MAX_LENGTH = 256
ENTAILMENT_INDEX = 1
PREMISE_PREFIX = "CI error log line: "

CATEGORY_PROMPTS = (
    (
        FaultCategory.IMPORT_ERROR,
        (
            "The error message states that a module cannot be found.",
            "The error message states that a required module cannot be imported.",
            "The error message states that a module is missing.",
        ),
    ),
    (
        FaultCategory.DEPENDENCY,
        (
            "The error message states that a package could not be found.",
            "The error message states that a dependency is missing.",
            "The error message states that the package manager returned a 404 error.",
            "The error message states that a dependency version could not be resolved.",
            "The error message states that there is a dependency resolution error.",
        ),
    ),
    (
        FaultCategory.SYNTAX,
        (
            "The error message states that the code has invalid syntax.",
            "The error message states that there is a syntax error.",
            "The error message states that an unexpected token was found.",
            "The error message states that a token is invalid.",
        ),
    ),
    (
        FaultCategory.TEST_FAILURE,
        (
            "The error message states that an assertion failed.",
            "The error message states that a test assertion failed.",
            "The error message states that a test failed.",
            "The error message states that expected and actual values differ.",
            "The log line throws an assertion error.",
            "The log line contains an assertion error.",

        ),
    ),
    (
        FaultCategory.TIMEOUT,
        (
            "The error message states that the operation timed out.",
            "The error message states that a deadline was exceeded.",
            "The error message states that the process took too long.",
            "The error message states that the operation exceeded its time limit.",
            "The log line states that this is a timeout scenario.",
            "The log line contains a timeout.",
        ),
    ),
    (
        FaultCategory.BUILD,
        (
            "The error message states that the build failed.",
            "The error message states that compilation failed.",
            "The error message states that the build tool rejected the code.",
            "The error message states that the compiler reported a type error.",
            "The log line contains a TypeScript error code.",
        ),
    ),
)


@functools.lru_cache(maxsize=1)
def _runtime():
    cache_dir = str(settings.MODEL_CACHE_DIR)
    model_path = hf_hub_download(
        repo_id=settings.CLASSIFICATION_MODEL,
        filename=settings.CLASSIFICATION_MODEL_FILE,
        cache_dir=cache_dir,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        settings.CLASSIFICATION_MODEL,
        cache_dir=cache_dir,
    )
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    input_names = {item.name for item in session.get_inputs()}
    return tokenizer, session, input_names


def _as_text(text):
    if isinstance(text, (bytes, bytearray)):
        return text.decode("utf-8", "replace")
    return text or ""


def _softmax(logits):
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=1, keepdims=True)


def _model_inputs(encoded, input_names):
    inputs = {}
    for name in input_names:
        if name in encoded:
            inputs[name] = encoded[name].astype(np.int64)
        elif name == "token_type_ids":
            inputs[name] = np.zeros_like(encoded["input_ids"], dtype=np.int64)
    return inputs


@functools.lru_cache(maxsize=2048)
def _classify_cached(text):
    tokenizer, session, input_names = _runtime()

    candidates = []
    hypotheses = []

    for category, prompts in CATEGORY_PROMPTS:
        for prompt in prompts:
            candidates.append(category)
            hypotheses.append(prompt)

    premise = f"{PREMISE_PREFIX}{text}"
    encoded = tokenizer(
        [premise] * len(hypotheses),
        hypotheses,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="np",
    )

    logits = session.run(None, _model_inputs(encoded, input_names))[0]
    probabilities = _softmax(np.asarray(logits, dtype=np.float32))
    scores = probabilities[:, ENTAILMENT_INDEX]

    best_scores = {}

    for category, score in zip(candidates, scores):
        score = float(score)
        if category not in best_scores or score > best_scores[category]:
            best_scores[category] = score

    best_category = max(best_scores, key=best_scores.get)

    if best_scores[best_category] < settings.CLASSIFICATION_THRESHOLD:
        return FaultCategory.UNKNOWN

    return best_category


def classify_signature(signature):
    text = _as_text(signature).strip()
    if not text:
        return FaultCategory.UNKNOWN

    try:
        return _classify_cached(text)
    except Exception:
        logger.exception("classification failed")
        return FaultCategory.UNKNOWN