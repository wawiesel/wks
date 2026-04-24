from wks.api.config.output_models import output_model

CatCmdOutput = output_model("CatCmdOutput", "content", "target", "checksum", "output_path")

__all__ = ["CatCmdOutput"]
