# GPU Service Consolidation Plan

## Overview

This document outlines the plan to consolidate all GPU-dependent capabilities from the startupp.chat application into a single FastAPI service that can run on a dedicated GPU server.

---

## Current GPU-Dependent Capabilities

### 1. TranscriptionService (Whisper)

| Attribute | Value |
|-----------|-------|
| **Location** | `services/transcription_service.py` |
| **Framework** | PyTorch + faster-whisper |
| **GPU Required** | Yes (configurable) |
| **Models** | OpenAI Whisper (tiny, base, small, medium, large) |
| **Device** | CUDA |
| **Compute Type** | float16 |

**Functionality:**
- Transcribes audio/video files to text
- Configurable model sizes for speed/accuracy tradeoff
- Beam search for improved transcription accuracy

---

### 2. PersonaTranscriptionService (WhisperX + Speaker Diarization)

| Attribute | Value |
|-----------|-------|
| **Location** | `services/transcription_service.py` |
| **Framework** | PyTorch + WhisperX + PyAnnote |
| **GPU Required** | **MANDATORY** (fails without CUDA) |
| **Models** | Whisper + pyannote/speaker-diarization-3.1 |
| **Device** | CUDA (enforced) |
| **Compute Type** | float16 |

**Functionality:**
- Advanced transcription with speaker identification
- Speaker diarization (identifies who is speaking)
- Timestamp alignment per language
- Requires HuggingFace token for pyannote models

**GPU Operations:**
1. WhisperX model loading
2. Audio transcription (batch processing)
3. Timestamp alignment
4. Speaker diarization pipeline
5. Speaker assignment to segments

---

### 3. OllamaAnalysisService (LLM Inference)

| Attribute | Value |
|-----------|-------|
| **Location** | `services/analysis_service.py` |
| **Framework** | Ollama |
| **GPU Required** | Yes (via Ollama server) |
| **Models** | llama3.2, gpt-oss:20b |
| **Endpoint** | http://nvda:30434 |

**Functionality:**
- Transcription analysis and summarization
- LinkedIn post generation
- Bluesky post generation with validation loop
- Post validation against constraints

---

### 4. Embedding Generation (Ollama)

| Attribute | Value |
|-----------|-------|
| **Location** | `test_ollama_embed.py` |
| **Framework** | Ollama |
| **GPU Required** | Yes (via Ollama server) |
| **Model** | mxbai-embed-large |
| **Vector Dimension** | 1024 |

**Functionality:**
- Generates text embeddings for vector storage
- Stores in Qdrant vector database

---

## Proposed FastAPI GPU Service Architecture

### Service Name: `startupp-gpu-service`

