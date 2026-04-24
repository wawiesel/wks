from wks.api.config.output_models import output_model

IndexOutput = output_model("IndexOutput", "index_name", "uri", "chunk_count", "checksum")
IndexStatusOutput = output_model("IndexStatusOutput", "indexes")
IndexAutoOutput = output_model("IndexAutoOutput", "uri", "priority", "indexed", "skipped")
IndexEmbedOutput = output_model("IndexEmbedOutput", "index_name", "embedding_model", "chunk_count", "dimensions")

__all__ = ["IndexAutoOutput", "IndexEmbedOutput", "IndexOutput", "IndexStatusOutput"]
