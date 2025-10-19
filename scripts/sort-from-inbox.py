import sys
# Add the path to A_GIS to the sys.path if necessary
sys.path.append("/Users/ww5/a-gis/source")

import A_GIS

import json
import pathlib
root = pathlib.Path("/Users/ww5/Desktop/stacks")
scope = A_GIS.File.read(file=root/'_root.node.md')
inbox_path = root / '_inbox'
collection='file_changes'
database='file_monitor'

# Define the log file path
log_file_path = pathlib.Path(__file__).parent / 'sort-from-inbox.log'

# Open the log file for appending output
log_file = open(log_file_path, 'a')

# Function to log messages to the file
def log(message):
    log_file.write(message + '\n')
    log_file.flush()  # Ensure the log is written to the file immediately

while True:
    files = A_GIS.File.glob(paths=[inbox_path])
    for target_file in files:
        if str(target_file.name).startswith('.'):
            continue
        log(f'sorting {target_file} ...')
        show_tree = A_GIS.File.show_tree(directory=root,max_levels=3,num_per_dir=10,ignore_dirs=['_inbox','_']).tree
        log('show tree done ...')
        content = A_GIS.File.read_to_text(path=target_file,beginchar=0,endchar=4999).text
        log('read done ...')
        chatbot = A_GIS.Ai.Chatbot.init(system=f'''
        You are an AI that distributes files into a directory structure. 
        
        Summarize your thought process before calling functions. 
        
        You should start in the root directory {root}. You can use the 
        A_GIS.File.show_tree function to understand the existing structure.
        Note that A_GIS.File.show_tree does not show all files by default.
        
        You can use the A_GIS.File.read_to_text function to read any file.
        
        This STACKS archive file structure contains root, trunk, branch, and leaf nodes.
        A leaf node is a directory which contains a logical grouping of files. 
        The _leaf.node.md file in a lead node directory explains the scope of that
        leaf node. The branch node is a directory where leaf nodes may be placed, 
        where _branch.node.md explains the content of the branch. Trunk nodes provide
        the user-specified organization and should in general not be changed. 
        
        You will have to decide whether to put a file in an existing leaf node or
        create a new leaf node in a branch node.
        
        You must move the file out of the _inbox.
        
        You should use the A_GIS.File.Database.get_nearest function to determine 
        the top nearest files by similarity where 1.0 is completely similar
        and 0.0 is not similar. If there is a very close file, it will have an 
        similarity of 0.9 or more but even lower similarities can help identify
        approximately where to place files. If you find very similar files in an
        existing leaf node you should move the file to the leaf node instead of
        creating a new leaf.
        
        When you use the A_GIS.File.Database.get_nearest function, use arguments
        
            collection_name='{collection}'
            database_name='{database}'
        
        Here's the scope for this STACKS archive from {root}/_root.node.md:
        
        {scope}
        
        Use the A_GIS.File.Node.move function to move the file to a 
        specific directory.
        
        ''',
            model='qwen2.5:14b',
            tool_names=["A_GIS.File.read_to_text",
                        "A_GIS.File.show_tree",
                        "A_GIS.File.Database.get_nearest",
                        "A_GIS.File.Node.move"],
            num_predict=4000,
            num_ctx=20000,
        )
        log('chat initiated ...')
        
        result = chatbot.chat(message=f'''Please distribute the target_file={target_file}.
        The content of the first 5000 characters is:
        {content}
        
        The contents of {root} is using show_tree(max_levels=3,num_per_dir=10):
        {show_tree}
        
        Take your time and use the functions at your disposal to make a well-informed decision.''')
        
        log(result.messages[-1]['content'])
        