```
┌─────────────────────────────────────────────────────────────────┐
│                    startupp-gpu-service                         │
│                      (FastAPI + GPU)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  /transcribe     │  │  /transcribe/    │  │  /embeddings │  │
│  │                  │  │  diarize         │  │              │  │
│  │  Whisper         │  │  WhisperX +      │  │  mxbai-embed │  │
│  │  (faster-whisper)│  │  PyAnnote        │  │  -large      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  /analyze        │  │  /generate/      │  │  /health     │  │
│  │                  │  │  linkedin        │  │              │  │
│  │  LLM Analysis    │  │  /generate/      │  │  GPU Status  │  │
│  │                  │  │  bluesky         │  │  Model Info  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   GPU Resource Manager                   │   │
│  │  - Model caching & lazy loading                         │   │
│  │  - VRAM management                                       │   │
│  │  - Request queuing                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Design

### 1. Health & Status

```
GET /health
```
Returns GPU availability, loaded models, VRAM usage.

```json
{
  "status": "healthy",
  "gpu": {
    "available": true,
    "device_count": 1,
    "device_name": "NVIDIA RTX 4090",
    "vram_total_gb": 24.0,
    "vram_used_gb": 8.5,
    "vram_free_gb": 15.5
  },
  "models_loaded": {
    "whisper": "medium",
    "whisperx": true,
    "diarization": true,
    "embeddings": true
  }
}
```

---

### 2. Transcription Endpoints

#### Basic Transcription
```
POST /transcribe
Content-Type: multipart/form-data
```

**Request:**
- `file`: Audio/video file
- `model_size`: tiny | base | small | medium | large (default: medium)
- `language`: Optional language code

**Response:**
```json
{
  "text": "Full transcription text...",
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, welcome to the show."
    }
  ],
  "language": "en",
  "duration": 120.5,
  "processing_time": 15.2
}
```

#### Transcription with Speaker Diarization
```
POST /transcribe/diarize
Content-Type: multipart/form-data
```

**Request:**
- `file`: Audio/video file
- `model_size`: tiny | base | small | medium | large (default: medium)
- `min_speakers`: Minimum expected speakers (optional)
- `max_speakers`: Maximum expected speakers (optional)

**Response:**
```json
{
  "text": "Full transcription text...",
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, welcome to the show.",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 2.5,
      "end": 5.0,
      "text": "Thanks for having me!",
      "speaker": "SPEAKER_01"
    }
  ],
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "language": "en",
  "duration": 120.5,
  "processing_time": 25.3
}
```

---

### 3. Embedding Endpoints

```
POST /embeddings
Content-Type: application/json
```

**Request:**
```json
{
  "texts": ["First text to embed", "Second text to embed"],
  "model": "mxbai-embed-large"
}
```

**Response:**
```json
{
  "embeddings": [
    [0.123, -0.456, ...],
    [0.789, -0.012, ...]
  ],
  "model": "mxbai-embed-large",
  "dimension": 1024,
  "processing_time": 0.45
}
```

---

### 4. LLM Analysis Endpoints

#### Transcription Analysis
```
POST /analyze
Content-Type: application/json
```

**Request:**
```json
{
  "transcription": "Full transcription text...",
  "analysis_type": "summary",
  "model": "llama3.2",
  "temperature": 0.7
}
```

**Response:**
```json
{
  "analysis": "Summary of the transcription...",
  "model": "llama3.2",
  "tokens_used": 1500,
  "processing_time": 3.2
}
```

#### Social Post Generation
```
POST /generate/linkedin
POST /generate/bluesky
Content-Type: application/json
```

**Request:**
```json
{
  "transcription": "Full transcription text...",
  "analysis": "Analysis summary...",
  "model": "llama3.2",
  "temperature": 0.8
}
```

**Response:**
```json
{
  "post": "Generated social media post...",
  "hashtags": ["#AI", "#Tech"],
  "character_count": 250,
  "valid": true,
  "processing_time": 2.1
}
```

---

## Project Structure

```
startupp-gpu-service/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py       # Health check endpoints
│   │   │   ├── transcription.py # Transcription endpoints
│   │   │   ├── embeddings.py   # Embedding endpoints
│   │   │   └── analysis.py     # LLM analysis endpoints
│   │   └── deps.py             # Dependency injection
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── gpu_manager.py      # GPU resource management
│   │   └── model_cache.py      # Model caching & loading
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transcription.py    # Whisper transcription
│   │   ├── diarization.py      # Speaker diarization
│   │   ├── embeddings.py       # Embedding generation
│   │   └── llm.py              # LLM inference
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── transcription.py    # Pydantic models
│   │   ├── embeddings.py
│   │   └── analysis.py
│   │
│   └── prompts/
│       ├── analysis-prompt.txt
│       ├── linkedin-prompt.txt
│       ├── bluesky-prompt.txt
│       └── bluesky-validation-prompt.txt
│
└── tests/
    ├── __init__.py
    ├── test_transcription.py
    ├── test_embeddings.py
    └── test_analysis.py
```

---

## Dependencies

```toml
[project]
name = "startupp-gpu-service"
version = "1.0.0"
requires-python = ">=3.11"

