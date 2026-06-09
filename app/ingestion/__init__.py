"""Ingestion layer: source seam, normalization, deterministic metadata, persistence.

Owns the normalized review schema and the deterministic ingestion_run metadata
(ingestion.md). Q&A and summary read what this layer commits; they never recompute
counts or redefine the schema.
"""
