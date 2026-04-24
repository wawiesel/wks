from .output_models import output_model

ConfigListOutput = output_model("ConfigListOutput", "section", "content", "config_path")
ConfigSetOutput = output_model("ConfigSetOutput", "key", "value", "config_path")
ConfigShowOutput = output_model("ConfigShowOutput", "section", "content", "config_path")
ConfigVersionOutput = output_model("ConfigVersionOutput", "version")

__all__ = ["ConfigListOutput", "ConfigSetOutput", "ConfigShowOutput", "ConfigVersionOutput"]
