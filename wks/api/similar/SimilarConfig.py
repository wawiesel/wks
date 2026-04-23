"""Configuration for document similarity."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _NearDuplicateConfig(BaseModel):
    """Thresholds for near-duplicate classification."""

    model_config = ConfigDict(extra="forbid")

    min_matched_chunks: int = Field(default=2, ge=1)
    min_coverage_query: float = Field(default=0.8, ge=0.0, le=1.0)
    min_coverage_candidate: float = Field(default=0.8, ge=0.0, le=1.0)
    min_mean_similarity: float = Field(default=0.88, ge=0.0, le=1.0)
    min_order_consistency: float = Field(default=0.8, ge=0.0, le=1.0)


class _SameDocumentFamilyConfig(BaseModel):
    """Thresholds for document-lineage classification."""

    model_config = ConfigDict(extra="forbid")

    min_coverage_query: float = Field(default=0.35, ge=0.0, le=1.0)
    min_max_similarity: float = Field(default=0.88, ge=0.0, le=1.0)
    min_stem_similarity: float = Field(default=0.75, ge=0.0, le=1.0)
    support_min_stem_similarity: float = Field(default=0.5, ge=0.0, le=1.0)
    support_min_path_similarity: float = Field(default=0.35, ge=0.0, le=1.0)
    export_pair_min_stem_similarity: float = Field(default=0.9, ge=0.0, le=1.0)


class _TopicRelatedConfig(BaseModel):
    """Thresholds for weaker topical similarity."""

    model_config = ConfigDict(extra="forbid")

    min_matched_chunks: int = Field(default=1, ge=1)
    min_coverage_query: float = Field(default=0.2, ge=0.0, le=1.0)
    min_mean_similarity: float = Field(default=0.72, ge=0.0, le=1.0)
    min_max_similarity: float = Field(default=0.82, ge=0.0, le=1.0)


class _ScoreWeightsConfig(BaseModel):
    """Ranking weights after label classification."""

    model_config = ConfigDict(extra="forbid")

    mean_similarity: float = Field(default=0.35, ge=0.0)
    coverage_query: float = Field(default=0.2, ge=0.0)
    coverage_candidate: float = Field(default=0.1, ge=0.0)
    order_consistency: float = Field(default=0.1, ge=0.0)
    stem_similarity: float = Field(default=0.1, ge=0.0)
    path_similarity: float = Field(default=0.05, ge=0.0)
    seed_score: float = Field(default=0.1, ge=0.0)
    seed_scale: float = Field(default=60.0, gt=0.0)

    @model_validator(mode="after")
    def validate_weight_sum(self) -> "_ScoreWeightsConfig":
        total = (
            self.mean_similarity
            + self.coverage_query
            + self.coverage_candidate
            + self.order_consistency
            + self.stem_similarity
            + self.path_similarity
            + self.seed_score
        )
        if total <= 0.0:
            raise ValueError("similar.score_weights must have positive total weight")
        return self


class SimilarConfig(BaseModel):
    """Top-level defaults and thresholds for document similarity."""

    model_config = ConfigDict(extra="forbid")

    default_index: str = ""
    top: int = Field(default=10, ge=1)
    per_chunk: int = Field(default=5, ge=1)
    candidates: int = Field(default=25, ge=1)
    heartbeat_secs: float = Field(default=5.0, gt=0.0)
    match_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    rrf_k: float = Field(default=60.0, gt=0.0)
    evidence_limit: int = Field(default=3, ge=1)
    evidence_chars: int = Field(default=120, ge=16)
    export_pairs: list[list[str]] = [
        [".docx", ".pdf"],
        [".md", ".pdf"],
        [".pptx", ".pdf"],
        [".xlsx", ".pdf"],
    ]
    near_duplicate: _NearDuplicateConfig = _NearDuplicateConfig()
    same_document_family: _SameDocumentFamilyConfig = _SameDocumentFamilyConfig()
    topic_related: _TopicRelatedConfig = _TopicRelatedConfig()
    score_weights: _ScoreWeightsConfig = _ScoreWeightsConfig()

    @field_validator("export_pairs")
    @classmethod
    def validate_export_pairs(cls, value: list[list[str]]) -> list[list[str]]:
        """Require each export pair to contain exactly two suffix strings."""
        for pair in value:
            if len(pair) != 2:
                raise ValueError("similar.export_pairs entries must contain exactly two suffix strings")
            if any(not suffix.strip() for suffix in pair):
                raise ValueError("similar.export_pairs suffixes must be non-empty")
        return value
