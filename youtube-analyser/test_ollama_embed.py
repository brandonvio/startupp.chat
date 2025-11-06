#!/usr/bin/env python3
"""
Test script for Ollama embedding models.
Tests the mxbai-embed-large model using configuration from .env
"""

import os
import asyncio
import numpy as np
import json
import re
import hashlib
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from ollama import AsyncClient
from qdrant_client import QdrantClient
from qdrant_client.http import models
import time
import uuid


class OllamaEmbeddingTester:
    """Test class for Ollama embedding functionality."""

    def __init__(self, log_file: str = None, include_embeddings: bool = True):
        # Load environment variables
        load_dotenv()

        # Get Ollama configuration - use same URL pattern as analysis service
        self.ollama_url = os.getenv("OLLAMA_URL", "http://nvda:30434")
        self.model_name = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
        self.include_embeddings = include_embeddings

        # Get Qdrant configuration - MANDATORY
        self.qdrant_url = os.getenv("QDRANT_URL", "http://nvda:30333")
        self.collection_name = os.getenv("QDRANT_COLLECTION", "ollama_embeddings_test")

        # Set up log file
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = "_with_embeddings" if include_embeddings else "_stats_only"
            self.log_file = f"embedding_test_results_{timestamp}{suffix}.json"
        else:
            self.log_file = log_file

        # Initialize async client
        self.client = AsyncClient(host=self.ollama_url)

        # Initialize Qdrant client - MANDATORY
        try:
            # Parse URL to get host and port
            from urllib.parse import urlparse

            parsed_url = urlparse(self.qdrant_url)
            host = parsed_url.hostname
            port = parsed_url.port

            self.qdrant_client = QdrantClient(host=host, port=port, timeout=30)
            logger.info(f"Initialized Qdrant client at {host}:{port} with 30s timeout")

            # Test connectivity - MUST succeed
            if not self.test_qdrant_connectivity():
                raise Exception("Qdrant server is not accessible")

        except Exception as e:
            logger.error(f"❌ FATAL: Failed to initialize Qdrant client: {str(e)}")
            logger.error(
                f"❌ FATAL: Qdrant at {self.qdrant_url} is required for this test"
            )
            raise SystemExit(f"Qdrant initialization failed: {str(e)}")

        # Initialize test results log
        self.test_results = {
            "test_session": {
                "timestamp": datetime.now().isoformat(),
                "model_name": self.model_name,
                "ollama_url": self.ollama_url,
                "qdrant_url": self.qdrant_url,
                "collection_name": self.collection_name,
                "log_file": self.log_file,
            },
            "tests": [],
        }

        logger.info(
            f"Initialized Ollama embedding tester with {self.ollama_url} using model {self.model_name}"
        )
        logger.info(f"Results will be logged to: {self.log_file}")
        logger.info(
            f"✅ Qdrant storage ready: {self.qdrant_url} collection: {self.collection_name}"
        )

    def log_test_result(self, test_type: str, test_data: Dict[str, Any]) -> None:
        """Log test result to the results structure."""
        test_entry = {
            "test_type": test_type,
            "timestamp": datetime.now().isoformat(),
            "data": test_data,
        }
        self.test_results["tests"].append(test_entry)
        logger.info(f"Logged {test_type} test result")

    def save_results_to_file(self) -> None:
        """Save all test results to JSON file."""
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.test_results, f, indent=2, ensure_ascii=False)

            # Get file size for logging
            file_size = os.path.getsize(self.log_file)
            size_mb = file_size / (1024 * 1024)

            if self.include_embeddings and size_mb > 10:
                logger.warning(
                    f"Large log file created: {self.log_file} ({size_mb:.1f} MB)"
                )
                logger.info(
                    "Note: mxbai-embed-large produces 1024-dimension vectors (~4KB each as JSON)"
                )
            else:
                logger.success(
                    f"Test results saved to {self.log_file} ({size_mb:.1f} MB)"
                )

        except Exception as e:
            logger.error(f"Failed to save results to {self.log_file}: {str(e)}")

    def test_qdrant_connectivity(self) -> bool:
        """Test if Qdrant server is accessible."""
        try:
            collections_response = self.qdrant_client.get_collections()
            logger.success(
                f"✅ Qdrant connectivity test passed - found {len(collections_response.collections)} collections"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Qdrant connectivity test failed: {str(e)}")
            return False

    def setup_qdrant_collection(self, vector_dimension: int) -> bool:
        """Setup Qdrant collection for storing embeddings."""

        try:
            # Check if collection already exists
            collections = self.qdrant_client.get_collections()
            collection_exists = any(
                col.name == self.collection_name for col in collections.collections
            )

            if not collection_exists:
                # Create collection with proper vector configuration
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_dimension, distance=models.Distance.COSINE
                    ),
                )
                logger.success(
                    f"✅ Created new Qdrant collection: {self.collection_name}"
                )
            else:
                logger.info(
                    f"📦 Qdrant collection already exists: {self.collection_name}"
                )

            # Verify collection is accessible by getting info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            vector_count = collection_info.points_count or 0
            vector_size = collection_info.config.params.vectors.size
            logger.info(
                f"📊 Collection '{self.collection_name}': {vector_size}D vectors, {vector_count} points stored"
            )

            return True
        except Exception as e:
            logger.error(f"❌ FATAL: Failed to setup Qdrant collection: {str(e)}")
            raise SystemExit(f"Qdrant collection setup failed: {str(e)}")

    def generate_text_metadata(self, text: str) -> Dict[str, Any]:
        """Generate comprehensive metadata for a text."""
        # Basic text statistics
        word_count = len(text.split())
        sentence_count = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
        char_count = len(text)
        char_count_no_spaces = len(text.replace(" ", ""))

        # Text complexity metrics
        avg_word_length = (
            np.mean([len(word) for word in text.split()]) if word_count > 0 else 0
        )
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

        # Language patterns
        has_numbers = bool(re.search(r"\d", text))
        has_special_chars = bool(re.search(r"[^\w\s]", text))
        has_urls = bool(re.search(r"https?://", text))
        has_email = bool(
            re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
        )

        # Technical content detection
        tech_keywords = [
            "algorithm",
            "machine learning",
            "ai",
            "neural",
            "network",
            "data",
            "model",
            "programming",
            "code",
            "software",
            "computer",
            "technology",
            "digital",
        ]
        tech_score = sum(
            1 for keyword in tech_keywords if keyword.lower() in text.lower()
        ) / len(tech_keywords)

        # Content hash for deduplication
        content_hash = hashlib.md5(text.encode()).hexdigest()

        return {
            # Text statistics
            "word_count": word_count,
            "sentence_count": sentence_count,
            "char_count": char_count,
            "char_count_no_spaces": char_count_no_spaces,
            "avg_word_length": float(avg_word_length),
            "avg_sentence_length": float(avg_sentence_length),
            # Content patterns
            "has_numbers": has_numbers,
            "has_special_chars": has_special_chars,
            "has_urls": has_urls,
            "has_email": has_email,
            "tech_score": float(tech_score),
            # Identification
            "content_hash": content_hash,
            "text_preview": text[:100],
            "text_suffix": text[-50:] if len(text) > 50 else text,
        }

    def store_embedding_in_qdrant(
        self, text: str, embedding: List[float], metadata: Dict[str, Any] = None
    ) -> str:
        """Store embedding in Qdrant with comprehensive metadata and return the point ID."""

        try:
            # Generate unique ID for this embedding
            point_id = str(uuid.uuid4())

            # Generate comprehensive text metadata
            text_metadata = self.generate_text_metadata(text)

            # Calculate embedding statistics
            embedding_array = np.array(embedding)
            embedding_metadata = {
                "embedding_dimension": len(embedding),
                "embedding_mean": float(np.mean(embedding_array)),
                "embedding_std": float(np.std(embedding_array)),
                "embedding_min": float(np.min(embedding_array)),
                "embedding_max": float(np.max(embedding_array)),
                "embedding_norm": float(np.linalg.norm(embedding_array)),
                "embedding_non_zero_count": int(np.count_nonzero(embedding_array)),
                "embedding_hash": hashlib.md5(str(embedding).encode()).hexdigest()[:16],
            }

            # Prepare comprehensive payload
            payload = {
                # Core data
                "text": text,
                "model": self.model_name,
                "timestamp": datetime.now().isoformat(),
                "point_id": point_id,
                # Text metadata
                **text_metadata,
                # Embedding metadata
                **embedding_metadata,
                # Custom metadata from caller
                **(metadata or {}),
            }

            # Prepare point data
            point = models.PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )

            # Store in Qdrant
            operation_result = self.qdrant_client.upsert(
                collection_name=self.collection_name, points=[point]
            )

            # Log detailed operation result status
            logger.info("📊 Qdrant upsert operation result:")
            logger.info(
                f"   🔹 Status: {operation_result.status if hasattr(operation_result, 'status') else 'Unknown'}"
            )
            logger.info(
                f"   🔹 Operation ID: {operation_result.operation_id if hasattr(operation_result, 'operation_id') else 'N/A'}"
            )

            if operation_result:
                logger.success("💾 Successfully stored embedding in Qdrant:")
                logger.info(f"   🔹 Point ID: {point_id}")
                logger.info(
                    f"   🔹 Text preview: '{text[:50]}{'...' if len(text) > 50 else ''}'"
                )
                logger.info(f"   🔹 Vector dimension: {len(embedding)}")
                logger.info(f"   🔹 Collection: {self.collection_name}")
                return point_id
            else:
                logger.error(
                    "❌ FATAL: Qdrant upsert operation failed - operation_result is falsy"
                )
                raise SystemExit("Qdrant upsert operation failed")
        except Exception as e:
            logger.error(f"❌ FATAL: Failed to store embedding in Qdrant: {str(e)}")
            raise SystemExit(f"Qdrant storage failed: {str(e)}")

    def search_similar_embeddings(
        self,
        query_embedding: List[float],
        limit: int = 5,
        metadata_filter: Dict[str, Any] = None,
    ) -> List[Dict]:
        """Search for similar embeddings in Qdrant with optional metadata filtering."""

        try:
            # First verify the collection exists and has points
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            points_count = collection_info.points_count or 0

            if points_count == 0:
                logger.error(
                    f"❌ FATAL: Collection '{self.collection_name}' is empty - no points to search"
                )
                raise SystemExit(f"Collection is empty: {self.collection_name}")

            logger.info(
                f"🔍 Searching collection '{self.collection_name}' with {points_count} points"
            )

            # Build query filter from metadata_filter
            query_filter = None
            if metadata_filter:
                query_filter = self._build_metadata_filter(metadata_filter)
                logger.info(f"🔍 Applying metadata filter: {metadata_filter}")

            search_result = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=limit,
                query_filter=query_filter,
            )

            similar_embeddings = []
            for point in search_result.points:
                result_data = {
                    "point_id": point.id,
                    "score": point.score,
                    "text": point.payload.get("text", ""),
                    "model": point.payload.get("model", ""),
                    "timestamp": point.payload.get("timestamp", ""),
                    # Enhanced metadata
                    "word_count": point.payload.get("word_count", 0),
                    "tech_score": point.payload.get("tech_score", 0),
                    "has_numbers": point.payload.get("has_numbers", False),
                    "embedding_dimension": point.payload.get("embedding_dimension", 0),
                    "test_type": point.payload.get("test_type", "unknown"),
                    "content_hash": point.payload.get("content_hash", ""),
                }
                similar_embeddings.append(result_data)

            logger.success("🔍 Qdrant similarity search completed:")
            logger.info(f"   🔹 Query vector dimension: {len(query_embedding)}")
            logger.info(f"   🔹 Results found: {len(similar_embeddings)}")
            logger.info(f"   🔹 Search limit: {limit}")
            logger.info(f"   🔹 Collection: {self.collection_name}")
            if metadata_filter:
                logger.info(f"   🔹 Metadata filter applied: {metadata_filter}")
            return similar_embeddings
        except Exception as e:
            logger.error(f"❌ FATAL: Failed to search similar embeddings: {str(e)}")
            raise SystemExit(f"Qdrant similarity search failed: {str(e)}")

    def _build_metadata_filter(self, metadata_filter: Dict[str, Any]) -> models.Filter:
        """Build Qdrant filter from metadata criteria."""
        conditions = []

        for key, value in metadata_filter.items():
            if isinstance(value, dict):
                # Handle range queries like {"word_count": {"gte": 10, "lte": 50}}
                for operator, filter_value in value.items():
                    if operator == "gte":
                        conditions.append(
                            models.FieldCondition(
                                key=key, range=models.Range(gte=filter_value)
                            )
                        )
                    elif operator == "lte":
                        conditions.append(
                            models.FieldCondition(
                                key=key, range=models.Range(lte=filter_value)
                            )
                        )
                    elif operator == "gt":
                        conditions.append(
                            models.FieldCondition(
                                key=key, range=models.Range(gt=filter_value)
                            )
                        )
                    elif operator == "lt":
                        conditions.append(
                            models.FieldCondition(
                                key=key, range=models.Range(lt=filter_value)
                            )
                        )
            elif isinstance(value, list):
                # Handle array matching like {"test_type": ["single_embedding", "batch_embedding"]}
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchAny(any=value))
                )
            else:
                # Handle exact matching
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )

        return models.Filter(must=conditions) if conditions else None

    def search_by_metadata_only(
        self, metadata_filter: Dict[str, Any], limit: int = 10
    ) -> List[Dict]:
        """Search for embeddings based purely on metadata criteria without vector similarity."""
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            points_count = collection_info.points_count or 0

            if points_count == 0:
                logger.error(f"❌ Collection '{self.collection_name}' is empty")
                return []

            logger.info(
                f"🔍 Metadata-only search in collection '{self.collection_name}' with {points_count} points"
            )
            logger.info(f"🔍 Filter criteria: {metadata_filter}")

            query_filter = self._build_metadata_filter(metadata_filter)

            # Use scroll to get points matching metadata criteria
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,  # We don't need vectors for metadata search
            )

            results = []
            for point in scroll_result[0]:  # scroll returns (points, next_page_offset)
                result_data = {
                    "point_id": point.id,
                    "text": point.payload.get("text", ""),
                    "model": point.payload.get("model", ""),
                    "timestamp": point.payload.get("timestamp", ""),
                    "word_count": point.payload.get("word_count", 0),
                    "sentence_count": point.payload.get("sentence_count", 0),
                    "tech_score": point.payload.get("tech_score", 0),
                    "has_numbers": point.payload.get("has_numbers", False),
                    "has_urls": point.payload.get("has_urls", False),
                    "embedding_dimension": point.payload.get("embedding_dimension", 0),
                    "test_type": point.payload.get("test_type", "unknown"),
                    "content_hash": point.payload.get("content_hash", ""),
                }
                results.append(result_data)

            logger.success(
                f"🔍 Metadata search completed: {len(results)} results found"
            )
            return results

        except Exception as e:
            logger.error(f"❌ Failed to search by metadata: {str(e)}")
            return []

    def get_collection_metadata_stats(self) -> Dict[str, Any]:
        """Get statistics about metadata in the collection."""
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            points_count = collection_info.points_count or 0

            if points_count == 0:
                return {"error": "Collection is empty"}

            # Get a sample of points to analyze metadata
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=min(100, points_count),  # Sample up to 100 points
                with_payload=True,
                with_vectors=False,
            )

            points = scroll_result[0]

            # Analyze metadata statistics
            word_counts = [
                p.payload.get("word_count", 0)
                for p in points
                if p.payload.get("word_count")
            ]
            tech_scores = [
                p.payload.get("tech_score", 0)
                for p in points
                if p.payload.get("tech_score")
            ]
            test_types = [p.payload.get("test_type", "unknown") for p in points]
            has_numbers_count = sum(
                1 for p in points if p.payload.get("has_numbers", False)
            )
            has_urls_count = sum(1 for p in points if p.payload.get("has_urls", False))

            stats = {
                "total_points": points_count,
                "sample_size": len(points),
                "word_count_stats": {
                    "min": min(word_counts) if word_counts else 0,
                    "max": max(word_counts) if word_counts else 0,
                    "mean": np.mean(word_counts) if word_counts else 0,
                    "std": np.std(word_counts) if word_counts else 0,
                },
                "tech_score_stats": {
                    "min": min(tech_scores) if tech_scores else 0,
                    "max": max(tech_scores) if tech_scores else 0,
                    "mean": np.mean(tech_scores) if tech_scores else 0,
                },
                "content_flags": {
                    "has_numbers_percentage": (
                        (has_numbers_count / len(points) * 100) if points else 0
                    ),
                    "has_urls_percentage": (
                        (has_urls_count / len(points) * 100) if points else 0
                    ),
                },
                "test_type_distribution": {
                    test_type: test_types.count(test_type)
                    for test_type in set(test_types)
                },
            }

            logger.success(
                f"📊 Collection metadata statistics computed from {len(points)} points"
            )
            return stats

        except Exception as e:
            logger.error(f"❌ Failed to get metadata stats: {str(e)}")
            return {"error": str(e)}

    async def test_qdrant_similarity_search(self) -> None:
        """Test Qdrant similarity search functionality."""

        logger.info("🔍 Testing Qdrant similarity search functionality")

        # Multiple search queries to test different domains
        search_queries = [
            "Machine learning and artificial intelligence",
            "Computer vision and image processing",
            "Natural language processing techniques",
            "Cloud computing and distributed systems",
        ]

        all_search_results = []

        for query_text in search_queries:
            logger.info(f"\n🔎 Searching for: '{query_text}'")

            # Generate embedding for search query
            search_result = await self.test_single_embedding(query_text)

            if not search_result["success"]:
                logger.error(
                    f"❌ Failed to generate embedding for search query: '{query_text}'"
                )
                continue

            # Search for similar embeddings
            similar_embeddings = self.search_similar_embeddings(
                search_result["embedding"],
                limit=5,  # Increased limit for more results
            )

            # Display results with detailed logging
            if similar_embeddings:
                logger.success(
                    f"✅ Found {len(similar_embeddings)} similar embeddings:"
                )
                for i, result in enumerate(similar_embeddings, 1):
                    similarity_percentage = result["score"] * 100
                    logger.info(
                        f"   {i}. [{similarity_percentage:.1f}%] '{result['text'][:60]}{'...' if len(result['text']) > 60 else ''}'"
                    )
                    logger.info(
                        f"      ID: {result['point_id']}, Length: {result['text_length']} chars"
                    )
            else:
                logger.warning(f"⚠️ No similar embeddings found for: '{query_text}'")

            # Log the results
            search_data = {
                "query_text": query_text,
                "query_embedding_id": search_result.get("qdrant_point_id"),
                "similar_embeddings": similar_embeddings,
                "search_successful": len(similar_embeddings) > 0,
                "results_count": len(similar_embeddings),
            }

            all_search_results.append(search_data)

        # Log comprehensive search results
        self.log_test_result(
            "qdrant_similarity_search",
            {
                "total_queries": len(search_queries),
                "successful_searches": len(
                    [r for r in all_search_results if r["search_successful"]]
                ),
                "total_results_found": sum(
                    r["results_count"] for r in all_search_results
                ),
                "individual_searches": all_search_results,
            },
        )

        # Summary logging
        successful_searches = len(
            [r for r in all_search_results if r["search_successful"]]
        )
        total_results = sum(r["results_count"] for r in all_search_results)
        logger.success(
            f"🎯 Similarity search summary: {successful_searches}/{len(search_queries)} queries successful, {total_results} total results found"
        )

    async def test_single_embedding(self, text: str) -> Dict[str, Any]:
        """Test embedding generation for a single text."""
        try:
            logger.info(f"Generating embedding for text: '{text[:50]}...'")
            start_time = time.time()

            response = await self.client.embed(model=self.model_name, input=text)

            end_time = time.time()

            if "embeddings" in response and len(response["embeddings"]) > 0:
                embedding = response["embeddings"][0]
                embedding_length = len(embedding)

                logger.success("Embedding generated successfully")
                logger.info(f"   Vector dimension: {embedding_length}")
                logger.info(f"   Generation time: {end_time - start_time:.2f}s")

                # Calculate basic statistics
                embedding_array = np.array(embedding)
                stats = {
                    "dimension": embedding_length,
                    "mean": float(np.mean(embedding_array)),
                    "std": float(np.std(embedding_array)),
                    "min": float(np.min(embedding_array)),
                    "max": float(np.max(embedding_array)),
                    "norm": float(np.linalg.norm(embedding_array)),
                    "generation_time": end_time - start_time,
                }

                # Store in Qdrant - MANDATORY
                # Setup collection on first embedding (we now know the dimension)
                if not hasattr(self, "_qdrant_setup_done"):
                    self.setup_qdrant_collection(embedding_length)
                    self._qdrant_setup_done = True

                # Store embedding with metadata
                qdrant_point_id = self.store_embedding_in_qdrant(
                    text,
                    embedding,
                    {"test_type": "single_embedding"},
                )

                result = {
                    "success": True,
                    "embedding": embedding,
                    "stats": stats,
                    "text_length": len(text),
                    "text_preview": text[:100],  # Store first 100 chars for reference
                    "qdrant_point_id": qdrant_point_id,
                }

                # Log the test result with optional full embedding
                log_data = {
                    "input_text": text,
                    "success": True,
                    "embedding_dimension": stats["dimension"],
                    "generation_time": stats["generation_time"],
                    "embedding_stats": stats,
                    "text_length": len(text),
                    "qdrant_point_id": qdrant_point_id,
                }

                if self.include_embeddings:
                    log_data["embedding_vector"] = (
                        embedding  # Store the actual embedding vector
                    )

                self.log_test_result("single_embedding", log_data)

                return result
            else:
                logger.error("No embeddings returned in response")
                error_result = {"success": False, "error": "No embeddings in response"}

                # Log the failed test
                self.log_test_result(
                    "single_embedding",
                    {
                        "input_text": text,
                        "success": False,
                        "error": "No embeddings in response",
                        "text_length": len(text),
                    },
                )

                return error_result

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            error_result = {"success": False, "error": str(e)}

            # Log the failed test
            self.log_test_result(
                "single_embedding",
                {
                    "input_text": text,
                    "success": False,
                    "error": str(e),
                    "text_length": len(text),
                },
            )

            return error_result

    async def test_batch_embeddings(self, texts: List[str]) -> Dict[str, Any]:
        """Test embedding generation for multiple texts."""
        logger.info(f"Generating embeddings for {len(texts)} texts")

        results = []
        total_start = time.time()

        for i, text in enumerate(texts):
            logger.info(f"Processing text {i + 1}/{len(texts)}")
            result = await self.test_single_embedding(text)
            results.append(result)

            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.1)

        total_time = time.time() - total_start

        # Calculate batch statistics
        successful_results = [r for r in results if r["success"]]

        if successful_results:
            dimensions = [r["stats"]["dimension"] for r in successful_results]
            generation_times = [
                r["stats"]["generation_time"] for r in successful_results
            ]

            batch_stats = {
                "total_texts": len(texts),
                "successful_embeddings": len(successful_results),
                "failed_embeddings": len(texts) - len(successful_results),
                "avg_dimension": np.mean(dimensions),
                "avg_generation_time": np.mean(generation_times),
                "total_batch_time": total_time,
                "throughput_per_second": len(texts) / total_time,
            }

            logger.success("Batch processing completed")
            logger.info(f"   Success rate: {len(successful_results)}/{len(texts)}")
            logger.info(f"   Total time: {total_time:.2f}s")
            logger.info(
                f"   Throughput: {batch_stats['throughput_per_second']:.2f} embeddings/sec"
            )

            # Log batch results with optional full embeddings
            individual_results = []
            for text, result in zip(texts, results):
                result_data = {
                    "input_text": text,
                    "text_preview": text[:50] + "..." if len(text) > 50 else text,
                    "success": result["success"],
                    "generation_time": (
                        result.get("stats", {}).get("generation_time", 0)
                        if result["success"]
                        else 0
                    ),
                    "embedding_stats": (
                        result.get("stats") if result["success"] else None
                    ),
                    "qdrant_point_id": (
                        result.get("qdrant_point_id") if result["success"] else None
                    ),
                    "error": result.get("error") if not result["success"] else None,
                }

                if self.include_embeddings and result["success"]:
                    result_data["embedding_vector"] = result.get("embedding")

                individual_results.append(result_data)

            self.log_test_result(
                "batch_embeddings",
                {
                    "input_texts": texts,
                    "batch_stats": batch_stats,
                    "individual_results": individual_results,
                },
            )

            return {"success": True, "results": results, "batch_stats": batch_stats}
        else:
            # Log failed batch results
            individual_results = []
            for text, result in zip(texts, results):
                result_data = {
                    "input_text": text,
                    "text_preview": text[:50] + "..." if len(text) > 50 else text,
                    "success": result["success"],
                    "embedding_stats": (
                        result.get("stats") if result["success"] else None
                    ),
                    "qdrant_point_id": (
                        result.get("qdrant_point_id") if result["success"] else None
                    ),
                    "error": result.get("error") if not result["success"] else None,
                }

                if self.include_embeddings and result["success"]:
                    result_data["embedding_vector"] = result.get("embedding")

                individual_results.append(result_data)

            self.log_test_result(
                "batch_embeddings",
                {
                    "input_texts": texts,
                    "success": False,
                    "error": "All embedding generations failed",
                    "individual_results": individual_results,
                },
            )

            return {
                "success": False,
                "results": results,
                "error": "All embedding generations failed",
            }

    def calculate_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        return dot_product / (norm1 * norm2)

    async def test_similarity_analysis(self) -> None:
        """Test semantic similarity between different texts."""
        logger.info("Testing semantic similarity analysis")

        # Test texts with varying similarity levels
        test_pairs = [
            # High similarity - synonymous phrases
            ("The cat sat on the mat", "A feline rested on the carpet"),
            ("Machine learning algorithms", "Artificial intelligence models"),
            ("Deep neural networks", "Multi-layer perceptron architectures"),
            # Medium similarity - related concepts
            ("Python programming language", "JavaScript programming language"),
            ("Cloud computing infrastructure", "Distributed system architecture"),
            ("Data science methodology", "Statistical analysis techniques"),
            # Low similarity - different domains
            ("The weather is sunny today", "I love eating pizza"),
            ("Quantum physics principles", "Medieval history events"),
            ("Basketball game strategy", "Cooking recipe instructions"),
            # Technical vs. Non-technical
            ("Neural network backpropagation", "Walking in the park peacefully"),
            ("Database query optimization", "Sunset over the ocean waves"),
        ]

        similarity_results = []

        for text1, text2 in test_pairs:
            logger.info(f"Comparing: '{text1}' vs '{text2}'")

            result1 = await self.test_single_embedding(text1)
            result2 = await self.test_single_embedding(text2)

            pair_result = {
                "text1": text1,
                "text2": text2,
                "embedding1_success": result1["success"],
                "embedding2_success": result2["success"],
            }

            if result1["success"] and result2["success"]:
                similarity = self.calculate_similarity(
                    result1["embedding"], result2["embedding"]
                )
                logger.info(f"   Cosine similarity: {similarity:.4f}")

                similarity_data = {
                    "similarity_computed": True,
                    "cosine_similarity": float(similarity),
                    "embedding1_stats": result1["stats"],
                    "embedding2_stats": result2["stats"],
                    "embedding1_qdrant_id": result1.get("qdrant_point_id"),
                    "embedding2_qdrant_id": result2.get("qdrant_point_id"),
                }

                if self.include_embeddings:
                    similarity_data.update(
                        {
                            "embedding1_vector": result1["embedding"],
                            "embedding2_vector": result2["embedding"],
                        }
                    )

                pair_result.update(similarity_data)
            else:
                logger.warning(
                    "   Failed to compute similarity - embedding generation failed"
                )
                pair_result.update(
                    {
                        "similarity_computed": False,
                        "error": "Embedding generation failed",
                        "embedding1_error": (
                            result1.get("error") if not result1["success"] else None
                        ),
                        "embedding2_error": (
                            result2.get("error") if not result2["success"] else None
                        ),
                    }
                )

            similarity_results.append(pair_result)
            print()  # Add spacing between comparisons

        # Log all similarity analysis results
        self.log_test_result(
            "similarity_analysis",
            {
                "test_pairs": similarity_results,
                "total_pairs": len(test_pairs),
                "successful_comparisons": len(
                    [r for r in similarity_results if r["similarity_computed"]]
                ),
                "average_similarity": (
                    np.mean(
                        [
                            r["cosine_similarity"]
                            for r in similarity_results
                            if r.get("cosine_similarity")
                        ]
                    )
                    if any(r.get("cosine_similarity") for r in similarity_results)
                    else None
                ),
            },
        )

    async def test_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        try:
            # Try to get model information if available
            logger.info(f"Checking model information for {self.model_name}")

            # Test with a simple text to verify model is accessible
            test_result = await self.test_single_embedding("Test embedding")

            if test_result["success"]:
                model_info = {
                    "model_name": self.model_name,
                    "ollama_url": self.ollama_url,
                    "vector_dimension": test_result["stats"]["dimension"],
                    "model_accessible": True,
                }

                # Log model info
                self.log_test_result("model_info", model_info)
                return model_info
            else:
                model_info = {
                    "model_name": self.model_name,
                    "ollama_url": self.ollama_url,
                    "model_accessible": False,
                    "error": test_result.get("error", "Unknown error"),
                }

                # Log failed model info
                self.log_test_result("model_info", model_info)
                return model_info

        except Exception as e:
            logger.error(f"Failed to get model info: {str(e)}")
            model_info = {
                "model_name": self.model_name,
                "ollama_url": self.ollama_url,
                "model_accessible": False,
                "error": str(e),
            }

            # Log failed model info
            self.log_test_result("model_info", model_info)
            return model_info

    async def test_metadata_storage_and_search(self) -> None:
        """Test comprehensive metadata storage and search functionality."""
        logger.info("🔍 Testing metadata storage and search functionality")

        # Test texts with different characteristics for metadata analysis
        test_texts_with_metadata = [
            {
                "text": "Machine learning algorithms process data efficiently using neural networks and deep learning techniques.",
                "expected_metadata": {"test_type": "tech_content", "category": "AI"},
            },
            {
                "text": "The weather is sunny today! Temperature is 25°C. Perfect for a walk in the park.",
                "expected_metadata": {
                    "test_type": "casual_content",
                    "category": "weather",
                },
            },
            {
                "text": "Email me at test@example.com or visit https://example.com for more information about our services.",
                "expected_metadata": {
                    "test_type": "contact_content",
                    "category": "business",
                },
            },
            {
                "text": "Short text",
                "expected_metadata": {
                    "test_type": "short_content",
                    "category": "minimal",
                },
            },
            {
                "text": "This is a very long text with many words that should result in higher word count statistics. "
                * 10,
                "expected_metadata": {
                    "test_type": "long_content",
                    "category": "verbose",
                },
            },
        ]

        stored_points = []

        # Store embeddings with custom metadata
        logger.info(
            f"📊 Storing {len(test_texts_with_metadata)} test embeddings with metadata"
        )
        for i, item in enumerate(test_texts_with_metadata):
            text = item["text"]
            custom_metadata = item["expected_metadata"]

            logger.info(f"Processing text {i + 1}: '{text[:50]}...'")
            result = await self.test_single_embedding(text)

            if result["success"]:
                # Store additional metadata beyond what's automatically generated
                enhanced_metadata = {**custom_metadata, "test_sequence": i}
                point_id = self.store_embedding_in_qdrant(
                    text, result["embedding"], enhanced_metadata
                )
                stored_points.append(
                    {
                        "point_id": point_id,
                        "text": text,
                        "metadata": enhanced_metadata,
                        "embedding": result["embedding"],
                    }
                )

        logger.success(f"✅ Stored {len(stored_points)} embeddings with metadata")

        # Test 1: Get collection metadata statistics
        logger.info("\n🔍 Test 1: Collection Metadata Statistics")
        metadata_stats = self.get_collection_metadata_stats()
        logger.info(
            f"📊 Collection stats: {json.dumps(metadata_stats, indent=2, default=str)}"
        )

        # Test 2: Search by metadata only (no vector similarity)
        logger.info("\n🔍 Test 2: Metadata-Only Search")

        metadata_searches = [
            {"test_type": "tech_content"},
            {"category": "weather"},
            {"has_numbers": True},
            {"has_urls": True},
            {"word_count": {"gte": 10, "lte": 50}},
            {"tech_score": {"gt": 0.1}},
        ]

        for search_filter in metadata_searches:
            logger.info(f"Searching with filter: {search_filter}")
            results = self.search_by_metadata_only(search_filter, limit=5)
            logger.info(f"Found {len(results)} results")
            for result in results:
                logger.info(
                    f"  - '{result['text'][:60]}...' (words: {result['word_count']}, tech: {result['tech_score']:.2f})"
                )

        # Test 3: Combined vector + metadata search
        logger.info("\n🔍 Test 3: Combined Vector + Metadata Search")

        if stored_points:
            # Use first stored embedding as query
            query_embedding = stored_points[0]["embedding"]

            # Search with different metadata filters
            combined_searches = [
                {"test_type": "tech_content"},
                {"word_count": {"gte": 5}},
                {"has_numbers": False},
            ]

            for metadata_filter in combined_searches:
                logger.info(f"Vector search with metadata filter: {metadata_filter}")
                results = self.search_similar_embeddings(
                    query_embedding, limit=3, metadata_filter=metadata_filter
                )
                logger.info(f"Found {len(results)} results")
                for result in results:
                    logger.info(
                        f"  - Score: {result['score']:.3f}, '{result['text'][:60]}...'"
                    )

        # Test 4: Metadata analysis and insights
        logger.info("\n🔍 Test 4: Metadata Analysis")

        # Find embeddings with specific characteristics
        tech_embeddings = self.search_by_metadata_only({"tech_score": {"gte": 0.2}})
        short_embeddings = self.search_by_metadata_only({"word_count": {"lte": 5}})
        url_embeddings = self.search_by_metadata_only({"has_urls": True})

        logger.info("📊 Analysis results:")
        logger.info(f"  - High tech content: {len(tech_embeddings)} embeddings")
        logger.info(f"  - Short texts: {len(short_embeddings)} embeddings")
        logger.info(f"  - Contains URLs: {len(url_embeddings)} embeddings")

        # Log comprehensive test results
        self.log_test_result(
            "metadata_storage_and_search",
            {
                "test_texts_count": len(test_texts_with_metadata),
                "stored_points_count": len(stored_points),
                "collection_metadata_stats": metadata_stats,
                "metadata_only_searches": len(metadata_searches),
                "combined_searches": len(combined_searches),
                "analysis_results": {
                    "high_tech_content": len(tech_embeddings),
                    "short_texts": len(short_embeddings),
                    "contains_urls": len(url_embeddings),
                },
                "stored_point_ids": [p["point_id"] for p in stored_points],
            },
        )

        logger.success("✅ Metadata storage and search testing completed")

    async def test_advanced_metadata_queries(self) -> None:
        """Test advanced metadata query capabilities."""
        logger.info("🔍 Testing advanced metadata query capabilities")

        # Test complex range queries
        logger.info("\n📊 Testing range queries")
        range_queries = [
            {"word_count": {"gte": 10, "lte": 20}},  # Medium length texts
            {"tech_score": {"gt": 0.0, "lt": 0.5}},  # Low-medium tech content
            {"embedding_norm": {"gte": 1.0}},  # Normalized embeddings
        ]

        for query in range_queries:
            results = self.search_by_metadata_only(query, limit=10)
            logger.info(f"Range query {query}: {len(results)} results")

        # Test multiple condition queries
        logger.info("\n📊 Testing multiple condition queries")
        complex_query = {
            "test_type": ["tech_content", "contact_content"],  # Multiple values
            "word_count": {"gte": 5},  # Range condition
            "has_numbers": True,  # Boolean condition
        }

        complex_results = self.search_by_metadata_only(complex_query, limit=10)
        logger.info(f"Complex query: {len(complex_results)} results")

        for result in complex_results:
            logger.info(
                f"  - {result['test_type']}: '{result['text'][:50]}...' ({result['word_count']} words)"
            )

        # Test content analysis patterns
        logger.info("\n📊 Testing content pattern analysis")
        patterns = [
            {"has_urls": True, "has_email": True},  # Contact information
            {
                "tech_score": {"gte": 0.3},
                "word_count": {"gte": 10},
            },  # Substantial tech content
            {
                "sentence_count": {"gte": 3},
                "avg_word_length": {"gte": 5},
            },  # Detailed content
        ]

        pattern_results = {}
        for i, pattern in enumerate(patterns):
            results = self.search_by_metadata_only(pattern, limit=20)
            pattern_results[f"pattern_{i + 1}"] = len(results)
            logger.info(f"Pattern {i + 1} {pattern}: {len(results)} results")

        # Log advanced query test results
        self.log_test_result(
            "advanced_metadata_queries",
            {
                "range_queries_tested": len(range_queries),
                "complex_query_results": len(complex_results),
                "pattern_analysis": pattern_results,
                "total_query_types": len(range_queries) + 1 + len(patterns),
            },
        )

        logger.success("✅ Advanced metadata query testing completed")


