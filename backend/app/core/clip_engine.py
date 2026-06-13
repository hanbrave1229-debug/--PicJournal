"""
CLIP-ViT-B/32 ONNX 离线语义向量引擎
=====================================
模型首次使用时自动从 HuggingFace Hub 下载（~340 MB），之后完全离线。
本模块只依赖已安装的 onnxruntime、Pillow、numpy；无需 PyTorch。

Public API
----------
    is_available() -> bool
    encode_image(image_path: str) -> np.ndarray  # (512,) float32, L2-normed
    encode_text(text: str) -> np.ndarray          # (512,) float32, L2-normed
    cosine_sim(a, b) -> float
"""
from __future__ import annotations

import logging
import os
import re
import struct
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MODEL_REPO   = "Xenova/clip-vit-base-patch32"
_MODELS_DIR  = Path(os.getenv("MODELS_DIR", "/data/models/clip"))

# CLIP image normalization params (ImageNet mean/std, CLIP convention)
_MEAN = np.array([0.48145466, 0.4578275,  0.40821073], dtype=np.float32)
_STD  = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
_IMG_SIZE = 224

# ── Lazy globals ────────────────────────────────────────────────────────────────
_visual_session  = None
_textual_session = None
_tokenizer: Optional["CLIPTokenizer"] = None
_available: Optional[bool] = None


def is_available() -> bool:
    """True when ONNX models are downloaded and onnxruntime loads them."""
    global _available
    if _available is not None:
        return _available
    try:
        _load_models()
        _available = True
    except Exception as exc:
        logger.warning("CLIP not available: %s", exc)
        _available = False
    return _available


def encode_image(image_path: str) -> np.ndarray:
    """Return L2-normalised 512-dim CLIP image embedding."""
    _load_models()
    pixel_values = _preprocess_image(image_path)               # (1,3,224,224)
    outputs = _visual_session.run(None, {"pixel_values": pixel_values})
    emb = outputs[0].astype(np.float32).flatten()              # (512,)
    return _l2_norm(emb)


def encode_text(text: str) -> np.ndarray:
    """Return L2-normalised 512-dim CLIP text embedding."""
    _load_models()
    input_ids = _tokenizer.encode(text)                        # (1, 77)
    outputs = _textual_session.run(None, {"input_ids": input_ids})
    emb = outputs[0].astype(np.float32).flatten()              # (512,)
    return _l2_norm(emb)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Dot product of two L2-normed vectors = cosine similarity."""
    return float(np.dot(a, b))


# ── Internal: model loading ────────────────────────────────────────────────────

def _load_models() -> None:
    global _visual_session, _textual_session, _tokenizer

    if _visual_session is not None:
        return  # already loaded

    visual_path  = _MODELS_DIR / "visual.onnx"
    textual_path = _MODELS_DIR / "textual.onnx"
    vocab_path   = _MODELS_DIR / "vocab.json"
    merges_path  = _MODELS_DIR / "merges.txt"

    # ── Download if needed ─────────────────────────────────────────────────────
    if not (visual_path.exists() and textual_path.exists()):
        _download_models(visual_path, textual_path, vocab_path, merges_path)

    # ── Load ONNX sessions ────────────────────────────────────────────────────
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 2
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    _visual_session  = ort.InferenceSession(str(visual_path),  opts)
    _textual_session = ort.InferenceSession(str(textual_path), opts)
    _tokenizer       = CLIPTokenizer(str(vocab_path), str(merges_path))
    logger.info("CLIP ONNX models loaded from %s", _MODELS_DIR)


def _download_models(visual_path: Path, textual_path: Path,
                     vocab_path: Path, merges_path: Path) -> None:
    """Download CLIP ONNX files from HuggingFace Hub."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub not installed; cannot auto-download CLIP models. "
            "pip install huggingface-hub"
        ) from exc

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading CLIP ONNX models from HuggingFace Hub (%s)…", MODEL_REPO)

    files = {
        "onnx/visual.onnx":  visual_path,
        "onnx/textual.onnx": textual_path,
        "tokenizer/vocab.json": vocab_path,
        "tokenizer/merges.txt": merges_path,
    }
    for repo_file, local_path in files.items():
        if not local_path.exists():
            dl = hf_hub_download(repo_id=MODEL_REPO, filename=repo_file, local_dir=str(_MODELS_DIR))
            Path(dl).rename(local_path) if Path(dl) != local_path else None
    logger.info("CLIP models ready at %s", _MODELS_DIR)


# ── Internal: image preprocessing ─────────────────────────────────────────────