dependencies = [
    # FastAPI & Web
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "python-multipart>=0.0.12",

    # GPU/ML - Transcription
    "faster-whisper>=1.2.0",
    "whisperx>=3.4.2",
    "torch>=2.0.0",
    "torchaudio>=2.0.0",

    # GPU/ML - Speaker Diarization
    "pyannote-audio>=3.1.0",
    "transformers>=4.55.4",

    # GPU/ML - LLM & Embeddings
    "ollama>=0.3.0",

    # Utilities
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.0.0",
]
```

---

## Docker Configuration

### Dockerfile

```dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04

WORKDIR /app

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  gpu-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - WHISPER_MODEL_SIZE=medium
      - WHISPER_COMPUTE_TYPE=float16
      - HF_TOKEN=${HF_TOKEN}
      - OLLAMA_URL=http://ollama:11434
    volumes:
      - ./models:/app/models
      - huggingface-cache:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  huggingface-cache:
  ollama-data:
```

---

## Environment Variables

```bash
# GPU Configuration
CUDA_VISIBLE_DEVICES=0
CUDNN_DETERMINISTIC=1
CUDNN_BENCHMARK=0

# Whisper Configuration
WHISPER_MODEL_SIZE=medium
WHISPER_COMPUTE_TYPE=float16
WHISPER_DEVICE=cuda
WHISPER_BATCH_SIZE=16

# HuggingFace (for pyannote speaker diarization)
HF_TOKEN=hf_xxxxxxxxxxxxx

# Ollama Configuration
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large

# Service Configuration
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
WORKERS=1
```

---

## GPU Resource Management Strategy

### Model Loading Priority

1. **Whisper Model** - Load on startup (primary use case)
2. **WhisperX + Alignment Models** - Lazy load on first diarization request
3. **PyAnnote Diarization** - Lazy load (downloads ~1GB on first use)
4. **Ollama Models** - Managed by Ollama service

### VRAM Management

```python
class GPUResourceManager:
    """Manages GPU memory and model lifecycle."""

    def __init__(self, max_vram_usage_pct: float = 0.85):
        self.max_vram_usage_pct = max_vram_usage_pct
        self.loaded_models = {}

    def get_vram_usage(self) -> dict:
        """Returns current VRAM usage statistics."""
        return {
            "total": torch.cuda.get_device_properties(0).total_memory,
            "allocated": torch.cuda.memory_allocated(0),
            "cached": torch.cuda.memory_reserved(0),
            "free": torch.cuda.get_device_properties(0).total_memory
                    - torch.cuda.memory_allocated(0)
        }

    def clear_cache(self):
        """Clears CUDA cache and runs garbage collection."""
        torch.cuda.empty_cache()
        gc.collect()

    def should_unload_models(self) -> bool:
        """Check if VRAM usage exceeds threshold."""
        usage = self.get_vram_usage()
        return usage["allocated"] / usage["total"] > self.max_vram_usage_pct
```

### Request Queuing

For resource-intensive operations, implement request queuing:

```python
from asyncio import Queue, Semaphore

class TranscriptionQueue:
    """Manages concurrent transcription requests."""

    def __init__(self, max_concurrent: int = 2):
        self.semaphore = Semaphore(max_concurrent)
        self.queue = Queue()

    async def process(self, task):
        async with self.semaphore:
            return await task()