async def run_comprehensive_tests():
    """Run all embedding tests."""
    logger.info("Starting comprehensive Ollama embedding tests")

    tester = OllamaEmbeddingTester()

    # Test 1: Model accessibility
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Model Information & Accessibility")
    logger.info("=" * 60)
    model_info = await tester.test_model_info()
    logger.info(f"Model info: {model_info}")

    if not model_info.get("model_accessible", False):
        logger.error("Model not accessible. Cannot proceed with further tests.")
        logger.error(f"Error: {model_info.get('error', 'Unknown error')}")
        return

    # Test 2: Single embedding
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Single Embedding Generation")
    logger.info("=" * 60)
    single_result = await tester.test_single_embedding(
        "This is a test sentence for embedding generation."
    )

    # Test 3: Batch embeddings
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Batch Embedding Generation")
    logger.info("=" * 60)
    test_texts = [
        "Artificial intelligence is transforming technology.",
        "Machine learning models require large datasets.",
        "Natural language processing enables text understanding.",
        "Deep learning neural networks are powerful tools.",
        "Computer vision can analyze images automatically.",
        "Reinforcement learning trains agents through rewards.",
        "Large language models understand human text.",
        "Data science combines statistics and programming.",
        "Cloud computing provides scalable infrastructure.",
        "Blockchain technology ensures secure transactions.",
        "Internet of Things connects everyday devices.",
        "Quantum computing promises exponential speedups.",
        "Cybersecurity protects against digital threats.",
        "Big data analytics reveals hidden patterns.",
        "Edge computing processes data locally.",
        "Virtual reality creates immersive experiences.",
        "Augmented reality overlays digital information.",
        "5G networks enable ultra-fast connectivity.",
        "Autonomous vehicles navigate without drivers.",
        "Robotics automates physical tasks efficiently.",
    ]
    logger.info(
        f"📊 Generating embeddings for {len(test_texts)} diverse technology texts"
    )
    batch_result = await tester.test_batch_embeddings(test_texts)

    # Test 4: Similarity analysis
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Semantic Similarity Analysis")
    logger.info("=" * 60)
    await tester.test_similarity_analysis()

    # Test 5: Qdrant similarity search
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Qdrant Similarity Search")
    logger.info("=" * 60)
    await tester.test_qdrant_similarity_search()

    # Test 6: Metadata storage and search
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Metadata Storage and Search")
    logger.info("=" * 60)
    await tester.test_metadata_storage_and_search()

    # Test 7: Advanced metadata queries
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Advanced Metadata Queries")
    logger.info("=" * 60)
    await tester.test_advanced_metadata_queries()

    # Test 8: Final Qdrant collection status
    logger.info("\n" + "=" * 60)
    logger.info("TEST 8: Final Qdrant Collection Status")
    logger.info("=" * 60)

    try:
        final_collection_info = tester.qdrant_client.get_collection(
            tester.collection_name
        )
        final_count = final_collection_info.points_count or 0
        logger.success("📊 Final Qdrant collection status:")
        logger.info(f"   🔹 Collection: {tester.collection_name}")
        logger.info(f"   🔹 Total embeddings stored: {final_count}")
        logger.info(
            f"   🔹 Vector dimension: {final_collection_info.config.params.vectors.size}"
        )
        logger.info(
            f"   🔹 Distance metric: {final_collection_info.config.params.vectors.distance}"
        )

        tester.log_test_result(
            "final_collection_status",
            {
                "collection_name": tester.collection_name,
                "total_points": final_count,
                "vector_dimension": final_collection_info.config.params.vectors.size,
                "distance_metric": str(
                    final_collection_info.config.params.vectors.distance
                ),
            },
        )
    except Exception as e:
        logger.error(f"❌ FATAL: Failed to get final collection status: {str(e)}")
        raise SystemExit(f"Qdrant collection status check failed: {str(e)}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.success(f"✅ Model: {model_info['model_name']}")
    logger.success(f"✅ Ollama URL: {model_info['ollama_url']}")
    logger.success(
        f"✅ Vector Dimension: {model_info.get('vector_dimension', 'Unknown')}"
    )

    logger.success(f"✅ Qdrant URL: {tester.qdrant_url}")
    logger.success(f"✅ Qdrant Collection: {tester.collection_name}")

    if single_result["success"]:
        logger.success(
            f"✅ Single embedding: {single_result['stats']['generation_time']:.2f}s"
        )
    else:
        logger.error(f"❌ Single embedding failed: {single_result.get('error')}")

    if batch_result["success"]:
        stats = batch_result["batch_stats"]
        logger.success(
            f"✅ Batch embeddings: {stats['successful_embeddings']}/{stats['total_texts']} successful"
        )
        logger.success(
            f"✅ Batch throughput: {stats['throughput_per_second']:.2f} embeddings/sec"
        )

        successful_stores = len(
            [
                t
                for t in tester.test_results["tests"]
                if t["test_type"] == "single_embedding"
                and t["data"].get("qdrant_point_id") is not None
            ]
        )
        logger.success(
            f"✅ Qdrant storage: {successful_stores} embeddings successfully stored"
        )
    else:
        logger.error(f"❌ Batch embeddings failed: {batch_result.get('error')}")

    # Save all test results to file
    tester.save_results_to_file()
    logger.success(f"💾 All test results saved to: {tester.log_file}")

    logger.success(
        f"🔍 Qdrant embeddings available for similarity search in collection: {tester.collection_name}"
    )


if __name__ == "__main__":
    # Run the tests
    asyncio.run(run_comprehensive_tests())