def _preprocess_image(image_path: str) -> np.ndarray:
    """Load → resize 224×224 → CLIP normalize → (1, 3, 224, 224) float32."""
    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    # Resize shortest edge to 224, then center-crop
    w, h = img.size
    scale = _IMG_SIZE / min(w, h)
    nw, nh = max(_IMG_SIZE, int(w * scale)), max(_IMG_SIZE, int(h * scale))
    img = img.resize((nw, nh), Image.BICUBIC)
    left = (nw - _IMG_SIZE) // 2
    top  = (nh - _IMG_SIZE) // 2
    img  = img.crop((left, top, left + _IMG_SIZE, top + _IMG_SIZE))

    arr = np.array(img, dtype=np.float32) / 255.0             # (224,224,3)
    arr = (arr - _MEAN) / _STD                                 # normalize
    arr = arr.transpose(2, 0, 1)[np.newaxis]                   # (1,3,224,224)
    return arr.astype(np.float32)


# ── Internal: L2 normalisation ─────────────────────────────────────────────────

def _l2_norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / (n + 1e-9)


# ── Minimal CLIP BPE Tokenizer ─────────────────────────────────────────────────

class CLIPTokenizer:
    """
    Pure-Python CLIP BPE tokenizer.
    Ported from openai/CLIP (MIT licence).
    Vocab file: tokenizer/vocab.json
    Merges file: tokenizer/merges.txt
    """
    SOT_TOKEN = 49406
    EOT_TOKEN = 49407
    CONTEXT_LENGTH = 77

    def __init__(self, vocab_path: str, merges_path: str) -> None:
        import json
        with open(vocab_path, encoding="utf-8") as f:
            self.encoder: dict[str, int] = json.load(f)
        self.decoder = {v: k for k, v in self.encoder.items()}

        with open(merges_path, encoding="utf-8") as f:
            merges = [tuple(line.split()) for line in f.read().splitlines()[1:]
                      if line and not line.startswith("#")]
        self.bpe_ranks = {pair: i for i, pair in enumerate(merges)}
        self._cache: dict[str, tuple[str, ...]] = {}
        self._pat = re.compile(
            r"""'s|'t|'re|'ve|'m|'ll|'d|[\p{L}]+|[\p{N}]|[^\s\p{L}\p{N}]+""",
            re.IGNORECASE,
        ) if hasattr(re, "findall") else None

    # Simple fallback tokeniser for tokens
    def _tokenize_word(self, text: str) -> list[str]:
        return list(text)   # character-level fallback (overridden by BPE below)

    def _bytes_to_unicode(self) -> dict[int, str]:
        bs = list(range(ord("!"), ord("~") + 1)) + \
             list(range(ord("¡"), ord("¬") + 1)) + \
             list(range(ord("®"), ord("ÿ") + 1))
        cs = list(bs)
        n = 0
        for b in range(2**8):
            if b not in bs:
                bs.append(b)
                cs.append(2**8 + n)
                n += 1
        return {b: chr(c) for b, c in zip(bs, cs)}

    @lru_cache(maxsize=None)
    def _byte_encoder(self) -> dict[int, str]:
        return self._bytes_to_unicode()

    def _get_pairs(self, word: tuple[str, ...]) -> set[tuple[str, str]]:
        return {(word[i], word[i + 1]) for i in range(len(word) - 1)}

    def _bpe(self, token: str) -> tuple[str, ...]:
        if token in self._cache:
            return self._cache[token]
        word = tuple(token)
        pairs = self._get_pairs(word)
        if not pairs:
            self._cache[token] = word
            return word
        while True:
            bigram = min(pairs, key=lambda p: self.bpe_ranks.get(p, float("inf")))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word: list[str] = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                except ValueError:
                    new_word.extend(word[i:])
                    break
                new_word.extend(word[i:j])
                i = j
                if i < len(word) - 1 and word[i + 1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = tuple(new_word)
            if len(word) == 1:
                break
            pairs = self._get_pairs(word)
        self._cache[token] = word
        return word

    def encode(self, text: str) -> np.ndarray:
        """Tokenise text and return int32 array of shape (1, 77)."""
        be = self._byte_encoder()
        # Simple word-level split (no regex dependency)
        text = unicodedata.normalize("NFC", text.lower().strip())
        # Split on whitespace/punctuation boundaries
        tokens: list[int] = []
        for word in re.split(r'(\s+)', text):
            word = word.strip()
            if not word:
                continue
            bpe_word = "".join(be.get(b, chr(b)) for b in word.encode("utf-8"))
            for subtoken in self._bpe(bpe_word):
                idx = self.encoder.get(subtoken)
                if idx is not None:
                    tokens.append(idx)
        # Truncate & pad to CONTEXT_LENGTH
        tokens = tokens[:self.CONTEXT_LENGTH - 2]
        tokens = [self.SOT_TOKEN] + tokens + [self.EOT_TOKEN]
        tokens += [0] * (self.CONTEXT_LENGTH - len(tokens))
        return np.array([tokens], dtype=np.int64)