```

---

## Implementation Steps

### Phase 1: Core Service Setup
1. Create FastAPI application skeleton
2. Implement health check endpoints with GPU status
3. Set up configuration management with pydantic-settings
4. Implement GPU resource manager

### Phase 2: Transcription Services
1. Port TranscriptionService to new service
2. Port PersonaTranscriptionService with diarization
3. Add API endpoints for both services
4. Implement model caching and lazy loading

### Phase 3: LLM & Embeddings
1. Integrate Ollama client for LLM inference
2. Implement embedding generation endpoint
3. Port analysis prompts and generation logic
4. Add social media post generation endpoints

### Phase 4: Production Hardening
1. Add comprehensive error handling
2. Implement request validation
3. Add rate limiting
4. Configure logging and monitoring
5. Write tests

### Phase 5: Deployment
1. Create Docker configuration
2. Set up docker-compose with GPU support
3. Create deployment documentation
4. Configure health checks and monitoring

---

## Hardware Requirements

### Minimum Recommended
- **GPU**: NVIDIA RTX 3080 (10GB VRAM) or better
- **CPU**: 8 cores
- **RAM**: 32GB
- **Storage**: 100GB SSD (for models)

### Optimal Configuration
- **GPU**: NVIDIA RTX 4090 (24GB VRAM) or A100
- **CPU**: 16+ cores
- **RAM**: 64GB
- **Storage**: 500GB NVMe SSD

### VRAM Usage Estimates

| Model | VRAM Usage |
|-------|------------|
| Whisper medium (float16) | ~2.5 GB |
| Whisper large (float16) | ~5 GB |
| WhisperX alignment model | ~1 GB |
| PyAnnote diarization 3.1 | ~2 GB |
| Ollama llama3.2 (8B) | ~8 GB |
| mxbai-embed-large | ~1 GB |
| **Total (concurrent)** | **~15-20 GB** |

---

## Client Integration

The main startupp.chat application can integrate with this GPU service:

```python
from httpx import AsyncClient

class GPUServiceClient:
    """Client for startupp-gpu-service."""

    def __init__(self, base_url: str = "http://gpu-server:8000"):
        self.base_url = base_url
        self.client = AsyncClient(base_url=base_url, timeout=300.0)

    async def transcribe(self, audio_file: bytes, model_size: str = "medium"):
        """Transcribe audio file."""
        response = await self.client.post(
            "/transcribe",
            files={"file": audio_file},
            data={"model_size": model_size}
        )
        return response.json()

    async def transcribe_with_diarization(
        self,
        audio_file: bytes,
        min_speakers: int = None,
        max_speakers: int = None
    ):
        """Transcribe with speaker identification."""
        response = await self.client.post(
            "/transcribe/diarize",
            files={"file": audio_file},
            data={
                "min_speakers": min_speakers,
                "max_speakers": max_speakers
            }
        )
        return response.json()

    async def generate_embeddings(self, texts: list[str]):
        """Generate embeddings for texts."""
        response = await self.client.post(
            "/embeddings",
            json={"texts": texts}
        )
        return response.json()

    async def analyze(self, transcription: str):
        """Analyze transcription with LLM."""
        response = await self.client.post(
            "/analyze",
            json={"transcription": transcription}
        )
        return response.json()
```

---

## Monitoring & Observability

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
transcription_requests = Counter(
    "transcription_requests_total",
    "Total transcription requests",
    ["model_size", "with_diarization"]
)

transcription_duration = Histogram(
    "transcription_duration_seconds",
    "Transcription processing time",
    ["model_size"]
)

# GPU metrics
gpu_vram_used = Gauge(
    "gpu_vram_used_bytes",
    "GPU VRAM currently in use"
)

gpu_utilization = Gauge(
    "gpu_utilization_percent",
    "GPU utilization percentage"
)
```

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "transcription_complete",
    duration=15.2,
    model_size="medium",
    audio_duration=120.5,
    word_count=500,
    gpu_vram_used=2500000000
)
```

---

## Summary

This plan consolidates four GPU-dependent capabilities into a single FastAPI service:

1. **Whisper Transcription** - Basic speech-to-text
2. **WhisperX + Speaker Diarization** - Advanced transcription with speaker identification
3. **Ollama LLM Inference** - Text analysis and generation
4. **Embedding Generation** - Vector embeddings for semantic search

The unified service provides:
- Single deployment target for all GPU workloads
- Efficient GPU resource management
- Consistent API interface
- Docker-based deployment with NVIDIA GPU support
- Monitoring and observability out of the box

This architecture allows the main application to offload all GPU-intensive work to a dedicated server, enabling horizontal scaling and better resource utilization.
