import sys
import os
import pathlib
import threading

# Add the path to A_GIS to the sys.path if necessary
sys.path.append("/Users/ww5/a-gis/source")

import A_GIS

logger = A_GIS.Log.get_sublogger(name='file-monitor-daemon',file_name="/Users/ww5/bin/file-monitor-daemon.log")

for status in A_GIS.File.Database.monitor(
		root_dir=pathlib.Path("/Users/ww5/Desktop/stacks"),
		should_ignore=A_GIS.File.should_ignore(
			ignore_dirs=["/Users/ww5/Library"],
			ignore_subdirs=["build", "venv"],
			only_extensions=[
				".txt",
				".docx",
				".pptx",
				".pdf",
				".py",
				".md",
				".cc",
				".hh",
				".f90",
				".cpp",
				".tex",
				".ipynb",
			],
			ignore_dot_files=True,
			logger=logger,
		),
		collection=A_GIS.File.Database.get_collection(
			name="file_changes", from_database="file_monitor"
		),
		logger=logger,
		min_bytes=100,
	):
	logger.debug(status)
